#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
from aspera.apps_implementation.company_directory import Employee
from aspera.apps_implementation.work_calendar import Event

EventId = str
EmployeeId = str


def simulate_user_calendar(events: list[Event]) -> list[EventId]:
    """Simulate the calendar of the device user. The user does not
    need to be included as an attendee, this is automatically handled
    in the backed.

    Parameters
    ----------
    events
        The events assumed to exist in the employee calendar. Any employees
        referenced in the event fields should exist in the company directory
        (use `simulate_employee_profile` to create an employee profile)

    Notes
    -----
    1. The user should not be included in `attendees`.
    """


def simulate_employee_calendar(employee: Employee, events: list[Event]):
    """Simulate the calendar of an employee in the company directory.

    Parameters
    ----------
    employee
        The employee whose calendar needs to be created. The employee
        should exist in the company directory (ie the name of the employee
        should be passed to `simulate_org_structure`).
    events
        The events in the employee's calendar.

    Notes
    -----
    1. The employee owning the calendar should not be included in `attendees`.
    2. When creating calendars for multiple employees, ensure events are
    consistent among them.
    3. Any employees referenced in event fields should also exist in the
    company directory. Use `simulate_employee_profile` to create them.
    """
