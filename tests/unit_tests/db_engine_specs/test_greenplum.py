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
from sqlalchemy import column, types
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION, ENUM, JSON

from superset.db_engine_specs.base import DatabaseCategory
from superset.db_engine_specs.greenplum import (
    GreenplumEngineSpec as spec,  # noqa: N813
)
from superset.db_engine_specs.postgres import PostgresEngineSpec
from superset.utils.core import GenericDataType
from tests.unit_tests.db_engine_specs.utils import (
    assert_column_spec,
    assert_convert_dttm,
)
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


def test_engine_identity() -> None:
    """
    DB Eng Specs (greenplum): basic identity attributes.
    """
    assert spec.engine == "greenplum"
    assert spec.engine_name == "Greenplum"
    assert spec.default_driver == "psycopg2"


def test_inherits_from_postgres() -> None:
    """
    DB Eng Specs (greenplum): inherits from PostgresEngineSpec so that
    Greenplum reuses Postgres SQL behavior.
    """
    assert issubclass(spec, PostgresEngineSpec)


def test_metadata_top_level_keys() -> None:
    """
    DB Eng Specs (greenplum): metadata exposes the keys consumed by the UI.
    """
    metadata = spec.metadata
    assert isinstance(metadata, dict)
    expected_keys = {
        "description",
        "logo",
        "homepage_url",
        "categories",
        "pypi_packages",
        "connection_string",
        "default_port",
        "parameters",
        "docs_url",
    }
    assert expected_keys.issubset(metadata.keys())


def test_metadata_description_and_logo() -> None:
    """
    DB Eng Specs (greenplum): description and logo are populated.
    """
    metadata = spec.metadata
    assert "Greenplum" in metadata["description"]
    assert "massively parallel processing" in metadata["description"]
    assert metadata["logo"] == "greenplum.png"
    assert metadata["homepage_url"].startswith("https://")
    assert metadata["docs_url"].startswith("https://")


def test_metadata_categories() -> None:
    """
    DB Eng Specs (greenplum): categories include the expected RDBMS and
    open source classifications.
    """
    categories = spec.metadata["categories"]
    assert isinstance(categories, list)
    assert DatabaseCategory.TRADITIONAL_RDBMS in categories
    assert DatabaseCategory.OPEN_SOURCE in categories


def test_metadata_pypi_packages() -> None:
    """
    DB Eng Specs (greenplum): pypi_packages lists the required drivers.
    """
    packages = spec.metadata["pypi_packages"]
    assert isinstance(packages, list)
    assert "psycopg2" in packages
    assert "sqlalchemy-greenplum" in packages


def test_metadata_connection_string_template() -> None:
    """
    DB Eng Specs (greenplum): connection_string template includes all
    placeholders expected by the UI.
    """
    template = spec.metadata["connection_string"]
    assert template.startswith("greenplum://")
    for placeholder in ("{username}", "{password}", "{host}", "{port}", "{database}"):
        assert placeholder in template


def test_metadata_default_port() -> None:
    """
    DB Eng Specs (greenplum): default port matches the PostgreSQL default.
    """
    assert spec.metadata["default_port"] == 5432


def test_metadata_parameters_keys() -> None:
    """
    DB Eng Specs (greenplum): parameters dict documents each connection field.
    """
    parameters = spec.metadata["parameters"]
    assert isinstance(parameters, dict)
    assert set(parameters.keys()) == {
        "username",
        "password",
        "host",
        "port",
        "database",
    }
    for value in parameters.values():
        assert isinstance(value, str)
        assert value


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Date", "TO_DATE('2019-01-02', 'YYYY-MM-DD')"),
        (
            "DateTime",
            "TO_TIMESTAMP('2019-01-02 03:04:05.678900', 'YYYY-MM-DD HH24:MI:SS.US')",
        ),
        (
            "TimeStamp",
            "TO_TIMESTAMP('2019-01-02 03:04:05.678900', 'YYYY-MM-DD HH24:MI:SS.US')",
        ),
        ("UnknownType", None),
    ],
)
def test_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    """
    DB Eng Specs (greenplum): convert_dttm produces Postgres-style
    TO_DATE / TO_TIMESTAMP literals (inherited from Postgres) and returns
    None for unknown target types.
    """
    assert_convert_dttm(spec, target_type, expected_result, dttm)


def test_convert_dttm_with_timezone_aware_datetime() -> None:
    """
    DB Eng Specs (greenplum): convert_dttm handles tz-aware datetimes by
    embedding the timezone offset in the formatted string.
    """
    from datetime import timezone

    tz_dttm = datetime(2024, 6, 15, 12, 30, 45, 123456, tzinfo=timezone.utc)
    result = spec.convert_dttm("DateTime", tz_dttm)
    assert result is not None
    assert "2024-06-15 12:30:45.123456" in result
    assert "TO_TIMESTAMP" in result


def test_convert_dttm_date_boundary_values() -> None:
    """
    DB Eng Specs (greenplum): convert_dttm handles boundary date values such
    as the Unix epoch and dates far in the future.
    """
    epoch = datetime(1970, 1, 1, 0, 0, 0)
    assert spec.convert_dttm("Date", epoch) == "TO_DATE('1970-01-01', 'YYYY-MM-DD')"

    far_future = datetime(2999, 12, 31, 23, 59, 59, 999999)
    result = spec.convert_dttm("DateTime", far_future)
    assert result == (
        "TO_TIMESTAMP('2999-12-31 23:59:59.999999', 'YYYY-MM-DD HH24:MI:SS.US')"
    )


def test_convert_dttm_empty_target_type_returns_none() -> None:
    """
    DB Eng Specs (greenplum): an empty target type cannot be resolved to a
    SQLAlchemy type and should return None instead of raising.
    """
    assert spec.convert_dttm("", datetime(2024, 1, 1)) is None


def test_epoch_to_dttm() -> None:
    """
    DB Eng Specs (greenplum): epoch_to_dttm returns the Postgres-style
    interval expression used to convert an epoch column to a timestamp.
    """
    expr = spec.epoch_to_dttm()
    assert expr == "(timestamp 'epoch' + {col} * interval '1 second')"
    assert "{col}" in expr


def test_epoch_ms_to_dttm_uses_epoch_seconds() -> None:
    """
    DB Eng Specs (greenplum): epoch_ms_to_dttm should fall back to dividing
    millisecond columns by 1000 and reusing epoch_to_dttm.
    """
    expr = spec.epoch_ms_to_dttm()
    assert "{col}" in expr
    assert "1000" in expr


@pytest.mark.parametrize(
    "time_grain,expected_result",
    [
        ("PT1S", "DATE_TRUNC('second', col)"),
        (
            "PT5S",
            "DATE_TRUNC('minute', col) + INTERVAL '5 seconds' * FLOOR(EXTRACT(SECOND FROM col) / 5)",  # noqa: E501
        ),
        (
            "PT30S",
            "DATE_TRUNC('minute', col) + INTERVAL '30 seconds' * FLOOR(EXTRACT(SECOND FROM col) / 30)",  # noqa: E501
        ),
        ("PT1M", "DATE_TRUNC('minute', col)"),
        (
            "PT5M",
            "DATE_TRUNC('hour', col) + INTERVAL '5 minutes' * FLOOR(EXTRACT(MINUTE FROM col) / 5)",  # noqa: E501
        ),
        (
            "PT10M",
            "DATE_TRUNC('hour', col) + INTERVAL '10 minutes' * FLOOR(EXTRACT(MINUTE FROM col) / 10)",  # noqa: E501
        ),
        (
            "PT15M",
            "DATE_TRUNC('hour', col) + INTERVAL '15 minutes' * FLOOR(EXTRACT(MINUTE FROM col) / 15)",  # noqa: E501
        ),
        (
            "PT30M",
            "DATE_TRUNC('hour', col) + INTERVAL '30 minutes' * FLOOR(EXTRACT(MINUTE FROM col) / 30)",  # noqa: E501
        ),
        ("PT1H", "DATE_TRUNC('hour', col)"),
        ("P1D", "DATE_TRUNC('day', col)"),
        ("P1W", "DATE_TRUNC('week', col)"),
        ("P1M", "DATE_TRUNC('month', col)"),
        ("P3M", "DATE_TRUNC('quarter', col)"),
        ("P1Y", "DATE_TRUNC('year', col)"),
    ],
)
def test_timegrain_expressions(time_grain: str, expected_result: str) -> None:
    """
    DB Eng Specs (greenplum): time grains inherited from Postgres render
    the expected DATE_TRUNC expressions.
    """
    actual = str(
        spec.get_timestamp_expr(col=column("col"), pdf=None, time_grain=time_grain)
    )
    assert actual == expected_result


def test_timegrain_expressions_none_returns_raw_column() -> None:
    """
    DB Eng Specs (greenplum): a None time grain returns the column expression
    unchanged.
    """
    actual = str(spec.get_timestamp_expr(col=column("col"), pdf=None, time_grain=None))
    assert actual == "col"


@pytest.mark.parametrize(
    "native_type,sqla_type,generic_type,is_dttm",
    [
        ("SMALLINT", types.SmallInteger, GenericDataType.NUMERIC, False),
        ("INTEGER", types.Integer, GenericDataType.NUMERIC, False),
        ("BIGINT", types.BigInteger, GenericDataType.NUMERIC, False),
        ("DECIMAL", types.Numeric, GenericDataType.NUMERIC, False),
        ("NUMERIC", types.Numeric, GenericDataType.NUMERIC, False),
        ("REAL", types.REAL, GenericDataType.NUMERIC, False),
        ("DOUBLE PRECISION", DOUBLE_PRECISION, GenericDataType.NUMERIC, False),
        ("MONEY", types.Numeric, GenericDataType.NUMERIC, False),
        ("CHAR", types.String, GenericDataType.STRING, False),
        ("VARCHAR", types.String, GenericDataType.STRING, False),
        ("TEXT", types.String, GenericDataType.STRING, False),
        ("ARRAY", types.String, GenericDataType.STRING, False),
        ("ENUM", ENUM, GenericDataType.STRING, False),
        ("JSON", JSON, GenericDataType.STRING, False),
        ("DATE", types.Date, GenericDataType.TEMPORAL, True),
        ("TIMESTAMP", types.TIMESTAMP, GenericDataType.TEMPORAL, True),
        ("TIME", types.Time, GenericDataType.TEMPORAL, True),
        ("BOOLEAN", types.Boolean, GenericDataType.BOOLEAN, False),
    ],
)
def test_get_column_spec(
    native_type: str,
    sqla_type: type[types.TypeEngine],
    generic_type: GenericDataType,
    is_dttm: bool,
) -> None:
    """
    DB Eng Specs (greenplum): native Postgres column types are recognized
    when looked up via the Greenplum spec.
    """
    assert_column_spec(spec, native_type, sqla_type, None, generic_type, is_dttm)


def test_get_column_spec_unknown_type_returns_none() -> None:
    """
    DB Eng Specs (greenplum): an unrecognized native type yields no column
    spec rather than raising.
    """
    assert spec.get_column_spec("DOES_NOT_EXIST_TYPE") is None


def test_custom_errors_inherited() -> None:
    """
    DB Eng Specs (greenplum): inherits Postgres custom error regex mapping
    used to translate driver errors into SupersetErrorType values.
    """
    custom_errors = spec.custom_errors
    assert isinstance(custom_errors, dict)
    assert len(custom_errors) > 0


def test_get_dbapi_exception_mapping_default() -> None:
    """
    DB Eng Specs (greenplum): get_dbapi_exception_mapping returns an empty
    mapping by default (inherited from BaseEngineSpec).
    """
    mapping = spec.get_dbapi_exception_mapping()
    assert mapping == {}


def test_get_dbapi_mapped_exception_returns_original_when_unmapped() -> None:
    """
    DB Eng Specs (greenplum): when no mapping is configured, the original
    exception is returned unchanged.
    """

    class FakeDBAPIError(Exception):
        pass

    err = FakeDBAPIError("boom")
    assert spec.get_dbapi_mapped_exception(err) is err


def test_supports_multivalues_insert_inherited() -> None:
    """
    DB Eng Specs (greenplum): inherits the multi-values INSERT support flag
    from PostgresBaseEngineSpec.
    """
    assert spec.supports_multivalues_insert is True


def test_supports_dynamic_schema_inherited() -> None:
    """
    DB Eng Specs (greenplum): inherits the dynamic schema flag from
    PostgresEngineSpec, allowing search_path overrides.
    """
    assert spec.supports_dynamic_schema is True
