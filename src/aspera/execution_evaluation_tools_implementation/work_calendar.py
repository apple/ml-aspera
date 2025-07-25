#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
from aspera.apps_implementation.company_directory import Employee
from aspera.simulation.database_schemas import DatabaseNamespace
from aspera.simulation.execution_context import get_current_context


def assert_user_calendar_shared(employees: list[Employee]):
    """Check that the user calendar was indeed shared with the
    intended recipients."""
    context = get_current_context()
    db = context.get_database(namespace=DatabaseNamespace.USER_METADATA)
    visible_to = []
    for record in db.to_dicts():
        visible_to += record["calendar_visible_to"]
    assert sorted(visible_to) == sorted([e.employee_id for e in employees])
