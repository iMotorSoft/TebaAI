import json
from pathlib import Path
R=Path(__file__).resolve().parents[3]/'data/reports/breslov/2026-07-15-investigative-qa-api-v1'
def test_http_golden_batch_grounded():
 d=json.loads((R/'golden_batch_results.json').read_text());assert (d['questions'],d['processed'],d['valid_status'],d['grounded'])==(17,17,17,17)
def test_http_response_has_no_external_sources():
 d=json.loads((R/'responses'/'plegaria.json').read_text());assert not d['execution']['used_external_sources'];assert not d['execution']['used_ocr'];assert all(h['quote'] for h in d['hits'])
