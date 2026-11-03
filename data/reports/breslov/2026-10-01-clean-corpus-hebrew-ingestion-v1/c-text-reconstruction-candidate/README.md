# C — reconstrucción textual aislada, evidencia y límites

## A. Veredicto

**TEXT_RECONSTRUCTION_BLOCKED**.
`TEBAAI_BRESLOV_LIKUTEY_HALAJOT_TEXT_RECONSTRUCTION_V1_BLOCKED`.
`READY_FOR_C_REINGEST = NO`.
Los gates de visibilidad e ingesta integral permanecen abiertos. Esto es un
experimento offline, NO un extractor alternativo autorizado ni integración.

## B–C. Visibilidad / familias reales

Filtro anterior congelado: no se cambió `pdf_text_visibility.py`.
671 históricos; 385 suprimidos por la regla anterior; 286 retenidos antes y
después. Refinamiento: **0 supresiones nuevas**. Falsos positivos visibles
certificados: **NO DETERMINADO**, nunca confundirlo con cero.

| Pattern | Count | Suppress | Retain | Still ambiguous |
|---|---:|---:|---:|---:|
| Full trace, tinta de operación compartida no contenida, un overlay | 197 | 0 | 197 | 197 |
| Mismo límite, un overlay full + overlays parciales adicionales | 89 | 0 | 89 | 89 |
| Total | 286 | 0 | 286 | 286 |

Los 89 incluyen 84 con 4 overlays, 3 con 5 y 2 con 3. Los 286 tienen un
rectángulo blanco opaco posterior que contiene el trace, pero ninguno contiene
la tinta completa de la operación. No sumar overlays para forzar una decisión.
`ambiguous-families.json` conserva identidad/página/geometría/evidencia por run.
No se atribuyen table backgrounds, clipping, máscaras ni draw-order incierto a
estos runs sin evidencia: esas categorías no aparecen en este registro
seleccionado por la regla. Esto no demuestra su ausencia en todo el PDF.

Se prepararon 40 muestras distribuidas entre PDF 13 y 275, incluyendo los dos
runs suprimidos cuyo Unicode contiene números, con crop + candidato + overlays.
Contacto visual: `suppression-contact-sheet.png`. Se observan reemplazos visibles
«Notas y Fuentes», «Likutey Halajot Explicado», «Halajá 1/2», «Diagramas».
No confundir esos reemplazos posteriores con los runs históricos suprimidos.
La hoja es consistente con la hipótesis de oclusión, pero **no certifica** la
identidad de glifos ocultos ni cero pérdidas en las 385 exclusiones.

Cobertura de categorías en el Unicode recuperado de los 385: hebreo=0,
marcas=0, números=2, referencias con ':'=0, bbox superior <70=0. Muchos valores
siguen U+FFFD: no inferir que originalmente no había hebreo/niqqud. La muestra
requerida por tipo de texto no queda certificada con este Unicode. Revisiones
individuales siguen `PENDING` en audit.json. Falta una comparación de render con
ablación exacta de operandos/glifos, sin redacción por bbox ni borrar reemplazos.

## D. Root cause — orden

First bad stage: `PyMuPDF get_texttrace`, antes del Markdown y del navegador.
Ejemplo PDF 55: seqno 0 devuelve `תוכלה` con x creciente 375.57→394.81;
las posiciones visibles requieren orden lógico `הלכות`. El encabezado ocupa
varios spans del mismo seqno. El seqno 13 incluye varias baselines: no invertir
el span entero ni tratar cada span como una línea.

Fix experimental: agrupar por seqno + baseline (tolerancia 0.04 em contra una
baseline fija); ordenar bases hebreas por x decreciente y Latin/números por x
creciente solo en líneas de un script; conservar espacios PDF explícitos. No
se insertan espacios. No reverse de strings/spans/líneas. No construir Unicode
mediante el bidi del navegador. Inputs mixtos, delimitadores espejados y U+FFFD
se conservan íntegros con diagnósticos: eso evita pérdidas, **no los corrige**.

La agrupación por seqno evita juntar operaciones distintas por proximidad
vertical, pero NO demuestra columnas/paragraphs dentro de una operación.
PDF 55 revela una primera mala etapa adicional de estructura: seqno de pintura
no es orden de lectura, y notas de columnas distintas comparten baseline.
El candidato conserva ese defecto explícitamente; no declarar estructura PASS.

## E. Niqqud

First bad stage: char-level texttrace tras recuperación CID candidata.
PDF 55, baseline 127.15: qamats x388.51 aparece antes de pe x385.51 y dentro de
su intervalo [385.51,391.57]; dagesh comparte x385.51 con pe. Son dos mecanismos
distintos, no «adjuntar todas las marcas al codepoint anterior».

Fix experimental: owner único por mismo origen (0.002 em), o posición
estrictamente dentro del bbox de base hebrea, con compatibilidad de baseline.
Empates/bordes/marcas sin owner: mantener secuencia original y diagnosticar.
El bbox de trace sigue siendo métrico: este criterio necesita validación de
más fuentes/holam/cantillation antes de ser una regla de ingesta.

Golden manual corto PDF 55: `וְזֶה פֵּרוּשׁ הַפָּסוּק`.
Output local: `וְזֶה פֵּרוּשׁ הַפָּסוּק `; bases/marcas correctas en este fragmento,
comparación por equivalencia NFD PASS. No se cambia NFC/NFD del output; se
registran input/output NFC/NFD por línea. La línea completa contiene una
referencia parentética aún sin resolver y el golden completo NO pasa.

## F–G. Reconstrucción y fixtures

Conservación de multiset de codepoints: PASS en las cinco páginas **retenidas
por A**. No equivale a probar que A conservó todo texto visible. Pruebas
sintéticas: hebreo, múltiples marcas, números/puntuación LTR, incertidumbre
RTL/LTR, baseline, operaciones, espacios reales y permutación geométrica.
Los casos mixtos prueban retención/diagnóstico, NO una reparación material.

| PDF | Categoría | Golden local | Orden/niqqud página | Resultado |
|---|---|---|---|---|
| 2 | Portada compleja / históricos | ליקוטי / הלכות PASS | Títulos acotados; layout sin certificar | BLOCKED página |
| 41 | Niqqud / referencias / notas en columnas | Likutey Halajot Explicado PASS | 8 líneas unresolved | BLOCKED |
| 55 | Hidden / niqqud / Salmos 16:1 / orden | Referencia PASS; fragmento niqqud equivalente PASS | 4 líneas unresolved; párrafos/celdas erróneos | BLOCKED |
| 56 | Niqqud / heading / notas 35–36 | MELODÍAS Y PLEGARIAS PASS | 4 líneas unresolved | BLOCKED |
| 143 | Niqqud / referencias mixtas / columnas | Likutey Halajot Explicado PASS | 10 líneas unresolved | BLOCKED |

Fixtures reales: `backend/tests/fixtures/likutey_halajot_reconstruction_v1.json`.
Por página: PDF render, rawdict/spans/chars/orígenes/bbox, líneas candidatas,
visibility verdicts, Markdown diagnóstico y viewer local. La extracción actual
previa está en `../c-visibility-candidate/page-*-candidate-unfiltered.md`.
El Markdown nuevo es filtrado/reconstruido, pero deliberadamente **no canónico**:
blank lines por baseline/operación no son párrafos. No usarlo para ingesta.

Estado material del libro (no de un test local): Unicode FAIL; logical order
FAIL; niqqud FAIL; numbers FAIL/no certificado mixto; punctuation FAIL;
spacing FAIL/no certificado integral; paragraph/line structure FAIL.

## H. Visual desktop / mobile

Chromium offline `file://`, sin app/API/login/servicios. 1440×1000 y 390×844;
5 páginas × 2 viewports: 10 checks de identidad DOM PASS, overflow horizontal
0, page/console errors 0, peticiones HTTP/5xx no aplicables. Capturas iniciales
y región hebrea. Primera captura fullPage falló; se repitió reproduciblemente
con capturas de viewport + scroll a hebreo, sin ocultar el fallo.

Desktop candidate: FAIL (fidelidad). Mobile candidate: FAIL (fidelidad).
PDF 55: hebreo va después del cuerpo español y una línea con paréntesis sigue
corrupta; las notas fusionan columnas. `<bdi dir="auto">` aísla presentación,
no arregla estos strings ni la estructura. No se modificó CSS global/frontend.
Characters reversed: YES en fallback no resuelto. Broken words/detached niqqud:
no descartados en esas líneas. Synthetic spaces: ninguno añadido por B; no se
certifica el converter. Incorrect number joins: no descartados integralmente.
Visible text accidentally removed: NO CERTIFICADO (no afirmar NO).

## I. Tests / reproducción

Backend focalizado: **118 PASS** (baseline 91 + 27 nuevos).
Frontend focalizado: **35 PASS**; suite frontend adicional: **128 PASS**.
Check: PASS, 0 errores / 9 hints existentes. Build: PASS, 9 páginas.
Diff-check: PASS. No LAT/@lat cambiado; lat check no requerido.
No suite backend completa ni E2E autenticado ni escrituras ejecutados.

Desde backend:

```sh
uv run python ../../data/reports/breslov/2026-10-01-clean-corpus-hebrew-ingestion-v1/audit-c-text-reconstruction.py
uv run pytest tests/test_pdf_text_visibility.py tests/test_pdf_font_unicode.py tests/test_pdf_hebrew_fidelity.py tests/test_page_first_pipeline.py tests/test_page_first_utf8_preview.py tests/test_dev_content_reset.py tests/test_pdf_text_reconstruction.py tests/test_pdf_visibility_conservative_regression.py
```

Desde raíz:

```sh
node data/reports/breslov/2026-10-01-clean-corpus-hebrew-ingestion-v1/validate-c-text-candidate.cjs
```

## J–L. Corpus, Git, producción

Corpus snapshot informado: documents=3, pages=896, chunks=2146, vectors=2146.
NO revalidado en vivo: no conexión PG/Milvus. Reset NO; reingest NO.
Fuente PDF: SHA-256 antes/después
`440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a`.

Branch: `feature/console-backend-core`.
HEAD inicial/final: `1fa9290bdc7840e7277a998aa3ca66345c6080ee`.
Cambios anteriores del worktree preservados. Nuevos: módulo experimental B,
dos archivos de tests, fixture real, scripts offline y esta evidencia.
Status actualizado por inserción acotada. Pipeline canónico no modificado.
Commit NO; push NO; production modified NO.

## Decisión / siguiente paso

¿Visibilidad suficientemente certificada? **NO**.
¿Demostrado que no elimina texto visible? **NO**.
¿Orden hebreo correcto integralmente? **NO**.
¿Niqqud correctamente asociado integralmente? **NO** (sí fragmento acotado).
¿Números/puntuación correctos integralmente? **NO**.
¿Markdown corresponde fielmente al PDF? **NO**.
¿Lectura correcta desktop? **NO**. ¿Mobile? **NO**.
¿Listos para reemplazar C desde UI? **NO**.

Próximo loop: fixtures cortos para línea hebrea + referencia parentética,
segmentación RTL/LTR explícita sin reversa global, y bloques/columnas respaldados
por rawdict/geometría; luego resolver U+FFFD con evidencia del programa de font.
Certificar A mediante ablación exacta de operaciones y comparación de render,
no mediante borrar rectángulos ni coincidencia textual dañada. Conservar los
286 mientras no exista prueba mayor. Riesgo principal: mejorar apariencia
sin corregir texto lógico, asociaciones o semántica. **No hay PASS ni permiso
de reingesta.**
