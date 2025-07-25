#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import datetime

import pytest

from aspera.apps_implementation.company_directory import Employee
from aspera.apps_implementation.work_calendar import Event
from tests.apps_implementation.work_calendar_utils import EMPLOYEE_DETAILS


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "uncollect_if(*, func): function to unselect tests from parametrization",
    )


def pytest_collection_modifyitems(config, items):
    removed = []
    kept = []
    for item in items:
        m = item.get_closest_marker("uncollect_if")
        if m:
            func = m.kwargs["func"]
            if func(**item.callspec.params):
                removed.append(item)
                continue
        kept.append(item)
    if removed:
        config.hook.pytest_deselected(items=removed)
        items[:] = kept


@pytest.fixture()
def employees() -> dict[str, Employee]:
    return {
        "Alex": Employee(
            name=EMPLOYEE_DETAILS["Alex"].name,
            employee_id=EMPLOYEE_DETAILS["Alex"].employee_id,
        ),
        "Pete": Employee(
            name=EMPLOYEE_DETAILS["Pete"].name,
            employee_id=EMPLOYEE_DETAILS["Pete"].employee_id,
        ),
        "Anders": Employee(
            name=EMPLOYEE_DETAILS["Anders"].name,
            employee_id=EMPLOYEE_DETAILS["Anders"].employee_id,
        ),
        "Hector": Employee(
            name=EMPLOYEE_DETAILS["Hector"].name,
            employee_id=EMPLOYEE_DETAILS["Hector"].employee_id,
        ),
        "Joris": Employee(
            name=EMPLOYEE_DETAILS["Joris"].name,
            employee_id=EMPLOYEE_DETAILS["Joris"].employee_id,
        ),
    }


@pytest.fixture
def basic_event(employees: dict[str, Employee]) -> Event:
    return Event(
        attendees=[employees["Pete"], employees["Anders"]],
        optional_attendees=[employees["Hector"]],
        avoid_attendees=[employees["Joris"]],
        subject="End of internship party",
        starts_at=datetime.datetime(2024, 9, 26, 12, 0, 0),
        ends_at=datetime.datetime(2024, 9, 26, 13, 0, 0),
        video_link="alexlink@webex.com",
        notes="A quick gather up to celebrate success.",
    )
