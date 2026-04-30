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

# pylint: disable=import-outside-toplevel

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from unittest.mock import MagicMock, Mock, patch

import pytest
from sqlalchemy import column, types
from sqlalchemy.dialects.mysql import (
    BIT,
    DECIMAL,
    DOUBLE,
    FLOAT,
    INTEGER,
    LONGTEXT,
    MEDIUMINT,
    MEDIUMTEXT,
    TINYINT,
    TINYTEXT,
)
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION, ENUM, JSON
from sqlalchemy.engine.url import make_url

from superset.utils import json
from superset.utils.core import GenericDataType
from tests.unit_tests.conftest import with_feature_flags
from tests.unit_tests.db_engine_specs.utils import (
    assert_column_spec,
    assert_convert_dttm,
)
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


# ---------------------------------------------------------------------------
# AuroraMySQLDataAPI – class attributes
# ---------------------------------------------------------------------------
def test_aurora_mysql_data_api_properties() -> None:
    from superset.db_engine_specs.aurora import AuroraMySQLDataAPI

    assert AuroraMySQLDataAPI.engine == "mysql"
    assert AuroraMySQLDataAPI.default_driver == "auroradataapi"
    assert AuroraMySQLDataAPI.engine_name == "Aurora MySQL (Data API)"
    assert "mysql+auroradataapi://" in AuroraMySQLDataAPI.sqlalchemy_uri_placeholder


def test_aurora_mysql_data_api_inherits_from_mysql() -> None:
    from superset.db_engine_specs.aurora import AuroraMySQLDataAPI
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    assert issubclass(AuroraMySQLDataAPI, MySQLEngineSpec)


# ---------------------------------------------------------------------------
# AuroraPostgresDataAPI – class attributes
# ---------------------------------------------------------------------------
def test_aurora_postgres_data_api_properties() -> None:
    from superset.db_engine_specs.aurora import AuroraPostgresDataAPI

    assert AuroraPostgresDataAPI.engine == "postgresql"
    assert AuroraPostgresDataAPI.default_driver == "auroradataapi"
    assert AuroraPostgresDataAPI.engine_name == "Aurora PostgreSQL (Data API)"
    assert (
        "postgresql+auroradataapi://"
        in AuroraPostgresDataAPI.sqlalchemy_uri_placeholder
    )


def test_aurora_postgres_data_api_inherits_from_postgres() -> None:
    from superset.db_engine_specs.aurora import AuroraPostgresDataAPI
    from superset.db_engine_specs.postgres import PostgresEngineSpec

    assert issubclass(AuroraPostgresDataAPI, PostgresEngineSpec)


# ---------------------------------------------------------------------------
# AuroraMySQLEngineSpec – class attributes & inheritance
# ---------------------------------------------------------------------------
def test_aurora_mysql_engine_spec_properties() -> None:
    from superset.db_engine_specs.aurora import AuroraMySQLEngineSpec

    assert AuroraMySQLEngineSpec.engine == "mysql"
    assert AuroraMySQLEngineSpec.engine_name == "Aurora MySQL"
    assert AuroraMySQLEngineSpec.default_driver == "mysqldb"


def test_aurora_mysql_inherits_from_mysql() -> None:
    from superset.db_engine_specs.aurora import AuroraMySQLEngineSpec
    from superset.db_engine_specs.mysql import MySQLEngineSpec

    assert issubclass(AuroraMySQLEngineSpec, MySQLEngineSpec)
    assert AuroraMySQLEngineSpec.supports_dynamic_schema is True


# ---------------------------------------------------------------------------
# AuroraPostgresEngineSpec – class attributes & inheritance
# ---------------------------------------------------------------------------
def test_aurora_postgres_engine_spec_properties() -> None:
    from superset.db_engine_specs.aurora import AuroraPostgresEngineSpec

    assert AuroraPostgresEngineSpec.engine == "postgresql"
    assert AuroraPostgresEngineSpec.engine_name == "Aurora PostgreSQL"
    assert AuroraPostgresEngineSpec.default_driver == "psycopg2"


def test_aurora_postgres_inherits_from_postgres() -> None:
    from superset.db_engine_specs.aurora import AuroraPostgresEngineSpec
    from superset.db_engine_specs.postgres import PostgresEngineSpec

    assert issubclass(AuroraPostgresEngineSpec, PostgresEngineSpec)
    assert AuroraPostgresEngineSpec.supports_dynamic_schema is True
    assert AuroraPostgresEngineSpec.supports_catalog is True


# ---------------------------------------------------------------------------
# AuroraMySQLEngineSpec – convert_dttm (inherited from MySQLEngineSpec)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Date", "STR_TO_DATE('2019-01-02', '%Y-%m-%d')"),
        (
            "DateTime",
            "STR_TO_DATE('2019-01-02 03:04:05.678900', '%Y-%m-%d %H:%i:%s.%f')",
        ),
        ("UnknownType", None),
    ],
)
def test_aurora_mysql_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    from superset.db_engine_specs.aurora import AuroraMySQLEngineSpec

    assert_convert_dttm(AuroraMySQLEngineSpec, target_type, expected_result, dttm)


# ---------------------------------------------------------------------------
# AuroraMySQLDataAPI – convert_dttm (inherited from MySQLEngineSpec)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Date", "STR_TO_DATE('2019-01-02', '%Y-%m-%d')"),
        (
            "DateTime",
            "STR_TO_DATE('2019-01-02 03:04:05.678900', '%Y-%m-%d %H:%i:%s.%f')",
        ),
        ("UnknownType", None),
    ],
)
def test_aurora_mysql_data_api_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    from superset.db_engine_specs.aurora import AuroraMySQLDataAPI

    assert_convert_dttm(AuroraMySQLDataAPI, target_type, expected_result, dttm)


# ---------------------------------------------------------------------------
# AuroraPostgresEngineSpec – convert_dttm (inherited from PostgresEngineSpec)
# ---------------------------------------------------------------------------
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
def test_aurora_postgres_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    from superset.db_engine_specs.aurora import AuroraPostgresEngineSpec

    assert_convert_dttm(AuroraPostgresEngineSpec, target_type, expected_result, dttm)


# ---------------------------------------------------------------------------
# AuroraPostgresDataAPI – convert_dttm (inherited from PostgresEngineSpec)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Date", "TO_DATE('2019-01-02', 'YYYY-MM-DD')"),
        (
            "DateTime",
            "TO_TIMESTAMP('2019-01-02 03:04:05.678900', 'YYYY-MM-DD HH24:MI:SS.US')",
        ),
        ("UnknownType", None),
    ],
)
def test_aurora_postgres_data_api_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    from superset.db_engine_specs.aurora import AuroraPostgresDataAPI

    assert_convert_dttm(AuroraPostgresDataAPI, target_type, expected_result, dttm)


# ---------------------------------------------------------------------------
# epoch_to_dttm
# ---------------------------------------------------------------------------
def test_aurora_mysql_epoch_to_dttm() -> None:
    from superset.db_engine_specs.aurora import AuroraMySQLEngineSpec

    assert AuroraMySQLEngineSpec.epoch_to_dttm() == "from_unixtime({col})"


def test_aurora_mysql_data_api_epoch_to_dttm() -> None:
    from superset.db_engine_specs.aurora import AuroraMySQLDataAPI

    assert AuroraMySQLDataAPI.epoch_to_dttm() == "from_unixtime({col})"


def test_aurora_postgres_epoch_to_dttm() -> None:
    from superset.db_engine_specs.aurora import AuroraPostgresEngineSpec

    assert (
        AuroraPostgresEngineSpec.epoch_to_dttm()
        == "(timestamp 'epoch' + {col} * interval '1 second')"
    )


def test_aurora_postgres_data_api_epoch_to_dttm() -> None:
    from superset.db_engine_specs.aurora import AuroraPostgresDataAPI

    assert (
        AuroraPostgresDataAPI.epoch_to_dttm()
        == "(timestamp 'epoch' + {col} * interval '1 second')"
    )


# ---------------------------------------------------------------------------
# AuroraMySQLEngineSpec – get_column_spec (inherited from MySQLEngineSpec)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "native_type,sqla_type,attrs,generic_type,is_dttm",
    [
        ("TINYINT", TINYINT, None, GenericDataType.NUMERIC, False),
        ("SMALLINT", types.SmallInteger, None, GenericDataType.NUMERIC, False),
        ("MEDIUMINT", MEDIUMINT, None, GenericDataType.NUMERIC, False),
        ("INT", INTEGER, None, GenericDataType.NUMERIC, False),
        ("BIGINT", types.BigInteger, None, GenericDataType.NUMERIC, False),
        ("DECIMAL", DECIMAL, None, GenericDataType.NUMERIC, False),
        ("FLOAT", FLOAT, None, GenericDataType.NUMERIC, False),
        ("DOUBLE", DOUBLE, None, GenericDataType.NUMERIC, False),
        ("BIT", BIT, None, GenericDataType.NUMERIC, False),
        ("CHAR", types.String, None, GenericDataType.STRING, False),
        ("VARCHAR", types.String, None, GenericDataType.STRING, False),
        ("TINYTEXT", TINYTEXT, None, GenericDataType.STRING, False),
        ("MEDIUMTEXT", MEDIUMTEXT, None, GenericDataType.STRING, False),
        ("LONGTEXT", LONGTEXT, None, GenericDataType.STRING, False),
        ("DATE", types.Date, None, GenericDataType.TEMPORAL, True),
        ("DATETIME", types.DateTime, None, GenericDataType.TEMPORAL, True),
        ("TIMESTAMP", types.TIMESTAMP, None, GenericDataType.TEMPORAL, True),
        ("TIME", types.Time, None, GenericDataType.TEMPORAL, True),
    ],
)
def test_aurora_mysql_get_column_spec(
    native_type: str,
    sqla_type: type[types.TypeEngine],
    attrs: Optional[dict[str, Any]],
    generic_type: GenericDataType,
    is_dttm: bool,
) -> None:
    from superset.db_engine_specs.aurora import AuroraMySQLEngineSpec

    assert_column_spec(
        AuroraMySQLEngineSpec, native_type, sqla_type, attrs, generic_type, is_dttm
    )


# ---------------------------------------------------------------------------
# AuroraPostgresEngineSpec – get_column_spec (inherited from PostgresEngineSpec)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "native_type,sqla_type,attrs,generic_type,is_dttm",
    [
        ("SMALLINT", types.SmallInteger, None, GenericDataType.NUMERIC, False),
        ("INTEGER", types.Integer, None, GenericDataType.NUMERIC, False),
        ("BIGINT", types.BigInteger, None, GenericDataType.NUMERIC, False),
        ("DECIMAL", types.Numeric, None, GenericDataType.NUMERIC, False),
        ("NUMERIC", types.Numeric, None, GenericDataType.NUMERIC, False),
        ("REAL", types.REAL, None, GenericDataType.NUMERIC, False),
        ("DOUBLE PRECISION", DOUBLE_PRECISION, None, GenericDataType.NUMERIC, False),
        ("MONEY", types.Numeric, None, GenericDataType.NUMERIC, False),
        ("CHAR", types.String, None, GenericDataType.STRING, False),
        ("VARCHAR", types.String, None, GenericDataType.STRING, False),
        ("TEXT", types.String, None, GenericDataType.STRING, False),
        ("ARRAY", types.String, None, GenericDataType.STRING, False),
        ("ENUM", ENUM, None, GenericDataType.STRING, False),
        ("JSON", JSON, None, GenericDataType.STRING, False),
        ("DATE", types.Date, None, GenericDataType.TEMPORAL, True),
        ("TIMESTAMP", types.TIMESTAMP, None, GenericDataType.TEMPORAL, True),
        ("TIME", types.Time, None, GenericDataType.TEMPORAL, True),
        ("BOOLEAN", types.Boolean, None, GenericDataType.BOOLEAN, False),
    ],
)
def test_aurora_postgres_get_column_spec(
    native_type: str,
    sqla_type: type[types.TypeEngine],
    attrs: Optional[dict[str, Any]],
    generic_type: GenericDataType,
    is_dttm: bool,
) -> None:
    from superset.db_engine_specs.aurora import AuroraPostgresEngineSpec

    assert_column_spec(
        AuroraPostgresEngineSpec, native_type, sqla_type, attrs, generic_type, is_dttm
    )


# ---------------------------------------------------------------------------
# AuroraMySQLEngineSpec – time grain expressions
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "time_grain,expected_result",
    [
        (
            "PT1S",
            "DATE_ADD(DATE(col), INTERVAL"
            " (HOUR(col)*60*60 + MINUTE(col)*60"
            " + SECOND(col)) SECOND)",
        ),
        (
            "PT1M",
            "DATE_ADD(DATE(col), INTERVAL (HOUR(col)*60 + MINUTE(col)) MINUTE)",
        ),
        ("PT1H", "DATE_ADD(DATE(col), INTERVAL HOUR(col) HOUR)"),
        ("P1D", "DATE(col)"),
        ("P1W", "DATE(DATE_SUB(col, INTERVAL DAYOFWEEK(col) - 1 DAY))"),
        ("P1M", "DATE(DATE_SUB(col, INTERVAL DAYOFMONTH(col) - 1 DAY))"),
        ("P1Y", "DATE(DATE_SUB(col, INTERVAL DAYOFYEAR(col) - 1 DAY))"),
    ],
)
def test_aurora_mysql_timegrain_expressions(
    time_grain: str,
    expected_result: str,
) -> None:
    from superset.db_engine_specs.aurora import AuroraMySQLEngineSpec

    actual = str(
        AuroraMySQLEngineSpec.get_timestamp_expr(
            col=column("col"), pdf=None, time_grain=time_grain
        )
    )
    assert actual == expected_result


# ---------------------------------------------------------------------------
# AuroraPostgresEngineSpec – time grain expressions
# ---------------------------------------------------------------------------
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
def test_aurora_postgres_timegrain_expressions(
    time_grain: str,
    expected_result: str,
) -> None:
    from superset.db_engine_specs.aurora import AuroraPostgresEngineSpec

    actual = str(
        AuroraPostgresEngineSpec.get_timestamp_expr(
            col=column("col"), pdf=None, time_grain=time_grain
        )
    )
    assert actual == expected_result


# ---------------------------------------------------------------------------
# AuroraMySQLEngineSpec – cancel_query / get_cancel_query_id
# ---------------------------------------------------------------------------
@patch("sqlalchemy.engine.Engine.connect")
def test_aurora_mysql_get_cancel_query_id(engine_mock: Mock) -> None:
    from superset.db_engine_specs.aurora import AuroraMySQLEngineSpec
    from superset.models.sql_lab import Query

    query = Query()
    cursor_mock = engine_mock.return_value.__enter__.return_value
    cursor_mock.fetchone.return_value = ["456"]
    assert AuroraMySQLEngineSpec.get_cancel_query_id(cursor_mock, query) == "456"


@patch("sqlalchemy.engine.Engine.connect")
def test_aurora_mysql_cancel_query(engine_mock: Mock) -> None:
    from superset.db_engine_specs.aurora import AuroraMySQLEngineSpec
    from superset.models.sql_lab import Query

    query = Query()
    cursor_mock = engine_mock.return_value.__enter__.return_value
    assert AuroraMySQLEngineSpec.cancel_query(cursor_mock, query, "456") is True


@patch("sqlalchemy.engine.Engine.connect")
def test_aurora_mysql_cancel_query_failed(engine_mock: Mock) -> None:
    from superset.db_engine_specs.aurora import AuroraMySQLEngineSpec
    from superset.models.sql_lab import Query

    query = Query()
    cursor_mock = engine_mock.raiseError.side_effect = Exception()
    assert AuroraMySQLEngineSpec.cancel_query(cursor_mock, query, "456") is False


# ---------------------------------------------------------------------------
# AuroraMySQLEngineSpec – adjust_engine_params (schema support)
# ---------------------------------------------------------------------------
def test_aurora_mysql_adjust_engine_params_with_schema() -> None:
    from superset.db_engine_specs.aurora import AuroraMySQLEngineSpec

    url = make_url("mysql://user:password@host/db1")
    returned_url, returned_connect_args = AuroraMySQLEngineSpec.adjust_engine_params(
        url, {}, schema="my_schema"
    )
    assert returned_url.database == "my_schema"


def test_aurora_mysql_adjust_engine_params_without_schema() -> None:
    from superset.db_engine_specs.aurora import AuroraMySQLEngineSpec

    url = make_url("mysql://user:password@host/db1")
    returned_url, returned_connect_args = AuroraMySQLEngineSpec.adjust_engine_params(
        url, {}
    )
    assert returned_url.database == "db1"


# ---------------------------------------------------------------------------
# AuroraPostgresEngineSpec – adjust_engine_params (catalog support)
# ---------------------------------------------------------------------------
def test_aurora_postgres_adjust_engine_params_with_catalog() -> None:
    from superset.db_engine_specs.aurora import AuroraPostgresEngineSpec

    adjusted = AuroraPostgresEngineSpec.adjust_engine_params(
        make_url("postgresql://user:password@host:5432/dev"),
        {},
        catalog="prod",
    )
    assert adjusted == (make_url("postgresql://user:password@host:5432/prod"), {})


# ---------------------------------------------------------------------------
# AuroraMySQLEngineSpec – get_schema_from_engine_params
# ---------------------------------------------------------------------------
def test_aurora_mysql_get_schema_from_engine_params() -> None:
    from superset.db_engine_specs.aurora import AuroraMySQLEngineSpec

    assert (
        AuroraMySQLEngineSpec.get_schema_from_engine_params(
            make_url("mysql://user:password@host/db1"), {}
        )
        == "db1"
    )


# ---------------------------------------------------------------------------
# AuroraMySQLEngineSpec – validate_database_uri
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "sqlalchemy_uri,error",
    [
        ("mysql://user:password@host/db1?local_infile=1", True),
        ("mysql+mysqlconnector://user:password@host/db1?allow_local_infile=1", True),
        ("mysql://user:password@host/db1", False),
    ],
)
def test_aurora_mysql_validate_database_uri(sqlalchemy_uri: str, error: bool) -> None:
    from superset.db_engine_specs.aurora import AuroraMySQLEngineSpec

    url = make_url(sqlalchemy_uri)
    if error:
        with pytest.raises(ValueError):  # noqa: PT011
            AuroraMySQLEngineSpec.validate_database_uri(url)
        return
    AuroraMySQLEngineSpec.validate_database_uri(url)


# ---------------------------------------------------------------------------
# AuroraMySQLEngineSpec – IAM support (encrypted_extra_sensitive_fields)
# ---------------------------------------------------------------------------
def test_aurora_mysql_has_iam_support() -> None:
    from superset.db_engine_specs.aurora import AuroraMySQLEngineSpec

    assert (
        "$.aws_iam.external_id"
        in AuroraMySQLEngineSpec.encrypted_extra_sensitive_fields
    )
    assert (
        "$.aws_iam.role_arn" in AuroraMySQLEngineSpec.encrypted_extra_sensitive_fields
    )


# ---------------------------------------------------------------------------
# AuroraMySQLEngineSpec – update_params_from_encrypted_extra (without IAM)
# ---------------------------------------------------------------------------
def test_aurora_mysql_update_params_without_iam() -> None:
    from superset.db_engine_specs.aurora import AuroraMySQLEngineSpec

    database = MagicMock()
    database.encrypted_extra = json.dumps({})
    database.sqlalchemy_uri_decrypted = (
        "mysql://user:password@mydb.us-east-1.rds.amazonaws.com:3306/mydb"
    )

    params: dict[str, Any] = {}
    AuroraMySQLEngineSpec.update_params_from_encrypted_extra(database, params)
    assert params == {}


def test_aurora_mysql_update_params_no_encrypted_extra() -> None:
    from superset.db_engine_specs.aurora import AuroraMySQLEngineSpec

    database = MagicMock()
    database.encrypted_extra = None

    params: dict[str, Any] = {}
    AuroraMySQLEngineSpec.update_params_from_encrypted_extra(database, params)
    assert params == {}


def test_aurora_mysql_update_params_invalid_json() -> None:
    from superset.db_engine_specs.aurora import AuroraMySQLEngineSpec

    database = MagicMock()
    database.encrypted_extra = "not-valid-json"

    params: dict[str, Any] = {}
    with pytest.raises(json.JSONDecodeError):
        AuroraMySQLEngineSpec.update_params_from_encrypted_extra(database, params)


def test_aurora_mysql_update_params_iam_disabled() -> None:
    from superset.db_engine_specs.aurora import AuroraMySQLEngineSpec

    database = MagicMock()
    database.encrypted_extra = json.dumps(
        {
            "aws_iam": {
                "enabled": False,
                "role_arn": "arn:aws:iam::123456789012:role/TestRole",
                "region": "us-east-1",
            }
        }
    )
    database.sqlalchemy_uri_decrypted = (
        "mysql://user:password@mydb.us-east-1.rds.amazonaws.com:3306/mydb"
    )

    params: dict[str, Any] = {}
    AuroraMySQLEngineSpec.update_params_from_encrypted_extra(database, params)
    assert params == {}


def test_aurora_mysql_update_params_merges_remaining_extra() -> None:
    from superset.db_engine_specs.aurora import AuroraMySQLEngineSpec

    database = MagicMock()
    database.encrypted_extra = json.dumps(
        {
            "aws_iam": {"enabled": False},
            "pool_size": 5,
        }
    )
    database.sqlalchemy_uri_decrypted = (
        "mysql://user:password@mydb.us-east-1.rds.amazonaws.com:3306/mydb"
    )

    params: dict[str, Any] = {}
    AuroraMySQLEngineSpec.update_params_from_encrypted_extra(database, params)
    assert "aws_iam" not in params
    assert params["pool_size"] == 5


@with_feature_flags(AWS_DATABASE_IAM_AUTH=True)
def test_aurora_mysql_update_params_from_encrypted_extra_with_iam() -> None:
    from superset.db_engine_specs.aurora import AuroraMySQLEngineSpec
    from superset.db_engine_specs.aws_iam import AWSIAMAuthMixin

    database = MagicMock()
    database.encrypted_extra = json.dumps(
        {
            "aws_iam": {
                "enabled": True,
                "role_arn": "arn:aws:iam::123456789012:role/TestRole",
                "region": "us-east-1",
                "db_username": "superset_iam_user",
            }
        }
    )
    database.sqlalchemy_uri_decrypted = (
        "mysql://user@mydb.cluster-xyz.us-east-1.rds.amazonaws.com:3306/mydb"
    )

    params: dict[str, Any] = {}

    with (
        patch.object(
            AWSIAMAuthMixin,
            "get_iam_credentials",
            return_value={
                "AccessKeyId": "ASIA...",
                "SecretAccessKey": "secret...",
                "SessionToken": "token...",
            },
        ),
        patch.object(
            AWSIAMAuthMixin,
            "generate_rds_auth_token",
            return_value="iam-auth-token",
        ),
    ):
        AuroraMySQLEngineSpec.update_params_from_encrypted_extra(database, params)

    assert "connect_args" in params
    assert params["connect_args"]["password"] == "iam-auth-token"  # noqa: S105
    assert params["connect_args"]["user"] == "superset_iam_user"


# ---------------------------------------------------------------------------
# AuroraPostgresEngineSpec – update_params_from_encrypted_extra
# ---------------------------------------------------------------------------
def test_aurora_postgres_update_params_without_iam() -> None:
    from superset.db_engine_specs.postgres import PostgresEngineSpec

    database = MagicMock()
    database.encrypted_extra = json.dumps({})
    database.sqlalchemy_uri_decrypted = (
        "postgresql://user:password@mydb.us-east-1.rds.amazonaws.com:5432/mydb"
    )

    params: dict[str, Any] = {}
    PostgresEngineSpec.update_params_from_encrypted_extra(database, params)
    assert params == {}


def test_aurora_postgres_update_params_iam_disabled() -> None:
    from superset.db_engine_specs.postgres import PostgresEngineSpec

    database = MagicMock()
    database.encrypted_extra = json.dumps(
        {
            "aws_iam": {
                "enabled": False,
                "role_arn": "arn:aws:iam::123456789012:role/TestRole",
                "region": "us-east-1",
                "db_username": "superset_user",
            }
        }
    )
    database.sqlalchemy_uri_decrypted = (
        "postgresql://user:password@mydb.us-east-1.rds.amazonaws.com:5432/mydb"
    )

    params: dict[str, Any] = {}
    PostgresEngineSpec.update_params_from_encrypted_extra(database, params)
    assert params == {}


@with_feature_flags(AWS_DATABASE_IAM_AUTH=True)
def test_aurora_postgres_update_params_with_iam() -> None:
    from superset.db_engine_specs.aws_iam import AWSIAMAuthMixin
    from superset.db_engine_specs.postgres import PostgresEngineSpec

    database = MagicMock()
    database.encrypted_extra = json.dumps(
        {
            "aws_iam": {
                "enabled": True,
                "role_arn": "arn:aws:iam::123456789012:role/TestRole",
                "region": "us-east-1",
                "db_username": "superset_iam_user",
            }
        }
    )
    database.sqlalchemy_uri_decrypted = (
        "postgresql://user@mydb.cluster-xyz.us-east-1.rds.amazonaws.com:5432/mydb"
    )

    params: dict[str, Any] = {}

    with (
        patch.object(
            AWSIAMAuthMixin,
            "get_iam_credentials",
            return_value={
                "AccessKeyId": "ASIA...",
                "SecretAccessKey": "secret...",
                "SessionToken": "token...",
            },
        ),
        patch.object(
            AWSIAMAuthMixin,
            "generate_rds_auth_token",
            return_value="iam-auth-token",
        ),
    ):
        PostgresEngineSpec.update_params_from_encrypted_extra(database, params)

    assert "connect_args" in params
    assert params["connect_args"]["password"] == "iam-auth-token"  # noqa: S105
    assert params["connect_args"]["user"] == "superset_iam_user"
    assert params["connect_args"]["sslmode"] == "require"


def test_aurora_postgres_update_params_merges_remaining_extra() -> None:
    from superset.db_engine_specs.postgres import PostgresEngineSpec

    database = MagicMock()
    database.encrypted_extra = json.dumps(
        {
            "aws_iam": {"enabled": False},
            "pool_size": 10,
        }
    )
    database.sqlalchemy_uri_decrypted = (
        "postgresql://user:password@mydb.us-east-1.rds.amazonaws.com:5432/mydb"
    )

    params: dict[str, Any] = {}
    PostgresEngineSpec.update_params_from_encrypted_extra(database, params)
    assert "aws_iam" not in params
    assert params["pool_size"] == 10


def test_aurora_postgres_update_params_no_encrypted_extra() -> None:
    from superset.db_engine_specs.postgres import PostgresEngineSpec

    database = MagicMock()
    database.encrypted_extra = None

    params: dict[str, Any] = {}
    PostgresEngineSpec.update_params_from_encrypted_extra(database, params)
    assert params == {}


def test_aurora_postgres_update_params_invalid_json() -> None:
    from superset.db_engine_specs.postgres import PostgresEngineSpec

    database = MagicMock()
    database.encrypted_extra = "not-valid-json"

    params: dict[str, Any] = {}
    with pytest.raises(json.JSONDecodeError):
        PostgresEngineSpec.update_params_from_encrypted_extra(database, params)


# ---------------------------------------------------------------------------
# AuroraPostgresEngineSpec – encrypted_extra_sensitive_fields
# ---------------------------------------------------------------------------
def test_aurora_postgres_encrypted_extra_sensitive_fields() -> None:
    from superset.db_engine_specs.postgres import PostgresEngineSpec

    assert (
        "$.aws_iam.external_id" in PostgresEngineSpec.encrypted_extra_sensitive_fields
    )
    assert "$.aws_iam.role_arn" in PostgresEngineSpec.encrypted_extra_sensitive_fields


# ---------------------------------------------------------------------------
# AuroraPostgresEngineSpec – mask_encrypted_extra
# ---------------------------------------------------------------------------
def test_aurora_postgres_mask_encrypted_extra() -> None:
    from superset.db_engine_specs.postgres import PostgresEngineSpec

    encrypted_extra = json.dumps(
        {
            "aws_iam": {
                "enabled": True,
                "role_arn": "arn:aws:iam::123456789012:role/SecretRole",
                "external_id": "secret-external-id-12345",
                "region": "us-east-1",
                "db_username": "superset_user",
            }
        }
    )

    masked = PostgresEngineSpec.mask_encrypted_extra(encrypted_extra)
    assert masked is not None

    masked_config = json.loads(masked)

    assert (
        masked_config["aws_iam"]["role_arn"]
        != "arn:aws:iam::123456789012:role/SecretRole"
    )
    assert masked_config["aws_iam"]["external_id"] != "secret-external-id-12345"

    assert masked_config["aws_iam"]["enabled"] is True
    assert masked_config["aws_iam"]["region"] == "us-east-1"
    assert masked_config["aws_iam"]["db_username"] == "superset_user"


# ---------------------------------------------------------------------------
# AuroraMySQLEngineSpec – adjust_engine_params (local_infile enforcement)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "sqlalchemy_uri,connect_args,returns",
    [
        ("mysql://user:password@host/db1", {"local_infile": 1}, {"local_infile": 0}),
        (
            "mysql+mysqlconnector://user:password@host/db1",
            {"allow_local_infile": 1},
            {"allow_local_infile": 0},
        ),
        ("mysql://user:password@host/db1", {}, {"local_infile": 0}),
    ],
)
def test_aurora_mysql_adjust_engine_params_local_infile(
    sqlalchemy_uri: str,
    connect_args: dict[str, Any],
    returns: dict[str, Any],
) -> None:
    from superset.db_engine_specs.aurora import AuroraMySQLEngineSpec

    url = make_url(sqlalchemy_uri)
    _, returned_connect_args = AuroraMySQLEngineSpec.adjust_engine_params(
        url, connect_args
    )
    assert returned_connect_args == returns
