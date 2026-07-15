import hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
PDF=Path('/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY MOHARÁN XV KDP.pdf')
REPORT=ROOT/'data/reports/breslov/2026-07-15-lm-xv-kdp-page-first-column-aware-v1'

def test_source_guard_identity():
    assert PDF.name == 'LIKUTEY MOHARÁN XV KDP.pdf'
    assert hashlib.sha256(PDF.read_bytes()).hexdigest() == 'f4d7eb195cadf94d6566c5cd6d636113b62f4c6748f987b250fc4bd0fcd61303'

def test_column_rules_cover_all_pages():
    import json
    data=json.loads((REPORT/'column_rules_report.json').read_text())
    assert len(data['pages']) == 514
    assert sum(x['reading_order_method']=='blank' for x in data['pages']) == 5

def test_ingest_qa_passed():
    import json
    data=json.loads((REPORT/'lm_xv_page_first_qa_results.json').read_text())
    assert data['status'] == 'PASS'
    assert data['metrics']['textual'] == 509
