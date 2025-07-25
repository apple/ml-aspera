#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
from aspera.apps_implementation.company_directory import (
    Employee,
    Team,
    find_employee,
    find_manager_of,
    find_reports_of,
    find_team_of,
    get_all_employees,
    get_assistant,
    get_current_user,
)
from aspera.runtime_state_generation_tools_implementation.company_directory import (
    simulate_org_structure,
)
from aspera.simulation.execution_context import ExecutionContext, new_context


def test_find_team_of():

    context = ExecutionContext()
    with new_context(context=context):
        org = simulate_org_structure(
            [], teams_to_extend={Team.Engineering: ["John", "David", "Rhodes"]}
        )
        user = get_current_user()
        user_team = find_team_of(user)
        expected_members = sorted([m.name for m in org.teams[Team.Engineering]])
        actual_members = sorted([m.name for m in user_team])
        assert expected_members == actual_members


def test_find_reports_of():

    import random

    random.seed(42)
    context = ExecutionContext()
    with new_context(context=context):
        org = simulate_org_structure(
            [],
            user_team=Team.Engineering,
            user_role="Manager",
            teams_to_extend={Team.Engineering: ["John", "Travolta", "Fairy", "Colper"]},
        )
        user = get_current_user()
        user_reports = find_reports_of(user)
        colper = find_employee("Colper")[0]
        colper_reports = find_reports_of(colper)
        expected_user_reports, expected_colper_reports = [], []
        assert colper_reports
        assert user_reports
        for employee in org.teams[Team.Engineering]:
            if employee.manager.employee_id == user.employee_id:
                expected_user_reports.append(
                    Employee(name=employee.name, employee_id=employee.employee_id)
                )
            elif employee.manager.employee_id == colper.employee_id:
                expected_colper_reports.append(
                    Employee(name=employee.name, employee_id=employee.employee_id)
                )
        expected_user_reports.sort(key=lambda x: x.name)
        expected_colper_reports.sort(key=lambda x: x.name)
        assert user_reports == expected_user_reports
        assert colper_reports == expected_colper_reports


def test_find_manager():

    context = ExecutionContext()
    with new_context(context=context):
        org = simulate_org_structure(
            [],
            user_team=Team.Engineering,
            user_role="Manager",
            teams_to_extend={Team.Engineering: ["John", "Travolta", "Fairy", "Colper"]},
        )
        [cfo_name] = [e.name for e in org.leadership if e.role == "CFO"]
        [ceo_name] = [e.name for e in org.leadership if e.role == "CEO"]
        cfo = find_employee(cfo_name)[0]
        ceo = find_employee(ceo_name)[0]
        actual_manager = find_manager_of(cfo)
        assert actual_manager == ceo


def test_get_assistant():

    context = ExecutionContext()
    with new_context(context=context):
        employee_names = [
            "A",
            "B",
            "C",
            "D",
            "E",
            "F",
            "G",
            "H",
            "I",
            "J",
            "K",
            "L",
            "M",
            "N",
            "O",
        ]
        org = simulate_org_structure(employee_names)
        user = get_current_user()
        assert get_assistant(user) is None
        [ceo_name] = [e.name for e in org.leadership if e.role == "CEO"]
        ceo = find_employee(ceo_name)[0]
        assert get_assistant(ceo).name in employee_names


def test_get_all_employees():

    context = ExecutionContext()
    with new_context(context=context):
        employee_names = [
            "A",
            "Alex",  # add user
            "B",
            "C",
            "D",
            "E",
            "F",
            "G",
            "H",
            "I",
            "J",
            "K",
            "L",
            "M",
            "N",
            "O",
        ]
        simulate_org_structure(employee_names)
        company = get_all_employees()
        assert employee_names == [e.name for e in company]
