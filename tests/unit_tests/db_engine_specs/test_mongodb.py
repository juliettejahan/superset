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

from datetime import datetime, timezone
from typing import Optional

import pytest
from sqlalchemy import column

from superset.constants import TimeGrain
from superset.db_engine_specs.base import DatabaseCategory
from superset.db_engine_specs.mongodb import MongoDBEngineSpec as spec  # noqa: N813
from tests.unit_tests.db_engine_specs.utils import assert_convert_dttm
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


def test_engine_attributes() -> None:
    """MongoDB engine spec exposes the expected class attributes."""
    assert spec.engine == "mongodb"
    assert spec.engine_name == "MongoDB"
    assert spec.force_column_alias_quotes is False


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        # String / TEXT-like targets render as quoted ISO datetime
        ("text", "'2019-01-02 03:04:05'"),
        ("TEXT", "'2019-01-02 03:04:05'"),
        ("Text", "'2019-01-02 03:04:05'"),
        ("string", "'2019-01-02 03:04:05'"),
        ("String", "'2019-01-02 03:04:05'"),
        ("STRING", "'2019-01-02 03:04:05'"),
        ("varchar", "'2019-01-02 03:04:05'"),
        ("VARCHAR", "'2019-01-02 03:04:05'"),
        ("char", "'2019-01-02 03:04:05'"),
        # DateTime / TIMESTAMP / Date all map to a datetime literal
        ("datetime", "'2019-01-02 03:04:05'"),
        ("DateTime", "'2019-01-02 03:04:05'"),
        ("DATETIME", "'2019-01-02 03:04:05'"),
        ("timestamp", "'2019-01-02 03:04:05'"),
        ("TIMESTAMP", "'2019-01-02 03:04:05'"),
        ("TimeStamp", "'2019-01-02 03:04:05'"),
        ("date", "'2019-01-02 03:04:05'"),
        ("Date", "'2019-01-02 03:04:05'"),
        ("DATE", "'2019-01-02 03:04:05'"),
        # Non-temporal / non-string targets are not converted
        ("integer", None),
        ("INTEGER", None),
        ("number", None),
        ("Numeric", None),
        ("float", None),
        ("boolean", None),
        ("Boolean", None),
        ("BOOLEAN", None),
        ("UnknownType", None),
        ("unknowntype", None),
    ],
)
def test_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    """``convert_dttm`` returns ISO-formatted strings for textual/temporal types."""
    assert_convert_dttm(spec, target_type, expected_result, dttm)


def test_convert_dttm_drops_microseconds() -> None:
    """Sub-second precision is truncated by ``timespec='seconds'``."""
    value = datetime(2024, 7, 15, 12, 34, 56, 789123)
    assert spec.convert_dttm("DateTime", value) == "'2024-07-15 12:34:56'"


def test_convert_dttm_with_timezone_aware_datetime() -> None:
    """Timezone-aware datetimes preserve their offset in the ISO output."""
    value = datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    result = spec.convert_dttm("DateTime", value)
    assert result == "'2024-01-02 03:04:05+00:00'"


@pytest.mark.parametrize(
    "value,expected",
    [
        # Lower boundary
        (datetime(1, 1, 1, 0, 0, 0), "'0001-01-01 00:00:00'"),
        # Epoch
        (datetime(1970, 1, 1, 0, 0, 0), "'1970-01-01 00:00:00'"),
        # 32-bit time_t boundary
        (datetime(2038, 1, 19, 3, 14, 7), "'2038-01-19 03:14:07'"),
        # Far future
        (datetime(9999, 12, 31, 23, 59, 59), "'9999-12-31 23:59:59'"),
    ],
)
def test_convert_dttm_boundary_values(value: datetime, expected: str) -> None:
    """``convert_dttm`` handles datetime boundary values without errors."""
    assert spec.convert_dttm("DateTime", value) == expected


def test_convert_dttm_with_db_extra_is_ignored(
    dttm: datetime,  # noqa: F811
) -> None:
    """Passing ``db_extra`` does not alter the output for MongoDB."""
    no_extra = spec.convert_dttm("DateTime", dttm)
    with_extra = spec.convert_dttm("DateTime", dttm, db_extra={"version": "5.0"})
    assert no_extra == with_extra == "'2019-01-02 03:04:05'"


def test_convert_dttm_with_none_db_extra(
    dttm: datetime,  # noqa: F811
) -> None:
    """Explicit ``None`` for ``db_extra`` is accepted."""
    assert spec.convert_dttm("DateTime", dttm, db_extra=None) == "'2019-01-02 03:04:05'"


def test_convert_dttm_empty_target_type_returns_none(
    dttm: datetime,  # noqa: F811
) -> None:
    """Unknown / empty target types fall through to ``None``."""
    assert spec.convert_dttm("", dttm) is None


def test_epoch_to_dttm() -> None:
    """``epoch_to_dttm`` returns the SQLite-compatible expression."""
    assert spec.epoch_to_dttm() == "datetime({col}, 'unixepoch')"


def test_epoch_ms_to_dttm_uses_default() -> None:
    """``epoch_ms_to_dttm`` derives from ``epoch_to_dttm`` divided by 1000."""
    expr = spec.epoch_ms_to_dttm()
    assert "{col}/1000" in expr or "/1000" in expr


def test_get_dbapi_exception_mapping() -> None:
    """MongoDB does not override ``get_dbapi_exception_mapping``."""
    assert spec.get_dbapi_exception_mapping() == {}


@pytest.mark.parametrize(
    "grain,expected_expression",
    [
        (None, "{col}"),
        (TimeGrain.SECOND, "DATETIME(STRFTIME('%Y-%m-%dT%H:%M:%S', {col}))"),
        (TimeGrain.MINUTE, "DATETIME(STRFTIME('%Y-%m-%dT%H:%M:00', {col}))"),
        (TimeGrain.HOUR, "DATETIME(STRFTIME('%Y-%m-%dT%H:00:00', {col}))"),
        (TimeGrain.DAY, "DATETIME({col}, 'start of day')"),
        (
            TimeGrain.WEEK,
            "DATETIME({col}, 'start of day', -strftime('%w', {col}) || ' days')",
        ),
        (TimeGrain.MONTH, "DATETIME({col}, 'start of month')"),
        (
            TimeGrain.QUARTER,
            "DATETIME({col}, 'start of month', "
            "printf('-%d month', (strftime('%m', {col}) - 1) % 3))",
        ),
        (TimeGrain.YEAR, "DATETIME({col}, 'start of year')"),
        (
            TimeGrain.WEEK_ENDING_SATURDAY,
            "DATETIME({col}, 'start of day', 'weekday 6')",
        ),
        (
            TimeGrain.WEEK_ENDING_SUNDAY,
            "DATETIME({col}, 'start of day', 'weekday 0')",
        ),
        (
            TimeGrain.WEEK_STARTING_SUNDAY,
            "DATETIME({col}, 'start of day', 'weekday 0', '-7 days')",
        ),
        (
            TimeGrain.WEEK_STARTING_MONDAY,
            "DATETIME({col}, 'start of day', 'weekday 1', '-7 days')",
        ),
    ],
)
def test_time_grain_expressions(
    grain: Optional[str],
    expected_expression: str,
) -> None:
    """Each MongoDB time grain maps to its expected SQLite-style expression."""
    # pylint: disable=protected-access
    assert spec._time_grain_expressions.get(grain) == expected_expression


def test_time_grain_expressions_keys() -> None:
    """The full set of supported MongoDB time grains is unchanged."""
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
        TimeGrain.WEEK_ENDING_SATURDAY,
        TimeGrain.WEEK_ENDING_SUNDAY,
        TimeGrain.WEEK_STARTING_SUNDAY,
        TimeGrain.WEEK_STARTING_MONDAY,
    }
    # pylint: disable=protected-access
    assert set(spec._time_grain_expressions.keys()) == expected_keys


@pytest.mark.parametrize(
    "time_grain,expected_substring",
    [
        (TimeGrain.SECOND, "STRFTIME('%Y-%m-%dT%H:%M:%S'"),
        (TimeGrain.MINUTE, "STRFTIME('%Y-%m-%dT%H:%M:00'"),
        (TimeGrain.HOUR, "STRFTIME('%Y-%m-%dT%H:00:00'"),
        (TimeGrain.DAY, "start of day"),
        (TimeGrain.MONTH, "start of month"),
        (TimeGrain.YEAR, "start of year"),
    ],
)
def test_get_timestamp_expr(time_grain: str, expected_substring: str) -> None:
    """``get_timestamp_expr`` substitutes the column name into the grain template."""
    expr = str(
        spec.get_timestamp_expr(col=column("ts"), pdf=None, time_grain=time_grain)
    )
    assert expected_substring in expr
    assert "ts" in expr


def test_get_timestamp_expr_no_grain() -> None:
    """A ``None`` time grain yields the bare column expression."""
    expr = str(spec.get_timestamp_expr(col=column("ts"), pdf=None, time_grain=None))
    assert expr == "ts"


def test_metadata_structure() -> None:
    """The metadata dictionary exposes all keys required by the UI."""
    metadata = spec.metadata
    assert "description" in metadata
    assert "logo" in metadata
    assert "homepage_url" in metadata
    assert "categories" in metadata
    assert "pypi_packages" in metadata
    assert "connection_string" in metadata
    assert "parameters" in metadata
    assert "drivers" in metadata
    assert "notes" in metadata
    assert "docs_url" in metadata


def test_metadata_categories() -> None:
    """MongoDB is categorized under Search & NoSQL and Proprietary."""
    categories = spec.metadata["categories"]
    assert DatabaseCategory.SEARCH_NOSQL in categories
    assert DatabaseCategory.PROPRIETARY in categories


def test_metadata_pypi_packages() -> None:
    """The PyMongoSQL package powers the SQLAlchemy dialect."""
    assert "pymongosql" in spec.metadata["pypi_packages"]


def test_metadata_connection_string() -> None:
    """The default connection string contains required MongoDB tokens."""
    conn = spec.metadata["connection_string"]
    assert conn.startswith("mongodb://")
    assert "mode=superset" in conn
    for token in ("{username}", "{password}", "{host}", "{port}", "{database}"):
        assert token in conn


def test_metadata_parameters() -> None:
    """All connection parameters are documented for the UI."""
    params = spec.metadata["parameters"]
    assert set(params.keys()) == {
        "username",
        "password",
        "host",
        "port",
        "database",
    }


def test_metadata_drivers_recommended_atlas() -> None:
    """The Atlas driver is the recommended option."""
    drivers = spec.metadata["drivers"]
    assert len(drivers) == 2

    atlas = drivers[0]
    assert atlas["name"] == "MongoDB Atlas Cloud"
    assert atlas["pypi_package"] == "pymongosql"
    assert atlas["is_recommended"] is True
    assert atlas["connection_string"].startswith("mongodb+srv://")
    assert "mode=superset" in atlas["connection_string"]


def test_metadata_drivers_self_hosted_cluster() -> None:
    """The cluster driver targets self-hosted MongoDB instances."""
    cluster = spec.metadata["drivers"][1]
    assert cluster["name"] == "MongoDB Cluster"
    assert cluster["pypi_package"] == "pymongosql"
    assert cluster["is_recommended"] is False
    assert cluster["connection_string"].startswith("mongodb://")


def test_metadata_notes_mention_partiql() -> None:
    """The notes call out the PartiQL/``mode=superset`` requirement."""
    notes = spec.metadata["notes"]
    assert "PartiQL" in notes
    assert "mode=superset" in notes


def test_metadata_docs_url_points_to_pymongosql() -> None:
    """The docs URL references the PyMongoSQL project."""
    assert "PyMongoSQL" in spec.metadata["docs_url"]
