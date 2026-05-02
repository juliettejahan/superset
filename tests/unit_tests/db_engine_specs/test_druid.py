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

from superset.exceptions import SupersetException
from tests.unit_tests.db_engine_specs.utils import assert_convert_dttm
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Date", "CAST(TIME_PARSE('2019-01-02') AS DATE)"),
        ("DateTime", "TIME_PARSE('2019-01-02T03:04:05')"),
        ("TimeStamp", "TIME_PARSE('2019-01-02T03:04:05')"),
        ("UnknownType", None),
    ],
)
def test_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    from superset.db_engine_specs.druid import DruidEngineSpec as spec  # noqa: N813

    assert_convert_dttm(spec, target_type, expected_result, dttm)


@pytest.mark.parametrize(
    "time_grain,expected_result",
    [
        ("PT1S", "TIME_FLOOR(CAST(col AS TIMESTAMP), 'PT1S')"),
        ("PT5M", "TIME_FLOOR(CAST({col} AS TIMESTAMP), 'PT5M')"),
        (
            "P1W/1970-01-03T00:00:00Z",
            "TIME_SHIFT(TIME_FLOOR(TIME_SHIFT(CAST(col AS TIMESTAMP), 'P1D', 1), 'P1W'), 'P1D', 5)",  # noqa: E501
        ),
        (
            "1969-12-28T00:00:00Z/P1W",
            "TIME_SHIFT(TIME_FLOOR(TIME_SHIFT(CAST(col AS TIMESTAMP), 'P1D', 1), 'P1W'), 'P1D', -1)",  # noqa: E501
        ),
    ],
)
def test_timegrain_expressions(time_grain: str, expected_result: str) -> None:
    """
    DB Eng Specs (druid): Test time grain expressions
    """
    from superset.db_engine_specs.druid import DruidEngineSpec

    assert str(
        DruidEngineSpec.get_timestamp_expr(
            col=column("col"), pdf=None, time_grain=time_grain
        )
    )


def test_extras_without_ssl() -> None:
    from superset.db_engine_specs.druid import DruidEngineSpec
    from tests.integration_tests.fixtures.database import default_db_extra

    database = mock.Mock()
    database.extra = default_db_extra
    database.server_cert = None
    extras = DruidEngineSpec.get_extra_params(database)
    assert "connect_args" not in extras["engine_params"]


def test_extras_with_ssl() -> None:
    from superset.db_engine_specs.druid import DruidEngineSpec
    from tests.integration_tests.fixtures.certificates import ssl_certificate
    from tests.integration_tests.fixtures.database import default_db_extra

    database = mock.Mock()
    database.extra = default_db_extra
    database.server_cert = ssl_certificate
    extras = DruidEngineSpec.get_extra_params(database)
    connect_args = extras["engine_params"]["connect_args"]
    assert connect_args["scheme"] == "https"
    assert "ssl_verify_cert" in connect_args


def test_extras_with_empty_extra() -> None:
    """
    ``get_extra_params`` should treat an empty ``extra`` field as ``{}``.
    """
    from superset.db_engine_specs.druid import DruidEngineSpec

    database = mock.Mock()
    database.extra = ""
    database.server_cert = None
    extras = DruidEngineSpec.get_extra_params(database)
    assert extras == {}


def test_extras_with_invalid_json_raises() -> None:
    """
    ``get_extra_params`` should raise ``SupersetException`` when the database
    ``extra`` payload is not valid JSON.
    """
    from superset.db_engine_specs.druid import DruidEngineSpec

    database = mock.Mock()
    database.extra = "{not valid json"
    database.server_cert = None
    with pytest.raises(SupersetException, match="Unable to parse database extras"):
        DruidEngineSpec.get_extra_params(database)


def test_extras_with_ssl_preserves_existing_engine_params() -> None:
    """
    When ``extra`` already has ``engine_params.connect_args``, those existing
    arguments should be preserved while the SSL-related keys are added.
    """
    from superset.db_engine_specs.druid import DruidEngineSpec
    from tests.integration_tests.fixtures.certificates import ssl_certificate

    database = mock.Mock()
    database.extra = (
        '{"engine_params": {"connect_args": {"existing_key": "existing_value"}}}'
    )
    database.server_cert = ssl_certificate
    extras = DruidEngineSpec.get_extra_params(database)
    connect_args = extras["engine_params"]["connect_args"]
    assert connect_args["existing_key"] == "existing_value"
    assert connect_args["scheme"] == "https"
    assert "ssl_verify_cert" in connect_args


def test_alter_new_orm_column_marks_time_column() -> None:
    """
    ``alter_new_orm_column`` should set ``is_dttm=True`` on Druid's reserved
    ``__time`` column.
    """
    from superset.db_engine_specs.druid import DruidEngineSpec

    orm_col = mock.Mock()
    orm_col.column_name = "__time"
    orm_col.is_dttm = False
    DruidEngineSpec.alter_new_orm_column(orm_col)
    assert orm_col.is_dttm is True


def test_alter_new_orm_column_leaves_other_columns_unchanged() -> None:
    """
    ``alter_new_orm_column`` must not modify non-``__time`` columns.
    """
    from superset.db_engine_specs.druid import DruidEngineSpec

    orm_col = mock.Mock()
    orm_col.column_name = "some_other_column"
    orm_col.is_dttm = False
    DruidEngineSpec.alter_new_orm_column(orm_col)
    assert orm_col.is_dttm is False


def test_epoch_to_dttm() -> None:
    """
    ``epoch_to_dttm`` returns the SQL template that converts seconds since
    epoch into a timestamp.
    """
    from superset.db_engine_specs.druid import DruidEngineSpec

    assert DruidEngineSpec.epoch_to_dttm() == "MILLIS_TO_TIMESTAMP({col} * 1000)"


def test_epoch_ms_to_dttm() -> None:
    """
    ``epoch_ms_to_dttm`` returns the SQL template that converts milliseconds
    since epoch into a timestamp.
    """
    from superset.db_engine_specs.druid import DruidEngineSpec

    assert DruidEngineSpec.epoch_ms_to_dttm() == "MILLIS_TO_TIMESTAMP({col})"


def test_get_dbapi_exception_mapping() -> None:
    """
    The DBAPI exception mapping should map ``requests.ConnectionError`` to
    ``SupersetDBAPIConnectionError``.
    """
    from requests import exceptions as requests_exceptions

    from superset.db_engine_specs.druid import DruidEngineSpec
    from superset.db_engine_specs.exceptions import SupersetDBAPIConnectionError

    mapping = DruidEngineSpec.get_dbapi_exception_mapping()
    assert mapping == {
        requests_exceptions.ConnectionError: SupersetDBAPIConnectionError
    }


def test_engine_metadata() -> None:
    """
    Sanity-check the static engine metadata exposed by ``DruidEngineSpec``.
    """
    from superset.db_engine_specs.druid import DruidEngineSpec

    assert DruidEngineSpec.engine == "druid"
    assert DruidEngineSpec.engine_name == "Apache Druid"
    assert DruidEngineSpec.allows_subqueries is True
    assert DruidEngineSpec.type_probe_needs_row is True


def test_convert_dttm_with_microseconds(dttm: datetime) -> None:  # noqa: F811
    """
    ``convert_dttm`` should drop sub-second precision when emitting
    ``TIME_PARSE`` for ``DateTime`` / ``TIMESTAMP`` targets.
    """
    from superset.db_engine_specs.druid import DruidEngineSpec

    result = DruidEngineSpec.convert_dttm("DateTime", dttm)
    assert result == "TIME_PARSE('2019-01-02T03:04:05')"


def test_convert_dttm_date_uses_iso_date(dttm: datetime) -> None:  # noqa: F811
    """
    ``convert_dttm`` should emit ``CAST(TIME_PARSE(...) AS DATE)`` using the
    ISO date representation of the input ``datetime``.
    """
    from superset.db_engine_specs.druid import DruidEngineSpec

    result = DruidEngineSpec.convert_dttm("DATE", dttm)
    assert result == "CAST(TIME_PARSE('2019-01-02') AS DATE)"
