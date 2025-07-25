#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import datetime
from copy import deepcopy
from enum import StrEnum, auto
from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel, model_validator
from pydantic_core import PydanticCustomError

from aspera.apps_implementation.exceptions import SearchError
from aspera.apps_implementation.time_utils import TimeInterval
from aspera.simulation.utils import (
    exact_match_filter_dataframe,
    filter_dataframe,
    fuzzy_match_filter_dataframe,
)


class Team(StrEnum):

    SalesMarketing = auto()
    Engineering = auto()
    Finance = auto()
    Leadership = auto()
    Assistants = auto()


if TYPE_CHECKING:
    from aspera.simulation.database_schemas import DatabaseNamespace

EmployeeID = str


class EmployeeDetails(BaseModel, frozen=True):
    """Employee details stored in the company directory.

    Parameters
    ----------
    manager
        The employee ID of manager of the employee. Set to `None` only
        for the company CEO, who has no line manager.
    assistant
        The employee ID of the assistant of this employee. Populated
        only for members of the leadership team.
    is_user
        Flag to distinguishes the current user from the other
        employees.
    """

    name: str
    email_address: str
    mobile: str
    team: Team
    role: str
    video_conference_link: str
    joined_date: datetime.date
    birth_date: datetime.date
    manager: Optional[EmployeeID]
    assistant: Optional[EmployeeID] = None
    reports: list[EmployeeID] | None = None
    employee_id: str | None = None
    is_user: bool = False

    def __str__(self) -> str:
        return f"{self.name} ({self.employee_id})"


class Employee(BaseModel, frozen=True):
    """A member of the organization, registered in the company
    directory. This object should not be directly instantiated.
    Use `find_employee` to return it instead.

    Parameters
    ----------
    name
        The name of the person.
    """

    name: str
    employee_id: str

    @model_validator(mode="before")
    @classmethod
    def employee_id_set(cls, data: dict[str, Any]) -> dict[str, Any]:
        try:
            assert "employee_id" in data
        except AssertionError:
            raise PydanticCustomError(
                "SolutionError",
                "Employee classes cannot be instantiated directly, use `find_employee` to search for an employee",  # noqa
            )
        return data


def get_employee_profile(employee: Employee) -> EmployeeDetails:
    """Return the profile of an employee, including details
    such as team name, mobile number, department, etc.
    """
    from aspera.simulation.database_schemas import DatabaseNamespace
    from aspera.simulation.execution_context import get_current_context

    context = get_current_context()
    assert employee.employee_id is not None
    raw_records = filter_dataframe(
        dataframe=context.get_database(
            namespace=DatabaseNamespace.EMPLOYEES,
        ),
        filter_criteria=[
            ("employee_id", employee.employee_id, exact_match_filter_dataframe),
        ],
    ).to_dicts()
    # this should be unique because we are querying with a structured
    # object returned by `find_employee`, which should unambiguously
    # identify the individual
    assert len(raw_records) == 1
    record = deepcopy(raw_records[0])
    return EmployeeDetails(**record)


def get_current_user() -> Employee:
    """Get the employee profile of the device user."""
    from aspera.simulation.database_schemas import DatabaseNamespace
    from aspera.simulation.execution_context import get_current_context

    context = get_current_context()
    raw_records = filter_dataframe(
        dataframe=context.get_database(
            namespace=DatabaseNamespace.EMPLOYEES,
        ),
        filter_criteria=[("is_user", True, exact_match_filter_dataframe)],
    ).to_dicts()
    try:
        assert len(raw_records) == 1
    except AssertionError:
        raise SearchError("Unable to retrieve user profile from the company directory.")
    return Employee(
        name=raw_records[0]["name"], employee_id=raw_records[0]["employee_id"]
    )


def find_employee(name: str) -> list[Employee]:
    """Find an employee by name in the company's directory.

    Parameters
    ----------
    name
       The name of the employee searched (fuzzy matched).
    """

    from aspera.simulation.database_schemas import DatabaseNamespace
    from aspera.simulation.execution_context import get_current_context

    context = get_current_context()
    raw_records = filter_dataframe(
        dataframe=context.get_database(
            namespace=DatabaseNamespace.EMPLOYEES,
        ),
        # a threshold of 90 is used to fuzzy match the names
        filter_criteria=[
            ("name", name, fuzzy_match_filter_dataframe),
        ],
    ).to_dicts()
    if raw_records:
        return [
            Employee(name=r["name"], employee_id=r["employee_id"]) for r in raw_records
        ]
    return []


def find_team_of(employee: Employee) -> list[Employee]:
    """Find org members in the same team.

    Parameters
    ----------
    employee
        The employee of the team to search for.

    Returns
    -------
    A list of employees part of the same team, sorted according
    to `name`, excluding `employee`.
    """

    from aspera.simulation.database_schemas import DatabaseNamespace
    from aspera.simulation.execution_context import get_current_context

    profile = get_employee_profile(employee)
    team = profile.team
    context = get_current_context()
    raw_records = filter_dataframe(
        dataframe=context.get_database(namespace=DatabaseNamespace.EMPLOYEES),
        filter_criteria=[("team", team, exact_match_filter_dataframe)],
    ).to_dicts()
    team = [
        Employee(name=r["name"], employee_id=r["employee_id"])
        for r in raw_records
        if r["employee_id"] != employee.employee_id
    ]
    team.sort(key=lambda x: x.name)
    return team


def find_reports_of(employee: Employee) -> list[Employee]:
    """Find a person's reports.

    Returns
    -------
    A (possibly empty) list of employees who report to `employee`,
    sorted according to employee `name`.
    """
    profile = get_employee_profile(employee)
    if profile.reports is None or not profile.reports:
        return []
    reports = []
    for report_id in profile.reports:
        reports.append(_get_employee_by_id(report_id))
    reports.sort(key=lambda x: x.name)
    return reports


def find_manager_of(employee: Employee) -> Employee | None:
    """Find a persons' manager."""

    profile = get_employee_profile(employee)
    manager_id = profile.manager
    if manager_id is None:
        return
        # raise SearchError("Employee does not have a manager!")
    manager = _get_employee_by_id(manager_id)
    return manager


def get_assistant(employee: Employee) -> Optional[Employee]:
    """Find the assistant of an employee, if it exists. Only
    members of the senior leadership team have assistants."""

    leadership_roles = ["CEO", "CFO", "COO"]
    profile = get_employee_profile(employee)
    if profile.role not in leadership_roles:
        return
    assistant_id = profile.assistant
    assert assistant_id is not None
    assistant = _get_employee_by_id(assistant_id)
    return assistant


def get_vacation_schedule(employee: Employee) -> list[TimeInterval] | None:
    """Returns the vacation schedule of the employee or `None`
    if the employee has not booked a holiday. Multiple time
    intervals returned if the user has booked more than one holiday
    in the current fiscal year.

    Notes
    -----
    1. Holiday periods are sorted according to start day.
    """
    from aspera.simulation.database_schemas import DatabaseNamespace
    from aspera.simulation.execution_context import get_current_context

    current_context = get_current_context()
    db = current_context.get_database(
        namespace=DatabaseNamespace.EMPLOYEE_VACATIONS,
    )
    holiday_info = filter_dataframe(
        dataframe=db,
        filter_criteria=[
            ("employee_id", employee.employee_id, exact_match_filter_dataframe),
        ],
    ).to_dicts()
    # employee ID not in DB => no hols booked
    if not holiday_info:
        return
    schedule = []
    for period in holiday_info:
        schedule.append(TimeInterval(start=period["starts"], end=period["ends"]))
    schedule.sort(key=lambda x: x.start)
    return schedule


def get_all_employees() -> list[Employee]:
    """List all employees of the company in alphabetical order according to `name`."""

    from aspera.simulation.database_schemas import DatabaseNamespace
    from aspera.simulation.execution_context import get_current_context

    context = get_current_context()

    raw_db = context.get_database(namespace=DatabaseNamespace.EMPLOYEES).to_dicts()
    company = [Employee(name=r["name"], employee_id=r["employee_id"]) for r in raw_db]
    company.sort(key=lambda x: x.name)
    return company


def _get_employee_by_id(employee_id: str) -> Employee:
    """Retrieve the employee with `employee_id` from the
    company directory.

    Raises
    ------
    SearchError if `employee` is not in the database.
    """

    from aspera.simulation.database_schemas import DatabaseNamespace
    from aspera.simulation.execution_context import get_current_context

    current_context = get_current_context()
    raw_records = filter_dataframe(
        dataframe=current_context.get_database(namespace=DatabaseNamespace.EMPLOYEES),
        filter_criteria=[
            ("employee_id", employee_id, exact_match_filter_dataframe),
        ],
    ).to_dicts()
    employees = [
        Employee(name=record["name"], employee_id=record["employee_id"])
        for record in raw_records
    ]
    assert len(employees) == 1
    return employees[0]


def get_office_location(employee: Employee) -> str:
    """Returns the location of the office where
    the employee is based."""
    return "30 Station Road, Cambridge, CV3 2AL"
