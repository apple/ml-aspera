#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import datetime

from aspera.apps_implementation.time_utils import TimeInterval


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
