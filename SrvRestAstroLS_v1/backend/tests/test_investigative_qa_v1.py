import asyncio
import psycopg
from psycopg.rows import dict_row
from modules.library.investigative_qa_v1 import QaRequest,WORKS,Hit,run,validate_grounded_render
from globalVar import POSTGRES_DSN
def test_request_allowlist_and_defaults():
 q=QaRequest(question='¿Dónde aparece la plegaria?');assert not q.include_audit;assert set(q.works)==WORKS
def test_request_rejects_bad_limit():
 try:QaRequest(question='ok',max_hits_per_work=99)
 except Exception:return
 assert False
def test_real_postgres_retrieval_is_grounded():
 async def x():
  async with await psycopg.AsyncConnection.connect(POSTGRES_DSN,row_factory=dict_row) as c:return await run(c,QaRequest(question='¿Dónde aparece plegaria?',works=['potencia_plegaria','lh'],ai={'enabled':False}))
 r=asyncio.run(x());assert r['status']=='ok';assert all(h['quote'] for h in r['hits']);assert r['execution']['used_deterministic_fallback']
def test_adversarial_grounding_rejects_page_and_doctrine():
 h=Hit(hit_id='h1',work_code='lh',work_title='LH',pdf_page=10,quote='literal',source_view='v',search_record_type='fine',source_layer='fine',matched_terms=['x'],evidence_type='validated_fine_zone_quote',evidence_strength='strong')
 assert validate_grounded_render({'answer_markdown':'PDF p. 999','used_evidence_ids':['h1'],'claims':[{'claim':'x','evidence_ids':['h1']}]},[h])[0] is None
 assert validate_grounded_render({'answer_markdown':'Esto demuestra dependencia doctrinal','used_evidence_ids':['h1'],'claims':[{'claim':'x','evidence_ids':['h1']}]},[h])[0] is None
