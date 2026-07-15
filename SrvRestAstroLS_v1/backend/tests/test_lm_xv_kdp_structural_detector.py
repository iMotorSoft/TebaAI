import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
R=ROOT/'data/reports/breslov/2026-07-15-lm-xv-kdp-structural-detector-v1'
def test_profile_coverage():
 assert len(json.loads((R/'structural_profile_pages.json').read_text())) == 514
def test_qa_passed():
 assert json.loads((R/'structural_detector_qa_results.json').read_text())['status'] == 'PASS'
