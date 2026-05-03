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

from superset.constants import TimeGrain
from superset.db_engine_specs.base import DatabaseCategory
from superset.db_engine_specs.firebolt import FireboltEngineSpec
from tests.unit_tests.db_engine_specs.utils import assert_convert_dttm
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


def test_engine_attributes() -> None:
    assert FireboltEngineSpec.engine == "firebolt"
    assert FireboltEngineSpec.engine_name == "Firebolt"
    assert FireboltEngineSpec.default_driver == "firebolt"


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Date", "CAST('2019-01-02' AS DATE)"),
        ("DateTime", "CAST('2019-01-02T03:04:05' AS DATETIME)"),
        ("TimeStamp", "CAST('2019-01-02T03:04:05' AS TIMESTAMP)"),
        ("UnknownType", None),
    ],
)
def test_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    assert_convert_dttm(FireboltEngineSpec, target_type, expected_result, dttm)


def test_convert_dttm_unknown_type_returns_none(
    dttm: datetime,  # noqa: F811
) -> None:
    assert FireboltEngineSpec.convert_dttm(target_type="NotAType", dttm=dttm) is None


def test_convert_dttm_with_db_extra(
    dttm: datetime,  # noqa: F811
) -> None:
    assert (
        FireboltEngineSpec.convert_dttm(
            target_type="Date", dttm=dttm, db_extra={"foo": "bar"}
        )
        == "CAST('2019-01-02' AS DATE)"
    )


def test_convert_dttm_timezone_aware() -> None:
    aware_dttm = datetime(2024, 6, 15, 12, 30, 45, tzinfo=timezone.utc)
    result = FireboltEngineSpec.convert_dttm("DateTime", aware_dttm)
    assert result == "CAST('2024-06-15T12:30:45+00:00' AS DATETIME)"


def test_convert_dttm_timestamp_with_microseconds(
    dttm: datetime,  # noqa: F811
) -> None:
    assert (
        FireboltEngineSpec.convert_dttm("TimeStamp", dttm)
        == "CAST('2019-01-02T03:04:05' AS TIMESTAMP)"
    )


@pytest.mark.parametrize(
    "boundary_dttm,expected_date",
    [
        (datetime(1970, 1, 1, 0, 0, 0), "CAST('1970-01-01' AS DATE)"),
        (datetime(2038, 1, 19, 3, 14, 7), "CAST('2038-01-19' AS DATE)"),
        (datetime(9999, 12, 31, 23, 59, 59), "CAST('9999-12-31' AS DATE)"),
    ],
)
def test_convert_dttm_date_boundary_values(
    boundary_dttm: datetime, expected_date: str
) -> None:
    assert FireboltEngineSpec.convert_dttm("Date", boundary_dttm) == expected_date


def test_epoch_to_dttm() -> None:
    assert (
        FireboltEngineSpec.epoch_to_dttm().format(col="ts_col")
        == "from_unixtime(ts_col)"
    )


def test_epoch_to_dttm_returns_format_string() -> None:
    expression = FireboltEngineSpec.epoch_to_dttm()
    assert "{col}" in expression
    assert expression == "from_unixtime({col})"


@pytest.mark.parametrize(
    "grain,expected_template",
    [
        (TimeGrain.SECOND, "date_trunc('second', CAST({col} AS TIMESTAMP))"),
        (TimeGrain.MINUTE, "date_trunc('minute', CAST({col} AS TIMESTAMP))"),
        (TimeGrain.HOUR, "date_trunc('hour', CAST({col} AS TIMESTAMP))"),
        (TimeGrain.DAY, "date_trunc('day', CAST({col} AS TIMESTAMP))"),
        (TimeGrain.WEEK, "date_trunc('week', CAST({col} AS TIMESTAMP))"),
        (TimeGrain.MONTH, "date_trunc('month', CAST({col} AS TIMESTAMP))"),
        (TimeGrain.QUARTER, "date_trunc('quarter', CAST({col} AS TIMESTAMP))"),
        (TimeGrain.YEAR, "date_trunc('year', CAST({col} AS TIMESTAMP))"),
    ],
)
def test_time_grain_expressions(grain: str, expected_template: str) -> None:
    assert FireboltEngineSpec._time_grain_expressions[grain] == expected_template


def test_time_grain_expression_no_grain() -> None:
    assert FireboltEngineSpec._time_grain_expressions[None] == "{col}"


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
    assert set(FireboltEngineSpec._time_grain_expressions.keys()) == expected_keys


def test_time_grain_expression_format_renders_column() -> None:
    template = FireboltEngineSpec._time_grain_expressions[TimeGrain.DAY]
    rendered = template.format(col="event_time")
    assert rendered == "date_trunc('day', CAST(event_time AS TIMESTAMP))"


def test_get_dbapi_exception_mapping_returns_empty_dict() -> None:
    assert FireboltEngineSpec.get_dbapi_exception_mapping() == {}


def test_metadata_basic_keys() -> None:
    metadata = FireboltEngineSpec.metadata
    assert "description" in metadata
    assert "logo" in metadata
    assert "homepage_url" in metadata
    assert "categories" in metadata
    assert "pypi_packages" in metadata
    assert "connection_string" in metadata
    assert "parameters" in metadata
    assert "drivers" in metadata


def test_metadata_categories_contain_expected_values() -> None:
    categories = FireboltEngineSpec.metadata["categories"]
    assert DatabaseCategory.CLOUD_DATA_WAREHOUSES in categories
    assert DatabaseCategory.ANALYTICAL_DATABASES in categories
    assert DatabaseCategory.PROPRIETARY in categories


def test_metadata_pypi_packages() -> None:
    assert FireboltEngineSpec.metadata["pypi_packages"] == ["firebolt-sqlalchemy"]


def test_metadata_homepage_url() -> None:
    assert FireboltEngineSpec.metadata["homepage_url"] == "https://www.firebolt.io/"


def test_metadata_logo() -> None:
    assert FireboltEngineSpec.metadata["logo"] == "firebolt.png"


def test_metadata_connection_string_format() -> None:
    conn_str = FireboltEngineSpec.metadata["connection_string"]
    assert conn_str.startswith("firebolt://")
    assert "{client_id}" in conn_str
    assert "{client_secret}" in conn_str
    assert "{database}" in conn_str
    assert "{engine_name}" in conn_str
    assert "{account_name}" in conn_str


def test_metadata_parameters_keys() -> None:
    params = FireboltEngineSpec.metadata["parameters"]
    assert set(params.keys()) == {
        "client_id",
        "client_secret",
        "database",
        "engine_name",
        "account_name",
    }


def test_metadata_drivers_structure() -> None:
    drivers = FireboltEngineSpec.metadata["drivers"]
    assert isinstance(drivers, list)
    assert len(drivers) == 1
    driver = drivers[0]
    assert driver["name"] == "firebolt-sqlalchemy"
    assert driver["pypi_package"] == "firebolt-sqlalchemy"
    assert driver["is_recommended"] is True
    assert "{client_id}" in driver["connection_string"]


def test_metadata_description_content() -> None:
    description = FireboltEngineSpec.metadata["description"]
    assert "Firebolt" in description
    assert "cloud data warehouse" in description
