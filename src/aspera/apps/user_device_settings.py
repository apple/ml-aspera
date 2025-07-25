"""An app that controls settings on the user device."""

from aspera.apps.navigation import LocationEventTrigger
from aspera.apps.time_utils import TimeInterval


def set_do_not_disturb(
    schedule: list[TimeInterval] | None = None,
    trigger: LocationEventTrigger | None = None,
):
    """Ensure the user's do not disturb profile is enabled according to a
    schedule or based on a location specific trigger."""
