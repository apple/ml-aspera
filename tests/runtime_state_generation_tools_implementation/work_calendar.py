#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import datetime
from copy import deepcopy

import pytest

from aspera.apps_implementation.company_directory import Employee
from aspera.apps_implementation.work_calendar import Event, get_calendar
from aspera.runtime_state_generation_tools_implementation.work_calendar import (
    simulate_employee_calendar,
)
from aspera.simulation.database_schemas import DatabaseNamespace
from aspera.simulation.execution_context import ExecutionContext, new_context
from tests.apps_implementation.work_calendar_utils import setup_employee_database


@pytest.fixture
def joris_event(basic_event: Event) -> Event:

    event = deepcopy(basic_event)
    event.starts_at = basic_event.starts_at + datetime.timedelta(hours=1)
    event.ends_at = basic_event.ends_at + datetime.timedelta(hours=1)
    event.video_link = "joris@webex.com"
    event.notes = "Discuss shell crash"
    event.subject = "Secret"
    event.optional_attendees = None
    return event


def test_simulate_employee_calendar(
    employees: dict[str, Employee], basic_event: Event, joris_event: Event
):

    event = deepcopy(basic_event)
    event.optional_attendees = None
    context = ExecutionContext()
    with new_context(context=context) as context:
        hector_ids = simulate_employee_calendar(employees["Hector"], [event])
        joris_ids = simulate_employee_calendar(employees["Joris"], [joris_event])
        all_ids = hector_ids + joris_ids
        raw_db = context.get_database(namespace=DatabaseNamespace.SHARED_CALENDARS)
        assert len(all_ids) == 2
        assert len(raw_db) == len(all_ids)


def test_get_calendar(
    employees: dict[str, Employee], basic_event: Event, joris_event: Event
):
    event = deepcopy(basic_event)
    event.optional_attendees = None
    context = ExecutionContext()
    with new_context(context=context):
        setup_employee_database()
        hector_ids = simulate_employee_calendar(employees["Hector"], [event])
        joris_ids = simulate_employee_calendar(employees["Joris"], [joris_event])
        hector_calendar = get_calendar(employees["Hector"])
        joris_calendar = get_calendar(employees["Joris"])
        assert len(hector_calendar) == len(joris_calendar) == 1
        assert hector_ids[0] == hector_calendar[0].event_id
        assert joris_ids[0] == joris_calendar[0].event_id
        assert hector_calendar[0].optional_attendees is None
