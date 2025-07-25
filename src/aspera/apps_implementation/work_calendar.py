#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
"""A powerful calendar app provided by the user's employer to help them get organised."""

import datetime
import functools
import logging
import uuid
from copy import deepcopy
from enum import StrEnum, auto
from typing import TYPE_CHECKING, Any, Literal, NamedTuple, Self

import polars as pl
from polars.exceptions import NoDataError
from pydantic import BaseModel, field_serializer

from aspera.apps.files import Document
from aspera.apps_implementation.company_directory import Employee, _get_employee_by_id
from aspera.apps_implementation.exceptions import EventDefinitionError, SearchError
from aspera.apps_implementation.time_utils import (
    Duration,
    RepetitionSpec,
    TimeExpressions,
    TimeInterval,
    TimeUnits,
    _repetition_schedule,
    get_next_dow,
    now_,
    parse_time_string,
)
from aspera.simulation.utils import (
    NOT_GIVEN,
    exact_match_filter_dataframe,
    filter_dataframe,
    fuzzy_match_filter_dataframe,
)

if TYPE_CHECKING:
    from aspera.simulation.database_schemas import DatabaseNamespace
DEFAULT_EVENT_DURATION_MINUTES = 16

EventId = str

logger = logging.getLogger(__name__)


def get_default_preparation_time() -> Duration:
    """Returns a default preparation time of 30 minutes for a meeting.
    Use when the user requests changing meeting durations to include
    preparation without specifying a given duration.
    """
    return Duration(30, unit=TimeUnits.Minutes)


# enumeration for setting the meeting status
class ShowAsStatus(StrEnum):
    Busy = auto()
    OutOfOffice = auto()
    Free = auto()


EMPLOYEE_FIELDS = (
    "attendees",
    "attendees_to_avoid",
    "optional_attendees",
    "declined_by",
    "tentative_attendees",
)

ID_FIELDS = ("event_id", "recurrent_event_id")
STRUCT_FIELDS = ("repeats", "attachments")


class Event(BaseModel):
    """A calendar event.

    Parameters
    ----------
    attendees
        List of attendees who have accepted the event invitation.
    attendees_to_avoid
        Most useful for excluding certain individuals when the list of
        attendees is populated automatically (eg with employees
        returned from an API).
    optional_attendees
        A list of attendees for which the event invitation will be marked as optional.
    declined_by
       Attendees which declined the calendar invite.
    tentative_attendees
        Attendees which have yet to confirm their attendance or marked
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
    event_id
        The unique ID of the event.
    recurrent_event_id
        If this field is set, the event is an instance of a recurring event,
        and is eqyal to the `event_id` of the parent event. Not set for
        recurring events.
    original_starts_at
        For instances of recurring events, this field represents the start
        time of the parent recurring event. It is different from `start_time`
        if this instance was moved.
    """

    # TODO: TEMPORARY EMPLOYEE - THE CALENDAR CAN BE DECOUPLED FROM THE ORGANISATION & SIMULATION
    #  CAN BE USED FOR ENTITY RESOLUTION
    #  -> Employee class superseded by Attendee(name, email)
    #  -> for work meetings name/email can be resolved via find_employee()
    #  -> otherwise, the name/email can be resolved from contacts via find_contact
    #       (can borrow AgentSandbox impl)
    #  -> we can also expose a more general entity resolver for the LLM to use
    #     if it's not clear who the entity is
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
    event_id: str | None = None
    recurrent_event_id: str | None = None
    original_starts_at: datetime.datetime | None = None

    @property
    def duration(self) -> Duration:
        """Returns the duration of an event, in minutes"""
        duration = (self.ends_at - self.starts_at).total_seconds() / 60
        return Duration(number=duration, unit=TimeUnits.Minutes)

    @field_serializer(*EMPLOYEE_FIELDS)
    def serialise_attendees(
        self, employee_list: list[Employee] | None
    ) -> list[str] | None:
        if employee_list is not None:
            employee_list = sorted(employee_list, key=lambda e: e.name)
            employee_list = [a.employee_id for a in employee_list]
            return employee_list
        return

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        data = deepcopy(data)
        for f in EMPLOYEE_FIELDS:
            if (f_val := data[f]) is not None:
                data[f] = [_get_employee_by_id(id_) for id_ in f_val]
        for f in STRUCT_FIELDS:
            if data[f] is not None and all(val is None for val in data[f].values()):
                data[f] = None
        return cls(**data)

    def __eq__(self, other: Self) -> bool:
        """Override default equality test to ensure order or attendees fields
        does not matter in comparison."""

        for f in self.model_fields:
            self_f = getattr(self, f)
            other_f = getattr(other, f)
            if f in EMPLOYEE_FIELDS:
                if any(el is None for el in (self_f, other_f)):
                    if self_f != other_f:
                        return False
                else:
                    sort_self = sorted(self_f, key=lambda x: x.name)
                    sort_other = sorted(other_f, key=lambda x: x.name)
                    if sort_self != sort_other:
                        return False
            else:
                if other_f != self_f:
                    return False
        return True

    def __str__(self) -> str:
        starts_at_str = (
            self.starts_at.strftime("%Y-%m-%d %H:%M:%S") if self.starts_at else "N/A"
        )
        ends_at_str = (
            self.ends_at.strftime("%Y-%m-%d %H:%M:%S") if self.ends_at else "N/A"
        )
        duration_str = "N/A"
        if self.starts_at and self.ends_at:
            duration = self.ends_at - self.starts_at
            hours, remainder = divmod(duration.total_seconds(), 3600)
            minutes, _ = divmod(remainder, 60)
            if hours == 0 and minutes == 0:
                duration_str = "less than a minute"
            elif hours == 0:
                duration_str = f"{int(minutes)} minutes"
            elif minutes == 0:
                duration_str = f"{int(hours)} hours"
            else:
                duration_str = f"{int(hours)} hours and {int(minutes)} minutes"
        attendees_str = (
            ", ".join([attendee.name for attendee in self.attendees])
            if self.attendees
            else "None"
        )
        if self.subject:
            if attendees_str == "None":
                display = (
                    f"'{self.subject}' "
                    f"starting at: {starts_at_str}, ending at {ends_at_str}"
                )
            else:
                display = (
                    f"'{self.subject}' with {attendees_str} "
                    f"starting at: {starts_at_str} for {duration_str}"
                )
        else:
            display = (
                f"Meeting with {attendees_str} "
                f"starting at: {starts_at_str} for {duration_str}"
            )
        if self.location is not None:
            display += f" (location: {self.location})"
        return display


def get_event_ids(
    namespace: "DatabaseNamespace | None" = None,
) -> set[EventId]:
    """Return the IDs of the events existing in the database."""
    from aspera.simulation.database_schemas import DatabaseNamespace
    from aspera.simulation.execution_context import get_current_context

    if namespace is None:
        namespace = DatabaseNamespace.USER_CALENDAR
    current_context = get_current_context()
    events = current_context.get_database(
        namespace=namespace,
    )
    return set(events["event_id"].to_list())


def expand_to_instances(event: Event) -> list[Event] | None:
    """Returns the instances of a recurring event or None if
    the event passed does not recur."""

    if event.repeats is None:
        return None
    if any((event.starts_at is None, event.ends_at is None)):
        raise EventDefinitionError(
            "Could not expand recurring event into its instances because "
            "either the event start time or the end time were not provided"
        )
    instance_start_times = _repetition_schedule(
        when=event.starts_at.time(),
        spec=event.repeats,
        start_date=event.starts_at.date(),
    )
    duration = event.ends_at - event.starts_at
    instances = []
    for instance_start_time in instance_start_times:
        this_instance = deepcopy(event)
        this_instance.event_id = str(uuid.uuid4())
        this_instance.repeats = None
        this_instance.starts_at = instance_start_time
        this_instance.ends_at = instance_start_time + duration
        this_instance.recurrent_event_id = event.event_id
        this_instance.original_starts_at = event.starts_at
        instances.append(this_instance)
    return instances


def add_event(event: Event) -> EventId:
    """Add an event to the user's calendar.

    Notes
    -----
    1. This API manages the user calendar, so it is not necessary
    to include the user profile in attendees fields - this is handled
    by the backend.
    2. If the user does not specify the end time of the event, the
    backend will automatically determine a suitable event duration. Hence,
    do not make assumptions on when a particular event should end.
    """

    from aspera.simulation.database_schemas import DatabaseNamespace
    from aspera.simulation.execution_context import get_current_context

    validate_starts_at(event)

    current_context = get_current_context()
    existing_ids = get_event_ids()
    if event.event_id is None:
        # assume default duration if end time not specified
        if event.ends_at is None:
            logger.warning(
                "Event end time not specified, default duration will be assumed"
            )
            try:
                ends_at = event.starts_at + datetime.timedelta(
                    minutes=DEFAULT_EVENT_DURATION_MINUTES
                )
            except TypeError:
                raise TypeError("Could not schedule event without start time")
            event.ends_at = ends_at
        event.event_id = str(uuid.uuid4())
    # the event exists in the DB so the call is made to update an existing event
    # remove the event and possibly any linked recurring instances from the database
    # if it exists - this means the model updated the database
    if event.event_id in existing_ids:
        delete_event(event)
    # possibly expand a recurring event into its instances
    maybe_recurrent_instances = expand_to_instances(event)
    new_records = [event.model_dump()]
    if maybe_recurrent_instances is not None:
        for instance in maybe_recurrent_instances:
            new_records.append(instance.model_dump())
    current_context.add_to_database(
        namespace=DatabaseNamespace.USER_CALENDAR,
        rows=new_records,
    )
    return event.event_id


def validate_starts_at(event):
    if event.repeats is not None and event.starts_at is None:
        raise EventDefinitionError(
            "Start time is required to expand a recurring event into instances."
        )


def _find_event_helper(attendees: list[Employee] | None, subject: str | None):
    """Helper function for finding both upcoming and past events in
    the user calendar."""

    from aspera.simulation.database_schemas import DatabaseNamespace
    from aspera.simulation.execution_context import get_current_context

    current_context = get_current_context()
    # only the parent recurring events are returned
    filter_recurring_instances = [
        ("recurrent_event_id", None, exact_match_filter_dataframe),
    ]
    if all((attendees is None, subject is None)):
        raw_records = filter_dataframe(
            dataframe=current_context.get_database(
                namespace=DatabaseNamespace.USER_CALENDAR,
            ),
            filter_criteria=filter_recurring_instances,
        ).to_dicts()
    else:
        # the semantics of attendees = [] is events with
        # no attendees
        if attendees is None:
            attendees = NOT_GIVEN
        if attendees is not NOT_GIVEN:
            attendees = [a.employee_id for a in sorted(attendees, key=lambda x: x.name)]
        subject = subject or NOT_GIVEN
        raw_records = filter_dataframe(
            dataframe=current_context.get_database(
                namespace=DatabaseNamespace.USER_CALENDAR
            ),
            filter_criteria=[
                ("attendees", attendees, exact_match_filter_dataframe),
                (
                    "subject",
                    subject,
                    functools.partial(fuzzy_match_filter_dataframe, threshold=90),
                ),
            ]
            + filter_recurring_instances,
        ).to_dicts()
    events = [Event.from_dict(record) for record in raw_records]
    events.sort(key=lambda x: x.starts_at)
    return events


def find_events(
    attendees: list[Employee] | None = None, subject: str | None = None
) -> list[Event]:
    """Search an upcoming event by specific attendees or title in the user's calendar.
    Call with no parameters will return all the events in the user's calendar.

    Notes
    -----
    1. For recurring events, only the parent events are returned. To access the event
    instances, use the `get_event_instances`.

    # TODO: SHOULD RETURN EVENT EXCEPTIONS (IE RECURRING INSTANCES THAT HAVE BEEN CHANGED)
    """

    events = _find_event_helper(attendees, subject)
    # NB: this also filters recurrences that have started in the past
    return [e for e in events if e.starts_at >= now_()]


def find_past_events(
    attendees: list[Employee] | None = None, subject: str | None = None
) -> list[Event]:
    """Endpoint for finding events which have already occurred **in the user's calendar.**
    When called with no parameters, all the past events in the user's calendar are returned.
    """
    events = _find_event_helper(attendees, subject)
    return [e for e in events if e.starts_at < now_()]


def delete_event(event: Event):
    """Delete an event from the user calendar."""

    from aspera.simulation.database_schemas import DatabaseNamespace
    from aspera.simulation.execution_context import get_current_context

    context = get_current_context()
    if event.event_id is None:
        raise SearchError(f"Not in database: {event} ")
    event_predicate = pl.col("event_id") == event.event_id
    context.remove_from_database(
        namespace=DatabaseNamespace.USER_CALENDAR,
        predicate=event_predicate,
    )
    # remove any recurrent instances if found
    try:
        recurrent_pred = (pl.col("recurrent_event_id") == event.event_id) & (
            pl.col("recurrent_event_id").is_not_null()
        )
        context.remove_from_database(
            namespace=DatabaseNamespace.USER_CALENDAR,
            predicate=recurrent_pred,
        )
    except NoDataError:
        pass


def get_event_instances(event: Event) -> list[Event]:
    """Return the instances of a recurring event from the
    underlying calendar database.

    Parameters
    ----------
    event
        An existing parent recurring event to be expanded into instances.

    Raises
    ------
    SearchError if `event` is not in the calendar.
    """

    from aspera.simulation.database_schemas import DatabaseNamespace
    from aspera.simulation.execution_context import get_current_context

    existing_event_ids = get_event_ids()
    if event.event_id not in existing_event_ids:
        raise SearchError(
            "The event you are looking for is not in the calendar. "
            "This function should only be called with existing events."
        )
    parent_event_id = event.event_id
    recurring_instances_filter = (
        "recurrent_event_id",
        parent_event_id,
        exact_match_filter_dataframe,
    )
    current_context = get_current_context()
    raw_records = filter_dataframe(
        dataframe=current_context.get_database(
            namespace=DatabaseNamespace.USER_CALENDAR
        ),
        filter_criteria=[recurring_instances_filter],
    ).to_dicts()
    events = [Event.from_dict(record) for record in raw_records]
    events.sort(key=lambda x: x.starts_at)
    return events


def get_event_by_id(event_id: str) -> Event:
    """Retrieve the event with `event_id` from the calendar.

    Raises
    ------
    SearchError if `event_id` is not in the calendar.
    """

    from aspera.simulation.database_schemas import DatabaseNamespace
    from aspera.simulation.execution_context import get_current_context

    event_ids = get_event_ids()
    if event_id not in event_ids:
        raise SearchError(f"No event with {event_id} was found in the calendar.")
    current_context = get_current_context()
    raw_records = filter_dataframe(
        dataframe=current_context.get_database(
            namespace=DatabaseNamespace.USER_CALENDAR
        ),
        filter_criteria=[
            ("event_id", event_id, exact_match_filter_dataframe),
        ],
    ).to_dicts()
    events = [Event.from_dict(record) for record in raw_records]
    assert len(events) == 1
    return events[0]


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

    if calendar_key.lower() not in {"work", "default"}:
        raise ValueError("Only work and default calendar are supported.")
    return CalendarSearchSettings(
        earliest_free_slot_start=parse_time_string(TimeExpressions["StartOfWorkDay"]),
        latest_free_slot_finish=parse_time_string(TimeExpressions["EndOfWorkDay"]),
    )


def find_available_slots(
    events: list[Event],
    search_settings: CalendarSearchSettings | None = None,
    date: datetime.date | None = None,
) -> list[TimeInterval]:
    """Return a list of time slots when no events are scheduled.

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

    def generate_daily_slots(
        start: datetime.date, end: datetime.date, settings: CalendarSearchSettings
    ):
        """Generate slots for each day between `start` and `end`."""
        current_date = start
        while current_date <= end:
            day_start = datetime.datetime.combine(
                current_date, settings.earliest_free_slot_start
            )
            day_end = datetime.datetime.combine(
                current_date, settings.latest_free_slot_finish
            )
            yield day_start, day_end
            current_date += datetime.timedelta(days=1)

    def return_default_slots(
        date: datetime.date | None, search_settings: CalendarSearchSettings
    ):
        """If there are no events, a single slot determined by `search_settings` is returned
        for each date from the calling time till the next Friday, unless a `date` is specified.
        """
        today = now_().date()
        end_date = get_next_dow("Friday")
        if date is not None:
            return [
                TimeInterval(
                    start=datetime.datetime.combine(
                        date, search_settings.earliest_free_slot_start
                    ),
                    end=datetime.datetime.combine(
                        date, search_settings.latest_free_slot_finish
                    ),
                )
            ]
        return [
            TimeInterval(start=start, end=end)
            for start, end in generate_daily_slots(today, end_date, search_settings)
        ]

    def determine_availability_window(
        events: list[Event], search_settings: CalendarSearchSettings
    ) -> tuple[datetime.datetime, datetime.datetime]:
        """Determine the window for which availability is checked given the events."""
        earliest_start = min(
            (e.starts_at for e in events if e.starts_at), default=now_()
        )
        latest_end = max((e.ends_at for e in events if e.ends_at), default=now_())
        search_start = datetime.datetime.combine(
            earliest_start.date(), search_settings.earliest_free_slot_start
        )
        search_end = datetime.datetime.combine(
            latest_end.date(), search_settings.latest_free_slot_finish
        )
        return search_end, search_start

    def no_events_on_date(date: datetime.date, events: list[Event]) -> bool:
        for event in events:
            interval = TimeInterval(event.starts_at, event.ends_at)
            if interval.contains_date(date):
                return False
        return True

    if search_settings is None:
        search_settings = get_search_settings("default")

    # if the user marked themselves as free, return the slot
    events = [e for e in events if e.show_as_status != ShowAsStatus.Free]
    if not events or (
        bool(events) and date is not None and no_events_on_date(date, events)
    ):
        return return_default_slots(date, search_settings)

    search_end, search_start = determine_availability_window(events, search_settings)
    if (
        not events
        and date is not None
        and (date < search_start.date() or date > search_end.date())
    ):
        return return_default_slots(date=date, search_settings=search_settings)

    events.sort(key=lambda e: e.starts_at or datetime.datetime.min)
    available_slots = []

    # Determine the available slots for each day in the availability window
    for day_start, day_end in generate_daily_slots(
        search_start.date(), search_end.date(), search_settings
    ):
        if date is not None and day_start.date() != date:
            continue
        daily_events = [
            (e.starts_at, e.ends_at)
            for e in events
            if e.starts_at.date() <= day_start.date() <= e.ends_at.date()
        ]
        daily_events.sort()
        # Process slots within the current day
        current_day_start = max(day_start, search_start)
        for event_start, event_end in daily_events:
            if current_day_start < event_start:
                available_slots.append(
                    TimeInterval(start=current_day_start, end=event_start)
                )
            current_day_start = max(current_day_start, event_end)
        if current_day_start < day_end:
            available_slots.append(TimeInterval(start=current_day_start, end=day_end))
    available_slots.sort(key=lambda e: e.start or datetime.datetime.min)
    return available_slots


def get_calendar(employee: Employee) -> list[Event]:
    """Use this function to check the calendar of another team member.

    Notes
    -----
    1. This API does not return events in the user calendar. Use `find_events` instead.
    2. When querying for events in `employees` calendar with certain attendees, the calendar owner *should not* include the calendar's owner (e.g., if looking up a meeting between Mark and his manager in manager's calendar, you will only find Mark's profile in the attendees.
    """

    from aspera.simulation.database_schemas import DatabaseNamespace
    from aspera.simulation.execution_context import get_current_context

    context = get_current_context()
    all_shared_calendars = context.get_database(
        namespace=DatabaseNamespace.SHARED_CALENDARS
    )
    raw_records = filter_dataframe(
        dataframe=all_shared_calendars,
        filter_criteria=[
            ("calendar_id", employee.employee_id, exact_match_filter_dataframe),
        ],
    ).to_dicts()
    for r in raw_records:
        r.pop("calendar_id")
    events = [Event.from_dict(record) for record in raw_records]
    return events


def share_calendar(recipients: list[Employee]):
    """Share user's calendar with specified recipients."""

    from aspera.simulation.database_schemas import DatabaseNamespace
    from aspera.simulation.execution_context import get_current_context

    employee_ids = [e.employee_id for e in recipients]
    employee_ids.sort()
    context = get_current_context()
    context.add_to_database(
        namespace=DatabaseNamespace.USER_METADATA,
        rows=[{"calendar_visible_to": employee_ids}],
    )


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

    person_reference = "your calendar" if name is None else f"{name}'s calendar"

    if not events:
        return f"There are no events in {person_reference}."
    return f"There are {len(events)} events in {person_reference}. Here are the details of the first: {events[0]}"  # noqa


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
    if not events:
        return "There are no events that satisfy these criteria"
    events = sorted(events, key=lambda e: e.starts_at)
    events_str = [str(e) for e in events]
    if len(events_str) == 1:
        return events_str[0]
    events_str = [f"{i}. {e}" for i, e in enumerate(events_str)]
    return "\n".join(events_str)
