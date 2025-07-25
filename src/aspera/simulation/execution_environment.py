#
# For licensing see accompanying LICENSE file.
# Copyright © 2024-2025 Apple Inc. All Rights Reserved.
#
import code
import io
import traceback
from contextlib import redirect_stderr, redirect_stdout

from attrs import field
from pydantic import BaseModel

from aspera.aliases import ImportStr, ProgramStr
from aspera.parser import ExtractFunctionName
from aspera.simulation.execution_context import RoleType, get_current_context

function_name_parser = ExtractFunctionName()


class Message(BaseModel):
    """Messages each role reads and writes"""

    sender: RoleType = field(converter=RoleType)
    recipient: RoleType = field(converter=RoleType)
    content: str
    # Optional field for storing exceptions that occurred as part of the tool call.
    tool_call_exception: str | None = None
    # Optional field tracing tool execution for this message
    tool_trace: list[str] | None = None
    # If the conversation ended unexpectedly with an exception,
    # the exception is saved in termination_stack_trace
    termination_stack_trace: str | None = None
    # Message visibility. By default, should be visible to sender and recipient
    visible_to: list[RoleType] | None = None

    def __attrs_post_init__(self) -> None:
        # Bypass frozen. See https://github.com/python-attrs/attrs/issues/120.
        # Assign default visibility
        if self.visible_to is None:
            object.__setattr__(self, "visible_to", [self.sender, self.recipient])


class BaseRole:
    """Base class for all roles. A role is an object that can read and write
    messages from execution context. A role could be a dialog agent, a user simulator,
    a code execution environment and more.

    At this point roles are designed to be stateless.
    State representations are stored in execution context database
    """

    role_type: RoleType | None = None


def execute_script(program: str, role_type: RoleType) -> Message:
    """Execute a `python` script in an interactive console.

    Parameters
    ----------
    program
        The program to execute, including all the imports from the library.
    """
    context = get_current_context()
    console = context.interactive_console
    # First compile the code string to a command, which checks if the command is
    # valid and complete (regarding completeness see `if command is None` below for
    # details). Note that we cannot use the default `symbol=single` since that assumes
    # that we want to only generate a single statement. This would result in a syntax
    # error for e.g. `a = 1\nb = 2` saying
    #    "multiple statements found while compiling a single statement"
    try:
        command = code.compile_command(program, symbol="exec")
    except (OverflowError, SyntaxError, ValueError):
        # We do not want to leak details like the code path so we only include the
        # actual exception in the traceback.
        traceback_str = traceback.format_exc(limit=0)
        return Message(
            sender=role_type,
            recipient=RoleType.AGENT,
            content=traceback_str,
            tool_call_exception=traceback_str,
        )
    if command is None:
        # `None` is returned when the given code string is incomplete. An example
        # would be `code.compile_command("if True:")`. The LLM should not generate
        # such code so we consider this an error/failure.
        response = f"Error: The given code was incomplete and could not be executed: '{program}'"
        return Message(
            sender=role_type,
            recipient=RoleType.AGENT,
            content=response,
            tool_call_exception=response,
        )
    # Open StringIO and capture stdout && stderr from env
    with (
        io.StringIO() as f_stdout,
        io.StringIO() as f_stderr,
        redirect_stdout(f_stdout),
        redirect_stderr(f_stderr),
    ):
        # Execute the code. At this point we know that the code is valid Python, but it
        # can still throw exceptions.
        console.runcode(command)
        stdout_message = f_stdout.getvalue()
        stderr_message = f_stderr.getvalue()
        # Start with stdout, it ends with newline
        content_lines = stdout_message.rstrip().split("\n") if stdout_message else []
        exception_str = None
        if stderr_message:
            stderr_lines = stderr_message.rstrip().split("\n")
            exception_str = stderr_lines[-1]
            content_lines.append(exception_str)
    return Message(
        sender=role_type,
        recipient=RoleType.AGENT,
        content="\n".join(content_lines),
        tool_call_exception=exception_str,
    )


class ExecutionEnvironment(BaseRole):
    """An Execution Environment able to execute python code in an REPL console in a stateful manner
    Note that this happens in the same process and thread as your main process,
    just under a different scope.
    """

    role_type: RoleType = RoleType.EXECUTION_ENVIRONMENT

    def execute(self, program: ProgramStr, imports: ImportStr) -> Message:
        function_name = function_name_parser(program)
        return execute_script(
            f"{imports}\n\n{program}\n\n{function_name}()", role_type=self.role_type
        )
