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
from sqlalchemy import column

from superset.constants import TimeGrain
from superset.db_engine_specs.arc import ArcEngineSpec as spec  # noqa: N813
from superset.db_engine_specs.base import DatabaseCategory
from tests.unit_tests.db_engine_specs.utils import assert_convert_dttm
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


def test_engine_attributes() -> None:
    assert spec.engine == "arc"
    assert spec.engine_name == "Arc"
    assert spec.default_driver == "arrow"


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Date", None),
        ("DateTime", None),
        ("TimeStamp", None),
        ("UnknownType", None),
    ],
)
def test_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    assert_convert_dttm(spec, target_type, expected_result, dttm)


def test_epoch_to_dttm() -> None:
    with pytest.raises(NotImplementedError):
        spec.epoch_to_dttm()


def test_get_dbapi_exception_mapping() -> None:
    assert spec.get_dbapi_exception_mapping() == {}


@pytest.mark.parametrize(
    "time_grain,expected_result",
    [
        ("PT1S", "DATE_TRUNC('second', col)"),
        ("PT1M", "DATE_TRUNC('minute', col)"),
        ("PT1H", "DATE_TRUNC('hour', col)"),
        ("P1D", "DATE_TRUNC('day', col)"),
        ("P1W", "DATE_TRUNC('week', col)"),
        ("P1M", "DATE_TRUNC('month', col)"),
        ("P3M", "DATE_TRUNC('quarter', col)"),
        ("P1Y", "DATE_TRUNC('year', col)"),
    ],
)
def test_time_grain_expressions(time_grain: str, expected_result: str) -> None:
    actual = str(
        spec.get_timestamp_expr(col=column("col"), pdf=None, time_grain=time_grain)
    )
    assert actual == expected_result


def test_time_grain_expression_no_grain() -> None:
    actual = str(spec.get_timestamp_expr(col=column("col"), pdf=None, time_grain=None))
    assert actual == "col"


def test_time_grain_expressions_keys() -> None:
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
    }
    assert set(spec._time_grain_expressions.keys()) == expected_keys


def test_metadata_structure() -> None:
    metadata = spec.metadata
    assert "description" in metadata
    assert "categories" in metadata
    assert DatabaseCategory.OTHER in metadata["categories"]
    assert DatabaseCategory.PROPRIETARY in metadata["categories"]
    assert "pypi_packages" in metadata
    assert "arc-superset-arrow" in metadata["pypi_packages"]
    assert "connection_string" in metadata
    assert "parameters" in metadata
    assert "drivers" in metadata
    assert "notes" in metadata


def test_metadata_drivers() -> None:
    drivers = spec.metadata["drivers"]
    assert len(drivers) == 2

    arrow_driver = drivers[0]
    assert arrow_driver["name"] == "Apache Arrow (Recommended)"
    assert arrow_driver["pypi_package"] == "arc-superset-arrow"
    assert arrow_driver["is_recommended"] is True
    assert "arc+arrow://" in arrow_driver["connection_string"]

    json_driver = drivers[1]
    assert json_driver["name"] == "JSON"
    assert json_driver["pypi_package"] == "arc-superset-dialect"
    assert json_driver["is_recommended"] is False
    assert "arc+json://" in json_driver["connection_string"]


def test_metadata_parameters() -> None:
    params = spec.metadata["parameters"]
    assert "api_key" in params
    assert "hostname" in params
    assert "port" in params
    assert "database" in params


def test_unsupported_time_grain() -> None:
    with pytest.raises(NotImplementedError):
        spec.get_timestamp_expr(col=column("col"), pdf=None, time_grain="PT2H")
