# Live pipeline and integration boundary

Existing runtime: upload → durable worker → ConcretePageFirstPipeline →
page_markdown/Markdown string → persist_document_and_pages → chunks → embedding
→ vectors. Unchanged. No enforcement, storage or transport was installed there.

New opt-in callable in `backend/modules/library/extractors.py`:

1. `extract_pdf_with_region_certificates(path, pages=physical_pages)`.
2. Compute document SHA from actual bytes; validate selected physical pages.
3. `parse_document(document, pages=zero_based, use_ocr=False)` — installed
   PyMuPDF4LLM canonical layout, retaining all boxes/textlines/spans.
4. Derive strong-script direction from ALL source codepoints; detect explicit
   footnote anchors and candidate bottom zone. No supplied layout certificates.
5. Reuse `map_layout_page` on the note flow and independent non-note boxes.
   Its source identities, column checks, serializer and transformation guards
   remain authoritative. Unsupported boxes are retained with unresolved status.
6. Append source-backed serialized fragments and rebase their local offsets.
7. Match source lines against independent PDF text trace by baseline/geometry;
   require painted opaque non-overwritten glyphs for positive quality evidence.
8. Emit page-local Markdown and serializable certificates/aggregate together.

No reverse substring search into final Markdown, no manual golden imports in
product code. Golden boundaries are read only by the evaluation script AFTER
extraction. Holdout annotations likewise never enter certificate issuance.

## First loss / irreversible boundary

Normal runtime string serialization loses source identity before persistence.
The opt-in forward adapter avoids that particular loss. Damaged Hebrew Unicode
is already present in layout text BEFORE this adapter; its all-U+FFFD text
cannot prove RTL. The parser retains coordinates, not a trustworthy semantic
body-vs-unlabelled-note zone. Replacing missing evidence with fixture answers
would recreate the rejected offline trust model.

V1 fails on ordinary implementation/evidence insufficiency, not a claim that
PyMuPDF cannot expose geometry or that integration is structurally impossible.

## Future worker contract (NOT connected)

A future passing extraction version must return its own immutable Markdown and
certificates together, with document SHA, extractor/certificate versions and
page-local ranges. The worker must validate versions and inventory, never reuse
these ranges with old canonical Markdown, then enforce before canonical/pages
persistence. This V1 issuer must NOT be admitted: known false zone certificates
and missing continuation/body proofs remain. PostgreSQL persistence and worker
quarantine are separate future work.
