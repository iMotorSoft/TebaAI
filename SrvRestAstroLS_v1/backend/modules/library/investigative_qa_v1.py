"""Grounded conversational investigative QA; corpus evidence is authoritative."""
from __future__ import annotations
import json,re,time
from typing import Literal
import httpx
from pydantic import BaseModel,Field
from globalVar import LITELLM_API_KEY,LITELLM_BASE_URL,LITELLM_TIMEOUT_SECONDS,RESEARCH_CONVERSATION_MODEL

WORKS={'kitzur','lmii','lh','lm_xv','potencia_plegaria'}
class QaAi(BaseModel): enabled:bool=True;model:str='gpt-5.4-nano'
class QaRequest(BaseModel):
 question:str=Field(min_length=2,max_length=1000);works:list[str]=Field(default_factory=lambda:sorted(WORKS));languages:list[Literal['es','en','he']]=Field(default_factory=lambda:['es','he','en']);include_thematic:bool=True;include_audit:bool=False;min_evidence:Literal['literal','strong','medium','weak']='literal';max_hits_per_work:int=Field(default=10,ge=1,le=20);return_markdown:bool=True;return_json:bool=True;ai:QaAi=Field(default_factory=QaAi);conversation:dict=Field(default_factory=dict)
class Hit(BaseModel):
 hit_id:str;work_code:str;work_title:str;pdf_page:int|None=None;printed_page:int|None=None;quote:str;source_view:str;search_record_type:str;source_layer:str;zone_type:str|None=None;note_number:str|None=None;surface_form:str|None=None;normalized_reference_name:str|None=None;matched_terms:list[str];evidence_type:str;evidence_strength:Literal['strong','medium','weak'];relation_level:Literal['literal','contextual','thematic']='literal';warnings:list[str]=Field(default_factory=list)
def language(q:str)->str:
 return 'he' if re.search(r'[\u0590-\u05ff]',q) else 'en' if re.search(r'\b(where|what|prayer|fear|joy|faith)\b',q,re.I) else 'es'
def terms(q:str)->list[str]:
 base=re.findall(r"[\wáéíóúñÁÉÍÓÚÑ]+",q.lower()); maps={'plegaria':['plegaria','oración','rezar','rezo'],'oración':['oración','plegaria'],'fe':['fe','emuná','emuna'],'miedo':['miedo','temor'],'rebe':['rebe najmán'],'rabino':['rabí natán','reb noson'],'hitbodedut':['hitbodedut','aislamiento'],'conocimiento':['conocimiento','daat']};out=[]
 for x in base:out+=maps.get(x,[x])
 return list(dict.fromkeys([x for x in out if len(x)>2]))[:12]
async def _ai_interpret(question:str)->tuple[dict,list[str]]:
 fallback={'detected_language':language(question),'normalized_question':question,'concepts':terms(question),'requires_cross_corpus':True};
 if not LITELLM_API_KEY:return fallback,['ai_interpretation_fallback:litellm_key_missing']
 try:
  async with httpx.AsyncClient(timeout=LITELLM_TIMEOUT_SECONDS) as c:
   r=await c.post(f'{LITELLM_BASE_URL}/v1/chat/completions',headers={'Authorization':f'Bearer {LITELLM_API_KEY}'},json={'model':RESEARCH_CONVERSATION_MODEL,'messages':[{'role':'system','content':'Return JSON only: detected_language(es|en|he), normalized_question, concepts(array of literal search terms), requires_cross_corpus(boolean). Never provide citations.'},{'role':'user','content':question}],'temperature':0,'max_tokens':250,'response_format':{'type':'json_object'}})
  value=json.loads(r.json()['choices'][0]['message']['content']);return {'detected_language':value.get('detected_language',fallback['detected_language']),'normalized_question':value.get('normalized_question',question),'concepts':[str(x) for x in value.get('concepts',fallback['concepts'])][:12],'requires_cross_corpus':bool(value.get('requires_cross_corpus',True))},[]
 except Exception as e:return fallback,[f'ai_interpretation_fallback:{type(e).__name__}']
async def _fetch(conn,work:str,term:str,limit:int)->list[dict]:
 cfg={
 'kitzur':("select null::int pdf_page,null::int printed_page,content quote,'chunk' record,null::text zone,null::text note,null::text surface from library_document_chunks c join library_documents d on d.id=c.document_id where d.title='KITZUR' and content ilike %s limit %s",'Kitzur','library_document_chunks'),
 'lmii':("select pdf_page_number pdf_page,printed_page_number printed_page,literal_text quote,'page_literal' record,null::text zone,null::text note,null::text surface from library_lmii_search_ready_v2 where literal_text ilike %s limit %s",'Likutey Moharán II','library_lmii_search_ready_v2'),
 'lh':("select pdf_page,printed_page,coalesce(resolution_quote,nominal_reference_quote,note_source_quote,fine_zone_quote,page_text) quote,search_record_type record,fine_zone_type zone,visible_note_number::text note,surface_form surface from library_likutey_halajot_investigative_search_v1 where coalesce(resolution_quote,nominal_reference_quote,note_source_quote,fine_zone_quote,page_text,'') ilike %s limit %s",'Likutey Halajot','library_likutey_halajot_investigative_search_v1'),
 'lm_xv':("select pdf_page,printed_page,coalesce(text_quote,raw_text) quote,coalesce(zone_type,'page_literal') record,zone_type zone,null::text note,null::text surface from library_lm_xv_kdp_search_ready_v3 where coalesce(text_quote,raw_text,'') ilike %s limit %s",'Likutey Moharán XV KDP','library_lm_xv_kdp_search_ready_v3'),
 'potencia_plegaria':("select pdf_page,null::int printed_page,quote,search_record_type record,zone_type zone,note_number::text note,surface_form surface from library_la_potencia_plegaria_investigative_search_v1 where quote ilike %s limit %s",'La Potencia de la Plegaria','library_la_potencia_plegaria_investigative_search_v1')}
 sql,title,view=cfg[work]
 async with conn.cursor() as cur:
  await cur.execute(sql,(f'%{term}%',limit)); rows=await cur.fetchall()
 return [(r,title,view) for r in rows]
def classify(work:str,r:dict,term:str,i:int)->Hit:
 rec=r['record'];nom=bool(r['surface']);note=bool(r['note']);typ='validated_nominal_reference' if nom else 'validated_numbered_note' if note else 'validated_fine_zone_quote' if rec in ('fine_zone','main_text_spanish','main_text_hebrew') else 'literal_same_page';strength='strong' if typ.startswith('validated') or typ=='literal_same_page' else 'medium';warn=['pdf_page_null_for_kitzur_chunk'] if work=='kitzur' and r['pdf_page'] is None else []
 return Hit(hit_id=f'{work}-{i}-{abs(hash(r["quote"]))%1000000}',work_code=work,work_title={'kitzur':'Kitzur','lmii':'Likutey Moharán II','lh':'Likutey Halajot','lm_xv':'Likutey Moharán XV KDP','potencia_plegaria':'La Potencia de la Plegaria'}[work],pdf_page=r['pdf_page'],printed_page=r['printed_page'],quote=r['quote'][:900],source_view='',search_record_type=rec,source_layer=rec,zone_type=r['zone'],note_number=r['note'],surface_form=r['surface'],matched_terms=[term],evidence_type=typ,evidence_strength=strength,warnings=warn)
def render(question:str,hits:list[Hit],warnings:list[str])->str:
 lines=['## Síntesis investigativa',f'Se recuperaron {len(hits)} evidencias literales para: {question}.','', '## Evidencia principal']
 for h in hits[:20]:lines += [f'### {h.work_title} — PDF p. {h.pdf_page if h.pdf_page is not None else "no disponible"}',f'> {h.quote[:420]}',f'**Evidencia:** `{h.evidence_type}` · **Fuerza:** {h.evidence_strength} · **Capa:** `{h.source_layer}`','']
 lines += ['## Límites','- Los paralelos entre obras no demuestran una relación doctrinal.','- Una referencia nominal sólo acredita la aparición literal de esa forma.']
 if warnings:lines+=['','## Advertencias']+[f'- {w}' for w in sorted(set(warnings))]
 return '\n'.join(lines)
async def _ai_render(question:str,hits:list[Hit])->tuple[str|None,list[str],list[dict]]:
 """Closed-context renderer; unknown evidence IDs are rejected before response."""
 if not LITELLM_API_KEY:return None,['ai_render_fallback:litellm_key_missing'],[]
 context=[{'id':h.hit_id,'work':h.work_title,'page':h.pdf_page,'quote':h.quote,'type':h.evidence_type,'strength':h.evidence_strength,'warnings':h.warnings} for h in hits[:20]]
 try:
  async with httpx.AsyncClient(timeout=LITELLM_TIMEOUT_SECONDS) as c:
   r=await c.post(f'{LITELLM_BASE_URL}/v1/chat/completions',headers={'Authorization':f'Bearer {LITELLM_API_KEY}'},json={'model':RESEARCH_CONVERSATION_MODEL,'messages':[{'role':'system','content':'Return JSON only: answer_markdown, used_evidence_ids, claims. claims is an array of {claim,evidence_ids}. Use only supplied evidence. Never invent quotes/pages/works. Nominal references are literal appearances, never doctrine. State limits.'},{'role':'user','content':json.dumps({'question':question,'evidence':context},ensure_ascii=False)}],'temperature':0,'max_tokens':1200,'response_format':{'type':'json_object'}})
  v=json.loads(r.json()['choices'][0]['message']['content']);text,claims=validate_grounded_render(v,hits)
  if text is None:return None,['ai_render_rejected_grounding_validation'],[]
  return text,[],claims
 except Exception as e:return None,[f'ai_render_fallback:{type(e).__name__}'],[]
def validate_grounded_render(value:dict,hits:list[Hit])->tuple[str|None,list[dict]]:
 """Pure validator used by live renderer and adversarial regression tests."""
 used=set(value.get('used_evidence_ids',[]));allowed={h.hit_id for h in hits};text=str(value.get('answer_markdown',''));claims=value.get('claims',[])
 if not used or not used.issubset(allowed) or not text or not isinstance(claims,list) or any(not isinstance(x,dict) or not x.get('claim') or not set(x.get('evidence_ids',[])).issubset(allowed) or not x.get('evidence_ids') for x in claims):return None,[]
 pages={str(h.pdf_page) for h in hits if h.pdf_page is not None}
 if any(x not in pages for x in re.findall(r'(?i)(?:página|pdf p\.)\s*(\d+)',text)):return None,[]
 if re.search(r'(?i)(demuestra|dependencia doctrinal|prueba doctrinal)',text):return None,[]
 return text,claims
async def run(conn,data:QaRequest)->dict:
 started=time.perf_counter();warnings=[];interp,iw=await _ai_interpret(data.question) if data.ai.enabled else ({'detected_language':language(data.question),'normalized_question':data.question,'concepts':terms(data.question),'requires_cross_corpus':True},['ai_disabled']);warnings+=iw;plan={'queries':interp['concepts'] or terms(data.question),'works':[w for w in data.works if w in WORKS],'languages':data.languages,'layers':['page_literal','fine_zone','note_source_unit','nominal_reference'],'include_audit':False,'retrieval_mode':'sql_literal'};hits=[]
 for w in plan['works']:
  for term in plan['queries']:
   for row,title,view in await _fetch(conn,w,term,data.max_hits_per_work):
    h=classify(w,row,term,len(hits));h.source_view=view
    if h.hit_id not in {x.hit_id for x in hits}:hits.append(h)
 warnings += [z for h in hits for z in h.warnings];status='ok' if hits else 'no_evidence';markdown=render(data.question,hits,warnings);ai_markdown,aw,claims=await _ai_render(data.question,hits) if data.ai.enabled and hits else (None,[],[]);warnings+=aw
 if ai_markdown:markdown=ai_markdown
 matrix=[{'work_code':w,'hits':sum(h.work_code==w for h in hits)} for w in plan['works']];return {'question':data.question,'status':status,'answer_text':markdown,'answer_markdown':markdown,'summary':f'{len(hits)} evidencias literales recuperadas','conversation':{'conversation_id':data.conversation.get('conversation_id'),'turn_id':data.conversation.get('turn_id'),'resolved_context':[]},'interpretation':interp,'search_plan':plan,'works_consulted':plan['works'],'hits':[h.model_dump() for h in hits],'evidence_matrix':matrix,'cross_corpus_matrix':matrix,'claims':claims,'not_found':[] if hits else plan['queries'],'warnings':list(dict.fromkeys(warnings)),'execution':{'pipeline_version':'investigative_qa_v1','model':RESEARCH_CONVERSATION_MODEL,'used_ai_interpretation':data.ai.enabled and not iw,'used_ai_rendering':bool(ai_markdown),'ai_render_validated':bool(ai_markdown),'used_deterministic_fallback':not bool(ai_markdown),'used_vector':False,'used_external_sources':False,'used_ocr':False,'database':'postgresql','duration_ms':round((time.perf_counter()-started)*1000,2)}}
