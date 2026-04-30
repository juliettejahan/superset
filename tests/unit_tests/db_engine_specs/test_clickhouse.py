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

import pandas as pd
import pytest
from sqlalchemy import column, types
from sqlalchemy.engine.url import make_url
from sqlalchemy.types import (
    Boolean,
    Date,
    DateTime,
    DECIMAL,
    Float,
    Integer,
    String,
    TypeEngine,
)
from urllib3.connection import HTTPConnection
from urllib3.exceptions import NewConnectionError

from superset.db_engine_specs.base import BasicParametersType
from superset.db_engine_specs.clickhouse import (
    ClickHouseBaseEngineSpec,
    ClickHouseConnectEngineSpec,
    ClickHouseEngineSpec,
)
from superset.db_engine_specs.exceptions import SupersetDBAPIDatabaseError
from superset.utils.core import GenericDataType
from tests.unit_tests.db_engine_specs.utils import (
    assert_column_spec,
    assert_convert_dttm,
)
from tests.unit_tests.fixtures.common import dttm  # noqa: F401

# ---------------------------------------------------------------------------
# ClickHouseBaseEngineSpec tests
# ---------------------------------------------------------------------------


def test_base_class_attributes() -> None:
    assert ClickHouseBaseEngineSpec.time_groupby_inline is True
    assert ClickHouseBaseEngineSpec.supports_multivalues_insert is True


def test_epoch_to_dttm() -> None:
    assert ClickHouseBaseEngineSpec.epoch_to_dttm() == "{col}"


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Date", "toDate('2019-01-02')"),
        ("DateTime", "toDateTime('2019-01-02 03:04:05')"),
        ("UnknownType", None),
    ],
)
def test_base_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    assert_convert_dttm(ClickHouseBaseEngineSpec, target_type, expected_result, dttm)


@pytest.mark.parametrize(
    "time_grain,expected_result",
    [
        (None, "col"),
        ("PT1M", "toStartOfMinute(toDateTime(col))"),
        ("PT5M", "toDateTime(intDiv(toUInt32(toDateTime(col)), 300)*300)"),
        ("PT10M", "toDateTime(intDiv(toUInt32(toDateTime(col)), 600)*600)"),
        ("PT15M", "toDateTime(intDiv(toUInt32(toDateTime(col)), 900)*900)"),
        ("PT30M", "toDateTime(intDiv(toUInt32(toDateTime(col)), 1800)*1800)"),
        ("PT1H", "toStartOfHour(toDateTime(col))"),
        ("P1D", "toStartOfDay(toDateTime(col))"),
        ("P1W", "toMonday(toDateTime(col))"),
        ("P1M", "toStartOfMonth(toDateTime(col))"),
        ("P3M", "toStartOfQuarter(toDateTime(col))"),
        ("P1Y", "toStartOfYear(toDateTime(col))"),
    ],
)
def test_base_time_grain_expressions(
    time_grain: Optional[str], expected_result: str
) -> None:
    actual = str(
        ClickHouseBaseEngineSpec.get_timestamp_expr(
            col=column("col"), pdf=None, time_grain=time_grain
        )
    )
    assert actual == expected_result


@pytest.mark.parametrize(
    "native_type,sqla_type,attrs,generic_type,is_dttm",
    [
        ("Enum8('a'=1)", String, None, GenericDataType.STRING, False),
        ("Array(String)", String, None, GenericDataType.STRING, False),
        ("UUID", String, None, GenericDataType.STRING, False),
        ("Bool", Boolean, None, GenericDataType.BOOLEAN, False),
        ("String", String, None, GenericDataType.STRING, False),
        ("FixedString(16)", String, None, GenericDataType.STRING, False),
        ("Int32", types.INTEGER, None, GenericDataType.NUMERIC, False),
        ("UInt64", types.INTEGER, None, GenericDataType.NUMERIC, False),
        ("Decimal(10,2)", types.DECIMAL, None, GenericDataType.NUMERIC, False),
        ("DateTime64(3)", DateTime, None, GenericDataType.TEMPORAL, True),
        ("Date", Date, None, GenericDataType.TEMPORAL, True),
    ],
)
def test_base_column_type_mappings(
    native_type: str,
    sqla_type: type[TypeEngine],
    attrs: Optional[dict[str, object]],
    generic_type: GenericDataType,
    is_dttm: bool,
) -> None:
    assert_column_spec(
        ClickHouseBaseEngineSpec, native_type, sqla_type, attrs, generic_type, is_dttm
    )


# ---------------------------------------------------------------------------
# ClickHouseEngineSpec tests (legacy sqlalchemy connector)
# ---------------------------------------------------------------------------


def test_engine_spec_attributes() -> None:
    assert ClickHouseEngineSpec.engine == "clickhouse"
    assert ClickHouseEngineSpec.engine_name == "ClickHouse (sqlalchemy)"
    assert ClickHouseEngineSpec._show_functions_column == "name"
    assert ClickHouseEngineSpec.supports_file_upload is False


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Date", "toDate('2019-01-02')"),
        ("DateTime", "toDateTime('2019-01-02 03:04:05')"),
        ("UnknownType", None),
    ],
)
def test_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    assert_convert_dttm(ClickHouseEngineSpec, target_type, expected_result, dttm)


def test_execute_connection_error() -> None:
    database = Mock()
    cursor = Mock()
    cursor.execute.side_effect = NewConnectionError(
        HTTPConnection("localhost"), "Exception with sensitive data"
    )
    with pytest.raises(SupersetDBAPIDatabaseError) as excinfo:
        ClickHouseEngineSpec.execute(cursor, "SELECT col1 from table1", database)
    assert str(excinfo.value) == "Connection failed"


def test_get_dbapi_exception_mapping() -> None:
    mapping = ClickHouseEngineSpec.get_dbapi_exception_mapping()
    assert mapping == {NewConnectionError: SupersetDBAPIDatabaseError}


def test_get_dbapi_mapped_exception_connection_error() -> None:
    exc = NewConnectionError(HTTPConnection("localhost"), "connection refused")
    result = ClickHouseEngineSpec.get_dbapi_mapped_exception(exc)
    assert isinstance(result, SupersetDBAPIDatabaseError)
    assert str(result) == "Connection failed"


def test_get_dbapi_mapped_exception_unmapped() -> None:
    exc = ValueError("some other error")
    result = ClickHouseEngineSpec.get_dbapi_mapped_exception(exc)
    assert result is exc


def test_get_dbapi_mapped_exception_non_superset_mapping() -> None:
    with patch.object(
        ClickHouseEngineSpec,
        "get_dbapi_exception_mapping",
        return_value={RuntimeError: TypeError},
    ):
        exc = RuntimeError("test error")
        result = ClickHouseEngineSpec.get_dbapi_mapped_exception(exc)
        assert isinstance(result, TypeError)
        assert str(result) == "test error"


def test_get_function_names_happy_path() -> None:
    database = Mock()
    database.get_df.return_value = pd.DataFrame({"name": ["func1", "func2", "func3"]})
    result = ClickHouseEngineSpec.get_function_names.__wrapped__(
        ClickHouseEngineSpec, database
    )
    assert result == ["func1", "func2", "func3"]


def test_get_function_names_wrong_column() -> None:
    database = Mock()
    database.get_df.return_value = pd.DataFrame({"function_name": ["func1", "func2"]})
    result = ClickHouseEngineSpec.get_function_names.__wrapped__(
        ClickHouseEngineSpec, database
    )
    assert result == ["func1", "func2"]


def test_get_function_names_wrong_column_multiple() -> None:
    database = Mock()
    database.get_df.return_value = pd.DataFrame(
        {"col_a": ["func1"], "col_b": ["func2"]}
    )
    result = ClickHouseEngineSpec.get_function_names.__wrapped__(
        ClickHouseEngineSpec, database
    )
    assert result == []


def test_get_function_names_exception() -> None:
    database = Mock()
    database.get_df.side_effect = Exception("connection failed")
    result = ClickHouseEngineSpec.get_function_names.__wrapped__(
        ClickHouseEngineSpec, database
    )
    assert result == []


# ---------------------------------------------------------------------------
# ClickHouseConnectEngineSpec tests (recommended connector)
# ---------------------------------------------------------------------------


def test_connect_engine_spec_attributes() -> None:
    assert ClickHouseConnectEngineSpec.engine == "clickhousedb"
    assert ClickHouseConnectEngineSpec.engine_name == "ClickHouse"
    assert ClickHouseConnectEngineSpec.default_driver == "connect"
    assert ClickHouseConnectEngineSpec.supports_dynamic_schema is True


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Date", "toDate('2019-01-02')"),
        ("DateTime", "toDateTime('2019-01-02 03:04:05')"),
        ("UnknownType", None),
    ],
)
def test_connect_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    assert_convert_dttm(ClickHouseConnectEngineSpec, target_type, expected_result, dttm)


@pytest.mark.parametrize(
    "native_type,sqla_type,attrs,generic_type,is_dttm",
    [
        ("String", String, None, GenericDataType.STRING, False),
        ("LowCardinality(String)", String, None, GenericDataType.STRING, False),
        ("Nullable(String)", String, None, GenericDataType.STRING, False),
        (
            "LowCardinality(Nullable(String))",
            String,
            None,
            GenericDataType.STRING,
            False,
        ),
        ("Array(UInt8)", String, None, GenericDataType.STRING, False),
        ("Enum('hello', 'world')", String, None, GenericDataType.STRING, False),
        ("Enum('UInt32', 'Bool')", String, None, GenericDataType.STRING, False),
        (
            "LowCardinality(Enum('hello', 'world'))",
            String,
            None,
            GenericDataType.STRING,
            False,
        ),
        (
            "Nullable(Enum('hello', 'world'))",
            String,
            None,
            GenericDataType.STRING,
            False,
        ),
        (
            "LowCardinality(Nullable(Enum('hello', 'world')))",
            String,
            None,
            GenericDataType.STRING,
            False,
        ),
        ("FixedString(16)", String, None, GenericDataType.STRING, False),
        ("Nullable(FixedString(16))", String, None, GenericDataType.STRING, False),
        (
            "LowCardinality(Nullable(FixedString(16)))",
            String,
            None,
            GenericDataType.STRING,
            False,
        ),
        ("UUID", String, None, GenericDataType.STRING, False),
        ("Int8", Integer, None, GenericDataType.NUMERIC, False),
        ("Int16", Integer, None, GenericDataType.NUMERIC, False),
        ("Int32", Integer, None, GenericDataType.NUMERIC, False),
        ("Int64", Integer, None, GenericDataType.NUMERIC, False),
        ("Int128", Integer, None, GenericDataType.NUMERIC, False),
        ("Int256", Integer, None, GenericDataType.NUMERIC, False),
        ("Nullable(Int256)", Integer, None, GenericDataType.NUMERIC, False),
        (
            "LowCardinality(Nullable(Int256))",
            Integer,
            None,
            GenericDataType.NUMERIC,
            False,
        ),
        ("UInt8", Integer, None, GenericDataType.NUMERIC, False),
        ("UInt16", Integer, None, GenericDataType.NUMERIC, False),
        ("UInt32", Integer, None, GenericDataType.NUMERIC, False),
        ("UInt64", Integer, None, GenericDataType.NUMERIC, False),
        ("UInt128", Integer, None, GenericDataType.NUMERIC, False),
        ("UInt256", Integer, None, GenericDataType.NUMERIC, False),
        ("Nullable(UInt256)", Integer, None, GenericDataType.NUMERIC, False),
        (
            "LowCardinality(Nullable(UInt256))",
            Integer,
            None,
            GenericDataType.NUMERIC,
            False,
        ),
        ("Float32", Float, None, GenericDataType.NUMERIC, False),
        ("Float64", Float, None, GenericDataType.NUMERIC, False),
        ("Decimal(1, 2)", DECIMAL, None, GenericDataType.NUMERIC, False),
        ("Decimal32(2)", DECIMAL, None, GenericDataType.NUMERIC, False),
        ("Decimal64(2)", DECIMAL, None, GenericDataType.NUMERIC, False),
        ("Decimal128(2)", DECIMAL, None, GenericDataType.NUMERIC, False),
        ("Decimal256(2)", DECIMAL, None, GenericDataType.NUMERIC, False),
        ("Bool", Boolean, None, GenericDataType.BOOLEAN, False),
        ("Nullable(Bool)", Boolean, None, GenericDataType.BOOLEAN, False),
        ("Date", Date, None, GenericDataType.TEMPORAL, True),
        ("Nullable(Date)", Date, None, GenericDataType.TEMPORAL, True),
        ("LowCardinality(Nullable(Date))", Date, None, GenericDataType.TEMPORAL, True),
        ("Date32", Date, None, GenericDataType.TEMPORAL, True),
        ("Datetime", DateTime, None, GenericDataType.TEMPORAL, True),
        ("Nullable(Datetime)", DateTime, None, GenericDataType.TEMPORAL, True),
        (
            "LowCardinality(Nullable(Datetime))",
            DateTime,
            None,
            GenericDataType.TEMPORAL,
            True,
        ),
        ("Datetime('UTC')", DateTime, None, GenericDataType.TEMPORAL, True),
        ("Datetime64(3)", DateTime, None, GenericDataType.TEMPORAL, True),
        ("Datetime64(3, 'UTC')", DateTime, None, GenericDataType.TEMPORAL, True),
    ],
)
def test_connect_get_column_spec(
    native_type: str,
    sqla_type: type[TypeEngine],
    attrs: Optional[dict[str, object]],
    generic_type: GenericDataType,
    is_dttm: bool,
) -> None:
    assert_column_spec(
        ClickHouseConnectEngineSpec,
        native_type,
        sqla_type,
        attrs,
        generic_type,
        is_dttm,
    )


def test_connect_get_dbapi_exception_mapping() -> None:
    mapping = ClickHouseConnectEngineSpec.get_dbapi_exception_mapping()
    assert mapping == {}


def test_connect_get_dbapi_mapped_exception_unmapped() -> None:
    exc = ValueError("some error")
    result = ClickHouseConnectEngineSpec.get_dbapi_mapped_exception(exc)
    assert result is exc


def test_connect_get_dbapi_mapped_exception_no_match() -> None:
    exc = RuntimeError("runtime issue")
    result = ClickHouseConnectEngineSpec.get_dbapi_mapped_exception(exc)
    assert result is exc


def test_connect_get_dbapi_mapped_exception_superset_error() -> None:
    with patch.object(
        ClickHouseConnectEngineSpec,
        "get_dbapi_exception_mapping",
        return_value={ValueError: SupersetDBAPIDatabaseError},
    ):
        exc = ValueError("bad value")
        result = ClickHouseConnectEngineSpec.get_dbapi_mapped_exception(exc)
        assert isinstance(result, SupersetDBAPIDatabaseError)
        assert str(result) == "Connection failed"


def test_connect_get_dbapi_mapped_exception_other_mapping() -> None:
    with patch.object(
        ClickHouseConnectEngineSpec,
        "get_dbapi_exception_mapping",
        return_value={ValueError: TypeError},
    ):
        exc = ValueError("bad value")
        result = ClickHouseConnectEngineSpec.get_dbapi_mapped_exception(exc)
        assert isinstance(result, TypeError)
        assert str(result) == "bad value"


def test_connect_get_function_names_cached() -> None:
    mock_exceptions = Mock()
    mock_driver = Mock(exceptions=mock_exceptions)
    mock_cc = Mock(driver=mock_driver)
    with patch.dict(
        "sys.modules",
        {
            "clickhouse_connect": mock_cc,
            "clickhouse_connect.driver": mock_driver,
            "clickhouse_connect.driver.exceptions": mock_exceptions,
        },
    ):
        ClickHouseConnectEngineSpec._function_names = ["cached_func"]
        try:
            database = Mock()
            result = ClickHouseConnectEngineSpec.get_function_names(database)
            assert result == ["cached_func"]
            database.get_df.assert_not_called()
        finally:
            ClickHouseConnectEngineSpec._function_names = []


def test_connect_get_function_names_fetches() -> None:
    mock_exceptions = Mock()
    mock_exceptions.ClickHouseError = type("ClickHouseError", (Exception,), {})
    mock_driver = Mock(exceptions=mock_exceptions)
    mock_cc = Mock(driver=mock_driver)
    with patch.dict(
        "sys.modules",
        {
            "clickhouse_connect": mock_cc,
            "clickhouse_connect.driver": mock_driver,
            "clickhouse_connect.driver.exceptions": mock_exceptions,
        },
    ):
        ClickHouseConnectEngineSpec._function_names = []
        database = Mock()
        database.get_df.return_value = pd.DataFrame(
            {"name": ["arrayJoin", "toDate", "now"]}
        )
        result = ClickHouseConnectEngineSpec.get_function_names(database)
        assert result == ["arrayJoin", "toDate", "now"]
        ClickHouseConnectEngineSpec._function_names = []


def test_connect_get_function_names_error() -> None:
    mock_clickhouse_error = type("ClickHouseError", (Exception,), {})
    mock_exceptions = Mock(ClickHouseError=mock_clickhouse_error)
    mock_driver = Mock(exceptions=mock_exceptions)
    mock_cc = Mock(driver=mock_driver)
    with patch.dict(
        "sys.modules",
        {
            "clickhouse_connect": mock_cc,
            "clickhouse_connect.driver": mock_driver,
            "clickhouse_connect.driver.exceptions": mock_exceptions,
        },
    ):
        ClickHouseConnectEngineSpec._function_names = []
        database = Mock()
        database.get_df.side_effect = mock_clickhouse_error("query failed")
        result = ClickHouseConnectEngineSpec.get_function_names(database)
        assert result == []
        ClickHouseConnectEngineSpec._function_names = []


def test_connect_get_datatype() -> None:
    assert ClickHouseConnectEngineSpec.get_datatype("String") == "String"
    assert ClickHouseConnectEngineSpec.get_datatype("UInt64") == "UInt64"
    assert ClickHouseConnectEngineSpec.get_datatype("DateTime64(3)") == "DateTime64(3)"


@pytest.mark.parametrize(
    "schema, expected_result",
    [
        (None, "clickhousedb+connect://localhost:443/__default__"),
        (
            "new_schema",
            "clickhousedb+connect://localhost:443/new_schema",
        ),
    ],
)
def test_adjust_engine_params_fully_qualified(
    schema: str, expected_result: str
) -> None:
    url = make_url("clickhousedb+connect://localhost:443/__default__")
    uri = ClickHouseConnectEngineSpec.adjust_engine_params(url, {}, None, schema)[0]
    assert str(uri) == expected_result


def test_adjust_engine_params_no_schema() -> None:
    url = make_url("clickhousedb+connect://localhost:443/mydb")
    uri, connect_args = ClickHouseConnectEngineSpec.adjust_engine_params(
        url, {"timeout": 30}, None, None
    )
    assert str(uri) == "clickhousedb+connect://localhost:443/mydb"
    assert connect_args == {"timeout": 30}


def test_adjust_engine_params_special_chars_schema() -> None:
    url = make_url("clickhousedb+connect://localhost:443/__default__")
    uri, _ = ClickHouseConnectEngineSpec.adjust_engine_params(
        url, {}, None, "my schema"
    )
    assert str(uri) == "clickhousedb+connect://localhost:443/my%20schema"


def test_build_sqlalchemy_uri_with_encryption() -> None:
    parameters = BasicParametersType(
        host="clickhouse.example.com",
        port=8443,
        username="user",
        password="p",  # noqa: S106
        database="analytics",
        encryption=True,
        query={},
    )
    uri = ClickHouseConnectEngineSpec.build_sqlalchemy_uri(parameters)
    parsed_uri = make_url(uri)
    assert "clickhousedb+connect://" in uri
    assert parsed_uri.host == "clickhouse.example.com"
    assert "secure=true" in uri
    assert "analytics" in uri


def test_build_sqlalchemy_uri_without_encryption() -> None:
    parameters = BasicParametersType(
        host="localhost",
        port=8123,
        username="default",
        password="",
        database="default",
        encryption=False,
    )
    uri = ClickHouseConnectEngineSpec.build_sqlalchemy_uri(parameters)
    assert "clickhousedb+connect://" in uri
    assert "secure" not in uri


def test_build_sqlalchemy_uri_no_database() -> None:
    parameters = BasicParametersType(
        host="localhost",
        port=8123,
        username="default",
        password="",
        database="",
        encryption=False,
    )
    uri = ClickHouseConnectEngineSpec.build_sqlalchemy_uri(parameters)
    assert "__default__" in uri


def test_get_parameters_from_uri_with_secure() -> None:
    uri = "clickhousedb+connect://user:pass@host:8443/mydb?secure=true"
    params = ClickHouseConnectEngineSpec.get_parameters_from_uri(uri)
    assert params["username"] == "user"
    assert params["password"] == "pass"  # noqa: S105
    assert params["host"] == "host"
    assert params["port"] == 8443
    assert params["database"] == "mydb"
    assert params["encryption"] is True
    assert "secure" not in params.get("query", {})


def test_get_parameters_from_uri_without_secure() -> None:
    uri = "clickhousedb+connect://user:pass@host:8123/mydb"
    params = ClickHouseConnectEngineSpec.get_parameters_from_uri(uri)
    assert params["encryption"] is False


def test_get_parameters_from_uri_default_database() -> None:
    uri = "clickhousedb+connect://user:pass@host:8123/__default__"
    params = ClickHouseConnectEngineSpec.get_parameters_from_uri(uri)
    assert params["database"] == ""


def test_get_parameters_from_uri_secure_false() -> None:
    uri = "clickhousedb+connect://user:pass@host:8123/db?secure=false"
    params = ClickHouseConnectEngineSpec.get_parameters_from_uri(uri)
    assert params["encryption"] is False
    assert "secure" not in params.get("query", {})


def test_get_parameters_from_uri_extra_query() -> None:
    uri = "clickhousedb+connect://user:pass@host:8123/db?secure=true&timeout=30"
    params = ClickHouseConnectEngineSpec.get_parameters_from_uri(uri)
    assert params["encryption"] is True
    assert params["query"] == {"timeout": "30"}


def _mock_clickhouse_connect_modules() -> dict[str, Mock]:
    mock_default_port = Mock(return_value=8123)
    mock_exceptions = Mock()
    mock_exceptions.ClickHouseError = type("ClickHouseError", (Exception,), {})
    mock_driver = Mock(default_port=mock_default_port, exceptions=mock_exceptions)
    mock_cc = Mock(driver=mock_driver)
    return {
        "clickhouse_connect": mock_cc,
        "clickhouse_connect.driver": mock_driver,
        "clickhouse_connect.driver.exceptions": mock_exceptions,
    }


@patch("superset.db_engine_specs.clickhouse.is_hostname_valid", return_value=False)
def test_validate_parameters_invalid_hostname(mock_hostname: Mock) -> None:
    with patch.dict("sys.modules", _mock_clickhouse_connect_modules()):
        properties = {
            "parameters": {
                "host": "invalid..host",
                "port": 8123,
            }
        }
        errors = ClickHouseConnectEngineSpec.validate_parameters(properties)  # type: ignore
        assert len(errors) == 1
        assert "can't be resolved" in errors[0].message


def test_validate_parameters_missing_host() -> None:
    with patch.dict("sys.modules", _mock_clickhouse_connect_modules()):
        properties: dict[str, dict[str, object]] = {"parameters": {}}
        errors = ClickHouseConnectEngineSpec.validate_parameters(properties)  # type: ignore
        assert len(errors) == 1
        assert "required" in errors[0].message


def test_validate_parameters_empty_host() -> None:
    with patch.dict("sys.modules", _mock_clickhouse_connect_modules()):
        properties = {"parameters": {"host": ""}}
        errors = ClickHouseConnectEngineSpec.validate_parameters(properties)  # type: ignore
        assert len(errors) == 1
        assert "required" in errors[0].message


@patch("superset.db_engine_specs.clickhouse.is_hostname_valid", return_value=True)
@patch("superset.db_engine_specs.clickhouse.is_port_open", return_value=False)
def test_validate_parameters_closed_port(mock_port: Mock, mock_hostname: Mock) -> None:
    with patch.dict("sys.modules", _mock_clickhouse_connect_modules()):
        properties = {
            "parameters": {
                "host": "localhost",
                "port": 9999,
            }
        }
        errors = ClickHouseConnectEngineSpec.validate_parameters(properties)  # type: ignore
        assert len(errors) == 1
        assert "closed" in errors[0].message


@patch("superset.db_engine_specs.clickhouse.is_hostname_valid", return_value=True)
@patch("superset.db_engine_specs.clickhouse.is_port_open", return_value=True)
def test_validate_parameters_success(mock_port: Mock, mock_hostname: Mock) -> None:
    with patch.dict("sys.modules", _mock_clickhouse_connect_modules()):
        properties = {
            "parameters": {
                "host": "localhost",
                "port": 8123,
            }
        }
        errors = ClickHouseConnectEngineSpec.validate_parameters(properties)  # type: ignore
        assert errors == []


@patch("superset.db_engine_specs.clickhouse.is_hostname_valid", return_value=True)
def test_validate_parameters_invalid_port(mock_hostname: Mock) -> None:
    with patch.dict("sys.modules", _mock_clickhouse_connect_modules()):
        properties = {
            "parameters": {
                "host": "localhost",
                "port": "not_a_number",
            }
        }
        errors = ClickHouseConnectEngineSpec.validate_parameters(properties)  # type: ignore
        assert len(errors) == 1
        assert "valid integer" in errors[0].message


@patch("superset.db_engine_specs.clickhouse.is_hostname_valid", return_value=True)
def test_validate_parameters_port_out_of_range(mock_hostname: Mock) -> None:
    with patch.dict("sys.modules", _mock_clickhouse_connect_modules()):
        properties = {
            "parameters": {
                "host": "localhost",
                "port": 70000,
            }
        }
        errors = ClickHouseConnectEngineSpec.validate_parameters(properties)  # type: ignore
        assert len(errors) == 1
        assert "valid integer" in errors[0].message


@patch("superset.db_engine_specs.clickhouse.is_hostname_valid", return_value=True)
def test_validate_parameters_port_zero(mock_hostname: Mock) -> None:
    with patch.dict("sys.modules", _mock_clickhouse_connect_modules()):
        properties = {
            "parameters": {
                "host": "localhost",
                "port": 0,
            }
        }
        errors = ClickHouseConnectEngineSpec.validate_parameters(properties)  # type: ignore
        assert len(errors) == 1
        assert "valid integer" in errors[0].message


@patch("superset.db_engine_specs.clickhouse.is_hostname_valid", return_value=True)
def test_validate_parameters_negative_port(mock_hostname: Mock) -> None:
    with patch.dict("sys.modules", _mock_clickhouse_connect_modules()):
        properties = {
            "parameters": {
                "host": "localhost",
                "port": -1,
            }
        }
        errors = ClickHouseConnectEngineSpec.validate_parameters(properties)  # type: ignore
        assert len(errors) == 1
        assert "valid integer" in errors[0].message


@patch("superset.db_engine_specs.clickhouse.is_hostname_valid", return_value=True)
def test_validate_parameters_port_none_uses_default(mock_hostname: Mock) -> None:
    with patch.dict("sys.modules", _mock_clickhouse_connect_modules()):
        with patch(
            "superset.db_engine_specs.clickhouse.is_port_open", return_value=True
        ):
            properties = {
                "parameters": {
                    "host": "localhost",
                }
            }
            errors = ClickHouseConnectEngineSpec.validate_parameters(properties)  # type: ignore
            assert errors == []
