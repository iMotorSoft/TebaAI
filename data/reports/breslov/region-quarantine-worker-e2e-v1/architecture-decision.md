# Integration decision (scoped DEV gate)

## Boundary

The existing V5 producer supplies forward-owned immutable region Markdown/certificates. `region_publication.publish_certified_page` decides publication unchanged. The worker default is `extract_pdf_region_published`, not the legacy `extract_pdf_page_first` compatibility API. Exceptions propagate: there is no unfiltered fallback. The gateway also rejects absent/mismatched publication data before canonical persistence and before chunk creation.

Canonical page/document text contains only published regions. Per-region chunking resets overlap across EVERY region. Chunk metadata includes region_id and protected source reference. Quarantine metadata (hash, bbox, source/page/region identity, statuses/reasons) resides in existing `library_pages_v2.layout_notes.region_publication`, without rejected text. Zero accepted regions is a successful visual-only candidate with warnings and no embedding dispatch, not a document-wide failure.

## Durable visual original

Reuse `CONTENT_MANAGER_STORAGE_DIR`: `sources/<document_uuid>/original.pdf`. No second storage service or migration. Before finalization deletes the upload, copy atomically, fsync and verify SHA-256. The existing `library_documents.source_path` holds the server-only reference. PDFs are not stored in PostgreSQL or exposed as public static files. Manifest cleanup deletes only the deterministic source owned by the deleted controlled document.

New protected source and page-publication endpoints reuse JWT validation and the complete existing knowledge-scope membership chain. Only ready/test_candidate documents are readable, and arbitrary DB paths cannot be served. Metadata/citations contain endpoint references, never filesystem paths. Bearer-authorized fetch is required; opening a bare browser URL without auth correctly returns 401. No frontend/viewer was built; the backend full-PDF/page-reference contract was exercised through authenticated ASGI HTTP. Browser rendering was not validated in this gate.

## Retrieval/citation

The existing search HTTP route now selects the existing isolated Milvus collection for the E2E scope instead of silently searching primary. Hybrid validation requires actual vector signals, not merely HTTP 200. Citations use the existing canonical rehydration repository and `build_evidence_v1` builder, with additive regional/source links; the normal simple-RAG evidence serializer propagates those links. Generative answer rendering was not evaluated.

## Compatibility

The legacy offline extraction API is kept unchanged to avoid replacing the source-geometry extraction contract outside the worker. The worker's default extractor has a dedicated regression test, and its real gateway rejects legacy pages. Initial integration changed the compatibility API and caused three regressions; these were fixed by separating the mandatory worker boundary, not by weakening tests/certification. Final backend suite retains exactly the original 20 baseline failures.

## Explicit limitation / gate failure

The five existing declared-certificate fixtures pass through worker/chunk/embedding unit integration. They are not a proof that arbitrary synthetic PDF layouts receive those certificates. Actual simple PDFs generated with frozen GOOD/BAD expectations all receive UNRESOLVED under unchanged V5. Consequently A/C/D lose four expected GOOD units upstream of publication. The real Breslov subset does have three ACCEPTED+CERTIFIED units, all preserved end to end. Do not relabel synthetic GOOD units, add acceptance bypasses or change certification to turn this result into PASS. This gate is FAIL, not an infrastructure BLOCKED result.

## Preexisting dependencies

V5 and annotation_preseal_validation were already untracked at task start. They are required imports for the selected existing producer and are versioned unchanged in a separate dependency commit, with their existing unit tests. No evaluator, lineage research, font repair or V5 redesign is included. Existing extractors.py modifications, font/Unicode/visibility experiments, frontend changes, status changes and historical reports remain unstaged.
