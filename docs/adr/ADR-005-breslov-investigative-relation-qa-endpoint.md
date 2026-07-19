# ADR-005: Breslov Investigative Relation QA Backend Endpoint

Estado: accepted and implemented.

Fecha: 2026-07-08.

## Contexto

El laboratorio editorial Breslov validó retrieval relacional, clasificación de evidencia y síntesis acotada, pero no existía un contrato HTTP autenticado y auditable para investigadores.

`POST /library/search` sigue siendo retrieval bibliográfico sin generación. La nueva capacidad necesita interpretación opcional sin convertir inferencias, notas o contexto compuesto en citas literales.

## Decisión

TebaAI incorpora `POST /library/relation-qa` como endpoint especializado de investigación editorial Breslov, separado del search general y protegido por el mismo guard de autenticación.

El endpoint aplica este orden:

1. autorización por `knowledge_scope_code` y resolución de `knowledge_scope_id`;
2. expansión determinística de conceptos;
3. PostgreSQL FTS, fallback ILIKE, patrones relacionales y coocurrencia;
4. Milvus dense search read-only con embeddings de query vía LiteLLM;
5. rehidratación y filtrado de todos los candidatos desde PostgreSQL;
6. clasificación editorial, ranking y source map deduplicado por `chunk_id`;
7. síntesis opcional con `openai_gpt-5.4-nano` vía LiteLLM;
8. validación estructurada y fallback determinístico ante salida IA inválida.

## Autoridad y citas

PostgreSQL conserva la autoridad exclusiva del texto servido como evidencia.

Milvus aporta únicamente `chunk_id` y score. `content_preview` nunca se devuelve como fuente. `composite_page_context` puede aportar contexto, pero nunca se marca como cita final.

La respuesta separa evidencia literal, referencias, roles editoriales, coocurrencia, tema, derash, remez, ambigüedad e inferencia IA. Si no hay relación literal, `literal_relation_found` permanece en `false` aunque el modelo proponga una lectura.

### Trazabilidad claim-evidencia

Las superficies conversacionales derivadas conservan asociaciones estructuradas y no extraen fuentes desde Markdown.

- cada claim incluye `claim_id`, `text`, `strength`, `evidence_ids` y `primary_evidence_id`;
- `primary_evidence_id` pertenece siempre a `evidence_ids` y todos los IDs existen en `hits`;
- `primary_evidence_ids` define el orden de selección inicial para clientes;
- `literal_strength` describe la fidelidad literal del registro, mientras `evidence_strength` describe su fuerza para la relación consultada;
- `relation_relevance` distingue relación directa, coocurrencia contextual, coincidencia de un solo término y ruido literal;
- el límite por obra se aplica después de deduplicar y ordenar el resultado final, no por cada expansión léxica;
- los IDs de evidencia son hashes estables del contenido y la obra, no posiciones ni hashes de proceso.

Una coincidencia literal de un solo concepto no puede convertirse en evidencia primaria de una consulta relacional. El frontend sólo consume estas asociaciones validadas; no parsea IDs desde la narrativa.

## Modelo y gateway

La generación queda limitada a una síntesis editorial posterior al retrieval.

| Capacidad | Contrato |
|---|---|
| Embedding de query | `openai_text_embedding_3_small`, dimensión 1536 |
| Síntesis editorial | `openai_gpt-5.4-nano` |
| Gateway | LiteLLM exclusivo |
| Salida del modelo | JSON validado con source IDs permitidos |
| Fallback | Respuesta determinística con warning explícito |

## Autorización y lifecycle

El cliente no puede imponer un scope sin autorización server-side.

La ruta resuelve la cadena activa usuario, organización, workspace, proyecto y scope. `include_test_candidates=true` solo habilita lectura investigativa y preserva `document_status`; nunca promueve ni indexa el documento.

## Operaciones prohibidas

El endpoint carece de paths de mutación de corpus o infraestructura.

- no ingiere ni promueve documentos;
- no escribe PostgreSQL ni Milvus;
- no crea colecciones Milvus;
- no recalcula embeddings de corpus;
- no usa OpenAI directo;
- no usa `collection_id` ni `library_collections_legacy` para routing;
- no incorpora lógica al frontend.

## Alternativas consideradas

Las alternativas no satisfacían al mismo tiempo trazabilidad y límites editoriales.

| Alternativa | Decisión |
|---|---|
| Extender `/library/search` con generación | Rechazada: mezcla retrieval general con interpretación |
| Exponer directamente el script de laboratorio | Rechazada: no ofrece contrato, auth ni lifecycle web |
| Respuesta solo Markdown | Rechazada: no es auditable ni estable para consumidores |
| Usar solo IA para clasificar | Rechazada: literalidad y roles deben validarse determinísticamente |
| Nuevo endpoint estructurado | Aceptada |

## Consecuencias

La API ofrece una superficie backend-only auditable, a cambio de mantener un clasificador heurístico y un contrato editorial versionable.

Los consumidores deben tratar `warnings`, `evidence_type`, `document_status`, `citable` e `is_final_citation` como parte del contrato. El hardening futuro debe agregar rate limiting, caché, observabilidad y regresiones editoriales continuas.

## Extensión conversacional multilingüe de `/library/investigative-qa/v1`

La superficie de investigación admite comprensión ES/EN/HE y consultas mixtas mediante un contrato híbrido:

1. preprocesamiento Unicode determinístico y preservación de la pregunta original;
2. interpretación estructurada opcional con `openai_gpt-5.4-nano` vía LiteLLM;
3. validación Pydantic estricta, allowlists y reconstrucción determinística de normalizaciones y variantes;
4. fallback determinístico ante timeout, HTTP, JSON o schema inválido;
5. retrieval PostgreSQL autoritativo posterior a la interpretación;
6. validación de IDs, páginas, claims y evidencia antes de responder.

La IA puede clasificar idioma, intent y estructura conversacional, pero no aporta queries libres, IDs, fuentes, páginas, SQL ni evidence strength. Cuando una interpretación reconocible contradice las invariantes determinísticas, el backend conserva la clasificación y los sujetos seguros. Los follow-ups reutilizan únicamente preguntas acotadas y sujetos validados; no confían en narrativa generada previa.
