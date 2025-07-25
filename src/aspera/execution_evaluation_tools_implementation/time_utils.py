#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import datetime
from itertools import islice

from aspera.apps_implementation.time_utils import (
    MAX_EVENT_RECURRENCES,
    RepetitionSpec,
    now_,
)


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
    if spec is None:
        return []

    if not start_date:
        start_date = now_().date()

    occurrences = spec.generate_occurrences(start_date, when)
    if not spec.finite:
        return list(islice(occurrences, MAX_EVENT_RECURRENCES))
    return list(occurrences)
