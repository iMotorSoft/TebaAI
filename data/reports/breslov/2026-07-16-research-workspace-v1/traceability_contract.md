# Contrato de trazabilidad claim-evidencia

El backend es la autoridad de asociación. El frontend no analiza Markdown para encontrar IDs.

## Claims

Cada claim validado contiene `claim_id`, `text`, `strength`, `evidence_ids` existentes y un `primary_evidence_id` miembro de esa lista. `primary_evidence_ids` conserva el orden global y `hits[0]` coincide con su primer elemento cuando existe.

## Evidencia

- `literal_strength`: fidelidad literal del tipo de registro.
- `evidence_strength`: fuerza para la consulta relacional.
- `relation_relevance`: relación directa, coocurrencia contextual, coincidencia de un solo término, temática, inferida o ruido.
- `matched_concepts` y `matched_terms`: cobertura estructurada.
- `is_primary`: pertenencia a la selección principal.
- `quote`: texto canónico recuperado.
- `snippet`: corte de presentación con elipsis y límite de palabra u oración.

Una coincidencia de un solo término tiene fuerza relacional insuficiente y no puede ser primaria para una consulta de dos conceptos.

## Conteos y límites

`evidence_counts` separa `primary`, `contextual` y `additional_literal`. `max_hits_per_work` se aplica después de deduplicar y ordenar.

## Compatibilidad y seguridad

Los campos son aditivos. El normalizador valida IDs, pertenencia de primarias, counts no negativos y enums. Claims incompatibles producen un error seguro y no se renderizan.
