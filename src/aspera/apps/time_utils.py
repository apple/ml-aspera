"""A light wrapper around the `datetime` library, containing utilities
for parsing complex time strings into `datetime` objects, scheduling helpers and more.
Always needed when time is involved in any shape or form, current time on the user
device must be parsed using now_()."""

import datetime
from enum import Enum, auto
from typing import Literal, NamedTuple, Self

from pydantic import BaseModel

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
DateExpressions.__doc__ = """Expressions which can be resolved to a given date, relative to the current date.

Notes
-----
    1. LastMonth is resolved to the last day of the previous month.
"""  # noqa

TimeUnits = Enum("TimeUnits", ["Hours", "Minutes", "Days", "Months"])
TimeUnits.__doc__ = """Enumerations used for parsing durations to specific time units"""

weekdays = Literal[
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
]


class Duration(NamedTuple):
    """A duration.

    Parameters
    ----------
    number
        A float or integer representing the length of time.
    unit
        The unit of time used to measure the duration.
    """

    number: int | float
    unit: TimeUnits


class TimeInterval(NamedTuple):
    """Represents the time interval between two specific time points."""

    start: datetime.datetime
    end: datetime.datetime

    def contains(self, dt: datetime.datetime) -> bool:
        """Check if a give datetime is contained within this time interval."""

    def contains_date(self, dt: datetime.date) -> bool:
        """Check if a given date is contained within this time interval."""

    def includes(self, other: Self) -> bool:
        """Check if `other` is included in this time interval."""


def convert(interval: TimeInterval, unit: TimeUnits) -> Duration:
    """Convert the duration of a time interval to a given time unit."""


class DateRange(NamedTuple):
    """Represents a duration between two specific dates."""

    start: datetime.date
    end: datetime.date


def now_() -> datetime.datetime:
    """Return the current date and time on the user's device."""
    return datetime.datetime(year=2024, day=25, month=6, hour=9, minute=6)  # Tuesday


def get_weekday() -> weekdays:
    """Get the current weekday, as a human-readable string."""


def this_week_dates() -> list[datetime.date]:
    """The actual dates corresponding to days in the current week,
    including today and past days this week."""


def get_weekday_ordinal() -> int:
    """Get an integer in the range [0, 6] representing the
    current weekday."""


def parse_time_string(time_expr: TimeExpressions) -> datetime.time:
    """Resolve a string representing a time of the day to a specific time
    on the user device."""


def time_by_hm(hour: int, minute: int, am_or_pm: str) -> datetime.time:
    """Create an object representing a specific time"""


def date_by_mdy(
    month: int | None = None, day: int | None = None, year: int | None = None
) -> datetime.date:
    """Create an object representing a day in a given month and year. If any values are not
    provided,`now_()` is used to infer the missing values"""


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


def parse_date_string(date_expr: DateExpressions) -> datetime.date:
    """Resolve date expressions to `datetime`.

    Notes
    -----
    LastMonth is resolved to the last day of the previous month.
    """


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
        will be summed to 1 day, etc.
    """


class ComparisonResult(Enum):

    GREATER: str = "Greater"
    SMALLER: str = "Smaller"
    EQUAL: str = "Equal"


def compare_with_fixed_duration(
    interval: TimeInterval, duration: Duration
) -> ComparisonResult:
    """Compare a given interval with a fixed duration."""


def modify(
    datetime_to_change: datetime.datetime,
    duration: Duration,
    *,
    operator: DateTimeClauseOperators,
) -> datetime.datetime:
    """Offset `datetime_to_change` by duration according to the given `operator`."""


def combine(date: datetime.date, time: datetime.time) -> datetime.datetime:
    """Combine a date and time into a single object representing a given moment
    in time."""


def intervals_overlap(
    interval_1: TimeInterval,
    interval_2: TimeInterval,
    min_duration: Duration = Duration(1, TimeUnits["Minutes"]),
) -> bool:
    """Check if intervals_1 and intervals_2 overlap for at least `min_duration`.
    Returns False if the two intervals are disjoint or overlap less than `min_duration`.
    """


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


class EventFrequency(Enum):
    DAILY = auto()
    WEEKLY = auto()
    MONTHLY = auto()
    YEARLY = auto()


class RepetitionSpec(BaseModel):
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
