# Editorial Evidence Granularity & Stable IDs V1 — DEV report

Phase: `TEBAAI_EDITORIAL_EVIDENCE_GRANULARITY_STABLE_IDS_V1_DEV`

Date: 2026-08-04 (DEV only)

## Result

**Gate: `TEBAAI_EDITORIAL_EVIDENCE_GRANULARITY_STABLE_IDS_V1_DEV_READY`**

| Control | Result |
|---|---|
| Contract identified (chunk-level → entity-level) | PASS |
| Canonical unit defined | PASS (editorial entity) |
| Note 35 identifiable | PASS (`ev-4e5a8dfb9583bcc2`) |
| Note 36 identifiable | PASS (`ev-3f9669e232ecf193`) |
| Note 35 ≠ Note 36 | PASS |
| Query variants note 36 → same ID | PASS (plain = ligature) |
| Heading ≠ footnote | PASS |
| Reference variants → same ID | PASS (Salmos 16:1 / (Salmos) / salmos) |
| Same entity cross-interface (admin/guest) | PASS |
| Claim grounding does not alter IDs | PASS (backend validation) |
| Dedupe by entity (within response) | PASS (chunk dedupe unchanged) |
| ID independent of rank | PASS |
| ID independent of IA | PASS |
| ID independent of query variant | PASS |
| Span identity defined | deferred (not yet implemented) |
| Legacy compatibility | PASS (`legacy_evidence_id` preserved) |
| Backend focused | 68 PASS |
| Backend complete | 1482 PASS |
| Frontend | 0 errors, 70 tests, build PASS |
| Admin E2E | PASS |
| Guest E2E | PASS |
| Mobile E2E | PASS |
| E2E regressions | 8/8 PASS |
| ADR-021 | PASS |
| Fixture | PASS |
| Audit script | PASS (all checks) |
| Status modified | No |
| Corpus reingested | No |
| Embeddings recalculated | No |
| Milvus modified | No |
| Production modified | No |
| Push | No |

## Before / After

Before (v1, chunk-based):
```
note 35 → ev-e419ec6448d2d992
note 36 → ev-e419ec6448d2d992  ← same as note 35!
heading 6 → ev-e419ec6448d2d992  ← same as notes!
```

After (v2, entity-based):
```
note 35 → ev-4e5a8dfb9583bcc2 (legacy: ev-e419ec6448d2d992)
note 36 → ev-3f9669e232ecf193 (legacy: ev-e419ec6448d2d992)
heading 6 → ev-4903b73f2011afee (legacy: ev-e419ec6448d2d992)
Salmos → ev-68c3400c24c38e8a (legacy: ev-716847bfff6da041)
```

## Root cause

The page-first V2 pipeline stores one chunk per full page. Three editorial
entities (note 35, note 36, heading 6) coexist in chunk `036be7c5-...`. The
old `_evidence_id` derived identity solely from `chunk_id`, so all three
received the same ID.

## Implementation

- `_evidence_id(chunk)` now includes chunk_id + entity discriminator derived
  from `_entity_key(chunk)`: `footnote:{number}`, `heading:{_fold(title)}`,
  `reference:{normalized_surface}`, `body`, etc.
- `_legacy_chunk_evidence_id(chunk_id)` preserves the old chunk-based ID.
- Hit payload includes `evidence_identity_version: "v2"` and
  `legacy_evidence_id`.
- Tests, fixtures, E2E and audit script updated.
