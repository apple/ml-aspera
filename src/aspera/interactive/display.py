#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import ast
import importlib
import inspect

from rich.console import Console
from rich.prompt import Prompt
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from aspera.aliases import ProgramStr, SimulationModuleName, SimulationToolName
from aspera.dataset_schema import DataPoint, EditedDataPoint
from aspera.interactive.console_messages import CODE_EDIT
from aspera.parser import ExtractSignature


def display_programs(queries: list[DataPoint], show_syntax_errors: bool = True):
    """Display a list of queries as a rich table with the following format

    ┏━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┓
    ┃ ID ┃ Query               ┃ Program       ┃ Syntax Error ┃
    ┡━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━┩
    """  # noqa

    console = Console()
    table = Table(show_header=True, header_style="bold magenta", expand=True)

    # Define columns
    table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column("Query", style="dim", width=40)
    table.add_column("Program", style="white")
    syntax_errors = []
    if show_syntax_errors:
        syntax_errors = [has_syntax_errors(example) for example in queries]
        table.add_column("Syntax Error", justify="center", style="red", no_wrap=True)

    for i, query in enumerate(queries):
        syntax = Syntax(
            query.program,
            "python",
            theme="monokai",
            line_numbers=True,
            word_wrap=False,
        )
        if show_syntax_errors:
            syntax_error = "YES" if syntax_errors[i] else "NO"
            table.add_row(str(i), query.query, syntax, syntax_error)
        else:
            table.add_row(str(i), query.query, syntax)

    console.print(table)


def display_edits(queries: list[EditedDataPoint]):
    """Display a list of queries alongside generated programs and
    curator edited version.

    ┏━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┓
    ┃ ID ┃ Query          ┃ Program       ┃ Edited Program ┃ Feedback      ┃
    ┡━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━┩
    """  # noqa

    query_col_width = 15
    feedback_col_width = 15

    console = Console()
    table = Table(show_header=True, header_style="bold magenta")

    # Define columns
    table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column("Query", style="dim", width=query_col_width)
    table.add_column("Program", style="white")
    table.add_column("Edited Program", style="white")
    table.add_column("Feedback", style="green", width=feedback_col_width)

    for i, query in enumerate(queries):
        syntax_program = Syntax(
            query.program,
            "python",
            theme="monokai",
            line_numbers=True,
            word_wrap=True,
        )
        syntax_edited_program = Syntax(
            query.edited_program,
            "python",
            theme="monokai",
            line_numbers=True,
            word_wrap=True,
        )

        table.add_row(
            str(i),
            query.query,
            syntax_program,
            syntax_edited_program,
            query.feedback,
        )

    console.print(table, width=None)


def display_queries(queries: list[str], ids: list[int] | None = None):
    """Display a list of queries as a `rich` table."""
    console = Console()
    table = Table(show_header=True, header_style="bold magenta", show_lines=True)
    table.add_column("Index", style="dim", width=6)
    table.add_column("Utterance")
    iterator = enumerate(queries, start=1) if not ids else zip(ids, queries)
    for i, utterance in iterator:
        table.add_row(str(i), utterance)
    console.print(table)


def display_edits_multitable(queries: list[EditedDataPoint]):
    """Display each edited program as a standalone table with the following
    format:

                                          Query ID: 1
    ┌──────────────────────────────────────────────────────────────────────────┐
    │ Query: Hey, [Assistant], plan an off-site event with my team this  │
    │ weekend at Central Park starting at 10 AM.                               │
    ├──────────────────────────────────────────────────────────────────────────┤
    │ Feedback: Refactored code to remove unnecessary comments and improve     │
    │ readability.                                                             │
    ├──────────────────────────────────────────────────────────────────────────┤
    │  Program                               Edited program                    │
    """
    console = Console()
    for i, query in enumerate(queries):
        table = Table(
            show_header=False,
            header_style="bold magenta",
            show_lines=True,
            title_style="bold magenta",
            title=f"Query ID: {str(i)}",
        )
        table.add_row(Text(f"Query: {query.query}", style="dim"))
        table.add_row(Text(f"Feedback: {query.feedback}", style="green"))
        syntax_program = Syntax(
            query.program,
            "python",
            theme="monokai",
            line_numbers=True,
            word_wrap=False,
        )
        syntax_edited_program = Syntax(
            query.edited_program,
            "python",
            theme="monokai",
            line_numbers=True,
            word_wrap=False,
        )
        programs_table = Table(
            show_header=True,
            header_style="bold magenta",
            show_lines=False,
            expand=True,
            box=None,
        )
        programs_table.add_column("Program")
        programs_table.add_column("Edited program")
        programs_table.add_row(syntax_program, syntax_edited_program)
        table.add_row(programs_table)
        console.print(table)


def display_simulation_tools(
    simulation_tools: dict[SimulationModuleName, list[SimulationToolName]],
    module_path_prefix: str,
) -> Table:
    """Display a table in the format

    ┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃ Module            ┃ Definition                                           ┃
    ┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩

    to show available simulation tools.
    """
    table = Table(title="Tools")
    table.add_column("Module", style="cyan", no_wrap=True)
    table.add_column("Definition", style="magenta")
    table.add_column("Tool path")

    for module_name, functions in simulation_tools.items():
        module_path = f"{module_path_prefix}.{module_name}"
        module = importlib.import_module(module_path)
        for fcn in functions:
            func = getattr(module, fcn)
            func = str(inspect.getsource(func))
            syntax = Syntax(
                func, "python", theme="monokai", line_numbers=False, word_wrap=True
            )
            table.add_row(module_name, syntax, f"{module_name}::{fcn}")
    return table


def display_function_template(template: str):

    console = Console()
    table = Table(title="Setup Program Template")
    table.add_column("Template", style="cyan", no_wrap=True)
    syntax = Syntax(template, "python", theme="monokai", line_numbers=True)
    table.add_row(syntax)
    console.print(table)


def display_executable_and_runtime_setup_programs(
    query: str, executable: ProgramStr, runtime_setup: ProgramStr
) -> Table:
    """Display `executable` and `runtime_setup` in a table

    ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃ Evaluation program (EP)     ┃ State initialisation program (SIP)                   ┃
    ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩

    where `query` is the title of the table.
    """
    executable_syntax = Syntax(executable, "python", line_numbers=True, word_wrap=True)
    runtime_setup_syntax = Syntax(
        runtime_setup, "python", line_numbers=True, word_wrap=True
    )
    table = Table(title=query)
    table.add_column("Evaluation program (EP)", style="cyan")
    table.add_column("State initialisation program (SIP)", style="magenta")
    table.add_row(executable_syntax, runtime_setup_syntax)

    return table


def has_syntax_errors(example: DataPoint) -> bool:
    """Returns `True` if an example has syntax errors."""
    try:
        _ = ast.parse(example.program)
    except SyntaxError:
        return True
    return False


def _prompt_for_edit_error_correction(edit_errors: list[EditedDataPoint]):
    """Prompt the user to actually edit any programs they forgot to edit."""
    signature_processor = ExtractSignature()
    programs_with_errors = [signature_processor(err.program) for err in edit_errors]
    console = Console()
    table = Table(show_header=True, header_style="bold red", show_lines=True)
    table.add_column("Index", style="dim", width=6)
    table.add_column("Utterance")
    for i, progr in enumerate(programs_with_errors):
        table.add_row(str(i), progr)
    console.print(table)
    _ = Prompt.ask(CODE_EDIT)


def display_annotation_correction(
    query: str, current_program: ProgramStr, corrected_program: ProgramStr
):
    console = Console()
    current_syntax = Syntax(
        current_program, "python", line_numbers=True, word_wrap=True
    )
    runtime_setup_syntax = Syntax(
        corrected_program, "python", line_numbers=True, word_wrap=True
    )
    table = Table(title=query)
    table.add_column("Current", style="cyan")
    table.add_column("Corrected program", style="magenta")
    table.add_row(current_syntax, runtime_setup_syntax)
    console.print(table)
