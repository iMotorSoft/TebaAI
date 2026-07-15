import json
from pathlib import Path
R=Path(__file__).resolve().parents[3]/'data/reports/breslov/2026-07-15-cross-corpus-qa-potencia-v1'
def test_batch_answers_are_evidenced():
 d=json.loads((R/'cross_corpus_qa_results.json').read_text());assert len(d)==17;assert all(h['quote'] for x in d for h in x['hits'])
def test_assertions_pass():assert json.loads((R/'qa_assertions.json').read_text())['status']=='PASS'
