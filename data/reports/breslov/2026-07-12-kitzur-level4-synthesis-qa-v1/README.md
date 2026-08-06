# Kitzur Level 4 — Synthesis QA V1

## Resumen ejecutivo

**Estado: PASS**

| Diagnóstico | Valor |
|---|---|
| LEVEL4_PASS | ✅ |
| CLAIM_COVERAGE_GAP | 0/29 |
| RELATION_COVERAGE_GAP | 6/15 inferidas (no fallo) |
| SYNTHESIS_GAP | Ninguno — AI y fallback producidos |
| EVIDENCE_VALIDATION_GAP | Ninguno — todas las páginas verificadas vía PostgreSQL |
| VECTOR_RETRIEVAL_GAP | VectorSearchBackend auto → Milvus; hits bajos (0) por filtro run_id |
| RELATION_QA_GAP | Relation QA no invocado en este pipeline |
| INCONCLUSIVE | No |

## Infraestructura

| Componente | Estado | Observación |
|---|---|---|
| Backend | PASS | Litestar disponible |
| PostgreSQL | PASS | 512 páginas Kitzur V2 verificadas |
| VectorSearchBackend auto | PASS | Resuelve a Milvus |
| Milvus | PASS | `tebaai_breslov_chunks_v2_dev` cargado |
| pgvector | PASS | `library_vector_embeddings_v2_dev` (506 registros) |
| LiteLLM | PASS | GPT-5.4-nano para síntesis |

## Pregunta

> Explica la interconexión entre la humildad, el conocimiento (daat), la verdad, la alegría,
> la pureza sexual y la unión con los Tzadikim como vía principal para alcanzar el propósito
> final de la vida según el Kitzur Likutey Moharán.

## Claim coverage

| Claim ID | Claim | Estado | Mejor fuente | Página | Método | Tipo evidencia |
|---|---|---|---:|---|---|---|
| A1 | El propósito final de la vida es servir a Dios. | PASS | page_direct | 471 | SQL/page | literal |
| A2 | El servicio a Dios conduce a merecer conocerlo. | PASS | page_direct | 471 | SQL/page | literal |
| A3 | El conocimiento de Dios es el deleite eterno. | PASS | page_direct | 103 | SQL/page | literal |
| B1 | La humildad anula orgullo y materialidad. | PASS | page_direct | 22 | SQL/page | literal |
| B2 | Aceptar insultos en silencio. | PASS | page_direct | 29 | SQL/page | thematic |
| B3 | Volverse "nada" permite recibir luz de Dios. | PASS | page_direct | 363 | SQL/page | literal |
| C1 | La verdad es luz de Dios. | PASS | page_direct | 236 | SQL/page | thematic |
| C2 | La verdad es fundamento de la fe. | PASS | page_direct | 236 | SQL/page | literal |
| C3 | La verdad en plegaria/acciones permite elevación. | PASS | page_direct | 41 | SQL/page | literal |
| D1 | La alegría sostiene verdad/conocimiento. | PASS | page_direct | 462 | SQL/page | thematic |
| D2 | La alegría es esencia de Shabat. | PASS | page_direct | 462 | SQL/page | literal |
| D3 | La alegría permite bailar. | PASS | page_direct | 209 | SQL/page | literal |
| D4 | La alegría mitiga juicios severos. | PASS | page_direct | 209 | SQL/page | literal |
| E1 | Daat es percepción de la Divinidad. | PASS | page_direct | 148 | SQL/page | literal |
| E2 | Daat es meta espiritual. | PASS | page_direct | 149 | SQL/page | literal |
| E3 | Daat se vincula con rectificación de la mente. | PASS | page_direct | 148 | SQL/page | literal |
| F1 | Pureza sexual rectifica la mente. | PASS | page_direct | 145 | SQL/page | literal |
| F2 | Pureza sexual permite Lenguaje Sagrado. | PASS | page_direct | 82 | SQL/page | literal |
| F3 | Pureza sexual se relaciona con daat. | PASS | page_direct | 145 | SQL/page | paraphrase |
| F4 | Pureza sexual facilita sustento espiritual. | PASS | page_direct | 82 | SQL/page | literal |
| G1 | El Tzadik ilumina. | PASS | page_direct | 53 | SQL/page | thematic |
| G2 | El Tzadik despierta el corazón. | PASS | page_direct | 53 | SQL/page | thematic |
| G3 | El Tzadik enseña la verdad. | PASS | page_direct | 53 | SQL/page | literal |
| G4 | El Tzadik guía en arrepentimiento. | PASS | page_direct | 177 | SQL/page | thematic |
| G5 | El Tzadik revela la Torá. | PASS | page_direct | 53 | SQL/page | literal |
| G6 | El Tzadik acerca a los lejanos. | PASS | page_direct | 70 | SQL/page | thematic |
| G7 | El Tzadik revela la voluntad de Dios. | PASS | page_direct | 70 | SQL/page | literal |
| H1 | Humildad ayuda a reconocer verdadero Tzadik. | PASS | page_direct | 312 | SQL/page | literal |
| H2 | Verdad ayuda a reconocer verdadero Tzadik. | PASS | page_direct | 312 | SQL/page | literal |

## Relation coverage

| Relation ID | From | To | Estado | Tipo relación | Evidencia | Páginas | Confianza |
|---|---|---|---|---|---|---|---|
| R1 | humildad | verdad | INFERRED | thematic | Co-ocurrencia temática | — | 0.3 |
| R2 | humildad (nada) | recibir luz divina | INFERRED | thematic | Relación conceptual | — | 0.3 |
| R3 | verdad | fe | PASS | literal | Misma página | 236 | 0.9 |
| R4 | verdad | plegaria elevada | PASS | literal | Evidencia directa | 41 | 0.9 |
| R5 | alegría | verdad/conocimiento | INFERRED | thematic | Relación conceptual | — | 0.3 |
| R6 | alegría | mitigación de juicios | PASS | literal | Evidencia directa | 209 | 0.9 |
| R7 | pureza sexual | rectificación de mente | INFERRED | thematic | Co-ocurrencia temática | — | 0.3 |
| R8 | pureza sexual | daat | INFERRED | thematic | Relación conceptual | — | 0.3 |
| R9 | Tzadik | verdad | INFERRED | thematic | Conexión temática | — | 0.3 |
| R10 | Tzadik | arrepentimiento | PASS | literal | Evidencia directa | 177 | 0.9 |
| R11 | Tzadik | Torá | PASS | literal | Evidencia directa | 53 | 0.9 |
| R12 | Tzadik | acercar lejanos | PASS | thematic | Evidencia directa | 70 | 0.9 |
| R13 | humildad + verdad | reconocer verdadero Tzadik | PASS | literal | Misma página | 312 | 0.9 |
| R14 | daat | propósito final | PASS | literal | Misma página | 471 | 0.9 |
| R15 | red completa | conocimiento de Dios | PASS | thematic | Evidencia temática | 103 | 0.9 |

## Matriz de evidencia

Ver `claim_evidence_matrix.json` para la matriz completa con snippet, página, método y tipo
de evidencia.

## Síntesis final (AI)

Ver `synthesis_output.md`. Generada por LiteLLM (`openai_gpt-5.4-nano`).

## Fallback determinístico

Ver `fallback_output.md`. Generada solo desde matriz de evidencia, sin IA.

## Auditoría

| Método | Hits | Evidencia aceptada | Evidencia descartada | Nota |
|---|---:|---:|---:|---|
| SQL/page | 46 | 46 | 0 | Búsqueda directa por página esperada |
| Book QA | 0 | 0 | 0 | No invocado con filtro de claim atómico |
| FTS | 174 | 0 | 174 | Hits FTS dispersos, no pasaron filtro de página |
| Vector auto (Milvus) | 0 | 0 | 0 | V2 dev con filtro run_id — sin match |
| Relation QA | 0 | 0 | 0 | No invocado |

## Diagnóstico técnico

**Fortalezas:**
1. SQL/page direct encuentra evidencia literal con alta precisión (46 hits en páginas esperadas)
2. 29/29 claims (100%) confirmados con evidencia textual verificada en PostgreSQL
3. 9/15 relaciones con evidencia directa; 6 inferidas temáticamente (marcadas como INFERRED)
4. Páginas esperadas confirmadas: 471, 103, 22, 33, 363, 236, 237, 41, 462, 209, 148, 149, 82, 145, 53, 54, 70, 71, 177, 178, 312
5. AI synthesis produce 7079 chars con estructura académica
6. Fallback determinístico garantiza respuesta sin IA

**Debilidades:**
1. VectorSearchBackend auto → Milvus no devuelve hits con filtro `run_id` en V2 dev — los 506 vectores en `library_vector_embeddings_v2_dev` no tienen `run_id` en el mismo formato esperado
2. 6 relaciones inferidas (R1, R2, R5, R7, R8, R9) no tienen co-ocurrencia literal en misma página
3. La AI synthesis generó citas no estándar (uso de `TEM`, `cabado`) — el prompt debe refinarse
4. Las claims no se descompusieron automáticamente (descomposición manual)

## Pendientes

1. Revisar VectorSearchBackend V2 dev: los vectores pueden no tener `run_id` como filtro; considerar remover filtro o usar `knowledge_scope_code` solamente
2. Refinar el prompt de AI synthesis para forzar formato de citas estricto
3. Implementar descomposición automática de preguntas (en lugar de manual) para futuras Nivel 4
4. Integrar Relation QA en el pipeline Level 4 para relaciones más profundas
