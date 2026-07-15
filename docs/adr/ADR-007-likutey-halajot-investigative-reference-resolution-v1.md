# ADR-007: Likutey Halajot investigative reference resolution V1

Estado: accepted and implemented.

Fecha: 2026-07-15.

## Decisión

Las referencias nominales ambiguas se resuelven en una tabla separada y versionada. La resolución es metadata de búsqueda: conserva el literal, la cita y el padre original; no modifica page-first, no sustituye la fila nominal ni crea relaciones o autorías.

La cadena determinística intenta catálogo, variantes, patrones, comparación de corpus y contexto literal. Los localizadores internos se rechazan como falsos positivos; una mención textual útil sin normalización segura cierra como `keep_generic_source`. IA no fue requerida por V1.

## Consecuencia

Los consumidores pueden distinguir una referencia canónica de búsqueda, una mención genérica y un localizador interno rechazado sin tratar ninguno como afirmación doctrinal o editorial.
