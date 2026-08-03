# Canonical Editorial Evidence Selection V1 — 2026-08-03 (DEV)

Gate: `TEBAAI_CANONICAL_EDITORIAL_EVIDENCE_SELECTION_V1_DEV_READY`

## 1. Estado

**PASS** — `TEBAAI_CANONICAL_EDITORIAL_EVIDENCE_SELECTION_V1_DEV_READY`.

Gates elevados:

```
TEBAAI_EXACT_EDITORIAL_EVIDENCE_RANKING_V1_DEV_READY
TEBAAI_LIKUTEY_HALAJOT_PAGE_FIRST_REINGEST_V2_DEV_READY
```

Gates acumulados:

```
TEBAAI_GUEST_RESEARCH_ACCESS_E2E_RECOVERY_DEV_READY
TEBAAI_FOOTNOTE_LITERAL_RANKING_V1_DEV_READY
TEBAAI_PAGE_FIRST_EDITORIAL_CONVENTIONS_DOCUMENTED_DEV_READY
```

## 2. Entorno

| Servicio | Estado |
|---|---|
| Milvus 2.6 | healthy, NO reiniciado por el agente; colección `tebaai_breslov_chunks_v1` 5.370 entidades |
| PostgreSQL | NO reiniciado |
| LiteLLM | NO reiniciado |
| Backend DEV | activo en 127.0.0.1:7008 (reiniciado por el agente con los fixes) |
| Astro DEV | activo en 127.0.0.1:3008 |
| Producción / corpus / embeddings / `.bashrc` | No modificados |
| Push | No realizado |

Preflight read-only de Milvus: `milvus-baseline-readonly.json` (LoadState
Loaded, 5.370 entidades, query sample ok, index HNSW/COSINE).

## 3. Síntomas y causa raíz

### Headings 51/53/56 perdían frente a 52/55/57

1. La línea heading (`4 ■ CONSTRUYENDO UN MISHKÁN`) vive dentro de
   `library_document_chunks.content`, pero la búsqueda estructural solo
   comparaba `section_title` y `search_text_normalized` → el chunk golden solo
   alcanzaba `structural_heading_partial` (80) por palabras dispersas.
2. El `section_title` heredado por los chunks cuerpo adyacentes (52/55/57) los
   clasificaba como `structural_heading_all_tokens_ordered` (130).
3. `_literal_evidence_strength` no incluía tipos `structural_heading_*`:
   el `exact_phrase` (30) del carril literal genérico descartaba la
   clasificación estructural del golden (0) durante el merge.

### Salmos 16:1 alternaba PRIMARY y perdía printed_page

1. Falso positivo: ILIKE `%salmos 16:1%` coincidía con `(Salmos 16:10)` en
   Cruzando 368 → etiquetado `printed_reference_exact` + boost +15.
2. `merge_results` asignaba `literal_rank` por orden de llegada → los scores
   combinados dependían del orden de recuperación.
3. `priority_literal_query` excluía referencias impresas → el PRIMARY caía en
   el orden de claims de la IA (no determinista).
4. `printed_page=null`: `extract_printed_page` devolvía null en páginas de
   folio impar y el resolver abortaba en la primera línea no coincidente
   (preámbulo de glifos RTL binarios antes del folio `"  37"`).

## 4. Fix (general, sin hardcodes)

| Capa | Cambio |
|---|---|
| Clasificación | reconocimiento de líneas heading `N ■ TITLE` dentro de `content`; `heading_from_content` (contenido > metadata heredada) |
| Selección | tipos canónicos (exact/normalized/accent_folded) = PRIMARY; body `all_tokens_ordered` = contexto |
| Merge | `_literal_evidence_strength` cubre `structural_heading_*`; sort literal determinista por `(literal_score, chunk_id)`; tie-break estable `(combined, semantic, document_id, chunk_id)` |
| Referencias | superficie exacta con borde de versículo `(?!\d)`; el tag `printed_reference_exact` exige superficie real |
| PRIMARY | `priority_literal_query` incluye `is_printed_reference`; PRIMARY fijado antes de la IA; claim grounding no puede cambiarlo |
| printed_page | preservación de no-nulo; recuperación del folio visible en el encabezado (preámbulo RTL tolerado) |
| Scope | `Salmos 16:1 en Likutey Halajot` filtra al documento y agrega la superficie desnuda como variante |
| Frontend | `marginal_reference` aceptado como source layer + label; `literal_match_kind` passthrough para kinds editoriales exactos |

## 5. Matriz de resultados

| Control | Resultado |
|---|---|
| Milvus healthy | PASS (5.370, no reiniciado) |
| Semantic status | ok |
| Research status | no degraded |
| Mishkán 51/33 `structural_heading_exact` PRIMARY | PASS (5/5 idéntico) |
| Bondad 53/35 `structural_heading_exact` PRIMARY | PASS (5/5 idéntico) |
| Melodías 56/38 `structural_heading_exact` PRIMARY | PASS (5/5 idéntico) |
| Salmos LH 55/37 `printed_reference_exact` `marginal_reference` PRIMARY | PASS (5/5 y 20/20 idéntico) |
| `structural_heading_exact` preservado | PASS |
| Body asociado como contexto | PASS |
| Claim grounding no cambia PRIMARY | PASS |
| Nota 35 (56/38, marker 35) | PASS (5/5) |
| Proper name (Gedalia of Linitz/Gedalia/Linitz) | PASS |
| Hebreo (niqqud y sin niqqud) | PASS |
| Bibliographic planner (Azamra) | PASS |
| Negativos (headings inventados, 16:99, 99:99, 116:1) | PASS (sin falsos exactos) |
| Scope explícito LH | PASS (55/37 inequívoco) |

## 6. Validaciones

- Backend focalizado (`-k "structural_heading or printed_reference or exact_editorial or primary_evidence or claim_grounding or page_first or simple_research or likutey_halajot"`):
  132 passed, 0 failed.
- Backend completo: **1430 passed, 0 failed** (baseline 1409 + 21 nuevos
  tests en `test_canonical_editorial_evidence_selection.py`).
- Frontend `pnpm check`: 0 errores, 0 warnings (2 hints).
- Frontend `pnpm test`: 69 passed.
- Frontend `pnpm build`: PASS, 8 páginas.
- E2E Playwright completo: **75 passed, 25 skipped, 0 failed** (skips
  documentados: goldens de era pre-reingest / pipeline avanzado, cubiertos
  por tests backend).
- API autenticada: 5 casos canónicos × 5 runs → 1 firma única por caso;
  Salmos 20/20 → 1 firma única (`ev-716847bfff6da041`, 55/37).
- `git diff --check`: PASS.

## 7. Reconciliación Git

- Rama: `feature/console-backend-core`; HEAD inicial `f85c2e4`; HEAD final
  (ver commits funcional + documental de esta fase).
- Preexistentes preservados (sin tocar): `global.js`, `PublicLayout.astro`,
  `manual-dev-pro-configuration.md`, ADR-013, `lat.md`, screenshots y reportes
  untracked ajenos.
- Commit funcional: `fix(breslov): make canonical editorial evidence selection deterministic`
- Commit documental: `docs(breslov): close canonical editorial evidence selection v1`
- Push: NO.

## 8. Servicios finales

Backend DEV activo en 127.0.0.1:7008; Astro DEV activo en 127.0.0.1:3008.
Milvus healthy y no reiniciado por el agente; PostgreSQL y LiteLLM no
reiniciados; producción, corpus y embeddings no modificados; `.bashrc` no
modificada; push no realizado.

## 9. Artefactos

- `case-mishkan.json`, `case-bondad.json`, `case-melodias.json`,
  `case-salmos.json` — matrices before/after por caso.
- `milvus-baseline-readonly.json` — preflight read-only de Milvus.
- `api-five-cases-5x.json` — resultados de los 5 casos × 5 runs.
- `salmos-determinism-20x.json` — 20/20 Salmos.
- `negatives.json` — resultados de los negativos.
- ADR: `docs/adr/ADR-016-canonical-editorial-evidence-selection-v1.md`.
