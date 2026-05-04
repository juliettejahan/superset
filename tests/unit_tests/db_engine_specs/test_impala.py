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
from unittest.mock import MagicMock, Mock, patch

import pytest

from superset.constants import QUERY_EARLY_CANCEL_KEY, TimeGrain
from superset.db_engine_specs.impala import ImpalaEngineSpec as spec  # noqa: N813
from superset.models.core import Database
from superset.models.sql_lab import Query
from tests.unit_tests.db_engine_specs.utils import assert_convert_dttm
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


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


def test_convert_dttm_zero_microseconds() -> None:
    """convert_dttm should still output microseconds for whole seconds."""
    dt = datetime(2024, 6, 15, 12, 30, 45)
    assert (
        spec.convert_dttm("TIMESTAMP", dt)
        == "CAST('2024-06-15T12:30:45.000000' AS TIMESTAMP)"
    )


def test_convert_dttm_unknown_returns_none() -> None:
    """convert_dttm returns None for unsupported target types."""
    dt = datetime(2024, 1, 1, 0, 0, 0)
    assert spec.convert_dttm("ARRAY", dt) is None
    assert spec.convert_dttm("STRUCT", dt) is None
    assert spec.convert_dttm("BOOLEAN", dt) is None


def test_convert_dttm_date_only() -> None:
    """Date target ignores the time part of the datetime."""
    dt = datetime(2020, 12, 31, 23, 59, 59, 999999)
    assert spec.convert_dttm("DATE", dt) == "CAST('2020-12-31' AS DATE)"


def test_epoch_to_dttm() -> None:
    """epoch_to_dttm should return Impala's `from_unixtime` template."""
    assert spec.epoch_to_dttm() == "from_unixtime({col})"


def test_epoch_ms_to_dttm() -> None:
    """epoch_ms_to_dttm uses the inherited default that divides by 1000."""
    assert spec.epoch_ms_to_dttm() == "from_unixtime(({col}/1000))"


def test_get_dbapi_exception_mapping_returns_empty() -> None:
    """Impala inherits the default empty exception mapping."""
    assert spec.get_dbapi_exception_mapping() == {}


def test_get_dbapi_mapped_exception_passes_through() -> None:
    """Without a mapping, the original exception should be returned."""
    original = ValueError("boom")
    assert spec.get_dbapi_mapped_exception(original) is original


@pytest.mark.parametrize(
    "time_grain,expected_expression",
    [
        (None, "{col}"),
        (TimeGrain.MINUTE, "TRUNC({col}, 'MI')"),
        (TimeGrain.HOUR, "TRUNC({col}, 'HH')"),
        (TimeGrain.DAY, "TRUNC({col}, 'DD')"),
        (TimeGrain.WEEK, "TRUNC({col}, 'WW')"),
        (TimeGrain.MONTH, "TRUNC({col}, 'MONTH')"),
        (TimeGrain.QUARTER, "TRUNC({col}, 'Q')"),
        (TimeGrain.YEAR, "TRUNC({col}, 'YYYY')"),
    ],
)
def test_time_grain_expressions(
    time_grain: Optional[str], expected_expression: str
) -> None:
    """Each supported time grain maps to its TRUNC expression."""
    assert spec._time_grain_expressions[time_grain] == expected_expression


def test_engine_metadata() -> None:
    """The engine metadata advertises Impala's defaults."""
    assert spec.engine == "impala"
    assert spec.engine_name == "Apache Impala"
    assert spec.has_query_id_before_execute is False
    assert spec.metadata["default_port"] == 21050
    assert "impyla" in spec.metadata["pypi_packages"]


def test_has_implicit_cancel() -> None:
    """Impala does not implicitly cancel queries on cursor close."""
    assert spec.has_implicit_cancel() is False


def test_get_schema_names() -> None:
    """get_schema_names returns the non-internal schemas reported by SHOW SCHEMAS."""
    inspector = Mock()
    inspector.engine.execute.return_value = [
        ("default",),
        ("analytics",),
        ("_impala_builtins",),
        ("_internal",),
    ]
    schemas = spec.get_schema_names(inspector)
    assert schemas == {"default", "analytics"}
    inspector.engine.execute.assert_called_once_with("SHOW SCHEMAS")


def test_get_schema_names_empty() -> None:
    """get_schema_names handles an empty schema listing."""
    inspector = Mock()
    inspector.engine.execute.return_value = []
    assert spec.get_schema_names(inspector) == set()


def test_execute_calls_execute_async() -> None:
    """execute should delegate to cursor.execute_async."""
    cursor = Mock()
    database = Mock()
    spec.execute(cursor, "SELECT 1", database)
    cursor.execute_async.assert_called_once_with("SELECT 1")


def test_execute_wraps_exceptions() -> None:
    """Exceptions raised during execute_async are mapped via the engine spec."""
    cursor = Mock()
    cursor.execute_async.side_effect = RuntimeError("driver failure")
    database = Mock()
    with pytest.raises(RuntimeError, match="driver failure"):
        spec.execute(cursor, "SELECT 1", database)


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


def test_get_cancel_query_id_returns_none_when_no_operation() -> None:
    """get_cancel_query_id should return None if no last operation is set."""
    query = Query()
    cursor = Mock(spec=[])  # cursor without `_last_operation`
    assert spec.get_cancel_query_id(cursor, query) is None


def test_get_cancel_query_id_returns_none_when_operation_is_falsy() -> None:
    """A falsy `_last_operation` (e.g. None) should also yield None."""
    query = Query()
    cursor = Mock()
    cursor._last_operation = None
    assert spec.get_cancel_query_id(cursor, query) is None


@patch("requests.post")
def test_cancel_query(post_mock: Mock) -> None:
    query = Query()
    database = Database(
        database_name="test_impala", sqlalchemy_uri="impala://localhost:21050/default"
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
def test_cancel_query_failed(post_mock: Mock) -> None:
    query = Query()
    database = Database(
        database_name="test_impala", sqlalchemy_uri="impala://localhost:21050/default"
    )
    query.database = database

    response_mock = Mock()
    response_mock.status_code = 500
    post_mock.return_value = response_mock

    result = spec.cancel_query(None, query, "6940643a2731718b:9fbdba2000000000")

    post_mock.assert_called_once_with(
        "http://localhost:25000/cancel_query?query_id=6940643a2731718b:9fbdba2000000000",
        timeout=3,
    )
    assert result is False


@patch("requests.post")
def test_cancel_query_exception(post_mock: Mock) -> None:
    query = Query()
    database = Database(
        database_name="test_impala", sqlalchemy_uri="impala://localhost:21050/default"
    )
    query.database = database

    post_mock.side_effect = Exception("Network error")

    result = spec.cancel_query(None, query, "6940643a2731718b:9fbdba2000000000")

    assert result is False


@patch("requests.post")
def test_cancel_query_no_response(post_mock: Mock) -> None:
    """A None response from requests.post should produce False."""
    query = Query()
    database = Database(
        database_name="test_impala", sqlalchemy_uri="impala://localhost:21050/default"
    )
    query.database = database
    post_mock.return_value = None
    result = spec.cancel_query(None, query, "deadbeef:cafef00d")
    assert result is False


@patch("superset.db_engine_specs.impala.app")
@patch("superset.db_engine_specs.impala.db")
@patch("superset.db_engine_specs.impala.time.sleep")
def test_handle_cursor_finished_immediately(
    sleep_mock: Mock,
    db_mock: Mock,
    app_mock: Mock,
) -> None:
    """If the cursor reports a terminal state from the start, we exit promptly."""
    cursor = Mock()
    cursor.status.return_value = "FINISHED_STATE"
    query = Query()
    query.id = 1
    query.progress = 0

    spec.handle_cursor(cursor, query)

    cursor.status.assert_called_once_with()
    sleep_mock.assert_not_called()


@patch("superset.db_engine_specs.impala.app")
@patch("superset.db_engine_specs.impala.db")
@patch("superset.db_engine_specs.impala.time.sleep")
def test_handle_cursor_progresses_then_finishes(
    sleep_mock: Mock,
    db_mock: Mock,
    app_mock: Mock,
) -> None:
    """handle_cursor should update progress from logs and stop on finish."""
    cursor = Mock()
    cursor.status.side_effect = ["RUNNING_STATE", "FINISHED_STATE"]
    cursor.get_log.return_value = (
        "Query 5543ffdf692b7d02:f78a944000000000: 42% Complete (17 out of 547)"
    )

    query = MagicMock(spec=Query)
    query.id = 1
    query.progress = 0
    query.extra = {}

    db_mock.session.query.return_value.filter_by.return_value.one.return_value = query
    app_mock.config = {"DB_POLL_INTERVAL_SECONDS": {}}

    spec.handle_cursor(cursor, query)

    assert query.progress == 42
    db_mock.session.commit.assert_called_once()
    sleep_mock.assert_called_once_with(5)


@patch("superset.db_engine_specs.impala.app")
@patch("superset.db_engine_specs.impala.db")
@patch("superset.db_engine_specs.impala.time.sleep")
def test_handle_cursor_progress_not_higher_skips_commit(
    sleep_mock: Mock,
    db_mock: Mock,
    app_mock: Mock,
) -> None:
    """If progress did not increase, no commit should be issued."""
    cursor = Mock()
    cursor.status.side_effect = ["RUNNING_STATE", "FINISHED_STATE"]
    cursor.get_log.return_value = (
        "Query 5543ffdf692b7d02:f78a944000000000: 10% Complete"
    )

    query = MagicMock(spec=Query)
    query.id = 1
    query.progress = 50  # already higher than the parsed value
    query.extra = {}

    db_mock.session.query.return_value.filter_by.return_value.one.return_value = query
    app_mock.config = {"DB_POLL_INTERVAL_SECONDS": {"impala": 1}}

    spec.handle_cursor(cursor, query)

    assert query.progress == 50
    db_mock.session.commit.assert_not_called()
    sleep_mock.assert_called_once_with(1)


@patch("superset.db_engine_specs.impala.app")
@patch("superset.db_engine_specs.impala.db")
@patch("superset.db_engine_specs.impala.time.sleep")
def test_handle_cursor_get_log_exception(
    sleep_mock: Mock,
    db_mock: Mock,
    app_mock: Mock,
) -> None:
    """A failure in get_log() should be swallowed and treated as an empty log."""
    cursor = Mock()
    cursor.status.side_effect = ["RUNNING_STATE", "FINISHED_STATE"]
    cursor.get_log.side_effect = Exception("kaboom")

    query = MagicMock(spec=Query)
    query.id = 1
    query.progress = 0
    query.extra = {}

    db_mock.session.query.return_value.filter_by.return_value.one.return_value = query
    app_mock.config = {"DB_POLL_INTERVAL_SECONDS": {}}

    spec.handle_cursor(cursor, query)

    db_mock.session.commit.assert_not_called()
    sleep_mock.assert_called_once_with(5)


@patch("superset.db_engine_specs.impala.app")
@patch("superset.db_engine_specs.impala.db")
@patch("superset.db_engine_specs.impala.time.sleep")
def test_handle_cursor_get_log_returns_none(
    sleep_mock: Mock,
    db_mock: Mock,
    app_mock: Mock,
) -> None:
    """A None log from get_log() should be normalized to empty string."""
    cursor = Mock()
    cursor.status.side_effect = ["RUNNING_STATE", "FINISHED_STATE"]
    cursor.get_log.return_value = None

    query = MagicMock(spec=Query)
    query.id = 1
    query.progress = 0
    query.extra = {}

    db_mock.session.query.return_value.filter_by.return_value.one.return_value = query
    app_mock.config = {"DB_POLL_INTERVAL_SECONDS": {}}

    spec.handle_cursor(cursor, query)

    db_mock.session.commit.assert_not_called()
    sleep_mock.assert_called_once_with(5)


@patch("superset.db_engine_specs.impala.app")
@patch("superset.db_engine_specs.impala.db")
@patch("superset.db_engine_specs.impala.time.sleep")
def test_handle_cursor_log_without_progress_match(
    sleep_mock: Mock,
    db_mock: Mock,
    app_mock: Mock,
) -> None:
    """A non-matching log line should not update progress."""
    cursor = Mock()
    cursor.status.side_effect = ["RUNNING_STATE", "FINISHED_STATE"]
    cursor.get_log.return_value = "irrelevant log line without progress info"

    query = MagicMock(spec=Query)
    query.id = 1
    query.progress = 0
    query.extra = {}

    db_mock.session.query.return_value.filter_by.return_value.one.return_value = query
    app_mock.config = {"DB_POLL_INTERVAL_SECONDS": {}}

    spec.handle_cursor(cursor, query)

    assert query.progress == 0
    db_mock.session.commit.assert_not_called()


@patch("superset.db_engine_specs.impala.app")
@patch("superset.db_engine_specs.impala.db")
@patch("superset.db_engine_specs.impala.time.sleep")
def test_handle_cursor_early_cancel(
    sleep_mock: Mock,
    db_mock: Mock,
    app_mock: Mock,
) -> None:
    """An early-cancel flag should trigger cancel_operation and break the loop."""
    cursor = Mock()
    cursor.status.return_value = "RUNNING_STATE"

    query = MagicMock(spec=Query)
    query.id = 1
    query.progress = 0
    query.extra = {QUERY_EARLY_CANCEL_KEY: True}

    db_mock.session.query.return_value.filter_by.return_value.one.return_value = query
    app_mock.config = {"DB_POLL_INTERVAL_SECONDS": {}}

    spec.handle_cursor(cursor, query)

    cursor.cancel_operation.assert_called_once_with()
    cursor.close_operation.assert_called_once_with()
    cursor.close.assert_called_once_with()
    sleep_mock.assert_not_called()


@patch("superset.db_engine_specs.impala.app")
@patch("superset.db_engine_specs.impala.db")
@patch("superset.db_engine_specs.impala.time.sleep")
def test_handle_cursor_status_raises(
    sleep_mock: Mock,
    db_mock: Mock,
    app_mock: Mock,
) -> None:
    """A failure on the very first status() call returns silently."""
    cursor = Mock()
    cursor.status.side_effect = Exception("driver disconnect")
    query = Query()
    query.id = 1
    query.progress = 0

    assert spec.handle_cursor(cursor, query) is None
    sleep_mock.assert_not_called()
