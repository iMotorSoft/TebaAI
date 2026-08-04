# ADR-021 — Editorial Evidence Granularity & Stable IDs V1

## Estado

Aceptado (DEV).

## Contexto

La fase anterior de normalización de ligaduras PDF reveló que la nota 35 y la
nota 36 (ambas en la página 56, folio impreso 38 del Interior Final)
compartían el mismo `evidence_id` (`ev-e419ec6448d2d992`), al igual que el
heading 6 (MELODÍAS Y PLEGARIAS) en la misma página.

La causa: el pipeline page-first V2 persiste una página completa como un solo
chunk (`036be7c5-...`). La función `_evidence_id` derivaba su identidad
exclusivamente del `chunk_id` mediante `SHA-256(chunk_id)[:16]`. Tres
entidades editoriales distintas (dos notas y un heading) en el mismo chunk
recibían el mismo identificador.

Los campos `footnote_number`, `source_layer`, `block_role` y `exact_quote`
distinguían las sub-entidades en tiempo de renderizado, pero no se reflejaban
en la identidad persistente. Dentro de una misma respuesta esto no producía
colisiones (el merge deduplica por chunk_id), pero sí impedía distinguir
entidades entre consultas distintas o en historiales de sesión.

## Decisión

**El `evidence_id` ahora identifica la entidad editorial**, no el chunk de
almacenamiento.

### Componentes del hash (v2)

```json
{"v": "2", "chunk": "<chunk_id>", "entity": "<entity_key>"}
```

Orden de claves normalizado con `sort_keys=True`, serializado con
`separators=(",", ":")`, hasheado con SHA-256 y prefijado con `ev-`.

### Claves de entidad

| Match type | Entity key | Discriminator |
|---|---|---|
| `footnote_literal_exact` | `footnote:{number}` | `chunk.footnote_number` |
| `structural_heading_*` | `heading:{_fold(heading_original)}` | heading original |
| `printed_reference_exact` | `reference:{_fold(matched).strip(parenthesis)}` | superficie normalizada |
| `body_literal_exact` | `body` | — |
| `english_name_exact` | `name:{_fold(matched)}` | nombre |
| `evidence_role=footnote_body` | `footnote:unknown` | solo rol |
| `evidence_role={other}` | `role:{evidence_role}` | rol |
| fallback | `chunk` | — |

### Campos adicionales en el hit

- `evidence_identity_version`: `"v2"` (string fijo)
- `legacy_evidence_id`: `ev-{SHA-256(chunk_id)[:16]}` (ID de chunk anterior)

### Compatibilidad

El ID legacy se preserva para consumidores que requieran el identificador
anterior (reportes, depuración, transición de historial). El nuevo ID es
determinista y estable: misma entidad editorial produce el mismo ID, y
entidades distintas producen IDs distintos.

### Span identity

No se implementó `matched_span_id` en esta fase. Dentro de una misma entidad
editorial, diferentes spans de consulta comparten el mismo `evidence_id`. La
cita exacta y el `footnote_number`/`heading_original` distinguen la
presentación.

## Invariantes

- Diferente entidad editorial → diferente `evidence_id` (nota 35 ≠ nota 36 ≠ heading).
- Misma entidad editorial → mismo `evidence_id` estable (nota 36 con ligadura = nota 36 sin ligadura).
- Las variantes de query no afectan la identidad (`Salmos 16:1` = `(Salmos 16:1)` = `salmos 16:1`).
- El rank, score, status y claim order no afectan la identidad.
- La IA no puede inventar, sustituir ni fusionar IDs (validación backend).
- El ID legacy se preserva en campo separado.

## No decisiones

- No se reingiere.
- No se modifican embeddings, chunks, páginas ni Milvus.
- No se cambia el ranking, scope, metadata bibliográfica ni status.
- No se promueve `Interior Final`.

## Consecuencias

- Notas, headings y referencias ahora son entidades citables con identidad
  separable.
- El dedupe sigue siendo por chunk (un solo hit por chunk dentro de una
  respuesta), pero las entidades pueden distinguirse entre consultas.
- La IA puede asociar claims a IDs granulares.
- El frontend recibe IDs únicos para cada entidad editorial.
- Backward compatibility vía `legacy_evidence_id`.

## Rollback

Reversión de las funciones `_evidence_id` y `_entity_key` a la versión
anterior (solo chunk_id), eliminación de `legacy_evidence_id` y
`evidence_identity_version`, y reversión de fixtures y tests.
