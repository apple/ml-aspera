#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
from aspera.constants import (
    EVALUATION_TOOLS_IMPLEMENTATIONS_PATH,
    EVALUATION_TOOLS_PATH,
    SIMULATION_TOOLS_IMPLEMENTATIONS_PATH,
    SIMULATION_TOOLS_PATH,
)

CODE_CHECK = """[bold red]Follow the instructions in the annotation module to curate the generated code.
Press Enter when you have finished inspecting the labels.[/bold red]"""

CODE_PARSING_ERROR_FIX = """[bold red]An error occurred while parsing the annotations.
Perhaps you missed a # before the annotation tag or a : after? "
Press Enter when you have fixed the error[/bold red]"""

CODE_EDIT = "[bold red]Edit the programs, press enter when done...[/bold red]"
SIMULATION_TOOLS_NOTIFICATION = f"""[bold green]The default simulation tools above will be shown to the model. Press Enter if you would like to continue with defaults. If you have implemented additional tools or require a subset of defaults, enter the required tools as a comma-separated string, where the entries are in the format "module::function". New modules should be implemented under {SIMULATION_TOOLS_IMPLEMENTATIONS_PATH} and the docs copied to a module with the same name under {SIMULATION_TOOLS_PATH}[/bold green]."""
EVALUATION_TOOLS_NOTIFICATION = f"""[bold green]The default execution evaluation tools above will be shown to the model. Press Enter if you would like to continue with defaults. If you have implemented additional tools or require a subset of defaults, enter the required tools as a comma-separated string, where the entries are in the format "module::function". Module should be implemented under {EVALUATION_TOOLS_IMPLEMENTATIONS_PATH} and the docs copied to a module with the same name under {EVALUATION_TOOLS_PATH}[/bold green]."""
TODOS_INSTRUCTION = f"""[bold green]The user query is[/bold green] {{query}} [bold green] Enter a '::' separated list of #TODO instructions to guide the generation of the function above. #TODO prefix will be added automatically. [/bold green]"""  # noqa
SIMULATION_TOOLS_IMPLEMENTATION = f"""You may now implement additional simulation tools you require to simulate the environment state under {SIMULATION_TOOLS_IMPLEMENTATIONS_PATH} and add their docstrings to {SIMULATION_TOOLS_PATH}."""
EVALUATION_TOOLS_IMPLEMENTATION = f"""You may now implement additional tools you require for the LLM to check execution was correct under {EVALUATION_TOOLS_IMPLEMENTATIONS_PATH} and add their docstrings to {EVALUATION_TOOLS_PATH}."""
EVAL_CODE_GENERATION_CONFIRMATION = """Please confirm you would like to generate evaluation code for the execution function and runtime state shown above."""
PARSING_FAILED = """[bold red] The LLM annotation could not be parsed. You will have to manually fix the issue by copy-pasting the relevant programs from the completion below to `recovery.py` in the staging directory.[/bold red]"""
CODE_INSPECTION = "[bold red]Follow the instructions in the annotation module to curate the generated code. Press Enter when you are done.[/bold red]"
RECOVERY_FILE_POPULATED_CONFIRMATION = "[bold red]Press Enter when you have populated the recovery file. Make sure there are no imports or module level comments![/bold red]"
CHANGE_GENERATION_FOCUS = "You can influence what the agent generates next by 'focus' instructions, in an attempt to control the diversity of the examples. For example, a focus instruction could be  'We really seem to have under-explored our codebase a bit. There are no complex scenarios using the `find_event` API.'"
