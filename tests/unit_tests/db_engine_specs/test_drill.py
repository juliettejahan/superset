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
# pylint: disable=unused-argument, import-outside-toplevel, protected-access

from datetime import datetime
from typing import Optional

import pytest
from pytest_mock import MockerFixture
from sqlalchemy.engine.url import make_url

from tests.unit_tests.db_engine_specs.utils import assert_convert_dttm
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


def test_odbc_impersonation(mocker: MockerFixture) -> None:
    """
    Test ``impersonate_user`` method when driver == odbc.

    The method adds the parameter ``DelegationUID`` to the query string.
    """
    from sqlalchemy.engine.url import URL

    from superset.db_engine_specs.drill import DrillEngineSpec

    database = mocker.MagicMock()

    url = URL.create("drill+odbc")
    username = "DoAsUser"
    url, _ = DrillEngineSpec.impersonate_user(
        database=database,
        username=username,
        user_token=None,
        url=url,
        engine_kwargs={},
    )
    assert url.query["DelegationUID"] == username


def test_jdbc_impersonation(mocker: MockerFixture) -> None:
    """
    Test ``impersonate_user`` method when driver == jdbc.

    The method adds the parameter ``impersonation_target`` to the query string.
    """
    from sqlalchemy.engine.url import URL

    from superset.db_engine_specs.drill import DrillEngineSpec

    database = mocker.MagicMock()

    url = URL.create("drill+jdbc")
    username = "DoAsUser"
    url, _ = DrillEngineSpec.impersonate_user(
        database=database,
        username=username,
        user_token=None,
        url=url,
        engine_kwargs={},
    )
    assert url.query["impersonation_target"] == username


def test_sadrill_impersonation(mocker: MockerFixture) -> None:
    """
    Test ``impersonate_user`` method when driver == sadrill.

    The method adds the parameter ``impersonation_target`` to the query string.
    """
    from sqlalchemy.engine.url import URL

    from superset.db_engine_specs.drill import DrillEngineSpec

    database = mocker.MagicMock()

    url = URL.create("drill+sadrill")
    username = "DoAsUser"
    url, _ = DrillEngineSpec.impersonate_user(
        database=database,
        username=username,
        user_token=None,
        url=url,
        engine_kwargs={},
    )
    assert url.query["impersonation_target"] == username


def test_invalid_impersonation(mocker: MockerFixture) -> None:
    """
    Test ``impersonate_user`` method when driver == foobar.

    The method raises an exception because impersonation is not supported
    for drill+foobar.
    """
    from sqlalchemy.engine.url import URL

    from superset.db_engine_specs.drill import DrillEngineSpec
    from superset.db_engine_specs.exceptions import SupersetDBAPIProgrammingError

    database = mocker.MagicMock()

    url = URL.create("drill+foobar")
    username = "DoAsUser"

    with pytest.raises(SupersetDBAPIProgrammingError):
        DrillEngineSpec.impersonate_user(
            database=database,
            username=username,
            user_token=None,
            url=url,
            engine_kwargs={},
        )


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Date", "TO_DATE('2019-01-02', 'yyyy-MM-dd')"),
        ("TimeStamp", "TO_TIMESTAMP('2019-01-02 03:04:05', 'yyyy-MM-dd HH:mm:ss')"),
        ("UnknownType", None),
    ],
)
def test_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    from superset.db_engine_specs.drill import DrillEngineSpec as spec  # noqa: N813

    assert_convert_dttm(spec, target_type, expected_result, dttm)


def test_get_schema_from_engine_params() -> None:
    """
    Test ``get_schema_from_engine_params``.
    """
    from superset.db_engine_specs.drill import DrillEngineSpec

    assert (
        DrillEngineSpec.get_schema_from_engine_params(
            make_url("drill+sadrill://localhost:8047/dfs/test?use_ssl=False"),
            {},
        )
        == "dfs.test"
    )


@pytest.mark.parametrize(
    "column_name,expected_result",
    [
        # SHA-256 hash suffix (first 6 chars) with default HASH_ALGORITHM
        ("time", "time_336074"),
        ("count", "count_6c3549"),
    ],
)
def test_connect_make_label_compatible(column_name: str, expected_result: str) -> None:
    from superset.db_engine_specs.drill import (
        DrillEngineSpec as spec,  # noqa: N813
    )

    label = spec.make_label_compatible(column_name)
    assert label == expected_result


def test_epoch_ms_to_dttm() -> None:
    """``epoch_ms_to_dttm`` returns Drill's ``TO_DATE`` SQL fragment."""
    from superset.db_engine_specs.drill import DrillEngineSpec

    assert DrillEngineSpec.epoch_ms_to_dttm() == "TO_DATE({col})"


def test_epoch_to_dttm() -> None:
    """``epoch_to_dttm`` multiplies the seconds column by 1000 to reuse ``epoch_ms_to_dttm``."""  # noqa: E501
    from superset.db_engine_specs.drill import DrillEngineSpec

    assert DrillEngineSpec.epoch_to_dttm() == "TO_DATE(({col}*1000))"


def test_convert_dttm_none_db_extra(dttm: datetime) -> None:  # noqa: F811
    """``convert_dttm`` accepts ``None`` ``db_extra`` and returns ``None`` for unsupported types."""  # noqa: E501
    from superset.db_engine_specs.drill import DrillEngineSpec

    assert DrillEngineSpec.convert_dttm("UnknownType", dttm, db_extra=None) is None
    assert DrillEngineSpec.convert_dttm("Date", dttm, db_extra={"foo": "bar"}) == (
        "TO_DATE('2019-01-02', 'yyyy-MM-dd')"
    )


def test_adjust_engine_params_no_schema() -> None:
    """``adjust_engine_params`` is a no-op when no ``schema`` is provided."""
    from superset.db_engine_specs.drill import DrillEngineSpec

    url = make_url("drill+sadrill://localhost:8047/dfs?use_ssl=False")
    new_url, connect_args = DrillEngineSpec.adjust_engine_params(
        uri=url,
        connect_args={"foo": "bar"},
    )
    assert new_url is url
    assert connect_args == {"foo": "bar"}


def test_adjust_engine_params_with_schema() -> None:
    """``adjust_engine_params`` rewrites the DB segment when ``schema`` is provided.

    Dots in the schema are replaced with slashes so Drill can parse the path
    components, and the resulting value is URL-quoted.
    """
    from superset.db_engine_specs.drill import DrillEngineSpec

    url = make_url("drill+sadrill://localhost:8047/dfs?use_ssl=False")
    new_url, connect_args = DrillEngineSpec.adjust_engine_params(
        uri=url,
        connect_args={},
        schema="dfs.test",
    )
    assert new_url.database == "dfs%2Ftest"
    assert connect_args == {}


def test_adjust_engine_params_with_schema_no_dots() -> None:
    """A schema without dots is still URL-quoted but kept unchanged otherwise."""
    from superset.db_engine_specs.drill import DrillEngineSpec

    url = make_url("drill+sadrill://localhost:8047/dfs?use_ssl=False")
    new_url, _ = DrillEngineSpec.adjust_engine_params(
        uri=url,
        connect_args={},
        schema="cp",
    )
    assert new_url.database == "cp"


def test_get_schema_from_engine_params_no_dots() -> None:
    """A single-component database path is returned verbatim after URL-decoding."""
    from superset.db_engine_specs.drill import DrillEngineSpec

    assert (
        DrillEngineSpec.get_schema_from_engine_params(
            make_url("drill+sadrill://localhost:8047/cp"),
            {},
        )
        == "cp"
    )


def test_impersonate_user_no_username(mocker: MockerFixture) -> None:
    """``impersonate_user`` returns the URL unchanged when ``username`` is ``None``."""
    from sqlalchemy.engine.url import URL

    from superset.db_engine_specs.drill import DrillEngineSpec

    database = mocker.MagicMock()
    url = URL.create("drill+sadrill")
    engine_kwargs: dict[str, dict[str, str]] = {"connect_args": {"foo": "bar"}}

    new_url, new_kwargs = DrillEngineSpec.impersonate_user(
        database=database,
        username=None,
        user_token=None,
        url=url,
        engine_kwargs=engine_kwargs,
    )
    assert new_url is url
    assert new_kwargs is engine_kwargs


def test_fetch_data_returns_super_result(mocker: MockerFixture) -> None:
    """``fetch_data`` returns whatever ``BaseEngineSpec.fetch_data`` produces."""
    from superset.db_engine_specs.base import BaseEngineSpec
    from superset.db_engine_specs.drill import DrillEngineSpec

    expected = [("a", 1), ("b", 2)]
    mocker.patch.object(BaseEngineSpec, "fetch_data", return_value=expected)
    cursor = mocker.MagicMock()

    assert DrillEngineSpec.fetch_data(cursor, limit=10) == expected


def test_fetch_data_swallows_stop_iteration(mocker: MockerFixture) -> None:
    """``fetch_data`` swallows the StopIteration ``RuntimeError`` raised by Drill."""
    from superset.db_engine_specs.base import BaseEngineSpec
    from superset.db_engine_specs.drill import DrillEngineSpec

    mocker.patch.object(
        BaseEngineSpec,
        "fetch_data",
        side_effect=RuntimeError("generator raised StopIteration"),
    )
    cursor = mocker.MagicMock()

    assert DrillEngineSpec.fetch_data(cursor) == []


def test_fetch_data_reraises_unrelated_runtime_error(
    mocker: MockerFixture,
) -> None:
    """``fetch_data`` re-raises ``RuntimeError`` not caused by StopIteration."""
    from superset.db_engine_specs.base import BaseEngineSpec
    from superset.db_engine_specs.drill import DrillEngineSpec

    mocker.patch.object(
        BaseEngineSpec,
        "fetch_data",
        side_effect=RuntimeError("something else"),
    )
    cursor = mocker.MagicMock()

    with pytest.raises(RuntimeError, match="something else"):
        DrillEngineSpec.fetch_data(cursor)


def test_mutate_label_is_deterministic_and_suffixed() -> None:
    """``_mutate_label`` appends a 6-character hash suffix to the input label."""
    from superset.db_engine_specs.drill import DrillEngineSpec

    label = "my_column"
    mutated = DrillEngineSpec._mutate_label(label)

    assert mutated.startswith(f"{label}_")
    assert len(mutated) == len(label) + 1 + 6
    # ``_mutate_label`` is deterministic for a given input.
    assert mutated == DrillEngineSpec._mutate_label(label)
    # Different labels produce different suffixes.
    assert DrillEngineSpec._mutate_label("other") != DrillEngineSpec._mutate_label(
        label
    )


def test_time_grain_expressions_use_nearestdate() -> None:
    """All Drill time grains delegate to Drill's ``NEARESTDATE`` function."""
    from superset.constants import TimeGrain
    from superset.db_engine_specs.drill import DrillEngineSpec

    grains = DrillEngineSpec._time_grain_expressions
    assert grains[None] == "{col}"
    for grain in (
        TimeGrain.SECOND,
        TimeGrain.MINUTE,
        TimeGrain.FIFTEEN_MINUTES,
        TimeGrain.THIRTY_MINUTES,
        TimeGrain.HOUR,
        TimeGrain.DAY,
        TimeGrain.WEEK,
        TimeGrain.MONTH,
        TimeGrain.QUARTER,
        TimeGrain.YEAR,
    ):
        assert "NEARESTDATE({col}" in grains[grain]


def test_drill_engine_spec_static_attributes() -> None:
    """Static configuration on the engine spec is wired up correctly."""
    from superset.db_engine_specs.drill import DrillEngineSpec

    assert DrillEngineSpec.engine == "drill"
    assert DrillEngineSpec.engine_name == "Apache Drill"
    assert DrillEngineSpec.default_driver == "sadrill"
    assert DrillEngineSpec.supports_dynamic_schema is True
