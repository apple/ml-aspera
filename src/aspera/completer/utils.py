#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import logging
from enum import Enum, unique
from typing import Literal

import tiktoken
from pydantic import BaseModel
from pyrate_limiter import Duration, Limiter, Rate
from typing_extensions import TypedDict

from aspera.ratelimiter import (
    NoopLimiter,
    NoopRateLimiter,
    RateLimiter,
    TokenUsageRateLimiter,
)

logger = logging.getLogger(__name__)


_REQUEST_RATE_LIMITS = {
    "gpt-3.5-turbo": Rate(3_500, Duration.MINUTE),
    "gpt-3.5-turbo-16k": Rate(3_500, Duration.MINUTE),
    "gpt-4": Rate(200, Duration.MINUTE),
    "gpt-4o": Rate(200, Duration.MINUTE),
    "gpt-4o-mini": Rate(200, Duration.MINUTE),
    "gpt-3.5-turbo-0125": Rate(90_000, Duration.MINUTE),
    "o1-preview-2024-09-12": Rate(100, Duration.MINUTE),
    "o1-mini-2024-09-12": Rate(250, Duration.MINUTE),
    "o3-mini": Rate(250, Duration.MINUTE),
    "o3": Rate(250, Duration.MINUTE),
    "gpt-4o-mini-2024-07-18": Rate(200, Duration.MINUTE),
    "gpt-4o-2024-05-13": Rate(200, Duration.MINUTE),
    "gpt-4o-2024-08-06": Rate(200, Duration.MINUTE),
}

_TOKEN_RATE_LIMITS = {
    "gpt-3.5-turbo": Rate(90_000, Duration.MINUTE),
    "gpt-3.5-turbo-16k": Rate(180_000, Duration.MINUTE),
    "gpt-4": Rate(40_000, Duration.MINUTE),
    "gpt-4o": Rate(40_000, Duration.MINUTE),
    "gpt-4o-mini": Rate(40_000, Duration.MINUTE),
    "gpt-3.5-turbo-0125": Rate(90_000, Duration.MINUTE),
    "o1-preview-2024-09-12": Rate(100_000, Duration.MINUTE),
    "o1-mini-2024-09-12": Rate(100_000, Duration.MINUTE),
    "o3-mini": Rate(100_000, Duration.MINUTE),
    "o3": Rate(100_000, Duration.MINUTE),
    "gpt-4o-mini-2024-07-18": Rate(100_000, Duration.MINUTE),
    "gpt-4o-2024-05-13": Rate(60_000, Duration.MINUTE),
    "gpt-4o-2024-08-06": Rate(60_000, Duration.MINUTE),
}

MAX_CONTEXT_LENGTH = {
    "gpt-3.5-turbo": 16385,
    "gpt-3.5-turbo-16k": 16385,
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4": 8192,
    "claude-3-5-sonnet-20240620": 200000,
    "gpt-3.5-turbo-0125": 16385,
    "o1-preview-2024-09-12": 128000,
    "o1-mini-2024-09-12": 128000,
    "o3-mini": 128000,
    "o3": 200000,
    "gpt-4o-mini-2024-07-18": 128000,
    "gpt-4o-2024-05-13": 128000,
    "gpt-4o-2024-08-06": 128000,
}
MAX_OUTPUT_TOKENS = {
    "gpt-3.5-turbo": 4096,
    "gpt-4": 4096,
    "gpt-4o": 4096,
    "gpt-4o-mini": 4096,
    "gpt-3.5-turbo-0125": 4096,
    "gpt-4o-mini-2024-07-18": 16384,
    "gpt-4o-2024-05-13": 4096,
    "gpt-4o-2024-08-06": 16384,
    "o1-preview-2024-09-12": 32768,
    "o1-mini-2024-09-12": 65536,
    "o3": 100000,
    "gpt-3.5-turbo-16k": 4096,
    "claude-3-5-sonnet-20240620": 4096,
}
WARN_COMPLETION_THRESHOLD = 512


@unique
class ChatRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    MODEL = "model"


class ChatMessage(TypedDict):
    role: str
    content: str


MessageList = list[ChatMessage]


class LLMPrompt(BaseModel):
    # The messages in the chat history
    messages: MessageList

    # Text to stop completion on.
    stop_texts: list[str] | None = None


def _request_rate_limiter(model_name: str, max_delay: int | None = None) -> Limiter:
    if model_name in _REQUEST_RATE_LIMITS:
        return Limiter(_REQUEST_RATE_LIMITS[model_name], max_delay=max_delay)
    else:
        logger.warning(f"Not rate limiting requests for unknown model: {model_name}")
        return NoopLimiter()


def _token_rate_limiter(model_name: str) -> RateLimiter:
    if model_name in _TOKEN_RATE_LIMITS:
        return TokenUsageRateLimiter(rate=_TOKEN_RATE_LIMITS[model_name])
    else:
        logger.warning(f"Not rate limiting tokens for unknown model:{model_name}")
        return NoopRateLimiter()


def num_tokens_from_messages(
    messages: MessageList, model="gpt-4o", verbose: bool = False
) -> int:
    """Returns the number of tokens used by a list of messages.

    Note
    ----
    This function is taken from OpenAI docs and its intended usage
    is for gpt-* models excluding gpt-40. Results are an approx.
    guide only.
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        print("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")
    if model in {
        "gpt-3.5-turbo-0613",
        "gpt-3.5-turbo-16k-0613",
        "gpt-3.5-turbo-0125",
        "gpt-4-0314",
        "gpt-4-32k-0314",
        "gpt-4-0613",
        "gpt-4-32k-0613",
        "gpt-4o",
    }:
        tokens_per_message = 3
        tokens_per_name = 1
    elif model == "gpt-3.5-turbo-0301":
        tokens_per_message = (
            4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
        )
        tokens_per_name = -1  # if there's a name, the role is omitted
    elif "gpt-3.5-turbo" in model:
        if verbose:
            logger.warning(
                "gpt-3.5-turbo may update over time. "
                "Returning num tokens assuming gpt-3.5-turbo-0613."
            )
        return num_tokens_from_messages(messages, model="gpt-3.5-turbo-0613")
    elif "gpt-4" in model or "o1" in model or "o3" in model:
        if verbose:
            logger.warning(
                "gpt-4 may update over time. Returning num tokens assuming gpt-4-0613."
            )
        return num_tokens_from_messages(messages, model="gpt-4-0613")
    else:
        raise NotImplementedError(
            f"""num_tokens_from_messages() is not implemented for model {model}."""
            """See https://github.com/openai/openai-python/blob/main/chatml.md
            for information on how messages are converted to tokens."""
        )
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":
                num_tokens += tokens_per_name
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens


def _make_cache_key(prompt: LLMPrompt) -> str:
    return prompt.model_dump_json()


def get_message(text: str, role: Literal["system", "assistant", "user"]) -> ChatMessage:
    """Format `text` as a chat message."""
    assert role in [
        "system",
        "assistant",
        "user",
    ], "Role must be 'system' or 'assistant' or 'user'"
    return {"content": text, "role": role}


def print_messages(messages: MessageList):
    """Prints a list of messages using rich to have nice syntax highlighting.

    ** Use with caution - it may print syntax errors that do not actually exist.**
    """
    # from rich import print

    for m in messages:
        print(m["content"])
        print()


class CompletionError(ValueError):
    pass


class CompletionApiError(CompletionError):
    pass


class CompletionTooShortError(CompletionError):
    pass


class CompletionGetPromptError(CompletionError):
    pass


class TokenCounter(BaseModel):

    total_prompt_tokens: int = 0
    total_output_tokens: int = 0
    last_prompt_tokens: int = 0
    last_output_tokens: int = 0
    model: str

    def increment_prompt(self, offset: int) -> None:
        self.last_prompt_tokens = offset
        self.total_prompt_tokens += offset

    def increment_output_tokens(self, offset: int) -> None:
        self.last_output_tokens = offset
        self.total_output_tokens += offset
