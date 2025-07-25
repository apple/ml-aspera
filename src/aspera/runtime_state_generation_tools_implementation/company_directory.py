#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import datetime
import random
import uuid
from copy import deepcopy
from functools import cached_property
from typing import Any, Literal, NamedTuple, Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from pydantic_core.core_schema import FieldValidationInfo

from aspera.apps_implementation.company_directory import Employee, EmployeeDetails, Team
from aspera.apps_implementation.time_utils import TimeInterval, now_
from aspera.runtime_state_generation_tools_implementation.utils import (
    fake_email_address,
    fake_phone_number,
    fake_video_conference_link,
    random_dates,
)
from aspera.simulation.database_schemas import DatabaseNamespace
from aspera.simulation.execution_context import get_current_context
from aspera.simulation.utils import NOT_GIVEN
from aspera.utils import count_nested_dict_values

UserRole = Literal["CEO", "COO", "CFO", "Manager", "Team Member"]
LEADERSHIP_ROLES = ["CEO", "COO", "CFO"]
OTHER_ROLES = ["Manager", "Team Member"]
DEFAULT_ORG_NAMES = (
    "Horace",
    "Mafalda",
    "Splendour",
    "Charm",
    "Sweethearta",
    "Robespierre",
    "Danton",
    "Marat",
    "Ileana",
    "Elina",
    "Spookington",
    "Jeeves",
)
DEFAULT_TEAM_EXTENSION_NAMES = ("Songoku", "Frodopop")
DEFAULT_ORG_MIN_MEMBERS = 12
EXTENDED_TEAM_MIN_MEMBERS = 2

# parameterise start dates
LEADERSHIP_START_DATE = datetime.date(2023, 7, 23)
NEW_HIRE_PROBABILITY = 0.5
FIXED_HIRE_DATE = datetime.date(2024, 5, 22)
MAX_HIRED_ON_FIXED_DATE = 2


class NewHireJoinedRange(NamedTuple):

    start: datetime.date = now_().date() - datetime.timedelta(days=30)
    end: datetime.date = now_().date() - datetime.timedelta(days=1)


class VeteranJoinedRange(NamedTuple):

    start: datetime.date = LEADERSHIP_START_DATE
    end: datetime.date = datetime.date(2023, 12, 1)


class BirthDayRange(NamedTuple):

    start: datetime.date = datetime.date(1979, 1, 1)
    end: datetime.date = datetime.date(2005, 1, 1)


class EmployeeConstructor:
    """Employee details stored in the company directory.

    Parameters
    ----------
    role
        The user role. One of "CEO", "COO", "CFO", "Manager", "Team Member"
    reports
        A list of names of the employees who report to this employee.
    manager
        The manager of the employee. Set to `None` only
        for the company CEO, who has no line manager.
    assistant
        The name of the assistant of this employee. Populated
        only for members of the leadership team.
    is_user
        Flag to distinguishes the current user from the other
        employees.
    """

    def __init__(
        self,
        name: str,
        team: Team,
        role: str,
        manager: Self | None | NOT_GIVEN,
        reports: list[Self] | None = None,
        assistant: Self | None = None,
        is_user: bool = False,
        fix_hire_date: bool = False,
    ):
        self.name = name
        self.team = team
        self.role = role
        self.reports = reports if reports is not None else []
        self.assistant = assistant
        self.manager = manager
        self.is_user = is_user
        self._self_details: EmployeeDetails | None = None
        self._hire_date = FIXED_HIRE_DATE if fix_hire_date else None

    @cached_property
    def mobile(self) -> str:
        return fake_phone_number()

    @cached_property
    def email_address(self) -> str:
        return fake_email_address(self.name)

    @cached_property
    def video_conference_link(self) -> str:
        return fake_video_conference_link(self.name)

    @cached_property
    def joined_date(self) -> datetime.date:
        if self.role in LEADERSHIP_ROLES:
            return LEADERSHIP_START_DATE
        if self.is_user:
            range = VeteranJoinedRange()
        elif self._hire_date is not None:
            return self._hire_date
        else:
            if random.random() > NEW_HIRE_PROBABILITY:
                range = NewHireJoinedRange()
            else:
                range = VeteranJoinedRange()
        return random_dates(*range, n=1)[0]

    @cached_property
    def birth_date(self) -> datetime.date:
        range = BirthDayRange()
        bday = random_dates(*range, n=1)[0]
        bday_months = [7, 8]
        return bday.replace(month=random.choice(bday_months))

    @cached_property
    def employee_id(self) -> str:
        return str(uuid.uuid4())

    def __repr__(self):
        return f"{self.name} ({self.role})"

    @cached_property
    def db_record(self) -> EmployeeDetails:
        return EmployeeDetails(
            name=self.name,
            email_address=self.email_address,
            mobile=self.mobile,
            team=self.team,
            role=self.role,
            video_conference_link=self.video_conference_link,
            joined_date=self.joined_date,
            birth_date=self.birth_date,
            manager=self.manager.employee_id if self.manager is not None else None,
            assistant=(
                self.assistant.employee_id if self.assistant is not None else None
            ),
            reports=[r.employee_id for r in self.reports],
            employee_id=self.employee_id,
            is_user=self.is_user,
        )


class OrgStructure(BaseModel):

    leadership: list[EmployeeConstructor]
    teams: dict[Team, list[EmployeeConstructor]]
    user: EmployeeConstructor
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def org_size(self) -> int:
        # *2 because every leader has an assistant
        return len(self.leadership) * 2 + sum(
            count_nested_dict_values(self.teams).values()
        )

    def __str__(self) -> str:
        def format_employee(employee: EmployeeConstructor, level: int = 0) -> str:
            indent = "  " * level
            if employee.role == "Manager" and employee.manager.team == Team.Leadership:
                team_name = (
                    employee.team.name
                    if employee.team != Team.SalesMarketing
                    else "Sales & Marketing"
                )
                result = f"{indent}{employee.name} ({team_name} {employee.role})\n"
            else:
                result = f"{indent}{employee.name} ({employee.role})\n"
            for report in employee.reports:
                result += format_employee(report, level + 1)
            return result

        ceo = next(emp for emp in self.leadership if emp.role == "CEO")
        org_chart = format_employee(ceo)
        org_chart = f"{org_chart}\n{self._user_str()}"

        return org_chart

    def _user_str(self) -> str:
        if self.user.role in LEADERSHIP_ROLES:
            user = f"{self.user.name} ({self.user.role})"
        else:
            team_name = (
                self.user.team.name
                if self.user.team != Team.SalesMarketing
                else "Sales & Marketing"
            )
            if (
                self.user.role == "Manager"
                and self.user.manager.role in LEADERSHIP_ROLES
            ):
                user = f"{self.user.name} ({team_name} {self.user_role})"
            else:
                user = f"{self.user.name} ({self.user.role} in {team_name})"
        return user

    def get_fixed_hire_date_employees(self, team: Team) -> int:
        return len([e for e in self.teams[team] if e.joined_date == FIXED_HIRE_DATE])


def validate_user_role(role: UserRole | None):
    expected_roles = ["CEO", "COO", "CFO", "Manager", "Team Member", None]
    try:
        assert role in expected_roles
    except AssertionError:
        raise ValueError(
            f"Invalid user role: {role}. "
            f"Should be one of {''.join(expected_roles[:-1])} or None."
        )


def validate_nb_employees(
    names: list[str],
    additional_names: tuple[str, ...] = DEFAULT_ORG_NAMES,
    min_members: int = DEFAULT_ORG_MIN_MEMBERS,
):
    """Ensure there are enough people to generate the simplest
    org structure where:

     - there are 3 members of the leadership team
     - all leaders have an assistant
     - an employee and a manager exist for each team
    """

    if (outstanding := (len(names) - min_members)) < 0:
        for i in range(abs(outstanding)):
            names.append(additional_names[i])


def simulate_basic_org_structure(
    names: list[str],
    user_name: str,
    user_team: Team = Team.Engineering,
    user_role: UserRole = "Team Member",
) -> OrgStructure:
    """Simulate a simple org structure for given the

    Notes
    -----

        1. Leadership team: CEO, COO, CFO
        2. Each member of the leadership team has an assistant
        3. Each team has at least a manager and an employee.
        4. Not written with duplicate members in mind - extend implementation if you want this.
    """

    class LeadershipTeam(NamedTuple):
        """Leadership team.

        Parameters
        ----------
        all_
            List of the company bosses, in the order CEO, CFO, COO.

        """

        all_: list[EmployeeConstructor]
        ceo: EmployeeConstructor
        coo: EmployeeConstructor
        cfo: EmployeeConstructor

    def create_leadership_team(
        names: list[str], user_name: str, user_role: UserRole | None
    ) -> LeadershipTeam:
        """Create the leadership team, including their assistants. This function modifies
        `names` in place."""
        # Create placeholders for the leadership roles
        ceo = coo = cfo = None
        leadership: list[EmployeeConstructor] = []
        # Determine if the user is assigned a leadership role
        if user_role == "CEO":
            ceo = EmployeeConstructor(
                name=user_name,
                team=Team.Leadership,
                role="CEO",
                manager=None,
                is_user=True,
            )
            names.remove(user_name)
        elif user_role == "COO":
            coo = EmployeeConstructor(
                name=user_name,
                team=Team.Leadership,
                role="COO",
                manager=NOT_GIVEN,
                is_user=True,
            )
            names.remove(user_name)
        elif user_role == "CFO":
            cfo = EmployeeConstructor(
                name=user_name,
                team=Team.Leadership,
                role="CFO",
                # assigned later on
                manager=None,
                is_user=True,
            )
            names.remove(user_name)
        # Create the remaining leadership team, ensuring the user, handled last, cannot
        # be assigned to a leadership role if this was not explicitly mentioned
        add_back_user_name = False
        if user_name in names:
            names.remove(user_name)
            add_back_user_name = True
        if ceo is None:
            ceo = EmployeeConstructor(
                name=names.pop(),
                team=Team.Leadership,
                role="CEO",
                manager=None,
            )
        if coo is None:
            coo = EmployeeConstructor(
                name=names.pop(),
                team=Team.Leadership,
                role="COO",
                # assigned later on
                manager=NOT_GIVEN,
            )
        if cfo is None:
            cfo = EmployeeConstructor(
                name=names.pop(),
                team=Team.Leadership,
                role="CFO",
                # assigned later on
                manager=NOT_GIVEN,
            )
        # COO and CFO should report to the CEO
        assert all((ceo is not None, cfo is not None, coo is not None))
        ceo.reports = [coo, cfo]
        coo.manager = ceo
        cfo.manager = ceo
        leadership.extend([ceo, coo, cfo])
        # Assign assistants to leadership - note the user cannot be an assistant
        for leader in leadership:
            assistant = EmployeeConstructor(
                name=names.pop(), team=Team.Assistants, role="Assistant", manager=leader
            )
            leader.assistant = assistant
        if add_back_user_name:
            names.insert(0, user_name)
        return LeadershipTeam(all_=leadership, ceo=ceo, cfo=cfo, coo=coo)

    # Ensure the user_name is in the names list
    names = deepcopy(names)
    validate_user_role(user_role)
    validate_nb_employees(names)
    if user_name not in names:
        names.append(user_name)
    random.shuffle(names)

    leadership_team = create_leadership_team(names, user_name, user_role)
    ceo, coo, cfo = leadership_team.all_

    # Create other teams
    teams: dict[Team, list[EmployeeConstructor]] = {
        Team.SalesMarketing: [],
        Team.Engineering: [],
        Team.Finance: [],
    }
    # for simplicity, every team has one manager to start with
    managers: dict[Team, EmployeeConstructor] = {}

    # Assign managers for each team
    for team in teams:
        manager_name = names.pop()
        # we add the user to the org structure at the end
        if user_name == manager_name:
            manager_name = names.pop()
            names.insert(0, user_name)
        manager = EmployeeConstructor(
            name=manager_name,
            team=team,
            role="Manager",
            manager=NOT_GIVEN,
        )
        teams[team].append(manager)
        managers[team] = manager
        # ensure they report to the leadership team
        match team:
            case Team.Finance:
                cfo.reports.append(manager)
                managers[team].manager = cfo
            case _:
                coo.reports.append(manager)
                managers[team].manager = coo

    # Assign team members to each team
    # user is assigned last and might be a manager - if we have
    # exactly the number of employees we need for a complete org
    # structure then it is possible to have teams without any members
    sorted_teams = [t for t in teams if t != user_team]
    if user_team != Team.Leadership:
        sorted_teams.append(user_team)
    while names:
        for team in sorted_teams:
            if names == [user_name] or not names:
                break
            member_name = names.pop()
            # we add the user to the org structure at the end
            if user_name == member_name:
                member_name = names.pop()
                names.insert(0, user_name)
            member = EmployeeConstructor(
                name=member_name, team=team, role="Team Member", manager=managers[team]
            )
            # Assign team member to manager
            teams[team].append(member)
            managers[team].reports.append(member)
        if names == [user_name] or not names:
            break

    # Add the user if they are not in a leadership role, using default settings
    if user_role not in LEADERSHIP_ROLES:
        user = EmployeeConstructor(
            name=user_name,
            team=user_team,
            role=user_role,
            manager=managers[user_team],
            is_user=True,
        )
        teams[user_team].append(user)
        # assumes one manager per team
        managers[user_team].reports.append(user)
        # ensure the user has at least a report if they're a manager
        if user_role == "Manager":
            user_report = EmployeeConstructor(
                name="Rumplestinskin", team=user_team, role="Team Member", manager=user
            )
            teams[user_team].append(user_report)
            user.reports.append(user_report)
    else:
        # Find the user's role in the leadership
        user = ceo if user_role == "CEO" else coo if user_role == "COO" else cfo

    # Structure the organization
    organization = {
        "leadership": [leader for leader in leadership_team.all_],
        "teams": teams,
        "user": user,
    }
    return OrgStructure(**organization)


def extend_team(
    organization: OrgStructure,
    new_names: list[str],
    team_to_extend: Team,
    manager_probability: float = 0.2,
):
    """In-place extend a team in the organization to have additional members and managers.

    Parameters
    ----------
    new_names
        The names of the employees to be added to the team. At least two should be specified
        to ensure that at least a manager reports to a manager in the team and that all
        managers have reports.
    manager_probability
        Probability of adding a new manager to the team.

    Notes
    -----
    1. Adding members with same names with existing employees or the user is not
        tested/accounted for.

    Raises
    -----
    ValueError
        If the team to be extended has no manager.
    """
    new_names = deepcopy(new_names)
    current_managers = [
        member
        for member in organization.teams[team_to_extend]
        if member.role == "Manager"
    ]
    if not current_managers:
        raise ValueError("The specified team does not have any managers to extend.")
    validate_nb_employees(
        new_names,
        additional_names=DEFAULT_TEAM_EXTENSION_NAMES,
        min_members=EXTENDED_TEAM_MIN_MEMBERS,
    )

    # Ensure at least one manager has another manager as a direct report
    for manager in current_managers:
        if any(report.role == "Manager" for report in manager.reports):
            break
    else:
        new_manager_name = new_names.pop()
        manager_to_extend = random.choice(current_managers)
        new_manager = EmployeeConstructor(
            name=new_manager_name,
            team=team_to_extend,
            role="Manager",
            manager=manager_to_extend,
        )
        manager_to_extend.reports.append(new_manager)
        current_managers.append(new_manager)
        new_employee_name = new_names.pop()
        new_employee = EmployeeConstructor(
            name=new_employee_name,
            team=team_to_extend,
            role="Team Member",
            manager=new_manager,
        )
        new_manager.reports.append(new_employee)
        organization.teams[team_to_extend].extend([new_manager, new_employee])

    # Add the remaining new employees to the team
    while new_names:
        new_employee_name = new_names.pop()
        role = "Manager" if random.random() < manager_probability else "Team Member"
        if len(new_names) in range(1):
            role = "Team Member"
        # Choose from all the managers that don't have reports yet first
        managers_without_reports = [
            manager for manager in current_managers if not manager.reports
        ]
        if managers_without_reports:
            manager_to_report = random.choice(managers_without_reports)
        else:
            manager_to_report = random.choice(current_managers)
        fix_hiring_date = False
        if (
            organization.get_fixed_hire_date_employees(team_to_extend)
            < MAX_HIRED_ON_FIXED_DATE
        ):
            fix_hiring_date = True
        new_employee = EmployeeConstructor(
            name=new_employee_name,
            team=team_to_extend,
            role=role,
            manager=manager_to_report,
            fix_hire_date=fix_hiring_date,
        )
        # Assign the new employee to report to a random manager
        manager_to_report.reports.append(new_employee)
        # If the new employee is a manager, add them to the list of current managers
        if role == "Manager":
            current_managers.append(new_employee)
        organization.teams[team_to_extend].append(new_employee)


def write_to_db(employee_record: EmployeeDetails) -> Employee:
    """Add an employee to the company directory.

    Notes
    -----
    1. When simulating an employee, make sure that any relevant
    employees referenced in this record are added to the directory in subsequent
    simulate_employee calls.

    For example:

        - if the `assistant_name` field is populated, then a separate
        call to `simulate_employee_profile` should be made to add the assistant
        to the company directory
        - similar considerations apply to the `manager` field.
    """

    context = get_current_context()
    employee_dict = employee_record.model_dump()
    context.add_to_database(namespace=DatabaseNamespace.EMPLOYEES, rows=[employee_dict])
    return Employee(
        name=employee_dict["name"], employee_id=employee_dict["employee_id"]
    )


def write_to_database(org_structure: OrgStructure) -> None:
    """Write the employees to the underlying database"""

    def _recursive_write(employee: EmployeeConstructor):
        write_to_db(employee.db_record)
        for report in employee.reports:
            _recursive_write(report)
        if employee.assistant is not None:
            _recursive_write(employee.assistant)

    # recursively write all employees to the DB, starting with the root (CEO)
    ceo = next(emp for emp in org_structure.leadership if emp.role == "CEO")
    _recursive_write(ceo)


class ReportAssignment(BaseModel):
    """Specifies which reports are assigned to a manager.

    Parameters
    ----------
    manager
        The name of the manager.
    reports
        The name of the employees who should be
        assigned to this manager.
    """

    manager: str
    reports: list[str]


class TeamExtension(BaseModel):
    """Specify detailed structure to a team structure.

    Parameters
    ----------
    team
        Which team has to be extended.
    additional_members
        The names of the additional team members.
    managers
        A subset of `additional_members` which should
        be assigned management roles. Managers are
        otherwise assigned with a certain probability.
    structure_constraints
        Use this property to constrain team structure if
        necessary. The manager should be listed in the
        `managers` property and that they are also listed
        in `additional_members`. Each name listed in the
        `reports` must also be part of the `additional_members`
        list.
    """

    team: Team
    additional_members: list[str]
    managers: list[str] | None = None
    structure_constraints: list[ReportAssignment] | None = None

    @field_validator("managers", mode="before")
    @classmethod
    def managers_must_be_additional_members(
        cls, managers: list[str], info: FieldValidationInfo
    ):
        """Ensure that each manager is in the `additional_members` list."""
        additional_members = info.data.get("additional_members", [])
        if not all(manager in additional_members for manager in managers):
            raise ValueError(
                "At least one manager in not specified as additional member."
            )
        return managers

    @model_validator(mode="before")
    @classmethod
    def validate_structure_constraints(cls, data: dict[str, Any]):
        """Ensure that `structure_constraints` follow the rules."""
        additional_members = data.get("additional_members", [])
        managers = data.get("managers", [])
        structure_constraints = data.get("structure_constraints", [])

        if structure_constraints:
            for constraint in structure_constraints:
                if constraint.manager not in managers:
                    raise ValueError(f"Manager {constraint.manager} not in managers!")
                for report in constraint.reports:
                    if report not in additional_members:
                        raise ValueError(
                            f"Report {report} is not specified as a team member!"
                        )

        return data


def simulate_org_structure(
    default_employee_names: list[str],
    user_name: str = "Alex",
    user_role: UserRole = "Team Member",
    user_team: Team = Team.Engineering,
    teams_to_extend: dict[Team, list[str]] | None = None,
) -> OrgStructure:
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

    basic_org = simulate_basic_org_structure(
        names=default_employee_names,
        user_name=user_name,
        user_team=user_team,
        user_role=user_role,
    )
    if teams_to_extend is not None:
        for team, new_members in teams_to_extend.items():
            extend_team(basic_org, new_names=new_members, team_to_extend=team)
    write_to_database(basic_org)
    return basic_org


def simulate_vacation_schedule(employee: Employee, time_off: list[TimeInterval]):
    """Simulate the vacation schedule for `employee`.

    Parameters
    ----------
    employee
        The employee whose vacation schedule is to be simulated.
    time_off
        A list of non-overlapping time intervals when the employee is off work.
    """

    db_records = []
    for period in time_off:
        db_records.append(
            {
                "employee_id": employee.employee_id,
                "starts": period.start,
                "ends": period.end,
            }
        )
    context = get_current_context()
    context.add_to_database(
        namespace=DatabaseNamespace.EMPLOYEE_VACATIONS, rows=db_records
    )
