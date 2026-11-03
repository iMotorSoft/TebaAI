# Hebrew holdout + regional OCR rejection safety V1

## Gates independientes

| Gate | Resultado |
|---|---|
| TEBAAI_BRESLOV_HEBREW_ORTHOGRAPHIC_HOLDOUT_V1 | **FAIL_RECALL** |
| TEBAAI_BRESLOV_REGIONAL_OCR_QUALITY_GATE_V1 | **BLOCKED** — rechazo seguro observado, utilidad discriminante no demostrada |
| Integración recomendada | **D. BOTH_NOT_READY** |
| READY_FOR_C_REINGEST | **NO** |

## A. Reglas congeladas y holdout

Frozen rules SHA-256: `b574140737fe062af5f13ec7a42b97447f10687af86ed49ab825859806904303`.
Hash de bytes UTF-8 con newline, separado del artefacto para no autorreferenciarlo.
`orthographic-rules-frozen.json` incluye código completo del prototipo y normalizador,
8 sustituciones dirigidas, límite 4, guarda manual y prioridad de ranking.
Se congeló antes de extraer/inspeccionar el nuevo documento y crear las anotaciones.
Secuencia ejecutada: `freeze.py` → raster/inspección → `define_holdout.py` → `evaluate.py`.
No existe prueba temporal externa/notarial; son artefactos locales reproducibles.
Reglas, pares y thresholds no se ajustaron tras resultados. Las correcciones de
transcripción contra raster/extracción auxiliar se hicieron antes de sellar el holdout.

42 fixtures: 28 positivos (66.7%) y 14 negativos (33.3%). Documento real
`LIKUTEY MOHARAN II Interior.pdf`, páginas físicas 22/24/26/30/32/34; el contenido
visible está rotulado LIKUTEY MOHARÁN #7. Se identifica por filename/hash/página,
**no se infiere que esas páginas sean LM II** por el nombre del archivo.
Rasters originales bajo `crops/holdout-*.png`. Fuente SHA: `ce7304e31c37cadd5bc938732d93c8e5385afc026c0af0de612635d8b76cab61`.
Cero términos query/canonical normalizados reutilizados de los 17 casos anteriores;
cero entradas de los ocho pares de diseño. La anotación quedó sellada antes de ejecutar reglas.

**Límite de independencia:** nuevos documento/páginas/lexemas, pero mismo anotador
asistente, no revisión humana ciega. Consultas ortográficas y negativas son probes
editoriales anclados en palabras reales, **no pares de variantes atestiguados en dos
ediciones**. No se completó un holdout lingüístico independiente de esa calidad;
no se declara generalización poblacional ni PASS_SAFE_FOR_INTEGRATION.
Los fragmentos pointed son etiquetas manuales cortas, no citas publicables; exact
base-only está explícito. Revisión editorial hebrea humana pendiente.

### Métricas

- Positive recall: **18/28 = 64.29%**.
- Precision: **18/18 = 100% observada**, no garantía fuera de muestra.
- Dangerous false positives: **0/14**; negative rejection **14/14 = 100%**.
- EXACT **4/4**, NIQQUD_INSENSITIVE **14/14**, ORTHOGRAPHIC_VARIANT **0/10**.
- SEMANTIC no se suma a recall léxico; no hay fixtures positivos semantic-only.
- Exact ranking regressions: **0/42** concursos aislados con candidato exacto;
  no es validación del ranking productivo/full-corpus. Canónico/query: 0 mutaciones.
- Canonical evidence unchanged: se verifica hash del texto de cada fixture y original_query.
- Recall ortográfico no generaliza: **NO**; recomendado **REJECT** el prototipo congelado
  como mecanismo general de equivalencia; futura V2 requerirá nuevo holdout.

La guarda `confirmed_context` del set anterior era una etiqueta manual de verdad.
Aquí no se pasa al clasificador. No hay desambiguador automático congelado.
Aun con esa guarda, el lookup no genera candidatos para estos diez lexemas nuevos.
El focal conocido recupera ORTHOGRAPHIC_VARIANT **sólo con su guarda legacy**;
sin ella NO_MATCH. Ambas regresiones están en `known-regressions.json`, fuera del holdout.
La consulta original y canónico permanecen intactos. No se ocultó esta dependencia.

### Semantic baseline

Estado `PASS_LOCAL_FIXTURE_EMBEDDINGS`. Mismo alias/modelo configurado, 1536 dimensiones,
preflight gateway real local, mapping/model ID/fallback verificados por el runner previo.
Positivos: **26/28 top1, 28/28 top3**. Targets negativos peligrosos:
**8/14 top1, 12/14 top3**. Son candidatos semánticos, NO equivalencias ortográficas.
Sin threshold cosine elegido post-hoc. Nunca se convierten en evidencia literal.

**No se midieron embeddings persistidos existentes ni retrieval Milvus vivo.**
Se generaron vectores transitorios del mismo modelo para este universo de snippets,
cosine exacto en memoria; no índice, reembedding de corpus ni modificación de vectores.
Por ello la comparación pedida contra embeddings existentes del corpus queda
**NOT_MEASURED**. No presentar este baseline acotado como full-corpus safety.
Preflight y métricas sanitizadas completos en `semantic-baseline.json`.

| Fixture | Query | Expected | Exact | No niqqud | Variant | Semantic | Final | Correct |
|---|---|---|---|---|---|---|---|---|
| H01 | זרע → זרע | EXACT | True | True | False | rank 1 (SEMANTIC) | EXACT | True |
| H02 | אמת → אמת | EXACT | True | True | False | rank 1 (SEMANTIC) | EXACT | True |
| H03 | נחש → נחש | EXACT | True | True | False | rank 1 (SEMANTIC) | EXACT | True |
| H04 | מאה → מאה | EXACT | True | True | False | rank 1 (SEMANTIC) | EXACT | True |
| H05 | עצה → עֵצָה | NIQQUD_INSENSITIVE | False | True | False | rank 1 (SEMANTIC) | NIQQUD_INSENSITIVE | True |
| H06 | צדיק → צַדִּיק | NIQQUD_INSENSITIVE | False | True | False | rank 1 (SEMANTIC) | NIQQUD_INSENSITIVE | True |
| H07 | אדם → אָדָם | NIQQUD_INSENSITIVE | False | True | False | rank 1 (SEMANTIC) | NIQQUD_INSENSITIVE | True |
| H08 | שמירה → שְׁמִירָה | NIQQUD_INSENSITIVE | False | True | False | rank 1 (SEMANTIC) | NIQQUD_INSENSITIVE | True |
| H09 | עינים → עֵינַיִם | NIQQUD_INSENSITIVE | False | True | False | rank 1 (SEMANTIC) | NIQQUD_INSENSITIVE | True |
| H10 | אמונה → אֱמוּנָה | NIQQUD_INSENSITIVE | False | True | False | rank 2 (SEMANTIC) | NIQQUD_INSENSITIVE | True |
| H11 | דעה → דֵּעָה | NIQQUD_INSENSITIVE | False | True | False | rank 1 (SEMANTIC) | NIQQUD_INSENSITIVE | True |
| H12 | פעמים → פְּעָמִים | NIQQUD_INSENSITIVE | False | True | False | rank 1 (SEMANTIC) | NIQQUD_INSENSITIVE | True |
| H13 | נישואין → נִשּׂוּאִין | ORTHOGRAPHIC_VARIANT | False | False | False | rank 2 (SEMANTIC) | NO_MATCH | False |
| H14 | זיווג → זִוּוּג | ORTHOGRAPHIC_VARIANT | False | False | False | rank 1 (SEMANTIC) | NO_MATCH | False |
| H15 | תושייה → תּוּשִׁיָּה | ORTHOGRAPHIC_VARIANT | False | False | False | rank 1 (SEMANTIC) | NO_MATCH | False |
| H16 | המוח → הַמֹּחַ | ORTHOGRAPHIC_VARIANT | False | False | False | rank 1 (SEMANTIC) | NO_MATCH | False |
| H17 | טיפי → טִפֵּי | ORTHOGRAPHIC_VARIANT | False | False | False | rank 1 (SEMANTIC) | NO_MATCH | False |
| H18 | כולו → כֻּלּוֹ | ORTHOGRAPHIC_VARIANT | False | False | False | rank 1 (SEMANTIC) | NO_MATCH | False |
| H19 | הניאוף → הַנִּאוּף | ORTHOGRAPHIC_VARIANT | False | False | False | rank 1 (SEMANTIC) | NO_MATCH | False |
| H20 | הגלות → הַגָּלוּת | NIQQUD_INSENSITIVE | False | True | False | rank 1 (SEMANTIC) | NIQQUD_INSENSITIVE | True |
| H21 | הגאולה → הַגְּאֻלָּה | ORTHOGRAPHIC_VARIANT | False | False | False | rank 1 (SEMANTIC) | NO_MATCH | False |
| H22 | לומדים → לוֹמְדִים | NIQQUD_INSENSITIVE | False | True | False | rank 1 (SEMANTIC) | NIQQUD_INSENSITIVE | True |
| H23 | תלמוד → תַּלְמוּד | NIQQUD_INSENSITIVE | False | True | False | rank 1 (SEMANTIC) | NIQQUD_INSENSITIVE | True |
| H24 | כשולחן → כְּשֻׁלְחָן | ORTHOGRAPHIC_VARIANT | False | False | False | rank 1 (SEMANTIC) | NO_MATCH | False |
| H25 | החכמות → הַחָכְמוֹת | NIQQUD_INSENSITIVE | False | True | False | rank 1 (SEMANTIC) | NIQQUD_INSENSITIVE | True |
| H26 | השיכחה → הַשִּׁכְחָה | ORTHOGRAPHIC_VARIANT | False | False | False | rank 1 (SEMANTIC) | NO_MATCH | False |
| H27 | מצות → מִצְוַת | NIQQUD_INSENSITIVE | False | True | False | rank 1 (SEMANTIC) | NIQQUD_INSENSITIVE | True |
| H28 | אחד → אֶחָד | NIQQUD_INSENSITIVE | False | True | False | rank 1 (SEMANTIC) | NIQQUD_INSENSITIVE | True |
| H29 | זר → זרע | NO_MATCH | False | False | False | rank 1 (SEMANTIC) | NO_MATCH | True |
| H30 | אדום → אָדָם | NO_MATCH | False | False | False | rank 1 (SEMANTIC) | NO_MATCH | True |
| H31 | רעש → רָשָׁע | NO_MATCH | False | False | False | rank 1 (SEMANTIC) | NO_MATCH | True |
| H32 | צדק → צַדִּיק | NO_MATCH | False | False | False | rank 1 (SEMANTIC) | NO_MATCH | True |
| H33 | שכלו → הַשֵּׂכֶל | NO_MATCH | False | False | False | rank 2 (SEMANTIC) | NO_MATCH | True |
| H34 | שומר → שְׁמִירָה | NO_MATCH | False | False | False | rank 7 (SEMANTIC) | NO_MATCH | True |
| H35 | ציץ → צִיצִית | NO_MATCH | False | False | False | rank 1 (SEMANTIC) | NO_MATCH | True |
| H36 | נחוש → נָחָשׁ | NO_MATCH | False | False | False | rank 2 (SEMANTIC) | NO_MATCH | True |
| H37 | זוגה → זִוּוּג | NO_MATCH | False | False | False | rank 2 (SEMANTIC) | NO_MATCH | True |
| H38 | עין → עֵינַיִם | NO_MATCH | False | False | False | rank 1 (SEMANTIC) | NO_MATCH | True |
| H39 | אומן → אֱמוּנָה | NO_MATCH | False | False | False | rank 3 (SEMANTIC) | NO_MATCH | True |
| H40 | שולח → שֻׁלְחָן | NO_MATCH | False | False | False | rank 1 (SEMANTIC) | NO_MATCH | True |
| H41 | אחר → אֶחָד | NO_MATCH | False | False | False | rank 1 (SEMANTIC) | NO_MATCH | True |
| H42 | מעט → מֵאָה | NO_MATCH | False | False | False | rank 5 (SEMANTIC) | NO_MATCH | True |

## B. OCR quality gate

Tesseract **5.3.4**, sin instalación/cambio de motor ni tuning. 16 regiones únicas
(13 previas + título/folios recortados); 32 muestras a 300/400 DPI, OEM1 PSM6 fijo.
Dos invocaciones por muestra (texto + TSV/confidence): **64 ejecuciones del motor**.
No PSM nuevo, no selección del mejor resultado; 400/PSM6 es primario y 300 señal
de estabilidad. Muestras/configuraciones/crops solapados NO son observaciones independientes.
Páginas 167/55/143, Hebrew, punctuation, structural digits, español/referencias LTR y
control de columnas combinadas. No se transcribieron páginas completas ni se OCRizaron páginas completas.

Golden visual corto reutilizado del audit anterior; tres nuevos crops verificados
visualmente. El embedded corrupto nunca es golden. Los controles de contexto español
sin transcripción completa tienen métricas null y expectativa de rechazo por incertidumbre,
**no se cuentan como errores materiales transcritos**. Anotación editorial humana pendiente.

La función `decide(signals)` **no recibe golden, expected ni métricas contra golden**.
Confidence, Unicode, ratio hebreo, native disagreement, token/word divergence,
reducción U+FFFD, geometría y líneas son señales/diagnósticos separados.
Sin una referencia confiable independiente de letras/orden/límites no se acepta OCR.
Acuerdo de DPI, alfabeto válido y alta confianza no prueban lectura correcta.
Geometría y fiabilidad de folios son metadata **anotada para este replay**, no un
segmentador/detector de confiabilidad automático. No se certifica su generalización.

- OCR quality fixtures: **16**; accept expected **3**, reject expected **13**.
- Known bad OCR rejected: **YES**; **149→9 YES**, **37→7 YES**.
- Folio aislado 149→19 y 37→`| 7` también rechazados por OCR_DIGIT_LOSS.
- Known good fragments accepted: **NO**.
- Unsafe OCR accepted: **0 observados**; no se equiparan 13 rechazos a 13 errores
  materiales completos (algunos son controles inciertos sin golden completo).
- Safe OCR incorrectly rejected: **3** (אוֹר הַפָּנִים, línea143 y título167).
- Search gate usable: **NO**; display gate usable: **NO**.
- Recommended: **MORE_EVIDENCE**, no REGIONAL_AUTO_FALLBACK ni FRAGMENT_READY.

**Rechazar todo no demuestra un quality gate discriminante.** Se demuestra el
bloqueo auditable de números dañados cuando hay referencia numérica fiable,
pero falta una señal operativa que permita aceptar fragmentos buenos sin oráculo.
Por eso el resultado es BLOCKED, no un PASS vacuo.

Todos los rechazos mantienen native/reconstruction/unresolved según contexto.
`replacement_authorized=false` siempre; ninguna sustitución de texto canónico.
Fuente visual GOOD en regiones revisadas. SOURCE_PDF_ERROR se prueba sólo en
unit test sintético, no se inventa un error fuente ni se bloquea el libro completo.

| Page | Region | Expected search | OCR | Search Gate | Display Gate | Reason |
|---|---|---|---|---|---|---|
| 167 | R167_A | OCR_REJECT_EXPECTED | 9 ליקוטי הלכות | SEARCH_REJECT | DISPLAY_REJECT | OCR_DIGIT_LOSS, OCR_UNCERTAIN |
| 167 | R167_B | OCR_REJECT_EXPECTED | רְגָלִים פַנַּ"ל, וּמְשֶם נְמְשָכִין בָּחִינַת מִנְעָלִים שְָהֶם שוּמָרִין אֶת הֶרְגְלִין מְהַחִיצוּנִים. /  / וְזֶהגּ: "כֶּתְפִיל… (full JSON) | SEARCH_REJECT | DISPLAY_REJECT | OCR_CONFIG_DISAGREEMENT, OCR_UNCERTAIN |
| 167 | R167_B_line1 | OCR_REJECT_EXPECTED | רְגָלִים פַנַּ"ל, וּמְשֶם נְמְשָכִין בָּחִינַת מִנְעָלִים שְָהֶם שוּמָרִין אֶת הֶרְגְלִין מְהַחִיצוּנִים. | SEARCH_REJECT | DISPLAY_REJECT | OCR_CONFIG_DISAGREEMENT, OCR_UNCERTAIN |
| 167 | R167_B_line2 | OCR_REJECT_EXPECTED | וְעֶלכֶן צָרִיכִין לְנְעל שַל יִמִין תִּחְלָה, כִּי עְקָר הוּא בְּחִינַת יָמִין שַָהוּא חֶסֶד, שְעַליידִי-זֶּה קוצָרין | SEARCH_REJECT | DISPLAY_REJECT | OCR_CONFIG_DISAGREEMENT, OCR_UNCERTAIN |
| 167 | R167_B_line3 | OCR_REJECT_EXPECTED | אוּתֶהּ מָהֶם גּבוּנִין אותֶהפַנּ"ל. | SEARCH_REJECT | DISPLAY_REJECT | OCR_CONFIG_DISAGREEMENT, OCR_UNCERTAIN |
| 167 | R167_C | OCR_REJECT_EXPECTED | וְזֶהגּ: "כֶּתְפִילִין", שָהֶם אור הַפָּנִים, כַיּדוּעַ (פרי עץ חיים שער התפלין פרק ג), | SEARCH_REJECT | DISPLAY_REJECT | OCR_CONFIG_DISAGREEMENT, OCR_UNCERTAIN |
| 167 | R167_C_niqqud | OCR_ACCEPT_EXPECTED | אור הַפָּנִים, | SEARCH_REJECT | DISPLAY_REJECT | OCR_UNCERTAIN |
| 167 | R167_D | OCR_REJECT_EXPECTED | protección extra para elevarlos de las fuerzas externas adyacentes a ellos. Pues / los pies están conceptualmente asociados con Ma… (full JSON) | SEARCH_REJECT | DISPLAY_REJECT | OCR_CONFIG_DISAGREEMENT, OCR_UNCERTAIN |
| 167 | R167_E_left | OCR_REJECT_EXPECTED | 60 Ver Pri Etz Jaim, Shaar HaTefila 3. /  / 61 Ver 81 más arriba. /  / 62 Pri Etz Jaim, Op. Cit. /  / 63 Una cita entre paréntesis… (full JSON) | SEARCH_REJECT | DISPLAY_REJECT | OCR_CONFIG_DISAGREEMENT, OCR_UNCERTAIN |
| 167 | R167_E_right | OCR_REJECT_EXPECTED | se refrena en general de amonestar al pueblo judío (ver LM / I, 22:1), el Rebe Najmán enseña que el sufrimiento que le / produce e… (full JSON) | SEARCH_REJECT | DISPLAY_REJECT | OCR_UNCERTAIN |
| 167 | R167_E_combined | OCR_REJECT_EXPECTED | 60 Ver Pri Etz Jaim, Shaar HaTefilá 3. se refrena en general de amonestar al pueblo judío (ver LM / 61 Ver 81 más arriba. I, 22:1)… (full JSON) | SEARCH_REJECT | DISPLAY_REJECT | OCR_GEOMETRY_MISMATCH, OCR_CONFIG_DISAGREEMENT, OCR_UNCERTAIN |
| 55 | R55_A | OCR_REJECT_EXPECTED | 7 ליקוטי הלכות | SEARCH_REJECT | DISPLAY_REJECT | OCR_DIGIT_LOSS, OCR_UNCERTAIN |
| 143 | R143_line | OCR_ACCEPT_EXPECTED | שחוזֶרין בָּכֶל פּעַם אֶל הָאוּת הֶרְאשון, כַּמְבאָר שֶם, עיַן שֶם. | SEARCH_REJECT | DISPLAY_REJECT | OCR_CONFIG_DISAGREEMENT, OCR_UNCERTAIN |
| 167 | Q167_title | OCR_ACCEPT_EXPECTED | ליקוטי הלכות | SEARCH_REJECT | DISPLAY_REJECT | OCR_UNCERTAIN |
| 167 | Q167_folio | OCR_REJECT_EXPECTED | 19 | SEARCH_REJECT | DISPLAY_REJECT | OCR_DIGIT_LOSS, OCR_UNCERTAIN |
| 55 | Q55_folio | OCR_REJECT_EXPECTED | &#124; 7 | SEARCH_REJECT | DISPLAY_REJECT | OCR_DIGIT_LOSS, OCR_UNCERTAIN |

## Reproducción y límites

Desde raíz, con artefactos congelados existentes:

```bash
PYTHONDONTWRITEBYTECODE=1 SrvRestAstroLS_v1/backend/.venv/bin/python data/reports/breslov/hebrew-holdout-ocr-quality-v1/evaluate.py
# Hace llamadas embeddings DEV nuevas, nunca PG/Milvus:
PYTHONDONTWRITEBYTECODE=1 SrvRestAstroLS_v1/backend/.venv/bin/python data/reports/breslov/hebrew-holdout-ocr-quality-v1/evaluate.py --semantic
PYTHONDONTWRITEBYTECODE=1 SrvRestAstroLS_v1/backend/.venv/bin/python data/reports/breslov/hebrew-holdout-ocr-quality-v1/evaluate.py --ocr
PYTHONDONTWRITEBYTECODE=1 SrvRestAstroLS_v1/backend/.venv/bin/python data/reports/breslov/hebrew-holdout-ocr-quality-v1/report.py
cd SrvRestAstroLS_v1/backend
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider tests/test_hebrew_lexical_normalizer.py ../../data/reports/breslov/hebrew-holdout-ocr-quality-v1/test_validation.py -q
```

`freeze.py` y `define_holdout.py` rehúsan sobrescribir el freeze/holdout sellado.
No ejecutarlos de nuevo sobre estos artefactos. No retocar reglas tras el test.
Ver [validaciones](validation.md), [thresholds](ocr-quality-threshold-analysis.md),
[falsos positivos](holdout-false-positive-analysis.md) y [recomendación](recommendation.md).

## Aislamiento Git / corpus

Branch: `feature/console-backend-core`.
HEAD inicial/final: `1fa9290bdc7840e7277a998aa3ca66345c6080ee`.
Archivos añadidos únicamente bajo este directorio; worktree previo preservado.
Commit NO; push NO; reset NO; reingest NO; PostgreSQL/Milvus writes/connections NO;
production modified NO; worker/extractor/configuración canónica NO; servicios
reiniciados/migrados/reconfigurados NO. READY_FOR_C_REINGEST=NO.

Impacto: sólo evidencia experimental. Riesgos: independencia editorial incompleta,
lookup sin cobertura fuera del diseño, negativos correlacionados, semantic candidates
peligrosos y ausencia de verificador automático de lectura Hebrew.
Próximo paso: aprobación de protocolo V2 con anotador hebreo independiente/pares
atestiguados y referencia operacional de calidad OCR; nuevo holdout, sin integrar V1.
