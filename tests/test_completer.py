#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
from unittest.mock import Mock, patch

import pytest
from vertexai.generative_models import Content, Part

from aspera.completer import GeminiChatCompleter
from aspera.completer.completer import DummyCompleter
from aspera.completer.utils import ChatMessage, ChatRole, LLMPrompt, MessageList


@patch(
    "aspera.completer.completer.Completer.complete",
    Mock(return_value="hello world"),
)
def test_completer_simple():
    prompt = LLMPrompt(messages=MessageList([ChatMessage(role="foo", content="bar")]))
    completer = DummyCompleter()
    assert completer.complete(prompt)
