#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import datetime
import uuid
from copy import deepcopy
from typing import Iterator

import pytest

from aspera.apps_implementation.company_directory import Employee, find_employee
from aspera.apps_implementation.exceptions import SearchError
from aspera.apps_implementation.time_utils import EventFrequency, RepetitionSpec, now_
from aspera.apps_implementation.work_calendar import (
    DEFAULT_EVENT_DURATION_MINUTES,
    Event,
    add_event,
    delete_event,
    find_events,
    find_past_events,
    get_event_by_id,
    get_event_instances,
    share_calendar,
    summarise_calendar,
)
from aspera.execution_evaluation_tools_implementation.work_calendar import (
    assert_user_calendar_shared,
)
from aspera.simulation.database_schemas import DatabaseNamespace
from aspera.simulation.execution_context import (
    ExecutionContext,
    get_current_context,
    new_context,
)
from tests.apps_implementation.work_calendar_utils import setup_employee_database


@pytest.fixture
def basic_event(employees: dict[str, Employee]) -> Event:

    return Event(
        attendees=[employees["Pete"], employees["Anders"]],
        optional_attendees=[employees["Hector"]],
        avoid_attendees=[employees["Joris"]],
        subject="End of internship party",
        starts_at=datetime.datetime(2024, 9, 26, 12, 0, 0),
        ends_at=datetime.datetime(2024, 9, 26, 13, 0, 0),
        video_link="alexlink@webex.com",
        notes="A quick gather up to celebrate success.",
    )


@pytest.fixture
def recurring_event(basic_event: Event) -> Event:
    event = deepcopy(basic_event)
    event.repeats = RepetitionSpec(frequency=EventFrequency.DAILY, max_repetitions=5)
    return event


@pytest.fixture(scope="function", autouse=True)
def execution_context() -> Iterator[None]:
    """Autouse fixture which will setup and teardown execution
    context before and after each test function

    Returns:

    """
    # Set test context
    test_context = ExecutionContext()
    # ensure that the employees are added to the database
    with new_context(test_context):
        setup_employee_database()
        yield


def test_employee_list_serialisation(basic_event: Event) -> None:

    serialised = basic_event.model_dump()
    attendees = sorted(basic_event.attendees, key=lambda x: x.name)
    assert serialised["attendees"] == [attendee.employee_id for attendee in attendees]


def test_event_deserialisation(basic_event: Event) -> None:

    serialised = basic_event.model_dump()
    deserialised = Event.from_dict(serialised)
    assert deserialised.attendees == sorted(basic_event.attendees, key=lambda x: x.name)
    # check that the ordering of the employees does not affect comparisons
    assert deserialised in [basic_event]


def test_add_event(basic_event: Event):

    event_id = add_event(basic_event)
    all_events = find_events()
    assert len(all_events) == 1
    [expected_event] = [e for e in all_events if e.event_id == event_id]
    assert expected_event == basic_event


def test_find_event_subject_exact(basic_event: Event):

    event_id = add_event(basic_event)
    found = find_events(subject=basic_event.subject)
    assert len(found) == 1
    assert found[0].event_id == event_id


def test_find_event_subject_fuzzy(basic_event: Event):

    event_id = add_event(basic_event)
    found = find_events(subject="Internship party")
    assert len(found) == 1
    assert found[0].event_id == event_id


def test_find_event_attendees(basic_event: Event):

    event_id = add_event(basic_event)
    found = find_events(attendees=basic_event.attendees)
    assert len(found) == 1
    assert found[0].event_id == event_id


def test_find_event_no_match(basic_event: Event):

    _ = add_event(basic_event)
    found = find_events(
        attendees=[Employee(name="Dean", employee_id=str(uuid.uuid4()))]
    )
    assert not found


def test_event_update(basic_event: Event, employees: dict[str, Employee]):

    add_event(basic_event)
    joris = employees["Joris"]
    found = find_events(attendees=basic_event.attendees)
    assert len(found) == 1
    expected_event = found[0]
    new_attendees = basic_event.attendees + [joris]
    expected_event.attendees = new_attendees
    updated_event_id = add_event(expected_event)
    assert updated_event_id == expected_event.event_id
    found = find_events(subject=basic_event.subject)
    assert len(found) == 1
    assert found[0].event_id == updated_event_id
    # have to sort the attendees since these are normalised when writing to the underlying DB
    assert found[0].attendees == sorted(new_attendees, key=lambda a: a.name)


def test_add_recurring_event(recurring_event: Event):

    event_id = add_event(recurring_event)
    found = find_events()
    # we don't return instances of recurring events - only their parents
    assert len(found) == 1
    assert found[0].event_id == event_id
    # check we restored the repetition spec properly from the DB
    assert found[0].repeats == recurring_event.repeats
    context = get_current_context()
    raw_db = context.get_database(namespace=DatabaseNamespace.USER_CALENDAR)
    # however, we store the recurring event instances - they can be
    # retrieved from the DB with a separate function call
    assert len(raw_db) == recurring_event.repeats.max_repetitions + 1


def test_modify_recurring_event(recurring_event: Event):

    event_id = add_event(recurring_event)
    recurring_event.repeats.max_repetitions = 3
    new_event_id = add_event(recurring_event)
    assert new_event_id == event_id
    found = find_events()
    assert len(found) == 1
    context = get_current_context()
    raw_db = context.get_database(namespace=DatabaseNamespace.USER_CALENDAR)
    assert len(raw_db) == recurring_event.repeats.max_repetitions + 1


def test_delete_event(basic_event: Event, recurring_event: Event):

    recurring_event_id = add_event(recurring_event)
    basic_event_id = add_event(basic_event)
    found = find_events()
    assert len(found) == 2
    [rec_ev] = [e for e in found if e.event_id == recurring_event_id]
    [basic_event] = [e for e in found if e.event_id == basic_event_id]
    delete_event(basic_event)
    assert len(find_events()) == 1
    delete_event(rec_ev)
    context = get_current_context()
    raw_db = context.get_database(namespace=DatabaseNamespace.USER_CALENDAR)
    assert len(raw_db) == 0


def test_delete_event_raises_search_error(basic_event: Event):

    with pytest.raises(SearchError):
        delete_event(basic_event)


def test_get_recurrent_event_instances(recurring_event: Event):

    add_event(recurring_event)
    instances = get_event_instances(recurring_event)
    assert len(instances) == recurring_event.repeats.max_repetitions


# TODO: TEST UPDATE TO RECURRING EVENT INSTANCE


def test_get_recurrent_event_instance_raises_exception(
    recurring_event, basic_event: Event
):
    add_event(recurring_event)
    with pytest.raises(SearchError):
        get_event_instances(basic_event)


def test_get_event_instance_by_id(recurring_event: Event):

    add_event(recurring_event)
    last_instance = get_event_instances(recurring_event)[-1]
    last_instance_id = last_instance.event_id
    assert last_instance == get_event_by_id(last_instance_id)


def test_event_no_attendees(basic_event: Event):

    test_context = ExecutionContext()
    with new_context(test_context):
        test_event = Event(
            attendees=[],
            subject="Focus time",
            starts_at=now_(),
            ends_at=now_() + datetime.timedelta(hours=1),
        )
        add_event(test_event)
        events = find_events(attendees=[])
        assert len(events) == 1
        event = events[0]
        assert event.subject == "Focus time"
        assert not event.attendees
        assert isinstance(event.event_id, str)


def test_event_default_duration(employees: dict[str, Employee]):

    test_event = Event(
        attendees=[employees["Pete"]],
        subject="Catch-up",
        starts_at=now_() + datetime.timedelta(hours=1),
    )
    add_event(test_event)
    events = find_events(attendees=[employees["Pete"]])
    assert len(events) == 1
    event = events[0]
    assert event.ends_at is not None
    assert event.ends_at == test_event.starts_at + datetime.timedelta(
        minutes=DEFAULT_EVENT_DURATION_MINUTES
    )


def test_past_events(basic_event: Event):

    past_event = deepcopy(basic_event)
    past_event_start = now_() - datetime.timedelta(days=1)
    past_event_end = (
        now_() - datetime.timedelta(days=1) + datetime.timedelta(minutes=30)
    )
    past_event.starts_at = past_event_start
    past_event.ends_at = past_event_end
    add_event(basic_event)
    add_event(past_event)
    past_events = find_past_events()
    assert len(past_events) == 1
    assert past_events[0].starts_at == past_event_start
    assert past_events[0].ends_at == past_event_end
    future_event = find_events()
    assert len(future_event) == 1


@pytest.fixture
def sample_events(employees: dict[str, Employee]):
    """Fixture to create sample events for testing"""
    now = datetime.datetime.now()
    employee1 = employees["Pete"]
    employee2 = employees["Alex"]

    event1 = Event(
        attendees=[employee1, employee2],
        subject="Meeting with team",
        location="Conference Room",
        starts_at=now,
        ends_at=now + datetime.timedelta(hours=1),
    )
    event2 = Event(
        attendees=[],
        subject="Lunch with client",
        location="Restaurant",
        starts_at=now + datetime.timedelta(days=1),
        ends_at=now + datetime.timedelta(days=1, hours=2),
    )
    return [event1, event2]


def test_summarise_calendar_no_events():
    """Test summarise_calendar with no events"""
    assert summarise_calendar([]) == "There are no events in the calendar"


def test_summarise_calendar_with_events(sample_events):
    """Test summarise_calendar with events"""
    summary = summarise_calendar(sample_events)
    assert summary.startswith("There are 2 events in your calendar.")
    assert "'Meeting with team' with Pete, Alex starting at:" in summary
    assert "for 1 hours" in summary
    assert "(location: Conference Room)" in summary


def test_share_calendar(employees: dict[str, Employee]):

    shared_with = [find_employee("Pete")[0], find_employee("Joris")[0]]
    share_calendar(shared_with)
    assert_user_calendar_shared(shared_with)
