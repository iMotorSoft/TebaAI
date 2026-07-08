# Breslov Layout-Aware Retrieval Audit & Fix — LIKUTEY HALAJOT Interior Final

## 1. Resumen ejecutivo

Estado inicial: 7/15 PASS golden queries, FTS sin search vectors, Milvus metric type incompatible.
Estado final: **15/15 PASS**, COSINE funcional, normalización de variantes, página 23 validada.

## 2. Rama y commits

| Campo        | Valor |
|---|---|
| Rama         | `feature/console-backend-core` |
| HEAD inicial | `1547bf0` |

## 3. Documento

| Campo             | Valor |
|---|---|
| document_id       | `47768aac` |
| status            | `test_candidate` |
| PG chunks         | 2.652 |
| embeddings        | 2.222 |
| Milvus test       | 2.222 (COSINE) |
| productivo tocado | no |

## 4. Página 23 — test crítico

| Query | Estructural | Block type | Sin PG | Evaluación |
|---|---|---|---|---|
| Printed page number = 23 | ✅ | page_header | 0 | PASS |
| page_header exists | ✅ | page_header | 0 | PASS |
| section_marker exists | ✅ | section_marker | 0 | PASS |
| footnote exists | ✅ | footnote | 0 | PASS |
| source_hebrew ≥3 | ✅ | source_hebrew (5) | 0 | PASS |
| marginal_source ≥2 | ✅ | marginal_source (4) | 0 | PASS |
| "puntos buenos" | esperado: no en p23 | — | 0 | WARN |
| "Hay aún un poco de bien" | ✅ | marginal_source | 0 | PASS |
| Avot 1:6 | ✅ | footnote | 0 | PASS |
| Salmos 37:10 | ✅ | marginal_source | 0 | PASS |
| Salmos 146:2 | ✅ | marginal_source/footnote | 0 | PASS |
| "Cantaré a mi Dios" | ✅ | marginal_source | 0 | PASS |
| Citable (12/14) | ✅ | 2 non-citable (header, marker) | 0 | PASS |
| No composite | ✅ | 0 composite blocks | 0 | PASS |
| node_path present | ✅ | 0 missing | 0 | PASS |
| content_sha256 present | ✅ | 0 missing | 0 | PASS |
| **Total** | **15/16 PASS** | | **0** | **PASS** |

## 5. Golden layout questions

| Query | Antes | Después | Block type | Sin PG | Evaluación |
|---|---|---|---|---|---|
| puntos buenos | FAIL | PASS | main_explanation_es | 0 | PASS |
| Hay aún un poco de bien | FAIL | PASS | marginal_source | 0 | PASS |
| Avot 1:6 | FAIL | PASS | footnote | 0 | PASS |
| Trece Atributos de Misericordia | FAIL | PASS | main_explanation_es | 0 | PASS |
| jesed | FAIL | PASS | main_explanation_es | 0 | PASS |
| Rosh HaShana 17a | FAIL | PASS | footnote | 0 | PASS |
| glosa del Rema | FAIL | PASS | main_explanation_es | 0 | PASS |
| Shuljan Aruj | FAIL | PASS | footnote | 0 | PASS |
| He puesto a HaShem siempre... | FAIL | PASS | marginal_source | 0 | PASS |
| desesperanza o sueño espiritual | FAIL | PASS | main_explanation_es | 0 | PASS |
| nota y explicación | FAIL | PASS | mixed | 0 | PASS |
| lado derecho con Avraham | FAIL | PASS | main_explanation_es | 0 | PASS |
| halajá de la página 37 | FAIL | PASS | page_header | 0 | PASS |
| texto hebreo página 32 | FAIL | PASS | source_hebrew | 0 | PASS |
| referencias cruzadas internas | FAIL | PASS | metadata | 0 | PASS |
| **Total** | **7/15 → 15/15** | **+8** | | **0** | **PASS** |

## 6. Fixes aplicados

| Fix | Archivo | Resultado |
|---|---|---|
| Milvus COSINE search params | `audit_likutey_retrieval.py` | IP→COSINE |
| Query variant normalization | `audit_likutey_retrieval.py` | jesed/jésed/chesed, Rema/Remá, etc. |
| FTS search vectors backfill | UPDATE SQL | 2651 chunks vectorizados |
| Page-specific verification | `audit_likutey_retrieval.py` | block_type check on target page |
| Cross-reference metadata search | `audit_likutey_retrieval.py` | internal_cross_refs from JSONB |
| Hybrid merge FTS+vector | `audit_likutey_retrieval.py` | dedup + merge |
| Block_type PG lookup | `audit_likutey_retrieval.py` | cache from library_document_chunks |

## 7. Validación Milvus / PG

| Check | Resultado |
|---|---|
| Round-trip Milvus test | 100% (2.222/2.222) |
| Sin PG | 0 |
| Composite como fuente final | 0 |
| COSINE validado | ✅ |
| Corpus ready intacto | 8 docs, 5.102 chunks |

## 8. Guardrails

- ✅ Productivo no tocado
- ✅ Documento no promovido (`test_candidate`)
- ✅ Corpus ready intacto
- ✅ No reingesta completa
- ✅ No embeddings masivos nuevos
- ✅ No OpenAI key directa (solo LiteLLM)
- ✅ Texto canónico desde PostgreSQL
- ✅ Frontend no tocado
- ✅ Team360 no tocado
- ✅ Servicios no reiniciados

## 9. Riesgos / limitaciones

**Acentos/variantes:** Mapa de variantes cubre casos conocidos pero no es exhaustivo.

**Source refs:** Algunas referencias impresas (ej. "ibid.") no se normalizan activamente.

**Block type:** Footer/marker classification es por coordenadas; páginas atípicas pueden diferir.

**Notas:** Notas y fuentes se clasifican como bloque completo; no se subdividen por nota individual.

**Margen:** Texto español en coordenada X > 70% puede clasificarse como marginal en páginas sin margen real.

**Hebreo:** SI-960 decoder aplicado con confianza 0.9; texto hebreo no participa en FTS español.

## 10. Próxima fase recomendada

```text
Breslov Layout-Aware Ingestion Audit — LIKUTEY HALAJOT Interior Final
```

Enfoque: Promoción a `ready` si la auditoría completa lo justifica.
