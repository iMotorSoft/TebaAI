"""Accelerated, literal-only investigative resolution of Likutey Halajot references."""
from __future__ import annotations
import argparse, asyncio, json, re, sys
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import psycopg
from psycopg.rows import dict_row
from globalVar import POSTGRES_DSN

NOMINAL_RUN='likutey_halajot_nominal_reference_detector_v1_20260715'
FALSE_POSITIVE=re.compile(r'(?i)^(?:más |también$|la nota|el párrafo|el pasaje|apéndice|diagramas?\)?$|sección|la las notas|desde un extremo|el panim|a los peregrinos)')
BIBLE=re.compile(r'(?i)\b(Bereshit|Shemot|Vayikrá|Bamidbar|Devarim|Eclesiastés|Ezequiel|Jeremías|Job|Salmos|Zacarías)\s+\d+')
TALMUD=re.compile(r'(?i)\b(Berajot|Shabat|Jaguigá|Ioma|Sanedrín|Rosh HaShaná|Avot)\s+\d+')
COMMENTATOR=re.compile(r'(?i)\b(Rashi|Rashbam|Rambam|Ramban|Maharsha|Radak|Metzudat David|Bejor Shor|Rokeaj)\b')
WORK=re.compile(r'(?i)\b(Etz Jaim|Pri Etz Jaim|Shaar HaKavanot|Shaar HaMitzvot|Sefer HaBrit|Baal Shem Tov al HaTorá|Arba Olamot|Iaarot Devash|Partzufim|Kav)\b')
BRESLOV=re.compile(r'(?i)\b(LH,?\s+[^,;\n]+|Likutey Halajot|Likutey Mohar[aá]n|LM\s+[I1V]+)\b')

def resolve(row):
    surface=row['surface_form'].strip(); quote=row['text_quote']; chain=['exact_catalog_match:miss','variant_catalog_match:miss','corpus_cross_match:miss','parent_note_context:literal_quote_available','halakhah_context:not_used_for_resolution','multilingual_literal_match:miss']
    if FALSE_POSITIVE.search(surface):
        return ('rejected_false_positive',None,None,None,'false_positive_rule',chain+['false_positive_rule:internal_locator'],.98,['internal_locator_not_nominal_source'])
    for pattern,kind in ((BRESLOV,'breslov_work'),(BIBLE,'biblical_book'),(TALMUD,'talmudic_tractate'),(COMMENTATOR,'rabbinic_commentator'),(WORK,'rabbinic_work')):
        match=pattern.search(surface)
        if match:
            name=match.group(1).strip()
            if kind=='breslov_work' and name.upper().startswith('LH'):
                name='Likutey Halajot'
            return ('resolved_canonical_reference',kind,name,name,'deterministic_pattern',chain+[f'deterministic_pattern:{kind}'],.92,[])
    # Same literal name validated elsewhere is safe only if it already has one canonical mapping.
    mappings=row.get('cross_mappings') or []
    if len(mappings)==1 and mappings[0]:
        return ('resolved_canonical_reference',row['cross_kind'],mappings[0],mappings[0],'corpus_cross_match',chain+['corpus_cross_match:unique_validated_surface'],.90,[])
    return ('keep_generic_source','generic_source',None,surface,'fallback_keep_generic',chain+['fallback_keep_generic:literal_useful'],.72,['literal_reference_not_safely_normalized'])

async def main():
    p=argparse.ArgumentParser(); p.add_argument('--run-id',default=f'likutey_halajot_reference_resolution_investigative_v1_{date.today():%Y%m%d}');p.add_argument('--apply',action='store_true');args=p.parse_args()
    counts={}; total=inserted=0
    async with await psycopg.AsyncConnection.connect(POSTGRES_DSN,row_factory=dict_row) as conn:
      async with conn.cursor() as cur:
       await cur.execute("""select r.*,coalesce((select array_agg(distinct v.normalized_reference_name) from library_likutey_halajot_nominal_references_v1 v where v.surface_form=r.surface_form and v.validation_status='validated' and v.normalized_reference_name is not null),array[]::text[]) cross_mappings,(select max(v.reference_kind) from library_likutey_halajot_nominal_references_v1 v where v.surface_form=r.surface_form and v.validation_status='validated') cross_kind from library_likutey_halajot_nominal_references_v1 r where r.nominal_reference_run_id=%s and r.reference_kind='generic_source' order by r.pdf_page,r.id""",(NOMINAL_RUN,))
       for row in await cur.fetchall():
        total+=1; decision,kind,name,family,method,chain,confidence,warnings=resolve(row);counts[decision]=counts.get(decision,0)+1
        if args.apply:
         await cur.execute("""insert into library_likutey_halajot_nominal_reference_resolution_v1(nominal_reference_id,document_id,pdf_page,printed_page,visible_note_number,halakhah_header_hint,surface_form,original_reference_kind,original_validation_status,original_normalized_reference_name,original_quote,resolution_run_id,resolution_decision,resolved_reference_kind,resolved_normalized_reference_name,resolved_surface_family,resolution_method,resolver_chain,evidence_quote,evidence_surface_form,evidence_context,confidence,warnings) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s::jsonb,%s,%s::jsonb) on conflict(resolution_run_id,nominal_reference_id) do update set resolution_decision=excluded.resolution_decision,resolved_reference_kind=excluded.resolved_reference_kind,resolved_normalized_reference_name=excluded.resolved_normalized_reference_name,resolved_surface_family=excluded.resolved_surface_family,resolution_method=excluded.resolution_method,resolver_chain=excluded.resolver_chain,evidence_quote=excluded.evidence_quote,evidence_surface_form=excluded.evidence_surface_form,evidence_context=excluded.evidence_context,confidence=excluded.confidence,warnings=excluded.warnings""",(row['id'],row['document_id'],row['pdf_page'],row['printed_page'],row['visible_note_number'],row['halakhah_header_hint'],row['surface_form'],row['reference_kind'],row['validation_status'],row['normalized_reference_name'],row['text_quote'],args.run_id,decision,kind,name,family,method,json.dumps(chain),row['text_quote'],row['surface_form'],json.dumps({'nominal_reference_id':str(row['id']),'page_first_quote_verified':True,'ai':'ai_not_required_deterministic_resolution'}),confidence,json.dumps(warnings)));inserted+=cur.rowcount
       if args.apply: await conn.commit()
    print(json.dumps({'run':args.run_id,'apply':args.apply,'total':total,'inserted':inserted,'decisions':counts,'ai':'ai_not_required_deterministic_resolution'},ensure_ascii=False))
if __name__=='__main__': asyncio.run(main())
