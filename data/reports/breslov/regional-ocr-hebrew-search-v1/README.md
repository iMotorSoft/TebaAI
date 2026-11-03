# Regional OCR fallback + Hebrew unpointed search — V1

## Resultado

**OCR: MORE_EVIDENCE_REQUIRED / BLOCKED.** No motor OCR hebreo ejecutable/verificado en el entorno inspeccionado; no se instaló ni se invocó API. No existe salida OCR para declarar mejora, precisión, search/display PASS o recomendar integración.

**SEARCH: HEBREW_UNPOINTED_SEARCH_BLOCKED** como gate completo. Equivalencia **por niqqud y mismas letras base** PASS offline reutilizando helpers existentes; display original intacto. El ejemplo solicitado tiene una י adicional en la query y no es equivalencia solo por niqqud. No se alteraron consonantes para forzar PASS. No retrieval vivo ni garantía universal de cero false positives. [Contrato y próximos pasos](recommendation.md).

La auditoría histórica sigue `TEBAAI_BRESLOV_HISTORICAL_EXTRACTION_SOLUTION_AUDIT_V1_PASS`; no se reinvestigaron las11 áreas. `READY_FOR_C_REINGEST=NO`.

| Gate | Resultado |
|---|---|
| TEBAAI_BRESLOV_PAGE167_HYBRID_EXTRACTION_BENCHMARK_V1 | BLOCKED (comparadores offline completos; falta OCR) |
| TEBAAI_BRESLOV_REGIONAL_OCR_FALLBACK_EVALUATION_V1 | BLOCKED |
| TEBAAI_BRESLOV_HEBREW_UNPOINTED_SEARCH_V1_PASS | NO EMITIDO; contratos focalizados offline pasan, gate completo bloqueado |

## Fuente / evidencia

PDF original SHA-256 `440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a`, 284 páginas. Hash verificado antes del replay. `LIKUTEY_HALAJOT_COMPLEX_PAGE_GOLDEN_V1`: física167 / impresa149.

- `historical-ocr-audit.md`, `historical-ocr-search.txt`, `historical-ocr-git.txt`: búsqueda histórica acotada. Candidatos de zonas IA históricos, pero clasifican texto nativo, no reconocen raster.
- `engine-inventory.json`: ejecutables/packages disponibles, versión, Hebrew support verificado o pendiente, coste/latencia no medidos, dependencias/privacy. No confundir rasterizador con OCR.
- `page-{41,55,56,143,167}.png`: renders originales 130dpi revisados visualmente; no defecto fuente obvio en el muestreo. Revisión por asistente, no signoff editorial humano.
- `page167-regions.json`, `page167-{region}.png`: clips originales220dpi, bbox en PDF points, regiones A/B/C/D/E y E izquierda/derecha, block IDs. Viabilidad de render + provenance demostrada; mapeo word-level OCR aún no probado.
- `manual-golden.json`, `page167-hebrew-detail.png`: heading,3 líneas base, fragmento pointed, número, referencia parentética y control español; no transcripción completa. Bbox de fragmentos son ventanas aproximadas de revisión, no anotaciones character-level.
- `native-historical-reconstruction.json`: extracción con FLAGS reales de layout, `likutey_layout_parser.parse_page` histórico y candidato actual font-map + visibilidad conservadora + reconstrucción. Font maps solo en documento en memoria; original nunca guardado/modificado.
- `page167-comparison.json`: comparación verificable por fragmentos/region, búsqueda de fragmentos en orden normalizado; NO precisión de página completa ni métricas OCR.
- `ocr-results.json`: sin runs, métricas null; regiones A/B167 seleccionadas para futuro benchmark y páginas adicionales justificadas.
- `hebrew-search-normalization.json`: dos queries con las mismas letras base → mismo ID offline/display intacto; ejemplo con י extra negativo y colisión punctuation documentada.
- `source-pdf-errors.json`: ninguna anomalía visual obvia encontrada en las5 páginas; no certificado editorial de todo el libro.
- `benchmark_offline.py`, `test_offline_contracts.py`, `tests.txt`: replay y validación aislados. No importación/ejecución de workers/gateways/ingestores SQL.

PyMuPDF/PyMuPDF4LLM1.27.2.3; dependencia layout vigente, no reproducción de un entorno histórico. Native U+FFFD por página con FLAGS actuales:41=809,55=633,56=1047,143=870,167=933. Conteos incluyen texto oculto; no son tasas de error visual ni OCR.

## Tabla final por región

`NO MEDIDO` no equivale a FAIL. Search/display fit refiere al texto candidato completo de la región, salvo fragmentos expresamente acotados.

| Page / Region | Native | Historical | Reconstruction | OCR | Search fit | Display fit |
|---|---|---|---|---|---|---|
| 41 / Hebrew | FAIL Unicode | no certificado / inseguro | no certificado; diagnóstico disponible | NO MEDIDO | no certificado | NO |
| 55 / broken header + Hebrew | FAIL Unicode | FAIL Unicode; folio preservado | PARTIAL; sin certificado integral | NO MEDIDO | parcial, no aprobación | NO |
| 56 / Hebrew | FAIL Unicode | inseguro | PARTIAL; sin certificado integral | NO MEDIDO | no certificado | NO |
| 56 / notas35–36 | texto raw nativo útil; Markdown regresión ya auditada | inseguro global | sin certificado estructural | NO NECESARIO para regresión Markdown | preservar native; reparar estructura | native + contrato pendiente |
| 143 / Hebrew | FAIL Unicode | no certificado / inseguro | PARTIAL; mixed refs pendientes | NO MEDIDO | no certificado | NO |
| 167 / A header | FAIL Hebrew;149 correcto | FAIL Hebrew;149 correcto | PARTIAL: heading/149 pasan; halajá contaminada | NO MEDIDO | solo heading/folio comprobados | NO región completa |
| 167 / B Hebrew main | FAIL | FAIL | PARTIAL:3 líneas base pasan; pointed/mixed ref en orden incorrecto | NO MEDIDO | solo fragmentos certificados offline | NO región completa |
| 167 / C transición | caption visible correcto + texto oculto corrupto | caption visible + texto oculto | caption visible recuperado | NO NECESARIO | NATIVE visible con provenance | NATIVE visible; filtro pendiente |
| 167 / D español | PASS control visible | PASS control visible | texto útil; superscript/orden integral no certificado | NO NECESARIO | NATIVE | NATIVE |
| 167 / E título notas | visible correcto + texto oculto corrupto | visible + texto oculto | título visible recuperado | NO NECESARIO | NATIVE visible | NATIVE visible; filtro pendiente |
| 167 / E notas izquierda | PASS texto/bbox nativo | FAIL: pseudohebreo español | FAIL: mezcla columnas | NO MEDIDO / no reemplazo | NATIVE por región | NATIVE |
| 167 / E notas derecha | PASS texto/bbox nativo | texto útil; orden derecha antes de izquierda incorrecto | FAIL: mezcla columnas | NO MEDIDO / no reemplazo | NATIVE por región | NATIVE |

Las conclusiones parciales41/55/56/143 no certifican nuevos goldens completos: se registró native/historical/reconstruction y se revisó el render; el golden corto nuevo es167 exclusivamente. OCR solo donde haya Unicode roto. No se reabrió printed-page55 ni el contrato Markdown56.

### Hallazgo regional decisivo sin OCR

Native167 conserva notas en bloques29/30 con bbox separados (izquierda x56.7–245.4; derecha x255.4–444.1). El candidato reconstruye ambos bajo seqno29/baseline común: `60 Ver ... 3.se refrena ...`, `61 Ver §1 ... I, 22:1)...`. **FAIL de columnas**; no se acepta ese output como página ni search. Su geometría/header recuperan heading/folio y3 líneas Hebrew con orden correcto, pero la línea de `אור הפנים` y paréntesis se conserva invertida con diagnóstico fail-closed. Así, no es alternativa completa certificada ni baseline OCR golden.

## Página167 — respuesta obligatoria

```text
PDF visual good: YES (alcance muestreado, revisión raster)
Native Hebrew extraction: FAIL
Historical decoder: FAIL
Experimental reconstruction: PARTIAL
OCR base letters: NOT_EVALUATED
OCR word order: NOT_EVALUATED
OCR numbers: NOT_EVALUATED
OCR punctuation: NOT_EVALUATED
OCR niqqud: NOT_EVALUATED
OCR suitable for search: NOT_EVALUATED
OCR suitable for display: NOT_EVALUATED
Recommended extraction source: UNRESOLVED (Hebrew completo)
```

No se rellenan PASS/FAIL o YES/NO ficticios cuando falta OCR. Por tipo de región: **NATIVE español y notas**, reconstrucción útil solo como candidato de ciertos fragmentos, **UNRESOLVED Hebrew/mixed completo**; ninguna elección OCR/HYBRID aprobada.

## Respuestas finales

| Pregunta | Respuesta |
|---|---|
| ¿Existió OCR histórico relevante? | PARTIAL: experimentos de zonas/candidatos, no benchmark OCR raster |
| ¿Existe algo reutilizable? | PARTIAL: provenance/geometry/search; no motor OCR probado |
| ¿Página167 tiene render visual correcto? | YES, muestreo visible legible |
| ¿Su embedded Hebrew es confiable? | NO |
| ¿OCR regional mejora letras base? | NO DETERMINADO, sin motor |
| ¿OCR mejora logical order? | NO DETERMINADO |
| ¿OCR suficientemente bueno para búsqueda? | NO DETERMINADO |
| ¿OCR suficientemente bueno para display? | NO DETERMINADO |
| ¿Búsqueda hebrea debe requerir niqqud? | NO |
| ¿Eliminar niqqud del canonical text? | NO |
| ¿Mantener search representation sin niqqud? | YES, derivada; adaptar capa existente |
| ¿Conviene OCR regional? | NO DETERMINADO; benchmark aún necesario |
| ¿Conviene OCR full-page? | NO recomendado como solución; ventaja no demostrada |
| ¿Listos para integrar? | NO |

## Validaciones / límites / cierre Git

87 tests PASS:52 lexical existentes +6 LMII layout existentes +14 ligaduras existentes +15 casos adicionales offline que reutilizan helpers. Comprueban native good stays native, broken native pide benchmark, SOURCE_PDF_ERROR permanece, unknown no elección silenciosa, regresión estructural no OCR, derivación search/display intacto, números/límites/orden/mixed, misma base misma evidencia y negativas. No tests de precisión OCR porque no hay OCR. El intento inicial de igualdad con el ejemplo solicitado falló; se conservó como caso negativo correcto y se añadió la equivalencia de mismas bases, no se cambió código canónico.

Reproducir desde `SrvRestAstroLS_v1/backend`:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python ../../data/reports/breslov/regional-ocr-hebrew-search-v1/benchmark_offline.py
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider tests/test_hebrew_lexical_normalizer.py tests/test_likutey_moharan_ii_layout.py tests/test_pdf_ligature_normalization.py ../../data/reports/breslov/regional-ocr-hebrew-search-v1/test_offline_contracts.py -q
```

`git diff --check` PASS; scripts/reportes/JSON/diff final revisados. No LAT/@lat/frontend cambios: lat check/pnpm/E2E no aplican. No full suite ni retrieval vivo. Cambios de esta fase **solo archivos nuevos dentro de este directorio**. Worktree previo backend/frontend/status/experimentos conservado, no adjudicado a esta fase.

```text
branch: feature/console-backend-core
HEAD initial: 1fa9290bdc7840e7277a998aa3ca66345c6080ee
HEAD final:   1fa9290bdc7840e7277a998aa3ca66345c6080ee
canonical code changed: NO
CANONICAL_PIPELINE_MODIFIED: NO
commit: NO
push: NO
Production modified: NO
RESET: NO
REINGEST: NO
POSTGRES WRITES: NO
MILVUS WRITES: NO
PG/Milvus/LiteLLM connections: NO
service management / new dependencies: NO
READY_FOR_C_REINGEST: NO
```

Impacto: delimita regiones nativas aprovechables, controles y bloqueos; no cambia el producto. Riesgos: aprobar OCR sin medirlo, confundir helper offline con retrieval real, niqqud equivalence con plene/defective spelling, o aceptar texto con columnas mezcladas. Próximo paso: autorización de motor OCR hebreo y aclaración del contrato ortográfico para el ejemplo con י adicional; después benchmark comparativo, todavía antes del worker/reingesta.
