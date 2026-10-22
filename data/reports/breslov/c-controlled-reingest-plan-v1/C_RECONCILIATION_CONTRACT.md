# OLD C vs NEW C reconciliation contract V1

Design only. Current inventory is not a reconciliation PASS for a nonexistent NEW.

**Refresh 2026-10-22** (second plan run, DEV read-only): OLD C was re-inventoried and
is byte-identical to the first run (same document/run/job, 284 pages, 942 chunks, 942
vectors, same content digests). Two new constraints were added to this contract:
the live uniqueness index that forbids a second same-source document row, and the
fact that the page-publication route currently resolves the **latest completed run**,
so an un-cutover candidate run can hijack the published page view.

## Authoritative inputs

Sealed source SHA, OLD/NEW document/run/job/attempt/manifest IDs, immutable code and config hashes, model/dimension, full 284-page inventory, all region certificate/publication metadata and geometry, canonical texts, chunks and exact vector PK mappings, source/viewer checks, query baseline and normal-retrieval visibility epoch. An input absent/unattributable/ambiguous is FAIL, not zero. Current OLD has no persisted regional certificates; its region coverage is UNKNOWN, not zero accepted regions.

## Reconciliation keys and matching

- `source SHA + physical PDF page` is stable. Printed pagination is a label, never a page join key. Source pages must be exactly the set 1..284.
- document_id differs by approved pipeline version **only if** the prerequisite migration replaces the live uniqueness index `uq_library_documents_scope_collection_sha256 (knowledge_scope_id, collection_id, source_sha256)`. If the candidate is modelled as a new generation **inside the same document row**, document_id is identical for OLD and NEW and the generation identity (new column, new run, or new chunk-set version — whichever the prerequisite adopts) becomes the primary reconciliation key. page_id includes run; chunk UUID includes document/pipeline/page/region/local-index/content hash. None of these are cross-generation equality keys; they are lineage inputs.
- The generation identity that the prerequisite adopts must be recorded in the
  reconciliation artifacts as `old_generation_id` / `new_generation_id` and must be
  the key used by every reader-side filter. Until that identity exists, the
  reconciliation contract cannot be executed for a same-document candidate.
- Milvus primary key is derived from chunk identity (currently chunk_uid); embedding tracking supplies the exact mapping. Evidence ID v2 is chunk/entity-derived and therefore can legitimately change. Record OLD->NEW citation lineage, never require identical evidence_id.
- Current chunks are page-local with page_start=page_end, job/attempt metadata but no region IDs; pages have old unfiltered Markdown and layout notes, no region publication. A loss cannot be attributed to an old region using IDs alone.
- Freeze offline source structural lineage with source SHA, physical page, rotation/crop/coordinate system, PDF block/line/span references, raw geometry, normalized geometry, language/editorial role, immutable text/span hashes and certificate ranges. Region IDs are local handles, not assumed stable across runs. Native span lineage is preferred. Non-native/OCR lineage requires explicit geometry and source visual review.
- Match unique same-source/page lineage sets first, then reproducible geometric overlap and normalized text-span alignment within the same page. Retain original Hebrew codepoints/niqqud and raw text; matching-only whitespace/known ligature normalization cannot certify quality. No transliteration or fuzzy semantic similarity may silently certify fidelity.
- For splits/merges build a many-to-many lineage graph; compare unions of source spans and good-text coverage, not number of regions/chunks. Chunk overlaps do not count twice. Freeze algorithm/version/coordinates, ordering and thresholds in the future baseline before opening NEW. Any geometric heuristic candidate needs an unambiguous lineage/span alignment or explicit signed visual adjudication; a threshold alone is not proof. If old serializer corruption prevents deterministic attribution, mark AMBIGUOUS and block cutover until adjudicated, not EXPECTED_REMOVAL.

## Per-region semantics

A region is publishable iff policy says quality ACCEPTED and provenance CERTIFIED with valid ownership/range/source binding. No inference from a clean-looking string.

- **PRESERVED** / EXPECTED_PRESERVATION: good source span remains fully represented in NEW accepted canonical text and chunks, embedding/vector mappings and correct citation/page/source; known-good retrieval succeeds. Counts and boundaries may change.
- **EXPECTED_REMOVAL**, reason `EXPECTED_QUARANTINE_REMOVAL`: OLD indexed the mapped span AND NEW publication policy proves that source region is not publishable. Show old evidence references, new nonpublishable verdict, reasons, lineage and source visual availability. Zero new searchable text/chunks/embeddings/vectors/textual citations attributable to the rejected span. A reduction of a whole mixed chunk is not fully expected if its good neighbor is lost.
- **UNEXPECTED_LOSS**: accepted/certified nonempty region lacks full textual coverage, chunk/vector/citation/source mapping; known-good page/note disappears, good Spanish note adjacent to rejected Hebrew is lost, formerly good page unexpectedly UNUSABLE, any page missing. Blocks cutover, regardless of global counts.
- **UNEXPECTED_GAIN**: untrusted/unresolved/quarantined span becomes searchable or cited, any vector lacks an accepted source region, duplicate active evidence appears, content outside approved PDF/lineage is introduced. Blocks cutover. Newly certified good source text absent in OLD can be approved preservation/coverage expansion only with explicit source-bound certification and a recorded adjudication; otherwise it is an unexpected gain.

No accepted+certified region may be made empty merely to meet a count or leak test. All relevant unexpected losses/gains are blockers; do not waive them as minor by changing the baseline.

## Future artifacts (required schemas, no fabricated results now)

`region-reconciliation.json`: schema_version, source_sha256, old/new generation IDs, code/algorithm seals; records contain physical page, region_id (NEW), old_region_ids if any, old_searchable (true/false/UNKNOWN), old chunk/evidence IDs and span ranges, lineage references, bbox, matching method/confidence/adjudication, new_quality, new_provenance, new_publication_status, new_chunk_ids/count, new_embedding_ids/count, new_vector_pks/count, new citation IDs, source/visual availability, classification in PRESERVED/EXPECTED_REMOVAL/UNEXPECTED_LOSS/UNEXPECTED_GAIN, reason (including EXPECTED_QUARANTINE_REMOVAL), good-neighbor coverage and mismatch detail. Unmatched old spans are explicit records; no dropped records. AMBIGUOUS matching is a separate blocking field until resolved, not a fifth passing classification.

`page-reconciliation.json`: one record per physical page 1..284: old_status (LEGACY_UNCLASSIFIED or legacy empty), new_status FULL/PARTIAL/UNUSABLE, accepted/quarantined region IDs/counts, old/new chunks/vectors and citations, old/new searchable span hashes and coverage, expected_removals, unexpected_losses/gains, matching ambiguities, source_available, printed-label mapping, empty-page reason and review. Empty physical pages remain represented and visually resolvable, even if regional aggregate is UNUSABLE. Legacy is never retroactively called FULL.

`document-reconciliation.json`: generation/source/seal identities; total_pages; FULL/PARTIAL/UNUSABLE and empty physical pages; accepted/quarantined regions; old/new chunks/embeddings/vectors; expected removals (count and lineage/spans); unexpected losses/gains; missing pages/source; good-neighbor loss; accepted evidence/citation coverage; exact vector/chunk set mismatches; duplicate active evidence; query group and citation results; ambiguity count; signed GO/NO-GO with reasons.

Baseline metrics must be per page/region and query, not just global totals: searchable good-span coverage, retrievable accepted evidence, correct citations, partial pages, source/page coverage and visual availability. OLD has 284 pages (268 nonempty, 16 empty), 942 chunks and 942 vectors. Do NOT demand OLD_CHUNK_COUNT == NEW_CHUNK_COUNT or OLD_VECTOR_COUNT == NEW_VECTOR_COUNT.

## Vector and duplicate invariants

Within NEW, exact accepted chunk set = embedded chunk set = indexed chunk set (one expected model/vector per chunk); compare PK, chunk, document, page, content hash, source hash, model, dimension 1536, collection and vector digest. Global counts alone cannot prove this. Enumerate entire live collection with Strong consistency; do not query only expected PKs and thereby hide orphan vectors. Join every primary vector to PG and manifest; every PG embedding must map back to the same chunk and PK. Validate embedding request hashes/counters against accepted-only inputs.

Distinct active generations for logical C = 1, whatever the physical carrier is
(separate document row or generation-scoped chunks in one document row). Duplicate
active chunks/vectors/citations = 0, using logical source/page/lineage/entity/span signatures, not just UUID distinctness or text equality across different pages. Overlapping chunks and legitimately repeated printed text are not new evidence; deduplicate editorial lineage appropriately. OLD and NEW may both be stored, never both eligible. Candidate-only validation may explicitly inspect NEW, normal retrieval may not before cutover. Cross-generation contamination = 0 in retrieval, hydration, citations and viewer references.

## Retrieval and citations

Seal fixtures before NEW evaluation with query text, language, source/page/region/lineage, good/bad rationale, expected allowed evidence and prohibited spans, retrieval mode/top-k/config, criticality and OLD result IDs. Include all accepted pages in coverage checks plus exhaustive accepted-region-to-chunk proof; goldens supplement but do not substitute coverage.

A KNOWN GOOD seeds: `CONSTRUYENDO UN MISHKÁN` p51, `INCLINADO HACIA LA BONDAD` p53, `Salmos 16:1` p55, note 35 and `MELODÍAS Y PLEGARIAS` p56, and accepted source-bound cases throughout all chapters. These historical seeds must be verified/resealed against current OLD and visual source, not claimed to pass today. Each must retrieve accepted evidence with correct physical page and textual citation.

B KNOWN BAD: sealed unique snippets/hashes from rejected Hebrew regions (p55/56/167 seeds from previous fixture evidence plus all newly identified rejected regions). Assert no evidence **attributable to those regions**, no textual citation, vector or embedding request for them. A semantic query can legitimately return unrelated accepted evidence; do not mistake any nonempty response for bad-region leakage. Use exhaustive storage lineage checks as well as direct/normalized queries. Rejected plaintext stays in restricted offline evaluation material, never searchable metadata.

C PARTIAL PAGE: query accepted Spanish notes and neighboring good regions on p55/56/167 and every resulting mixed page, including boundaries and paragraph overlaps. Good content/citations must remain; rejected region excluded. Quarantined region visual source available via same approved PDF/page/bbox, textual citation unavailable. Test normal viewer and authorized candidate inspector separately, lexical/hybrid/vector plus research/relation endpoints. Future authenticated browser/Playwright checks need credentials from environment; not performed here.

**Route inventory that the candidate-isolation proof must cover** (re-verified
2026-10-22, static read of the current backend):

| Route | Current generation filter | Status |
|---|---|---|
| `modules/library/text_search.py` (lexical/FTS) | none — no `status` predicate at all | MISSING |
| `modules/library/hybrid_search.py` (vector) | scope only; PG hydration hardened to drop unauthorizable/misattributed hits | MISSING (no active-generation filter) |
| `modules/library/simple_research_repository.py` | `status='ready'` (+ opt-in `test_candidate`) | PARTIAL (opt-in can expose candidates) |
| `modules/library/relation_qa_repository.py` | status allow-list (`_statuses(include_test_candidates)`) | PARTIAL |
| `modules/library/source_repository.get_authorized_source` | `status IN ('ready','test_candidate')` | PARTIAL (no generation) |
| `modules/library/source_repository.get_page_publication` | newest **completed** run of the document | MISSING (a finished candidate run hijacks the viewer) |
| `modules/library/indexing_service.py` | `status='ready'` / `status='test_candidate'` | PARTIAL (promotion path) |

A candidate that is ingested but not cut over must be invisible on **every** row of
this table, including the page-publication route.

## Absolute PASS/FAIL

PASS only when all expected artifacts/seals exist, coverage and attribution complete, known-good/partial/citation cases PASS, source checks PASS, candidate fully reconciled, rollback retained, and all counters below are exactly zero:

- unexpected good-content loss;
- unexpected gains and unresolved matching ambiguities;
- bad/untrusted searchable leakage (text, chunks, embedding input, vectors, retrieval, citations);
- good-neighbor loss;
- unexpected physical pages missing;
- active duplicate evidence;
- unavailable source or incorrect page/citation mapping;
- cross-generation contamination and PG/vector mismatches.

UNKNOWN, skipped critical checks, infrastructure fallback, missing evidence or manual review outstanding -> NO-GO, never best effort. Expected quarantine removals are explicitly reported, not regressions. Reconciliation failure keeps OLD active and NEW inactive; after cutover the same failures mandate rollback.
