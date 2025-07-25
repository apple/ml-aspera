#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import uuid
from copy import deepcopy

from aspera.apps_implementation.company_directory import Employee
from aspera.apps_implementation.work_calendar import (
    Event,
    add_event,
    expand_to_instances,
    validate_starts_at,
)
from aspera.simulation.database_schemas import DatabaseNamespace
from aspera.simulation.execution_context import get_current_context

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

    event_ids = [add_event(e) for e in events]
    return event_ids


class RuntimeSetupError(Exception):
    pass


def simulate_employee_calendar(
    employee: Employee, events: list[Event]
) -> list[EventId]:
    """Simulate the calendar of an employee in the company directory.

    Parameters
    ----------
    employee
        The employee whose calendar needs to be created. The employee
        should exist in the company directory (ie the name of the employee
        should be passed to `simulate_org_structure`).
    events
        The events in the employee's calendar. `employee` should not be
        part of any fields of type list[Employee] because they own the calendar.

    Notes
    -----
    1. The employee owning the calendar should not be included in `attendees`.
    2. When creating calendars for multiple employees, ensure events are
    consistent among them.
    3. Any employees referenced in event fields should also exist in the
    company directory. Use `simulate_employee_profile` to create them.
    """

    def add_shared_calendar_event(calendar_id: str, event: Event) -> EventId:
        """Add an event to the shared calendars database.

        Raises
        ------
        RuntimeSetupError
            If the event provided has an ID. This should not occur
            as IDs are assigned to events as they are written to the DB.
        """
        validate_starts_at(event)
        context = get_current_context()
        try:
            assert event.event_id is None
        except AssertionError:
            raise RuntimeSetupError("Event has already been written to the database")
        event.event_id = str(uuid.uuid4())
        new_records = [{**event.model_dump(), "calendar_id": calendar_id}]
        # expand recurrences into instances
        maybe_recurrent_instances = expand_to_instances(event)
        if maybe_recurrent_instances is not None:
            for instance in maybe_recurrent_instances:
                new_records.append(
                    {**instance.model_dump(), "calendar_id": calendar_id}
                )
        context.add_to_database(
            namespace=DatabaseNamespace.SHARED_CALENDARS,
            rows=new_records,
        )
        return event.event_id

    ids = []
    calendar_id = employee.employee_id
    for event in events:
        try:
            event_id = add_shared_calendar_event(calendar_id, event)
            ids.append(event_id)
        except RuntimeSetupError:
            event = deepcopy(event)
            event.attendees.remove(employee)
            event.event_id = None
            event_id = add_shared_calendar_event(calendar_id, event)
            ids.append(event_id)
    return ids
