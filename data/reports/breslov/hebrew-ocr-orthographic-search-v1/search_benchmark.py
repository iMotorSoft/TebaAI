"""Offline query-candidate experiment; semantic embeddings optionally via existing DEV gateway.
No PG/Milvus/ingestion; source fixtures immutable. Gateway configuration through facade only.
"""
from pathlib import Path
import hashlib
import json
import math
import re
import sys
import unicodedata

OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT.parents[3] / 'SrvRestAstroLS_v1/backend'))
from modules.library.hebrew_lexical_normalizer import normalize_hebrew_search as fold

# Not a general linguistic rule. Directed lexeme candidates, exact whole tokens only.
# Context guards belong to fixtures for this experiment, not platform configuration.
CANDIDATES = {'פירוש':'פרוש', 'עיקר':'עקר', 'תחילה':'תחלה', 'תפילין':'תפלין',
              'בבוקר':'בבקר', 'תפילה':'תפלה', 'חידושין':'חדושין', 'עיבור':'עבור'}


def expand(original):
    tokens = fold(original).split()
    variants = []
    for i, token in enumerate(tokens):
        if token in CANDIDATES:
            changed = tokens.copy(); changed[i] = CANDIDATES[token]
            variants.append({'text':' '.join(changed), 'variant_type':'orthographic',
                             'original_query_preserved':True, 'rule_id':token+'->'+CANDIDATES[token]})
    return {'original_query':original, 'expanded_variants':variants[:4]}


def match(case):
    original, canonical = case['query'], case['canonical_source']
    exact = unicodedata.normalize('NFC', original) == unicodedata.normalize('NFC', canonical)
    unpointed = fold(original) == fold(canonical)
    variants = expand(original)
    candidate = any(v['text'] == fold(canonical) for v in variants['expanded_variants'])
    # Source evidence must confirm intended lexeme: observed context or pointed source.
    accepted = candidate and case.get('lexeme_guard') == 'confirmed_context'
    kind = 'exact' if exact else 'niqqud_insensitive' if unpointed else 'orthographic_variant' if accepted else None
    return {'exact':exact, 'no_niqqud':unpointed, 'variant_candidate_found':candidate,
            'variant':accepted, 'safest_match_type':kind, **variants,
            'canonical_source':canonical, 'canonical_sha256':hashlib.sha256(canonical.encode()).hexdigest()}


def cosine(a,b):
    return sum(x*y for x,y in zip(a,b)) / math.sqrt(sum(x*x for x in a) * sum(y*y for y in b))


def semantic(cases):
    import globalVar as g
    import httpx
    result = {'status':'BLOCKED', 'scope':'isolated in-memory exact cosine ranking of fixture snippets; not live corpus recall/Milvus ANN',
              'alias':g.EMBEDDINGS_MODEL_ALIAS, 'dimension':g.EMBEDDINGS_DIMENSION,
              'gateway_configured':bool(g.LITELLM_API_KEY), 'fallback_status':'NOT VERIFIED', 'rows':[]}
    if not g.LITELLM_API_KEY:
        result['reason']='DEV gateway key absent'; return result
    if g.LITELLM_BASE_URL.rstrip('/') not in ('http://127.0.0.1:4000','http://localhost:4000'):
        result['reason']='not verified local DEV endpoint'; return result
    headers={'Authorization':'Bearer '+g.LITELLM_API_KEY}
    try:
        with httpx.Client(base_url=g.LITELLM_BASE_URL, headers=headers, timeout=60) as client:
            info=client.get('/model/info')
            if info.status_code != 200:
                result['reason']='model preflight HTTP '+str(info.status_code); return result
            models=[r for r in info.json().get('data',[]) if r.get('model_name')==g.EMBEDDINGS_MODEL_ALIAS]
            upstream=[r.get('litellm_params',{}).get('model') for r in models]
            result['configured_upstream']=upstream
            result['configured_model_ids']=[r.get('model_info',{}).get('id') for r in models]
            if not models or any(m!='openai/'+g.EMBEDDINGS_MODEL_NAME for m in upstream):
                result['reason']='effective upstream mismatch'; return result
            inputs=list(dict.fromkeys([c['canonical_source'] for c in cases]+[c['query'] for c in cases]))
            probe=client.post('/embeddings',json={'model':g.EMBEDDINGS_MODEL_ALIAS,'input':['פֵּרוּשׁ']})
            result['probe_http']=probe.status_code
            if probe.status_code!=200:
                result['reason']='embedding probe failed'; return result
            response=client.post('/embeddings',json={'model':g.EMBEDDINGS_MODEL_ALIAS,'input':inputs})
            result['batch_http']=response.status_code
            if response.status_code!=200:
                result['reason']='embedding batch failed'; return result
            body=response.json()
            result['returned_model']=body.get('model')
            result['response_headers']={k:v for k,v in response.headers.items() if k in ('x-litellm-model-id','x-litellm-attempted-fallbacks','x-litellm-attempted-retries')}
            vectors=[r['embedding'] for r in sorted(body['data'],key=lambda r:r['index'])]
            if len(vectors)!=len(inputs) or any(len(v)!=g.EMBEDDINGS_DIMENSION for v in vectors):
                result['reason']='vector dimension/count mismatch'; return result
            if (body.get('model') not in (g.EMBEDDINGS_MODEL_NAME, g.EMBEDDINGS_MODEL_ALIAS)
                or result['response_headers'].get('x-litellm-model-id') not in result['configured_model_ids']
                or result['response_headers'].get('x-litellm-attempted-fallbacks') != '0'):
                result['reason']='model ID or fallback provenance not verified'; return result
            result['fallback_status']='VERIFIED: configured expected upstream; matching model ID; attempted fallbacks=0'
            result['status']='PASS_LOCAL_FIXTURE_EMBEDDINGS'
            result['input_count']=len(inputs); result['usage']=body.get('usage'); result['vectors_persisted']=False
            vec=dict(zip(inputs,vectors))
            corpus=list(dict.fromkeys(c['canonical_source'] for c in cases))
            for c in cases:
                ranked=sorted([(s,cosine(vec[c['query']],vec[s])) for s in corpus],key=lambda r:(-r[1],r[0]))
                rank=next(i for i,(s,_) in enumerate(ranked,1) if s==c['canonical_source'])
                result['rows'].append({'id':c['id'], 'target_rank':rank, 'target_cosine':cosine(vec[c['query']],vec[c['canonical_source']]),
                     'found_at_1':rank==1, 'found_at_3':rank<=3, 'top3':[{'canonical':s,'cosine':v} for s,v in ranked[:3]],
                     'match_type':'semantic', 'expected_positive':c['expected_positive']})
    except Exception as error:
        result['reason']='sanitized exception type: '+type(error).__name__
    return result


def run():
    fixtures=json.loads((OUT/'orthographic-fixtures.json').read_text())
    cases=fixtures['cases']
    before=json.dumps(cases,ensure_ascii=False)
    rows=[{'id':c['id'], 'expected_positive':c['expected_positive'], **match(c)} for c in cases]
    assert before==json.dumps(cases,ensure_ascii=False)
    sem=semantic(cases)
    for row in rows:
        sr=next((r for r in sem['rows'] if r['id']==row['id']),None)
        row['semantic']=sr
    positives=[r for r in rows if r['expected_positive']]
    negatives=[r for r in rows if not r['expected_positive']]
    result={'gate':'TEBAAI_BRESLOV_HEBREW_ORTHOGRAPHIC_SEARCH_VARIANTS_V1', 'status':'BLOCKED',
            'reason':'small curated development set, no independent holdout/full-corpus false-positive evaluation; semantic-only sufficiency not certified',
            'rows':rows, 'semantic_preflight':sem,
            'metrics':{'positive_count':len(positives),'negative_count':len(negatives),
                       'exact_recall':sum(r['exact'] for r in positives)/len(positives),
                       'no_niqqud_recall':sum(r['no_niqqud'] for r in positives)/len(positives),
                       'controlled_cascade_recall':sum(r['safest_match_type'] is not None for r in positives)/len(positives),
                       'false_positive_count':sum(r['safest_match_type'] is not None for r in negatives),
                       'variant_false_positive_count':sum(r['variant'] for r in negatives)},
            'ranking_contract':['exact','niqqud_insensitive','orthographic_variant','semantic'],
            'ranking_validation':'lexical precedence checked by tests; no end-to-end ranking claim',
            'canonical_mutations':0, 'query_mutations':0, 'production_integration':False}
    (OUT/'orthographic-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':run()
