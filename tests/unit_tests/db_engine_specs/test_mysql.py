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
from decimal import Decimal
from typing import Any, Optional
from unittest.mock import MagicMock, Mock, patch

import pytest
from sqlalchemy import types
from sqlalchemy.dialects.mysql import (
    BIT,
    DECIMAL,
    DOUBLE,
    FLOAT,
    INTEGER,
    LONGTEXT,
    MEDIUMINT,
    MEDIUMTEXT,
    TINYINT,
    TINYTEXT,
)
from sqlalchemy.engine.url import make_url, URL  # noqa: F401

from superset.errors import SupersetErrorType
from superset.utils import json
from superset.utils.core import GenericDataType
from tests.unit_tests.db_engine_specs.utils import (
    assert_column_spec,
    assert_convert_dttm,
)
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


@pytest.mark.parametrize(
    "native_type,sqla_type,attrs,generic_type,is_dttm",
    [
        # Numeric
        ("TINYINT", TINYINT, None, GenericDataType.NUMERIC, False),
        ("SMALLINT", types.SmallInteger, None, GenericDataType.NUMERIC, False),
        ("MEDIUMINT", MEDIUMINT, None, GenericDataType.NUMERIC, False),
        ("INT", INTEGER, None, GenericDataType.NUMERIC, False),
        ("BIGINT", types.BigInteger, None, GenericDataType.NUMERIC, False),
        ("DECIMAL", DECIMAL, None, GenericDataType.NUMERIC, False),
        ("FLOAT", FLOAT, None, GenericDataType.NUMERIC, False),
        ("DOUBLE", DOUBLE, None, GenericDataType.NUMERIC, False),
        ("BIT", BIT, None, GenericDataType.NUMERIC, False),
        # String
        ("CHAR", types.String, None, GenericDataType.STRING, False),
        ("VARCHAR", types.String, None, GenericDataType.STRING, False),
        ("TINYTEXT", TINYTEXT, None, GenericDataType.STRING, False),
        ("MEDIUMTEXT", MEDIUMTEXT, None, GenericDataType.STRING, False),
        ("LONGTEXT", LONGTEXT, None, GenericDataType.STRING, False),
        # Temporal
        ("DATE", types.Date, None, GenericDataType.TEMPORAL, True),
        ("DATETIME", types.DateTime, None, GenericDataType.TEMPORAL, True),
        ("TIMESTAMP", types.TIMESTAMP, None, GenericDataType.TEMPORAL, True),
        ("TIME", types.Time, None, GenericDataType.TEMPORAL, True),
    ],
)
def test_get_column_spec(
    native_type: str,
    sqla_type: type[types.TypeEngine],
    attrs: Optional[dict[str, Any]],
    generic_type: GenericDataType,
    is_dttm: bool,
) -> None:
    from superset.db_engine_specs.mysql import MySQLEngineSpec as spec  # noqa: N813

    assert_column_spec(spec, native_type, sqla_type, attrs, generic_type, is_dttm)


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Date", "STR_TO_DATE('2019-01-02', '%Y-%m-%d')"),
        (
            "DateTime",
            "STR_TO_DATE('2019-01-02 03:04:05.678900', '%Y-%m-%d %H:%i:%s.%f')",
        ),
        ("UnknownType", None),
    ],
)
def test_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    from superset.db_engine_specs.mysql import MySQLEngineSpec as spec  # noqa: N813

    assert_convert_dttm(spec, target_type, expected_result, dttm)


@pytest.mark.parametrize(
    "sqlalchemy_uri,error",
    [
        ("mysql://user:password@host/db1?local_infile=1", True),
        ("mysql+mysqlconnector://user:password@host/db1?allow_local_infile=1", True),
        ("mysql://user:password@host/db1?local_infile=0", True),
        ("mysql+mysqlconnector://user:password@host/db1?allow_local_infile=0", True),
        ("mysql://user:password@host/db1", False),
        ("mysql+mysqlconnector://user:password@host/db1", False),
    ],
)
def test_validate_database_uri(sqlalchemy_uri: str, error: bool) -> None:
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    url = make_url(sqlalchemy_uri)
    if error:
        with pytest.raises(ValueError):  # noqa: PT011
            MySQLEngineSpec.validate_database_uri(url)
        return
    MySQLEngineSpec.validate_database_uri(url)


@pytest.mark.parametrize(
    "sqlalchemy_uri,connect_args,returns",
    [
        ("mysql://user:password@host/db1", {"local_infile": 1}, {"local_infile": 0}),
        (
            "mysql+mysqlconnector://user:password@host/db1",
            {"allow_local_infile": 1},
            {"allow_local_infile": 0},
        ),
        ("mysql://user:password@host/db1", {"local_infile": -1}, {"local_infile": 0}),
        (
            "mysql+mysqlconnector://user:password@host/db1",
            {"allow_local_infile": -1},
            {"allow_local_infile": 0},
        ),
        ("mysql://user:password@host/db1", {"local_infile": 0}, {"local_infile": 0}),
        (
            "mysql+mysqlconnector://user:password@host/db1",
            {"allow_local_infile": 0},
            {"allow_local_infile": 0},
        ),
        (
            "mysql://user:password@host/db1",
            {"param1": "some_value"},
            {"local_infile": 0, "param1": "some_value"},
        ),
        (
            "mysql+mysqlconnector://user:password@host/db1",
            {"param1": "some_value"},
            {"allow_local_infile": 0, "param1": "some_value"},
        ),
        (
            "mysql://user:password@host/db1",
            {"local_infile": 1, "param1": "some_value"},
            {"local_infile": 0, "param1": "some_value"},
        ),
        (
            "mysql+mysqlconnector://user:password@host/db1",
            {"allow_local_infile": 1, "param1": "some_value"},
            {"allow_local_infile": 0, "param1": "some_value"},
        ),
    ],
)
def test_adjust_engine_params(
    sqlalchemy_uri: str, connect_args: dict[str, Any], returns: dict[str, Any]
) -> None:
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    url = make_url(sqlalchemy_uri)
    returned_url, returned_connect_args = MySQLEngineSpec.adjust_engine_params(
        url, connect_args
    )
    assert returned_connect_args == returns


@patch("sqlalchemy.engine.Engine.connect")
def test_get_cancel_query_id(engine_mock: Mock) -> None:
    from superset.db_engine_specs.mysql import MySQLEngineSpec
    from superset.models.sql_lab import Query

    query = Query()
    cursor_mock = engine_mock.return_value.__enter__.return_value
    cursor_mock.fetchone.return_value = ["123"]
    assert MySQLEngineSpec.get_cancel_query_id(cursor_mock, query) == "123"


@patch("sqlalchemy.engine.Engine.connect")
def test_cancel_query(engine_mock: Mock) -> None:
    from superset.db_engine_specs.mysql import MySQLEngineSpec
    from superset.models.sql_lab import Query

    query = Query()
    cursor_mock = engine_mock.return_value.__enter__.return_value
    assert MySQLEngineSpec.cancel_query(cursor_mock, query, "123") is True


@patch("sqlalchemy.engine.Engine.connect")
def test_cancel_query_failed(engine_mock: Mock) -> None:
    from superset.db_engine_specs.mysql import MySQLEngineSpec
    from superset.models.sql_lab import Query

    query = Query()
    cursor_mock = engine_mock.raiseError.side_effect = Exception()
    assert MySQLEngineSpec.cancel_query(cursor_mock, query, "123") is False


def test_get_schema_from_engine_params() -> None:
    """
    Test the ``get_schema_from_engine_params`` method.
    """
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    assert (
        MySQLEngineSpec.get_schema_from_engine_params(
            make_url("mysql://user:password@host/db1"), {}
        )
        == "db1"
    )


@pytest.mark.parametrize(
    "data,description,expected_result",
    [
        (
            [("1.23456", "abc")],
            [("dec", "decimal(12,6)"), ("str", "varchar(3)")],
            [(Decimal("1.23456"), "abc")],
        ),
        (
            [(Decimal("1.23456"), "abc")],
            [("dec", "decimal(12,6)"), ("str", "varchar(3)")],
            [(Decimal("1.23456"), "abc")],
        ),
        (
            [(None, "abc")],
            [("dec", "decimal(12,6)"), ("str", "varchar(3)")],
            [(None, "abc")],
        ),
        (
            [("1.23456", "abc")],
            [("dec", "varchar(255)"), ("str", "varchar(3)")],
            [("1.23456", "abc")],
        ),
    ],
)
def test_column_type_mutator(
    data: list[tuple[Any, ...]],
    description: list[Any],
    expected_result: list[tuple[Any, ...]],
):
    from superset.db_engine_specs.mysql import MySQLEngineSpec as spec  # noqa: N813

    mock_cursor = Mock()
    mock_cursor.fetchall.return_value = data
    mock_cursor.description = description

    assert spec.fetch_data(mock_cursor) == expected_result


def test_engine_metadata() -> None:
    """Engine constants and metadata expose the expected MySQL defaults."""
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    assert MySQLEngineSpec.engine == "mysql"
    assert MySQLEngineSpec.engine_name == "MySQL"
    assert MySQLEngineSpec.default_driver == "mysqldb"
    assert MySQLEngineSpec.max_column_name_length == 64
    assert MySQLEngineSpec.supports_dynamic_schema is True
    assert MySQLEngineSpec.supports_multivalues_insert is True
    assert MySQLEngineSpec.encryption_parameters == {"ssl": "1"}
    assert MySQLEngineSpec.metadata["default_port"] == 3306
    assert "mysqlclient" in MySQLEngineSpec.metadata["pypi_packages"]


def test_disallow_and_enforce_uri_query_params() -> None:
    """Driver-specific guards on local-file inclusion are configured."""
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    assert MySQLEngineSpec.disallow_uri_query_params == {
        "mysqldb": {"local_infile"},
        "mysqlconnector": {"allow_local_infile"},
    }
    assert MySQLEngineSpec.enforce_uri_query_params == {
        "mysqldb": {"local_infile": 0},
        "mysqlconnector": {"allow_local_infile": 0},
    }


def test_time_grain_expressions_defined() -> None:
    """Each supported MySQL time grain maps to a SQL expression."""
    from superset.constants import TimeGrain
    from superset.db_engine_specs.mysql import MySQLEngineSpec

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
        TimeGrain.WEEK_STARTING_MONDAY,
    }
    expressions = MySQLEngineSpec._time_grain_expressions
    assert expected_keys.issubset(set(expressions))
    for key in expected_keys:
        assert "{col}" in expressions[key]


def test_time_grain_expression_formatting() -> None:
    """Time-grain templates accept a column placeholder substitution."""
    from superset.constants import TimeGrain
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    rendered = MySQLEngineSpec._time_grain_expressions[TimeGrain.DAY].format(
        col="my_col"
    )
    assert rendered == "DATE(my_col)"


def test_convert_dttm_returns_none_for_unsupported_type(dttm: datetime) -> None:  # noqa: F811
    """Unknown SQLA types fall through to ``None``."""
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    assert MySQLEngineSpec.convert_dttm("ARRAY", dttm) is None


def test_convert_dttm_db_extra_ignored(dttm: datetime) -> None:  # noqa: F811
    """``db_extra`` does not influence the rendered SQL."""
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    expected = "STR_TO_DATE('2019-01-02', '%Y-%m-%d')"
    assert (
        MySQLEngineSpec.convert_dttm("DATE", dttm, db_extra={"foo": "bar"}) == expected
    )


def test_epoch_to_dttm() -> None:
    """``epoch_to_dttm`` returns the MySQL ``from_unixtime`` template."""
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    assert MySQLEngineSpec.epoch_to_dttm() == "from_unixtime({col})"


def test_epoch_ms_to_dttm_uses_epoch_template() -> None:
    """The base helper for millisecond epochs delegates to ``epoch_to_dttm``."""
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    rendered = MySQLEngineSpec.epoch_ms_to_dttm()
    assert "from_unixtime" in rendered
    assert "1000" in rendered


@pytest.mark.parametrize(
    "schema,expected_database",
    [
        ("public", "public"),
        ("with space", "with%20space"),
        ("schema/with/slash", "schema%2Fwith%2Fslash"),
    ],
)
def test_adjust_engine_params_sets_schema(schema: str, expected_database: str) -> None:
    """A schema argument overrides the URL database with URL-encoded value."""
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    url = make_url("mysql://user:password@host/original_db")
    new_url, _ = MySQLEngineSpec.adjust_engine_params(url, {}, schema=schema)
    assert new_url.database == expected_database


def test_adjust_engine_params_preserves_database_when_no_schema() -> None:
    """Without a schema override the original database is left intact."""
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    url = make_url("mysql://user:password@host/original_db")
    new_url, connect_args = MySQLEngineSpec.adjust_engine_params(url, {})
    assert new_url.database == "original_db"
    assert connect_args == {"local_infile": 0}


def test_get_schema_from_engine_params_unquotes_database() -> None:
    """URL-encoded characters in the database segment round-trip cleanly."""
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    url = make_url("mysql://user:password@host/with%20space")
    assert MySQLEngineSpec.get_schema_from_engine_params(url, {}) == "with space"


class _FakeFieldType:
    """Stand-in for ``MySQLdb.constants.FIELD_TYPE`` with stable hashable values."""

    VAR_STRING = 253
    DECIMAL = 0
    _private = "ignored"


def _fake_mysqldb() -> MagicMock:
    fake = MagicMock()
    fake.constants.FIELD_TYPE = _FakeFieldType
    return fake


def test_get_datatype_with_string_passthrough() -> None:
    """A non-integer string type code is returned verbatim."""
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    MySQLEngineSpec.type_code_map = {}
    try:
        with patch.dict("sys.modules", {"MySQLdb": _fake_mysqldb()}):
            assert MySQLEngineSpec.get_datatype("VARCHAR") == "VARCHAR"
    finally:
        MySQLEngineSpec.type_code_map = {}


def test_get_datatype_with_int_lookup() -> None:
    """Integer type codes are translated through the cached map."""
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    MySQLEngineSpec.type_code_map = {}
    try:
        with patch.dict("sys.modules", {"MySQLdb": _fake_mysqldb()}):
            assert MySQLEngineSpec.get_datatype(253) == "VAR_STRING"
            # Underscore-prefixed attributes are excluded from the cached map.
            assert all(
                not name.startswith("_")
                for name in MySQLEngineSpec.type_code_map.values()
            )
    finally:
        MySQLEngineSpec.type_code_map = {}


def test_get_datatype_returns_none_for_unknown_int() -> None:
    """Unknown integer codes fall through to ``None``."""
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    MySQLEngineSpec.type_code_map = {1: "DECIMAL"}
    try:
        assert MySQLEngineSpec.get_datatype(9999) is None
    finally:
        MySQLEngineSpec.type_code_map = {}


def test_get_datatype_returns_none_for_empty_string() -> None:
    """Empty strings are normalized to ``None``."""
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    MySQLEngineSpec.type_code_map = {1: "DECIMAL"}
    try:
        assert MySQLEngineSpec.get_datatype("") is None
    finally:
        MySQLEngineSpec.type_code_map = {}


def test_get_datatype_caches_field_type_map() -> None:
    """The MySQLdb FIELD_TYPE map is loaded only once and then reused."""
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    MySQLEngineSpec.type_code_map = {}
    try:
        fake_module = _fake_mysqldb()
        with patch.dict("sys.modules", {"MySQLdb": fake_module}):
            assert MySQLEngineSpec.get_datatype(0) == "DECIMAL"
            cached = dict(MySQLEngineSpec.type_code_map)
        # Even after removing the fake module, cached lookups still work
        # because the type_code_map was populated on the first call.
        assert MySQLEngineSpec.get_datatype(253) == "VAR_STRING"
        assert MySQLEngineSpec.type_code_map == cached
    finally:
        MySQLEngineSpec.type_code_map = {}


def test_extract_error_message_with_args_tuple() -> None:
    """Driver-style ``(code, message)`` tuples expose the human-readable text."""
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    exc = Exception(1064, "You have an error in your SQL syntax")
    assert (
        MySQLEngineSpec._extract_error_message(exc)
        == "You have an error in your SQL syntax"
    )


def test_extract_error_message_falls_back_to_str() -> None:
    """When ``args`` is empty the fallback uses ``str(ex)``."""
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    exc = Exception("bare message")
    assert MySQLEngineSpec._extract_error_message(exc) == "bare message"


def test_extract_error_message_handles_non_tuple_args() -> None:
    """When ``args`` is not a tuple the fallback ``str(ex)`` is returned."""
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    class _NonTupleArgsError(Exception):
        def __init__(self) -> None:
            super().__init__("fallback-message")

        @property
        def args(self) -> list[str]:  # type: ignore[override]
            return ["not", "a", "tuple"]

    exc = _NonTupleArgsError()
    # Verify our override truly produces a non-tuple value.
    assert not isinstance(exc.args, tuple)
    assert MySQLEngineSpec._extract_error_message(exc) == "fallback-message"


def test_extract_error_message_single_arg_tuple() -> None:
    """A single-element args tuple keeps using ``str(ex)``."""
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    exc = Exception("only-one")
    assert exc.args == ("only-one",)
    assert MySQLEngineSpec._extract_error_message(exc) == "only-one"


def test_custom_errors_access_denied() -> None:
    """Access-denied messages map to a structured Superset error."""
    from superset.db_engine_specs.mysql import (
        CONNECTION_ACCESS_DENIED_REGEX,
        MySQLEngineSpec,
    )

    raw_message = "Access denied for user 'alice'@'10.0.0.1' (using password: YES)"
    assert CONNECTION_ACCESS_DENIED_REGEX.search(raw_message) is not None

    _, error_type, extras = MySQLEngineSpec.custom_errors[
        CONNECTION_ACCESS_DENIED_REGEX
    ]
    assert error_type == SupersetErrorType.CONNECTION_ACCESS_DENIED_ERROR
    assert extras == {"invalid": ["username", "password"]}


def test_custom_errors_invalid_hostname() -> None:
    """Invalid-hostname messages map to a hostname error."""
    from superset.db_engine_specs.mysql import (
        CONNECTION_INVALID_HOSTNAME_REGEX,
        MySQLEngineSpec,
    )

    raw_message = "Unknown MySQL server host 'badhost' (-2)"
    match = CONNECTION_INVALID_HOSTNAME_REGEX.search(raw_message)
    assert match is not None
    assert match.group("hostname") == "badhost"

    _, error_type, extras = MySQLEngineSpec.custom_errors[
        CONNECTION_INVALID_HOSTNAME_REGEX
    ]
    assert error_type == SupersetErrorType.CONNECTION_INVALID_HOSTNAME_ERROR
    assert extras == {"invalid": ["host"]}


def test_custom_errors_host_down() -> None:
    """Host-down messages map to a host-down error."""
    from superset.db_engine_specs.mysql import (
        CONNECTION_HOST_DOWN_REGEX,
        MySQLEngineSpec,
    )

    raw_message = "Can't connect to MySQL server on 'db.example.com' (110)"
    assert CONNECTION_HOST_DOWN_REGEX.search(raw_message) is not None

    _, error_type, extras = MySQLEngineSpec.custom_errors[CONNECTION_HOST_DOWN_REGEX]
    assert error_type == SupersetErrorType.CONNECTION_HOST_DOWN_ERROR
    assert extras == {"invalid": ["host", "port"]}


def test_custom_errors_unknown_database() -> None:
    """Unknown-database messages map to an unknown-database error."""
    from superset.db_engine_specs.mysql import (
        CONNECTION_UNKNOWN_DATABASE_REGEX,
        MySQLEngineSpec,
    )

    raw_message = "Unknown database 'missing_db'"
    match = CONNECTION_UNKNOWN_DATABASE_REGEX.search(raw_message)
    assert match is not None
    assert match.group("database") == "missing_db"

    _, error_type, extras = MySQLEngineSpec.custom_errors[
        CONNECTION_UNKNOWN_DATABASE_REGEX
    ]
    assert error_type == SupersetErrorType.CONNECTION_UNKNOWN_DATABASE_ERROR
    assert extras == {"invalid": ["database"]}


def test_custom_errors_syntax_error() -> None:
    """SQL syntax errors are surfaced with the raw server text."""
    from superset.db_engine_specs.mysql import MySQLEngineSpec, SYNTAX_ERROR_REGEX

    raw_message = (
        "You have an error in your SQL syntax; check the manual that "
        "corresponds to your MySQL server version for the right syntax to "
        "use near 'SELEC * FROM users' at line 1"
    )
    match = SYNTAX_ERROR_REGEX.search(raw_message)
    assert match is not None
    assert match.group("server_error").startswith("SELEC * FROM users")

    _, error_type, extras = MySQLEngineSpec.custom_errors[SYNTAX_ERROR_REGEX]
    assert error_type == SupersetErrorType.SYNTAX_ERROR
    assert extras == {}


def test_encrypted_extra_sensitive_fields_paths() -> None:
    """The sensitive-field paths only target the AWS IAM block."""
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    assert set(MySQLEngineSpec.encrypted_extra_sensitive_fields) == {
        "$.aws_iam.external_id",
        "$.aws_iam.role_arn",
    }


def test_update_params_no_encrypted_extra_returns_early() -> None:
    """An empty/None ``encrypted_extra`` is a no-op."""
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    database = MagicMock()
    database.encrypted_extra = None
    params: dict[str, Any] = {"existing": 1}

    MySQLEngineSpec.update_params_from_encrypted_extra(database, params)

    assert params == {"existing": 1}


def test_update_params_invalid_json_raises_and_logs() -> None:
    """Malformed ``encrypted_extra`` JSON propagates a decode error."""
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    database = MagicMock()
    database.encrypted_extra = "{not valid json"

    raised: Optional[Exception] = None
    try:
        MySQLEngineSpec.update_params_from_encrypted_extra(database, {})
    except Exception as exc:  # noqa: BLE001
        raised = exc

    assert raised is not None
    assert type(raised).__name__ == "JSONDecodeError"
    # Confirm the underlying class is the simplejson decode error.
    assert raised.__class__.__module__.startswith("simplejson")


def test_update_params_iam_disabled_merges_remaining_keys() -> None:
    """IAM blocks marked disabled are dropped while other keys are merged."""
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    database = MagicMock()
    database.encrypted_extra = json.dumps(
        {"aws_iam": {"enabled": False}, "pool_size": 7}
    )
    params: dict[str, Any] = {}

    MySQLEngineSpec.update_params_from_encrypted_extra(database, params)

    assert params == {"pool_size": 7}


def test_update_params_iam_missing_block_merges_remaining_keys() -> None:
    """Without an aws_iam block the remaining encrypted_extra is merged."""
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    database = MagicMock()
    database.encrypted_extra = json.dumps({"connect_timeout": 5})
    params: dict[str, Any] = {"existing": True}

    MySQLEngineSpec.update_params_from_encrypted_extra(database, params)

    assert params == {"existing": True, "connect_timeout": 5}


def test_update_params_iam_enabled_invokes_aws_helper() -> None:
    """An enabled IAM block delegates to ``AWSIAMAuthMixin._apply_iam_authentication``."""  # noqa: E501
    from superset.db_engine_specs.aws_iam import AWSIAMAuthMixin
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    iam_config = {"enabled": True, "role_arn": "arn", "region": "us-east-1"}
    database = MagicMock()
    database.encrypted_extra = json.dumps({"aws_iam": iam_config, "extra_key": "x"})
    params: dict[str, Any] = {}

    with patch.object(AWSIAMAuthMixin, "_apply_iam_authentication") as mock_apply:
        MySQLEngineSpec.update_params_from_encrypted_extra(database, params)

    mock_apply.assert_called_once()
    call_kwargs = mock_apply.call_args.kwargs
    assert call_kwargs["ssl_args"] == {}
    assert call_kwargs["default_port"] == 3306
    # ``extra_key`` should still be merged into params after IAM handling.
    assert params["extra_key"] == "x"


def test_column_type_mutator_decimal_passthrough_for_non_string() -> None:
    """The DECIMAL mutator is a no-op when the value isn't a string."""
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    mutator = MySQLEngineSpec.column_type_mutators[DECIMAL]
    assert mutator(Decimal("1.5")) == Decimal("1.5")
    assert mutator(None) is None


def test_column_type_mappings_match_expected_generic_types() -> None:
    """A representative subset of MySQL types resolves to the expected generic type."""
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    mapping_by_input = {
        "tinyint": (TINYINT, GenericDataType.NUMERIC),
        "mediumint": (MEDIUMINT, GenericDataType.NUMERIC),
        "decimal(10,2)": (DECIMAL, GenericDataType.NUMERIC),
        "float": (FLOAT, GenericDataType.NUMERIC),
        "double precision": (DOUBLE, GenericDataType.NUMERIC),
        "bit(1)": (BIT, GenericDataType.NUMERIC),
        "tinytext": (TINYTEXT, GenericDataType.STRING),
        "mediumtext": (MEDIUMTEXT, GenericDataType.STRING),
        "longtext": (LONGTEXT, GenericDataType.STRING),
        "INTEGER": (INTEGER, GenericDataType.NUMERIC),
    }

    for input_type, (expected_sqla_cls, expected_generic) in mapping_by_input.items():
        spec = MySQLEngineSpec.get_column_spec(input_type)
        assert spec is not None
        assert isinstance(spec.sqla_type, expected_sqla_cls)
        assert spec.generic_type == expected_generic


def test_validate_database_uri_rejects_disallowed_param_for_connector() -> None:
    """``mysql+mysqlconnector`` rejects ``allow_local_infile`` regardless of value."""
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    url = make_url("mysql+mysqlconnector://user:password@host/db1?allow_local_infile=0")
    with pytest.raises(ValueError, match="Forbidden query parameter"):
        MySQLEngineSpec.validate_database_uri(url)


def test_validate_database_uri_allows_unrelated_params() -> None:
    """Unrelated query parameters are accepted by the URI validator."""
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    url = make_url("mysql://user:password@host/db1?charset=utf8mb4")
    # Should not raise.
    MySQLEngineSpec.validate_database_uri(url)


def test_get_cancel_query_id_executes_connection_id() -> None:
    """``get_cancel_query_id`` issues ``SELECT CONNECTION_ID()`` and returns the row."""
    from superset.db_engine_specs.mysql import MySQLEngineSpec
    from superset.models.sql_lab import Query

    cursor = Mock()
    cursor.fetchone.return_value = (42,)

    result = MySQLEngineSpec.get_cancel_query_id(cursor, Query())

    cursor.execute.assert_called_once_with("SELECT CONNECTION_ID()")
    assert result == 42


def test_cancel_query_runs_kill_connection_statement() -> None:
    """A successful cancel issues ``KILL CONNECTION <id>`` and returns ``True``."""
    from superset.db_engine_specs.mysql import MySQLEngineSpec
    from superset.models.sql_lab import Query

    cursor = Mock()
    assert MySQLEngineSpec.cancel_query(cursor, Query(), "99") is True
    cursor.execute.assert_called_once_with("KILL CONNECTION 99")


def test_cancel_query_returns_false_on_exception() -> None:
    """Driver errors during cancel cause ``cancel_query`` to return ``False``."""
    from superset.db_engine_specs.mysql import MySQLEngineSpec
    from superset.models.sql_lab import Query

    cursor = Mock()
    cursor.execute.side_effect = RuntimeError("boom")
    assert MySQLEngineSpec.cancel_query(cursor, Query(), "99") is False
