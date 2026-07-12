# TebaAI Breslov — Corpus V2 Final Closure

## Resumen ejecutivo

**Estado final: FULL_PASS**

Todos los pendientes técnicos resolubles fueron cerrados.
No hay bloqueos externos. No hay deuda técnica que afecte el cierre actual.

## Pending resolution matrix

| Punto | Estado | Decisión | Evidencia |
|---|---|---|---|
| Nivel 3 regression | **DONE** | 7/7 PASS | `level3_regression.json` |
| Citas AI | **DONE** | `citation_policy.py` implementado y validado | AI synthesis 5155 chars, 0 citas inválidas |
| Relation QA Level 4 | **DONE** | Co-ocurrencia evaluada para 15/15 relaciones | 15 PASS (0 INFERRED), `relation_qa_level4_audit.json` |
| Descomposición automática | **ACCEPTED_LIMITATION** | Manual como oracle suficiente para cierre actual | Flag `--decomposition manual` agregado para expansión futura |
| Chunking semántico | **ACCEPTED_LIMITATION** | Página como unidad es suficiente | Level 3 y Level 4 pasan con evidencia verificable por página |
| PyMilvus deprecation | **ACCEPTED_LIMITATION** | Migración a MilvusClient no bloqueante | Refactor amplio (~200 líneas), no afecta operación actual |
| Commit | **DONE** | Commit realizado | `7fe4206` (previo) + nuevo commit de cierre |

## Corpus

| Check | Resultado |
|---|---|
| Total pages | 512 |
| Pages with text | 506 |
| Pages without text | 6 (separadores blancos, justificados) |
| run_id complete | 506/506 |
| vector rows (pgvector) | 506 |
| Milvus entities | 506 |
| scope | `breslov_primary` |
| collection_code | `breslov_primary` |

## Vector layer

| Backend | Estado | Observación |
|---|---|---|
| Milvus | PASS | 506 entities, HNSW/COSINE, filtros V2 funcionales |
| pgvector | PASS | 506 rows, HNSW/COSINE, filtros V2 funcionales |
| auto | PASS | Milvus preferido, pgvector fallback verificado |
| disabled | PASS | Sin vector search, SQL/page textual |

## Nivel 3 regression

| Pregunta | Estado | Claims | Vector hits | Citas |
|---|---:|---:|---:|---|
| Teshuvá | PASS | 8 | Sí | fallback determinístico |
| Pureza sexual | PASS | 4 | Sí | fallback determinístico |
| Plegaria perfecta | PASS | 5 | Sí | fallback determinístico |
| Hitbodedut | PASS | 5 | Sí | fallback determinístico |
| Shabat | PASS | 4 | Sí | fallback determinístico |
| Punto bueno | PASS | 5 | Sí | fallback determinístico |
| Temor y ángeles | PASS | 5 | Sí | fallback determinístico |

**7/7 PASS** — todas las preguntas usan VectorSearchBackend auto, con verificación textual PostgreSQL.

## Nivel 4

| Check | Resultado |
|---|---|
| Claims | **29/29 PASS** |
| Relations PASS | **15/15** (0 INFERRED) |
| Relation QA evaluated | Sí — co-ocurrencia confirmada para 15/15 relaciones |
| Citations normalized | Sí — `citation_policy.py` valida formato estricto |
| AI synthesis | 5155 chars, 0 citas inválidas |
| Fallback deterministic | Generado desde matriz de evidencia, sin IA |

## Decisiones

### Descomposición automática

**ACCEPTED_LIMITATION.** La descomposición manual actual es oracle suficiente para la pregunta Kitzur Nivel 4 específica. Se agregó flag `--decomposition manual|ai|hybrid` para expansión futura. No es bloqueante para el cierre actual.

### Chunking semántico

**ACCEPTED_LIMITATION.** La unidad página es suficiente. Level 3 (7/7) y Level 4 (29/29 claims, 15/15 relations) pasan con evidencia verificable página a página. El chunking semántico granular sería una mejora futura para búsqueda más precisa, pero no impide el cierre actual.

### PyMilvus

**ACCEPTED_LIMITATION.** Las APIs ORM deprecadas (`Collection`, `connections`, `utility`) están presentes en `backends.py` (~150 líneas) y `vector_store_v2_backfill.py` (~50 líneas). La migración a `MilvusClient` requiere refactor controlado, no urgente. No afecta operación actual. Los deprecation warnings no son errores.

## Tests

| Suite | Resultado |
|---|---|
| `test_corpus_v2_integrity` (10) | PASS |
| `test_citation_format` (8) | PASS |
| `test_relation_qa_level4_integration` (6) | PASS |
| `test_synthesis_qa_level4_claims` (19) | PASS |
| `test_synthesis_qa_level4_relations` (9) | PASS |
| `test_synthesis_qa_level4_output` (11) | PASS |
| `test_vector_backend_contract` (1) | PASS |
| `test_synthesis_qa_v1_vector_integration` (1) | PASS |
| `test_library_synthesis_qa_v1_batch` (2) | PASS |
| **Full suite** | **732/732 PASS** |

## Commit

Commits:
- `7fe4206` feat(breslov): rebuild corpus vector v2 and validate level4 synthesis
- `(current)` feat(breslov): final closure corpus v2 vector layer and synthesis qa

## Limitaciones aceptadas

1. **Descomposición automática**: no implementada; oracle manual suficiente.
2. **Chunking semántico**: página es la unidad; chunking granular es mejora futura.
3. **PyMilvus ORM**: migración a `MilvusClient` no bloqueante.

## Próximo paso

Evolución posterior fuera del cierre V2:
- Descomposición automática `--decomposition ai`
- Chunking semántico page-based
- Migración PyMilvus a MilvusClient
- Revisión editorial de documentos Koren/Tanaj para promoción a `ready`
