"""Offline protected-C comparison; no runtime imports or store connections."""
import importlib.util
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
SOURCE = OUT.parent / 'c-parallel-generation-safety-v1' / 'summarize_inventory.py'


def main():
    spec = importlib.util.spec_from_file_location('foundation_summary', SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OUT = OUT
    results = [module.summary(label) for label in ('before', 'after')]
    for label, result in zip(('before', 'after'), results):
        module.save(f'{label}-c-inventory.json', result)
    before, after = results
    keys = ('document_metadata_sha256', 'fingerprints', 'vectors_sha256',
            'historical_live_runs', 'generation_document_count_by_scope_and_source',
            'active_chunk_count_observed', 'active_vector_count_observed')
    comparisons = {key: before[key] == after[key] for key in keys}
    assert before['active_chunk_count_observed'] == after['active_chunk_count_observed'] == 942
    assert before['active_vector_count_observed'] == after['active_vector_count_observed'] == 942
    assert before['observed_active_run'] == after['observed_active_run'] == '6c1a19b8-b60b-52de-b709-5496f4c6e937'
    source_equal = before['source_metadata'] == after['source_metadata']
    assert source_equal and all(comparisons.values())
    module.save('integrity-verification.json', {
        'comparisons': comparisons, 'source_before_after_equal': source_equal,
        'current_c_content_unchanged': True, 'c_reingest_executed': False,
        'source_durability_resolved': False, 'source_metadata_repair_executed': False,
        'current_c_pg_content_writes': 0, 'current_c_milvus_content_writes': 0,
        'production_touched': False,
        'limitations': 'Read-only observations, not a global writer fence or restorable vector backup.',
    })
    print('CURRENT_C_CONTENT_UNCHANGED=YES; 942 chunks; 942 vectors; source and run unchanged')


if __name__ == '__main__':
    main()
