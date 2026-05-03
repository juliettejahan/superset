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
from typing import Optional
from unittest import mock

import pytest
from sqlalchemy import column

from superset.constants import TimeGrain
from superset.db_engine_specs.base import BaseEngineSpec, DatabaseCategory
from superset.db_engine_specs.exasol import ExasolEngineSpec as spec  # noqa: N813
from tests.unit_tests.db_engine_specs.utils import assert_convert_dttm
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


def test_engine_attributes() -> None:
    assert spec.engine == "exa"
    assert spec.engine_name == "Exasol"
    assert spec.max_column_name_length == 128


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Date", None),
        ("DateTime", None),
        ("TimeStamp", None),
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
    with pytest.raises(NotImplementedError):
        spec.epoch_to_dttm()


def test_get_dbapi_exception_mapping() -> None:
    assert spec.get_dbapi_exception_mapping() == {}


@pytest.mark.parametrize(
    "time_grain,expected_result",
    [
        ("PT1S", "DATE_TRUNC('second', col)"),
        ("PT1M", "DATE_TRUNC('minute', col)"),
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


def test_time_grain_expression_no_grain() -> None:
    actual = str(spec.get_timestamp_expr(col=column("col"), pdf=None, time_grain=None))
    assert actual == "col"


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


def test_unsupported_time_grain() -> None:
    with pytest.raises(NotImplementedError):
        spec.get_timestamp_expr(col=column("col"), pdf=None, time_grain="PT2H")


def test_metadata_structure() -> None:
    metadata = spec.metadata
    assert "description" in metadata
    assert "logo" in metadata
    assert metadata["logo"] == "exasol.png"
    assert "homepage_url" in metadata
    assert metadata["homepage_url"] == "https://www.exasol.com/"
    assert "categories" in metadata
    assert DatabaseCategory.ANALYTICAL_DATABASES in metadata["categories"]
    assert DatabaseCategory.PROPRIETARY in metadata["categories"]
    assert "pypi_packages" in metadata
    assert "sqlalchemy-exasol" in metadata["pypi_packages"]
    assert "connection_string" in metadata
    assert metadata["connection_string"] == "exa+pyodbc://{username}:{password}@{dsn}"
    assert "default_port" in metadata
    assert metadata["default_port"] == 8563
    assert "parameters" in metadata
    assert "drivers" in metadata


def test_metadata_parameters() -> None:
    params = spec.metadata["parameters"]
    assert "username" in params
    assert "password" in params
    assert "dsn" in params


def test_metadata_drivers() -> None:
    drivers = spec.metadata["drivers"]
    assert len(drivers) == 3

    pyodbc_driver = drivers[0]
    assert pyodbc_driver["name"] == "pyodbc"
    assert pyodbc_driver["pypi_package"] == "sqlalchemy-exasol"
    assert pyodbc_driver["is_recommended"] is True
    assert "exa+pyodbc://" in pyodbc_driver["connection_string"]
    assert "notes" in pyodbc_driver

    turbodbc_driver = drivers[1]
    assert turbodbc_driver["name"] == "turbodbc"
    assert turbodbc_driver["pypi_package"] == "sqlalchemy-exasol[turbodbc]"
    assert turbodbc_driver["is_recommended"] is False
    assert "exa+turbodbc://" in turbodbc_driver["connection_string"]

    websocket_driver = drivers[2]
    assert websocket_driver["name"] == "websocket"
    assert websocket_driver["pypi_package"] == "sqlalchemy-exasol[websocket]"
    assert websocket_driver["is_recommended"] is False
    assert "exa+websocket://" in websocket_driver["connection_string"]


def test_fetch_data_unpacks_pyodbc_rows() -> None:
    cursor = mock.MagicMock()
    raw_rows = [(1, "foo"), (2, "bar")]

    with (
        mock.patch.object(BaseEngineSpec, "fetch_data", return_value=raw_rows),
        mock.patch.object(
            spec,
            "pyodbc_rows_to_tuples",
            return_value="converted",
        ) as mock_pyodbc_rows_to_tuples,
    ):
        result = spec.fetch_data(cursor, 10)

    mock_pyodbc_rows_to_tuples.assert_called_once_with(raw_rows)
    assert result == "converted"


def test_fetch_data_default_limit() -> None:
    cursor = mock.MagicMock()
    raw_rows: list[tuple[object, ...]] = []

    with (
        mock.patch.object(
            BaseEngineSpec, "fetch_data", return_value=raw_rows
        ) as mock_super_fetch,
        mock.patch.object(
            spec,
            "pyodbc_rows_to_tuples",
            return_value=raw_rows,
        ),
    ):
        result = spec.fetch_data(cursor)

    mock_super_fetch.assert_called_once_with(cursor, None)
    assert result == raw_rows


def test_fetch_data_passes_through_tuples() -> None:
    """When the cursor returns plain tuples, ``fetch_data`` returns them unchanged."""

    cursor = mock.MagicMock()
    rows = [(1, "a"), (2, "b")]

    with mock.patch.object(BaseEngineSpec, "fetch_data", return_value=rows):
        result = spec.fetch_data(cursor, limit=2)

    assert result == rows


def test_fetch_data_converts_pyodbc_row_objects() -> None:
    """Rows whose class is named ``Row`` (mimicking pyodbc) get unpacked to tuples."""

    class Row:
        def __init__(self, *values: object) -> None:
            self._values = values

        def __iter__(self):  # noqa: ANN204
            return iter(self._values)

    rows = [Row(1, "foo"), Row(2, "bar")]
    cursor = mock.MagicMock()

    with mock.patch.object(BaseEngineSpec, "fetch_data", return_value=rows):
        result = spec.fetch_data(cursor, limit=None)

    assert result == [(1, "foo"), (2, "bar")]
    assert all(isinstance(row, tuple) for row in result)


def test_fetch_data_empty_result() -> None:
    cursor = mock.MagicMock()

    with mock.patch.object(BaseEngineSpec, "fetch_data", return_value=[]):
        result = spec.fetch_data(cursor, limit=5)

    assert result == []
