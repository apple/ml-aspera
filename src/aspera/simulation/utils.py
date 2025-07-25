#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
from typing import Any, Literal, Protocol, Sequence, runtime_checkable

import polars as pl
from rapidfuzz import fuzz, process, utils


class NotGiven:
    """
    A sentinel singleton class used to distinguish omitted keyword arguments
    from those passed in with the value None (which may have different behavior).

    For example:

    ```py
    def search(
        a: Union[int, NotGiven, None] = NotGiven(),
        b: Union[int, NotGiven, None] = NotGiven(),
    ): ...


    search(a=1, b=2)  # Search in database with constraint a == 1, b==2
    search(a=None, b=3)  # Search in database with constraint a == None, b==3
    search(b=4)  # Search in database with constraint b==4
    ```
    """

    def __bool__(self) -> Literal[False]:
        return False

    def __repr__(self) -> str:
        return "NOT_GIVEN"


NOT_GIVEN = NotGiven()


@runtime_checkable
class DataframeFilterMethodType(Protocol):
    """Callable type def for Dataframe filtering functions."""

    def __call__(
        self,
        dataframe: pl.DataFrame,
        column_name: str,
        value: Any,
        **kwargs: int | Any,
    ) -> pl.DataFrame: ...


def exact_match_filter_dataframe(
    dataframe: pl.DataFrame, column_name: str, value: Any, **kwargs: int | Any
) -> pl.DataFrame:
    """Filter dataframe by exact matching value on 1 column

    Parameters
    ----------
        dataframe:      Dataframe to filter
        column_name:    Name of column
        value:          Value to match against

    Returns
    -------
        Filtered dataframe

    """
    if value is None:
        return dataframe.filter(pl.col(column_name).is_null())
    return dataframe.filter(pl.col(column_name) == value)


def subsequence_filter_dataframe(
    dataframe: pl.DataFrame, column_name: str, value: Any, **kwargs: int | Any
) -> pl.DataFrame:
    """Filter dataframe for rows that contains value as a subsequence in column_name

    Parameters
    ----------
        dataframe:      Dataframe to filter
        column_name:    Name of column
        value:          Value to match against

    Returns
    -------
        Filtered dataframe

    """
    return dataframe.filter(pl.col(column_name).str.contains(str(value)))


def lt_eq_filter_dataframe(
    dataframe: pl.DataFrame, column_name: str, value: Any, **kwargs: int | Any
) -> pl.DataFrame:
    """Filter dataframe for rows whose column_name are less than or equal to value.
    The value must implement __lt__.

    Parameters
    ----------
        dataframe:      Dataframe to filter
        column_name:    Name of column
        value:          Upperbound of column value

    Returns
    -------
        Filtered dataframe

    """
    return dataframe.filter(pl.col(column_name) <= value)


def gt_eq_filter_dataframe(
    dataframe: pl.DataFrame, column_name: str, value: Any, **kwargs: int | Any
) -> pl.DataFrame:
    """Filter dataframe for rows whose column_name are greater than or equal to value.
    The value must implement __gt__.

    Parameters
    ----------
        dataframe:      Dataframe to filter
        column_name:    Name of column
        value:          Lowerbound of column value

    Returns
    -------
        Filtered dataframe

    """
    return dataframe.filter(pl.col(column_name) >= value)


def fuzzy_match_filter_dataframe(
    dataframe: pl.DataFrame, column_name: str, value: Any, **kwargs: int | Any
) -> pl.DataFrame:
    """Filter dataframe by fuzzy matching string value on 1 column. Backed by fuzz.WRatio

    Parameters
    ----------
        dataframe:      Dataframe to filter
        column_name:    Name of column
        value:          Value to match against
        **kwargs:       Additional kwargs for matching, for example
                        threshold for fuzz.WRatio, only entries above the threshold are selected

    Returns
    -------
        Filtered dataframe
    """
    threshold = kwargs.get("threshold", 90)
    # Find the indices of top scored rows, process.extract returns a tuple of (string, score, index)
    matches = process.extract(
        query=value,
        choices=dataframe.get_column(column_name),
        processor=utils.default_process,
        scorer=fuzz.WRatio,
        score_cutoff=threshold,
        limit=50,
    )
    return dataframe[[x[-1] for x in matches]]


def is_sequence_member_filter_dataframe(
    dataframe: pl.DataFrame, column_name: str, value: Sequence, **kwargs: int | Any
):
    """Filter dataframe for rows whose column_name is in value.

    Parameters
    ----------
        dataframe:      Dataframe to filter
        column_name:    Name of column
        value:          A sequence of values against the value in column_name should be matched.

    Returns
    -------
        Filtered dataframe
    """
    # TODO: TEST ME
    return dataframe.filter(pl.col(column_name).is_in(value))


def filter_dataframe(
    dataframe: pl.DataFrame,
    filter_criteria: list[tuple[str, Any, DataframeFilterMethodType]],
) -> pl.DataFrame:
    """Filter dataframe given a filter method, column name and target value

    Parameters
    ----------
    dataframe
        Dataframe to filter
    filter_criteria
        A list of filter constraints on each column,
        each tuple contains [column_name, value, filter_method]

    Returns
    -------
        Filtered dataframe
    """
    if all(x[1] is NOT_GIVEN for x in filter_criteria):
        raise ValueError(
            f"No search criteria are given. At least one search criteria should be provided among "
            f"{tuple(x[0] for x in filter_criteria)}"
        )
    for column_name, filter_value, filter_method in filter_criteria:
        if filter_value is not NOT_GIVEN:
            dataframe = filter_method(
                dataframe=dataframe,
                column_name=column_name,
                value=filter_value,
            )
    return dataframe
