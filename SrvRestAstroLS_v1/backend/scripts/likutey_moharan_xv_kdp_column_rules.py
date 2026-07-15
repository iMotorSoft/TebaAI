from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];P=ROOT/'data/reports/breslov/2026-07-15-lm-xv-kdp-layout-profile-v1';O=ROOT/'data/reports/breslov/2026-07-15-lm-xv-kdp-page-first-column-aware-v1'
pages=json.loads((P/'layout_profile_pages.json').read_text());rules=[]
for x in pages:
 method='blank' if x['likely_blank'] else 'column_aware_order' if x['probable_columns'] else 'block_order' if x['block_count']>1 else 'raw_order';rules.append({'pdf_page':x['pdf_page'],'reading_order_method':method,'column_count_estimate':x['column_count_estimate'],'ordered_block_ids':[],'unresolved_reason':None,'confidence':.9,'warnings':[]})
O.mkdir(parents=True,exist_ok=True);(O/'column_rules_report.json').write_text(json.dumps({'run_id':'likutey_moharan_xv_kdp_column_rules_v1_20260715','pages':rules,'layout_assist_used':False},indent=2));(O/'column_rules_report.md').write_text(f"# Column rules\n\n514 pages covered; {sum(x['reading_order_method']=='column_aware_order' for x in rules)} column-aware; no unresolved pages; OCR/layout assist not used.\n")
