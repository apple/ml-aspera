"""A simple and easy to use reminder app - use it for all
your TODOs and all things important."""

import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from aspera.apps.contacts import Contact
from aspera.apps.navigation import LocationTrigger


class ListName:
    name: str


@dataclass
class PersonalReminder:
    """A reminder for a specific event.

    Parameters
    ----------
    subject
        The subject of the reminder.
    when
        The time when the reminder should trigger. It is
        optional because the reminder app can be used
        as a simple to-do list.
    location
        The user may add a specific location to a reminder
        or update the location of an existing reminder.
    is_complete
        Flag indicating if the reminder has been marked
        as complete by the user.
    lists
        Indicates what user lists the reminder is part of.

    """

    subject: str
    when: datetime.datetime | None = None
    repeats: list[datetime.datetime] | None = None
    location: LocationTrigger = None
    is_complete: bool = False
    lists: list[str] = field(default_factory=list)
    priority: Literal["low", "medium", "high"] | None = None


ReminderListOps = Enum("ReminderListOps", ["Add", "Delete"])


def add_reminder(reminder: PersonalReminder) -> None:
    """Remind user of a specific event.

    Parameters
    ----------
    reminder : PersonalReminder
        The reminder to be added.
    """
    ...


def search_reminder(
    by_subject: str = None,
    by_time_period: list[datetime.datetime] = None,
    by_list_membership: list[ListName] = None,
) -> list[PersonalReminder]:
    """Find a reminder by `subject` or see scheduled reminders at given point in
    time or over a period. You can also return the reminders found on one
    or more lists mentioned by the user."""
    ...


def organise(
    reminder: PersonalReminder, target_list: ListName, operation: ReminderListOps
) -> PersonalReminder:
    """Add or delete an existing reminder to/from `target_list`.
    This endpoint can also be used for creating lists containing multiple reminders.
    """
    ...


def share_reminders(reminders: list[PersonalReminder], contacts: list[Contact]):
    """Share reminders with one or more contacts."""
    ...
