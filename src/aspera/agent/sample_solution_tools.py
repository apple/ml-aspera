#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from aspera.agent.base_agent import BaseAgent
from aspera.aliases import ExamplesModule
from aspera.apps.time_utils import now_
from aspera.code_utils.code_symbol import CodeSymbol
from aspera.code_utils.utils import (
    get_apps_symbols_from_program,
    get_imports,
    get_source_code_for_apps,
    remove_import_statements,
)
from aspera.completer import CompleterType
from aspera.completer.utils import ChatMessage
from aspera.constants import EXAMPLES_ROOT
from aspera.dataset_schema import DataPoint
from aspera.parser import ExtractFunctionReturnType, ParserType
from aspera.prompting.system_turn_prompts import OracleSystemTurnTemplate
from aspera.prompting.user_turn_prompts import UserTurnTemplate

logger = logging.getLogger(__name__)


class SampleSolutionToolsAgent(BaseAgent):
    """Agent which is prompted only with symbols used in the sample
    solution and knowledge of date, time and weekday on the user device
    to solve the queries."""

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
        annotation = self.evaluator.load_annotation(query.query)
        self._prepare_annotation_for_prompt_generation(annotation)

        # Symbols from the ground-truth program
        ground_truth_symbols = get_apps_symbols_from_program(annotation.program)

        # Also add any symbols from the in-context examples
        examples_src = [
            f"{EXAMPLES_ROOT}.{module}" for module in annotation.scenario.query_solution
        ]
        code = [
            remove_import_statements(source)
            for source in get_source_code_for_apps(examples_src)
        ]
        examples_code = "\n".join(code)
        examples_code += (
            f"\n{now_.__name__}()"  # make sure now_() is invariably included
        )
        examples_symbols = get_apps_symbols_from_program(examples_code)

        symbols_for_scenario = ground_truth_symbols + examples_symbols
        symbols_for_scenario.sort(key=lambda x: x.line_no)
        scenario = deepcopy(annotation.scenario)
        scenario.symbols_in_apps = symbols_for_scenario

        imports = get_imports(annotation.scenario, executable=True)

        messages = [
            OracleSystemTurnTemplate(template_factory=self._system_template).get_prompt(
                scenario
            ),
            UserTurnTemplate(template_factory=self._user_template).get_prompt(
                {
                    "queries": [query.query],
                    "return_type": ExtractFunctionReturnType()(annotation.program),
                }
            ),
        ]
        return messages, imports, None
