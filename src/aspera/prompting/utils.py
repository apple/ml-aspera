#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import abc
from abc import abstractmethod
from copy import deepcopy
from typing import Any, Callable

from jinja2 import Environment, meta

from aspera.utils import snake_case

EXCLUDE_VARIABLES = {
    "loop",
    "self",
    "context",
    "macros",
    "request",
    "session",
    "g",
    "url_for",
    "config",
}


class TemplateMixin(abc.ABC):
    def __init__(
        self,
        template_factory: Callable[[], str] = lambda: "",
        filters: list[Callable[[Any], str]] = None,
    ):
        self._template_generator = template_factory
        self._template_variables: set[str] = set()
        self._template = None
        self._filters = filters

    def initialize(self, environment: Environment) -> None:
        self._set_filters(environment)
        self._set_template_and_variables(environment)

    def _set_template_and_variables(self, environment: Environment):
        template_variables = meta.find_undeclared_variables(
            environment.parse(self._template_generator())
        )
        self._template = environment.from_string(self._template_generator())
        self._template_variables = template_variables.difference(EXCLUDE_VARIABLES)

    def _set_filters(self, environment: Environment):
        if self._filters is None:
            return
        for f in self._filters:
            try:
                environment.filters[snake_case(f.__name__)] = f
            except AttributeError:
                environment.filters[snake_case(f.__class__.__name__)] = f

    def _get_variables_from_kwargs(self, variable: str, request: Any, **kwargs) -> str:

        value = kwargs.get(variable)
        if value is None and getattr(self, variable, None) is None:
            raise AttributeError(
                f"Undefined variable {variable} for template {self.__class__.__name__}"
            )
        return str(value)

    def _get_template_variables(self, request: Any, **kwargs: Any) -> dict[str, Any]:
        """Resolve the variables from the prompt template.
        To be resolved, a template variable must
        have a corresponding method named `_get_${variable_name}`
        which returns its value.
        """
        template_variables: set = deepcopy(self._template_variables)
        vars, vals = [], []
        while template_variables:
            variable = template_variables.pop()
            try:
                value = getattr(self, f"_get_{variable}")(request, **kwargs)
            except AttributeError:
                try:
                    value = self._get_variables_from_kwargs(variable, request, **kwargs)
                except AttributeError:
                    if isinstance(request, dict):
                        value = request.get(variable, None)
                    else:
                        value = getattr(request, variable, None)
                    if value is None:
                        raise AttributeError(
                            f"Undefined variable {variable} for template {self.__class__.__name__}"
                        )
            vars.append(variable)
            vals.append(value)
        return dict(zip(vars, vals))

    @abstractmethod
    def get_prompt(self, request: Any, **kwargs: Any) -> str:
        raise NotImplementedError
