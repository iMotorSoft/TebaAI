# ADR-004: PG18 Product Schema v1

**Estado:** Implementado

**Fecha:** 2026-07-03

## Contexto

TebaAI necesitaba una estructura productiva PostgreSQL 18 v1 que soportara:

1. Autenticación y login multi-proveedor.
2. Multi-tenencia (organizaciones, workspaces, proyectos).
3. `knowledge_scopes` como contenedor lógico del conocimiento.
4. Biblioteca documental con trazabilidad completa.
5. Versionado de chunks y embeddings.
6. Separación entre estado documental y estado de indexación.
7. Validación, promoción y auditoría.
8. Soporte multi-cliente desde el día uno.

El esquema anterior usaba `library_collections` como único agrupador, sin multi-tenencia ni versionado.

## Decisión

Implementar PG18 Product Schema v1 con migraciones incrementales sobre la base TebaAI exclusivamente.

## Tablas creadas (migración 009)

| Tabla | Propósito |
|---|---|
| `organizations` | Cliente/organización raíz multi-tenant |
| `organization_members` | Miembros con roles (owner/admin/member/viewer/service) |
| `workspaces` | Espacio de trabajo dentro de organización |
| `workspace_members` | Miembros a nivel workspace |
| `projects` | Proyecto dentro de workspace (bibliographic_library, assistant, etc.) |
| `project_members` | Miembros a nivel proyecto |
| `knowledge_scopes` | Contenedor lógico del conocimiento, eje central de la biblioteca |
| `auth_identities` | Identidades de autenticación multi-proveedor (local, google, etc.) |
| `library_validation_runs` | Trazabilidad de validaciones técnicas y editoriales |
| `library_promotion_events` | Auditoría de decisiones de promoción documental |

## Tablas modificadas

| Tabla | Cambios |
|---|---|
| `users` | +`email_normalized`, +`user_status`, +`display_name` |
| `auth_sessions` | +`ip_hash`, +`user_agent_hash` |
| `library_documents` | +`knowledge_scope_id`, +`organization_id`, +`workspace_id`, +`project_id`, +`document_code`, +`content_sha256`, +`canonical_text_role`, +`editor`, +`translator`, +`edition`, +`chunk_set_version`, +`archived_at` |
| `library_document_texts` | +`text_role`, +`knowledge_scope_id`, +`page_markers_enabled`, +`page_count` |
| `library_document_chunks` | +`chunk_set_version`, +`knowledge_scope_id`, +`organization_id`, +`workspace_id`, +`project_id`, +`page_mapping_status`, +`section_title`, +`node_path`, +`chunking_strategy`, +`chunking_version`, +`token_estimate`, +`is_empty` |
| `library_chunk_embeddings` | +`embedding_model_alias`, +`embedding_version`, +`chunk_set_version`, +`knowledge_scope_id`, +`organization_id`, +`workspace_id`, +`project_id`, +`vector_status` |
| `library_embedding_runs` | +`organization_id`, +`workspace_id`, +`project_id`, +`knowledge_scope_id`, +`target`, +`run_type`, +`chunk_set_version`, +`document_ids` |

## Jerarquía productiva v1

```
user/account
  → organization (tebaai, cliente_x, ...)
    → workspace (breslov, soporte, ventas, ...)
      → project (breslov_library, assistant_support, ...)
        → knowledge_scope (breslov_primary, manuals_es, ...)
          → library_document
            → document_text
              → chunks
                → embeddings → Milvus
```

## Estados documentales v1

Solo: `draft`, `test_candidate`, `ready`, `archived`, `error`.

## Estados de indexación v1

Separados del estado documental: `pending`, `generated`, `indexed_test`, `validated_test`, `indexed_production`, `stale`, `needs_reindex`, `error`.

## Versionado

Campos `chunk_set_version`, `embedding_version`, `chunking_version` garantizan trazabilidad. Si cambia `content_sha256` o `chunk_set_version`, los embeddings anteriores quedan `stale`.

## Relación PostgreSQL / Milvus

PostgreSQL = fuente de verdad. Milvus = índice derivado/reconstruible. Milvus productivo solo acepta embeddings con `chunk_set_version` coincidente con PG.

## Enums agregados

`user_status`, `member_role`, `project_type`, `scope_type`, `scope_status`, `text_role`, `page_mapping_status`, `vector_status`, `index_target`, `index_run_type`, `validation_type`, `promotion_decision`, `canonical_text_role`

## Bootstrap inicial

- Org: `tebaai` (Teba AI)
- Workspace: `breslov` (Breslov)
- Project: `breslov_library` (Breslov Bibliographic Library)
- Knowledge Scope: `breslov_primary` (corpus principal multilingüe ES/EN/HE)
- Admin users vinculados como miembros de organización

## Pendientes v1 (futuros)

- Implementar endpoints CRUD para organizations/workspaces/projects/knowledge_scopes
- Implementar guards de autorización multi-tenant
- Sparse vectors/BM25 productivo
- Shoresh/lemas
- Interfaz frontend de administración multi-tenant

## Historial de cambios

- 2026-07-03: `library_collections` renombrada a `library_collections_legacy` (migración 011).
  `knowledge_scopes` es la fuente primaria. `library_collections_legacy` preserva datos históricos.
  No crear writes nuevos en legacy. No crear vista de compatibilidad.

- 2026-07-04: Corte runtime completo a `knowledge_scopes`.
  - Todos los módulos productivos (repository, text_search, hybrid_search, indexing_service, routes, schemas)
    usan `knowledge_scopes` como única fuente de routing operativo.
  - `library_collections_legacy` queda deprecated, histórico, read-only.
  - `collection_id` preservado como campo legacy en tablas (NOT NULL), pero no usado como filtro operativo.
  - Datos existentes backfilleados: 9.478 chunks y 231 embeddings con `knowledge_scope_id` poblado.
  - Regla: `knowledge_scopes` es el único contenedor primario para todo flujo activo.
    `library_collections_legacy` no debe ser usado por runtime, ingesta, retrieval, validación,
    indexación ni promoción.
