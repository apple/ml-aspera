#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
from collections import defaultdict

from aspera.aliases import FunctionName, ModuleName


def parse_tools(
    tools: list[str] | None,
) -> dict[ModuleName, list[FunctionName]] | None:
    """Parse tools from module::function_name format to a dict where
    keys are module names and values are list of functions implemented
    in that module."""

    if tools is None:
        return
    module_to_tool = defaultdict(list)
    for tool in tools:
        module, fcn_name = tool.split("::")
        module_to_tool[module].append(fcn_name)
    return dict(module_to_tool)


def ignore_prefix_before(input_: str, pattern: str) -> str:
    """Ignore the prefix before the given pattern."""
    start = input_.find(pattern)
    if start == -1:
        return input_
    return input_[start:]
