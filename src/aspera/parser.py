#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import ast
import logging
import re
from abc import ABC, abstractmethod
from textwrap import dedent
from typing import TypedDict, cast

from aspera.code_utils.utils import format_program_str, is_import, is_python_code

logger = logging.getLogger(__name__)

FUNCTION_SIGNATURE_REGEX = r"^\s*def\s+\w+\s*\([^)]*\)\s*(->\s*[^:]+)?\s*:"
"""Pattern that matches Python function signatures."""
FUNCTION_NAME_REGEX = r"^\s*def\s+(\w+)\s*\("
DUMMY_PLACEHOLDER_BAD_SOLUTION = (
    "def parser_failed_placeholder_bad_solution(): return None"
)


class ParsingError(Exception):
    pass


class CompletionProcessor(ABC):
    @abstractmethod
    def __call__(self, text: str) -> str:
        """
        Process the given text.
        May raise a ValueError to indicate that the input text is invalid.
        """


class NoOp(CompletionProcessor):
    """Does nothing."""

    def __call__(self, text: str) -> str:
        return text


class PipelineProcessor(CompletionProcessor):
    def __init__(self, processors: list[CompletionProcessor]):
        self._processors = processors

    def __call__(self, text: str) -> str:
        """Process the given text through the processors in the pipeline in order."""
        for processor in self._processors:
            text = processor(text)
        return text


class DocstringInfo(TypedDict):

    no_query_docstring: str
    docstring_raw: str
    query: str


def remove_query_from_docstrings(docstring: str) -> str:
    cleaned = re.sub(r"\s*Query:.*", "", docstring, flags=re.DOTALL).strip()
    return cleaned  # + '"""'


def extract_docstrings_and_queries(program: str) -> dict[str, DocstringInfo]:
    """Extract the docstring and possibly user query from `program`"""

    tree = ast.parse(program)
    functions_info: dict[str, DocstringInfo] = cast(dict[str, DocstringInfo], {})
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            docstring = ast.get_docstring(node, clean=False)
            if docstring:
                lines = docstring.split("\n")
                user_query = None
                for line in lines:
                    if line.strip().startswith("Query:"):
                        user_query = line.strip().strip()
                        break
                functions_info[node.name] = {
                    "docstring_raw": docstring,
                    "query": user_query,
                    "no_query_docstring": remove_query_from_docstrings(docstring),
                }
    return functions_info


class ProgramFinderError(Exception):
    pass


class ProgramStringFinder(CompletionProcessor):
    """Takes a string and finds the markdown-delimited Python program inside"""

    def __init__(self, start_seq: str = "```python", end_seq: str = "```"):
        self._start_seq = start_seq
        self._end_seq = end_seq

    def __call__(self, text: str) -> str:
        if not self._start_seq:
            return text

        # Find backtick-delimited regions and check if they can be parsed as python programs
        pattern = rf"{self._start_seq}(.*?){self._end_seq}"
        python_markdown_blocks = re.findall(pattern, text, re.DOTALL)
        if python_markdown_blocks:
            for block in python_markdown_blocks:
                # Greedily return the first valid one
                # TODO: Check them all?
                no_markdown = (
                    block.lstrip(self._start_seq).rstrip(self._end_seq).lstrip("\n")
                )
                if is_python_code(no_markdown):
                    return no_markdown.strip()

        else:
            # Failure fallback; try to parse the whole string as python
            text = text.strip("`")
            if is_python_code(text):
                return text

        raise ProgramFinderError(f"Failed to find valid Python code in {text}")


class SimpleProgramFinder(CompletionProcessor):

    def __init__(self, start_seq: str = "```python", end_seq: str = "```"):
        self._start_seq = start_seq
        self._end_seq = end_seq

    def __call__(self, text: str) -> str:
        if not self._start_seq or not self._end_seq:
            return text
        orig_text = text
        start_idx = text.find(self._start_seq)
        if start_idx == -1:
            raise ProgramFinderError(
                f"Could not find starting sequence {self._start_seq} in {text}"
            )
        start_idx += len(self._start_seq)
        end_idx = text.rfind(self._end_seq, start_idx)
        if end_idx == -1:
            logger.warning(f"Could not find ending sequence {self._end_seq} in {text}")
            text = text[start_idx:].lstrip("\n")
        else:
            text = text[start_idx:end_idx].lstrip("\n")

        if is_python_code(text):
            return text

        raise ProgramFinderError(f"Failed to find valid Python code in {orig_text}")


class RemoveQueryFromDocstrings(CompletionProcessor):

    def __call__(self, text: str) -> str:
        """Removes the query from a program docstring."""
        docs_info = extract_docstrings_and_queries(text)
        for _, info in docs_info.items():
            text = text.replace(
                info["docstring_raw"], info["no_query_docstring"]
            ).strip("\n ")
        return text


class RemoveEntryPointCode(CompletionProcessor):

    def __call__(self, text: str) -> str:
        """Remove the code following `if __name__ == '__main__': from
        a python script."""

        pattern = re.compile(r"if\s+__name__\s*==\s*['\"]__main__['\"]\s*:")

        # Search for the pattern in the text
        match = pattern.search(text)

        if match:
            return text[: match.start()].strip("\n ")
        return text.strip("\n ")


class RemoveModuleLevelFunctionCalls(CompletionProcessor):

    def __call__(self, text: str) -> str:
        """Removes the module level function calls from the module code"""

        # Assumes function calls are in the format: function_name(arguments)
        # This will also match function calls with no arguments.
        pattern = r"^[a-zA-Z_]\w*\(.*?\)\s*$(?=[^)]*(?:\n|$))"

        # Use re.MULTILINE to apply pattern on each line and re.DOTALL to handle multiline calls
        cleaned_code = re.sub(pattern, "", text, flags=re.MULTILINE | re.DOTALL)

        return cleaned_code.strip("\n ")


class ExtractSignature(CompletionProcessor):
    """Extract the function signature from a python function."""

    def __call__(self, text: str) -> str:
        match = re.search(FUNCTION_SIGNATURE_REGEX, text, re.MULTILINE)
        if match is None:
            return ""
        return text[match.start() : match.end()]


class ExtractFunctionName(CompletionProcessor):
    """Extract the function name from a python function."""

    def __call__(self, text: str) -> str:
        signature = ExtractSignature()(text)
        if not signature:
            raise ProgramFinderError(f"Can't extract function signature from {text}")
        match = re.search(FUNCTION_NAME_REGEX, signature, re.MULTILINE)
        if match is None:
            raise ProgramFinderError(f"Can't extract function name from {text}")
        return match.group(1)


class ExtractFunctionReturnType(CompletionProcessor):
    """Extract the return type from a python function."""

    def __call__(self, text: str) -> str:
        signature = ExtractSignature()(text)
        if not signature:
            raise ProgramFinderError(f"Can't extract function signature from {text}")
        if "->" in signature:
            return signature.split("->")[1].rstrip(":").strip()
        else:
            return ""


class ProgramParser:
    def __init__(
        self, preprocessor: PipelineProcessor | CompletionProcessor | None = None
    ):
        self._preprocessor = preprocessor
        if preprocessor is None:
            self._preprocessor = ProgramStringFinder()

    @abstractmethod
    def _parse_inner(self, text: str) -> list[str]: ...

    def parse(self, text: str) -> list[str]:
        """Processes the given text into a list of strings,
        where each string represents a `python` program."""
        if len(text) == 0:
            raise ProgramFinderError(f"Can't parse empty completion")
        return [format_program_str(f) for f in self._parse_inner(text)]


class ProgramParserBasic(ProgramParser):
    def __init__(
        self, preprocessor: PipelineProcessor | CompletionProcessor | None = None
    ):
        super().__init__(preprocessor)
        # matches all functions, including local ones
        # self._pattern = r"(?=^\s*def\s+\w+\s*\([^)]*\)\s*:)"
        # only module level functions
        self._pattern = r"(?=^def\s+\w+\s*\([^)]*\)\s*(?:->\s*[\w\[\], ]+)?\s*:)"

    def _parse_inner(self, text: str) -> list[str]:
        text = self._preprocessor(text)
        functions = re.split(self._pattern, text, flags=re.MULTILINE)
        return [dedent(f).strip("\n ") for f in functions if f.strip()]


class ProgramParserWithImportHandling(ProgramParser):
    """Similar to ProgramParser, except that it also returns any
    imports between functions."""

    def __init__(
        self, preprocessor: PipelineProcessor | CompletionProcessor | None = None
    ):
        super().__init__(preprocessor)
        # Updated pattern to match functions with optional return type annotations and imports
        self._pattern_with_import = (
            r"(?=^(?:def\s+\w+\s*\([^)]*\)\s*(?:->\s*[\w\[\], ]+)?\s*:|"
            r"(?:import\s+\w|from\s+\w+\s+import\s+)))"
        )
        self._imports = []

    @property
    def imports(self) -> list[str]:
        return self._imports

    def _parse_inner(self, text: str) -> list[str]:
        """Processes the given text into a list of strings,
        where each string represents a `python` program."""
        text = dedent(text)
        text = self._preprocessor(text)
        functions = re.split(self._pattern_with_import, text, flags=re.MULTILINE)
        functions = [dedent(f).strip("\n ") for f in functions if f.strip()]

        # Merge consecutive import statements
        merged_functions = []
        temp_imports = []

        for func in functions:
            if is_import(func):
                temp_imports.append(func)
            else:
                if temp_imports:
                    merged_functions.append("\n".join(temp_imports))
                    self._imports += temp_imports
                    temp_imports = []
                merged_functions.append(func)

        if temp_imports:  # In case the last block(s) were imports
            merged_functions.append("\n".join(temp_imports))
            self._imports += temp_imports

        return merged_functions


ParserType = ProgramParserBasic | ProgramParserWithImportHandling


class DocstringExtractor(CompletionProcessor):
    def __call__(self, text: str) -> str:
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                return ast.get_docstring(node) or ""
        raise ValueError("No function definition with docstring found")


class ReturnValueExtractor(CompletionProcessor):
    def __call__(self, text: str) -> str:
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for body_item in node.body:
                    if isinstance(body_item, ast.Return):
                        if isinstance(body_item.value, ast.NameConstant):
                            return str(body_item.value.value)
        raise ValueError("No return statement with True or False found")
