#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import ast
import importlib
import inspect
import textwrap
from typing import Any, Callable

from jinja2 import Environment, StrictUndefined
from rich.prompt import Prompt

from aspera.aliases import FunctionName, ModuleName, ProgramStr
from aspera.code_utils.utils import (
    filter_for_functions_or_classes,
    get_source_code_for_apps,
    nodes_to_source,
    remove_import_statements,
)
from aspera.completer.utils import ChatMessage, ChatRole
from aspera.constants import EVALUATION_TOOLS_PATH, EXAMPLES_ROOT, SIMULATION_TOOLS_PATH
from aspera.dataset_schema import DataPoint, EditedDataPoint, function_name_parser
from aspera.interactive.console_messages import TODOS_INSTRUCTION
from aspera.interactive.display import display_function_template
from aspera.prompting.prompt_utils import parse_tools
from aspera.prompting.user_turn_prompt_formatters import EditFeedbackFormatter
from aspera.prompting.user_turn_templates import annotation_edit_feedback, start_turn
from aspera.prompting.utils import TemplateMixin
from aspera.scenario import Scenario


class TemplateError(Exception):
    pass


class UserTurnTemplate(TemplateMixin):
    def __init__(
        self,
        template_factory=start_turn,
        filters: list[Callable[[Any], str]] = None,
    ):
        super().__init__(template_factory=template_factory, filters=filters)
        environment = Environment()
        self.initialize(environment)

    def get_prompt(self, request: Any, **kwargs: Any) -> ChatMessage:
        template_vars = self._get_template_variables(request, **kwargs)
        message: ChatMessage = {
            "role": ChatRole.USER,
            "content": self._template.render(
                **template_vars,
                undefined=StrictUndefined,
            ),
        }
        return message


class QueryHistoryUserTurnTemplate(UserTurnTemplate):
    def _get_queries(self, request: Any, **kwargs: Any) -> list[Any]:
        assert "queries" in kwargs
        return kwargs.get("queries", [])


class ProgramGenerationFeedbackUserTurnTemplate(UserTurnTemplate):

    def __init__(
        self,
        template_factory=annotation_edit_feedback,
        filters: list[Callable[[Any], str]] = None,
    ):
        if filters is None:
            super().__init__(
                template_factory=template_factory, filters=[EditFeedbackFormatter()]
            )
        else:
            super().__init__(template_factory=template_factory, filters=filters)


class RuntimeEnvironmentSetupUserTurnTemplate(UserTurnTemplate):
    setup_program_template: str = textwrap.dedent(
        '''\
    def setup_env_{function_name}():
        """Simulate the environment for the query:

        {query}

        Note this means to create any persons, contacts, emails, events
        and everything that should exist in the user's virtual context when
        they make the query. You **should not** create new entities that
        are implied in the user request that the assistant has created in
        the `{function_name}` function.
        """
    '''
    )

    def _filter_code(self, tool_list: list[str], tools_module_path: str, **kwargs):
        """Filter modules to contain members specified in the tool list.

        Parameters
        ----------
        tool_list
            A list where members are in the format module::tool_name.
        tools_module_path
            The path where the modules implementing the tools can be found.
        """

        tools: dict[ModuleName, list[FunctionName]] = parse_tools(tool_list)
        if not tools:
            raise TemplateError("Could not parse tools, none were specified.")
        code_str = ""
        for module, fcns in tools.items():
            source_module = inspect.getsource(
                importlib.import_module(f"{tools_module_path}.{module}")
            )
            # nb: disadvantage of using ast.unparse is that we lose linting
            this_module_code = nodes_to_source(
                filter_for_functions_or_classes(ast.parse(source_module), fcns)
            )
            code_str += f"# {module}.py\n\n{this_module_code}\n\n"
        return code_str

    def _get_setup_code(self, scenario: Scenario, **kwargs) -> str:
        """Read implementations of tools LLM can use to setup runtime
        state from the codebase."""
        return self._filter_code(
            scenario.simulation_tools, tools_module_path=SIMULATION_TOOLS_PATH, **kwargs
        )

    def _read_examples(self, from_modules: list[str]) -> str:
        examples_src = [f"{EXAMPLES_ROOT}.{module}" for module in from_modules]
        code = [
            remove_import_statements(source)
            for source in get_source_code_for_apps(examples_src)
        ]
        return "\n".join(code)

    def _get_runtime_setup_examples(self, scenario: Scenario, **kwargs) -> str:
        return self._read_examples(scenario.runtime_setup)

    def maybe_update_with_dynamic_instructions(self, query: str, program_def: str):
        """Ask the data curator to add instructions to help guide the generation
        of the program.

        Parameters
        ----------
        query
        program_def
            The signature and docstring of a program the LLM needs to write.
        """
        display_function_template(program_def)
        instructions = Prompt.ask(TODOS_INSTRUCTION.format(**{"query": query}))
        if instructions:
            program_def = self.update_with_instructions(
                program_def, instructions.split("::")
            )
        return program_def

    @staticmethod
    def update_with_instructions(template: str, instructions: list[str]) -> str:
        """Update the template with instructions provided by the data curator."""
        if not instructions:
            return template
        instruction_str = f"\t# TODO: {instructions[0]}\n"
        for instr in instructions[1:]:
            instruction_str += f"\t# TODO: {instr}\n"
        instruction_str = instruction_str.strip("\n")
        template = textwrap.dedent(f"{template}\n\n{instruction_str}")
        return template

    def render_runtime_setup_program_templ(
        self, example: DataPoint | EditedDataPoint
    ) -> str:
        """Returns the signature and docs of a function the LLM has to write
        to set the environment state."""
        query = example.query
        fields = {
            "query": query,
            "function_name": example.plan_name,
        }
        rendered = self.setup_program_template.format(**fields).strip()
        return self.maybe_update_with_dynamic_instructions(query, rendered)


class EvaluationCodeGenerationUserTurnTemplate(RuntimeEnvironmentSetupUserTurnTemplate):

    eval_program_template: str = textwrap.dedent(
        '''\
    def evaluate_{function_name}(
        query: str, executable: Callable[[], Any], setup_function: Callable[[], Any]
    ):
        """Validate that `executable` program for the query

        {query}

        has the expected effect on the runtime environment.

        Parameters
        ----------
        query
            The query to validate.
        executable
            The query execution function, `{function_name}`
        setup_function
            `{setup_function_name}` function.
        """
    '''
    )

    skip_eval_program_template: str = '''
    def evaluate_{function_name}(
        query: str, executable: Callable[[], Any], setup_function: Callable[[], Any]
    ):
        """Validate that `executable` program for the query

        {query}

        has the expected effect on the runtime environment.

        Parameters
        ----------
        query
            The query to validate.
        executable
            The query execution function, `{function_name}`
        setup_function
            `{setup_function_name}` function.
        """
        pass
    '''

    def render_eval_program_templ(
        self, example: DataPoint | EditedDataPoint, runtime_setup_program: ProgramStr
    ) -> str:
        """Returns the signature and docs of a function the LLM
        has to write to check the query was correctly executed."""
        query = example.query
        fields = {
            "query": query,
            "function_name": example.plan_name,
            "setup_function_name": function_name_parser(runtime_setup_program),
        }
        rendered = self.eval_program_template.format(**fields).strip()
        return self.maybe_update_with_dynamic_instructions(query, rendered)

    @staticmethod
    def render_skip_eval_template(example: DataPoint | EditedDataPoint) -> str:
        fields = {
            "query": example.query,
            "function_name": example.plan_name,
            "setup_function_name": example.setup_function_name,
        }
        template = (
            EvaluationCodeGenerationUserTurnTemplate.skip_eval_program_template.format(
                **fields
            ).strip()
        )
        return template

    def _get_testing_code(self, scenario: Scenario, **kwargs) -> str:
        return self._filter_code(
            scenario.evaluation_tools, tools_module_path=EVALUATION_TOOLS_PATH, **kwargs
        )

    def _get_evaluation_examples(self, scenario: Scenario, **kwargs) -> str:
        return self._read_examples(scenario.evaluation)
