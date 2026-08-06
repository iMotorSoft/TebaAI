# Plan de rollback conceptual — Likutey Halajot (Interior Final)

Válido para el gate futuro `TEBAAI_LIKUTEY_HALAJOT_CONTROLLED_PROMOTION_V1`.
Ningún rollback se ejecuta en esta fase.

## Reversión de status

```sql
-- Dentro de transacción, solo si el documento es el esperado
UPDATE library_documents
SET status = 'test_candidate', updated_at = now()
WHERE id = '132a791a-d12b-45bc-9b34-dd143605de12'
  AND status = 'ready';
```

- Confirmar `rowcount = 1`; si no, abortar transacción.
- No se modifican metadata, chunks, embeddings ni vectores: el rollback es
  puramente de status.

## Metadata a restaurar

- `bibliographic_metadata.canonical_identity_v1`: NO se modifica en la
  promoción → nada que restaurar (la identidad es independiente del status).
- `library_documents.status`: único campo cambiante.

## Cachés e índices

- Invalidar cachés de búsqueda/UI del frontend que cacheen resultados por
  status (si existen).
- Índices PostgreSQL FTS/trigram no requieren rebuild (status no indexado).
- Milvus no indexa status: sin cambios de índice.

## Logs

- Conservar: job de transición (si se usa Content Manager), evidencia de
  auditoría, reportes del gate de promoción.

## Usuarios

- Notificar a: administradores del sistema (ningún usuario externo esperado).

## Verificación post-rollback

- Interior Final vuelve a `test_candidate`.
- Los 8 documentos `ready` previos permanecen intactos.
- PG↔Milvus del documento sin cambios (268/268).
- Batería de retrieval sigue pasando (la evidencia exacta del test_candidate
  ya prioriza según ADR-016).
