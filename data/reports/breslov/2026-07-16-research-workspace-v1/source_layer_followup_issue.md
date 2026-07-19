# Follow-up de naturaleza de fuente pendiente

Estado: `SOURCE_LAYER_FOLLOWUP_ANSWER_BLOCKED`.

## Caso reproducible

Después de recuperar la frase hebrea de `LIKUTEY MOHARÁN XV KDP.pdf`, preguntar:

`¿Es parte de la lección del Rebe, una cita o una nota?`

## Resultado actual

El backend conserva la evidencia, su identidad y `source_layer=biblical_quote_in_lesson`, pero `answer_markdown` reutiliza una síntesis del turno anterior. La respuesta no contesta de forma directa la disyuntiva del investigador.

## Resultado esperado

La narración debe comenzar con una respuesta basada en la capa del turno actual:

`Sí. Es una cita bíblica incluida dentro de la lección del Rebe. No es una nota editorial.`

Si la capa no está confirmada, debe responder `No confirmado` y mantener la confianza prudente.

## Alcance del checkpoint

Los gates existentes validan prioridad hebrea, clasificación estructurada, trazabilidad, estabilidad del evidence ID y presentación original → traducción. El E2E multi-turno actual no afirma todavía la formulación narrativa directa.

La corrección queda fuera de estos commits de preservación y debe realizarse después como:

`fix(breslov): answer source-layer follow-ups directly`
