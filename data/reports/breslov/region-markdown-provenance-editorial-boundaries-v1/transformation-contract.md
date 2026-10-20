# Transformation contract V1

Ownership travels from source IR into serialization; text equality is only a
secondary verification, never the mapping authority.

Allowed in this candidate:

- `MARKDOWN_DECORATION`: the existing PyMuPDF4LLM serializer emits headings,
  `>`, `_`, `**`, strikeout, brackets already in source, and whitespace/style
  boundaries. Emphasis wrappers do not become new editorial identities.
- `EDITORIAL_GROUPING`: split an extractor box at a source note start; group
  lines and multiple source blocks according to the certified column flow.
  Cross-page continuation remains an explicit relation, not merged offsets.

No font decoding, ligature repair, RTL reversal, character invention, number
substitution, spelling correction, column dropping or column-interleaving is
allowed. `SAFE_NORMALIZATION` is deliberately not activated here. Source
ligatures/fragmented `Tefi lá`/`refi namiento` retain extraction representation.

`transformation_status=ALLOWLIST_ONLY` describes the supported serializer path,
NOT independent quality approval. The existing quality contract still requires
positive text/order/structure evidence. A source line ending in `-` triggers
conservative `UNRESOLVED` transformation status: the historical serializer can
silently remove that hyphen. The offline quality bridge refuses acceptance of
that unit even if the caller supplies positive verification flags. This phase
neither fixes nor silently certifies that behavior (real page56 body example).

## Independent round-trip checks

Tests/report use MarkdownIt's inline tokens (strikethrough enabled) to strip
allowed structural decoration. Source canonical projection and semantic output
are compared after **whitespace-only equivalence**. Letters, punctuation,
numbers, case, marks and order are NOT normalized. This tests text conservation,
not Hebrew correctness, and is not used to discover source ownership.

Critical checks: all five167 Spanish body units, all60–66 page167 note units,
both35/36 page56 units, and terminal36/66 continuation units on57/168.
Generic tests cover `>`, `_`, `**`, `[35]`, repeated identical text, multiline
and neighboring notes. A deliberately unsupported dehyphenation must remain
unaccepted; it cannot pass via a forgiving round-trip correction.

Same source + adapter version + engine versions produces the same IDs, source
parts, boundaries, order, canonical offsets and decorated Markdown offsets.
Three fresh PDF parses are compared in `idempotence-results.json`; geometric
permutations preserve only structures whose order is geometry-authoritative.
