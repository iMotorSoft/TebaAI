# Rollback — PDF Ligature Literal Normalization V1 (DEV)

## Scope

Rollback is code-only. No persisted data changed in this phase: PostgreSQL
received zero writes (all audits ran read-only), Milvus was not touched,
chunks/embeddings were not regenerated, and no document status changed.

## Steps

1. Revert the functional code:

   ```bash
   cd /media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/TebaAI
   git revert <commit_feat_pdf_ligature>   # or restore from the commit before it
   ```

   The functional surface is:

   - `SrvRestAstroLS_v1/backend/modules/library/pdf_ligature_normalization.py`
     (new module; deleting it restores prior behavior);
   - `SrvRestAstroLS_v1/backend/modules/library/simple_research_rag.py`
     (query fragmentation variants + footnote number detection);
   - `SrvRestAstroLS_v1/backend/modules/library/simple_research_repository.py`
     (SQL literal lane with parenthetical-gloss elision);
   - `SrvRestAstroLS_v1/backend/tests/test_pdf_ligature_normalization.py` and
     `SrvRestAstroLS_v1/backend/tests/fixtures/pdf_ligature_literal_normalization_v1.json`;
   - `SrvRestAstroLS_v1/backend/scripts/audit_pdf_ligature_literal_normalization_v1.py`;
   - `SrvRestAstroLS_v1/astro/e2e/research-pdf-ligature-normalization.spec.ts`;
   - optional additive Hit fields (`matched_normalized_text`,
     `normalization_applied`, `normalization_kinds`).

2. Restart DEV backend: `./SrvRestAstroLS_v1/backend-dev.sh restart`.

3. Restore the 24/25 behavior (or the pre-phase baseline) and re-run:

   ```bash
   cd SrvRestAstroLS_v1/backend && uv run pytest -q
   ```

## No-op sections

- No database migration is required.
- No re-ingestion is required.
- No embedding recalculation is required.
- No Milvus operation is required.
- `Interior Final` remains `test_candidate` before and after rollback.
