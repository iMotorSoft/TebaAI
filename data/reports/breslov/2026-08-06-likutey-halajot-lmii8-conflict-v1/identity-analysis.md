# Análisis de identidad — Likutey Halajot / LM II 8 — 2026-08-06

## Registros implicados (PostgreSQL)

| Rol | document_id | título | status | familia canónica | relación fuente |
|---|---|---|---|---|---|
| Antología conflictiva (ready) | `56ddcc3b-8296-4832-ac95-2bfe032cd4c6` | Likutey Halajot LM II 8 | `ready` | `likutey_halajot` | `likutey_moharan_ii:8 develops` (explicit) |
| Edición page-first (test) | `132a791a-d12b-45bc-9b34-dd143605de12` | Likutey Halajot — Interior Final | `test_candidate` | `likutey_halajot` | ninguno a nivel documento (por sección/chunk) |
| Original LM II (test) | `3715c6e0-db56-49a1-82df-62d0a4d0b5cd` | Likutey Moharán II — edición española BRI | `test_candidate` | `likutey_moharan_ii` | ninguno (obra original) |

## Identidad canónica persistida (ADR-019)

- `56ddcc3b` declara `work_family=likutey_halajot`, `edition="The Rosenberg Edition"` (explicit, portada), `volume=null/unresolved` y `source_identities=[{source_work_code: likutey_moharan_ii, source_lesson: 8, source_relation: develops, confidence: explicit}]`.
- `132a791a` declara familia `likutey_halajot`, `edition="Interior Final"` (derived del filename), `technical_version=v2` (derived del pipeline), volumen null.
- `3715c6e0` declara familia `likutey_moharan_ii`, `edition="Edición española BRI"`, `technical_version=layout_v1`.

## Verificación del resolver (evidencia `scope-resolution.json`)

| Consulta | scope | documentos seleccionados |
|---|---|---|
| `Likutey Halajot` | familia lh | Interior Final + Rosenberg |
| `Likutey Halajot LM II 8` | familia lh + source lmii:8 | **solo Rosenberg** |
| `Likutey Moharán II` | familia lmii | **solo LM II BRI** (Rosenberg excluido) |
| `Likutey Moharán II lección 8` / `LM II 8` | familia lmii + lección 8 | solo LM II BRI |
| `Likutey` / `LM` | `scope_ambiguous` | ninguno (por diseño, ADR-019) |

## Conclusiones

1. **No hay contaminación de scope**: el resolver excluye a `56ddcc3b` del scope `lmii` y lo selecciona únicamente para consultas LH que declaran la relación fuente lmii:8. La "contaminación" reportada en ADR-017 era un artefacto del diagnóstico previo, no del resolver actual.
2. **No hay ambigüedad sin resolver**: `Likutey`/`LM` retornan `scope_ambiguous` por diseño (decisión explícita de ADR-019).
3. **El `8` es lección fuente, nunca volumen/edición**: `volume` permanece null/unresolved en las tres fuentes; `v2` en Interior Final es versión técnica, no volumen 2.
4. **Sin duplicados**: 0 content_sha256 compartidos entre documentos auditados; 0 duplicados dentro de cada documento.
5. **Evidence IDs**: 0 colisiones cross-document en la muestra (los IDs derivan de `chunk_id` + entity key; los chunk_ids son UUID distintos por documento).
6. **Milvus**: no verificable en esta corrida (servicio caído ambientalmente); la reconciliación PG↔Milvus queda para el readiness V2.

## Clasificación

- **A (alias de metadata sin corrupción de contenido)**: VERDADERO → resolución presente.
- **B–K**: FALSAS (sin defectos de duplicado, ownership, drift, colisión, superseded o inferencia incorrecta).
- **L (ambigüedad editorial)**: VERDADERO → comportamiento diseñado (`scope_ambiguous`), ya decidido en ADR-019.

**Resolución: técnica, sin modificación de datos.** No se requiere reparación; el gate se cierra con resolución diagnóstica y cero escrituras.
