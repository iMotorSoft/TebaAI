# Small serializable contract (experimental)

`RegionCertificate.to_dict()` returns strict JSON-compatible primitives;
non-finite floats are rejected by JSON encoding. Fields:

- document_sha: SHA256 of actual source bytes;
- pdf_page: physical one-based page;
- region_id: deterministic adapter source identity, never random UUID;
- bbox: unrotated PDF-point source geometry;
- zone_type, direction;
- source_block_ids, source_line_ids: native source lineage, not text matches;
- markdown_ranges: page-local half-open Python Unicode-codepoint offsets;
- mapping_method: FORWARD_IR_SERIALIZATION;
- provenance_status: CERTIFIED / UNRESOLVED;
- quality_status: existing RegionState exactly (ACCEPTED,
  PLATFORM_EXTRACTION_ERROR, SOURCE_PDF_ERROR, UNRESOLVED);
- reason_codes: explicit computed evidence/failed prerequisite;
- note_number, end_reason, continuation_of;
- certificate_version: automatic-region-certification-v1.

`CertifiedPage` includes the actual immutable candidate Markdown, source hash,
physical page, inventory and existing FULL/PARTIAL/UNUSABLE aggregate. A PARTIAL
aggregate does not establish correct semantic zones or satisfy the gate.

Provenance certification is intended to require supported identity, known zone,
known strong direction and unambiguous mapping. Holdout proves that copying
footer/section-header labels as semantic zones is UNSAFE. **CERTIFIED in this
experimental version is not a trusted operational authorization.**

Duplicate strings use source identity and independent ranges. Unresolved
unsupported boxes retain their serialized source-backed output, not deletion.
Malformed documents/invalid page selection may raise rather than return any
positive certificate. Duplicate source identities are unresolved; no promise of
unique distinct identities can be made for duplicate copies of the same raw IR.

Cross-page model: each page-local fragment has its own region ID. Existing
adapter Ownership supports `continuation_of`; a future automatic editorial
unit would reuse the first region identity as its chain root. V1 DOES NOT
resolve the chain, sets no continuation identity, and marks PAGE_BOUNDARY,
never a verified editorial termination. Notes36/66 full ends remain unproven.

Reuse of IDENTITY/MARKDOWN_DECORATION/SAFE_NORMALIZATION/EDITORIAL_GROUPING:
no new text transformation. Adapter emits decoration/grouping; safe acceptance
requires source/native token equality and decoration-only Markdown equivalence.
Line-end hyphenation, literal Markdown metacharacter ambiguity, direction or
column ambiguity prevents acceptance. No character invention, spelling repair,
RTL reversal, number replacement or automatic source-error assignment.
