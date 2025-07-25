#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import uuid
from datetime import datetime

from aspera.apps_implementation.time_utils import TimeInterval
from aspera.simulation.database_schemas import DatabaseNamespace
from aspera.simulation.execution_context import get_current_context

RoomId = str
RoomBookingID = str


def create_room(room_name: str, capacity: int) -> RoomId:
    """Create a room in the underlying database."""
    context = get_current_context()
    room_id = str(uuid.uuid4())
    context.add_to_database(
        namespace=DatabaseNamespace.CONFERENCE_ROOMS,
        rows=[{"room_id": room_id, "capacity": capacity, "room_name": room_name}],
    )
    return room_id


def create_booking(room_id: str, start: datetime, end: datetime) -> RoomBookingID:
    """Create a booking for an existing conference room.

    Parameters
    ----------
    room_id
        The unique identifier of the conference room booked
    start, end
        Start and end booking times.
    """

    context = get_current_context()
    booking_id = str(uuid.uuid4())
    booking = {
        "room_id": room_id,
        "booking_id": booking_id,
        "start": start,
        "end": end,
    }
    context.add_to_database(
        namespace=DatabaseNamespace.CONFERENCE_ROOM_BOOKINGS,
        rows=[booking],
    )
    return booking_id


def simulate_conference_room(
    room_name: str,
    capacity: int,
    bookings: dict[datetime.date, list[TimeInterval]] | None = None,
):
    """Add a conference room to the conference room database.

    Parameters
    ----------
    room_name
        Which conference room to add to the database
    capacity
        The maximum number of people the room can host.
    bookings
        Time intervals when the room is booked. Set to `None` if
        there is no booking for this room.

    Notes
    -----
    1. Booking dates should be in the future with respect to the current time
    (returned by the now_() function).
    2. Bookings should respect the start and end of the working day.
    """

    # add room to the DB
    room_id = create_room(room_name, capacity)
    # create the bookings
    if bookings is not None:
        for date, times_booked in bookings.items():
            for interval in times_booked:
                create_booking(room_id, interval.start, interval.end)
