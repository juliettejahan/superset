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

import sys
import types as py_types
from datetime import datetime, timezone
from typing import Any, Optional
from unittest.mock import patch

import pytest
from sqlalchemy import column, types as sqla_types

from superset.constants import TimeGrain
from superset.db_engine_specs.base import DatabaseCategory
from superset.db_engine_specs.elasticsearch import (
    ElasticSearchEngineSpec,
    OpenDistroEngineSpec,
)
from superset.db_engine_specs.exceptions import (
    SupersetDBAPIDatabaseError,
    SupersetDBAPIOperationalError,
    SupersetDBAPIProgrammingError,
)
from tests.unit_tests.db_engine_specs.utils import assert_convert_dttm
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


# ---------------------------------------------------------------------------
# ElasticSearchEngineSpec class-level attributes
# ---------------------------------------------------------------------------
def test_elasticsearch_engine_attributes() -> None:
    assert ElasticSearchEngineSpec.engine == "elasticsearch"
    assert ElasticSearchEngineSpec.engine_name == "Elasticsearch"
    assert ElasticSearchEngineSpec.time_groupby_inline is True
    assert ElasticSearchEngineSpec.allows_joins is False
    assert ElasticSearchEngineSpec.allows_subqueries is True
    assert ElasticSearchEngineSpec.allows_sql_comments is False


def test_elasticsearch_metadata_structure() -> None:
    metadata = ElasticSearchEngineSpec.metadata
    assert "description" in metadata
    assert "Elasticsearch is a distributed search" in metadata["description"]
    assert metadata["logo"] == "elasticsearch.png"
    assert metadata["homepage_url"] == "https://www.elastic.co/elasticsearch/"
    assert DatabaseCategory.SEARCH_NOSQL in metadata["categories"]
    assert DatabaseCategory.OPEN_SOURCE in metadata["categories"]
    assert metadata["pypi_packages"] == ["elasticsearch-dbapi"]
    assert metadata["default_port"] == 9243
    assert "user" in metadata["parameters"]
    assert "password" in metadata["parameters"]
    assert "host" in metadata["parameters"]


def test_elasticsearch_metadata_drivers() -> None:
    drivers = ElasticSearchEngineSpec.metadata["drivers"]
    assert len(drivers) == 2

    recommended = drivers[0]
    assert recommended["name"] == "Elasticsearch SQL API (Recommended)"
    assert recommended["pypi_package"] == "elasticsearch-dbapi"
    assert recommended["is_recommended"] is True
    assert "elasticsearch+https://" in recommended["connection_string"]

    opendistro = drivers[1]
    assert opendistro["name"] == "OpenDistro / OpenSearch SQL"
    assert opendistro["pypi_package"] == "elasticsearch-dbapi"
    assert opendistro["is_recommended"] is False
    assert "odelasticsearch+https://" in opendistro["connection_string"]


def test_elasticsearch_metadata_compatible_databases() -> None:
    databases = ElasticSearchEngineSpec.metadata["compatible_databases"]
    assert len(databases) == 2

    elastic_cloud = databases[0]
    assert elastic_cloud["name"] == "Elastic Cloud"
    assert DatabaseCategory.SEARCH_NOSQL in elastic_cloud["categories"]
    assert DatabaseCategory.HOSTED_OPEN_SOURCE in elastic_cloud["categories"]
    assert "cloud.es.io" in elastic_cloud["connection_string"]

    aws = databases[1]
    assert aws["name"] == "Amazon OpenSearch Service"
    assert DatabaseCategory.CLOUD_AWS in aws["categories"]
    assert DatabaseCategory.SEARCH_NOSQL in aws["categories"]


def test_elasticsearch_date_trunc_functions() -> None:
    assert ElasticSearchEngineSpec._date_trunc_functions == {"DATETIME": "DATE_TRUNC"}


def test_elasticsearch_type_code_map_default_empty() -> None:
    assert ElasticSearchEngineSpec.type_code_map == {}


# ---------------------------------------------------------------------------
# ElasticSearchEngineSpec time grain expressions
# ---------------------------------------------------------------------------
def test_elasticsearch_time_grain_expressions_keys() -> None:
    expected_keys = {
        None,
        TimeGrain.SECOND,
        TimeGrain.MINUTE,
        TimeGrain.HOUR,
        TimeGrain.DAY,
        TimeGrain.WEEK,
        TimeGrain.MONTH,
        TimeGrain.YEAR,
    }
    assert set(ElasticSearchEngineSpec._time_grain_expressions.keys()) == expected_keys


def test_elasticsearch_time_grain_expressions_values() -> None:
    expressions = ElasticSearchEngineSpec._time_grain_expressions
    assert expressions[None] == "{col}"
    assert expressions[TimeGrain.SECOND] == "{func}('second', {col})"
    assert expressions[TimeGrain.MINUTE] == "{func}('minute', {col})"
    assert expressions[TimeGrain.HOUR] == "{func}('hour', {col})"
    assert expressions[TimeGrain.DAY] == "{func}('day', {col})"
    assert expressions[TimeGrain.WEEK] == "{func}('week', {col})"
    assert expressions[TimeGrain.MONTH] == "{func}('month', {col})"
    assert expressions[TimeGrain.YEAR] == "{func}('year', {col})"


@pytest.mark.parametrize(
    "time_grain,expected_result",
    [
        ("PT1S", "DATE_TRUNC('second', col)"),
        ("PT1M", "DATE_TRUNC('minute', col)"),
        ("PT1H", "DATE_TRUNC('hour', col)"),
        ("P1D", "DATE_TRUNC('day', col)"),
        ("P1W", "DATE_TRUNC('week', col)"),
        ("P1M", "DATE_TRUNC('month', col)"),
        ("P1Y", "DATE_TRUNC('year', col)"),
    ],
)
def test_elasticsearch_get_timestamp_expr_with_datetime_column(
    time_grain: str, expected_result: str
) -> None:
    """With DATETIME columns, ``{func}`` is replaced via ``_date_trunc_functions``."""
    actual = str(
        ElasticSearchEngineSpec.get_timestamp_expr(
            col=column("col", type_=sqla_types.DateTime()),
            pdf=None,
            time_grain=time_grain,
        )
    )
    assert actual == expected_result


def test_elasticsearch_get_timestamp_expr_unmapped_column_keeps_func_token() -> None:
    """If the column has no matching type, {func} placeholder is left untouched."""
    actual = str(
        ElasticSearchEngineSpec.get_timestamp_expr(
            col=column("col"), pdf=None, time_grain="PT1S"
        )
    )
    assert actual == "{func}('second', col)"


def test_elasticsearch_get_timestamp_expr_no_grain() -> None:
    actual = str(
        ElasticSearchEngineSpec.get_timestamp_expr(
            col=column("col"), pdf=None, time_grain=None
        )
    )
    assert actual == "col"


def test_elasticsearch_unsupported_time_grain() -> None:
    with pytest.raises(NotImplementedError):
        ElasticSearchEngineSpec.get_timestamp_expr(
            col=column("col"), pdf=None, time_grain="P3M"
        )


# ---------------------------------------------------------------------------
# ElasticSearchEngineSpec.convert_dttm
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "target_type,db_extra,expected_result",
    [
        # No db_extra (None) → falls back to CAST.
        ("DateTime", None, "CAST('2019-01-02T03:04:05' AS DATETIME)"),
        # Empty db_extra dict → no version, falls back to CAST.
        ("DateTime", {}, "CAST('2019-01-02T03:04:05' AS DATETIME)"),
        # db_extra with no "version" key → falls back to CAST.
        ("DateTime", {"other": "value"}, "CAST('2019-01-02T03:04:05' AS DATETIME)"),
        # version exactly 7.7 → still uses CAST (below threshold).
        ("DateTime", {"version": "7.7"}, "CAST('2019-01-02T03:04:05' AS DATETIME)"),
        # version exactly 7.8 → uses DATETIME_PARSE.
        (
            "DateTime",
            {"version": "7.8"},
            "DATETIME_PARSE('2019-01-02 03:04:05', 'yyyy-MM-dd HH:mm:ss')",
        ),
        # version 7.8.0 (exact match) → uses DATETIME_PARSE.
        (
            "DateTime",
            {"version": "7.8.0"},
            "DATETIME_PARSE('2019-01-02 03:04:05', 'yyyy-MM-dd HH:mm:ss')",
        ),
        # version above 7.8 → uses DATETIME_PARSE.
        (
            "DateTime",
            {"version": "8.10.2"},
            "DATETIME_PARSE('2019-01-02 03:04:05', 'yyyy-MM-dd HH:mm:ss')",
        ),
        # Unparseable version → swallowed exception, falls back to CAST.
        (
            "DateTime",
            {"version": "unparseable semver version"},
            "CAST('2019-01-02T03:04:05' AS DATETIME)",
        ),
        # Empty string version is falsy → CAST path.
        (
            "DateTime",
            {"version": ""},
            "CAST('2019-01-02T03:04:05' AS DATETIME)",
        ),
        # Non-DateTime sqla type → returns None.
        ("Unknown", None, None),
        ("Unknown", {"version": "7.8"}, None),
    ],
)
def test_elasticsearch_convert_dttm(
    target_type: str,
    db_extra: Optional[dict[str, Any]],
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    assert_convert_dttm(
        ElasticSearchEngineSpec, target_type, expected_result, dttm, db_extra
    )


def test_elasticsearch_convert_dttm_strips_microseconds(
    dttm: datetime,  # noqa: F811
) -> None:
    """convert_dttm should serialize datetimes with seconds precision only."""
    result = ElasticSearchEngineSpec.convert_dttm(
        target_type="DateTime", dttm=dttm, db_extra={"version": "7.8"}
    )
    assert result is not None
    assert ".678900" not in result
    assert "2019-01-02 03:04:05" in result


def test_elasticsearch_convert_dttm_with_timezone() -> None:
    """convert_dttm should handle timezone-aware datetimes."""
    tz_dttm = datetime(2019, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    result = ElasticSearchEngineSpec.convert_dttm(
        target_type="DateTime", dttm=tz_dttm, db_extra={"version": "7.8"}
    )
    assert (
        result == "DATETIME_PARSE('2019-01-02 03:04:05+00:00', 'yyyy-MM-dd HH:mm:ss')"
    )


def test_elasticsearch_convert_dttm_logs_on_version_error(
    dttm: datetime,  # noqa: F811
) -> None:
    """Unparseable versions are caught and logged — function still returns CAST."""
    with patch("superset.db_engine_specs.elasticsearch.logger") as mock_logger:
        result = ElasticSearchEngineSpec.convert_dttm(
            target_type="DateTime",
            dttm=dttm,
            db_extra={"version": "not-a-version"},
        )
    assert result == "CAST('2019-01-02T03:04:05' AS DATETIME)"
    assert mock_logger.error.called
    assert mock_logger.exception.called


# ---------------------------------------------------------------------------
# ElasticSearchEngineSpec.get_dbapi_exception_mapping
# ---------------------------------------------------------------------------
def _build_fake_es_modules() -> tuple[
    py_types.ModuleType,
    py_types.ModuleType,
    type[Exception],
    type[Exception],
    type[Exception],
]:
    """Build stand-in modules mimicking the ``es.exceptions`` module structure.

    The ``elasticsearch-dbapi`` driver is not part of the test environment, so
    we register lightweight ``ModuleType`` instances under the ``es`` and
    ``es.exceptions`` names and attach exception classes to them.
    """
    fake_es = py_types.ModuleType("es")
    fake_exceptions = py_types.ModuleType("es.exceptions")

    class FakeDatabaseError(Exception):
        pass

    class FakeOperationalError(Exception):
        pass

    class FakeProgrammingError(Exception):
        pass

    fake_exceptions.DatabaseError = FakeDatabaseError  # type: ignore[attr-defined]
    fake_exceptions.OperationalError = (  # type: ignore[attr-defined]
        FakeOperationalError
    )
    fake_exceptions.ProgrammingError = (  # type: ignore[attr-defined]
        FakeProgrammingError
    )
    fake_es.exceptions = fake_exceptions  # type: ignore[attr-defined]

    return (
        fake_es,
        fake_exceptions,
        FakeDatabaseError,
        FakeOperationalError,
        FakeProgrammingError,
    )


def test_elasticsearch_get_dbapi_exception_mapping() -> None:
    """Verify the dbapi exception mapping uses the elasticsearch-dbapi exceptions."""
    fake_es, fake_exceptions, db_err, op_err, prog_err = _build_fake_es_modules()

    with patch.dict(sys.modules, {"es": fake_es, "es.exceptions": fake_exceptions}):
        mapping = ElasticSearchEngineSpec.get_dbapi_exception_mapping()

    assert mapping == {
        db_err: SupersetDBAPIDatabaseError,
        op_err: SupersetDBAPIOperationalError,
        prog_err: SupersetDBAPIProgrammingError,
    }


def test_elasticsearch_get_dbapi_exception_mapping_returns_dict() -> None:
    """The mapping result is always a dict with three entries."""
    fake_es, fake_exceptions, *_ = _build_fake_es_modules()

    with patch.dict(sys.modules, {"es": fake_es, "es.exceptions": fake_exceptions}):
        mapping = ElasticSearchEngineSpec.get_dbapi_exception_mapping()

    assert isinstance(mapping, dict)
    assert len(mapping) == 3
    assert all(issubclass(target, Exception) for target in mapping.values())


# ---------------------------------------------------------------------------
# OpenDistroEngineSpec
# ---------------------------------------------------------------------------
def test_opendistro_engine_attributes() -> None:
    assert OpenDistroEngineSpec.engine == "odelasticsearch"
    assert OpenDistroEngineSpec.engine_name == "OpenSearch (OpenDistro)"
    assert OpenDistroEngineSpec.time_groupby_inline is True
    assert OpenDistroEngineSpec.allows_joins is False
    assert OpenDistroEngineSpec.allows_subqueries is True
    assert OpenDistroEngineSpec.allows_sql_comments is False


def test_opendistro_time_grain_expressions_keys() -> None:
    expected_keys = {
        None,
        TimeGrain.SECOND,
        TimeGrain.MINUTE,
        TimeGrain.HOUR,
        TimeGrain.DAY,
        TimeGrain.MONTH,
        TimeGrain.YEAR,
    }
    assert set(OpenDistroEngineSpec._time_grain_expressions.keys()) == expected_keys


def test_opendistro_time_grain_expressions_values() -> None:
    expressions = OpenDistroEngineSpec._time_grain_expressions
    assert expressions[None] == "{col}"
    assert expressions[TimeGrain.SECOND] == (
        "date_format({col}, 'yyyy-MM-dd HH:mm:ss.000')"
    )
    assert expressions[TimeGrain.MINUTE] == (
        "date_format({col}, 'yyyy-MM-dd HH:mm:00.000')"
    )
    assert expressions[TimeGrain.HOUR] == (
        "date_format({col}, 'yyyy-MM-dd HH:00:00.000')"
    )
    assert expressions[TimeGrain.DAY] == (
        "date_format({col}, 'yyyy-MM-dd 00:00:00.000')"
    )
    assert expressions[TimeGrain.MONTH] == (
        "date_format({col}, 'yyyy-MM-01 00:00:00.000')"
    )
    assert expressions[TimeGrain.YEAR] == (
        "date_format({col}, 'yyyy-01-01 00:00:00.000')"
    )


@pytest.mark.parametrize(
    "time_grain,expected_result",
    [
        ("PT1S", "date_format(col, 'yyyy-MM-dd HH:mm:ss.000')"),
        ("PT1M", "date_format(col, 'yyyy-MM-dd HH:mm:00.000')"),
        ("PT1H", "date_format(col, 'yyyy-MM-dd HH:00:00.000')"),
        ("P1D", "date_format(col, 'yyyy-MM-dd 00:00:00.000')"),
        ("P1M", "date_format(col, 'yyyy-MM-01 00:00:00.000')"),
        ("P1Y", "date_format(col, 'yyyy-01-01 00:00:00.000')"),
    ],
)
def test_opendistro_get_timestamp_expr(time_grain: str, expected_result: str) -> None:
    actual = str(
        OpenDistroEngineSpec.get_timestamp_expr(
            col=column("col"), pdf=None, time_grain=time_grain
        )
    )
    assert actual == expected_result


def test_opendistro_get_timestamp_expr_no_grain() -> None:
    actual = str(
        OpenDistroEngineSpec.get_timestamp_expr(
            col=column("col"), pdf=None, time_grain=None
        )
    )
    assert actual == "col"


def test_opendistro_unsupported_time_grain() -> None:
    with pytest.raises(NotImplementedError):
        OpenDistroEngineSpec.get_timestamp_expr(
            col=column("col"), pdf=None, time_grain="P1W"
        )


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("DateTime", "'2019-01-02T03:04:05'"),
        ("DATETIME", "'2019-01-02T03:04:05'"),
        ("Unknown", None),
        ("VARCHAR", None),
    ],
)
def test_opendistro_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    assert_convert_dttm(OpenDistroEngineSpec, target_type, expected_result, dttm)


def test_opendistro_convert_dttm_with_timezone() -> None:
    """OpenDistro's convert_dttm preserves timezone offset in ISO output."""
    tz_dttm = datetime(2019, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    result = OpenDistroEngineSpec.convert_dttm(target_type="DateTime", dttm=tz_dttm)
    assert result == "'2019-01-02T03:04:05+00:00'"


def test_opendistro_convert_dttm_strips_microseconds(
    dttm: datetime,  # noqa: F811
) -> None:
    result = OpenDistroEngineSpec.convert_dttm(target_type="DateTime", dttm=dttm)
    assert result == "'2019-01-02T03:04:05'"


# ---------------------------------------------------------------------------
# OpenDistroEngineSpec._mutate_label
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "original,expected",
    [
        ("Col", "Col"),
        ("Col.keyword", "Col_keyword"),
        ("a.b.c", "a_b_c"),
        ("", ""),
        (".", "_"),
        ("no_dot_here", "no_dot_here"),
        ("multiple..dots", "multiple__dots"),
        (".leading", "_leading"),
        ("trailing.", "trailing_"),
    ],
)
def test_opendistro_mutate_label(original: str, expected: str) -> None:
    assert OpenDistroEngineSpec._mutate_label(original) == expected


@pytest.mark.parametrize(
    "original,expected",
    [
        ("Col", "Col"),
        ("Col.keyword", "Col_keyword"),
        ("a.b.c", "a_b_c"),
    ],
)
def test_opendistro_make_label_compatible(original: str, expected: str) -> None:
    """make_label_compatible delegates through _mutate_label for OpenDistro."""
    assert OpenDistroEngineSpec.make_label_compatible(original) == expected
