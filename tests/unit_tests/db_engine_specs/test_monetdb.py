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
from superset.db_engine_specs.base import BaseEngineSpec, DatabaseCategory
from superset.db_engine_specs.monetdb import MonetDbEngineSpec as spec  # noqa: N813
from tests.unit_tests.db_engine_specs.utils import assert_convert_dttm
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


def test_engine_attributes() -> None:
    assert spec.engine == "monetdb"
    assert spec.engine_name == "MonetDB"
    assert spec.default_driver == "pymonetdb"
    assert issubclass(spec, BaseEngineSpec)


def test_metadata_structure() -> None:
    metadata = spec.metadata
    assert "MonetDB" in metadata["description"]
    assert "column-oriented" in metadata["description"]
    assert metadata["logo"] == "monet-db.png"
    assert metadata["homepage_url"] == "https://www.monetdb.org/"
    assert metadata["docs_url"] == "https://www.monetdb.org/documentation/"
    assert metadata["default_port"] == 50000
    assert "monetdb://" in metadata["connection_string"]


def test_metadata_categories() -> None:
    categories = spec.metadata["categories"]
    assert DatabaseCategory.TRADITIONAL_RDBMS in categories
    assert DatabaseCategory.OPEN_SOURCE in categories
    assert len(categories) == 2


def test_metadata_pypi_packages() -> None:
    packages = spec.metadata["pypi_packages"]
    assert "sqlalchemy-monetdb" in packages
    assert "pymonetdb" in packages
    assert len(packages) == 2


def test_metadata_parameters() -> None:
    params = spec.metadata["parameters"]
    assert "username" in params
    assert "password" in params
    assert "host" in params
    assert "port" in params
    assert "database" in params


def test_metadata_connection_string_format() -> None:
    connection_string = spec.metadata["connection_string"]
    assert "{username}" in connection_string
    assert "{password}" in connection_string
    assert "{host}" in connection_string
    assert "{port}" in connection_string
    assert "{database}" in connection_string


def test_time_grain_expressions_keys() -> None:
    expected_keys = {
        None,
        TimeGrain.SECOND,
        TimeGrain.MINUTE,
        TimeGrain.HOUR,
        TimeGrain.DAY,
        TimeGrain.MONTH,
        TimeGrain.YEAR,
    }
    assert set(spec._time_grain_expressions.keys()) == expected_keys


def test_time_grain_expression_no_grain() -> None:
    actual = str(spec.get_timestamp_expr(col=column("col"), pdf=None, time_grain=None))
    assert actual == "col"


@pytest.mark.parametrize(
    "time_grain,expected_result",
    [
        (
            TimeGrain.SECOND,
            "CAST(FLOOR(EXTRACT(EPOCH FROM col)) AS TIMESTAMP)",
        ),
        (
            TimeGrain.MINUTE,
            "CAST(col AS TIMESTAMP) - "
            "CAST(EXTRACT(SECOND FROM col) AS INTERVAL SECOND)",
        ),
        (
            TimeGrain.HOUR,
            "CAST(col AS TIMESTAMP) - "
            "CAST(EXTRACT(MINUTE FROM col) AS INTERVAL MINUTE) - "
            "CAST(EXTRACT(SECOND FROM col) AS INTERVAL SECOND)",
        ),
        (
            TimeGrain.DAY,
            "CAST(col AS DATE)",
        ),
        (
            TimeGrain.MONTH,
            "CAST(EXTRACT(YEAR FROM col) || '-' || "
            "LPAD(CAST(EXTRACT(MONTH FROM col) AS VARCHAR), 2, '0') || "
            "'-01' AS DATE)",
        ),
        (
            TimeGrain.YEAR,
            "CAST(EXTRACT(YEAR FROM col) || '-01-01' AS DATE)",
        ),
    ],
)
def test_time_grain_expressions(time_grain: str, expected_result: str) -> None:
    actual = str(
        spec.get_timestamp_expr(col=column("col"), pdf=None, time_grain=time_grain)
    )
    assert actual == expected_result


@pytest.mark.parametrize(
    "unsupported_grain",
    [
        TimeGrain.WEEK,
        TimeGrain.QUARTER,
        TimeGrain.FIVE_MINUTES,
        TimeGrain.HALF_HOUR,
        "PT2H",
        "P2D",
    ],
)
def test_unsupported_time_grain(unsupported_grain: str) -> None:
    with pytest.raises(NotImplementedError):
        spec.get_timestamp_expr(
            col=column("col"), pdf=None, time_grain=unsupported_grain
        )


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Date", None),
        ("DateTime", None),
        ("TimeStamp", None),
        ("UnknownType", None),
        ("", None),
    ],
)
def test_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    assert_convert_dttm(spec, target_type, expected_result, dttm)


def test_convert_dttm_with_db_extra(dttm: datetime) -> None:  # noqa: F811
    assert (
        spec.convert_dttm(target_type="Date", dttm=dttm, db_extra={"key": "value"})
        is None
    )


def test_convert_dttm_with_none_db_extra(dttm: datetime) -> None:  # noqa: F811
    assert spec.convert_dttm(target_type="Date", dttm=dttm, db_extra=None) is None


def test_epoch_to_dttm() -> None:
    with pytest.raises(NotImplementedError):
        spec.epoch_to_dttm()


def test_get_dbapi_exception_mapping() -> None:
    assert spec.get_dbapi_exception_mapping() == {}
