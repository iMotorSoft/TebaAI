"""Read-only Level 3 diagnostic for the explicit Kitzur Ingesta V2 run."""
import asyncio, json, os, re
from pathlib import Path
import httpx, psycopg

RUN_ID = "492acd8d-06bd-42ac-a511-f3ec52f97bb3"
SCOPE = "breslov_test"
BASE = "http://127.0.0.1:7008"
OUT = Path(__file__).with_name("metrics.json")

Q = [
 ("q1_teshuva", "Teshuvá", "¿Cómo describe el Kitzur Likutey Moharán el proceso de teshuvá: humildad ante insultos, confesión, vergüenza, juicio de sí mismo, Keter y arrepentirse de arrepentimientos anteriores?", [20,21,29,30,31,32,33,65,66,204,205], ["insultos en silencio","confesión verbal","juzgarse a sí mismo","temores caídos","vergüenza","arrepentirse del arrepentimiento anterior","correr y retornar","Keter","EHIéH"]),
 ("q2_pureza", "Pureza sexual", "¿Cómo se alcanza la pureza sexual mediante Lenguaje Sagrado, apartar pensamientos lujuriosos, tzitzit y rectificación del brit, y qué beneficios trae para plegaria, sabiduría, voz, sustento y rúaj hakodesh?", [17,36,81,82,136,137,140,145], ["Lenguaje Sagrado","pensamientos lujuriosos","tzitzit","pureza sexual","merecer orar","rostro radiante","sabiduría","voz para cantar","sustento","espíritu sagrado"]),
 ("q3_plegaria", "Plegaria perfecta", "¿Cómo se alcanza la plegaria perfecta: sinceridad y verdad, energía y alegría, unión con verdaderos Tzadikim, eliminación de pensamientos extraños y orgullo, unidad interior y paz?", [17,18,25,41,60,61,292,293,331,332], ["sinceridad","verdad","alegría","verdaderos Tzadikim","pensamientos ajenos","orgullo","plegaria perfecta","paz general"]),
 ("q4_hitbodedut", "Hitbodedut", "¿Qué es hitbodedut como plegaria personal, conversación con el Creador y juicio de sí mismo, y qué beneficios tiene: eliminar temores caídos, luz oculta, vergüenza y llevar el mundo al bien?", [65,66,166,167,202,203,237,466], ["idioma familiar","conversación con el Creador","noche","fuera de las zonas habitadas","unirse a Dios","juzgarse a sí misma","temores caídos","luz oculta","vergüenza"]),
 ("q5_shabat", "Shabat", "¿Cómo relaciona el Kitzur la santidad y alegría de Shabat con fe, bendiciones, daat, compasión, alma adicional, comer en Shabat, libertad y elevación de temores caídos?", [159,160,328,341,343,344,404,461,462], ["encarnación de la fe","bendiciones","pies","daat","compasión","alma adicional","comer en Shabat","alegría del Shabat","libertad","temores caídos"]),
 ("q6_punto_bueno", "Punto bueno", "¿Qué enseña la Lección 282 sobre el punto bueno o nekudá tová: buscar bien aun entre pecados, evitar depresión, lograr alegría y plegaria, y juzgar favorablemente?", [407,408,409,410,411], ["Lección 282","punto bueno","puntos buenos","impurezas","vida y alegría","orar","líder de la plegaria","juzgar favorablemente"]),
 ("q7_temor_angeles", "Temor y ángeles", "¿Cómo se alcanza el temor perfecto a Dios y el dominio sobre los ángeles mediante rectificar deseos de dinero, sexualidad y comida, Tres Festividades, plegaria perfecta y unión a líderes verdaderos?", [419,420,421,422,423,424], ["dominio sobre los ángeles","temor perfecto","dinero","placer sexual","comida","Pesaj","Shavuot","Sukot","plegaria perfecta","líderes verdaderos","almas de Israel"]),
]

def tok(n): return round(n / 4)
async def main():
 conf=dict(user=os.environ['DB_PG_USER'], password=os.environ['DB_PG_PASS'], host=os.environ.get('DB_PG_IP','localhost'), port=int(os.environ.get('DB_PG_PORT','5432')), dbname='tebaai')
 conn=await psycopg.AsyncConnection.connect(**conf)
 async with httpx.AsyncClient(timeout=60) as http:
  login=await http.post(BASE+'/auth/login',json={'email':os.environ['TEBAAI_E2E_ADMIN_EMAIL'],'password':os.environ['TEBAAI_E2E_ADMIN_PASSWORD']})
  login.raise_for_status(); headers={'Authorization':'Bearer '+login.json()['access_token']}
  rows=[]
  for qid,title,longq,pages,claims in Q:
   long=await http.post(BASE+'/library/book-qa',headers=headers,json={'question':longq,'run_id':RUN_ID,'scope_code':SCOPE,'top_k':20,'language':'es'})
   data=long.json()
   claim_results=[]
   for claim in claims:
    r=await http.post(BASE+'/library/book-qa',headers=headers,json={'question':'¿Dónde aparece '+claim+'?','run_id':RUN_ID,'scope_code':SCOPE,'top_k':20,'language':'es'})
    d=r.json(); claim_results.append({'claim':claim,'http':r.status_code,'sources':len(d.get('sources',[])),'pages':[s.get('page_number') for s in d.get('sources',[])]})
   page_hits=[]
   async with conn.cursor() as cur:
    for p in pages:
     await cur.execute('SELECT text FROM library_pages_v2 WHERE run_id=%s AND page_number=%s',(RUN_ID,p))
     x=await cur.fetchone(); text=x[0] if x else ''
     matched=[c for c in claims if c.lower() in text.lower()]
     page_hits.append({'page':p,'text_chars':len(text),'matched_claim_phrases':matched})
   long_sources=data.get('sources',[])
   rows.append({'question_id':qid,'title':title,'long_question':longq,'long':{'query_chars':len(longq),'approx_query_tokens':tok(len(longq)),'top_k':20,'chunks_retrieved':len(long_sources),'unique_pages':len({x.get('page_number') for x in long_sources if x.get('page_number')}),'retrieved_context_chars':sum(len(x.get('snippet','')) for x in long_sources),'truncation_detected':'unknown','status_code':long.status_code,'answer_type':data.get('answer_type'),'warnings':data.get('warnings',[])},'claims':claim_results,'page_direct':page_hits,'expected_pages':pages})
 await conn.close()
 OUT.write_text(json.dumps({'run_id':RUN_ID,'scope_code':SCOPE,'model_runtime':'openai_gpt-5.4-nano','rows':rows},ensure_ascii=False,indent=2))
asyncio.run(main())
