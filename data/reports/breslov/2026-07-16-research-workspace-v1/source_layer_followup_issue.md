# Follow-up de naturaleza de fuente resuelto

Estado: `SOURCE_LAYER_FOLLOWUP_DIRECT_ANSWER_PASS`.

## Caso reproducible

Después de recuperar la frase hebrea de `LIKUTEY MOHARÁN XV KDP.pdf`, preguntar:

`¿Es parte de la lección del Rebe, una cita o una nota?`

## Resultado anterior

El backend conserva la evidencia, su identidad y `source_layer=biblical_quote_in_lesson`, pero `answer_markdown` reutiliza una síntesis del turno anterior. La respuesta no contesta de forma directa la disyuntiva del investigador.

## Resultado implementado

La narración comienza con una respuesta basada en la capa del turno actual:

`Sí. Es una cita bíblica incluida dentro de la lección del Rebe. No es una nota editorial.`

Si la capa no está confirmada, responde `No confirmado` y mantiene la confianza prudente.

## Alcance de la corrección

Los gates validan prioridad hebrea, clasificación estructurada, trazabilidad, estabilidad del evidence ID, presentación original → traducción y formulación narrativa directa.

La corrección se preserva en:

`fix(breslov): answer source-layer follow-ups directly`
