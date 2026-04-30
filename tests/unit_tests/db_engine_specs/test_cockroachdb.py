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

from superset.db_engine_specs.cockroachdb import (
    CockroachDbEngineSpec as spec,  # noqa: N813
)
from tests.unit_tests.db_engine_specs.utils import assert_convert_dttm
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Date", "'2019-01-02'"),
        ("DateTime", "'2019-01-02 03:04:05'"),
        ("TimeStamp", "'2019-01-02 03:04:05'"),
        ("VARCHAR", "'2019-01-02 03:04:05'"),
        ("TEXT", "'2019-01-02 03:04:05'"),
        ("CHAR", "'2019-01-02 03:04:05'"),
        ("UnknownType", None),
    ],
)
def test_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    assert_convert_dttm(spec, target_type, expected_result, dttm)


def test_convert_dttm_date_iso_format(dttm: datetime) -> None:  # noqa: F811
    result = spec.convert_dttm("Date", dttm)
    assert result == "'2019-01-02'"


def test_convert_dttm_datetime_iso_format(dttm: datetime) -> None:  # noqa: F811
    result = spec.convert_dttm("DateTime", dttm)
    assert result == "'2019-01-02 03:04:05'"


def test_convert_dttm_string_type(dttm: datetime) -> None:  # noqa: F811
    result = spec.convert_dttm("VARCHAR", dttm)
    assert result == "'2019-01-02 03:04:05'"


def test_convert_dttm_unknown_type_returns_none(dttm: datetime) -> None:  # noqa: F811
    result = spec.convert_dttm("UnknownType", dttm)
    assert result is None


def test_convert_dttm_with_db_extra(dttm: datetime) -> None:  # noqa: F811
    result = spec.convert_dttm("Date", dttm, db_extra={"foo": "bar"})
    assert result == "'2019-01-02'"


def test_convert_dttm_with_none_db_extra(dttm: datetime) -> None:  # noqa: F811
    result = spec.convert_dttm("DateTime", dttm, db_extra=None)
    assert result == "'2019-01-02 03:04:05'"


def test_convert_dttm_midnight() -> None:
    dt = datetime(2023, 6, 15, 0, 0, 0)
    result = spec.convert_dttm("DateTime", dt)
    assert result == "'2023-06-15 00:00:00'"


def test_convert_dttm_end_of_day() -> None:
    dt = datetime(2023, 12, 31, 23, 59, 59)
    result = spec.convert_dttm("DateTime", dt)
    assert result == "'2023-12-31 23:59:59'"


def test_convert_dttm_date_leap_year() -> None:
    dt = datetime(2024, 2, 29, 12, 0, 0)
    result = spec.convert_dttm("Date", dt)
    assert result == "'2024-02-29'"


def test_convert_dttm_epoch() -> None:
    dt = datetime(1970, 1, 1, 0, 0, 0)
    result = spec.convert_dttm("DateTime", dt)
    assert result == "'1970-01-01 00:00:00'"


def test_convert_dttm_boolean_returns_none(dttm: datetime) -> None:  # noqa: F811
    result = spec.convert_dttm("BOOLEAN", dttm)
    assert result is None


def test_convert_dttm_integer_returns_none(dttm: datetime) -> None:  # noqa: F811
    result = spec.convert_dttm("INTEGER", dttm)
    assert result is None


def test_engine_name() -> None:
    assert spec.engine == "cockroachdb"
    assert spec.engine_name == "CockroachDB"


def test_metadata() -> None:
    assert spec.metadata is not None
    assert spec.metadata["default_port"] == 26257
    assert "cockroachdb" in spec.metadata["pypi_packages"]
    assert spec.metadata["logo"] == "cockroachdb.png"
    assert "cockroachdb://" in spec.metadata["connection_string"]
    assert spec.metadata["homepage_url"] == "https://www.cockroachlabs.com/"
    assert (
        spec.metadata["docs_url"]
        == "https://github.com/cockroachdb/sqlalchemy-cockroachdb"
    )


def test_metadata_categories() -> None:
    from superset.db_engine_specs.base import DatabaseCategory

    categories = spec.metadata["categories"]
    assert DatabaseCategory.TRADITIONAL_RDBMS in categories
    assert DatabaseCategory.OPEN_SOURCE in categories


def test_inherits_postgres_time_grains() -> None:
    from superset.db_engine_specs.postgres import PostgresEngineSpec

    assert spec._time_grain_expressions == PostgresEngineSpec._time_grain_expressions


def test_inherits_postgres_column_type_mappings() -> None:
    from superset.db_engine_specs.postgres import PostgresEngineSpec

    assert spec.column_type_mappings == PostgresEngineSpec.column_type_mappings
