from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from modules.auth.domain import User, UserRole
from modules.auth.repository import TenantContextConfigurationError, UserRepository


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "membership_role"),
    [
        (UserRole.ADMIN, "admin"),
        (UserRole.EDITOR, "member"),
        (UserRole.VIEWER, "viewer"),
    ],
)
async def test_create_assigns_complete_default_tenant_chain(
    role: UserRole,
    membership_role: str,
) -> None:
    user = User(
        id=uuid4(),
        email=f"{role.value}@example.test",
        username=role.value,
        password_hash="hash",
        role=role,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    context = {
        "organization_id": uuid4(),
        "workspace_id": uuid4(),
        "project_id": uuid4(),
    }

    with (
        patch(
            "modules.auth.repository.fetch_one",
            new=AsyncMock(return_value=context),
        ) as fetch,
        patch(
            "modules.auth.repository.execute",
            new=AsyncMock(return_value=1),
        ) as execute,
    ):
        await UserRepository(AsyncMock()).create(user)

    assert execute.await_count == 4
    create_params = execute.await_args_list[0].args[2]
    assert create_params["email_normalized"] == user.email
    context_sql = fetch.await_args.args[1]
    assert "default_user_context" in context_sql
    assert "breslov" not in context_sql.lower()
    membership_calls = execute.await_args_list[1:]
    assert "organization_members" in membership_calls[0].args[1]
    assert "workspace_members" in membership_calls[1].args[1]
    assert "project_members" in membership_calls[2].args[1]
    for call in membership_calls:
        assert call.args[2]["user_id"] == str(user.id)
        assert call.args[2]["membership_role"] == membership_role


@pytest.mark.asyncio
async def test_create_fails_closed_without_one_default_tenant_context() -> None:
    user = User(
        id=uuid4(),
        email="viewer@example.test",
        username=None,
        password_hash="hash",
        role=UserRole.VIEWER,
    )

    with (
        patch(
            "modules.auth.repository.fetch_one",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "modules.auth.repository.execute",
            new=AsyncMock(return_value=1),
        ) as execute,
    ):
        with pytest.raises(
            TenantContextConfigurationError,
            match="Exactly one active default tenant context",
        ):
            await UserRepository(AsyncMock()).create(user)

    assert execute.await_count == 1
