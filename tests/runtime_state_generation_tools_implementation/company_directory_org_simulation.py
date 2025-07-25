#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import datetime
import uuid
from typing import Any

import polars as pl
import pydantic
import pytest

from aspera.apps_implementation.company_directory import (
    EmployeeDetails,
    Team,
    get_employee_profile,
)
from aspera.runtime_state_generation_tools_implementation.company_directory import (
    DEFAULT_ORG_MIN_MEMBERS,
    EXTENDED_TEAM_MIN_MEMBERS,
    LEADERSHIP_ROLES,
    OTHER_ROLES,
    OrgStructure,
    ReportAssignment,
    TeamExtension,
    UserRole,
    extend_team,
    simulate_basic_org_structure,
    simulate_org_structure,
    write_to_db,
)
from aspera.simulation.database_schemas import DatabaseNamespace
from aspera.simulation.execution_context import (
    ExecutionContext,
    get_current_context,
    new_context,
)
from aspera.simulation.utils import NOT_GIVEN

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


def test_add_employee(
    alex_profile: EmployeeDetails,
    pete_profile: EmployeeDetails,
    anders_profile: EmployeeDetails,
):

    # reset the context automatically set by the execution_context feature
    context = ExecutionContext()
    with new_context(context):
        write_to_db(anders_profile)
        write_to_db(pete_profile)
        alex = write_to_db(alex_profile)
        alex_details = get_employee_profile(alex)
        assert alex_details.employee_id == alex.employee_id
        for f in alex_profile.model_fields:
            # employee_id exists in the schema but is set in the DB
            if f != "employee_id":
                assert getattr(alex_profile, f) == getattr(alex_details, f)

        raw_db = get_current_context().get_database(
            namespace=DatabaseNamespace.EMPLOYEES
        )
        assert raw_db.select(pl.col("is_user")).sum().to_series().to_list() == [1]
        assert len(raw_db) == 3


def uncollect_if_team_role_mismatch(**kwargs: Any) -> bool:
    role, team = kwargs["user_role"], kwargs["user_team"]
    conditions = [
        role in LEADERSHIP_ROLES and team != Team.Leadership,
        team == Team.Leadership and role not in LEADERSHIP_ROLES,
    ]
    return any(conditions)


user = "Jack"
employee_names = [
    # default org
    [],
    # enough employees, user among them
    [
        "Alice",
        "Bob",
        "Charlie",
        "David",
        "Eve",
        "Frank",
        "Grace",
        "Hank",
        "Ivy",
        user,
        "Lulu",
        "Tena",
        "Polo",
        "Harvey",
    ],
    # as above, removed user
    [
        "Alice",
        "Bob",
        "Charlie",
        "David",
        "Eve",
        "Frank",
        "Grace",
        "Hank",
        "Ivy",
        "Lulu",
        "Tena",
        "Polo",
        "Harvey",
    ],
    # employee subset w/ user
    ["Alice", "Bob", "Charlie", user],
    # employee subset w/o user
    ["Alice", "Bob", "Charlie"],
]
user_name = [user]
user_role = LEADERSHIP_ROLES + OTHER_ROLES
user_team = [t for t in Team]


def calculate_org_size(
    names: list[str],
    additional_names: list[str],
    user_role: UserRole | None,
    user_name: str | None,
) -> int:

    size_ = len(names)
    if len(names) < DEFAULT_ORG_MIN_MEMBERS:
        size_ = DEFAULT_ORG_MIN_MEMBERS

    if additional_names:
        size_ += (
            len(additional_names)
            if len(additional_names) >= EXTENDED_TEAM_MIN_MEMBERS
            else EXTENDED_TEAM_MIN_MEMBERS
        )

    # added to names list automatically
    if user_name not in names:
        size_ += 1
    # report automatically added
    if user_role == "Manager":
        size_ += 1
    return size_


@pytest.mark.uncollect_if(func=uncollect_if_team_role_mismatch)
@pytest.mark.parametrize(
    "names", employee_names, ids=lambda x: f"employess={', '.join(x)}"
)
@pytest.mark.parametrize("user_name", user_name, ids="user_name={}".format)
@pytest.mark.parametrize("user_role", user_role, ids="user_role={}".format)
@pytest.mark.parametrize("user_team", user_team, ids=lambda x: f"user_team={x.name}")
@pytest.mark.parametrize("n_trials", [10], ids="trials={}".format)
def test_simulate_basic_org_structure(
    names: list[str], user_name: str, user_role: str, user_team: Team, n_trials: int
):

    for _ in range(n_trials):
        org = simulate_basic_org_structure(
            names=names,
            user_name=user_name,
            user_team=user_team,
            user_role=user_role,
        )
        assert_on_org_structure(org, names, user_name, user_role)


def assert_on_org_structure(
    org: OrgStructure,
    names: list[str],
    user_name: str,
    user_role: str,
    additional_employees: list[str] | None = None,
    check_db: bool = False,
):

    users_found = []
    additional_employees = additional_employees or []
    # check each team has manager & each manager has a report
    for team, members in org.teams.items():
        assert any(m.role == "Manager" for m in members)
        assert any(m.role == "Team Member" for m in members)
        assert all(m.manager is not None for m in members)
        assert not any(m.manager is NOT_GIVEN for m in members)
        assert all(m.reports for m in members if m.role != "Team Member")
        managers = [m for m in members if m.role == "Manager"]
        assert all(bool(m.reports) for m in managers)
        users_found += [m for m in members if m.is_user]
    # check org size is as expected
    assert org.org_size == calculate_org_size(
        names=names,
        additional_names=additional_employees,
        user_role=user_role,
        user_name=user_name,
    )
    users_found += [m for m in org.leadership if m.is_user]
    assert len(users_found) == 1
    for leader in org.leadership:
        match leader.role:
            case "CEO":
                assert leader.manager is None
                assert len(leader.reports) == 2
                assert leader.assistant is not None
                assert leader.assistant.manager == leader
                assert not leader.assistant.reports
                for _, members in org.teams.items():
                    assert leader.assistant not in members
            case _:
                assert leader.manager.role == "CEO"
                assert leader.assistant is not None
                assert not leader.assistant.reports
                assert leader.assistant.manager == leader
                assert len(leader.reports) in range(1, 3)
                for _, members in org.teams.items():
                    assert leader.assistant not in members
    if check_db:
        context = get_current_context()
        db = context.get_database(namespace=DatabaseNamespace.EMPLOYEES)
        assert len(db) == org.org_size
        assert db.get_column("assistant").drop_nulls().len() == 3
        employee_id = db.get_column("employee_id").to_list()
        managers = {el for el in db.get_column("manager").to_list() if el is not None}
        assert set(managers).issubset(employee_id)
        for reports in db.get_column("reports").to_list():
            assert all(r in employee_id for r in reports)
        assert len(employee_id) == len(set(employee_id))


extended_teams = [t for t in Team if t != Team.Leadership]
manager_probas = [0.2, 0.3, 0.4]
additional_employees = [["Gogu"], ["Sylvester", "Tweety", "Stan", "Bran"]]


@pytest.mark.uncollect_if(func=uncollect_if_team_role_mismatch)
@pytest.mark.parametrize(
    "names",
    employee_names,
    ids=lambda x: f"employees={', '.join(x)}",
)
@pytest.mark.parametrize("user_name", user_name, ids="user_name={}".format)
@pytest.mark.parametrize("user_role", user_role, ids="user_role={}".format)
@pytest.mark.parametrize("user_team", user_team, ids=lambda x: f"user_team={x.name}")
@pytest.mark.parametrize(
    "team_to_extend", extended_teams, ids="team_to_extend={}".format
)
@pytest.mark.parametrize(
    "manager_probability", manager_probas, ids="manager_probability={}".format
)
@pytest.mark.parametrize(
    "additional_employees", additional_employees, ids="additional_employees={}".format
)
@pytest.mark.parametrize("n_trials", [10], ids="trials={}".format)
def test_team_extend(
    user_team: Team,
    user_role: str,
    user_name: str,
    names: list[str],
    team_to_extend: Team,
    manager_probability: float,
    n_trials: int,
    additional_employees: list[str],
):

    org = simulate_basic_org_structure(
        names=names,
        user_name=user_name,
        user_team=user_team,
        user_role=user_role,
    )
    extend_team(org, additional_employees, team_to_extend, manager_probability)
    assert_on_org_structure(org, names, user_name, user_role, additional_employees)


@pytest.mark.uncollect_if(func=uncollect_if_team_role_mismatch)
@pytest.mark.parametrize(
    "names",
    employee_names,
    ids=lambda x: f"employees={', '.join(x)}",
)
@pytest.mark.parametrize("user_name", user_name, ids="user_name={}".format)
@pytest.mark.parametrize("user_role", user_role, ids="user_role={}".format)
@pytest.mark.parametrize("user_team", user_team, ids=lambda x: f"user_team={x.name}")
@pytest.mark.parametrize(
    "team_to_extend", extended_teams, ids="team_to_extend={}".format
)
@pytest.mark.parametrize(
    "manager_probability", [manager_probas], ids="manager_probability={}".format
)
@pytest.mark.parametrize(
    "additional_employees", additional_employees, ids="additional_employees={}".format
)
@pytest.mark.parametrize("n_trials", [10], ids="trials={}".format)
def test_simulate_org_structure(
    user_team: Team,
    user_role: str,
    user_name: str,
    names: list[str],
    team_to_extend: Team,
    manager_probability: float,
    n_trials: int,
    additional_employees: list[str],
):
    team_definition = {team_to_extend: additional_employees}
    context = ExecutionContext()
    with new_context(context):
        basic_org = simulate_org_structure(
            names, user_name, user_role, user_team, team_definition
        )
        assert_on_org_structure(
            basic_org, names, user_name, user_role, additional_employees, check_db=True
        )
        # TODO: TEST GET CURRENT USER


# test org structure constraints


@pytest.fixture
def valid_team():
    return Team.Engineering


@pytest.fixture
def new_members():
    return ["Alice", "Bob", "Charlie"]


@pytest.fixture
def managers():
    return ["Alice", "Charlie"]


@pytest.fixture
def team_structure():
    return [
        ReportAssignment(manager="Alice", reports=["Bob"]),
        ReportAssignment(manager="Charlie", reports=["Alice"]),
    ]


def test_valid_team_extension(
    valid_team: Team,
    new_members: list[str],
    managers: list[str],
    team_structure: list[ReportAssignment],
):
    model = TeamExtension(
        team=valid_team,
        additional_members=new_members,
        managers=managers,
        structure_constraints=team_structure,
    )
    assert model.team == valid_team
    assert model.additional_members == new_members
    assert model.managers == managers
    assert model.structure_constraints == team_structure


def test_invalid_manager_not_in_additional_members(valid_team: Team):
    with pytest.raises(pydantic.ValidationError) as excinfo:
        TeamExtension(
            team=valid_team,
            additional_members=["Bob", "Charlie"],
            managers=["Alice"],  # Invalid, Alice is not in additional_members
        )
    assert "Alice" in str(excinfo.value)


def test_invalid_structure_constraint_manager_not_in_managers(
    valid_team: Team, new_members: list[str]
):
    with pytest.raises(pydantic.ValidationError) as excinfo:
        TeamExtension(
            team=valid_team,
            additional_members=new_members,
            managers=["Alice"],
            structure_constraints=[
                ReportAssignment(manager="Charlie", reports=["Bob"]),
            ],  # Invalid, Charlie is not in managers
        )
    assert "Charlie" in str(excinfo.value)


def test_invalid_structure_constraint_report_not_in_additional_members(
    valid_team, managers: list[str]
):
    with pytest.raises(pydantic.ValidationError) as excinfo:
        TeamExtension(
            team=valid_team,
            additional_members=["Alice", "Charlie"],
            managers=managers,
            structure_constraints=[
                ReportAssignment(manager="Alice", reports=["Bob"]),
            ],  # Invalid, Bob is not in additional_members
        )
    assert "Bob" in str(excinfo.value)


def test_team_extension_missing_optional_fields(valid_team, new_members: list[str]):
    model = TeamExtension(
        team=valid_team,
        additional_members=new_members,
    )
    assert model.managers is None
    assert model.structure_constraints is None
