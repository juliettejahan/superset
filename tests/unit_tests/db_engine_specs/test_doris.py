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

from typing import Any, Optional
from unittest.mock import Mock

import pytest
from pytest_mock import MockerFixture
from sqlalchemy import JSON, types
from sqlalchemy.engine.url import make_url

from superset.db_engine_specs.doris import (
    AggState,
    ARRAY,
    BITMAP,
    DEFAULT_CATALOG,
    DOUBLE,
    HLL,
    LARGEINT,
    MAP,
    QuantileState,
    STRUCT,
    TINYINT,
)
from superset.errors import ErrorLevel, SupersetError, SupersetErrorType
from superset.utils.core import GenericDataType
from tests.unit_tests.db_engine_specs.utils import assert_column_spec


@pytest.mark.parametrize(
    "native_type,sqla_type,attrs,generic_type,is_dttm",
    [
        # Numeric
        ("tinyint", TINYINT, None, GenericDataType.NUMERIC, False),
        ("largeint", LARGEINT, None, GenericDataType.NUMERIC, False),
        ("decimal(38,18)", types.DECIMAL, None, GenericDataType.NUMERIC, False),
        ("decimalv3(38,18)", types.DECIMAL, None, GenericDataType.NUMERIC, False),
        ("double", DOUBLE, None, GenericDataType.NUMERIC, False),
        # String
        ("char(10)", types.CHAR, None, GenericDataType.STRING, False),
        ("varchar(65533)", types.VARCHAR, None, GenericDataType.STRING, False),
        ("binary", types.BINARY, None, GenericDataType.STRING, False),
        ("text", types.TEXT, None, GenericDataType.STRING, False),
        ("string", types.String, None, GenericDataType.STRING, False),
        # Date
        ("datetimev2", types.DateTime, None, GenericDataType.TEMPORAL, True),
        ("datev2", types.Date, None, GenericDataType.TEMPORAL, True),
        # Complex type
        ("array<varchar(65533)>", ARRAY, None, GenericDataType.STRING, False),
        ("map<string,int>", MAP, None, GenericDataType.STRING, False),
        ("struct<int,string>", STRUCT, None, GenericDataType.STRING, False),
        ("json", JSON, None, GenericDataType.STRING, False),
        ("jsonb", JSON, None, GenericDataType.STRING, False),
        ("bitmap", BITMAP, None, GenericDataType.STRING, False),
        ("hll", HLL, None, GenericDataType.STRING, False),
        ("quantile_state", QuantileState, None, GenericDataType.STRING, False),
        ("agg_state", AggState, None, GenericDataType.STRING, False),
    ],
)
def test_get_column_spec(
    native_type: str,
    sqla_type: type[types.TypeEngine],
    attrs: Optional[dict[str, Any]],
    generic_type: GenericDataType,
    is_dttm: bool,
) -> None:
    from superset.db_engine_specs.doris import DorisEngineSpec as spec  # noqa: N813

    assert_column_spec(spec, native_type, sqla_type, attrs, generic_type, is_dttm)


@pytest.mark.parametrize(
    "sqlalchemy_uri, connect_args, catalog, schema, return_schema,return_connect_args",
    [
        (
            "doris://user:password@host/db1",
            {"param1": "some_value"},
            None,
            None,
            "db1",
            {"param1": "some_value"},
        ),
        (
            "pydoris://user:password@host/db1",
            {"param1": "some_value"},
            None,
            None,
            "db1",
            {"param1": "some_value"},
        ),
        (
            "doris://user:password@host/catalog1.db1",
            {"param1": "some_value"},
            None,
            None,
            "catalog1.db1",
            {"param1": "some_value"},
        ),
        (
            "pydoris://user:password@host/catalog1.db1",
            {"param1": "some_value"},
            None,
            None,
            "catalog1.db1",
            {"param1": "some_value"},
        ),
        (
            "pydoris://user:password@host/catalog1.db1",
            {"param1": "some_value"},
            "catalog2",
            None,
            "catalog2.db1",
            {"param1": "some_value"},
        ),
        (
            "pydoris://user:password@host/catalog1.db1",
            {"param1": "some_value"},
            None,
            "db2",
            "catalog1.db2",
            {"param1": "some_value"},
        ),
        (
            "pydoris://user:password@host/catalog1.db1",
            {"param1": "some_value"},
            "catalog2",
            "db2",
            "catalog2.db2",
            {"param1": "some_value"},
        ),
    ],
)
def test_adjust_engine_params(
    sqlalchemy_uri: str,
    connect_args: dict[str, Any],
    catalog: str | None,
    schema: str | None,
    return_schema: str,
    return_connect_args: dict[str, Any],
) -> None:
    from superset.db_engine_specs.doris import DorisEngineSpec

    url = make_url(sqlalchemy_uri)
    returned_url, returned_connect_args = DorisEngineSpec.adjust_engine_params(
        url,
        connect_args,
        catalog,
        schema,
    )

    assert returned_url.database == return_schema
    assert returned_connect_args == return_connect_args


def test_adjust_engine_params_no_database() -> None:
    """
    Test that we raise an exception when the database is not specified.
    """
    from superset.db_engine_specs.doris import DorisEngineSpec

    url = make_url("doris://user:password@host")
    with pytest.raises(
        ValueError,
        match="Doris requires a database to be specified in the URI.",
    ):
        DorisEngineSpec.adjust_engine_params(url, {})


@pytest.mark.parametrize(
    "url,expected_schema",
    [
        ("doris://localhost:9030/hive.test", "test"),
        ("doris://localhost:9030/test", "test"),
        ("doris://localhost:9030/", None),
    ],
)
def test_get_schema_from_engine_params(
    url: str, expected_schema: Optional[str]
) -> None:
    """
    Test the ``get_schema_from_engine_params`` method.
    """
    from superset.db_engine_specs.doris import DorisEngineSpec

    assert (
        DorisEngineSpec.get_schema_from_engine_params(
            make_url(url),
            {},
        )
        == expected_schema
    )


@pytest.mark.parametrize(
    "database_value,expected_catalog",
    [
        ("catalog1.schema1", "catalog1"),
        ("schema1", "catalog2"),
        ("", "catalog2"),
    ],
)
def test_get_default_catalog(
    mocker: MockerFixture,
    database_value: Optional[str],
    expected_catalog: Optional[str],
) -> None:
    """
    Test the ``get_default_catalog`` method.
    """
    from superset.db_engine_specs.doris import DorisEngineSpec
    from superset.models.core import Database

    database = mocker.MagicMock(spec=Database)
    database.url_object.database = database_value
    rows = [
        mocker.MagicMock(IsCurrent=False, CatalogName="catalog1"),
        mocker.MagicMock(IsCurrent=True, CatalogName="catalog2"),
    ]
    with database.get_sqla_engine() as engine:
        engine.execute.return_value = rows

    assert DorisEngineSpec.get_default_catalog(database) == expected_catalog


@pytest.mark.parametrize(
    "mock_catalogs,expected_result",
    [
        (
            [
                Mock(CatalogName="catalog1"),
                Mock(CatalogName="catalog2"),
                Mock(CatalogName="catalog3"),
            ],
            {"catalog1", "catalog2", "catalog3"},
        ),
        (
            [Mock(CatalogName="single_catalog")],
            {"single_catalog"},
        ),
        (
            [],
            set(),
        ),
    ],
)
def test_get_catalog_names(
    mock_catalogs: list[Mock], expected_result: set[str]
) -> None:
    """
    Test the ``get_catalog_names`` method.
    """
    from superset.db_engine_specs.doris import DorisEngineSpec
    from superset.models.core import Database

    database = Mock(spec=Database)
    inspector = Mock()
    inspector.bind.execute.return_value = mock_catalogs

    catalogs = DorisEngineSpec.get_catalog_names(database, inspector)

    # Verify the SQL query
    inspector.bind.execute.assert_called_once_with("SHOW CATALOGS")

    # Verify the returned catalog names
    assert catalogs == expected_result


def test_get_default_catalog_falls_back_to_default(mocker: MockerFixture) -> None:
    """
    When the URI has no catalog and ``SHOW CATALOGS`` returns no current catalog,
    ``get_default_catalog`` should fall back to ``DEFAULT_CATALOG``.
    """
    from superset.db_engine_specs.doris import DorisEngineSpec
    from superset.models.core import Database

    database = mocker.MagicMock(spec=Database)
    database.url_object.database = "schema_only"
    rows = [
        mocker.MagicMock(IsCurrent=False, CatalogName="catalog1"),
        mocker.MagicMock(IsCurrent=False, CatalogName="catalog2"),
    ]
    with database.get_sqla_engine() as engine:
        engine.execute.return_value = rows

    assert DorisEngineSpec.get_default_catalog(database) == DEFAULT_CATALOG
    assert DEFAULT_CATALOG == "internal"


def test_array_python_type() -> None:
    """``ARRAY.python_type`` should return ``list``."""
    assert ARRAY().python_type is list


def test_map_python_type() -> None:
    """``MAP.python_type`` should return ``dict``."""
    assert MAP().python_type is dict


def test_struct_python_type() -> None:
    """``STRUCT.python_type`` should return ``None`` (no native Python type)."""
    assert STRUCT().python_type is None


@pytest.mark.parametrize(
    "type_class,visit_name",
    [
        (TINYINT, "TINYINT"),
        (LARGEINT, "LARGEINT"),
        (DOUBLE, "DOUBLE"),
        (HLL, "HLL"),
        (BITMAP, "BITMAP"),
        (QuantileState, "QUANTILE_STATE"),
        (AggState, "AGG_STATE"),
        (ARRAY, "ARRAY"),
        (MAP, "MAP"),
        (STRUCT, "STRUCT"),
    ],
)
def test_custom_type_visit_names(
    type_class: type[types.TypeEngine], visit_name: str
) -> None:
    """Each Doris-specific SQLAlchemy type exposes the expected ``__visit_name__``."""
    assert type_class().__visit_name__ == visit_name


def test_engine_metadata() -> None:
    """Sanity-check class-level attributes used for connection registration."""
    from superset.db_engine_specs.doris import DorisEngineSpec

    assert DorisEngineSpec.engine == "pydoris"
    assert DorisEngineSpec.engine_aliases == {"doris"}
    assert DorisEngineSpec.engine_name == "Apache Doris"
    assert DorisEngineSpec.default_driver == "pydoris"
    assert DorisEngineSpec.max_column_name_length == 64
    assert DorisEngineSpec.encryption_parameters == {"ssl": "0"}
    assert DorisEngineSpec.supports_dynamic_schema is True
    assert DorisEngineSpec.supports_catalog is True
    assert DorisEngineSpec.supports_dynamic_catalog is True
    assert DorisEngineSpec.supports_cross_catalog_queries is False
    assert DorisEngineSpec.metadata["default_port"] == 9030
    assert "pydoris" in DorisEngineSpec.metadata["pypi_packages"]


def test_extract_errors_access_denied() -> None:
    """An access-denied error message should map to a structured Superset error."""
    from superset.db_engine_specs.doris import DorisEngineSpec

    msg = "Access denied for user 'alice'@'1.2.3.4' (using password: YES)"
    result = DorisEngineSpec.extract_errors(Exception(msg))

    assert result == [
        SupersetError(
            error_type=SupersetErrorType.CONNECTION_ACCESS_DENIED_ERROR,
            message='Either the username "alice" or the password is incorrect.',
            level=ErrorLevel.ERROR,
            extra={
                "engine_name": "Apache Doris",
                "invalid": ["username", "password"],
                "issue_codes": [
                    {
                        "code": 1014,
                        "message": (
                            "Issue 1014 - Either the username or the password is wrong."
                        ),
                    },
                    {
                        "code": 1015,
                        "message": (
                            "Issue 1015 - Either the database is spelled "
                            "incorrectly or does not exist."
                        ),
                    },
                ],
            },
        )
    ]


def test_extract_errors_invalid_hostname() -> None:
    """An unknown-host error should map to ``CONNECTION_INVALID_HOSTNAME_ERROR``."""
    from superset.db_engine_specs.doris import DorisEngineSpec

    msg = "Unknown Doris server host 'doris.invalid' (8)"
    result = DorisEngineSpec.extract_errors(Exception(msg))

    assert len(result) == 1
    error = result[0]
    assert error.error_type == SupersetErrorType.CONNECTION_INVALID_HOSTNAME_ERROR
    assert error.message == 'Unknown Doris server host "doris.invalid".'
    assert error.level == ErrorLevel.ERROR
    assert error.extra is not None
    assert error.extra["engine_name"] == "Apache Doris"
    assert error.extra["invalid"] == ["host"]


def test_extract_errors_host_down() -> None:
    """A connection-refused error should map to ``CONNECTION_HOST_DOWN_ERROR``."""
    from superset.db_engine_specs.doris import DorisEngineSpec

    msg = "Can't connect to Doris server on 'doris.example.com' (110)"
    result = DorisEngineSpec.extract_errors(Exception(msg))

    assert len(result) == 1
    error = result[0]
    assert error.error_type == SupersetErrorType.CONNECTION_HOST_DOWN_ERROR
    assert (
        error.message
        == 'The host "doris.example.com" might be down and can\'t be reached.'
    )
    assert error.extra is not None
    assert error.extra["invalid"] == ["host", "port"]


def test_extract_errors_unknown_database() -> None:
    """An unknown-database error should map to ``CONNECTION_UNKNOWN_DATABASE_ERROR``."""
    from superset.db_engine_specs.doris import DorisEngineSpec

    msg = "Unknown database 'nope_db'"
    result = DorisEngineSpec.extract_errors(Exception(msg))

    assert len(result) == 1
    error = result[0]
    assert error.error_type == SupersetErrorType.CONNECTION_UNKNOWN_DATABASE_ERROR
    assert error.message == 'Unable to connect to database "nope_db".'
    assert error.extra is not None
    assert error.extra["invalid"] == ["database"]


def test_extract_errors_syntax_error() -> None:
    """A syntax error message should map to ``SYNTAX_ERROR``."""
    from superset.db_engine_specs.doris import DorisEngineSpec

    msg = (
        "You have an error in your SQL syntax; check the manual that "
        "corresponds to your MySQL server version for the right syntax to "
        "use near 'SLECT * FROM t' at line 1"
    )
    result = DorisEngineSpec.extract_errors(Exception(msg))

    assert len(result) == 1
    error = result[0]
    assert error.error_type == SupersetErrorType.SYNTAX_ERROR
    assert "SLECT * FROM t" in error.message


def test_extract_errors_generic_fallback() -> None:
    """An error that matches no custom regex should fall back to a generic error."""
    from superset.db_engine_specs.doris import DorisEngineSpec

    msg = "Some completely unrelated, unmatched failure message"
    result = DorisEngineSpec.extract_errors(Exception(msg))

    assert len(result) == 1
    error = result[0]
    assert error.error_type == SupersetErrorType.GENERIC_DB_ENGINE_ERROR
    assert error.message == msg
    assert error.extra is not None
    assert error.extra["engine_name"] == "Apache Doris"


def test_extract_errors_with_context() -> None:
    """Context should be merged into ``extra`` alongside regex captures."""
    from superset.db_engine_specs.doris import DorisEngineSpec

    msg = "Unknown Doris server host 'foo.bar' (8)"
    result = DorisEngineSpec.extract_errors(
        Exception(msg), context={"hostname": "foo.bar"}
    )

    assert len(result) == 1
    error = result[0]
    assert error.error_type == SupersetErrorType.CONNECTION_INVALID_HOSTNAME_ERROR
    assert error.extra is not None
    assert error.extra["engine_name"] == "Apache Doris"


def test_get_schema_from_engine_params_with_url_encoded_schema() -> None:
    """URL-encoded schema names should be decoded when extracted from the URI."""
    from superset.db_engine_specs.doris import DorisEngineSpec

    assert (
        DorisEngineSpec.get_schema_from_engine_params(
            make_url("doris://localhost:9030/catalog.my%20schema"),
            {},
        )
        == "my schema"
    )


def test_get_default_catalog_with_uri_catalog(mocker: MockerFixture) -> None:
    """When the URI contains ``catalog.schema``, the catalog should be returned
    without consulting the engine."""
    from superset.db_engine_specs.doris import DorisEngineSpec
    from superset.models.core import Database

    database = mocker.MagicMock(spec=Database)
    database.url_object.database = "my_catalog.my_schema"

    assert DorisEngineSpec.get_default_catalog(database) == "my_catalog"
    database.get_sqla_engine.assert_not_called()
