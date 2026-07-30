# ADR-009: Short proper-name literal retrieval

Estado: accepted for DEV validation

Fecha: 2026-07-29

## Problema

Una búsqueda inglesa nominal corta como `Gedalia of Linitz` podía llegar a
Milvus como una consulta temática y perder la mención literal. El documento y
el chunk existían tanto en PostgreSQL como en Milvus, pero el vector correcto no
entraba en el top 30. Además, el flujo de análisis confirmado ejecutaba
incondicionalmente el pipeline avanzado aunque el pipeline DEV configurado
fuera `simple_rag`.

El resultado era un falso `no_evidence` pese a existir Markdown canónico
citable.

## Decisión

Las dos formas de invocar `POST /library/investigative-qa/v1` —directa y por
confirmación— resuelven el mismo selector
`TEBAAI_RESEARCH_PIPELINE=simple_rag|advanced|compare`.

`simple_rag` reconoce de forma determinística una forma nominal acotada:

- entre uno y cinco tokens latinos;
- capitalización nominal, honorífico o conector nominal;
- sin depender del clasificador de intención;
- conservando conectores como `of`;
- excluyendo conectores únicamente del conjunto de tokens probatorios.

La normalización de búsqueda aplica NFKC, case folding, espacios, saltos,
comillas, guiones y controles invisibles. No modifica la pregunta original.
Las alternancias `e`/`i` son aproximaciones acotadas de retrieval, no equivalencias
editoriales: se consultan solo si no hubo exacta y producen estado `partial` y
warning.

## Ranking y selección

El orden nominal es:

1. `english_name_exact`;
2. `english_name_normalized`;
3. todos los tokens en orden/proximidad;
4. variante ortográfica aproximada;
5. coincidencia nominal parcial;
6. `semantic_only`.

El bloque de prioridad literal es independiente del score vectorial. Una fuente
`semantic_only` sin coincidencia nominal no puede ser primaria. Si existe una
exacta, el contexto generativo se limita a las coincidencias exactas y se
reserva la primera como evidencia principal. Esto evita que una fuente temática
lateral agregue biografía no solicitada.

Los chunks que abarcan más de una página resuelven la página visible usando el
marcador canónico `## Page N` inmediatamente anterior a la variante coincidente,
sin alterar datos persistentes.

## PostgreSQL y Milvus

PostgreSQL continúa siendo la autoridad para Markdown, documento, checksum,
obra, página y evidence ID. La búsqueda literal conserva la variante y su
ordinal.

Milvus continúa siendo complementario. La ausencia del chunk exacto en su top K
no autoriza `no_evidence` cuando PostgreSQL sí entrega una coincidencia literal.
No se reingieren documentos ni se recalculan embeddings en este gate.

## Grounding y estados

El context pack contiene pregunta original, `query_shape`, idioma, tipo de
coincidencia, variante, obra, página, evidence ID y Markdown canónico. Para
`short_proper_name`, la IA describe únicamente el contexto de la mejor mención
literal y no agrega biografía externa.

- exacta canónica con las capas sanas: `complete`;
- variante aproximada: `partial`;
- una capa caída con rescate válido: `degraded`;
- búsquedas sanas sin evidencia: `no_evidence`;
- IDs recuperados sin Markdown canónico: error técnico, no ausencia.

La respuesta generada debe incluir un evidence ID permitido en el Markdown y
cada claim debe usar IDs enviados al modelo.

## Observabilidad

Los logs sanitizados agregan `query_language`, `query_shape`, match primario,
tokens nominales, selección primaria, estados y latencias. La consulta se
registra solo como hash.

## Pruebas y rollout

Los tests cubren normalización, preservación de `of`, detección nominal,
ranking literal sobre semántica, prohibición de primaria semántica, página
local del match y selector de pipeline en el flujo confirmado.

El E2E DEV verifica admin y guest sobre `/research`, documento físico, página,
fragmento, evidence ID, estado, UI móvil, read-only y logout. No hay rollout a
producción en esta decisión.
