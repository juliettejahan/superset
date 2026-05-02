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

# pylint: disable=line-too-long, import-outside-toplevel, protected-access, invalid-name

from __future__ import annotations

from datetime import datetime

import pytest
from pytest_mock import MockerFixture
from sqlalchemy import select
from sqlalchemy.engine.url import make_url
from sqlalchemy.sql import sqltypes

pytest.importorskip("sqlalchemy_datastore")
from sqlalchemy_datastore import CloudDatastoreDialect  # noqa: E402

from superset.db_engine_specs.datastore import (
    DatastoreEngineSpec,
    DatastoreParametersType,
)
from superset.sql.parse import Table
from superset.superset_typing import ResultSetColumnType
from superset.utils import json
from tests.unit_tests.db_engine_specs.utils import assert_convert_dttm
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


def test_get_fields() -> None:
    """
    Test the custom ``_get_fields`` method.

    The method adds custom labels (aliases) to the columns to prevent
    collision when referencing record fields. Eg, if we had these two
    columns:

        name STRING
        project STRUCT<name STRING>

    One could write this query:

        SELECT
            `name`,
            `project`.`name`
        FROM
            the_table

    But then both columns would get aliased as "name".

    The custom method will replace the fields so that the final query
    looks like this:

        SELECT
            `name` AS `name`,
            `project`.`name` AS project__name
        FROM
            the_table

    """

    columns: list[ResultSetColumnType] = [
        {"column_name": "limit", "name": "limit", "type": "STRING", "is_dttm": False},
        {"column_name": "name", "name": "name", "type": "STRING", "is_dttm": False},
        {
            "column_name": "project.name",
            "name": "project.name",
            "type": "STRING",
            "is_dttm": False,
        },
    ]
    fields = DatastoreEngineSpec._get_fields(columns)

    query = select(fields)
    assert str(query.compile(dialect=CloudDatastoreDialect())) == (
        'SELECT "limit" AS "limit", name AS name, "project.name" AS project__name'
    )


def test_select_star(mocker: MockerFixture) -> None:
    """
    Test the ``select_star`` method.

    The method removes pseudo-columns from structures inside arrays. While these
    pseudo-columns show up as "columns" for metadata reasons, we can't select them
    in the query, as opposed to fields from non-array structures.
    """

    cols: list[ResultSetColumnType] = [
        {
            "column_name": "trailer",
            "name": "trailer",
            "type": sqltypes.ARRAY(sqltypes.JSON()),
            "nullable": True,
            "comment": None,
            "default": None,
            "precision": None,
            "scale": None,
            "max_length": None,
            "is_dttm": False,
        },
        {
            "column_name": "trailer.key",
            "name": "trailer.key",
            "type": sqltypes.String(),
            "nullable": True,
            "comment": None,
            "default": None,
            "precision": None,
            "scale": None,
            "max_length": None,
            "is_dttm": False,
        },
        {
            "column_name": "trailer.value",
            "name": "trailer.value",
            "type": sqltypes.String(),
            "nullable": True,
            "comment": None,
            "default": None,
            "precision": None,
            "scale": None,
            "max_length": None,
            "is_dttm": False,
        },
        {
            "column_name": "trailer.email",
            "name": "trailer.email",
            "type": sqltypes.String(),
            "nullable": True,
            "comment": None,
            "default": None,
            "precision": None,
            "scale": None,
            "max_length": None,
            "is_dttm": False,
        },
    ]

    # mock the database so we can compile the query
    database = mocker.MagicMock()
    database.compile_sqla_query = lambda query, catalog, schema: str(
        query.compile(
            dialect=CloudDatastoreDialect(), compile_kwargs={"literal_binds": True}
        )
    )

    dialect = CloudDatastoreDialect()

    sql = DatastoreEngineSpec.select_star(
        database=database,
        table=Table("my_table"),
        dialect=dialect,
        limit=100,
        show_cols=True,
        indent=True,
        latest_partition=False,
        cols=cols,
    )
    assert (
        sql
        == """SELECT
  trailer AS trailer
FROM my_table
LIMIT 100"""
    )


def test_get_parameters_from_uri_serializable() -> None:
    """
    Test that the result from ``get_parameters_from_uri`` is JSON serializable.
    """

    parameters = DatastoreEngineSpec.get_parameters_from_uri(
        "datastore://dbt-tutorial-347100/",
        {"access_token": "TOP_SECRET"},
    )
    assert parameters == {"access_token": "TOP_SECRET", "query": {}}
    assert json.loads(json.dumps(parameters)) == parameters


def test_unmask_encrypted_extra() -> None:
    """
    Test that the private key can be reused from the previous `encrypted_extra`.
    """

    old = json.dumps(
        {
            "credentials_info": {
                "project_id": "black-sanctum-314419",
                "private_key": "SECRET",
            },
        }
    )
    new = json.dumps(
        {
            "credentials_info": {
                "project_id": "yellow-unicorn-314419",
                "private_key": "XXXXXXXXXX",
            },
        }
    )

    assert DatastoreEngineSpec.unmask_encrypted_extra(old, new) == json.dumps(
        {
            "credentials_info": {
                "project_id": "yellow-unicorn-314419",
                "private_key": "SECRET",
            },
        }
    )


def test_unmask_encrypted_extra_field_changed() -> None:
    """
    Test that the private key is not reused when the field has changed.
    """

    old = json.dumps(
        {
            "credentials_info": {
                "project_id": "black-sanctum-314419",
                "private_key": "SECRET",
            },
        }
    )
    new = json.dumps(
        {
            "credentials_info": {
                "project_id": "yellow-unicorn-314419",
                "private_key": "NEW-SECRET",
            },
        }
    )

    assert DatastoreEngineSpec.unmask_encrypted_extra(old, new) == json.dumps(
        {
            "credentials_info": {
                "project_id": "yellow-unicorn-314419",
                "private_key": "NEW-SECRET",
            },
        }
    )


def test_unmask_encrypted_extra_when_old_is_none() -> None:
    """
    Test that a `None` value for the old field works for `encrypted_extra`.
    """

    old = None
    new = json.dumps(
        {
            "credentials_info": {
                "project_id": "yellow-unicorn-314419",
                "private_key": "XXXXXXXXXX",
            },
        }
    )

    assert DatastoreEngineSpec.unmask_encrypted_extra(old, new) == json.dumps(
        {
            "credentials_info": {
                "project_id": "yellow-unicorn-314419",
                "private_key": "XXXXXXXXXX",
            },
        }
    )


def test_unmask_encrypted_extra_when_new_is_none() -> None:
    """
    Test that a `None` value for the new field works for `encrypted_extra`.
    """

    old = json.dumps(
        {
            "credentials_info": {
                "project_id": "black-sanctum-314419",
                "private_key": "SECRET",
            },
        }
    )
    new = None

    assert DatastoreEngineSpec.unmask_encrypted_extra(old, new) is None


def test_mask_encrypted_extra() -> None:
    """
    Test that the private key is masked when the database is edited.
    """

    config = json.dumps(
        {
            "credentials_info": {
                "project_id": "black-sanctum-314419",
                "private_key": "SECRET",
            },
        }
    )

    assert DatastoreEngineSpec.mask_encrypted_extra(config) == json.dumps(
        {
            "credentials_info": {
                "project_id": "black-sanctum-314419",
                "private_key": "XXXXXXXXXX",
            },
        }
    )


def test_mask_encrypted_extra_when_empty() -> None:
    """
    Test that the encrypted extra will return a none value if the field is empty.
    """

    assert DatastoreEngineSpec.mask_encrypted_extra(None) is None


def test_parse_error_message() -> None:
    """
    Test that we parse a received message and just extract the useful information.

    Example errors:
    datastore error: 400 Syntax error:  Table \"case_detail_all_suites\" must be qualified with a dataset (e.g. dataset.table).

    (job ID: ddf30b05-44e8-4fbf-aa29-40bfccaed886)
                                                -----Query Job SQL Follows-----
    |    .    |    .    |    .    |\n   1:select * from case_detail_all_suites\n   2:LIMIT 1001\n    |    .    |    .    |    .    |
    """  # noqa: E501

    message = 'datastore error: 400 Syntax error: Table "case_detail_all_suites" must be qualified with a dataset (e.g. dataset.table).\n\n(job ID: ddf30b05-44e8-4fbf-aa29-40bfccaed886)\n\n     -----Query Job SQL Follows-----     \n\n    |    .    |    .    |    .    |\n   1:select * from case_detail_all_suites\n   2:LIMIT 1001\n    |    .    |    .    |    .    |'  # noqa: E501
    expected_result = 'datastore error: 400 Syntax error: Table "case_detail_all_suites" must be qualified with a dataset (e.g. dataset.table).'  # noqa: E501
    assert (
        str(DatastoreEngineSpec.parse_error_exception(Exception(message)))
        == expected_result
    )


def test_parse_error_raises_exception() -> None:
    """
    Test that we handle any exception we might get from calling the parse_error_exception method.

    Example errors:
    400 Syntax error: Expected "(" or keyword UNNEST but got "@" at [4:80]
    datastore error: 400 Table \"case_detail_all_suites\" must be qualified with a dataset (e.g. dataset.table).
    """  # noqa: E501

    message = 'datastore error: 400 Syntax error: Table "case_detail_all_suites" must be qualified with a dataset (e.g. dataset.table).'  # noqa: E501
    message_2 = "6"
    expected_result = 'datastore error: 400 Syntax error: Table "case_detail_all_suites" must be qualified with a dataset (e.g. dataset.table).'  # noqa: E501
    assert (
        str(DatastoreEngineSpec.parse_error_exception(Exception(message)))
        == expected_result
    )
    assert str(DatastoreEngineSpec.parse_error_exception(Exception(message_2))) == "6"


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Date", "CAST('2019-01-02' AS DATE)"),
        ("DateTime", "CAST('2019-01-02T03:04:05.678900' AS DATETIME)"),
        ("TimeStamp", "CAST('2019-01-02T03:04:05.678900' AS TIMESTAMP)"),
        ("Time", "CAST('03:04:05.678900' AS TIME)"),
        ("UnknownType", None),
    ],
)
def test_convert_dttm(
    target_type: str,
    expected_result: str | None,
    dttm: datetime,  # noqa: F811
) -> None:
    """
    DB Eng Specs (datastore): Test conversion to date time
    """
    assert_convert_dttm(DatastoreEngineSpec, target_type, expected_result, dttm)


def test_get_default_catalog(mocker: MockerFixture) -> None:
    """
    Test that we get the default catalog from the connection URI.
    """
    from superset.models.core import Database

    mocker.patch.object(Database, "get_sqla_engine")
    get_client = mocker.patch.object(DatastoreEngineSpec, "_get_client")
    get_client().project = "project"

    database = Database(
        database_name="my_db",
        sqlalchemy_uri="datastore://project",
    )
    assert DatastoreEngineSpec.get_default_catalog(database) == "project"

    database = Database(
        database_name="my_db",
        sqlalchemy_uri="datastore:///project",
    )
    assert DatastoreEngineSpec.get_default_catalog(database) == "project"

    database = Database(
        database_name="my_db",
        sqlalchemy_uri="datastore://",
    )
    assert DatastoreEngineSpec.get_default_catalog(database) == "project"


def test_adjust_engine_params_catalog_as_host() -> None:
    """
    Test passing a custom catalog.

    In this test, the original URI has the catalog as the host.
    """

    url = make_url("datastore://project")

    uri = DatastoreEngineSpec.adjust_engine_params(url, {})[0]
    assert str(uri) == "datastore://project"

    uri = DatastoreEngineSpec.adjust_engine_params(
        url,
        {},
        catalog="other-project",
    )[0]
    assert str(uri) == "datastore://other-project/"


def test_adjust_engine_params_catalog_as_database() -> None:
    """
    Test passing a custom catalog.

    In this test, the original URI has the catalog as the database.
    """

    url = make_url("datastore:///project")

    uri = DatastoreEngineSpec.adjust_engine_params(url, {})[0]
    assert str(uri) == "datastore:///project"

    uri = DatastoreEngineSpec.adjust_engine_params(
        url,
        {},
        catalog="other-project",
    )[0]
    assert str(uri) == "datastore://other-project/"


def test_adjust_engine_params_no_catalog() -> None:
    """
    Test passing a custom catalog.

    In this test, the original URI has no catalog.
    """

    url = make_url("datastore://")

    uri = DatastoreEngineSpec.adjust_engine_params(url, {})[0]
    assert str(uri) == "datastore://"

    uri = DatastoreEngineSpec.adjust_engine_params(
        url,
        {},
        catalog="other-project",
    )[0]
    assert str(uri) == "datastore://other-project/"


def test_get_client_passes_database_from_url(mocker: MockerFixture) -> None:
    """
    Test that ``_get_client`` passes the ``database`` query parameter
    from the engine URL through to ``datastore.Client``.
    """

    mock_client_cls = mocker.patch(
        "superset.db_engine_specs.datastore.datastore.Client"
    )
    mocker.patch(
        "superset.db_engine_specs.datastore.service_account"
        ".Credentials.from_service_account_info",
        return_value=mocker.MagicMock(),
    )

    engine = mocker.MagicMock()
    engine.dialect.credentials_info = {"project_id": "my-project", "private_key": "k"}
    engine.url.query = {"database": "my-db"}

    database = mocker.MagicMock()

    DatastoreEngineSpec._get_client(engine, database)
    mock_client_cls.assert_called_once_with(credentials=mocker.ANY, database="my-db")


def test_get_client_passes_none_when_no_database(mocker: MockerFixture) -> None:
    """
    Test that ``_get_client`` passes ``database=None`` when the URL
    has no ``database`` query parameter.
    """

    mock_client_cls = mocker.patch(
        "superset.db_engine_specs.datastore.datastore.Client"
    )
    mocker.patch(
        "superset.db_engine_specs.datastore.service_account"
        ".Credentials.from_service_account_info",
        return_value=mocker.MagicMock(),
    )

    engine = mocker.MagicMock()
    engine.dialect.credentials_info = {"project_id": "my-project", "private_key": "k"}
    engine.url.query = {}

    database = mocker.MagicMock()

    DatastoreEngineSpec._get_client(engine, database)
    mock_client_cls.assert_called_once_with(credentials=mocker.ANY, database=None)


def test_get_client_default_credentials_passes_database(
    mocker: MockerFixture,
) -> None:
    """
    Test that ``_get_client`` passes ``database`` when falling back
    to default credentials.
    """

    mock_client_cls = mocker.patch(
        "superset.db_engine_specs.datastore.datastore.Client"
    )
    mocker.patch(
        "superset.db_engine_specs.datastore.google.auth.default",
        return_value=(mocker.MagicMock(), "my-project"),
    )

    engine = mocker.MagicMock()
    engine.dialect.credentials_info = None
    engine.url.query = {"database": "other-db"}

    database = mocker.MagicMock()

    DatastoreEngineSpec._get_client(engine, database)
    mock_client_cls.assert_called_once_with(credentials=mocker.ANY, database="other-db")


def test_parameters_json_schema_has_encrypted_extra() -> None:
    """
    Test that ``parameters_json_schema`` marks ``credentials_info`` with
    ``x-encrypted-extra`` so the frontend moves credentials into
    ``masked_encrypted_extra``.
    """

    schema = DatastoreEngineSpec.parameters_json_schema()
    assert schema is not None
    credentials_info = schema["properties"]["credentials_info"]
    assert credentials_info["x-encrypted-extra"] is True


def test_execute_with_cursor_no_warnings(mocker: MockerFixture) -> None:
    """
    Test ``execute_with_cursor`` delegates to the base class and does not
    set warnings when the cursor has none.
    """

    mocker.patch(
        "superset.db_engine_specs.base.BaseEngineSpec.execute_with_cursor",
    )

    cursor = mocker.MagicMock()
    cursor.warnings = []
    query = mocker.MagicMock()

    DatastoreEngineSpec.execute_with_cursor(cursor, "SELECT 1", query)
    query.set_extra_json_key.assert_not_called()


def test_execute_with_cursor_with_warnings(mocker: MockerFixture) -> None:
    """
    Test ``execute_with_cursor`` stores cursor warnings in the query's
    ``extra_json`` when the cursor reports warnings.
    """

    mocker.patch(
        "superset.db_engine_specs.base.BaseEngineSpec.execute_with_cursor",
    )

    cursor = mocker.MagicMock()
    cursor.warnings = ["Missing composite index for query"]
    query = mocker.MagicMock()

    DatastoreEngineSpec.execute_with_cursor(cursor, "SELECT * FROM Kind", query)
    query.set_extra_json_key.assert_called_once_with(
        "warnings", ["Missing composite index for query"]
    )


def test_execute_with_cursor_no_warnings_attr(mocker: MockerFixture) -> None:
    """
    Test ``execute_with_cursor`` does not fail when the cursor has no
    ``warnings`` attribute.
    """

    mocker.patch(
        "superset.db_engine_specs.base.BaseEngineSpec.execute_with_cursor",
    )

    cursor = mocker.MagicMock(spec=[])  # no attributes at all
    query = mocker.MagicMock()

    DatastoreEngineSpec.execute_with_cursor(cursor, "SELECT 1", query)
    query.set_extra_json_key.assert_not_called()


def test_get_client_dependencies_not_installed(mocker: MockerFixture) -> None:
    """
    Test that ``_get_client`` raises ``SupersetException`` when the
    google-cloud-datastore package is not installed.
    """
    from superset.exceptions import SupersetException

    mocker.patch(
        "superset.db_engine_specs.datastore.dependencies_installed",
        False,
    )

    engine = mocker.MagicMock()
    database = mocker.MagicMock()

    with pytest.raises(SupersetException, match="Could not import libraries"):
        DatastoreEngineSpec._get_client(engine, database)


def test_get_client_default_credentials_error(mocker: MockerFixture) -> None:
    """
    Test that ``_get_client`` raises ``SupersetDBAPIConnectionError`` when
    google.auth.default() fails.
    """
    from google.auth.exceptions import DefaultCredentialsError

    from superset.db_engine_specs.exceptions import SupersetDBAPIConnectionError

    mocker.patch(
        "superset.db_engine_specs.datastore.google.auth.default",
        side_effect=DefaultCredentialsError("No credentials found"),
    )

    engine = mocker.MagicMock()
    engine.dialect.credentials_info = None
    engine.url.query = {}
    database = mocker.MagicMock()

    with pytest.raises(
        SupersetDBAPIConnectionError,
        match="database credentials could not be found",
    ):
        DatastoreEngineSpec._get_client(engine, database)


def test_fetch_data_regular_tuples(mocker: MockerFixture) -> None:
    """
    Test ``fetch_data`` with regular tuple rows passes them through unchanged.
    """
    from superset.db_engine_specs.base import BaseEngineSpec

    data = [(1, "foo"), (2, "bar")]
    mocker.patch.object(BaseEngineSpec, "fetch_data", return_value=data)

    result = DatastoreEngineSpec.fetch_data(mocker.MagicMock(), 0)
    assert result == [(1, "foo"), (2, "bar")]


def test_fetch_data_with_row_objects(mocker: MockerFixture) -> None:
    """
    Test ``fetch_data`` with google.cloud.datastore Row-like objects that
    have a ``values()`` method.
    """
    from superset.db_engine_specs.base import BaseEngineSpec

    class Row:
        def __init__(self, val: tuple[int, str]) -> None:
            self._val = val

        def values(self) -> tuple[int, str]:
            return self._val

    data = [Row((1, "a")), Row((2, "b"))]
    mocker.patch.object(BaseEngineSpec, "fetch_data", return_value=data)

    result = DatastoreEngineSpec.fetch_data(mocker.MagicMock(), 0)
    assert result == [(1, "a"), (2, "b")]


def test_fetch_data_empty(mocker: MockerFixture) -> None:
    """
    Test ``fetch_data`` with an empty result set.
    """
    from superset.db_engine_specs.base import BaseEngineSpec

    mocker.patch.object(BaseEngineSpec, "fetch_data", return_value=[])

    result = DatastoreEngineSpec.fetch_data(mocker.MagicMock(), 0)
    assert result == []


def test_build_sqlalchemy_uri() -> None:
    """
    Test building a SQLAlchemy URI from parameters and encrypted_extra.
    """

    parameters: DatastoreParametersType = {
        "credentials_info": {},
        "query": {},
    }
    encrypted_extra = {
        "credentials_info": {
            "project_id": "my-project",
            "private_key": "SECRET",
        }
    }
    result = DatastoreEngineSpec.build_sqlalchemy_uri(parameters, encrypted_extra)
    assert result == "datastore://my-project/?"


def test_build_sqlalchemy_uri_with_query_params() -> None:
    """
    Test building a SQLAlchemy URI with query parameters.
    """

    parameters: DatastoreParametersType = {
        "credentials_info": {},
        "query": {"database": "my-db"},
    }
    encrypted_extra = {
        "credentials_info": {
            "project_id": "my-project",
            "private_key": "SECRET",
        }
    }
    result = DatastoreEngineSpec.build_sqlalchemy_uri(parameters, encrypted_extra)
    assert result == "datastore://my-project/?database=my-db"


def test_build_sqlalchemy_uri_string_credentials() -> None:
    """
    Test building a URI when ``credentials_info`` is a JSON string.
    """

    parameters: DatastoreParametersType = {
        "credentials_info": {},
        "query": {},
    }
    encrypted_extra = {
        "credentials_info": json.dumps(
            {"project_id": "string-project", "private_key": "SECRET"}
        )
    }
    result = DatastoreEngineSpec.build_sqlalchemy_uri(parameters, encrypted_extra)
    assert result == "datastore://string-project/?"


def test_build_sqlalchemy_uri_missing_encrypted_extra() -> None:
    """
    Test that ``build_sqlalchemy_uri`` raises ``ValidationError`` when
    ``encrypted_extra`` is None.
    """
    from marshmallow.exceptions import ValidationError

    parameters: DatastoreParametersType = {"credentials_info": {}, "query": {}}
    with pytest.raises(ValidationError, match="Missing service credentials"):
        DatastoreEngineSpec.build_sqlalchemy_uri(parameters, None)


def test_build_sqlalchemy_uri_missing_project_id() -> None:
    """
    Test that ``build_sqlalchemy_uri`` raises ``ValidationError`` when
    ``project_id`` is missing from credentials.
    """
    from marshmallow.exceptions import ValidationError

    parameters: DatastoreParametersType = {"credentials_info": {}, "query": {}}
    encrypted_extra = {"credentials_info": {"private_key": "SECRET"}}
    with pytest.raises(ValidationError, match="Invalid service credentials"):
        DatastoreEngineSpec.build_sqlalchemy_uri(parameters, encrypted_extra)


def test_get_parameters_from_uri() -> None:
    """
    Test extracting parameters from a URI with encrypted_extra.
    """

    encrypted_extra = {
        "credentials_info": {
            "project_id": "my-project",
            "private_key": "SECRET",
        }
    }
    result = DatastoreEngineSpec.get_parameters_from_uri(
        "datastore://my-project/?database=my-db",
        encrypted_extra,
    )
    assert result == {
        "credentials_info": {
            "project_id": "my-project",
            "private_key": "SECRET",
        },
        "query": {"database": "my-db"},
    }


def test_get_parameters_from_uri_missing_credentials() -> None:
    """
    Test that ``get_parameters_from_uri`` raises ``ValidationError`` when
    ``encrypted_extra`` is None.
    """
    from marshmallow.exceptions import ValidationError

    with pytest.raises(ValidationError, match="Invalid service credentials"):
        DatastoreEngineSpec.get_parameters_from_uri("datastore://project/", None)


def test_validate_parameters_returns_empty() -> None:
    """
    Test that ``validate_parameters`` returns an empty list (validation
    is a no-op for Datastore).
    """

    result = DatastoreEngineSpec.validate_parameters(
        {
            "parameters": {
                "host": "",
                "port": 0,
                "username": "",
                "password": "",
                "database": "",
                "query": {},
            },
        }
    )
    assert result == []


def test_get_allow_cost_estimate() -> None:
    """
    Test that cost estimation is not supported.
    """

    assert DatastoreEngineSpec.get_allow_cost_estimate({}) is False


def test_get_function_names(mocker: MockerFixture) -> None:
    """
    Test that ``get_function_names`` returns the expected GQL functions.
    """

    database = mocker.MagicMock()
    result = DatastoreEngineSpec.get_function_names(database)
    assert result == ["sum", "avg", "count", "count_up_to", "min", "max"]


def test_get_view_names(mocker: MockerFixture) -> None:
    """
    Test that ``get_view_names`` returns an empty set because Datastore
    has no view concept.
    """

    result = DatastoreEngineSpec.get_view_names(
        mocker.MagicMock(), mocker.MagicMock(), "some_schema"
    )
    assert result == set()


def test_get_dbapi_exception_mapping() -> None:
    """
    Test that the DBAPI exception mapping maps ``DefaultCredentialsError``
    to ``SupersetDBAPIConnectionError``.
    """
    from superset.db_engine_specs.exceptions import SupersetDBAPIConnectionError

    mapping = DatastoreEngineSpec.get_dbapi_exception_mapping()
    assert len(mapping) == 1
    exc_cls = next(iter(mapping))
    assert exc_cls.__name__ == "DefaultCredentialsError"
    assert mapping[exc_cls] is SupersetDBAPIConnectionError


def test_mutate_label_simple() -> None:
    """
    Test ``_mutate_label`` with labels that need no mutation.
    """

    assert DatastoreEngineSpec._mutate_label("col") == "col"
    assert DatastoreEngineSpec._mutate_label("my_column") == "my_column"
    assert DatastoreEngineSpec._mutate_label("_private") == "_private"


def test_mutate_label_starts_with_digit() -> None:
    """
    Test ``_mutate_label`` prefixes an underscore when the label starts
    with a digit.
    """

    result = DatastoreEngineSpec._mutate_label("123col")
    assert result.startswith("_123col")
    # Hash suffix is added because the label was mutated
    assert len(result) > len("_123col")


def test_mutate_label_special_characters() -> None:
    """
    Test ``_mutate_label`` replaces non-alphanumeric characters and adds
    a hash suffix.
    """

    result = DatastoreEngineSpec._mutate_label("SUM(x)")
    assert result.startswith("SUM_x_")
    # Should have a hash suffix
    assert "_" in result[5:]


def test_truncate_label() -> None:
    """
    Test ``_truncate_label`` returns a hash prefixed with underscore.
    """

    result = DatastoreEngineSpec._truncate_label("some_very_long_label")
    assert result.startswith("_")
    # The hash should be deterministic
    assert result == DatastoreEngineSpec._truncate_label("some_very_long_label")
    # Different labels produce different hashes
    assert result != DatastoreEngineSpec._truncate_label("another_label")


def test_select_star_without_cols(mocker: MockerFixture) -> None:
    """
    Test ``select_star`` when no columns are provided (cols=None).
    """

    database = mocker.MagicMock()
    database.compile_sqla_query = lambda query, catalog, schema: str(
        query.compile(
            dialect=CloudDatastoreDialect(), compile_kwargs={"literal_binds": True}
        )
    )
    dialect = CloudDatastoreDialect()

    sql = DatastoreEngineSpec.select_star(
        database=database,
        table=Table("my_table"),
        dialect=dialect,
        limit=100,
        show_cols=False,
        indent=True,
        latest_partition=False,
        cols=None,
    )
    assert "FROM my_table" in sql
    assert "LIMIT 100" in sql


def test_get_catalog_names(mocker: MockerFixture) -> None:
    """
    Test that ``get_catalog_names`` delegates to the base class.
    """

    database = mocker.MagicMock()
    inspector = mocker.MagicMock()
    inspector.bind.execute.return_value = []

    mocker.patch(
        "superset.db_engine_specs.base.BaseEngineSpec.get_catalog_names",
        return_value={"my-project"},
    )

    result = DatastoreEngineSpec.get_catalog_names(database, inspector)
    assert result == {"my-project"}


def test_get_client_default_credentials_no_database(mocker: MockerFixture) -> None:
    """
    Test that ``_get_client`` falls back to default credentials and passes
    ``database=None`` when the URL has no ``database`` query parameter.
    """

    mock_client_cls = mocker.patch(
        "superset.db_engine_specs.datastore.datastore.Client"
    )
    mocker.patch(
        "superset.db_engine_specs.datastore.google.auth.default",
        return_value=(mocker.MagicMock(), "my-project"),
    )

    engine = mocker.MagicMock()
    engine.dialect.credentials_info = None
    engine.url.query = {}

    database = mocker.MagicMock()

    DatastoreEngineSpec._get_client(engine, database)
    mock_client_cls.assert_called_once_with(credentials=mocker.ANY, database=None)


def test_parameters_json_schema_returns_none_without_schema(
    mocker: MockerFixture,
) -> None:
    """
    Test that ``parameters_json_schema`` returns ``None`` when the engine spec
    has no ``parameters_schema`` defined.
    """

    mocker.patch.object(DatastoreEngineSpec, "parameters_schema", None)
    assert DatastoreEngineSpec.parameters_json_schema() is None


def test_parse_error_exception_fallback_on_construction_failure() -> None:
    """
    Test ``parse_error_exception`` returns the original exception when the
    exception type cannot be reconstructed from a single string argument.

    Some exception subclasses require multiple positional arguments in their
    ``__init__`` (e.g. ``code`` plus ``message``). In that case, calling
    ``type(exception)("...")`` raises ``TypeError``; the helper should fall
    back to returning the original exception unchanged.
    """

    class StrictError(Exception):
        def __init__(self, code: int, message: str) -> None:
            super().__init__(message)
            self.code = code
            self.message = message

    original = StrictError(500, "boom\nsecond line")
    result = DatastoreEngineSpec.parse_error_exception(original)
    assert result is original


def test_parse_error_exception_empty_message() -> None:
    """
    Test ``parse_error_exception`` returns the original exception when the
    exception's string form has no lines (empty string).
    """

    original = Exception("")
    result = DatastoreEngineSpec.parse_error_exception(original)
    assert result is original


def test_module_dependencies_not_installed_attribute(mocker: MockerFixture) -> None:
    """
    Test that the ``dependencies_installed`` flag in the module can be
    monkeypatched, exercising the ``ImportError`` fallback path indirectly
    by validating the runtime check it controls.
    """
    from superset.exceptions import SupersetException

    mocker.patch(
        "superset.db_engine_specs.datastore.dependencies_installed",
        False,
    )
    engine = mocker.MagicMock()
    database = mocker.MagicMock()

    with pytest.raises(SupersetException, match="Could not import"):
        DatastoreEngineSpec._get_client(engine, database)


def test_select_star_with_no_array_columns(mocker: MockerFixture) -> None:
    """
    Test ``select_star`` with columns but none of them are arrays, so no
    columns should be filtered out.
    """

    cols: list[ResultSetColumnType] = [
        {
            "column_name": "name",
            "name": "name",
            "type": sqltypes.String(),
            "nullable": True,
            "comment": None,
            "default": None,
            "precision": None,
            "scale": None,
            "max_length": None,
            "is_dttm": False,
        },
        {
            "column_name": "age",
            "name": "age",
            "type": sqltypes.Integer(),
            "nullable": True,
            "comment": None,
            "default": None,
            "precision": None,
            "scale": None,
            "max_length": None,
            "is_dttm": False,
        },
    ]

    database = mocker.MagicMock()
    database.compile_sqla_query = lambda query, catalog, schema: str(
        query.compile(
            dialect=CloudDatastoreDialect(), compile_kwargs={"literal_binds": True}
        )
    )
    dialect = CloudDatastoreDialect()

    sql = DatastoreEngineSpec.select_star(
        database=database,
        table=Table("my_table"),
        dialect=dialect,
        limit=100,
        show_cols=True,
        indent=True,
        latest_partition=False,
        cols=cols,
    )
    assert "name" in sql
    assert "age" in sql
    assert "FROM my_table" in sql


def test_engine_class_attributes() -> None:
    """
    Test the static configuration attributes of ``DatastoreEngineSpec``.
    """
    from superset.sql.parse import LimitMethod

    assert DatastoreEngineSpec.engine == "datastore"
    assert DatastoreEngineSpec.engine_name == "Google Datastore"
    assert DatastoreEngineSpec.default_driver == "datastore"
    assert DatastoreEngineSpec.max_column_name_length == 128
    assert DatastoreEngineSpec.disable_ssh_tunneling is True
    assert DatastoreEngineSpec.run_multiple_statements_as_one is True
    assert DatastoreEngineSpec.allows_hidden_cc_in_orderby is True
    assert DatastoreEngineSpec.supports_dynamic_schema is True
    assert DatastoreEngineSpec.supports_catalog is True
    assert DatastoreEngineSpec.supports_dynamic_catalog is True
    assert DatastoreEngineSpec.supports_cross_catalog_queries is True
    assert DatastoreEngineSpec.limit_method == LimitMethod.FETCH_MANY
    assert DatastoreEngineSpec.arraysize == 5000
    assert DatastoreEngineSpec.encrypted_extra_sensitive_fields == {
        "$.credentials_info.private_key"
    }


def test_metadata_describes_database() -> None:
    """
    Test the metadata dictionary that drives the database picker UI.
    """
    metadata = DatastoreEngineSpec.metadata
    assert metadata["logo"] == "datastore.png"
    assert metadata["homepage_url"] == "https://cloud.google.com/datastore/"
    assert "python-datastore-sqlalchemy" in metadata["pypi_packages"]
    assert metadata["connection_string"].startswith("datastore://")
    auth_methods = metadata["authentication_methods"]
    assert len(auth_methods) == 1
    assert auth_methods[0]["name"] == "Service Account JSON"


def test_time_grain_expressions_have_required_grains() -> None:
    """
    Test that the ``_time_grain_expressions`` dictionary supports the
    grains the Datastore spec advertises.
    """
    from superset.constants import TimeGrain

    grains = DatastoreEngineSpec._time_grain_expressions
    expected_grains = {
        None,
        TimeGrain.SECOND,
        TimeGrain.MINUTE,
        TimeGrain.FIVE_MINUTES,
        TimeGrain.TEN_MINUTES,
        TimeGrain.FIFTEEN_MINUTES,
        TimeGrain.THIRTY_MINUTES,
        TimeGrain.HOUR,
        TimeGrain.DAY,
        TimeGrain.WEEK,
        TimeGrain.WEEK_STARTING_MONDAY,
        TimeGrain.MONTH,
        TimeGrain.QUARTER,
        TimeGrain.YEAR,
    }
    assert expected_grains.issubset(set(grains.keys()))
    # The default identity expression should preserve the column name.
    assert grains[None] == "{col}"


def test_date_trunc_functions() -> None:
    """
    Test the ``_date_trunc_functions`` mapping covers the SQL date types.
    """
    funcs = DatastoreEngineSpec._date_trunc_functions
    assert funcs["DATE"] == "DATE_TRUNC"
    assert funcs["DATETIME"] == "DATETIME_TRUNC"
    assert funcs["TIME"] == "TIME_TRUNC"
    assert funcs["TIMESTAMP"] == "TIMESTAMP_TRUNC"


def test_custom_errors_match_expected_patterns() -> None:
    """
    Test the ``custom_errors`` regex-to-message mapping triggers on the
    expected error strings.
    """

    errors = DatastoreEngineSpec.custom_errors
    permission_msg = (
        "Access Denied: Project my-project: User does not have "
        "datastore.databases.create permission in project my-project"
    )
    table_msg = (
        'Table name "my_table" missing dataset while no default '
        "dataset is set in the request"
    )
    column_msg = "Unrecognized name: my_col at [3:14]"
    schema_msg = "datastore error: 404 Not found: Dataset proj:my_schema was not found in location"  # noqa: E501
    syntax_msg = 'Syntax error: Expected end of input but got identifier "FROM"'

    assert any(pattern.search(permission_msg) for pattern in errors)
    assert any(pattern.search(table_msg) for pattern in errors)
    assert any(pattern.search(column_msg) for pattern in errors)
    assert any(pattern.search(schema_msg) for pattern in errors)
    assert any(pattern.search(syntax_msg) for pattern in errors)


def test_mutate_label_label_unchanged_no_hash() -> None:
    """
    Test ``_mutate_label`` does not append a hash suffix when the label
    requires no mutation.
    """

    label = "regular_label"
    result = DatastoreEngineSpec._mutate_label(label)
    # No change, so no hash suffix appended.
    assert result == label


def test_truncate_label_distinct_inputs_produce_distinct_outputs() -> None:
    """
    Test ``_truncate_label`` is deterministic and discriminates between
    different inputs.
    """

    a = DatastoreEngineSpec._truncate_label("alpha")
    b = DatastoreEngineSpec._truncate_label("beta")
    a_again = DatastoreEngineSpec._truncate_label("alpha")
    assert a == a_again
    assert a != b
    assert a.startswith("_")


def test_get_default_catalog_uses_database_path(mocker: MockerFixture) -> None:
    """
    Test that ``get_default_catalog`` returns the project from the URL
    database part when the host is empty.
    """
    from superset.models.core import Database

    mocker.patch.object(Database, "get_sqla_engine")
    mocker.patch.object(DatastoreEngineSpec, "_get_client")

    database = Database(
        database_name="my_db",
        sqlalchemy_uri="datastore:///path-project",
    )
    assert DatastoreEngineSpec.get_default_catalog(database) == "path-project"


def test_get_dbapi_exception_mapping_imports_lazily() -> None:
    """
    Test ``get_dbapi_exception_mapping`` imports DefaultCredentialsError
    from ``google.auth.exceptions`` lazily and exposes the canonical
    Superset connection-error class as the target.
    """
    from google.auth.exceptions import DefaultCredentialsError

    from superset.db_engine_specs.exceptions import SupersetDBAPIConnectionError

    mapping = DatastoreEngineSpec.get_dbapi_exception_mapping()
    assert mapping == {DefaultCredentialsError: SupersetDBAPIConnectionError}


def test_get_parameters_from_uri_with_query_params() -> None:
    """
    Test that ``get_parameters_from_uri`` round-trips multiple query
    parameters into the ``query`` dict.
    """

    encrypted_extra = {"credentials_info": {"project_id": "p", "private_key": "K"}}
    result = DatastoreEngineSpec.get_parameters_from_uri(
        "datastore://p/?database=my-db&foo=bar",
        encrypted_extra,
    )
    assert result["query"] == {"database": "my-db", "foo": "bar"}


def test_validate_parameters_does_not_raise() -> None:
    """
    Test ``validate_parameters`` is a no-op for arbitrary inputs.
    """

    properties: dict[str, dict[str, str]] = {
        "parameters": {"anything": "goes"},
    }
    # Cast to expected type via direct call; the implementation ignores
    # the input completely.
    assert DatastoreEngineSpec.validate_parameters(properties) == []  # type: ignore[arg-type]


def test_module_import_handles_missing_google_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test that the module reports ``dependencies_installed = False`` when the
    optional Google Cloud Datastore dependencies are missing at import time.

    The module catches ``ImportError`` when ``google.cloud.datastore`` (and
    related packages) are not installed, falling back to ``False`` so the
    runtime check in ``_get_client`` can surface a friendly error.
    """
    import importlib
    import sys

    # Save original modules so we can restore them after the test.
    saved_modules: dict[str, object] = {}
    for name in list(sys.modules):
        if name.startswith("google") or name == "superset.db_engine_specs.datastore":
            saved_modules[name] = sys.modules[name]

    try:
        # Remove the cached datastore module and any google.* modules so the
        # reimport will hit the ImportError fallback.
        for name in list(sys.modules):
            if (
                name.startswith("google")
                or name == "superset.db_engine_specs.datastore"
            ):
                del sys.modules[name]

        # Block the ``google.cloud.datastore`` import to trigger the
        # ImportError branch on module load.
        import builtins

        real_import = builtins.__import__

        def fake_import(
            name: str,
            globals: dict[str, object] | None = None,  # noqa: A002
            locals: dict[str, object] | None = None,  # noqa: A002
            fromlist: tuple[str, ...] = (),
            level: int = 0,
        ) -> object:
            if name in {
                "google.auth",
                "google.cloud",
                "google.oauth2",
            } or name.startswith(("google.auth.", "google.cloud.", "google.oauth2.")):
                raise ImportError(f"forced failure for {name}")
            return real_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr("builtins.__import__", fake_import)

        reloaded = importlib.import_module("superset.db_engine_specs.datastore")
        assert reloaded.dependencies_installed is False
    finally:
        # Restore real modules and reload the datastore module so subsequent
        # tests use the correct (working) implementation.
        monkeypatch.undo()
        for name, mod in saved_modules.items():
            sys.modules[name] = mod  # type: ignore[assignment]
        importlib.reload(sys.modules["superset.db_engine_specs.datastore"])
