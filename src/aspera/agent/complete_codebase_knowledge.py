#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import logging
from pathlib import Path
from typing import Any, Callable

from aspera.agent.base_agent import BaseAgent
from aspera.aliases import ExamplesModule
from aspera.code_utils.code_symbol import CodeSymbol
from aspera.code_utils.utils import get_imports
from aspera.completer import CompleterType
from aspera.completer.utils import ChatMessage
from aspera.dataset_schema import DataPoint
from aspera.parser import ExtractFunctionReturnType, ParserType
from aspera.prompting.system_turn_prompts import SystemTurnTemplate
from aspera.prompting.user_turn_prompts import UserTurnTemplate

logger = logging.getLogger(__name__)


class CompleteCodebaseKnowledgeAgent(BaseAgent):
    """Agent prompted with full knowledge of the codebase for the relevant apps."""

    def __init__(
        self,
        queries_dir: str | Path,
        parser: ParserType,
        completer: CompleterType,
        system: Callable[..., str],
        user: Callable[..., str],
        guidelines: dict[str, list[str]] | None = None,
        single_shot: bool = False,
        format_examples_module: ExamplesModule | None = None,
        **kwargs: Any,
    ):
        super().__init__(
            queries_dir,
            parser,
            completer,
            guidelines,
            single_shot,
            format_examples_module,
            **kwargs,
        )
        self._system_template: Callable[..., str] = system
        self._user_template: Callable[..., str] = user

    def _make_messages_and_imports(
        self, query: DataPoint
    ) -> tuple[list[ChatMessage], list[str], list[CodeSymbol] | None]:
        annotation: DataPoint = self.evaluator.load_annotation(query.query)
        self._prepare_annotation_for_prompt_generation(annotation)
        imports = get_imports(annotation.scenario, executable=True)
        messages = [
            SystemTurnTemplate(template_factory=self._system_template).get_prompt(
                annotation.scenario
            ),
            UserTurnTemplate(template_factory=self._user_template).get_prompt(
                {
                    "queries": [query.query],
                    "return_type": ExtractFunctionReturnType()(annotation.program),
                }
            ),
        ]
        return messages, imports, None
