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

from superset.constants import TimeGrain
from superset.db_engine_specs.db2 import Db2EngineSpec
from superset.db_engine_specs.ibmi import IBMiEngineSpec
from superset.sql.parse import LimitMethod, Table
from tests.unit_tests.db_engine_specs.utils import assert_convert_dttm
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


def test_engine_attributes() -> None:
    """
    Test the engine identifier, display name, and column-name length cap.
    """
    assert IBMiEngineSpec.engine == "ibmi"
    assert IBMiEngineSpec.engine_name == "IBM Db2 for i"
    assert IBMiEngineSpec.max_column_name_length == 128


def test_inherits_from_db2() -> None:
    """
    Ensure IBMiEngineSpec is a subclass of Db2EngineSpec so it picks up
    Db2-specific behaviour by default.
    """
    assert issubclass(IBMiEngineSpec, Db2EngineSpec)
    assert IBMiEngineSpec is not Db2EngineSpec


def test_max_column_name_length_overrides_parent() -> None:
    """
    Db2 caps column names at 30 characters; IBM Db2 for i allows 128.
    The override must not silently regress to the parent value.
    """
    assert IBMiEngineSpec.max_column_name_length == 128
    assert IBMiEngineSpec.max_column_name_length != Db2EngineSpec.max_column_name_length


def test_epoch_to_dttm_returns_ibmi_specific_expression() -> None:
    """
    The override should return the IBM i compatible expression, not the
    inherited Db2 expression.
    """
    assert IBMiEngineSpec.epoch_to_dttm() == (
        "(DAYS({col}) - DAYS('1970-01-01')) * 86400 + MIDNIGHT_SECONDS({col})"
    )
    assert IBMiEngineSpec.epoch_to_dttm() != Db2EngineSpec.epoch_to_dttm()


@pytest.mark.parametrize(
    "col_name",
    [
        "epoch_dttm",
        "my_col",
        "MY_COL",
        "table.column_name",
        "a",
    ],
)
def test_epoch_to_dttm_format_with_column_name(col_name: str) -> None:
    """
    Verify the placeholder `{col}` is replaced for varied identifiers
    (lowercase, uppercase, dotted, single-character).
    """
    expected = (
        f"(DAYS({col_name}) - DAYS('1970-01-01')) * 86400 "
        f"+ MIDNIGHT_SECONDS({col_name})"
    )
    assert IBMiEngineSpec.epoch_to_dttm().format(col=col_name) == expected


def test_epoch_to_dttm_format_with_empty_col() -> None:
    """
    Edge case: formatting with an empty string still produces a syntactically
    valid expression (even if the resulting SQL would be invalid).
    """
    assert IBMiEngineSpec.epoch_to_dttm().format(col="") == (
        "(DAYS() - DAYS('1970-01-01')) * 86400 + MIDNIGHT_SECONDS()"
    )


def test_epoch_to_dttm_classmethod_idempotent() -> None:
    """
    The method has no state; multiple invocations must return the same string.
    """
    assert IBMiEngineSpec.epoch_to_dttm() == IBMiEngineSpec.epoch_to_dttm()


def test_convert_dttm_returns_none_inherited(
    dttm: datetime,  # noqa: F811
) -> None:
    """
    IBMi does not override `convert_dttm`; it inherits the base implementation
    which returns None for every target type.
    """
    for target_type in ("Date", "DateTime", "TimeStamp", "UnknownType"):
        assert_convert_dttm(IBMiEngineSpec, target_type, None, dttm)


def test_convert_dttm_with_db_extra(dttm: datetime) -> None:  # noqa: F811
    """
    The optional `db_extra` argument must be accepted and have no effect on
    the inherited `convert_dttm` behaviour.
    """
    result: Optional[str] = IBMiEngineSpec.convert_dttm(
        target_type="DateTime",
        dttm=dttm,
        db_extra={"some_key": "some_value"},
    )
    assert result is None


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
def test_time_grain_expressions_inherited(
    grain: Optional[TimeGrain],
    expected_expression: str,
) -> None:
    """
    IBMiEngineSpec inherits Db2's time grain expressions verbatim.
    """
    actual = IBMiEngineSpec._time_grain_expressions[grain].format(col="my_col")
    assert actual == expected_expression


def test_time_grain_expressions_match_db2() -> None:
    """
    Inheriting Db2's mapping means both classes share the exact same dict.
    """
    assert (
        IBMiEngineSpec._time_grain_expressions == Db2EngineSpec._time_grain_expressions
    )


def test_inherited_class_flags() -> None:
    """
    Boolean / enum flags inherited from Db2 must be exposed on the subclass.
    """
    assert IBMiEngineSpec.limit_method == LimitMethod.WRAP_SQL
    assert IBMiEngineSpec.force_column_alias_quotes is True
    assert IBMiEngineSpec.supports_dynamic_schema is True
    assert IBMiEngineSpec.supports_multivalues_insert is True


def test_get_table_comment_inherited(mocker: MockerFixture) -> None:
    """
    `get_table_comment` is inherited from Db2 and unwraps the tuple returned
    by the underlying inspector.
    """
    mock_inspector = mocker.MagicMock()
    mock_inspector.get_table_comment.return_value = {
        "text": ("This is an IBM i table comment",)
    }

    assert (
        IBMiEngineSpec.get_table_comment(mock_inspector, Table("my_table", "my_schema"))
        == "This is an IBM i table comment"
    )


def test_get_table_comment_empty_inherited(mocker: MockerFixture) -> None:
    """
    When the inspector returns no comment text, `get_table_comment` should
    fall through to None.
    """
    mock_inspector = mocker.MagicMock()
    mock_inspector.get_table_comment.return_value = {}

    assert (
        IBMiEngineSpec.get_table_comment(mock_inspector, Table("my_table", "my_schema"))
        is None
    )


def test_get_table_comment_unexpected_exception(mocker: MockerFixture) -> None:
    """
    Inherited `get_table_comment` swallows unexpected exceptions and returns
    None rather than propagating to the caller.
    """
    mock_inspector = mocker.MagicMock()
    mock_inspector.get_table_comment.side_effect = RuntimeError("boom")

    assert (
        IBMiEngineSpec.get_table_comment(mock_inspector, Table("my_table", "my_schema"))
        is None
    )


def test_get_prequeries_no_schema(mocker: MockerFixture) -> None:
    """
    Without a schema argument the inherited helper returns no prequeries.
    """
    database = mocker.MagicMock()
    assert IBMiEngineSpec.get_prequeries(database) == []


def test_get_prequeries_with_schema(mocker: MockerFixture) -> None:
    """
    When a schema is provided the inherited helper sets the current schema.
    """
    database = mocker.MagicMock()
    assert IBMiEngineSpec.get_prequeries(database, schema="my_schema") == [
        'set current_schema "my_schema"'
    ]


def test_get_prequeries_with_empty_schema(mocker: MockerFixture) -> None:
    """
    Empty-string schemas are falsy and must not generate a `set current_schema`
    statement.
    """
    database = mocker.MagicMock()
    assert IBMiEngineSpec.get_prequeries(database, schema="") == []


def test_get_dbapi_exception_mapping_inherited() -> None:
    """
    The base implementation returns an empty mapping; IBMi inherits it.
    """
    assert IBMiEngineSpec.get_dbapi_exception_mapping() == {}
