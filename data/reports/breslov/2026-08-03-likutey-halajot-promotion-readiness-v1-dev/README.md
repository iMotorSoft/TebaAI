# Likutey Halajot Corpus Promotion Readiness V1 — DEV

Gate: `TEBAAI_LIKUTEY_HALAJOT_CORPUS_PROMOTION_READINESS_V1_DEV_READY`
Audit status: **PASS (audit completed)**
Recommendation: **`NOT_READY_FOR_PROMOTION`**
Document status before/after: **`test_candidate` → `test_candidate`**

No promotion, production change, corpus write, reingestion, embedding
recalculation, vector mutation or push was performed.

## Executive decision

Source and index integrity are complete, and the five canonical editorial
controls are stable. Promotion is nevertheless not ready because natural
Investigative/Relation QA and work scope do not reliably isolate Interior
Final; a conflicting existing `ready` record is titled as Likutey Halajot while
sampled content identifies Likutey Moharán II #8; critical bibliographic fields
are not persisted; and the PDF's rights notice requires prior written consent
that has not been evidenced.

## Identity and source

- observed document ID: `132a791a-d12b-45bc-9b34-dd143605de12` (future tools
  must resolve by hash/filename/family, not hardcode it);
- filename: `LIKUTEY HALAJOT (Interior Final).pdf`;
- SHA-256: `440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a`;
- status: `test_candidate`; language: `es`;
- pipeline: `likutey_halajot_page_first_v2`;
- source file accessible, PDF 1.6, unencrypted, 4,550,267 bytes, 284 pages.

The 16 text-empty pages (6, 8, 34, 38, 100, 102, 116, 118, 146, 202,
204, 240, 242, 266, 274, 284) were rendered at bounded low resolution and are
visually blank. No OCR was run.

## Page-first, chunks and embeddings

| Control | Result |
|---|---:|
| canonical page rows | 284 |
| unique page IDs / PDF numbers | 284 / 284 |
| textual / source-blank pages | 268 / 16 |
| gaps / duplicate pages / orphan pages | 0 / 0 / 0 |
| chunks | 268 |
| unique IDs / UIDs | 268 / 268 |
| empty / unnormalized / unanchored chunks | 0 / 0 / 0 |
| invalid ranges / duplicate content hashes | 0 / 0 |
| embeddings | 268 |
| Milvus vectors for document | 268 |
| PG↔Milvus | 100% |
| missing / orphan / duplicate vectors | 0 / 0 / 0 |
| metadata mismatches | 0 |
| model / dimension | `openai_text_embedding_3_small` / 1536 |
| collection total | 5,370 |

All 268 chunks resolve through a page anchor to an existing page with matching
document and PDF page. Persisted chunk roles are intentionally coarse
(`page_first_v2/commentary`); retrieval derives heading, marginal-reference and
footnote layers deterministically. Only 12/268 chunks persist a printed-page
label; critical labels are recovered from visible page headers. This is a
metadata condition, not a count/integrity failure.

## Editorial evidence

Canonical controls:

| Query | PDF / printed | Type / layer | Stability |
|---|---|---|---:|
| CONSTRUYENDO UN MISHKÁN | 51 / 33 | `structural_heading_exact` / `section_heading` | 10/10 |
| INCLINADO HACIA LA BONDAD | 53 / 35 | `structural_heading_exact` / `section_heading` | 10/10 |
| MELODÍAS Y PLEGARIAS | 56 / 38 | `structural_heading_exact` / `section_heading` | 10/10 |
| Salmos 16:1 | 55 / 37 | `printed_reference_exact` / `marginal_reference` | 20/20 |
| literal note 35 | 56 / 38 | `footnote_literal_exact` / `footnote` | 10/10 |

Expanded heading audit passed 12/12. The source audit covers notes 34–37 and
reference boundary negatives. The 25-query expanded batch has **24/25 target
primaries**: a normalized note-36 query (`Birur ... refinamiento ... chispas`)
loses to semantic evidence in another ready work, while the literal
surface in Interior Final contains PDF ligature/split artifacts. Ten negatives
produced no false exact evidence.

## Investigative and Relation QA blockers

Direct canonical surfaces pass, but natural wrappers do not preserve them:

- “¿Dónde habla ... construir un Mishkán?” selected the conflicting ready
  record, PDF 386;
- “¿Dónde aparece ‘Inclinado hacia la Bondad’?” selected Kitzur, PDF 313;
- “¿Qué dice la nota 35 ...?” selected La Potencia de la Plegaria, PDF 352;
- “¿Qué relación existe entre melodías y plegarias?” selected La Potencia,
  PDF 123;
- Salmos 16:1 remained correct at Interior Final 55/37.

Scoped relation queries likewise selected the conflicting ready record for
melody/prayer, favorable judgment and Mishkán/construction. Salmos and
Azamra/puntos buenos selected the candidate correctly. Evidence is not
fabricated, but scope/PRIMARY does not meet promotion criteria.

## Versions and scope

There is no second active document with the candidate hash and no binary
chunk/vector duplicate. One related ready row exists:

- title/file: `Likutey Halajot LM II 8` / `LIKUTEY HALAJOT LM II 8.pdf`;
- hash: `c0460178...`;
- 1,205 chunks / embeddings;
- sampled persisted content identifies `_LIKUTEY MOHARÁN II #8_`.

Because title-family matching treats it as Likutey Halajot, it pollutes scope,
bibliographic grouping and semantic primaries. No status was changed and the
record was not marked superseded.

## Bibliography and the prior Tomo 2 claim

The prior claim was invalid. `document_code=likutey_halajot_interior_final_v2`
contains an ingestion version, not bibliographic volume 2. The planner was
fixed generally so technical `_v2` no longer counts as a volume and unresolved
metadata returns `volume_number=null` / `Tomo no resuelto`, not “obra completa”.
The authenticated API is stable 10/10 and never says Tomo 2.

Real source evidence:

- PDF 3: Rabí Natán; Moshé Mykoff with Dov Grant; Spanish translation by
  Guillermo Beilinson; Breslov Research Institute;
- PDF 4: Copyright © 2020; first edition;
- PDF 10: explicitly says **“el primer volumen ... está ahora en sus manos”**.

Therefore source volume is explicitly **1**, but persisted/planner volume must
remain null until an authorized editorial metadata phase records it. ISBN is
unresolved.

## Multilingual, proper names and Hebrew

- ES canonical controls pass.
- EN can recover Spanish evidence as expansion; it is not labeled a literal
  English quotation.
- Global Hebrew goldens with and without niqqud returned the same LM II page
  14 evidence; candidate promotion does not change their score in simulation.
- Mixed queries may select other corpus works and are not promoted to false
  literal translation.
- Gedalia of Linitz/Gedalia/Linitz and Reb Noson pass existing exact-name lanes;
  Rabí Natán/Rebe Najmán remain partial or normalized where appropriate.

## Status simulation

The pure simulation proves that promotion would add the document to normal
ready-only retrieval and remove the DEV warning. It would not change scores or
tie-break keys because `document_status` is not part of `merge_results` scoring.
Exact editorial evidence remains stronger than semantic-only evidence.
Promotion therefore cannot repair the observed scope/routing failures and
would expose them more broadly.

## Legal/editorial

- technical integrity: PASS;
- editorial readiness: FAIL pending metadata/scope and natural QA fixes;
- legal status: `LEGAL_REVIEW_REQUIRED`;
- PDF 4 requires prior written editor consent for reproduction/storage/
  transmission; no permission evidence was found;
- public exposure: not authorized by this audit.

## Tests and browser validation

- focused backend: 220 passed, 0 failed, 1,218 deselected;
- full backend: 1,438 passed, 0 failed, 94 known warnings;
- frontend check: 0 errors, 0 warnings, 2 hints;
- frontend Vitest: 69 passed;
- frontend build: PASS, 8 pages;
- selected real Chromium gate: 10 passed, 0 failed, 4 existing documented
  skips; admin, guest, 390×844 mobile, read-only denial, refresh/session,
  evidence and logout passed.

Auth/UI success does not override the functional retrieval blockers.

## Future promotion and rollback

No future status write is allowed until:

1. conflicting ready work identity/scope is corrected in an authorized phase;
2. natural Investigative/Relation and 25-query literal batches have zero
   blocking failures;
3. source metadata (including volume 1) is editorially approved and persisted;
4. written-permission/legal policy is closed for intended exposure;
5. a fresh readiness audit recommends promotion.

A later authorized phase would resolve the candidate by hash, capture a logical
backup/baseline and change only `library_documents.status`. Rollback changes
only `ready → test_candidate`; no page/chunk/vector changes or reingestion are
needed. See `rollback-plan.md`.

## Artefacts

The JSON files in this directory contain sanitized identity, page/chunk/vector
reconciliation, role and version inventories, API runs, deterministic
signatures, multilingual/proper-name/Hebrew results, negatives, status
simulation, promotion matrix, tests and E2E evidence. No PDF, token, password,
credential, dump or vector is included.
