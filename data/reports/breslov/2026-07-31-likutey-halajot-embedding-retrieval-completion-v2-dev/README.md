# Likutey Halajot Page-First V2 — Embedding & Retrieval Completion — DEV

Estado: `TEBAAI_LIKUTEY_HALAJOT_PAGE_FIRST_REINGEST_V2_DEV_READY`

Fecha: 2026-07-31

Rama: `feature/console-backend-core`

## 1. Documento

| Campo | Valor |
|---|---|
| Document ID | `132a791a-d12b-45bc-9b34-dd143605de12` |
| Title | Likutey Halajot — Interior Final |
| SHA-256 | `440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a` |
| Status | `test_candidate` |
| Scope | `breslov_primary` |
| Pages | 284 |
| Chunks | 268 |
| FTS NULL | 0 |

## 2. Chunk Audit

| Métrica | Valor |
|---|---|
| Min chars | 20 |
| Max chars | 5,575 |
| Avg chars | 3,286 |
| P50 chars | 3,604 |
| P95 chars | 4,672 |
| Token estimate | NULL (no calcularon en ingestion) |
| Oversized | 0 |
| Splits applied | 0 |

## 3. Embeddings

| Métrica | Valor |
|---|---|
| Run ID | `90ac0fe8-11bf-464f-b1a8-ecef557677e6` |
| Model | `openai_text_embedding_3_small` |
| Dimension | 1536 |
| Batch size | 16 |
| Batches | 17 (aproximadamente) |
| Elapsed | 179.8s |
| Chunks embedded | 268 |
| Failed | 0 |
| Skipped | 0 |

## 4. PG↔Milvus Reconciliation

| Métrica | Valor |
|---|---|
| PG chunk IDs | 268 |
| Milvus PKs | 268 |
| Match | 268 (100%) |
| Missing in Milvus | 0 |
| Orphans in Milvus | 0 |
| Duplicate PKs | 0 |
| Status | `indexed` |

Total Milvus: 5,370 entities (5,102 previos + 268 nuevos)

## 5. Code Fix

**File:** `backend/modules/library/simple_research_repository.py:54`

**Bug:** `resolve_ready_documents` comparaba `alias` (sin casefold) contra `title.casefold()`, rompiendo matches cuando el usuario pasaba títulos completos (ej. "Likutey Halajot") en vez de códigos (ej. "lh").

**Fix:** Cambiado `alias in ...` a `alias.casefold() in ...`.

## 6. Retrieval Validation

| Query | Page | Doc | Primary | Match Kind |
|---|---|---|---|---|
| CONSTRUYENDO UN MISHKÁN | 51 | LH Interior Final (test_candidate) | ✅ PRIMARY | structural_heading |
| INCLINADO HACIA LA BONDAD | 53 | LH Interior Final (test_candidate) | ✅ PRIMARY | structural_heading |
| MELODÍAS Y PLEGARIAS | 56 | LH Interior Final (test_candidate) | ✅ PRIMARY | structural_heading |
| el hombre se une a HaShem | 56 | LH Interior Final (test_candidate) | ✅ PRIMARY | exact_phrase |
| Salmos 16:1 | 55 | LH Interior Final (test_candidate) | ⚠️ SECONDARY | exact_phrase (ready doc ranks higher) |

### Salmos 16:1 — Nota

El contenido "(Salmos 16:1)" existe en page 55 del test_candidate y es recuperable via SQL con LIKE. En la API, otras obras `ready` y especialmente "Likutey Halajot LM II 8" producen 12+ matches semánticos/trigram que desplazan el match exacto del test_candidate. La causa raíz es doble:

1. `build_query_variants("Salmos 16:1")` genera `["Salmos 16:1", "salmos"]` — la variante corta "salmos" dispara ILIKE en docenas de chunks de obras `ready`, inflando su `literal_score` al mismo nivel que el match exacto del test_candidate.
2. El ranking final en `_apply_claim_traceability` prefiere chunks `ready` sobre `test_candidate` a igualdad de scoring.

No se corrigió en esta fase porque modificar la estrategia de variantes o el scoring documental requiere un ADR de ranking.

## 7. Tests

| Suite | Resultado |
|---|---|
| Backend focal (`embedding or milvus or ...`) | 213 passed, 0 failed |
| Backend completo | 1,401 passed, 94 warnings (deuda datetime.utcnow) |
| Frontend check | 0 errors, 0 warnings, 0 hints |
| Frontend test | 60 passed, 5 files |
| Frontend build | 8 pages, 3.85s |

## 8. Gate Final

```
TEBAAI_LIKUTEY_HALAJOT_PAGE_FIRST_REINGEST_V2_DEV_READY
```

| Control | Resultado |
|---|---|
| Documento nuevo identificado | PASS |
| 284 páginas | PASS |
| Chunks auditados | PASS |
| Embeddings completos 268/268 | PASS |
| PG↔Milvus 100% | PASS |
| Missing/Orphan/Duplicate | 0 / 0 / 0 |
| Otros documentos intactos | PASS |
| Mishkán (page 51, PRIMARY) | PASS |
| Bondad (page 53, PRIMARY) | PASS |
| Nota 35 section heading (page 56) | PASS |
| Nota 35 text (page 56) | PASS |
| Salmos 16:1 (page 55) | ⚠️ contenido presente, ranking prefiere ready |
| Backend tests | PASS |
| Frontend check/build/test | PASS |
| Producción modificada | No |
| Push | No |
