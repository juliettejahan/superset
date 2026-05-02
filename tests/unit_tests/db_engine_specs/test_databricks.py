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
# pylint: disable=unused-argument, import-outside-toplevel, protected-access

import re
import sys
from datetime import datetime
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest
from pytest_mock import MockerFixture
from sqlalchemy import column, types
from sqlalchemy.engine.url import make_url

from superset.constants import TimeGrain
from superset.db_engine_specs.databricks import (
    DatabricksBaseEngineSpec,
    DatabricksHiveEngineSpec,
    DatabricksNativeEngineSpec,
    DatabricksODBCEngineSpec,
    DatabricksPythonConnectorEngineSpec,
    DatabricksStringType,
    monkeypatch_dialect,
    time_grain_expressions,
)
from superset.errors import ErrorLevel, SupersetError, SupersetErrorType
from superset.utils import json
from tests.unit_tests.db_engine_specs.utils import assert_convert_dttm
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


def test_get_parameters_from_uri() -> None:
    """
    Test that the result from ``get_parameters_from_uri`` is JSON serializable.
    """
    from superset.db_engine_specs.databricks import (
        DatabricksNativeEngineSpec,
        DatabricksNativeParametersType,
    )

    parameters = DatabricksNativeEngineSpec.get_parameters_from_uri(
        "databricks+connector://token:abc12345@my_hostname:1234/test"
    )
    assert parameters == DatabricksNativeParametersType(
        {
            "access_token": "abc12345",
            "host": "my_hostname",
            "port": 1234,
            "database": "test",
            "encryption": False,
        }
    )
    assert json.loads(json.dumps(parameters)) == parameters


def test_build_sqlalchemy_uri() -> None:
    """
    test that the parameters are can correctly be compiled into a
    sqlalchemy_uri
    """
    from superset.db_engine_specs.databricks import (
        DatabricksNativeEngineSpec,
        DatabricksNativeParametersType,
    )

    parameters = DatabricksNativeParametersType(
        {
            "access_token": "abc12345",
            "host": "my_hostname",
            "port": 1234,
            "database": "test",
            "encryption": False,
        }
    )
    encrypted_extra = None
    sqlalchemy_uri = DatabricksNativeEngineSpec.build_sqlalchemy_uri(
        parameters, encrypted_extra
    )
    assert sqlalchemy_uri == (
        "databricks+connector://token:abc12345@my_hostname:1234/test"
    )


def test_parameters_json_schema() -> None:
    """
    test that the parameters schema can be converted to json
    """
    from superset.db_engine_specs.databricks import DatabricksNativeEngineSpec

    json_schema = DatabricksNativeEngineSpec.parameters_json_schema()

    assert json_schema == {
        "type": "object",
        "properties": {
            "access_token": {"type": "string"},
            "database": {"type": "string"},
            "encryption": {
                "description": "Use an encrypted connection to the database",
                "type": "boolean",
            },
            "host": {"type": "string"},
            "http_path": {"type": "string"},
            "port": {
                "description": "Database port",
                "maximum": 65536,
                "minimum": 0,
                "type": "integer",
            },
        },
        "required": ["access_token", "database", "host", "http_path", "port"],
    }


def test_get_extra_params(mocker: MockerFixture) -> None:
    """
    Test the ``get_extra_params`` method.
    """
    from superset.db_engine_specs.databricks import DatabricksNativeEngineSpec

    database = mocker.MagicMock()

    database.extra = {}
    assert DatabricksNativeEngineSpec.get_extra_params(database) == {
        "engine_params": {
            "connect_args": {
                "http_headers": [("User-Agent", "Apache Superset")],
                "_user_agent_entry": "Apache Superset",
            }
        }
    }

    database.extra = json.dumps(
        {
            "engine_params": {
                "connect_args": {
                    "http_headers": [("User-Agent", "Custom user agent")],
                    "_user_agent_entry": "Custom user agent",
                    "foo": "bar",
                }
            }
        }
    )
    assert DatabricksNativeEngineSpec.get_extra_params(database) == {
        "engine_params": {
            "connect_args": {
                "http_headers": [["User-Agent", "Custom user agent"]],
                "_user_agent_entry": "Custom user agent",
                "foo": "bar",
            }
        }
    }

    # it should also remove whitespace from http_path
    database.extra = json.dumps(
        {
            "engine_params": {
                "connect_args": {
                    "http_headers": [("User-Agent", "Custom user agent")],
                    "_user_agent_entry": "Custom user agent",
                    "http_path": "/some_path_here_with_whitespace ",
                }
            }
        }
    )
    assert DatabricksNativeEngineSpec.get_extra_params(database) == {
        "engine_params": {
            "connect_args": {
                "http_headers": [["User-Agent", "Custom user agent"]],
                "_user_agent_entry": "Custom user agent",
                "http_path": "/some_path_here_with_whitespace",
            }
        }
    }


def test_extract_errors() -> None:
    """
    Test that custom error messages are extracted correctly.
    """

    msg = ": mismatched input 'from_'. Expecting: "
    result = DatabricksNativeEngineSpec.extract_errors(Exception(msg))

    assert result == [
        SupersetError(
            message=": mismatched input 'from_'. Expecting: ",
            error_type=SupersetErrorType.GENERIC_DB_ENGINE_ERROR,
            level=ErrorLevel.ERROR,
            extra={
                "engine_name": "Databricks (legacy)",
                "issue_codes": [
                    {
                        "code": 1002,
                        "message": "Issue 1002 - The database returned an unexpected error.",  # noqa: E501
                    }
                ],
            },
        )
    ]


def test_extract_errors_with_context() -> None:
    """
    Test that custom error messages are extracted correctly with context.
    """

    msg = ": mismatched input 'from_'. Expecting: "
    context = {"hostname": "foo"}
    result = DatabricksNativeEngineSpec.extract_errors(Exception(msg), context)

    assert result == [
        SupersetError(
            message=": mismatched input 'from_'. Expecting: ",
            error_type=SupersetErrorType.GENERIC_DB_ENGINE_ERROR,
            level=ErrorLevel.ERROR,
            extra={
                "engine_name": "Databricks (legacy)",
                "issue_codes": [
                    {
                        "code": 1002,
                        "message": "Issue 1002 - The database returned an unexpected error.",  # noqa: E501
                    }
                ],
            },
        )
    ]


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Date", "CAST('2019-01-02' AS DATE)"),
        (
            "TimeStamp",
            "CAST('2019-01-02 03:04:05.678900' AS TIMESTAMP)",
        ),
        ("UnknownType", None),
    ],
)
def test_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    from superset.db_engine_specs.databricks import (
        DatabricksNativeEngineSpec as spec,  # noqa: N813
    )

    assert_convert_dttm(spec, target_type, expected_result, dttm)


def test_get_prequeries(mocker: MockerFixture) -> None:
    """
    Test the ``get_prequeries`` method.
    """
    from superset.db_engine_specs.databricks import DatabricksNativeEngineSpec

    database = mocker.MagicMock()

    assert DatabricksNativeEngineSpec.get_prequeries(database) == []
    assert DatabricksNativeEngineSpec.get_prequeries(database, schema="test") == [
        "USE SCHEMA `test`",
    ]
    assert DatabricksNativeEngineSpec.get_prequeries(database, catalog="test") == [
        "USE CATALOG `test`",
    ]
    assert DatabricksNativeEngineSpec.get_prequeries(
        database, catalog="foo", schema="bar"
    ) == [
        "USE CATALOG `foo`",
        "USE SCHEMA `bar`",
    ]

    assert DatabricksNativeEngineSpec.get_prequeries(
        database, catalog="with-hyphen", schema="hyphen-again"
    ) == [
        "USE CATALOG `with-hyphen`",
        "USE SCHEMA `hyphen-again`",
    ]

    assert DatabricksNativeEngineSpec.get_prequeries(
        database, catalog="`escaped-hyphen`", schema="`hyphen-escaped`"
    ) == [
        "USE CATALOG `escaped-hyphen`",
        "USE SCHEMA `hyphen-escaped`",
    ]


def test_engine_attributes_hive() -> None:
    assert DatabricksHiveEngineSpec.engine == "databricks"
    assert DatabricksHiveEngineSpec.engine_name == "Databricks Interactive Cluster"
    assert DatabricksHiveEngineSpec.default_driver == "pyhive"
    assert DatabricksHiveEngineSpec._show_functions_column == "function"
    assert DatabricksHiveEngineSpec._time_grain_expressions is time_grain_expressions


def test_engine_attributes_odbc() -> None:
    assert DatabricksODBCEngineSpec.engine == "databricks"
    assert DatabricksODBCEngineSpec.engine_name == "Databricks SQL Endpoint"
    assert DatabricksODBCEngineSpec.default_driver == "pyodbc"


def test_engine_attributes_native() -> None:
    assert DatabricksNativeEngineSpec.engine == "databricks"
    assert DatabricksNativeEngineSpec.engine_name == "Databricks (legacy)"
    assert DatabricksNativeEngineSpec.default_driver == "connector"
    assert DatabricksNativeEngineSpec.supports_dynamic_schema is True
    assert DatabricksNativeEngineSpec.supports_catalog is True
    assert DatabricksNativeEngineSpec.supports_dynamic_catalog is True
    assert DatabricksNativeEngineSpec.supports_cross_catalog_queries is True


def test_engine_attributes_python_connector() -> None:
    assert DatabricksPythonConnectorEngineSpec.engine == "databricks"
    assert DatabricksPythonConnectorEngineSpec.engine_name == "Databricks"
    assert DatabricksPythonConnectorEngineSpec.default_driver == "databricks-sql-python"
    assert DatabricksPythonConnectorEngineSpec.supports_dynamic_schema is True
    assert DatabricksPythonConnectorEngineSpec.supports_catalog is True
    assert DatabricksPythonConnectorEngineSpec.supports_dynamic_catalog is True


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
        TimeGrain.WEEK_ENDING_SATURDAY,
        TimeGrain.WEEK_STARTING_SUNDAY,
    }
    assert set(time_grain_expressions.keys()) == expected_keys


@pytest.mark.parametrize(
    "time_grain,expected",
    [
        (None, "col"),
        (TimeGrain.SECOND, "date_trunc('second', col)"),
        (TimeGrain.MINUTE, "date_trunc('minute', col)"),
        (TimeGrain.HOUR, "date_trunc('hour', col)"),
        (TimeGrain.DAY, "date_trunc('day', col)"),
        (TimeGrain.WEEK, "date_trunc('week', col)"),
        (TimeGrain.MONTH, "date_trunc('month', col)"),
        (TimeGrain.QUARTER, "date_trunc('quarter', col)"),
        (TimeGrain.YEAR, "date_trunc('year', col)"),
        (
            TimeGrain.WEEK_ENDING_SATURDAY,
            "date_trunc('week', col + interval '1 day') + interval '5 days'",
        ),
        (
            TimeGrain.WEEK_STARTING_SUNDAY,
            "date_trunc('week', col + interval '1 day') - interval '1 day'",
        ),
    ],
)
def test_native_time_grain_expressions(
    time_grain: Optional[str], expected: str
) -> None:
    actual = str(
        DatabricksNativeEngineSpec.get_timestamp_expr(
            col=column("col"), pdf=None, time_grain=time_grain
        )
    )
    assert actual == expected


def test_epoch_to_dttm_native() -> None:
    """``DatabricksBaseEngineSpec.epoch_to_dttm`` defers to Hive."""
    from superset.db_engine_specs.hive import HiveEngineSpec

    assert DatabricksBaseEngineSpec.epoch_to_dttm() == HiveEngineSpec.epoch_to_dttm()


def test_epoch_to_dttm_odbc() -> None:
    from superset.db_engine_specs.hive import HiveEngineSpec

    assert DatabricksODBCEngineSpec.epoch_to_dttm() == HiveEngineSpec.epoch_to_dttm()


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Date", "CAST('2019-01-02' AS DATE)"),
        ("TimeStamp", "CAST('2019-01-02 03:04:05.678900' AS TIMESTAMP)"),
        ("UnknownType", None),
    ],
)
def test_convert_dttm_odbc(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    assert_convert_dttm(DatabricksODBCEngineSpec, target_type, expected_result, dttm)


def test_databricks_string_type_process_literal_param() -> None:
    """Single quotes are escaped to backslash form by ParamEscaper."""
    s = DatabricksStringType()
    assert s.process_literal_param("hello", dialect=None) == "'hello'"
    assert s.process_literal_param("O'Hara", dialect=None) == "'O\\'Hara'"


def test_databricks_string_type_literal_processor_double_percents() -> None:
    """When the dialect doubles percents, ``%`` is escaped as ``%%``."""
    s = DatabricksStringType()
    dialect = MagicMock()
    dialect.identifier_preparer._double_percents = True
    proc = s.literal_processor(dialect)
    assert proc("100%") == "'100%%'"
    assert proc("plain") == "'plain'"


def test_databricks_string_type_literal_processor_no_double_percents() -> None:
    """When the dialect does not double percents, ``%`` is left untouched."""
    s = DatabricksStringType()
    dialect = MagicMock()
    dialect.identifier_preparer._double_percents = False
    proc = s.literal_processor(dialect)
    assert proc("100%") == "'100%'"


def test_monkeypatch_dialect_with_pyhive() -> None:
    """When pyhive is importable, ``monkeypatch_dialect`` registers a custom
    string type on ``HiveDialect.colspecs`` that defers to ``DatabricksStringType``
    for Databricks dialects only."""

    class FakeHiveDialect:
        colspecs: dict[type, type] = {}

    fake_module = MagicMock()
    fake_module.HiveDialect = FakeHiveDialect

    with patch.dict(sys.modules, {"pyhive.sqlalchemy_hive": fake_module}):
        monkeypatch_dialect()

    assert types.String in FakeHiveDialect.colspecs
    custom_type = FakeHiveDialect.colspecs[types.String]()

    databricks_dialect = MagicMock()
    databricks_dialect.__class__.__name__ = "DatabricksDialect"
    databricks_dialect.identifier_preparer._double_percents = False
    proc = custom_type.literal_processor(databricks_dialect)
    assert proc("foo") == "'foo'"


def test_monkeypatch_dialect_non_databricks_falls_back_to_super() -> None:
    """For non-Databricks dialects, ``literal_processor`` defers to the base
    ``TypeDecorator.literal_processor``."""

    class FakeHiveDialect:
        colspecs: dict[type, type] = {}

    fake_module = MagicMock()
    fake_module.HiveDialect = FakeHiveDialect

    with patch.dict(sys.modules, {"pyhive.sqlalchemy_hive": fake_module}):
        monkeypatch_dialect()

    custom_type = FakeHiveDialect.colspecs[types.String]()

    other_dialect_cls = type(
        "OtherDialect",
        (),
        {
            "identifier_preparer": MagicMock(_double_percents=False),
        },
    )
    # ``super().literal_processor`` returns ``None`` for ``TypeDecorator`` whose
    # ``impl`` is plain ``String`` without an overridden ``process_literal_param``.
    # We only assert it does NOT raise and that it does not invoke the
    # Databricks-specific escaping logic.
    if (proc := custom_type.literal_processor(other_dialect_cls())) is not None:
        # SQLAlchemy's default String literal processor doubles single quotes
        # rather than backslash-escaping them.
        assert proc("O'Hara") != "'O\\'Hara'"


def test_monkeypatch_dialect_pyhive_missing() -> None:
    """``monkeypatch_dialect`` silently ignores ``ImportError``."""
    with patch.dict(sys.modules, {"pyhive.sqlalchemy_hive": None}):
        # Should not raise even if the import fails.
        monkeypatch_dialect()


def test_extract_errors_with_known_pattern(mocker: MockerFixture) -> None:
    """A custom error regex provided via app config is matched and used."""
    custom_pattern = re.compile(r"port_closed:(?P<port_value>\d+)")
    mocker.patch.object(
        DatabricksNativeEngineSpec,
        "get_database_custom_errors",
        return_value={
            custom_pattern: (
                "Port %(port_value)s is not reachable",
                SupersetErrorType.CONNECTION_PORT_CLOSED_ERROR,
                {"invalid": ["port"]},
            )
        },
    )

    result = DatabricksNativeEngineSpec.extract_errors(
        Exception("port_closed:1234"),
        context={"hostname": "h", "port": 1234},
    )
    assert len(result) == 1
    error = result[0]
    assert error.error_type == SupersetErrorType.CONNECTION_PORT_CLOSED_ERROR
    assert error.message == "Port 1234 is not reachable"
    assert error.extra is not None
    assert error.extra["engine_name"] == DatabricksNativeEngineSpec.engine_name
    assert error.extra["invalid"] == ["port"]


def test_extract_errors_non_dict_custom_errors(mocker: MockerFixture) -> None:
    """``extract_errors`` defends against non-dict return values from
    ``get_database_custom_errors`` by treating them as an empty mapping."""
    mocker.patch.object(
        DatabricksNativeEngineSpec,
        "get_database_custom_errors",
        return_value="not-a-dict",
    )
    result = DatabricksNativeEngineSpec.extract_errors(Exception("boom"))
    assert len(result) == 1
    assert result[0].error_type == SupersetErrorType.GENERIC_DB_ENGINE_ERROR


def test_extract_errors_uses_database_name(mocker: MockerFixture) -> None:
    """``database_name`` is forwarded to ``get_database_custom_errors``."""
    spy = mocker.patch.object(
        DatabricksNativeEngineSpec,
        "get_database_custom_errors",
        return_value={},
    )
    DatabricksNativeEngineSpec.extract_errors(Exception("oops"), database_name="my_db")
    spy.assert_called_once_with("my_db")


def test_validate_parameters_missing_required(mocker: MockerFixture) -> None:
    """When required parameters are missing, a single combined error is returned."""
    mocker.patch(
        "superset.db_engine_specs.databricks.is_hostname_valid",
        return_value=True,
    )
    mocker.patch(
        "superset.db_engine_specs.databricks.is_port_open",
        return_value=True,
    )
    properties = {
        "parameters": {},
        "extra": json.dumps({"engine_params": {"connect_args": {}}}),
    }
    errors = DatabricksNativeEngineSpec.validate_parameters(properties)  # type: ignore[arg-type]
    assert len(errors) == 1
    assert errors[0].error_type == SupersetErrorType.CONNECTION_MISSING_PARAMETERS_ERROR
    assert errors[0].level == ErrorLevel.WARNING
    missing = errors[0].extra["missing"]  # type: ignore[index]
    for required in ("access_token", "host", "port", "database"):
        assert required in missing


def test_validate_parameters_invalid_hostname(mocker: MockerFixture) -> None:
    mocker.patch(
        "superset.db_engine_specs.databricks.is_hostname_valid",
        return_value=False,
    )
    properties = {
        "parameters": {
            "access_token": "tkn",
            "host": "bad host",
            "port": 443,
            "database": "db",
        },
        "extra": json.dumps({"engine_params": {"connect_args": {}}}),
    }
    errors = DatabricksNativeEngineSpec.validate_parameters(properties)  # type: ignore[arg-type]
    assert len(errors) == 1
    assert errors[0].error_type == SupersetErrorType.CONNECTION_INVALID_HOSTNAME_ERROR
    assert errors[0].extra is not None
    assert errors[0].extra["invalid"] == ["host"]


def test_validate_parameters_no_host_short_circuits(mocker: MockerFixture) -> None:
    """When ``host`` is missing, hostname/port checks are skipped."""
    mocker.patch(
        "superset.db_engine_specs.databricks.is_hostname_valid"
    ).side_effect = AssertionError("should not be called")
    mocker.patch(
        "superset.db_engine_specs.databricks.is_port_open"
    ).side_effect = AssertionError("should not be called")
    properties = {
        "parameters": {
            "access_token": "tkn",
            "port": 443,
            "database": "db",
        },
        "extra": json.dumps({"engine_params": {"connect_args": {}}}),
    }
    errors = DatabricksNativeEngineSpec.validate_parameters(properties)  # type: ignore[arg-type]
    # Only the missing-parameters error should be present.
    assert len(errors) == 1
    assert errors[0].error_type == SupersetErrorType.CONNECTION_MISSING_PARAMETERS_ERROR


def test_validate_parameters_no_port(mocker: MockerFixture) -> None:
    mocker.patch(
        "superset.db_engine_specs.databricks.is_hostname_valid",
        return_value=True,
    )
    properties = {
        "parameters": {
            "access_token": "tkn",
            "host": "h",
            "database": "db",
        },
        "extra": json.dumps({"engine_params": {"connect_args": {}}}),
    }
    errors = DatabricksNativeEngineSpec.validate_parameters(properties)  # type: ignore[arg-type]
    assert len(errors) == 1
    assert errors[0].error_type == SupersetErrorType.CONNECTION_MISSING_PARAMETERS_ERROR


def test_validate_parameters_port_not_int(mocker: MockerFixture) -> None:
    mocker.patch(
        "superset.db_engine_specs.databricks.is_hostname_valid",
        return_value=True,
    )
    properties = {
        "parameters": {
            "access_token": "tkn",
            "host": "h",
            "port": "not-an-int",
            "database": "db",
        },
        "extra": json.dumps({"engine_params": {"connect_args": {}}}),
    }
    errors = DatabricksNativeEngineSpec.validate_parameters(properties)  # type: ignore[arg-type]
    types_seen = {e.error_type for e in errors}
    assert SupersetErrorType.CONNECTION_INVALID_PORT_ERROR in types_seen


def test_validate_parameters_port_out_of_range(mocker: MockerFixture) -> None:
    mocker.patch(
        "superset.db_engine_specs.databricks.is_hostname_valid",
        return_value=True,
    )
    properties = {
        "parameters": {
            "access_token": "tkn",
            "host": "h",
            "port": 70000,
            "database": "db",
        },
        "extra": json.dumps({"engine_params": {"connect_args": {}}}),
    }
    errors = DatabricksNativeEngineSpec.validate_parameters(properties)  # type: ignore[arg-type]
    assert any(
        e.error_type == SupersetErrorType.CONNECTION_INVALID_PORT_ERROR for e in errors
    )


def test_validate_parameters_port_closed(mocker: MockerFixture) -> None:
    mocker.patch(
        "superset.db_engine_specs.databricks.is_hostname_valid",
        return_value=True,
    )
    mocker.patch(
        "superset.db_engine_specs.databricks.is_port_open",
        return_value=False,
    )
    properties = {
        "parameters": {
            "access_token": "tkn",
            "host": "h",
            "port": 443,
            "database": "db",
        },
        "extra": json.dumps(
            {
                "engine_params": {
                    "connect_args": {"http_path": "/sql/1.0/warehouses/abc"}
                }
            }
        ),
    }
    errors = DatabricksNativeEngineSpec.validate_parameters(properties)  # type: ignore[arg-type]
    assert any(
        e.error_type == SupersetErrorType.CONNECTION_PORT_CLOSED_ERROR for e in errors
    )


def test_validate_parameters_success(mocker: MockerFixture) -> None:
    mocker.patch(
        "superset.db_engine_specs.databricks.is_hostname_valid",
        return_value=True,
    )
    mocker.patch(
        "superset.db_engine_specs.databricks.is_port_open",
        return_value=True,
    )
    properties = {
        "parameters": {
            "access_token": "tkn",
            "host": "h",
            "port": 443,
            "database": "db",
        },
        "extra": json.dumps(
            {
                "engine_params": {
                    "connect_args": {"http_path": "/sql/1.0/warehouses/abc"}
                }
            }
        ),
    }
    assert DatabricksNativeEngineSpec.validate_parameters(properties) == []  # type: ignore[arg-type]


def test_native_build_sqlalchemy_uri_with_encryption() -> None:
    parameters = {
        "access_token": "abc",
        "host": "host",
        "port": 443,
        "database": "default",
        "encryption": True,
    }
    uri = DatabricksNativeEngineSpec.build_sqlalchemy_uri(parameters)  # type: ignore[arg-type]
    assert uri.startswith("databricks+connector://token:abc@host:443/default")
    assert "ssl=1" in uri


def test_native_build_sqlalchemy_uri_encryption_without_params(
    mocker: MockerFixture,
) -> None:
    mocker.patch.object(DatabricksNativeEngineSpec, "encryption_parameters", {})
    parameters = {
        "access_token": "abc",
        "host": "host",
        "port": 443,
        "database": "default",
        "encryption": True,
    }
    with pytest.raises(Exception, match="encryption"):
        DatabricksNativeEngineSpec.build_sqlalchemy_uri(parameters)  # type: ignore[arg-type]


def test_native_get_parameters_from_uri_with_encryption() -> None:
    uri = "databricks+connector://token:abc@host:443/default?ssl=1"
    parameters = DatabricksNativeEngineSpec.get_parameters_from_uri(uri)
    assert parameters["encryption"] is True


def test_native_parameters_json_schema_no_schema(mocker: MockerFixture) -> None:
    mocker.patch.object(DatabricksNativeEngineSpec, "properties_schema", None)
    assert DatabricksNativeEngineSpec.parameters_json_schema() is None


def test_native_get_default_catalog_explicit(mocker: MockerFixture) -> None:
    """If ``connect_args.catalog`` is set, it is returned without querying."""
    database = mocker.MagicMock()
    database.extra = json.dumps(
        {"engine_params": {"connect_args": {"catalog": "my_cat"}}}
    )
    assert DatabricksNativeEngineSpec.get_default_catalog(database) == "my_cat"


def test_native_get_default_catalog_single_catalog(mocker: MockerFixture) -> None:
    """If ``SHOW CATALOGS`` returns a single row, that value is returned."""
    database = mocker.MagicMock()
    database.extra = "{}"

    engine = MagicMock()
    engine.execute.return_value = [("only_catalog",)]
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=engine)
    cm.__exit__ = MagicMock(return_value=False)
    database.get_sqla_engine.return_value = cm

    assert DatabricksNativeEngineSpec.get_default_catalog(database) == "only_catalog"


def test_native_get_default_catalog_multiple_catalogs(mocker: MockerFixture) -> None:
    database = mocker.MagicMock()
    database.extra = "{}"

    engine = MagicMock()

    def execute(query: str) -> object:
        if query == "SHOW CATALOGS":
            return [("a",), ("b",)]
        return MagicMock(scalar=lambda: "current_cat")

    engine.execute.side_effect = execute
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=engine)
    cm.__exit__ = MagicMock(return_value=False)
    database.get_sqla_engine.return_value = cm

    assert DatabricksNativeEngineSpec.get_default_catalog(database) == "current_cat"


def test_native_get_catalog_names(mocker: MockerFixture) -> None:
    inspector = mocker.MagicMock()
    inspector.bind.execute.return_value = [("a",), ("b",), ("c",)]
    database = mocker.MagicMock()
    assert DatabricksNativeEngineSpec.get_catalog_names(database, inspector) == {
        "a",
        "b",
        "c",
    }


def test_dynamic_get_table_names(mocker: MockerFixture) -> None:
    """``get_table_names`` returns the inspector's tables minus the views."""
    mocker.patch.object(
        DatabricksNativeEngineSpec.__mro__[1].__mro__[2],
        "get_table_names",
        return_value={"t1", "t2", "v1"},
    )
    mocker.patch.object(
        DatabricksNativeEngineSpec,
        "get_view_names",
        return_value={"v1"},
    )
    database = mocker.MagicMock()
    inspector = mocker.MagicMock()
    assert DatabricksNativeEngineSpec.get_table_names(
        database, inspector, schema=None
    ) == {"t1", "t2"}


def test_python_connector_build_sqlalchemy_uri_full() -> None:
    parameters = {
        "access_token": "tkn",
        "host": "host",
        "port": 443,
        "http_path_field": "/sql/1.0/warehouses/abc",
        "default_catalog": "main",
        "default_schema": "default",
        "encryption": False,
    }
    uri = DatabricksPythonConnectorEngineSpec.build_sqlalchemy_uri(parameters)  # type: ignore[arg-type]
    parsed = make_url(uri)
    assert parsed.username == "token"
    assert parsed.password == "tkn"  # noqa: S105
    assert parsed.host == "host"
    assert parsed.port == 443
    assert parsed.query["http_path"] == "/sql/1.0/warehouses/abc"
    assert parsed.query["catalog"] == "main"
    assert parsed.query["schema"] == "default"
    assert "ssl" not in parsed.query


def test_python_connector_build_sqlalchemy_uri_with_encryption() -> None:
    parameters = {
        "access_token": "tkn",
        "host": "host",
        "port": 443,
        "http_path_field": "/sql/1.0/warehouses/abc",
        "default_catalog": "main",
        "default_schema": "default",
        "encryption": True,
    }
    uri = DatabricksPythonConnectorEngineSpec.build_sqlalchemy_uri(parameters)  # type: ignore[arg-type]
    parsed = make_url(uri)
    assert parsed.query["ssl"] == "1"


def test_python_connector_build_sqlalchemy_uri_minimal() -> None:
    parameters = {
        "access_token": "tkn",
        "host": "host",
        "port": 443,
        "encryption": False,
    }
    uri = DatabricksPythonConnectorEngineSpec.build_sqlalchemy_uri(parameters)  # type: ignore[arg-type]
    parsed = make_url(uri)
    assert parsed.host == "host"
    assert parsed.port == 443
    assert "http_path" not in parsed.query
    assert "catalog" not in parsed.query
    assert "schema" not in parsed.query


def test_python_connector_get_parameters_from_uri() -> None:
    uri = (
        "databricks://token:tkn@host:443"
        "?http_path=/sql/1.0/warehouses/abc&catalog=main&schema=default"
    )
    parameters = DatabricksPythonConnectorEngineSpec.get_parameters_from_uri(uri)
    assert parameters == {
        "access_token": "tkn",
        "host": "host",
        "port": 443,
        "http_path_field": "/sql/1.0/warehouses/abc",
        "default_catalog": "main",
        "default_schema": "default",
        "encryption": False,
    }


def test_python_connector_get_parameters_from_uri_with_encryption() -> None:
    uri = (
        "databricks://token:tkn@host:443"
        "?http_path=/sql/1.0/warehouses/abc&catalog=main&schema=default&ssl=1"
    )
    parameters = DatabricksPythonConnectorEngineSpec.get_parameters_from_uri(uri)
    assert parameters["encryption"] is True


def test_python_connector_get_default_catalog(mocker: MockerFixture) -> None:
    database = mocker.MagicMock()
    database.url_object.query = {"catalog": "my_cat"}
    assert DatabricksPythonConnectorEngineSpec.get_default_catalog(database) == "my_cat"


def test_python_connector_get_default_catalog_missing(mocker: MockerFixture) -> None:
    database = mocker.MagicMock()
    database.url_object.query = {}
    assert DatabricksPythonConnectorEngineSpec.get_default_catalog(database) is None


def test_python_connector_get_catalog_names(mocker: MockerFixture) -> None:
    inspector = mocker.MagicMock()
    inspector.bind.execute.return_value = [("a",), ("b",)]
    database = mocker.MagicMock()
    assert DatabricksPythonConnectorEngineSpec.get_catalog_names(
        database, inspector
    ) == {"a", "b"}


def test_python_connector_adjust_engine_params_catalog_and_schema() -> None:
    uri = make_url("databricks://token:tkn@host:443/?http_path=/p")
    new_uri, args = DatabricksPythonConnectorEngineSpec.adjust_engine_params(
        uri, {"foo": "bar"}, catalog="cat1", schema="schema1"
    )
    assert new_uri.query["catalog"] == "cat1"
    assert new_uri.query["schema"] == "schema1"
    assert args == {"foo": "bar"}


def test_python_connector_adjust_engine_params_no_overrides() -> None:
    uri = make_url("databricks://token:tkn@host:443/?http_path=/p&catalog=c0")
    new_uri, args = DatabricksPythonConnectorEngineSpec.adjust_engine_params(uri, {})
    assert new_uri.query.get("catalog") == "c0"
    assert "schema" not in new_uri.query
    assert args == {}


def test_python_connector_metadata_drivers() -> None:
    drivers = DatabricksPythonConnectorEngineSpec.metadata["drivers"]
    names = [d["name"] for d in drivers]
    assert "Databricks Python Connector (Recommended)" in names
    assert "Hive Connector (Interactive Clusters)" in names
    assert "ODBC (SQL Endpoints)" in names
    assert "databricks-dbapi (Legacy)" in names
    recommended = [d for d in drivers if d.get("is_recommended")]
    assert len(recommended) == 1
    assert recommended[0]["pypi_package"] == "databricks-sql-connector"


def test_python_connector_required_parameters() -> None:
    required = DatabricksPythonConnectorEngineSpec.required_parameters
    for key in (
        "access_token",
        "host",
        "port",
        "default_catalog",
        "default_schema",
        "http_path_field",
    ):
        assert key in required


def test_native_required_parameters_extends_base() -> None:
    required = DatabricksNativeEngineSpec.required_parameters
    for key in ("access_token", "host", "port", "database", "extra"):
        assert key in required
