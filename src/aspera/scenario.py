#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
from pydantic import BaseModel, field_validator

from aspera.aliases import AppName, EvaluationTool, ExamplesModule, SimulationTool
from aspera.code_utils.code_symbol import CodeSymbol


class Guidelines(BaseModel):
    generation_labelling: list[str] | None
    runtime_setup: list[str] | None
    evaluation: list[str] | None


class Scenario(BaseModel):
    """
    apps
        Apps from which the query and its solution
        are to be composed.
    query_solution
        Modules containing `python` programs that
        execute sample user queries.
    runtime_setup
        Modules containing `python` programs that
        show the LLM how to setup the runtime env
        for a given query.
    evaluation
        Modules containing `python` programs that
        show the LLM how to write evaluation
        scripts for a given query.
    guidelines
        Standing instructions the data curator may
        provide for generation/labelling prompts,
        or during environment setup or testing code
        generation.
    simulation_tools
        Tools shown to the LLM for setting up
        runtime environment.
    evaluation_tools
        Tools shown to the LLM for writing evaluation
        code.
    symbols_in_apps
        Specific symbols in `apps` to show in the prompt
    """

    apps: list[AppName]
    query_solution: list[ExamplesModule]
    runtime_setup: list[ExamplesModule] | None = None
    evaluation: list[ExamplesModule] | None = None
    guidelines: Guidelines | None = None
    simulation_tools: list[SimulationTool] | None = None
    evaluation_tools: list[EvaluationTool] | None = None
    symbols_in_apps: list[CodeSymbol] | None = None

    @field_validator("symbols_in_apps", mode="before")
    @classmethod
    def validate_symbols_in_apps(cls, v: str | list[str]) -> list[str] | None:
        if isinstance(v, str):
            try:
                assert not v
                return
            except AssertionError:
                raise ValueError(f"Incorrect value {v} for symbols_in_apps")
        return v
