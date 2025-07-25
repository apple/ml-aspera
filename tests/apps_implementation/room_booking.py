#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import datetime
from typing import Iterator

import pytest

from aspera.apps_implementation.exceptions import SearchError
from aspera.apps_implementation.room_booking import (
    find_available_time_slots,
    search_conference_room,
)
from aspera.apps_implementation.time_utils import (
    TimeExpressions,
    TimeInterval,
    combine,
    now_,
    parse_time_string,
)
from aspera.runtime_state_generation_tools_implementation.room_booking import (
    simulate_conference_room,
)
from aspera.simulation.execution_context import ExecutionContext, new_context

rooms_and_bookings = [
    {
        "room_name": "Alpha Room",
        "capacity": 10,
        "bookings": {
            datetime.date(2024, 8, 10): [
                TimeInterval(
                    start=datetime.datetime(2024, 8, 10, 9, 0),
                    end=datetime.datetime(2024, 8, 10, 11, 0),
                ),
                TimeInterval(
                    start=datetime.datetime(2024, 8, 10, 13, 0),
                    end=datetime.datetime(2024, 8, 10, 15, 0),
                ),
            ],
            datetime.date(2024, 8, 11): [
                TimeInterval(
                    start=datetime.datetime(2024, 8, 11, 10, 0),
                    end=datetime.datetime(2024, 8, 11, 12, 0),
                ),
            ],
        },
    },
    {
        "room_name": "Beta Room",
        "capacity": 20,
        "bookings": {
            datetime.date(2024, 8, 10): [
                TimeInterval(
                    start=datetime.datetime(2024, 8, 10, 14, 0),
                    end=datetime.datetime(2024, 8, 10, 16, 0),
                ),
            ],
            datetime.date(2024, 8, 12): [
                TimeInterval(
                    start=datetime.datetime(2024, 8, 12, 9, 0),
                    end=datetime.datetime(2024, 8, 12, 11, 0),
                ),
                TimeInterval(
                    start=datetime.datetime(2024, 8, 12, 13, 0),
                    end=datetime.datetime(2024, 8, 12, 14, 0),
                ),
            ],
        },
    },
]


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
        for room_data in rooms_and_bookings:
            simulate_conference_room(**room_data)
        yield


def test_search_conference_room_no_capacity():
    room_availability = search_conference_room(
        time_constraints=[
            TimeInterval(
                start=datetime.datetime(2024, 8, 10, 11, 30),
                end=datetime.datetime(2024, 8, 10, 12, 30),
            )
        ],
        capacity=22,
    )
    assert not room_availability


def test_search_conference_room_two_rooms_available():

    constraint = TimeInterval(
        start=datetime.datetime(2024, 8, 10, 11, 30),
        end=datetime.datetime(2024, 8, 10, 12, 30),
    )
    room_availability = search_conference_room(
        time_constraints=[constraint], capacity=5
    )
    assert len(room_availability) == 2
    for slots, _ in room_availability:
        assert len(slots) == 1
        assert slots[0] == constraint


def test_search_conference_room_with_partial_availability():
    constraint = TimeInterval(
        start=datetime.datetime(2024, 8, 10, 10, 00),
        end=datetime.datetime(2024, 8, 10, 14, 30),
    )
    room_availability = search_conference_room(
        time_constraints=[constraint],
    )
    assert len(room_availability) == 2
    for slots, room in room_availability:
        match room.room_name:
            case "Alpha Room":
                assert len(slots) == 1
                assert slots[0] == TimeInterval(
                    start=datetime.datetime(2024, 8, 10, 11, 00),
                    end=datetime.datetime(2024, 8, 10, 13, 0),
                )
            case "Beta Room":
                assert len(slots) == 1
                assert slots[0] == TimeInterval(
                    start=datetime.datetime(2024, 8, 10, 10, 00),
                    end=datetime.datetime(2024, 8, 10, 14, 00),
                )


def test_search_conference_split_availability():
    constraint = TimeInterval(
        start=datetime.datetime(2024, 8, 10, 12, 30),
        end=datetime.datetime(2024, 8, 10, 15, 30),
    )
    room_availability = search_conference_room(
        time_constraints=[constraint],
    )
    for slots, room in room_availability:
        match room.room_name:
            case "Alpha Room":
                assert len(slots) == 2
                assert slots[0] == TimeInterval(
                    start=datetime.datetime(2024, 8, 10, 12, 30),
                    end=datetime.datetime(2024, 8, 10, 13, 0),
                )
                assert slots[1] == TimeInterval(
                    start=datetime.datetime(2024, 8, 10, 15, 0),
                    end=datetime.datetime(2024, 8, 10, 15, 30),
                )
            case "Beta Room":
                assert len(slots) == 1
                assert slots[0] == TimeInterval(
                    start=datetime.datetime(2024, 8, 10, 12, 30),
                    end=datetime.datetime(2024, 8, 10, 14, 00),
                )


def test_search_conference_multiple_constraints():
    constraint = [
        TimeInterval(
            start=datetime.datetime(2024, 8, 10, 12, 30),
            end=datetime.datetime(2024, 8, 10, 15, 30),
        ),
        TimeInterval(
            start=datetime.datetime(2024, 8, 10, 15, 45),
            end=datetime.datetime(2024, 8, 10, 16, 30),
        ),
    ]
    room_availability = search_conference_room(
        time_constraints=constraint,
    )
    for slots, room in room_availability:
        match room.room_name:
            case "Alpha Room":
                # nb: first constraint is the same as in test_search_conference_split_availability
                assert len(slots) == 3
                assert slots[-1] == constraint[-1]
            case "Beta Room":
                assert len(slots) == 2
                assert slots[-1] == TimeInterval(
                    start=datetime.datetime(2024, 8, 10, 16, 0),
                    end=datetime.datetime(2024, 8, 10, 16, 30),
                )


def test_search_conference_dates():

    constraint = [datetime.date(2024, 8, 10), datetime.date(2024, 8, 11)]
    room_availability = search_conference_room(
        time_constraints=constraint,
    )
    for slots, room in room_availability:
        match room.room_name:
            case "Alpha Room":
                assert len(slots) == 4
                assert slots[0] == TimeInterval(
                    start=datetime.datetime(2024, 8, 10, 11, 0),
                    end=datetime.datetime(2024, 8, 10, 13, 0),
                )
                assert slots[1] == TimeInterval(
                    start=datetime.datetime(2024, 8, 10, 15, 0),
                    end=combine(
                        constraint[0],
                        parse_time_string(TimeExpressions["EndOfWorkDay"]),
                    ),
                )
                assert slots[2] == TimeInterval(
                    start=combine(
                        constraint[1],
                        parse_time_string(TimeExpressions["StartOfWorkDay"]),
                    ),
                    end=datetime.datetime(2024, 8, 11, 10, 0),
                )
                assert slots[3] == TimeInterval(
                    start=datetime.datetime(2024, 8, 11, 12, 0),
                    end=combine(
                        constraint[1],
                        parse_time_string(TimeExpressions["EndOfWorkDay"]),
                    ),
                )
            case "Beta Room":
                assert len(slots) == 3
                assert slots[0] == TimeInterval(
                    start=combine(
                        constraint[0],
                        parse_time_string(TimeExpressions["StartOfWorkDay"]),
                    ),
                    end=datetime.datetime(2024, 8, 10, 14, 0),
                )
                assert slots[1] == TimeInterval(
                    start=datetime.datetime(2024, 8, 10, 16, 0),
                    end=combine(
                        constraint[0],
                        parse_time_string(TimeExpressions["EndOfWorkDay"]),
                    ),
                )
                assert slots[2] == TimeInterval(
                    start=combine(
                        constraint[1],
                        parse_time_string(TimeExpressions["StartOfWorkDay"]),
                    ),
                    end=combine(
                        constraint[1],
                        parse_time_string(TimeExpressions["EndOfWorkDay"]),
                    ),
                )


def test_find_available_time_slots_wrong_room_name():

    with pytest.raises(SearchError):
        _ = find_available_time_slots("Room Gamma", time_window=[now_().date()])
