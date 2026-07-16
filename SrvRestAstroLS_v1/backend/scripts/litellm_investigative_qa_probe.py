import json,httpx,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from globalVar import LITELLM_BASE_URL,LITELLM_API_KEY,RESEARCH_CONVERSATION_MODEL,LITELLM_TIMEOUT_SECONDS
R=Path(__file__).resolve().parents[3]/'data/reports/breslov/2026-07-15-investigative-qa-ai-gate-v1';R.mkdir(parents=True,exist_ok=True)
cases=[('simple','Respondé únicamente con la palabra OK.'),('json','Respondé sólo JSON: {"detected_language":"es","concepts":["plegaria"]}'),('es','¿Dónde aparece la plegaria?'),('en','Where is prayer discussed?'),('he','היכן מופיעה התפילה?')];out=[]
for name,prompt in cases:
 r=httpx.post(LITELLM_BASE_URL+'/v1/chat/completions',headers={'Authorization':'Bearer '+LITELLM_API_KEY},json={'model':RESEARCH_CONVERSATION_MODEL,'messages':[{'role':'user','content':prompt}],'temperature':0,'max_tokens':120,'response_format':{'type':'json_object'} if name=='json' else None},timeout=LITELLM_TIMEOUT_SECONDS);body=r.json();out.append({'case':name,'status':r.status_code,'model':body.get('model'),'request_id':body.get('id') or r.headers.get('x-request-id'),'content':body.get('choices',[{}])[0].get('message',{}).get('content',''),'usage':body.get('usage')})
(R/'litellm_probe_results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps({'cases':len(out),'success':sum(x['status']==200 for x in out)}))
