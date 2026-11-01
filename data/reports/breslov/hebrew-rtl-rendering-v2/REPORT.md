# TEBAAI_BRESLOV_HEBREW_RTL_RENDERING_V2 — PASS

Cierre del fix de visualización hebrea/RTL que ya existía en el working tree.
Validación real en Chromium contra corpus real en DEV, sobre bytes congelados.
Fecha: 2026-11-01. Rama: `feature/console-backend-core`.
Base autoritativa: `0d3064d7a1181ff40bfae150af1c81546d9920cb` (local = tracking = remoto).

## Alcance

Sólo rendering/fidelidad hebrea. Sin reingesta, extracción, embeddings, vectores ni punteros.
Sin tocar Foundation V2, migración 043, lifecycle, rollback, `page_first_gateway`,
`region_publication.py`, cuarentena, certifier V5, corpus C, durable source, retrieval
ni `status_actual.md`.

## Archivos del fix (congelados)

Producto frontend:

- `astro/src/components/library/DirectionalSourceText.svelte` (nuevo)
- `astro/src/components/library/RelationQAPanel.svelte`
- `astro/src/components/library/sourceTextRuns.ts`
- `astro/src/components/research/SourcePanel.svelte`
- `astro/src/components/research/markdownRenderer.ts`

Fidelidad backend:

- `backend/modules/library/pdf_hebrew_fidelity.py`

Tests:

- `astro/src/components/library/sourceTextRuns.test.ts`
- `astro/src/components/research/markdownRenderer.test.ts`
- `backend/tests/test_pdf_hebrew_fidelity.py`

`AMBIGUOUS = 0`. Los otros cambios sucios (import V5 en `extractors.py`, `status_actual.md`,
experimentos de font-unicode/reconstruction/visibility, dev reset, tests V5 y reportes previos)
quedaron clasificados `PREEXISTING_UNRELATED` y no se tocaron ni se stagearon.

## Automático (bytes congelados)

| Suite | Comando | Resultado |
| --- | --- | --- |
| Backend fidelidad hebrea | `uv run pytest tests/test_pdf_hebrew_fidelity.py -q` | 23 passed, 0 failed |
| Frontend RTL/ecuaciones | `pnpm vitest run sourceTextRuns.test.ts markdownRenderer.test.ts textDirection.test.ts` | 55 passed, 0 failed |
| Svelte/Astro | `pnpm check` | 0 errors, 0 warnings, 9 hints preexistentes |
| Diff | `git diff --check` | PASS |

El test backend ahora exige preservación de letras y multiset de marcas combinatorias:
las vocales pueden moverse a su base geométrica, ninguna puede desaparecer.

## QA real en Chromium (corpus real DEV)

Servicios levantados sólo para QA: backend `127.0.0.1:7008`, Astro `127.0.0.1:3008`.
Cero errores de consola y cero HTTP 5xx. Navegación por la UI real de investigación,
evidencia seleccionada desde el panel de fuentes.

### A — Un Día en la Vida de un Jasid de Breslov, PDF 187

Chunk real `f741e872-1850-5bb7-8d73-a7e121f4084d`.

- Texto renderizado idéntico al `display_snippet` almacenado (NFC, sin controles bidi).
- `bdi dir="auto"` resuelto RTL; niqqud sobre su glifo base, sin espacios internos artificiales.
- Cero `U+FFFD` en el fragmento A.
- Español y metadata LTR circundantes intactos.
- Desktop 1440×900 y mobile 390×844 PASS, sin overflow horizontal.

### B — La Potencia de la Plegaria, PDF 416

Chunk real `9ad96286-7e98-5583-8e96-279e3603430a`.

- 27 celdas de ecuación aisladas, todas `bdi dir="ltr"`, `white-space: nowrap`.
- En cada celda: número a la izquierda de `=`, `=` a la izquierda del glifo hebreo, misma línea visual.
- Casos verificados: `6 = ו`, `1 = א`, `400 = ת`, `80 = פ,ף`, `20 = כ,ך`, `500 = ך`, etc.
- Desktop 1440×900 y mobile 390×844 PASS; ninguna celda se parte ni desborda.

### Presentation forms / puntuación

- Run hebreo almacenado con `U+FB20` (ayin alternativo): `bdi dir="auto"`, isla RTL correcta.
- Nota real: NFC descompone la mayor parte de `U+FB1D–U+FB4F` a letra + niqqud; `U+FB20`
  no tiene descomposición canónica y es el caso que el fix incorpora al rango hebreo.
- Respuesta mixta real (español + hebreo con `U+FB4B`, `U+FB3C`, `U+FB35`): 5 islas
  `bdi dir="auto" lang="he"`, sólo hebreo dentro, sin puntuación ni espacios en los bordes,
  0 nodos de puntuación dentro de una isla.
- Respuesta con paréntesis y comillas: 4 islas hebreas, paréntesis/comillas/puntos fuera de
  la isla; el orden visual LTR del español se mantiene.

### Regresión LTR

- Evidencia real sólo en español: bloque `dir="ltr"`, `bdi dir="auto"` resuelto LTR.
- Respuesta sólo en español: `dir="ltr"`, 0 `bdi`, 0 `rtl`.
- `/admin/content`: `body` y tabla en LTR, sin overflow. El único `dir="rtl"` es el span
  aislado de la marca hebrea, no una dirección global.

## Corpus C

`C Hebrew textual quality = NOT CERTIFIED`. C tiene 180238 `U+FFFD` en chunks publicados;
no se usó como evidencia positiva de texto hebreo. Este gate no modificó C.

## Integridad post-freeze

`final-frozen-hash-check.json`: 9/9 archivos con SHA-256 idéntico al freeze.
`post-freeze mutations = 0`. No se corrigió nada después de observar el QA.

## Commit

Un único commit con allowlist explícita. Sin push. Los cambios sucios ajenos se preservan.

Nota de evidencia: `frontend-tests.txt` y `pnpm-check.txt` son capturas literales de salida
de comandos. Se normalizó únicamente su whitespace (espacio final y línea en blanco al EOF)
para que `git diff --cached --check` quede limpio; no se alteró ninguna línea de contenido.

## Conclusión

```text
HEBREW_RTL_RENDERING = PASS
NIQQUD_BASE_ATTACHMENT = PASS
PRESENTATION_FORMS_ISOLATION = PASS
GEMATRIA_EQUATION_DIRECTION = PASS
MOBILE_390x844 = PASS
DESKTOP = PASS
A_P187 = PASS
B_P416 = PASS
C_HEBREW_TEXT_CERTIFIED = NO
```
