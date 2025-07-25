import datetime
from collections import defaultdict

from aspera.apps.company_directory import (
    find_employee,
    find_manager_of,
    find_reports_of,
    find_team_of,
    get_current_user,
)
from aspera.apps.exceptions import RequiresUserInput
from aspera.apps.time_utils import (
    DateExpressions,
    DateTimeClauseOperators,
    Duration,
    TimeExpressions,
    TimeUnits,
    combine,
    date_by_mdy,
    get_next_dow,
    modify,
    parse_date_string,
    parse_time_string,
    sum_time_units,
    this_week_dates,
    time_by_hm,
)
from aspera.apps.work_calendar import Event, add_event, find_events


def user_schedules_team_meeting():
    """Schedule a meeting with user's team.

    Query: Hey, [Assistant] put something in the calendar with my team at lunch tomorrow.
    """

    # find the user's team to determine event attendees
    user = get_current_user()
    team = find_team_of(user)
    # use the library to resolve the meeting time specified by the user
    resolved_date = DateExpressions["Tomorrow"]
    meeting_date = parse_date_string(resolved_date)
    resolved_time = TimeExpressions["Lunch"]
    meeting_time = parse_time_string(resolved_time)
    starts_at = combine(meeting_date, meeting_time)
    # add the event to the calendar
    event = Event(attendees=team, starts_at=starts_at, subject="Team lunch")
    add_event(event)


def user_schedules_meeting_with_manager_and_reports():
    """Schedule a meeting with manager and reports.

    Query: Hey, [Assistant], add an event with my manager and reports on the 5th of May at 10 in the morning.
    """

    # find the meeting attendees
    current_user = get_current_user()
    manager = find_manager_of(current_user)
    reports = find_reports_of(current_user)
    attendees = [manager] + reports
    # parse the time and date specified in the user query
    meeting_time = time_by_hm(hour=10, minute=0, am_or_pm="am")
    meeting_date = date_by_mdy(month=5, day=10)
    event_start = combine(meeting_date, meeting_time)
    # add the event to the calendar
    event = Event(
        attendees=attendees,
        starts_at=event_start,
        subject="Meeting with Manager and Reports",
    )
    add_event(event)


def avoid_specific_attendees():
    """Schedule a team meeting avoiding some attendees.

    Query: Hey, [Assistant] Make sure our team project planning is scheduled the
    thursday after next at 14:30. Ben and Jerry don't need to attend because
    they're on a different project.
    """

    # find attendees
    usr = get_current_user()
    team = find_team_of(usr)
    # by structure guideline #1
    attendees_to_avoid = [find_employee(name)[0] for name in ["Ben", "Jerry"]]
    attendees = [p for p in team if p not in attendees_to_avoid]
    # determine the event start time
    planning_time = time_by_hm(hour=2, minute=30, am_or_pm="pm")
    next_thursday = get_next_dow("Thursday")
    planning_date = get_next_dow("Thursday", after=next_thursday)
    starts_at = combine(planning_date, planning_time)
    # add the event to the calendar
    event = Event(
        subject="Project planning",
        starts_at=starts_at,
        attendees=attendees,
        attendees_to_avoid=attendees_to_avoid,
    )
    add_event(event)


def modify_existing_event_start_time():
    """Change the start time of an existing event.

    Query: Hey, [Assistant], would you mind pushing back
     my catch-up meeting with Pete taking place next Tuesday by 23 minutes?
    """

    # find the meeting the user refers to
    employees_named_pete = find_employee("Pete")
    events = []
    # hold off applying structure guideline #1 because the meeting
    # date might resolve the ambiguity - I'll follow structure
    # guideline #2 if this is not the case
    for employee in employees_named_pete:
        events += find_events(
            attendees=[employee],
            subject="Catch-up",
        )
    meeting_date = get_next_dow("Tuesday")
    filtered_events = [e for e in events if e.starts_at.date() == meeting_date]
    # by structure guideline #2
    if len(filtered_events) == 0:
        raise RequiresUserInput(
            "No catch-up meetings with Pete at the specified time were found."
        )
    elif len(filtered_events) > 1:
        template = f"{len(filtered_events)} were found, the first of which is {filtered_events[0]}. "
        if len(employees_named_pete) > 1:
            template += f"{len(employees_named_pete)} employees named Pete were found, which one did you mean"
        raise RequiresUserInput(template)
    else:
        next_tues_catch_up = filtered_events[0]
        # update the event
        offset = Duration(23, unit=TimeUnits.Minutes)
        new_meeting_start = modify(
            next_tues_catch_up.starts_at, offset, operator=DateTimeClauseOperators.add
        )
        new_meeting_end = modify(
            next_tues_catch_up.ends_at, offset, operator=DateTimeClauseOperators.add
        )
        next_tues_catch_up.starts_at = new_meeting_start
        next_tues_catch_up.ends_at = new_meeting_end
        # add the updated event to the calendar
        add_event(next_tues_catch_up)


def busiest_day_this_week() -> datetime.date | None:
    """Inform the user when they are busiest in the current week.

    Query: Hey, [Assistant], my busiest day this week?
    """

    # find all the *future* events in the user calendar
    all_events = find_events()
    # create a look-up of relevant events
    events_by_day = defaultdict(list)
    this_week = this_week_dates()
    for e in all_events:
        event_date = e.starts_at.date()
        if event_date in this_week:
            events_by_day[event_date].append(e.duration)
    # user has no meetings this week
    if not events_by_day:
        return
    # busiest day means the most time spent in meetings
    event_durations = {e: sum_time_units(events_by_day[e]) for e in events_by_day}
    return max(event_durations, key=event_durations.get)
