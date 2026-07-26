# Auditoría del flujo previo

Antes del cambio, el submit de `ResearchWorkspace` llamaba directamente al pipeline completo de `POST /library/investigative-qa/v1`. Query understanding, PostgreSQL, selección de evidencia, claims y respuesta ocurrían dentro de la misma solicitud.

El punto reutilizable era `interpret_query` dentro de `investigative_qa_v1.py`. Se extrajo preparación compartida sin duplicar retrieval ni convertir una respuesta vacía en pantalla de confirmación.

Flujo final:

`submit → phase=interpret → awaiting_confirmation → Analizar → phase=analyze → completed`

`awaiting_confirmation → Modificar → phase=interpret con supersedes_interpretation_id → awaiting_confirmation`
