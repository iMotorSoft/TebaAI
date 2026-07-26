# Contrato de interpretación

`POST /library/investigative-qa/v1` con `phase: "interpret"` autentica, valida la consulta y ejecuta como máximo una interpretación IA, con fallback determinístico.

La respuesta incluye:

- `phase: interpretation`;
- `status: awaiting_confirmation`;
- `interpretation_id` opaco;
- `conversation_id`;
- `original_query`;
- `display_interpretation` generado por plantilla;
- `query_understanding` estructurado;
- `actions: ["analyze", "modify"]`;
- warnings y expiración;
- `execution.retrieval_executed: false`.

No devuelve hits, claims, matrices, fuentes ni IDs de evidencia. El registro autoritativo queda en servidor, ligado a usuario y conversación, con TTL de una hora y límite de 1000 registros en el runtime single-worker.
