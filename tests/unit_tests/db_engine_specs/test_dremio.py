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
from pytest_mock import MockerFixture

from superset.constants import TimeGrain
from tests.unit_tests.db_engine_specs.utils import assert_convert_dttm
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Date", "TO_DATE('2019-01-02', 'YYYY-MM-DD')"),
        (
            "TimeStamp",
            "TO_TIMESTAMP('2019-01-02 03:04:05.678', 'YYYY-MM-DD HH24:MI:SS.FFF')",
        ),
        ("UnknownType", None),
    ],
)
def test_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    from superset.db_engine_specs.dremio import DremioEngineSpec as spec  # noqa: N813

    assert_convert_dttm(spec, target_type, expected_result, dttm)


def test_convert_dttm_time_returns_none(dttm: datetime) -> None:  # noqa: F811
    """``convert_dttm`` returns ``None`` for non-Date/non-TIMESTAMP types."""
    from superset.db_engine_specs.dremio import DremioEngineSpec

    assert DremioEngineSpec.convert_dttm("Time", dttm) is None
    assert DremioEngineSpec.convert_dttm("BigInteger", dttm) is None


def test_convert_dttm_with_db_extra(dttm: datetime) -> None:  # noqa: F811
    """``convert_dttm`` ignores ``db_extra`` and returns the same SQL."""
    from superset.db_engine_specs.dremio import DremioEngineSpec

    assert (
        DremioEngineSpec.convert_dttm("Date", dttm, db_extra={"version": "24.1.0"})
        == "TO_DATE('2019-01-02', 'YYYY-MM-DD')"
    )
    assert DremioEngineSpec.convert_dttm("Date", dttm, db_extra=None) == (
        "TO_DATE('2019-01-02', 'YYYY-MM-DD')"
    )


def test_convert_dttm_timestamp_with_timezone() -> None:
    """``convert_dttm`` truncates to milliseconds and ignores tzinfo."""
    from superset.db_engine_specs.dremio import DremioEngineSpec

    aware = datetime(2024, 6, 15, 10, 20, 30, 123456, tzinfo=timezone.utc)
    result = DremioEngineSpec.convert_dttm("TIMESTAMP", aware)
    assert result == (
        "TO_TIMESTAMP('2024-06-15 10:20:30.123+00:00', 'YYYY-MM-DD HH24:MI:SS.FFF')"
    )


def test_convert_dttm_timestamp_without_microseconds() -> None:
    """``convert_dttm`` zero-pads when microseconds are absent."""
    from superset.db_engine_specs.dremio import DremioEngineSpec

    naive = datetime(2024, 1, 1, 0, 0, 0)
    result = DremioEngineSpec.convert_dttm("TIMESTAMP", naive)
    assert result == (
        "TO_TIMESTAMP('2024-01-01 00:00:00.000', 'YYYY-MM-DD HH24:MI:SS.FFF')"
    )


def test_convert_dttm_date_at_epoch_boundary() -> None:
    """``convert_dttm`` handles date boundaries such as the epoch."""
    from superset.db_engine_specs.dremio import DremioEngineSpec

    epoch = datetime(1970, 1, 1, 0, 0, 0)
    assert (
        DremioEngineSpec.convert_dttm("DATE", epoch)
        == "TO_DATE('1970-01-01', 'YYYY-MM-DD')"
    )


def test_epoch_to_dttm() -> None:
    """``epoch_to_dttm`` returns the Dremio-specific TO_DATE expression."""
    from superset.db_engine_specs.dremio import DremioEngineSpec

    assert DremioEngineSpec.epoch_to_dttm() == "TO_DATE({col})"


def test_epoch_to_dttm_format_substitution() -> None:
    """The ``{col}`` placeholder substitutes correctly."""
    from superset.db_engine_specs.dremio import DremioEngineSpec

    rendered = DremioEngineSpec.epoch_to_dttm().format(col="my_col")
    assert rendered == "TO_DATE(my_col)"


def test_get_allows_alias_in_select_no_version(mocker: MockerFixture) -> None:
    """When no ``version`` extra is set, aliases are allowed."""
    from superset.db_engine_specs.dremio import DremioEngineSpec

    database = mocker.MagicMock()
    database.get_extra.return_value = {}
    assert DremioEngineSpec.get_allows_alias_in_select(database) is True


def test_get_allows_alias_in_select_at_fixed_version(mocker: MockerFixture) -> None:
    """At the fixed version (24.1.0), aliases are allowed."""
    from superset.db_engine_specs.dremio import DremioEngineSpec

    database = mocker.MagicMock()
    database.get_extra.return_value = {"version": "24.1.0"}
    assert DremioEngineSpec.get_allows_alias_in_select(database) is True


def test_get_allows_alias_in_select_below_fixed_version(
    mocker: MockerFixture,
) -> None:
    """Below the fixed version (24.0.0), aliases are not allowed."""
    from superset.db_engine_specs.dremio import DremioEngineSpec

    database = mocker.MagicMock()
    database.get_extra.return_value = {"version": "24.0.0"}
    assert DremioEngineSpec.get_allows_alias_in_select(database) is False


def test_get_allows_alias_in_select_old_version(mocker: MockerFixture) -> None:
    """Older versions disallow aliases in SELECT."""
    from superset.db_engine_specs.dremio import DremioEngineSpec

    database = mocker.MagicMock()
    database.get_extra.return_value = {"version": "20.0.0"}
    assert DremioEngineSpec.get_allows_alias_in_select(database) is False


def test_get_allows_alias_in_select_newer_version(mocker: MockerFixture) -> None:
    """Versions newer than the fixed one allow aliases in SELECT."""
    from superset.db_engine_specs.dremio import DremioEngineSpec

    database = mocker.MagicMock()
    database.get_extra.return_value = {"version": "25.0.0"}
    assert DremioEngineSpec.get_allows_alias_in_select(database) is True


def test_get_allows_alias_in_select_empty_version(mocker: MockerFixture) -> None:
    """Falsy ``version`` strings are treated as missing version data."""
    from superset.db_engine_specs.dremio import DremioEngineSpec

    database = mocker.MagicMock()
    database.get_extra.return_value = {"version": ""}
    assert DremioEngineSpec.get_allows_alias_in_select(database) is True


def test_mutate_label_appends_hash_suffix() -> None:
    """``_mutate_label`` appends a 6-character hash derived from the label."""
    from superset.db_engine_specs.dremio import DremioEngineSpec
    from superset.utils.hashing import hash_from_str

    label = "my_label"
    expected_suffix = hash_from_str(label)[:6]
    result = DremioEngineSpec._mutate_label(label)
    assert result == f"{label}_{expected_suffix}"
    assert result.startswith(f"{label}_")
    assert len(result) == len(label) + 1 + 6


def test_mutate_label_distinct_for_different_labels() -> None:
    """Different labels yield different mutated outputs."""
    from superset.db_engine_specs.dremio import DremioEngineSpec

    a = DremioEngineSpec._mutate_label("alpha")
    b = DremioEngineSpec._mutate_label("beta")
    assert a != b
    assert a.startswith("alpha_")
    assert b.startswith("beta_")


def test_mutate_label_empty_string() -> None:
    """``_mutate_label`` still produces a deterministic suffix for empty input."""
    from superset.db_engine_specs.dremio import DremioEngineSpec

    result = DremioEngineSpec._mutate_label("")
    # Underscore separator + 6 hex chars
    assert len(result) == 7
    assert result.startswith("_")


def test_mutate_label_is_deterministic() -> None:
    """``_mutate_label`` returns the same value for the same input."""
    from superset.db_engine_specs.dremio import DremioEngineSpec

    assert DremioEngineSpec._mutate_label("repeat") == DremioEngineSpec._mutate_label(
        "repeat"
    )


def test_engine_metadata() -> None:
    """The Dremio engine spec exposes the expected metadata."""
    from superset.db_engine_specs.dremio import DremioEngineSpec

    assert DremioEngineSpec.engine == "dremio"
    assert DremioEngineSpec.engine_name == "Dremio"
    assert DremioEngineSpec.engine_aliases == {"dremio+flight"}
    assert DremioEngineSpec.default_driver == "flight"
    assert "flight" in DremioEngineSpec.drivers
    assert "pyodbc" in DremioEngineSpec.drivers


def test_time_grain_expressions_cover_all_grains() -> None:
    """Every supported grain maps to a ``DATE_TRUNC`` expression."""
    from superset.db_engine_specs.dremio import DremioEngineSpec

    expressions = DremioEngineSpec._time_grain_expressions
    assert expressions[None] == "{col}"
    expected = {
        TimeGrain.SECOND: "second",
        TimeGrain.MINUTE: "minute",
        TimeGrain.HOUR: "hour",
        TimeGrain.DAY: "day",
        TimeGrain.WEEK: "week",
        TimeGrain.MONTH: "month",
        TimeGrain.QUARTER: "quarter",
        TimeGrain.YEAR: "year",
    }
    for grain, unit in expected.items():
        assert expressions[grain] == f"DATE_TRUNC('{unit}', {{col}})"


def test_time_grain_expressions_render_with_column() -> None:
    """Time-grain expressions render with a column placeholder."""
    from superset.db_engine_specs.dremio import DremioEngineSpec

    rendered = DremioEngineSpec._time_grain_expressions[TimeGrain.DAY].format(
        col="my_dt"
    )
    assert rendered == "DATE_TRUNC('day', my_dt)"


def test_metadata_dict_structure() -> None:
    """The exposed ``metadata`` dictionary describes the connector."""
    from superset.db_engine_specs.dremio import DremioEngineSpec

    metadata = DremioEngineSpec.metadata
    assert "description" in metadata
    assert metadata["logo"] == "dremio.png"
    assert metadata["homepage_url"] == "https://www.dremio.com/"
    assert metadata["pypi_packages"] == ["sqlalchemy_dremio"]
    assert isinstance(metadata["drivers"], list)
    recommended = [d for d in metadata["drivers"] if d.get("is_recommended")]
    assert len(recommended) == 1
    assert recommended[0]["name"].startswith("Arrow Flight")


def test_sqlalchemy_uri_placeholder_format() -> None:
    """The placeholder URI documents the Arrow Flight token connection."""
    from superset.db_engine_specs.dremio import DremioEngineSpec

    placeholder = DremioEngineSpec.sqlalchemy_uri_placeholder
    assert placeholder.startswith("dremio+flight://")
    assert "Token=<TOKEN>" in placeholder
    assert "UseEncryption=true" in placeholder


def test_fixed_alias_in_select_version_constant() -> None:
    """The version threshold constant is set to 24.1.0."""
    from packaging.version import Version

    from superset.db_engine_specs.dremio import FIXED_ALIAS_IN_SELECT_VERSION

    assert FIXED_ALIAS_IN_SELECT_VERSION == Version("24.1.0")
