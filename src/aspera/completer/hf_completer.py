#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import logging
import os
from pathlib import Path

import torch
from huggingface_hub import login
from transformers import pipeline

from aspera.completer.completer import Completer, CompletionCache
from aspera.completer.utils import ChatMessage, ChatRole, LLMPrompt, MessageList
from aspera.constants import DEFAULT_CACHE_DIR

logger = logging.getLogger(__name__)


class HuggingFaceCompleter(Completer):

    def __init__(  # noqa: PLR0913
        self,
        model_name: str = "google/codegemma-7b-it",
        max_output_tokens: int = 4096,
        seed: int = 42,
        cache_dir: Path | None = DEFAULT_CACHE_DIR / "huggingface",
    ):
        super().__init__(max_tokens=max_output_tokens, model_name=model_name)
        if "HUGGINGFACE_API_KEY" not in os.environ:
            raise RuntimeError(
                f"Set HUGGINGFACE_API_KEY env variables to use {self.__class__.__name__}"
            )
        login(token=os.environ.get("HUGGINGFACE_API_KEY"))
        self._model_name = model_name
        self._chatbot = pipeline(
            "text-generation",
            model=model_name,
            device_map="auto",
            torch_dtype=torch.bfloat16,
            # model_kwargs=quant_config,
        )
        self._cache = CompletionCache(self._full_cache_dir(cache_dir))

    def _full_cache_dir(self, cache_dir: Path | None) -> Path | None:
        if cache_dir is None:
            return None
        return cache_dir / f"chat__{self._model_name}"

    def _transform_prompt_for_gemma(self, prompt: LLMPrompt) -> LLMPrompt:
        """convert LLMPrompt to support Google gemma-it format


        Google gemma have two role: user and model. It does not support system role,
        so we follow this suggestion:
        https://www.googlecloudcommunity.com/gc/AI-ML/Gemini-Pro-Context-Option/m-p/684704/highlight/true#M4159
        """

        message_list = []
        for message in prompt.messages:
            role = message["role"]
            if role == ChatRole.SYSTEM:
                message_list.extend(
                    [
                        ChatMessage(role=ChatRole.USER, content=message["content"]),
                        ChatMessage(
                            role=ChatRole.ASSISTANT,
                            content="Understood.",
                        ),
                    ]
                )

            elif role in [ChatRole.USER, ChatRole.ASSISTANT]:
                message_list.append(message)
            else:
                raise ValueError(f"Unexpected message role {role} in prompt")

        return LLMPrompt(messages=MessageList(message_list))

    def _apply_chat_template(self, prompt: LLMPrompt) -> str:
        """render chat messages with template to follow model's input chat format

        for debugging purpose only since HuggingFace pipeline interface
        calls apply_chat_template for you
        """
        return self._chatbot.tokenizer.apply_chat_template(
            self._transform_prompt_for_gemma(prompt).messages,
            tokenize=False,
            add_generation_prompt=True,
        )

    def _complete(self, prompt: LLMPrompt) -> str:
        # # Gemma does not support system role
        if "gemma" in self._model_name:
            prompt = self._transform_prompt_for_gemma(prompt)
            prompt_str = self._apply_chat_template(prompt)
            output = self._chatbot(prompt.messages, max_new_tokens=self._max_tokens)
            output_str = output[0]["generated_text"][-1]["content"]
        else:
            prompt_str = "\n".join([message["content"] for message in prompt.messages])
            output = self._chatbot(prompt_str, max_new_tokens=self._max_tokens)
            output_str = output[0]["generated_text"][len(prompt_str) :]

        logger.debug(f"------{self.model_name} prompt -----")
        logger.debug(prompt_str)
        return output_str
