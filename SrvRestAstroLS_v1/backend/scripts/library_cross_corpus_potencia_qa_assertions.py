import json
from pathlib import Path
R=Path(__file__).resolve().parents[3]/'data/reports/breslov/2026-07-15-cross-corpus-qa-potencia-v1'
d=json.loads((R/'cross_corpus_qa_results.json').read_text());checks={'questions_16':len(d)>=16,'quotes_present':all(h['quote'] for x in d for h in x['hits']),'no_doctrinal_relation':all(x['cross_relation'] in ('cross_work_literal_parallel','no_cross_evidence') for x in d)};out={'status':'PASS' if all(checks.values()) else 'FAIL','checks':checks};(R/'qa_assertions.json').write_text(json.dumps(out,indent=2));print(json.dumps(out));raise SystemExit(0 if out['status']=='PASS' else 1)
