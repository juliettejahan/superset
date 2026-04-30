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

from superset.constants import TimeGrain
from superset.db_engine_specs.crate import CrateEngineSpec
from tests.unit_tests.db_engine_specs.utils import assert_convert_dttm
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


def test_engine_attributes() -> None:
    assert CrateEngineSpec.engine == "crate"
    assert CrateEngineSpec.engine_name == "CrateDB"


def test_metadata() -> None:
    meta = CrateEngineSpec.metadata
    assert meta["default_port"] == 4200
    assert "crate" in meta["connection_string"]
    assert len(meta["drivers"]) == 1
    assert meta["drivers"][0]["is_recommended"] is True


def test_epoch_to_dttm() -> None:
    assert CrateEngineSpec.epoch_to_dttm() == "{col} * 1000"


def test_epoch_ms_to_dttm() -> None:
    assert CrateEngineSpec.epoch_ms_to_dttm() == "{col}"


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("TimeStamp", "CAST('2019-01-02T03:04:05.678900' AS TIMESTAMP)"),
        ("TIMESTAMP", "CAST('2019-01-02T03:04:05.678900' AS TIMESTAMP)"),
        ("timestamp", "CAST('2019-01-02T03:04:05.678900' AS TIMESTAMP)"),
        ("UnknownType", None),
        ("DATE", None),
        ("VARCHAR", None),
        ("INTEGER", None),
        ("", None),
    ],
)
def test_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    assert_convert_dttm(CrateEngineSpec, target_type, expected_result, dttm)


def test_convert_dttm_with_db_extra(dttm: datetime) -> None:  # noqa: F811
    result = CrateEngineSpec.convert_dttm(
        target_type="TIMESTAMP",
        dttm=dttm,
        db_extra={"foo": "bar"},
    )
    assert result == "CAST('2019-01-02T03:04:05.678900' AS TIMESTAMP)"


def test_convert_dttm_with_none_db_extra(dttm: datetime) -> None:  # noqa: F811
    result = CrateEngineSpec.convert_dttm(
        target_type="TIMESTAMP",
        dttm=dttm,
        db_extra=None,
    )
    assert result == "CAST('2019-01-02T03:04:05.678900' AS TIMESTAMP)"


def test_convert_dttm_epoch_datetime() -> None:
    epoch = datetime(1970, 1, 1, 0, 0, 0)
    result = CrateEngineSpec.convert_dttm(target_type="TIMESTAMP", dttm=epoch)
    assert result == "CAST('1970-01-01T00:00:00' AS TIMESTAMP)"


def test_alter_new_orm_column_timestamp() -> None:
    from superset.connectors.sqla.models import SqlaTable, TableColumn
    from superset.models.core import Database

    database = Database(database_name="crate", sqlalchemy_uri="crate://db")
    tbl = SqlaTable(table_name="tbl", database=database)
    col = TableColumn(column_name="ts", type="TIMESTAMP", table=tbl)
    CrateEngineSpec.alter_new_orm_column(col)
    assert col.python_date_format == "epoch_ms"


def test_alter_new_orm_column_non_timestamp() -> None:
    from superset.connectors.sqla.models import SqlaTable, TableColumn
    from superset.models.core import Database

    database = Database(database_name="crate", sqlalchemy_uri="crate://db")
    tbl = SqlaTable(table_name="tbl", database=database)
    col = TableColumn(column_name="name", type="VARCHAR", table=tbl)
    original_format = col.python_date_format
    CrateEngineSpec.alter_new_orm_column(col)
    assert col.python_date_format == original_format


@pytest.mark.parametrize(
    "time_grain,expected_expression",
    [
        (None, "{col}"),
        (TimeGrain.SECOND, "DATE_TRUNC('second', {col})"),
        (TimeGrain.MINUTE, "DATE_TRUNC('minute', {col})"),
        (TimeGrain.HOUR, "DATE_TRUNC('hour', {col})"),
        (TimeGrain.DAY, "DATE_TRUNC('day', {col})"),
        (TimeGrain.WEEK, "DATE_TRUNC('week', {col})"),
        (TimeGrain.MONTH, "DATE_TRUNC('month', {col})"),
        (TimeGrain.QUARTER, "DATE_TRUNC('quarter', {col})"),
        (TimeGrain.YEAR, "DATE_TRUNC('year', {col})"),
    ],
)
def test_time_grain_expressions(
    time_grain: Optional[str],
    expected_expression: str,
) -> None:
    assert CrateEngineSpec._time_grain_expressions[time_grain] == expected_expression


def test_time_grain_expressions_completeness() -> None:
    expected_grains = {
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
    assert set(CrateEngineSpec._time_grain_expressions.keys()) == expected_grains
