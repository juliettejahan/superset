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
from unittest.mock import MagicMock

import pandas as pd
import pytest
from pytest_mock import MockerFixture
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.engine.url import make_url
from sqlalchemy.sql import select

from superset.exceptions import SupersetException
from superset.sql.parse import Table
from superset.superset_typing import ResultSetColumnType
from tests.unit_tests.db_engine_specs.utils import assert_convert_dttm
from tests.unit_tests.fixtures.common import dttm  # noqa: F401


@pytest.mark.parametrize(
    "target_type,expected_result",
    [
        ("Date", "CAST('2019-01-02' AS DATE)"),
        (
            "TimeStamp",
            "CAST('2019-01-02 03:04:05.678900' AS TIMESTAMP)",
        ),
        ("UnknownType", None),
    ],
)
def test_convert_dttm(
    target_type: str,
    expected_result: Optional[str],
    dttm: datetime,  # noqa: F811
) -> None:
    from superset.db_engine_specs.hive import HiveEngineSpec as spec  # noqa: N813

    assert_convert_dttm(spec, target_type, expected_result, dttm)


def test_get_schema_from_engine_params() -> None:
    """
    Test the ``get_schema_from_engine_params`` method.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    assert (
        HiveEngineSpec.get_schema_from_engine_params(
            make_url("hive://localhost:10000/default"), {}
        )
        == "default"
    )


def test_get_schema_from_engine_params_url_quoted() -> None:
    """
    Schemas with URL-encoded characters are properly decoded.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    url = make_url("hive://localhost:10000/my%20schema")
    assert HiveEngineSpec.get_schema_from_engine_params(url, {}) == "my schema"


def test_select_star(mocker: MockerFixture) -> None:
    """
    Test the ``select_star`` method.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    database = mocker.MagicMock()
    dialect = mocker.MagicMock()

    def quote_table(table: Table, dialect: Dialect) -> str:
        return ".".join(
            part for part in (table.catalog, table.schema, table.table) if part
        )

    mocker.patch.object(HiveEngineSpec, "quote_table", quote_table)

    HiveEngineSpec.select_star(
        database=database,
        table=Table("my_table", "my_schema", "my_catalog"),
        dialect=dialect,
        limit=100,
        show_cols=False,
        indent=True,
        latest_partition=False,
        cols=None,
    )

    query = database.compile_sqla_query.mock_calls[0][1][0]
    assert (
        str(query)
        == """
SELECT * \nFROM my_schema.my_table
 LIMIT :param_1
    """.strip()
    )


def test_adjust_engine_params_with_schema() -> None:
    """
    ``adjust_engine_params`` updates the URL database when a schema is provided.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    url = make_url("hive://localhost:10000/default")
    new_url, connect_args = HiveEngineSpec.adjust_engine_params(
        url, {}, schema="custom_schema"
    )
    assert new_url.database == "custom_schema"
    assert connect_args == {}


def test_adjust_engine_params_without_schema() -> None:
    """
    ``adjust_engine_params`` returns the URL unchanged when schema is None.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    url = make_url("hive://localhost:10000/default")
    new_url, connect_args = HiveEngineSpec.adjust_engine_params(url, {})
    assert new_url.database == "default"
    assert connect_args == {}


def test_adjust_engine_params_quotes_schema() -> None:
    """
    Schemas containing special characters are URL-encoded.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    url = make_url("hive://localhost:10000/default")
    new_url, _ = HiveEngineSpec.adjust_engine_params(url, {}, schema="a/b")
    assert new_url.database == "a%2Fb"


def test_extract_error_message_with_match() -> None:
    """
    ``_extract_error_message`` extracts the inner ``errorMessage`` value.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    msg = (
        '{...} errorMessage="Error while compiling statement: FAILED: '
        "SemanticException [Error 10001]: Line 4"
        ":5 Table not found 'fact_ridesfdslakj'\", statusCode=3, "
        "sqlState='42S02', errorCode=10001)){...}"
    )
    assert HiveEngineSpec._extract_error_message(Exception(msg)) == (
        "Error while compiling statement: FAILED: "
        "SemanticException [Error 10001]: Line 4:5 "
        "Table not found 'fact_ridesfdslakj'"
    )


def test_extract_error_message_no_match() -> None:
    """
    Without a match the original message is returned.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    ex = Exception("plain message without errorMessage marker")
    assert HiveEngineSpec._extract_error_message(ex) == str(ex)


def test_extract_error_message_via_extract_error_message() -> None:
    """
    The public ``extract_error_message`` prepends the engine name.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    msg = 'foo errorMessage="hello world", bar'
    assert HiveEngineSpec.extract_error_message(Exception(msg)) == (
        "hive error: hello world"
    )


def test_progress_no_jobs() -> None:
    """
    Progress is 0 with no parsable log lines.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    log = [
        "17/02/07 18:26:27 INFO log.PerfLogger: <PERFLOG method=compile>",
        "17/02/07 18:26:27 INFO log.PerfLogger: <PERFLOG method=parse>",
    ]
    assert HiveEngineSpec.progress(log) == 0


def test_progress_total_jobs_only() -> None:
    """
    Progress is still 0 when only total jobs is reported.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    log = ["17/02/07 19:15:55 INFO ql.Driver: Total jobs = 2"]
    assert HiveEngineSpec.progress(log) == 0


def test_progress_total_jobs_zero_falls_back_to_one() -> None:
    """
    When the parsed total jobs value is 0 it is coerced to 1.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    log = ["17/02/07 19:15:55 INFO ql.Driver: Total jobs = 0"]
    assert HiveEngineSpec.progress(log) == 0


def test_progress_launching_job_resets_stages() -> None:
    """
    ``progress`` resets stage state when a new job is launched.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    log = [
        "17/02/07 19:15:55 INFO ql.Driver: Total jobs = 2",
        "17/02/07 19:15:55 INFO ql.Driver: Launching Job 1 out of 2",
        "17/02/07 19:16:09 INFO exec.Task: Stage-1 map = 100%,  reduce = 0%",
        "17/02/07 19:15:55 INFO ql.Driver: Launching Job 2 out of 2",
        "17/02/07 19:16:09 INFO exec.Task: Stage-1 map = 0%,  reduce = 0%",
        "17/02/07 19:16:09 INFO exec.Task: Stage-1 map = 40%,  reduce = 0%",
    ]
    assert HiveEngineSpec.progress(log) == 60


def test_progress_partial_stage() -> None:
    """
    Stage progress contributes proportionally to overall progress.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    log = [
        "17/02/07 19:15:55 INFO ql.Driver: Total jobs = 2",
        "17/02/07 19:15:55 INFO ql.Driver: Launching Job 1 out of 2",
        "17/02/07 19:16:09 INFO exec.Task: Stage-1 map = 0%,  reduce = 0%",
        "17/02/07 19:16:09 INFO exec.Task: Stage-1 map = 40%,  reduce = 0%",
        "17/02/07 19:16:09 INFO exec.Task: Stage-1 map = 80%,  reduce = 40%",
    ]
    assert HiveEngineSpec.progress(log) == 30


def test_progress_launching_job_zero_max_jobs_falls_back() -> None:
    """
    A launching-job log line with a max_jobs of 0 falls back to 1.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    log = [
        "17/02/07 19:15:55 INFO ql.Driver: Launching Job 1 out of 0",
    ]
    assert HiveEngineSpec.progress(log) == 0


def test_get_tracking_url_from_logs_found() -> None:
    """
    The first matching tracking URL is returned.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    log = [
        "INFO Driver: starting query",
        "INFO Driver: Tracking URL = http://tracker/job/1/",
        "INFO Driver: Tracking URL = http://tracker/job/2/",
    ]
    assert HiveEngineSpec.get_tracking_url_from_logs(log) == "http://tracker/job/1/"


def test_get_tracking_url_from_logs_missing() -> None:
    """
    ``None`` is returned when no tracking URL is present.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    assert HiveEngineSpec.get_tracking_url_from_logs(["foo", "bar"]) is None


def test_has_implicit_cancel() -> None:
    """
    Hive returns ``True`` because the live cursor handles implicit cancel.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    assert HiveEngineSpec.has_implicit_cancel() is True


def test_execute_passes_async_kwarg() -> None:
    """
    ``execute`` translates the ``async_`` kwarg to the legacy ``async`` keyword.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    cursor = MagicMock()
    HiveEngineSpec.execute(cursor, "SELECT 1", MagicMock(), async_=True)
    cursor.execute.assert_called_once_with("SELECT 1", **{"async": True})


def test_execute_default_sync() -> None:
    """
    When ``async_`` is not provided the cursor is invoked synchronously.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    cursor = MagicMock()
    HiveEngineSpec.execute(cursor, "SELECT 2", MagicMock())
    cursor.execute.assert_called_once_with("SELECT 2", **{"async": False})


def test_get_columns_delegates_to_base(mocker: MockerFixture) -> None:
    """
    ``get_columns`` delegates to ``BaseEngineSpec.get_columns`` rather than
    Presto's overridden implementation.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    base_cls = mocker.patch(
        "superset.db_engine_specs.hive.BaseEngineSpec.get_columns",
        return_value=[{"name": "col1"}],
    )
    inspector = mocker.MagicMock()
    table = Table("t")
    result = HiveEngineSpec.get_columns(inspector, table, options={"foo": 1})
    base_cls.assert_called_once_with(inspector, table, {"foo": 1})
    assert result == [{"name": "col1"}]


def test_get_fields_delegates_to_base(mocker: MockerFixture) -> None:
    """
    ``_get_fields`` delegates to the base class implementation.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    base_cls = mocker.patch(
        "superset.db_engine_specs.hive.BaseEngineSpec._get_fields",
        return_value=["dummy"],
    )
    cols: list[ResultSetColumnType] = [
        {"column_name": "a", "name": "a", "type": "STRING", "is_dttm": False}
    ]
    assert HiveEngineSpec._get_fields(cols) == ["dummy"]
    base_cls.assert_called_once_with(cols)


def test_latest_sub_partition_returns_none() -> None:
    """
    ``latest_sub_partition`` is intentionally a no-op (TODO in source).
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    assert HiveEngineSpec.latest_sub_partition(MagicMock(), Table("t")) is None


def test_latest_partition_from_df_empty() -> None:
    """
    ``_latest_partition_from_df`` returns ``None`` for an empty DataFrame.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    assert HiveEngineSpec._latest_partition_from_df(pd.DataFrame()) is None


def test_latest_partition_from_df_single_partition() -> None:
    """
    A single partition column returns a single value.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    df = pd.DataFrame({"partition": ["ds=2024-01-01"]})
    assert HiveEngineSpec._latest_partition_from_df(df) == ["2024-01-01"]


def test_latest_partition_from_df_multi_partition() -> None:
    """
    Multiple partition columns are split on ``/``.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    df = pd.DataFrame(
        {
            "partition": [
                "ds=2024-01-01/hour=1",
                "ds=2024-03-01/hour=1",
                "ds=2024-02-01/hour=2",
            ]
        }
    )
    assert HiveEngineSpec._latest_partition_from_df(df) == ["2024-03-01", "1"]


def test_partition_query_with_schema() -> None:
    """
    ``_partition_query`` qualifies the table with the schema when present.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    sql = HiveEngineSpec._partition_query(Table("foo", "bar"), [], MagicMock())
    assert sql == "SHOW PARTITIONS bar.foo"


def test_partition_query_without_schema() -> None:
    """
    ``_partition_query`` falls back to the bare table name without a schema.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    sql = HiveEngineSpec._partition_query(Table("foo"), [], MagicMock())
    assert sql == "SHOW PARTITIONS foo"


def test_impersonate_user_no_username() -> None:
    """
    Without a username the inputs are returned unchanged.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    url = make_url("hive://localhost:10000/default")
    kwargs: dict[str, object] = {"connect_args": {"foo": "bar"}}
    new_url, new_kwargs = HiveEngineSpec.impersonate_user(
        MagicMock(), None, None, url, kwargs
    )
    assert new_url is url
    assert new_kwargs == {"connect_args": {"foo": "bar"}}


def test_impersonate_user_hive_backend() -> None:
    """
    For the hive backend the proxy user is added to ``connect_args``.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    url = make_url("hive://localhost:10000/default")
    new_url, new_kwargs = HiveEngineSpec.impersonate_user(
        MagicMock(), "alice", None, url, {}
    )
    assert (
        new_kwargs["connect_args"]["configuration"]["hive.server2.proxy.user"]
        == "alice"
    )
    assert new_url is url


def test_impersonate_user_hive_backend_preserves_configuration() -> None:
    """
    Existing ``configuration`` keys are preserved when adding the proxy user.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    url = make_url("hive://localhost:10000/default")
    kwargs: dict[str, object] = {
        "connect_args": {"configuration": {"existing.key": "value"}}
    }
    _, new_kwargs = HiveEngineSpec.impersonate_user(
        MagicMock(), "bob", None, url, kwargs
    )
    config = new_kwargs["connect_args"]["configuration"]
    assert config["existing.key"] == "value"
    assert config["hive.server2.proxy.user"] == "bob"


def test_impersonate_user_non_hive_backend() -> None:
    """
    Non-hive backends do not get the proxy user injected.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    url = make_url("presto://localhost:8080/default")
    _, new_kwargs = HiveEngineSpec.impersonate_user(MagicMock(), "alice", None, url, {})
    assert new_kwargs.get("connect_args", {}) == {}


def _call_get_function_names(database: object) -> list[str]:
    """Invoke ``HiveEngineSpec.get_function_names`` bypassing the cache."""
    from superset.db_engine_specs.hive import HiveEngineSpec

    raw = HiveEngineSpec.__dict__["get_function_names"].__func__
    underlying = getattr(raw, "uncached", raw)
    return underlying(HiveEngineSpec, database)


def test_get_function_names_known_column(mocker: MockerFixture) -> None:
    """
    The ``tab_name`` column of a ``SHOW FUNCTIONS`` result returns its values.
    """
    database = mocker.MagicMock()
    database.get_df.return_value = pd.DataFrame({"tab_name": ["abs", "avg", "count"]})
    assert _call_get_function_names(database) == ["abs", "avg", "count"]


def test_get_function_names_single_column_fallback(
    mocker: MockerFixture,
) -> None:
    """
    A single non-standard column is used as a fallback.
    """
    database = mocker.MagicMock()
    database.get_df.return_value = pd.DataFrame({"name": ["abs", "avg"]})
    assert _call_get_function_names(database) == ["abs", "avg"]


def test_get_function_names_no_recognizable_columns(
    mocker: MockerFixture,
) -> None:
    """
    Multiple unknown columns yield an empty list.
    """
    database = mocker.MagicMock()
    database.get_df.return_value = pd.DataFrame({"a": [1], "b": [2]})
    assert _call_get_function_names(database) == []


def test_get_view_names_with_schema() -> None:
    """
    ``SHOW VIEWS IN ...`` is issued when a schema is supplied.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    database = MagicMock()
    cursor = MagicMock()
    database.get_raw_connection.return_value.__enter__.return_value.cursor.return_value = (  # noqa: E501
        cursor
    )
    cursor.fetchall.return_value = [["a", "b"], ["c", "d"]]

    result = HiveEngineSpec.get_view_names(database, MagicMock(), "myschema")
    cursor.execute.assert_called_once_with("SHOW VIEWS IN `myschema`")
    assert result == {"a", "c"}


def test_get_view_names_without_schema() -> None:
    """
    ``SHOW VIEWS`` is issued without a schema qualifier.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    database = MagicMock()
    cursor = MagicMock()
    database.get_raw_connection.return_value.__enter__.return_value.cursor.return_value = (  # noqa: E501
        cursor
    )
    cursor.fetchall.return_value = [["v1"], ["v2"]]

    result = HiveEngineSpec.get_view_names(database, MagicMock(), None)
    cursor.execute.assert_called_once_with("SHOW VIEWS")
    assert result == {"v1", "v2"}


def test_fetch_data_error_state(mocker: MockerFixture) -> None:
    """
    ``fetch_data`` raises when the cursor reports an error state.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    cursor = mocker.MagicMock()
    fake_state = MagicMock()
    fake_state.ERROR_STATE = "ERROR_STATE"
    fake_ttypes = MagicMock(TOperationState=fake_state)
    pyhive_mod = MagicMock()
    pyhive_mod.exc.ProgrammingError = type("ProgrammingError", (Exception,), {})
    mocker.patch.dict(
        "sys.modules",
        {
            "pyhive": pyhive_mod,
            "TCLIService": MagicMock(ttypes=fake_ttypes),
        },
    )
    cursor.poll.return_value.operationState = "ERROR_STATE"
    cursor.poll.return_value.errorMessage = "boom"
    with pytest.raises(Exception, match="Query error"):
        HiveEngineSpec.fetch_data(cursor)


def test_fetch_data_programming_error(mocker: MockerFixture) -> None:
    """
    ``fetch_data`` swallows ``pyhive.exc.ProgrammingError`` and returns ``[]``.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    fake_state = MagicMock()
    fake_state.ERROR_STATE = "ERROR_STATE"
    fake_ttypes = MagicMock(TOperationState=fake_state)
    programming_error = type("ProgrammingError", (Exception,), {})
    pyhive_mod = MagicMock()
    pyhive_mod.exc.ProgrammingError = programming_error
    mocker.patch.dict(
        "sys.modules",
        {
            "pyhive": pyhive_mod,
            "TCLIService": MagicMock(ttypes=fake_ttypes),
        },
    )
    mocker.patch(
        "superset.db_engine_specs.hive.PrestoEngineSpec.fetch_data",
        side_effect=programming_error("boom"),
    )

    cursor = MagicMock()
    cursor.poll.return_value.operationState = "FINISHED_STATE"
    assert HiveEngineSpec.fetch_data(cursor) == []


def test_fetch_data_success(mocker: MockerFixture) -> None:
    """
    ``fetch_data`` delegates to ``PrestoEngineSpec.fetch_data`` on success.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    fake_state = MagicMock()
    fake_state.ERROR_STATE = "ERROR_STATE"
    fake_ttypes = MagicMock(TOperationState=fake_state)
    pyhive_mod = MagicMock()
    pyhive_mod.exc.ProgrammingError = type("ProgrammingError", (Exception,), {})
    mocker.patch.dict(
        "sys.modules",
        {
            "pyhive": pyhive_mod,
            "TCLIService": MagicMock(ttypes=fake_ttypes),
        },
    )
    mocker.patch(
        "superset.db_engine_specs.hive.PrestoEngineSpec.fetch_data",
        return_value=[(1, "a"), (2, "b")],
    )

    cursor = MagicMock()
    cursor.poll.return_value.operationState = "FINISHED_STATE"
    assert HiveEngineSpec.fetch_data(cursor, limit=2) == [(1, "a"), (2, "b")]


def test_patch_replaces_pyhive_attributes(mocker: MockerFixture) -> None:
    """
    ``patch`` rebinds the pyhive ``hive`` module attributes from TCLIService.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    hive_mod = MagicMock()
    pyhive_mod = MagicMock(hive=hive_mod)
    tcli_service_mod = MagicMock()
    constants_mod = MagicMock()
    ttypes_mod = MagicMock()
    tcli_pkg = MagicMock(
        constants=constants_mod,
        TCLIService=tcli_service_mod,
        ttypes=ttypes_mod,
    )
    mocker.patch.dict(
        "sys.modules",
        {
            "pyhive": pyhive_mod,
            "pyhive.hive": hive_mod,
            "TCLIService": tcli_pkg,
        },
    )

    HiveEngineSpec.patch()
    assert hive_mod.TCLIService is tcli_service_mod
    assert hive_mod.constants is constants_mod
    assert hive_mod.ttypes is ttypes_mod


def test_df_to_sql_append_raises() -> None:
    """
    ``df_to_sql`` rejects ``if_exists='append'``.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    with pytest.raises(SupersetException, match="Append operation"):
        HiveEngineSpec.df_to_sql(
            MagicMock(), Table("t"), pd.DataFrame(), {"if_exists": "append"}
        )


def test_df_to_sql_fail_table_exists() -> None:
    """
    ``df_to_sql`` rejects ``if_exists='fail'`` when the table exists.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    database = MagicMock()
    database.get_df.return_value.empty = False
    with pytest.raises(SupersetException, match="Table already exists"):
        HiveEngineSpec.df_to_sql(
            database, Table("t"), pd.DataFrame(), {"if_exists": "fail"}
        )


def test_df_to_sql_fail_table_exists_with_schema() -> None:
    """
    ``df_to_sql`` queries with the schema when one is provided.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    database = MagicMock()
    database.get_df.return_value.empty = False
    with pytest.raises(SupersetException, match="Table already exists"):
        HiveEngineSpec.df_to_sql(
            database,
            Table("t", "myschema"),
            pd.DataFrame(),
            {"if_exists": "fail"},
        )
    called_sql = database.get_df.call_args[0][0]
    assert "SHOW TABLES IN myschema LIKE" in called_sql


def test_df_to_sql_replace_drops_table(mocker: MockerFixture) -> None:
    """
    ``df_to_sql`` issues ``DROP TABLE IF EXISTS`` for ``if_exists='replace'``.
    """
    from superset.db_engine_specs import hive
    from superset.db_engine_specs.hive import HiveEngineSpec

    database = MagicMock()

    engine = MagicMock()
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=engine)
    cm.__exit__ = MagicMock(return_value=False)
    mocker.patch.object(HiveEngineSpec, "get_engine", return_value=cm)
    mocker.patch.object(hive, "upload_to_s3", return_value="s3a://bucket/foo")
    mocker.patch.object(hive.g, "user", "u", create=True)
    mocker.patch.object(hive, "app", MagicMock())
    hive.app.config = {
        "UPLOAD_FOLDER": "/tmp",  # noqa: S108
        "CSV_TO_HIVE_UPLOAD_DIRECTORY_FUNC": lambda *a, **kw: "prefix/",
    }

    HiveEngineSpec.df_to_sql(
        database,
        Table("foobar"),
        pd.DataFrame({"a": [1]}),
        {"if_exists": "replace"},
    )
    engine.execute.assert_any_call("DROP TABLE IF EXISTS foobar")


def test_upload_to_s3_no_bucket(mocker: MockerFixture) -> None:
    """
    ``upload_to_s3`` raises when the upload bucket is unset.
    """
    from superset.db_engine_specs import hive
    from superset.db_engine_specs.hive import upload_to_s3

    mocker.patch.object(hive, "app", MagicMock())
    hive.app.config = {"CSV_TO_HIVE_UPLOAD_S3_BUCKET": None}

    with pytest.raises(Exception, match="No upload bucket"):
        upload_to_s3("filename", "prefix", Table("t"))


def test_upload_to_s3_success(mocker: MockerFixture) -> None:
    """
    ``upload_to_s3`` returns the s3a URI on success.
    """
    from superset.db_engine_specs import hive
    from superset.db_engine_specs.hive import upload_to_s3

    mocker.patch.object(hive, "app", MagicMock())
    hive.app.config = {"CSV_TO_HIVE_UPLOAD_S3_BUCKET": "my-bucket"}

    boto_mod = MagicMock()
    boto_mod.s3.transfer.TransferConfig = MagicMock()
    boto_mod.client = MagicMock()
    transfer_mod = MagicMock()
    transfer_mod.TransferConfig = MagicMock()
    mocker.patch.dict(
        "sys.modules",
        {
            "boto3": boto_mod,
            "boto3.s3": MagicMock(),
            "boto3.s3.transfer": transfer_mod,
        },
    )

    location = upload_to_s3(
        "/tmp/file.parquet",  # noqa: S108
        "prefix",
        Table("mytable"),
    )
    assert location == "s3a://my-bucket/prefix/mytable"


def test_where_latest_partition_no_partition(mocker: MockerFixture) -> None:
    """
    Returns ``None`` when ``latest_partition`` raises (table not partitioned).
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    mocker.patch(
        "superset.db_engine_specs.hive.PrestoEngineSpec.latest_partition",
        side_effect=Exception("no partitions"),
    )
    columns: list[ResultSetColumnType] = [
        {"column_name": "ds", "name": "ds", "type": "STRING", "is_dttm": True}
    ]
    result = HiveEngineSpec.where_latest_partition(
        MagicMock(), Table("t"), select(), columns
    )
    assert result is None


def test_where_latest_partition_no_columns(mocker: MockerFixture) -> None:
    """
    Returns ``None`` when no columns are supplied.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    mocker.patch(
        "superset.db_engine_specs.hive.PrestoEngineSpec.latest_partition",
        return_value=(("ds",), ("01-01-19",)),
    )
    result = HiveEngineSpec.where_latest_partition(
        MagicMock(), Table("t"), select(), None
    )
    assert result is None


def test_where_latest_partition_no_values(mocker: MockerFixture) -> None:
    """
    Returns ``None`` when ``latest_partition`` reports no values.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    mocker.patch(
        "superset.db_engine_specs.hive.PrestoEngineSpec.latest_partition",
        return_value=(("ds",), None),
    )
    columns: list[ResultSetColumnType] = [
        {"column_name": "ds", "name": "ds", "type": "STRING", "is_dttm": True}
    ]
    result = HiveEngineSpec.where_latest_partition(
        MagicMock(), Table("t"), select(), columns
    )
    assert result is None


def test_where_latest_partition_applies_filter(mocker: MockerFixture) -> None:
    """
    The latest partition values are applied as filters on the query.
    """
    from superset.db_engine_specs.hive import HiveEngineSpec

    mocker.patch(
        "superset.db_engine_specs.hive.PrestoEngineSpec.latest_partition",
        return_value=(("ds", "hour"), ("2024-01-01", 5)),
    )
    columns: list[ResultSetColumnType] = [
        {
            "column_name": "ds",
            "name": "ds",
            "type": "STRING",
            "is_dttm": True,
        },
        {
            "column_name": "hour",
            "name": "hour",
            "type": "INT",
            "is_dttm": False,
        },
    ]
    result = HiveEngineSpec.where_latest_partition(
        MagicMock(), Table("t"), select(), columns
    )
    assert result is not None
    rendered = str(result.compile(compile_kwargs={"literal_binds": True}))
    assert "ds = '2024-01-01'" in rendered
    assert "hour = 5" in rendered


def test_handle_cursor_progress_and_tracking(mocker: MockerFixture) -> None:
    """
    ``handle_cursor`` updates progress and tracking metadata while polling.
    """
    from superset.db_engine_specs import hive
    from superset.db_engine_specs.hive import HiveEngineSpec

    finished = "FINISHED"
    init_state = "INIT"
    running = "RUNNING"
    fake_op_state = MagicMock(INITIALIZED_STATE=init_state, RUNNING_STATE=running)
    hive_mod = MagicMock()
    hive_mod.ttypes.TOperationState = fake_op_state
    pyhive_mod = MagicMock(hive=hive_mod)
    mocker.patch.dict(
        "sys.modules",
        {"pyhive": pyhive_mod, "pyhive.hive": hive_mod},
    )

    mocker.patch.object(hive, "app", MagicMock())
    hive.app.config = {"DB_POLL_INTERVAL_SECONDS": {}}
    mocker.patch.object(hive.time, "sleep", return_value=None)
    db_mock = mocker.patch.object(hive, "db")

    cursor = MagicMock()
    polls = [
        MagicMock(operationState=running),
        MagicMock(operationState=finished),
    ]
    cursor.poll.side_effect = polls
    cursor.fetch_logs.return_value = [
        "INFO ql.Driver: Total jobs = 1",
        "INFO ql.Driver: Launching Job 1 out of 1",
        "INFO exec.Task: Stage-1 map = 100%,  reduce = 100%",
        "Tracking URL = http://tracker/job_1/",
    ]

    query = MagicMock()
    query.id = 1
    query.progress = 0
    query.status = "RUNNING"
    db_mock.session.query.return_value.filter_by.return_value.one.return_value = query  # noqa: E501

    HiveEngineSpec.handle_cursor(cursor, query)
    assert query.progress == 100
    assert query.tracking_url == "http://tracker/job_1/"


def test_handle_cursor_stop_cancels(mocker: MockerFixture) -> None:
    """
    ``handle_cursor`` cancels the cursor when the query has been stopped.
    """
    from superset.common.db_query_status import QueryStatus
    from superset.db_engine_specs import hive
    from superset.db_engine_specs.hive import HiveEngineSpec

    init_state = "INIT"
    running = "RUNNING"
    fake_op_state = MagicMock(INITIALIZED_STATE=init_state, RUNNING_STATE=running)
    hive_mod = MagicMock()
    hive_mod.ttypes.TOperationState = fake_op_state
    pyhive_mod = MagicMock(hive=hive_mod)
    mocker.patch.dict(
        "sys.modules",
        {"pyhive": pyhive_mod, "pyhive.hive": hive_mod},
    )
    mocker.patch.object(hive, "app", MagicMock())
    hive.app.config = {"DB_POLL_INTERVAL_SECONDS": {}}
    mocker.patch.object(hive.time, "sleep", return_value=None)
    db_mock = mocker.patch.object(hive, "db")

    cursor = MagicMock()
    cursor.poll.return_value = MagicMock(operationState=running)

    query = MagicMock()
    query.id = 7
    query.status = QueryStatus.STOPPED
    db_mock.session.query.return_value.filter_by.return_value.one.return_value = query  # noqa: E501

    HiveEngineSpec.handle_cursor(cursor, query)
    cursor.cancel.assert_called_once()


def test_handle_cursor_fetch_logs_failure(mocker: MockerFixture) -> None:
    """
    Logging failures are tolerated and the loop terminates normally.
    """
    from superset.db_engine_specs import hive
    from superset.db_engine_specs.hive import HiveEngineSpec

    finished = "FINISHED"
    running = "RUNNING"
    fake_op_state = MagicMock(INITIALIZED_STATE="INIT", RUNNING_STATE=running)
    hive_mod = MagicMock()
    hive_mod.ttypes.TOperationState = fake_op_state
    pyhive_mod = MagicMock(hive=hive_mod)
    mocker.patch.dict(
        "sys.modules",
        {"pyhive": pyhive_mod, "pyhive.hive": hive_mod},
    )
    mocker.patch.object(hive, "app", MagicMock())
    hive.app.config = {"DB_POLL_INTERVAL_SECONDS": {}}
    mocker.patch.object(hive.time, "sleep", return_value=None)
    db_mock = mocker.patch.object(hive, "db")

    cursor = MagicMock()
    cursor.fetch_logs.side_effect = RuntimeError("logs unavailable")
    cursor.poll.side_effect = [
        MagicMock(operationState=running),
        MagicMock(operationState=finished),
    ]

    query = MagicMock()
    query.id = 1
    query.progress = 0
    query.status = "RUNNING"
    db_mock.session.query.return_value.filter_by.return_value.one.return_value = query  # noqa: E501

    HiveEngineSpec.handle_cursor(cursor, query)
    assert query.progress == 0


def test_handle_cursor_uses_legacy_poll_interval(mocker: MockerFixture) -> None:
    """
    The deprecated ``HIVE_POLL_INTERVAL`` config is honoured if set.
    """
    from superset.db_engine_specs import hive
    from superset.db_engine_specs.hive import HiveEngineSpec

    finished = "FINISHED"
    running = "RUNNING"
    fake_op_state = MagicMock(INITIALIZED_STATE="INIT", RUNNING_STATE=running)
    hive_mod = MagicMock()
    hive_mod.ttypes.TOperationState = fake_op_state
    pyhive_mod = MagicMock(hive=hive_mod)
    mocker.patch.dict(
        "sys.modules",
        {"pyhive": pyhive_mod, "pyhive.hive": hive_mod},
    )
    mocker.patch.object(hive, "app", MagicMock())
    hive.app.config = {
        "HIVE_POLL_INTERVAL": 1,
        "DB_POLL_INTERVAL_SECONDS": {},
    }
    sleep_mock = mocker.patch.object(hive.time, "sleep", return_value=None)
    db_mock = mocker.patch.object(hive, "db")

    cursor = MagicMock()
    cursor.fetch_logs.return_value = []
    cursor.poll.side_effect = [
        MagicMock(operationState=running),
        MagicMock(operationState=finished),
    ]

    query = MagicMock()
    query.id = 2
    query.progress = 0
    query.status = "RUNNING"
    db_mock.session.query.return_value.filter_by.return_value.one.return_value = query  # noqa: E501

    HiveEngineSpec.handle_cursor(cursor, query)
    sleep_mock.assert_called_with(1)
