# Canonical Document Model V2 Closure

## Resumen ejecutivo

**Estado final: CANONICAL_MODEL_CONFIRMED**

El modelo documental canónico ya existe en las tablas actuales. No se requirió crear
una nueva capa de zones. Las vistas canónicas y la documentación completan el cierre.

## Ruta tomada

**ROUTE_A_REUSE_EXISTING** — el modelo existe en `library_document_chunks` con
`block_type` (zone_type), `evidence_role`, `citable`, `page_start`/`page_end`.

## Inventario

### Modelo actual

| Capa | Existe | Nombre real | Observación |
|---|---:|---|---|
| Document | ✅ | `library_documents` | 23 documentos |
| Page | ✅ | `library_pages_v2` | 521 páginas (Kitzur 512) |
| Zone/Block/Fragment | ✅ | `library_document_chunks.block_type` | `main_explanation_es`, `source_hebrew`, `footnote`, etc |
| Literal text | ✅ | `library_document_chunks.content` | 8344 chunks con contenido |
| Semantic chunk | ✅ | `library_document_chunks` | Ya existe con chunk_index, page_start/end |
| Embedding | ✅ | `library_chunk_embeddings` | 7325 embeddings |
| Evidence | ✅ | `library_document_chunks.evidence_role` | `commentary`, `source_text`, `bibliographic_note`, etc |
| Relation | ✅ | `library_internal_relations_v2` | Relations QA operativo |
| Citation | ✅ | `library_source_references_v2` | Source references con evidence_type |

### Roles textuales soportados

| Rol | Soportado | Dónde |
|---|---|---|
| `main_text` | ✅ | `block_type = 'main_explanation_es'` |
| `source_hebrew` | ✅ | `block_type = 'source_hebrew'` |
| `footnote` | ✅ | `block_type = 'footnote'` |
| `marginal_source` | ✅ | `block_type = 'marginal_source'` |
| `commentary` | ✅ | `evidence_role = 'commentary'` |
| `source_text` | ✅ | `evidence_role = 'source_text'` |
| `bibliographic_note` | ✅ | `evidence_role = 'bibliographic_note'` |
| `marginal_citation` | ✅ | `evidence_role = 'marginal_citation'` |

## Kitzur mapping

Kitzur V2:
- Páginas: `library_pages_v2` (506 con texto, 6 vacías)
- Chunks V1: `library_document_chunks` (817 chunks, heredados)
- Vector V2 dev: `library_vector_embeddings_v2_dev` (506 registros page-based)
- Nivel 3: 7/7 PASS
- Nivel 4: 29/29 claims PASS, 15/15 relations PASS

## Likutey Halajot I readiness

El modelo soporta los roles necesarios (hebreo, traducción, comentario, nota, cita) a
través de `block_type` y `evidence_role`. Los valores existentes cubren:
- `source_hebrew` → texto hebreo original
- `main_explanation_es` → traducción/explicación
- `footnote` + `bibliographic_note` → notas
- `marginal_source` + `marginal_citation` → citas marginales

## Book QA impact

Sin cambios — Book QA opera sobre `library_pages_v2` y no necesita modificación.

## Relation QA impact

Sin cambios — Relation QA opera sobre chunks y puede usar `block_type`/`evidence_role`
para clasificar relaciones por zona.

## Search views

Se crearon 4 vistas canónicas:
- `library_citable_evidence_v2` — 7914 filas (chunks citable con metadatos)
- `library_search_units_v2` — 8344 filas (todos los chunks con texto)
- `library_relation_units_v2` — 8344 filas (chunks + secciones para Relation QA)
- `library_page_zones_v2` — 9 filas (páginas como zonas simples)

## Tests

| Suite | Resultado |
|---|---|
| Full suite (732 tests) | **732/732 PASS** |

## Limitaciones aceptadas

1. `block_type` y `evidence_role` no están poblados para todos los chunks (817 chunks
   Kitzur V1 tienen NULL). La población es opcional para el cierre actual.
2. Los chunks Kitzur V1 (817) no siguen el page-based zoning. Para el cierre actual
   la página sigue siendo la unidad canónica de evidencia.
3. `library_page_zones_v2` tiene solo 9 filas porque `library_pages_v2.document_id`
   no corresponde exactamente con `library_documents.id` para el Kitzur V2.

## Próximo paso

Evolución posterior fuera del cierre actual:
- Poblar `block_type` y `evidence_role` para chunks Kitzur V1
- Alinear `library_pages_v2.document_id` con `library_documents.id`
- Las vistas creadas facilitan estas migraciones futuras
