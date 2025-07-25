#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import logging
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

from openai import OpenAI, OpenAIError
from openai.types.chat import ChatCompletion
from requests import HTTPError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)
from tiktoken import encoding_name_for_model

from aspera.completer.completer import Completer, CompletionCache
from aspera.completer.utils import (
    MAX_OUTPUT_TOKENS,
    CompletionApiError,
    CompletionTooShortError,
    LLMPrompt,
    TokenCounter,
    _request_rate_limiter,
    _token_rate_limiter,
    num_tokens_from_messages,
)
from aspera.constants import DEFAULT_CACHE_DIR

O1_MAX_COMPLETION_TOKENS = 32768

logger = logging.getLogger(__name__)


class OpenAiChatCompleter(Completer):
    """Completer for OpenAi Chat.

    Parameters
    ----------
    max_tokens
        The maximum number of tokens to complete. This
        should take into account the maximum context length
        of the model, which is the sum between the number
        of tokens in the prompt and the completion. To generate
        without a token limit, set max_tokens to -1. This
        will trigger a calculation of the max_tokens as the
        difference between the context length for the model and
        the *estimated* nb of tokens in the prompt.
    """

    def __init__(
        self,
        model_name: str = "o1-preview-2024-09-12",
        max_tokens: int = 512,
        best_of_n: int = 1,
        temperature: float = 0.7,
        timeout: float = 120,
        max_retries: int = 1,
        cache_dir: Path | None = DEFAULT_CACHE_DIR / "openai",
        max_delay: int | None = None,
        seed: int = 0,
    ):
        super().__init__(max_tokens, model_name)
        if (
            "OPENAI_API_KEY" not in os.environ
            and "OPENAI_API_KEY_PATH" not in os.environ
        ):
            raise RuntimeError(
                f"Set OPENAI_API_KEY or OPENAI_API_KEY_PATH "
                f"env variables to use {self.__class__.__name__}"
            )
        try:
            encoding_name_for_model(model_name)
        except KeyError:
            logger.warning(
                f"Cannot apply token based rate limiting to unknown model {model_name}!"
            )
        self._best_of_n = best_of_n
        self._temperature = temperature
        self._seed = seed
        self._timeout = float(timeout)
        self._max_retries = max_retries
        self._token_rate_limiter = _token_rate_limiter(model_name)
        self._request_rate_limiter = _request_rate_limiter(
            model_name, max_delay=max_delay
        )
        self._token_counter = TokenCounter(model=model_name)
        self._client = OpenAI()
        self._init_num_tokens(max_tokens)
        self._cache = CompletionCache(self._full_cache_dir(cache_dir))
        logger.info(f"Running experiment with seed {seed}")

    def _full_cache_dir(self, cache_dir: Path | None) -> Path | None:
        if cache_dir is None:
            return None
        return (
            cache_dir
            / f"chat__{self._model_name}"
            / f"mt_{self._max_tokens}_n_{self._best_of_n}__temp_{self._temperature:.3f}_seed_{self._seed}"  # noqa
        )

    def _init_num_tokens(self, max_tokens: int):
        self._max_tokens = max_tokens
        if max_tokens == -1 and self._model_name in MAX_OUTPUT_TOKENS:
            self._max_tokens = MAX_OUTPUT_TOKENS[self._model_name]

    def _transform_prompt_for_o1(self, prompt: LLMPrompt) -> LLMPrompt:
        """The o1 model preview only supports user messages at the
        time of writing."""
        prompt = deepcopy(prompt)
        for m in prompt.messages:
            if m["role"] == "system":
                m["role"] = "user"
        return prompt

    def _call(self, prompt: LLMPrompt) -> ChatCompletion:

        completer_kwargs = {
            "n": self._best_of_n,
            "timeout": self._timeout,
            "seed": self._seed,
        }
        if "o1" in self._model_name or "o3" in self._model_name:
            prompt = self._transform_prompt_for_o1(prompt)
            return self._client.chat.completions.create(
                model=self._model_name,
                messages=prompt.messages,
                # this is the only default supported by the api at the moment
                temperature=1,
                # this is a parameter specific to this model
                max_completion_tokens=O1_MAX_COMPLETION_TOKENS,
                **completer_kwargs,
            )
        return self._client.chat.completions.create(  # type: ignore[no-any-return]
            model=self._model_name,
            messages=prompt.messages,
            temperature=self._temperature,
            max_tokens=self.max_tokens,
            stop=prompt.stop_texts,
            **completer_kwargs,
        )  # type: ignore[no-untyped-call]

    @property
    def budget_info(self) -> dict[str, str | int]:
        """Return counts for the last and cumulative calls across this interaction
        session."""
        token_counts = self._token_counter.model_dump()
        return token_counts

    @budget_info.setter
    def budget_info(self, value: dict[str, str | int]):
        self._token_counter = TokenCounter.model_validate(value)

    @retry(
        wait=wait_random_exponential(multiplier=1, max=40),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type(HTTPError),
    )
    def _complete(self, prompt: LLMPrompt) -> str:
        """Implementation that is wrapped by `complete`, potentially cached."""

        response: dict[str, Any]

        try:
            self._request_rate_limiter.try_acquire(self._model_name)
            num_prompt_tokens = num_tokens_from_messages(
                prompt.messages, self._model_name
            )
            self._prompt_est_len = num_prompt_tokens
            assert num_prompt_tokens is not None
            self._token_rate_limiter.consume(num_prompt_tokens)
            response = self._call(prompt)
            response = response.to_dict()
            num_completion_tokens = response.get("usage", {}).get(
                "completion_tokens", 0
            )
            num_prompt_tokens = response.get("usage", {}).get("prompt_tokens", 0)
            self._token_counter.increment_output_tokens(num_completion_tokens)
            self._token_counter.increment_prompt(num_prompt_tokens)
            self._token_rate_limiter.consume(num_completion_tokens)
        except OpenAIError as e:
            raise CompletionApiError(f"OpenAIError: {e!r}")

        if not len(response.get("choices", [])) >= 1:
            raise CompletionApiError("No completion returned from API")

        top_completion = response["choices"][0]
        message = top_completion["message"]
        if message["role"] != "assistant":
            raise CompletionApiError(
                f"API returned message with role '{message['role']}', "
                f"expected to be 'assistant'."
            )

        text = cast(str, message["content"])
        if prompt.stop_texts is not None:
            ends_with_stop_text = prompt.stop_texts and any(
                text.endswith(stop_text) for stop_text in prompt.stop_texts
            )
            if (
                top_completion.get("finish_reason") == "length"
                and not ends_with_stop_text
            ):
                raise CompletionTooShortError(
                    "API reached token limit before returning answer"
                )
        return text
