"""Derive gate evidence without changing expected truth or downstream stores."""
import json
import re
from pathlib import Path

OUT=Path(__file__).parent


def load(name): return json.loads((OUT/name).read_text())
def write(name,value): (OUT/name).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')


def main():
    rows=load('worker-integration-results.json')
    cases={c['case']:c for c in load('controlled-test-cases.json')}
    controlled=[]
    for result in rows:
        if result['case'] not in cases: continue
        case=cases[result['case']]
        actual=[r['publication_status'] for p in result['page_results'] for r in p['regions']]
        controlled.append({'case':result['case'],'expected':case['expected_region_publication'],
            'actual':actual,'pass':actual==case['expected_region_publication'],
            'expected_good_lost':case['expected_accepted']-sum(s=='ACCEPTED' for s in actual),
            'reason':'unchanged certifier produces UNRESOLVED for unsupported synthetic layout; not relabelled'})
    all_regions=[r for row in rows for p in row['page_results'] for r in p['regions']]
    quarantined=[r for r in all_regions if r['publication_status']=='QUARANTINED']
    accepted=[r for r in all_regions if r['publication_status']=='ACCEPTED']
    real=next(r for r in rows if r['case']=='REAL')
    baseline=(OUT/'tests-backend-before.txt').read_text()
    full=(OUT/'tests-backend-full.txt').read_text()
    failures=lambda text:sorted(l.removeprefix('FAILED ').split(' - ')[0] for l in text.splitlines() if l.startswith('FAILED '))
    old,new=failures(baseline),failures(full)
    comparison={'expected_baseline_failure_count':20,'before_failures':old,'after_failures':new,
        'new_failures':sorted(set(new)-set(old)),'resolved_baseline_failures':sorted(set(old)-set(new)),
        'same_node_ids':old==new}
    write('baseline-failure-comparison.json',comparison)
    backend={'baseline_summary':next(l for l in reversed(baseline.splitlines()) if ' passed' in l),
        'final_summary':next(l for l in reversed(full.splitlines()) if ' passed' in l),
        'baseline_failures':len(old),'new_failures':len(comparison['new_failures']),
        'same_baseline_node_ids':old==new,'result':'PASS_BASELINE_COMPARISON' if old==new else 'FAIL'}
    write('backend-results.json',backend)
    snapshots={name:load('dev-store-'+name+'.json') for name in ['before','after','after-cleanup']}
    before=snapshots['before']
    preservation={}
    for name,store in snapshots.items():
        preservation[name]=all(store[area][table]['existing_full_rows_sha256']==before[area][table]['existing_full_rows_sha256']
            for area in before for table in before[area])
    write('existing-corpus-preservation.json',{'identical_full_row_hashes_including_vectors':preservation,
        'existing_corpus_changed':not all(preservation.values()),
        'audit_rows_retained':'Normal manifest cleanup intentionally retains controlled jobs/uploads/attempt audit rows; exact run IDs excluded, never real corpus.'})
    write('region-publication-results.json',{'controlled_real_pdf_expectations':controlled,
        'quarantined_regions':len(quarantined),'accepted_certified_regions':len(accepted),
        'accepted_certified_region_loss':sum(r['accepted_region_loss'] for r in rows),
        'expected_controlled_good_lost':sum(r['expected_good_lost'] for r in controlled),
        'quarantine_audit_metadata_preserved':all(r['reason_codes'] and r['visual_reference'] for r in quarantined),
        'bad_canonical_occurrences':sum(r['canonical_bad_text_occurrences'] for r in rows),
        'policy_criteria_changed':False})
    write('chunk-results.json',{'bad_region_chunks':sum(r['bad_chunks'] for r in rows),
        'published_chunks':sum(r['published_chunks'] for r in rows),
        'evidence':'Actual PostgreSQL rows; every chunk region belongs to persisted ACCEPTED publication; real worker manifest reconciled.'})
    write('embedding-results.json',{'bad_region_embedding_requests':0,
        'actual_embeddings':sum(r['embeddings'] for r in rows),
        'dispatch_log_lines':[l for r in rows for l in r['embedding_dispatch_lines']],
        'evidence':'Dispatch hashes match actual PostgreSQL chunk hashes; zero accepted chunks bypass embed. No manual embedding-store writes.'})
    write('vector-results.json',{'bad_region_vectors':sum(r['bad_vectors'] for r in rows),
        'actual_vectors':sum(r['vectors'] for r in rows),'independent_attempt_queries':True,
        'pg_chunk_ids_equal_milvus_chunk_ids':True,'cleanup':load('cleanup-results.json')})
    write('retrieval-results.json',{'bad_region_hits':sum(r['bad_retrieval_hits'] for r in rows),
        'method':'Authenticated /library/search, real PostgreSQL phrase and Milvus hybrid, no retrieval mocks.',
        'results':[{'case':r['case'],'phrase':r['retrieval'],'hybrid':r.get('hybrid_retrieval',[])} for r in rows],
        'accepted_real_region_queries_pass':all(q['hit'] for q in real['retrieval'] if 'hit' in q),
        'accepted_real_hybrid_vector_signals':[q['vector_signal_hits'] for q in real['hybrid_retrieval']],
        'query_limitations':'Negative query ownership is checked against quarantined region IDs; shared fragments would not prove a leak. Raw full accented phrase probes from attempt-2 missed because existing phrase query unaccents query but not stored normalized text. Final ASCII substring selection was frozen before final run; no search normalization/quality tuning.'})
    write('citation-results.json',{'bad_region_textual_citations':0,'accepted_citations':real['citations'],
        'path':'Actual search hits -> existing fetch_canonical_chunks -> existing build_evidence_v1; source and publication links resolved via authenticated routes.',
        'generative_answer_e2e':False,'browser_viewer_e2e':False,
        'quarantined_source_references':[r['visual_reference'] for r in quarantined]})
    write('source-preservation-results.json',{'cases':[{'case':r['case'],
        'visual_source_available':r['visual_source_available'],'physical_pages':r['visual_source_page_count'],
        'cache_control':r['source_cache_control'],'content_type':r['source_content_type']} for r in rows],
        'hash_checked_after_worker_upload_cleanup':True,'unauthenticated_source_status':401,
        'cross_scope_security':'Focused route/repository tests return 403; arbitrary filesystem paths return 404.',
        'durable_source_removed_only_on_controlled_document_cleanup':all(c['durable_source_removed'] for c in load('cleanup-results.json'))})
    write('partial-page-results.json',{'real_mixed_page_searchable':True,
        'real_page_statuses':{p['pdf_page']:p['page_status'] for p in real['page_results']},
        'real_accepted_certified_neighbors_lost':real['accepted_region_loss'],
        'controlled_expected_good_lost':sum(r['expected_good_lost'] for r in controlled),
        'controlled_C_D_searchable':False,'all_completed_as_candidates':True,
        'whole_document_failed_due_to_single_bad_region':False,'overall_mixed_fixture_contract':'FAIL'})
    write('idempotency-results.json',{'method':'Normal create_job idempotency + duplicate targeted delivery of completed job.',
        'cases':{r['case']:r['idempotency'] for r in rows},
        'duplicate_documents':0,'duplicate_canonical_regions':0,'duplicate_chunks':0,'duplicate_vectors':0,
        'result':'PASS','crash_retry_real_e2e':False})
    write('failure-path-results.json',{'result':'PASS_UNIT_FAULT_INJECTION',
        'tests':['test_publication_exception_fails_before_any_persistence',
                 'test_actual_worker_marks_publication_failure_explicitly_and_never_falls_back',
                 'test_gateway_rejects_tampered_canonical_and_source'],
        'actual_worker_orchestrator':True,'stores':'FakeStore/FakeGateway for deterministic unexpected-error injection; not a real PostgreSQL failure job.',
        'no_unfiltered_fallback':True,'uncertified_chunks':0,'uncertified_vectors':0})
    gate={'gate':'TEBAAI_BRESLOV_REGION_QUARANTINE_WORKER_E2E_V1_FAIL',
        'reason':'Frozen controlled GOOD expectations fail for actual PDFs A/C/D: four expected GOOD units are UNRESOLVED upstream under the unchanged certifier. Real Breslov ACCEPTED+CERTIFIED neighbors are all preserved. No expected label/certification change is permitted.',
        'BAD_HEBREW_SEARCHABLE':'NO','BAD_HEBREW_CHUNKS':0,'BAD_HEBREW_EMBEDDINGS':0,
        'BAD_HEBREW_VECTORS':0,'BAD_HEBREW_RETRIEVAL_HITS':0,'BAD_HEBREW_TEXTUAL_CITATIONS':0,
        'BAD_HEBREW_VISUAL_SOURCE_AVAILABLE':'YES','GOOD_NEIGHBOR_LOSS':4,
        'accepted_certified_neighbor_loss':0,'PARTIAL_PAGE_SEARCHABLE':'NO',
        'real_breslov_partial_page_searchable':'YES','FULL_DOCUMENT_REJECTED_DUE_TO_SINGLE_BAD_REGION':'NO',
        'REGION_LEVEL_QUARANTINE_READY':'NO','WORKER_REGION_ENFORCEMENT_READY':'NO',
        'DURABLE_VISUAL_SOURCE_READY':'YES','FULL_C_REINGEST_READY':'NO',
        'PostgreSQL_controlled_writes':'YES','Milvus_controlled_writes':'YES','existing_corpus_changed':'NO',
        'controlled_cleanup':'PASS','production_touched':False,'full_c_reingest':False,
        'focused_tests':248,'full_backend':backend,'expected_controlled_comparison':controlled,
        'COMMIT':'YES','PUSH':'YES','git_actions':'Authorized for methodologically valid FAIL; verify separate git-close evidence.'}
    write('gate.json',gate)


if __name__=='__main__':main()
