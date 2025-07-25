#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import json
import logging
import textwrap
from copy import deepcopy
from pathlib import Path
from typing import Self

from jinja2 import Environment, StrictUndefined
from pydantic import BaseModel

from aspera.aliases import ProgramStr, Query
from aspera.apps_implementation.exceptions import RequiresUserInput
from aspera.code_utils.code_symbol import CodeSymbol, dedup_and_sort_symbols
from aspera.code_utils.utils import (
    get_apps_symbols_from_program,
    get_imports,
    remove_import_statements,
)
from aspera.completer.utils import LLMPrompt
from aspera.constants import QUERY_FILE_EXTENSION
from aspera.dataset_schema import AnnotatedPrograms, DataPoint
from aspera.execution_evaluation_tools_implementation.exceptions import SolutionError
from aspera.parser import ExtractFunctionName
from aspera.readers import parse_plans_and_evaluation_assets, read_all_shards_flat
from aspera.scenario import Scenario
from aspera.simulation.execution_context import RoleType
from aspera.simulation.execution_environment import Message, execute_script

logger = logging.getLogger(__name__)


class Solution(BaseModel):
    """The solution for a query.

    Parameters
    ----------
    query
        The input query
    program
        The program that executes the user query. The expected format is
        a list of imports for the relevant tool and a program that


        ''''
        from aspera.apps_implementation.work_calendar import find_events
        from aspera.apps_implementation.company_directory import find_employee


        def count_meetings_with_jianpeng() -> int:
            \"""Count the number of meetings with Jianpeng in the user's calendar.\"""

            # find the employee named Jianpeng
            jianpeng = find_employee("Jianpeng")[0]  # by structure guideline #1

            # find all events with Jianpeng
            events_with_jianpeng = find_events(attendees=[jianpeng])

            # return the count of these events
            return len(events_with_jianpeng)
        ''''
    """

    query: str
    program: ProgramStr
    prompt: LLMPrompt | None = None
    primitives_selection_symbols: list[CodeSymbol] | None = None
    raw_completion: str | None = None
    program_no_imports: ProgramStr | None = None


eval_script_template = textwrap.dedent(
    """\
    import sys
    import textwrap
    from types import ModuleType

    solution = textwrap.dedent(
        '''{{solution.program}}
        '''
    )

    {{ setup_eval_imports }}

    {{ query.state_generation_programs[0] }}

    {{ query.evaluation_programs[0] }}

    if __name__ == '__console__':
        def _make_module_from_source(module: str, source: str):
            mod = ModuleType(module)
            sys.modules[module] = mod
            exec(source, mod.__dict__)
            
        from aspera.simulation.execution_context import ExecutionContext, new_context

        _make_module_from_source("query_executable", solution)
        import query_executable

        context = ExecutionContext()
        context.query = \"""{{ solution.query }}\"""
        with new_context(context):
            {{ query.evaluation_programs[0] | function_name_parser }}(
                query="",
                executable=query_executable.{{solution.program | remove_imports | function_name_parser}},
                setup_function={{ query.state_generation_programs[0] | function_name_parser }},
        )"""  # noqa
)


def assert_no_side_effects(tool_exception: str | None):
    if tool_exception is None:
        return
    assert SolutionError.__name__ not in tool_exception, tool_exception


def solution_correct(feedback: list[Message]) -> bool:
    assert feedback, "There was no feedback for assessing solution correctness"
    return all(m.tool_call_exception is None for m in feedback)


def handback_control(feedback: list[Message]) -> bool:
    assert feedback, "There was no feedback"
    for message in feedback:
        if RequiresUserInput.__name__ in (message.tool_call_exception or ""):
            return True
    return False


class F1Score(BaseModel):
    precision: float
    recall: float
    f1: float


class PrimitivesSelectionResult(F1Score):
    retrieved_symbol_names: set[str]
    ground_truth_symbol_names: set[str]


class Evaluator:
    """
    Parameters
    ----------
    plans_dir
        The path to the `plans` subdirectory of the dataset assets.
    """

    def __init__(self, plans_dir: Path):
        self._correct: dict[Query, bool] = {}
        self._import_lenient_correct: dict[Query, bool] = {}
        self.corpus_dir = plans_dir
        annotations = [
            DataPoint(**e)
            for e in read_all_shards_flat(plans_dir, extension=QUERY_FILE_EXTENSION)
        ]
        self._annotations: dict[str, DataPoint] = {
            example.query: example for example in annotations
        }
        self.total_queries = len(annotations)
        self.total_err_count = 0
        self.handback_control_err_count = 0
        environment = Environment()
        environment.filters["function_name_parser"] = ExtractFunctionName()
        environment.filters["remove_imports"] = lambda x: remove_import_statements(
            x
        ).strip("\n ")
        self._template = environment.from_string(eval_script_template)
        # queries the agent is not allowed to re-attempt if the soln was incorrect
        self.failed_queries: set[str] = set()
        # if the execution fails with a solution error, the message returned by
        # the execution environment is stored here until the `solution_error_feedback`
        # is accessed.
        self._side_effect_feedback: list[Message] = []

        # Tool retrieval information, if applicable
        self._tr_result_per_query: dict[Query, PrimitivesSelectionResult] = {}

    @property
    def annotations(self) -> list[DataPoint]:
        return sorted(list(self._annotations.values()), key=lambda x: int(x.query_id))

    def get_score(self, import_lenient: bool = False) -> float:
        """Returns the score the agent achieved on the benchmark."""
        if not self._correct:
            return 0.0

        # Calculate the proportion of correct evaluations
        correct_count = (
            sum(self._import_lenient_correct.values())
            if import_lenient
            else sum(self._correct.values())
        )
        total_count = len(self._correct)

        return correct_count / total_count * 100

    @property
    def has_primitives_selection_results(self) -> bool:
        return any(
            result.retrieved_symbol_names != set()
            for result in self._tr_result_per_query.values()
        )

    @staticmethod
    def _calc_f1(precision: float, recall: float) -> float:
        try:
            return 2 * ((precision * recall) / (precision + recall))
        except ZeroDivisionError:
            logger.debug(
                "F1 score could not be computed, both precision and recall were zero "
            )
            return 0.0

    def get_primitives_selection_macro_f1(self) -> float | None:
        if not self.has_primitives_selection_results:
            return None
        f1_values = [v.f1 for v in self._tr_result_per_query.values()]
        return sum(f1_values) / len(f1_values)

    def get_primitives_selection_micro_f1(
        self,
    ) -> tuple[float, float, float] | tuple[None, None, None]:
        if not self.has_primitives_selection_results:
            return None, None, None
        all_predicted_positives = 0
        all_true_positives = 0
        all_actual_positives = 0
        for query, result in self._tr_result_per_query.items():
            all_predicted_positives += len(result.retrieved_symbol_names)
            all_true_positives += len(
                result.retrieved_symbol_names.intersection(
                    result.ground_truth_symbol_names
                )
            )
            all_actual_positives += len(result.ground_truth_symbol_names)
        global_precision = all_true_positives / all_predicted_positives
        global_recall = all_true_positives / all_actual_positives
        return (
            self._calc_f1(global_precision, global_recall),
            global_precision,
            global_recall,
        )

    def load_annotation(self, query: str) -> DataPoint:
        return self._annotations[query]

    def _get_eval_scripts(self, solution: Solution) -> list[str]:
        """Renders a template with code that runs the solution
        in a sandbox environment and check its effects on the
        runtime are as expected."""
        annotation = self.load_annotation(solution.query)
        runtime_setup_progr, eval_progr = (
            annotation.state_generation_programs,
            annotation.evaluation_programs,
        )
        eval_scripts = []
        for state_progr, eval_code in zip(runtime_setup_progr, eval_progr):
            this_state_input = deepcopy(annotation)
            this_state_input.program = solution.program
            this_state_input.state_generation_programs = [state_progr]
            this_state_input.evaluation_programs = [eval_code]
            this_state_imports = "".join(
                get_imports(
                    this_state_input.scenario,
                    import_simulation_tools=True,
                    import_testing_tools=True,
                    # applies only to runtime_setup and evaluation tools
                    starred=False,
                    executable=True,
                )
            )
            eval_scripts.append(
                self._template.render(
                    solution=solution,
                    setup_eval_imports=this_state_imports,
                    query=this_state_input,
                    undefined=StrictUndefined,
                )
            )
        return eval_scripts

    def get_solution_feedback(
        self, solution: Solution, import_lenient: bool = False
    ) -> list[Message]:
        """Execute the agent solution and provide a feedback messages
        to inform the agent of their task performance. If exceptions
        occur, agent is allowed to re-attempt the solution unless they
        had an undesirable effect on the runtime (case in which a
        SolutionError is raised).

        Returns
        -------
        messages
            A list of messages, each corresponding to a test case for
            the solution. If an error occurred, the `tool_call_exception`
            field will be populated with the exception message.

        Raises
        ------
        SolutionError
            If the solution had an undesirable effect on the runtime.
            Agent should catch this error and solve the next query.
        """
        if solution.query in self.failed_queries:
            raise SolutionError(
                "Solution re-attempt disallowed because the previous "
                "solution had an undesirable effect on the runtime. "
                "Please proceed to the next query"
            )

        messages = []
        for script in self._get_eval_scripts(solution):
            feedback = execute_script(script, RoleType.EXECUTION_ENVIRONMENT)
            try:
                assert_no_side_effects(feedback.tool_call_exception)
            except AssertionError:
                if import_lenient:
                    self._import_lenient_correct[solution.query] = False
                else:
                    self.failed_queries.add(solution.query)
                    self._correct[solution.query] = False
                    self._import_lenient_correct[solution.query] = False
                    self._side_effect_feedback = [feedback]
                    self.total_err_count += 1
                raise SolutionError("Incorrect solution. Proceed to the next query.")
            messages.append(feedback)
        is_correct = solution_correct(messages)
        if import_lenient:
            self._import_lenient_correct[solution.query] = is_correct
        else:
            self._correct[solution.query] = is_correct
            self._import_lenient_correct[solution.query] = is_correct
            self.total_err_count += int(not is_correct)
            self.handback_control_err_count += int(
                (not is_correct) and handback_control(messages)
            )
        return messages

    def get_primitives_selection_feedback(
        self, solution: Solution, ground_truth_program: str
    ) -> PrimitivesSelectionResult:
        retrieved_symbol_names = (
            {s.obj_name for s in solution.primitives_selection_symbols}
            if solution.primitives_selection_symbols
            else set()
        )
        ground_truth_symbols = dedup_and_sort_symbols(
            get_apps_symbols_from_program(ground_truth_program)
        )
        ground_truth_symbol_names = {s.obj_name for s in ground_truth_symbols}

        if not ground_truth_symbol_names and not retrieved_symbol_names:
            precision, recall, f1 = 1.0, 1.0, 1.0
        elif not ground_truth_symbol_names:
            recall = 1.0
            intersection = len(
                retrieved_symbol_names.intersection(ground_truth_symbol_names)
            )
            precision = intersection / len(retrieved_symbol_names)
            f1 = self._calc_f1(precision, recall)
        elif not retrieved_symbol_names:
            precision, recall, f1 = 0.0, 0.0, 0.0
        else:
            intersection = len(
                retrieved_symbol_names.intersection(ground_truth_symbol_names)
            )
            precision = intersection / len(retrieved_symbol_names)
            recall = intersection / len(ground_truth_symbol_names)
            f1 = self._calc_f1(precision, recall)
        retrieval_result = PrimitivesSelectionResult(
            precision=precision,
            recall=recall,
            f1=f1,
            retrieved_symbol_names=retrieved_symbol_names,
            ground_truth_symbol_names=ground_truth_symbol_names,
        )
        self._tr_result_per_query[solution.query] = retrieval_result
        return retrieval_result

    @property
    def side_effect_feedback(self) -> list[Message]:
        """Returns a list with a single message indicating that a SolutionError was raised."""
        to_return = deepcopy(self._side_effect_feedback)
        self._side_effect_feedback = []
        return to_return

    @property
    def no_solution_feedback(self) -> list[Message]:
        """Some models do not generate a valid program. We
        return a dummy feedback message to identify such
        cases in results."""
        return [
            Message(
                sender=RoleType.EXECUTION_ENVIRONMENT,
                recipient=RoleType.AGENT,
                content="Error: The given code was incomplete and could not be executed",
                tool_call_exception="Error: The given code was incomplete and could not be executed",  # noqa
            )
        ]


class EvaluationResult(BaseModel):
    """Result of evaluating a single query.

    Parameters
    ----------
    reference_free_correct
        A flag indicating whether the solution is correct predicted
        by an LLM prompted with pairs of correct/incorrect plans
    reference_free_correct_explanation
        An explanation generated by an LLM evaluator explaining
        why the plan was assessed as `reference_free_correct`

    """

    query_id: str
    query: str
    solution: ProgramStr
    ground_truth_solution: ProgramStr
    feedback: list[Message]
    prompt: LLMPrompt
    raw_completion: str | None = None
    state_generation_programs: list[ProgramStr] | None = None
    evaluation_programs: list[ProgramStr] | None = None
    correct: bool
    import_lenient_correct: bool
    import_lenient_feedback: list[Message] | None = None
    reference_free_correct: bool | str | None = None
    reference_free_correct_explanation: str | None = None
    primitives_selection_result: PrimitivesSelectionResult | None = None

    def format_feedback(self) -> str:
        """Format the exceptions raised during the execution."""
        exceptions = []
        for msg in self.feedback:
            if msg.tool_call_exception is not None:
                exceptions.append(msg.tool_call_exception)
        return "\n".join(exceptions) or "Solution Correct"

    def make_executable_script(
        self, scenario: Scenario, gold_source_dir: str | Path, output_dir: str | Path
    ):
        """Create a python module containing the predicted solution
        and the gold evaluation assets (ie env initialisation programs
        and post-conditions check scripts) along with endpoint code to run it.

        Parameters
        ----------
        gold_source_dir
            The directory where the ground truth solutions are located.
        output_dir
            The directory where the evaluator output will be stored.
        """
        if isinstance(output_dir, str):
            output_dir = Path(output_dir)
        source_dir = Path(gold_source_dir)
        eval_assets: AnnotatedPrograms = parse_plans_and_evaluation_assets(
            self.query_id, source_dir
        )
        executable_assets = deepcopy(eval_assets)
        executable_assets.plan = self.solution
        executable_assets.write_script(self.query_id, scenario, output_dir)


class IteratorMixin:
    def __init__(self, in_path: Path, **kwargs):
        with open(in_path, "r") as f_in:
            self._results = [
                EvaluationResult.model_validate(json.loads(line)) for line in f_in
            ]
        self._current_index = 0

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> EvaluationResult:
        if self._current_index >= len(self._results):
            raise StopIteration
        current = self._results[self._current_index]
        self._current_index += 1
        return current

    @property
    def len(self) -> int:
        return len(self._results)

    @property
    def ix(self) -> int:
        return self._current_index

    def prev(self) -> None:
        self._current_index = max(self._current_index - 2, 0)

    def same(self) -> None:
        self._current_index = max(self._current_index - 1, 0)


class EvalResultIterator(IteratorMixin):
    def __init__(self, in_path: Path, just_errors: bool) -> None:
        super().__init__(in_path)
        if just_errors:
            self._results = [r for r in self._results if not r.correct]


class ResultIteratorForEvalComparison(IteratorMixin):
    """

    Parameters
    ----------
    just_differences
        Filter out data points where the evaluators agree.

    """

    def __init__(self, in_path: Path, just_differences: bool) -> None:
        super().__init__(in_path)

        if just_differences:
            self._results = [
                r for r in self._results if r.correct != r.reference_free_correct
            ]
