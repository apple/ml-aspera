#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import textwrap

import pytest

from aspera.parser import (
    DocstringExtractor,
    ExtractFunctionName,
    ExtractFunctionReturnType,
    ExtractSignature,
    ProgramParserBasic,
    ProgramParserWithImportHandling,
    ProgramStringFinder,
    RemoveEntryPointCode,
    RemoveModuleLevelFunctionCalls,
    ReturnValueExtractor,
)

functions = [
    """
    def example_function(param1: int, param2: str):
        pass
    """,
    """
    def example_function(param1: int, param2: str) -> bool:
        pass
    """,
    """
    def example_function_long_name_has_been_split_into_multiple_lines(
        param1: str, param2: Callable[[], Any], setup_function: Callable[[], Any]
    ):
        pass
    """,
]
expected_result = [
    "def example_function(param1: int, param2: str):",
    "def example_function(param1: int, param2: str) -> bool:",
    textwrap.dedent(
        """def example_function_long_name_has_been_split_into_multiple_lines(
        param1: str, param2: Callable[[], Any], setup_function: Callable[[], Any]
    ):"""
    ),
]


@pytest.mark.parametrize("functions", [functions], ids="fcn={}".format)
@pytest.mark.parametrize("expected_results", [expected_result], ids="res={}".format)
def test_extract_signature(functions: list[str], expected_results: list[str]):
    extractor = ExtractSignature()
    for input_, result in zip(functions, expected_results):
        assert extractor(input_).strip() == result


expected_result = ["example_function", "example_function"]


@pytest.mark.parametrize("functions", [functions], ids="fcn={}".format)
@pytest.mark.parametrize("expected_results", [expected_result], ids="res={}".format)
def test_extract_function_name(functions: list[str], expected_results: list[str]):
    extractor = ExtractFunctionName()

    for input_, result in zip(functions, expected_results):
        assert extractor(input_).strip() == result


def test_extract_function_return_type():
    extractor = ExtractFunctionReturnType()
    for fn, result in zip(
        [
            "def example_function(param1: int, param2: str) -> bool:",
            "def example_function(param1: int, param2: str) -> int:",
            "def example_function() -> Optional[int]:",
            "def example_function() -> tuple[CustomType, str]:",
        ],
        ["bool", "int", "Optional[int]", "tuple[CustomType, str]"],
    ):
        assert extractor(fn).strip() == result


@pytest.fixture
def parser_with_import_handling() -> ProgramParserWithImportHandling:
    return ProgramParserWithImportHandling(
        preprocessor=ProgramStringFinder(start_seq="", end_seq="")
    )


@pytest.fixture
def simple_parser() -> ProgramParserBasic:
    return ProgramParserBasic(
        preprocessor=ProgramStringFinder(start_seq="", end_seq="")
    )


def test_parser_simple_functions(
    parser_with_import_handling: ProgramParserWithImportHandling,
):
    code = textwrap.dedent(
        """\
    def executable_1():
        ...

    def executable_3() -> bool:
        ...

    def executable_2():
        ...
    """
    )

    expected = [
        textwrap.dedent(
            """\
        def executable_1(): ...\n"""
        ),
        textwrap.dedent(
            """\
            def executable_3() -> bool: ...\n"""
        ),
        textwrap.dedent(
            """\
        def executable_2(): ...\n"""
        ),
    ]

    result = parser_with_import_handling.parse(code)
    assert result == expected, f"Expected {expected}, but got {result}"


def test_parser_functions_with_imports(
    parser_with_import_handling: ProgramParserWithImportHandling,
):
    code = textwrap.dedent(
        """\
    import datetime
    from datetime import (
        timedelta,
        timezone
    )

    def executable_1() -> bool:
        ...

    import timeit

    def executable_2():
        ...
    """
    )

    expected = [
        textwrap.dedent(
            """\
        import datetime
        from datetime import timedelta, timezone\n"""
        ),
        textwrap.dedent(
            """\
        def executable_1() -> bool: ...\n"""
        ),
        textwrap.dedent(
            """\
        import timeit\n"""
        ),
        textwrap.dedent(
            """\
        def executable_2(): ...\n"""
        ),
    ]

    result = parser_with_import_handling.parse(code)
    assert result == expected, f"Expected {expected}, but got {result}"


def test_parser_for_functions_with_local_imports(
    parser_with_import_handling: ProgramParserWithImportHandling,
):
    code = textwrap.dedent(
        """\
    import os

    def executable_1():
        import sys
        ...

    from datetime import datetime

    def executable_2():
        from math import sqrt
        ...

    import timeit

    def executable_3() -> bool:
        pass
    """
    )

    expected = [
        "import os\n",
        textwrap.dedent(
            """\
        def executable_1():
            import sys

            ...\n"""
        ),
        "from datetime import datetime\n",
        textwrap.dedent(
            """\
        def executable_2():
            from math import sqrt

            ...\n"""
        ),
        "import timeit\n",
        textwrap.dedent(
            """\
        def executable_3() -> bool:
            pass\n"""
        ),
    ]

    result = parser_with_import_handling.parse(code)
    assert result == expected, f"Expected {expected}, but got {result}"


def test_parser_with_local_functions(simple_parser: ProgramParserBasic):

    code = textwrap.dedent(
        """\
    def executable_1():
        ...

    def executable_4() -> bool:
        ...

    def executable_2():
        def local_to_executable_2():
            ...

        def another_local():
            ...
        ...

    def executable_3():
        pass
    """
    )

    expected = [
        textwrap.dedent(
            """\
        def executable_1(): ...\n"""
        ),
        textwrap.dedent(
            """\
        def executable_4() -> bool: ...\n"""
        ),
        textwrap.dedent(
            """\
        def executable_2():
            def local_to_executable_2(): ...

            def another_local(): ...

            ...\n"""
        ),
        textwrap.dedent(
            """\
        def executable_3():
            pass\n"""
        ),
    ]
    result = simple_parser.parse(code)
    assert result == expected, f"Expected {expected}, but got {result}"


def test_module_function_call_processor():
    code = textwrap.dedent(
        """\
        def foo():
            print("Inside foo")

        def bar():
            foo()

        foo()"""
    )
    expected_result = textwrap.dedent(
        """\
        def foo():
            print("Inside foo")

        def bar():
            foo()"""
    )
    processor = RemoveModuleLevelFunctionCalls()
    assert processor(code).strip("\n ") == expected_result


def test_remove_if__name__is__main__block():
    processor = RemoveEntryPointCode()

    code = [
        textwrap.dedent(
            """\
    import sys

    def main():
        print("Hello, World!")

    if __name__ == '__main__':
        main()
    """
        ),
        textwrap.dedent(
            """\
        import sys

        def main():
            print("Hello, World!")"""
        ),
    ]
    expected = [
        textwrap.dedent(
            """\
            import sys

            def main():
                print("Hello, World!")"""
        ).strip("\n "),
        textwrap.dedent(
            """\
            import sys

            def main():
                print("Hello, World!")"""
        ).strip("\n "),
    ]
    for input_, expected_result in zip(code, expected):
        assert processor(input_) == expected_result


def test_parser_multiple_markdown_blocks():
    test_output_variations = [
        textwrap.dedent(
            """\
    ```python
    def llm_generated_function(
        stuff: str, more_stuff: int
    ):
        import math
        foo = math.sqrt(9)
    ```
    """  # simple case
        ).strip(),
        textwrap.dedent(
            """\
    ```python
    def llm_generated_function(
        stuff: str, more_stuff: int
    ):
        import math
        foo = math.sqrt(9)
    ```

    ### Explanation of the Code ###

    **Blah blah**
    blah
    """  # extra markdown
        ).strip(),
        textwrap.dedent(
            """\
    ```python
    def llm_generated_function(
        stuff: str, more_stuff: int
    ):
        import math
        foo = math.sqrt(9)
    ```

    ```
    ### Explanation of the Code ###

    **Blah blah**
    blah
    ```
```
    """  # extra markdown in backticks
        ).strip(),
        textwrap.dedent(
            """\
    ```python
    def llm_generated_function(
        stuff: str, more_stuff: int
    ):
        import math
        foo = math.sqrt(9)
    ```

    ```
    ### Explanation of the Code ###

    **Blah blah**
    blah
    """  # loose extra backticks at start of explanation
        ).strip(),
        textwrap.dedent(
            """\
    ```python
    def llm_generated_function(
        stuff: str, more_stuff: int
    ):
        import math
        foo = math.sqrt(9)
    ```

    ### Explanation of the Code ###

    **Blah blah**
    blah
```
    """  # loose extra backticks at end of explanation
        ).strip(),
    ]

    processor = ProgramStringFinder()
    for test_output in test_output_variations:
        processed = processor(test_output)
        for program_str in ["def llm_generated_function", "import math"]:
            if program_str not in processed:
                raise AssertionError(f"Parse of {test_output} missing program contents")
        for explanation_str in ["### Explanation of the Code", "blah"]:
            if explanation_str in processed:
                raise AssertionError(f"Parse of {test_output} included explanation")


@pytest.fixture
def code_with_true():
    return '''
def is_correct() -> bool:
    """This function checks if the result is correct."""
    return True
    '''


@pytest.fixture
def code_with_false():
    return '''
def is_wrong() -> bool:
    """This function checks if the result is wrong."""
    return False
    '''


@pytest.fixture
def code_without_docstring():
    return """
def no_docstring() -> bool:
    return True
    """


@pytest.fixture
def code_without_return():
    return '''
def no_return() -> bool:
    """This function has no return statement."""
    pass
    '''


@pytest.fixture
def code_with_non_bool_return():
    return '''
def return_non_bool() -> int:
    """This function returns a non-boolean value."""
    return 42
    '''


def test_docstring_extractor_with_true(code_with_true):
    doc_extractor = DocstringExtractor()
    docstring = doc_extractor(code_with_true)
    assert docstring == "This function checks if the result is correct."


def test_docstring_extractor_with_false(code_with_false):
    doc_extractor = DocstringExtractor()
    docstring = doc_extractor(code_with_false)
    assert docstring == "This function checks if the result is wrong."


def test_docstring_extractor_no_docstring(code_without_docstring):
    doc_extractor = DocstringExtractor()
    docstring = doc_extractor(code_without_docstring)
    assert docstring == ""


def test_return_value_extractor_with_true(code_with_true):
    return_extractor = ReturnValueExtractor()
    returned_value = return_extractor(code_with_true)
    assert returned_value == "True"


def test_return_value_extractor_with_false(code_with_false):
    return_extractor = ReturnValueExtractor()
    returned_value = return_extractor(code_with_false)
    assert returned_value == "False"


def test_return_value_extractor_no_return(code_without_return):
    return_extractor = ReturnValueExtractor()
    with pytest.raises(
        ValueError, match="No return statement with True or False found"
    ):
        return_extractor(code_without_return)


def test_return_value_extractor_non_bool_return(code_with_non_bool_return):
    return_extractor = ReturnValueExtractor()
    with pytest.raises(
        ValueError, match="No return statement with True or False found"
    ):
        return_extractor(code_with_non_bool_return)


def test_parser_program_with_inline_functions() -> None:
    test_program = textwrap.dedent(
        """
    ```python
    def my_solution() -> list[TimeInterval] | None:
        def inner_function(date: datetime.date) -> bool:
            weekday_index = date.weekday()  # 0 is Monday, 6 is Sunday
            return weekday_index >= 5  # 5 is Saturday, 6 is Sunday

        def inner_function_2(events: list[Event], date: datetime.date) -> list[Event]:
            return [e for e in events if e.starts_at.date() == date]

        def inner_function_3(intervals1: list[TimeInterval], intervals2: list[TimeInterval]) -> list[TimeInterval]:
            result = []
            return result

        inner_function()
        inner_function_2()
        return None
    ```
    """  # noqa: E501
    ).strip()

    parser = ProgramParserWithImportHandling(preprocessor=ProgramStringFinder())
    parser.parse(test_program)


def test_paser_program_with_stray_newline() -> None:
    test_program = textwrap.dedent(
        '''
     ```python
    def arrange_monthly_strategy_meeting():
        """Arrange a monthly strategy meeting on the first Monday of each month at 9:30 AM with all the department heads.

        Query: Hey, [Assistant], arrange a monthly strategy meeting on the first Monday of each month at 9:30 AM with all the department heads.
        """
        from datetime import timedelta

        all_employees = get_all_employees()
        leadership_team = []
        # Find employees in 'Leadership' team
        for emp in all_employees:
            details = get_employee_profile(emp)
            if details.team == Team['Leadership']:
                leadership_team.append(emp)

        # Find CEO (employee with no manager)
        CEO = None
        for leader in leadership_team:
            if find_manager_of(leader) is None:
                CEO = leader
                break

        # Assuming CEO found
        if CEO is None:
            raise RequiresUserInput("CEO not found in leadership team.")

        # CFO and COO are other leaders
        CFO_and_COO = [e for e in leadership_team if e != CEO]
        if not CFO_and_COO:
            raise RequiresUserInput("No CFO or COO found.")

        # Get reports of CFO and COO (department heads)
        department_heads = []
        for exec in CFO_and_COO:
            reports = find_reports_of(exec)
            if reports:
                department_heads.extend(reports)
        if not department_heads:
            raise RequiresUserInput("No department heads found.")

        # Remove duplicates
        department_heads = list(set(department_heads))

        # Now, find the date of the first Monday of next occurrence
        # Use helper function to get first Monday of month

        # Use now_() to get current date
        now = now_()
        current_date = now.date()
        current_year = current_date.year
        current_month = current_date.month

        def get_first_weekday_of_month(weekday: int, month: int, year: int) -> datetime.date:
            first_day = datetime.date(year=year, month=month, day=1)
            days_to_weekday = (weekday - first_day.weekday()) % 7
            first_weekday = first_day + timedelta(days=days_to_weekday)
            return first_weekday

        # We need to get next first Monday
        first_monday_this_month = get_first_weekday_of_month(0, current_month, current_year)

        if first_monday_this_month >= current_date:
            # Use this date
            first_occurrence_date = first_monday_this_month
        else:
            # Move to next month
            if current_month == 12:
                next_month = 1
                next_year = current_year + 1
            else:
                next_month = current_month + 1
                next_year = current_year
            first_occurrence_date = get_first_weekday_of_month(0, next_month, next_year)

        # Get the time at 9:30 AM
        meeting_time = time_by_hm(hour=9, minute=30, am_or_pm='am')
        starts_at = combine(first_occurrence_date, meeting_time)

        # Create the RepetitionSpec
        repetition = RepetitionSpec(
            frequency=EventFrequency.MONTHLY,
            which_weekday=[0],  # Monday
            bysetpos=[1],  # First occurrence
        )

        # Create Event
        event = Event(
            attendees=department_heads,
            starts_at=starts_at,
            subject="Monthly Strategy Meeting",
            repeats=repetition,
        )

        # Add the event to the calendar
        add_event(event)
    ```
     '''  # noqa: E501
    ).strip()

    parser = ProgramParserWithImportHandling(preprocessor=ProgramStringFinder())
    parser.parse(test_program)


def test_parser_program_with_empty_() -> None:
    test_program = textwrap.dedent(
        """
    ```python
    {
    # YOUR CODE HERE
    }
    ```
    """
    ).strip()

    parser = ProgramParserWithImportHandling(preprocessor=ProgramStringFinder())
    parsed = parser.parse(test_program)
    assert len(parsed) == 1
