# ADR-010: Recuperación literal de encabezados estructurales

Estado: accepted for DEV validation

Fecha: 2026-07-30

## Problema

La consulta `CONSTRUYENDO UN MISHKÁN` devolvía evidencia temática de otra
edición o quedaba sin evidencia primaria, aunque el encabezado y su bajada
existían en PostgreSQL para `LIKUTEY HALAJOT (Interior Final).pdf`, página
física 51 e impresa 33.

La causa era combinada:

- la forma en mayúsculas se confundía con `short_proper_name`;
- la búsqueda literal genérica consultaba chunks `ready`, pero no los bloques
  estructurales `test_candidate` habilitados en DEV read-only;
- el heading y la bajada eran chunks contiguos independientes;
- sus vectores existían únicamente en la colección Milvus de test, mientras
  `simple_rag` consulta correctamente la colección productiva;
- el ranking semántico podía promover fragmentos sobre el Mishkán que no
  contenían el título.

## Decisión

`simple_rag` incorpora una rama PostgreSQL acotada para títulos y encabezados
existentes. La consulta conserva su valor original y se normaliza por separado
con NFKC, case folding, espacios Unicode, controles invisibles, marcadores
Markdown, puntuación editorial, número inicial y una proyección sin diacríticos.
La cita visible nunca usa la proyección sin acentos.

La forma de consulta sólo es una candidata. `query_shape=structural_heading` se
establece únicamente cuando una línea estructural real del corpus coincide. Las
consultas en mayúsculas con apariencia editorial que no encuentran heading no
pueden promover evidencia temática como título.

Fuentes reutilizadas, sin migración:

- `library_document_chunks.section_title`;
- headings Markdown dentro de chunks normalizados e indexados;
- bloques compactos de layout existentes en documentos DEV
  `test_candidate`, limitados por longitud y metadata;
- `library_content_nodes_v2` continúa siendo la ruta literal hebrea ya
  existente.

## Ranking y evidencia

El orden es:

1. `structural_heading_exact`;
2. `structural_heading_normalized`;
3. `structural_heading_accent_folded`;
4. `structural_heading_all_tokens_ordered`;
5. `structural_heading_all_tokens_proximity`;
6. `body_literal`;
7. `structural_heading_partial`;
8. `semantic_only`.

Un heading estructural válido domina un resultado semántico aunque el score
vectorial de este último sea mayor. `semantic_only` no puede ser evidencia
primaria de una consulta estructural.

Cuando heading y cuerpo están separados, el backend asocia el siguiente bloque
canónico citable de la misma página y tipo estructural. La evidencia mantiene el
ID y el texto del chunk de heading, incorpora la bajada canónica, expone el
`associated_chunk_id` y deduplica el contexto de generación.

## Página y presentación

La evidencia conserva por separado:

- página física del PDF;
- página impresa;
- heading original almacenado;
- sección editorial visible;
- archivo físico;
- chunk o node;
- evidence ID estable.

Para el caso focal, el signo decorativo almacenado `4 ■` se conserva en
`heading_original`; la sección visible se presenta como
`4. CONSTRUYENDO UN MISHKÁN`.

La UI etiqueta `Coincidencia exacta con título de sección` y muestra obra,
archivo, ambas páginas, sección, variante normalizada, chunk asociado y evidence
ID, sin exponer scores por defecto.

## Estados y fallbacks

- heading exacto, contexto y capas sanas: `complete`;
- coincidencia estructural parcial: `partial`;
- una capa general caída con heading PostgreSQL válido: `degraded`;
- lookup editorial sano sin heading: `no_evidence`;
- IDs sin rehidratación canónica: error técnico, no ausencia documental.

La síntesis trata el título como consulta válida, explica dónde aparece y qué
desarrolla el fragmento asociado, sin conocimiento externo ni metacomentarios
sobre la gramática de la consulta.

## Milvus y datos

PostgreSQL sigue siendo la fuente de verdad. Milvus sigue siendo derivado. La
rama estructural rescata evidencia aunque el vector no esté en el top K o esté
sólo en la colección de test. Este gate no reingiere, no recalcula embeddings,
no promueve documentos, no migra y no modifica corpus.

## Consecuencias y límites

La solución evita un índice nuevo y reutiliza campos e índices existentes. El
fallback para bloques layout sin `search_text_normalized` está limitado a
bloques cortos de documentos DEV; no hace extracción completa del corpus por
request. Si el volumen creciera o esa rama dejara de ser acotada, un índice
persistente requerirá una ADR y migración separadas.

Los tests cubren normalización, clasificación corpus-backed, asociación
heading→body, ranking sobre semántica, páginas física/impresa, negativos,
nombres propios y regresiones multilingües. El rollout queda limitado a DEV.
