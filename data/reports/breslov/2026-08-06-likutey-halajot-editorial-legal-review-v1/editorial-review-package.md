# Paquete de revisión editorial — Likutey Halajot (Interior Final) — 2026-08-06

Documento: `132a791a-d12b-45bc-9b34-dd143605de12` · status `test_candidate`

## Instrucciones para el revisor

Completar cada control con `Aprobar`, `Corregir`, `NA` o `Pendiente` y registrar
nombre, rol, fecha, observaciones y evidencia de aprobación. No se aplica ningún
cambio en esta fase; los resultados alimentan la matriz de decisión.

## Identidad editorial (ADR-019)

- work_family: **Likutey Halajot** (`likutey_halajot`)
- canonical_work: Likutey Halajot
- edition: **Interior Final** (derivada del filename) — ⚠️ la portada del PDF dice
  **"THE ROSENBERG EDITION"** (ver hallazgo H1)
- volume: null (unresolved)
- source_work/source_lesson: null a nivel documento (relaciones por sección/chunk)
- language: es (hebreo embebido)
- NUNCA es "Likutey Moharán II" ni "LM II 8" como obra (ADR-018/019)

## Hallazgos de evidencia (no decisiones)

| ID | Hallazgo | Impacto |
|---|---|---|
| H1 | Portada (pág. 1): "Likutey Halakhot / Reb Noson of Breslov / THE ROSENBERG EDITION" + "Rabí Natán de Breslov / Likutey Halajot". La edición persistida "Interior Final" difiere de la portada. | Revisar etiqueta de edición |
| H2 | Página 143: encabezado con glifos corruptos (`\x98\x83...`) + bytes de control; el cuerpo en español está íntegro. | Calidad de texto puntual |
| H3 | Página 1: bloque hebreo del título con bytes de control (artefacto de codificación). | Calidad de texto puntual |
| H4 | 120 chunks contienen hebreo (niqqud preservado); muestras incluidas en `editorial-sampling.json`. | OK / muestrear |
| H5 | 16 páginas físicas en blanco justificadas (6, 8, 34, 38, 100, 102, 116, 118, 146, 202, 204, 240, 242, 266, 274, 284). | OK |

## Checklist editorial

| Control | Decisión (revisor) |
|---|---|
| Título correcto | ⬜ Aprobar / Corregir — nota: portada dice "Likutey Halakhot", título persistido "Likutey Halajot — Interior Final" |
| Autor o atribución | ⬜ Aprobar / Corregir — portada: "Reb Noson of Breslov" / "Rabí Natán de Breslov" |
| Familia documental | ⬜ Aprobar / Corregir — `likutey_halajot` |
| Obra canónica | ⬜ Aprobar / Corregir — Likutey Halajot |
| Edición | ⬜ Aprobar / Corregir / Pendiente — H1 |
| Volumen | ⬜ Aprobar / Corregir / NA — null persistido |
| Idioma | ⬜ Aprobar / Corregir — es |
| Páginas | ⬜ Aprobar / Corregir — 284 físicas, 268 textuales |
| Orden de páginas | ⬜ Aprobar / Corregir |
| Headings | ⬜ Aprobar / Corregir — golden Mishkán pág 51 (structural_heading_exact) |
| Notas al pie | ⬜ Aprobar / Corregir — nota 35 pág 56; ligaduras normalizadas (ADR-020) |
| Referencias impresas | ⬜ Aprobar / Corregir — golden Salmos 16:1 pág 55 |
| Calidad del texto | ⬜ Aprobar / Corregir — H2/H3 |
| Citas hebreas | ⬜ Aprobar / Corregir / NA — 120 chunks con hebreo |
| Niqqud | ⬜ Aprobar / Corregir / NA |
| Fragmentación | ⬜ Aprobar / Corregir |
| Resultados de búsqueda | ⬜ Aprobar / Corregir — retrieval literal/FTS/híbrido PASS |
| Advertencias | ⬜ Aceptar / Bloquear — H1/H2/H3 no bloqueantes técnicamente |
| Nombre visible al usuario | ⬜ Aprobar / Corregir |
| Descripción editorial | ⬜ Aprobar / Corregir |

## Muestras

Ver `editorial-sampling.json` (páginas 1/16/51/55/56/96/143/200/283/284, goldens
con evidence IDs, muestras hebreas). Incluye casos normales, difíciles (pág.
143), páginas vacías, Unicode/RTL y referencias ambiguas.

## Revisor

- Nombre: ____________________ · Rol: ____________________
- Fecha: ________ · Decisión: ____________________
- Observaciones: ____________________
- Evidencia de aprobación: ____________________
