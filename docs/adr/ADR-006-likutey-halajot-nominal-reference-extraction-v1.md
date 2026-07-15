# ADR-006: Likutey Halajot nominal reference extraction V1

Estado: accepted and implemented.

Fecha: 2026-07-15.

## Contexto

El corpus page-first de Likutey Halajot conserva notas y fuentes con cita verificable, pero sus nombres no eran una dimensión de búsqueda aislable.

## Decisión

Se agrega metadata de referencias nominales literal-only en `library_likutey_halajot_nominal_references_v1`. Cada fila conserva página física, contexto literal, padres opcionales y validación contra el literal padre y page-first. El catálogo es abierto: ayuda a detectar patrones seguros, mientras que los candidatos genéricos quedan sin normalizar y en revisión editorial.

No se crean relaciones, autorías, atribuciones doctrinales ni vínculos editoriales. La tabla no sustituye ninguna nota ni zona existente. La IA no interviene en V1 (`ai_not_required_for_v1`).

## Consecuencias

La búsqueda puede filtrar por forma superficial, forma normalizada segura, tipo, nota, halajá o página. Los consumidores deben presentar `validation_status` y tratar toda fila como: «esta forma aparece literalmente aquí», no como una afirmación sobre procedencia o comentario.
