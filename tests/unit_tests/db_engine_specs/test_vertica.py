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
from sqlalchemy import column, types

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
    assert spec.metadata["default_port"] == 5433
    assert DatabaseCategory.ANALYTICAL_DATABASES in spec.metadata["categories"]
    assert DatabaseCategory.PROPRIETARY in spec.metadata["categories"]
    assert "sqlalchemy-vertica-python" in spec.metadata["pypi_packages"]
    assert "vertica+vertica_python://" in spec.metadata["connection_string"]


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


@pytest.mark.parametrize(
    "time_grain,expected_result",
    [
        ("PT1S", "DATE_TRUNC('second', col)"),
        (
            "PT5S",
            "DATE_TRUNC('minute', col) + INTERVAL '5 seconds' * FLOOR(EXTRACT(SECOND FROM col) / 5)",  # noqa: E501
        ),
        (
            "PT30S",
            "DATE_TRUNC('minute', col) + INTERVAL '30 seconds' * FLOOR(EXTRACT(SECOND FROM col) / 30)",  # noqa: E501
        ),
        ("PT1M", "DATE_TRUNC('minute', col)"),
        (
            "PT5M",
            "DATE_TRUNC('hour', col) + INTERVAL '5 minutes' * FLOOR(EXTRACT(MINUTE FROM col) / 5)",  # noqa: E501
        ),
        (
            "PT10M",
            "DATE_TRUNC('hour', col) + INTERVAL '10 minutes' * FLOOR(EXTRACT(MINUTE FROM col) / 10)",  # noqa: E501
        ),
        (
            "PT15M",
            "DATE_TRUNC('hour', col) + INTERVAL '15 minutes' * FLOOR(EXTRACT(MINUTE FROM col) / 15)",  # noqa: E501
        ),
        (
            "PT30M",
            "DATE_TRUNC('hour', col) + INTERVAL '30 minutes' * FLOOR(EXTRACT(MINUTE FROM col) / 30)",  # noqa: E501
        ),
        ("PT1H", "DATE_TRUNC('hour', col)"),
        ("P1D", "DATE_TRUNC('day', col)"),
        ("P1W", "DATE_TRUNC('week', col)"),
        ("P1M", "DATE_TRUNC('month', col)"),
        ("P3M", "DATE_TRUNC('quarter', col)"),
        ("P1Y", "DATE_TRUNC('year', col)"),
    ],
)
def test_time_grain_expressions(time_grain: str, expected_result: str) -> None:
    actual = str(
        spec.get_timestamp_expr(col=column("col"), pdf=None, time_grain=time_grain)
    )
    assert actual == expected_result


def test_fetch_data_no_description() -> None:
    cursor = MagicMock()
    cursor.description = None
    assert spec.fetch_data(cursor) == []


def test_fetch_data_with_results() -> None:
    cursor = MagicMock()
    cursor.description = [("col1", "varchar"), ("col2", "integer")]
    cursor.fetchall.return_value = [("a", 1), ("b", 2)]
    result = spec.fetch_data(cursor)
    assert result == [("a", 1), ("b", 2)]
