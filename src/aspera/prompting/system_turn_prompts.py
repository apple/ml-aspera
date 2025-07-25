#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
from pathlib import Path
from typing import Any

from jinja2 import Environment, StrictUndefined

from aspera.code_utils.utils import (
    get_imports_and_docstring_from_file,
    get_source_code_for_apps,
    get_source_code_for_symbols_used_in_program,
    make_prompt_code_string,
    remove_import_statements,
)
from aspera.completer.utils import ChatMessage, ChatRole
from aspera.constants import APP_DOCS_ROOT, DOCS_ROOT, EXAMPLES_ROOT, ExamplesModuleName
from aspera.prompting.system_turn_templates import (
    simple_program_generation_with_structure_guidelines,
)
from aspera.prompting.utils import TemplateMixin
from aspera.scenario import Scenario


class SystemTurnTemplate(TemplateMixin):
    def __init__(
        self, template_factory=simple_program_generation_with_structure_guidelines
    ):
        super().__init__(template_factory=template_factory)
        environment = Environment()
        self._set_template_and_variables(environment)

    def _get_code(self, scenario: Scenario, **kwargs) -> str:
        apps = [f"{APP_DOCS_ROOT}.{app}" for app in scenario.apps]
        code = [
            remove_import_statements(source)
            for source in get_source_code_for_apps(apps)
        ]
        code_str = ""
        for source, app in zip(code, scenario.apps):
            code_str += make_prompt_code_string(app, source)
        return code_str.strip()

    def _get_query_solution_examples(self, scenario: Scenario, **kwargs) -> str:
        examples_src = [
            f"{EXAMPLES_ROOT}.{module}" for module in scenario.query_solution
        ]
        code = [
            remove_import_statements(source)
            for source in get_source_code_for_apps(examples_src)
        ]
        return "\n".join(code)

    def get_prompt(self, request: Scenario, **kwargs) -> ChatMessage:
        template_vars = self._get_template_variables(request, **kwargs)
        message: ChatMessage = {
            "role": ChatRole.SYSTEM,
            "content": self._template.render(
                **template_vars,
                undefined=StrictUndefined,
            ),
        }
        return message

    def followup_generation(self, request: Any):
        """Generate more complex user queries given a list of initial generations."""
        raise NotImplementedError


class OracleSystemTurnTemplate(SystemTurnTemplate):
    """
    SystemTurnTemplate where we fetch specific definitions from source files rather than
    including all the source code in the prompt.
    """

    def _get_code(self, scenario: Scenario, **kwargs) -> str:
        apps = [f"{APP_DOCS_ROOT}.{app}" for app in scenario.apps]
        if not scenario.symbols_in_apps:
            raise AssertionError("No target symbols provided for oracle system prompt")
        source_code_per_file = get_source_code_for_symbols_used_in_program(
            apps, scenario.symbols_in_apps
        )
        code_str = ""
        for filename, source in source_code_per_file.items():
            source = remove_import_statements(source)
            filename_as_module = filename.replace("/", ".").split(f"{DOCS_ROOT}.")[1]
            code_str += f"# {filename_as_module}\n\n"
            imports_and_docstring = get_imports_and_docstring_from_file(Path(filename))
            if imports_and_docstring:
                code_str += f"{imports_and_docstring}\n\n"
            code_str += f"{source}\n\n"
        return code_str.strip()


class LLMEvaluatorSystemTurnTemplate(SystemTurnTemplate):

    def _get_evaluation_examples(
        self, request: Any, examples_module: ExamplesModuleName, **kwargs
    ) -> str:
        examples_src = [f"{EXAMPLES_ROOT}.{examples_module}"]
        return "\n".join(get_source_code_for_apps(examples_src))
