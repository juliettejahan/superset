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
from unittest.mock import Mock, patch

import pytest

from superset.constants import TimeGrain
from superset.db_engine_specs.ascend import AscendEngineSpec as spec  # noqa: N813
from superset.db_engine_specs.base import DatabaseCategory
from superset.db_engine_specs.impala import ImpalaEngineSpec
from superset.models.core import Database
from superset.models.sql_lab import Query
from tests.unit_tests.db_engine_specs.utils import assert_convert_dttm
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


def test_engine_attributes() -> None:
    assert spec.engine == "ascend"
    assert spec.engine_name == "Ascend"
    assert issubclass(spec, ImpalaEngineSpec)


def test_metadata() -> None:
    assert spec.metadata is not None
    assert "Ascend.io" in spec.metadata["description"]
    assert spec.metadata["logo"] == "ascend.webp"
    assert spec.metadata["homepage_url"] == "https://www.ascend.io/"
    assert DatabaseCategory.CLOUD_DATA_WAREHOUSES in spec.metadata["categories"]
    assert DatabaseCategory.ANALYTICAL_DATABASES in spec.metadata["categories"]
    assert DatabaseCategory.HOSTED_OPEN_SOURCE in spec.metadata["categories"]
    assert spec.metadata["pypi_packages"] == ["impyla"]
    assert "ascend://" in spec.metadata["connection_string"]
    assert "auth_mechanism=PLAIN" in spec.metadata["connection_string"]
    assert "use_ssl=true" in spec.metadata["connection_string"]


def test_time_grain_expressions() -> None:
    expressions = spec._time_grain_expressions
    assert expressions[None] == "{col}"
    assert expressions[TimeGrain.SECOND] == "DATE_TRUNC('second', {col})"
    assert expressions[TimeGrain.MINUTE] == "DATE_TRUNC('minute', {col})"
    assert expressions[TimeGrain.HOUR] == "DATE_TRUNC('hour', {col})"
    assert expressions[TimeGrain.DAY] == "DATE_TRUNC('day', {col})"
    assert expressions[TimeGrain.WEEK] == "DATE_TRUNC('week', {col})"
    assert expressions[TimeGrain.MONTH] == "DATE_TRUNC('month', {col})"
    assert expressions[TimeGrain.QUARTER] == "DATE_TRUNC('quarter', {col})"
    assert expressions[TimeGrain.YEAR] == "DATE_TRUNC('year', {col})"


def test_epoch_to_dttm() -> None:
    assert spec.epoch_to_dttm() == "from_unixtime({col})"


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Date", "CAST('2019-01-02' AS DATE)"),
        ("TimeStamp", "CAST('2019-01-02T03:04:05.678900' AS TIMESTAMP)"),
        ("UnknownType", None),
    ],
)
def test_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    assert_convert_dttm(spec, target_type, expected_result, dttm)


def test_get_cancel_query_id() -> None:
    query = Query()

    cursor_mock = Mock()
    last_operation_mock = Mock()
    cursor_mock._last_operation = last_operation_mock

    guid = bytes(reversed(bytes.fromhex("9fbdba20000000006940643a2731718b")))
    last_operation_mock.handle.operationId.guid = guid

    assert (
        spec.get_cancel_query_id(cursor_mock, query)
        == "6940643a2731718b:9fbdba2000000000"
    )


def test_get_cancel_query_id_no_last_operation() -> None:
    query = Query()
    cursor_mock = Mock()
    cursor_mock._last_operation = None

    assert spec.get_cancel_query_id(cursor_mock, query) is None


@patch("requests.post")
def test_cancel_query_success(post_mock: Mock) -> None:
    query = Query()
    database = Database(
        database_name="test_ascend", sqlalchemy_uri="ascend://localhost:21050/default"
    )
    query.database = database

    response_mock = Mock()
    response_mock.status_code = 200
    post_mock.return_value = response_mock

    result = spec.cancel_query(None, query, "6940643a2731718b:9fbdba2000000000")

    post_mock.assert_called_once_with(
        "http://localhost:25000/cancel_query?query_id=6940643a2731718b:9fbdba2000000000",
        timeout=3,
    )
    assert result is True


@patch("requests.post")
def test_cancel_query_failed_status(post_mock: Mock) -> None:
    query = Query()
    database = Database(
        database_name="test_ascend", sqlalchemy_uri="ascend://localhost:21050/default"
    )
    query.database = database

    response_mock = Mock()
    response_mock.status_code = 500
    post_mock.return_value = response_mock

    result = spec.cancel_query(None, query, "6940643a2731718b:9fbdba2000000000")
    assert result is False


@patch("requests.post")
def test_cancel_query_exception(post_mock: Mock) -> None:
    query = Query()
    database = Database(
        database_name="test_ascend", sqlalchemy_uri="ascend://localhost:21050/default"
    )
    query.database = database

    post_mock.side_effect = Exception("Network error")

    result = spec.cancel_query(None, query, "6940643a2731718b:9fbdba2000000000")
    assert result is False


def test_has_implicit_cancel() -> None:
    assert spec.has_implicit_cancel() is False
