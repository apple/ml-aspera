#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import datetime
from datetime import timedelta

from aspera.apps_implementation.time_utils import TimeInterval, combine, now_
from aspera.runtime_state_generation_tools_implementation.room_booking import (
    create_booking,
    create_room,
    simulate_conference_room,
)
from aspera.simulation.database_schemas import DatabaseNamespace
from aspera.simulation.execution_context import ExecutionContext, new_context


def test_create_room():

    context = ExecutionContext()
    room_1 = {"room_name": "Open All Hours", "capacity": 4}
    room_2 = {"room_name": "The Mighty Boosh", "capacity": 16}
    with new_context(context):
        room_1_id = create_room(**room_1)
        room_1["room_id"] = room_1_id
        room_2_id = create_room(**room_2)
        room_2["room_id"] = room_2_id
        room_db = context.get_database(namespace=DatabaseNamespace.CONFERENCE_ROOMS)
        assert len(room_db) == 2
        assert all(r in room_db.to_dicts() for r in (room_1, room_2))


def test_create_booking():
    context = ExecutionContext()
    room_1 = {"room_name": "Open All Hours", "capacity": 4}
    booking_start = now_()
    booking_end = booking_start + timedelta(hours=1)
    with new_context(context):
        room_1_id = create_room(**room_1)
        booking_id = create_booking(room_1_id, booking_start, booking_end)
        booking_db = context.get_database(
            namespace=DatabaseNamespace.CONFERENCE_ROOM_BOOKINGS
        )
        assert len(booking_db) == 1
        booking = booking_db.to_dicts()[0]
        assert booking["booking_id"] == booking_id
        assert booking["start"] == booking_start
        assert booking["end"] == booking_end


def test_simulate_conference_room():
    context = ExecutionContext()
    today = now_().date()
    tomorrow = today + timedelta(days=1)
    with new_context(context):
        simulate_conference_room(
            "Shaun The Sheep",
            capacity=2,
            bookings={
                today: [
                    TimeInterval(start=now_(), end=now_() + timedelta(hours=1)),
                    TimeInterval(
                        start=now_() + timedelta(hours=2),
                        end=now_() + timedelta(hours=3),
                    ),
                ],
                tomorrow: [
                    TimeInterval(
                        start=combine(tomorrow, datetime.time(10, 0)),
                        end=combine(tomorrow, datetime.time(17, 0)),
                    )
                ],
            },
        )
        room_db = context.get_database(namespace=DatabaseNamespace.CONFERENCE_ROOMS)
        assert len(room_db) == 1
        booking_db = context.get_database(
            namespace=DatabaseNamespace.CONFERENCE_ROOM_BOOKINGS
        )
        assert len(booking_db) == 3
