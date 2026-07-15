"""Critical integrity QA for Likutey Halajot investigative reference resolutions."""
from __future__ import annotations
import asyncio,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import psycopg
from psycopg.rows import dict_row
from globalVar import POSTGRES_DSN
RUN='likutey_halajot_reference_resolution_investigative_v1_20260715'
async def main():
 async with await psycopg.AsyncConnection.connect(POSTGRES_DSN,row_factory=dict_row) as c:
  async with c.cursor() as q:
   await q.execute("""select count(*) total,count(*) filter(where x.evidence_quote<>r.text_quote) bad_quote,count(*) filter(where x.evidence_surface_form<>r.surface_form) bad_surface,count(*) filter(where x.resolution_decision not in ('resolved_canonical_reference','keep_generic_source','rejected_false_positive','needs_research_review')) bad_decision,count(*) filter(where x.resolution_method not in ('exact_catalog_match','variant_catalog_match','deterministic_pattern','corpus_cross_match','parent_note_context','halakhah_context','multilingual_literal_match','ai_textual_classification','fallback_keep_generic','false_positive_rule')) bad_method from library_likutey_halajot_nominal_reference_resolution_v1 x join library_likutey_halajot_nominal_references_v1 r on r.id=x.nominal_reference_id where x.resolution_run_id=%s""",(RUN,));result=await q.fetchone()
 print(json.dumps(result,default=str))
 if result['total']!=136 or any(result[x] for x in ('bad_quote','bad_surface','bad_decision','bad_method')):sys.exit(1)
if __name__=='__main__':asyncio.run(main())
