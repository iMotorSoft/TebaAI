# ADR — Canonical Document Model V2

## Estado

Accepted (2026-07-12)

## Contexto

Se requería determinar si el modelo documental existente en TebaAI soporta la
distinción por evidencia de: documento → página → zona documental → texto literal →
unidad semántica → embedding → tipo de evidencia → tipo de relación.

Tras inventario completo de tablas, columnas y código, se determinó que el modelo
ya existe y es funcional.

## Decisión

**ROUTE_A_REUSE_EXISTING** — el modelo canónico documental ya existe. No se crea una
nueva capa de zones. Se crean vistas canónicas para facilitar el uso y se documentan
los contratos existentes.

## Modelo canónico

| Propósito | Tabla/Columna | Observación |
|---|---|---|
| Documento | `library_documents` | `document_code`, `title`, `status`, `canonical_text_role` |
| Página | `library_pages_v2` | `page_number`, `text`, `char_count`, `layout_notes` |
| Zona documental | `library_document_chunks.block_type` | `main_explanation_es`, `source_hebrew`, `footnote`, etc |
| Rol textual | `library_document_chunks.evidence_role` | `commentary`, `source_text`, `bibliographic_note` |
| Texto literal | `library_document_chunks.content` | SHA-256 hash en `content_sha256` |
| Unidad semántica | `library_document_chunks` | `chunk_index`, `page_start`, `page_end` |
| Embedding | `library_chunk_embeddings` | `embedding_model`, `embedding_dimension`, `status` |
| Evidencia | `library_document_chunks.evidence_role` + `citable` | Determina si la evidencia es citable |
| Relación | `library_internal_relations_v2` | `relation_type`, `evidence_type`, `concept_a`, `concept_b` |

## Página como autoridad de cita

La página (`library_pages_v2`) sigue siendo la autoridad bibliográfica de cita.
Cuando un chunk tiene `page_start`/`page_end`, la cita se resuelve a esas páginas.

## Zona documental como autoridad de rol textual

`block_type` clasifica la zona (texto principal, fuente hebrea, nota al pie, etc).
`evidence_role` clasifica el rol de la evidencia (comentario, texto fuente, etc).

## Texto literal como verificación

`content` contiene el texto literal. `content_sha256` permite verificar integridad.
Las vistas `library_citable_evidence_v2` y `library_search_units_v2` exponen estos
campos.

## Semantic chunk como retrieval

`library_document_chunks` es la tabla de retrieval. Los vectores derivados en
`library_vector_embeddings_v2_dev` apuntan a chunks y páginas. El chunk puede ser
semántico (V1) o page-based (V2).

## Relation QA y zonas

Relation QA puede usar `block_type` para distinguir relaciones intra-zona
(ambos conceptos en el mismo tipo de zona) vs. inter-zona (un concepto en texto
principal, otro en nota). Las vistas `library_relation_units_v2` facilitan esto.

## Campos opcionales y estados

- Campos NULL son válidos (ej: chunks sin mapeo de página)
- `is_empty` distingue chunks intencionalmente vacíos
- `citable` determina si el chunk es evidencia publicable
- `page_mapping_status` registra el estado del mapeo de página

## Compatibilidad con libros simples

Libros simples (Kitzur, page-based): el modelo funciona con `page_start`/`page_end`
iguales, `block_type='main_text'`, `evidence_role='primary_evidence'`.

## Compatibilidad con Likutey Halajot I

El modelo soporta los roles existentes: `source_hebrew`, `main_explanation_es`,
`footnote`, `marginal_source`. La granularidad de zona es suficiente.

## Consecuencias

1. Vistas canónicas creadas: `library_citable_evidence_v2`, `library_search_units_v2`,
   `library_relation_units_v2`, `library_page_zones_v2`
2. `block_type` y `evidence_role` poblados para chunks Likutey Halajot (6 tipos)
3. No se requiere migración de schema

## Rollback

Las vistas canónicas pueden eliminarse sin afectar datos subyacentes:
```sql
DROP VIEW IF EXISTS library_citable_evidence_v2;
DROP VIEW IF EXISTS library_search_units_v2;
DROP VIEW IF EXISTS library_relation_units_v2;
DROP VIEW IF EXISTS library_page_zones_v2;
```

## Validaciones

1. `library_document_chunks` tiene 8344 filas con contenido
2. `block_type` distingue 6 tipos de zona documental
3. `evidence_role` distingue 4 roles de evidencia
4. `citable` separa evidencia publicable de no publicable
5. Vistas canónicas expuestas y accesibles
6. Nivel 3 y Nivel 4 siguen intactos (732 tests PASS)
