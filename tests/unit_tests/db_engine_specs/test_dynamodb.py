# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
# pylint: disable=invalid-name, unused-argument, import-outside-toplevel, redefined-outer-name

from datetime import datetime, timezone
from typing import Optional

import pytest
from sqlalchemy.engine import create_engine

from superset.constants import TimeGrain
from tests.unit_tests.db_engine_specs.utils import assert_convert_dttm
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("text", "'2019-01-02 03:04:05'"),
        ("Text", "'2019-01-02 03:04:05'"),
        ("TEXT", "'2019-01-02 03:04:05'"),
        ("VARCHAR", "'2019-01-02 03:04:05'"),
        ("dateTime", "'2019-01-02 03:04:05'"),
        ("DateTime", "'2019-01-02 03:04:05'"),
        ("DATETIME", "'2019-01-02 03:04:05'"),
        # TIMESTAMP is a DateTime subclass in SQLAlchemy, so it is formatted too
        ("TIMESTAMP", "'2019-01-02 03:04:05'"),
        ("Date", None),
        ("Integer", None),
        ("unknowntype", None),
        ("", None),
    ],
)
def test_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    """Verify convert_dttm formats String/DateTime targets and ignores others."""
    from superset.db_engine_specs.dynamodb import (
        DynamoDBEngineSpec as spec,  # noqa: N813
    )

    assert_convert_dttm(spec, target_type, expected_result, dttm)


def test_convert_dttm_truncates_microseconds() -> None:
    """convert_dttm uses second-level precision (no microseconds)."""
    from superset.db_engine_specs.dynamodb import DynamoDBEngineSpec

    sample = datetime(2024, 6, 15, 9, 30, 45, 123456)
    assert (
        DynamoDBEngineSpec.convert_dttm("DateTime", sample) == "'2024-06-15 09:30:45'"
    )


def test_convert_dttm_with_timezone_aware_datetime() -> None:
    """convert_dttm preserves timezone offset in the formatted output."""
    from superset.db_engine_specs.dynamodb import DynamoDBEngineSpec

    sample = datetime(2024, 6, 15, 9, 30, 45, tzinfo=timezone.utc)
    assert (
        DynamoDBEngineSpec.convert_dttm("DateTime", sample)
        == "'2024-06-15 09:30:45+00:00'"
    )


def test_convert_dttm_with_db_extra_is_ignored() -> None:
    """convert_dttm accepts and ignores db_extra parameter."""
    from superset.db_engine_specs.dynamodb import DynamoDBEngineSpec

    sample = datetime(2019, 1, 2, 3, 4, 5)
    assert (
        DynamoDBEngineSpec.convert_dttm("Text", sample, db_extra={"foo": "bar"})
        == "'2019-01-02 03:04:05'"
    )
    assert (
        DynamoDBEngineSpec.convert_dttm("Text", sample, db_extra=None)
        == "'2019-01-02 03:04:05'"
    )


def test_convert_dttm_boundary_values() -> None:
    """convert_dttm handles min/max-like datetime boundary values."""
    from superset.db_engine_specs.dynamodb import DynamoDBEngineSpec

    assert (
        DynamoDBEngineSpec.convert_dttm("DateTime", datetime(1970, 1, 1, 0, 0, 0))
        == "'1970-01-01 00:00:00'"
    )
    assert (
        DynamoDBEngineSpec.convert_dttm("DateTime", datetime(9999, 12, 31, 23, 59, 59))
        == "'9999-12-31 23:59:59'"
    )


def test_epoch_to_dttm() -> None:
    """epoch_to_dttm returns a SQL expression converting unix epoch to datetime."""
    from superset.db_engine_specs.dynamodb import DynamoDBEngineSpec

    expr = DynamoDBEngineSpec.epoch_to_dttm()
    assert expr == "datetime({col}, 'unixepoch')"
    assert "{col}" in expr


def test_epoch_ms_to_dttm() -> None:
    """epoch_ms_to_dttm derives from epoch_to_dttm with millisecond scaling."""
    from superset.db_engine_specs.dynamodb import DynamoDBEngineSpec

    expr = DynamoDBEngineSpec.epoch_ms_to_dttm()
    assert expr == "datetime(({col}/1000), 'unixepoch')"


def test_engine_metadata() -> None:
    """Engine name, label, and metadata fields are populated as expected."""
    from superset.db_engine_specs.base import DatabaseCategory
    from superset.db_engine_specs.dynamodb import DynamoDBEngineSpec

    assert DynamoDBEngineSpec.engine == "dynamodb"
    assert DynamoDBEngineSpec.engine_name == "Amazon DynamoDB"

    metadata = DynamoDBEngineSpec.metadata
    assert "PartiQL" in metadata["description"]
    assert metadata["logo"] == "aws.png"
    assert metadata["homepage_url"] == "https://aws.amazon.com/dynamodb/"
    assert metadata["pypi_packages"] == ["pydynamodb"]
    assert "connector=superset" in metadata["connection_string"]
    assert set(metadata["parameters"].keys()) == {
        "aws_access_key_id",
        "aws_secret_access_key",
        "region",
    }
    assert DatabaseCategory.CLOUD_AWS in metadata["categories"]
    assert DatabaseCategory.SEARCH_NOSQL in metadata["categories"]
    assert DatabaseCategory.PROPRIETARY in metadata["categories"]


def test_time_grain_expressions_keys() -> None:
    """All expected time grains are present and parametrized with {col}."""
    from superset.db_engine_specs.dynamodb import DynamoDBEngineSpec

    expressions = DynamoDBEngineSpec._time_grain_expressions
    assert expressions[None] == "{col}"
    expected_grains = {
        TimeGrain.SECOND,
        TimeGrain.MINUTE,
        TimeGrain.HOUR,
        TimeGrain.DAY,
        TimeGrain.WEEK,
        TimeGrain.MONTH,
        TimeGrain.QUARTER,
        TimeGrain.YEAR,
        TimeGrain.WEEK_ENDING_SATURDAY,
        TimeGrain.WEEK_ENDING_SUNDAY,
        TimeGrain.WEEK_STARTING_SUNDAY,
        TimeGrain.WEEK_STARTING_MONDAY,
    }
    for grain in expected_grains:
        assert grain in expressions, f"missing grain: {grain}"
        assert "{col}" in expressions[grain]


@pytest.mark.parametrize(
    "input_dttm,grain,expected",
    [
        ("2022-05-04 05:06:07", TimeGrain.SECOND, "2022-05-04 05:06:07"),
        ("2022-05-04 05:06:07", TimeGrain.MINUTE, "2022-05-04 05:06:00"),
        ("2022-05-04 05:06:07", TimeGrain.HOUR, "2022-05-04 05:00:00"),
        ("2022-05-04 05:06:07", TimeGrain.DAY, "2022-05-04 00:00:00"),
        ("2022-05-04 05:06:07", TimeGrain.WEEK, "2022-05-01 00:00:00"),
        ("2022-05-04 05:06:07", TimeGrain.MONTH, "2022-05-01 00:00:00"),
        ("2022-05-04 05:06:07", TimeGrain.YEAR, "2022-01-01 00:00:00"),
        (
            "2022-05-04 05:06:07",
            TimeGrain.WEEK_ENDING_SATURDAY,
            "2022-05-07 00:00:00",
        ),
        (
            "2022-05-04 05:06:07",
            TimeGrain.WEEK_ENDING_SUNDAY,
            "2022-05-08 00:00:00",
        ),
        (
            "2022-05-04 05:06:07",
            TimeGrain.WEEK_STARTING_SUNDAY,
            "2022-05-01 00:00:00",
        ),
        (
            "2022-05-04 05:06:07",
            TimeGrain.WEEK_STARTING_MONDAY,
            "2022-05-02 00:00:00",
        ),
        ("2022-01-15 05:06:07", TimeGrain.QUARTER, "2022-01-01 00:00:00"),
        ("2022-02-15 05:06:07", TimeGrain.QUARTER, "2022-01-01 00:00:00"),
        ("2022-03-15 05:06:07", TimeGrain.QUARTER, "2022-01-01 00:00:00"),
        ("2022-04-15 05:06:07", TimeGrain.QUARTER, "2022-04-01 00:00:00"),
        ("2022-06-15 05:06:07", TimeGrain.QUARTER, "2022-04-01 00:00:00"),
        ("2022-07-15 05:06:07", TimeGrain.QUARTER, "2022-07-01 00:00:00"),
        ("2022-09-15 05:06:07", TimeGrain.QUARTER, "2022-07-01 00:00:00"),
        ("2022-10-15 05:06:07", TimeGrain.QUARTER, "2022-10-01 00:00:00"),
        ("2022-12-15 05:06:07", TimeGrain.QUARTER, "2022-10-01 00:00:00"),
    ],
)
def test_time_grain_expressions_evaluation(
    input_dttm: str, grain: str, expected: str
) -> None:
    """DynamoDB time grain expressions evaluate correctly (verified via SQLite)."""
    from superset.db_engine_specs.dynamodb import DynamoDBEngineSpec

    engine = create_engine("sqlite://")
    connection = engine.connect()
    connection.execute("CREATE TABLE t (dttm DATETIME)")
    connection.execute("INSERT INTO t VALUES (?)", input_dttm)

    expression = DynamoDBEngineSpec._time_grain_expressions[grain].format(col="dttm")
    sql = f"SELECT {expression} FROM t"  # noqa: S608
    result = connection.execute(sql).scalar()
    assert result == expected


def test_time_grain_expression_default_passthrough() -> None:
    """The None grain passes the column through unchanged."""
    from superset.db_engine_specs.dynamodb import DynamoDBEngineSpec

    engine = create_engine("sqlite://")
    connection = engine.connect()
    connection.execute("CREATE TABLE t (dttm DATETIME)")
    connection.execute("INSERT INTO t VALUES (?)", "2022-05-04 05:06:07")

    expression = DynamoDBEngineSpec._time_grain_expressions[None].format(col="dttm")
    sql = f"SELECT {expression} FROM t"  # noqa: S608
    result = connection.execute(sql).scalar()
    assert result == "2022-05-04 05:06:07"


def test_epoch_to_dttm_evaluation() -> None:
    """epoch_to_dttm produces a SQL expression that converts seconds to UTC datetime."""
    from superset.db_engine_specs.dynamodb import DynamoDBEngineSpec

    engine = create_engine("sqlite://")
    connection = engine.connect()
    expression = DynamoDBEngineSpec.epoch_to_dttm().format(col=0)
    result = connection.execute(f"SELECT {expression}").scalar()  # noqa: S608
    assert result == "1970-01-01 00:00:00"


def test_epoch_ms_to_dttm_evaluation() -> None:
    """epoch_ms_to_dttm converts millisecond epochs to a UTC datetime string."""
    from superset.db_engine_specs.dynamodb import DynamoDBEngineSpec

    engine = create_engine("sqlite://")
    connection = engine.connect()
    expression = DynamoDBEngineSpec.epoch_ms_to_dttm().format(col=1_700_000_000_000)
    result = connection.execute(f"SELECT {expression}").scalar()  # noqa: S608
    assert result == "2023-11-14 22:13:20"
