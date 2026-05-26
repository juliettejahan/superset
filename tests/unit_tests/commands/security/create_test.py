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

from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from superset.commands.exceptions import (
    DatasourceNotFoundValidationError,
    RolesNotFoundValidationError,
)
from superset.commands.security.create import CreateRLSRuleCommand

# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


def test_run_happy_path(mocker: MockerFixture) -> None:
    """run() calls validate then RLSDAO.create and returns the new object."""
    role = MagicMock()
    table = MagicMock()
    table.id = 1

    mocker.patch(
        "superset.commands.security.create.populate_roles",
        return_value=[role],
    )
    mock_query = MagicMock()
    mock_query.filter.return_value.all.return_value = [table]
    mocker.patch(
        "superset.commands.security.create.db.session.query",
        return_value=mock_query,
    )

    expected = MagicMock(name="rls_rule")
    mock_create = mocker.patch(
        "superset.commands.security.create.RLSDAO.create",
        return_value=expected,
    )

    # Bypass the @transaction() decorator's Flask `g` access
    mocker.patch(
        "superset.utils.decorators.g",
        MagicMock(in_transaction=False),
    )
    mocker.patch("superset.db")

    data = {
        "tables": [1],
        "roles": [10],
        "clause": "client_id = 1",
    }
    command = CreateRLSRuleCommand(data)
    result = command.run()

    assert result is expected
    mock_create.assert_called_once()
    call_kwargs = mock_create.call_args
    attrs = call_kwargs.kwargs.get("attributes") or call_kwargs[1].get("attributes")
    assert attrs["roles"] == [role]
    assert attrs["tables"] == [table]


def test_validate_resolves_roles_and_tables(mocker: MockerFixture) -> None:
    """validate() replaces integer IDs with ORM objects in _properties."""
    role = MagicMock()
    table = MagicMock()
    table.id = 5

    mocker.patch(
        "superset.commands.security.create.populate_roles",
        return_value=[role],
    )
    mock_query = MagicMock()
    mock_query.filter.return_value.all.return_value = [table]
    mocker.patch(
        "superset.commands.security.create.db.session.query",
        return_value=mock_query,
    )

    command = CreateRLSRuleCommand({"tables": [5], "roles": [20]})
    command.validate()

    assert command._properties["roles"] == [role]
    assert command._properties["tables"] == [table]


# ---------------------------------------------------------------------------
# Validation-error tests: missing / invalid datasource
# ---------------------------------------------------------------------------


def test_validate_raises_on_missing_table(mocker: MockerFixture) -> None:
    """validate() raises DatasourceNotFoundValidationError when a table ID
    does not resolve to an existing SqlaTable row."""
    mocker.patch(
        "superset.commands.security.create.populate_roles",
        return_value=[],
    )
    mock_query = MagicMock()
    mock_query.filter.return_value.all.return_value = []  # nothing found
    mocker.patch(
        "superset.commands.security.create.db.session.query",
        return_value=mock_query,
    )

    command = CreateRLSRuleCommand({"tables": [999], "roles": []})

    with pytest.raises(DatasourceNotFoundValidationError):
        command.validate()


def test_validate_raises_on_partial_table_match(mocker: MockerFixture) -> None:
    """validate() raises when only some of the requested table IDs exist."""
    table = MagicMock()
    table.id = 1

    mocker.patch(
        "superset.commands.security.create.populate_roles",
        return_value=[],
    )
    mock_query = MagicMock()
    mock_query.filter.return_value.all.return_value = [table]  # 1 of 2
    mocker.patch(
        "superset.commands.security.create.db.session.query",
        return_value=mock_query,
    )

    command = CreateRLSRuleCommand({"tables": [1, 2], "roles": []})

    with pytest.raises(DatasourceNotFoundValidationError):
        command.validate()


# ---------------------------------------------------------------------------
# Validation-error tests: invalid roles
# ---------------------------------------------------------------------------


def test_validate_raises_on_invalid_roles(mocker: MockerFixture) -> None:
    """validate() raises RolesNotFoundValidationError when populate_roles
    cannot resolve the given role IDs."""
    mocker.patch(
        "superset.commands.security.create.populate_roles",
        side_effect=RolesNotFoundValidationError(),
    )

    command = CreateRLSRuleCommand({"tables": [], "roles": [999]})

    with pytest.raises(RolesNotFoundValidationError):
        command.validate()


# ---------------------------------------------------------------------------
# Edge cases: empty inputs
# ---------------------------------------------------------------------------


def test_validate_empty_tables_and_roles(mocker: MockerFixture) -> None:
    """validate() succeeds when both tables and roles are empty lists."""
    mocker.patch(
        "superset.commands.security.create.populate_roles",
        return_value=[],
    )
    mock_query = MagicMock()
    mock_query.filter.return_value.all.return_value = []
    mocker.patch(
        "superset.commands.security.create.db.session.query",
        return_value=mock_query,
    )

    command = CreateRLSRuleCommand({"tables": [], "roles": []})
    command.validate()

    assert command._properties["roles"] == []
    assert command._properties["tables"] == []


def test_validate_tables_key_missing_defaults_to_empty(
    mocker: MockerFixture,
) -> None:
    """validate() treats a missing 'tables' key as an empty list."""
    mocker.patch(
        "superset.commands.security.create.populate_roles",
        return_value=[],
    )
    mock_query = MagicMock()
    mock_query.filter.return_value.all.return_value = []
    mocker.patch(
        "superset.commands.security.create.db.session.query",
        return_value=mock_query,
    )

    command = CreateRLSRuleCommand({"roles": []})
    command.validate()

    assert command._properties["tables"] == []


def test_validate_roles_key_missing_defaults_to_empty(
    mocker: MockerFixture,
) -> None:
    """validate() treats a missing 'roles' key as an empty list."""
    mocker.patch(
        "superset.commands.security.create.populate_roles",
        return_value=[],
    )
    mock_query = MagicMock()
    mock_query.filter.return_value.all.return_value = []
    mocker.patch(
        "superset.commands.security.create.db.session.query",
        return_value=mock_query,
    )

    command = CreateRLSRuleCommand({"tables": []})
    command.validate()

    assert command._properties["roles"] == []


def test_init_does_not_mutate_original_data() -> None:
    """__init__() copies the input dict so the caller's data is not mutated."""
    data: dict[str, list[int]] = {"tables": [1], "roles": [2]}
    command = CreateRLSRuleCommand(data)
    command._properties["extra_key"] = "injected"

    assert "extra_key" not in data


def test_validate_empty_data(mocker: MockerFixture) -> None:
    """validate() succeeds with a completely empty input dict."""
    mocker.patch(
        "superset.commands.security.create.populate_roles",
        return_value=[],
    )
    mock_query = MagicMock()
    mock_query.filter.return_value.all.return_value = []
    mocker.patch(
        "superset.commands.security.create.db.session.query",
        return_value=mock_query,
    )

    command = CreateRLSRuleCommand({})
    command.validate()

    assert command._properties["roles"] == []
    assert command._properties["tables"] == []


def test_run_propagates_validate_error(mocker: MockerFixture) -> None:
    """run() propagates validation errors raised during validate()."""
    mocker.patch(
        "superset.commands.security.create.populate_roles",
        return_value=[],
    )
    mock_query = MagicMock()
    mock_query.filter.return_value.all.return_value = []
    mocker.patch(
        "superset.commands.security.create.db.session.query",
        return_value=mock_query,
    )
    mocker.patch(
        "superset.utils.decorators.g",
        MagicMock(in_transaction=False),
    )
    mocker.patch("superset.db")

    command = CreateRLSRuleCommand({"tables": [1], "roles": []})

    with pytest.raises(DatasourceNotFoundValidationError):
        command.run()


def test_validate_multiple_valid_tables(mocker: MockerFixture) -> None:
    """validate() succeeds when all requested table IDs resolve."""
    table1 = MagicMock()
    table1.id = 1
    table2 = MagicMock()
    table2.id = 2

    mocker.patch(
        "superset.commands.security.create.populate_roles",
        return_value=[],
    )
    mock_query = MagicMock()
    mock_query.filter.return_value.all.return_value = [table1, table2]
    mocker.patch(
        "superset.commands.security.create.db.session.query",
        return_value=mock_query,
    )

    command = CreateRLSRuleCommand({"tables": [1, 2], "roles": []})
    command.validate()

    assert command._properties["tables"] == [table1, table2]
