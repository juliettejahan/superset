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

import pytest
from pytest_mock import MockerFixture
from sqlalchemy import column
from sqlglot import parse_one
from sqlglot.errors import ParseError

from superset.constants import TimeGrain
from superset.sql.parse import LimitMethod, Table
from tests.unit_tests.db_engine_specs.utils import assert_convert_dttm
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


def test_engine_attributes() -> None:
    """
    Test the basic class-level attributes of ``Db2EngineSpec``.
    """
    from superset.db_engine_specs.db2 import Db2EngineSpec

    assert Db2EngineSpec.engine == "db2"
    assert Db2EngineSpec.engine_aliases == {"ibm_db_sa"}
    assert Db2EngineSpec.engine_name == "IBM Db2"
    assert Db2EngineSpec.limit_method == LimitMethod.WRAP_SQL
    assert Db2EngineSpec.force_column_alias_quotes is True
    assert Db2EngineSpec.max_column_name_length == 30
    assert Db2EngineSpec.supports_dynamic_schema is True
    assert Db2EngineSpec.supports_multivalues_insert is True


def test_metadata_structure() -> None:
    """
    Test the ``metadata`` mapping declared on ``Db2EngineSpec``.
    """
    from superset.db_engine_specs.base import DatabaseCategory
    from superset.db_engine_specs.db2 import Db2EngineSpec

    metadata = Db2EngineSpec.metadata
    assert "description" in metadata
    assert metadata["logo"] == "ibm-db2.svg"
    assert metadata["homepage_url"] == "https://www.ibm.com/db2"
    assert metadata["default_port"] == 50000
    assert DatabaseCategory.TRADITIONAL_RDBMS in metadata["categories"]
    assert DatabaseCategory.PROPRIETARY in metadata["categories"]
    assert metadata["pypi_packages"] == ["ibm_db_sa"]
    assert "{username}" in metadata["connection_string"]
    assert metadata["docs_url"] == "https://github.com/ibmdb/python-ibmdbsa"


def test_metadata_drivers() -> None:
    """
    Test the driver entries on ``Db2EngineSpec.metadata``.
    """
    from superset.db_engine_specs.db2 import Db2EngineSpec

    drivers = Db2EngineSpec.metadata["drivers"]
    assert len(drivers) == 2

    recommended = drivers[0]
    assert recommended["name"] == "ibm_db_sa (with LIMIT)"
    assert recommended["is_recommended"] is True
    assert recommended["connection_string"].startswith("db2+ibm_db://")

    fallback = drivers[1]
    assert fallback["name"] == "ibm_db_sa (without LIMIT syntax)"
    assert fallback["is_recommended"] is False
    assert fallback["connection_string"].startswith("ibm_db_sa://")
    assert "Recommended for SQL Lab" in fallback["notes"]


def test_metadata_compatible_databases() -> None:
    """
    Test the ``compatible_databases`` entry on ``Db2EngineSpec.metadata``.
    """
    from superset.db_engine_specs.base import DatabaseCategory
    from superset.db_engine_specs.db2 import Db2EngineSpec

    compatible = Db2EngineSpec.metadata["compatible_databases"]
    assert len(compatible) == 1

    db2_for_i = compatible[0]
    assert db2_for_i["name"] == "IBM Db2 for i (AS/400)"
    assert db2_for_i["pypi_packages"] == ["sqlalchemy-ibmi"]
    assert db2_for_i["connection_string"].startswith("ibmi://")
    assert db2_for_i["docs_url"] == "https://github.com/IBM/sqlalchemy-ibmi"
    assert DatabaseCategory.PROPRIETARY in db2_for_i["categories"]
    assert set(db2_for_i["parameters"].keys()) == {
        "username",
        "password",
        "host",
        "database",
    }


def test_epoch_to_dttm() -> None:
    """
    Test the ``epoch_to_dttm`` method.
    """
    from superset.db_engine_specs.db2 import Db2EngineSpec

    assert (
        Db2EngineSpec.epoch_to_dttm().format(col="epoch_dttm")
        == "(TIMESTAMP('1970-01-01', '00:00:00') + epoch_dttm SECONDS)"
    )


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Date", None),
        ("DateTime", None),
        ("TimeStamp", None),
        ("UnknownType", None),
    ],
)
def test_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    """
    ``Db2EngineSpec`` does not override ``convert_dttm``, so the base
    implementation should return ``None`` for every target type.
    """
    from superset.db_engine_specs.db2 import Db2EngineSpec

    assert_convert_dttm(Db2EngineSpec, target_type, expected_result, dttm)


def test_get_dbapi_exception_mapping() -> None:
    """
    ``Db2EngineSpec`` does not override ``get_dbapi_exception_mapping``,
    so the inherited mapping should be empty.
    """
    from superset.db_engine_specs.db2 import Db2EngineSpec

    assert Db2EngineSpec.get_dbapi_exception_mapping() == {}


def test_get_table_comment(mocker: MockerFixture) -> None:
    """
    Test the ``get_table_comment`` method when a comment tuple is returned.
    """
    from superset.db_engine_specs.db2 import Db2EngineSpec

    mock_inspector = mocker.MagicMock()
    mock_inspector.get_table_comment.return_value = {
        "text": ("This is a table comment",)
    }

    assert (
        Db2EngineSpec.get_table_comment(mock_inspector, Table("my_table", "my_schema"))
        == "This is a table comment"
    )


def test_get_table_comment_no_schema(mocker: MockerFixture) -> None:
    """
    ``get_table_comment`` should still work when the table has no schema and
    pass ``None`` through to the inspector.
    """
    from superset.db_engine_specs.db2 import Db2EngineSpec

    mock_inspector = mocker.MagicMock()
    mock_inspector.get_table_comment.return_value = {"text": ("schemaless comment",)}

    assert (
        Db2EngineSpec.get_table_comment(mock_inspector, Table("my_table"))
        == "schemaless comment"
    )
    mock_inspector.get_table_comment.assert_called_once_with("my_table", None)


def test_get_table_comment_empty(mocker: MockerFixture) -> None:
    """
    Test the ``get_table_comment`` method when the inspector returns an empty
    mapping (no ``text`` key). The result should be ``None``.
    """
    from superset.db_engine_specs.db2 import Db2EngineSpec

    mock_inspector = mocker.MagicMock()
    mock_inspector.get_table_comment.return_value = {}

    assert (
        Db2EngineSpec.get_table_comment(mock_inspector, Table("my_table", "my_schema"))
        is None
    )


def test_get_table_comment_empty_tuple(mocker: MockerFixture) -> None:
    """
    Test the ``get_table_comment`` method when the inspector returns an empty
    tuple under ``text``. Indexing the tuple raises ``IndexError`` and the
    method falls through to the bound ``comment`` value (the empty tuple).
    """
    from superset.db_engine_specs.db2 import Db2EngineSpec

    mock_inspector = mocker.MagicMock()
    mock_inspector.get_table_comment.return_value = {"text": ()}

    result = Db2EngineSpec.get_table_comment(
        mock_inspector, Table("my_table", "my_schema")
    )
    assert result == ()


def test_get_table_comment_unexpected_exception(mocker: MockerFixture) -> None:
    """
    Test the ``get_table_comment`` method when the inspector raises an
    unexpected exception. The method should log the error and return ``None``.
    """
    from superset.db_engine_specs.db2 import Db2EngineSpec

    mock_inspector = mocker.MagicMock()
    mock_inspector.get_table_comment.side_effect = RuntimeError("driver exploded")
    mock_logger = mocker.patch("superset.db_engine_specs.db2.logger")

    assert (
        Db2EngineSpec.get_table_comment(mock_inspector, Table("my_table", "my_schema"))
        is None
    )
    mock_logger.error.assert_called_once()
    mock_logger.exception.assert_called_once()


def test_get_prequeries(mocker: MockerFixture) -> None:
    """
    Test the ``get_prequeries`` method for both the schema and no-schema cases.
    """
    from superset.db_engine_specs.db2 import Db2EngineSpec

    database = mocker.MagicMock()

    assert Db2EngineSpec.get_prequeries(database) == []
    assert Db2EngineSpec.get_prequeries(database, schema="") == []
    assert Db2EngineSpec.get_prequeries(database, schema=None) == []
    assert Db2EngineSpec.get_prequeries(database, schema="my_schema") == [
        'set current_schema "my_schema"'
    ]
    assert Db2EngineSpec.get_prequeries(
        database, catalog="my_catalog", schema="my_schema"
    ) == ['set current_schema "my_schema"']


@pytest.mark.parametrize(
    ("grain", "expected_expression"),
    [
        (None, "my_col"),
        (
            TimeGrain.SECOND,
            "CAST(my_col as TIMESTAMP) - MICROSECOND(my_col) MICROSECONDS",
        ),
        (
            TimeGrain.MINUTE,
            "CAST(my_col as TIMESTAMP)"
            " - SECOND(my_col) SECONDS - MICROSECOND(my_col) MICROSECONDS",
        ),
        (
            TimeGrain.HOUR,
            "CAST(my_col as TIMESTAMP)"
            " - MINUTE(my_col) MINUTES"
            " - SECOND(my_col) SECONDS - MICROSECOND(my_col) MICROSECONDS ",
        ),
        (TimeGrain.DAY, "DATE(my_col)"),
        (TimeGrain.WEEK, "my_col - (DAYOFWEEK(my_col)) DAYS"),
        (TimeGrain.MONTH, "my_col - (DAY(my_col)-1) DAYS"),
        (
            TimeGrain.QUARTER,
            "my_col - (DAY(my_col)-1) DAYS"
            " - (MONTH(my_col)-1) MONTHS + ((QUARTER(my_col)-1) * 3) MONTHS",
        ),
        (
            TimeGrain.YEAR,
            "my_col - (DAY(my_col)-1) DAYS - (MONTH(my_col)-1) MONTHS",
        ),
    ],
)
def test_time_grain_expressions(grain: Optional[str], expected_expression: str) -> None:
    """
    Test that time grain expressions generate the expected SQL when the
    template is formatted with a column name.
    """
    from superset.db_engine_specs.db2 import Db2EngineSpec

    actual = Db2EngineSpec._time_grain_expressions[grain].format(col="my_col")
    assert actual == expected_expression


def test_time_grain_expressions_keys() -> None:
    """
    All standard ``TimeGrain`` values supported by Db2 should be present in
    ``_time_grain_expressions``.
    """
    from superset.db_engine_specs.db2 import Db2EngineSpec

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
    }
    assert set(Db2EngineSpec._time_grain_expressions.keys()) == expected_keys


@pytest.mark.parametrize(
    ("time_grain", "expected_sql"),
    [
        (None, "my_col"),
        (TimeGrain.DAY, "DATE(my_col)"),
        (TimeGrain.WEEK, "my_col - (DAYOFWEEK(my_col)) DAYS"),
        (TimeGrain.MONTH, "my_col - (DAY(my_col)-1) DAYS"),
    ],
)
def test_get_timestamp_expr(time_grain: Optional[str], expected_sql: str) -> None:
    """
    ``get_timestamp_expr`` should return a SQLAlchemy expression rendering to
    the same SQL as direct template substitution.
    """
    from superset.db_engine_specs.db2 import Db2EngineSpec

    expr = Db2EngineSpec.get_timestamp_expr(
        col=column("my_col"), pdf=None, time_grain=time_grain
    )
    assert str(expr) == expected_sql


def test_unsupported_time_grain() -> None:
    """
    Requesting an unsupported time grain should raise ``NotImplementedError``.
    """
    from superset.db_engine_specs.db2 import Db2EngineSpec

    with pytest.raises(NotImplementedError):
        Db2EngineSpec.get_timestamp_expr(
            col=column("my_col"), pdf=None, time_grain="PT2H"
        )


def test_time_grain_day_parseable() -> None:
    """
    Test that the DAY time grain expression generates valid SQL that can be
    parsed by sqlglot.

    This test addresses the bug where the previous expression
    ``CAST({col} as TIMESTAMP) - HOUR({col}) HOURS - ...`` could not be parsed
    by sqlglot.
    """
    from superset.db_engine_specs.db2 import Db2EngineSpec

    expression = Db2EngineSpec._time_grain_expressions[TimeGrain.DAY].format(
        col="my_timestamp_col",
    )
    sql = f"SELECT {expression} FROM my_table"  # noqa: S608

    try:
        parsed = parse_one(sql)
        assert parsed is not None
    except ParseError as e:
        pytest.fail(f"Failed to parse DAY time grain SQL: {e}")
