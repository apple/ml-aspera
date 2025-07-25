"""The company directory. Contains tools for navigating the organisation structure and searching
employee names. Search tools return objects required by downstream calendar, reminder and email
APIs."""

import datetime
from enum import StrEnum, auto
from typing import NamedTuple, Optional

from aspera.apps.time_utils import TimeInterval


class Team(StrEnum):

    SalesMarketing = auto()
    Engineering = auto()
    Finance = auto()
    Leadership = auto()


class EmployeeDetails(NamedTuple):

    name: str
    email_address: str
    mobile: str
    team: Team
    video_conference_link: str
    joined_date: datetime.date
    birth_date: datetime.date


class Employee(NamedTuple):
    """A member of the organization.

    Parameters
    ----------
    name
        The name of the person.
    """

    name: str


def get_current_user() -> Employee:
    """Get the employee profile of the device user."""


def find_employee(name: str) -> list[Employee]:
    """Find an employee by name in the company's directory.

    Parameters
    ----------
    name
       The name of the employee searched (fuzzy matched).
    """


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


def find_reports_of(employee: Employee) -> list[Employee]:
    """Find a person's reports.

    Returns
    -------
    A (possibly empty) list of employees who report to `employee`,
    sorted according to employee `name`.
    """


def find_manager_of(employee: Employee) -> Employee | None:
    """Find a persons' manager."""


def get_assistant(employee: Employee) -> Optional[Employee]:
    """Find the assistant of an employee, if it exists. Only
    members of the senior leadership team have assistants."""


def get_vacation_schedule(employee: Employee) -> list[TimeInterval] | None:
    """Returns the vacation schedule of the employee or `None`
    if the employee has not booked a holiday. Multiple time
    intervals returned if the user has booked more than one holiday
    in the current fiscal year.

    Notes
    -----
    1. Holiday periods are sorted according to start day.
    """


def get_employee_profile(employee: Employee) -> EmployeeDetails:
    """Return the profile of an employee, including details
    such as team name, mobile number, department, etc."""


def get_all_employees() -> list[Employee]:
    """List all employees of the company in alphabetical order according to `name`."""


def get_office_location(employee: Employee) -> str:
    """Returns the location of the office where
    the employee is based."""
