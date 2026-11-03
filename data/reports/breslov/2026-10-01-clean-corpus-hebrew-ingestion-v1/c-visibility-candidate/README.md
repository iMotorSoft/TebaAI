# Likutey Halajot — visibilidad real, candidato aislado

## A. Veredicto

**LIKUTEY_HALAJOT_VISIBLE_EXTRACTION_BLOCKED**.
`READY_FOR_C_REINGEST`: NO. Ambos gates C/integral permanecen abiertos.
Esta fase implementa y prueba un filtro de traces aislado, no un fix canónico
ni una reingesta. No se satisface todavía el objetivo final del usuario.

## B. Primera capa incorrecta / causa raíz

FIRST_BAD_STAGE: extracción PyMuPDF (get_text/rawdict/texttrace) sin resolver
oclusiones posteriores. ROOT_CAUSE: el PDF conserva objetos de texto bajo
rectángulos blancos; presencia textual no implica visibilidad. Después,
PyMuPDF4LLM transforma ese contenido en Markdown. Es anterior al frontend.
C tiene además fuentes CID sin ToUnicode y problemas independientes de orden
lógico/niqqud. La recuperación Unicode existente sigue siendo candidata.

Hallazgo adicional: un seqno puede corresponder a varios traces. Sus bbox
métricos no son bbox de tinta; get_bboxlog devuelve el envelope de la operación
completa. No se puede borrar una operación compartida solo por cubrir un run.
El converter también cambia métricas globales de PyMuPDF (small_glyph_heights);
la auditoría termina toda la clasificación y captura raw antes de invocarlo.
El emparejamiento histórico usa página + seqno + font + glyph IDs, no igualdad
frágil de floats. Se emparejaron los 671 runs, sin depender de strings dañados.

## C. Regla / implementación candidata

`backend/modules/library/pdf_text_visibility.py`:
- solo path rectangular simple relleno blanco RGB exacto, opacity=1;
- seqno del rectángulo estrictamente posterior al texto;
- extended drawings level=0 y sin capa opcional; clips/grupos no se infieren
  desde sus bounding boxes;
- FULL containment de bbox de trace **y** envelope de tinta de la operación;
- NO/PARTIAL overlap no elimina runs; se registra área intersectada/área del
  trace para medición, sin threshold arbitrario;
- guard adicional de compositing: masks o blending no Normal en el documento
  impiden exclusión. En C se observaron 11 objetos con BM=Normal, SMask=None;
- 530 clip paths, cero transparency groups reportados por extended drawings.
  Esto no equivale a implementar ni validar todo el modelo gráfico PDF;
- retained traces preservados literalmente: mismo orden, chars, glyph IDs,
  espacios y combinantes. No reverse, normalización ni redacciones.

La exclusión opera únicamente sobre fixtures de texttrace. No hay Markdown
filtrado conectado a ingesta. Una redacción geométrica se descartó como atajo:
puede borrar también la traducción visible posterior en el mismo bbox.
La guardia de compositing es conservadora y no interpreta cada graphics state.
La revisión visual y el manejo de los 286 casos compartidos siguen pendientes.

## D. Runs

| Métrica | Resultado |
|---|---:|
| Conocidos antes | 671 |
| Conocidos emparejados | 671 |
| Cobertura demostrada por regla conservadora | 385 |
| Excluidos en fixture de traces | 385 |
| Conocidos pendientes, retenidos | 286 |
| Otros overlaps parciales registrados | 387 |
| Exclusiones en pipeline persistido | 0 |
| Falsos positivos visibles | NO CERTIFICADO |

NO afirmar remaining hidden=0 ni false positives=0. Los 387 overlaps parciales
no son necesariamente texto parcialmente invisible: algunos pertenecen a
operaciones que cruzan fondos o regiones decorativas. Requieren análisis.

## E. Reingesta

NO ejecutada. Título: Likutey Halajot — Interior Final.
SHA: `440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a`.
SHA antes/después idéntico. Nuevos document_id/job_id: ninguno.
Páginas fuente: 284. Chunks/vectors/missing/orphans/duplicates/publication:
no se volvieron a medir; el snapshot anterior no certifica este candidato.
PG/Milvus no consultados ni modificados durante esta fase.
Corpus previo informado: 3 docs / 896 páginas / 2146 chunks y vectores,
no revalidado en vivo en esta fase.

## F. Hebreo / muestras

`audit.json` incluye bbox, texto, glyph IDs, seqno, fill, opacity, overlap,
veredicto y categorías representativas: hebreo puro, niqqud, números,
puntuación, referencias/encabezados candidatos, FULL/PARTIAL. No se encontró
una muestra mixed RTL/LTR en los overlaps seleccionados; no inventar cobertura.

Páginas 1/2/13/37/41/55/56/63/143: screenshot PDF, raw, filtered traces,
Markdown Unicode candidato **sin filtro**. `filtered-traces.txt` NO es texto
canónico lógico ni se usa como extractor principal. El canónico filtrado
permanece NOT_IMPLEMENTED.

Página 55 revisada contra screenshot: las dos franjas de títulos visibles no
contienen las cadenas de reemplazo que incluye el Markdown. La región hebrea
visible es legible en PDF, pero raw/Markdown candidato no conservan orden
lógico correcto; Markdown interpone espacios y marcas. Esto bloquea Unicode,
logical order y niqqud aunque mejoren los conteos de visibilidad.
Persisten U+FFFD en retained traces de páginas 55/56/143 (4/2/4 caracteres).
No fueron borrados por ser U+FFFD.

Normalization: las nueve muestras se miden en audit.json. No se cambió la
normalización global. Un test de identidad de traces con `שָׁלוֹם (16:1), ABC 37`
prueba que el filtro no altera bases/combinantes/números/puntuación, pero no
certifica la recuperación del hebreo real de C.

Pure Hebrew / niqqud / mixed RTL-LTR reales: **BLOCKED**.
Numbers/punctuation: PASS unitario de preservación; gate real no certificado.
Characters reversed / words broken / synthetic spaces / hidden text visible:
no se puede declarar NO para C final, puesto que aún no existe tal resultado.

## G–H. UI / consultas

Desktop, mobile, answer, citation, evidence, preview: NO revalidados con C
corregido. Literal, semantic, Hebrew, numbers/references, negative grounding:
NO ejecutados en esta fase. Sin cambios CSS/RTL/bdi/frontend.

## I. Regresión

A / PDF 187 y B / PDF 416: los tests existentes de geometría y entrypoints
sobre fuentes locales pasan; no se reingestaron ni se hizo nueva QA UI.
No se cambió su extractor activo. Esto no equivale a regresión integral.

## J. Tests

Backend focalizado: **91 PASS**, incluidos **26 tests nuevos** de visibilidad,
orden de pintura, overlap, opacity, compositing, texto posterior preservado y
bases/combinantes/números/puntuación sin transformaciones.
Frontend relevante: **35 PASS**. Check: **PASS**, 0 errores/9 hints existentes.
Build: **PASS**, 9 páginas. Diff-check: **PASS**.
No cambios LAT ni referencias @lat; lat check no requerido.

Reproducción (desde backend):

```sh
uv run python ../../data/reports/breslov/2026-10-01-clean-corpus-hebrew-ingestion-v1/audit-c-visible-extraction.py
uv run pytest tests/test_pdf_text_visibility.py tests/test_pdf_font_unicode.py tests/test_pdf_hebrew_fidelity.py tests/test_page_first_pipeline.py tests/test_page_first_utf8_preview.py tests/test_dev_content_reset.py
```

## K–L. Git / PROD

Branch: `feature/console-backend-core`.
HEAD inicial/final: `1fa9290bdc7840e7277a998aa3ca66345c6080ee`.
Nuevos: pdf_text_visibility.py, test_pdf_text_visibility.py, script auditoría
y evidencia en esta carpeta. Status actualizado sin pisar cambios previos.
Cambios de trabajo anteriores preservados, no consolidados.
Commit: NO. Push: NO. Production modified: NO. Deploy/reset/ingesta: NO.

## Próximo paso concreto / riesgos

Resolver límites de tinta por glifo/objeto para los 286 candidatos retenidos,
y aplicar la exclusión *antes* del converter sin tocar texto posterior.
Después resolver orden lógico/asociación niqqud y añadir goldens reales
verificados contra las nueve capturas. Solo tras todo el gate pre-reingesta:
reemplazo soportado de C por UI una vez, reconciliación y QA Playwright.
Riesgos abiertos: contenido visible eliminado por filtros geométricos,
operaciones compartidas, marcas sobre bases incorrectas y fragmentación del
converter. Nada de esta fase autoriza cerrar el gate C ni el integral.
