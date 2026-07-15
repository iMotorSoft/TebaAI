"""Assert that generated cross-corpus evidence is literal and locally sourced."""
from __future__ import annotations
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];P=ROOT/'data/reports/breslov/2026-07-15-cross-corpus-investigative-qa-v1/cross_corpus_qa_results.json'
rows=json.loads(P.read_text());bad=[]
for row in rows:
 if not row['question'].get('id'):bad.append('missing_question')
 for hit in row['hits']:
  if not hit.get('quote') or hit.get('source') not in ('library_document_chunks','library_lmii_search_ready_v2','library_likutey_halajot_investigative_search_v1'):bad.append(row['question']['id'])
 if not (ROOT/'data/reports/breslov/2026-07-15-cross-corpus-investigative-qa-v1/answers'/f"{row['question']['id']}.md").exists():bad.append('missing_answer')
print(json.dumps({'questions':len(rows),'with_hits':sum(bool(x['hits']) for x in rows),'cross':sum(x['cross_relation']!='no_cross_evidence' for x in rows),'bad':bad}))
sys.exit(bool(bad) or len(rows)!=12)
