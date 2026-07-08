from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from modules.library.errors import ScopeAccessDeniedError
from modules.library.domain import KnowledgeScope, LibraryCollection
from modules.library.repository import get_authorized_scope_by_code
from modules.library.service import _resolve_scope


@pytest.mark.asyncio
async def test_authorized_scope_requires_user_and_scope_filters() -> None:
    user_id = uuid4()
    scope_id = uuid4()
    row = {
        "id": scope_id,
        "organization_id": uuid4(),
        "workspace_id": uuid4(),
        "project_id": uuid4(),
        "knowledge_scope_code": "breslov_primary",
        "name": "Breslov Primary Corpus",
        "status": "active",
        "metadata": {},
    }

    with patch(
        "modules.library.repository.fetch_one",
        new=AsyncMock(return_value=row),
    ) as fetch:
        scope = await get_authorized_scope_by_code(
            AsyncMock(),
            user_id=user_id,
            knowledge_scope_code=" BRESLOV_PRIMARY ",
        )

    assert scope.id == scope_id
    assert scope.knowledge_scope_code == "breslov_primary"
    sql = fetch.await_args.args[1]
    params = fetch.await_args.args[2]
    assert "organization_members" in sql
    assert "workspace_members" in sql
    assert "project_members" in sql
    assert "ks.status = 'active'" in sql
    assert params == {
        "user_id": str(user_id),
        "scope_code": "breslov_primary",
    }


@pytest.mark.asyncio
async def test_scope_access_denied_does_not_reveal_existence() -> None:
    with patch(
        "modules.library.repository.fetch_one",
        new=AsyncMock(return_value=None),
    ):
        with pytest.raises(
            ScopeAccessDeniedError,
            match="Knowledge scope is unavailable",
        ):
            await get_authorized_scope_by_code(
                AsyncMock(),
                user_id=uuid4(),
                knowledge_scope_code="sibling_tenant_scope",
            )


@pytest.mark.asyncio
async def test_legacy_alias_resolves_from_collection_metadata() -> None:
    scope = KnowledgeScope(
        id=uuid4(),
        organization_id=uuid4(),
        workspace_id=uuid4(),
        project_id=uuid4(),
        knowledge_scope_code="canonical_scope",
        name="Canonical",
        status="active",
    )
    legacy = LibraryCollection.create(
        "legacy_alias",
        "Legacy",
        metadata={"knowledge_scope_code": "canonical_scope"},
    )
    scope_lookup = AsyncMock(side_effect=[None, scope])

    with (
        patch("modules.library.service.get_scope_by_code", scope_lookup),
        patch(
            "modules.library.service.get_collection_by_code",
            new=AsyncMock(return_value=legacy),
        ),
    ):
        resolved = await _resolve_scope(AsyncMock(), "legacy_alias")

    assert resolved is scope
    assert scope_lookup.await_args_list[1].args[1] == "canonical_scope"
