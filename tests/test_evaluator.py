#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import shutil
import textwrap
from pathlib import Path
from typing import Iterator

import pytest

from aspera.code_utils.utils import get_imports
from aspera.evaluator import Evaluator, Solution
from aspera.execution_evaluation_tools_implementation.exceptions import SolutionError

DATA_DIR = "asper_bench"

PLANS_DIR = Path(__file__).parent.parent / DATA_DIR / "plans"


@pytest.fixture(params=[PLANS_DIR])
def evaluator(request, tmp_path_factory):
    temp_dir = tmp_path_factory.mktemp("plans_test_copy")
    shutil.copytree(request.param, temp_dir, dirs_exist_ok=True)
    return Evaluator(temp_dir)


def ground_truth_executables(evaluator: Evaluator) -> Iterator[Solution]:
    for query, annotation in evaluator._annotations.items():
        imports = get_imports(annotation.scenario, executable=True)
        import_str = "".join(imports)
        soln = textwrap.dedent(f"{import_str}{annotation.program}")
        yield Solution(query=query, program=soln)


def error_executables(error: str, evaluator: Evaluator) -> Iterator[Solution]:
    for query, annotation in evaluator._annotations.items():
        imports = get_imports(annotation.scenario, executable=True)
        import_str = "".join(imports)
        err_progr = textwrap.dedent(
            f"""\
            def dummy_program():
                raise {error}("Testing")
            """
        )
        err_soln = textwrap.dedent(f"{import_str}{err_progr}")
        yield Solution(query=query, program=err_soln)


def test_ground_truth_evaluation(evaluator: Evaluator):
    for solution in ground_truth_executables(evaluator):
        _ = evaluator.get_solution_feedback(solution)
    assert evaluator.get_score() == 100.0


def test_programs_with_errors(evaluator: Evaluator):
    req_user_input_queries = [
        """Hey, [Assistant], share my calendar with my assistant."""
    ]

    error = RuntimeError.__name__
    for solution in error_executables(error, evaluator):
        print(solution)
        try:
            feedback = evaluator.get_solution_feedback(solution)
            assert error in feedback[0].tool_call_exception
        except SolutionError:
            assert solution.query in req_user_input_queries
    assert evaluator.get_score() == 0.0


def test_programs_with_solution_errors(evaluator: Evaluator):

    error = SolutionError.__name__
    i = 0
    for i, solution in enumerate(error_executables(error, evaluator), start=i):
        with pytest.raises(SolutionError):
            _ = evaluator.get_solution_feedback(solution)

    assert len(evaluator.failed_queries) == i + 1
    assert evaluator.get_score() == 0.0
