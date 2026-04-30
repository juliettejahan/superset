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
    assert spec.supports_multivalues_insert is True


def test_metadata() -> None:
    assert spec.metadata is not None
    assert spec.metadata["description"] == (
        "Vertica is a column-oriented analytics database."
    )
    assert spec.metadata["logo"] == "vertica.png"
    assert spec.metadata["homepage_url"] == "https://www.vertica.com/"
    assert DatabaseCategory.ANALYTICAL_DATABASES in spec.metadata["categories"]
    assert DatabaseCategory.PROPRIETARY in spec.metadata["categories"]
    assert spec.metadata["pypi_packages"] == ["sqlalchemy-vertica-python"]
    assert spec.metadata["default_port"] == 5433
    assert "username" in spec.metadata["parameters"]
    assert "password" in spec.metadata["parameters"]
    assert "host" in spec.metadata["parameters"]
    assert "database" in spec.metadata["parameters"]
    assert "port" in spec.metadata["parameters"]
    assert spec.metadata["connection_string"] == (
        "vertica+vertica_python://{username}:{password}@{host}/{database}"
    )


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


def test_epoch_to_dttm() -> None:
    assert spec.epoch_to_dttm() == "(timestamp 'epoch' + {col} * interval '1 second')"


@pytest.mark.parametrize(
    "native_type,sqla_type,attrs,generic_type,is_dttm",
    [
        # Numeric
        ("SMALLINT", types.SmallInteger, None, GenericDataType.NUMERIC, False),
        ("INTEGER", types.Integer, None, GenericDataType.NUMERIC, False),
        ("BIGINT", types.BigInteger, None, GenericDataType.NUMERIC, False),
        ("DECIMAL", types.Numeric, None, GenericDataType.NUMERIC, False),
        ("NUMERIC", types.Numeric, None, GenericDataType.NUMERIC, False),
        ("REAL", types.REAL, None, GenericDataType.NUMERIC, False),
        ("DOUBLE PRECISION", types.Float, None, GenericDataType.NUMERIC, False),
        ("MONEY", types.Numeric, None, GenericDataType.NUMERIC, False),
        # String
        ("CHAR", types.String, None, GenericDataType.STRING, False),
        ("VARCHAR", types.String, None, GenericDataType.STRING, False),
        ("TEXT", types.String, None, GenericDataType.STRING, False),
        # Temporal
        ("DATE", types.Date, None, GenericDataType.TEMPORAL, True),
        ("TIMESTAMP", types.TIMESTAMP, None, GenericDataType.TEMPORAL, True),
        ("TIME", types.Time, None, GenericDataType.TEMPORAL, True),
        # Boolean
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


def test_time_grain_expressions() -> None:
    time_grains = spec.get_time_grain_expressions()
    assert TimeGrain.SECOND in time_grains
    assert TimeGrain.MINUTE in time_grains
    assert TimeGrain.HOUR in time_grains
    assert TimeGrain.DAY in time_grains
    assert TimeGrain.WEEK in time_grains
    assert TimeGrain.MONTH in time_grains
    assert TimeGrain.QUARTER in time_grains
    assert TimeGrain.YEAR in time_grains
    assert time_grains[TimeGrain.DAY] == "DATE_TRUNC('day', {col})"
    assert time_grains[TimeGrain.MONTH] == "DATE_TRUNC('month', {col})"


def test_fetch_data_no_description() -> None:
    cursor = MagicMock()
    cursor.description = None
    result = spec.fetch_data(cursor)
    assert result == []


def test_fetch_data_with_description() -> None:
    cursor = MagicMock()
    cursor.description = [
        ("col1", "VARCHAR", None, None, None, None, None),
        ("col2", "INTEGER", None, None, None, None, None),
    ]
    cursor.fetchall.return_value = [("a", 1), ("b", 2)]
    result = spec.fetch_data(cursor)
    assert result == [("a", 1), ("b", 2)]


def test_convert_dttm_with_none_type(
    dttm: datetime,  # noqa: F811
) -> None:
    result = spec.convert_dttm(
        target_type="SomeRandomUnsupported",
        dttm=dttm,
    )
    assert result is None
