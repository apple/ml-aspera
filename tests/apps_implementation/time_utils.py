#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import datetime

from aspera.apps_implementation.time_utils import (
    EventFrequency,
    RepetitionSpec,
    get_prev_dow,
)


# 9:06 are defaults inside recurrent event generation
def create_test_datetime(
    year: int, month: int, day: int, hour: int = 9, minute: int = 6
) -> datetime.datetime:
    return datetime.datetime(year, month, day, hour, minute)


def test_daily_recurrence_with_exclusions():
    start_date = datetime.date(2024, 8, 1)
    repetition = RepetitionSpec(
        frequency=EventFrequency.DAILY,
        period=1,
        max_repetitions=5,
        exclude_occurrence=[
            create_test_datetime(2024, 8, 2),
            create_test_datetime(2024, 8, 4),
        ],
    )

    occurrences = list(repetition.generate_occurrences(start_date=start_date))

    expected_dates = [
        create_test_datetime(2024, 8, 1),
        create_test_datetime(2024, 8, 3),
        create_test_datetime(2024, 8, 5),
    ]

    assert (
        occurrences == expected_dates
    ), f"Expected {expected_dates}, but got {occurrences}"


def test_get_prev_dow():
    # Define some test cases
    test_cases = [
        (
            "Monday",
            datetime.date(2024, 6, 25),
            datetime.date(2024, 6, 24),
        ),  # Previous Monday
        (
            "Tuesday",
            datetime.date(2024, 6, 25),
            datetime.date(2024, 6, 18),
        ),  # Previous Tuesday
        (
            "Wednesday",
            datetime.date(2024, 6, 25),
            datetime.date(2024, 6, 19),
        ),  # Previous Wednesday
        (
            "Thursday",
            datetime.date(2024, 6, 25),
            datetime.date(2024, 6, 20),
        ),  # Previous Thursday
        (
            "Friday",
            datetime.date(2024, 6, 25),
            datetime.date(2024, 6, 21),
        ),  # Previous Friday
        (
            "Saturday",
            datetime.date(2024, 6, 25),
            datetime.date(2024, 6, 22),
        ),  # Previous Saturday
        (
            "Sunday",
            datetime.date(2024, 6, 25),
            datetime.date(2024, 6, 23),
        ),  # Previous Sunday
    ]

    for day_of_week, before_date, expected_date in test_cases:
        assert get_prev_dow(day_of_week, before=before_date) == expected_date

    # Test when `before` is not provided
    # `now_()` returns 2024-06-25 (Tuesday)
    assert get_prev_dow("Monday") == datetime.date(2024, 6, 24)  # Previous Monday
    assert get_prev_dow("Tuesday") == datetime.date(2024, 6, 18)  # Previous Tuesday

    # Edge case: Testing day of the week that is the same as `now_()`
    assert get_prev_dow("Tuesday", before=datetime.date(2024, 6, 25)) == datetime.date(
        2024, 6, 18
    )  # Previous Tuesday
