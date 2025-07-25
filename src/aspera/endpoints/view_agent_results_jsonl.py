#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
from __future__ import annotations

import sys
import termios
import tty
from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.table import Table

from aspera.constants import PROGRAM_LINE_LENGTH
from aspera.evaluator import EvalResultIterator, EvaluationResult

QUERY_COL_WIDTH = 15
FEEDBACK_COL_WIDTH = 50

FOOTER_PREFIX = r"choose [bold]f[/bold]orward, [bold]b[/bold]ack, "
FOOTER_SUFFIX = ", [bold]q[/bold]uit"
ASTERISK_DELIMITER_WIDTH = 35


def get_keypress() -> str:
    """Get single keypress event."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def _input_loop(
    result_iter: EvalResultIterator,
    current_result: EvaluationResult,
    console: Console,
    counter: str,
) -> bool:
    match get_keypress():
        case "q":
            return False
        case "t":
            console.clear()
            tr_result = current_result.primitives_selection_result
            if tr_result:
                table = Table(
                    show_header=True, header_style="bold magenta", show_lines=True
                )
                table.add_column("Query", style="dim", width=QUERY_COL_WIDTH)
                table.add_column("Retrieved", style="white")
                table.add_column("Ground-truth", style="white")
                table.add_column("Precision", style="white")
                table.add_column("Recall", style="white")
                table.add_column("F1", style="white")
                retrieved_symbols = "\n".join(tr_result.retrieved_symbol_names)
                gt_symbols = "\n".join(tr_result.ground_truth_symbol_names)

                table.add_row(
                    f"{current_result.query_id}: {current_result.query}",
                    retrieved_symbols,
                    gt_symbols,
                    f"{tr_result.precision:.2f}",
                    f"{tr_result.recall:.2f}",
                    f"{tr_result.f1:.2f}",
                )
                console.print(table, width=None)
            console.print(counter, end=" ", markup=False)
            console.print(
                FOOTER_PREFIX
                + "[bold]r[/bold]esult, [cyan][bold]t[/bold]ools[/cyan], [bold]s[/bold]etup, [bold]p[/bold]rompt"
                + FOOTER_SUFFIX
            )
            _input_loop(result_iter, current_result, console, counter)
            return True
        case "s":
            console.clear()
            table = Table(
                show_header=True, header_style="bold magenta", show_lines=True
            )
            table.add_column("Query", style="dim", width=QUERY_COL_WIDTH)
            table.add_column("State Initialisation Program (SIP)", style="white")
            table.add_column("Evaluation Programs (EP)", style="white")
            assert current_result.state_generation_programs
            state_gen = ""
            for ix, state_generation_program in enumerate(
                current_result.state_generation_programs
            ):
                state_gen += f"""\n{'*' * ASTERISK_DELIMITER_WIDTH}\n{ix + 1}\n{'*' * ASTERISK_DELIMITER_WIDTH}\n\n"""
                state_gen += f"{state_generation_program}\n"
            runtime_setup_syntax = Syntax(
                state_gen, "python", line_numbers=True, word_wrap=True
            )
            assert current_result.evaluation_programs
            eval = ""
            for ix, evaluation_program in enumerate(current_result.evaluation_programs):
                eval += f"""\n{'*' * ASTERISK_DELIMITER_WIDTH}\n{ix + 1}\n{'*' * ASTERISK_DELIMITER_WIDTH}\n\n"""
                eval += f"{evaluation_program}\n"
            evaluation_syntax = Syntax(
                eval, "python", line_numbers=True, word_wrap=True
            )
            table.add_row(
                f"{current_result.query_id}: {current_result.query}",
                runtime_setup_syntax,
                evaluation_syntax,
            )
            console.print(table, width=None)
            console.print(counter, end=" ", markup=False)
            console.print(
                FOOTER_PREFIX
                + "[bold]r[/bold]esult, [bold]t[/bold]ools, [cyan][bold]s[/bold]etup[/cyan], [bold]p[/bold]rompt"
                + FOOTER_SUFFIX
            )
            _input_loop(result_iter, current_result, console, counter)
            return True
        case "p":
            console.clear()
            table = Table(
                show_header=True, header_style="bold magenta", show_lines=True
            )
            table.add_column("Query", style="dim", width=QUERY_COL_WIDTH)
            table.add_column("Prompt")
            prompt_text = ""
            for m in current_result.prompt.messages:
                prompt_text += f"{m['content']}\n"
            table.add_row(
                f"{current_result.query_id}: {current_result.query}",
                Markdown(prompt_text),
            )
            console.print(table, width=None)
            console.print(counter, end=" ", markup=False)
            console.print(
                FOOTER_PREFIX
                + "[bold]r[/bold]esult, [bold]t[/bold]ools, [bold]s[/bold]etup, [cyan][bold]p[/bold]rompt[/cyan]"
                + FOOTER_SUFFIX
            )
            _input_loop(result_iter, current_result, console, counter)
            return True
        case "f" | "\r":
            return True
        case "b":
            result_iter.prev()
            return True
        case _:
            result_iter.same()
            return True


@click.command()
@click.argument("p", type=Path)
@click.option("--just-errors", is_flag=True, help="Just show errors")
def view_results_jsonl(p: Path, just_errors: bool = False) -> None:
    console = Console()
    result_iter = EvalResultIterator(p, just_errors)
    for result in result_iter:
        console.clear()
        table = Table(show_header=True, header_style="bold magenta", show_lines=True)
        table.add_column("ID", justify="right", style="cyan", no_wrap=True)
        table.add_column("Correct", justify="right", style="cyan", no_wrap=True)
        table.add_column("Query", style="dim", width=QUERY_COL_WIDTH)
        table.add_column("Program", style="white", width=PROGRAM_LINE_LENGTH)
        table.add_column("Ground Truth", style="white", width=PROGRAM_LINE_LENGTH)
        table.add_column("Feedback", style="white", width=FEEDBACK_COL_WIDTH)
        program_syntax = Syntax(
            result.solution, "python", line_numbers=True, word_wrap=True
        )
        ground_truth_syntax = Syntax(
            result.ground_truth_solution, "python", line_numbers=True, word_wrap=True
        )
        table.add_row(
            result.query_id,
            "yes" if result.correct else "no",
            result.query,
            program_syntax,
            ground_truth_syntax,
            result.format_feedback(),
        )
        console.print(table, width=None)
        counter_str = f"\n[{result_iter.ix}/{result_iter.len}]"
        console.print(counter_str, end=" ", markup=False)
        console.print(
            FOOTER_PREFIX
            + "[cyan][bold]r[/bold]esult[/cyan], [bold]t[/bold]ools, [bold]s[/bold]etup, [bold]p[/bold]rompt"
            + FOOTER_SUFFIX
        )
        should_continue = _input_loop(result_iter, result, console, counter_str)
        if not should_continue:
            break
