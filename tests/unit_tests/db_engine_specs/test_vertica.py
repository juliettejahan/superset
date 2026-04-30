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

from datetime import datetime
from typing import Any, Optional
from unittest.mock import MagicMock

import pytest
from sqlalchemy import types

from superset.constants import TimeGrain
from superset.db_engine_specs.base import DatabaseCategory
from superset.db_engine_specs.vertica import VerticaEngineSpec as spec  # noqa: N813
from superset.utils.core import GenericDataType
from tests.unit_tests.db_engine_specs.utils import (
    assert_column_spec,
    assert_convert_dttm,
)
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


def test_engine_attributes() -> None:
    assert spec.engine == "vertica"
    assert spec.engine_name == "Vertica"


def test_metadata() -> None:
    meta = spec.metadata
    assert meta is not None
    assert meta["description"] == "Vertica is a column-oriented analytics database."
    assert meta["logo"] == "vertica.png"
    assert meta["homepage_url"] == "https://www.vertica.com/"
    assert DatabaseCategory.ANALYTICAL_DATABASES in meta["categories"]
    assert DatabaseCategory.PROPRIETARY in meta["categories"]
    assert meta["pypi_packages"] == ["sqlalchemy-vertica-python"]
    assert "vertica+vertica_python://" in meta["connection_string"]
    assert meta["default_port"] == 5433
    assert "username" in meta["parameters"]
    assert "password" in meta["parameters"]
    assert "host" in meta["parameters"]
    assert "database" in meta["parameters"]
    assert "port" in meta["parameters"]
    assert meta["notes"] == "Supports load balancer backup host configuration."
    assert meta["docs_url"] == "http://www.vertica.com/"


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
    ],
)
def test_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    assert_convert_dttm(spec, target_type, expected_result, dttm)


def test_convert_dttm_with_none_db_extra(
    dttm: datetime,  # noqa: F811
) -> None:
    result = spec.convert_dttm(target_type="Date", dttm=dttm, db_extra=None)
    assert result == "TO_DATE('2019-01-02', 'YYYY-MM-DD')"


def test_convert_dttm_with_empty_db_extra(
    dttm: datetime,  # noqa: F811
) -> None:
    result = spec.convert_dttm(target_type="Date", dttm=dttm, db_extra={})
    assert result == "TO_DATE('2019-01-02', 'YYYY-MM-DD')"


def test_epoch_to_dttm() -> None:
    assert spec.epoch_to_dttm() == "(timestamp 'epoch' + {col} * interval '1 second')"


@pytest.mark.parametrize(
    "native_type,sqla_type,attrs,generic_type,is_dttm",
    [
        ("SMALLINT", types.SmallInteger, None, GenericDataType.NUMERIC, False),
        ("INTEGER", types.Integer, None, GenericDataType.NUMERIC, False),
        ("BIGINT", types.BigInteger, None, GenericDataType.NUMERIC, False),
        ("DECIMAL", types.Numeric, None, GenericDataType.NUMERIC, False),
        ("NUMERIC", types.Numeric, None, GenericDataType.NUMERIC, False),
        ("REAL", types.REAL, None, GenericDataType.NUMERIC, False),
        ("MONEY", types.Numeric, None, GenericDataType.NUMERIC, False),
        ("CHAR", types.String, None, GenericDataType.STRING, False),
        ("VARCHAR", types.String, None, GenericDataType.STRING, False),
        ("TEXT", types.String, None, GenericDataType.STRING, False),
        ("DATE", types.Date, None, GenericDataType.TEMPORAL, True),
        ("TIMESTAMP", types.TIMESTAMP, None, GenericDataType.TEMPORAL, True),
        ("TIME", types.Time, None, GenericDataType.TEMPORAL, True),
        ("BOOLEAN", types.Boolean, None, GenericDataType.BOOLEAN, False),
    ],
)
def test_get_column_spec(
    native_type: str,
    sqla_type: type[types.TypeEngine],
    attrs: Optional[dict[str, Any]],
    generic_type: GenericDataType,
    is_dttm: bool,
) -> None:
    assert_column_spec(spec, native_type, sqla_type, attrs, generic_type, is_dttm)


def test_get_column_spec_unknown_type() -> None:
    result = spec.get_column_spec("UNKNOWN_TYPE_XYZ")
    assert result is None


@pytest.mark.parametrize(
    "time_grain,expected_expression",
    [
        (None, "{col}"),
        (TimeGrain.SECOND, "DATE_TRUNC('second', {col})"),
        (TimeGrain.MINUTE, "DATE_TRUNC('minute', {col})"),
        (TimeGrain.HOUR, "DATE_TRUNC('hour', {col})"),
        (TimeGrain.DAY, "DATE_TRUNC('day', {col})"),
        (TimeGrain.WEEK, "DATE_TRUNC('week', {col})"),
        (TimeGrain.MONTH, "DATE_TRUNC('month', {col})"),
        (TimeGrain.QUARTER, "DATE_TRUNC('quarter', {col})"),
        (TimeGrain.YEAR, "DATE_TRUNC('year', {col})"),
    ],
)
def test_time_grain_expressions(
    time_grain: Optional[str],
    expected_expression: str,
) -> None:
    assert spec._time_grain_expressions[time_grain] == expected_expression


def test_time_grain_five_seconds() -> None:
    expr = spec._time_grain_expressions[TimeGrain.FIVE_SECONDS]
    assert "DATE_TRUNC('minute', {col})" in expr
    assert "INTERVAL '5 seconds'" in expr


def test_time_grain_thirty_seconds() -> None:
    expr = spec._time_grain_expressions[TimeGrain.THIRTY_SECONDS]
    assert "DATE_TRUNC('minute', {col})" in expr
    assert "INTERVAL '30 seconds'" in expr


def test_time_grain_five_minutes() -> None:
    expr = spec._time_grain_expressions[TimeGrain.FIVE_MINUTES]
    assert "DATE_TRUNC('hour', {col})" in expr
    assert "INTERVAL '5 minutes'" in expr


def test_time_grain_ten_minutes() -> None:
    expr = spec._time_grain_expressions[TimeGrain.TEN_MINUTES]
    assert "DATE_TRUNC('hour', {col})" in expr
    assert "INTERVAL '10 minutes'" in expr


def test_time_grain_fifteen_minutes() -> None:
    expr = spec._time_grain_expressions[TimeGrain.FIFTEEN_MINUTES]
    assert "DATE_TRUNC('hour', {col})" in expr
    assert "INTERVAL '15 minutes'" in expr


def test_time_grain_thirty_minutes() -> None:
    expr = spec._time_grain_expressions[TimeGrain.THIRTY_MINUTES]
    assert "DATE_TRUNC('hour', {col})" in expr
    assert "INTERVAL '30 minutes'" in expr


def test_supports_multivalues_insert() -> None:
    assert spec.supports_multivalues_insert is True


def test_fetch_data_with_empty_cursor() -> None:
    cursor = MagicMock()
    cursor.description = None
    result = spec.fetch_data(cursor)
    assert result == []


def test_fetch_data_with_results() -> None:
    cursor = MagicMock()
    cursor.description = [("col1", "VARCHAR"), ("col2", "VARCHAR")]
    cursor.fetchall.return_value = [("val1", "val2"), ("val3", "val4")]
    result = spec.fetch_data(cursor)
    assert len(result) == 2


def test_fetch_data_with_limit() -> None:
    cursor = MagicMock()
    cursor.description = [("col1", "INTEGER")]
    cursor.fetchall.return_value = [(1,), (2,), (3,)]
    result = spec.fetch_data(cursor, limit=10)
    assert len(result) == 3


def test_get_dbapi_exception_mapping() -> None:
    mapping = spec.get_dbapi_exception_mapping()
    assert isinstance(mapping, dict)


def test_custom_errors_inherited() -> None:
    assert len(spec.custom_errors) > 0
