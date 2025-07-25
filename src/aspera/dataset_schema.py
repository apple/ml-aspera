#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
"""Structured types used by the interactive sessions for data collection."""

import ast
import logging
import textwrap
from functools import cached_property
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, field_validator
from pydantic_core.core_schema import ValidationInfo

from aspera.aliases import ProgramStr
from aspera.code_utils.utils import get_imports
from aspera.completer.utils import MessageList, TokenCounter
from aspera.constants import (
    EVALUATION_PROGRAM_FUNCTION_NAME_PREFIX,
    IMPLEMENTATIONS_ROOT,
    PACKAGE_NAME,
    RUNTIME_SETUP_PROGRAM_FUNCTION_NAME_PREFIX,
)
from aspera.execution_evaluation_tools_implementation.exceptions import SolutionError
from aspera.parser import ExtractFunctionName, ProgramFinderError
from aspera.scenario import Scenario

logger = logging.getLogger(__name__)

function_name_parser = ExtractFunctionName()


class DataPoint(BaseModel):
    query_id: str
    program: ProgramStr
    query: str
    scenario: Scenario | None
    state_generation_programs: list[ProgramStr] | None = None
    evaluation_programs: list[ProgramStr] | None = None

    @cached_property
    def plan_name(self) -> str:
        try:
            return function_name_parser(self.program)
        except ProgramFinderError:
            return ""

    @property
    def curated_program(self):
        return self.program

    @property
    def setup_function_name(self) -> str:
        # generate a default name for the setup function - use for
        # prompt building in data gen
        if self.state_generation_programs is None:
            return f"{RUNTIME_SETUP_PROGRAM_FUNCTION_NAME_PREFIX}_{self.plan_name}"
        # parse the function name of an existing setup function
        plan_name = function_name_parser(self.state_generation_programs[0])
        if self.state_generation_programs:
            if len(self.state_generation_programs) > 1:
                logger.warning(
                    "There were multiple runtime functions defined, returning the name"
                    "of the first one."
                )
            return f"{plan_name}"
        return f"{plan_name}"

    @property
    def test_function_name(self) -> str:
        # generate a default name for the evaluation function - use for prompt
        # building in data generation
        if self.evaluation_programs is None:
            return f"{EVALUATION_PROGRAM_FUNCTION_NAME_PREFIX}_{self.plan_name}"
        # parse the function name of an existing eval function
        plan_name = function_name_parser(self.evaluation_programs[0])
        if self.evaluation_programs:
            if len(self.evaluation_programs) > 1:
                logger.warning(
                    "There were multiple evaluation functions defined, returning the name"
                    "of the first one"
                )
        return plan_name

    @property
    def contains_edits(self) -> bool:
        return False

    def update_with_runtime_state_generation_programs(
        self,
        state_generation_code: "AnnotatedDatapoints",
    ):
        maybe_edited_programs = [e.curated_program for e in state_generation_code.all]
        self.state_generation_programs = maybe_edited_programs


class EditedDataPoint(DataPoint):
    edited_program: str
    feedback: str

    @cached_property
    def plan_name(self):
        return function_name_parser(self.edited_program)

    @property
    def contains_edits(self) -> bool:
        return True

    @property
    def curated_program(self):
        return self.edited_program

    @property
    def misedited(self) -> bool:
        syntax_err = False
        try:
            _ = ast.parse(self.program)
            _ = ast.parse(self.edited_program)
        except SyntaxError:
            try:
                _ = ast.parse(self.edited_program)
            except SyntaxError:
                logger.warning("Edited program has a syntax error")
            else:
                logger.warning("Original program has a syntax error")
            syntax_err = True
        return self.edited_program == self.program or syntax_err

    @field_validator("state_generation_programs", "evaluation_programs", mode="before")
    @classmethod
    def validate_symbols_in_apps(
        cls, v: str | list[str], info: ValidationInfo
    ) -> list[str] | None:
        if isinstance(v, str):
            try:
                assert not v
                return
            except AssertionError:
                raise ValueError(f"Incorrect value {v} for {info.field_name} ")
        return v


class DiscardedDataPoint(DataPoint):
    comment: str


class EnvironmentState(BaseModel):
    """Stores the state before/after running the query."""

    query: str
    query_id: str
    initial_states: list[dict[Literal["dbs"], dict]]
    final_states: list[dict[Literal["dbs"], dict]]


class AnnotatedDatapoints(BaseModel):
    edited: list[EditedDataPoint]
    discarded: list[DiscardedDataPoint]
    correct: list[DataPoint]
    all: list[DataPoint | DiscardedDataPoint | EditedDataPoint]


class SessionLog(BaseModel):
    chat_history: MessageList
    last_user_turn: str
    completion: str
    budget: TokenCounter
    queries: list[str]
    unparsed_queries: list[str] | None = None


def cast_to_datapoint(datapoint: EditedDataPoint | DataPoint) -> DataPoint:
    """Remove information specific to EditedDatapoints from the input. The
    `program` field of the output is replaced by the `edited_program` field
    of the input."""
    if not datapoint.contains_edits:
        return datapoint
    new_example = {"program": datapoint.edited_program}
    for k in DataPoint.model_fields:
        if k not in new_example:
            new_example[k] = getattr(datapoint, k)
    return DataPoint(**new_example)


def create_datapoints(
    programs: list[str],
    queries: list[str],
    scenario: Scenario,
    unprocessed_queries: list[str] | None = None,
) -> list[DataPoint]:
    """Creates a list of datapoints for a set of programs and queries."""
    try:
        assert len(programs) == len(queries)
    except AssertionError:
        logger.warning(
            f"The length of programs ({len(programs)}) and queries ({queries}) do not match."
        )
        assert len(queries) > len(programs)
        if unprocessed_queries is not None:
            unprocessed_queries.extend(queries[len(programs) :])
        queries = queries[: len(programs)]
    data_points: list[DataPoint] = [
        DataPoint(
            **{
                "query_id": str(i),
                "program": programs[i],
                "query": queries[i],
                "scenario": scenario,
            }
        )
        for i in range(len(queries))
    ]
    return data_points


EVAL_ENTRY_POINT_TEMPLATE = """\
    if __name__ == '{module_name}':
        from aspera.simulation.execution_context import ExecutionContext, new_context

        context = ExecutionContext()
        with new_context(context):
            {test_function_name}(
                query="",
                executable={plan_name},
                setup_function={setup_function_name},
            )
    """


def get_eval_entry_point_code(
    example: DataPoint,
    module_name: str = "__main__",
) -> str:
    """Render a template that can be added to a .py file to run an arbitrary function
    in the sandbox environment."""
    data = {
        "test_function_name": example.test_function_name,
        "plan_name": example.plan_name,
        "setup_function_name": example.setup_function_name,
        "module_name": module_name,
    }
    template = textwrap.dedent(EVAL_ENTRY_POINT_TEMPLATE).format(**data)
    return template


class AnnotatedPrograms(BaseModel):
    plan: ProgramStr
    state: list[ProgramStr]
    eval: list[ProgramStr]

    @property
    def _programs(self) -> str:
        """Returns a string that concatenates the programs"""
        example = DataPoint(
            query_id="",
            query="",
            program=self.plan,
            state_generation_programs=self.state,
            evaluation_programs=self.eval,
            scenario=None,
        )

        entry_point = get_eval_entry_point_code(example)  # noqa
        state_progr_str = "\n\n".join([s for s in self.state])
        eval_progr_str = "\n\n".join([s for s in self.eval])
        return "\n\n".join([self.plan, state_progr_str, eval_progr_str, entry_point])

    def write_script(
        self,
        query_id: str,
        scenario: Scenario,
        odir: Path,
        filter_app_impl_imports: bool = True,
    ):
        """Write the programs into a script that can be executed in the
        sandbox environment."""
        imports = get_imports(
            scenario,
            import_simulation_tools=True,
            import_testing_tools=True,
            executable=True,
            starred=True,
        )
        if filter_app_impl_imports:
            imports = [
                stmt
                for stmt in imports
                if f"{PACKAGE_NAME}.{IMPLEMENTATIONS_ROOT}" not in stmt
            ]
        content = f"{''.join(imports)}\n\n{self._programs}"
        file = odir / f"query_{query_id}.py"
        with open(file, "w") as corrections_file:
            corrections_file.writelines(content)
