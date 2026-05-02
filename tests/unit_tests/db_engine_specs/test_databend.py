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
from typing import Any, cast, Optional
from unittest.mock import Mock, patch

import pytest
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

from superset.db_engine_specs.base import BasicParametersType, BasicPropertiesType
from superset.db_engine_specs.exceptions import SupersetDBAPIDatabaseError
from superset.errors import ErrorLevel, SupersetErrorType
from superset.utils.core import GenericDataType
from tests.unit_tests.db_engine_specs.utils import (
    assert_column_spec,
    assert_convert_dttm,
)
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Date", "to_date('2019-01-02')"),
        ("DateTime", "to_dateTime('2019-01-02 03:04:05')"),
        ("TimeStamp", "TO_TIMESTAMP('2019-01-02T03:04:05.678900')"),
        ("UnknownType", None),
    ],
)
def test_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    from superset.db_engine_specs.databend import (
        DatabendEngineSpec as spec,  # noqa: N813
    )

    assert_convert_dttm(spec, target_type, expected_result, dttm)


def test_convert_dttm_base_spec(dttm: datetime) -> None:  # noqa: F811
    from superset.db_engine_specs.databend import DatabendBaseEngineSpec

    assert_convert_dttm(DatabendBaseEngineSpec, "Date", "to_date('2019-01-02')", dttm)
    assert_convert_dttm(
        DatabendBaseEngineSpec,
        "DateTime",
        "to_dateTime('2019-01-02 03:04:05')",
        dttm,
    )
    assert_convert_dttm(
        DatabendBaseEngineSpec,
        "TimeStamp",
        "TO_TIMESTAMP('2019-01-02T03:04:05.678900')",
        dttm,
    )
    assert_convert_dttm(DatabendBaseEngineSpec, "UnknownType", None, dttm)


def test_epoch_to_dttm() -> None:
    from superset.db_engine_specs.databend import DatabendBaseEngineSpec

    assert DatabendBaseEngineSpec.epoch_to_dttm() == "{col}"


def test_time_grain_expressions() -> None:
    from superset.constants import TimeGrain
    from superset.db_engine_specs.databend import DatabendBaseEngineSpec

    expressions = DatabendBaseEngineSpec._time_grain_expressions
    assert expressions[None] == "{col}"
    assert expressions[TimeGrain.SECOND] == "DATE_TRUNC('SECOND', {col})"
    assert expressions[TimeGrain.MINUTE] == "to_start_of_minute(TO_DATETIME({col}))"
    assert (
        expressions[TimeGrain.FIVE_MINUTES]
        == "to_start_of_five_minutes(TO_DATETIME({col}))"
    )
    assert (
        expressions[TimeGrain.TEN_MINUTES]
        == "to_start_of_ten_minutes(TO_DATETIME({col}))"
    )
    assert (
        expressions[TimeGrain.FIFTEEN_MINUTES]
        == "to_start_of_fifteen_minutes(TO_DATETIME({col}))"
    )
    assert expressions[TimeGrain.HOUR] == "to_start_of_hour(TO_DATETIME({col}))"
    assert expressions[TimeGrain.DAY] == "to_start_of_day(TO_DATETIME({col}))"
    assert expressions[TimeGrain.WEEK] == "to_monday(TO_DATETIME({col}))"
    assert expressions[TimeGrain.MONTH] == "to_start_of_month(TO_DATETIME({col}))"
    assert expressions[TimeGrain.QUARTER] == "to_start_of_quarter(TO_DATETIME({col}))"
    assert expressions[TimeGrain.YEAR] == "to_start_of_year(TO_DATETIME({col}))"


def test_class_attributes() -> None:
    from superset.db_engine_specs.databend import (
        DatabendBaseEngineSpec,
        DatabendConnectEngineSpec,
        DatabendEngineSpec,
    )

    assert DatabendBaseEngineSpec.time_secondary_columns is True
    assert DatabendBaseEngineSpec.time_groupby_inline is True

    assert DatabendEngineSpec.engine == "databend"
    assert DatabendEngineSpec.engine_name == "Databend (legacy)"
    assert DatabendEngineSpec.supports_file_upload is False
    assert DatabendEngineSpec._show_functions_column == "name"

    assert DatabendConnectEngineSpec.engine == "databend"
    assert DatabendConnectEngineSpec.engine_name == "Databend"
    assert DatabendConnectEngineSpec.default_driver == "databend"
    assert DatabendConnectEngineSpec.encryption_parameters == {"secure": "true"}
    assert "databend://" in DatabendConnectEngineSpec.sqlalchemy_uri_placeholder


def test_metadata() -> None:
    from superset.db_engine_specs.base import DatabaseCategory
    from superset.db_engine_specs.databend import DatabendConnectEngineSpec

    metadata = DatabendConnectEngineSpec.metadata
    assert "Databend" in metadata["description"]
    assert metadata["logo"] == "databend.png"
    assert metadata["homepage_url"] == "https://www.databend.com/"
    assert DatabaseCategory.CLOUD_DATA_WAREHOUSES in metadata["categories"]
    assert DatabaseCategory.ANALYTICAL_DATABASES in metadata["categories"]
    assert DatabaseCategory.PROPRIETARY in metadata["categories"]
    assert metadata["pypi_packages"] == ["databend-sqlalchemy"]
    assert metadata["default_port"] == 443


def test_execute_connection_error() -> None:
    from superset.db_engine_specs.databend import DatabendEngineSpec

    database = Mock()
    cursor = Mock()
    cursor.execute.side_effect = NewConnectionError(
        HTTPConnection("Dummypool"), "Exception with sensitive data"
    )
    with pytest.raises(SupersetDBAPIDatabaseError) as excinfo:
        DatabendEngineSpec.execute(cursor, "SELECT col1 from table1", database)
    assert str(excinfo.value) == "Connection failed"


def test_get_dbapi_exception_mapping_legacy() -> None:
    from superset.db_engine_specs.databend import DatabendEngineSpec

    mapping = DatabendEngineSpec.get_dbapi_exception_mapping()
    assert mapping == {NewConnectionError: SupersetDBAPIDatabaseError}


def test_get_dbapi_exception_mapping_connect() -> None:
    from superset.db_engine_specs.databend import DatabendConnectEngineSpec

    assert DatabendConnectEngineSpec.get_dbapi_exception_mapping() == {}


def test_get_dbapi_mapped_exception_connection_failed() -> None:
    from superset.db_engine_specs.databend import DatabendEngineSpec

    exc = NewConnectionError(HTTPConnection("Dummy"), "boom")
    mapped = DatabendEngineSpec.get_dbapi_mapped_exception(exc)
    assert isinstance(mapped, SupersetDBAPIDatabaseError)
    assert str(mapped) == "Connection failed"


def test_get_dbapi_mapped_exception_unmapped_returns_original() -> None:
    from superset.db_engine_specs.databend import DatabendEngineSpec

    exc = ValueError("not mapped")
    mapped = DatabendEngineSpec.get_dbapi_mapped_exception(exc)
    assert mapped is exc


def test_get_dbapi_mapped_exception_other_mapping_constructs_new() -> None:
    """Cover the branch where the mapped exception is not SupersetDBAPIDatabaseError."""
    from superset.db_engine_specs.databend import DatabendEngineSpec

    class CustomMappedError(Exception):
        pass

    with patch.object(
        DatabendEngineSpec,
        "get_dbapi_exception_mapping",
        classmethod(lambda cls: {ValueError: CustomMappedError}),
    ):
        exc = ValueError("boom")
        mapped = DatabendEngineSpec.get_dbapi_mapped_exception(exc)
        assert isinstance(mapped, CustomMappedError)
        assert str(mapped) == "boom"


def test_get_dbapi_mapped_exception_connect_returns_original() -> None:
    """DatabendConnectEngineSpec has empty mapping so all exceptions pass through."""
    from superset.db_engine_specs.databend import DatabendConnectEngineSpec

    exc = NewConnectionError(HTTPConnection("Dummy"), "boom")
    mapped = DatabendConnectEngineSpec.get_dbapi_mapped_exception(exc)
    assert mapped is exc


def test_get_dbapi_mapped_exception_connect_supersetdb_branch() -> None:
    """Cover the SupersetDBAPIDatabaseError branch on the Connect spec."""
    from superset.db_engine_specs.databend import DatabendConnectEngineSpec

    with patch.object(
        DatabendConnectEngineSpec,
        "get_dbapi_exception_mapping",
        classmethod(lambda cls: {ValueError: SupersetDBAPIDatabaseError}),
    ):
        mapped = DatabendConnectEngineSpec.get_dbapi_mapped_exception(
            ValueError("boom")
        )
        assert isinstance(mapped, SupersetDBAPIDatabaseError)
        assert str(mapped) == "Connection failed"


def test_get_dbapi_mapped_exception_connect_other_mapping() -> None:
    from superset.db_engine_specs.databend import DatabendConnectEngineSpec

    class CustomMappedError(Exception):
        pass

    with patch.object(
        DatabendConnectEngineSpec,
        "get_dbapi_exception_mapping",
        classmethod(lambda cls: {ValueError: CustomMappedError}),
    ):
        mapped = DatabendConnectEngineSpec.get_dbapi_mapped_exception(
            ValueError("boom")
        )
        assert isinstance(mapped, CustomMappedError)
        assert str(mapped) == "boom"


def test_get_function_names_legacy_uses_cache() -> None:
    from superset.db_engine_specs.databend import DatabendEngineSpec

    DatabendEngineSpec._function_names = ["count", "sum"]
    try:
        names = DatabendEngineSpec.get_function_names(Mock())
        assert names == ["count", "sum"]
    finally:
        DatabendEngineSpec._function_names = []


def test_get_function_names_legacy_queries_database() -> None:
    from superset.db_engine_specs.databend import DatabendEngineSpec

    DatabendEngineSpec._function_names = []
    database = Mock()
    df = Mock()
    df.__getitem__ = Mock(return_value=Mock(tolist=Mock(return_value=["foo", "bar"])))
    database.get_df.return_value = df
    try:
        names = DatabendEngineSpec.get_function_names(database)
        assert names == ["foo", "bar"]
        assert DatabendEngineSpec._function_names == ["foo", "bar"]
    finally:
        DatabendEngineSpec._function_names = []


def test_get_function_names_legacy_handles_exception() -> None:
    from superset.db_engine_specs.databend import DatabendEngineSpec

    DatabendEngineSpec._function_names = []
    database = Mock()
    database.get_df.side_effect = RuntimeError("boom")
    try:
        names = DatabendEngineSpec.get_function_names(database)
        assert names == []
    finally:
        DatabendEngineSpec._function_names = []


def test_get_function_names_connect_uses_cache() -> None:
    from superset.db_engine_specs.databend import DatabendConnectEngineSpec

    DatabendConnectEngineSpec._function_names = ["sum"]
    try:
        names = DatabendConnectEngineSpec.get_function_names(Mock())
        assert names == ["sum"]
    finally:
        DatabendConnectEngineSpec._function_names = []


def test_get_function_names_connect_queries_database() -> None:
    from superset.db_engine_specs.databend import DatabendConnectEngineSpec

    DatabendConnectEngineSpec._function_names = []
    database = Mock()
    df = Mock()
    df.__getitem__ = Mock(return_value=Mock(tolist=Mock(return_value=["x", "y"])))
    database.get_df.return_value = df
    try:
        names = DatabendConnectEngineSpec.get_function_names(database)
        assert names == ["x", "y"]
        assert DatabendConnectEngineSpec._function_names == ["x", "y"]
    finally:
        DatabendConnectEngineSpec._function_names = []


def test_get_function_names_connect_handles_exception() -> None:
    from superset.db_engine_specs.databend import DatabendConnectEngineSpec

    DatabendConnectEngineSpec._function_names = []
    database = Mock()
    database.get_df.side_effect = RuntimeError("boom")
    try:
        names = DatabendConnectEngineSpec.get_function_names(database)
        assert names == []
    finally:
        DatabendConnectEngineSpec._function_names = []


def test_get_datatype() -> None:
    from superset.db_engine_specs.databend import DatabendConnectEngineSpec

    assert DatabendConnectEngineSpec.get_datatype("Int64") == "Int64"
    assert DatabendConnectEngineSpec.get_datatype("VARCHAR") == "VARCHAR"


def test_default_port() -> None:
    from superset.db_engine_specs.databend import DatabendConnectEngineSpec

    assert DatabendConnectEngineSpec.default_port("http", True) == 443
    assert DatabendConnectEngineSpec.default_port("http", False) == 8000
    assert DatabendConnectEngineSpec.default_port("https", True) == 443
    with pytest.raises(ValueError, match="Unrecognized Databend interface"):
        DatabendConnectEngineSpec.default_port("ftp", True)


def test_build_sqlalchemy_uri_with_encryption() -> None:
    from superset.db_engine_specs.databend import DatabendConnectEngineSpec

    parameters: BasicParametersType = {
        "username": "u",
        "password": "p",  # noqa: S106
        "host": "localhost",
        "port": 8000,
        "database": "db",
        "encryption": True,
        "query": {"foo": "bar"},
    }
    uri = DatabendConnectEngineSpec.build_sqlalchemy_uri(parameters)
    assert uri.startswith("databend://u:p@localhost:8000/db")
    assert "secure=true" in uri
    assert "foo=bar" in uri


def test_build_sqlalchemy_uri_without_encryption_keeps_query() -> None:
    from superset.db_engine_specs.databend import DatabendConnectEngineSpec

    parameters: BasicParametersType = {
        "username": "u",
        "password": "p",  # noqa: S106
        "host": "localhost",
        "port": 8000,
        "database": "db",
        "encryption": False,
        "query": {"foo": "bar"},
    }
    uri = DatabendConnectEngineSpec.build_sqlalchemy_uri(parameters)
    assert "secure=true" not in uri
    assert "foo=bar" in uri


def test_build_sqlalchemy_uri_default_database() -> None:
    from superset.db_engine_specs.databend import DatabendConnectEngineSpec

    parameters: BasicParametersType = {
        "username": "u",
        "password": "p",  # noqa: S106
        "host": "localhost",
        "port": 8000,
        "encryption": False,
    }
    uri = DatabendConnectEngineSpec.build_sqlalchemy_uri(parameters)
    assert "/__default__" in uri


def _fake_url(
    *,
    username: Optional[str] = None,
    password: Optional[str] = None,  # noqa: S107
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    query: Optional[dict[str, str]] = None,
) -> Mock:
    """Build a URL-like object whose query dict is mutable (the source mutates it)."""
    url = Mock()
    url.username = username
    url.password = password
    url.host = host
    url.port = port
    url.database = database
    url.query = dict(query or {})
    return url


def test_get_parameters_from_uri_with_secure_true() -> None:
    from superset.db_engine_specs.databend import DatabendConnectEngineSpec

    fake_url = _fake_url(
        username="u",
        password="p",  # noqa: S106
        host="localhost",
        port=8000,
        database="mydb",
        query={"secure": "true", "foo": "bar"},
    )
    with patch(
        "superset.db_engine_specs.databend.make_url_safe", return_value=fake_url
    ):
        params = DatabendConnectEngineSpec.get_parameters_from_uri(
            "databend://u:p@localhost:8000/mydb?secure=true&foo=bar"
        )
    assert params["username"] == "u"
    assert params["password"] == "p"  # noqa: S105
    assert params["host"] == "localhost"
    assert params["port"] == 8000
    assert params["database"] == "mydb"
    assert params["encryption"] is True
    assert params["query"] == {"foo": "bar"}


def test_get_parameters_from_uri_with_secure_false() -> None:
    from superset.db_engine_specs.databend import DatabendConnectEngineSpec

    fake_url = _fake_url(
        username="u",
        password="p",  # noqa: S106
        host="localhost",
        port=8000,
        database="mydb",
        query={"secure": "false"},
    )
    with patch(
        "superset.db_engine_specs.databend.make_url_safe", return_value=fake_url
    ):
        params = DatabendConnectEngineSpec.get_parameters_from_uri(
            "databend://u:p@localhost:8000/mydb?secure=false"
        )
    assert params["encryption"] is False


def test_get_parameters_from_uri_without_secure() -> None:
    from superset.db_engine_specs.databend import DatabendConnectEngineSpec

    uri = "databend://u:p@localhost:8000/mydb"
    params = DatabendConnectEngineSpec.get_parameters_from_uri(uri)
    assert params["encryption"] is False
    # SQLAlchemy returns an immutabledict here, but it's iterable like a dict.
    assert dict(params["query"]) == {}


def test_get_parameters_from_uri_default_database_placeholder() -> None:
    from superset.db_engine_specs.databend import DatabendConnectEngineSpec

    fake_url = _fake_url(
        username="u",
        password="p",  # noqa: S106
        host="localhost",
        port=8000,
        database="__default__",
        query={},
    )
    with patch(
        "superset.db_engine_specs.databend.make_url_safe", return_value=fake_url
    ):
        params = DatabendConnectEngineSpec.get_parameters_from_uri(
            "databend://u:p@localhost:8000/__default__"
        )
    assert params["database"] == ""


def _props(**parameters: Any) -> BasicPropertiesType:
    """Build a BasicPropertiesType-shaped dict for validate_parameters tests."""
    return cast(BasicPropertiesType, {"parameters": parameters})


def test_validate_parameters_missing_host() -> None:
    from superset.db_engine_specs.databend import DatabendConnectEngineSpec

    errors = DatabendConnectEngineSpec.validate_parameters(_props())
    assert len(errors) == 1
    assert errors[0].message == "Hostname is required"
    assert errors[0].error_type == SupersetErrorType.CONNECTION_MISSING_PARAMETERS_ERROR
    assert errors[0].level == ErrorLevel.WARNING


def test_validate_parameters_missing_host_top_level() -> None:
    """Cover the fallback branch where 'parameters' key is absent."""
    from superset.db_engine_specs.databend import DatabendConnectEngineSpec

    errors = DatabendConnectEngineSpec.validate_parameters(
        cast(BasicPropertiesType, {})
    )
    assert len(errors) == 1
    assert errors[0].message == "Hostname is required"


def test_validate_parameters_invalid_hostname() -> None:
    from superset.db_engine_specs.databend import DatabendConnectEngineSpec

    with patch(
        "superset.db_engine_specs.databend.is_hostname_valid", return_value=False
    ):
        errors = DatabendConnectEngineSpec.validate_parameters(
            _props(host="not-a-real-host")
        )
    assert len(errors) == 1
    assert "can't be resolved" in errors[0].message
    assert errors[0].error_type == SupersetErrorType.CONNECTION_INVALID_HOSTNAME_ERROR
    assert errors[0].level == ErrorLevel.ERROR


def test_validate_parameters_valid_port_skips_port_check() -> None:
    from superset.db_engine_specs.databend import DatabendConnectEngineSpec

    with (
        patch("superset.db_engine_specs.databend.is_hostname_valid", return_value=True),
        patch(
            "superset.db_engine_specs.databend.is_port_open", return_value=False
        ) as port_open_mock,
    ):
        errors = DatabendConnectEngineSpec.validate_parameters(
            _props(host="localhost", port=8000)
        )
    assert errors == []
    port_open_mock.assert_not_called()


def test_validate_parameters_port_as_string() -> None:
    from superset.db_engine_specs.databend import DatabendConnectEngineSpec

    with (
        patch("superset.db_engine_specs.databend.is_hostname_valid", return_value=True),
        patch("superset.db_engine_specs.databend.is_port_open", return_value=True),
    ):
        errors = DatabendConnectEngineSpec.validate_parameters(
            _props(host="localhost", port="8000")
        )
    assert errors == []


def test_validate_parameters_port_string_not_numeric_falls_back_to_default() -> None:
    from superset.db_engine_specs.databend import DatabendConnectEngineSpec

    with (
        patch("superset.db_engine_specs.databend.is_hostname_valid", return_value=True),
        patch(
            "superset.db_engine_specs.databend.is_port_open", return_value=True
        ) as port_open_mock,
    ):
        errors = DatabendConnectEngineSpec.validate_parameters(
            _props(host="localhost", port="abc")
        )
    assert errors == []
    # Default port (8000 unencrypted) should be checked since "abc" is invalid.
    port_open_mock.assert_called_once_with("localhost", 8000)


def test_validate_parameters_port_out_of_range_falls_back_to_default() -> None:
    from superset.db_engine_specs.databend import DatabendConnectEngineSpec

    with (
        patch("superset.db_engine_specs.databend.is_hostname_valid", return_value=True),
        patch(
            "superset.db_engine_specs.databend.is_port_open", return_value=True
        ) as port_open_mock,
    ):
        errors = DatabendConnectEngineSpec.validate_parameters(
            _props(host="localhost", port=99999)
        )
    assert errors == []
    port_open_mock.assert_called_once_with("localhost", 8000)


def test_validate_parameters_port_zero_falls_back_to_default() -> None:
    from superset.db_engine_specs.databend import DatabendConnectEngineSpec

    with (
        patch("superset.db_engine_specs.databend.is_hostname_valid", return_value=True),
        patch(
            "superset.db_engine_specs.databend.is_port_open", return_value=True
        ) as port_open_mock,
    ):
        errors = DatabendConnectEngineSpec.validate_parameters(
            _props(host="localhost", port=0)
        )
    assert errors == []
    port_open_mock.assert_called_once_with("localhost", 8000)


def test_validate_parameters_port_non_int_str_skipped() -> None:
    """Cover branch where port is not an int or str (e.g. a float)."""
    from superset.db_engine_specs.databend import DatabendConnectEngineSpec

    with (
        patch("superset.db_engine_specs.databend.is_hostname_valid", return_value=True),
        patch(
            "superset.db_engine_specs.databend.is_port_open", return_value=True
        ) as port_open_mock,
    ):
        errors = DatabendConnectEngineSpec.validate_parameters(
            _props(host="localhost", port=8000.0)
        )
    assert errors == []
    port_open_mock.assert_not_called()


def test_validate_parameters_no_port_uses_default_unencrypted() -> None:
    from superset.db_engine_specs.databend import DatabendConnectEngineSpec

    with (
        patch("superset.db_engine_specs.databend.is_hostname_valid", return_value=True),
        patch(
            "superset.db_engine_specs.databend.is_port_open", return_value=True
        ) as port_open_mock,
    ):
        errors = DatabendConnectEngineSpec.validate_parameters(_props(host="localhost"))
    assert errors == []
    port_open_mock.assert_called_once_with("localhost", 8000)


def test_validate_parameters_no_port_uses_default_encrypted() -> None:
    from superset.db_engine_specs.databend import DatabendConnectEngineSpec

    with (
        patch("superset.db_engine_specs.databend.is_hostname_valid", return_value=True),
        patch(
            "superset.db_engine_specs.databend.is_port_open", return_value=True
        ) as port_open_mock,
    ):
        errors = DatabendConnectEngineSpec.validate_parameters(
            _props(host="localhost", encryption=True)
        )
    assert errors == []
    port_open_mock.assert_called_once_with("localhost", 443)


def test_validate_parameters_default_port_invalid_returns_error() -> None:
    """Cover the branch where default_port returns an out-of-range value."""
    from superset.db_engine_specs.databend import DatabendConnectEngineSpec

    with (
        patch("superset.db_engine_specs.databend.is_hostname_valid", return_value=True),
        patch.object(DatabendConnectEngineSpec, "default_port", return_value=99999),
    ):
        errors = DatabendConnectEngineSpec.validate_parameters(_props(host="localhost"))
    assert len(errors) == 1
    assert errors[0].error_type == SupersetErrorType.CONNECTION_INVALID_PORT_ERROR


def test_validate_parameters_port_closed_returns_error() -> None:
    from superset.db_engine_specs.databend import DatabendConnectEngineSpec

    with (
        patch("superset.db_engine_specs.databend.is_hostname_valid", return_value=True),
        patch("superset.db_engine_specs.databend.is_port_open", return_value=False),
    ):
        errors = DatabendConnectEngineSpec.validate_parameters(_props(host="localhost"))
    assert len(errors) == 1
    assert errors[0].error_type == SupersetErrorType.CONNECTION_PORT_CLOSED_ERROR
    assert errors[0].level == ErrorLevel.ERROR


def test_validate_parameters_host_non_string_coerced() -> None:
    """Cover the branch where host is provided as a non-string value."""
    from superset.db_engine_specs.databend import DatabendConnectEngineSpec

    with (
        patch("superset.db_engine_specs.databend.is_hostname_valid", return_value=True),
        patch("superset.db_engine_specs.databend.is_port_open", return_value=True),
    ):
        errors = DatabendConnectEngineSpec.validate_parameters(
            _props(host=12345, port=8000)
        )
    assert errors == []


@pytest.mark.parametrize(
    "native_type,sqla_type,attrs,generic_type,is_dttm",
    [
        ("Varchar", String, None, GenericDataType.STRING, False),
        ("Nullable(Varchar)", String, None, GenericDataType.STRING, False),
        ("Array(UInt8)", String, None, GenericDataType.STRING, False),
        ("Int8", Integer, None, GenericDataType.NUMERIC, False),
        ("Int16", Integer, None, GenericDataType.NUMERIC, False),
        ("Int32", Integer, None, GenericDataType.NUMERIC, False),
        ("Int64", Integer, None, GenericDataType.NUMERIC, False),
        ("Int128", Integer, None, GenericDataType.NUMERIC, False),
        ("Int256", Integer, None, GenericDataType.NUMERIC, False),
        ("Nullable(Int64)", Integer, None, GenericDataType.NUMERIC, False),
        ("UInt8", Integer, None, GenericDataType.NUMERIC, False),
        ("UInt16", Integer, None, GenericDataType.NUMERIC, False),
        ("UInt32", Integer, None, GenericDataType.NUMERIC, False),
        ("UInt64", Integer, None, GenericDataType.NUMERIC, False),
        ("UInt128", Integer, None, GenericDataType.NUMERIC, False),
        ("UInt256", Integer, None, GenericDataType.NUMERIC, False),
        ("Float", Float, None, GenericDataType.NUMERIC, False),
        ("Double", Float, None, GenericDataType.NUMERIC, False),
        ("Decimal(1, 2)", DECIMAL, None, GenericDataType.NUMERIC, False),
        ("Decimal32(2)", DECIMAL, None, GenericDataType.NUMERIC, False),
        ("Decimal64(2)", DECIMAL, None, GenericDataType.NUMERIC, False),
        ("Decimal128(2)", DECIMAL, None, GenericDataType.NUMERIC, False),
        ("Decimal256(2)", DECIMAL, None, GenericDataType.NUMERIC, False),
        ("Bool", Boolean, None, GenericDataType.BOOLEAN, False),
        ("Nullable(Bool)", Boolean, None, GenericDataType.BOOLEAN, False),
        ("Date", Date, None, GenericDataType.TEMPORAL, True),
        ("Nullable(Date)", Date, None, GenericDataType.TEMPORAL, True),
        ("Datetime", DateTime, None, GenericDataType.TEMPORAL, True),
        ("Nullable(Datetime)", DateTime, None, GenericDataType.TEMPORAL, True),
    ],
)
def test_get_column_spec(
    native_type: str,
    sqla_type: type[TypeEngine],
    attrs: Optional[dict[str, Any]],
    generic_type: GenericDataType,
    is_dttm: bool,
) -> None:
    from superset.db_engine_specs.databend import (
        DatabendConnectEngineSpec as spec,  # noqa: N813
    )

    assert_column_spec(spec, native_type, sqla_type, attrs, generic_type, is_dttm)


@pytest.mark.parametrize(
    "native_type,generic_type",
    [
        ("Map(String, String)", GenericDataType.STRING),
        ("Json", GenericDataType.STRING),
    ],
)
def test_get_column_spec_extra_types(
    native_type: str, generic_type: GenericDataType
) -> None:
    from superset.db_engine_specs.databend import DatabendConnectEngineSpec

    column_spec = DatabendConnectEngineSpec.get_column_spec(native_type)
    assert column_spec is not None
    assert column_spec.generic_type == generic_type


@pytest.mark.parametrize(
    "column_name,expected_result",
    [
        # SHA-256 hash suffix (first 6 chars) with default HASH_ALGORITHM
        ("time", "time_336074"),
        ("count", "count_6c3549"),
    ],
)
def test_make_label_compatible(column_name: str, expected_result: str) -> None:
    from superset.db_engine_specs.databend import (
        DatabendConnectEngineSpec as spec,  # noqa: N813
    )

    label = spec.make_label_compatible(column_name)
    assert label == expected_result


def test_parameters_schema_validation() -> None:
    from superset.db_engine_specs.databend import DatabendParametersSchema

    schema = DatabendParametersSchema()
    result = schema.load(
        {
            "username": "u",
            "password": "p",
            "host": "localhost",
            "port": 8000,
            "database": "db",
            "encryption": True,
            "query": {"foo": "bar"},
        }
    )
    assert result["host"] == "localhost"
    assert result["port"] == 8000


def test_parameters_schema_port_out_of_range() -> None:
    from marshmallow import ValidationError

    from superset.db_engine_specs.databend import DatabendParametersSchema

    schema = DatabendParametersSchema()
    with pytest.raises(ValidationError):
        schema.load({"host": "localhost", "port": 999999})
