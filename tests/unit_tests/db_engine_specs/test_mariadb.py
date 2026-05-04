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

# pylint: disable=import-outside-toplevel

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import column, types
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
from sqlalchemy.engine.url import make_url

from superset.utils.core import GenericDataType
from tests.unit_tests.db_engine_specs.utils import (
    assert_column_spec,
    assert_convert_dttm,
)
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


# ---------------------------------------------------------------------------
# Class attributes
# ---------------------------------------------------------------------------
def test_mariadb_engine_spec_engine_attribute() -> None:
    from superset.db_engine_specs.mariadb import MariaDBEngineSpec

    assert MariaDBEngineSpec.engine == "mariadb"


def test_mariadb_engine_spec_engine_name_attribute() -> None:
    from superset.db_engine_specs.mariadb import MariaDBEngineSpec

    assert MariaDBEngineSpec.engine_name == "MariaDB"


def test_mariadb_engine_spec_metadata_keys() -> None:
    from superset.db_engine_specs.mariadb import MariaDBEngineSpec

    assert isinstance(MariaDBEngineSpec.metadata, dict)
    for key in (
        "description",
        "logo",
        "homepage_url",
        "categories",
        "pypi_packages",
        "connection_string",
        "default_port",
        "notes",
    ):
        assert key in MariaDBEngineSpec.metadata


def test_mariadb_engine_spec_metadata_values() -> None:
    from superset.db_engine_specs.mariadb import MariaDBEngineSpec

    metadata = MariaDBEngineSpec.metadata
    assert metadata["logo"] == "mariadb.png"
    assert metadata["homepage_url"] == "https://mariadb.org/"
    assert metadata["default_port"] == 3306
    assert metadata["pypi_packages"] == ["mysqlclient"]
    assert metadata["connection_string"] == (
        "mysql://{username}:{password}@{host}/{database}"
    )
    assert "MariaDB" in metadata["description"]
    assert "MySQL driver" in metadata["notes"]


def test_mariadb_engine_spec_categories() -> None:
    from superset.db_engine_specs.base import DatabaseCategory
    from superset.db_engine_specs.mariadb import MariaDBEngineSpec

    categories = MariaDBEngineSpec.metadata["categories"]
    assert DatabaseCategory.TRADITIONAL_RDBMS in categories
    assert DatabaseCategory.OPEN_SOURCE in categories


# ---------------------------------------------------------------------------
# Inheritance from MySQLEngineSpec
# ---------------------------------------------------------------------------
def test_mariadb_inherits_from_mysql() -> None:
    from superset.db_engine_specs.mariadb import MariaDBEngineSpec
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    assert issubclass(MariaDBEngineSpec, MySQLEngineSpec)


def test_mariadb_inherits_class_settings() -> None:
    from superset.db_engine_specs.mariadb import MariaDBEngineSpec

    # Settings inherited from MySQLEngineSpec.
    assert MariaDBEngineSpec.default_driver == "mysqldb"
    assert MariaDBEngineSpec.max_column_name_length == 64
    assert MariaDBEngineSpec.supports_dynamic_schema is True
    assert MariaDBEngineSpec.supports_multivalues_insert is True
    assert MariaDBEngineSpec.encryption_parameters == {"ssl": "1"}


def test_mariadb_overrides_engine_identity_only() -> None:
    """
    MariaDB only overrides identity/branding fields. The class body should not
    redefine behavioral attributes inherited from ``MySQLEngineSpec``.
    """
    from superset.db_engine_specs.mariadb import MariaDBEngineSpec

    own_attrs = set(vars(MariaDBEngineSpec))
    # Allow dunder attributes added by Python itself.
    overrides = {a for a in own_attrs if not a.startswith("__")}
    assert overrides == {"engine", "engine_name", "metadata"}


# ---------------------------------------------------------------------------
# convert_dttm – inherited from MySQLEngineSpec
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Date", "STR_TO_DATE('2019-01-02', '%Y-%m-%d')"),
        (
            "DateTime",
            "STR_TO_DATE('2019-01-02 03:04:05.678900', '%Y-%m-%d %H:%i:%s.%f')",
        ),
        ("UnknownType", None),
        ("", None),
    ],
)
def test_mariadb_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    from superset.db_engine_specs.mariadb import MariaDBEngineSpec

    assert_convert_dttm(MariaDBEngineSpec, target_type, expected_result, dttm)


def test_mariadb_convert_dttm_with_extreme_dates() -> None:
    from superset.db_engine_specs.mariadb import MariaDBEngineSpec

    early = datetime(1, 1, 1, 0, 0, 0)
    assert MariaDBEngineSpec.convert_dttm("Date", early) == (
        "STR_TO_DATE('0001-01-01', '%Y-%m-%d')"
    )

    late = datetime(9999, 12, 31, 23, 59, 59, 999999)
    assert MariaDBEngineSpec.convert_dttm("DateTime", late) == (
        "STR_TO_DATE('9999-12-31 23:59:59.999999', '%Y-%m-%d %H:%i:%s.%f')"
    )


# ---------------------------------------------------------------------------
# epoch_to_dttm – inherited from MySQLEngineSpec
# ---------------------------------------------------------------------------
def test_mariadb_epoch_to_dttm() -> None:
    from superset.db_engine_specs.mariadb import MariaDBEngineSpec

    expression = MariaDBEngineSpec.epoch_to_dttm()
    assert "from_unixtime" in expression
    # Format string passed to ``str.format`` must accept a column substitution.
    assert expression.format(col="ts") == "from_unixtime(ts)"


# ---------------------------------------------------------------------------
# get_column_spec – inherited from MySQLEngineSpec
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "native_type,sqla_type,generic_type,is_dttm",
    [
        # Numeric
        ("TINYINT", TINYINT, GenericDataType.NUMERIC, False),
        ("SMALLINT", types.SmallInteger, GenericDataType.NUMERIC, False),
        ("MEDIUMINT", MEDIUMINT, GenericDataType.NUMERIC, False),
        ("INT", INTEGER, GenericDataType.NUMERIC, False),
        ("BIGINT", types.BigInteger, GenericDataType.NUMERIC, False),
        ("DECIMAL", DECIMAL, GenericDataType.NUMERIC, False),
        ("FLOAT", FLOAT, GenericDataType.NUMERIC, False),
        ("DOUBLE", DOUBLE, GenericDataType.NUMERIC, False),
        ("BIT", BIT, GenericDataType.NUMERIC, False),
        # String
        ("CHAR", types.String, GenericDataType.STRING, False),
        ("VARCHAR", types.String, GenericDataType.STRING, False),
        ("TINYTEXT", TINYTEXT, GenericDataType.STRING, False),
        ("MEDIUMTEXT", MEDIUMTEXT, GenericDataType.STRING, False),
        ("LONGTEXT", LONGTEXT, GenericDataType.STRING, False),
        # Temporal
        ("DATE", types.Date, GenericDataType.TEMPORAL, True),
        ("DATETIME", types.DateTime, GenericDataType.TEMPORAL, True),
        ("TIMESTAMP", types.TIMESTAMP, GenericDataType.TEMPORAL, True),
        ("TIME", types.Time, GenericDataType.TEMPORAL, True),
    ],
)
def test_mariadb_get_column_spec(
    native_type: str,
    sqla_type: type[types.TypeEngine],
    generic_type: GenericDataType,
    is_dttm: bool,
) -> None:
    from superset.db_engine_specs.mariadb import MariaDBEngineSpec

    assert_column_spec(
        MariaDBEngineSpec, native_type, sqla_type, None, generic_type, is_dttm
    )


def test_mariadb_get_column_spec_unknown_type() -> None:
    from superset.db_engine_specs.mariadb import MariaDBEngineSpec

    assert MariaDBEngineSpec.get_column_spec("DEFINITELY_NOT_A_TYPE") is None


# ---------------------------------------------------------------------------
# validate_database_uri – inherited from MySQLEngineSpec
# ---------------------------------------------------------------------------
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
def test_mariadb_validate_database_uri(sqlalchemy_uri: str, error: bool) -> None:
    from superset.db_engine_specs.mariadb import MariaDBEngineSpec

    url = make_url(sqlalchemy_uri)
    if error:
        with pytest.raises(ValueError):  # noqa: PT011
            MariaDBEngineSpec.validate_database_uri(url)
        return
    MariaDBEngineSpec.validate_database_uri(url)


# ---------------------------------------------------------------------------
# adjust_engine_params – inherited from MySQLEngineSpec
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "sqlalchemy_uri,connect_args,expected",
    [
        (
            "mysql://user:password@host/db1",
            {"local_infile": 1},
            {"local_infile": 0},
        ),
        (
            "mysql://user:password@host/db1",
            {"local_infile": -1},
            {"local_infile": 0},
        ),
        (
            "mysql://user:password@host/db1",
            {"local_infile": 0},
            {"local_infile": 0},
        ),
        (
            "mysql://user:password@host/db1",
            {"param1": "some_value"},
            {"local_infile": 0, "param1": "some_value"},
        ),
        (
            "mysql+mysqlconnector://user:password@host/db1",
            {"allow_local_infile": 1, "param1": "some_value"},
            {"allow_local_infile": 0, "param1": "some_value"},
        ),
        (
            "mysql://user:password@host/db1",
            {},
            {"local_infile": 0},
        ),
    ],
)
def test_mariadb_adjust_engine_params(
    sqlalchemy_uri: str,
    connect_args: dict[str, object],
    expected: dict[str, object],
) -> None:
    from superset.db_engine_specs.mariadb import MariaDBEngineSpec

    url = make_url(sqlalchemy_uri)
    _, returned = MariaDBEngineSpec.adjust_engine_params(url, connect_args)
    assert returned == expected


# ---------------------------------------------------------------------------
# cancel_query / get_cancel_query_id – inherited from MySQLEngineSpec
# ---------------------------------------------------------------------------
@patch("sqlalchemy.engine.Engine.connect")
def test_mariadb_get_cancel_query_id(engine_mock: Mock) -> None:
    from superset.db_engine_specs.mariadb import MariaDBEngineSpec
    from superset.models.sql_lab import Query

    query = Query()
    cursor_mock = engine_mock.return_value.__enter__.return_value
    cursor_mock.fetchone.return_value = ["123"]
    assert MariaDBEngineSpec.get_cancel_query_id(cursor_mock, query) == "123"


@patch("sqlalchemy.engine.Engine.connect")
def test_mariadb_cancel_query(engine_mock: Mock) -> None:
    from superset.db_engine_specs.mariadb import MariaDBEngineSpec
    from superset.models.sql_lab import Query

    query = Query()
    cursor_mock = engine_mock.return_value.__enter__.return_value
    assert MariaDBEngineSpec.cancel_query(cursor_mock, query, "123") is True


@patch("sqlalchemy.engine.Engine.connect")
def test_mariadb_cancel_query_failed(engine_mock: Mock) -> None:
    from superset.db_engine_specs.mariadb import MariaDBEngineSpec
    from superset.models.sql_lab import Query

    query = Query()
    cursor_mock = engine_mock.raiseError.side_effect = Exception()
    assert MariaDBEngineSpec.cancel_query(cursor_mock, query, "123") is False


# ---------------------------------------------------------------------------
# get_schema_from_engine_params – inherited from MySQLEngineSpec
# ---------------------------------------------------------------------------
def test_mariadb_get_schema_from_engine_params() -> None:
    from superset.db_engine_specs.mariadb import MariaDBEngineSpec

    assert (
        MariaDBEngineSpec.get_schema_from_engine_params(
            make_url("mysql://user:password@host/db1"), {}
        )
        == "db1"
    )


# ---------------------------------------------------------------------------
# fetch_data / column_type_mutator – inherited from MySQLEngineSpec
# ---------------------------------------------------------------------------
def test_mariadb_fetch_data_decimal_string_is_coerced() -> None:
    from superset.db_engine_specs.mariadb import MariaDBEngineSpec

    cursor = Mock()
    cursor.description = [("dec", "decimal(12,6)"), ("str", "varchar(3)")]
    cursor.fetchall.return_value = [("1.23456", "abc")]

    assert MariaDBEngineSpec.fetch_data(cursor) == [(Decimal("1.23456"), "abc")]


def test_mariadb_fetch_data_decimal_passthrough() -> None:
    from superset.db_engine_specs.mariadb import MariaDBEngineSpec

    cursor = Mock()
    cursor.description = [("dec", "decimal(12,6)"), ("str", "varchar(3)")]
    cursor.fetchall.return_value = [(Decimal("1.23456"), "abc")]

    assert MariaDBEngineSpec.fetch_data(cursor) == [(Decimal("1.23456"), "abc")]


def test_mariadb_fetch_data_null_decimal_preserved() -> None:
    from superset.db_engine_specs.mariadb import MariaDBEngineSpec

    cursor = Mock()
    cursor.description = [("dec", "decimal(12,6)"), ("str", "varchar(3)")]
    cursor.fetchall.return_value = [(None, "abc")]

    assert MariaDBEngineSpec.fetch_data(cursor) == [(None, "abc")]


def test_mariadb_fetch_data_non_decimal_unchanged() -> None:
    from superset.db_engine_specs.mariadb import MariaDBEngineSpec

    cursor = Mock()
    cursor.description = [("dec", "varchar(255)"), ("str", "varchar(3)")]
    cursor.fetchall.return_value = [("1.23456", "abc")]

    assert MariaDBEngineSpec.fetch_data(cursor) == [("1.23456", "abc")]


# ---------------------------------------------------------------------------
# Time grain expressions – inherited from MySQLEngineSpec
# ---------------------------------------------------------------------------
def test_mariadb_time_grain_expressions_inherit_from_mysql() -> None:
    """``_time_grain_expressions`` should be exactly the MySQL grain mapping."""
    from superset.db_engine_specs.mariadb import MariaDBEngineSpec
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    assert (
        MariaDBEngineSpec._time_grain_expressions
        is MySQLEngineSpec._time_grain_expressions
    )


@pytest.mark.parametrize(
    "grain",
    ["PT1S", "PT1M", "PT1H", "P1D", "P1W", "P1M", "P3M", "P1Y"],
)
def test_mariadb_time_grain_expression_renders(grain: str) -> None:
    from superset.db_engine_specs.mariadb import MariaDBEngineSpec

    col = column("my_col", types.DateTime)
    expr = MariaDBEngineSpec.get_timestamp_expr(col=col, pdf=None, time_grain=grain)
    rendered = str(expr.compile(compile_kwargs={"literal_binds": True}))
    assert "my_col" in rendered


@pytest.mark.parametrize("pdf", ["epoch_s", "epoch_ms"])
def test_mariadb_time_grain_expression_with_epoch(pdf: str) -> None:
    from superset.db_engine_specs.mariadb import MariaDBEngineSpec

    col = column("ts", types.BigInteger)
    expr = MariaDBEngineSpec.get_timestamp_expr(col=col, pdf=pdf, time_grain="P1D")
    rendered = str(expr.compile(compile_kwargs={"literal_binds": True}))
    assert "from_unixtime" in rendered.lower()
