#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import ast
import functools
import importlib
import inspect
import logging
import re
import sys
import textwrap
from enum import EnumType
from pathlib import Path
from types import ModuleType
from typing import Any, Literal, get_args, get_origin

import black

from aspera import apps
from aspera.aliases import AppName
from aspera.code_utils.code_symbol import CodeSymbol
from aspera.constants import (
    APP_DOCS_ROOT,
    DOCS_ROOT,
    EVALUATION_TOOLS_IMPLEMENTATIONS_PATH,
    EVALUATION_TOOLS_PATH,
    IMPLEMENTATIONS_ROOT,
    PACKAGE_NAME,
    PROGRAM_LINE_LENGTH,
    SIMULATION_TOOLS_IMPLEMENTATIONS_PATH,
    SIMULATION_TOOLS_PATH,
)
from aspera.scenario import Scenario

logger = logging.getLogger(__name__)


ASPERA_FILENAMES = [p.stem for p in Path(apps.__path__[0]).glob("*.py")]


def _has_aspera_filenames(in_str: str) -> bool:
    return any(fn in in_str for fn in ASPERA_FILENAMES)


def remove_import_statements(
    source_code: str,
    package_name: str | None = PACKAGE_NAME,
    global_only: bool = True,
    remove_aspera_imports_only: bool = False,
) -> str:
    """
    Remove import statements from the given source code.

    This function removes both single-line and multi-line import statements.
    If a package_name is specified, only imports from that package will be removed.

    Parameters
    ----------
    source_code
        The source code from which to remove import statements.
    package_name
        If specified, only imports from this package will be removed.
    global_only:
        Only remove top-level imports.
    remove_aspera_imports_only:
        Only filter out imports from aspera filenames

    Returns
    -------
    str
        The source code with specified import statements removed.
    """
    line_start = r"^" if global_only else r"^\s*"
    if package_name:
        import_pattern = re.compile(
            rf"""
            {line_start}(
                import\s+"""
            + re.escape(package_name)
            + r"""\.[^\n]+  # Match 'import <package_name>...'
                |                           # OR
                from\s+"""
            + re.escape(package_name)
            + r"""\.[^\s]+\s+import\s+  # Match 'from <package_name>... import ...'
                (                           # Begin group for multi-line imports
                    \([^\)]*\)              # Match parentheses and anything inside them
                    |                       # OR
                    [^\n]+                  # Match the rest of the line
                )                           # End group for multi-line imports
            )                               # End group for import statements
            """,
            re.VERBOSE | re.MULTILINE,
        )
    else:
        import_pattern = re.compile(
            rf"""
            {line_start}(
            import\s+[^\n]+                    # Match 'import module[, module2...]'
            |                                  # OR
            from\s+\S+\s+import\s+             # Match 'from module import'
            (?:                                # Non-capturing group:
                \([^\)]+\)                     # Match parenthesized multi-line import on the same line
                |                              # OR
                \(.*?\)                        # Match multi-line import across lines (non-greedy)
                |                              # OR
                [^\n]+                         # Single-line imports
            )
        )
            """,
            re.VERBOSE | re.MULTILINE,
        )

    if remove_aspera_imports_only:
        # This is getting tricky for regex; switch to AST parse
        lines = source_code.splitlines()
        to_remove = []
        for node in ast.walk(ast.parse(source_code)):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                    start, end = node.lineno, node.end_lineno
                    code_segment = "\n".join(lines[start - 1 : end])
                    spans = (start, end)
                    if _has_aspera_filenames(code_segment) and spans not in to_remove:
                        to_remove.append(spans)
        if to_remove:
            for start, end in reversed(sorted(to_remove)):
                del lines[start - 1 : end]
            cleaned_source = "\n".join(lines)
        else:
            cleaned_source = source_code
    else:
        cleaned_source = re.sub(import_pattern, "", source_code)
    cleaned_source = re.sub(r"\n{3,}", "\n\n", cleaned_source)
    return cleaned_source.strip()


def make_prompt_code_string(app_name: str, code: str) -> str:
    return f"# {app_name}.py\n\n{code}\n\n"


def remove_module_comments(code: str) -> str:
    """Use a regular expression to find all lines that start with '#'"""
    return re.sub(r"^#.*$", "", code, flags=re.MULTILINE)


def get_source_code_for_apps(apps: list[AppName]) -> list[str]:
    """
    Retrieve the source code of the listed apps.

    Parameters
    ----------
    apps
        List of app names like `foo.bar`

    Returns
    ----------
    list of strings holding source code for each app
    """

    app_codes = []
    for app in apps:
        module = importlib.import_module(app)
        app_codes.append(inspect.getsource(module))
    return app_codes


def get_source_code_for_symbols_used_in_program(
    apps: list[AppName], target_symbols: list[CodeSymbol]
) -> dict[str, str]:
    """
    Traverses the source code of the listed apps and retrieves the code for
    the target symbols, as well as (recursively) any symbols used in that code.

    Parameters
    ----------
    apps
        List of app names like `foo.bar`
    target_symbols:
        List of symbols to fetch the code for.

    Returns
    ----------
    dict: Keys are apps, values are strings holding source code.
    """

    def _find_alias_definition(alias: Any) -> str | None:
        """These aren't linked to the module in the same way, so we need a bit extra to find them"""
        for _, sys_module in list(sys.modules.items()):
            if sys_module:
                try:
                    for name, obj in inspect.getmembers(sys_module):
                        if obj is alias:
                            try:
                                return inspect.getfile(sys_module)
                            except TypeError:
                                logging.debug(f"Couldn't get source for {sys_module}")
                except ModuleNotFoundError:
                    logging.debug(f"Couldn't get source for {sys_module}")
        return None

    def _get_aspera_code_path(symbol_ref: Any) -> str | None:
        try:
            source_file_path = inspect.getfile(symbol_ref)
        except TypeError:
            source_file_path = _find_alias_definition(symbol_ref)
        if (
            not source_file_path
            or f"{PACKAGE_NAME}/{DOCS_ROOT}/" not in source_file_path
        ):
            return None
        return source_file_path

    def _get_code_for_module_by_file(
        module: ModuleType, target_symbols: list[CodeSymbol]
    ) -> dict[str, list[str]]:
        # Make a list of all the symbols to fetch
        for symbol_name, symbol_ref in inspect.getmembers(module):
            if not _get_aspera_code_path(symbol_ref):
                continue
            if symbol_name in [s.obj_name for s in target_symbols]:
                try:
                    source = inspect.getsource(symbol_ref)
                    target_symbols.extend(
                        [
                            s
                            for s in get_apps_symbols_from_program(source)
                            if s not in target_symbols
                        ]
                    )
                except (OSError, TypeError):
                    logging.debug(f"Couldn't get source for {symbol_ref}")
        target_symbols.sort(key=lambda x: x.line_no)
        code_for_module_by_file = {}
        for target_symbol in target_symbols:
            for symbol_name, symbol_ref in inspect.getmembers(module):
                if symbol_name == target_symbol.obj_name:
                    source_file_path = _get_aspera_code_path(symbol_ref)
                    if not source_file_path:
                        continue
                    if not code_for_module_by_file.get(source_file_path):
                        code_for_module_by_file[source_file_path] = []
                    try:
                        source = inspect.getsource(symbol_ref)
                        code_for_module_by_file[source_file_path].append(f"{source}\n")
                    except OSError as e:
                        if isinstance(symbol_ref, EnumType):
                            # inspect.getsource doesn't work with enums which are defined at runtime
                            # The source code is simple so we can hackily recreate it as follows
                            enum_name = symbol_ref.__name__
                            doc = symbol_ref.__doc__
                            enum_rendered = f'{enum_name} = Enum("{enum_name}", {list(symbol_ref.__members__.keys())})'  # noqa
                            if doc:
                                enum_rendered += f'\n"""{doc}"""\n\n'
                            else:
                                enum_rendered += "\n"
                            code_for_module_by_file[source_file_path].append(
                                enum_rendered
                            )
                        else:
                            raise Exception(symbol_name, symbol_ref, module) from e
                    except TypeError as e:
                        origin = get_origin(symbol_ref)
                        if origin is Literal:
                            # inspect.getsource similarly doesn't work for typing.Literal
                            code_for_module_by_file[source_file_path].append(
                                f'{symbol_name} = Literal[{", ".join(map(repr, symbol_ref.__args__))}]\n'  # noqa
                            )
                        # Custom rules for recreating type aliases
                        elif origin is list:
                            args = get_args(symbol_ref)
                            simplified_args = [
                                arg.__name__ if hasattr(arg, "__name__") else str(arg)
                                for arg in args
                            ]
                            code_for_module_by_file[source_file_path].append(
                                f"{symbol_name} = {origin.__name__}[{', '.join(simplified_args)}]"
                            )
                        else:
                            raise Exception(symbol_name, symbol_ref, module) from e
        return {
            k: list(dict.fromkeys(v)) for k, v in code_for_module_by_file.items() if v
        }

    # Deduplicate so we don't have repeated entries
    all_code_per_file_deduplicated = {}
    for app in apps:
        module = importlib.import_module(app)
        code_for_module_by_file = _get_code_for_module_by_file(module, target_symbols)
        for k, v in code_for_module_by_file.items():
            if k in all_code_per_file_deduplicated:
                for elem in v:
                    if elem not in all_code_per_file_deduplicated[k]:
                        all_code_per_file_deduplicated[k].append(elem)
            else:
                all_code_per_file_deduplicated[k] = v

    return {k: "\n\n".join(v) for k, v in all_code_per_file_deduplicated.items()}


def filter_for_functions_or_classes(
    node: ast.Module, fcn_names_or_classes: list[str]
) -> list[ast.AST]:
    """Filter the module, retaining only the function names and classes specified.

    Module level assigns are also kept.
    """

    relevant_nodes = []
    for child in ast.iter_child_nodes(node):
        if (
            isinstance(child, (ast.FunctionDef, ast.ClassDef))
            and child.name in fcn_names_or_classes
        ):
            relevant_nodes.append(child)
            if isinstance(child, ast.ClassDef):
                for class_child in ast.iter_child_nodes(child):
                    if isinstance(class_child, ast.FunctionDef):
                        relevant_nodes.append(class_child)
        elif isinstance(child, ast.Assign):
            relevant_nodes.append(child)
        elif isinstance(child, (ast.AnnAssign)):
            relevant_nodes.append(child)
        relevant_nodes.extend(
            filter_for_functions_or_classes(child, fcn_names_or_classes)
        )
    return relevant_nodes


def nodes_to_source(nodes: list[ast.AST]) -> str:

    return "\n\n".join([ast.unparse(node) for node in nodes])


def is_python_code(candidate: str) -> bool:
    candidate = textwrap.dedent(candidate)
    try:
        ast.parse(candidate)
    except SyntaxError as e:
        logger.warning(f"Candidate \n {candidate} \n is not valid Python code")
        logger.warning(f"ast.parse reported the following syntax error: {e}")
        return False
    return True


def extract_import_statements(
    module_content: str, filter_package: str | None = None
) -> list[str]:
    tree = ast.parse(module_content)
    import_statements = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            # Handle 'import ...' statements
            import_parts = [
                f"{alias.name} as {alias.asname}" if alias.asname else alias.name
                for alias in node.names
            ]
            import_statements.append(f"import {', '.join(import_parts)}")
        elif isinstance(node, ast.ImportFrom):
            # Handle 'from ... import ...' statements
            module = node.module
            import_parts = [
                f"{alias.name} as {alias.asname}" if alias.asname else alias.name
                for alias in node.names
            ]
            import_statements.append(f"from {module} import {', '.join(import_parts)}")
    if filter_package is None:
        return import_statements
    return [import_ for import_ in import_statements if filter_package not in import_]


def _create_imports(
    scenario: Scenario,
    *,
    which_tools: Literal["evaluation", "runtime_setup"],
    executable: bool,
    starred: bool,
) -> list[str]:
    """Create import strings for runtime simulation and evaluation tools."""
    match which_tools:
        case "evaluation":
            imports = ["from typing import Any, Callable\n"]
            tool_list = scenario.evaluation_tools
            pck_path = (
                EVALUATION_TOOLS_IMPLEMENTATIONS_PATH
                if executable
                else EVALUATION_TOOLS_PATH
            )
        case "runtime_setup":
            tool_list = scenario.simulation_tools
            pck_path = (
                SIMULATION_TOOLS_IMPLEMENTATIONS_PATH
                if executable
                else SIMULATION_TOOLS_PATH
            )
            imports = []
        case _:
            raise ValueError(f"Unknown tool type: {which_tools}")
    if not tool_list or tool_list is None:
        return []
    if starred:
        apps = {app.split("::")[0] for app in tool_list}
        return imports + [f"from {pck_path}.{app} import *\n" for app in apps]
    for tool_path in tool_list:
        app, tool = tool_path.split("::")
        imports.append(f"from {pck_path}.{app} import {tool}\n")
    return imports


def create_apps_imports(scenario: Scenario, *, executable: bool) -> list[str]:
    """Star-import all the members from the apps specified in `scenario`."""
    apps_package = IMPLEMENTATIONS_ROOT if executable else DOCS_ROOT
    content = [
        f"from {PACKAGE_NAME}.{apps_package}.{app} import *\n" for app in scenario.apps
    ]
    return content


def get_imports(
    scenario: Scenario,
    instructions: str | None = None,
    import_simulation_tools: bool = False,
    import_testing_tools: bool = False,
    executable: bool = False,
    starred: bool = True,
) -> list[str]:
    """Returns imports relevant for `scenario`. These are displayed
    at the top of the staging file during data gen/annotation or
    are imported inside the dynamically generated evaluation scripts."""
    content = [] if instructions is None else [instructions, "\n\n"]
    content += create_apps_imports(scenario, executable=executable)
    if import_simulation_tools:
        content += _create_imports(
            scenario,
            which_tools="runtime_setup",
            executable=executable,
            starred=starred,
        )
    if import_testing_tools:
        content += _create_imports(
            scenario, which_tools="evaluation", executable=executable, starred=starred
        )
    content.append("\n\n")
    return content


def is_import(text: str) -> bool:
    """Determines if a given text block is an import statement."""
    if not text:
        return False
    try:
        tree = ast.parse(text.strip())
        return all(isinstance(node, (ast.Import, ast.ImportFrom)) for node in tree.body)
    except SyntaxError:
        raise SyntaxError


@functools.lru_cache
def _get_all_aspera_symbols(
    module_name: str = APP_DOCS_ROOT,
    module: ModuleType = importlib.import_module(APP_DOCS_ROOT),
) -> list[CodeSymbol]:
    def _list_symbols_in_module(module: ModuleType) -> list[CodeSymbol]:
        code_symbols = []
        for name, obj in inspect.getmembers(module):
            code_symbols.append(
                CodeSymbol(obj_name=name, module_name=module.__name__, symbol_ref=obj)
            )
        return code_symbols

    all_code_symbols = _list_symbols_in_module(module)
    for name, obj in inspect.getmembers(module, inspect.ismodule):
        if obj.__name__.startswith(module_name):
            all_code_symbols += _get_all_aspera_symbols(
                module_name=module_name, module=obj
            )

    all_code_symbols.sort(key=lambda x: x.line_no)
    return all_code_symbols


def get_apps_symbols_from_program(program_str: str) -> list[CodeSymbol]:
    """
    Look for any `src/aspera/apps` function or class names in the given string

    Parameters
    ----------
    program_str: String representation of Python program.

    Returns
    ----------
    list: List of fetched code symbols.
    """

    symbols_in_program = []
    for symbol in _get_all_aspera_symbols():
        # Low-risk workaround to the issue of some symbols being
        # common words or prefixes of other symbols
        for formulation in [
            f"{symbol.obj_name}(",
            f"{symbol.obj_name}.",
            f"{symbol.obj_name}:",
            f"{symbol.obj_name}]",
            f"{symbol.obj_name},",
            f"{symbol.obj_name})",
            # type annotation a: int = 1
            f": {symbol.obj_name} = ",
            # type annotation a: int | None = None
            f": {symbol.obj_name} |",
        ]:
            if formulation in program_str:
                symbols_in_program.append(symbol)
                break
    return symbols_in_program


def get_imports_and_docstring_from_file(path: Path) -> str | None:
    """Get top-level import statements and docstring from the given file"""
    with open(path, "r") as f_in:
        tree = ast.parse(f_in.read())
        out_str = ""

        docstring = ast.get_docstring(tree)
        if docstring:
            out_str = f'"""\n{docstring}\n"""'
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    if PACKAGE_NAME not in name.name:
                        out_str += f"\nimport {name.name}"
            elif isinstance(node, ast.ImportFrom):
                module = node.module
                if PACKAGE_NAME not in module:
                    for name in node.names:
                        out_str += f"\nfrom {module} import {name.name}"

        if out_str:
            return out_str.strip()


def format_program_str(program: str) -> str:
    return black.format_str(
        program,
        mode=black.Mode(
            target_versions={black.TargetVersion.PY310}, line_length=PROGRAM_LINE_LENGTH
        ),
    )


def escape_program_str(program: str) -> str:
    return program.replace("\\", "\\\\")
