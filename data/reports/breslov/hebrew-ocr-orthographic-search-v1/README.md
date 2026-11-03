# Hebrew regional OCR real + orthographic search variants V1

## Resultado

| Gate | Estado / alcance |
|---|---|
| TEBAAI_BRESLOV_HEBREW_REGIONAL_OCR_REAL_V1 | **PASS_NOT_USEFUL** para fallback automático del cuerpo principal con engine/pack/config probados; rescate parcial real medido |
| TEBAAI_BRESLOV_HEBREW_ORTHOGRAPHIC_SEARCH_VARIANTS_V1 | **BLOCKED**: mecanismo offline demostrado, guardas anotadas sin holdout ni validación full-corpus |
| READY_FOR_C_REINGEST | **NO** |

42 ejecuciones OCR reales, 3 páginas (167/55/143), pocas regiones reproducibles; no página completa. **97.10–98.55% de letras base en las3 líneas principales167 NO implica SEARCH PASS:** hay palabras fusionadas y letras materialmente incorrectas. Sí existen fragmentos SEARCH útiles sin niqqud perfecto; no se aprobó DISPLAY del cuerpo.

Search: 17 casos reales/atestiguados; exact1/11 positivos, sin-niqqud3/11, candidatos controlados con guarda anotada11/11; negativos rechazados6/6. Embeddings reales:10/11 positivos top1,11/11 top3; negativos5/6 top1,6/6 top3. El focal se recupera lexicalmente por candidato ortográfico y semánticamente top1, sin modificar source/query. No convertir esos resultados de desarrollo en garantía lingüística o equivalencia textual.

[Decisión y mínima arquitectura futura](recommendation.md) · [precisión y riesgos](false-positive-analysis.md) · [resumen reproducible](findings.json)

## Fuente / aislamiento

PDF original: `LIKUTEY HALAJOT (Interior Final).pdf`, SHA-256 `440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a`; hash comprobado antes de cada replay. Página167 física /149 impresa visual **GOOD**, fuente legible; no SOURCE_PDF_ERROR observado en regiones revisadas. Sólo lectura; no PDF copiado ni guardado de nuevo.

No se repitió la auditoría histórica: baseline reutilizado de `../regional-ocr-hebrew-search-v1/`. Comparadores nativos actuales con FLAGS de layout; historical/reconstruction desde evidencia previa con mismo SHA. Los comparadores overlapping-block conservan contexto adicional: **no atribuirles precisión character-level de un crop**; se evalúa presencia de fragmentos/defectos conocidos. El nativo y OCR sí disponen de crop/fixture comunes.

Motor: Tesseract5.3.4 / Leptonica1.82.0, OEM1, PSM6; PSM7 sólo en fixtures de línea. Traineddata heb/spa packaged `1:4.1.0-2`, paths/SHA exactos en [ocr-environment.json](ocr-environment.json). Instalación mínima user-local DEV detallada en [ocr-installation.md](ocr-installation.md), sin sudo, servicios persistentes ni paquetes de producción.

Render RGB raw300/400dpi, rotación0, bboxes en puntos PDF sin rotar/top-left; sin filtros, binarización ni tuning adicional. El único postproceso OCR elimina controles Unicode Cf (bidi), **no invierte ni reordena**. Segundo motor/API OCR: NOT TESTED.

Corrección de anotaciones antes del benchmark final: los bboxes previos eran aproximados; inspección visible detectó crops que no incluían el fragmento pointed/referencia completo o cortaban heading. Se ampliaron heading a x360, referencia a x150, pointed a x300–348 y cuerpo hasta y214 para excluir una línea parcial. No se cambió texto para hacer pasar OCR. Todos los resultados finales corresponden a los bboxes corregidos de `ocr-goldens.json`.

## Golden / métricas

`ocr-goldens.json`: heading+folio,3 líneas base, referencia/puntuación, fragmento pointed167; heading/folio55; línea143. Revisión por asistente contra raster original, no embedded ni OCR; signoff editorial humano pendiente. Goldens base-only no puntúan marks. Header lógico de lectura: folio a la derecha, luego título. Contexto español/columnas sin transcripción integral tiene métricas null, no PASS inventado.

Definiciones completas en `ocr-comparison.json` y tests:

- Base letters: `max(0,1-edit_distance/gold_base_count)`, penaliza inserciones.
- Word order accuracy: proporción de tokens exactos alineados en secuencia, **proxy conservador también afectado por reconocimiento**, no porcentaje puro de orden. Orden lógico real revisado aparte: PASS en líneas Hebrew, sin reverse.
- Boundaries: F1 de espacios proyectados al golden por alineación de caracteres base.
- Numbers/punctuation: edit accuracy de sus secuencias; null si ausentes del golden.
- Niqqud: edit accuracy de secuencia NFD de marks **sólo en fragmento pointed**; no certificado de anclaje editorial de todos los marks.
- Unexpected: caracteres fuera de script/clases esperadas; replacement: U+FFFD exacto. Detectar un alfabeto válido NO detecta palabras inventadas.

Criterio experimental conservador: ≥99% letras y límites, orden lógico conservado, ningún target material corrupto/fusionado. DISPLAY requiere además marks/puntuación/números fieles. No es detector productivo calibrado.

### Tres líneas167 — configuraciones fijas, sin elegir lo mejor por línea

| DPI / PSM | Letras base (138) | Edits | Boundaries F1 por línea | Ordered exact tokens por línea | Unexpected / U+FFFD |
|---|---|---|---|---|---|
| 300 /6 | 97.10% |4| .909 / .938 / .889 | .917 / .778 / .667 |0 /0|
| 300 /7 | 95.65% |6| .909 / .938 / .667 | .917 / .778 / .667 |0 /0|
| 400 /6 | 97.10% |4| 1 / .938 / .889 | .917 / .778 / .500 |0 /0|
| 400 /7 | 98.55% |2| 1 / .938 / .889 | .917 / .778 / .667 |1 /0 (`=`)|

Puntuación por esas líneas:100% /40% /100% en cada configuración. Entre otros: `כנ"ל → פנ"ל`, `בחינת → חינת`, maqaf convertido en י, palabras fusionadas. 400dpi no mejora uniformemente. No sumar este promedio con header/fragmento overlapping para inflar precisión.

Fragmento `אוֹר הַפָּנִים,`:8/8 letras, orden/límites/puntuación100%;4/5 marks (80%, falta holam),300/400dpi. Header167 y55:11/11 letras del título, pero149→9 y37→7 (number_accuracy=0), no aptos como folios OCR. Línea143:300dpi36/37,400dpi37/37 letras;400dpi límites/orden/puntuación100%; niqqud no certificado.

### Tabla OCR final (SEARCH/DISPLAY refieren al OCR salvo nota explícita)

| Page | Region | Native | Historical | Reconstruction | OCR | Search usable | Display usable |
|---|---|---|---|---|---|---|---|
|167|A heading/folio|Hebrew FAIL,149 correcto|Hebrew FAIL|heading+folio recuperados|title100%,149→9|sólo título; HYBRID_BEST|NO región completa|
|167|B main /3 líneas|FAIL|FAIL|PARTIAL;3 goldens base recuperados, no cuerpo completo|97.10–98.55%, fusiones|NO cuerpo; UNRESOLVED|NO|
|167|C reference line|FAIL|FAIL|orden invertido conocido|46/48 letras, puntuación100%|NO línea completa; UNRESOLVED|NO|
|167|C pointed fragment|FAIL|FAIL|orden invertido|8/8 letras,4/5 marks|YES; OCR_BEST_FOR_SEARCH|NO|
|167|D Spanish|PASS, preferido|control útil|no ventaja necesaria|daña superscripts|NATIVE_BEST; no disparar OCR|preferir native|
|167|E notes left/right|PASS con bbox separados|izquierda pseudo-Hebrew / orden inadecuado|mezcla columnas|separadas útiles; juntas OCR_LAYOUT_FAIL|NATIVE_BEST|preferir native|
|55|A affected header|Hebrew FAIL,37 correcto|Hebrew FAIL|título+37 recuperados|11/11 letras,37→7|título sí; RECONSTRUCTION_BEST global|NO header OCR completo|
|143|selected line|FAIL|FAIL|línea conservada|400dpi37/37 letras|YES; RECONSTRUCTION_BEST también|NO niqqud certificado|

Página55 exclusivamente header afectado Cc→U+FFFD; mejora OCR **YES frente native/historical**, **NO mejora frente reconstrucción** ya útil. No se OCRizó su cuerpo ni se disfrazó un problema de folio. Página56 NO OCR; notas35/36 permanecen regresión Markdown/contrato.

Español correcto167 permanece native: OCR real de controles no autoriza seleccionarlo. Notas combinadas PSM6 fusionan `60 Ver ... 3. se refrena ...`, reproduciendo un FAIL de layout; no invalida automáticamente el fragmento Hebrew superior.

## Search — variantes, no corrección

[Historia dirigida](orthographic-history.md). Reutilizado `normalize_hebrew_search`, sin cambiarlo. Separación estable canonical/display, representación derivada y query expansion. `search_benchmark.py` conserva original_query, candidatos/rule_id y hash del canonical; nada se escribe al corpus.

**Guardas anotadas**: el prototipo exige lexema confirmado por revisión/contexto. No implementa un desambiguador real; las entradas fueron seleccionadas del mismo set, no hay holdout. Sin esa guarda el candidato focal no se acepta como match. No prefijos/stems automáticos ni borrar י/ו. 8 entradas dirigidas de desarrollo, NO diccionario de equivalencias.

### Tabla SEARCH final

`Variant=YES` = aceptación offline con guarda anotada. Semantic indica rank del source target en los15 snippets únicos; no retrieval vivo de corpus. Las filas marcadas base-only en fixtures son transcripciones manuales de letras visibles, no snapshots completos pointed ni texto apto para DISPLAY/citas: se conserva el raster original como evidencia. No se inventó niqqud para aparentar un canonical exacto. Los tres controles y el focal sí preservan sus fragmentos pointed; ningún texto del corpus se modificó.

| Query | Canonical source | Exact | No-niqqud | Variant | Semantic | Expected safest match |
|---|---|---|---|---|---|---|
|פירוש|פֵּרוּשׁ|NO|NO|YES|rank1|orthographic_variant|
|עיקר|עקר|NO|NO|YES|rank1|orthographic_variant|
|תחילה|תחלה|NO|NO|YES|rank1|orthographic_variant|
|תפילין|תפלין|NO|NO|YES|rank1|orthographic_variant|
|בבוקר|בבקר|NO|NO|YES|rank1|orthographic_variant|
|תפילה|תְּפִלָּה|NO|NO|YES|rank2|orthographic_variant|
|חידושין|חִדּוּשִׁין|NO|NO|YES|rank1|orthographic_variant|
|עיבור|עִבּוּר|NO|NO|YES|rank1|orthographic_variant|
|פֵּרוּשׁ|פֵּרוּשׁ|YES|YES|NO|rank1|exact|
|פרוש|פֵּרוּשׁ|NO|YES|NO|rank1|niqqud_insensitive|
|אור הפנים|אוֹר הַפָּנִים|NO|YES|NO|rank1|niqqud_insensitive|
|לנגדי|לנגד|NO|NO|NO|rank1|reject literal/orthographic|
|בעצמו|בעצמי|NO|NO|NO|rank1|reject literal/orthographic|
|מימיני|ממנו|NO|NO|NO|rank1|reject literal/orthographic|
|שהיא|שהוא|NO|NO|NO|rank1|reject literal/orthographic|
|אותו|את|NO|NO|NO|rank1|reject literal/orthographic|
|יכול|כל|NO|NO|NO|rank3|reject literal/orthographic|

Semantic probado vía integración DEV ya configurada LiteLLM, alias `openai_text_embedding_3_small`, upstream configurado `openai/text-embedding-3-small`,1536 dimensiones. Preflight `/model/info` y embedding probe200, batch200; model ID configurado coincide con header, retries0/fallbacks0. Gateway devuelve alias en `model`, no nombre upstream: la primera comprobación demasiado estricta bloqueó esa respuesta; se verificó mediante mapping+model ID+fallback headers, no se ignoró el mismatch. Dos batches de31 textos y dos probes durante evaluación; último batch205 tokens. No se persistieron vectores ni se creó colección. Sólo snippets textuales cortos por integración existente; **ningún PDF/crop enviado a OCR/vision externa**. No generative call. Evidencia sanitizada en `orthographic-results.json`.

El dataset contiene15 canonical snippets únicos (17 casos con focal repetido); la evaluación es exact cosine in-memory, no HNSW/Milvus ni full-corpus precision. El caso focal semantic top1 (cosine .474) no establece equivalencia editorial. No elegir umbral cosine post-hoc para hacer pasar positivos y ocultar negativos.

## Respuestas obligatorias

```text
OCR engine: Tesseract
version: 5.3.4
Hebrew language available: YES
Page 167 visual source: GOOD
Page 167 native: FAIL (Hebrew; Spanish valid)
Page 167 OCR base letters: FAIL (eligibilidad de cuerpo completo; rescate medido 97.10–98.55%)
Page 167 OCR word order: PASS (secuencia lógica revisada; tokens exactos no perfectos)
Page 167 OCR niqqud: PARTIAL (4/5 marks del fragmento pointed; no certificado global)
Page 167 OCR search usable: NO cuerpo completo / YES fragmento pointed
Page 167 OCR display usable: NO
Page 55 OCR improvement: YES vs native/historical; NO vs reconstrucción
Regional OCR recommended: NO automático con configuración probada; candidato futuro sólo validado por región
Full-page OCR recommended: NO

Strip niqqud exact search: PASS para mismas letras base; FAIL como solución completa del focal
פירוש → פֵּרוּשׁ recoverable: YES (offline guarded y semantic fixture)
Required mechanism: ORTHOGRAPHIC_VARIANT para trazabilidad léxica; SEMANTIC ya encuentra candidato
Controlled orthographic variants improve recall: YES en set anotado (3/11 →11/11)
False-positive risk acceptable: NO demostrado fuera del set;0/6 no es garantía
Recommended: MORE_EVIDENCE
```

## Artefactos / reproducción / validación

Obligatorios: README; ocr-environment/installation; ocr-page167/55-results; ocr-comparison; ocr-goldens; orthographic-history/fixtures/results; false-positive-analysis; recommendation. Adicionales: ocr-page143-results, findings, scripts aislados, tests/log y sólo crops necesarios (~2MB total). Salida raw y lógica por cada run junto con page/bbox/engine/version/language/dpi/config/source_method=`visual_ocr`.

Desde raíz:

```bash
PYTHONDONTWRITEBYTECODE=1 SrvRestAstroLS_v1/backend/.venv/bin/python data/reports/breslov/hebrew-ocr-orthographic-search-v1/benchmark.py
# Este replay siguiente hace nuevas llamadas embeddings DEV, no OCR externo:
PYTHONDONTWRITEBYTECODE=1 SrvRestAstroLS_v1/backend/.venv/bin/python data/reports/breslov/hebrew-ocr-orthographic-search-v1/search_benchmark.py
PYTHONDONTWRITEBYTECODE=1 SrvRestAstroLS_v1/backend/.venv/bin/python data/reports/breslov/hebrew-ocr-orthographic-search-v1/summarize.py
cd SrvRestAstroLS_v1/backend
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider \
 tests/test_hebrew_lexical_normalizer.py tests/test_likutey_moharan_ii_layout.py \
 tests/test_pdf_ligature_normalization.py \
 ../../data/reports/breslov/hebrew-ocr-orthographic-search-v1/test_benchmark.py -q
```

**97 tests PASS,0 failures**, log `tests.txt`; git diff --check PASS. Diff/scripts/JSON/crops revisados. Sin LAT/@lat/frontend/backend productivo editados: lat check, pnpm y E2E no aplican; no full suite ni live corpus retrieval.

```text
Branch: feature/console-backend-core
HEAD initial/final: 1fa9290bdc7840e7277a998aa3ca66345c6080ee
Files added: sólo data/reports/breslov/hebrew-ocr-orthographic-search-v1/
Existing local changes: PRESERVED, no adjudicados a esta fase
Commit / Push: NO / NO
Canonical pipeline modified: NO
PG writes / Milvus writes: NO / NO
PG/Milvus connections: NO
Reingest / Production: NO / NO
Service restarts / migrations / resets: NO
READY_FOR_C_REINGEST: NO
```

Impacto: evidencia experimental nueva, no cambio runtime. Riesgos abiertos: errores materiales OCR pese a promedio alto, números dañados, colisiones ortográficas/semánticas y guardas manuales sobre el mismo set. Próximo paso: holdout independiente/validación de quality gates antes de un prompt posterior de integración mínima; no reingesta autorizada.
