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
import sys
import types as py_types
from collections.abc import Generator
from datetime import datetime, timezone
from typing import Optional
from unittest import mock

import pytest
from sqlalchemy import column
from sqlalchemy.dialects.mssql.base import SMALLDATETIME

from superset.constants import TimeGrain
from superset.db_engine_specs.base import DatabaseCategory
from superset.db_engine_specs.exceptions import (
    SupersetDBAPIDatabaseError,
    SupersetDBAPIOperationalError,
    SupersetDBAPIProgrammingError,
)
from superset.db_engine_specs.kusto import KustoKqlEngineSpec, KustoSqlEngineSpec
from superset.sql.parse import LimitMethod, SQLScript
from superset.utils.core import GenericDataType
from tests.unit_tests.db_engine_specs.utils import assert_convert_dttm
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


@pytest.mark.parametrize(
    "sql,expected",
    [
        ("SELECT foo FROM tbl", False),
        ("SHOW TABLES", False),
        ("EXPLAIN SELECT foo FROM tbl", False),
        ("INSERT INTO tbl (foo) VALUES (1)", True),
        ("UPDATE tbl SET foo = 1", True),
        ("DELETE FROM tbl WHERE foo = 1", True),
    ],
)
def test_sql_has_mutation(sql: str, expected: bool) -> None:
    """SQL dialect: only SELECT/SHOW/EXPLAIN are read-only."""
    assert SQLScript(sql, engine=KustoSqlEngineSpec.engine).has_mutation() == expected


@pytest.mark.parametrize(
    "kql,expected",
    [
        ("tbl | limit 100", False),
        ("let foo = 1; tbl | where bar == foo", False),
        (".show tables", False),
        ("print 1", False),
        ("set querytrace; Events | take 100", False),
        (".drop table foo", True),
        (".set-or-append table foo <| bar", True),
    ],
)
def test_kql_has_mutation(kql: str, expected: bool) -> None:
    """KQL dialect: only read-style queries are non-mutating."""
    assert SQLScript(kql, engine=KustoKqlEngineSpec.engine).has_mutation() == expected


def test_sql_engine_attributes() -> None:
    """KustoSqlEngineSpec exposes the expected dialect attributes."""
    assert KustoSqlEngineSpec.engine == "kustosql"
    assert KustoSqlEngineSpec.engine_name == "Azure Data Explorer"
    assert KustoSqlEngineSpec.limit_method == LimitMethod.WRAP_SQL
    assert KustoSqlEngineSpec.time_groupby_inline is True
    assert KustoSqlEngineSpec.allows_joins is True
    assert KustoSqlEngineSpec.allows_subqueries is True
    assert KustoSqlEngineSpec.allows_sql_comments is False


def test_kql_engine_attributes() -> None:
    """KustoKqlEngineSpec exposes the expected dialect attributes."""
    assert KustoKqlEngineSpec.engine == "kustokql"
    assert KustoKqlEngineSpec.engine_name == "Azure Data Explorer (KQL)"
    assert KustoKqlEngineSpec.time_groupby_inline is True
    assert KustoKqlEngineSpec.allows_joins is True
    assert KustoKqlEngineSpec.allows_subqueries is True
    assert KustoKqlEngineSpec.allows_sql_comments is False
    assert KustoKqlEngineSpec.run_multiple_statements_as_one is True


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Date", "CONVERT(DATE, '2019-01-02', 23)"),
        ("DateTime", "CONVERT(DATETIME, '2019-01-02T03:04:05.678', 126)"),
        ("SmallDateTime", "CONVERT(SMALLDATETIME, '2019-01-02 03:04:05', 20)"),
        ("TimeStamp", "CONVERT(TIMESTAMP, '2019-01-02 03:04:05', 20)"),
        ("UnknownType", None),
        ("", None),
    ],
)
def test_sql_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    """KustoSqlEngineSpec.convert_dttm covers all branches of the SQL dialect."""
    assert_convert_dttm(KustoSqlEngineSpec, target_type, expected_result, dttm)


def test_sql_convert_dttm_with_timezone(dttm: datetime) -> None:  # noqa: F811
    """convert_dttm preserves an attached timezone in the rendered ISO string."""
    aware = dttm.replace(tzinfo=timezone.utc)
    result = KustoSqlEngineSpec.convert_dttm("DateTime", aware)
    assert result is not None
    assert "+00:00" in result


def test_sql_convert_dttm_db_extra_ignored(dttm: datetime) -> None:  # noqa: F811
    """db_extra is accepted but does not influence the rendered expression."""
    base = KustoSqlEngineSpec.convert_dttm("Date", dttm)
    with_extra = KustoSqlEngineSpec.convert_dttm("Date", dttm, db_extra={"x": 1})
    assert base == with_extra == "CONVERT(DATE, '2019-01-02', 23)"


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("DateTime", "datetime(2019-01-02T03:04:05.678900)"),
        ("TimeStamp", "datetime(2019-01-02T03:04:05.678900)"),
        ("Date", "datetime(2019-01-02)"),
        ("UnknownType", None),
        ("", None),
    ],
)
def test_kql_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    """KustoKqlEngineSpec.convert_dttm covers all branches of the KQL dialect."""
    assert_convert_dttm(KustoKqlEngineSpec, target_type, expected_result, dttm)


def test_kql_convert_dttm_with_timezone(dttm: datetime) -> None:  # noqa: F811
    """KQL convert_dttm preserves microsecond precision and tz info."""
    aware = dttm.replace(tzinfo=timezone.utc)
    result = KustoKqlEngineSpec.convert_dttm("DateTime", aware)
    assert result is not None
    assert result.startswith("datetime(2019-01-02T03:04:05.678900")
    assert "+00:00" in result


@pytest.mark.parametrize(
    "in_duration,expected_result",
    [
        ("PT1S", "bin(temporal,1s)"),
        ("PT30S", "bin(temporal,30s)"),
        ("PT1M", "bin(temporal,1m)"),
        ("PT5M", "bin(temporal,5m)"),
        ("PT30M", "bin(temporal,30m)"),
        ("PT1H", "bin(temporal,1h)"),
        ("P1D", "startofday(temporal)"),
        ("P1W", "startofweek(temporal)"),
        ("P1M", "startofmonth(temporal)"),
        ("P1Y", "startofyear(temporal)"),
    ],
)
def test_kql_timegrain_expressions(in_duration: str, expected_result: str) -> None:
    """KustoKqlEngineSpec maps every TimeGrain duration to the correct KQL bin."""
    col = column("temporal")
    actual_result = KustoKqlEngineSpec.get_timestamp_expr(
        col=col, pdf=None, time_grain=in_duration
    )
    assert str(actual_result) == expected_result


def test_kql_timegrain_no_grain() -> None:
    """KQL spec passes a column through unchanged when no grain is provided."""
    col = column("temporal")
    actual_result = KustoKqlEngineSpec.get_timestamp_expr(
        col=col, pdf=None, time_grain=None
    )
    assert str(actual_result) == "temporal"


@pytest.mark.parametrize(
    "in_duration",
    [
        "PT1S",
        "PT1M",
        "PT5M",
        "PT10M",
        "PT15M",
        "PT0.5H",
        "PT1H",
        "P1D",
        "P1W",
        "P1M",
        "P3M",
        "P1Y",
    ],
)
def test_sql_timegrain_expressions(in_duration: str) -> None:
    """KustoSqlEngineSpec wraps every supported TimeGrain in DATEADD/DATEDIFF."""
    col = column("temporal")
    actual_result = KustoSqlEngineSpec.get_timestamp_expr(
        col=col, pdf=None, time_grain=in_duration
    )
    rendered = str(actual_result)
    assert "DATEADD" in rendered
    assert "temporal" in rendered


def test_sql_timegrain_no_grain() -> None:
    """SQL spec passes a column through unchanged when no grain is provided."""
    col = column("temporal")
    actual_result = KustoSqlEngineSpec.get_timestamp_expr(
        col=col, pdf=None, time_grain=None
    )
    assert str(actual_result) == "temporal"


def test_sql_timegrain_keys_present() -> None:
    """The SQL grain table covers the durations defined by the source spec."""
    keys = set(KustoSqlEngineSpec._time_grain_expressions.keys())
    expected = {
        None,
        TimeGrain.SECOND,
        TimeGrain.MINUTE,
        TimeGrain.FIVE_MINUTES,
        TimeGrain.TEN_MINUTES,
        TimeGrain.FIFTEEN_MINUTES,
        TimeGrain.HALF_HOUR,
        TimeGrain.HOUR,
        TimeGrain.DAY,
        TimeGrain.WEEK,
        TimeGrain.MONTH,
        TimeGrain.QUARTER,
        TimeGrain.YEAR,
        TimeGrain.WEEK_STARTING_SUNDAY,
        TimeGrain.WEEK_STARTING_MONDAY,
    }
    assert keys == expected


def test_kql_timegrain_keys_present() -> None:
    """The KQL grain table covers the durations defined by the source spec."""
    keys = set(KustoKqlEngineSpec._time_grain_expressions.keys())
    expected = {
        None,
        TimeGrain.SECOND,
        TimeGrain.THIRTY_SECONDS,
        TimeGrain.MINUTE,
        TimeGrain.FIVE_MINUTES,
        TimeGrain.THIRTY_MINUTES,
        TimeGrain.HOUR,
        TimeGrain.DAY,
        TimeGrain.WEEK,
        TimeGrain.MONTH,
        TimeGrain.YEAR,
    }
    assert keys == expected


def test_sql_metadata_structure() -> None:
    """KustoSqlEngineSpec.metadata has the documented top-level keys and values."""
    metadata = KustoSqlEngineSpec.metadata
    assert "description" in metadata
    assert metadata["logo"] == "kusto.png"
    assert (
        metadata["homepage_url"]
        == "https://azure.microsoft.com/en-us/products/data-explorer/"
    )
    assert DatabaseCategory.CLOUD_AZURE in metadata["categories"]
    assert DatabaseCategory.ANALYTICAL_DATABASES in metadata["categories"]
    assert DatabaseCategory.PROPRIETARY in metadata["categories"]
    assert metadata["pypi_packages"] == ["sqlalchemy-kusto"]
    assert "kustosql+https" in metadata["connection_string"]


def test_sql_metadata_drivers_and_parameters() -> None:
    """metadata advertises both SQL and KQL drivers with required parameters."""
    metadata = KustoSqlEngineSpec.metadata
    drivers = metadata["drivers"]
    assert {d["name"] for d in drivers} == {
        "SQL Interface (Recommended)",
        "KQL (Kusto Query Language)",
    }
    sql_driver = next(d for d in drivers if d["is_recommended"])
    kql_driver = next(d for d in drivers if not d["is_recommended"])
    assert sql_driver["pypi_package"] == "sqlalchemy-kusto"
    assert "kustosql+https" in sql_driver["connection_string"]
    assert "kustokql+https" in kql_driver["connection_string"]
    assert set(metadata["parameters"]) == {
        "cluster",
        "database",
        "client_id",
        "client_secret",
        "tenant_id",
    }


def test_sql_column_type_mapping_smalldatetime() -> None:
    """The smalldatetime regex maps to SMALLDATETIME with TEMPORAL category."""
    pattern, sqla_type, generic = KustoSqlEngineSpec.column_type_mappings[0]
    assert pattern.match("SMALLDATETIME")
    assert pattern.match("smalldatetime")
    assert pattern.match("smalldatetime(0)")
    assert pattern.match("SMALLDATETIME with extras")
    assert pattern.match("datetime") is None
    assert isinstance(sqla_type, SMALLDATETIME)
    assert generic is GenericDataType.TEMPORAL


def test_type_code_map_starts_empty() -> None:
    """Both engine specs start with an empty type_code_map cache."""
    assert KustoSqlEngineSpec.type_code_map == {}
    assert KustoKqlEngineSpec.type_code_map == {}


def test_sql_epoch_to_dttm_not_overridden() -> None:
    """KustoSqlEngineSpec inherits the base epoch_to_dttm (raises)."""
    with pytest.raises(NotImplementedError):
        KustoSqlEngineSpec.epoch_to_dttm()


def test_kql_epoch_to_dttm_not_overridden() -> None:
    """KustoKqlEngineSpec inherits the base epoch_to_dttm (raises)."""
    with pytest.raises(NotImplementedError):
        KustoKqlEngineSpec.epoch_to_dttm()


class _FakeKustoErrors(py_types.ModuleType):
    DatabaseError: type[Exception]
    OperationalError: type[Exception]
    ProgrammingError: type[Exception]


def _install_fake_sqlalchemy_kusto() -> _FakeKustoErrors:
    """Inject a stub ``sqlalchemy_kusto.errors`` module so the mapping imports."""
    parent = py_types.ModuleType("sqlalchemy_kusto")
    errors = _FakeKustoErrors("sqlalchemy_kusto.errors")

    class DatabaseError(Exception):
        pass

    class OperationalError(Exception):
        pass

    class ProgrammingError(Exception):
        pass

    errors.DatabaseError = DatabaseError
    errors.OperationalError = OperationalError
    errors.ProgrammingError = ProgrammingError
    parent.errors = errors  # type: ignore[attr-defined]

    sys.modules["sqlalchemy_kusto"] = parent
    sys.modules["sqlalchemy_kusto.errors"] = errors
    return errors


@pytest.fixture
def fake_kusto_errors() -> Generator[_FakeKustoErrors, None, None]:
    saved_parent = sys.modules.get("sqlalchemy_kusto")
    saved_errors = sys.modules.get("sqlalchemy_kusto.errors")
    errors = _install_fake_sqlalchemy_kusto()
    try:
        yield errors
    finally:
        if saved_parent is not None:
            sys.modules["sqlalchemy_kusto"] = saved_parent
        else:
            sys.modules.pop("sqlalchemy_kusto", None)
        if saved_errors is not None:
            sys.modules["sqlalchemy_kusto.errors"] = saved_errors
        else:
            sys.modules.pop("sqlalchemy_kusto.errors", None)


def test_sql_get_dbapi_exception_mapping(
    fake_kusto_errors: _FakeKustoErrors,
) -> None:
    """KustoSqlEngineSpec maps each kusto exception to a Superset DBAPI error."""
    mapping = KustoSqlEngineSpec.get_dbapi_exception_mapping()
    assert mapping == {
        fake_kusto_errors.DatabaseError: SupersetDBAPIDatabaseError,
        fake_kusto_errors.OperationalError: SupersetDBAPIOperationalError,
        fake_kusto_errors.ProgrammingError: SupersetDBAPIProgrammingError,
    }


def test_kql_get_dbapi_exception_mapping(
    fake_kusto_errors: _FakeKustoErrors,
) -> None:
    """KustoKqlEngineSpec maps each kusto exception to a Superset DBAPI error."""
    mapping = KustoKqlEngineSpec.get_dbapi_exception_mapping()
    assert mapping == {
        fake_kusto_errors.DatabaseError: SupersetDBAPIDatabaseError,
        fake_kusto_errors.OperationalError: SupersetDBAPIOperationalError,
        fake_kusto_errors.ProgrammingError: SupersetDBAPIProgrammingError,
    }


def test_get_dbapi_exception_mapping_propagates_import_error() -> None:
    """If ``sqlalchemy_kusto`` cannot be imported, ImportError surfaces."""
    saved_parent = sys.modules.pop("sqlalchemy_kusto", None)
    saved_errors = sys.modules.pop("sqlalchemy_kusto.errors", None)
    try:
        with mock.patch.dict(sys.modules, {}):
            sys.modules.pop("sqlalchemy_kusto", None)
            sys.modules.pop("sqlalchemy_kusto.errors", None)
            with pytest.raises(ModuleNotFoundError):
                KustoSqlEngineSpec.get_dbapi_exception_mapping()
            with pytest.raises(ModuleNotFoundError):
                KustoKqlEngineSpec.get_dbapi_exception_mapping()
    finally:
        if saved_parent is not None:
            sys.modules["sqlalchemy_kusto"] = saved_parent
        if saved_errors is not None:
            sys.modules["sqlalchemy_kusto.errors"] = saved_errors
