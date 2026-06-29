# Status actual - TebaAI lat.md

Este tablero resume la arquitectura viva de TebaAI y evita repetir la historia técnica del runtime.

Objetivo: `arquitectura-viva`

Ultima actualizacion: 2026-06-29 (aislamiento de corpus bibliografico de prueba)

## Estado general

LAT documenta configuración, persistencia, autenticación, retrieval, validación y límites operativos con un índice único y referencias desde código.

- PostgreSQL 18 es fuente de verdad.
- Milvus 2.6 es un índice vectorial derivado.
- LiteLLM provee embeddings y será el gateway de modelos futuros.
- TebaAI recupera evidencia bibliográfica; todavía no genera respuestas RAG.
- Breslov es la primera colección, no una dependencia de dominio del núcleo genérico.

## Decisiones vigentes

Las decisiones estables se mantienen en documentos canónicos enlazados desde [[lat]].

- [[global-configuration-facade-policy]] concentra configuración y secretos.
- [[postgres-driver-policy]] fija `psycopg 3 async` y repositories SQL.
- [[authentication-security-policy]] define passwords, tokens, roles y sesión web.
- [[library-retrieval-models-policy]] separa retrieval textual, vectorial, híbrido y generación futura.
- [[breslov-test-corpus-policy]] separa candidatos experimentales del corpus `breslov` productivo.
- [[page-mapping-failure-diagnosis]] explica la baja cobertura de páginas y limita las mejoras a dry-runs validados.
- [[service-preflight-methodology]] gobierna pruebas con servicios reales.
- [[tebaai-knowledge-map]] ofrece el árbol de navegación.

## Consolidación 2026-06-28

La limpieza corrigió contradicciones entre documentación operativa, arquitectura y código vigente.

- `AGENTS.md` dejó de tratar una rama Team360 como rama canónica de TebaAI.
- El status runtime fue compactado y la historia quedó separada.
- El status duplicado y obsoleto de Astro fue retirado.
- Configuración y PostgreSQL dejaron de aparecer como pendientes.
- Milvus quedó registrado como integración implementada, no como tarea futura.
- Las credenciales E2E ya no tienen fallback versionado.
- Se agregaron referencias `@lat` en configuración, auth y retrieval.

## Validación

La documentación debe aprobar validación estructural y mantener referencias resolubles.

- `lat check`: gate obligatorio y objetivo de cero errores.
- `git diff --check`: obligatorio.
- tests focalizados: obligatorios cuando cambian referencias dentro de código.
- `lat search`: opcional mientras no exista clave LAT; usar `lat locate` como alternativa.

## Diagnóstico de page mapping 2026-06-29

El diagnóstico read-only confirmó que los chunks siguen presentes en la extracción completa, pero sus anchors se degradan al comparar contra extracción PyMuPDF página por página.

- Potencia: 50/50 anchors en extracción completa, 36/50 con evidencia baseline page-aware.
- Likutey: 50/50 anchors en extracción completa, 33/50 con evidencia baseline page-aware.
- La normalización ampliada es la candidata de bajo riesgo; Potencia requiere refinar el guard porque obtuvo 96% de precisión high en holdout, mientras Likutey obtuvo 100%.
- No se aplicó metadata ni se modificaron chunks, PostgreSQL, Milvus o embeddings.

## Corpus de prueba 2026-06-29

El corpus `breslov_test` permite validar documentos sin convertirlos en evidencia productiva.

- `library_documents.status` acepta `test_candidate` mediante migración 008.
- `bibliographic_metadata` conserva metadata documentaria separada de metadata operativa.
- `El Alma del Rebe Najmán` quedó persistido como candidato con texto y cero chunks.
- `breslov` mantiene sus documentos `ready` y sus chunks sin cambios.
- Milvus y LiteLLM no participaron en la ingesta del candidato.

## Pendientes

La deuda arquitectónica restante requiere decisiones explícitas y no debe mezclarse con tareas ya cerradas.

1. ADR para cookies `httpOnly`, CSRF y refresh automático.
2. ADR para el límite plataforma TebaAI / vertical Breslov.
3. ADR previo a cualquier generación RAG o síntesis con LLM.
4. Reconciliar conteos PostgreSQL/Milvus antes de reindexar.

## Seguridad

Los documentos y ejemplos no deben contener credenciales funcionales ni fallbacks compartidos.

Las pruebas autenticadas reciben email y password mediante variables de entorno y se omiten de forma explícita cuando faltan.
