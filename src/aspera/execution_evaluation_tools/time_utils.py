#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import datetime

from aspera.apps_implementation.time_utils import RepetitionSpec


def repetition_schedule(
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
