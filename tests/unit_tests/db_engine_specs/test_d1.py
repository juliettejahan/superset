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

from __future__ import annotations

from datetime import datetime
from typing import Optional

import pytest
from sqlalchemy import column

from superset.constants import TimeGrain
from superset.db_engine_specs.base import DatabaseCategory
from superset.db_engine_specs.d1 import CloudflareD1EngineSpec as spec  # noqa: N813
from superset.db_engine_specs.sqlite import SqliteEngineSpec
from tests.unit_tests.db_engine_specs.utils import assert_convert_dttm
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


# ---------------------------------------------------------------------------
# Class attributes & inheritance
# ---------------------------------------------------------------------------
def test_engine_attributes() -> None:
    assert spec.engine == "d1"
    assert spec.engine_name == "Cloudflare D1"
    assert spec.default_driver == "d1"


def test_inherits_from_sqlite_engine_spec() -> None:
    assert issubclass(spec, SqliteEngineSpec)


def test_inherits_sqlite_flags() -> None:
    # Inherited from SqliteEngineSpec.
    assert spec.disable_ssh_tunneling is True
    assert spec.supports_multivalues_insert is True


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------
def test_metadata_top_level_keys() -> None:
    metadata = spec.metadata
    expected_keys = {
        "description",
        "logo",
        "homepage_url",
        "categories",
        "pypi_packages",
        "connection_string",
        "parameters",
        "install_instructions",
    }
    assert expected_keys.issubset(set(metadata.keys()))


def test_metadata_description() -> None:
    assert spec.metadata["description"] == (
        "Cloudflare D1 is a serverless SQLite database."
    )


def test_metadata_logo_and_homepage() -> None:
    assert spec.metadata["logo"] == "cloudflare.png"
    assert spec.metadata["homepage_url"] == "https://developers.cloudflare.com/d1/"


def test_metadata_categories() -> None:
    categories = spec.metadata["categories"]
    assert DatabaseCategory.CLOUD_DATA_WAREHOUSES in categories
    assert DatabaseCategory.TRADITIONAL_RDBMS in categories
    assert DatabaseCategory.HOSTED_OPEN_SOURCE in categories
    assert len(categories) == 3


def test_metadata_pypi_packages() -> None:
    assert spec.metadata["pypi_packages"] == ["superset-engine-d1"]


def test_metadata_connection_string() -> None:
    connection_string = spec.metadata["connection_string"]
    assert connection_string.startswith("d1://")
    assert "{cloudflare_account_id}" in connection_string
    assert "{cloudflare_api_token}" in connection_string
    assert "{cloudflare_d1_database_id}" in connection_string


def test_metadata_parameters() -> None:
    params = spec.metadata["parameters"]
    assert params == {
        "cloudflare_account_id": "Cloudflare account ID",
        "cloudflare_api_token": "Cloudflare API token",
        "cloudflare_d1_database_id": "D1 database ID",
    }


def test_metadata_install_instructions() -> None:
    assert spec.metadata["install_instructions"] == "pip install superset-engine-d1"


def test_metadata_overrides_sqlite_metadata() -> None:
    # The D1 spec defines its own metadata dict that should not be the same
    # object as the parent's.
    assert spec.metadata is not SqliteEngineSpec.metadata
    assert spec.metadata["description"] != SqliteEngineSpec.metadata["description"]


# ---------------------------------------------------------------------------
# convert_dttm – inherited from SqliteEngineSpec
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Text", "'2019-01-02 03:04:05'"),
        ("DateTime", "'2019-01-02 03:04:05'"),
        ("TimeStamp", "'2019-01-02 03:04:05'"),
        ("Other", None),
        ("UnknownType", None),
    ],
)
def test_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    assert_convert_dttm(spec, target_type, expected_result, dttm)


# ---------------------------------------------------------------------------
# epoch_to_dttm – inherited from BaseEngineSpec via SqliteEngineSpec
# ---------------------------------------------------------------------------
def test_epoch_to_dttm() -> None:
    assert spec.epoch_to_dttm() == "datetime({col}, 'unixepoch')"


# ---------------------------------------------------------------------------
# get_dbapi_exception_mapping – inherited (default empty mapping)
# ---------------------------------------------------------------------------
def test_get_dbapi_exception_mapping_default() -> None:
    assert spec.get_dbapi_exception_mapping() == {}


# ---------------------------------------------------------------------------
# Time-grain expressions – inherited from SqliteEngineSpec
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "time_grain",
    [
        TimeGrain.SECOND,
        TimeGrain.MINUTE,
        TimeGrain.HOUR,
        TimeGrain.DAY,
        TimeGrain.WEEK,
        TimeGrain.MONTH,
        TimeGrain.QUARTER,
        TimeGrain.YEAR,
    ],
)
def test_time_grain_expressions_present(time_grain: str) -> None:
    expressions = spec._time_grain_expressions
    assert time_grain in expressions
    assert "{col}" in expressions[time_grain]


def test_time_grain_no_grain_returns_column() -> None:
    actual = str(spec.get_timestamp_expr(col=column("col"), pdf=None, time_grain=None))
    assert actual == "col"


def test_time_grain_day_renders_sqlite_datetime() -> None:
    actual = str(spec.get_timestamp_expr(col=column("col"), pdf=None, time_grain="P1D"))
    assert actual == "DATETIME(col, 'start of day')"


def test_time_grain_unsupported_raises() -> None:
    with pytest.raises(NotImplementedError):
        spec.get_timestamp_expr(col=column("col"), pdf=None, time_grain="PT2H")


# ---------------------------------------------------------------------------
# Custom errors mapping – inherited from SqliteEngineSpec
# ---------------------------------------------------------------------------
def test_custom_errors_includes_column_does_not_exist() -> None:
    # Inherited regex-keyed mapping; ensure at least one entry exists so the
    # error-message translation pipeline still works for D1.
    assert len(spec.custom_errors) >= 1
