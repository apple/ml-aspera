#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import code
import datetime
import uuid

import polars as pl
import pytest

from aspera.apps_implementation.company_directory import Team
from aspera.runtime_state_generation_tools_implementation.utils import (
    fake_email_address,
    fake_video_conference_link,
)
from aspera.simulation.database_schemas import DatabaseNamespace
from aspera.simulation.execution_context import ExecutionContext


@pytest.fixture
def populated_execution_context() -> ExecutionContext:
    """Execution context with a few entries populated in SETTINGS database and SANDBOX database

    Returns:
        A default init ExecutionContext object
    """
    test_context: ExecutionContext = ExecutionContext()
    test_context._dbs[DatabaseNamespace.SANDBOX] = pl.DataFrame(
        [
            {
                "sandbox_message_index": 0,
            },
        ]
    )
    name = "Alex"
    test_context._dbs[DatabaseNamespace.EMPLOYEES] = pl.DataFrame(
        [
            {
                "name": name,
                "email_address": fake_email_address(name),
                "mobile": "+407508222503",
                "team": Team.Engineering,
                "role": "Team Member",
                "video_conference_link": fake_video_conference_link(name),
                "joined_date": datetime.date(2020, 1, 1),
                "birth_date": datetime.date(1992, 1, 1),
                "manager": str(uuid.uuid4()),
                "assistant": str(uuid.uuid4()),
                "reports": [str(uuid.uuid4()) for _ in range(3)],
                "is_user": True,
            },
        ],
        schema=ExecutionContext.dbs_schemas[DatabaseNamespace.EMPLOYEES],
    )
    test_context._dbs[DatabaseNamespace.USER_CALENDAR] = pl.DataFrame(
        [
            {
                "attendees": None,
                "attendees_to_avoid": None,
                "optional_attendees": None,
                "declined_by": None,
                "tentative_attendees": None,
                "subject": None,
                "location": None,
                "starts_at": None,
                "ends_at": None,
                "show_as_status": None,
                "event_importance": None,
                "repeats": None,
                "notes": None,
                "video_link": None,
                "attachments": None,
                "event_id": None,
                "recurrent_event_id": None,
                "original_starts_at": None,
            }
        ],
        schema=ExecutionContext.dbs_schemas[DatabaseNamespace.USER_CALENDAR],
    )
    # Add other attributes
    command = code.compile_command("a=1", symbol="exec")
    assert command is not None
    test_context.interactive_console.runcode(command)
    return test_context


def test_serialization_copying(populated_execution_context: ExecutionContext) -> None:

    serialised = populated_execution_context.to_dict()
    deserialised = ExecutionContext.from_dict(serialised)
    for namespace in DatabaseNamespace:
        assert deserialised._dbs[namespace].equals(
            populated_execution_context._dbs[namespace]
        )
