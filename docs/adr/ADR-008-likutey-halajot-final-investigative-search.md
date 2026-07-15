# ADR-008: Likutey Halajot final investigative search

Estado: accepted and implemented.

Fecha: 2026-07-15.

## Decisión

Se crea una vista investigativa final mediante unión tipada de las capas page-first, estructura, zonas, notas, referencias nominales y sus resoluciones. La unión, en lugar de joins multiplicativos, conserva una evidencia independiente por fila y evita inferir relaciones entre capas de la misma página.

La vista normal excluye resoluciones `rejected_false_positive`; la vista de auditoría las conserva. Todas las referencias y resoluciones mantienen `is_authoritative_relation=false`.
