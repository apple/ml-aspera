#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
from typing import Any, Callable

from jinja2 import Environment, StrictUndefined

from aspera.completer.utils import ChatMessage
from aspera.prompting.utils import TemplateMixin


class PrimitivesSelectionTemplate(TemplateMixin):
    def __init__(
        self,
        template_factory: Callable[[], str],
    ):
        super().__init__(template_factory=template_factory)
        environment = Environment()
        self.initialize(environment)

    def get_prompt(self, request: Any, **kwargs: Any) -> ChatMessage:
        template_vars = self._get_template_variables(request, **kwargs)
        message: ChatMessage = {
            "role": "system",
            "content": self._template.render(
                **template_vars,
                undefined=StrictUndefined,
            ),
        }
        return message


class UserTurnPrimitivesSelectionTemplate(PrimitivesSelectionTemplate):

    def get_prompt(self, request: Any, **kwargs: Any) -> ChatMessage:

        message = super().get_prompt(request, **kwargs)
        message["role"] = "user"
        return message
