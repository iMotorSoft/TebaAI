# Rollback — Editorial Evidence Granularity & Stable IDs V1 (DEV)

## Scope

Code-only rollback. No data changed: PostgreSQL read-only, Milvus untouched,
no reingestion.

## Steps

1. Revert the function change:

   ```bash
   cd /media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/TebaAI
   git revert <commit>  # or restore simple_research_rag.py from pre-phase
   ```

   Files changed:
   - `backend/modules/library/simple_research_rag.py`: `_evidence_id` back to
     chunk-only, remove `_entity_key`, `_legacy_chunk_evidence_id`, remove
     `legacy_evidence_id` and `evidence_identity_version` from
     `_frontend_hit`;
   - `backend/tests/test_canonical_editorial_evidence_selection.py`: revert
     `test_evidence_id_stable` to original;
   - `backend/tests/test_editorial_evidence_granularity_v1.py`: remove;
   - `backend/tests/fixtures/editorial_evidence_granularity_stable_ids_v1.json`:
     remove;
   - `backend/scripts/audit_editorial_evidence_granularity_stable_ids_v1.py`:
     remove;
   - `astro/src/components/research/investigativeQaClient.ts`: remove
     `legacy_evidence_id` and `evidence_identity_version` from Hit interface.

2. Restart backend: `./SrvRestAstroLS_v1/backend-dev.sh restart`.

3. Run `uv run pytest -q` (expected 1482).

## No-op

- No database migration.
- No reingestion.
- No embedding recalculation.
- No Milvus operation.
- `Interior Final` remains `test_candidate`.
