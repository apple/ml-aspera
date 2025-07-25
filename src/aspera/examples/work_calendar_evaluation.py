from typing import Any, Callable

from aspera.apps.company_directory import (
    find_employee,
    find_manager_of,
    find_reports_of,
    find_team_of,
    get_current_user,
)
from aspera.apps.time_utils import (
    DateExpressions,
    TimeExpressions,
    combine,
    date_by_mdy,
    get_next_dow,
    parse_time_string,
    time_by_hm,
)
from aspera.apps.work_calendar import find_events
from aspera.execution_evaluation_tools.exceptions import SolutionError


def evaluate_user_schedules_team_meeting(
    query: str, executable: Callable[[], Any], setup_function: Callable[[], Any]
):
    """Validate that `executable` program for the query

    Query: Hey, [Assistant] put something in the calendar with my team at lunch tomorrow.

    has the expected effect on the runtime environment.

    Parameters
    ----------
    query
        The query to validate.
    executable
       The query execution function, user_schedules_team_meeting
    setup_function
        `setup_environment_user_schedules_team_meeting` function.
    """

    # Step 1: setup runtime environment
    setup_function()
    all_events_before = find_events()
    # Step 2: run the solution
    # result not needed because the query does not return anything
    _ = executable()
    # Step 3: check effects on runtime environment are as expected
    all_events_after = find_events()
    # check one and only one event created by the user was created
    try:
        assert len(all_events_after) == len(all_events_before) + 1
    except AssertionError:
        raise SolutionError("Incorrect solution")
    new_event = [e for e in all_events_after if e not in all_events_before][0]
    user = get_current_user()
    # testing guideline # 1
    team = sorted(find_team_of(user), key=lambda member: member.name)
    # check the event created as the right properties
    expected_meeting_time = combine(
        DateExpressions["Tomorrow"], parse_time_string(TimeExpressions["Lunch"])
    )
    try:
        assert new_event.attendees == team
        assert new_event.starts_at == expected_meeting_time
    except AssertionError:
        raise SolutionError("Incorrect solution")
    # skipping 'subject' check as per testing guidelines


def evaluate_user_schedules_meeting_with_manager_and_reports(
    query: str, executable: Callable[[], Any], setup_function: Callable[[], Any]
):
    """Validate that `executable` program for the query

    Query: Hey, [Assistant], add an event with my manager and reports on the 5th of May at 10 in the morning.

    has the expected effect on the runtime environment.

    Parameters
    ----------
    query
        The query to validate.
    executable
       The query execution function, `user_schedules_meeting_with_manager_and_reports`
    setup_function
        `setup_env_user_schedules_user_schedules_meeting_with_manager_and_reports` function.
    """

    # Step 1: setup runtime environment
    setup_function()
    all_events_before = find_events()
    # Step 2: run the solution
    # result not needed because the query does not return anything
    _ = executable()
    # Step 3: check effects on runtime environment are as expected
    all_events_after = find_events()
    # check one and only one event created by the user was created
    try:
        assert len(all_events_after) == len(all_events_before) + 1
    except AssertionError:
        raise SolutionError("Incorrect solution")

    # check the meeting details are as requested by the user
    new_event = [e for e in all_events_after if e not in all_events_before][0]
    # the meeting attendees
    current_user = get_current_user()
    manager = find_manager_of(current_user)
    reports = find_reports_of(current_user)
    # testing guideline # 1
    attendees = sorted([manager] + reports, key=lambda member: member.name)
    try:
        assert new_event.attendees == attendees
    except AssertionError:
        raise SolutionError("Incorrect solution")
    # the meeting time
    meeting_time = time_by_hm(hour=10, minute=0, am_or_pm="am")
    meeting_date = date_by_mdy(month=5, day=10)
    event_start = combine(meeting_date, meeting_time)
    try:
        assert new_event.starts_at == event_start
    except AssertionError:
        raise SolutionError("Incorrect solution")
    # skipping 'subject' check as per testing guidelines


def evaluate_avoid_specific_attendees(
    query: str, executable: Callable[[], Any], setup_function: Callable[[], Any]
):
    """Validate that `executable` program for the query

    Query: Hey, [Assistant] Make sure our team project planning is scheduled the
    thursday after next at 14:30. Ben and Jerry don't need to attend because
    they're on a different project.

    has the expected effect on the runtime environment.

    Parameters
    ----------
    query
        The query to validate.
    executable
       The query execution function, `avoid_specific_attendees`
    setup_function
        `setup_env_avoid_specific_attendees` function.
    """

    # Step 1: setup runtime environment
    setup_function()
    all_events_before = find_events()
    # Step 2: run the solution
    # result not needed because the query does not return anything
    _ = executable()
    # Step 3: check effects on runtime environment are as expected
    all_events_after = find_events()
    # check one and only one event created by the user actually created
    try:
        assert len(all_events_after) == len(all_events_before) + 1
    except AssertionError:
        raise SolutionError("Incorrect solution")

    # check the meeting details are as requested by the user
    new_event = [e for e in all_events_after if e not in all_events_before][0]
    # attendees are correct
    # testing guideline # 1
    attendees_to_avoid = sorted(
        [find_employee(name)[0] for name in ["Ben", "Jerry"]],
        key=lambda member: member.name,
    )
    try:
        assert all(e not in new_event.attendees for e in attendees_to_avoid)
    except AssertionError:
        raise SolutionError("Incorrect solution")
    try:
        assert new_event.attendees_to_avoid == attendees_to_avoid
    except AssertionError:
        raise SolutionError("Incorrect solution")
    # meeting time is correct
    planning_time = time_by_hm(hour=2, minute=30, am_or_pm="pm")
    next_thursday = get_next_dow("Thursday")
    planning_date = get_next_dow("Thursday", after=next_thursday)
    starts_at = combine(planning_date, planning_time)
    try:
        assert new_event.starts_at == starts_at
    except AssertionError:
        raise SolutionError("Incorrect solution")
    # skipping 'subject' check as per testing guidelines


def evaluate_modify_existing_event_start_time(
    query: str, executable: Callable[[], Any], setup_function: Callable[[], Any]
):
    """Validate that `executable` program for the query

    Query: Hey, [Assistant] Would you mind pushing back
     my catch-up meeting with Pete taking place next Tuesday by 23 minutes?

    has the expected effect on the runtime environment.

    Parameters
    ----------
    query
        The query to validate.
    executable
       The query execution function, `modify_existing_event_start_time`
    setup_function
        `setup_env_modify_existing_event_start_time` function.
    """

    import datetime
    from datetime import timedelta

    # Step 1: setup runtime environment
    setup_function()
    all_events_before = find_events()
    # Step 2: run the solution
    # result not needed because the query does not return anything
    _ = executable()
    # Step 3: check effects on runtime environment are as expected
    all_events_after = find_events()

    # check no new event was created
    try:
        assert len(all_events_after) == len(all_events_before)
    except AssertionError:
        raise SolutionError("Incorrect solution")

    # check the event the user expects actually exists
    # use setup_env_modify_existing_event_start_time to simplify code as per testing guidelines
    meeting_date = get_next_dow("Tuesday")
    expected_meeting_start_time = datetime.time(hour=14, minute=30 + 23)
    expected_meeting_starts = combine(meeting_date, expected_meeting_start_time)
    expected_meetings_ends = expected_meeting_starts + timedelta(minutes=30)
    pete = find_employee("Pete")[0]
    modified, other = [], []
    for event in all_events_after:
        # skipping 'subject' check as per testing guidelines
        if all(
            (
                event.attendees == [pete],
                event.starts_at == expected_meeting_starts,
                event.ends_at == expected_meetings_ends,
            )
        ):
            modified.append(event)
        else:
            other.append(event)
    try:
        assert len(modified) == 1
        assert all(e in all_events_before for e in other)
    except AssertionError:
        raise SolutionError("Incorrect solution")


def evaluate_busiest_day_this_week(
    query: str, executable: Callable[[], Any], setup_function: Callable[[], Any]
):
    """Validate that `executable` program for the query

    Query: Hey, [Assistant], my busiest day this week?


    has the expected effect on the runtime environment.

    Parameters
    ----------
    query
        The query to validate.
    executable
       The query execution function, `busiest_day_this_week`
    setup_function
        `setup_env_busiest_day_this_week` function.
    """

    import datetime

    # Step 1: setup runtime environment
    setup_function()
    # Step 2: run the solution
    result = executable()
    # Step 3: check the result
    # use setup_env_busiest_day_this_week to simplify code as per testing guidelines
    expected_date = datetime.date(year=2034, day=26, month=6)
    try:
        assert result == expected_date
    except AssertionError:
        raise SolutionError("Incorrect solution")
