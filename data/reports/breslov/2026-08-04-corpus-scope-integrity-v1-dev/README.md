# Breslov Corpus Scope Integrity Review V1 — DEV

## Result

`TEBAAI_BRESLOV_CORPUS_SCOPE_INTEGRITY_V1_DEV_BLOCKED`

No functional scope fix was applied. The mandatory reclassification premise was
rejected by the source itself.

## Preflight

- branch: `feature/console-backend-core`;
- initial HEAD: `9e88eee4f6fa82141dab1814f6af69748b55b8b9`;
- backend and Astro were initially stopped and were started only through the
  canonical DEV launchers;
- PostgreSQL `/ready`: up, database `tebaai`;
- Milvus collection `tebaai_breslov_chunks_v1`: Loaded, 5,370 entities;
- LiteLLM model inventory contains the expected embedding and generation aliases;
- unrelated dirty-worktree files were preserved.

PostgreSQL, Milvus and LiteLLM were not started, stopped, restarted or
reconfigured.

## Disputed record

| Field | Value |
|---|---|
| ID | `56ddcc3b-8296-4832-ac95-2bfe032cd4c6` |
| Title | `Likutey Halajot LM II 8` |
| Filename | `LIKUTEY HALAJOT LM II 8.pdf` |
| SHA-256 | `c04601782711751c14539224e8f679a740090b9d7f5f09d8877db9c3b6a5ff74` |
| Status | `ready` |
| Chunks / embeddings | 1,205 / 1,205 |
| Canonical family demonstrated | `likutey_halajot` |
| Related source lesson | `likutey_moharan_ii_8` |

### Internal evidence

The title page says `Likutey Halajot` and describes **eleven lessons based on**
Likutey Moharán II, 8. The contents enumerate Likutey Halajot discourses such
as Hiljot Tzitzit, Kriat HaTorá, Beit HaKneset, Netilat Iadaim, Birkat HaReiaj,
Iom Tov, Jol HaMoed and Suká. The edition note explicitly says those selected
Likutey Halajot lessons were chosen because they are based on LM II, 8.

Aggregate persisted evidence:

- 489/1,205 chunks mention Likutey Halajot;
- 422/1,205 contain Hiljot headings;
- 228/1,205 mention LM II, 8 because it is their common source lesson.

The prior audit sampled the source-lesson reference without preserving the
container/edition context. `work_family` and `source_lesson` were conflated.

## End-to-end scope trace

`resolve_ready_documents(... work_codes=["lh"])` includes the disputed row.
`resolve_ready_documents(... work_codes=["lmii"])` excludes it. Milvus has
1,205 corresponding vectors, but receives PostgreSQL-resolved document IDs; no
SQL/Milvus family disagreement or stale-family metadata was demonstrated.

The row therefore enters LH at title matching for a bibliographically correct
reason. Removing it from LH would be a false classification, not a scope repair.

## Natural QA and edition selection

The prior authenticated baseline remains:

- Investigative QA: 1/5 `Interior Final` primaries under the prior
  edition-specific expectation;
- Relation QA: 2/5 `Interior Final` primaries under that expectation.

Those numbers cannot be converted into family-integrity failures: three
Relation primaries come from another valid Likutey Halajot source. A query that
says only `en Likutey Halajot` does not specify `Interior Final`. Selecting one
edition requires explicit edition/source scope and reviewed canonical metadata.
A document-ID exclusion, title penalty or status manipulation was prohibited
and would be incorrect.

## Note 36

The exact failed query is:

`Birur hace referencia a la extracción y refinamiento de las chispas`

The expected page 56/38 contains `reﬁ namiento`: the PDF extraction preserved a
compatibility ligature and inserted a space inside the word. The candidate did
not enter the final literal context and semantic evidence from other works won.
This is an independent literal-normalization/candidate-recall defect. It was not
changed in this blocked phase; the expanded batch remains 24/25.

## Matrix

| Control | Result |
|---|---|
| Disputed row identified | PASS |
| Real family proved from internal evidence | PASS — Likutey Halajot |
| Prior cross-family hypothesis | REJECTED |
| LH resolver includes valid LH source | PASS |
| LM II resolver excludes disputed LH source | PASS |
| SQL↔Milvus identity discrepancy | Not found |
| Investigative QA required 5/5 | BLOCKED — expectation is edition-level |
| Relation QA required 5/5 | BLOCKED — expectation is edition-level |
| Note 36 / literal 25/25 | OPEN, 24/25 |
| Runtime/data fix | Not applied |
| Interior Final status | `test_candidate` before and after |
| Status/corpus/embedding/Milvus mutation | None |
| Promotion | Not executed |

## Reproduction

```bash
cd SrvRestAstroLS_v1/backend
PYTHONPATH=. uv run python scripts/audit_breslov_corpus_scope_integrity_v1.py \
  --output ../../data/reports/breslov/2026-08-04-corpus-scope-integrity-v1-dev
uv run pytest -q tests/test_breslov_corpus_scope_integrity_v1.py tests/test_work_identity.py
```

The audit opens a read-only PostgreSQL transaction and performs Milvus queries
only. It resolves sources by SHA-256, not mutable document IDs.

## Next step

Open separate work for (1) a canonical family/edition/source-lesson metadata
contract and migration and (2) PDF compatibility-ligature literal
normalization for note 36. Then repeat natural QA with expectations that state
whether scope means family or a specific edition. Promotion readiness remains
`NOT_READY_FOR_PROMOTION`, also due to legal and bibliographic blockers.
