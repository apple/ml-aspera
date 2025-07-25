"""A powerful calendar app provided by the user's employer to help them get organised."""

import datetime
from dataclasses import dataclass
from enum import StrEnum, auto
from typing import Literal, NamedTuple

from aspera.apps.company_directory import Employee
from aspera.apps.files import Document
from aspera.apps.time_utils import Duration, RepetitionSpec, TimeInterval


def get_default_preparation_time() -> Duration:
    """Returns a default preparation time of 30 minutes for a meeting.
    Use when the user requests changing meeting durations to include
    preparation without specifying a given duration.
    """


# enumeration for setting the meeting status
class ShowAsStatus(StrEnum):
    Busy = auto()
    OutOfOffice = auto()
    Free = auto()


@dataclass
class Event:
    """A calendar event.

    Parameters
    ----------
    attendees
        List of employees who have accepted the event invitation.
    attendees_to_avoid
        Specify to mark employees who should not be added to a meeting.
    optional_attendees
        A list of employees for whom the event invitation will be marked as optional.
    declined_by
       Employees who declined the calendar invite.
    tentative_attendees
        Employees which have yet to confirm their attendance or marked
        the event as tentative.
    location
        The location where the event will happen. This may
        be a conference room name or generic point of interest
        (eg Central Park, a specific address etc)
    event_importance
        Whether the event is important or not.
    repeats
        Allows the user to choose a default repetition
        schedule option or customise the frequency
        of a particular event.
    notes
        Brief notes the user can add to an event.
    original_starts_at
        For instances of recurring events, this field represents the start
        time of the parent recurring event. It is different from `start_time`
        if this instance was moved.
    """

    attendees: list[Employee] | None = None
    attendees_to_avoid: list[Employee] | None = None
    optional_attendees: list[Employee] | None = None
    declined_by: list[Employee] | None = None
    tentative_attendees: list[Employee] | None = None
    subject: str | None = None
    location: str | None = None
    starts_at: datetime.datetime | None = None
    ends_at: datetime.datetime | None = None
    show_as_status: ShowAsStatus = ShowAsStatus.Busy
    event_importance: Literal["normal", "high"] = "normal"
    repeats: RepetitionSpec | None = None
    notes: str | None = None
    video_link: str | None = None
    attachments: list[Document] | None = None
    original_starts_at: datetime.datetime | None = None

    @property
    def duration(self) -> Duration:
        """Returns the duration of an event, in minutes"""

    def __str__(self) -> str: ...


def add_event(event: Event) -> None:
    """Add an event or update an existing event in the user's calendar.

    Parameters
    ----------
    event
        An event to add to the user calendar or an existing event instance
        that has been updated.

    Notes
    -----
    1. This API manages the user calendar, so it is not necessary
    to include the user profile in attendees fields - this is handled
    by the backend.
    2. If the user does not specify the end time of the event, the
    backend will automatically determine a suitable event duration. Hence,
    do not make assumptions on when a particular event should end.
    """


def find_events(
    attendees: list[Employee] | None = None, subject: str | None = None
) -> list[Event]:
    """Search an upcoming event by specific attendees or title in the user's calendar.
    Call with no parameters will return all the events in the user's calendar.

    Parameters
    -----------
    attendees
        Invitees who have accepted the invitation, other than the user.
        Should *not* include user's profile.
    subject
        Meeting title (fuzzy matched).
    """


def find_past_events(
    attendees: list[Employee] | None = None, subject: str | None = None
) -> list[Event]:
    """Endpoint for finding events which have already occurred **in the user's calendar.**
    When called with no parameters, all the past events in the user's calendar are returned.

    Parameters
    -----------
    attendees
        Invitees who have accepted the invitation.

    Notes
    -----
    1. Just like `find_events`, the user profile should *not* be included in `attendees` when
    calling this API.
    """


def get_calendar(employee: Employee) -> list[Event]:
    """Use this function to check the calendar of another team member.

    Notes
    -----
    1. This API does not return events in the user calendar. Use `find_events` instead.
    2. When querying for events in `employees` calendar with certain attendees, the calendar owner *should not* include the calendar's owner (e.g., if looking up a meeting between Mark and his manager in manager's calendar, you will only find Mark's profile in the attendees.
    """


class CalendarSearchSettings(NamedTuple):
    """Calendar search settings.

    Parameters
    ---------
    earliest_free_slot_start
        The earliest start time of an available slot.
        Slots starting before this time are considered
        not available.
    latest_free_slot_finish
        The latest finish of an available time slot.
    """

    earliest_free_slot_start: datetime.time
    latest_free_slot_finish: datetime.time


def delete_event(event: Event):
    """Delete an event from the user calendar."""


def get_search_settings(
    calendar_key: Literal["work", "default"],
) -> CalendarSearchSettings:
    """Getter for settings which determine the returned free slots in the calendar.

    Parameters
    ----------
    calendar_key
        Which calendar is to be searched. Feature is only supported for work calendars
        at the moment.
    """


def find_available_slots(
    events: list[Event],
    search_settings: CalendarSearchSettings | None = None,
    date: datetime.date | None = None,
) -> list[TimeInterval]:
    """Return a list of time slots when no events are scheduled to occur.

    Parameters
    ----------
    events
        A list of events that are scheduled.
    search_settings
        If specified, a time interval where no event is scheduled is returned only if
        it starts at or after the `earliest_free_slot_start`. All intervals returned
        should finish before `latest_free_slot_finish`. If not specified, then the
        settings returned by `get_search_settings('default')` will be used.
    date
        If specified, only available slots on `date` are returned.

    Returns
    -------
    A list of time intervals where no events occur, subject to `search_settings` and
    `date` constraints.

    Notes
    -----
    1. If no events are specified, a time interval satisfying `search_settings` is
    returned for each date from the calling time till the next Friday. If `date` is
    specified, then a single time interval satisfying `search_settings` is returned
    for that particular date.
    """


def share_calendar(recipients: list[Employee]):
    """Share user's calendar with specified recipients."""


def summarise_calendar(events: list[Event], name: str | None = None) -> str:
    """Provide a succinct and informative summary of an event series. The
    summary mentions the number of events and details for the first
    event in the series.

    Parameters
    ----------
    name
        The name of the employee whose calendar is being summarized.

    Returns
    -------
    A string representing the summary.
    """


def provide_event_details(events: list[Event]) -> str:
    """Provide the user with details for specified events or use it to
    create a detailed summary of *all* `events` when needed.

    See also: `summarise_calendar`.

    Parameters
    ----------
    events
        The events to be included in the detailed summary.

    Returns
    -------
    A string representing detailed information about the events.
    """
