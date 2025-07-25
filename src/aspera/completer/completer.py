#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, cast

from diskcache import Cache

from aspera.completer.utils import (
    MAX_CONTEXT_LENGTH,
    WARN_COMPLETION_THRESHOLD,
    CompletionGetPromptError,
    LLMPrompt,
    _make_cache_key,
)

logger = logging.getLogger(__name__)


class CompletionCache:
    """
    A cache for completion results, that can be used by Completer implementations.
    Also implements retrying.
    """

    def __init__(self, cache_dir: Path | None):
        self._cache = self._make_cache(cache_dir)

    @staticmethod
    def _make_cache(cache_dir: Path | None) -> Cache | None:
        if cache_dir is None:
            return None
        cache_dir.mkdir(exist_ok=True, parents=True)
        assert cache_dir.is_dir()
        return Cache(str(cache_dir))

    def cached_complete(
        self,
        complete_fn: Callable[[LLMPrompt], str],
        prompt: LLMPrompt,
        max_retries: int,
        use_cache: bool = True,
        timeout: float | None = None,
    ) -> str:
        """Use the given complete_fn, or return a cached completion."""
        key = _make_cache_key(prompt)
        if self._cache is not None and use_cache:
            if key in self._cache:
                logger.debug("Retrieving cached completion ... ")
                return cast(str, self._cache[key])

        completion = complete_fn(prompt)
        if self._cache is not None and completion is not None:
            self._cache[key] = completion

        return completion


class Completer(ABC):
    """Class that can be used to complete prompts."""

    def __init__(self, max_tokens: int = 100, model_name: str = ""):
        self._max_tokens = max_tokens
        self._model_name = model_name
        self._prompt_est_len = 0

    _cache: CompletionCache

    def complete(
        self,
        prompt: LLMPrompt,
        use_cache: bool = True,
        max_retries: int = 1,
        timeout: float | None = None,
    ) -> str:
        """Complete the prompt, using the cache."""
        return self._cache.cached_complete(
            complete_fn=self._complete,
            prompt=prompt,
            use_cache=use_cache,
            max_retries=max_retries,
            timeout=timeout,
        )

    @abstractmethod
    def _complete(self, prompt: LLMPrompt) -> str:
        """Implementation of prompt completion, used by self.complete."""

    def get_prompt(self) -> LLMPrompt:
        """Returns a prompt to complete."""
        raise CompletionGetPromptError("get_prompt not implemented for this completer")

    def set_completion_response(self, response: str) -> None:
        """Sets the completion response."""
        pass

    @property
    def max_tokens(self):
        if self._max_tokens == -1:
            remaining_tokens = (
                MAX_CONTEXT_LENGTH[self._model_name] - self._prompt_est_len
            )
            if remaining_tokens < WARN_COMPLETION_THRESHOLD:
                logger.warning(f"Max completion length: {remaining_tokens}")
            return remaining_tokens
        if (
            self._prompt_est_len + self._max_tokens
            > MAX_CONTEXT_LENGTH[self._model_name]
        ):
            remaining_tokens = (
                MAX_CONTEXT_LENGTH[self._model_name] - self._prompt_est_len
            )
            logger.warning(
                f"Truncating max_tokens to {remaining_tokens} to avoid BadRequestError"
            )
            return remaining_tokens
        return self._max_tokens

    @property
    def model_name(self) -> str:
        return self._model_name


class DummyCompleter(Completer):
    def _complete(self, prompt: LLMPrompt) -> str:
        return self.complete(prompt)
