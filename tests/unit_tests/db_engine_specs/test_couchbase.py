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
from typing import Optional, Union
from unittest.mock import patch

import pytest
from sqlalchemy import types
from sqlalchemy.engine.url import make_url

from superset.db_engine_specs.base import (
    BasicParametersType,
    BasicPropertiesType,
)
from superset.db_engine_specs.couchbase import CouchbaseEngineSpec
from superset.errors import SupersetErrorType
from superset.utils.core import GenericDataType
from tests.unit_tests.db_engine_specs.utils import (
    assert_column_spec,
    assert_convert_dttm,
)
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


def test_engine_attributes() -> None:
    assert CouchbaseEngineSpec.engine == "couchbase"
    assert CouchbaseEngineSpec.engine_aliases == {"couchbasedb"}
    assert CouchbaseEngineSpec.engine_name == "Couchbase"
    assert CouchbaseEngineSpec.default_driver == "couchbase"
    assert CouchbaseEngineSpec.allows_joins is False
    assert CouchbaseEngineSpec.allows_subqueries is False


def test_epoch_to_dttm() -> None:
    assert CouchbaseEngineSpec.epoch_to_dttm() == "MILLIS_TO_STR({col} * 1000)"


def test_epoch_ms_to_dttm() -> None:
    assert CouchbaseEngineSpec.epoch_ms_to_dttm() == "MILLIS_TO_STR({col})"


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Date", "DATETIME(DATE_FORMAT_STR(STR_TO_UTC('2019-01-02'), 'iso8601'))"),
        (
            "DateTime",
            "DATETIME(DATE_FORMAT_STR(STR_TO_UTC('2019-01-02T03:04:05'), 'iso8601'))",
        ),
        (
            "TimeStamp",
            "DATETIME(DATE_FORMAT_STR(STR_TO_UTC('2019-01-02T03:04:05'), 'iso8601'))",
        ),
        (
            "OTHER",
            "DATETIME(DATE_FORMAT_STR(STR_TO_UTC('2019-01-02T03:04:05'), 'iso8601'))",
        ),
    ],
)
def test_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    assert_convert_dttm(CouchbaseEngineSpec, target_type, expected_result, dttm)


def test_convert_dttm_date_only(
    dttm: datetime,  # noqa: F811
) -> None:
    result = CouchbaseEngineSpec.convert_dttm("date", dttm)
    assert result == "DATETIME(DATE_FORMAT_STR(STR_TO_UTC('2019-01-02'), 'iso8601'))"


def test_convert_dttm_non_date(
    dttm: datetime,  # noqa: F811
) -> None:
    result = CouchbaseEngineSpec.convert_dttm("timestamp", dttm)
    assert "2019-01-02T03:04:05" in (result or "")


def test_time_grain_expressions() -> None:
    from superset.constants import TimeGrain

    tge = CouchbaseEngineSpec._time_grain_expressions
    assert tge[None] == "{col}"
    assert tge[TimeGrain.SECOND] == "DATE_TRUNC_STR(TOSTRING({col}),'second')"
    assert tge[TimeGrain.MINUTE] == "DATE_TRUNC_STR(TOSTRING({col}),'minute')"
    assert tge[TimeGrain.HOUR] == "DATE_TRUNC_STR(TOSTRING({col}),'hour')"
    assert tge[TimeGrain.DAY] == "DATE_TRUNC_STR(TOSTRING({col}),'day')"
    assert tge[TimeGrain.MONTH] == "DATE_TRUNC_STR(TOSTRING({col}),'month')"
    assert tge[TimeGrain.YEAR] == "DATE_TRUNC_STR(TOSTRING({col}),'year')"
    assert tge[TimeGrain.QUARTER] == "DATE_TRUNC_STR(TOSTRING({col}),'quarter')"


@pytest.mark.parametrize(
    "native_type,sqla_type,attrs,generic_type,is_dttm",
    [
        ("SMALLINT", types.SmallInteger, None, GenericDataType.NUMERIC, False),
        ("INTEGER", types.Integer, None, GenericDataType.NUMERIC, False),
        ("BIGINT", types.BigInteger, None, GenericDataType.NUMERIC, False),
        ("DECIMAL", types.Numeric, None, GenericDataType.NUMERIC, False),
        ("NUMERIC", types.Numeric, None, GenericDataType.NUMERIC, False),
        ("CHAR", types.String, None, GenericDataType.STRING, False),
        ("VARCHAR", types.String, None, GenericDataType.STRING, False),
        ("TEXT", types.String, None, GenericDataType.STRING, False),
        ("BOOLEAN", types.Boolean, None, GenericDataType.BOOLEAN, False),
    ],
)
def test_get_column_spec(
    native_type: str,
    sqla_type: type[types.TypeEngine],
    attrs: Union[dict[str, str], None],
    generic_type: GenericDataType,
    is_dttm: bool,
) -> None:
    assert_column_spec(
        CouchbaseEngineSpec, native_type, sqla_type, attrs, generic_type, is_dttm
    )


def test_build_sqlalchemy_uri_with_encryption() -> None:
    parameters = BasicParametersType(
        username="admin",
        password="secret",  # noqa: S106
        host="localhost",
        port=8091,
        database="",
        query={},
        encryption=True,
    )
    uri = CouchbaseEngineSpec.build_sqlalchemy_uri(parameters)
    assert "couchbase://" in uri
    assert "admin" in uri
    assert "localhost" in uri
    assert "8091" in uri
    assert "ssl=true" in uri


def test_build_sqlalchemy_uri_without_encryption() -> None:
    parameters = BasicParametersType(
        username="admin",
        password="secret",  # noqa: S106
        host="localhost",
        port=8091,
        database="",
        query={},
        encryption=False,
    )
    uri = CouchbaseEngineSpec.build_sqlalchemy_uri(parameters)
    assert "ssl=false" in uri


def test_build_sqlalchemy_uri_no_port() -> None:
    parameters = BasicParametersType(
        username="admin",
        password="secret",  # noqa: S106
        host="cb.example.com",
        database="",
        query={},
        encryption=True,
    )
    uri = CouchbaseEngineSpec.build_sqlalchemy_uri(parameters)
    parsed = make_url(uri)
    assert parsed.host == "cb.example.com"
    assert "ssl=true" in uri


def test_build_sqlalchemy_uri_with_extra_query_params() -> None:
    parameters = BasicParametersType(
        username="admin",
        password="secret",  # noqa: S106
        host="localhost",
        port=8091,
        database="",
        query={"truststorepath": "/path/to/cert"},
        encryption=True,
    )
    uri = CouchbaseEngineSpec.build_sqlalchemy_uri(parameters)
    assert "truststorepath" in uri
    assert "ssl=true" in uri


def test_get_parameters_from_uri_basic() -> None:
    uri = "couchbase://admin:secret@localhost:8091/?ssl=true"
    params = CouchbaseEngineSpec.get_parameters_from_uri(uri)
    assert params["username"] == "admin"
    assert params["password"] == "secret"  # noqa: S105
    assert params["host"] == "localhost"
    assert params["port"] == 8091
    assert params["encryption"] is True


def test_get_parameters_from_uri_no_ssl() -> None:
    uri = "couchbase://admin:secret@localhost:8091/?ssl=false"
    params = CouchbaseEngineSpec.get_parameters_from_uri(uri)
    assert params["encryption"] is False


def test_get_parameters_from_uri_missing_ssl() -> None:
    uri = "couchbase://admin:secret@localhost:8091/"
    params = CouchbaseEngineSpec.get_parameters_from_uri(uri)
    assert params["encryption"] is False


def test_validate_parameters_all_present() -> None:
    properties = BasicPropertiesType(
        parameters=BasicParametersType(
            host="localhost",
            username="admin",
            password="secret",  # noqa: S106
            database="mybucket",
        )
    )
    with patch(
        "superset.db_engine_specs.couchbase.is_hostname_valid", return_value=True
    ):
        errors = CouchbaseEngineSpec.validate_parameters(properties)
    assert len(errors) == 0


def test_validate_parameters_missing_fields() -> None:
    properties = BasicPropertiesType(
        parameters=BasicParametersType(
            host="",
            username="",
            password="",
            database="",
        )
    )
    errors = CouchbaseEngineSpec.validate_parameters(properties)
    assert len(errors) == 1
    assert errors[0].error_type == SupersetErrorType.CONNECTION_MISSING_PARAMETERS_ERROR
    extra = errors[0].extra
    assert extra is not None
    missing = extra["missing"]
    assert "host" in missing
    assert "username" in missing
    assert "password" in missing
    assert "database" in missing


def test_validate_parameters_missing_host_returns_early() -> None:
    properties = BasicPropertiesType(
        parameters=BasicParametersType(
            host="",
            username="admin",
            password="secret",  # noqa: S106
            database="mybucket",
        )
    )
    errors = CouchbaseEngineSpec.validate_parameters(properties)
    assert len(errors) == 1
    assert errors[0].error_type == SupersetErrorType.CONNECTION_MISSING_PARAMETERS_ERROR


def test_validate_parameters_invalid_hostname() -> None:
    properties = BasicPropertiesType(
        parameters=BasicParametersType(
            host="not-a-real-host.invalid",
            username="admin",
            password="secret",  # noqa: S106
            database="mybucket",
        )
    )
    with patch(
        "superset.db_engine_specs.couchbase.is_hostname_valid", return_value=False
    ):
        errors = CouchbaseEngineSpec.validate_parameters(properties)
    assert len(errors) == 1
    assert errors[0].error_type == SupersetErrorType.CONNECTION_INVALID_HOSTNAME_ERROR


def test_validate_parameters_invalid_port_type() -> None:
    properties = BasicPropertiesType(
        parameters=BasicParametersType(
            host="localhost",
            username="admin",
            password="secret",  # noqa: S106
            database="mybucket",
            port="not_a_number",  # type: ignore[typeddict-item]
        )
    )
    with patch(
        "superset.db_engine_specs.couchbase.is_hostname_valid", return_value=True
    ):
        errors = CouchbaseEngineSpec.validate_parameters(properties)
    assert len(errors) >= 1
    error_types = [e.error_type for e in errors]
    assert SupersetErrorType.CONNECTION_INVALID_PORT_ERROR in error_types


def test_validate_parameters_port_out_of_range() -> None:
    properties = BasicPropertiesType(
        parameters=BasicParametersType(
            host="localhost",
            username="admin",
            password="secret",  # noqa: S106
            database="mybucket",
            port=70000,
        )
    )
    with patch(
        "superset.db_engine_specs.couchbase.is_hostname_valid", return_value=True
    ):
        errors = CouchbaseEngineSpec.validate_parameters(properties)
    assert len(errors) == 1
    assert errors[0].error_type == SupersetErrorType.CONNECTION_INVALID_PORT_ERROR
    assert "65535" in errors[0].message


def test_validate_parameters_port_negative() -> None:
    properties = BasicPropertiesType(
        parameters=BasicParametersType(
            host="localhost",
            username="admin",
            password="secret",  # noqa: S106
            database="mybucket",
            port=-1,
        )
    )
    with patch(
        "superset.db_engine_specs.couchbase.is_hostname_valid", return_value=True
    ):
        errors = CouchbaseEngineSpec.validate_parameters(properties)
    assert len(errors) == 1
    assert errors[0].error_type == SupersetErrorType.CONNECTION_INVALID_PORT_ERROR


def test_validate_parameters_port_closed() -> None:
    properties = BasicPropertiesType(
        parameters=BasicParametersType(
            host="localhost",
            username="admin",
            password="secret",  # noqa: S106
            database="mybucket",
            port=9999,
        )
    )
    with (
        patch(
            "superset.db_engine_specs.couchbase.is_hostname_valid", return_value=True
        ),
        patch("superset.db_engine_specs.couchbase.is_port_open", return_value=False),
    ):
        errors = CouchbaseEngineSpec.validate_parameters(properties)
    assert len(errors) == 1
    assert errors[0].error_type == SupersetErrorType.CONNECTION_PORT_CLOSED_ERROR


def test_validate_parameters_port_open() -> None:
    properties = BasicPropertiesType(
        parameters=BasicParametersType(
            host="localhost",
            username="admin",
            password="secret",  # noqa: S106
            database="mybucket",
            port=8091,
        )
    )
    with (
        patch(
            "superset.db_engine_specs.couchbase.is_hostname_valid", return_value=True
        ),
        patch("superset.db_engine_specs.couchbase.is_port_open", return_value=True),
    ):
        errors = CouchbaseEngineSpec.validate_parameters(properties)
    assert len(errors) == 0


def test_validate_parameters_empty_parameters() -> None:
    properties = BasicPropertiesType(
        parameters=BasicParametersType(host=""),
    )
    errors = CouchbaseEngineSpec.validate_parameters(properties)
    assert len(errors) == 1
    assert errors[0].error_type == SupersetErrorType.CONNECTION_MISSING_PARAMETERS_ERROR
    extra = errors[0].extra
    assert extra is not None
    missing = extra["missing"]
    assert sorted(missing) == ["database", "host", "password", "username"]


def test_get_schema_from_engine_params() -> None:
    url = make_url("couchbase://admin:secret@localhost:8091/mybucket")
    schema = CouchbaseEngineSpec.get_schema_from_engine_params(url, {})
    assert schema == "mybucket"


def test_get_schema_from_engine_params_encoded() -> None:
    url = make_url("couchbase://admin:secret@localhost:8091/my%20bucket")
    schema = CouchbaseEngineSpec.get_schema_from_engine_params(url, {})
    assert schema == "my bucket"


def test_parameters_schema_validates() -> None:
    schema = CouchbaseEngineSpec.parameters_schema
    result = schema.load(
        {
            "host": "localhost",
            "port": 8091,
            "username": "admin",
            "password": "secret",
            "encryption": True,
        }
    )
    assert result["host"] == "localhost"
    assert result["port"] == 8091
    assert result["encryption"] is True


def test_parameters_schema_defaults() -> None:
    schema = CouchbaseEngineSpec.parameters_schema
    result = schema.load({"host": "localhost"})
    assert result.get("encryption", False) is False


def test_metadata_attributes() -> None:
    meta = CouchbaseEngineSpec.metadata
    assert "Couchbase" in meta["description"]
    assert meta["default_port"] == 8091
    assert len(meta["drivers"]) == 1
    assert meta["drivers"][0]["is_recommended"] is True
