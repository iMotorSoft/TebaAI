"""Format results without changing rules, annotations, or decisions."""
from pathlib import Path
import json

OUT=Path(__file__).resolve().parent

def load(name):return json.loads((OUT/name).read_text())
def write(name,text):(OUT/name).write_text(text.strip()+'\n')
def run():
    h=load('holdout-results.json');o=load('ocr-quality-results.json');s=load('semantic-baseline.json');d=load('holdout-definition.json')
    sem={r['id']:r for r in s.get('rows',[])}
    table=['| Fixture | Query | Expected | Exact | No niqqud | Variant | Semantic | Final | Correct |','|---|---|---|---|---|---|---|---|---|']
    for c,r in zip(d['cases'],h['rows']):
        rank=sem.get(c['id'],{}).get('target_rank','BLOCKED')
        table.append(f"| {c['id']} | {c['query']} → {c['canonical_source']} | {','.join(c['allowed_match_types'])} | {r['exact']} | {r['no_niqqud']} | {r['variant']} | rank {rank} (SEMANTIC) | {r['final']} | {r['correct']} |")
    otable=['| Page | Region | Expected search | OCR | Search Gate | Display Gate | Reason |','|---|---|---|---|---|---|---|']
    for r in o['rows']:
        text=r['OCR_output'].replace('\n',' / ').replace('|','&#124;')
        if len(text)>130:text=text[:130]+'… (full JSON)'
        otable.append(f"| {r['page']} | {r['id']} | {r['expected_search']} | {text} | {r['decision_search']} | {r['decision_display']} | {', '.join(r['reason_codes'])} |")
    write('README.md',f'''# Hebrew holdout + regional OCR rejection safety V1

## Gates independientes

| Gate | Resultado |
|---|---|
| TEBAAI_BRESLOV_HEBREW_ORTHOGRAPHIC_HOLDOUT_V1 | **FAIL_RECALL** |
| TEBAAI_BRESLOV_REGIONAL_OCR_QUALITY_GATE_V1 | **BLOCKED** — rechazo seguro observado, utilidad discriminante no demostrada |
| Integración recomendada | **D. BOTH_NOT_READY** |
| READY_FOR_C_REINGEST | **NO** |

## A. Reglas congeladas y holdout

Frozen rules SHA-256: `{h['frozen_rules_hash']}`.
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
Rasters originales bajo `crops/holdout-*.png`. Fuente SHA: `{d['source_sha256']}`.
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

Estado `{s['status']}`. Mismo alias/modelo configurado, 1536 dimensiones,
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

{chr(10).join(table)}

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

{chr(10).join(otable)}

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
''')
    write('holdout-false-positive-analysis.md','''# False-positive analysis

0/14 rechazos negativos fallidos en este holdout. No prueba precisión full-corpus:
el lookup cerrado no reconoce ninguno de los diez pares ortográficos nuevos.
La ausencia de expansión en estos casos limita mucho el poder del test de colisiones.
Los negativos incluyen י/ו, cambio de número gramatical, ר/ד, morfología y contexto
semántico similar. Las etiquetas se definieron antes de ejecutar las reglas.

No se añadieron excepciones ni guardas manuales. Los diez fallos ortográficos se
clasifican como OUT_OF_FROZEN_LOOKUP_COVERAGE y quedan sin reparar en V1.
La dependencia MANUAL_LEXEME_ORACLE del prototipo es un riesgo adicional, no una
capability automática. Requiere V2 y nuevo holdout; no reetiquetar fallos como semantic.

Con cero errores entre 14 negativos, incluso una aproximación binomial independiente
tendría cota superior unilateral 95% ~19.3% (1 - .05**(1/14)); la independencia no está
garantizada aquí. No usar 100% observado como garantía de producción.
Semantic devuelve el target peligroso top1 en 8/14 y top3 en 12/14, sin umbral de
aceptación. Eso sería peligroso SI se promoviera similitud a equivalencia; no se hizo.

Las pruebas de prioridad son concursos aislados, no ranking PostgreSQL/Milvus.
Canónico/query se conservan; los generated_variants están separados. No se escribe corpus.
''')
    write('ocr-quality-reason-codes.md','''# Reason codes

| Code | Significado / uso |
|---|---|
| OCR_DIGIT_LOSS | Secuencia numérica distinta de referencia estructural fiable; MATERIAL_OCR_ERROR; rechazo obligatorio, incluye sustitución/inserción |
| OCR_WORD_MERGE | Mismas letras, menos límites frente referencia confiable |
| OCR_WORD_SPLIT | Mismas letras, más límites frente referencia confiable |
| OCR_BASE_LETTER_ERROR | Diferencia material frente referencia confiable |
| OCR_LOW_HEBREW_RATIO | Reservado diagnóstico; sin umbral calibrado, no aplicado (LTR válido no es error) |
| OCR_UNICODE_INVALID | U+FFFD, surrogate o private-use inesperado |
| OCR_GEOMETRY_MISMATCH | Metadata de layout no certifica una región lógica; columna combinada conocida |
| OCR_CONFIG_DISAGREEMENT | 300/400 DPI difieren en letras/orden/límites/puntuación; no decide qué salida es correcta |
| OCR_UNCERTAIN | Sin referencia independiente confiable; fail closed |
| OCR_DISPLAY_UNCERTAIN | Search aceptable pero display sin transcript pointed completo |
| OCR_ACCEPT_SEARCH | Todas las condiciones operativas satisfechas; ninguno real en este replay |
| OCR_ACCEPT_DISPLAY | Además igualdad NFC de referencia display confiable; ninguno real |
| SOURCE_PDF_ERROR | Fuente visual defectuosa; no rescatar automáticamente (unit test sintético solamente) |

Los códigos merge/split/base-letter tienen cobertura unitaria sintética, no se
atribuyen al detector real cuando sólo el golden permite conocer el error.
El fallback es KEEP_NATIVE_RECONSTRUCTION_OR_UNRESOLVED; no SILENT_REPAIR.
''')
    write('ocr-quality-threshold-analysis.md','''# Threshold analysis — no tuning

Política implementada en ocr_gate.py, hash previo al replay en ocr-gate-hash.txt.
No se ajustó después de observar resultados. No se buscó corte de confidence,
ratio hebreo, token counts ni agreement para hacer pasar las regiones buenas.

Tolerancia de discrepancia material = cero: trazabilidad exige números exactos;
referencia confiable debe preservar letras/orden/límites. Es un requisito de
integridad, no un porcentaje ajustado a muestra. DISPLAY exige además referencia
pointed/puntuada completa y exactitud NFC. Niqqud parcial puede ser search-only,
pero no basta sin corroboración independiente de letras.

Se midieron confidence TSV, disagreement nativo, número de palabras/tokens (mismo
split aquí), Unicode, ratio Hebrew, U+FFFD, geometría suministrada y líneas TSV.
No son un clasificador calibrado. Token divergence contra native corrupto y reducción
U+FFFD no validan OCR. Acuerdo entre dos DPI correlacionados no es prueba independiente.

Los dos headers muestran el problema: título 11/11 letras y secuencia estable,
pero 149→9 / 37→7. OCR_DIGIT_LOSS rechaza ambos por referencia ASCII nativa
corroborada visualmente. Crops sólo número también fallan. Son errores materiales,
no minor character errors. Fiabilidad de la referencia numérica está anotada,
no detectada automáticamente por el prototipo.

El fragmento pointed tiene 8/8 letras y 4/5 marks, pero no existe runtime trusted
base-reference para certificarlo sin usar golden. El gate lo rechaza; no se pasa
golden por otra clave ni se crea allowlist de regiones buenas. Línea143 y título
limpio también son false rejections. 3/3 buenos rechazados: BLOCKED, no PASS.

No hay sensibilidad/precisión operacional calibrada ni display positivos transcritos
exhaustivamente. No se exige alcanzar un recall arbitrario; la falta total de capacidad
de aceptación real basta para NO autorizar integración. El replay sólo prueba rechazo
condicionado a evidencia fiable. SOURCE ERROR != PLATFORM ERROR sigue intacto.
''')
    write('recommendation.md','''# Recomendación única de integración

**D. BOTH_NOT_READY**

- Orthographic: FAIL_RECALL; 0/10 variantes inéditas. Rechazar integración del
  prototipo congelado como generalizador. No cambia la normalización niqqud ya válida.
- OCR: BLOCKED; rechaza 149→9 y 37→7 pero rechaza también los 3 fragmentos buenos.
  No se autoriza automático regional, fragmentos automáticos ni display.

No se implementó integración. READY_FOR_C_REINGEST = NO.
Una V2 debe usar pares reales atestiguados/revisión hebrea independiente y un nuevo
holdout; el corpus existente debe tener baseline semántico real read-only separado.
OCR necesita demostrar aceptación segura con señales disponibles operacionalmente,
no con golden, confianza alta ni allowlist manual. Integración y revalidación son
gates posteriores explícitos, no autorizados por esta evidencia.
''')

if __name__=='__main__':run()
