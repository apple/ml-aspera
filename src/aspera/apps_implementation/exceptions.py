#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
class ParseError(Exception):
    pass


class EventDefinitionError(Exception):
    pass


class SearchError(Exception):
    pass


class RequiresUserInputError(Exception):
    pass


class RequiresUserInput(Exception):
    pass


def assert_requires_input_error(tool_exception: str | None):
    if tool_exception is None:
        return
    assert RequiresUserInput.__name__ in tool_exception, tool_exception
