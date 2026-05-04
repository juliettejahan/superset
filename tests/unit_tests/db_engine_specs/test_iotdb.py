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

from superset.db_engine_specs.base import BaseEngineSpec, DatabaseCategory
from superset.db_engine_specs.iotdb import IoTDBEngineSpec as spec  # noqa: N813
from tests.unit_tests.db_engine_specs.utils import assert_convert_dttm
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


def test_engine_attributes() -> None:
    assert spec.engine == "iotdb"
    assert spec.engine_name == "Apache IoTDB"
    assert issubclass(spec, BaseEngineSpec)


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Date", None),
        ("DateTime", None),
        ("TimeStamp", None),
        ("Time", None),
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
        spec.convert_dttm(
            target_type="DateTime",
            dttm=dttm,
            db_extra={"engine_params": {}},
        )
        is None
    )


def test_convert_dttm_with_tz_aware_datetime() -> None:
    tz_dttm = datetime(2019, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    assert spec.convert_dttm(target_type="DateTime", dttm=tz_dttm) is None


def test_epoch_to_dttm() -> None:
    with pytest.raises(NotImplementedError):
        spec.epoch_to_dttm()


def test_epoch_ms_to_dttm() -> None:
    with pytest.raises(NotImplementedError):
        spec.epoch_ms_to_dttm()


def test_get_dbapi_exception_mapping() -> None:
    assert spec.get_dbapi_exception_mapping() == {}


def test_get_dbapi_mapped_exception_unmapped() -> None:
    err = ValueError("boom")
    mapped = spec.get_dbapi_mapped_exception(err)
    assert isinstance(mapped, Exception)


def test_time_grain_expressions_keys() -> None:
    assert set(spec._time_grain_expressions.keys()) == {None}
    assert spec._time_grain_expressions[None] == "{col}"


def test_time_grain_expression_no_grain() -> None:
    actual = str(spec.get_timestamp_expr(col=column("col"), pdf=None, time_grain=None))
    assert actual == "col"


@pytest.mark.parametrize(
    "time_grain",
    [
        "PT1S",
        "PT1M",
        "PT1H",
        "P1D",
        "P1W",
        "P1M",
        "P3M",
        "P1Y",
        "PT2H",
        "INVALID_GRAIN",
    ],
)
def test_unsupported_time_grains_raise(time_grain: str) -> None:
    with pytest.raises(NotImplementedError):
        spec.get_timestamp_expr(col=column("col"), pdf=None, time_grain=time_grain)


def test_get_time_grains_returns_empty_tuple() -> None:
    grains = spec.get_time_grains()
    assert grains == ()


def test_metadata_top_level_keys() -> None:
    metadata = spec.metadata
    expected_keys = {
        "description",
        "logo",
        "homepage_url",
        "categories",
        "pypi_packages",
        "connection_string",
        "default_port",
        "parameters",
        "notes",
    }
    assert expected_keys.issubset(metadata.keys())


def test_metadata_description() -> None:
    description = spec.metadata["description"]
    assert isinstance(description, str)
    assert "IoTDB" in description
    assert "time series" in description.lower()


def test_metadata_logo() -> None:
    assert spec.metadata["logo"] == "apache-iotdb.svg"


def test_metadata_homepage_url() -> None:
    assert spec.metadata["homepage_url"] == "https://iotdb.apache.org/"


def test_metadata_categories() -> None:
    categories = spec.metadata["categories"]
    assert DatabaseCategory.APACHE_PROJECTS in categories
    assert DatabaseCategory.TIME_SERIES in categories
    assert DatabaseCategory.OPEN_SOURCE in categories
    assert len(categories) == 3


def test_metadata_pypi_packages() -> None:
    assert spec.metadata["pypi_packages"] == ["apache-iotdb"]


def test_metadata_connection_string() -> None:
    connection_string = spec.metadata["connection_string"]
    assert connection_string.startswith("iotdb://")
    assert "{username}" in connection_string
    assert "{password}" in connection_string
    assert "{hostname}" in connection_string
    assert "{port}" in connection_string


def test_metadata_default_port() -> None:
    assert spec.metadata["default_port"] == 6667


def test_metadata_parameters() -> None:
    params = spec.metadata["parameters"]
    assert set(params.keys()) == {"username", "password", "hostname", "port"}
    for value in params.values():
        assert isinstance(value, str)
        assert len(value) > 0


def test_metadata_notes_mention_relational_model() -> None:
    notes = spec.metadata["notes"]
    assert isinstance(notes, str)
    assert "Superset" in notes
    assert "relational" in notes.lower()


def test_default_driver_inherited_none() -> None:
    assert spec.default_driver is None or isinstance(spec.default_driver, str)
