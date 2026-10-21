from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import httpx
from litestar import Litestar
import pytest

from modules.library.errors import ScopeAccessDeniedError
from modules.library.source_repository import get_authorized_source


@pytest.mark.asyncio
async def test_source_repository_rejects_inconsistent_document_tenant(monkeypatch):
    import modules.library.source_repository as module
    tenant = dict(organization_id=uuid4(), workspace_id=uuid4(), project_id=uuid4())
    scope = SimpleNamespace(id=uuid4(), **tenant)
    row = dict(knowledge_scope_code='breslov_e2e', knowledge_scope_id=scope.id, **tenant)
    row['organization_id']=uuid4()
    async def fetch(*args): return row
    async def authorize(*args, **kwargs): return scope
    monkeypatch.setattr(module,'fetch_one',fetch)
    monkeypatch.setattr(module,'get_authorized_scope_by_code',authorize)
    with pytest.raises(ScopeAccessDeniedError):
        await get_authorized_source(None,user_id=uuid4(),document_id=uuid4())


@pytest.mark.asyncio
async def test_source_route_no_public_exposure_or_cross_scope_read(monkeypatch):
    import modules.library.routes as module
    app=Litestar(route_handlers=[module.library_original_source,module.library_page_publication])
    document_id=uuid4()
    @asynccontextmanager
    async def tx(pool): yield None
    async def payload(*args): return {'sub':str(uuid4())}
    async def pool(*args): return None
    async def denied(*args, **kwargs): raise ScopeAccessDeniedError('unavailable')
    monkeypatch.setattr(module,'transaction',tx)
    monkeypatch.setattr(module,'get_current_user_payload',payload)
    monkeypatch.setattr(module,'get_pg_pool',pool)
    monkeypatch.setattr(module,'get_authorized_source',denied)
    transport=httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport,base_url='http://test') as client:
        for url in (f'/library/documents/{document_id}/source',
                    f'/library/documents/{document_id}/pages/1/publication'):
            assert (await client.get(url)).status_code==401
            response=await client.get(url,headers={'Authorization':'Bearer unit-test'})
            assert response.status_code==403
            assert 'source_path' not in response.text


@pytest.mark.asyncio
async def test_source_route_refuses_arbitrary_filesystem_path(monkeypatch,tmp_path):
    import modules.library.routes as module
    app=Litestar(route_handlers=[module.library_original_source])
    document_id=uuid4()
    arbitrary=tmp_path / 'private.pdf'; arbitrary.write_bytes(b'%PDF private')
    @asynccontextmanager
    async def tx(pool): yield None
    async def payload(*args): return {'sub':str(uuid4())}
    async def pool(*args): return None
    async def source(*args, **kwargs): return {'source_path':str(arbitrary)}
    monkeypatch.setattr(module,'transaction',tx)
    monkeypatch.setattr(module,'get_current_user_payload',payload)
    monkeypatch.setattr(module,'get_pg_pool',pool)
    monkeypatch.setattr(module,'get_authorized_source',source)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        result=await client.get(f'/library/documents/{document_id}/source',headers={'Authorization':'Bearer unit-test'})
        assert result.status_code==404
        assert str(arbitrary) not in result.text
