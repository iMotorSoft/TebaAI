# Diagnosis — Milvus Unavailable en Relation QA

**Causa raíz**: El contenedor Docker `milvus26-standalone` salió (estado `exited`). No es un problema de código, configuración ni entorno.

**Acción correctiva**: 
- El warning ahora incluye el tipo de excepción (p.ej. `MilvusConnectionError`)
- Para restaurar Milvus: `docker start milvus26-standalone`

**Archivos modificados**:
- `relation_qa_service.py`: El warning `milvus_unavailable` ahora incluye `exception_type` (p.ej. `MilvusConnectionError`)
