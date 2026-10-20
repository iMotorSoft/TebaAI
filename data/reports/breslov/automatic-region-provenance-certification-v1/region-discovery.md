# Generic discovery and coverage

No page/filename/note-number branch in product code. Physical pages and note
numbers occur only in fixtures/evaluator/annotations. No coordinates from the
offline goldens are passed to extraction.

Live PyMuPDF4LLM boxes provide boxclass, bbox and textlines with span block/line
IDs, font, size, origin, bidi and direction. Metadata available: text,
page-header, section-header, footnote, page-footer and unsupported nontext
classes. Not available as a trustworthy universal semantic certificate:
Spanish-body zone, Hebrew-body direction after corrupt extraction, unlabelled
continuation ownership or genuine note editorial end across page cuts.

V1 derives a bottom candidate zone from explicit footnote boxes and ALL strong
script in that zone. The old forward adapter verifies typography, source IDs,
nonoverlapping columns, note markers and geometry order. Its safe historical
numeric recognizer supports only its existing two-digit contract: unsupported
numbers remain unresolved; no extension to rescue holdout.

Independent non-note boxes are retained even when a note flow fails. Text boxes
are NOT automatically semantic body; unlabelled notes also carry `text`.
Broad geometry overlap prevents independent ownership certification. Container
permutations are stabilized by source geometry and identity; non-note multi-
column editorial reading order is not claimed as supported.

Goldens:167 notes60–66 and56 notes35/36 are discovered automatically with exact
page-local source boundaries/columns/order.55 corruption is found by native
trace/layout differential. Previous whole55 body box is not trimmed into the
manually selected old good tail.57 unlabelled notes remain unresolved, and168
mixed script/leading continuation cannot establish a chain. NO manual fallback.

See `page*-results.json`, `supporting-pages-results.json` and holdout per-region
source annotations. The implementation is a limited experimental issuer, not a
completed generic region discovery/certification capability.
