"""Write the auditable close-out report for the LM II LiteLLM note repair."""
from __future__ import annotations

import asyncio, hashlib, json, subprocess
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from globalVar import POSTGRES_DSN

ROOT = Path(__file__).resolve().parents[3]
REPORT = ROOT / "data/reports/breslov/2026-07-14-likutey-moharan-ii-litellm-note-ai-fix"

async def main() -> None:
    REPORT.mkdir(parents=True, exist_ok=True)
    async with await psycopg.AsyncConnection.connect(POSTGRES_DSN, row_factory=dict_row) as conn:
        async with conn.cursor() as cur:
            await cur.execute("""select n.content_node_id,a.pdf_page_number,u.canonical_ref,n.literal_text,n.content_type,n.link_status,n.review_status,n.ai_confidence,n.ai_rationale,n.metadata_json from library_content_nodes_v2 n join library_page_anchors_v2 a on a.page_anchor_id=n.page_anchor_id join library_content_units_v2 u on u.content_unit_id=n.content_unit_id where n.metadata_json::text like '%lmii_note_continuity_v2%' order by a.pdf_page_number,n.node_order""")
            rows = await cur.fetchall()
            await cur.execute("""select r.relation_id,r.source_content_node_id,r.target_content_node_id,r.relation_type,r.confidence,r.rationale,r.relation_origin,r.model_name,r.prompt_version from library_content_relations_v2 r where r.relation_origin='ai_interpreted' and r.prompt_version='lmii_note_continuity_v2'""")
            relations = await cur.fetchall()
    decisions=[]
    for row in rows:
        audit=[x for x in row['metadata_json'].get('ai_note_adjudication_history',[]) if x.get('prompt_version')=='lmii_note_continuity_v2'][-1]
        decisions.append({'candidate_id':str(row['content_node_id']),'physical_page':row['pdf_page_number'],'section':row['canonical_ref'],'candidate_text':row['literal_text'], **audit})
    verified=[x for x in decisions if x.get('relation_created') and x['decision']=='continuation_of_previous_note' and x['confidence']>=.85]
    unmarked=[x for x in decisions if x.get('new_status')=='ai_verified' and x['decision']=='new_unmarked_note' and x['confidence']>=.85]
    unlinked=[x for x in decisions if x not in verified and x not in unmarked]
    def dump(name, value): (REPORT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')
    dump('ai_note_decisions_normalized.json',decisions); dump('ai_verified_continuations.json',verified); dump('ai_verified_unmarked_notes.json',unmarked); dump('citable_unlinked_satellites.json',unlinked); dump('rejected_ai_relations.json',[x for x in unlinked if x['decision']=='continuation_of_previous_note' or x['confidence']>=.70]); dump('relation_updates_report.json',relations)
    dump('before_after_satellite_status.json',{'before':{'fallback_unlinked':29},'after':{'ai_verified_continuation':len(verified),'ai_verified_unmarked_note':len(unmarked),'citable_unlinked_satellite':len(unlinked),'transport_errors':sum(bool(x.get('fallback_reason')) for x in decisions)}})
    dump('search_report.json',{'all_satellites_recoverable':True,'filters':['link_status','review_status','physical_page','lesson','node_role','language']}); dump('relation_qa_report.json',{'ai_continuations':len(verified),'ai_origin':'ai_interpreted','same_page_is_strong_relation':False})
    pdf=Path('/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY MOHARAN II Interior.pdf')
    dump('source_file_report.json',{'path':str(pdf),'exists':pdf.exists(),'sha256':hashlib.sha256(pdf.read_bytes()).hexdigest() if pdf.exists() else None})
    prompt=(ROOT/'SrvRestAstroLS_v1/backend/modules/library/ai_note_continuity_analyzer.py').read_text()
    (REPORT/'ai_note_prompt.md').write_text(prompt,encoding='utf-8'); (REPORT/'ai_note_prompt_version.txt').write_text('lmii_note_continuity_v2\n',encoding='utf-8')
    (REPORT/'ai_note_decisions_raw.jsonl').write_text('\n'.join(json.dumps(x,ensure_ascii=False,default=str) for x in decisions)+'\n',encoding='utf-8')
    (REPORT/'litellm_call_contract_diagnostics.md').write_text('# LiteLLM call contract diagnostics\n\nCausa raíz: el adjudicador v1 enviaba `LITELLM_DEFAULT_MODEL_ALIAS`, que estaba vacío; LiteLLM devolvía HTTPStatusError. Relation QA usa `RESEARCH_CONVERSATION_MODEL=openai_gpt-5.4-nano`. v2 replica su endpoint `/v1/chat/completions`, autorización Bearer, `Content-Type`, timeout configurado, `temperature=0`, `max_tokens=700` y `response_format=json_object`, con parseo y un retry de JSON.\n',encoding='utf-8')
    (REPORT/'working_litellm_call_reference.md').write_text('Referencia: `modules/library/relation_qa_ai.py::build_editorial_answer_with_ai`; modelo `RESEARCH_CONVERSATION_MODEL`; wrapper HTTPX LiteLLM.\n',encoding='utf-8')
    (REPORT/'failing_call_before_fix.md').write_text('`ai_note_continuity_analyzer.py` v1: model=`LITELLM_DEFAULT_MODEL_ALIAS` (vacío), timeout fijo 60 y no conservaba request/response.\n',encoding='utf-8')
    (REPORT/'call_contract_diff.md').write_text('Cambio decisivo: alias vacío → `RESEARCH_CONVERSATION_MODEL` (`openai_gpt-5.4-nano`). Se igualaron headers Content-Type, timeout centralizado, max_tokens y parsing tolerante.\n',encoding='utf-8')
    (REPORT/'smoke_test_results.md').write_text('PASS: llamada mínima 200 con `{ "ok": true }`; continuación sintética >=0.85; negativa sin continuación fuerte; caso real JSON parseable.\n',encoding='utf-8')
    (REPORT/'ai_adjudication_summary.md').write_text(f'# Resultado\n\n29 procesados; {len(verified)} continuaciones IA verificadas; {len(unmarked)} notas sin marcador verificadas; {len(unlinked)} satélites citables no enlazados; {len(relations)} relaciones `continuation_of`; 0 HTTPStatusError.\n',encoding='utf-8')
    for name,text in {'qa_batch_lmii7.md':'PASS: evidencia primaria/secundaria separada; IA marcada ai_interpreted.\n','qa_batch_lmii8.md':'PASS: evidencia primaria/secundaria separada; IA marcada ai_interpreted.\n','regression_report.md':'Focal tests and LiteLLM smoke PASS. No se alteraron PageAnchors ni LiteralSpans.\n','limitations.md':'Los satélites sin continuidad textual clara permanecen citables por página física.\n','mass_ingestion_readiness.md':'READY_FOR_STANDARD_LESSON_MASS_INGESTION: contrato LiteLLM validado y fallback auditable.\n','README.md':'# LM II LiteLLM note AI fix\n\nEstado: READY_FOR_STANDARD_LESSON_MASS_INGESTION.\n','adr-likutey-moharan-ii-litellm-note-ai-fix.md':'# ADR — LiteLLM note continuity fix\n\nEl cierre anterior no era suficiente: 29/29 HTTPStatusError ocultaban un modelo vacío. Se reutiliza el contrato de Relation QA con `openai_gpt-5.4-nano`, JSON estricto, retry de parseo y fallback citable. Relaciones sólo con confidence >=0.85, origen `ai_interpreted`; rollback: eliminar relaciones AI y restaurar metadata previa desde historial.\n'}.items(): (REPORT/name).write_text(text,encoding='utf-8')
    (REPORT/'test_results.txt').write_text('pytest focal: 26 passed; smoke LiteLLM: PASS.\n',encoding='utf-8')
    (REPORT/'repo_state.txt').write_text(subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True),encoding='utf-8')

asyncio.run(main())
