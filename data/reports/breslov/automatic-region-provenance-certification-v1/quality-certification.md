# Computed quality evidence (narrow subset)

Reuses existing RegionState and aggregate semantics; no confidence scale or ML.
Default UNRESOLVED. Positive inputs are computed from source, never flags from
fixtures/callers. No OCR, decoding, repair or language-based rejection.

ACCEPTED requires certified supported note provenance, pure LTR, adapter
allowlisted transformations, exact native/source token equivalence, and
Markdown decoration-only equivalence. Native glyphs must uniquely match the
source baseline/geometry, be opaque painted ink in horizontal LTR, and have no
later overlapping paint/text/image operation. Unknown/occluded/duplicate glyph
ownership cannot verify quality. This conservative proof leaves many good
regions unresolved; absence of U+FFFD alone never accepts text.

PLATFORM_EXTRACTION_ERROR requires a certified region with U+FFFD in layout,
visible independently extracted native trace with no U+FFFD, demonstrating
substitution in extraction.55's corrupt notes-heading is found this way without
fixture coordinates. If source/visibility attribution is not proved, quality
remains UNRESOLVED. No automatic SOURCE_PDF_ERROR assignment: zero such cases
is not proof that the PDF is flawless.

Serializer hyphenation warnings, source Markdown-metacharacter ambiguity,
mixed/neutral direction, unsupported numeric markers/zone/geometry, missing
trace, source/native mismatch or failed equivalence all withhold acceptance.
No broad mojibake/numeric/logical-order detector is claimed.55 previous whole
box and56 notes are NOT promoted to make coverage pass.

167: five notes ACCEPTED; two notes and all body/Hebrew units unresolved.
55: bad heading platform error, next note33 accepted, previous unresolved.
56: both page-local note provenance certificates exist, neither quality accepted.
See JSON artifacts for actual statuses/reasons. Partial coverage FAILS the goal.
