# Request: Hey, [Assistant], schedule a meeting with my team every day next week at 3 PM.
def schedule_daily_team_meeting_next_week():
    """Schedule a daily meeting with the user's team next week at 3 PM."""

    # find the user's team to determine event attendees
    user = get_current_user()
    team = find_team_of(user)

    # resolve the meeting time specified by the user
    meeting_time = time_by_hm(hour=3, minute=0, am_or_pm="pm")

    # get the dates for next week
    next_week_dates = parse_duration_to_calendar("NextWeek")[0]

    # add the event to the calendar for each day next week
    for meeting_date in next_week_dates:
        starts_at = combine(meeting_date, meeting_time)
        event = Event(attendees=team, starts_at=starts_at, subject="Daily Team Meeting")
        add_event(event)


# Assessment:
def is_correct() -> bool:
    """The program above is not correct because while events are scheduled
    every day next week, the model fails to follow the instruction according to
    which events should not be scheduled at the weekend."""
    return False


# Request: Hey, [Assistant], schedule a meeting around 3 PM tomorrow with my team.
def schedule_meeting_with_team():
    """Schedule a meeting with the user's team.

    Query: Hey, [Assistant], schedule a meeting around 3 PM tomorrow with my team.
    """

    # find the user's team to determine event attendees
    user = get_current_user()
    team = find_team_of(user)

    # use the library to resolve the meeting time specified by the user
    resolved_date = DateExpressions["Tomorrow"]
    meeting_date = parse_date_string(resolved_date)
    meeting_time = time_by_hm(hour=3, minute=0, am_or_pm="pm")
    starts_at = combine(meeting_date, meeting_time)

    # add the event to the calendar
    event = Event(attendees=team, starts_at=starts_at, subject="Team meeting")
    add_event(event)


# Assessment:
def is_correct() -> bool:
    """The program above is correct. The tools from the time_utils library are used
    to correctly determine the meeting time, the team is added to the event. In addition,
    the user does not mention the end time of the meeting, and, since it cannot be deduced
    the `ends_at` is left unfilled as recommended in `add_event` documentation."""
    return True


# Request: Hey, [Assistant], schedule a project update meeting with my manager before 3 PM tomorrow.
def schedule_project_update_meeting():
    """Schedule a project update meeting with the user's manager before 3 PM tomorrow.

    Query: Hey, [Assistant], schedule a project update meeting with my manager before 3 PM tomorrow.
    """

    # find the current user and their manager
    current_user = get_current_user()
    manager = find_manager_of(current_user)

    # resolve the meeting date and time specified by the user
    resolved_date = DateExpressions["Tomorrow"]
    meeting_date = parse_date_string(resolved_date)
    latest_meeting_time = time_by_hm(hour=3, minute=0, am_or_pm="pm")

    # find available slots in the manager's calendar before 3 PM tomorrow
    manager_calendar = get_calendar(manager)
    search_settings = CalendarSearchSettings(
        earliest_free_slot_start=datetime.time(0, 0),  # start of the day
        latest_free_slot_finish=latest_meeting_time,
    )
    available_slots = find_available_slots(
        manager_calendar, search_settings, date=meeting_date
    )

    # if no available slots are found, raise an exception
    if not available_slots:
        raise RequiresUserInput("No available slots found before 3 PM tomorrow.")

    # schedule the meeting at the earliest available slot
    earliest_slot = available_slots[0]
    starts_at = earliest_slot.start
    ends_at = earliest_slot.end

    # add the event to the calendar
    event = Event(
        attendees=[manager],
        starts_at=starts_at,
        ends_at=ends_at,
        subject="Project Update Meeting",
    )
    add_event(event)


# Assessment:
def is_correct() -> bool:
    """The program above is not correct. By changing the search settings for checking
    availability to start at midnight, available slots in manager's calendar will
    be returned in the early ours of tomorrow as described in the `find_available_slots`
    documentation. Therefore, the meeting will be scheduled in the first available slot,
    which starts at midnight. Moreover, in setting the meeting end to the end of the
    available slot, as opposed to allowing the default event duration, the meeting duration
    is also incorrect."""
    return False


# Request:  Hey, [Assistant], can you remind me to send a thank-you email to the client after our meeting tomorrow?"
def remind_to_send_thank_you_email():
    """Remind the user to send a thank-you email to the client after their meeting tomorrow."""

    # use the library to resolve the meeting time specified by the user
    resolved_date = parse_date_string(DateExpressions["Tomorrow"])
    # find any client meetings
    client_meetings = find_events(subject="Client Meeting")
    # ensure they happen tomorrow
    client_meeting_tomorrow = [
        c for c in client_meetings if c.starts_at.date() == resolved_date
    ][0]
    # add the reminder event to the calendar
    reminder_event = Event(
        starts_at=client_meeting_tomorrow.ends_at,
        subject="Send thank-you email to the client",
        notes="Reminder to send a thank-you email to the client after the meeting.",
    )
    add_event(reminder_event)


# Assessment:
def is_correct() -> bool:
    """The program above is correct. The `find_event` tool is employed in combination with
    relevant filtering to identify the client meeting the user refers to and a suitable
    reminder time is determined as a result. The relevant is created in accord with the
    `add_event` documentation  - the user is not added to the attendees list because the
    reminder and a default duration for the event is assumed."""
    return True


# Request: Hey, [Assistant], can you find the email address for the CEO?
def find_ceo_email() -> str:
    """Find the email address for the CEO.

    Query: Hey, [Assistant], can you find the email address for the CEO?
    """

    # find the CEO in the company's directory
    ceo = find_employee("CEO")
    # by structure guideline #1
    if len(ceo) == 0:
        raise RequiresUserInput("No CEO found in the company's directory.")
    elif len(ceo) > 1:
        raise RequiresUserInput(f"Multiple CEOs found: {len(ceo)}. Please specify.")
    else:
        ceo_details = get_employee_profile(ceo[0])
        return ceo_details.email_address


# Assessment:
def is_correct() -> bool:
    """The program above is not correct. The documentation of the `find_employee` function
    clearly states that its purpose is to resolve a person's name (eg Jean) to an `Employee`
    object, and no mention is made that it can be used to find an employee according to their
    role. The program overlooks important guidelines information - that the CEO is part of the
    leadership team, and fails to apply common sense knowledge that the CEO is the only member
    of the leadership team without reports to indentify the correct employee. The program will
    fail with an error as a result."""
    return False


# Request:
def finance_team_with_overlapping_vacations() -> list[str]:
    """Find finance team members with overlapping vacations.

    Query: Hey, [Assistant], tell me the names of finance team members with overlapping vacations?
    """

    # Get all employees in the finance team
    finance_team = [
        emp
        for emp in get_all_employees()
        if get_employee_profile(emp).team == Team.Finance
    ]

    # Get vacation schedules for each finance team member
    vacation_schedules = {emp: get_vacation_schedule(emp) for emp in finance_team}

    # Find overlapping vacations
    overlapping_vacations = defaultdict(list)
    for emp, intervals in vacation_schedules.items():
        if intervals:
            for other_emp, other_intervals in vacation_schedules.items():
                if emp != other_emp and other_intervals:
                    for interval in intervals:
                        for other_interval in other_intervals:
                            if intervals_overlap(interval, other_interval):
                                overlapping_vacations[emp.name].append(other_emp.name)
                                overlapping_vacations[other_emp.name].append(emp.name)

    # Get unique names of employees with overlapping vacations
    overlapping_names = list(set(overlapping_vacations.keys()))
    return overlapping_names


# Assessment:
def is_correct() -> bool:
    """The program above is correct. In the first step the program correctly uses
    the relevant tools to identify the members of the finance team. All relevant
    holiday periods are taken account and potential overlaps detected.
    The program also takes into account the fact that a unique list of employee
    names are to be returned."""
    return True


# Request: Hey, [Assistant], schedule a training session for my team next Wednesday from 1 PM to 4 PM. Book a conference room with a capacity of at least 10 people.
def schedule_team_training_session():
    """Schedule a training session for the user's team.

    Query: Hey, [Assistant], schedule a training session for my team next Wednesday from 1 PM to 4 PM. Book a conference room with a capacity of at least 10 people.
    """

    # find the user's team to determine event attendees
    user = get_current_user()
    team = find_team_of(user)

    # resolve the meeting time specified by the user
    next_wednesday = get_next_dow("Wednesday")
    training_start_time = time_by_hm(hour=1, minute=0, am_or_pm="pm")
    training_end_time = time_by_hm(hour=4, minute=0, am_or_pm="pm")
    training_start = combine(next_wednesday, training_start_time)
    training_end = combine(next_wednesday, training_end_time)

    # search for an available conference room with a capacity of at least 10 people
    time_interval = TimeInterval(start=training_start, end=training_end)
    available_rooms = search_conference_room(
        time_constraints=[time_interval], capacity=10
    )

    if not available_rooms:
        raise RequiresUserInput(
            "No available conference rooms with the required capacity were found."
        )

    # book the first available room
    room_to_book = available_rooms[0].room
    event = Event(
        attendees=team,
        starts_at=training_start,
        ends_at=training_end,
        subject="Team Training Session",
        location=room_to_book.room_name,
    )
    add_event(event)


# Assessment:
def is_correct() -> bool:
    """The program above is not correct. The error stems from the incorrect reading of the
    documentation for the `room_booking` utilities. Crucially, the `search_conference_room`
    function will never return an empty list because the `RoomAvailability` documentations
    state that the `free_slots` will be empty if the room is not available during the specified
    time intervals. Moreover, the documentation clearly states that intervals when the room
    is free overlapping with the query window will be returned, and so the caller would be
    expected to check whether a room can accommodate a given event based on the slots returned,
    if any. In failing to take this into account the program may not function as intended because
    the first room may not be available."""
    return False


# Request: Hey, [Assistant], tell me the names of our marketing managers who are on holiday next week.
from typing import List


def marketing_managers_on_holiday_next_week() -> List[str]:
    """Tell the names of marketing managers who are on holiday next week."""

    # Get all employees
    all_employees = get_all_employees()

    # Filter employees who are in the Sales and Marketing team
    marketing_team = [
        emp
        for emp in all_employees
        if get_employee_profile(emp).team == Team.SalesMarketing
        and find_reports_of(emp)
    ]

    # Get the date range for next week
    next_week_range = parse_durations_to_date_interval(DateRanges.NextWeek)

    # Find marketing managers who are on holiday next week
    marketing_managers_on_holiday = []
    for employee in marketing_team:
        vacation_schedule = get_vacation_schedule(employee)
        if vacation_schedule:
            for interval in vacation_schedule:
                if (
                    interval.start.date() <= next_week_range.end
                    and interval.end.date() >= next_week_range.start
                ):
                    marketing_managers_on_holiday.append(employee.name)
                    break

    return marketing_managers_on_holiday


# Assessment:
def is_correct() -> bool:
    """The program above is correct. After correctly identifying the sales team
    managers and the relevant period, a correct comparison taking into account holidays
    that extend over the week boundaries is made to determine the relevant employees."""
    return True
