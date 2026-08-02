# Page-First & Editorial Retrieval — Conventions

Operational reference for Breslov PDF ingestion and retrieval. Authoritative
decisions live in ADR-014 and ADR-015.

---

## Ingesta: Page-First

```
PDF → extract full page → persist → derive blocks → derive chunks
```

1. Extract every PDF page as complete text (PyMuPDF4LLM + page markers).
2. Store full page in `library_pages_v2` before fragmenting.
3. Derive editorial blocks from page layout.
4. Derive chunks from blocks, never from pages directly.
5. Populate `search_text_normalized` on every chunk.

**Invariants:**

- Page is the atomic storage unit; chunks are derivations.
- `search_text_normalized` must never be NULL for citable chunks.
- Purge all prior representations before re-ingesting a document.

---

## Estructura Editorial

### Roles

| Role | Retrieval lane |
|---|---|
| `section_heading` | `structural_heading_exact` |
| `subsection_heading` | `structural_heading_exact` |
| `commentary` | `body_literal_exact` |
| `marginal_reference` | `printed_reference_exact` |
| `footnote_body` | `footnote_literal_exact` |
| `footnote_marker` | — (anchor only) |
| `running_header` | — (excluded) |
| `unknown` | — (fallback) |

### Relationships

```
heading           → associated body paragraph
marginal_reference → associated body paragraph
footnote_marker   → footnote_body
footnote_body     → anchor paragraph → containing section
```

---

## Referencias Impresas

- Surface form: `(Salmos 16:1)` — always preserved
- Normalized: `salmos 16:1` — for search only
- Detection: `_BIBLICAL_REFERENCE` regex
- No AI-based correction or expansion

---

## Notas al Pie

- Marker and body stored as separate blocks.
- Section resolved from anchor paragraph, not from visually nearest heading.
- Adjacent notes (e.g. 35/36/37) must be distinguishable by marker + anchor.
- `anchor_section` is the heading governing the marker anchor paragraph;
  `next_heading` is the following editorial boundary. They are not synonyms.
  For note 35: `anchor_section=5 ■ INCLINADO HACIA LA BONDAD` and
  `next_heading=6 ■ MELODÍAS Y PLEGARIAS`.
- Short lookup terms preserve the complete canonical quote. Literal phrases of
  three or more terms locate the source span; line-wrap whitespace is
  normalized for matching while the original quote remains intact.

---

## Ranking de Evidencia

### Tiers (strongest to weakest)

```
exact editorial (printed_reference, structural_heading, footnote, body)
  > normalized exact
  > short proper name exact
  > literal partial
  > semantic strong
  > semantic medium / thematic
  > AI inferred
```

### Status Documental

- `ready` — preferred at equal evidence strength
- `test_candidate` — full retrieval in DEV; tiebroken by ready
- `superseded` — no primary unless explicit
- `archived` / `invalid` — excluded

```
Exact scoped test_candidate  >  semantic ready
Ready exact                  >  test_candidate semantic
```

### Variant Rules

- Structured queries (printed references, headings) must NOT generate
  unqualified short variants.
- `is_printed_reference=True` suppresses `detect_short_english_name_query`.
- Reference boundaries: `16:1` must not match `16:10` or `116:1`.

---

## IA

- IA redacts the narrative answer.
- Backend retrieves and classifies evidence.
- IA must not invent references, pages, or quoted text.
- AI output is validated against evidence IDs in the response.

---

## Multilingüe

- ES: primary language for Spanish corpus.
- EN: secondary language; short proper names detected in English.
- HE: Hebrew exact lane (niqqud-preserving); RTL rendering in UI.
- Mixed queries: primary language determined from subject terms.

---

## Fixtures de Regresión

Permanent validation cases (see `tests/fixtures/likutey_halajot_page_first_v2_acceptance.json`):

1. `CONSTRUYENDO UN MISHKÁN` → page 51, structural_heading
2. `INCLINADO HACIA LA BONDAD` → page 53, structural_heading
3. `Salmos 16:1` → page 55, printed_reference
4. `El hombre se une a HaShem…` → page 56, footnote
5. `MELODÍAS Y PLEGARIAS` → page 56, structural_heading

---

## Documento de Referencia

- **Document:** `LIKUTEY HALAJOT (Interior Final).pdf`
- **SHA-256:** `440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a`
- **Status:** `test_candidate` (DEV)
- **Pages:** 284 | **Chunks:** 268 | **Embeddings:** 268/268
