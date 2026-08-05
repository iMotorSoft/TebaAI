# Page-First & Editorial Retrieval — Conventions

Operational reference for Breslov PDF ingestion and retrieval. Authoritative
decisions live in ADR-014, ADR-015 and ADR-016.

---

## Identidad y scope documental

El scope por obra se resuelve antes del ranking. La familia canónica no se
infiere desde un token compartido ni desde una referencia interna aislada:

```text
work_family ≠ free document title ≠ source lesson ≠ edition
LH ≠ LM II
```

Un volumen de Likutey Halajot puede seleccionar discursos basados en Likutey
Moharán II, 8 sin convertirse en una edición de Likutey Moharán II. El status
`ready|test_candidate` tampoco define identidad bibliográfica: solo participa
como desempate entre evidencias equivalentes.

Aliases ambiguos como `Likutey` o `LM` no deben resolverse automáticamente. Una
consulta comparativa puede habilitar ambas familias solo cuando el cruce es
explícito. Elegir una edición concreta dentro de una familia requiere scope o
metadata de edición explícitos; no se implementa mediante penalizaciones,
filename exclusions o document IDs especiales.

### Contrato canónico V1

| Dimensión | Semántica | Scope | Ranking |
|---|---|---|---|
| `work_family` | familia contenedora | sí | no |
| `canonical_work` | obra normalizada | sí | no |
| `edition` | edición publicada con procedencia | explícito | no |
| `volume` | volumen bibliográfico aprobado | explícito | no |
| `source_work` | obra desarrollada/citada | source scope | no |
| `source_lesson` | unidad de la obra fuente | source scope | no |
| `technical_version` | pipeline/representación | no | no |
| `document_instance` | ID, filename, hash y status | document scope | status solo desempata |

La procedencia permitida es `explicit|derived|unresolved|conflicting`. Un valor
no nulo nunca puede ser `unresolved`; filename y `document_code` solo generan
metadata `derived`. `_v2`, `II` en una obra fuente y el número de lección nunca
son volumen.

Scopes canónicos:

```text
family scope  ≠ edition scope ≠ document scope ≠ source scope
```

El family scope LH incluye Interior Final y The Rosenberg Edition. El edition
scope Interior Final excluye otras ediciones. El source scope LM II, lección 8
puede incluir el original y comentarios que declaren una relación explícita,
con roles separados. `Likutey Halajot LM II 8` es un documento LH que desarrolla
LM II, 8; la fuente no reemplaza su familia.

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

## Normalización Literal PDF (ADR-020)

Dos representaciones:

- `text_original`: superficie extraída/persistida; cita, evidencia visible,
  offsets y auditoría; nunca se reescribe.
- `search_text_normalized`: forma de búsqueda; NFKC + colapso de whitespace
  + variantes controladas de fragmentación.

Reglas (módulo `pdf_ligature_normalization.py`):

- Compatibilidad: `ﬀ→ff`, `ﬁ→fi`, `ﬂ→fl`, `ﬃ→ffi`, `ﬄ→ffl`, `ﬅ→st`, `ﬆ→st`
  (NFKC + tabla explícita determinista).
- Fragmentación segura: las variantes solo *insertan* el espacio de extracción
  tras un dígrafo de ligadura embebido (`refinamiento` → `refi namiento`);
  nunca se eliminan espacios, por lo que las palabras reales nunca se unen
  (`la flor`, `por fin`, `fi nal` intactas).
- Elisión de glosas parentéticas precedidas por letra (solo matching):
  `Birur (pl. birurim; lit. “tamizar”) hace` → `birur hace`;
  `(Salmos 16:1)` al inicio de línea/bloque se preserva.
- Idempotencia obligatoria y Hebreo intacto (niqqud/RTL/combining marks).
- La normalización no corrige ortografía (`aﬀecto`→`affecto`).
- Nota 36 (`reﬁ namiento`, página 56/38): recuperada como
  `footnote_literal_exact` PRIMARY con la consulta normalizada; la cita
  conserva la ligadura original. Batch literal ampliado **25/25**.

## Identidad Editorial de Evidencia (ADR-021)

El `evidence_id` (v2) identifica la **entidad editorial mínima citable**,
no el chunk de almacenamiento:

```text
evidence_id = ev-{SHA-256({"v":"2","chunk":chunk_id,"entity":entity_key})}
```

Claves por tipo:

| Match type | Entity key |
|---|---|
| `footnote_literal_exact` | `footnote:{number}` |
| `structural_heading_*` | `heading:{_fold(heading_original)}` |
| `printed_reference_exact` | `reference:{_fold(variant).strip(parenthesis)}` |
| `body_literal_exact` | `body` |
| fallback | `chunk` |

Campos asociados:
- `evidence_identity_version`: `"v2"`
- `legacy_evidence_id`: ID de chunk anterior (compatibilidad)

Invariantes:
- Distinta entidad → distinto ID (nota 35 ≠ nota 36 ≠ heading 6)
- Misma entidad → mismo ID (variantes de query, ligaduras, casing)
- Query, rank, IA, status → no afectan
- Cross-interface (admin/guest) → mismo ID


---

## Ranking de Evidencia

### Heading primary vs body context

For a nominal heading query, the canonical heading block
(`structural_heading_exact|normalized|accent_folded`) is the PRIMARY. A body
chunk that merely contains the query tokens (`all_tokens_ordered`) is context
or associated body, never the canonical cite.

- The heading line is recognized inside the chunk content (`N ■ TITLE` with
  the editorial symbol), independently of the inherited `section_title`.
- Content-derived headings outrank metadata-inherited headings.
- The merge preserves the structural classification over a generic
  `exact_phrase` from the general literal lane.
- The heading page (PDF and printed) is never replaced by the body page.

### Printed reference deterministic primary

For a structured reference such as `Salmos 16:1`:

1. `printed_reference_exact` (exact surface, verse boundary enforced:
   `16:1` never matches `16:10`/`16:11`/`116:1`);
2. explicit work scope (`Salmos 16:1 en Likutey Halajot`) filters to the
   document;
3. `source_layer=marginal_reference`;
4. complete editorial metadata (PDF + printed page);
5. document status as tiebreak between equivalents;
6. stable canonical key `(document_id, chunk_id)` as the final tie-break.

The PRIMARY is fixed by the backend before generative synthesis. The IA may
associate claims with allowed evidence IDs but cannot change the canonical
document/page or select a different primary. `printed_page` non-null is
preserved through merge/dedupe/enrichment; when the stored label is NULL the
visible printed folio is recovered from the opening running header of the
page content.

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

Permanent validation cases (see `tests/fixtures/likutey_halajot_page_first_v2_acceptance.json`,
which also records `expected_match_type`, `expected_source_layer`,
`expected_primary`, `expected_printed_page` and `expected_stable_primary`):

1. `CONSTRUYENDO UN MISHKÁN` → 51/33, structural_heading_exact, section_heading, PRIMARY
2. `INCLINADO HACIA LA BONDAD` → 53/35, structural_heading_exact, section_heading, PRIMARY
3. `Salmos 16:1` → 55/37, printed_reference_exact, marginal_reference, PRIMARY (determinista 20/20)
4. `El hombre se une a HaShem…` → 56/38, footnote_literal_exact, footnote, PRIMARY
5. `MELODÍAS Y PLEGARIAS` → 56/38, structural_heading_exact, section_heading, PRIMARY

Negativos: headings inventados → `no_evidence`; `Salmos 16:99`/`99:99` sin
`printed_reference_exact` falso; `(Salmos 116:1)` no se clasifica como
referencia impresa si el corpus solo contiene `116:10`.

---

## Gestor de Contenidos V1

La consola de upload no puede ejecutar esta ingesta mientras el pipeline
page-first continúe distribuido entre scripts específicos y servicios
parciales. El gate requiere un orquestador Python reusable que persista la
página completa antes de derivar bloques y chunks, seleccione una colección
test aislada, registre ownership y transiciones atómicas del job, y reconcilie
PostgreSQL↔Milvus antes de finalizar en `test_candidate`.

La continuación de 2026-08-05 agregó la base durable (claim exclusivo,
lease/heartbeat, grafo de estados, attempts y manifest), y la creación atómica
ahora encola en vez de quedar en `validating`. Esto no equivale a ingesta: el
contrato de worker todavía no tiene una implementación concreta reusable del
pipeline, reconciliación ni cleanup exacto. No se autoriza envolver scripts con
shell ni ejecutar E2E de escritura contra `breslov_primary`. Ver ADR-022 y el
reporte reproducible
`data/reports/breslov/2026-08-05-content-manager-v1-dev/`.

## Documento de Referencia

- **Document:** `LIKUTEY HALAJOT (Interior Final).pdf`
- **SHA-256:** `440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a`
- **Status:** `test_candidate` (DEV)
- **Pages:** 284 | **Chunks:** 268 | **Embeddings:** 268/268
