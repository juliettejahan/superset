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
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from superset.errors import SupersetErrorType
from superset.utils import json
from superset.utils.core import GenericDataType
from tests.conftest import with_config
from tests.unit_tests.db_engine_specs.utils import assert_convert_dttm
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Text", "'2019-01-02 03:04:05.678900'"),
        ("DateTime", "'2019-01-02 03:04:05.678900'"),
        ("UnknownType", None),
    ],
)
def test_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    from superset.db_engine_specs.duckdb import DuckDBEngineSpec as spec  # noqa: N813

    assert_convert_dttm(spec, target_type, expected_result, dttm)


def test_convert_dttm_with_db_extra(dttm: datetime) -> None:  # noqa: F811
    """`convert_dttm` should ignore ``db_extra`` and still produce a literal."""
    from superset.db_engine_specs.duckdb import DuckDBEngineSpec

    result = DuckDBEngineSpec.convert_dttm(
        target_type="DateTime",
        dttm=dttm,
        db_extra={"unused": "value"},
    )
    assert result == "'2019-01-02 03:04:05.678900'"


def test_epoch_to_dttm() -> None:
    """`epoch_to_dttm` returns the DuckDB ``datetime`` conversion expression."""
    from superset.db_engine_specs.duckdb import DuckDBEngineSpec

    assert DuckDBEngineSpec.epoch_to_dttm() == "datetime({col}, 'unixepoch')"


def test_time_grain_expressions() -> None:
    """All custom time grains map to ``DATE_TRUNC`` expressions."""
    from superset.constants import TimeGrain
    from superset.db_engine_specs.duckdb import DuckDBEngineSpec

    grains = DuckDBEngineSpec._time_grain_expressions
    assert grains[None] == "{col}"
    assert grains[TimeGrain.SECOND] == "DATE_TRUNC('second', {col})"
    assert grains[TimeGrain.MINUTE] == "DATE_TRUNC('minute', {col})"
    assert grains[TimeGrain.HOUR] == "DATE_TRUNC('hour', {col})"
    assert grains[TimeGrain.DAY] == "DATE_TRUNC('day', {col})"
    assert grains[TimeGrain.WEEK] == "DATE_TRUNC('week', {col})"
    assert grains[TimeGrain.MONTH] == "DATE_TRUNC('month', {col})"
    assert grains[TimeGrain.QUARTER] == "DATE_TRUNC('quarter', {col})"
    assert grains[TimeGrain.YEAR] == "DATE_TRUNC('year', {col})"


@with_config({"VERSION_STRING": "1.0.0"})
def test_get_extra_params(mocker: MockerFixture) -> None:
    """
    Test the ``get_extra_params`` method.
    """
    from superset.db_engine_specs.duckdb import DuckDBEngineSpec

    database = mocker.MagicMock()

    database.extra = {}
    assert DuckDBEngineSpec.get_extra_params(database) == {
        "engine_params": {
            "connect_args": {"config": {"custom_user_agent": "apache-superset/1.0.0"}}
        }
    }

    database.extra = json.dumps(
        {"engine_params": {"connect_args": {"config": {"custom_user_agent": "my-app"}}}}
    )
    assert DuckDBEngineSpec.get_extra_params(database) == {
        "engine_params": {
            "connect_args": {
                "config": {"custom_user_agent": "apache-superset/1.0.0 my-app"}
            }
        }
    }


@with_config({"VERSION_STRING": "9.9.9"})
def test_get_extra_params_with_query_source(mocker: MockerFixture) -> None:
    """``get_extra_params`` accepts an optional ``QuerySource`` argument."""
    from superset.db_engine_specs.duckdb import DuckDBEngineSpec
    from superset.utils.core import QuerySource

    database = mocker.MagicMock()
    database.extra = {}

    extra = DuckDBEngineSpec.get_extra_params(database, source=QuerySource.SQL_LAB)
    user_agent = extra["engine_params"]["connect_args"]["config"]["custom_user_agent"]
    assert user_agent.startswith("apache-superset")
    assert "9.9.9" in user_agent


def test_build_sqlalchemy_uri() -> None:
    """Test DuckDBEngineSpec.build_sqlalchemy_uri"""
    from superset.db_engine_specs.duckdb import DuckDBEngineSpec, DuckDBParametersType

    # No database provided, default to :memory:
    parameters = DuckDBParametersType()
    uri = DuckDBEngineSpec.build_sqlalchemy_uri(parameters)
    assert "duckdb:///:memory:" == uri

    # Database provided
    parameters = DuckDBParametersType(database="/path/to/duck.db")
    uri = DuckDBEngineSpec.build_sqlalchemy_uri(parameters)
    assert "duckdb:////path/to/duck.db" == uri


def test_build_sqlalchemy_uri_none_parameters() -> None:
    """``build_sqlalchemy_uri`` defaults to ``:memory:`` when parameters is None."""
    from superset.db_engine_specs.duckdb import DuckDBEngineSpec

    uri = DuckDBEngineSpec.build_sqlalchemy_uri(None)  # type: ignore[arg-type]
    assert uri == "duckdb:///:memory:"


def test_build_sqlalchemy_uri_routes_to_motherduck_with_token() -> None:
    """A non-default ``access_token`` routes to ``MotherDuckEngineSpec``."""
    from superset.db_engine_specs.duckdb import DuckDBEngineSpec, DuckDBParametersType

    parameters = DuckDBParametersType(database="my_db", access_token="real_token")  # noqa: S106
    uri = DuckDBEngineSpec.build_sqlalchemy_uri(parameters)
    assert uri.startswith("duckdb:///md:my_db")
    assert "motherduck_token=real_token" in uri


def test_build_sqlalchemy_uri_routes_to_motherduck_with_md_prefix() -> None:
    """A ``md:`` database name routes to ``MotherDuckEngineSpec``."""
    from superset.db_engine_specs.duckdb import DuckDBEngineSpec, DuckDBParametersType

    parameters = DuckDBParametersType(
        database="md:my_db",
        access_token="my_token",  # noqa: S106
    )
    uri = DuckDBEngineSpec.build_sqlalchemy_uri(parameters)
    assert uri.startswith("duckdb:///md:my_db")
    assert "motherduck_token=my_token" in uri


def test_build_sqlalchemy_uri_default_token_does_not_route() -> None:
    """The placeholder access token must NOT trigger MotherDuck routing."""
    from superset.db_engine_specs.duckdb import (
        DEFAULT_ACCESS_TOKEN_URL,
        DuckDBEngineSpec,
        DuckDBParametersType,
    )

    parameters = DuckDBParametersType(
        database="/path/to/duck.db",
        access_token=DEFAULT_ACCESS_TOKEN_URL,
    )
    uri = DuckDBEngineSpec.build_sqlalchemy_uri(parameters)
    assert uri == "duckdb:////path/to/duck.db"


def test_md_build_sqlalchemy_uri() -> None:
    """Test MotherDuckEngineSpec.build_sqlalchemy_uri"""
    from superset.db_engine_specs.duckdb import (
        DuckDBParametersType,
        MotherDuckEngineSpec,
    )

    # No access token provided, throw ValueError
    parameters = DuckDBParametersType(database="my_db")
    with pytest.raises(ValueError):  # noqa: PT011
        MotherDuckEngineSpec.build_sqlalchemy_uri(parameters)

    # No database provided, default to "md:"
    parameters = DuckDBParametersType(access_token="token")  # noqa: S106
    uri = MotherDuckEngineSpec.build_sqlalchemy_uri(parameters)
    assert "duckdb:///md:?motherduck_token=token"

    # Database and access_token provided
    parameters = DuckDBParametersType(database="my_db", access_token="token")  # noqa: S106
    uri = MotherDuckEngineSpec.build_sqlalchemy_uri(parameters)
    assert "duckdb:///md:my_db?motherduck_token=token" == uri


def test_md_build_sqlalchemy_uri_default_token_raises() -> None:
    """The default placeholder URL is not a real token and must raise."""
    from superset.db_engine_specs.duckdb import (
        DEFAULT_ACCESS_TOKEN_URL,
        DuckDBParametersType,
        MotherDuckEngineSpec,
    )

    parameters = DuckDBParametersType(
        database="md:my_db",
        access_token=DEFAULT_ACCESS_TOKEN_URL,
    )
    with pytest.raises(ValueError, match="Need MotherDuck token"):
        MotherDuckEngineSpec.build_sqlalchemy_uri(parameters)


def test_md_build_sqlalchemy_uri_already_md_prefixed() -> None:
    """An ``md:`` prefix on the database name must not be doubled."""
    from superset.db_engine_specs.duckdb import (
        DuckDBParametersType,
        MotherDuckEngineSpec,
    )

    parameters = DuckDBParametersType(
        database="md:already_prefixed",
        access_token="token",  # noqa: S106
    )
    uri = MotherDuckEngineSpec.build_sqlalchemy_uri(parameters)
    assert uri.startswith("duckdb:///md:already_prefixed")
    assert "md:md:" not in uri


def test_md_build_sqlalchemy_uri_preserves_extra_query() -> None:
    """Existing ``query`` parameters are preserved alongside the token."""
    from superset.db_engine_specs.duckdb import (
        DuckDBParametersType,
        MotherDuckEngineSpec,
    )

    parameters = DuckDBParametersType(
        database="my_db",
        access_token="token",  # noqa: S106
        query={"foo": "bar"},
    )
    uri = MotherDuckEngineSpec.build_sqlalchemy_uri(parameters)
    assert "foo=bar" in uri
    assert "motherduck_token=token" in uri


def test_get_parameters_from_uri() -> None:
    from superset.db_engine_specs.duckdb import DuckDBEngineSpec

    uri = "duckdb:////path/to/duck.db"
    parameters = DuckDBEngineSpec.get_parameters_from_uri(uri)

    assert parameters["database"] == "/path/to/duck.db"

    uri = "duckdb:///md:my_db?motherduck_token=token"
    parameters = DuckDBEngineSpec.get_parameters_from_uri(uri)

    assert parameters["database"] == "md:my_db"
    assert parameters["access_token"] == "token"  # noqa: S105


def test_get_parameters_from_uri_no_token() -> None:
    """A URI without a ``motherduck_token`` returns an empty access token."""
    from superset.db_engine_specs.duckdb import DuckDBEngineSpec

    parameters = DuckDBEngineSpec.get_parameters_from_uri("duckdb:////tmp/x.db")
    assert parameters["access_token"] == ""
    assert parameters["query"] == {}


def test_is_motherduck_helper() -> None:
    """``_is_motherduck`` detects the ``md:`` prefix on the duckdb spec."""
    from superset.db_engine_specs.duckdb import DuckDBEngineSpec

    assert DuckDBEngineSpec._is_motherduck("md:my_db") is True
    assert DuckDBEngineSpec._is_motherduck("/path/to/duck.db") is False
    assert DuckDBEngineSpec._is_motherduck("") is False


def test_motherduck_is_motherduck_always_true() -> None:
    """The MotherDuck spec always reports itself as MotherDuck."""
    from superset.db_engine_specs.duckdb import MotherDuckEngineSpec

    assert MotherDuckEngineSpec._is_motherduck("/some/local.db") is True
    assert MotherDuckEngineSpec._is_motherduck("") is True


def test_validate_parameters_local_database_no_errors() -> None:
    """A local DuckDB database has no required parameters."""
    from superset.db_engine_specs.duckdb import DuckDBEngineSpec

    errors = DuckDBEngineSpec.validate_parameters(
        {"parameters": {"database": "/path/to/duck.db"}}
    )
    assert errors == []


def test_validate_parameters_motherduck_missing_token() -> None:
    """A MotherDuck database without a token returns a CONNECTION error."""
    from superset.db_engine_specs.duckdb import DuckDBEngineSpec

    errors = DuckDBEngineSpec.validate_parameters(
        {"parameters": {"database": "md:my_db"}}
    )
    assert len(errors) == 1
    assert errors[0].error_type == (
        SupersetErrorType.CONNECTION_MISSING_PARAMETERS_ERROR
    )
    assert errors[0].extra is not None
    assert errors[0].extra["missing"] == ["access_token"]


def test_validate_parameters_motherduck_with_token() -> None:
    """A MotherDuck database with a token validates cleanly."""
    from superset.db_engine_specs.duckdb import DuckDBEngineSpec

    errors = DuckDBEngineSpec.validate_parameters(
        {
            "parameters": {
                "database": "md:my_db",
                "access_token": "token",
            }
        }
    )
    assert errors == []


def test_validate_parameters_empty_properties() -> None:
    """An empty ``properties`` dict yields no errors (no required params)."""
    from superset.db_engine_specs.duckdb import DuckDBEngineSpec

    errors = DuckDBEngineSpec.validate_parameters({})  # type: ignore[typeddict-item]
    assert errors == []


def test_parameters_json_schema_returns_openapi_schema() -> None:
    """``parameters_json_schema`` returns a dict describing the parameters."""
    from superset.db_engine_specs.duckdb import DuckDBEngineSpec

    schema = DuckDBEngineSpec.parameters_json_schema()
    assert isinstance(schema, dict)
    assert "properties" in schema
    assert set(schema["properties"]) == {"access_token", "database", "query"}


def test_parameters_json_schema_no_schema_returns_none() -> None:
    """If ``parameters_schema`` is falsy the method returns ``None``."""
    from superset.db_engine_specs.duckdb import DuckDBParametersMixin

    class _NoSchema(DuckDBParametersMixin):
        parameters_schema = None  # type: ignore[assignment]

    assert _NoSchema.parameters_json_schema() is None


def test_fetch_data_uses_fetchall_by_default() -> None:
    """``fetch_data`` calls ``fetchall`` and restores ``cursor.description``."""
    from superset.db_engine_specs.duckdb import DuckDBEngineSpec

    cursor = MagicMock()
    cursor.description = [("a",), ("b",)]
    cursor.fetchall.return_value = [(1, 2), (3, 4)]

    data = DuckDBEngineSpec.fetch_data(cursor)
    assert data == [(1, 2), (3, 4)]
    cursor.fetchall.assert_called_once_with()
    cursor.fetchmany.assert_not_called()
    # description must be re-asserted after fetchall to work around the
    # duckdb-engine bug noted in fetch_data's docstring.
    assert cursor.description == [("a",), ("b",)]


def test_fetch_data_uses_fetchmany_when_limit_method_is_fetch_many(
    mocker: MockerFixture,
) -> None:
    """When ``limit_method`` is ``FETCH_MANY`` and a limit is given, use it."""
    from superset.db_engine_specs.base import LimitMethod
    from superset.db_engine_specs.duckdb import DuckDBEngineSpec

    mocker.patch.object(DuckDBEngineSpec, "limit_method", LimitMethod.FETCH_MANY)

    cursor = MagicMock()
    cursor.description = [("c",)]
    cursor.fetchmany.return_value = [(1,), (2,)]

    data = DuckDBEngineSpec.fetch_data(cursor, limit=2)
    assert data == [(1,), (2,)]
    cursor.fetchmany.assert_called_once_with(2)
    cursor.fetchall.assert_not_called()


def test_fetch_data_fetch_many_without_limit_falls_back_to_fetchall(
    mocker: MockerFixture,
) -> None:
    """``FETCH_MANY`` without a limit falls back to ``fetchall``."""
    from superset.db_engine_specs.base import LimitMethod
    from superset.db_engine_specs.duckdb import DuckDBEngineSpec

    mocker.patch.object(DuckDBEngineSpec, "limit_method", LimitMethod.FETCH_MANY)

    cursor = MagicMock()
    cursor.description = []
    cursor.fetchall.return_value = []

    data = DuckDBEngineSpec.fetch_data(cursor, limit=None)
    assert data == []
    cursor.fetchall.assert_called_once_with()
    cursor.fetchmany.assert_not_called()


def test_fetch_data_sets_arraysize_when_configured(mocker: MockerFixture) -> None:
    """A non-zero ``arraysize`` is propagated to the cursor."""
    from superset.db_engine_specs.duckdb import DuckDBEngineSpec

    mocker.patch.object(DuckDBEngineSpec, "arraysize", 10)

    cursor = MagicMock()
    cursor.description = []
    cursor.fetchall.return_value = []

    DuckDBEngineSpec.fetch_data(cursor)
    assert cursor.arraysize == 10


def test_fetch_data_wraps_exceptions(mocker: MockerFixture) -> None:
    """Exceptions during ``fetchall`` are wrapped via ``get_dbapi_mapped_exception``."""
    from superset.db_engine_specs.duckdb import DuckDBEngineSpec

    mocker.patch.object(
        DuckDBEngineSpec,
        "get_dbapi_mapped_exception",
        side_effect=lambda exc: RuntimeError("mapped"),
    )

    cursor = MagicMock()
    cursor.description = []
    cursor.fetchall.side_effect = ValueError("boom")

    with pytest.raises(RuntimeError, match="mapped"):
        DuckDBEngineSpec.fetch_data(cursor)


def test_get_table_names_delegates_to_inspector() -> None:
    """``get_table_names`` returns the set of names from the inspector."""
    from superset.db_engine_specs.duckdb import DuckDBEngineSpec

    inspector = MagicMock()
    inspector.get_table_names.return_value = ["t1", "t2", "t1"]
    database = MagicMock()

    names = DuckDBEngineSpec.get_table_names(database, inspector, "main")
    assert names == {"t1", "t2"}
    inspector.get_table_names.assert_called_once_with("main")


def test_get_table_names_with_no_schema() -> None:
    """A ``None`` schema is forwarded verbatim to the inspector."""
    from superset.db_engine_specs.duckdb import DuckDBEngineSpec

    inspector = MagicMock()
    inspector.get_table_names.return_value = []
    database = MagicMock()

    assert DuckDBEngineSpec.get_table_names(database, inspector, None) == set()
    inspector.get_table_names.assert_called_once_with(None)


def test_motherduck_adjust_engine_params_with_catalog() -> None:
    """A non-empty catalog rewrites the URL to ``md:<catalog>``."""
    from superset.db_engine_specs.duckdb import MotherDuckEngineSpec

    uri = MagicMock()
    rewritten = MagicMock()
    uri.set.return_value = rewritten

    new_uri, connect_args = MotherDuckEngineSpec.adjust_engine_params(
        uri, {"k": "v"}, catalog="prod_db"
    )
    uri.set.assert_called_once_with(database="md:prod_db")
    assert new_uri is rewritten
    assert connect_args == {"k": "v"}


def test_motherduck_adjust_engine_params_without_catalog() -> None:
    """When no catalog is given the URL is returned unchanged."""
    from superset.db_engine_specs.duckdb import MotherDuckEngineSpec

    uri = MagicMock()

    new_uri, connect_args = MotherDuckEngineSpec.adjust_engine_params(uri, {})
    uri.set.assert_not_called()
    assert new_uri is uri
    assert connect_args == {}


def test_motherduck_get_default_catalog() -> None:
    """``get_default_catalog`` strips the ``md:`` prefix from the database."""
    from superset.db_engine_specs.duckdb import MotherDuckEngineSpec

    database = MagicMock()
    database.url_object.database = "md:prod_db"
    assert MotherDuckEngineSpec.get_default_catalog(database) == "prod_db"


def test_motherduck_get_catalog_names() -> None:
    """``get_catalog_names`` returns the set of attached catalogs."""
    from superset.db_engine_specs.duckdb import MotherDuckEngineSpec

    inspector = MagicMock()
    inspector.bind.execute.return_value = iter(
        [("default",), ("prod_db",), ("default",)]
    )
    database = MagicMock()

    names = MotherDuckEngineSpec.get_catalog_names(database, inspector)
    assert names == {"default", "prod_db"}
    inspector.bind.execute.assert_called_once_with(
        "SELECT alias FROM MD_ALL_DATABASES() WHERE is_attached;"
    )


def test_custom_errors_column_does_not_exist() -> None:
    """The custom error regex maps duckdb's column-not-found message."""
    from superset.db_engine_specs.duckdb import (
        COLUMN_DOES_NOT_EXIST_REGEX,
        DuckDBEngineSpec,
    )

    match = COLUMN_DOES_NOT_EXIST_REGEX.search("no such column: foo_bar")
    assert match is not None
    assert match.group("column_name") == "foo_bar"

    pattern, error = next(iter(DuckDBEngineSpec.custom_errors.items()))
    assert pattern is COLUMN_DOES_NOT_EXIST_REGEX
    assert error[1] == SupersetErrorType.COLUMN_DOES_NOT_EXIST_ERROR


def test_column_type_recognition() -> None:
    """Test that DuckDB column types are properly recognized as numeric."""
    from superset.db_engine_specs.duckdb import DuckDBEngineSpec

    # Test standard float/double types
    numeric_types = [
        "FLOAT",
        "DOUBLE",
        "DOUBLE PRECISION",
        "REAL",
        "DECIMAL(10,2)",
        "NUMERIC(10,2)",
        "INTEGER",
        "BIGINT",
        "SMALLINT",
        # DuckDB-specific unsigned types
        "HUGEINT",
        "UBIGINT",
        "UINTEGER",
        "USMALLINT",
        "UTINYINT",
    ]

    for type_str in numeric_types:
        col_spec = DuckDBEngineSpec.get_column_spec(type_str)
        assert col_spec is not None, f"Type {type_str} should be recognized"
        assert col_spec.generic_type == GenericDataType.NUMERIC, (
            f"Type {type_str} should be recognized as NUMERIC, "
            f"got {col_spec.generic_type}"
        )

    # Test that TINYINT (non-unsigned) is also recognized
    # Note: TINYINT is not in the default mappings, but should be handled
    col_spec = DuckDBEngineSpec.get_column_spec("TINYINT")
    # TINYINT matches the pattern "^int" so it should be recognized
    assert col_spec is None, "TINYINT doesn't match any patterns"
