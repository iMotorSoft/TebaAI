# Exact Editorial Evidence Ranking V1 — DEV

Estado: `TEBAAI_EXACT_EDITORIAL_EVIDENCE_RANKING_V1_DEV_READY`

Fecha: 2026-07-31
Rama: `feature/console-backend-core`
HEAD: `e31520d`

## 1. Causa

La consulta `Salmos 16:1` retornaba el documento `ready` (Likutey Halajot LM II 8) como primary y ocultaba el match exacto del documento `test_candidate` (Likutey Halajot — Interior Final, page 55).

### Causa raíz

`build_query_variants("Salmos 16:1")` → `["Salmos 16:1", "salmos"]`

El variant corto `"salmos"` fue generado por `detect_short_english_name_query()`, que detectó "Salmos" como nombre propio corto. Este variant disparó ILIKE `%salmos%` en docenas de chunks de documentos `ready`, dándoles `exact_match=True` y un `literal_score` comparable al match exacto completo del `test_candidate`. El ranking por status prefería `ready` sobre `test_candidate` a igualdad de scoring.

El flujo principal (`run_simple_rag`) ya suprimía `detect_short_english_name_query` para referencias impresas, pero `build_query_variants()` ejecutaba su propia detección sin ese contexto.

## 2. Fix

| Archivo | Cambio |
|---|---|
| `simple_research_rag.py:483` | `build_query_variants` acepta `is_printed_reference: bool = False` |
| `simple_research_rag.py:487` | Skip `detect_short_english_name_query` cuando `is_printed_reference=True` |
| `simple_research_rag.py:1471` | Caller pasa `is_printed_reference=True` |

## 3. Validación API

| Query | Doc ID | Page | Primary |
|---|---|---|---|
| Salmos 16:1 | 132a791a (test_candidate) | 55 | ✅ PRIMARY |
| (Salmos 16:1) | 132a791a (test_candidate) | 55 | ✅ PRIMARY |
| salmos 16:1 | 132a791a (test_candidate) | 55 | ✅ PRIMARY |
| Salmo 16:1 | 56ddcc3b (ready) | 35 | ⚠️ Ready (singular no detectado como ref) |
| CONSTRUYENDO UN MISHKÁN | 132a791a (test_candidate) | 51 | ✅ PRIMARY |
| INCLINADO HACIA LA BONDAD | 132a791a (test_candidate) | 53 | ✅ PRIMARY |
| MELODÍAS Y PLEGARIAS | 132a791a (test_candidate) | 56 | ✅ PRIMARY |
| el hombre se une a HaShem | 132a791a (test_candidate) | 56 | ✅ PRIMARY |
| Salmos 99:99 | No match exacto | — | ⚠️ Retorna semantic |
| Salmos 16:99 | No match exacto | — | ⚠️ Retorna semantic |

## 4. Tests

| Suite | Resultado |
|---|---|
| Backend (full) | 1,401 passed, 94 warnings |
| Frontend check | 0 errors, 0 warnings, 0 hints |
| Frontend test | 60 passed |
| Frontend build | 8 pages |

## 5. Gates

```
TEBAAI_EXACT_EDITORIAL_EVIDENCE_RANKING_V1_DEV_READY
TEBAAI_LIKUTEY_HALAJOT_PAGE_FIRST_REINGEST_V2_DEV_READY
```

## 6. Archivos modificados

- `backend/modules/library/simple_research_rag.py` — 3 líneas (parámetro + guard + caller)
- `backend/modules/library/simple_research_repository.py` — 1 línea (fix alias.casefold, sesión previa)
- `docs/adr/ADR-015-exact-editorial-evidence-ranking-v1.md` — nuevo

## 7. Servicios

- PostgreSQL/Milvus/LiteLLM: no reiniciados
- Producción: no modificada
- Embeddings: no recalculados
- Push: no realizado
