"""App providing convenience utilities for searching conference rooms."""

import datetime
from dataclasses import dataclass

from pydantic import BaseModel

from aspera.apps.time_utils import TimeInterval


@dataclass
class ConferenceRoom:

    room_name: str
    capacity: int


class RoomAvailability(BaseModel):
    """The availability schedule for a room.

    Attributes
    ----------
    room
    free_slots
        When is the room available for booking.
        This list may be empty if the search
        is queried with time windows when the room
        is fully booked.
    """

    room: ConferenceRoom
    free_slots: list[TimeInterval]


def find_available_time_slots(
    room_name: str,
    time_window: list[TimeInterval] | list[datetime.date],
) -> list[TimeInterval]:
    """Check the availability of a certain room on  certain dates or
    specific time intervals.

    Parameters
    ----------
    room_name
        The name of the room.
    time_window
        The dates or time intervals for which availability will be checked.

    Returns
    -------
    A list of time intervals indicating the room availability. If the room
    is not available for the duration of the entire time window, the intervals
    when the room is available, if any, are returned. An empty list is returned
    if there are no available time slots for the given time window.
    """


def room_booking_default_time_window() -> TimeInterval:
    """Get a default time interval extending from the current time to
    the end of the working day on the following Friday. Use for room search
    when the user does not specify the time interval (or intervals) they
    wish to book the room in."""


def search_conference_room(
    time_constraints: list[TimeInterval] | list[datetime.date],
    capacity: int | None = None,
) -> list[RoomAvailability]:
    """Search for an available conference room given time and room size constraints.

    Parameters
    ----------
    time_constraints
        When to search for the room. If dates are specified, availability will be
        checked between the start and end of the working day.
    capacity
        How many people should fit in the conference room. Rooms with capacity greater
        than or equal to `capacity` will be returned if `capacity` is specified.

    Returns
    -------
    availability
       The slots when the room can be booked that satisfy the time constraints
       for each room satisfying capacity constraints (if specified). If the
       room is not available for the entire duration of the time interval(s)
       specified, the intervals when the room is available overlapping with the
       specified time windows are returned. Note that if a room is unavailable
       for the queried duration, it is still included in the search results (see
       `RoomAvailability` docs)
    """


def summarise_availability(
    schedule: list[RoomAvailability],
    room_name: str | None = None,
) -> str:
    """Create a concise summary of the availability of conference rooms.

    Parameters
    ----------
    schedule
        The free slots for one or more conference rooms.
    room_name
        If specified, the summary will only contain information about this
        room. Otherwise, the availability of all rooms in the schedule
        will be summarised.
    """
