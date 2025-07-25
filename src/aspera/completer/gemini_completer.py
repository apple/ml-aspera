#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import logging
import subprocess
from pathlib import Path

import vertexai
from google.api_core.exceptions import ServerError, TooManyRequests
from requests import HTTPError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)
from vertexai import generative_models
from vertexai.generative_models import Content, GenerationConfig, GenerativeModel, Part

from aspera.completer.completer import Completer, CompletionCache
from aspera.completer.utils import ChatRole, LLMPrompt
from aspera.constants import DEFAULT_CACHE_DIR

logger = logging.getLogger(__name__)


class GeminiChatCompleter(Completer):
    """Completer for Google Gemini Chat."""

    def __init__(  # noqa: PLR0913
        self,
        gcp_project_id: str,
        gcp_location: str,
        model_name: str = "gemini-1.5-pro",
        temperature: float = 0.0,
        max_output_tokens: int = 8192,
        top_k: int = 1,
        top_p: float = 0.8,
        best_of_n: int = 1,
        seed: int = 0,
        cache_dir: Path | None = DEFAULT_CACHE_DIR / "gemini",
    ):
        super().__init__(max_tokens=max_output_tokens, model_name=model_name)
        self._temperature = temperature
        self._top_k = top_k
        self._top_p = top_p
        self._best_of_n = best_of_n
        self._seed = seed
        vertexai.init(project=gcp_project_id, location=gcp_location)
        self.model = GenerativeModel(model_name)
        self._cache = CompletionCache(self._full_cache_dir(cache_dir))

        if gcp_project_id != "cache":
            # prompt users to login when running locally when gcp project id is not cache
            auth_output = subprocess.run(
                ["gcloud", "auth", "application-default", "print-access-token"],
                capture_output=True,
            )
            if "reauthentication required" in auth_output.stderr.decode().lower():
                subprocess.run(["gcloud", "auth", "application-default", "login"])

    def _full_cache_dir(self, cache_dir: Path | None) -> Path | None:
        if cache_dir is None:
            return None
        return (
            cache_dir
            / f"chat__{self._model_name}"
            / f"mt_{self._max_tokens}_n_{self._best_of_n}__temp_{self._temperature:.3f}_seed_{self._seed}"  # noqa
        )

    def _transform_prompt_for_gemini(self, prompt: LLMPrompt) -> list[Content]:
        """convert LLMPrompt into GCP ContentsType


        Gemini have two role: user and model. It does not support system role,
        so we follow this suggestion:
        https://www.googlecloudcommunity.com/gc/AI-ML/Gemini-Pro-Context-Option/m-p/684704/highlight/true#M4159
        """

        msg_content = []
        for message in prompt.messages:
            role = message["role"]
            if role == ChatRole.SYSTEM:
                msg_content.extend(
                    [
                        Content(
                            role=ChatRole.USER,
                            parts=[Part.from_text(message["content"])],
                        ),
                        Content(
                            role=ChatRole.MODEL, parts=[Part.from_text("Understood.")]
                        ),
                    ]
                )

            elif role == ChatRole.USER:
                msg_content.append(
                    Content(
                        role=ChatRole.USER, parts=[Part.from_text(message["content"])]
                    )
                )
            else:
                raise ValueError(f"Unexpected message role {role} in prompt")
        return msg_content

    @retry(
        wait=wait_random_exponential(multiplier=1, max=40),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type((HTTPError, TooManyRequests, ServerError)),
    )
    def _complete(self, prompt: LLMPrompt) -> str:
        logger.debug("Calling gemini for completion ... ")
        generation_config = GenerationConfig(
            temperature=self._temperature,
            top_p=self._top_p,
            top_k=self._top_k,
            candidate_count=1,
            max_output_tokens=self._max_tokens,
            seed=self._seed,
        )
        safety_config = {
            generative_models.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: generative_models.HarmBlockThreshold.BLOCK_NONE,
            generative_models.HarmCategory.HARM_CATEGORY_HARASSMENT: generative_models.HarmBlockThreshold.BLOCK_NONE,
            generative_models.HarmCategory.HARM_CATEGORY_HATE_SPEECH: generative_models.HarmBlockThreshold.BLOCK_NONE,
            generative_models.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: generative_models.HarmBlockThreshold.BLOCK_NONE,
        }
        generation_response = self.model.generate_content(
            self._transform_prompt_for_gemini(prompt),
            generation_config=generation_config,
            safety_settings=safety_config,
        )
        return generation_response.text
