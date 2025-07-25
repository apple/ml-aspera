"""An app providing utilities for navigation and user device localisation."""

from dataclasses import dataclass
from enum import Enum

from aspera.apps.time_utils import Duration, TimeUnits


class NavigationInstruction:

    instruction: str


def calculate_travel_time(from_location: str, to_location: str) -> Duration:
    """Calculate the travel time between two locations."""


def get_directions(from_location: str, to_location: str) -> list[NavigationInstruction]:
    """Turn-by-turn directions between two locations."""
    pass


def get_current_location() -> str:
    """Get the current location of the user's device."""


class LocationEventTrigger(Enum):

    ARRIVES_AT = "arrival"
    DEPARTS_FROM = "departure"
    NOT_SET = "not_set"


@dataclass
class LocationTrigger:
    """A location-based event trigger. By default, the
    event will occur when the user has been at `location`
    for `time_lag`."""

    location: str
    time_lag: Duration = Duration(number=1, unit=TimeUnits.Hours)
    trigger: LocationEventTrigger = LocationEventTrigger.NOT_SET
