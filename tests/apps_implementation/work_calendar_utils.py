#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import datetime
import uuid

import pytest

from aspera.apps_implementation.company_directory import Employee, EmployeeDetails, Team
from aspera.runtime_state_generation_tools_implementation.company_directory import (
    write_to_db,
)

anders_details = EmployeeDetails(
    name="Anders",
    email_address="anders@company.com",
    mobile="+407536353121",
    team=Team.Leadership,
    role="CEO",
    video_conference_link="anders@webex.com",
    joined_date=datetime.date(1996, 4, 15),
    birth_date=datetime.date(1978, 7, 23),
    manager=None,
    employee_id=str(uuid.uuid4()),
)
pete_details = EmployeeDetails(
    name="Pete",
    email_address="pete@company.com",
    mobile="+407531253121",
    role="Engineering Manager",
    team=Team.Engineering,
    video_conference_link="pete@webex.com",
    joined_date=datetime.date(2018, 4, 15),
    birth_date=datetime.date(1996, 7, 23),
    manager=anders_details.employee_id,
    employee_id=str(uuid.uuid4()),
)
EMPLOYEE_DETAILS = {
    "Alex": EmployeeDetails(
        name="Alex",
        email_address="alex@company.com",
        mobile="+4075312531111",
        team=Team.Engineering,
        role="Team Member",
        video_conference_link="alex@webex.com",
        joined_date=datetime.date(2024, 4, 15),
        birth_date=datetime.date(1992, 7, 23),
        manager=pete_details.employee_id,
        employee_id=str(uuid.uuid4()),
        is_user=True,
    ),
    "Pete": pete_details,
    "Anders": anders_details,
    "Hector": EmployeeDetails(
        name="Hector",
        email_address="hector@company.com",
        mobile="+407536353121",
        team=Team.SalesMarketing,
        role="Manager",
        video_conference_link="anders@webex.com",
        joined_date=datetime.date(2019, 2, 11),
        birth_date=datetime.date(1978, 6, 22),
        manager=anders_details.employee_id,
        employee_id=str(uuid.uuid4()),
    ),
    "Joris": EmployeeDetails(
        name="Joris",
        email_address="joris@company.com",
        mobile="+407536753121",
        team=Team.Finance,
        role="CFO",
        video_conference_link="joris@webex.com",
        joined_date=datetime.date(2000, 2, 11),
        birth_date=datetime.date(1985, 6, 22),
        manager=anders_details.employee_id,
        employee_id=str(uuid.uuid4()),
    ),
}


@pytest.fixture
def alex_profile() -> EmployeeDetails:
    return EMPLOYEE_DETAILS["Alex"]


@pytest.fixture()
def pete_profile() -> EmployeeDetails:
    return EMPLOYEE_DETAILS["Pete"]


@pytest.fixture()
def anders_profile() -> EmployeeDetails:
    return EMPLOYEE_DETAILS["Anders"]


@pytest.fixture()
def hector_profile() -> EmployeeDetails:
    return EMPLOYEE_DETAILS["Hector"]


def setup_employee_database() -> dict[str, Employee]:
    return {
        "Alex": write_to_db(EMPLOYEE_DETAILS["Alex"]),
        "Pete": write_to_db(EMPLOYEE_DETAILS["Pete"]),
        "Anders": write_to_db(EMPLOYEE_DETAILS["Anders"]),
        "Hector": write_to_db(EMPLOYEE_DETAILS["Hector"]),
        "Joris": write_to_db(EMPLOYEE_DETAILS["Joris"]),
    }
