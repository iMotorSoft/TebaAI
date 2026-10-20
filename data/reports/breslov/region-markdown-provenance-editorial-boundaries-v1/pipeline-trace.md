# Real pipeline trace and first loss

Source: `LIKUTEY HALAJOT (Interior Final).pdf`, SHA-256
`440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a`.
PyMuPDF and PyMuPDF4LLM **1.27.2.3**. Source read only; OCR explicitly disabled.
Paths below starting `modules/` are relative to `SrvRestAstroLS_v1/backend/`.

## Observed stages (not an assumed legacy pipeline)

1. Runtime `page_first_pipeline.extract_pdf_page_first` delegates to
   `pdf_hebrew_fidelity.page_markdown` → `pymupdf4llm.to_markdown`.
2. Installed PyMuPDF4LLM uses `_use_layout=True`; `_layout_to_markdown`
   invokes `helpers.document_layout.parse_document`.
3. `parse_document`: `page.get_textpage(flags=FLAGS)` (`FLAGS=36420`),
   `extractDICT()['blocks']`. Native spans have text, font, bbox and origin.
   Geometry is already available here. Unknown native encoding is already
   represented by U+FFFD at this stage. Provenance does not repair that.
4. `get_layout` + `utils.find_reading_order` supplies ordered layout rectangles.
   `PageLayout.fulltext` retains native blocks; `get_raw_lines` produces each
   `LayoutBox.textlines` with bbox and spans carrying native `block`/`line`.
   A layout line can contain multiple native lines, or be a geometric fragment
   of a native line; `(block,line)` alone is NOT unique on these real pages.
5. `ParsedDocument.to_markdown` loops boxes, calling `text_to_md`,
   `footnote_to_md`, `section_hdr_to_md`, etc. It computes `string_lengths`
   internally, but the normal string-return path discards all box identity.
   `page_chunks` can retain box cumulative offsets, but not the editorial
   splits/joins and note continuations needed here.
6. `_layout_to_markdown` returns only a string; `page_markdown` optionally runs
   `repair_markdown` with a separate rawdict. This phase does NOT change it.
7. `analyze_page` sees only Markdown and signals; it cannot recover unique
   source ownership, especially repeated text, from that string alone.

**Where provenance is first available:** native extraction blocks/spans with
geometry, before Markdown. **Where previously lost:** the string return from
`ParsedDocument.to_markdown` / `_layout_to_markdown` (stage 5→6). The PDF does
not discard identity; a forward adapter is viable, so this is not BLOCKED.

## Exact ordering defect, 167

Layout boxes 11–13 contain 60/61, 62, 63. Box14 is the right-column
continuation of65; box15 (`page-footer`) contains66. Boxes16/17
(`page-footer`) contain left-column64/65. The default serializer therefore
emits65's continuation/66 before64/65. Executable regression reproduces that
bad output before checking corrected output. Sorting whole boxes just by y
would also interleave columns and fail.

Minimum change (offline only): preserve the IR; resolve the declared bottom
note-zone column flow; split at raw numbered starts using the existing
`editorial_evidence_v2.detect_footnote_number`; join continuation lines across
columns. Serialize each editorial unit using the SAME PyMuPDF4LLM serializer
on copied IR; append output and record offsets together. No regex/find over
final Markdown establishes ownership. No historical decoder or ingestor runs.

## Terminal boundaries are not page cuts

Visual evidence: `tebaai-notes-{55,56,57,167,168}.png`, crops of PDF points
`[45,550,450,655]`, scale2; source unchanged.

- 35: page56, left column + top of right, ends `...Nesiat Kapaim 5:6).` before36.
- 36: page56 continues after `...del Otro`; page57 left + right top ends
  `dirigidos hacia la santidad.` before37. Page57 has NO `footnote` labels;
  a **manual geometric note-zone certificate** `[45,560,450,650]` is input data,
  not a special branch in productive logic. Cross-page link requires same SHA,
  adjacent page and explicit caller-supplied previous note ownership.
- 65: page167 left bottom + right top, ends `...esto a continuación.` before66.
- 66: page167 continues after `...a las`; page168 left top ends
  `...s’mol dojé).` before67.

Supporting57/168 evidence is notes-only, not a whole-page certification. Full57
contains a duplicated marginal line `(block15,line1,bbox[369.207,337.206,
418.559,343.286])` in two layout boxes; the adapter correctly rejects that
ambiguous FULL-page input. No line is silently dropped to fix it. That
independent body defect is outside the requested goldens; all supporting note
lines are retained and accounted for.

## Frozen defects / limits

- Page55 notes heading has native overlay text `1RWHV\u0003\t\u00036RXUFHV`
  plus visible `Notas y Fuentes`; current layout combines visible text and
  U+FFFD. Quarantine the mapped heading, do not repair visibility/encoding.
- Page55 previous body box has an independent marginal/body overlap error.
  The **verified good tail**, entire unchanged previous box, and complete next
  note33 survive exact heading exclusion. We do NOT certify that whole body
  box as flawless or repair its unrelated layout bug.
- Serializer dehyphenation of page56 body (`jas ve-` line end) is NOT safe
  normalization: ownership remains mapped, transformation status UNRESOLVED;
  the thin quality bridge refuses acceptance even with positive caller flags.
- Unsupported lists/images/tables, missing/duplicated identities, incompatible
  note typography, unrelated footers, overlapping note lines, unidentified
  continuations, unsupported numeric starts: explicit `UnresolvedLayout`.

Does Markdown require reverse mapping? **NO**.
Minimum adaptation modifies no runtime caller, shared extractor, serializer,
visibility module, quality contract or worker.
