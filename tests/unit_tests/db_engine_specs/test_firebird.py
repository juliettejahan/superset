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

from superset.constants import TimeGrain
from superset.db_engine_specs.base import DatabaseCategory
from superset.db_engine_specs.firebird import FirebirdEngineSpec
from superset.sql.parse import LimitMethod
from tests.unit_tests.db_engine_specs.utils import assert_convert_dttm
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


def test_engine_attributes() -> None:
    assert FirebirdEngineSpec.engine == "firebird"
    assert FirebirdEngineSpec.engine_name == "Firebird"


def test_limit_method() -> None:
    """Firebird uses FETCH_MANY because it limits via ``SELECT FIRST N``."""
    assert FirebirdEngineSpec.limit_method == LimitMethod.FETCH_MANY


def test_metadata_basic_fields() -> None:
    meta = FirebirdEngineSpec.metadata
    assert meta["description"] == "Firebird is an open-source relational database."
    assert meta["logo"] == "firebird.png"
    assert meta["homepage_url"] == "https://firebirdsql.org/"
    assert meta["default_port"] == 3050
    assert meta["pypi_packages"] == ["sqlalchemy-firebird"]
    assert meta["version_requirements"] == "sqlalchemy-firebird>=0.7.0,<0.8"


def test_metadata_categories() -> None:
    categories = FirebirdEngineSpec.metadata["categories"]
    assert DatabaseCategory.TRADITIONAL_RDBMS in categories
    assert DatabaseCategory.OPEN_SOURCE in categories


def test_metadata_connection_string_template() -> None:
    template = FirebirdEngineSpec.metadata["connection_string"]
    assert template.startswith("firebird+fdb://")
    for token in ("{username}", "{password}", "{host}", "{port}", "{path_to_db_file}"):
        assert token in template


def test_metadata_connection_examples() -> None:
    examples = FirebirdEngineSpec.metadata["connection_examples"]
    assert isinstance(examples, list)
    assert len(examples) >= 1
    example = examples[0]
    assert "description" in example
    assert example["connection_string"].startswith("firebird+fdb://")


@pytest.mark.parametrize(
    "time_grain,expected",
    [
        (None, "timestamp_column"),
        (
            TimeGrain.SECOND,
            (
                "CAST(CAST(timestamp_column AS DATE) "
                "|| ' ' "
                "|| EXTRACT(HOUR FROM timestamp_column) "
                "|| ':' "
                "|| EXTRACT(MINUTE FROM timestamp_column) "
                "|| ':' "
                "|| FLOOR(EXTRACT(SECOND FROM timestamp_column)) AS TIMESTAMP)"
            ),
        ),
        (
            TimeGrain.MINUTE,
            (
                "CAST(CAST(timestamp_column AS DATE) "
                "|| ' ' "
                "|| EXTRACT(HOUR FROM timestamp_column) "
                "|| ':' "
                "|| EXTRACT(MINUTE FROM timestamp_column) "
                "|| ':00' AS TIMESTAMP)"
            ),
        ),
        (
            TimeGrain.HOUR,
            (
                "CAST(CAST(timestamp_column AS DATE) "
                "|| ' ' "
                "|| EXTRACT(HOUR FROM timestamp_column) "
                "|| ':00:00' AS TIMESTAMP)"
            ),
        ),
        (TimeGrain.DAY, "CAST(timestamp_column AS DATE)"),
        (
            TimeGrain.MONTH,
            (
                "CAST(EXTRACT(YEAR FROM timestamp_column) "
                "|| '-' "
                "|| EXTRACT(MONTH FROM timestamp_column) "
                "|| '-01' AS DATE)"
            ),
        ),
        (
            TimeGrain.YEAR,
            "CAST(EXTRACT(YEAR FROM timestamp_column) || '-01-01' AS DATE)",
        ),
    ],
)
def test_time_grain_expressions(time_grain: Optional[str], expected: str) -> None:
    template = FirebirdEngineSpec._time_grain_expressions[time_grain]
    assert template.format(col="timestamp_column") == expected


def test_time_grain_expressions_completeness() -> None:
    """Firebird supports a fixed set of grains; ensure none are missing or extra."""
    expected_grains = {
        None,
        TimeGrain.SECOND,
        TimeGrain.MINUTE,
        TimeGrain.HOUR,
        TimeGrain.DAY,
        TimeGrain.MONTH,
        TimeGrain.YEAR,
    }
    assert set(FirebirdEngineSpec._time_grain_expressions.keys()) == expected_grains


def test_time_grain_expressions_no_week_or_quarter() -> None:
    """Firebird does not expose WEEK / QUARTER grains."""
    assert TimeGrain.WEEK not in FirebirdEngineSpec._time_grain_expressions
    assert TimeGrain.QUARTER not in FirebirdEngineSpec._time_grain_expressions


def test_epoch_to_dttm() -> None:
    template = FirebirdEngineSpec.epoch_to_dttm()
    assert template == "DATEADD(second, {col}, CAST('00:00:00' AS TIMESTAMP))"
    assert (
        template.format(col="timestamp_column")
        == "DATEADD(second, timestamp_column, CAST('00:00:00' AS TIMESTAMP))"
    )


def test_epoch_to_dttm_with_numeric_literal() -> None:
    """``epoch_to_dttm`` should produce a valid expression when col is a literal."""
    formatted = FirebirdEngineSpec.epoch_to_dttm().format(col="0")
    assert formatted == "DATEADD(second, 0, CAST('00:00:00' AS TIMESTAMP))"


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Date", "CAST('2019-01-02' AS DATE)"),
        ("DateTime", "CAST('2019-01-02 03:04:05.6789' AS TIMESTAMP)"),
        ("TimeStamp", "CAST('2019-01-02 03:04:05.6789' AS TIMESTAMP)"),
        ("Time", "CAST('03:04:05.678900' AS TIME)"),
        ("UnknownType", None),
    ],
)
def test_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    assert_convert_dttm(FirebirdEngineSpec, target_type, expected_result, dttm)


def test_convert_dttm_unknown_returns_none(dttm: datetime) -> None:  # noqa: F811
    """Unsupported target types produce ``None`` rather than raising."""
    assert FirebirdEngineSpec.convert_dttm(target_type="VARCHAR", dttm=dttm) is None
    assert FirebirdEngineSpec.convert_dttm(target_type="INTEGER", dttm=dttm) is None
    assert FirebirdEngineSpec.convert_dttm(target_type="", dttm=dttm) is None


def test_convert_dttm_with_db_extra(dttm: datetime) -> None:  # noqa: F811
    """``db_extra`` is accepted but ignored by Firebird's ``convert_dttm``."""
    result = FirebirdEngineSpec.convert_dttm(
        target_type="DateTime",
        dttm=dttm,
        db_extra={"some": "value"},
    )
    assert result == "CAST('2019-01-02 03:04:05.6789' AS TIMESTAMP)"


def test_convert_dttm_with_none_db_extra(dttm: datetime) -> None:  # noqa: F811
    result = FirebirdEngineSpec.convert_dttm(
        target_type="Date",
        dttm=dttm,
        db_extra=None,
    )
    assert result == "CAST('2019-01-02' AS DATE)"


def test_convert_dttm_epoch_datetime() -> None:
    """Conversion at the Unix epoch boundary produces well-formed output."""
    epoch = datetime(1970, 1, 1, 0, 0, 0)
    assert (
        FirebirdEngineSpec.convert_dttm("DateTime", epoch)
        == "CAST('1970-01-01 00:00:00' AS TIMESTAMP)"
    )
    assert (
        FirebirdEngineSpec.convert_dttm("Date", epoch) == "CAST('1970-01-01' AS DATE)"
    )
    assert FirebirdEngineSpec.convert_dttm("Time", epoch) == "CAST('00:00:00' AS TIME)"


def test_convert_dttm_no_microseconds() -> None:
    """A ``datetime`` with no microseconds should still produce a valid TIMESTAMP."""
    no_micros = datetime(2024, 6, 15, 12, 30, 45)
    assert (
        FirebirdEngineSpec.convert_dttm("DateTime", no_micros)
        == "CAST('2024-06-15 12:30:45' AS TIMESTAMP)"
    )
    assert (
        FirebirdEngineSpec.convert_dttm("Time", no_micros) == "CAST('12:30:45' AS TIME)"
    )


def test_convert_dttm_truncates_microseconds_to_4_digits() -> None:
    """Firebird's TIMESTAMP precision is 4 fractional digits.

    The format is ``YYYY-MM-DD HH:MM:SS.MMMM``; inputs with full 6-digit
    microseconds must be truncated rather than rounded.
    """
    full_micros = datetime(2019, 1, 2, 3, 4, 5, 678999)
    assert (
        FirebirdEngineSpec.convert_dttm("DateTime", full_micros)
        == "CAST('2019-01-02 03:04:05.6789' AS TIMESTAMP)"
    )


def test_convert_dttm_low_microseconds_padded() -> None:
    """Single-digit microseconds are padded to six digits before truncation."""
    low_micros = datetime(2019, 1, 2, 3, 4, 5, 1)
    # ``isoformat`` yields ``2019-01-02 03:04:05.000001``; the first 24 chars are
    # ``2019-01-02 03:04:05.0000``.
    assert (
        FirebirdEngineSpec.convert_dttm("DateTime", low_micros)
        == "CAST('2019-01-02 03:04:05.0000' AS TIMESTAMP)"
    )


def test_convert_dttm_timezone_aware() -> None:
    """Timezone-aware datetimes are accepted; the offset is dropped on TIMESTAMP."""
    tz_aware = datetime(2019, 1, 2, 3, 4, 5, 678900, tzinfo=timezone.utc)
    # ``isoformat(sep=" ")`` -> ``2019-01-02 03:04:05.678900+00:00``;
    # truncation to 24 chars keeps just the millisecond portion.
    assert (
        FirebirdEngineSpec.convert_dttm("DateTime", tz_aware)
        == "CAST('2019-01-02 03:04:05.6789' AS TIMESTAMP)"
    )
    # ``date()`` ignores tz, so DATE conversion is unaffected.
    assert (
        FirebirdEngineSpec.convert_dttm("Date", tz_aware)
        == "CAST('2019-01-02' AS DATE)"
    )


def test_convert_dttm_time_includes_microseconds(dttm: datetime) -> None:  # noqa: F811
    """``Time`` conversion uses the full ``time().isoformat()`` (no truncation)."""
    assert (
        FirebirdEngineSpec.convert_dttm("Time", dttm)
        == "CAST('03:04:05.678900' AS TIME)"
    )
