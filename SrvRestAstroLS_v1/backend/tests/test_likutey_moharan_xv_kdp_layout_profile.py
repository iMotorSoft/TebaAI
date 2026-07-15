import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def test_layout_profile_contract():
 d=ROOT/'data/reports/breslov/2026-07-15-lm-xv-kdp-layout-profile-v1'; pages=json.loads((d/'layout_profile_pages.json').read_text()); summary=json.loads((d/'layout_profile_summary.md').read_text().split('\n',2)[2])
 assert len(pages)==514
 assert all(pages[n-1]['likely_blank'] for n in (1,2,4,504,514))
 assert summary['source_basename']=='LIKUTEY MOHARÁN XV KDP.pdf'
 assert summary['sha256']!='440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a'
 assert summary['strategy'] in {'PAGE_FIRST_COLUMN_AWARE_REQUIRED','PAGE_FIRST_WITH_BLOCK_COORDINATES_READY'}
 assert summary['ocr_used'] is False and summary['db_writes'] is False
