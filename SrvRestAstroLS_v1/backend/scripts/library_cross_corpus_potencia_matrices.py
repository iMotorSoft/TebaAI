import json
from pathlib import Path
R=Path(__file__).resolve().parents[3]/'data/reports/breslov/2026-07-15-cross-corpus-qa-potencia-v1'
d=json.loads((R/'cross_corpus_qa_results.json').read_text());works=['Kitzur','LM II','LH','LM XV','La Potencia']
ev=[];cross=[]
for x in d:
 present={h['work'] for h in x['hits']};ev.append({'question_id':x['id'],'hit_count':len(x['hits']),'works':sorted(present),'evidence_types':sorted({h['evidence_type'] for h in x['hits']})});cross.append({'question_id':x['id'],**{w:w in present for w in works},'cross_relation':x['cross_relation']})
(R/'evidence_matrix.json').write_text(json.dumps(ev,ensure_ascii=False,indent=2));(R/'cross_corpus_matrix.json').write_text(json.dumps(cross,ensure_ascii=False,indent=2));print(json.dumps({'questions':len(d)}))
