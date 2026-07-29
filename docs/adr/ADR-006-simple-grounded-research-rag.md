# ADR-006: Simple Grounded Research RAG as the Primary Path

Estado: accepted for DEV gate.

Fecha: 2026-07-29.

## Contexto

`POST /library/investigative-qa/v1` acumuló interpretación IA, reconciliación
determinística, intent, catálogos, expansiones y retrievals especializados antes
de responder. Esas capas son útiles como enriquecimiento, pero pueden convertir
una pregunta completa en un solo término o impedir la búsqueda cuando falla un
parser.

El baseline DEV lo demostró:

- `Relación sangre y habla` se redujo a `sangre` y terminó `no_evidence`;
- `qué relación hay entre alegría y emuná` se redujo a `Emuná`;
- `cómo se rectifica el miedo` quedó sin conceptos ni hits;
- los ocho casos del baseline informaron `used_vector=false`.

## Decisión

El endpoint existente conserva autenticación y contrato de evidencia, pero su
camino `legacy` usa por defecto `simple_rag`:

```text
pregunta original intacta
→ filtros explícitos
→ embedding de la pregunta completa
→ Milvus top K
+ PostgreSQL frase / FTS / trigram
→ fusión por chunk_id
→ Markdown canónico desde PostgreSQL
→ selección diversa
→ openai_gpt-5.4-nano vía LiteLLM
→ validación de evidence IDs y páginas
→ respuesta, fuentes, estado y warnings
```

La configuración `TEBAAI_RESEARCH_PIPELINE` admite:

- `simple_rag`: camino DEV por defecto;
- `advanced`: pipeline investigativo anterior;
- `compare`: responde con simple RAG y agrega métricas no bloqueantes del
  pipeline avanzado.

La pregunta original es inmutable. Las variantes controladas amplían recall,
pero nunca reemplazan el texto enviado al modelo de embeddings ni a la síntesis.

## Autoridad y evidencia

Milvus aporta identidad de chunk y score. PostgreSQL rehidrata el contenido
completo de `library_document_chunks.content`, metadatos documentarios, páginas
y sección. El texto de Milvus no se usa como fuente final.

Cada claim generado incluye IDs pertenecientes al context pack. El backend
rechaza IDs o páginas desconocidos. El frontend consume las asociaciones
estructuradas y muestra el Markdown canónico en el panel de fuentes.

La síntesis no usa conocimiento externo, SQL ni metadata inventada. Las
traducciones generadas no se presentan como cita literal.

## Retrieval y diversidad

La rama semántica usa `openai_text_embedding_3_small`, dimensión 1536, contra
`tebaai_breslov_chunks_v1`. El scope lógico `breslov_primary` se traduce al
metadata code histórico `breslov`.

La rama PostgreSQL combina:

- frase y aliases controlados;
- FTS español y simple;
- trigram limitado a la consulta principal para tolerar errores sin multiplicar
  el costo por todas las expansiones.

La fusión conserva score semántico, literal y combinado, más las señales de
origen. El contexto se deduplica por hash de contenido y se limita a 12 chunks,
con máximo de cuatro por obra salvo filtro explícito.

## Estados y fallbacks

El campo aditivo `research_status` distingue:

- `complete`: Milvus, literal e IA funcionaron;
- `partial`: existe evidencia, pero el contexto es insuficiente;
- `degraded`: una capa falló y otra permitió continuar;
- `no_evidence`: ambas búsquedas funcionaron y no recuperaron material.

El campo histórico `status` se preserva para consumidores existentes:
`complete → ok`, `degraded → partial`.

Fallbacks:

- Milvus falla: PostgreSQL literal continúa;
- literal falla: Milvus y rehidratación PostgreSQL continúan;
- síntesis falla: se muestran fuentes, páginas y evidence IDs;
- ambas búsquedas fallan: se informa problema técnico, nunca ausencia del
  corpus;
- advanced falla en `compare`: la respuesta simple se conserva.

## API y UX

No se crea un endpoint nuevo. La UI de `/research` envía la pregunta completa
directamente, sin confirmación obligatoria de intent. La jerarquía visible es:

1. Pregunta;
2. Respuesta;
3. Fuentes.

Interpretación, scoring y matrices permanecen secundarios o contraídos. Estados
y warnings de degradación son visibles. El panel de fuentes, ES/EN/HE, RTL,
guest read-only y evidence IDs continúan en el contrato.

## Observabilidad

El log sanitizado registra request ID, hash de consulta, idioma, filtros,
estados, conteos, fallback y latencias de embedding/Milvus, literal, fetch,
síntesis y total. No registra tokens, cookies, claves, DSN ni la pregunta
completa.

## Rollout y rollback

El gate se valida únicamente en DEV. No modifica corpus, embeddings,
PostgreSQL, Milvus o LiteLLM.

Rollback operativo:

```text
TEBAAI_RESEARCH_PIPELINE=advanced
```

requiere reiniciar solamente el backend DEV para releer configuración. No hay
migración que revertir.

## Consecuencias

El camino principal tolera fallos de interpretación y reduce la dependencia de
taxonomías previas. A cambio, el ranking híbrido y la selección de contexto
requieren evaluación continua con preguntas reales.

El pipeline avanzado no se elimina. Queda disponible para enriquecimiento,
comparación y compatibilidad durante el gate.
