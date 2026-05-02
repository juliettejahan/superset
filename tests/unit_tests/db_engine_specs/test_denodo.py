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
from sqlalchemy import column, types
from sqlalchemy.engine.url import make_url

from superset.db_engine_specs.denodo import DenodoEngineSpec as spec  # noqa: N813
from superset.errors import ErrorLevel, SupersetError, SupersetErrorType
from superset.utils.core import GenericDataType
from tests.unit_tests.db_engine_specs.utils import (
    assert_column_spec,
    assert_convert_dttm,
)
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Date", "TO_DATE('yyyy-MM-dd', '2019-01-02')"),
        (
            "DateTime",
            "TO_TIMESTAMP('yyyy-MM-dd HH:mm:ss.SSS', '2019-01-02 03:04:05.678')",
        ),
        (
            "TimeStamp",
            "TO_TIMESTAMP('yyyy-MM-dd HH:mm:ss.SSS', '2019-01-02 03:04:05.678')",
        ),
        ("UnknownType", None),
    ],
)
def test_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    """
    DB Eng Specs (denodo): Test ``convert_dttm`` for supported and unknown types.
    """
    assert_convert_dttm(spec, target_type, expected_result, dttm)


def test_convert_dttm_time_type_returns_none(
    dttm: datetime,  # noqa: F811
) -> None:
    """
    DB Eng Specs (denodo): ``convert_dttm`` should return ``None`` for non
    Date / DateTime SQLA types (e.g. ``Time``).
    """
    assert spec.convert_dttm("Time", dttm) is None


def test_convert_dttm_with_db_extra(
    dttm: datetime,  # noqa: F811
) -> None:
    """
    DB Eng Specs (denodo): ``convert_dttm`` should ignore ``db_extra`` and
    produce the same value as without it.
    """
    assert (
        spec.convert_dttm("Date", dttm, db_extra={"foo": "bar"})
        == "TO_DATE('yyyy-MM-dd', '2019-01-02')"
    )
    assert (
        spec.convert_dttm("DateTime", dttm, db_extra={"foo": "bar"})
        == "TO_TIMESTAMP('yyyy-MM-dd HH:mm:ss.SSS', '2019-01-02 03:04:05.678')"
    )


def test_convert_dttm_with_timezone() -> None:
    """
    DB Eng Specs (denodo): ``convert_dttm`` should serialize timezone-aware
    datetimes using the local clock components (``isoformat`` truncated to
    milliseconds).
    """
    dttm_utc = datetime(2024, 6, 15, 12, 30, 45, 123456, tzinfo=timezone.utc)
    assert (
        spec.convert_dttm("DateTime", dttm_utc)
        == "TO_TIMESTAMP('yyyy-MM-dd HH:mm:ss.SSS', "
        "'2024-06-15 12:30:45.123+00:00')"
    )


def test_convert_dttm_zero_microseconds() -> None:
    """
    DB Eng Specs (denodo): ``convert_dttm`` should still emit a millisecond
    component when the source datetime has no microseconds.
    """
    dttm_no_us = datetime(2020, 1, 1, 0, 0, 0)
    assert (
        spec.convert_dttm("DateTime", dttm_no_us)
        == "TO_TIMESTAMP('yyyy-MM-dd HH:mm:ss.SSS', '2020-01-01 00:00:00.000')"
    )


def test_epoch_to_dttm(
    dttm: datetime,  # noqa: F811
) -> None:
    """
    DB Eng Specs (denodo): ``epoch_to_dttm`` returns a Denodo-specific
    millisecond-to-timestamp conversion.
    """
    assert isinstance(dttm, datetime)
    assert (
        spec.epoch_to_dttm().format(col="epoch_dttm") == "GETTIMEFROMMILLIS(epoch_dttm)"
    )


def test_epoch_to_dttm_template_format() -> None:
    """
    DB Eng Specs (denodo): the ``epoch_to_dttm`` template must contain the
    ``{col}`` placeholder so it is usable with ``str.format``.
    """
    template = spec.epoch_to_dttm()
    assert "{col}" in template
    assert template.format(col="my_col") == "GETTIMEFROMMILLIS(my_col)"


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
    attrs: Optional[dict[str, object]],
    generic_type: GenericDataType,
    is_dttm: bool,
) -> None:
    """
    DB Eng Specs (denodo): native column types map to expected SQLA types.
    """
    assert_column_spec(spec, native_type, sqla_type, attrs, generic_type, is_dttm)


def test_get_schema_from_engine_params() -> None:
    """
    DB Eng Specs (denodo): ``get_schema_from_engine_params`` should return
    ``None`` since Denodo URIs do not encode a schema.
    """
    assert (
        spec.get_schema_from_engine_params(
            make_url("denodo://user:password@host/db"), {}
        )
        is None
    )


def test_get_default_catalog() -> None:
    """
    DB Eng Specs (denodo): ``get_default_catalog`` should return ``None``.
    """
    from superset.models.core import Database

    database = Database(
        database_name="denodo",
        sqlalchemy_uri="denodo://user:password@host:9996/db",
    )
    assert spec.get_default_catalog(database) is None


@pytest.mark.parametrize(
    "time_grain,expected_result",
    [
        (None, "col"),
        ("PT1M", "TRUNC(col,'MI')"),
        ("PT1H", "TRUNC(col,'HH')"),
        ("P1D", "TRUNC(col,'DDD')"),
        ("P1W", "TRUNC(col,'W')"),
        ("P1M", "TRUNC(col,'MONTH')"),
        ("P3M", "TRUNC(col,'Q')"),
        ("P1Y", "TRUNC(col,'YEAR')"),
    ],
)
def test_timegrain_expressions(time_grain: Optional[str], expected_result: str) -> None:
    """
    DB Eng Specs (denodo): time grain templates render the expected SQL.
    """
    actual = str(
        spec.get_timestamp_expr(col=column("col"), pdf=None, time_grain=time_grain)
    )
    assert actual == expected_result


def test_engine_metadata() -> None:
    """
    DB Eng Specs (denodo): basic engine metadata sanity checks.
    """
    assert spec.engine == "denodo"
    assert spec.engine_name == "Denodo"
    assert spec.default_driver == "psycopg2"
    assert spec.encryption_parameters == {"sslmode": "require"}
    assert spec.metadata["default_port"] == 9996
    assert spec.sqlalchemy_uri_placeholder.startswith("denodo://")


# ---------------------------------------------------------------------------
# get_datatype
# ---------------------------------------------------------------------------


def test_get_datatype_known_type_code() -> None:
    """
    DB Eng Specs (denodo): ``get_datatype`` should resolve a psycopg2 type
    code to its name (e.g. integer -> ``INTEGER``).
    """
    from psycopg2.extensions import string_types

    type_code, type_obj = next(iter(string_types.items()))
    assert spec.get_datatype(type_code) == type_obj.name


def test_get_datatype_integer_type_code() -> None:
    """
    DB Eng Specs (denodo): the well-known integer OIDs (21, 23) map to
    ``INTEGER``.
    """
    assert spec.get_datatype(23) == "INTEGER"
    assert spec.get_datatype(21) == "INTEGER"


def test_get_datatype_unknown_type_code_returns_none() -> None:
    """
    DB Eng Specs (denodo): an unknown psycopg2 type code returns ``None``.
    """
    assert spec.get_datatype(-1) is None
    assert spec.get_datatype(999_999) is None


def test_get_datatype_non_int_input_returns_none() -> None:
    """
    DB Eng Specs (denodo): non-integer / unhashable-miss inputs return
    ``None`` rather than raising.
    """
    assert spec.get_datatype("not-a-real-oid") is None


# ---------------------------------------------------------------------------
# extract_errors / custom_errors
# ---------------------------------------------------------------------------


def test_extract_errors_invalid_user_password() -> None:
    """
    DB Eng Specs (denodo): invalid credentials map to
    ``CONNECTION_INVALID_USERNAME_ERROR``.
    """
    msg = "FATAL: The username or password is incorrect"
    result = spec.extract_errors(Exception(msg))
    assert len(result) == 1
    err = result[0]
    assert err.error_type == SupersetErrorType.CONNECTION_INVALID_USERNAME_ERROR
    assert err.level == ErrorLevel.ERROR
    assert err.message == "Incorrect username or password."
    assert err.extra is not None
    assert err.extra["engine_name"] == "Denodo"
    assert err.extra["invalid"] == ["username", "password"]


def test_extract_errors_missing_password() -> None:
    """
    DB Eng Specs (denodo): a missing password maps to
    ``CONNECTION_ACCESS_DENIED_ERROR``.
    """
    msg = "FATAL: no password supplied"
    result = spec.extract_errors(Exception(msg))
    assert result[0].error_type == SupersetErrorType.CONNECTION_ACCESS_DENIED_ERROR
    assert result[0].message == "Please enter a password."
    assert result[0].extra is not None
    assert result[0].extra["invalid"] == ["password"]


def test_extract_errors_invalid_hostname() -> None:
    """
    DB Eng Specs (denodo): an unresolved hostname maps to
    ``CONNECTION_INVALID_HOSTNAME_ERROR`` and substitutes the bad hostname.
    """
    msg = (
        'could not translate host name "missing-host" to address: '
        "Name or service not known"
    )
    result = spec.extract_errors(Exception(msg))
    assert result[0].error_type == SupersetErrorType.CONNECTION_INVALID_HOSTNAME_ERROR
    assert result[0].message == 'Hostname "missing-host" cannot be resolved.'
    assert result[0].extra is not None
    assert result[0].extra["invalid"] == ["host"]


def test_extract_errors_port_closed() -> None:
    """
    DB Eng Specs (denodo): a refused TCP connection maps to
    ``CONNECTION_PORT_CLOSED_ERROR``.
    """
    msg = "Is the server running on that host and accepting TCP/IP connections?"
    result = spec.extract_errors(Exception(msg))
    assert result[0].error_type == SupersetErrorType.CONNECTION_PORT_CLOSED_ERROR
    assert result[0].extra is not None
    assert result[0].extra["invalid"] == ["host", "port"]


def test_extract_errors_unknown_database() -> None:
    """
    DB Eng Specs (denodo): an unknown database name maps to
    ``CONNECTION_UNKNOWN_DATABASE_ERROR`` and substitutes the database name.
    """
    msg = "Database 'sales_dw' not found"
    result = spec.extract_errors(Exception(msg))
    assert result[0].error_type == SupersetErrorType.CONNECTION_UNKNOWN_DATABASE_ERROR
    assert result[0].message == 'Unable to connect to database "sales_dw"'
    assert result[0].extra is not None
    assert result[0].extra["invalid"] == ["database"]


def test_extract_errors_forbidden_database() -> None:
    """
    DB Eng Specs (denodo): insufficient privileges map to
    ``CONNECTION_DATABASE_PERMISSIONS_ERROR``.
    """
    msg = "Insufficient privileges to connect to the database 'admin_db'"
    result = spec.extract_errors(Exception(msg))
    assert (
        result[0].error_type == SupersetErrorType.CONNECTION_DATABASE_PERMISSIONS_ERROR
    )
    assert (
        result[0].message
        == 'Unable to connect to database "admin_db": database does not '
        "exist or insufficient permissions"
    )


def test_extract_errors_query_syntax() -> None:
    """
    DB Eng Specs (denodo): a query parsing error maps to ``SYNTAX_ERROR`` and
    captures the offending token.
    """
    msg = "Exception parsing query near 'SELEKT'"
    result = spec.extract_errors(Exception(msg))
    assert result[0].error_type == SupersetErrorType.SYNTAX_ERROR
    assert (
        result[0].message
        == 'Please check your query for syntax errors at or near "SELEKT". '
        "Then, try running your query again."
    )


def test_extract_errors_column_not_exist() -> None:
    """
    DB Eng Specs (denodo): an unknown column maps to
    ``COLUMN_DOES_NOT_EXIST_ERROR`` and substitutes column / view names.
    """
    msg = "Field not found 'foo' in view 'public.bar'"
    result = spec.extract_errors(Exception(msg))
    assert result[0].error_type == SupersetErrorType.COLUMN_DOES_NOT_EXIST_ERROR
    assert result[0].message == 'Column "foo" not found in "public.bar".'


def test_extract_errors_groupby_capability_error() -> None:
    """
    DB Eng Specs (denodo): a GROUP BY capability error maps to
    ``SYNTAX_ERROR`` with a generic invalid-aggregation message.
    """
    msg = "Error computing capabilities of GROUP BY view"
    result = spec.extract_errors(Exception(msg))
    assert result[0].error_type == SupersetErrorType.SYNTAX_ERROR
    assert result[0].message == "Invalid aggregation expression."


def test_extract_errors_groupby_cant_project() -> None:
    """
    DB Eng Specs (denodo): a non-projectable GROUP BY expression maps to
    ``SYNTAX_ERROR`` and captures the offending expression.
    """
    msg = "Invalid GROUP BY expression. 'foo' cannot be projected"
    result = spec.extract_errors(Exception(msg))
    assert result[0].error_type == SupersetErrorType.SYNTAX_ERROR
    assert (
        result[0].message
        == '"foo" is neither an aggregation function nor appears in the '
        "GROUP BY clause."
    )


def test_extract_errors_unmatched_falls_back_to_generic() -> None:
    """
    DB Eng Specs (denodo): error messages that match no custom regex fall
    back to ``GENERIC_DB_ENGINE_ERROR``.
    """
    msg = "totally unrelated explosion"
    result = spec.extract_errors(Exception(msg))
    assert result == [
        SupersetError(
            error_type=SupersetErrorType.GENERIC_DB_ENGINE_ERROR,
            message=msg,
            level=ErrorLevel.ERROR,
            extra={"engine_name": "Denodo"},
        )
    ]


def test_extract_errors_with_context_passes_through() -> None:
    """
    DB Eng Specs (denodo): caller-supplied ``context`` does not break custom
    error handling.
    """
    msg = "FATAL: no password supplied"
    result = spec.extract_errors(Exception(msg), context={"username": "alice"})
    assert result[0].error_type == SupersetErrorType.CONNECTION_ACCESS_DENIED_ERROR
