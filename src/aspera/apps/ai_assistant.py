"""A powerful AI assistant, best used for summarising and processing documents and other forms of
written text on the user's device."""

from dataclasses import dataclass
from enum import StrEnum, auto
from typing import Literal


@dataclass
class ActionItem:
    """An action resulting from a meeting, optionally assigned
    to one or more people."""

    action: str
    directly_responsible_individuals: list[str] | None = None
    urgency: Literal["urgent", "not urgent"] | None = None


def summarise(content: str) -> str:
    """Use your AI assistant to summarise the content. Handy
    for keeping up with long meeting notes, the emails from your
    boss in the past month and so much more."""


def extract_action_items(notes: str) -> list[ActionItem]:
    """Use your smart assistant to speed-up your planning - turn
    your meeting notes into action items with a single function call."""


class SupportedLanguages(StrEnum):
    Romanian = auto()
    Russian = auto()
    English = auto()


def translate(text: str, language: SupportedLanguages) -> str:
    """Translate any text to a supported language."""
