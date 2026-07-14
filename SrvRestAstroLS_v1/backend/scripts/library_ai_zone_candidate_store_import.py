"""Import already-validated AI candidates; never promotes corpus content."""
from __future__ import annotations
import argparse,asyncio,json
from pathlib import Path
import psycopg
from globalVar import POSTGRES_DSN
async def main(a):
 rows=[json.loads(x) for x in Path(a.input_jsonl).read_text().splitlines() if x.strip()]; inserted=0
 if not a.apply: print(json.dumps({'dry_run':True,'rows':len(rows)}));return
 async with await psycopg.AsyncConnection.connect(POSTGRES_DSN) as c:
  async with c.cursor() as q:
   for r in rows:
    p=r['pdf_page']; candidate=r.get('candidate',r.get('parsed',{})); decision=r.get('validation_decision','keep_as_candidate')
    await q.execute("insert into library_ai_zone_candidates_v2(pdf_page,candidate_run_id,candidate_source,detection_origin,detection_model,candidate_page_kind,candidate_kind,candidate_marker_value,candidate_confidence,candidate_quote,raw_candidate,validation_run_id,validation_policy_version,validation_decision,validation_reasons,validation_warnings,source_report_path) values(%s,%s,'manual_import','ocr_layout_ai','openai_gpt_4o_mini_2024_07_18',%s,%s,%s,%s,%s,%s::jsonb,%s,'v1',%s,'[]','[]',%s) on conflict do nothing",(p,a.candidate_run_id,candidate.get('page_kind'),candidate.get('kind','unknown'),candidate.get('marker'),candidate.get('confidence'),candidate.get('quote'),json.dumps(candidate),a.validation_run_id,decision,a.source_report_path));inserted+=q.rowcount
  await c.commit()
 print(json.dumps({'inserted':inserted,'rows':len(rows)}))
p=argparse.ArgumentParser();p.add_argument('--input-jsonl',required=True);p.add_argument('--candidate-run-id',required=True);p.add_argument('--validation-run-id',required=True);p.add_argument('--source-report-path');p.add_argument('--apply',action='store_true');a=p.parse_args();asyncio.run(main(a))
