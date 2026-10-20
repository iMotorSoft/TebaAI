# Offline V2 proof contract

Module: `SrvRestAstroLS_v1/backend/modules/library/automatic_region_certification_v2.py`.
Version: `automatic-region-certification-v2` on every certificate. V1 unchanged.

Reuses RegionCertificate fields: document SHA, region ID, physical page, bbox, candidate zone/direction, source block/line IDs, forward Markdown ranges/method, provenance/quality, reasons, note identity, end reason, continuation reference. Adds only `proofs`, `local_boundary` and `continuation_status`. Candidate zone labels on UNRESOLVED certificates are NOT certified editorial assertions.

Pipeline: V1 discovers/maps candidates → V2 collects named evidence → all mandatory supported proofs present → CERTIFIED; otherwise UNRESOLVED. No quality acceptance without certified provenance.

## Supported NOTE

| Proof | Predicate |
|---|---|
| zone | Numbered mapped note + unique preceding notes separator + explicit extractor footnote anchors; underlying mapper checks typography/columns |
| direction | Pure LTR strong script AND visible horizontal native trace with source token order equivalence |
| ownership | Every source identity unique, exact number of mapped parts, no conflicting line geometry internally/externally; Markdown emitted with lineage |
| local_boundary | Explicit start number and mapped end marked NEXT_NOTE_IN_COLUMN_FLOW or PAGE_BOUNDARY |
| order | Consecutive note markers, one/two non-null columns, V1 disjoint-flow checks passed |
| continuation | NEXT_NOTE_IN_COLUMN_FLOW; an explicit next note closes the current editorial unit |

All predicates mandatory; corrupt-text replacement signal withholds certification. V1 quality status is retained ONLY after the complete V2 proof set passes. Native evidence is stronger than script but not a general visual-quality guarantee. No source error is invented.

## BODY, HEADER, FOOTER, RTL and unsupported families

Not supported by this issuer. Labels, position, font size and regex are not sufficient zone certificates. Output is unresolved, including otherwise good Spanish body. Required future body proof must distinguish it independently from unlabelled note continuation. RTL additionally needs script/logical-order and ownership evidence; neither automatic Hebrew rejection nor automatic acceptance is allowed.

The currently emitted proof names describe the supported note contract; on unsupported candidates they are diagnostic missing proofs, not a claim that body requires note markers. This narrow scope is an explicit utility failure, not a universal certification implementation.

## Local versus editorial boundaries

`local_boundary=KNOWN` describes mapped local note geometry. It does NOT authorize quality/evidence ingestion. `continuation_status=COMPLETE` requires the full certified proof set and next marker. Page-terminal segments emit `UNRESOLVED_CONTINUATION`; 36/66 are never declared complete at 56/167.

V2 does not implement automatic CONTINUES / CONTINUED_FROM_PREVIOUS linking. Missing links are not guessed even when adjacent pages are present. Cross-page unit certification therefore remains incomplete. No worker, canonical text, chunks or vectors consume this output.
