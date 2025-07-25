#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import datetime

from aspera.apps_implementation.company_directory import (
    find_employee,
    get_current_user,
    get_vacation_schedule,
)
from aspera.apps_implementation.time_utils import TimeInterval
from aspera.runtime_state_generation_tools_implementation.company_directory import (
    simulate_org_structure,
    simulate_vacation_schedule,
)
from aspera.simulation.execution_context import ExecutionContext, new_context


def test_simulate_vacation_schedule():

    context = ExecutionContext()
    with new_context(context=context):
        default_names = ["Pete", "Alex"]
        simulate_org_structure(
            default_names,
        )
        # simulate some holidays for Pete
        start_1 = datetime.datetime(year=2024, month=7, day=7, hour=8, minute=0)
        end_1 = datetime.datetime(year=2024, month=8, day=2, hour=5, minute=0)
        start_2 = datetime.datetime(year=2024, month=12, day=20, hour=8, minute=0)
        end_2 = datetime.datetime(year=2025, month=1, day=2, hour=5, minute=0)
        pete = find_employee("Pete")[0]
        expected_schedule = [
            TimeInterval(start=start_1, end=end_1),
            TimeInterval(start=start_2, end=end_2),
        ]
        simulate_vacation_schedule(pete, time_off=expected_schedule)
        schedule = get_vacation_schedule(pete)
        user_vacation = get_vacation_schedule(get_current_user())
        assert user_vacation is None
        assert schedule == expected_schedule
