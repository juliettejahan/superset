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
import unittest.mock as mock
from datetime import datetime
from textwrap import dedent
from typing import Any, Optional

import pytest
from sqlalchemy import column, table
from sqlalchemy.dialects import mssql
from sqlalchemy.dialects.mssql import DATE, NTEXT, NVARCHAR, TEXT, VARCHAR
from sqlalchemy.sql import select
from sqlalchemy.types import String, TypeEngine, UnicodeText

from superset.errors import ErrorLevel, SupersetError, SupersetErrorType
from superset.models.sql_types.mssql_sql_types import GUID
from superset.utils.core import GenericDataType
from tests.unit_tests.db_engine_specs.utils import (
    assert_column_spec,
    assert_convert_dttm,
)
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


@pytest.mark.parametrize(
    "native_type,sqla_type,attrs,generic_type,is_dttm",
    [
        ("CHAR", String, None, GenericDataType.STRING, False),
        ("CHAR(10)", String, None, GenericDataType.STRING, False),
        ("VARCHAR", String, None, GenericDataType.STRING, False),
        ("VARCHAR(10)", String, None, GenericDataType.STRING, False),
        ("TEXT", String, None, GenericDataType.STRING, False),
        ("NCHAR(10)", UnicodeText, None, GenericDataType.STRING, False),
        ("NVARCHAR(10)", UnicodeText, None, GenericDataType.STRING, False),
        ("NTEXT", UnicodeText, None, GenericDataType.STRING, False),
        ("uniqueidentifier", GUID, None, GenericDataType.STRING, False),
    ],
)
def test_get_column_spec(
    native_type: str,
    sqla_type: type[TypeEngine],
    attrs: Optional[dict[str, Any]],
    generic_type: GenericDataType,
    is_dttm: bool,
) -> None:
    from superset.db_engine_specs.mssql import MssqlEngineSpec as spec  # noqa: N813

    assert_column_spec(spec, native_type, sqla_type, attrs, generic_type, is_dttm)


def test_where_clause_n_prefix() -> None:
    from superset.db_engine_specs.mssql import MssqlEngineSpec

    dialect = mssql.dialect()

    # non-unicode col
    sqla_column_type = MssqlEngineSpec.get_column_types("VARCHAR(10)")
    assert sqla_column_type is not None
    type_, _ = sqla_column_type
    str_col = column("col", type_=type_)

    # unicode col
    sqla_column_type = MssqlEngineSpec.get_column_types("NTEXT")
    assert sqla_column_type is not None
    type_, _ = sqla_column_type
    unicode_col = column("unicode_col", type_=type_)

    tbl = table("tbl")
    sel = (
        select([str_col, unicode_col])
        .select_from(tbl)
        .where(str_col == "abc")
        .where(unicode_col == "abc")
    )

    query = str(sel.compile(dialect=dialect, compile_kwargs={"literal_binds": True}))
    query_expected = (
        "SELECT col, unicode_col \n"
        "FROM tbl \n"
        "WHERE col = 'abc' AND unicode_col = N'abc'"
    )
    assert query == query_expected


def test_time_exp_mixed_case_col_1y() -> None:
    from superset.db_engine_specs.mssql import MssqlEngineSpec

    col = column("MixedCase")
    expr = MssqlEngineSpec.get_timestamp_expr(col, None, "P1Y")
    result = str(expr.compile(None, dialect=mssql.dialect()))
    assert result == "DATEADD(YEAR, DATEDIFF(YEAR, 0, [MixedCase]), 0)"


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        (
            "date",
            "CONVERT(DATE, '2019-01-02', 23)",
        ),
        (
            "datetime",
            "CONVERT(DATETIME, '2019-01-02T03:04:05.678', 126)",
        ),
        (
            "smalldatetime",
            "CONVERT(SMALLDATETIME, '2019-01-02 03:04:05', 20)",
        ),
        ("Other", None),
    ],
)
def test_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    from superset.db_engine_specs.mssql import MssqlEngineSpec as spec  # noqa: N813

    assert_convert_dttm(spec, target_type, expected_result, dttm)


def test_extract_error_message() -> None:
    from superset.db_engine_specs.mssql import MssqlEngineSpec

    test_mssql_exception = Exception(
        "(8155, b\"No column name was specified for column 1 of 'inner_qry'."
        "DB-Lib error message 20018, severity 16:\\nGeneral SQL Server error: "
        'Check messages from the SQL Server\\n")'
    )
    error_message = MssqlEngineSpec.extract_error_message(test_mssql_exception)
    expected_message = (
        "mssql error: All your SQL functions need to "
        "have an alias on MSSQL. For example: SELECT COUNT(*) AS C1 FROM TABLE1"
    )
    assert expected_message == error_message

    test_mssql_exception = Exception(
        '(8200, b"A correlated expression is invalid because it is not in a '
        "GROUP BY clause.\\n\")'"
    )
    error_message = MssqlEngineSpec.extract_error_message(test_mssql_exception)
    expected_message = "mssql error: " + MssqlEngineSpec._extract_error_message(
        test_mssql_exception
    )
    assert expected_message == error_message


def test_fetch_data_no_description() -> None:
    from superset.db_engine_specs.mssql import MssqlEngineSpec

    cursor = mock.MagicMock()
    cursor.description = []
    assert MssqlEngineSpec.fetch_data(cursor) == []


def test_fetch_data() -> None:
    from superset.db_engine_specs.base import BaseEngineSpec
    from superset.db_engine_specs.mssql import MssqlEngineSpec

    with mock.patch.object(
        MssqlEngineSpec,
        "pyodbc_rows_to_tuples",
        return_value="converted",
    ) as mock_pyodbc_rows_to_tuples:
        cursor = mock.MagicMock()
        data = [(1, "foo")]
        with mock.patch.object(BaseEngineSpec, "fetch_data", return_value=data):
            result = MssqlEngineSpec.fetch_data(cursor, 0)
            mock_pyodbc_rows_to_tuples.assert_called_once_with(data)
            assert result == "converted"


@pytest.mark.parametrize(
    "original,expected",
    [
        (DATE(), "DATE"),
        (VARCHAR(length=255), "VARCHAR(255)"),
        (VARCHAR(length=255, collation="utf8_general_ci"), "VARCHAR(255)"),
        (NVARCHAR(length=128), "NVARCHAR(128)"),
        (TEXT(), "TEXT"),
        (NTEXT(collation="utf8_general_ci"), "NTEXT"),
    ],
)
def test_column_datatype_to_string(original: TypeEngine, expected: str) -> None:
    from superset.db_engine_specs.mssql import MssqlEngineSpec

    actual = MssqlEngineSpec.column_datatype_to_string(original, mssql.dialect())
    assert actual == expected


@pytest.mark.parametrize(
    "original,expected",
    [
        (
            dedent(
                """
with currency as (
select 'INR' as cur
),
currency_2 as (
select 'EUR' as cur
)
select * from currency union all select * from currency_2
"""
            ),
            """WITH currency AS (
  SELECT
    'INR' AS cur
), currency_2 AS (
  SELECT
    'EUR' AS cur
), __cte AS (
  SELECT
    *
  FROM currency
  UNION ALL
  SELECT
    *
  FROM currency_2
)""",
        ),
        (
            "SELECT 1 as cnt",
            None,
        ),
        (
            dedent(
                """
select 'INR' as cur
union
select 'AUD' as cur
union
select 'USD' as cur
"""
            ),
            None,
        ),
    ],
)
def test_cte_query_parsing(original: TypeEngine, expected: str) -> None:
    from superset.db_engine_specs.mssql import MssqlEngineSpec

    actual = MssqlEngineSpec.get_cte_query(original)
    assert actual == expected


def test_extract_errors() -> None:
    """
    Test that custom error messages are extracted correctly.
    """
    from superset.db_engine_specs.mssql import MssqlEngineSpec

    msg = dedent(
        """
DB-Lib error message 20009, severity 9:
Unable to connect: Adaptive Server is unavailable or does not exist (localhost_)
        """
    )
    result = MssqlEngineSpec.extract_errors(Exception(msg))
    assert result == [
        SupersetError(
            error_type=SupersetErrorType.CONNECTION_INVALID_HOSTNAME_ERROR,
            message='The hostname "localhost_" cannot be resolved.',
            level=ErrorLevel.ERROR,
            extra={
                "engine_name": "Microsoft SQL Server",
                "issue_codes": [
                    {
                        "code": 1007,
                        "message": "Issue 1007 - The hostname provided can't be resolved.",  # noqa: E501
                    }
                ],
            },
        )
    ]

    msg = dedent(
        """
DB-Lib error message 20009, severity 9:
Unable to connect: Adaptive Server is unavailable or does not exist (localhost)
Net-Lib error during Connection refused (61)
DB-Lib error message 20009, severity 9:
Unable to connect: Adaptive Server is unavailable or does not exist (localhost)
Net-Lib error during Connection refused (61)
        """
    )
    result = MssqlEngineSpec.extract_errors(
        Exception(msg), context={"port": 12345, "hostname": "localhost"}
    )
    assert result == [
        SupersetError(
            error_type=SupersetErrorType.CONNECTION_PORT_CLOSED_ERROR,
            message='Port 12345 on hostname "localhost" refused the connection.',
            level=ErrorLevel.ERROR,
            extra={
                "engine_name": "Microsoft SQL Server",
                "issue_codes": [
                    {"code": 1008, "message": "Issue 1008 - The port is closed."}
                ],
            },
        )
    ]

    msg = dedent(
        """
DB-Lib error message 20009, severity 9:
Unable to connect: Adaptive Server is unavailable or does not exist (example.com)
Net-Lib error during Operation timed out (60)
DB-Lib error message 20009, severity 9:
Unable to connect: Adaptive Server is unavailable or does not exist (example.com)
Net-Lib error during Operation timed out (60)
        """
    )
    result = MssqlEngineSpec.extract_errors(
        Exception(msg), context={"port": 12345, "hostname": "example.com"}
    )
    assert result == [
        SupersetError(
            error_type=SupersetErrorType.CONNECTION_HOST_DOWN_ERROR,
            message=(
                'The host "example.com" might be down, '
                "and can't be reached on port 12345."
            ),
            level=ErrorLevel.ERROR,
            extra={
                "engine_name": "Microsoft SQL Server",
                "issue_codes": [
                    {
                        "code": 1009,
                        "message": "Issue 1009 - The host might be down, and can't be reached on the provided port.",  # noqa: E501
                    }
                ],
            },
        )
    ]

    msg = dedent(
        """
DB-Lib error message 20009, severity 9:
Unable to connect: Adaptive Server is unavailable or does not exist (93.184.216.34)
Net-Lib error during Operation timed out (60)
DB-Lib error message 20009, severity 9:
Unable to connect: Adaptive Server is unavailable or does not exist (93.184.216.34)
Net-Lib error during Operation timed out (60)
        """
    )
    result = MssqlEngineSpec.extract_errors(
        Exception(msg), context={"port": 12345, "hostname": "93.184.216.34"}
    )
    assert result == [
        SupersetError(
            error_type=SupersetErrorType.CONNECTION_HOST_DOWN_ERROR,
            message=(
                'The host "93.184.216.34" might be down, '
                "and can't be reached on port 12345."
            ),
            level=ErrorLevel.ERROR,
            extra={
                "engine_name": "Microsoft SQL Server",
                "issue_codes": [
                    {
                        "code": 1009,
                        "message": "Issue 1009 - The host might be down, and can't be reached on the provided port.",  # noqa: E501
                    }
                ],
            },
        )
    ]

    msg = dedent(
        """
DB-Lib error message 20018, severity 14:
General SQL Server error: Check messages from the SQL Server
DB-Lib error message 20002, severity 9:
Adaptive Server connection failed (mssqldb.cxiotftzsypc.us-west-2.rds.amazonaws.com)
DB-Lib error message 20002, severity 9:
Adaptive Server connection failed (mssqldb.cxiotftzsypc.us-west-2.rds.amazonaws.com)
        """
    )
    result = MssqlEngineSpec.extract_errors(
        Exception(msg), context={"username": "testuser", "database": "testdb"}
    )
    assert result == [
        SupersetError(
            message='Either the username "testuser", password, or database name "testdb" is incorrect.',  # noqa: E501
            error_type=SupersetErrorType.CONNECTION_ACCESS_DENIED_ERROR,
            level=ErrorLevel.ERROR,
            extra={
                "engine_name": "Microsoft SQL Server",
                "issue_codes": [
                    {
                        "code": 1014,
                        "message": "Issue 1014 - Either the username or "
                        "the password is wrong.",
                    },
                    {
                        "code": 1015,
                        "message": "Issue 1015 - Either the database is "
                        "spelled incorrectly or does not exist.",
                    },
                ],
            },
        )
    ]


@pytest.mark.parametrize(
    "name,expected_result",
    [
        ("col", "col"),
        ("Col", "Col"),
        ("COL", "COL"),
    ],
)
def test_denormalize_name(name: str, expected_result: str):
    from superset.db_engine_specs.mssql import MssqlEngineSpec as spec  # noqa: N813

    assert spec.denormalize_name(mssql.dialect(), name) == expected_result


def test_epoch_to_dttm() -> None:
    """
    Test the `epoch_to_dttm` method returns the expected SQL expression.
    """
    from superset.db_engine_specs.mssql import MssqlEngineSpec

    assert MssqlEngineSpec.epoch_to_dttm() == "dateadd(S, {col}, '1970-01-01')"
    assert (
        MssqlEngineSpec.epoch_to_dttm().format(col="ts_col")
        == "dateadd(S, ts_col, '1970-01-01')"
    )


def test_engine_class_attributes() -> None:
    """
    Verify static class attributes that affect query generation behavior.
    """
    from superset.db_engine_specs.mssql import MssqlEngineSpec

    assert MssqlEngineSpec.engine == "mssql"
    assert MssqlEngineSpec.engine_name == "Microsoft SQL Server"
    assert MssqlEngineSpec.max_column_name_length == 128
    assert MssqlEngineSpec.allows_cte_in_subquery is False
    assert MssqlEngineSpec.supports_multivalues_insert is True


@pytest.mark.parametrize(
    "time_grain,expected_fragment",
    [
        ("PT1S", "DATEADD(SECOND,"),
        ("PT1M", "DATEADD(MINUTE, DATEDIFF(MINUTE, 0, [MixedCase]), 0)"),
        ("PT5M", "/ 5 * 5, 0)"),
        ("PT10M", "/ 10 * 10, 0)"),
        ("PT15M", "/ 15 * 15, 0)"),
        ("PT30M", "/ 30 * 30, 0)"),
        ("PT1H", "DATEADD(HOUR, DATEDIFF(HOUR, 0, [MixedCase]), 0)"),
        ("P1D", "DATEADD(DAY, DATEDIFF(DAY, 0, [MixedCase]), 0)"),
        ("P1W", "DATEPART(WEEKDAY, [MixedCase])"),
        ("P1M", "DATEADD(MONTH, DATEDIFF(MONTH, 0, [MixedCase]), 0)"),
        ("P3M", "DATEADD(QUARTER, DATEDIFF(QUARTER, 0, [MixedCase]), 0)"),
        ("P1Y", "DATEADD(YEAR, DATEDIFF(YEAR, 0, [MixedCase]), 0)"),
        (
            "1969-12-28T00:00:00Z/P1W",
            "DATEADD(DAY, -1, DATEADD(WEEK, DATEDIFF(WEEK, 0, [MixedCase]), 0))",
        ),
        (
            "1969-12-29T00:00:00Z/P1W",
            "DATEADD(WEEK, DATEDIFF(WEEK, 0, DATEADD(DAY, -1, [MixedCase])), 0)",
        ),
    ],
)
def test_time_grain_expressions(time_grain: str, expected_fragment: str) -> None:
    """
    Verify each supported `_time_grain_expressions` compiles and contains the
    expected SQL fragment.
    """
    from superset.db_engine_specs.mssql import MssqlEngineSpec

    col = column("MixedCase")
    expr = MssqlEngineSpec.get_timestamp_expr(col, None, time_grain)
    result = str(expr.compile(None, dialect=mssql.dialect()))
    assert expected_fragment in result


def test_time_grain_none_returns_column() -> None:
    """
    A `None` time grain should pass through the column expression unchanged.
    """
    from superset.db_engine_specs.mssql import MssqlEngineSpec

    col = column("MixedCase")
    expr = MssqlEngineSpec.get_timestamp_expr(col, None, None)
    result = str(expr.compile(None, dialect=mssql.dialect()))
    assert result == "[MixedCase]"


def test_convert_dttm_unknown_type() -> None:
    """
    Unknown column types should return None instead of raising.
    """
    from superset.db_engine_specs.mssql import MssqlEngineSpec

    target = datetime(2023, 6, 15, 12, 0, 0)
    assert MssqlEngineSpec.convert_dttm("UNKNOWN_TYPE", target) is None


def test_convert_dttm_with_db_extra() -> None:
    """
    Passing a `db_extra` argument should not affect the conversion result.
    """
    from superset.db_engine_specs.mssql import MssqlEngineSpec

    target = datetime(2024, 12, 31, 23, 59, 59, 999000)
    assert (
        MssqlEngineSpec.convert_dttm("DATE", target, db_extra={"engine_params": {}})
        == "CONVERT(DATE, '2024-12-31', 23)"
    )


def test_convert_dttm_datetime_microseconds_truncated_to_milliseconds() -> None:
    """
    `DATETIME` conversion should keep millisecond precision (truncate microseconds).
    """
    from superset.db_engine_specs.mssql import MssqlEngineSpec

    target = datetime(2024, 1, 2, 3, 4, 5, 678999)
    assert (
        MssqlEngineSpec.convert_dttm("DATETIME", target)
        == "CONVERT(DATETIME, '2024-01-02T03:04:05.678', 126)"
    )


def test_convert_dttm_smalldatetime_drops_subseconds() -> None:
    """
    `SMALLDATETIME` conversion uses 'YYYY-MM-DD HH:MM:SS' (no subseconds).
    """
    from superset.db_engine_specs.mssql import MssqlEngineSpec

    target = datetime(2024, 1, 2, 3, 4, 5, 678999)
    assert (
        MssqlEngineSpec.convert_dttm("smalldatetime", target)
        == "CONVERT(SMALLDATETIME, '2024-01-02 03:04:05', 20)"
    )


def test_convert_dttm_date_ignores_time_component() -> None:
    """
    `DATE` conversion should use only the calendar date part of the datetime.
    """
    from superset.db_engine_specs.mssql import MssqlEngineSpec

    target = datetime(2024, 7, 4, 23, 59, 59, 999999)
    assert (
        MssqlEngineSpec.convert_dttm("DATE", target)
        == "CONVERT(DATE, '2024-07-04', 23)"
    )


def test_extract_error_message_no_match() -> None:
    """
    `extract_error_message` should fall back to the generic prefix for non-8155
    errors.
    """
    from superset.db_engine_specs.mssql import MssqlEngineSpec

    ex = Exception("Some unrelated error message")
    result = MssqlEngineSpec.extract_error_message(ex)
    assert result.startswith("mssql error: ")
    assert "Some unrelated error message" in result


def test_get_dbapi_exception_mapping_inherits_default() -> None:
    """
    `MssqlEngineSpec` does not override `get_dbapi_exception_mapping`, so it
    should return the (empty) mapping from the base class.
    """
    from superset.db_engine_specs.mssql import MssqlEngineSpec

    mapping = MssqlEngineSpec.get_dbapi_exception_mapping()
    assert isinstance(mapping, dict)


def test_smalldatetime_column_type_mapping() -> None:
    """
    `smalldatetime` native type should map to `SMALLDATETIME` and be flagged as
    a temporal type.
    """
    from sqlalchemy.dialects.mssql.base import SMALLDATETIME

    from superset.db_engine_specs.mssql import MssqlEngineSpec

    column_spec = MssqlEngineSpec.get_column_spec("smalldatetime")
    assert column_spec is not None
    assert isinstance(column_spec.sqla_type, SMALLDATETIME)
    assert column_spec.generic_type == GenericDataType.TEMPORAL
    assert column_spec.is_dttm is True


def test_uniqueidentifier_column_type_mapping() -> None:
    """
    `uniqueidentifier` native type should map to the custom `GUID` type and be
    treated as a string column.
    """
    from superset.db_engine_specs.mssql import MssqlEngineSpec

    column_spec = MssqlEngineSpec.get_column_spec("uniqueidentifier")
    assert column_spec is not None
    assert isinstance(column_spec.sqla_type, GUID)
    assert column_spec.generic_type == GenericDataType.STRING
    assert column_spec.is_dttm is False


def test_extract_errors_unrecognized_message() -> None:
    """
    Unrecognized errors should fall back to the base class default extraction
    (a single generic Superset error).
    """
    from superset.db_engine_specs.mssql import MssqlEngineSpec

    msg = "Some completely unrelated error that no regex matches"
    result = MssqlEngineSpec.extract_errors(Exception(msg))
    assert len(result) == 1
    assert result[0].error_type == SupersetErrorType.GENERIC_DB_ENGINE_ERROR


def test_azure_synapse_spec_attributes() -> None:
    """
    `AzureSynapseSpec` shares the mssql engine but advertises a different
    engine name, default driver, and metadata.
    """
    from superset.db_engine_specs.mssql import AzureSynapseSpec, MssqlEngineSpec

    assert issubclass(AzureSynapseSpec, MssqlEngineSpec)
    assert AzureSynapseSpec.engine == "mssql"
    assert AzureSynapseSpec.engine_name == "Azure Synapse"
    assert AzureSynapseSpec.default_driver == "pyodbc"
    assert "Azure Synapse Analytics" in AzureSynapseSpec.metadata["description"]
    assert AzureSynapseSpec.metadata["logo"] == "azure.svg"


def test_azure_synapse_inherits_convert_dttm(
    dttm: datetime,  # noqa: F811
) -> None:
    """
    `AzureSynapseSpec` should inherit `convert_dttm` semantics from MssqlEngineSpec.
    """
    from superset.db_engine_specs.mssql import AzureSynapseSpec

    assert (
        AzureSynapseSpec.convert_dttm("DATE", dttm) == "CONVERT(DATE, '2019-01-02', 23)"
    )
    assert (
        AzureSynapseSpec.convert_dttm("DATETIME", dttm)
        == "CONVERT(DATETIME, '2019-01-02T03:04:05.678', 126)"
    )
    assert AzureSynapseSpec.convert_dttm("OTHER", dttm) is None


def test_azure_synapse_epoch_to_dttm() -> None:
    """
    `AzureSynapseSpec.epoch_to_dttm` should match MssqlEngineSpec's expression.
    """
    from superset.db_engine_specs.mssql import AzureSynapseSpec

    assert AzureSynapseSpec.epoch_to_dttm() == "dateadd(S, {col}, '1970-01-01')"
