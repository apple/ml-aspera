#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
"""A light wrapper around the `datetime` library, containing utilities
for parsing complex time strings into `datetime` objects, scheduling helpers and more.
Always needed when time is involved in any shape or form."""

import datetime
from collections.abc import Generator
from dataclasses import dataclass
from enum import Enum, StrEnum, auto
from itertools import islice
from typing import Literal, NamedTuple, Self

from dateutil import rrule
from dateutil.relativedelta import relativedelta
from dateutil.rrule import rruleset

from aspera.apps_implementation.exceptions import ParseError

MAX_EVENT_RECURRENCES = 23

TimeExpressions = Enum(
    "TimeExpressions",
    [
        "Afternoon",
        "Breakfast",
        "Brunch",
        "Dinner",
        "StartOfWorkDay",
        "EndOfWorkDay",
        "Evening",
        "Night",
        "LateAfternoon",
        "LateMorning",
        "Lunch",
        "Morning",
        "Noon",
        "Midnight",
    ],
)

DateRanges = Enum(
    "DateRanges",
    ["ThisWeekend", "NextWeek", "ThisMonth", "NextMonth"],
)


DateExpressions = Enum(
    "DateExpressions",
    ["Today", "Tomorrow", "Yesterday", "FirstDayNextYear", "ChristmasDay", "LastMonth"],
)
"""Expressions which can be resolved to a given date, relative to the current date.

Notes
-----
    1. LastMonth is resolved to the last day of the previous month.
"""

TimeUnits = Enum("TimeUnits", ["Hours", "Minutes", "Days", "Months"])
"""Enumerations used for parsing durations to specific time units"""

weekdays = Literal[
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
]


class Duration(NamedTuple):
    """A time unit, for representing event durations.

    Parameters
    ----------
    number
        A float or integer representing the length of time.
    unit
        The unit of time used to measure the duration.
    """

    number: int | float
    unit: TimeUnits

    def to_minutes(self) -> float:
        """Convert the Duration to minutes."""
        if self.unit == TimeUnits.Hours:
            return float(self.number * 60)
        elif self.unit == TimeUnits.Minutes:
            return float(self.number)
        elif self.unit == TimeUnits.Days:
            return float(self.number * 24 * 60)
        elif self.unit == TimeUnits.Months:
            raise TypeError("Cannot convert variable durations to minutes!")
        else:
            raise ValueError(f"Unsupported time unit: {self.unit}")

    def __le__(self, other: Self) -> bool:
        return self.to_minutes() <= other.to_minutes()

    def __lt__(self, other: Self) -> bool:
        return self.to_minutes() < other.to_minutes()

    def __ge__(self, other: Self) -> bool:
        return self.to_minutes() >= other.to_minutes()

    def __gt__(self, other: Self) -> bool:
        return self.to_minutes() > other.to_minutes()

    def __eq__(self, other: Self) -> bool:
        return self.to_minutes() == other.to_minutes()


def cast_to_timedelta(duration: Duration) -> datetime.timedelta:
    if duration.unit == TimeUnits.Hours:
        return datetime.timedelta(hours=duration.number)
    elif duration.unit == TimeUnits.Minutes:
        return datetime.timedelta(minutes=duration.number)
    elif duration.unit == TimeUnits.Days:
        return datetime.timedelta(days=duration.number)
    elif duration.unit == TimeUnits.Months:
        # Assuming 1 month = 30 days
        raise TypeError(
            "Cannot cast duration to timedelta for months: "
            "the number of days is variable."
        )
    else:
        raise ValueError(f"Unsupported time unit: {duration.unit}")


class TimeInterval(NamedTuple):
    """Represents the time interval between two specific time points."""

    start: datetime.datetime
    end: datetime.datetime

    def contains(self, dt: datetime.datetime) -> bool:
        """Check if a given datetime is contained within this time interval."""
        return self.start <= dt <= self.end

    def contains_date(self, d: datetime.date) -> bool:
        """Check if a given date is contained within this time interval."""
        return self.start.date() <= d <= self.end.date()

    def includes(self, other: Self) -> bool:
        """Check if `other` is included in this time interval."""
        return self.start <= other.start and self.end >= other.end


def convert(interval: TimeInterval, unit: TimeUnits) -> Duration:
    """Convert the duration of a time interval to a given time unit."""
    duration_in_seconds = (interval.end - interval.start).total_seconds()

    if unit == TimeUnits.Hours:
        number = duration_in_seconds / 3600
    elif unit == TimeUnits.Minutes:
        number = duration_in_seconds / 60
    elif unit == TimeUnits.Days:
        number = duration_in_seconds / 86400
    else:
        raise ValueError(f"Unsupported time unit: {unit}")

    return Duration(number=number, unit=unit)


class DateRange(NamedTuple):
    """Represents a duration between two specific dates."""

    start: datetime.date
    end: datetime.date


def now_() -> datetime.datetime:
    """Return the current date and time on the user's device."""
    return datetime.datetime(year=2024, day=25, month=6, hour=9, minute=6)  # Tuesday


def get_weekday() -> weekdays:
    """Get the current weekday, as a human-readable string."""
    return "Tuesday"


def this_week_dates() -> list[datetime.date]:
    """The actual dates corresponding to days in the current week,
    including today and past days this week."""
    today = now_().date()
    start_of_week = today - datetime.timedelta(days=today.weekday())
    return [start_of_week + datetime.timedelta(days=i) for i in range(7)]


def get_weekday_ordinal() -> int:
    """Get an integer in the range [0, 6] representing the
    current weekday."""
    return now_().weekday()


def parse_time_string(time_expr: TimeExpressions) -> datetime.time:
    """Resolve a string representing a time of the day to a specific time
    on the user device."""
    time_mappings = {
        TimeExpressions.Afternoon: (14, 19),
        TimeExpressions.Breakfast: (7, 23),
        TimeExpressions.Brunch: (11, 1),
        TimeExpressions.Dinner: (19, 29),
        TimeExpressions.StartOfWorkDay: (9, 6),
        TimeExpressions.EndOfWorkDay: (17, 10),
        TimeExpressions.Evening: (19, 23),
        TimeExpressions.Night: (22, 3),
        TimeExpressions.LateAfternoon: (17, 1),
        TimeExpressions.LateMorning: (10, 6),
        TimeExpressions.Lunch: (12, 17),
        TimeExpressions.Morning: (9, 5),
        TimeExpressions.Noon: (12, 15),
        TimeExpressions.Midnight: (0, 0),
    }
    try:
        hour, minute = time_mappings[time_expr]
    except KeyError:
        raise ParseError("Unknown time expression {}".format(time_expr))
    return datetime.time(hour=hour, minute=minute)


def time_by_hm(hour: int, minute: int, am_or_pm: str) -> datetime.time:
    """Create an object representing a specific time"""
    if am_or_pm.lower() == "pm" and hour < 12:
        hour += 12
    elif am_or_pm.lower() == "am" and hour == 12:
        hour = 0
    return datetime.time(hour, minute)


def date_by_mdy(
    month: int | None = None, day: int | None = None, year: int | None = None
) -> datetime.date:
    """Create an object representing a day in a given month and year. If any values are not
    provided,`now_()` is used to infer the missing values"""
    today = now_().date()
    if month is None:
        month = today.month
    if day is None:
        day = today.day
    if year is None:
        year = today.year
    return datetime.date(year=year, month=month, day=day)


def get_next_dow(
    day_of_week: weekdays, after: datetime.date | None = None
) -> datetime.date:
    """Return the calendar date corresponding to the next `day_of_week`, relative to
    the current date.

    Parameters
    ----------
    after
        If specified, the next `day_of_week` after the specified date is returned.
    """
    today = now_().date()
    if after:
        today = after
    weekdays = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    days_ahead = (list(weekdays).index(day_of_week) - today.weekday() + 7) % 7
    if days_ahead == 0:
        days_ahead = 7
    return today + datetime.timedelta(days=days_ahead)


def get_prev_dow(
    day_of_week: weekdays, before: datetime.date | None = None
) -> datetime.date:
    """Return the calendar date corresponding to the previous `day_of_week`, relative to
    the current date.

    Parameters
    ----------
    before
        If specified, the previous `day_of_week` before the specified date is returned.
    """

    today = now_().date()
    if before:
        today = before

    weekdays = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]

    day_index = weekdays.index(day_of_week)
    days_ago = (today.weekday() - day_index + 7) % 7

    if days_ago == 0:
        days_ago = 7

    return today - datetime.timedelta(days=days_ago)


def parse_duration_to_calendar(
    duration: Literal["NextWeek", "ThisMonth", "NextMonth"],
    after: datetime.date | None = None,
) -> list[list[datetime.date]]:
    """Convert standard durations to a list of lists of seven elements,
    where each list represents a week and each entry is the date corresponding
    to a particular day. The first day of the week is a Monday.

    Parameters
    ----------
    duration
        A string representing the duration to convert.
    after
        If specified, the calendar span returned is relative to the given date (ie
        the first date return is the date of the next Monday after the current date)

    Notes
    -----
    1. The `NextMonth` and "ThisMonth" calendars contain full weeks, including dates outside
     the current/next month (for example, next month calendar contains possibly the end
     of the current month and start of the month after next).
    2. The `NextWeek` parse contains a single element which is a list of seven objects
    representing the date for next week.
    3. A full calendar is returned for "ThisMonth" dates, including past dates. Appropriately
    filter the calendar when necessary for scheduling purposes.
    """
    today = now_().date()
    if after:
        today = after

    def get_week_dates(start_date: datetime.date) -> list[datetime.date]:
        return [start_date + datetime.timedelta(days=i) for i in range(7)]

    calendar = []

    if duration == "NextWeek":
        start_date = today + datetime.timedelta(days=(7 - today.weekday()))
        return [get_week_dates(start_date)]

    elif duration == "ThisMonth":
        start_date = today.replace(day=1)
        end_date = start_date.replace(
            month=start_date.month + 1, day=1
        ) - datetime.timedelta(days=1)
    elif duration == "NextMonth":
        start_date = (today.replace(day=1) + datetime.timedelta(days=32)).replace(day=1)
        end_date = start_date.replace(
            month=start_date.month + 1, day=1
        ) - datetime.timedelta(days=1)

    # Pad the first week
    first_week = [
        (
            (start_date - datetime.timedelta(days=start_date.weekday() - i))
            if i < start_date.weekday()
            else (start_date + datetime.timedelta(days=i - start_date.weekday()))
        )
        for i in range(7)
    ]

    calendar.append(first_week)

    current_date = first_week[-1] + datetime.timedelta(days=1)
    while current_date <= end_date:
        week = []
        for i in range(7):
            if current_date <= end_date:
                week.append(current_date)
                current_date += datetime.timedelta(days=1)
            else:
                week.append(current_date)
                current_date += datetime.timedelta(days=1)
        calendar.append(week)

    return calendar


def parse_durations_to_date_interval(
    expr: DateRanges, after: datetime.date | None = None
) -> DateRange:
    """Parse a duration to an interval.

    Parameters
    ----------
    after
        If provided the start of the interval returned will occur after `after`.

    Notes
    -----
    1. The first day of the weekend is assumed to be Saturday, not Friday.
    """
    today = now_().date()
    if after:
        today = after

    if expr == DateRanges.ThisWeekend:
        start = today + datetime.timedelta((5 - today.weekday()) % 7)
        end = start + datetime.timedelta(days=1)
    elif expr == DateRanges.NextWeek:
        start = today + datetime.timedelta(days=(7 - today.weekday()))
        end = start + datetime.timedelta(days=6)
    elif expr == DateRanges.ThisMonth:
        start = today.replace(day=1)
        end = start.replace(month=start.month + 1, day=1) - datetime.timedelta(days=1)
    elif expr == DateRanges.NextMonth:
        start = (today.replace(day=1) + datetime.timedelta(days=32)).replace(day=1)
        if start.month == 12:
            end = start.replace(
                year=start.year + 1, month=1, day=1
            ) - datetime.timedelta(days=1)
        else:
            end = start.replace(month=start.month + 1, day=1) - datetime.timedelta(
                days=1
            )
    else:
        raise ParseError(f"Invalid date expression: {expr}")
    return DateRange(start=start, end=end)


def parse_date_string(date_expr: DateExpressions) -> datetime.date:
    """Resolve date expressions to `datetime`.

    Notes
    -----
    LastMonth is resolved to the last day of the previous month.
    """
    today = now_().date()
    date_mappings = {
        DateExpressions.Today: today,
        DateExpressions.Tomorrow: today + datetime.timedelta(days=1),
        DateExpressions.Yesterday: today - datetime.timedelta(days=1),
        DateExpressions.FirstDayNextYear: datetime.date(today.year + 1, 1, 1),
        DateExpressions.ChristmasDay: datetime.date(today.year, 12, 25),
        DateExpressions.LastMonth: (today.replace(day=1) - datetime.timedelta(days=1)),
    }
    try:
        return date_mappings[date_expr]
    except KeyError:
        raise ParseError(f"Invalid date expression: {date_expr}")


DateTimeClauseOperators = Enum("DateTimeClauseOperators", ["add", "subtract"])
"""Operators for offsetting durations"""


def sum_time_units(time_units: list[Duration]) -> Duration:
    """Sum the duration of all time units.

    Returns
    ------
    duration
        An object representing the total duration of all time units.
        The `unit` of the result is the largest unit such that `number`
        is closest to 1. For example, durations summing to 130 minutes
        will be summed to 2.16 hours, durations summing to 1440 minutes
        will be summed to 1 day etc.
    """
    # Conversion factors to minutes
    conversion_to_minutes = {
        TimeUnits.Hours: 60,
        TimeUnits.Minutes: 1,
        TimeUnits.Days: 1440,  # 24 * 60
    }

    # Sum all durations in minutes
    total_minutes = sum(t.number * conversion_to_minutes[t.unit] for t in time_units)

    # Choose the largest unit for the result
    if total_minutes >= 1440:
        unit = TimeUnits.Days
        number = total_minutes / 1440
    elif total_minutes >= 60:
        unit = TimeUnits.Hours
        number = total_minutes / 60
    else:
        unit = TimeUnits.Minutes
        number = total_minutes

    return Duration(number=number, unit=unit)


class ComparisonResult(Enum):

    GREATER: str = "Greater"
    SMALLER: str = "Smaller"
    EQUAL: str = "Equal"


def compare_with_fixed_duration(
    interval: TimeInterval, duration: Duration
) -> ComparisonResult:
    """Compare a given interval with a fixed duration."""
    interval_duration = convert(interval, duration.unit)

    if interval_duration.number > duration.number:
        return ComparisonResult.GREATER
    elif interval_duration.number < duration.number:
        return ComparisonResult.SMALLER
    else:
        return ComparisonResult.EQUAL


def modify(
    datetime_to_change: datetime.datetime,
    duration: Duration,
    *,
    operator: DateTimeClauseOperators,
) -> datetime.datetime:
    """Offset `datetime_to_change` by duration according to the given `operator`."""

    if duration.unit == TimeUnits.Hours:
        delta = datetime.timedelta(hours=duration.number)
    elif duration.unit == TimeUnits.Minutes:
        delta = datetime.timedelta(minutes=duration.number)
    elif duration.unit == TimeUnits.Days:
        delta = datetime.timedelta(days=duration.number)
    elif duration.unit == TimeUnits.Months:
        delta = relativedelta(months=duration.number)
    else:
        raise ValueError(f"Unsupported time unit: {duration.unit}")

    if operator == DateTimeClauseOperators.add:
        return datetime_to_change + delta
    elif operator == DateTimeClauseOperators.subtract:
        return datetime_to_change - delta
    else:
        raise ValueError(f"Unsupported operator: {operator}")


def combine(date: datetime.date, time: datetime.time) -> datetime.datetime:
    """Combine a date and time into a single object representing a given moment
    in time."""
    return datetime.datetime.combine(date, time)


def intervals_overlap(
    interval_1: TimeInterval,
    interval_2: TimeInterval,
    min_duration: Duration = Duration(1, TimeUnits["Minutes"]),
) -> bool:
    """Check if intervals_1 and intervals_2 overlap for at least `min_duration`.
    Returns False if the two intervals are disjoint or overlap less than `min_duration`.
    """
    # Calculate the overlap between the intervals
    latest_start = max(interval_1.start, interval_2.start)
    earliest_end = min(interval_1.end, interval_2.end)
    overlap = (earliest_end - latest_start).total_seconds()

    # Convert min_duration to seconds
    if min_duration.unit == TimeUnits.Hours:
        min_overlap_seconds = min_duration.number * 3600
    elif min_duration.unit == TimeUnits.Minutes:
        min_overlap_seconds = min_duration.number * 60
    elif min_duration.unit == TimeUnits.Days:
        min_overlap_seconds = min_duration.number * 86400
    else:
        raise ValueError(f"Unsupported time unit: {min_duration.unit}")
    # Check if the overlap duration is at least the minimum duration
    return overlap >= min_overlap_seconds


def replace(
    date: datetime.date,
    month: int | None = None,
    day: int | None = None,
    year: int | None = None,
) -> datetime.date:
    """Return a new `datetime.date` object whose `month`, `day`, and `year` are updated
    to represent the input values. Most useful for date time arithmetic operations
    (eg to find the dates in the past such as first day of last month given the
    current date etc).

    Raises
    ------
    ValueError if the specified `month`, `day`, and `year` are invalid given `date`.
    """
    new_year = year if year is not None else date.year
    new_month = month if month is not None else date.month
    new_day = day if day is not None else date.day
    # nb: ValueError will be raised internally by the datetime module
    return datetime.date(new_year, new_month, new_day)


class EventFrequency(StrEnum):
    DAILY = auto()
    WEEKLY = auto()
    MONTHLY = auto()
    YEARLY = auto()


@dataclass
class RepetitionSpec:
    """
    Represents a recurrence rule for defining recurring events.

    Parameters
    ----------
    frequency
        How often the event occurs.
    period
        Interval between recurrences. For example, when using WEEKLY, a period of 2 means once every
        two weeks, but with HOURLY, it means once every two hours.
    recurs_until
        The last recurrence in the rule is the greatest datetime that is less than or equal
        to the value specified in the until parameter.
    max_repetitions
        Number of occurrences in the recurrence. Must not be set if recurs_until is set.
    which_weekday
        Days of the week on which the event occurs (0 - indexed)
    which_month_day
        Days of the month on which the event occurs (1-indexed).
    which_year_month
        Months of the year on which the event occurs (1 for January, 12 for December).
    bysetpos
        Specific positions within a set. Negative values count from the end
        (e.g., -1 for the last occurrence).Each given integer will specify an occurrence number,
         corresponding to the nth occurrence of the rule inside the frequency period.
         For example, a bysetpos of -1 if combined with a MONTHLY frequency, and a which_weekday
          of (0, 1, 2, 3, 4), will result in the last work day of every month.
    exclude_occurrence
        If specified, the event will not occur on the specified datetimes.
    occurrence_on_date
        If specified, the event will also occur on this date.

    Notes
    -----
    The start date and time for the first event in the series is inherited from the corresponding
     properties of the event on which the spec is set.
    """

    frequency: EventFrequency
    period: int = 1
    recurs_until: datetime.date | datetime.datetime | None = None
    max_repetitions: int | None = None
    which_weekday: list[int] | None = None
    which_month_day: list[int] | None = None
    which_year_month: list[int] | None = None
    bysetpos: list[int] | None = None
    exclude_occurrence: list[datetime.datetime] | None = None
    occurrence_on_date: datetime.datetime | None = None

    @property
    def finite(self) -> bool:
        return any([self.max_repetitions is not None, self.recurs_until is not None])

    def generate_occurrences(
        self,
        start_date: datetime.date | None = None,
        start_time: datetime.time | None = None,
    ) -> Generator[datetime.datetime, None, None]:
        """
        Generates occurrences based on the recurrence rule starting from the specified start date.

        Parameters
        ----------
        start_date
            The starting date of the recurrence.
        start_time
            The starting time of the recurrence.

        Returns
        -------
        An generator of datetime objects.
        """

        if self.max_repetitions is not None and self.recurs_until:
            raise ValueError("Both 'count' and 'until' cannot be set. Choose one.")

        if not start_date:
            start_date = now_().date()

        if not start_time:
            start_time = now_().time()
        if isinstance(self.recurs_until, datetime.date):
            self.recurs_until = datetime.datetime.combine(self.recurs_until, start_time)
        start_datetime = datetime.datetime.combine(start_date, start_time)

        freq_map = {
            EventFrequency.DAILY: rrule.DAILY,
            EventFrequency.WEEKLY: rrule.WEEKLY,
            EventFrequency.MONTHLY: rrule.MONTHLY,
            EventFrequency.YEARLY: rrule.YEARLY,
        }

        rule_params = {
            "freq": freq_map[self.frequency],
            "interval": self.period,
            "dtstart": start_datetime,
            "until": self.recurs_until,
            "count": self.max_repetitions,
            "byweekday": self.which_weekday,
            "bymonthday": self.which_month_day,
            "bymonth": self.which_year_month,
            "bysetpos": self.bysetpos,
        }
        rule = rrule.rrule(**{k: v for k, v in rule_params.items() if v is not None})
        set_ = rruleset()
        set_.rrule(rule)
        if self.exclude_occurrence is not None:
            for date in self.exclude_occurrence:
                set_.exdate(date)
        if self.occurrence_on_date is not None:
            set_.exdate(self.occurrence_on_date)

        return (occurrence for occurrence in set_)


def _repetition_schedule(
    when: datetime.time,
    spec: RepetitionSpec,
    start_date: datetime.date | None = None,
) -> list[datetime.datetime]:
    """
    Create a recurrence schedule for a meeting, reminder or any other task that can be set to recur.

    Parameters
    ----------
    when
        The time at which an event should occur.
    spec
        A specification of the rule according to which an event recurs.
    start_date
        The first day the event should occur. If not set, will default to today.
    """

    if not start_date:
        start_date = now_().date()

    occurrences = spec.generate_occurrences(start_date, when)
    if not spec.finite:
        return list(islice(occurrences, MAX_EVENT_RECURRENCES))
    return list(occurrences)
