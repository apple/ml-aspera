#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import logging
from copy import deepcopy
from pathlib import Path
from typing import Callable

from aspera import apps
from aspera.agent.base_agent import BaseAgent, GuidelineType
from aspera.aliases import AppName, ExamplesModule
from aspera.code_utils.code_symbol import CodeSymbol, dedup_and_sort_symbols
from aspera.code_utils.utils import (
    get_apps_symbols_from_program,
    get_imports,
    get_source_code_for_apps,
    make_prompt_code_string,
    remove_import_statements,
)
from aspera.completer import CompleterType
from aspera.completer.utils import ChatMessage, LLMPrompt, MessageList
from aspera.constants import APP_DOCS_ROOT, EXAMPLES_ROOT
from aspera.dataset_schema import DataPoint
from aspera.parser import ExtractFunctionReturnType, ParserType, ProgramFinderError
from aspera.prompting.primitives_selection_prompts import (
    PrimitivesSelectionTemplate,
    UserTurnPrimitivesSelectionTemplate,
)
from aspera.prompting.system_turn_prompts import OracleSystemTurnTemplate
from aspera.prompting.user_turn_prompts import UserTurnTemplate

logger = logging.getLogger(__name__)

# These are stubs or irrelevant, so we can ignore them to save tokens
APP_DENY_LIST = ["reminders"]


class PrimitivesSelectionAgent(BaseAgent):
    """Primitives selection agent which sequentially chooses functions from each module before
    writing its solution.

    Parameters
    ----------
    guidelines
        Detailed guidelines informing the agent about environment assumptions that have
        to be accounted for when generating execution plans
    primitives_selection_guidelines
        Subset of the above, containing guidelines that could influence tool selection.
    """

    def __init__(
        self,
        queries_dir: str | Path,
        parser: ParserType,
        completer: CompleterType,
        system: Callable[..., str],
        user: Callable[..., str],
        primitives_selection: Callable[..., str] | None = None,
        guidelines: dict[str, list[str]] | None = None,
        primitives_selection_guidelines: dict[str, list[str]] | None = None,
        single_shot: bool = False,
        format_examples_module: ExamplesModule | None = None,
        **kwargs,
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
        self._primitives_selection_template: Callable[..., str] = primitives_selection
        self._primitives_selection_guidelines: dict[GuidelineType, list[str]] = (
            primitives_selection_guidelines or {}
        )

    def _get_import_symbols_from_agent(self, query: DataPoint) -> list[CodeSymbol]:
        all_symbols = []
        for app in [
            f"{APP_DOCS_ROOT}.{app}"
            for app in apps.module_names
            if app not in APP_DENY_LIST
        ]:
            messages = self._make_messages_for_primitives_selection(app, query)
            completion = self._completer.complete(LLMPrompt(messages=messages))
            try:
                parsed = self._parser.parse(completion)
            except ProgramFinderError:
                logger.warning(f"Query {query.query_id}: {query.query}")
                logger.warning(
                    f"The completer did not output a valid output for app: {app}"
                )
                logger.warning(f"The completion was: {completion}")
                parsed = ["None"]
            for program in parsed:
                all_symbols.extend(get_apps_symbols_from_program(program))
        return dedup_and_sort_symbols(all_symbols)

    def _make_messages_for_primitives_selection(
        self, app: AppName, query: DataPoint
    ) -> MessageList:
        code = make_prompt_code_string(
            app,
            remove_import_statements(get_source_code_for_apps([app]).pop()),
        )
        messages = [
            PrimitivesSelectionTemplate(
                template_factory=self._primitives_selection_template
            ).get_prompt(
                {
                    "module": code,
                    "query": query.query,
                    "guidelines": self._primitives_selection_guidelines.get(
                        "generation_labelling", []
                    ),
                }
            ),
        ]
        return messages

    def _make_messages_and_imports(
        self, query: DataPoint
    ) -> tuple[list[ChatMessage], list[str], list[CodeSymbol] | None]:
        annotation = self.evaluator.load_annotation(query.query)
        self._prepare_annotation_for_prompt_generation(annotation)

        # Agent compares every module to the query to find relevant things to import
        symbols = self._get_import_symbols_from_agent(query)

        # Also add any symbols from the in-context examples
        examples_src = [
            f"{EXAMPLES_ROOT}.{module}" for module in annotation.scenario.query_solution
        ]
        code = [
            remove_import_statements(source)
            for source in get_source_code_for_apps(examples_src)
        ]
        examples_code = "\n".join(code)
        examples_symbols = get_apps_symbols_from_program(examples_code)

        symbols_for_scenario = symbols + examples_symbols
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
        return messages, imports, symbols


class PrimitivesSelectionAgentUserTurn(PrimitivesSelectionAgent):
    """Tool retrieval agent which sequentially chooses functions from each module before
    writing its solution."""

    def __init__(
        self,
        queries_dir: str | Path,
        parser: ParserType,
        completer: CompleterType,
        system: Callable[..., str],
        user: Callable[..., str],
        primitives_selection_system: Callable[..., str],
        primitives_selection_user: Callable[..., str],
        guidelines: dict[str, list[str]] | None = None,
        primitives_selection_guidelines: dict[str, list[str]] | None = None,
        **kwargs,
    ):
        super().__init__(
            queries_dir,
            parser,
            completer,
            system=system,
            user=user,
        )
        self._primitives_selection_template_system: Callable[..., str] = (
            primitives_selection_system
        )
        self._primitives_selection_template_user: Callable[..., str] = (
            primitives_selection_user
        )
        self._guidelines: dict[GuidelineType, list[str]] = guidelines or {}
        self._primitives_selection_guidelines: dict[GuidelineType, list[str]] = (
            primitives_selection_guidelines or {}
        )

    def _make_messages_for_primitives_selection(
        self, app: AppName, query: DataPoint
    ) -> MessageList:
        code = make_prompt_code_string(
            app,
            remove_import_statements(get_source_code_for_apps([app]).pop()),
        )
        messages = [
            PrimitivesSelectionTemplate(
                template_factory=self._primitives_selection_template_system
            ).get_prompt(
                {
                    "guidelines": self._primitives_selection_guidelines.get(
                        "generation_labelling", []
                    ),
                }
            ),
            UserTurnPrimitivesSelectionTemplate(
                template_factory=self._primitives_selection_template_user
            ).get_prompt(
                {
                    "module": code,
                    "query": query.query,
                }
            ),
        ]
        return messages
