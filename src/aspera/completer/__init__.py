#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
from aspera.completer.anthropic_completer import AnthropicCompleter
from aspera.completer.gemini_completer import GeminiChatCompleter
from aspera.completer.hf_completer import HuggingFaceCompleter
from aspera.completer.openai_completer import OpenAiChatCompleter

CompleterType = (
    OpenAiChatCompleter
    | AnthropicCompleter
    | GeminiChatCompleter
    | HuggingFaceCompleter
)
