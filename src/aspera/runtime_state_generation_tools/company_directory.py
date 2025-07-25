#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
from typing import Literal

from aspera.apps.company_directory import Employee, Team
from aspera.apps.time_utils import TimeInterval

UserRole = Literal["CEO", "COO", "CFO", "Manager", "Team Member"]


def simulate_org_structure(
    default_employee_names: list[str],
    user_name: str = "Alex",
    user_role: UserRole = "Team Member",
    user_team: Team = Team.Engineering,
    teams_to_extend: dict[Team, list[str]] | None = None,
):
    """Simulate a simple organisation structure.

    Parameters
    ----------
    default_employee_names
        The names of the employees in the  organisation. Names should be unique.

        Allocated as follows:

            - 3 team members are assigned to the leadership team (CEO, COO, CFO)
            - 3 team members are assistants to the leadership team
            - the remainder are assigned to the engineering, finance and & sales and marketing
            teams s.t. every team has a manager and a team member

        Callers may specify only a subset of names present in the query - the rest of the
        names will be automatically generated. Leave empty to use a set of default names.
    user_name, user_role, user_team
        The name, role and team for the device user. If `user_name` is not present
        in `default_employee_names`, it will be automatically added.
    teams_to_extend
        Additional team members that may need to be specified in situations where queries
        require a deeper organisational structure. The keys teams, and the values are
        lists of names of the additional team members. They should not overlap with
        `default_employee_names` or `user_name`. In addition, members of different teams
        should have  distinct names. If less than two members are specified, an
        additional member will be added so that each manager has an employee.

    Notes
    -----
    1. To ensure a given members or members are in the same team, pass an appropriate
    dictionary to `teams_to_extend`. Adding the names to `default_employee_names` *does not*
    guarantee the employees will be on the same team.
    2. If you extend a team, ensure that you do not include the same names in
    `default_employee_names` as this will duplicate the employee records.
    3. This tool should only be called once during a setup function.
    """


def simulate_vacation_schedule(employee: Employee, time_off: list[TimeInterval]):
    """Simulate the vacation schedule for `employee`.

    Parameters
    ----------
    employee
        The employee whose vacation schedule is to be simulated.
    time_off
        A list of non-overlapping time intervals when the employee is off work.
    """
