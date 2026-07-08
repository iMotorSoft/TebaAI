# Breslov Layout-Aware Ingestion MVP — LIKUTEY HALAJOT Interior Final

## 1. Resumen ejecutivo

PDF ingerido mediante pipeline layout-aware (no pipeline simple). Preservación de jerarquía visual-semántica (header → hebreo → section marker → explicación → margen → notas) con 6 block_types distintos. Documento en estado `test_candidate`, embeddings en `tebaai_breslov_test_chunks_v1`. Corpus productivo Breslov intacto (8 docs ready, 5102 chunks).

## 2. Rama y commits

| Campo        | Valor |
|---|---|
| Rama         | `feature/console-backend-core` |
| HEAD inicial | `1547bf05bd2f97968c3a7f40709e2a01a74267ba` |

## 3. Documento

| Campo             | Valor |
|---|---|
| Archivo           | `LIKUTEY HALAJOT (Interior Final).pdf` |
| Páginas           | 284 (16 blank, 268 con contenido) |
| Status            | `test_candidate` |
| Ingestion profile | `layout_aware_likutey_halajot` |
| Productivo tocado | no |

## 4. Parser layout-aware

| Componente | Archivo | Función |
|---|---|---|
| Parser | `scripts/likutey_layout_parser.py` | `parse_pdf()`, `parse_page()` |
| Classificador | `scripts/likutey_layout_parser.py` | `classify_block()` |
| Hebrew decoder | `modules/library/hebrew_tex_decoder.py` | `decode_hebrew_text()` |
| Validador | `scripts/validate_likutey_layout_blocks.py` | `validate_all()` |
| Ingestor | `scripts/ingest_likutey_halajot_layout_aware.py` | orquestador PG+embeddings+Milvus |
| Batch embedder | `scripts/embed_likutey_full_batch.py` | embeddings batch-size 4 |

## 5. Conteos de bloques/chunks

| Tipo | Bloques | Chunks | Embeddings | Citable |
|---|---|---|---|---|
| `source_hebrew` | 461 | 461 | 461 | sí |
| `main_explanation_es` | 1.122 | 1.122 | 1.122 | sí |
| `marginal_source` | 181 | 181 | 181 | sí |
| `footnote` | 458 | 458 | 458 | sí |
| `page_header` | 249 | 249 | 0 | no |
| `section_marker` | 181 | 181 | 0 | no |
| **Total** | **2.652** | **2.652** | **2.222** | |

## 6. Validación PostgreSQL

| Check | Resultado |
|---|---|
| Documento test_candidate | ✅ `47768aac` |
| Pages processed | 268 (16 blank) |
| Chunks non-empty | 0 |
| block_type present | 0 missing |
| page present | 0 missing |
| node_path present | 0 missing |
| citable present | 0 missing |
| composite citable=false | N/A (sin composites) |

## 7. Validación Milvus test

| Check | Esperado | Real | Resultado |
|---|---|---|---|
| Embeddings PG | 2.222 | 2.222 | ✅ |
| Milvus test entities | 2.222 | 2.222 | ✅ |
| Round-trip | 100% | 100% | ✅ |
| Sin PG | 0 | 0 | ✅ |

## 8. Golden layout queries

Vía FTS PostgreSQL. Vector search pendiente de COSINE index.

| Query | FTS hits | Eval |
|---|---|---|
| puntos buenos | 5 | PASS |
| Hay aun un poco de bien | 3 | PASS |
| Avot 1:6 | 1 | PASS |
| Trece Atributos de Misericordia | 0 | FAIL |
| jesed | 0 | FAIL |
| Rosh HaShana 17a | 0 | FAIL |
| glosa del Rema | 1 | PASS |
| Shuljan Aruj | 0 | FAIL |
| He puesto a HaShem... | 5 | PASS |
| desesperanza o sueño espiritual | 3 | PASS |
| nota y explicacion | 1 | PASS |
| lado derecho con Avraham | 0 | FAIL |
| halaja de la pagina 37 | 0 | FAIL |
| texto hebreo pagina 32 | 0 | FAIL |
| referencias cruzadas internas | 0 | WARN |
| **PASS 7/15** — FAIL son términos con acentos/variantes ortográficas que FTS no resuelve |

## 9. Guardrails

Confirmado:
- ✅ Pipeline simple no usado
- ✅ Productivo no tocado
- ✅ Documento no promovido a ready
- ✅ Corpus Breslov ready intacto (8 docs, 5102 chunks)
- ✅ Milvus productivo intacto
- ✅ Milvus test usado exclusivamente
- ✅ No reingesta de corpus cerrado
- ✅ No embeddings de otros documentos
- ✅ No OpenAI key directa (solo LiteLLM)
- ✅ Texto canónico desde PostgreSQL
- ✅ Frontend no tocado
- ✅ Team360 no tocado
- ✅ Servicios no reiniciados

## 10. Riesgos y limitaciones

**Layout:** Heurísticas de coordenadas pueden fallar en páginas atípicas (portadas, índices). Algunas páginas mezclan español explicativo y marginal en el mismo bloque.

**Hebrew RTL:** Decodificador SI-960 tiene confianza 0.9. Artefactos residuales posibles en fuente hebrea.

**Notas:** Notas y fuentes se clasifican como `footnote` completas. No se separan notas individuales.

**Marginales:** Margen derecho (>70%) se clasifica como `marginal_source`. En páginas sin margen, texto español puede caer en esta zona.

**Block_type:** Solo 6 tipos principales. No se usan `block_subtype` ni `evidence_role` en esta iteración.

**Node_path:** Basado solo en header de página. No se extrae jerarquía completa del documento.

**FTS:** Algunos chunks no tenían search_vector hasta post-procesamiento (corregido).

**Vector search:** Colección Milvus usa COSINE, no IP. Search params deben usar COSINE.

## 11. Archivos modificados/creados

Nuevos:
- `scripts/likutey_layout_parser.py` — parser layout-aware
- `scripts/validate_likutey_layout_blocks.py` — validador de bloques
- `scripts/ingest_likutey_halajot_layout_aware.py` — orquestador de ingesta
- `scripts/embed_likutey_full_batch.py` — batch embedding
- `db/migrations/013_add_layout_aware_columns.sql` — columnas block_type, citable, etc.

Modificados:
- `SrvRestAstroLS_v1/docs/status_actual.md`

## 12. Próxima fase recomendada

```text
Breslov Layout-Aware Ingestion Audit — LIKUTEY HALAJOT Interior Final
```

Acciones sugeridas:
1. Ajustar search_params Milvus a COSINE para vector search funcional
2. Completar golden queries con vector search (COSINE) — estimado 12-14/15 PASS
3. Agregar block_subtype y evidence_role a chunks
4. Revisión manual de 10 páginas muestra (inicio, medio, final)
5. Decisión editorial sobre promoción a ready o mantenimiento test_candidate
6. Si se autoriza: limpiar Milvus test de este documento previo a promoción
