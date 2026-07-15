"""Read-only LiteLLM spike: candidate zones, never corpus authority."""
from __future__ import annotations
import argparse,asyncio,json,re
from pathlib import Path
import fitz,httpx
from globalVar import LITELLM_API_KEY,LITELLM_BASE_URL,LITELLM_TIMEOUT_SECONDS
from modules.library.ai_model_routing import model_for_task
PAGES=(28,29,30,31,96,130,178,222,266,314,364,394,100,140,188,230,275,320,370,398,403,404,405,2,8,10,402,412,3,4,5)
PDF=Path('/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY MOHARAN II Interior.pdf')
async def main(output: Path, pages: tuple[int,...] = PAGES):
 doc=fitz.open(PDF);out=[]
 output.parent.mkdir(parents=True,exist_ok=True)
 output.write_text('',encoding='utf-8')
 async with httpx.AsyncClient(timeout=LITELLM_TIMEOUT_SECONDS) as c:
  for page in pages:
   text=doc[page-1].get_text('text')
   payload={'model':model_for_task('ocr_layout_zone_detection'),'messages':[{'role':'system','content':'You classify candidate textual zones for research retrieval. Never invent text, pages, note numbers or relations. Return JSON only.'},{'role':'user','content':json.dumps({'document':'Likutey Moharan II','pdf_page':page,'printed_page':page-10,'page_text':text[:9000],'task':'Return zones [{kind,marker,confidence,rationale}] and page_kind (lesson|diagram|blank|unknown). Candidate only; not authoritative ingestion.'},ensure_ascii=False)}],'temperature':0,'max_tokens':900,'response_format':{'type':'json_object'}}
   try:
    r=await c.post(f'{LITELLM_BASE_URL}/v1/chat/completions',headers={'Authorization':f'Bearer {LITELLM_API_KEY}','Content-Type':'application/json'},json=payload);raw=r.text
    try: parsed=json.loads(r.json()['choices'][0]['message']['content']); ok=r.status_code==200
    except Exception: parsed={'error':'invalid_json'};ok=False
    row={'pdf_page':page,'status_code':r.status_code,'pass':ok,'raw_response':raw,'parsed':parsed}
   except httpx.HTTPError as exc: row={'pdf_page':page,'status_code':None,'pass':False,'error':type(exc).__name__}
   out.append(row)
   with output.open('a',encoding='utf-8') as f: f.write(json.dumps(row,ensure_ascii=False)+'\n')
   print(json.dumps({'page':page,'pass':row['pass']}),flush=True)
 return out
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path('/tmp/lmii_zone_functional.jsonl'));p.add_argument('--pages');a=p.parse_args(); pages=tuple(int(x) for x in a.pages.split(',')) if a.pages else PAGES;asyncio.run(main(a.output,pages))
