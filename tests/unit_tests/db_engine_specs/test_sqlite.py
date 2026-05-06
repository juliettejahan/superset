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
# pylint: disable=invalid-name, unused-argument, import-outside-toplevel, redefined-outer-name
from datetime import datetime, timezone
from typing import Optional

import pytest
from pytest_mock import MockerFixture
from sqlalchemy.engine import create_engine

from superset.constants import TimeGrain
from superset.db_engine_specs.base import DatabaseCategory
from superset.db_engine_specs.sqlite import (
    COLUMN_DOES_NOT_EXIST_REGEX,
    SqliteEngineSpec as spec,  # noqa: N813
)
from superset.errors import ErrorLevel, SupersetErrorType
from tests.unit_tests.db_engine_specs.utils import assert_convert_dttm
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


def test_engine_attributes() -> None:
    assert spec.engine == "sqlite"
    assert spec.engine_name == "SQLite"
    assert spec.disable_ssh_tunneling is True
    assert spec.supports_multivalues_insert is True


def test_metadata() -> None:
    assert spec.metadata["logo"] == "sqlite.png"
    assert spec.metadata["homepage_url"] == "https://www.sqlite.org/"
    assert "self-contained" in spec.metadata["description"]
    assert DatabaseCategory.TRADITIONAL_RDBMS in spec.metadata["categories"]
    assert DatabaseCategory.OPEN_SOURCE in spec.metadata["categories"]
    assert spec.metadata["pypi_packages"] == []
    assert "sqlite:///" in spec.metadata["connection_string"]
    assert spec.metadata["notes"]


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Text", "'2019-01-02 03:04:05'"),
        ("DateTime", "'2019-01-02 03:04:05'"),
        ("TimeStamp", "'2019-01-02 03:04:05'"),
        ("VARCHAR", "'2019-01-02 03:04:05'"),
        ("CHAR", "'2019-01-02 03:04:05'"),
        ("Other", None),
        ("Date", None),
        ("Time", None),
        ("INTEGER", None),
        ("FLOAT", None),
    ],
)
def test_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    assert_convert_dttm(spec, target_type, expected_result, dttm)


def test_convert_dttm_with_db_extra(dttm: datetime) -> None:  # noqa: F811
    """``db_extra`` should be accepted but has no effect on the SQLite output."""
    assert (
        spec.convert_dttm("DateTime", dttm, db_extra={"foo": "bar"})
        == "'2019-01-02 03:04:05'"
    )
    assert spec.convert_dttm("DateTime", dttm, db_extra=None) == "'2019-01-02 03:04:05'"


def test_convert_dttm_truncates_microseconds(dttm: datetime) -> None:  # noqa: F811
    """Microseconds should be dropped because timespec is "seconds"."""
    result = spec.convert_dttm("DateTime", dttm)
    assert result is not None
    assert ".678900" not in result
    assert result == "'2019-01-02 03:04:05'"


def test_convert_dttm_with_tz_aware_datetime() -> None:
    """Timezone-aware datetimes should still serialise without raising."""
    dttm_utc = datetime(2022, 5, 4, 5, 6, 7, tzinfo=timezone.utc)
    result = spec.convert_dttm("DateTime", dttm_utc)
    assert result is not None
    assert result.startswith("'2022-05-04 05:06:07")


def test_epoch_to_dttm() -> None:
    assert spec.epoch_to_dttm() == "datetime({col}, 'unixepoch')"
    assert spec.epoch_to_dttm().format(col="ts_col") == "datetime(ts_col, 'unixepoch')"


def test_epoch_ms_to_dttm() -> None:
    """``epoch_ms_to_dttm`` is inherited but should compose with ``epoch_to_dttm``."""
    expr = spec.epoch_ms_to_dttm()
    assert "{col}" in expr
    assert "1000" in expr


def test_get_table_names_disregards_schema(mocker: MockerFixture) -> None:
    """SQLite does not have schemas, so any provided schema must be ignored."""
    inspector = mocker.MagicMock()
    inspector.get_table_names.return_value = ["users", "events", "logs"]
    database = mocker.MagicMock()

    result = spec.get_table_names(database, inspector, schema="ignored_schema")

    assert result == {"users", "events", "logs"}
    inspector.get_table_names.assert_called_once_with()


def test_get_table_names_with_none_schema(mocker: MockerFixture) -> None:
    inspector = mocker.MagicMock()
    inspector.get_table_names.return_value = []
    database = mocker.MagicMock()

    result = spec.get_table_names(database, inspector, schema=None)

    assert result == set()


def test_get_table_names_returns_set_dedup(mocker: MockerFixture) -> None:
    inspector = mocker.MagicMock()
    inspector.get_table_names.return_value = ["t1", "t1", "t2"]
    database = mocker.MagicMock()

    result = spec.get_table_names(database, inspector, schema=None)

    assert result == {"t1", "t2"}


def test_get_function_names(mocker: MockerFixture) -> None:
    database = mocker.MagicMock()
    result = spec.get_function_names(database)

    assert isinstance(result, list)
    assert all(isinstance(fn, str) for fn in result)
    assert len(result) > 100

    # A representative sample of categories of SQLite built-ins.
    expected_subset = {
        # aggregates
        "avg",
        "count",
        "max",
        "min",
        "sum",
        # math
        "abs",
        "ceil",
        "floor",
        "pi",
        "pow",
        "sqrt",
        # string
        "lower",
        "upper",
        "length",
        "substr",
        "trim",
        # date/time
        "date",
        "datetime",
        "julianday",
        "strftime",
        "unixepoch",
        # json
        "json",
        "json_extract",
        "json_object",
        # window
        "row_number",
        "rank",
        "dense_rank",
        "lag",
        "lead",
    }
    assert expected_subset.issubset(set(result))


def test_get_function_names_does_not_use_database(mocker: MockerFixture) -> None:
    """The database argument is unused; calling with a bare mock must work."""
    database = mocker.MagicMock()
    result = spec.get_function_names(database)
    assert "abs" in result
    database.assert_not_called()


def test_column_does_not_exist_regex_matches() -> None:
    match = COLUMN_DOES_NOT_EXIST_REGEX.search("no such column: foo")
    assert match is not None
    assert match.group("column_name") == "foo"


def test_column_does_not_exist_regex_no_match() -> None:
    assert COLUMN_DOES_NOT_EXIST_REGEX.search("syntax error near 'SELECT'") is None
    assert COLUMN_DOES_NOT_EXIST_REGEX.search("") is None


def test_custom_errors_contains_column_regex() -> None:
    assert COLUMN_DOES_NOT_EXIST_REGEX in spec.custom_errors
    message, error_type, extra = spec.custom_errors[COLUMN_DOES_NOT_EXIST_REGEX]
    assert "%(column_name)s" in message
    assert error_type == SupersetErrorType.COLUMN_DOES_NOT_EXIST_ERROR
    assert extra == {}


def test_extract_errors_column_does_not_exist() -> None:
    """A "no such column" error message produces a structured SupersetError."""
    msg = "no such column: missing_col"
    result = spec.extract_errors(Exception(msg))
    assert len(result) == 1
    err = result[0]
    assert err.error_type == SupersetErrorType.COLUMN_DOES_NOT_EXIST_ERROR
    assert err.level == ErrorLevel.ERROR
    assert err.message == 'We can\'t seem to resolve the column "missing_col"'
    assert err.extra is not None
    assert err.extra["engine_name"] == "SQLite"


def test_extract_errors_unknown_error_falls_back_to_generic() -> None:
    """An unrecognised error message yields a generic engine error."""
    msg = "something else went wrong"
    result = spec.extract_errors(Exception(msg))
    assert len(result) == 1
    assert result[0].error_type == SupersetErrorType.GENERIC_DB_ENGINE_ERROR
    assert result[0].level == ErrorLevel.ERROR
    assert result[0].extra is not None
    assert result[0].extra["engine_name"] == "SQLite"
    assert "something else" in result[0].message


def test_extract_errors_column_with_special_chars() -> None:
    """Column names with dots/quotes still get captured by the regex group."""
    msg = 'no such column: "tbl.col"'
    result = spec.extract_errors(Exception(msg))
    assert result[0].error_type == SupersetErrorType.COLUMN_DOES_NOT_EXIST_ERROR
    assert '"tbl.col"' in result[0].message


def test_time_grain_expressions_keys_cover_quarter_aliases() -> None:
    """``QUARTER_YEAR`` and ``HALF_HOUR`` are aliases of existing grains."""
    grains = spec._time_grain_expressions  # noqa: SLF001
    assert grains[TimeGrain.QUARTER_YEAR] == grains[TimeGrain.QUARTER]
    assert grains[TimeGrain.HALF_HOUR] == grains[TimeGrain.THIRTY_MINUTES]


def test_time_grain_expressions_default_passthrough() -> None:
    grains = spec._time_grain_expressions  # noqa: SLF001
    assert grains[None] == "{col}"


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Text", "'2019-01-02 03:04:05'"),
        ("DateTime", "'2019-01-02 03:04:05'"),
        ("TimeStamp", "'2019-01-02 03:04:05'"),
        ("Other", None),
    ],
)
def test_convert_dttm_legacy_cases(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    assert_convert_dttm(spec, target_type, expected_result, dttm)


@pytest.mark.parametrize(
    "dttm,grain,expected",
    [
        ("2022-05-04T05:06:07.89Z", TimeGrain.SECOND, "2022-05-04 05:06:07"),
        ("2022-05-04T05:06:07.89Z", TimeGrain.FIVE_SECONDS, "2022-05-04 05:06:05"),
        ("2022-05-04T05:06:37.89Z", TimeGrain.THIRTY_SECONDS, "2022-05-04 05:06:30"),
        ("2022-05-04T05:06:07.89Z", TimeGrain.MINUTE, "2022-05-04 05:06:00"),
        ("2022-05-04T05:06:07.89Z", TimeGrain.FIVE_MINUTES, "2022-05-04 05:05:00"),
        ("2022-05-04T05:36:07.89Z", TimeGrain.TEN_MINUTES, "2022-05-04 05:30:00"),
        ("2022-05-04T05:46:07.89Z", TimeGrain.FIFTEEN_MINUTES, "2022-05-04 05:45:00"),
        ("2022-05-04T05:36:07.89Z", TimeGrain.THIRTY_MINUTES, "2022-05-04 05:30:00"),
        ("2022-05-04T05:36:07.89Z", TimeGrain.HALF_HOUR, "2022-05-04 05:30:00"),
        ("2022-05-04T05:06:07.89Z", TimeGrain.HOUR, "2022-05-04 05:00:00"),
        ("2022-05-04T07:06:07.89Z", TimeGrain.SIX_HOURS, "2022-05-04 06:00:00"),
        ("2022-05-04T05:06:07.89Z", TimeGrain.DAY, "2022-05-04 00:00:00"),
        ("2022-05-04T05:06:07.89Z", TimeGrain.WEEK, "2022-05-01 00:00:00"),
        ("2022-05-04T05:06:07.89Z", TimeGrain.MONTH, "2022-05-01 00:00:00"),
        ("2022-05-04T05:06:07.89Z", TimeGrain.YEAR, "2022-01-01 00:00:00"),
        #  ___________________________
        # |         May 2022          |
        # |---------------------------|
        # | S | M | T | W | T | F | S |
        # |---+---+---+---+---+---+---|
        # | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
        #  ---------------------------
        (
            "2022-05-04T05:06:07.89Z",
            TimeGrain.WEEK_ENDING_SATURDAY,
            "2022-05-07 00:00:00",
        ),
        (
            "2022-05-04T05:06:07.89Z",
            TimeGrain.WEEK_ENDING_SUNDAY,
            "2022-05-08 00:00:00",
        ),
        (
            "2022-05-04T05:06:07.89Z",
            TimeGrain.WEEK_STARTING_SUNDAY,
            "2022-05-01 00:00:00",
        ),
        (
            "2022-05-04T05:06:07.89Z",
            TimeGrain.WEEK_STARTING_MONDAY,
            "2022-05-02 00:00:00",
        ),
        ("2022-01-04T05:06:07.89Z", TimeGrain.QUARTER_YEAR, "2022-01-01 00:00:00"),
        ("2022-02-04T05:06:07.89Z", TimeGrain.QUARTER_YEAR, "2022-01-01 00:00:00"),
        ("2022-03-04T05:06:07.89Z", TimeGrain.QUARTER_YEAR, "2022-01-01 00:00:00"),
        ("2022-04-04T05:06:07.89Z", TimeGrain.QUARTER_YEAR, "2022-04-01 00:00:00"),
        ("2022-05-04T05:06:07.89Z", TimeGrain.QUARTER_YEAR, "2022-04-01 00:00:00"),
        ("2022-06-04T05:06:07.89Z", TimeGrain.QUARTER_YEAR, "2022-04-01 00:00:00"),
        ("2022-07-04T05:06:07.89Z", TimeGrain.QUARTER_YEAR, "2022-07-01 00:00:00"),
        ("2022-08-04T05:06:07.89Z", TimeGrain.QUARTER_YEAR, "2022-07-01 00:00:00"),
        ("2022-09-04T05:06:07.89Z", TimeGrain.QUARTER_YEAR, "2022-07-01 00:00:00"),
        ("2022-10-04T05:06:07.89Z", TimeGrain.QUARTER_YEAR, "2022-10-01 00:00:00"),
        ("2022-11-04T05:06:07.89Z", TimeGrain.QUARTER_YEAR, "2022-10-01 00:00:00"),
        ("2022-12-04T05:06:07.89Z", TimeGrain.QUARTER_YEAR, "2022-10-01 00:00:00"),
        ("2022-01-04T05:06:07.89Z", TimeGrain.QUARTER, "2022-01-01 00:00:00"),
        ("2022-02-04T05:06:07.89Z", TimeGrain.QUARTER, "2022-01-01 00:00:00"),
        ("2022-03-04T05:06:07.89Z", TimeGrain.QUARTER, "2022-01-01 00:00:00"),
        ("2022-04-04T05:06:07.89Z", TimeGrain.QUARTER, "2022-04-01 00:00:00"),
        ("2022-05-04T05:06:07.89Z", TimeGrain.QUARTER, "2022-04-01 00:00:00"),
        ("2022-06-04T05:06:07.89Z", TimeGrain.QUARTER, "2022-04-01 00:00:00"),
        ("2022-07-04T05:06:07.89Z", TimeGrain.QUARTER, "2022-07-01 00:00:00"),
        ("2022-08-04T05:06:07.89Z", TimeGrain.QUARTER, "2022-07-01 00:00:00"),
        ("2022-09-04T05:06:07.89Z", TimeGrain.QUARTER, "2022-07-01 00:00:00"),
        ("2022-10-04T05:06:07.89Z", TimeGrain.QUARTER, "2022-10-01 00:00:00"),
        ("2022-11-04T05:06:07.89Z", TimeGrain.QUARTER, "2022-10-01 00:00:00"),
        ("2022-12-04T05:06:07.89Z", TimeGrain.QUARTER, "2022-10-01 00:00:00"),
    ],
)
def test_time_grain_expressions(dttm: str, grain: str, expected: str) -> None:  # noqa: F811
    engine = create_engine("sqlite://")
    connection = engine.connect()
    connection.execute("CREATE TABLE t (dttm DATETIME)")
    connection.execute("INSERT INTO t VALUES (?)", dttm)

    expression = spec._time_grain_expressions[grain].format(col="dttm")  # noqa: SLF001
    sql = f"SELECT {expression} FROM t"  # noqa: S608
    result = connection.execute(sql).scalar()
    assert result == expected
