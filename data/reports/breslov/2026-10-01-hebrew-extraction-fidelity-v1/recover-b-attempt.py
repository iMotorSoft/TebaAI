"""Retry official manifest compensation, retaining upload for normal retry."""
import asyncio,json,sys
from pathlib import Path
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT.parents[3]/'SrvRestAstroLS_v1/backend'))
import globalVar
from infrastructure.postgres.pool import create_pool_from_settings,open_pool,close_pool
from modules.library.content_manager_cleanup import ManifestCleanupService
async def main():
 assert globalVar.TEBAAI_ENV=='development'
 pool=create_pool_from_settings();await open_pool(pool)
 try:
  service=ManifestCleanupService(pool)
  job='a968ec45-8a10-4ec8-a899-2dd07017104f'
  manifest=await service._load(job,2)
  assert manifest['scope_code']=='breslov_e2e'
  result=await service.cleanup(job,2,remove_temporary=False)
  data={'job_id':job,'attempt':2,'status':result.status,'preserved_upload_for_retry':True,'items':[{'resource_type':i.resource_type,'resource_id':str(i.resource_id),'result':i.result,'error':i.error} for i in result.items]}
  (OUT/'b-compensation-recovered.json').write_text(json.dumps(data,indent=2))
  print(result.status,len(result.items),flush=True)
  assert result.status=='completed'
 finally:await close_pool(pool)
asyncio.run(main())
