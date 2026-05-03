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

from datetime import datetime, timezone
from typing import Optional

import pytest

from superset.constants import TimeGrain
from superset.db_engine_specs.base import BaseEngineSpec, DatabaseCategory
from superset.db_engine_specs.postgres import PostgresBaseEngineSpec
from superset.sql.parse import LimitMethod
from tests.unit_tests.db_engine_specs.utils import assert_convert_dttm
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


# ---------------------------------------------------------------------------
# Class-level attributes
# ---------------------------------------------------------------------------
def test_hana_engine_class_attributes() -> None:
    from superset.db_engine_specs.hana import HanaEngineSpec

    assert HanaEngineSpec.engine == "hana"
    assert HanaEngineSpec.engine_name == "SAP HANA"
    assert HanaEngineSpec.limit_method == LimitMethod.WRAP_SQL
    assert HanaEngineSpec.force_column_alias_quotes is True
    assert HanaEngineSpec.max_column_name_length == 30


def test_hana_engine_inherits_from_postgres_base() -> None:
    from superset.db_engine_specs.hana import HanaEngineSpec

    assert issubclass(HanaEngineSpec, PostgresBaseEngineSpec)
    assert issubclass(HanaEngineSpec, BaseEngineSpec)


def test_hana_metadata_structure() -> None:
    from superset.db_engine_specs.hana import HanaEngineSpec

    metadata = HanaEngineSpec.metadata
    assert isinstance(metadata, dict)
    assert "description" in metadata
    assert "logo" in metadata
    assert metadata["logo"] == "sap-hana.png"
    assert metadata["default_port"] == 30015
    assert metadata["pypi_packages"] == ["hdbcli", "sqlalchemy-hana"]
    assert "hana://" in metadata["connection_string"]
    assert metadata["docs_url"].startswith("https://")
    assert metadata["homepage_url"].startswith("https://")
    assert "install_instructions" in metadata
    assert metadata["install_instructions"] == "pip install apache_superset[hana]"


def test_hana_metadata_categories() -> None:
    from superset.db_engine_specs.hana import HanaEngineSpec

    categories = HanaEngineSpec.metadata["categories"]
    assert DatabaseCategory.TRADITIONAL_RDBMS in categories
    assert DatabaseCategory.PROPRIETARY in categories


# ---------------------------------------------------------------------------
# convert_dttm
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Date", "TO_DATE('2019-01-02', 'YYYY-MM-DD')"),
        (
            "TimeStamp",
            "TO_TIMESTAMP('2019-01-02T03:04:05.678900', "
            "'YYYY-MM-DD\"T\"HH24:MI:SS.ff6')",
        ),
        (
            "TIMESTAMP",
            "TO_TIMESTAMP('2019-01-02T03:04:05.678900', "
            "'YYYY-MM-DD\"T\"HH24:MI:SS.ff6')",
        ),
        ("UnknownType", None),
        ("BIGINT", None),
        ("VARCHAR(50)", None),
    ],
)
def test_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    from superset.db_engine_specs.hana import HanaEngineSpec as spec  # noqa: N813

    assert_convert_dttm(spec, target_type, expected_result, dttm)


def test_convert_dttm_at_midnight() -> None:
    from superset.db_engine_specs.hana import HanaEngineSpec

    midnight = datetime(2024, 5, 17, 0, 0, 0, 0)
    assert (
        HanaEngineSpec.convert_dttm("Date", midnight)
        == "TO_DATE('2024-05-17', 'YYYY-MM-DD')"
    )
    assert HanaEngineSpec.convert_dttm("TimeStamp", midnight) == (
        "TO_TIMESTAMP('2024-05-17T00:00:00.000000', 'YYYY-MM-DD\"T\"HH24:MI:SS.ff6')"
    )


def test_convert_dttm_with_microseconds() -> None:
    from superset.db_engine_specs.hana import HanaEngineSpec

    value = datetime(2024, 1, 1, 12, 34, 56, 123456)
    assert HanaEngineSpec.convert_dttm("TimeStamp", value) == (
        "TO_TIMESTAMP('2024-01-01T12:34:56.123456', 'YYYY-MM-DD\"T\"HH24:MI:SS.ff6')"
    )


def test_convert_dttm_with_tz_aware_datetime() -> None:
    from superset.db_engine_specs.hana import HanaEngineSpec

    aware = datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
    # Date conversion ignores the time component but must still produce a value.
    assert (
        HanaEngineSpec.convert_dttm("Date", aware)
        == "TO_DATE('2024-06-15', 'YYYY-MM-DD')"
    )
    # The timestamp branch propagates the timezone offset via isoformat().
    timestamp_sql = HanaEngineSpec.convert_dttm("TimeStamp", aware)
    assert timestamp_sql is not None
    assert "2024-06-15T10:00:00.000000+00:00" in timestamp_sql


def test_convert_dttm_with_db_extra_passthrough(
    dttm: datetime,  # noqa: F811
) -> None:
    from superset.db_engine_specs.hana import HanaEngineSpec

    assert HanaEngineSpec.convert_dttm("Date", dttm, db_extra={"foo": "bar"}) == (
        "TO_DATE('2019-01-02', 'YYYY-MM-DD')"
    )
    assert HanaEngineSpec.convert_dttm("Date", dttm, db_extra=None) == (
        "TO_DATE('2019-01-02', 'YYYY-MM-DD')"
    )


def test_convert_dttm_unknown_type_returns_none(
    dttm: datetime,  # noqa: F811
) -> None:
    from superset.db_engine_specs.hana import HanaEngineSpec

    assert HanaEngineSpec.convert_dttm("NOT_A_TYPE", dttm) is None
    assert HanaEngineSpec.convert_dttm("", dttm) is None


# ---------------------------------------------------------------------------
# Time grain expressions
# ---------------------------------------------------------------------------
def test_time_grain_expressions_keys() -> None:
    from superset.db_engine_specs.hana import HanaEngineSpec

    expressions = HanaEngineSpec._time_grain_expressions
    expected_keys = {
        None,
        TimeGrain.SECOND,
        TimeGrain.MINUTE,
        TimeGrain.HOUR,
        TimeGrain.DAY,
        TimeGrain.MONTH,
        TimeGrain.QUARTER,
        TimeGrain.YEAR,
    }
    assert set(expressions.keys()) == expected_keys


def test_time_grain_default_is_passthrough() -> None:
    from superset.db_engine_specs.hana import HanaEngineSpec

    assert HanaEngineSpec._time_grain_expressions[None] == "{col}"


@pytest.mark.parametrize(
    "grain,expected",
    [
        (
            TimeGrain.SECOND,
            "TO_TIMESTAMP(SUBSTRING(TO_TIMESTAMP({col}),0,20))",
        ),
        (
            TimeGrain.MINUTE,
            "TO_TIMESTAMP(SUBSTRING(TO_TIMESTAMP({col}),0,17) || '00')",
        ),
        (
            TimeGrain.HOUR,
            "TO_TIMESTAMP(SUBSTRING(TO_TIMESTAMP({col}),0,14) || '00:00')",
        ),
        (TimeGrain.DAY, "TO_DATE({col})"),
        (
            TimeGrain.MONTH,
            "TO_DATE(SUBSTRING(TO_DATE({col}),0,7)||'-01')",
        ),
        (TimeGrain.YEAR, "TO_DATE(YEAR({col})||'-01-01')"),
    ],
)
def test_time_grain_expressions_values(grain: str, expected: str) -> None:
    from superset.db_engine_specs.hana import HanaEngineSpec

    assert HanaEngineSpec._time_grain_expressions[grain] == expected


def test_time_grain_quarter_expression_contains_quarter_logic() -> None:
    from superset.db_engine_specs.hana import HanaEngineSpec

    quarter_expr = HanaEngineSpec._time_grain_expressions[TimeGrain.QUARTER]
    # Quarter expression derives the first month of each quarter using
    # ((quarter_index - 1) * 3 + 1) and pads it to two digits.
    assert "QUARTER(" in quarter_expr
    assert "LPAD" in quarter_expr
    assert "{col}" in quarter_expr
    assert "-01" in quarter_expr


def test_time_grain_expressions_contain_col_placeholder() -> None:
    from superset.db_engine_specs.hana import HanaEngineSpec

    for grain, expression in HanaEngineSpec._time_grain_expressions.items():
        assert "{col}" in expression, f"{grain} expression missing {{col}}"


# ---------------------------------------------------------------------------
# Inherited PostgresBaseEngineSpec behavior
# ---------------------------------------------------------------------------
def test_hana_epoch_to_dttm_inherited() -> None:
    from superset.db_engine_specs.hana import HanaEngineSpec

    assert (
        HanaEngineSpec.epoch_to_dttm()
        == "(timestamp 'epoch' + {col} * interval '1 second')"
    )


def test_hana_epoch_ms_to_dttm_uses_epoch() -> None:
    from superset.db_engine_specs.hana import HanaEngineSpec

    expression = HanaEngineSpec.epoch_ms_to_dttm()
    assert "{col}" in expression
    assert "1000" in expression


def test_hana_get_time_grain_expressions_returns_full_mapping() -> None:
    from superset.db_engine_specs.hana import HanaEngineSpec

    grains = HanaEngineSpec.get_time_grain_expressions()
    assert TimeGrain.DAY in grains
    assert grains[TimeGrain.DAY] == "TO_DATE({col})"
