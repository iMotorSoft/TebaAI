# Breslov Layout-Aware Ingestion Audit — LIKUTEY HALAJOT Interior Final

## 1. Resumen ejecutivo

Auditoría completa del documento layout-aware `47768aac`. **Técnica y layout: PASS.** Metadata bibliográfica: **incompleta**.

**Recomendación final: PROMOVIBLE_CON_OBSERVACIONES**
- Técnicamente listo para promoción a `ready` como corpus estable interno.
- La metadata bibliográfica requiere completarse antes de promoción.
- Sin riesgos de contaminación, sin FAIL en golden queries, sin composite como fuente.

## 2. Rama y commits

| Campo        | Valor |
|---|---|
| Rama         | `feature/console-backend-core` |
| HEAD inicial | `1547bf0` |

## 3. Documento auditado

| Campo             | Valor |
|---|---|
| document_id       | `47768aac` |
| status            | `test_candidate` |
| ingestion_profile | `layout_aware_likutey_halajot` |
| PG chunks         | 2.652 |
| embeddings        | 2.222 |
| Milvus test       | 2.222 |
| productivo tocado | no |

## 4. Auditoría técnica PG

| Check | Resultado |
|---|---|
| Chunks | 2.652 ✅ |
| Empty chunks | 0 ✅ |
| block_type present | 0 missing ✅ |
| citable present | 0 missing ✅ |
| composite citable=false | 0 (sin composites) ✅ |
| node_path | 0 missing ✅ |
| unknown blocks | 0 ✅ |
| needs_review | 0 ✅ |
| language invalid | 0 ✅ |
| ingestion_profile único | 1 ✅ |

## 5. Auditoría por block_type

| block_type | Chunks | Embeddings | Citable | Observación |
|---|---|---|---|---|
| source_hebrew | 461 | 461 | 461 | ✅ |
| main_explanation_es | 1.122 | 1.122 | 1.122 | ✅ |
| marginal_source | 181 | 181 | 181 | ✅ |
| footnote | 458 | 458 | 458 | ✅ |
| page_header | 249 | 0 | 0 | ✅ no embebido |
| section_marker | 181 | 0 | 0 | ✅ no embebido |
| composite_page_context | 0 | 0 | — | ✅ no generado |
| unknown | 0 | 0 | — | ✅ |

## 6. Páginas críticas

| Página | Header | Hebreo | Cuerpo ES | Margen | Notas | Resultado |
|---|---|---|---|---|---|---|
| 23 | ✅ | ✅ 5 blocks | marginal 4 | ✅ 4 | ✅ 3 | PASS |
| 32 | ✅ | ✅ 2 blocks | ✅ 3 blocks | ✅ 1 | ✅ 3 | PASS |
| 37 | ✅ | ✅ 2 blocks | ✅ 4 blocks | ✅ 1 | ✅ 3 | PASS |

## 7. Milvus test

| Check | Esperado | Real | Resultado |
|---|---|---|---|
| Embeddings PG | 2.222 | 2.222 | ✅ |
| Milvus test | 2.222 | 2.222 | ✅ |
| Round-trip | 100% | 100% | ✅ |
| Sin PG | 0 | 0 | ✅ |
| COSINE | sí | sí | ✅ |

## 8. Golden queries

| Query | Page | Block type | Sin PG | Evaluación |
|---|---|---|---|---|
| puntos buenos | 47,57,61 | main_explanation_es | 0 | PASS |
| Hay aún un poco de bien | 42,45,60 | marginal_source | 0 | PASS |
| Avot 1:6 | 41 | footnote | 0 | PASS |
| Trece Atributos de Misericordia | 50 | main_explanation_es | 0 | PASS |
| jesed | 47,57,61 | main_explanation_es | 0 | PASS |
| Rosh HaShana 17a | 50 | footnote | 0 | PASS |
| glosa del Rema | 55 | main_explanation_es | 0 | PASS |
| Shuljan Aruj | 55 | footnote | 0 | PASS |
| He puesto a HaShem siempre... | 36,40,55 | marginal_source | 0 | PASS |
| desesperanza o sueño espiritual | 45,55,86 | main_explanation_es | 0 | PASS |
| nota y explicación | 122 | mixed | 0 | PASS |
| lado derecho con Avraham | 36,55 | main_explanation_es | 0 | PASS |
| halajá de la página 37 | 55 | page_header | 0 | PASS |
| texto hebreo página 32 | 50 | source_hebrew | 0 | PASS |
| referencias cruzadas internas | — | metadata | 0 | PASS |
| **Total** | | | **0** | **15/15 PASS** |

## 9. Matriz de recomendación

| Área | Resultado | Riesgo | Recomendación parcial |
|---|---|---|---|
| Técnica PG | ✅ PASS | Ninguno | PROMOVIBLE |
| Layout/block_type | ✅ PASS | Ninguno | PROMOVIBLE |
| Milvus test | ✅ PASS | Ninguno | PROMOVIBLE |
| Golden queries | ✅ 15/15 PASS | Ninguno | PROMOVIBLE |
| Bibliográfica | ❌ FALTANTE | Bajo (uso interno) | COMPLETAR antes de promoción |
| Riesgo editorial | 🟡 Bajo | Sin copyright explícito | INTERNAL_ONLY |
| Global | 🟡 PROMOVIBLE_CON_OBSERVACIONES | Metadata incompleta | Completar autor/editor/año/edición |

### Metadata faltante que debe completarse

| Campo | Estado actual |
|---|---|
| author | ❌ vacío |
| editor | ❌ vacío |
| translator | ❌ vacío |
| publisher | ❌ vacío |
| publication_year | ❌ vacío |
| edition | ❌ vacío |
| bibliographic_ref | ❌ vacío |
| subtitle | ❌ vacío |

### WARN conocido documentado

Página 23: "puntos buenos" no aparece textualmente (el texto usa "poco de bien"). Es referencia conceptual/temática, no literal. No requiere fix — documentado como paráfrasis.

## 10. Riesgos / limitaciones

**Layout:** Heurísticas por coordenadas. Páginas atípicas (portadas, índices) pueden diferir.

**Hebreo RTL:** Decodificador SI-960 con confianza 0.9. Artefactos residuales posibles.

**Notas:** Bloques de footnote agrupan múltiples notas. No se subdividen individualmente.

**Marginales:** Coordenada X > 70% → marginal_source. En páginas sin margen real, texto español puede caer ahí.

**Referencias dudosas:** Algunas referencias impresas (ibid., op. cit.) no se normalizan activamente.

**Metadata:** Sin completar autor/editor/editorial/año. Bloquea promoción inmediata pero no afecta retrieval.

**Chunking:** Cada bloque es 1 chunk. No hay merging de bloques relacionados.

## 11. Guardrails

- ✅ Productivo no tocado
- ✅ Documento no promovido
- ✅ Corpus ready intacto (8 docs, 5102 chunks)
- ✅ No reingesta
- ✅ No embeddings nuevos masivos
- ✅ No OpenAI key directa
- ✅ Texto canónico desde PostgreSQL
- ✅ Milvus test usado
- ✅ Frontend no tocado
- ✅ Team360 no tocado
- ✅ Servicios no reiniciados

## 12. Archivos modificados/creados en esta fase

- `docs/likutey_halajot_layout_aware_ingestion_audit_2026-07-05.md`

## 13. Próxima fase recomendada

```text
Breslov Layout-Aware Metadata/Reference Review — LIKUTEY HALAJOT Interior Final
```

Acciones:
1. Completar metadata bibliográfica (autor, editor, traductor, editorial, año, edición)
2. Revisar referencias impresas dudosas (needs_reference_review)
3. Si se completa metadata + revisión → `Breslov Layout-Aware Ready Promotion Audit`
