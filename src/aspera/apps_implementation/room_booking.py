#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import datetime
from typing import TYPE_CHECKING

import polars as pl
from pydantic import BaseModel

from aspera.apps_implementation.exceptions import SearchError
from aspera.apps_implementation.time_utils import (
    TimeExpressions,
    TimeInterval,
    combine,
    get_next_dow,
    now_,
    parse_time_string,
)
from aspera.simulation.utils import filter_dataframe, gt_eq_filter_dataframe

if TYPE_CHECKING:
    from aspera.simulation.database_schemas import DatabaseNamespace


class ConferenceRoom(BaseModel):
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


def _maybe_convert_to_time_interval(
    time_window: list[datetime.date] | list[TimeInterval],
) -> list[TimeInterval]:
    """Convert dates to time intervals for the purposes of checking room availability."""
    # nb: we only check the first element so code could fail if the LLM mixes dates
    #  and time intervals - LLM should obey the type annotation and
    #  make two separate calls to the tool if eg user query is along the lines
    #  "see if room X is available between 3 and 5 PM today or anytime tomorrow"
    if isinstance(time_window[0], datetime.date):
        work_start = parse_time_string(TimeExpressions["StartOfWorkDay"])
        work_end = parse_time_string(TimeExpressions["EndOfWorkDay"])
        time_window = [
            TimeInterval(
                start=combine(d, work_start),
                end=combine(d, work_end),
            )
            for d in time_window
        ]
        return time_window
    return time_window


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
    from aspera.simulation.database_schemas import DatabaseNamespace
    from aspera.simulation.execution_context import get_current_context

    context = get_current_context()
    bookings_db: pl.DataFrame = context.get_database(
        namespace=DatabaseNamespace.CONFERENCE_ROOM_BOOKINGS
    )
    rooms_db: pl.DataFrame = context.get_database(
        namespace=DatabaseNamespace.CONFERENCE_ROOMS
    )
    time_window = _maybe_convert_to_time_interval(time_window)
    room = rooms_db.filter(
        pl.col("room_name").str.contains(f"(?i){room_name}", strict=False)
    ).select("room_id")
    if room.is_empty():
        raise SearchError(f"Room '{room_name}' not found")
    room_id = room[0, "room_id"]
    bookings = bookings_db.filter(pl.col("room_id") == room_id)
    available_intervals = []
    for interval in time_window:
        start, end = interval.start, interval.end
        overlapping_bookings = bookings.filter(
            (pl.col("start") <= end) & (pl.col("end") >= start)
        )

        if overlapping_bookings.is_empty():
            available_intervals.append(interval)
        else:
            current_start = start
            for booking in overlapping_bookings.iter_rows():
                booking_start, booking_end = booking[2], booking[3]
                if current_start < booking_start:
                    available_intervals.append(
                        TimeInterval(current_start, booking_start)
                    )
                current_start = max(current_start, booking_end)

            if current_start < end:
                available_intervals.append(TimeInterval(current_start, end))
    return available_intervals


def room_booking_default_time_window() -> TimeInterval:
    """Get a default time interval extending from the current time to
    the end of the working day on the following Friday. Use for room search
    when the user does not specify the time interval (or intervals) they
    wish to book the room in."""
    end = combine(
        get_next_dow("Friday"), parse_time_string(TimeExpressions["EndOfWorkDay"])
    )
    return TimeInterval(start=now_(), end=end)


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
       `RoomAvailability` docs)"""

    from aspera.simulation.database_schemas import DatabaseNamespace
    from aspera.simulation.execution_context import get_current_context

    context = get_current_context()
    rooms_db: pl.DataFrame = context.get_database(
        namespace=DatabaseNamespace.CONFERENCE_ROOMS
    )
    # filter the databases such that the rooms returned
    # have enough capacity
    if capacity is not None:
        rooms_db = filter_dataframe(
            rooms_db, filter_criteria=[("capacity", capacity, gt_eq_filter_dataframe)]
        )
        if len(rooms_db) == 0:
            return []
    time_constraints = _maybe_convert_to_time_interval(time_constraints)
    availability = []
    for room in rooms_db.iter_rows():
        room_name = room[2]
        free_slots: list[TimeInterval] = find_available_time_slots(
            room_name, time_constraints
        )
        availability.append(
            RoomAvailability(
                free_slots=free_slots,
                room=ConferenceRoom(room_name=room_name, capacity=room[1]),
            )
        )
    return availability


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

    if room_name is not None:
        schedule = [entry for entry in schedule if entry[1].room_name == room_name]

    if not schedule:
        return "No rooms found!"
    summaries = []
    # nb: free slots is not empty - if a room is not available find_available_time_slots
    #  will not include it.
    for result in schedule:
        room, free_slots = result.room, result.free_slots
        room_summary = f"Room: {room.room_name} (Capacity: {room.capacity})\n"
        for slot in free_slots:
            start = slot.start.strftime("%Y-%m-%d %H:%M")
            end = slot.end.strftime("%Y-%m-%d %H:%M")
            room_summary += f"  Available: {start} to {end}\n"
        if not free_slots:
            room_summary += "   Fully booked!\n"
        summaries.append(room_summary)

    return "\n".join(summaries)
