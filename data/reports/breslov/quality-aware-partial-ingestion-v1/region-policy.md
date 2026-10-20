# Region policy

Prefer existing text block/editorial zone/column region, not glyph or line rows.
Geometry is PDF points, unrotated, top-left; record bbox when source association
is demonstrated. Markdown paragraph is only a candidate textual boundary, NOT
proof of a source-region boundary.

Disposition before quarantine: SAFE_RECONNECT, QUARANTINE_REQUIRED, SOURCE_ERROR,
UNRESOLVED. Disposition is separate from quality: SAFE_RECONNECT never authorizes
indexing unrepaired text. After reconnect, re-evaluate with new positive evidence.

Page56: reconnect numbered starts through `markdown_note_starts`. Recognizes
blockquote/emphasis wrappers and preserves original offsets; no global stripping
or rewriting. Both35/36 starts recovered on real current Markdown. This does NOT
recover the final note boundary, anchors, roles, or citations. Do not declare full
note acceptance or make permanent quarantine to avoid this safe reconnect.

Page167: native Spanish notes have separate left/right blocks. Current Markdown
reorders continuation65/66 ahead of64/65. Native-block order is useful evidence,
not permission to replace the canonical Markdown extractor with plain text.
No OCR, SI960, font-map candidate or visibility suppression integrated.

Minimal defendible unit today: offline verified editorial body region for167;
corrupt Markdown paragraph sample for55. A GENERIC source-block -> Markdown
mapping is still missing in ExtractedPage/worker. Whole-page quarantine would
unnecessarily lose reliable Spanish; therefore do not install it as fallback.

Next adapter must map converter regions back to source blocks, detect omitted
or duplicated source units and unsafe merges, and export ordered bounded
Markdown. No new classifier ML or entire platform redesign is proposed.
