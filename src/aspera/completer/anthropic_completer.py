#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import os
from pathlib import Path
from typing import Any, cast

import anthropic
from anthropic.types import MessageParam
from requests import HTTPError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from aspera.completer.completer import Completer, CompletionCache
from aspera.completer.utils import (
    CompletionApiError,
    CompletionTooShortError,
    LLMPrompt,
)
from aspera.constants import DEFAULT_CACHE_DIR


class AnthropicCompleter(Completer):
    def __init__(
        self,
        model_name: str = "claude-v1",
        max_tokens: int = 100,
        temperature: float = 0.7,
        timeout: float = 120,
        cache_dir: Path | None = DEFAULT_CACHE_DIR / "anthropic",
    ):
        super().__init__(max_tokens, model_name)
        self._temperature = temperature
        self._cache = CompletionCache(self._full_cache_dir(cache_dir))
        self._timeout = timeout
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                f"Set ANTHROPIC_API_KEY env variable to use {self.__class__.__name__}"
            )
        self._prompt_est_len = 0
        self._client = anthropic.Anthropic()

    def estimate_tokens(self, messages: list[MessageParam]) -> int:

        estimation = 0
        for m in messages:
            estimation += self._client.count_tokens(m["content"])
        return estimation

    def _full_cache_dir(self, cache_dir: Path | None) -> Path | None:
        if cache_dir is None:
            return None
        return (
            cache_dir
            / self._model_name
            / f"mt_{self._max_tokens}__temp_{self._temperature:.3f}"
        )

    @retry(
        wait=wait_random_exponential(multiplier=1, max=40),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(HTTPError),
    )
    def _complete(self, prompt: LLMPrompt) -> str:
        """Implementation that is wrapped by `complete`, potentially cached."""
        stop_sequences = prompt.stop_texts if prompt.stop_texts is not None else []
        stop_sequences.append(anthropic.HUMAN_PROMPT)

        response: dict[str, Any]
        [system] = cast(
            MessageParam, [m for m in prompt.messages if m["role"] == "system"]
        )
        self._prompt_est_len = self.estimate_tokens(
            cast(list[MessageParam], prompt.messages)
        )
        messages = cast(
            list[MessageParam], [m for m in prompt.messages if m["role"] != "system"]
        )
        try:
            response = self._client.messages.create(
                model=self._model_name,
                max_tokens=self.max_tokens,
                system=system,
                messages=messages,
                temperature=self._temperature,
                timeout=self._timeout,
            ).to_dict()
        except anthropic.APIError as e:
            raise CompletionApiError(f"ApiException: {e!r}")

        text = response["content"]
        assert isinstance(text, str)
        if prompt.stop_texts is not None:

            ends_with_stop_text = prompt.stop_texts and any(
                text.endswith(stop_text) for stop_text in prompt.stop_texts
            )
            if response.get("stop_reason") == "max_tokens" and not ends_with_stop_text:
                raise CompletionTooShortError(
                    "API reached token limit before returning answer"
                )

        return text
