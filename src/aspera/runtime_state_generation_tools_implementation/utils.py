#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import datetime
import random


def fake_phone_number(prefix: str = "+40", n_digits: int = 10) -> str:
    """Generates a fake phone number."""

    fake_digits = [str(random.randint(0, 9)) for _ in range(n_digits)]
    fake_number = f"{prefix}{random.choice(['6', '7', '8', '9'])}{''.join(fake_digits)}"

    return fake_number


def fake_email_address(
    name: str, surname: str | None = None, domain: str = "company.co.ro"
) -> str:
    """Generates a fake email address."""
    if surname:
        return f"{name}_{surname}@{domain}".lower()
    return f"{name}@{domain}".lower()


def fake_video_conference_link(
    name: str, surname: str | None = None, domain: str = "xweb.com"
) -> str:
    if surname:
        return f"https://company.{domain}/{name}.{surname}".lower()
    return f"https://company.{domain}/{name}".lower()


def random_dates(
    start_date: datetime.date, end_date: datetime.date, n: int
) -> list[datetime.date]:
    """Generate a list of random dates within a given interval.

    Parameters
    ----------
    n
        The number of random dates to generate
    """

    dates = []

    for _ in range(n):
        delta = end_date - start_date
        random_days = random.randint(0, delta.days)
        random_date = start_date + datetime.timedelta(days=random_days)
        dates.append(random_date)

    return dates
