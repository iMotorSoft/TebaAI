import json
from pathlib import Path
R=Path(__file__).resolve().parents[3]/'data/reports/breslov/2026-07-15-lm-xv-kdp-fine-zone-detector-v1'
def test_profile_covers_pages():assert len(json.loads((R/'fine_zone_profile_pages.json').read_text()))==514
def test_qa_passes():assert json.loads((R/'fine_zone_detector_qa_results.json').read_text())['status']=='PASS'
