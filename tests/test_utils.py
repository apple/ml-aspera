#
# For licensing see accompanying LICENSE file.
# Copyright © 2025 Apple Inc. All Rights Reserved.
#
import pytest

from aspera.dataset_schema import DataPoint, EditedDataPoint
from aspera.scenario import Guidelines, Scenario


@pytest.fixture
def scenario() -> Scenario:
    return Scenario(
        apps=["app1"],
        query_solution=["app1_soln"],
        runtime_setup=None,
        evaluation=None,
        guidelines=Guidelines(
            generation_labelling=None, runtime_setup=None, evaluation=None
        ),
    )


@pytest.fixture
def datapoint(scenario: Scenario) -> DataPoint:
    return DataPoint(
        **{"query_id": "0", "program": "", "query": "", "scenario": scenario}
    )


@pytest.fixture
def edited_datapoint(scenario: Scenario) -> EditedDataPoint:
    return EditedDataPoint(
        **{
            "query_id": "0",
            "program": "",
            "feedback": "boo",
            "edited_program": "edit",
            "query": "",
            "scenario": scenario,
        }
    )


def test_contains_edits(datapoint: DataPoint):
    assert datapoint.contains_edits in {True, False}


def test_curated_program(datapoint: DataPoint):
    assert datapoint.curated_program == datapoint.program


def test_curated_program_edit(edited_datapoint: EditedDataPoint):
    assert edited_datapoint.curated_program != edited_datapoint.program
