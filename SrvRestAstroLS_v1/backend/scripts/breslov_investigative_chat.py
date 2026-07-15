#!/usr/bin/env python3
"""Terminal client; always consumes the HTTP contract, never service internals."""
import argparse,json
import httpx
p=argparse.ArgumentParser();p.add_argument('--endpoint',default='http://127.0.0.1:7008/library/investigative-qa/v1');p.add_argument('--question');p.add_argument('--format',choices=['enriched','json','both'],default='enriched');p.add_argument('--works');p.add_argument('--languages',default='es,he,en');p.add_argument('--include-audit',action='store_true');p.add_argument('--no-ai',action='store_true');p.add_argument('--show-debug',action='store_true');a=p.parse_args();history=[]
def ask(q):
 data={'question':q,'works':a.works.split(',') if a.works else ['kitzur','lmii','lh','lm_xv','potencia_plegaria'],'languages':a.languages.split(','),'include_audit':a.include_audit,'ai':{'enabled':not a.no_ai},'conversation':{'history':history}}
 r=httpx.post(a.endpoint,json=data,timeout=90);r.raise_for_status();x=r.json();history.extend([{'role':'user','content':q},{'role':'assistant','content':x['summary']}]);print(x['answer_markdown'] if a.format!='json' else json.dumps(x,ensure_ascii=False,indent=2));
 if a.format=='both' or a.show_debug:print('\n--- debug ---\n'+json.dumps({'interpretation':x['interpretation'],'search_plan':x['search_plan'],'warnings':x['warnings'],'execution':x['execution']},ensure_ascii=False,indent=2))
if a.question:ask(a.question)
else:
 print('Breslov Investigative Assistant — /exit para finalizar')
 while True:
  try:q=input('Investigador> ').strip()
  except EOFError:break
  if q in ('/exit','/quit'):break
  if q:ask(q)
