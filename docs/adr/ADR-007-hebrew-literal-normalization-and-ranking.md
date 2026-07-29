# ADR-007: Hebrew literal normalization and ranking

Estado: accepted for DEV validation

Fecha: 2026-07-29

## Problema

El texto hebreo extraído de PDF puede conservar las letras pero separar letras,
niqqud y límites visuales con espacios artificiales. NFC, NFD, controles bidi y
la ausencia de niqqud producen además representaciones binarias distintas. El
RAG simple buscaba solo chunks `ready`; cuando el texto canónico vivía en nodos
citables de un documento `test_candidate`, el literal devolvía cero resultados
y una coincidencia semántica sin términos podía convertirse en evidencia
principal.

## Decisión

`normalize_hebrew_for_search()` es la única normalización compartida de consulta
para este camino. Conserva el original y produce, sin escribir el corpus:

- NFC/NFKC de compatibilidad para búsqueda;
- remoción de taamim, niqqud y controles invisibles en variantes separadas;
- reagrupación de marcas combinantes con su letra;
- detección acotada de espaciado de glifos PDF;
- tokens, forma compacta y hasta 64 segmentaciones aproximadas.

Las aproximaciones sirven exclusivamente para retrieval. Nunca sustituyen la
cita canónica ni agregan vocales ausentes.

La búsqueda PostgreSQL de hebreo consulta nodos citables canónicos y compara la
secuencia compacta de letras. En DEV puede leer `test_candidate` de forma
explícita y read-only. Esa opción se fuerza a `false` fuera de `development`,
conserva `document_status` y agrega una advertencia; no promueve ni indexa
documentos.

Milvus continúa buscando el original. Para hebreo se agrega como máximo un
segundo embedding de la forma normalizada sin niqqud. Los resultados se
deduplican.

## Ranking e evidencia

El orden es:

1. `hebrew_exact_diacritized`;
2. `hebrew_exact_normalized`;
3. `hebrew_all_tokens_ordered`;
4. `hebrew_all_tokens_proximity`;
5. `hebrew_bigram`;
6. `hebrew_partial_tokens`;
7. `semantic_only`.

Una coincidencia literal hebrea recibe un bloque de prioridad independiente del
score vectorial. `semantic_only` con cero tokens nunca puede ser primaria. Para
una consulta literal hebrea, la selección reserva primero los nodos exactos y
el validador solo acepta como principales exactas normalizadas, exactas con
diacríticos o todos los tokens en orden.

PostgreSQL entrega `literal_text`, obra, archivo, checksum, nodo, ancla, página
física/impresa y sección. Milvus no es fuente de cita.

## Grounding, estados y fallbacks

El context pack distingue pregunta original, forma de búsqueda, tokens y tipo
de match. La IA no puede convertir `semantic_only` en prueba literal ni afirmar
ausencia en todo el corpus.

- Milvus caído: literal PostgreSQL y warning.
- Literal caído: Milvus, sin promoción a evidencia literal.
- IA caída: fuentes recuperadas visibles.
- Ambas recuperaciones caídas: error técnico, no ausencia.
- Búsquedas sanas sin soporte: `no_evidence`.

## Observabilidad

Se registran hashes y datos no sensibles: idioma, normalización aplicada,
espaciado artificial, estados, conteos, selección, match primario, fallback y
latencias. No se registra la pregunta completa ni credenciales.

## Límites y rollout

No se crean índices ni migraciones en este gate. La comparación compacta puede
costar algunos segundos sobre los nodos candidatos de DEV. Un índice derivado
solo se considerará después de medir volumen y con migración autorizada.

Este gate no reingiere, no modifica chunks/nodos, no recalcula embeddings y no
despliega producción. El rollout posterior requiere promover o corregir
metadatos editoriales por el proceso canónico y revalidar el flag fuera de DEV.

## Pruebas

Las pruebas cubren NFC/NFD, niqqud, taamim, controles bidi, presentación Unicode,
maqaf, espacios legítimos/artificiales, texto mixto, ranking literal sobre
semántica y prohibición de evidencia primaria `semantic_only`. El gate real
verifica con niqqud, sin niqqud y fragmentada contra el mismo nodo/fuente.
