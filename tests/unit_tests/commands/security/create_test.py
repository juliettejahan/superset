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
from unittest.mock import MagicMock, patch

import pytest

from superset.commands.exceptions import DatasourceNotFoundValidationError
from superset.commands.security.create import CreateRLSRuleCommand


def test_init_copies_data_and_extracts_tables_and_roles() -> None:
    data = {
        "name": "test_rule",
        "tables": [1, 2],
        "roles": [10, 20],
        "clause": "id = 1",
    }
    command = CreateRLSRuleCommand(data)

    assert command._properties == data
    assert command._properties is not data
    assert command._tables == [1, 2]
    assert command._roles == [10, 20]


def test_init_defaults_tables_and_roles_to_empty_lists() -> None:
    data = {"name": "test_rule", "clause": "id = 1"}
    command = CreateRLSRuleCommand(data)

    assert command._tables == []
    assert command._roles == []


@patch("superset.commands.security.create.db")
@patch("superset.commands.security.create.populate_roles")
def test_validate_success(mock_populate_roles: MagicMock, mock_db: MagicMock) -> None:
    mock_role_a = MagicMock()
    mock_role_b = MagicMock()
    mock_populate_roles.return_value = [mock_role_a, mock_role_b]

    mock_table_1 = MagicMock()
    mock_table_2 = MagicMock()
    mock_db.session.query.return_value.filter.return_value.all.return_value = [
        mock_table_1,
        mock_table_2,
    ]

    data = {
        "name": "test_rule",
        "tables": [1, 2],
        "roles": [10, 20],
        "clause": "id = 1",
    }
    command = CreateRLSRuleCommand(data)
    command.validate()

    mock_populate_roles.assert_called_once_with([10, 20])
    assert command._properties["roles"] == [mock_role_a, mock_role_b]
    assert command._properties["tables"] == [mock_table_1, mock_table_2]


@patch("superset.commands.security.create.db")
@patch("superset.commands.security.create.populate_roles")
def test_validate_raises_when_table_not_found(
    mock_populate_roles: MagicMock, mock_db: MagicMock
) -> None:
    mock_populate_roles.return_value = []

    mock_db.session.query.return_value.filter.return_value.all.return_value = [
        MagicMock()
    ]

    data = {"name": "test_rule", "tables": [1, 2], "roles": [], "clause": "id = 1"}
    command = CreateRLSRuleCommand(data)

    with pytest.raises(DatasourceNotFoundValidationError):
        command.validate()


@patch("superset.commands.security.create.db")
@patch("superset.commands.security.create.populate_roles")
def test_validate_with_empty_tables(
    mock_populate_roles: MagicMock, mock_db: MagicMock
) -> None:
    mock_populate_roles.return_value = [MagicMock()]
    mock_db.session.query.return_value.filter.return_value.all.return_value = []

    data = {"name": "test_rule", "tables": [], "roles": [10], "clause": "id = 1"}
    command = CreateRLSRuleCommand(data)
    command.validate()

    assert command._properties["tables"] == []
    assert len(command._properties["roles"]) == 1


@patch("superset.commands.security.create.db")
@patch("superset.commands.security.create.populate_roles")
def test_validate_with_empty_roles(
    mock_populate_roles: MagicMock, mock_db: MagicMock
) -> None:
    mock_populate_roles.return_value = []
    mock_db.session.query.return_value.filter.return_value.all.return_value = []

    data = {"name": "test_rule", "tables": [], "roles": [], "clause": "id = 1"}
    command = CreateRLSRuleCommand(data)
    command.validate()

    mock_populate_roles.assert_called_once_with([])
    assert command._properties["roles"] == []
    assert command._properties["tables"] == []


@patch("superset.commands.security.create.RLSDAO")
@patch("superset.commands.security.create.db")
@patch("superset.commands.security.create.populate_roles")
def test_run_calls_validate_and_creates_rule(
    mock_populate_roles: MagicMock, mock_db: MagicMock, mock_rls_dao: MagicMock
) -> None:
    mock_role = MagicMock()
    mock_populate_roles.return_value = [mock_role]

    mock_table = MagicMock()
    mock_db.session.query.return_value.filter.return_value.all.return_value = [
        mock_table
    ]

    expected_result = MagicMock()
    mock_rls_dao.create.return_value = expected_result

    data = {"name": "test_rule", "tables": [1], "roles": [10], "clause": "id = 1"}
    command = CreateRLSRuleCommand(data)
    result = command.run()

    mock_rls_dao.create.assert_called_once_with(attributes=command._properties)
    assert result == expected_result


@patch("superset.commands.security.create.RLSDAO")
@patch("superset.commands.security.create.db")
@patch("superset.commands.security.create.populate_roles")
def test_run_does_not_mutate_original_data(
    mock_populate_roles: MagicMock, mock_db: MagicMock, mock_rls_dao: MagicMock
) -> None:
    mock_populate_roles.return_value = []
    mock_db.session.query.return_value.filter.return_value.all.return_value = []
    mock_rls_dao.create.return_value = MagicMock()

    original_data = {"name": "test_rule", "tables": [], "roles": [], "clause": "id=1"}
    data_copy = original_data.copy()
    CreateRLSRuleCommand(original_data).run()

    assert original_data == data_copy


@patch("superset.commands.security.create.db")
@patch("superset.commands.security.create.populate_roles")
def test_validate_queries_sqla_table_with_correct_ids(
    mock_populate_roles: MagicMock, mock_db: MagicMock
) -> None:
    mock_populate_roles.return_value = []
    mock_query = MagicMock()
    mock_db.session.query.return_value = mock_query
    mock_query.filter.return_value.all.return_value = [MagicMock(), MagicMock()]

    data = {"name": "rule", "tables": [5, 9], "roles": [], "clause": "1=1"}
    command = CreateRLSRuleCommand(data)
    command.validate()

    mock_db.session.query.assert_called_once()
    mock_query.filter.assert_called_once()
