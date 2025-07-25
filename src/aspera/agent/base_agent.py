#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import logging
from abc import ABC, abstractmethod
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterator

from aspera.aliases import ExamplesModule
from aspera.code_utils.code_symbol import CodeSymbol
from aspera.code_utils.utils import (
    _has_aspera_filenames,
    escape_program_str,
    is_import,
    remove_import_statements,
)
from aspera.completer import CompleterType
from aspera.completer.utils import ChatMessage, LLMPrompt
from aspera.constants import DOCS_ROOT, IMPLEMENTATIONS_ROOT, PACKAGE_NAME
from aspera.dataset_schema import DataPoint
from aspera.evaluator import EvaluationResult, Evaluator, Solution, solution_correct
from aspera.execution_evaluation_tools_implementation.exceptions import SolutionError
from aspera.parser import DUMMY_PLACEHOLDER_BAD_SOLUTION, ParserType, ProgramFinderError

logger = logging.getLogger(__name__)

ZS_ASSERTION = "Please specify a module containing an example to guide the solution format. \
    This should be a .py file in the examples/ folder in root"


GuidelineType = str
# see src/aspera/scenario.py::Guideline for types


class BaseAgent(ABC):
    def __init__(
        self,
        queries_dir: str | Path,
        parser: ParserType,
        completer: CompleterType,
        guidelines: dict[str, list[str]] | None = None,
        single_shot: bool = False,
        format_examples_module: ExamplesModule | None = None,
        **kwargs: Any,
    ):
        self._parser: ParserType = parser.parser
        self._parsing_failure_cnt = 0
        self._solution_error_cnt = 0
        self._bad_import_queries: set[str] = set()
        self._completer: CompleterType = completer
        self.evaluator = Evaluator(queries_dir)
        # the package where the apps are implemented
        self.tools_package = f"{PACKAGE_NAME}.{IMPLEMENTATIONS_ROOT}"
        # the codebase documentation to be navigated is stored there
        self.docs_package = f"{PACKAGE_NAME}.{DOCS_ROOT}"
        self._guidelines: dict[GuidelineType, list[str]] = guidelines or {}
        if single_shot:
            assert format_examples_module is not None, ZS_ASSERTION
        self._single_shot = single_shot
        self._format_examples_module = format_examples_module

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @property
    def num_unparseable(self) -> int:
        return self._parsing_failure_cnt

    @property
    def parser_failure_rate(self) -> float:
        return (100 * self._parsing_failure_cnt) / self.evaluator.total_queries

    def submit_solution(self, query: DataPoint, solution: Solution) -> EvaluationResult:
        """Submit solution to the evaluator."""
        try:
            feedback = self.evaluator.get_solution_feedback(solution)
        except (SolutionError, AssertionError):
            feedback = self.evaluator.side_effect_feedback
            self._solution_error_cnt += 1
        except ProgramFinderError:
            self._parsing_failure_cnt += 1
            solution.program = DUMMY_PLACEHOLDER_BAD_SOLUTION
            feedback = self.evaluator.no_solution_feedback
        correct = solution_correct(feedback)

        import_lenient_feedback = None
        import_lenient_correct = correct
        if (
            feedback
            and ModuleNotFoundError.__name__ in feedback[0].content
            and solution.program_no_imports
        ):
            self._bad_import_queries.add(query.query_id)
            solution_no_imports = deepcopy(solution)
            solution_no_imports.program = solution.program_no_imports
            try:
                import_lenient_feedback = self.evaluator.get_solution_feedback(
                    solution_no_imports, import_lenient=True
                )
                import_lenient_correct = solution_correct(import_lenient_feedback)
            except (SolutionError, AssertionError):
                import_lenient_feedback = None
                import_lenient_correct = False

        ground_truth_solution = self.evaluator.load_annotation(query.query)
        return EvaluationResult(
            query_id=query.query_id,
            query=query.query,
            solution=solution.program,
            ground_truth_solution=ground_truth_solution.program,
            feedback=feedback,
            raw_completion=solution.raw_completion,
            prompt=solution.prompt,
            correct=correct,
            import_lenient_correct=import_lenient_correct,
            import_lenient_feedback=import_lenient_feedback,
            primitives_selection_result=self.evaluator.get_primitives_selection_feedback(
                solution, ground_truth_solution.program
            ),
        )

    @property
    def score(self) -> float:
        return self.evaluator.get_score()

    @property
    def import_lenient_score(self) -> float:
        return self.evaluator.get_score(import_lenient=True)

    @property
    def solution_err_rate(self) -> float:
        return (
            (100 * self._solution_error_cnt) / self.evaluator.total_err_count
            if self.evaluator.total_err_count > 0
            else 0.0
        )

    @property
    def control_handover_err_rate(self) -> float:
        """The % of tasks where the agent requires user input when
        this is not necessary."""
        other_err_count = self.evaluator.total_err_count - self._solution_error_cnt
        return (
            (100 * self.evaluator.handback_control_err_count) / other_err_count
            if other_err_count > 0
            else 0.0
        )

    @property
    def execution_error_rate(self) -> float:
        """The % of tasks where the task is not completed but neither
        is an assertion triggered, nor is the control handed over the user,
        relative to the total number of errors."""
        execution_err_count = (
            self.evaluator.total_err_count
            - self._solution_error_cnt
            - self.evaluator.handback_control_err_count
        )
        return (
            (100 * execution_err_count) / self.evaluator.total_err_count
            if self.evaluator.total_err_count > 0
            else 0.0
        )

    @property
    def control_handover_err_rate_normalised(self):
        """The % of tasks where the agent requires user input when
        this is not necessary."""
        return (
            (100 * self.evaluator.handback_control_err_count)
            / self.evaluator.total_err_count
            if self.evaluator.total_err_count > 0
            else 0.0
        )

    @property
    def bad_import_queries(self) -> list[int]:
        return sorted([int(_id) for _id in self._bad_import_queries])

    @property
    def bad_import_error_rate(self) -> float:
        return (
            (100 * len(self._bad_import_queries)) / self.evaluator.total_err_count
            if self.evaluator.total_err_count > 0
            else 0.0
        )

    def task_iterator(self) -> Iterator[DataPoint]:
        """Iterate through the tasks the agent has to solve."""
        for query in self.evaluator.annotations:
            yield query

    def execute_tasks(self):
        """Solve all the tasks in the benchmark."""
        for task in self.task_iterator():
            try:
                self.plan(task)
            except SolutionError:
                continue

    @abstractmethod
    def _make_messages_and_imports(
        self, query: DataPoint
    ) -> tuple[list[ChatMessage], list[str], list[CodeSymbol] | None]:
        """
        Take the query and prepare the messages and import statements for prompting

        Returns
        -------
        List of ChatMessage objects for prompt, imports for evaluation and, if applicable,
        list of symbols retrieved during tool retrieval.
        """
        ...

    def plan(self, query: DataPoint) -> Solution:
        messages, imports, tr_code_symbols = self._make_messages_and_imports(query)
        llm_prompt = LLMPrompt(messages=messages)
        completion = self._completer.complete(llm_prompt)
        try:
            parsed = self._parser.parse(completion)
        except ProgramFinderError:
            # Agent failed to produce valid Python; return this so it fails in a traceable way
            logger.warning(f"Query {query.query_id}: {query.query}")
            logger.warning(f"Failed to parse completion: {completion}")
            self._parsing_failure_cnt += 1
            return Solution(
                raw_completion=completion,
                query=query.query,
                program=DUMMY_PLACEHOLDER_BAD_SOLUTION,
                prompt=llm_prompt,
                primitives_selection_symbols=tr_code_symbols,
            )
        programs = []
        for program in parsed:
            if is_import(program):
                imports.append(f"{program}\n")
            else:
                programs.append(program)

        imports_list = list(dict.fromkeys(imports))
        imports_str = "".join(imports_list).strip()
        program_str = escape_program_str(programs.pop())
        try:
            # Remove model-issued imports at the top level
            filtered_imports_list = []
            for im in imports_list:
                if _has_aspera_filenames(im) and "*" not in im:
                    continue
                filtered_imports_list.append(im)
            filtered_imports_str = "".join(filtered_imports_list).strip()
            program_str_no_imports = remove_import_statements(
                program_str,
                package_name=None,
                global_only=False,
                remove_aspera_imports_only=True,
            )
        except SyntaxError:
            filtered_imports_str, program_str_no_imports = None, None
        return Solution(
            raw_completion=completion,
            query=query.query,
            program=f"{imports_str}\n\n{program_str}",
            prompt=llm_prompt,
            primitives_selection_symbols=tr_code_symbols,
            program_no_imports=(
                f"{filtered_imports_str}\n\n{program_str_no_imports}"
                if program_str_no_imports
                else None
            ),
        )

    def _prepare_annotation_for_prompt_generation(self, annotation: DataPoint):
        """Updates the annotation used to render to agent prompts with
        agent specific settings."""
        annotation.scenario.guidelines.generation_labelling = self._guidelines.get(
            "generation_labelling", []
        )
        if self._single_shot:
            annotation.scenario.query_solution = [self._format_examples_module]
