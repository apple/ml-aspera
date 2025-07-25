# For licensing see accompanying LICENSE file.
# Copyright (C) 2024-2025 Apple Inc. All Rights Reserved.
#
import code
import contextlib
import copy
import datetime
from enum import StrEnum, auto
from typing import Any, Iterator, Self, cast

import polars as pl
from polars.exceptions import NoDataError
from polars.type_aliases import IntoExprColumn

from aspera.simulation.database_schemas import DATABASE_SCHEMAS, DatabaseNamespace


class RoleType(StrEnum):
    """Types of roles available in the sandbox"""

    SYSTEM = auto()
    USER = auto()
    AGENT = auto()
    EXECUTION_ENVIRONMENT = auto()


class ExecutionContext:
    """Execution Context for sandbox simulation.

    Each ExecutionContext object is a full encapsulation of the sandbox world state, which

    1. Contains database for multiple tools which enables stateful execution
    without listing world state as function arguments.
    2. Contains an InteractiveConsole object used to execute code snippets coming from the agent

    All database also contains a null row as "headguard".

    One should instantiate this class as a global variable
    for all tools to access without taking ExecutionContext as function argument
    """

    # Database schema. Declared as class attributes so that it could be available prior to init
    # As you add more databases / columns, remember to also add their default similarity measure to
    # agent_sandbox.common.evaluation._default_dbs_column_similarities

    dbs_schemas: dict[DatabaseNamespace, dict[str, Any]] = DATABASE_SCHEMAS

    def __init__(
        self,
    ):
        """Init function for ExecutionContext"""
        import random

        random.seed(0)
        # Each database starts with a full null headguard
        # except on "sandbox_message_index" column, which is set to 0.
        self._dbs: dict[str, pl.DataFrame] = {
            namespace: pl.DataFrame(
                {
                    k: None if k != "sandbox_message_index" else 0
                    for k in self.dbs_schemas[namespace]
                },
                schema=self.dbs_schemas[namespace],
            )
            for namespace in self.dbs_schemas
        }
        self.interactive_console = code.InteractiveConsole()
        # the query that is currently executed
        self.query = ""

    def to_dict(self) -> dict[str, Any]:
        """Serializes to a dictionary

        We aim to make this serialization reversible, while still somewhat readable.

        Returns:
            A serialized dict.
        """

        def convert_datetime(value: Any) -> Any:
            if isinstance(value, (datetime.date, datetime.datetime)):
                return value.isoformat()
            return value

        return {
            "_dbs": {
                namespace: [
                    {k: convert_datetime(v) for k, v in record.items()}
                    for record in database.to_dicts()
                ]
                for namespace, database in self._dbs.items()
            },
        }

    @classmethod
    def from_dict(cls, serialized_dict: dict[str, Any]) -> Self:
        """Load a serialized dict produced by to_dict.

        Args:
            serialized_dict:    Serialized dict object.

        Returns:
            ExecutionContext object.
        """

        def convert_datetime(value, schema: dict[str, Any], key: str):
            if schema[key] is pl.Datetime:
                return datetime.datetime.fromisoformat(value) if value else None
            if schema[key] is pl.Date:
                return datetime.date.fromisoformat(value) if value else None
            return value

        execution_context = cls()
        for namespace in serialized_dict["_dbs"]:
            schema = cls.dbs_schemas[namespace]
            print(serialized_dict["_dbs"][namespace])
            records = [
                {k: convert_datetime(v, schema, k) for k, v in record.items()}
                for record in serialized_dict["_dbs"][namespace]
            ]
            execution_context._dbs[DatabaseNamespace[namespace.name]] = pl.from_dicts(
                records, schema=schema
            )
        return execution_context

    @staticmethod
    def headguard_predicate(column_names: set[str]) -> pl.Expr:
        """A polars expression matching headguard rows

        Specifically this looks for rows where all columns expect "sandbox_message_index" are None

        Args:
            column_names:   Column names in the dataframe
        Returns:
            A polars expression matching headguard rows
        """
        # Hacky way to make bitwise and work in a loop
        return pl.lit(True).and_(
            *[
                pl.col(column_name).is_null()
                for column_name in (column_names - {"sandbox_message_index"})
            ]
        )

    @classmethod
    def drop_headguard(cls, dataframe: pl.DataFrame) -> pl.DataFrame:
        """Drops the all None headguard row

        Args:
            dataframe:  Dataframe to drop headguard row from.

        Returns:
            Dataframe with headguard dropped.
        """
        return dataframe.filter(
            ~cls.headguard_predicate(column_names=set(dataframe.columns))
        )

    @property
    def max_sandbox_message_index(self) -> int:
        """Get the current max_sandbox_index, returns -1 when no messages exist

        Returns:

        """
        series = self.drop_headguard(self._dbs[DatabaseNamespace.SANDBOX]).get_column(
            "sandbox_message_index"
        )
        if series.is_empty():
            return -1
        return cast(int, series.max())

    def get_database(
        self,
        namespace: DatabaseNamespace,
        drop_headguard: bool = True,
    ) -> pl.DataFrame:
        """Get a database given the namespace

        Note that the database returned is a subview of the original database.
        Please treat it as an immutable object to avoid unintended effect.
        Use add / remove functions to modify database if needed.

        Parameters
        ----------
        namespace:
            Database namespace
        drop_headguard
            Drop the null headguard entry. Should only be turned off for debugging purposes

        Returns
        -------
            Requested database
        """
        dataframe = self._dbs[namespace]
        if drop_headguard:
            dataframe = self.drop_headguard(dataframe)
        return dataframe

    def add_to_database(
        self,
        namespace: DatabaseNamespace,
        rows: list[dict[str, Any]],
    ) -> None:
        """Add multiple rows to a database.

        Parameters
        ----------
        namespace
            Database namespace
        rows
            List of rows to be added, each item should be a Dict of column and value

        Returns
        -------

        Raises
        ------
        KeyError:   When provided column names in rows does not match given schema
        ValueError: When entry is all None. All None is reserved for headguard
        """
        # Check if column name in rows are found in namespace schema
        rows_column_names = {x for row in rows for x in row.keys()}
        schema_column_names = set(self.dbs_schemas[namespace].keys())
        if rows_column_names - schema_column_names:
            raise KeyError(
                f"Only column names {schema_column_names} are allowed for namespace {namespace}. "
                f"Found unknown column name {rows_column_names - schema_column_names}"
            )
        # Check if values are all None in some rows
        for row in rows:
            if all(
                row[column_name] is None if column_name in row else True
                for column_name in schema_column_names - {"sandbox_message_index"}
            ):
                raise ValueError(
                    "Cannot add row with all None values. "
                    "All None values are reserved for headguard"
                )
        rows = copy.deepcopy(rows)
        self._dbs[namespace] = self._dbs[namespace].vstack(
            pl.DataFrame(rows, schema=self.dbs_schemas[namespace])
        )

    def remove_from_database(
        self,
        namespace: DatabaseNamespace,
        predicate: IntoExprColumn,
    ) -> None:
        """Remove multiple rows from a database.

        Parameters
        ----------
        namespace
            Database namespace
        predicate
            A polars predicate that evaluates to boolean, used to identify the rows to remove

        Returns
        -------

        Raises
        ------
        NoDataError: If no matching rows where found
        KeyError: When attempting to remove entry from SANDBOX database
        """
        if namespace == DatabaseNamespace.SANDBOX:
            raise KeyError("Removal from SANDBOX database is not allowed")
        # Add sandbox_message_index predicate
        if self._dbs[namespace].filter(predicate).is_empty():
            raise NoDataError(f"No db entry matching {predicate=} found")
        # Remove entries that match predicate, except for headguard
        self._dbs[namespace] = self._dbs[namespace].filter(
            ~predicate
            | self.headguard_predicate(column_names=set(self._dbs[namespace].columns))
        )


def _create_global_execution_context() -> ExecutionContext:
    """Set up the global execution context.

    This is a workaround for the circular dependency between `ExecutionContext` and
    `agent_sandbox.tools`. More specifically, in the `ExecutionContext` we want to
    gather all registered tools so that we can scramble the tool names if requested. So
    inside `ExecutionContext.__init__` we gather the tools exposed in
    `agent_sandbox.tools`. Thus, we cannot just use
       _global_execution_context = ExecutionContext()
    at the module level since it would trigger the circular dependency. So what we are
    doing here is a lazily evaluated global variable following
    https://stackoverflow.com/a/54616590 .
    """
    execution_context = ExecutionContext()
    globals()["_global_execution_context"] = execution_context
    return execution_context


def get_current_context() -> ExecutionContext:
    """Getter for global execution context variable

    Returns
        global execution context object

    """
    # Just doing `global _global_execution_context` caused some tests to fail when
    # running them in parallel using pytest-xdist. The error was:
    #   NameError: name '_global_execution_context' is not defined
    # This has to do with how xdist executes the tests in different processes. As a
    # simple workaround we explicitly check if the global variable exists here and if
    # not we create it.
    global_execution_context = globals().get("_global_execution_context")
    if global_execution_context is None:
        return _create_global_execution_context()

    return cast(ExecutionContext, global_execution_context)


def set_current_context(execution_context: ExecutionContext) -> None:
    """Setter for global execution context variable

    Args:
        execution_context: new context to be applied as global execution context

    Returns:

    """
    globals()["_global_execution_context"] = execution_context


@contextlib.contextmanager
def new_context(context: ExecutionContext) -> Iterator[ExecutionContext]:
    """Handy context manager which patches _global_execution_context with context,
    and reverts after context exit

    Parameters
    ----------
    context
        Context to apply

    Returns
    -------

    """
    original_context = get_current_context()
    try:
        set_current_context(context)
        yield context
    # Release resource even when exceptions are raised
    finally:
        # Reset original context
        set_current_context(original_context)
