from __future__ import annotations
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];D=ROOT/'data/reports/breslov/2026-07-15-lm-xv-kdp-layout-profile-v1'
required=['layout_profile_pages.json','layout_profile_blocks.jsonl','layout_samples_manifest.json','reading_order_probe_report.json','document_part_candidates.json','structural_candidates.json','layout_ingestion_strategy_recommendation.md','no_contamination_report.json']
missing=[x for x in required if not (D/x).exists()];pages=json.loads((D/'layout_profile_pages.json').read_text()) if not missing else [];summary=json.loads((D/'layout_profile_summary.md').read_text().split('\n',2)[2]) if (D/'layout_profile_summary.md').exists() else {}
result={'pass':not missing and len(pages)==514 and all(pages[n-1]['likely_blank'] for n in (1,2,4,504,514)) and summary.get('ocr_used') is False and summary.get('db_writes') is False,'missing':missing,'pages':len(pages),'status':summary.get('status'),'strategy':summary.get('strategy')}
(D/'layout_profile_qa_results.json').write_text(json.dumps(result,indent=2));print(json.dumps(result));sys.exit(not result['pass'])
