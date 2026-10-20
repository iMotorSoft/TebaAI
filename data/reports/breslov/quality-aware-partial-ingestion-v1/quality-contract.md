# Quality contract V1 — OFFLINE CANDIDATE

Implementation: `SrvRestAstroLS_v1/backend/modules/library/region_quality.py`.
Not an approved change to the canonical extractor, not connected to the worker.

Four region states: ACCEPTED, PLATFORM_EXTRACTION_ERROR, SOURCE_PDF_ERROR,
UNRESOLVED. No warning state that weakens ACCEPTED.

ACCEPTED requires positive, referenced evidence of visible source, text fidelity,
logical order and sufficient structure. Absence of replacement characters is
NOT positive evidence. Source method must be pymupdf4llm. Unknown/unsupported
methods (including OCR and diagnostic plain text) cannot become evidence.

Defect diagnostics take precedence over claimed verification. Visual source
known bad with provenance => SOURCE_PDF_ERROR. Known extraction defect plus
source known good => PLATFORM_EXTRACTION_ERROR. Missing evidence => UNRESOLVED.
The policy never changes the candidate text. U+FFFD and non-whitespace controls
are deterministic automatic rejection signals, independent of script.

The contract consumes upstream certificates, not an automatic fidelity oracle.
Wrong order, number corruption, mojibake and visual uncertainty need referenced
diagnostics; this implementation cannot discover all of them from strings.
No filename, source hash, page number or Hebrew-specific dispatch in policy code.

`accepted_markdown` and `evidence_units` are safe *candidate* outputs; production
must certify complete source coverage, unique region association and ordering
before consuming them. The raw rejected string stays in offline diagnostics,
not in operational quality metadata or an evidence/search surface.

No published/indexed/citable/embedded text may come from a rejected unit.
The current worker does not enforce this contract yet. This phase does not
certify or clean existing corpus content.
