#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import textwrap

import pytest

from aspera.code_utils.utils import (
    _get_all_aspera_symbols,
    escape_program_str,
    extract_import_statements,
    get_apps_symbols_from_program,
    get_source_code_for_symbols_used_in_program,
    is_import,
    remove_import_statements,
)
from aspera.simulation.execution_context import RoleType
from aspera.simulation.execution_environment import execute_script


def test_single_line_import():
    content = "import os"
    expected = ["import os"]
    assert extract_import_statements(content) == expected


def test_multiple_single_line_imports():
    content = "import os\nimport sys"
    expected = ["import os", "import sys"]
    assert extract_import_statements(content) == expected


def test_multi_line_import():
    content = """
from datetime import (
    datetime,
    timedelta,
    timezone
)
"""
    expected = ["from datetime import datetime, timedelta, timezone"]
    assert extract_import_statements(content) == expected


def test_import_with_comments():
    content = """
# This is a comment
import os  # import os module
import sys
# Another comment
from datetime import (
    datetime,  # datetime class
    timedelta,
    timezone
)
"""
    expected = [
        "import os",
        "import sys",
        "from datetime import datetime, timedelta, timezone",
    ]
    assert extract_import_statements(content) == expected


def test_empty_string():
    content = ""
    expected = []
    assert extract_import_statements(content) == expected


def test_non_import_statements():
    content = """
def foo():
    pass

class Bar:
    def baz(self):
        pass
"""
    expected = []
    assert extract_import_statements(content) == expected


def test_complex_import_combinations():
    content = """
import os
import sys

from datetime import (
    datetime,
    timedelta,
    timezone
)
import numpy as np

# A comment
from functools import (
    partial,
    wraps
)
"""
    expected = [
        "import os",
        "import sys",
        "from datetime import datetime, timedelta, timezone",
        "import numpy as np",
        "from functools import partial, wraps",
    ]
    assert extract_import_statements(content) == expected


def test_is_import():
    to_check = [
        """
        import os
        import sys

        from datetime import (
            datetime,
            timedelta,
            timezone
        )
        import numpy as np

        from functools import (
            partial,
            wraps
        )
        """,
        """
        def foo():
            pass

        class Bar:
            def baz(self):
                pass
        """,
        "",
        """
        import os
        import sys

        from datetime import (
            datetime,  # datetime class
            timedelta,
            timezone
        )
        """,
        """
        from datetime import (
            datetime,
            timedelta,
            timezone
        )""",
        "import os\nimport sys",
        "import os",
    ]

    # Expected results for each string in to_check
    expected_results = [True, False, False, True, True, True, True]

    for idx, code in enumerate(to_check):
        code = textwrap.dedent(code.strip("\n"))
        assert (
            is_import(code) == expected_results[idx]
        ), f"Failed at index {idx} with input: {code.strip()}"


def test_get_all_aspera_symbols_basic():
    all_aspera_symbols = [s.import_path for s in _get_all_aspera_symbols()]
    # Check some arbitrary symbols from the codebase
    for symbol in [
        "aspera.apps.work_calendar.add_event",
        "aspera.apps.reminder.add_reminder",
        "aspera.apps.company_directory.EmployeeDetails",
        "aspera.apps.company_directory.find_employee",
    ]:
        assert symbol in all_aspera_symbols


def test_get_all_aspera_symbols_preserves_order():
    all_aspera_symbols = [s.import_path for s in _get_all_aspera_symbols()]
    assert all_aspera_symbols.index(
        "aspera.apps.company_directory.EmployeeDetails"
    ) < all_aspera_symbols.index("aspera.apps.company_directory.Employee")
    assert all_aspera_symbols.index(
        "aspera.apps.company_directory.EmployeeDetails"
    ) < all_aspera_symbols.index("aspera.apps.company_directory.find_employee")


def test_get_apps_symbols_from_program_1():
    program = '''
       def find_conference_room_for_team_meeting() -> str:
           """Find a suitable conference room for a team meeting later today."""

            # find the user's team to determine event attendees
            user = get_current_user()
            team = find_team_of(user)
            # search for an available conference room
            available_rooms = search_conference_room([now_().date()], capacity=len(team) + 1)
            # summarise the availability of the rooms found
            summary = summarise_availability(available_rooms)
            return summary  # by structure guideline #3
    '''
    symbol_names = [s.obj_name for s in get_apps_symbols_from_program(program)]
    for s in [
        "find_team_of",
        "get_current_user",
        "now_",
        "search_conference_room",
        "summarise_availability",
    ]:
        assert s in symbol_names


def test_get_apps_symbols_from_program_2():
    program = '''
       def schedule_weekly_meeting_with_engineering() -> list[datetime.date] | None:
           """Schedule a recurring weekly meeting with the engineering team."""

           engineering_team = [employee for employee in get_all_employees() if get_employee_profile(employee).team == Team.Engineering]

           # Resolve the meeting start time
           meeting_time = time_by_hm(hour=3, minute=0, am_or_pm="pm")
           # Determine the start and end date range for the next two months
           start_date = now_().date()
           end_date = replace(start_date, month=start_date.month + 2)

           # Filter only the Fridays within the next two months
           next_friday_meeting = combine(get_next_dow('Friday'), meeting_time)
           next_friday_meeting_end = modify(next_friday_meeting, Duration(30, unit=TimeUnits.Minutes), operator=DateTimeClauseOperators.add)
           meeting_dates = []
           for i in range(9):
               meeting_start_time = modify(next_friday_meeting, Duration(i * 7, TimeUnits.Days), operator=DateTimeClauseOperators.add)
               if meeting_start_time.date() <= end_date:
                   meeting_dates.append(meeting_start_time)

           # Search for existing events to avoid clashes
           existing_events = find_events()
           clash_dates = []
           for meeting_start in meeting_dates:
               booked_slots = [
                   TimeInterval(start=e.starts_at, end=e.ends_at)
                   for e in existing_events
                   if e.starts_at.date() == meeting_start.date()
               ]
               ends_at = modify(meeting_start, Duration(30, TimeUnits.Minutes), operator=DateTimeClauseOperators.add)
               meeting_interval = TimeInterval(start=meeting_start, end=ends_at)
               if any(intervals_overlap(meeting_interval, slot) for slot in booked_slots):
                   clash_dates.append(meeting_interval)

           repetition_spec = RepetitionSpec(
               frequency=EventFrequency.WEEKLY,
               recurs_until=end_date,
               period=1,
               exclude_occurrence=[clash.start for clash in clash_dates] or None
           )
           event = Event(
               attendees=engineering_team,
               starts_at=next_friday_meeting,
               ends_at=next_friday_meeting_end,
               subject="Weekly Engineering Team Meeting",
               repeats=repetition_spec
           )
           add_event(event)

           if clash_dates:
               return [clash.start.date() for clash in clash_dates]
    query: Hey, [Assistant], can you schedule a 30 mins recurring weekly meeting with the engineering team on Fridays at 3 PM for the next two months? If there are clashes, tell me their dates, don't double book.
    '''
    symbol_names = [s.obj_name for s in get_apps_symbols_from_program(program)]
    for s in [
        "DateTimeClauseOperators",
        "Duration",
        "Event",
        "EventFrequency",
        "RepetitionSpec",
        "Team",
        "TimeInterval",
        "TimeUnits",
        "add_event",
        "combine",
        "datetime",
        "find_events",
        "get_all_employees",
        "get_employee_profile",
        "get_next_dow",
        "intervals_overlap",
        "modify",
        "now_",
        "replace",
        "time_by_hm",
    ]:
        assert s in symbol_names


def test_get_apps_symbols_from_program_3():
    program = '''
        def schedule_training_session():
            """Schedule a training session for hires who joined this month."""

            # get the current date to determine the start of this month
            current_date = now_().date()
            start_of_month = current_date.replace(day=1)

            # find all employees who joined this month
            all_employees = get_all_employees()
            hires_this_month = [
                emp for emp in all_employees
                if get_employee_profile(emp).joined_date >= start_of_month
            ]

            # determine the event start and end time
            start_time = time_by_hm(hour=2, minute=0, am_or_pm="pm")
            end_time = time_by_hm(hour=5, minute=0, am_or_pm="pm")
            next_friday = get_next_dow("Friday")
            starts_at = combine(next_friday, start_time)
            ends_at = combine(next_friday, end_time)

            # add the event to the calendar
            event = Event(
                attendees=hires_this_month,
                starts_at=starts_at,
                ends_at=ends_at,
                subject="Training session for new hires"
            )
            add_event(event)
    '''
    symbol_names = [s.obj_name for s in get_apps_symbols_from_program(program)]
    for s in [
        "get_all_employees",
        "get_employee_profile",
        "combine",
        "get_next_dow",
        "now_",
        "replace",
        "time_by_hm",
        "add_event",
        "Event",
    ]:
        assert s in symbol_names


def test_get_apps_symbols_from_program_no_recursion():
    program = '''
        def schedule_training_session():
            """Schedule a training session for hires who joined this month."""

            # get the current date to determine the start of this month
            current_date = now_().date()
            start_of_month = current_date.replace(day=1)

            # find all employees who joined this month
            all_employees = get_all_employees()
            hires_this_month = [
                emp for emp in all_employees
                if get_employee_profile(emp).joined_date >= start_of_month
            ]

            # determine the event start and end time
            start_time = time_by_hm(hour=2, minute=0, am_or_pm="pm")
            end_time = time_by_hm(hour=5, minute=0, am_or_pm="pm")
            next_friday = get_next_dow("Friday")
            starts_at = combine(next_friday, start_time)
            ends_at = combine(next_friday, end_time)

            # add the event to the calendar
            event = Event(
                attendees=hires_this_month,
                starts_at=starts_at,
                ends_at=ends_at,
                subject="Training session for new hires"
            )
            add_event(event)
    '''
    symbol_names = [s.obj_name for s in get_apps_symbols_from_program(program)]
    for s in [
        "get_all_employees",
        "get_employee_profile",
        "combine",
        "get_next_dow",
        "now_",
        "replace",
        "time_by_hm",
        "add_event",
        "Event",
    ]:
        assert s in symbol_names


def test_get_apps_symbols_from_program_is_deterministic():
    program = '''
        def schedule_daily_team_meeting_next_week():
            """
            Schedule a daily meeting with the user's team at 3 PM next week.
            """
            def is_weekend(date):
                # Get the weekday of the date (0=Monday, 6=Sunday)
                weekday = date.weekday()
                # Check if it's Saturday (5) or Sunday (6)
                return weekday >= 5

            # find the user's team to determine event attendees
            user = get_current_user()
            team = find_team_of(user)

            # resolve the meeting time specified by the user
            meeting_time = time_by_hm(hour=3, minute=0, am_or_pm="pm")

            # resolve the dates for next week
            next_week_dates = parse_duration_to_calendar(duration="NextWeek")[0]

            # create daily events for next week
            for meeting_date in next_week_dates:
                # exclude weekdays
                if is_weekend(meeting_date):
                    continue
                starts_at = combine(meeting_date, meeting_time)
                event = Event(
                    attendees=team, starts_at=starts_at, subject="Daily Team Meeting"
                )
                add_event(event)
    '''
    symbol_names = [
        "Event",
        "get_current_user",
        "find_team_of",
        "add_event",
        "time_by_hm",
        "parse_duration_to_calendar",
        "combine",
    ]
    for _ in range(10):
        symbol_names_ = [s.obj_name for s in get_apps_symbols_from_program(program)]
        assert symbol_names_ == symbol_names


def test_get_source_code_for_symbols_used_in_program_basic():
    apps = [
        "aspera.apps.time_utils",
    ]
    symbol_allow_list = get_apps_symbols_from_program(
        "get_next_dow()\ntime_by_hm()\nDateRanges()\n"
    )
    codes = list(
        get_source_code_for_symbols_used_in_program(apps, symbol_allow_list).values()
    )
    assert len(codes) == 1
    code = codes.pop()
    assert "def get_next_dow(" in code
    assert "def time_by_hm(" in code
    assert "DateRanges = Enum(" in code


def test_get_source_code_for_symbols_used_in_program_preserves_order():
    apps = [
        "aspera.apps.time_utils",
    ]
    symbol_allow_list = get_apps_symbols_from_program(
        "DateRanges()\ntime_by_hm()\nget_next_dow()\n"
    )
    for _ in range(3):
        codes = list(
            get_source_code_for_symbols_used_in_program(
                apps, symbol_allow_list
            ).values()
        )
        assert len(codes) == 1
        code = codes.pop()
        # At time of writing, get_next_dow is defined on L127 and time_by_hm on L115
        assert code.index("def get_next_dow(") > code.index("def time_by_hm(")
        assert code.index("DateRanges =") < code.index("def time_by_hm(")
        assert code.index("DateRanges =") < code.index("def get_next_dow(")


def test_get_source_code_for_symbols_used_in_program_recursively_retrieves_code_for_args():
    apps = [
        "aspera.apps.time_utils",
    ]
    symbol_allow_list = get_apps_symbols_from_program("parse_time_string()")
    codes = list(
        get_source_code_for_symbols_used_in_program(apps, symbol_allow_list).values()
    )
    assert len(codes) == 1
    code = codes.pop()
    assert "TimeExpressions = Enum" in code


def test_get_source_code_for_symbols_used_in_program_recursively_retrieves_code_for_return_types():
    apps = [
        "aspera.apps.company_directory",
    ]
    symbol_allow_list = get_apps_symbols_from_program(
        "get_employee_profile()\nget_all_employees()\nget_office_location()\n"
    )
    codes = list(
        get_source_code_for_symbols_used_in_program(apps, symbol_allow_list).values()
    )
    assert len(codes) == 1
    code = codes.pop()
    assert "def get_employee_profile(" in code
    assert "class EmployeeDetails" in code
    assert "def get_all_employees(" in code
    assert "class Employee" in code


def test_get_source_code_for_symbols_used_in_program_gets_type_aliases():
    apps = [
        "aspera.apps.room_booking",
    ]
    symbol_allow_list = get_apps_symbols_from_program("find_available_time_slots()")
    source_code_by_file = get_source_code_for_symbols_used_in_program(
        apps, symbol_allow_list
    )
    codes = [v for k, v in source_code_by_file.items() if "room_booking" in k]
    assert len(codes) == 1
    code = codes.pop()
    assert "def find_available_time_slots(" in code

    codes = [v for k, v in source_code_by_file.items() if "time_utils" in k]
    assert len(codes) == 1
    code = codes.pop()
    assert "class TimeInterval(" in code

    apps = [
        "aspera.apps.room_booking",
    ]
    symbol_allow_list = get_apps_symbols_from_program("x = RoomAvailability(")
    source_code_by_file = get_source_code_for_symbols_used_in_program(
        apps, symbol_allow_list
    )
    codes = [v for k, v in source_code_by_file.items() if "room_booking" in k]
    assert len(codes) == 1
    code = codes.pop()
    assert "RoomAvailability" in code


def test_escape_program_str() -> None:
    program = textwrap.dedent(
        '''
       """
       This is
       a docstring
       """

       string_with_newline = "hello\\nworld"
       print(string_with_newline)
    '''
    )
    assert (
        execute_script(escape_program_str(program), RoleType.AGENT).content
        == "hello\\nworld"
    )


@pytest.mark.parametrize(
    "source, expected",
    [
        ("import os\n", "import os"),
        ("import aspera.work_calendar\n", ""),
        ("from aspera.work_calendar import foo\n", ""),
        ("from aspera.work_calendar import (\n    a, b, c\n)\n", ""),
        ("import aspera.work_calendar\nimport sys\n", "import sys"),
        ("def fn():\n    import aspera.work_calendar\n", "def fn():"),
    ],
)
def test_remove_import_statements_aspera_imports_only_global(
    source: str, expected: str
) -> None:
    assert (
        remove_import_statements(
            source, global_only=True, remove_aspera_imports_only=True
        )
        == expected
    )


@pytest.mark.parametrize(
    "source, expected",
    [
        (
            "def fn():\n    import aspera.work_calendar\n    print(1)\n",
            "def fn():\n    print(1)",
        ),
        (
            "from aspera.work_calendar import (\n    foo,\n    bar\n)\nprint(foo)",
            "print(foo)",
        ),
        ("import sys\n", "import sys"),
    ],
)
def test_remove_import_statements_aspera_imports_only_nonglobal(
    source: str, expected: str
) -> None:
    assert (
        remove_import_statements(
            source, global_only=False, remove_aspera_imports_only=True
        )
        == expected
    )


@pytest.mark.parametrize(
    "source, expected",
    [
        ("import os, sys\n", "import os, sys"),
        ("from pkg import a, b\n", "from pkg import a, b"),
    ],
)
def test_remove_import_statements_when_pattern_disabled(
    source: str, expected: str
) -> None:
    """Tests for standard import removal using regex path when remove_aspera_imports_only=False"""
    assert (
        remove_import_statements(source, remove_aspera_imports_only=False) == expected
    )


def test_remove_import_statements_consecutive_blank_lines():
    """Edge case: consecutive blank lines"""
    source = "import aspera.work_calendar\n\n\nprint(1)\n"
    assert (
        remove_import_statements(source, remove_aspera_imports_only=True) == "print(1)"
    )
