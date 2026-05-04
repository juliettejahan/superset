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

from __future__ import annotations

from datetime import datetime
from typing import Optional

import pytest
from sqlalchemy import column

from superset.constants import TimeGrain
from superset.db_engine_specs.base import BaseEngineSpec, DatabaseCategory
from superset.db_engine_specs.hologres import HologresEngineSpec as spec  # noqa: N813
from superset.db_engine_specs.postgres import PostgresBaseEngineSpec
from tests.unit_tests.db_engine_specs.utils import assert_convert_dttm
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


def test_engine_attributes() -> None:
    assert spec.engine == "hologres"
    assert spec.engine_name == "Hologres"
    assert spec.default_driver == "psycopg2"


def test_inherits_from_postgres_base() -> None:
    assert issubclass(spec, PostgresBaseEngineSpec)
    assert issubclass(spec, BaseEngineSpec)


def test_supports_multivalues_insert_inherited() -> None:
    # Inherited from PostgresBaseEngineSpec.
    assert spec.supports_multivalues_insert is True


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Date", "TO_DATE('2019-01-02', 'YYYY-MM-DD')"),
        (
            "DateTime",
            "TO_TIMESTAMP('2019-01-02 03:04:05.678900', 'YYYY-MM-DD HH24:MI:SS.US')",
        ),
        (
            "TimeStamp",
            "TO_TIMESTAMP('2019-01-02 03:04:05.678900', 'YYYY-MM-DD HH24:MI:SS.US')",
        ),
        ("UnknownType", None),
        ("", None),
    ],
)
def test_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    assert_convert_dttm(spec, target_type, expected_result, dttm)


def test_convert_dttm_with_db_extra(dttm: datetime) -> None:  # noqa: F811
    # `db_extra` is accepted but unused; passing one should not change behavior.
    assert (
        spec.convert_dttm("Date", dttm, db_extra={"some": "value"})
        == "TO_DATE('2019-01-02', 'YYYY-MM-DD')"
    )


def test_convert_dttm_microseconds_zero() -> None:
    boundary = datetime(2020, 6, 15, 12, 0, 0)
    assert (
        spec.convert_dttm("DateTime", boundary)
        == "TO_TIMESTAMP('2020-06-15 12:00:00.000000', 'YYYY-MM-DD HH24:MI:SS.US')"
    )


def test_convert_dttm_minimum_datetime() -> None:
    boundary = datetime(1, 1, 1, 0, 0, 0)
    assert spec.convert_dttm("Date", boundary) == "TO_DATE('0001-01-01', 'YYYY-MM-DD')"


def test_epoch_to_dttm() -> None:
    assert spec.epoch_to_dttm() == "(timestamp 'epoch' + {col} * interval '1 second')"


def test_epoch_ms_to_dttm() -> None:
    # `epoch_ms_to_dttm` is implemented on `BaseEngineSpec` in terms of
    # `epoch_to_dttm`.
    assert (
        spec.epoch_ms_to_dttm()
        == "(timestamp 'epoch' + ({col}/1000) * interval '1 second')"
    )


def test_get_dbapi_exception_mapping() -> None:
    # `HologresEngineSpec` does not override the default empty mapping.
    assert spec.get_dbapi_exception_mapping() == {}


@pytest.mark.parametrize(
    "time_grain,expected_result",
    [
        (None, "col"),
        (TimeGrain.SECOND, "DATE_TRUNC('second', col)"),
        (TimeGrain.MINUTE, "DATE_TRUNC('minute', col)"),
        (TimeGrain.HOUR, "DATE_TRUNC('hour', col)"),
        (TimeGrain.DAY, "DATE_TRUNC('day', col)"),
        (TimeGrain.WEEK, "DATE_TRUNC('week', col)"),
        (TimeGrain.MONTH, "DATE_TRUNC('month', col)"),
        (TimeGrain.QUARTER, "DATE_TRUNC('quarter', col)"),
        (TimeGrain.YEAR, "DATE_TRUNC('year', col)"),
    ],
)
def test_time_grain_expressions(
    time_grain: Optional[str], expected_result: str
) -> None:
    actual = str(
        spec.get_timestamp_expr(col=column("col"), pdf=None, time_grain=time_grain)
    )
    assert actual == expected_result


def test_time_grain_expressions_keys() -> None:
    expected_subset = {
        None,
        TimeGrain.SECOND,
        TimeGrain.FIVE_SECONDS,
        TimeGrain.THIRTY_SECONDS,
        TimeGrain.MINUTE,
        TimeGrain.FIVE_MINUTES,
        TimeGrain.TEN_MINUTES,
        TimeGrain.FIFTEEN_MINUTES,
        TimeGrain.THIRTY_MINUTES,
        TimeGrain.HOUR,
        TimeGrain.DAY,
        TimeGrain.WEEK,
        TimeGrain.MONTH,
        TimeGrain.QUARTER,
        TimeGrain.YEAR,
    }
    assert expected_subset.issubset(set(spec._time_grain_expressions.keys()))


def test_unsupported_time_grain() -> None:
    with pytest.raises(NotImplementedError):
        spec.get_timestamp_expr(col=column("col"), pdf=None, time_grain="PT2H")


def test_custom_errors_inherited_from_postgres_base() -> None:
    assert spec.custom_errors == PostgresBaseEngineSpec.custom_errors
    assert len(spec.custom_errors) >= 1


def test_metadata_structure() -> None:
    metadata = spec.metadata
    assert "description" in metadata
    assert "logo" in metadata
    assert metadata["logo"] == "hologres.png"
    assert "homepage_url" in metadata
    assert "categories" in metadata
    assert "pypi_packages" in metadata
    assert "connection_string" in metadata
    assert "parameters" in metadata
    assert "default_port" in metadata
    assert "notes" in metadata


def test_metadata_categories() -> None:
    categories = spec.metadata["categories"]
    assert DatabaseCategory.CLOUD_DATA_WAREHOUSES in categories
    assert DatabaseCategory.ANALYTICAL_DATABASES in categories
    assert DatabaseCategory.PROPRIETARY in categories


def test_metadata_pypi_packages() -> None:
    assert spec.metadata["pypi_packages"] == ["psycopg2"]


def test_metadata_default_port() -> None:
    assert spec.metadata["default_port"] == 80


def test_metadata_connection_string() -> None:
    cs = spec.metadata["connection_string"]
    assert cs.startswith("postgresql+psycopg2://")
    assert "{username}" in cs
    assert "{password}" in cs
    assert "{host}" in cs
    assert "{port}" in cs
    assert "{database}" in cs


def test_metadata_parameters() -> None:
    parameters = spec.metadata["parameters"]
    for key in ("username", "password", "host", "port", "database"):
        assert key in parameters
        assert isinstance(parameters[key], str)
        assert parameters[key]


def test_fetch_data_no_description_returns_empty_list() -> None:
    class _Cursor:
        description = None

    assert spec.fetch_data(_Cursor()) == []


def test_fetch_data_with_description_delegates() -> None:
    rows = [(1, "a"), (2, "b")]

    class _Cursor:
        # `BaseEngineSpec.fetch_data` reads the column type from `row[1]`,
        # so the description must include both name and type code.
        description = [("id", "INTEGER"), ("label", "VARCHAR")]
        arraysize: int = 0

        def fetchmany(self, size: int) -> list[tuple[int, str]]:  # noqa: ARG002
            return rows

        def fetchall(self) -> list[tuple[int, str]]:
            return rows

    # `BaseEngineSpec.fetch_data` ultimately returns rows from the cursor.
    assert spec.fetch_data(_Cursor()) == rows
