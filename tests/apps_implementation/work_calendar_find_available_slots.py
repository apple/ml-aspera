#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import datetime

import pytest

from aspera.apps_implementation.time_utils import TimeInterval, combine, now_
from aspera.apps_implementation.work_calendar import (
    CalendarSearchSettings,
    Event,
    ShowAsStatus,
    find_available_slots,
)


@pytest.fixture
def search_settings():
    return CalendarSearchSettings(
        earliest_free_slot_start=datetime.time(9, 0),
        latest_free_slot_finish=datetime.time(18, 0),
    )


def create_event(
    start: str, end: str, status: ShowAsStatus = ShowAsStatus.Busy
) -> Event:
    return Event(
        starts_at=datetime.datetime.fromisoformat(start),
        ends_at=datetime.datetime.fromisoformat(end),
        show_as_status=status,
    )


def test_no_events_with_default_settings(search_settings):
    slots = find_available_slots(events=[], search_settings=search_settings)
    today = now_().date()
    assert len(slots) == 4
    assert slots[0] == TimeInterval(
        start=combine(today, search_settings.earliest_free_slot_start),
        end=combine(today, search_settings.latest_free_slot_finish),
    )


def test_no_events_date(search_settings):
    avail_date = (now_() + datetime.timedelta(days=1)).date()
    slots = find_available_slots(
        events=[], search_settings=search_settings, date=avail_date
    )
    assert len(slots) == 1
    assert slots[0] == TimeInterval(
        start=combine(avail_date, search_settings.earliest_free_slot_start),
        end=combine(avail_date, search_settings.latest_free_slot_finish),
    )


def test_single_event_in_one_day(search_settings):
    event = create_event("2024-06-24T13:00", "2024-06-24T14:00")
    slots = find_available_slots(events=[event], search_settings=search_settings)
    assert slots == [
        TimeInterval(
            start=datetime.datetime(2024, 6, 24, 9, 0),
            end=datetime.datetime(2024, 6, 24, 13, 0),
        ),
        TimeInterval(
            start=datetime.datetime(2024, 6, 24, 14, 0),
            end=datetime.datetime(2024, 6, 24, 18, 0),
        ),
    ]


def test_multiple_events_in_one_day(search_settings):
    events = [
        create_event("2024-06-24T10:00", "2024-06-24T11:00"),
        create_event("2024-06-24T13:00", "2024-06-24T14:00"),
        create_event("2024-06-24T15:00", "2024-06-24T16:00"),
    ]
    slots = find_available_slots(events=events, search_settings=search_settings)
    assert slots == [
        TimeInterval(
            start=datetime.datetime(2024, 6, 24, 9, 0),
            end=datetime.datetime(2024, 6, 24, 10, 0),
        ),
        TimeInterval(
            start=datetime.datetime(2024, 6, 24, 11, 0),
            end=datetime.datetime(2024, 6, 24, 13, 0),
        ),
        TimeInterval(
            start=datetime.datetime(2024, 6, 24, 14, 0),
            end=datetime.datetime(2024, 6, 24, 15, 0),
        ),
        TimeInterval(
            start=datetime.datetime(2024, 6, 24, 16, 0),
            end=datetime.datetime(2024, 6, 24, 18, 0),
        ),
    ]


def test_event_across_multiple_days(search_settings):
    event = create_event("2024-06-24T17:00", "2024-06-25T10:00")
    slots = find_available_slots(events=[event], search_settings=search_settings)
    assert slots == [
        TimeInterval(
            start=datetime.datetime(2024, 6, 24, 9, 0),
            end=datetime.datetime(2024, 6, 24, 17, 0),
        ),
        TimeInterval(
            start=datetime.datetime(2024, 6, 25, 10, 0),
            end=datetime.datetime(2024, 6, 25, 18, 0),
        ),
    ]


def test_free_event_during_busy_hours(search_settings):
    events = [
        create_event("2024-06-24T10:00", "2024-06-24T11:00"),
        create_event("2024-06-24T12:00", "2024-06-24T13:00", status=ShowAsStatus.Free),
        create_event("2024-06-24T14:00", "2024-06-24T15:00"),
    ]
    slots = find_available_slots(events=events, search_settings=search_settings)
    assert slots == [
        TimeInterval(
            start=datetime.datetime(2024, 6, 24, 9, 0),
            end=datetime.datetime(2024, 6, 24, 10, 0),
        ),
        TimeInterval(
            start=datetime.datetime(2024, 6, 24, 11, 0),
            end=datetime.datetime(2024, 6, 24, 14, 0),
        ),
        TimeInterval(
            start=datetime.datetime(2024, 6, 24, 15, 0),
            end=datetime.datetime(2024, 6, 24, 18, 0),
        ),
    ]


def test_boundary_times(search_settings):
    events = [
        create_event("2024-06-24T09:00", "2024-06-24T10:00"),
        create_event("2024-06-24T17:00", "2024-06-24T18:00"),
    ]
    slots = find_available_slots(events=events, search_settings=search_settings)
    assert slots == [
        TimeInterval(
            start=datetime.datetime(2024, 6, 24, 10, 0),
            end=datetime.datetime(2024, 6, 24, 17, 0),
        )
    ]


def test_specific_date_filter(search_settings):
    events = [
        create_event("2024-06-24T10:00", "2024-06-24T11:00"),
        create_event("2024-06-25T10:00", "2024-06-25T11:00"),
    ]
    slots = find_available_slots(
        events=events, search_settings=search_settings, date=datetime.date(2024, 6, 25)
    )
    assert slots == [
        TimeInterval(
            start=datetime.datetime(2024, 6, 25, 9, 0),
            end=datetime.datetime(2024, 6, 25, 10, 0),
        ),
        TimeInterval(
            start=datetime.datetime(2024, 6, 25, 11, 0),
            end=datetime.datetime(2024, 6, 25, 18, 0),
        ),
    ]


def test_multi_day_events_date(search_settings):
    """Test with events spanning multiple days."""
    events = [
        create_event("2024-08-07T08:00:00", "2024-08-08T10:00:00"),
        create_event("2024-08-08T11:00:00", "2024-08-08T12:00:00"),
    ]
    slots = find_available_slots(
        events, search_settings=search_settings, date=datetime.date(2024, 8, 7)
    )
    assert not slots


def test_overlapping_events(search_settings):
    """Test with overlapping events on the same day."""
    events = [
        create_event("2024-08-07T09:00:00", "2024-08-07T12:00:00"),
        create_event("2024-08-07T11:00:00", "2024-08-07T15:00:00"),
    ]
    slots = find_available_slots(events, search_settings=search_settings, date=None)
    expected_slots = [
        TimeInterval(
            start=datetime.datetime(2024, 8, 7, 15, 0),
            end=datetime.datetime(2024, 8, 7, 18, 0),
        )
    ]
    assert slots == expected_slots
