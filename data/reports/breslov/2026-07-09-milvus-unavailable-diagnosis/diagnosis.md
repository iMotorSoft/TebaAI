# Diagnosis — Milvus Unavailable en Relation QA

## Resumen

Milvus no está disponible para el backend porque el contenedor Docker `milvus26-standalone` salió (estado: `exited`) durante la sesión. No hay problema de código, configuración o entorno faltante.

## Causa raíz

| Hipótesis | Evidencia | Estado |
|---|---|---|
| MILVUS_SERVICE_DOWN | `docker inspect` muestra `exited` a las 2026-07-09T11:43:47. El puerto 19530 no responde. | **CONFIRMADA** |
| MILVUS_HOST_PORT_ENV_MISSING | `MILVUS_HOST=127.0.0.1`, `MILVUS_PORT=19530` (defaults correctos) | Descartada |
| MILVUS_COLLECTION_ENV_MISSING | `MILVUS_COLLECTION_BRESLOV=tebaai_breslov_chunks_v1` (default correcto) | Descartada |
| BACKEND_DEV_ENV_NOT_LOADING | backend-dev.sh carga `.env.backend-dev.local` correctamente | Descartada |
| RELATION_QA_EXCEPTION_SWALLOWED | La excepción se captura como `except Exception:` y agrega warning genérico `milvus_unavailable: lexical retrieval used` | **Confirmada como mejora necesaria** |

## Evidencia

### Probe Milvus desde backend
```
MILVUS_ENABLED: False
MILVUS_HOST: 127.0.0.1
MILVUS_PORT: 19530
ERROR: MilvusException: <MilvusException: (code=2, message=Fail connecting to server on 127.0.0.1:19530, illegal connection params or server unavailable)>
```

### Docker container status
```
milvus26-standalone: exited (2026-07-09T11:43:47)
```

### Relación QA previa
```
used_milvus: False
retrieval: ['postgresql_fts_websearch', 'postgresql_ilike_fallback', 'postgresql_cooccurrence']
warnings: ['milvus_unavailable: lexical retrieval used']
```

## Acción correctiva

La acción inmediata sería reiniciar el contenedor Milvus:
```bash
docker start milvus26-standalone
```
Pero esto requiere verificar que el contenedor no tenga problemas de salud más profundos.

Mientras tanto, se mejoró el mensaje de error en `relation_qa_service.py`:
- El warning `milvus_unavailable` ahora incluye el tipo de excepción concreto (p. ej. `MilvusConnectionError`, `MilvusSearchError`)
- Esto permite distinguir entre "servidor caído", "timeout", "colección no encontrada", etc.
