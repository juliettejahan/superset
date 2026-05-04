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

from datetime import datetime, timezone
from typing import Optional

import pytest
from sqlalchemy import column

from superset.constants import TimeGrain
from superset.db_engine_specs.base import BaseEngineSpec, DatabaseCategory
from superset.db_engine_specs.kylin import KylinEngineSpec as spec  # noqa: N813
from tests.unit_tests.db_engine_specs.utils import assert_convert_dttm
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


# ---------------------------------------------------------------------------
# Engine class-level attributes
# ---------------------------------------------------------------------------
def test_engine_attributes() -> None:
    assert spec.engine == "kylin"
    assert spec.engine_name == "Apache Kylin"
    assert issubclass(spec, BaseEngineSpec)


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------
def test_metadata_top_level_fields() -> None:
    metadata = spec.metadata
    assert isinstance(metadata, dict)
    assert "description" in metadata
    assert "logo" in metadata
    assert "homepage_url" in metadata
    assert "categories" in metadata
    assert "pypi_packages" in metadata
    assert "connection_string" in metadata
    assert "default_port" in metadata


def test_metadata_description_and_branding() -> None:
    metadata = spec.metadata
    assert "Apache Kylin" in metadata["description"]
    assert "OLAP" in metadata["description"]
    assert metadata["logo"] == "apache-kylin.png"
    assert metadata["homepage_url"] == "https://kylin.apache.org/"


def test_metadata_categories() -> None:
    categories = spec.metadata["categories"]
    assert DatabaseCategory.APACHE_PROJECTS in categories
    assert DatabaseCategory.ANALYTICAL_DATABASES in categories
    assert DatabaseCategory.OPEN_SOURCE in categories


def test_metadata_pypi_packages() -> None:
    assert spec.metadata["pypi_packages"] == ["kylinpy"]


def test_metadata_connection_string() -> None:
    connection_string = spec.metadata["connection_string"]
    assert connection_string.startswith("kylin://")
    assert "{username}" in connection_string
    assert "{password}" in connection_string
    assert "{hostname}" in connection_string
    assert "{port}" in connection_string
    assert "{project}" in connection_string


def test_metadata_default_port() -> None:
    assert spec.metadata["default_port"] == 7070


# ---------------------------------------------------------------------------
# Time grain expressions
# ---------------------------------------------------------------------------
def test_time_grain_expressions_keys() -> None:
    expected_keys = {
        None,
        TimeGrain.SECOND,
        TimeGrain.MINUTE,
        TimeGrain.HOUR,
        TimeGrain.DAY,
        TimeGrain.WEEK,
        TimeGrain.MONTH,
        TimeGrain.QUARTER,
        TimeGrain.YEAR,
    }
    assert set(spec._time_grain_expressions.keys()) == expected_keys


def test_time_grain_expressions_default() -> None:
    assert spec._time_grain_expressions[None] == "{col}"


def test_time_grain_expressions_values() -> None:
    expressions = spec._time_grain_expressions
    assert expressions[TimeGrain.SECOND] == (
        "CAST(FLOOR(CAST({col} AS TIMESTAMP) TO SECOND) AS TIMESTAMP)"
    )
    assert expressions[TimeGrain.MINUTE] == (
        "CAST(FLOOR(CAST({col} AS TIMESTAMP) TO MINUTE) AS TIMESTAMP)"
    )
    assert expressions[TimeGrain.HOUR] == (
        "CAST(FLOOR(CAST({col} AS TIMESTAMP) TO HOUR) AS TIMESTAMP)"
    )
    assert expressions[TimeGrain.DAY] == (
        "CAST(FLOOR(CAST({col} AS TIMESTAMP) TO DAY) AS DATE)"
    )
    assert expressions[TimeGrain.WEEK] == (
        "CAST(FLOOR(CAST({col} AS TIMESTAMP) TO WEEK) AS DATE)"
    )
    assert expressions[TimeGrain.MONTH] == (
        "CAST(FLOOR(CAST({col} AS TIMESTAMP) TO MONTH) AS DATE)"
    )
    assert expressions[TimeGrain.QUARTER] == (
        "CAST(FLOOR(CAST({col} AS TIMESTAMP) TO QUARTER) AS DATE)"
    )
    assert expressions[TimeGrain.YEAR] == (
        "CAST(FLOOR(CAST({col} AS TIMESTAMP) TO YEAR) AS DATE)"
    )


@pytest.mark.parametrize(
    "time_grain,expected_sql_fragment",
    [
        (TimeGrain.SECOND, "TO SECOND"),
        (TimeGrain.MINUTE, "TO MINUTE"),
        (TimeGrain.HOUR, "TO HOUR"),
        (TimeGrain.DAY, "TO DAY"),
        (TimeGrain.WEEK, "TO WEEK"),
        (TimeGrain.MONTH, "TO MONTH"),
        (TimeGrain.QUARTER, "TO QUARTER"),
        (TimeGrain.YEAR, "TO YEAR"),
    ],
)
def test_get_timestamp_expr_for_each_grain(
    time_grain: str, expected_sql_fragment: str
) -> None:
    rendered = str(
        spec.get_timestamp_expr(col=column("col"), pdf=None, time_grain=time_grain)
    )
    assert "FLOOR" in rendered
    assert expected_sql_fragment in rendered


def test_get_timestamp_expr_no_grain() -> None:
    rendered = str(
        spec.get_timestamp_expr(col=column("col"), pdf=None, time_grain=None)
    )
    assert rendered == "col"


def test_unsupported_time_grain_raises() -> None:
    with pytest.raises(NotImplementedError):
        spec.get_timestamp_expr(col=column("col"), pdf=None, time_grain="PT2H")


# ---------------------------------------------------------------------------
# convert_dttm
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Date", "CAST('2019-01-02' AS DATE)"),
        ("TimeStamp", "CAST('2019-01-02 03:04:05' AS TIMESTAMP)"),
        ("UnknownType", None),
    ],
)
def test_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    assert_convert_dttm(spec, target_type, expected_result, dttm)


def test_convert_dttm_returns_none_for_empty_target_type(dttm: datetime) -> None:  # noqa: F811
    assert spec.convert_dttm("", dttm) is None


def test_convert_dttm_returns_none_for_unknown_type(dttm: datetime) -> None:  # noqa: F811
    assert spec.convert_dttm("ARRAY", dttm) is None


def test_convert_dttm_returns_none_for_numeric_type(dttm: datetime) -> None:  # noqa: F811
    assert spec.convert_dttm("INTEGER", dttm) is None


def test_convert_dttm_passes_db_extra_without_error(dttm: datetime) -> None:  # noqa: F811
    db_extra = {"some_setting": True}
    assert (
        spec.convert_dttm("Date", dttm, db_extra=db_extra)
        == "CAST('2019-01-02' AS DATE)"
    )


def test_convert_dttm_db_extra_none(dttm: datetime) -> None:  # noqa: F811
    assert (
        spec.convert_dttm("TimeStamp", dttm, db_extra=None)
        == "CAST('2019-01-02 03:04:05' AS TIMESTAMP)"
    )


def test_convert_dttm_drops_microseconds() -> None:
    moment = datetime(2024, 6, 15, 12, 30, 45, 999999)
    assert (
        spec.convert_dttm("TimeStamp", moment)
        == "CAST('2024-06-15 12:30:45' AS TIMESTAMP)"
    )


def test_convert_dttm_date_ignores_time_component() -> None:
    moment = datetime(2024, 6, 15, 23, 59, 59, 999999)
    assert spec.convert_dttm("Date", moment) == "CAST('2024-06-15' AS DATE)"


def test_convert_dttm_handles_timezone_aware_datetime() -> None:
    moment = datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    result = spec.convert_dttm("TimeStamp", moment)
    assert result == "CAST('2024-01-02 03:04:05+00:00' AS TIMESTAMP)"


def test_convert_dttm_handles_timezone_aware_date() -> None:
    moment = datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    assert spec.convert_dttm("Date", moment) == "CAST('2024-01-02' AS DATE)"


def test_convert_dttm_boundary_year() -> None:
    moment = datetime(1, 1, 1, 0, 0, 0)
    assert spec.convert_dttm("Date", moment) == "CAST('0001-01-01' AS DATE)"
    assert (
        spec.convert_dttm("TimeStamp", moment)
        == "CAST('0001-01-01 00:00:00' AS TIMESTAMP)"
    )


@pytest.mark.parametrize(
    "target_type",
    ["DATE", "date", "Date", "DaTe"],
)
def test_convert_dttm_date_case_insensitive(
    target_type: str,
    dttm: datetime,  # noqa: F811
) -> None:
    assert spec.convert_dttm(target_type, dttm) == "CAST('2019-01-02' AS DATE)"


@pytest.mark.parametrize(
    "target_type",
    ["TIMESTAMP", "timestamp", "TimeStamp", "Timestamp"],
)
def test_convert_dttm_timestamp_case_insensitive(
    target_type: str,
    dttm: datetime,  # noqa: F811
) -> None:
    assert (
        spec.convert_dttm(target_type, dttm)
        == "CAST('2019-01-02 03:04:05' AS TIMESTAMP)"
    )


# ---------------------------------------------------------------------------
# Inherited behavior (sanity checks for non-overridden methods)
# ---------------------------------------------------------------------------
def test_get_dbapi_exception_mapping_returns_dict() -> None:
    # KylinEngineSpec does not override this; should return the empty default.
    assert spec.get_dbapi_exception_mapping() == {}


def test_epoch_to_dttm_uses_inherited_default() -> None:
    # KylinEngineSpec does not override `epoch_to_dttm`; the BaseEngineSpec
    # default raises NotImplementedError.
    with pytest.raises(NotImplementedError):
        spec.epoch_to_dttm()
