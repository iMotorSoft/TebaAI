import json
from pathlib import Path
R=Path(__file__).resolve().parents[3]/'data/reports/breslov/2026-07-15-la-potencia-plegaria-final-ingestion-v1'
def test_page_first_and_qa():
 d=json.loads((R/'final_ingestion_qa_results.json').read_text());assert d['status']=='PASS';assert d['metrics']['pages']==416;assert d['metrics']['blocks']>0
def test_preflight_identity():
 assert json.loads((R/'page_first_ingest_report.json').read_text())['sha256']=='8e5c2ca6c153f47e7ae31e0ba2f2b8fefaedb9916dd8d0d79d484e2c96990c46'
