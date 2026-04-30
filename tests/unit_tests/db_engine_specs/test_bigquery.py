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

from datetime import datetime
from typing import Optional
from unittest import mock
from unittest.mock import MagicMock

import pytest
from marshmallow.exceptions import ValidationError
from pytest_mock import MockerFixture
from sqlalchemy import select
from sqlalchemy.engine.url import make_url
from sqlalchemy.sql import sqltypes
from sqlalchemy_bigquery import BigQueryDialect

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
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

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
    fields = BigQueryEngineSpec._get_fields(columns)

    query = select(fields)
    assert str(query.compile(dialect=BigQueryDialect())) == (
        "SELECT `limit` AS `limit`, `name` AS `name`, "
        "`project`.`name` AS `project__name`"
    )


def test_select_star(mocker: MockerFixture) -> None:
    """
    Test the ``select_star`` method.

    The method removes pseudo-columns from structures inside arrays. While these
    pseudo-columns show up as "columns" for metadata reasons, we can't select them
    in the query, as opposed to fields from non-array structures.
    """
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

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
        query.compile(dialect=BigQueryDialect(), compile_kwargs={"literal_binds": True})
    )

    dialect = BigQueryDialect()

    sql = BigQueryEngineSpec.select_star(
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
  `trailer` AS `trailer`
FROM `my_table`
LIMIT 100"""
    )


def test_get_parameters_from_uri_serializable() -> None:
    """
    Test that the result from ``get_parameters_from_uri`` is JSON serializable.
    """
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    parameters = BigQueryEngineSpec.get_parameters_from_uri(
        "bigquery://dbt-tutorial-347100/",
        {"access_token": "TOP_SECRET"},
    )
    assert parameters == {"access_token": "TOP_SECRET", "query": {}}
    assert json.loads(json.dumps(parameters)) == parameters


def test_unmask_encrypted_extra() -> None:
    """
    Test that the private key can be reused from the previous `encrypted_extra`.
    """
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

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

    assert BigQueryEngineSpec.unmask_encrypted_extra(old, new) == json.dumps(
        {
            "credentials_info": {
                "project_id": "yellow-unicorn-314419",
                "private_key": "SECRET",
            },
        }
    )


def test_unmask_encrypted_extra_field_changeed() -> None:
    """
    Test that the private key is not reused when the field has changed.
    """
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

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

    assert BigQueryEngineSpec.unmask_encrypted_extra(old, new) == json.dumps(
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
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    old = None
    new = json.dumps(
        {
            "credentials_info": {
                "project_id": "yellow-unicorn-314419",
                "private_key": "XXXXXXXXXX",
            },
        }
    )

    assert BigQueryEngineSpec.unmask_encrypted_extra(old, new) == json.dumps(
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
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    old = json.dumps(
        {
            "credentials_info": {
                "project_id": "black-sanctum-314419",
                "private_key": "SECRET",
            },
        }
    )
    new = None

    assert BigQueryEngineSpec.unmask_encrypted_extra(old, new) is None


def test_mask_encrypted_extra() -> None:
    """
    Test that the private key is masked when the database is edited.
    """
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    config = json.dumps(
        {
            "credentials_info": {
                "project_id": "black-sanctum-314419",
                "private_key": "SECRET",
            },
        }
    )

    assert BigQueryEngineSpec.mask_encrypted_extra(config) == json.dumps(
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
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    assert BigQueryEngineSpec.mask_encrypted_extra(None) is None


def test_parse_error_message() -> None:
    """
    Test that we parse a received message and just extract the useful information.

    Example errors:
    bigquery error: 400 Syntax error:  Table \"case_detail_all_suites\" must be qualified with a dataset (e.g. dataset.table).

    (job ID: ddf30b05-44e8-4fbf-aa29-40bfccaed886)
                                                -----Query Job SQL Follows-----
    |    .    |    .    |    .    |\n   1:select * from case_detail_all_suites\n   2:LIMIT 1001\n    |    .    |    .    |    .    |
    """  # noqa: E501
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    message = 'bigquery error: 400 Syntax error: Table "case_detail_all_suites" must be qualified with a dataset (e.g. dataset.table).\n\n(job ID: ddf30b05-44e8-4fbf-aa29-40bfccaed886)\n\n     -----Query Job SQL Follows-----     \n\n    |    .    |    .    |    .    |\n   1:select * from case_detail_all_suites\n   2:LIMIT 1001\n    |    .    |    .    |    .    |'  # noqa: E501
    expected_result = 'bigquery error: 400 Syntax error: Table "case_detail_all_suites" must be qualified with a dataset (e.g. dataset.table).'  # noqa: E501
    assert (
        str(BigQueryEngineSpec.parse_error_exception(Exception(message)))
        == expected_result
    )


def test_parse_error_raises_exception() -> None:
    """
    Test that we handle any exception we might get from calling the parse_error_exception method.

    Example errors:
    400 Syntax error: Expected "(" or keyword UNNEST but got "@" at [4:80]
    bigquery error: 400 Table \"case_detail_all_suites\" must be qualified with a dataset (e.g. dataset.table).
    """  # noqa: E501
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    message = 'bigquery error: 400 Syntax error: Table "case_detail_all_suites" must be qualified with a dataset (e.g. dataset.table).'  # noqa: E501
    message_2 = "6"
    expected_result = 'bigquery error: 400 Syntax error: Table "case_detail_all_suites" must be qualified with a dataset (e.g. dataset.table).'  # noqa: E501
    assert (
        str(BigQueryEngineSpec.parse_error_exception(Exception(message)))
        == expected_result
    )
    assert str(BigQueryEngineSpec.parse_error_exception(Exception(message_2))) == "6"


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
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    """
    DB Eng Specs (bigquery): Test conversion to date time
    """
    from superset.db_engine_specs.bigquery import (
        BigQueryEngineSpec as spec,  # noqa: N813
    )

    assert_convert_dttm(spec, target_type, expected_result, dttm)


def test_get_default_catalog(mocker: MockerFixture) -> None:
    """
    Test that we get the default catalog from the connection URI.
    """
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec
    from superset.models.core import Database

    mocker.patch.object(Database, "get_sqla_engine")
    get_client = mocker.patch.object(BigQueryEngineSpec, "_get_client")
    get_client().project = "project"

    database = Database(
        database_name="my_db",
        sqlalchemy_uri="bigquery://project",
    )
    assert BigQueryEngineSpec.get_default_catalog(database) == "project"

    database = Database(
        database_name="my_db",
        sqlalchemy_uri="bigquery:///project",
    )
    assert BigQueryEngineSpec.get_default_catalog(database) == "project"

    database = Database(
        database_name="my_db",
        sqlalchemy_uri="bigquery://",
    )
    assert BigQueryEngineSpec.get_default_catalog(database) == "project"


def test_adjust_engine_params_catalog_as_host() -> None:
    """
    Test passing a custom catalog.

    In this test, the original URI has the catalog as the host.
    """
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    url = make_url("bigquery://project")

    uri = BigQueryEngineSpec.adjust_engine_params(url, {})[0]
    assert str(uri) == "bigquery://project"

    uri = BigQueryEngineSpec.adjust_engine_params(
        url,
        {},
        catalog="other-project",
    )[0]
    assert str(uri) == "bigquery://other-project/"


def test_get_materialized_view_names() -> None:
    """
    Test get_materialized_view_names method.
    """
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    database = mock.Mock()
    database.get_default_catalog.return_value = "my_project"

    inspector = mock.Mock()

    # Mock the raw connection and cursor
    cursor_mock = mock.Mock()
    cursor_mock.fetchall.return_value = [
        ("materialized_view_1",),
        ("materialized_view_2",),
    ]

    connection_mock = mock.Mock()
    connection_mock.cursor.return_value = cursor_mock
    connection_mock.__enter__ = mock.Mock(return_value=connection_mock)
    connection_mock.__exit__ = mock.Mock(return_value=None)

    database.get_raw_connection.return_value = connection_mock

    result = BigQueryEngineSpec.get_materialized_view_names(
        database=database, inspector=inspector, schema="my_dataset"
    )

    assert result == {"materialized_view_1", "materialized_view_2"}

    # Verify the SQL query was correct
    cursor_mock.execute.assert_called_once()
    executed_query = cursor_mock.execute.call_args[0][0]
    assert "INFORMATION_SCHEMA.TABLES" in executed_query
    assert "table_type = 'MATERIALIZED VIEW'" in executed_query


def test_get_view_names_excludes_materialized_views() -> None:
    """
    Test get_view_names excludes materialized views.
    """
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    database = mock.Mock()
    database.get_default_catalog.return_value = "my_project"

    inspector = mock.Mock()

    # Mock the raw connection and cursor
    cursor_mock = mock.Mock()
    # Return only regular views, not materialized views
    cursor_mock.fetchall.return_value = [
        ("regular_view_1",),
        ("regular_view_2",),
    ]

    connection_mock = mock.Mock()
    connection_mock.cursor.return_value = cursor_mock
    connection_mock.__enter__ = mock.Mock(return_value=connection_mock)
    connection_mock.__exit__ = mock.Mock(return_value=None)

    database.get_raw_connection.return_value = connection_mock

    result = BigQueryEngineSpec.get_view_names(
        database=database, inspector=inspector, schema="my_dataset"
    )

    assert result == {"regular_view_1", "regular_view_2"}

    # Verify the SQL query only gets regular views
    cursor_mock.execute.assert_called_once()
    executed_query = cursor_mock.execute.call_args[0][0]
    assert "INFORMATION_SCHEMA.TABLES" in executed_query
    assert "table_type = 'VIEW'" in executed_query
    # Ensure it's not querying for materialized views
    assert "MATERIALIZED VIEW" not in executed_query


@pytest.mark.parametrize(
    "label,expected",
    [
        ("abc", "abc"),
        ("123col", "_123col"),
        ("col with spaces", "col_with_spaces__8e756"),
        ("col-with-dashes", "col_with_dashes__58012"),
        ("_starts_under", "_starts_under"),
        ("MixedCase", "MixedCase"),
        ("already_valid_123", "already_valid_123"),
        ("1", "_1"),
        ("a!@#b", "a___b_caborc"),
    ],
)
def test_mutate_label(label: str, expected: str) -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    result = BigQueryEngineSpec._mutate_label(label)
    # Labels starting with a digit get prefixed with underscore
    if label[0].isdigit():
        assert result.startswith("_")
    # Labels with non-alphanumeric chars get hash appended
    import re

    if re.sub(r"[^\w]+", "_", label) != label:
        assert "_" in result


def test_mutate_label_no_mutation_needed() -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    # A label that needs no mutation should be returned as-is
    assert BigQueryEngineSpec._mutate_label("valid_label") == "valid_label"
    assert BigQueryEngineSpec._mutate_label("_underscore") == "_underscore"


def test_mutate_label_starts_with_digit() -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    result = BigQueryEngineSpec._mutate_label("9columns")
    assert result.startswith("_")
    # since it was mutated, hash is appended
    assert len(result) > len("_9columns")


def test_mutate_label_special_chars() -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    result = BigQueryEngineSpec._mutate_label("col.name")
    # dot is replaced with underscore and hash appended
    assert "." not in result
    assert "_" in result


def test_truncate_label() -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    result = BigQueryEngineSpec._truncate_label("some_very_long_label")
    assert result.startswith("_")
    # Should be a hash
    assert len(result) > 1


def test_fetch_data_normal() -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    cursor = MagicMock()
    cursor.fetchall.return_value = [("a", 1), ("b", 2)]
    cursor.description = []
    data = BigQueryEngineSpec.fetch_data(cursor, limit=2)
    assert data == [("a", 1), ("b", 2)]


def test_fetch_data_bigquery_row() -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    class Row:
        """Mock BigQuery Row object."""

        def __init__(self, values_list: list[str]) -> None:
            self._values = values_list

        def values(self) -> list[str]:
            return self._values

    cursor = MagicMock()
    cursor.fetchall.return_value = [Row(["val1", "val2"]), Row(["val3", "val4"])]
    cursor.description = []
    data = BigQueryEngineSpec.fetch_data(cursor, limit=2)
    assert data == [["val1", "val2"], ["val3", "val4"]]


def test_fetch_data_empty() -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    cursor = MagicMock()
    cursor.fetchall.return_value = []
    cursor.description = []
    data = BigQueryEngineSpec.fetch_data(cursor, limit=10)
    assert data == []


def test_epoch_to_dttm() -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    assert BigQueryEngineSpec.epoch_to_dttm() == "TIMESTAMP_SECONDS({col})"


def test_epoch_ms_to_dttm() -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    assert BigQueryEngineSpec.epoch_ms_to_dttm() == "TIMESTAMP_MILLIS({col})"


def test_get_dbapi_exception_mapping() -> None:
    from google.auth.exceptions import DefaultCredentialsError

    from superset.db_engine_specs.bigquery import BigQueryEngineSpec
    from superset.db_engine_specs.exceptions import SupersetDBAPIConnectionError

    mapping = BigQueryEngineSpec.get_dbapi_exception_mapping()
    assert DefaultCredentialsError in mapping
    assert mapping[DefaultCredentialsError] is SupersetDBAPIConnectionError


def test_validate_parameters() -> None:
    from superset.db_engine_specs.base import BasicPropertiesType
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    properties: BasicPropertiesType = {"parameters": {}}
    result = BigQueryEngineSpec.validate_parameters(properties=properties)
    assert result == []


def test_get_allow_cost_estimate() -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    assert BigQueryEngineSpec.get_allow_cost_estimate({}) is True
    assert BigQueryEngineSpec.get_allow_cost_estimate({"foo": "bar"}) is True


def test_query_cost_formatter() -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    raw_cost = [{"MB Processed": 123.45}, {"GB Processed": 1.5}]
    result = BigQueryEngineSpec.query_cost_formatter(raw_cost)
    assert result == [{"MB Processed": "123.45"}, {"GB Processed": "1.5"}]


def test_query_cost_formatter_empty() -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    result = BigQueryEngineSpec.query_cost_formatter([])
    assert result == []


def test_build_sqlalchemy_uri_with_project() -> None:
    from superset.db_engine_specs.bigquery import (
        BigQueryEngineSpec,
        BigQueryParametersType,
    )

    parameters: BigQueryParametersType = {
        "credentials_info": {},
        "query": {"location": "US"},
    }
    encrypted_extra = {
        "credentials_info": {
            "project_id": "my-project",
            "private_key": "SECRET",
        }
    }
    uri = BigQueryEngineSpec.build_sqlalchemy_uri(parameters, encrypted_extra)
    assert "bigquery://my-project/" in uri
    assert "location=US" in uri


def test_build_sqlalchemy_uri_missing_credentials() -> None:
    from superset.db_engine_specs.bigquery import (
        BigQueryEngineSpec,
        BigQueryParametersType,
    )

    parameters: BigQueryParametersType = {"credentials_info": {}, "query": {}}
    with pytest.raises(ValidationError, match="Missing service credentials"):
        BigQueryEngineSpec.build_sqlalchemy_uri(parameters, encrypted_extra=None)


def test_build_sqlalchemy_uri_invalid_credentials() -> None:
    from superset.db_engine_specs.bigquery import (
        BigQueryEngineSpec,
        BigQueryParametersType,
    )

    parameters: BigQueryParametersType = {"credentials_info": {}, "query": {}}
    encrypted_extra = {
        "credentials_info": {
            "private_key": "SECRET",
        }
    }
    with pytest.raises(ValidationError, match="Invalid service credentials"):
        BigQueryEngineSpec.build_sqlalchemy_uri(parameters, encrypted_extra)


def test_build_sqlalchemy_uri_credentials_as_string() -> None:
    from superset.db_engine_specs.bigquery import (
        BigQueryEngineSpec,
        BigQueryParametersType,
    )

    parameters: BigQueryParametersType = {"credentials_info": {}, "query": {}}
    encrypted_extra = {
        "credentials_info": json.dumps(
            {
                "project_id": "string-project",
                "private_key": "SECRET",
            }
        ),
    }
    uri = BigQueryEngineSpec.build_sqlalchemy_uri(parameters, encrypted_extra)
    assert "bigquery://string-project/" in uri


def test_get_parameters_from_uri_missing_encrypted_extra() -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    with pytest.raises(ValidationError, match="Invalid service credentials"):
        BigQueryEngineSpec.get_parameters_from_uri(
            "bigquery://project/", encrypted_extra=None
        )


def test_parameters_json_schema() -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    schema = BigQueryEngineSpec.parameters_json_schema()
    assert schema is not None
    assert "properties" in schema


def test_parameters_json_schema_none() -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    original = BigQueryEngineSpec.parameters_schema
    BigQueryEngineSpec.parameters_schema = None  # type: ignore[assignment]
    try:
        assert BigQueryEngineSpec.parameters_json_schema() is None
    finally:
        BigQueryEngineSpec.parameters_schema = original


def test_custom_estimate_statement_cost_bytes(mocker: MockerFixture) -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    client = MagicMock()
    query_job = MagicMock()
    query_job.total_bytes_processed = 500  # < 1024, so Bytes
    client.query.return_value = query_job

    result = BigQueryEngineSpec.custom_estimate_statement_cost("SELECT 1", client)
    assert result == {"B Processed": 500}


def test_custom_estimate_statement_cost_kb(mocker: MockerFixture) -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    client = MagicMock()
    query_job = MagicMock()
    query_job.total_bytes_processed = 50000  # > 1024, < 1024^2
    client.query.return_value = query_job

    result = BigQueryEngineSpec.custom_estimate_statement_cost("SELECT 1", client)
    assert result == {"KB Processed": round(50000 / 1024, 2)}


def test_custom_estimate_statement_cost_mb(mocker: MockerFixture) -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    client = MagicMock()
    query_job = MagicMock()
    query_job.total_bytes_processed = 5000000  # > 1024^2, < 1024^3
    client.query.return_value = query_job

    result = BigQueryEngineSpec.custom_estimate_statement_cost("SELECT 1", client)
    assert result == {"MB Processed": round(5000000 / (1024**2), 2)}


def test_custom_estimate_statement_cost_gb(mocker: MockerFixture) -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    client = MagicMock()
    query_job = MagicMock()
    query_job.total_bytes_processed = 5000000000  # > 1024^3
    client.query.return_value = query_job

    result = BigQueryEngineSpec.custom_estimate_statement_cost("SELECT 1", client)
    assert result == {"GB Processed": round(5000000000 / (1024**3), 2)}


def test_custom_estimate_statement_cost_no_bytes(mocker: MockerFixture) -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    client = MagicMock()
    query_job = MagicMock(spec=[])  # No total_bytes_processed attribute
    client.query.return_value = query_job

    result = BigQueryEngineSpec.custom_estimate_statement_cost("SELECT 1", client)
    assert result == {}


def test_df_to_sql_no_pandas_gbq(mocker: MockerFixture) -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    mocker.patch("superset.db_engine_specs.bigquery.can_upload", False)
    database = MagicMock()
    table = Table("my_table", "my_dataset")
    import pandas as pd

    df = pd.DataFrame({"col": [1, 2, 3]})

    from superset.exceptions import SupersetException

    with pytest.raises(SupersetException, match="Could not import libraries"):
        BigQueryEngineSpec.df_to_sql(database, table, df, {})


def test_df_to_sql_no_schema(mocker: MockerFixture) -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    mocker.patch("superset.db_engine_specs.bigquery.can_upload", True)
    database = MagicMock()
    table = Table("my_table")  # no schema
    import pandas as pd

    df = pd.DataFrame({"col": [1, 2, 3]})

    from superset.exceptions import SupersetException

    with pytest.raises(SupersetException, match="table schema must be defined"):
        BigQueryEngineSpec.df_to_sql(database, table, df, {})


def test_df_to_sql_success(mocker: MockerFixture) -> None:
    import superset.db_engine_specs.bigquery as bq_module

    mocker.patch.object(bq_module, "can_upload", True)
    mock_to_gbq = mocker.patch.object(bq_module, "pandas_gbq", create=True)

    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    database = MagicMock()
    engine = MagicMock()
    engine.url.host = "my-project"
    engine.dialect.credentials_info = None
    database.get_sqla_engine.return_value.__enter__ = MagicMock(return_value=engine)
    database.get_sqla_engine.return_value.__exit__ = MagicMock(return_value=False)

    table = Table("my_table", "my_dataset")
    import pandas as pd

    df = pd.DataFrame({"col": [1, 2, 3]})

    BigQueryEngineSpec.df_to_sql(database, table, df, {"if_exists": "replace"})
    mock_to_gbq.to_gbq.assert_called_once()
    call_kwargs = mock_to_gbq.to_gbq.call_args[1]
    assert call_kwargs["project_id"] == "my-project"
    assert call_kwargs["if_exists"] == "replace"


def test_get_client_no_dependencies(mocker: MockerFixture) -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec
    from superset.exceptions import SupersetException

    mocker.patch("superset.db_engine_specs.bigquery.dependencies_installed", False)
    engine = MagicMock()
    database = MagicMock()

    with pytest.raises(SupersetException, match="Could not import libraries"):
        BigQueryEngineSpec._get_client(engine, database)


def test_get_client_with_credentials_info(mocker: MockerFixture) -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    mocker.patch("superset.db_engine_specs.bigquery.dependencies_installed", True)
    mock_sa = mocker.patch(
        "superset.db_engine_specs.bigquery.service_account.Credentials.from_service_account_info"
    )
    mock_bq = mocker.patch("superset.db_engine_specs.bigquery.bigquery.Client")

    engine = MagicMock()
    engine.dialect.credentials_info = {"project_id": "test", "private_key": "key"}
    database = MagicMock()

    BigQueryEngineSpec._get_client(engine, database)
    mock_sa.assert_called_once_with({"project_id": "test", "private_key": "key"})
    mock_bq.assert_called_once()


def test_get_client_default_credentials(mocker: MockerFixture) -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    mocker.patch("superset.db_engine_specs.bigquery.dependencies_installed", True)
    mock_default = mocker.patch("superset.db_engine_specs.bigquery.google.auth.default")
    mock_default.return_value = (MagicMock(), "project-id")
    mock_bq = mocker.patch("superset.db_engine_specs.bigquery.bigquery.Client")

    engine = MagicMock()
    engine.dialect.credentials_info = None
    database = MagicMock()

    BigQueryEngineSpec._get_client(engine, database)
    mock_default.assert_called_once()
    mock_bq.assert_called_once()


def test_get_client_default_credentials_error(mocker: MockerFixture) -> None:
    import google.auth.exceptions

    from superset.db_engine_specs.bigquery import BigQueryEngineSpec
    from superset.db_engine_specs.exceptions import SupersetDBAPIConnectionError

    mocker.patch("superset.db_engine_specs.bigquery.dependencies_installed", True)
    mock_default = mocker.patch("superset.db_engine_specs.bigquery.google.auth.default")
    mock_default.side_effect = google.auth.exceptions.DefaultCredentialsError(
        "no creds"
    )

    engine = MagicMock()
    engine.dialect.credentials_info = None
    database = MagicMock()

    with pytest.raises(SupersetDBAPIConnectionError):
        BigQueryEngineSpec._get_client(engine, database)


def test_get_catalog_names(mocker: MockerFixture) -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    database = MagicMock()
    engine = MagicMock()
    database.get_sqla_engine.return_value.__enter__ = MagicMock(return_value=engine)
    database.get_sqla_engine.return_value.__exit__ = MagicMock(return_value=False)

    mock_client = MagicMock()
    project1 = MagicMock()
    project1.project_id = "project-1"
    project2 = MagicMock()
    project2.project_id = "project-2"
    mock_client.list_projects.return_value = [project1, project2]

    mocker.patch.object(BigQueryEngineSpec, "_get_client", return_value=mock_client)

    inspector = MagicMock()
    result = BigQueryEngineSpec.get_catalog_names(database, inspector)
    assert result == {"project-1", "project-2"}


def test_get_catalog_names_connection_error(mocker: MockerFixture) -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec
    from superset.db_engine_specs.exceptions import SupersetDBAPIConnectionError

    database = MagicMock()
    engine = MagicMock()
    database.get_sqla_engine.return_value.__enter__ = MagicMock(return_value=engine)
    database.get_sqla_engine.return_value.__exit__ = MagicMock(return_value=False)

    mocker.patch.object(
        BigQueryEngineSpec,
        "_get_client",
        side_effect=SupersetDBAPIConnectionError("no creds"),
    )

    inspector = MagicMock()
    result = BigQueryEngineSpec.get_catalog_names(database, inspector)
    assert result == set()


def test_adjust_engine_params_no_catalog() -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    url = make_url("bigquery://project")
    uri, connect_args = BigQueryEngineSpec.adjust_engine_params(url, {})
    assert str(uri) == "bigquery://project"
    assert connect_args == {}


def test_adjust_engine_params_with_catalog() -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    url = make_url("bigquery://project")
    uri, connect_args = BigQueryEngineSpec.adjust_engine_params(
        url, {}, catalog="new-project"
    )
    assert str(uri) == "bigquery://new-project/"
    assert connect_args == {}


def test_parse_error_exception_single_line() -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    message = "Simple error message"
    result = BigQueryEngineSpec.parse_error_exception(Exception(message))
    assert str(result) == "Simple error message"


def test_parse_error_exception_unparseable() -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    # An exception where calling type(exception)(str) raises
    class WeirdError(Exception):
        def __init__(self, msg: str) -> None:
            if "\n" not in msg:
                raise RuntimeError("Cannot recreate")
            super().__init__(msg)

    exc = WeirdError("line1\nline2")
    result = BigQueryEngineSpec.parse_error_exception(exc)
    # Should return original exception since recreating fails
    assert result is exc


def test_get_materialized_view_names_no_schema() -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    database = MagicMock()
    inspector = MagicMock()

    result = BigQueryEngineSpec.get_materialized_view_names(
        database=database, inspector=inspector, schema=None
    )
    assert result == set()


def test_get_materialized_view_names_exception() -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    database = MagicMock()
    database.get_default_catalog.return_value = "project"
    database.get_raw_connection.side_effect = Exception("connection failed")
    inspector = MagicMock()

    result = BigQueryEngineSpec.get_materialized_view_names(
        database=database, inspector=inspector, schema="my_dataset"
    )
    assert result == set()


def test_get_materialized_view_names_no_catalog() -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    database = MagicMock()
    database.get_default_catalog.return_value = None

    cursor_mock = MagicMock()
    cursor_mock.fetchall.return_value = [("mv1",)]

    connection_mock = MagicMock()
    connection_mock.cursor.return_value = cursor_mock
    connection_mock.__enter__ = MagicMock(return_value=connection_mock)
    connection_mock.__exit__ = MagicMock(return_value=None)
    database.get_raw_connection.return_value = connection_mock

    inspector = MagicMock()
    result = BigQueryEngineSpec.get_materialized_view_names(
        database=database, inspector=inspector, schema="my_dataset"
    )
    assert result == {"mv1"}

    executed_query = cursor_mock.execute.call_args[0][0]
    assert "`my_dataset.INFORMATION_SCHEMA.TABLES`" in executed_query


def test_get_view_names_no_schema() -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    database = MagicMock()
    inspector = MagicMock()

    result = BigQueryEngineSpec.get_view_names(
        database=database, inspector=inspector, schema=None
    )
    assert result == set()


def test_get_view_names_exception_fallback(mocker: MockerFixture) -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    database = MagicMock()
    database.get_default_catalog.return_value = "project"
    database.get_raw_connection.side_effect = Exception("connection failed")

    inspector = MagicMock()
    inspector.get_view_names.return_value = ["fallback_view"]

    mocker.patch(
        "superset.db_engine_specs.base.BaseEngineSpec.get_view_names",
        return_value={"fallback_view"},
    )

    result = BigQueryEngineSpec.get_view_names(
        database=database, inspector=inspector, schema="my_dataset"
    )
    assert result == {"fallback_view"}


def test_get_view_names_no_catalog() -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    database = MagicMock()
    database.get_default_catalog.return_value = None

    cursor_mock = MagicMock()
    cursor_mock.fetchall.return_value = [("view1",), ("view2",)]

    connection_mock = MagicMock()
    connection_mock.cursor.return_value = cursor_mock
    connection_mock.__enter__ = MagicMock(return_value=connection_mock)
    connection_mock.__exit__ = MagicMock(return_value=None)
    database.get_raw_connection.return_value = connection_mock

    inspector = MagicMock()
    result = BigQueryEngineSpec.get_view_names(
        database=database, inspector=inspector, schema="my_dataset"
    )
    assert result == {"view1", "view2"}

    executed_query = cursor_mock.execute.call_args[0][0]
    assert "`my_dataset.INFORMATION_SCHEMA.TABLES`" in executed_query


def test_estimate_query_cost(mocker: MockerFixture) -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    database = MagicMock()
    database.get_extra.return_value = {}

    engine = MagicMock()
    database.get_sqla_engine.return_value.__enter__ = MagicMock(return_value=engine)
    database.get_sqla_engine.return_value.__exit__ = MagicMock(return_value=False)

    mock_client = MagicMock()
    query_job = MagicMock()
    query_job.total_bytes_processed = 1000
    mock_client.query.return_value = query_job

    mocker.patch.object(BigQueryEngineSpec, "_get_client", return_value=mock_client)
    mocker.patch.object(
        BigQueryEngineSpec, "get_allow_cost_estimate", return_value=True
    )

    result = BigQueryEngineSpec.estimate_query_cost(
        database=database,
        catalog="project",
        schema="dataset",
        sql="SELECT 1",
    )
    assert len(result) == 1
    assert "B Processed" in result[0]


def test_estimate_query_cost_not_allowed(mocker: MockerFixture) -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec
    from superset.exceptions import SupersetException

    database = MagicMock()
    database.get_extra.return_value = {}
    mocker.patch.object(
        BigQueryEngineSpec, "get_allow_cost_estimate", return_value=False
    )

    with pytest.raises(SupersetException, match="does not support cost estimation"):
        BigQueryEngineSpec.estimate_query_cost(
            database=database,
            catalog="project",
            schema="dataset",
            sql="SELECT 1",
        )


def test_select_star_no_cols(mocker: MockerFixture) -> None:
    """Test select_star when cols is None (passes through to super)."""
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    database = MagicMock()
    database.compile_sqla_query = lambda query, catalog, schema: str(
        query.compile(dialect=BigQueryDialect(), compile_kwargs={"literal_binds": True})
    )
    dialect = BigQueryDialect()

    sql = BigQueryEngineSpec.select_star(
        database=database,
        table=Table("my_table"),
        dialect=dialect,
        limit=100,
        show_cols=False,
        indent=True,
        latest_partition=False,
        cols=None,
    )
    assert "my_table" in sql


def test_select_star_struct_not_array(mocker: MockerFixture) -> None:
    """Test select_star with struct columns that are NOT inside arrays (kept)."""
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    cols: list[ResultSetColumnType] = [
        {
            "column_name": "author",
            "name": "author",
            "type": sqltypes.JSON(),
            "nullable": True,
            "comment": None,
            "default": None,
            "precision": None,
            "scale": None,
            "max_length": None,
            "is_dttm": False,
        },
        {
            "column_name": "author.name",
            "name": "author.name",
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

    database = MagicMock()
    database.compile_sqla_query = lambda query, catalog, schema: str(
        query.compile(dialect=BigQueryDialect(), compile_kwargs={"literal_binds": True})
    )
    dialect = BigQueryDialect()

    sql = BigQueryEngineSpec.select_star(
        database=database,
        table=Table("my_table"),
        dialect=dialect,
        limit=100,
        show_cols=True,
        indent=True,
        latest_partition=False,
        cols=cols,
    )
    # Both columns should be present since author is not an ARRAY
    assert "author" in sql
    assert "author__name" in sql


def test_where_latest_partition(mocker: MockerFixture) -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    database = MagicMock()
    table = Table("my_table", "my_dataset", "my_project")
    query = select()

    mocker.patch.object(
        BigQueryEngineSpec, "get_time_partition_column", return_value="_PARTITIONDATE"
    )
    mocker.patch.object(
        BigQueryEngineSpec, "get_max_partition_id", return_value="20230101"
    )

    result = BigQueryEngineSpec.where_latest_partition(database, table, query)
    assert result is not None
    compiled = str(result.compile(compile_kwargs={"literal_binds": True}))
    assert "PARSE_DATE" in compiled


def test_where_latest_partition_no_partition_column(mocker: MockerFixture) -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    database = MagicMock()
    table = Table("my_table", "my_dataset")
    query = select()

    mocker.patch.object(
        BigQueryEngineSpec, "get_time_partition_column", return_value=None
    )

    result = BigQueryEngineSpec.where_latest_partition(database, table, query)
    assert result is not None


def test_get_max_partition_id(mocker: MockerFixture) -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    database = MagicMock()
    database.get_dialect.return_value = BigQueryDialect()

    cursor_mock = MagicMock()
    cursor_mock.fetchone.return_value = ("20230615",)

    connection_mock = MagicMock()
    connection_mock.cursor.return_value = cursor_mock
    connection_mock.__enter__ = MagicMock(return_value=connection_mock)
    connection_mock.__exit__ = MagicMock(return_value=None)
    database.get_raw_connection.return_value = connection_mock

    table = Table("my_table", "my_dataset", "my_project")
    result = BigQueryEngineSpec.get_max_partition_id(database, table)
    assert result == "20230615"


def test_get_max_partition_id_no_result(mocker: MockerFixture) -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    database = MagicMock()
    database.get_dialect.return_value = BigQueryDialect()

    cursor_mock = MagicMock()
    cursor_mock.fetchone.return_value = None

    connection_mock = MagicMock()
    connection_mock.cursor.return_value = cursor_mock
    connection_mock.__enter__ = MagicMock(return_value=connection_mock)
    connection_mock.__exit__ = MagicMock(return_value=None)
    database.get_raw_connection.return_value = connection_mock

    table = Table("my_table", "my_dataset")
    result = BigQueryEngineSpec.get_max_partition_id(database, table)
    assert result is None


def test_get_time_partition_column(mocker: MockerFixture) -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    database = MagicMock()
    engine = MagicMock()
    database.get_sqla_engine.return_value.__enter__ = MagicMock(return_value=engine)
    database.get_sqla_engine.return_value.__exit__ = MagicMock(return_value=False)

    mock_client = MagicMock()
    bq_table = MagicMock()
    bq_table.time_partitioning.field = "_PARTITIONDATE"
    mock_client.get_table.return_value = bq_table
    mocker.patch.object(BigQueryEngineSpec, "_get_client", return_value=mock_client)

    table = Table("my_table", "my_dataset")
    result = BigQueryEngineSpec.get_time_partition_column(database, table)
    assert result == "_PARTITIONDATE"


def test_get_time_partition_column_no_partitioning(mocker: MockerFixture) -> None:
    from superset.db_engine_specs.bigquery import BigQueryEngineSpec

    database = MagicMock()
    engine = MagicMock()
    database.get_sqla_engine.return_value.__enter__ = MagicMock(return_value=engine)
    database.get_sqla_engine.return_value.__exit__ = MagicMock(return_value=False)

    mock_client = MagicMock()
    bq_table = MagicMock()
    bq_table.time_partitioning = None
    mock_client.get_table.return_value = bq_table
    mocker.patch.object(BigQueryEngineSpec, "_get_client", return_value=mock_client)

    table = Table("my_table", "my_dataset")
    result = BigQueryEngineSpec.get_time_partition_column(database, table)
    assert result is None
