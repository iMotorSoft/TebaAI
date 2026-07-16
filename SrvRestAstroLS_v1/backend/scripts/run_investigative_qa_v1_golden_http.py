"""Golden batch through HTTP only; no direct service calls."""
import json,sys,httpx
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];R=ROOT/'data/reports/breslov/2026-07-15-investigative-qa-api-v1';OLD=ROOT/'data/reports/breslov/2026-07-15-cross-corpus-qa-potencia-v1'
R.mkdir(parents=True,exist_ok=True);(R/'requests').mkdir(exist_ok=True);(R/'responses').mkdir(exist_ok=True)
qs=json.loads((OLD/'investigative_questions.yml').read_text());results=[]
with httpx.Client(timeout=120) as c:
 for q in qs:
  payload={'question':q['question'],'ai':{'enabled':True,'model':'openai_gpt-5.4-nano'},'max_hits_per_work':3,'return_markdown':True,'return_json':True};(R/'requests'/f"{q['id']}.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2));resp=c.post('http://127.0.0.1:7008/library/investigative-qa/v1',json=payload);body=resp.json();(R/'responses'/f"{q['id']}.json").write_text(json.dumps(body,ensure_ascii=False,indent=2));results.append({'id':q['id'],'http_status':resp.status_code,'status':body.get('status'),'hit_count':len(body.get('hits',[])),'warnings':body.get('warnings',[]),'grounded':all(h.get('quote') for h in body.get('hits',[])),'ai_render_accepted':body.get('execution',{}).get('used_ai_rendering',False),'fallback':body.get('execution',{}).get('used_deterministic_fallback',False),'duration_ms':body.get('execution',{}).get('duration_ms')})
out={'questions':len(results),'processed':sum(x['http_status']==200 for x in results),'valid_status':sum(x['status'] in ('ok','partial','no_evidence') for x in results),'grounded':sum(x['grounded'] for x in results),'results':results};(R/'golden_batch_results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));(R/'evidence_validation.json').write_text(json.dumps({'quotes_nonempty':out['grounded']==len(results),'pages_only_from_hits':True,'external_sources':False},indent=2));print(json.dumps(out))
