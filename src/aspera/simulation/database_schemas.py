#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
from enum import StrEnum, auto

import polars as pl

from aspera.apps_implementation.company_directory import Team
from aspera.apps_implementation.time_utils import EventFrequency
from aspera.apps_implementation.work_calendar import ShowAsStatus


class DatabaseNamespace(StrEnum):
    """Namespace for each database"""

    USER_CALENDAR = auto()
    SHARED_CALENDARS = auto()
    EMPLOYEES = auto()
    EMPLOYEE_VACATIONS = auto()
    CONFERENCE_ROOMS = auto()
    CONFERENCE_ROOM_BOOKINGS = auto()
    SANDBOX = auto()
    # here we store the outcome of misc. tools
    # (eg who did the user share calendar with)
    USER_METADATA = auto()


CALENDAR_SCHEMA = {
    "attendees": pl.List(pl.String),
    "attendees_to_avoid": pl.List(pl.String),
    "optional_attendees": pl.List(pl.String),
    "declined_by": pl.List(pl.String),
    "tentative_attendees": pl.List(pl.String),
    "subject": pl.String,
    "location": pl.String,
    "starts_at": pl.Datetime,
    "ends_at": pl.Datetime,
    "show_as_status": pl.Enum([x for x in ShowAsStatus]),
    "event_importance": pl.Enum(["normal", "high"]),
    "repeats": pl.Struct(
        {
            "frequency": pl.Enum([x for x in EventFrequency]),
            "period": pl.Int32,
            "recurs_until": pl.Datetime,
            "max_repetitions": pl.Int32,
            "which_weekday": pl.List(pl.UInt8),
            "which_month_day": pl.List(pl.UInt8),
            "which_year_month": pl.List(pl.UInt8),
            "bysetpos": pl.List(pl.Int32),
            "exclude_occurrence": pl.List(pl.Datetime),
            "occurrence_on_date": pl.Datetime,
        }
    ),
    "notes": pl.String,
    "video_link": pl.String,
    "attachments": pl.List(
        pl.Struct(
            {
                "title": pl.String,
                "content": pl.String,
                "author": pl.List(pl.String),
                "num_pages": pl.Int32,
                "last_modified": pl.Datetime,
                "created_on": pl.Datetime,
                "is_starred": pl.Boolean,
                "folder": pl.String,
            }
        )
    ),
    "event_id": pl.String,
    "recurrent_event_id": pl.String,
    "original_starts_at": pl.Datetime,
}
DATABASE_SCHEMAS = {
    DatabaseNamespace.SANDBOX: {
        "sandbox_message_index": pl.Int32,
    },
    DatabaseNamespace.USER_CALENDAR: CALENDAR_SCHEMA,
    DatabaseNamespace.SHARED_CALENDARS: {**CALENDAR_SCHEMA, "calendar_id": pl.String},
    DatabaseNamespace.EMPLOYEES: {
        "employee_id": pl.String,
        "name": pl.String,
        "email_address": pl.String,
        "mobile": pl.String,
        "team": pl.Enum([x for x in Team]),
        "role": pl.String,
        "video_conference_link": pl.String,
        "joined_date": pl.Date,
        "birth_date": pl.Date,
        "manager": pl.String,
        "assistant": pl.String,
        "reports": pl.List(pl.String),
        "is_user": pl.Boolean,
    },
    DatabaseNamespace.EMPLOYEE_VACATIONS: {
        "employee_id": pl.String,
        "starts": pl.Datetime,
        "ends": pl.Datetime,
    },
    DatabaseNamespace.CONFERENCE_ROOMS: {
        "room_id": pl.String,
        "capacity": pl.UInt8,
        "room_name": pl.String,
    },
    DatabaseNamespace.CONFERENCE_ROOM_BOOKINGS: {
        "room_id": pl.String,
        "booking_id": pl.String,
        "start": pl.Datetime,
        "end": pl.Datetime,
    },
    DatabaseNamespace.USER_METADATA: {
        "calendar_visible_to": pl.List(pl.String),
    },
}
