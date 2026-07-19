# Contrato de prioridad del idioma

- `interface_language`: idioma de la interfaz.
- `query_instruction_language`: idioma narrativo de la instrucción.
- `primary_retrieval_language`: idioma del término o frase buscada; hebreo prevalece cuando el término está en hebreo.
- `evidence_language`: idioma del fragmento recuperado.
- `source_original_language`: idioma original confirmado de la evidencia.

Orden: coincidencia exacta o normalizada en el idioma del término; texto original/cita dentro de la lección; edición original paralela; traducción contractual; comentario; nota; coincidencia temática. Si no existe evidencia en el idioma primario, el cambio de idioma debe declararse explícitamente.

Gate real: `language_priority_batch.json`, 18/18 para idioma primario y 18/18 para idioma de evidencia principal cuando existe.
