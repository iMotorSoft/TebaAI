from __future__ import annotations
from uuid import uuid4
import pytest
from modules.library.content_manager_cleanup import CleanupItem, ManifestCleanupService
from modules.library.page_first_gateway import E2EIsolationError
from globalVar import CONTENT_MANAGER_E2E_COLLECTION, CONTENT_MANAGER_E2E_SCOPE

class FakeIndex:
    rows=[]; fail=False; deleted=[]; query_blind=False
    def __init__(self,name): self.name=name
    def list_attempt(self,key):
        if self.fail: raise RuntimeError('milvus unavailable')
        if self.query_blind: return []  # scalar query returns nothing
        return list(self.rows)
    def delete_ids(self,ids):
        if self.query_blind:
            self.deleted.extend(ids); self.rows=[]
            return len(ids)
        present={str(r['pk']) for r in self.rows}
        matched=[i for i in ids if i in present]
        self.deleted.extend(matched); self.rows=[]
        return len(matched)

class Service(ManifestCleanupService):
    def __init__(self,manifest): super().__init__(None,index_factory=FakeIndex); self.manifest=manifest; self.finished=[]; self.pg=[]
    async def _load(self,*args): return self.manifest
    async def _set_status(self,*args): pass
    async def _finish(self,mid,items,status): self.finished.append((status,tuple(items)))
    async def _delete_pg(self,m,t,r): self.pg.append((t,r)); return CleanupItem(t,r,'deleted')
    async def _delete_temp(self,m,r): return CleanupItem('temporary_file',r,'deleted')

def manifest():
    job=uuid4()
    return {'manifest_id':uuid4(),'document_id':uuid4(),'job_id':job,'attempt_number':1,
        'scope_code':CONTENT_MANAGER_E2E_SCOPE,'collection_code':CONTENT_MANAGER_E2E_COLLECTION,
        'attempt_key':f'{job}:1','resources':{'vector':['v1'],'embedding':['e1'],
        'chunk':['c1'],'page':['p1'],'document_text':['t1'],'ingestion_run':['r1'],
        'document':['d1'],'temporary_file':['u1']}}

@pytest.mark.asyncio
async def test_manifest_cleanup_is_ordered_and_complete():
    FakeIndex.rows=[{'pk':'v1'}]; FakeIndex.fail=False; FakeIndex.deleted=[]; FakeIndex.query_blind=False
    service=Service(manifest()); result=await service.cleanup(service.manifest['job_id'],1)
    assert result.status=='completed' and FakeIndex.deleted==['v1']
    assert service.pg == [('embedding','e1'),('chunk','c1'),('page','p1'),
        ('document_text','t1'),('ingestion_run','r1'),('document','d1')]
    assert result.items[-1].resource_type=='temporary_file'

@pytest.mark.asyncio
async def test_cleanup_repeated_treats_absent_vector_as_success():
    FakeIndex.rows=[]; FakeIndex.fail=False; FakeIndex.deleted=[]; FakeIndex.query_blind=False
    service=Service(manifest()); result=await service.cleanup(service.manifest['job_id'],1)
    vector=next(item for item in result.items if item.resource_type=='vector')
    # A second cleanup finds the vector already gone: delete by id returns 0
    # and the item reports already_absent (idempotent success).
    assert FakeIndex.deleted==[]
    assert vector.result=='already_absent' and result.status=='completed'

@pytest.mark.asyncio
async def test_cleanup_deletes_manifest_vector_when_attempt_query_is_empty():
    """Regression: a silently-empty scalar query must not leave the manifest's
    vector behind. The E2E run revealed residual vectors in the isolated
    collection because cleanup only deleted ids returned by list_attempt."""
    FakeIndex.rows=[{'pk':'v_manifest_1'},{'pk':'v_manifest_2'}]
    FakeIndex.query_blind=True; FakeIndex.fail=False; FakeIndex.deleted=[]
    data=manifest(); data['resources']={'vector':['v_manifest_1','v_manifest_2'],'embedding':['e1'],
        'chunk':['c1'],'page':['p1'],'document_text':['t1'],'ingestion_run':['r1'],
        'document':['d1'],'temporary_file':['u1']}
    service=Service(data); result=await service.cleanup(data['job_id'],1)
    assert result.status=='completed'
    assert sorted(FakeIndex.deleted)==['v_manifest_1','v_manifest_2']
    vectors=[item for item in result.items if item.resource_type=='vector']
    assert all(item.result=='deleted' for item in vectors)
    FakeIndex.query_blind=False

@pytest.mark.asyncio
async def test_cleanup_stops_before_postgres_when_milvus_fails():
    FakeIndex.fail=True
    service=Service(manifest()); result=await service.cleanup(service.manifest['job_id'],1)
    assert result.status=='failed' and service.pg==[]
    FakeIndex.fail=False

@pytest.mark.asyncio
async def test_cleanup_can_preserve_validated_temporary_for_retry():
    FakeIndex.rows=[]
    service=Service(manifest()); result=await service.cleanup(service.manifest['job_id'],1,remove_temporary=False)
    assert not any(item.resource_type=='temporary_file' for item in result.items)

@pytest.mark.asyncio
async def test_cleanup_rejects_primary_scope():
    data=manifest(); data['scope_code']='breslov_primary'; data['collection_code']='tebaai_breslov_chunks_v1'
    service=Service(data)
    with pytest.raises(E2EIsolationError): await service.cleanup(data['job_id'],1)
