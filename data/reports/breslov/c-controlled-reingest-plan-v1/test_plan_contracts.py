"""Offline report consistency/safety tests. Never import the live inventory helper."""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).parent


def load(name):
    return json.loads((ROOT / name).read_text())


def test_current_identity_and_source():
    identity = load('current-c-identity.json')
    pg = load('postgres-before.json')
    source = load('current-c-source-inventory.json')
    assert identity['id'] == pg['selected_document_id']
    assert identity['pages'] == len(pg['pages']) == 284
    assert identity['active_chunks'] == len(pg['chunks']) == 942
    assert identity['active_vectors'] == len(pg['embeddings']) == 942
    assert source['external_original_verified']
    original = next(r for r in source['references'] if r['exists'])
    assert original['sha256'] == identity['source_sha256'] == source['approved_sha256']
    assert original['pages'] == 284
    assert not identity['source_durable']
    assert identity['source_path'] is None


def test_vector_chunk_identity_not_just_counts():
    pg = load('postgres-before.json')
    mv = load('current-c-milvus-inventory.json')
    chunks = {c['id']: c for c in pg['chunks']}
    vectors = {v['pk']: v for v in mv['pk_chunk_map']}
    assert {v['chunk_id'] for v in vectors.values()} == set(chunks)
    for e in pg['embeddings']:
        v = vectors[e['milvus_primary_key']]
        assert v['chunk_id'] == e['chunk_id']
        assert v['content_sha256'] == e['content_sha256'] == chunks[e['chunk_id']]['content_sha256']
        assert v['embedding_dimension'] == e['embedding_dimension'] == 1536
    for field in ('missing_chunk_ids', 'extra_chunk_ids', 'missing_tracking_pks', 'extra_tracking_pks', 'metadata_mismatches', 'orphan_vectors_loaded_collections'):
        assert mv[field] == []


def test_inventory_queries_only_select_and_read_only_session():
    queries = load('queries-before.json')
    assert queries
    assert all(q['sql'].lstrip().upper().startswith('SELECT ') for q in queries)
    for helper in ('inventory_readonly.py', 'indexes_readonly.py'):
        text = (ROOT / helper).read_text()
        assert 'default_transaction_read_only=on' in text
        assert 'REPEATABLE READ READ ONLY' in text
        tree = ast.parse(text)
        forbidden = {'upsert', 'insert', 'delete', 'flush', 'load_collection', 'release_collection', 'create_collection', 'ensure_collection', 'preserve_source', 'claim_next_job', 'run_worker'}
        # sys.path.insert configures import resolution, not a store insertion.
        assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                       and n.func.attr in forbidden and ast.unparse(n.func) != 'sys.path.insert'
                       for n in ast.walk(tree))
        assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in forbidden for n in ast.walk(tree))


def test_history_distinguishes_current_and_deleted():
    inv = load('current-c-run-inventory.json')
    assert len(inv['current_runs']) == 1
    assert inv['current_runs'][0]['active']
    assert all(not r['active'] for r in inv['historical_known_generations'])
    assert inv['historical_generations_without_recoverable_run_id'] == 2
    assert len([r for r in inv['historical_known_generations'] if r['run_id'] is None]) == 2


def test_gaps_prevent_execution_and_phases_complete():
    matrix = load('generation-capability-matrix.json')
    assert not matrix['execution_ready']
    by_name = {c['capability']: c for c in matrix['capabilities']}
    assert by_name['visibility switch']['classification'] == 'MISSING'
    assert by_name['retrieval isolation']['classification'] == 'MISSING'
    assert by_name['active generation pointer']['classification'] == 'MISSING'
    assert by_name['page publication route isolation']['classification'] == 'MISSING'
    assert by_name['region-level status']['classification'] == 'EXISTS'
    plan = (ROOT / 'C_CONTROLLED_REINGEST_EXECUTION_PLAN.md').read_text()
    for phase in range(10):
        assert f'## Phase {phase} —' in plan
    assert 'No NEW ID/job exists in this gate' in plan


def test_live_uniqueness_blocks_parallel_same_source_document():
    """The candidate strategy must not assume a second same-source document row."""
    idx = load('indexes-readonly.json')
    unique = {i['indexname']: i['indexdef'] for i in idx['unique_indexes']
              if i['tablename'] == 'library_documents'}
    assert 'uq_library_documents_scope_collection_sha256' in unique
    assert 'source_sha256' in unique['uq_library_documents_scope_collection_sha256']
    plan = (ROOT / 'C_CONTROLLED_REINGEST_EXECUTION_PLAN.md').read_text()
    assert 'uq_library_documents_scope_collection_sha256' in plan
    assert 'Candidate admission models' in plan


def test_reconciliation_contract_zero_tolerance():
    contract = (ROOT / 'C_RECONCILIATION_CONTRACT.md').read_text()
    for phrase in ('EXPECTED_QUARANTINE_REMOVAL', 'UNEXPECTED_LOSS', 'UNEXPECTED_GAIN',
                   'good-neighbor loss', 'active duplicate evidence'):
        assert phrase in contract
    assert 'OLD_CHUNK_COUNT == NEW_CHUNK_COUNT' in contract
    assert 'UNKNOWN, skipped critical checks' in contract


def test_rollback_runbook_is_reversible_without_reingest():
    runbook = (ROOT / 'C_ROLLBACK_RUNBOOK.md').read_text()
    assert 'ROLLBACK POSSIBLE = YES' in runbook
    assert 'ROLLBACK REQUIRES REINGESTING OLD C = NO' in runbook
    assert 'OLD PHYSICALLY DELETED AT CUTOVER = NO' in runbook
    assert 'CUTOVER REVERSIBLE BEFORE CLEANUP = YES' in runbook


def test_gate_result_is_plan_only():
    gate = load('gate.json')
    assert gate['result'] == 'TEBAAI_BRESLOV_C_CONTROLLED_REINGEST_PLAN_V1_PASS'
    assert gate['PLAN_READY'] == 'YES'
    assert gate['PREREQUISITE_IMPLEMENTATION_REQUIRED'] == 'YES'
    assert gate['READY_FOR_C_REINGEST_EXECUTION_GATE'] == 'NO'
    assert gate['C_REINGEST_EXECUTED'] == 'NO'
    assert gate['postgres_writes'] == 0
    assert gate['milvus_data_writes'] == 0
    assert gate['worker_jobs_created'] == 0


def test_before_after_inventories_show_no_mutation():
    pg_b = load('postgres-before.json')
    pg_a = load('postgres-after.json')
    pg_b.pop('captured_at')
    pg_a.pop('captured_at')
    assert pg_b == pg_a
    mv_b = load('milvus-before.json')
    mv_a = load('milvus-after.json')
    mv_b.pop('captured_at')
    mv_a.pop('captured_at')
    assert mv_b == mv_a
    assert load('source-before.json') == load('source-after.json')
