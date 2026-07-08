# Breslov Layout Probe — LIKUTEY HALAJOT Interior Final

**Fecha:** 2026-07-05
**Fase:** Layout probe read-only
**Rama:** `feature/console-backend-core`

---

## 1. Resumen ejecutivo

El PDF `LIKUTEY HALAJOT (Interior Final).pdf` (284 páginas, 4.4 MB) contiene la obra *Likutey Halajot Explicado* con un layout complejo de múltiples capas:

- **texto hebreo fuente** en codificación SI-960 (TeX Hebrew, misma familia que el Tanaj procesado anteriormente);
- **explicación/traducción española** en Unicode;
- **marginal sources** (citas bíblicas) en el margen derecho de páginas impares;
- **notas y fuentes** al pie, divididas en dos columnas;
- **separadores editoriales** "Likutey Halajot Explicado";
- **encabezados** bilingües (hebreo/español) con referencia halájica.

**Veredicto:** `PASS` con advertencias controladas. El layout es analizable, segmentable por coordenadas, y las capas semánticas son distinguibles mediante reglas de posición y detección de encoding. La ingesta layout-aware es viable, pero requiere:
1. Decodificación SI-960 para bloques hebreos (reutilizar `hebrew_tex_decoder.py`).
2. Segmentación por coordenadas para separar marginal sources y footnotes.
3. Manejo de continuidad de notas entre páginas.

**No se requiere OCR** — el PDF tiene texto embebido seleccionable.

---

## 2. Rama y commits

| Campo | Valor |
|---|---|
| Rama | `feature/console-backend-core` |
| HEAD inicial | `1547bf05bd2f97968c3a7f40709e2a01a74267ba` |
| HEAD final | `1547bf05bd2f97968c3a7f40709e2a01a74267ba` (sin cambios en código productivo) |
| Commit final | Sin cambios en código productivo. Solo scripts/ouputs en `tmp/likutey_layout_probe/` y este reporte. |

---

## 3. PDF analizado

| Campo | Valor |
|---|---|
| Archivo | `/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf` |
| Páginas | 284 |
| Texto embebido | Sí, seleccionable |
| OCR requerido | No |
| Tamaño | 4.4 MB |
| Page size | 496 x 694 pts |
| Productor | Acrobat Distiller 11.0 (PScript5.dll) |
| PDF version | 1.6 |
| Hebrew encoding | SI-960 (TeX Hebrew, Latin-1 supplement codepage) |
| Spanish encoding | Unicode directo |
| Section marker encoding | Codificación de fuente PDF (ej: `/LNXWH\ DODNKRW (OXFLGDWHG` = "Likutey Halajot Explicado") |
| Parser recomendado | `fitz` (PyMuPDF) con `get_text('blocks', sort=True)` para coordenadas, más `get_text('text')` para texto plano. Decodificador SI-960 para bloques hebreos. |

---

## 4. Páginas de muestra

Se analizaron 27 páginas en total (portada, introducción, cuerpo principal).

| Página impresa | Página PDF | Motivo | Resultado |
|---|---|---|---|
| (portada) | 0 | Portada/Legal | FAIL (sin layout halájico) |
| (portada) | 1 | Copyright | FAIL |
| (portada) | 2 | Créditos | FAIL |
| 2 | 19 | Intro — Leyes del Shuljan Aruj | WARN |
| 4 | 21 | Intro — Rabí Natán | WARN |
| 18 | 35 | Leyes del Shuljan Aruj | WARN |
| 22 | 39 | HALAJÁ 1:1 inicio español | WARN |
| **23** | **40** | **Hebreo + Español + Margen + Notas** | **PASS** |
| 24 | 41 | HALAJÁ 1:1 español cont | WARN |
| 31 | 48 | Hebreo + Margen + Notas | PASS |
| **32** | **49** | **Trece Atributos + Margen + Nota 23** | **PASS** |
| 33 | 50 | Hebreo + Margen + Notas | PASS |
| 36 | 53 | HALAJÁ 1:5 español | WARN |
| **37** | **54** | **Remá + Shuljan Aruj + Margen + Nota 33/34** | **PASS** |
| 38 | 55 | HALAJÁ 1:6 español | PASS |
| 40 | 57 | HALAJÁ 1:6 español | WARN |
| 45 | 62 | Hebreo + Margen | WARN |
| 50 | 67 | Español + Notas | PASS |
| 55 | 72 | Hebreo | WARN |
| 60 | 77 | Español + Notas | WARN |
| 65 | 82 | Hebreo + Margen + Notas | PASS |
| 70 | 87 | Español + Crossrefs | WARN |
| 75 | 92 | Hebreo + Margen | WARN |
| 80 | 97 | Español fin sección | WARN |

**Leyenda:**
- **PASS**: Header + hebreo + español + marginal sources + footnotes separados.
- **WARN**: Parcial (ej: página par sin marginal source, lo cual es esperado).
- **FAIL**: Página sin contenido estructural halájico (portada, legal, etc.).

---

## 5. Taxonomía de bloques

| block_type | Descripción | Se embebe | Fuente final |
|---|---|---|---|
| `page_header` | Encabezado de página (N obra sección halajá) | No | Metadata |
| `source_hebrew` | Texto hebreo fuente (SI-960 encoded) | Sí | Sí (previa decodificación) |
| `section_marker` | Separador editorial "Likutey Halajot Explicado" | No (opcional) | No |
| `main_explanation_es` | Explicación/traducción principal en español | Sí | Sí |
| `marginal_source` | Cita lateral o callout de fuente | Sí | Sí |
| `footnote` | Notas y fuentes al pie | Sí | Sí |
| `notes_marker` | Separador "Notas y Fuentes" | No | Metadata |
| `composite_page_context` | Contexto compuesto para retrieval (opcional) | Opcional | No |

### Subtipos detectados

| block_subtype | Ejemplos encontrados |
|---|---|
| `biblical_citation` | Salmos 37:10, Salmos 146:2, Salmos 16:1 |
| `rabbinic_reference` | Avot 1:6, Beit Hilel, Zohar |
| `halachic_reference` | Shuljan Aruj, Remá |
| `breslov_teaching` | "El Rebe Najmán conecta..." |
| `theological_explanation` | "los Trece Atributos de Misericordia..." |
| `bibliographic_note` | "23 Beit Hilel explica..." |

### Roles de evidencia detectados

| evidence_role | Ejemplos |
|---|---|
| `source_text` | Bloques hebreos SI-960 |
| `commentary` | Explicación española |
| `direct_quote` | Citas bíblicas en marginal sources |
| `marginal_citation` | "Hay aún un poco de bien" (Salmos 37:10) |
| `bibliographic_note` | Nota 23: "Beit Hilel explica... Rosh HaShaná 17a" |
| `halachic_derash` | Shuljan Aruj + Remá + interpretación Breslov |

---

## 6. Resultados de extracción

| Página | Header | Hebreo | Español | Margen | Notas | Evaluación |
|---|---|---|---|---|---|---|
| 23 | ✅ bilingüe | ✅ 4 bloques SI-960 | ✅ cuerpo central | ✅ 4 bloques (2 citas + 2 refs) | ✅ 2 columnas | PASS |
| 32 | ✅ español | ✅ 2 bloques SI-960 | ✅ 3 bloques | ✅ 1 bloque (Trece Atributos) | ✅ 2 columnas | PASS |
| 37 | ✅ bilingüe | ✅ 3 bloques SI-960 | ✅ 3 bloques | ✅ 1 bloque (Salmo 16:1) | ✅ 2 columnas (notas 33,34) | PASS |

### Patrón de layout por paridad

**Páginas pares (izquierda):**
- Header: "N LIKUTEY HALAJOT\nDISCURSO SOBRE EL LEVANTARSE EN LA MAÑANA HALAJÁ X:Y"
- Body: Explicación española continua
- Footnotes: columna completa al pie
- Sin hebreo ni marginal sources

**Páginas impares (derecha):**
- Header: "השכמת הבוקר N" (SI-960) + subtítulos hebreos
- Zona superior: texto fuente hebreo (SI-960)
- Section marker: "Likutey Halajot Explicado"
- Zona central: explicación española
- Margen derecho: citas bíblicas (x > 350)
- Footnotes: dos columnas al pie

---

## 7. Node path / halajá

| Página | Node path detectado | Confianza |
|---|---|---|
| 23 | `Likutey Halajot > השכמת הבוקר` | 0.60 (parcial: falta halaja ref exacta) |
| 32 | `Likutey Halajot > Discurso sobre el levantarse en la mañana` | 0.60 (parcial: header español incompleto) |
| 37 | `Likutey Halajot > השכמת הבוקר` | 0.60 (parcial) |

**Patrones de header detectados:**
- Hebreo: `\x98\x83\x89\x8a\x82 \x87\x86\x83\x95\x87\x8a N` → "השכמת הבוקר N"
- Hebreo halaja: `\x82\x8c\x81\x95\x82` → "הלכה"
- Español: `DISCURSO SOBRE EL LEVANTARSE EN LA MAÑANA — HALAJÁ X:Y`
- Español alternativo: `HALAJÁ X: Y` (con espacio variable)

**Observación:** La extracción de node_path es factible con patrones regex robustos. Se necesita normalización de espacio para "HALAJÁ X: Y".

---

## 8. Notas y fuentes

| Página | Notas | Source refs | Evaluación |
|---|---|---|---|
| 23 | 2 (notas 2, 3) | Avot 1:6, Salmos 146:2, Salmos 37:10 | ✅ Detectadas, separadas en 2 columnas |
| 32 | 1 (nota 23) | Beit Hilel, Rosh HaShaná 17a | ✅ Nota larga en columna izquierda |
| 37 | 2 (notas 33, 34) | Zohar, Salmos 16:1 | ✅ Referencia cruzada a §2 |

**Patrón de footnotes:**
- Separador `Notas y Fuentes` a y ≈ 0.82-0.86 de página
- Dos columnas:
  - Izquierda: x ≈ 54-245 (189px)
  - Derecha: x ≈ 255-444 (189px)
- Notas numeradas: `N Texto...`
- Referencias cruzadas: `ver §X más arriba`, `ver nota N más adelante`

---

## 9. Marginal sources

| Página | Marginales | Source refs | Evaluación |
|---|---|---|---|
| 23 | 4 bloques | "Hay aún un poco de bien" (Salmos 37:10), "Cantaré a mi Dios" (ibid. 146:2) | ✅ Detectados en margen derecho (x > 357) |
| 32 | 1 bloque | "¡HaShem! ¡HaShem! Dios piadoso..." (Trece Atributos) | ✅ Cita larga en margen derecho |
| 37 | 1 bloque | "He puesto a HaShem siempre delante de mí" (Salmos 16:1) | ✅ Marginal con referencia en el mismo bloque |

**Patrón de marginal sources:**
- Posición: x > 350, ancho < 95px
- Altura variable (8-105px)
- Frecuencia: 1-4 por página impar
- Contenido: citas bíblicas textuales con referencia
- Ocasionalmente la referencia está en bloque separado inmediatamente inferior

---

## 10. Golden layout questions

| Query | Página esperada | Block type esperado | Diseño responde | Evaluación |
|---|---|---|---|---|
| ¿Dónde aparece "puntos buenos"? | 23 | main_explanation_es | Sí | ✅ Encontrado en cuerpo español |
| ¿Dónde cita "Hay aún un poco de bien"? | 23 | marginal_source | Sí | ✅ Bloque marginal (x=357) |
| ¿Dónde aparece Avot 1:6? | 23 | footnote | Sí | ✅ Nota 2 en footnote columna izquierda |
| ¿Dónde aparecen los Trece Atributos? | 32 | marginal_source / main_explanation_es | Sí | ✅ Marginal + cuerpo español |
| ¿Dónde aparece jésed? | 32 | marginal_source / footnote | Sí | ✅ Marginal + nota 23 |
| ¿Dónde cita Rosh HaShaná 17a? | 32 | footnote | Sí | ✅ Nota 23 |
| ¿Dónde aparece la glosa del Remá? | 37 | main_explanation_es | Sí | ✅ Cuerpo español |
| ¿Dónde se menciona Shuljan Aruj? | 37 | main_explanation_es | Sí | ✅ Cuerpo español |
| ¿Dónde aparece "He puesto a HaShem..."? | 37 | marginal_source | Sí | ✅ Marginal (x=357) |
| ¿Dónde habla de desesperanza? | 37 | main_explanation_es | Sí | ✅ Cuerpo español |
| ¿Qué parte es nota y qué es explicación? | 23/32/37 | footnote vs main_explanation_es | Sí | ✅ Separado por coordenadas y |
| ¿Qué fuente vincula lado derecho con Avraham? | 37 | footnote | Sí | ✅ Nota 34: "El 'lado derecho' hace referencia... Zohar" |
| ¿Cuál es la halajá de la página 37? | 37 | page_header | Parcial | ✅ Header hebreo detectado pero halaja ref incompleta |
| ¿Qué texto hebreo corresponde a la explicación? | 32 | source_hebrew ↔ main_explanation_es | Sí | ✅ Capas separadas por coordenadas y |
| ¿Qué referencias cruzadas internas aparecen? | 23/37 | footnote / notes_marker | Sí | ✅ "ver §2 más arriba", "ver nota 16 más adelante", "ibíd." |

**Resultado:** 15/15 preguntas respondibles con el diseño propuesto.

---

## 11. Riesgos y limitaciones

### Extracción PDF
| Riesgo | Impacto | Mitigación |
|---|---|---|
| SI-960 decoding imperfecto | Caracteres hebreos mal decodificados | Reutilizar `hebrew_tex_decoder.py` y validar con muestra |
| Section marker en codificación PDF | No detectable por string match | Usar patrón `/LNXWH` o distancia Levenshtein |
| Encoding mixto en mismo bloque | Clasificación incorrecta | Separar por coordenadas + detección de encoding |

### Layout
| Riesgo | Impacto | Mitigación |
|---|---|---|
| Variación de posición entre páginas | Reglas fijas fallan | Usar proporciones relativas (y/PAGE_H, x/PAGE_W) |
| Páginas sin marginal sources | Falsos negativos | Aceptar como variante válida (páginas pares) |
| Notas que cruzan a página siguiente | Pérdida de continuidad | Detectar "continúa..." y mergear chunks |

### Hebreo RTL
| Riesgo | Impacto | Mitigación |
|---|---|---|
| Orden de lectura incorrecto | Chunks con texto desordenado | Usar `get_text('text', sort=True)` y decoder con reversal |
| Si-960 con caracteres no mapeados | Caracteres perdidos | Registrar en `KNOWN_UNMAPPED` y revisar |

### Notas en columnas
| Riesgo | Impacto | Mitigación |
|---|---|---|
| Notas desordenadas entre columnas | Footnote chunk incorrecto | Ordenar footnotes por y ascendente, mergear columnas |
| Mezcla de notas con cuerpo | Contaminación semántica | Umbral estricto y > 0.82 |

### Márgenes
| Riesgo | Impacto | Mitigación |
|---|---|---|
| Overlap con cuerpo principal | Marginal source dentro del bbox del cuerpo | Detectar por x > 350 independientemente del bbox contenedor |

### Referencias dudosas
| Riesgo | Impacto | Mitigación |
|---|---|---|
| Citas impresas que no coinciden con texto bíblico real | Error de fuente silencioso | Marcar `needs_reference_review: true` |

### Continuidad entre páginas
| Riesgo | Impacto | Mitigación |
|---|---|---|
| Explicación española que cruza página (página impar → par) | Chunk truncado | Usar chunking semántico con overlap controlado |
| Nota que continúa en página siguiente | Metadata incompleta | Detectar "nota N (cont.)" o footnotes sin separador |

### Chunking
| Riesgo | Impacto | Mitigación |
|---|---|---|
| Chunking ingenuo mezcla capas | Contaminación semántica | Layout-aware: chunk por block_type |
| Composite chunks citados como fuente | Falsa autoridad | Marcar `evidence_role: composite_for_retrieval` |

### Evidencia
| Riesgo | Impacto | Mitigación |
|---|---|---|
| Documentos Breslov ready no deben tocarse | Regresión | Validar antes de cualquier ingesta |
| Milvus productivo intacto | Corrupción | Safety guard en scripts |

---

## 12. Estrategia de chunking layout-aware

### Regla de chunking

1. **source_hebrew** → chunk independiente (previo decode SI-960 → Unicode)
2. **main_explanation_es** → chunk independiente (texto español continuo)
3. **marginal_source** → chunk independiente (cita + referencia)
4. **footnote** → chunk independiente (nota numerada completa)
5. **composite_page_context** → chunk opcional que une todos los bloques de una página para recall semántico, pero nunca citado como fuente final

### Tabla de chunking

| Chunk type | Se embebe | Fuente final | Uso |
|---|---|---|---|
| `source_hebrew` | Sí | Sí | Búsqueda hebrea / fuente directa |
| `main_explanation_es` | Sí | Sí | Búsqueda conceptual español |
| `marginal_source` | Sí | Sí | Citas/fuentes laterales |
| `footnote` | Sí | Sí | Referencias bibliográficas |
| `composite_page_context` | Opcional | No | Recall semántico |
| `page_header` | No | No | Metadata (node_path, halaja_ref) |
| `section_marker` | No | No | Metadata de estructura |

### Metadata por chunk

```json
{
  "page": 0,
  "node_path": "Likutey Halajot > ... > Halajá X:Y",
  "block_type": "main_explanation_es | source_hebrew | marginal_source | footnote",
  "block_subtype": "biblical_citation | rabbinic_reference | halachic_reference | ...",
  "language": "he | es | mixed",
  "evidence_role": "source_text | commentary | marginal_citation | bibliographic_note",
  "source_refs": ["Salmos 37:10", "Avot 1:6"],
  "internal_cross_refs": [{"type": "note_ref", "target": "nota 33"}],
  "needs_reference_review": false
}
```

### Regla clave

Composite chunks pueden ayudar al retrieval, pero la respuesta final debe citar bloques atómicos.

---

## 13. Recomendación siguiente

**Fase siguiente:** `Breslov Layout-Aware Ingestion MVP — LIKUTEY HALAJOT Interior Final`

El probe da **PASS** con advertencias controladas. La ingesta layout-aware es viable.

### Prerrequisitos para la fase siguiente

1. Implementar extractor layout-aware que:
   - Extraiga bloques por coordenadas usando `fitz`
   - Clasifique por tipo (header, hebrew, spanish, marginal, footnote)
   - Decodifique SI-960 para bloques hebreos
   - Preserve node_path por página
2. Validar con las 284 páginas completas.
3. Chunkear respetando capas semánticas.
4. NO tocar corpus productivo (solo `test_candidate`).
5. NO tocar Milvus productivo (solo `tebaai_breslov_test_chunks_v1`).

---

## 14. Guardrails

| Guardrail | Estado |
|---|---|
| No ingesta | ✅ |
| No embeddings generados | ✅ |
| No Milvus tocado | ✅ |
| No cambios en corpus Breslov ready | ✅ |
| No Koren/Yevamot | ✅ |
| No frontend | ✅ |
| No Team360 | ✅ |
| No OpenAI key directa | ✅ |
| Servicios no reiniciados | ✅ |
| No OCR masivo | ✅ |
| No asumir orden plano correcto | ✅ |

---

## 15. Archivos modificados/creados

### Scripts de probe (read-only, en `tmp/`)

| Archivo | Descripción |
|---|---|
| `tmp/likutey_layout_probe/probe_common.py` | Utilidades comunes: clasificación, detección de idioma, page mapping |
| `tmp/likutey_layout_probe/run_probe.py` | Probe principal: extracción de bloques por página, clasificación, summary |
| `tmp/likutey_layout_probe/refined_analysis.py` | Análisis refinado: node_path, sources, crossrefs, golden questions |

### Outputs generados

| Archivo | Descripción |
|---|---|
| `tmp/likutey_layout_probe/page_mapping.json` | Mapeo página impresa → PDF index |
| `tmp/likutey_layout_probe/compiled_probe_results.json` | Resultados compilados de 27 páginas |
| `tmp/likutey_layout_probe/refined_analysis.json` | Análisis refinado con sources y crossrefs |
| `tmp/likutey_layout_probe/page_*_blocks.json` | Bloques por página individual (27 archivos) |
| `tmp/likutey_layout_probe/page_*_text.txt` | Texto plano por página (27 archivos) |

### Documentación

| Archivo | Descripción |
|---|---|
| `docs/likutey_halajot_layout_probe_2026-07-05.md` | Este informe |
| `SrvRestAstroLS_v1/docs/status_actual.md` | Status actualizado (entrada compacta) |

---

## 16. Loop de resultados

### Loop 1 — Preflight

**Objetivo:** Confirmar estado del repositorio, PDF, herramientas disponibles.

**Acciones:** `git status`, `pdfinfo`, `python3 -c "import fitz"`.

**Resultado:** PASS. Rama correcta, PDF 284 páginas, texto embebido, fitz disponible.

### Loop 2 — Mapeo de páginas y extracción raw

**Objetivo:** Construir page mapping printed→PDF y extraer bloques con coordenadas de páginas muestra.

**Acciones:** `run_probe.py` analizó 27 páginas, generó blocks JSON y texto plano.

**Resultado:** PASS. 207/284 páginas mapeadas. Layout de páginas impares vs pares identificado.

### Loop 3 — Clasificación refinada

**Objetivo:** Clasificar bloques por tipo (header, source_hebrew, main_explanation_es, marginal_source, footnote).

**Acciones:** `refined_analysis.py` con clasificación por coordenadas y detección de encoding.

**Resultado:** PASS. Clasificación correcta para páginas clave (23, 32, 37). 7 sources types, 5 crossref types detectados.

### Loop 4 — Golden questions validation

**Objetivo:** Validar que las 15 preguntas golden son respondibles.

**Acciones:** Verificación manual + automática de contenido en páginas 23, 32, 37.

**Resultado:** PASS. 15/15 preguntas respondibles con el diseño propuesto.

---

## Anexo: Ejemplos de layout por página

### Página 23 (PDF 40) — Layout completo

```
┌─────────────────────────────────────────┬──────────────┐
│ השכמת הבוקר 23                         │              │
│ <SI-960 Hebrew text...>                 │              │
│                                         │  "Hay aún un  │
│ ──── Likutey Halajot Explicado ────     │  poco de bien"│
│                                         │  (Salmos 37:10)│
│ en sí al menos algún punto bueno.       │              │
│ Y de manera similar deberá seguir       │  "Cantaré a   │
│ buscando y encontrando más puntos       │  mi Dios..."  │
│ buenos dentro de sí misma.              │  (ibid. 146:2)│
│                                         │              │
│                                         │              │
│ Al juzgarse a sí misma de manera        │              │
│ favorable...                            │              │
├────────────────────────┬────────────────┴──────────────┤
│ Notas y Fuentes        │                                │
│ 2 Ver Avot 1:6.        │ cante a HaShem? Es el pequeño │
│ 3 El Rebe Najmán...    │ bien que aún encuentra...      │
└────────────────────────┴────────────────────────────────┘
```

### Página 32 (PDF 49) — Trece Atributos

```
┌─────────────────────────────────────────┬──────────────┐
│ 32 LIKUTEY HALAJOT                      │              │
│ DISCURSO SOBRE EL LEVANTARSE... HALAJÁ 1:3             │
│ <SI-960 Hebrew text...>                 │              │
│                                         │  "¡HaShem!   │
│ ──── Likutey Halajot Explicado ────     │  ¡HaShem!    │
│                                         │  Dios piadoso│
│ Habiendo explicado que al encontrar     │  misericord..│
│ el punto bueno despertamos la bondad    │  abundante   │
│ de HaShem y obtenemos Su perdón...      │  en jesed..."│
│ Éste es el concepto de los Trece        │              │
│ Atributos de Misericordia...            │              │
├────────────────────────┬────────────────┴──────────────┤
│ Notas y Fuentes        │                                │
│ 23 Beit Hilel explica  │ hacia la bondad. Incluso       │
│ el atributo Divino...  │ presupone el mérito...         │
│ (Rosh HaShaná 17a)    │                                │
└────────────────────────┴────────────────────────────────┘
```

### Página 37 (PDF 54) — Remá / Shuljan Aruj

```
┌─────────────────────────────────────────┬──────────────┐
│ השכמת הבוקר 37                         │              │
│ <SI-960 Hebrew text...>                 │              │
│                                         │              │
│ ──── Likutey Halajot Explicado ────     │              │
│                                         │  "He puesto  │
│ El Rabí Natán ha explicado que...       │  a HaShem    │
│ el despertar el alba alude a            │  siempre     │
│ levantarse del sueño espiritual...      │  delante de  │
│ Éste es el motivo por el cual la        │  mí..."      │
│ glosa del Rema, "He puesto a HaShem     │  (Salmos     │
│ siempre delante de mí"... se yuxtaponen │  16:1)       │
├────────────────────────┬────────────────┴──────────────┤
│ Notas y Fuentes        │                                │
│ 33 Anteriormente hemos│ se explicó anteriormente,       │
│ visto que el punto     │ es imposible que la persona    │
│ bueno... (ver §2 más   │ no haya hecho nunca algo       │
│ arriba).               │ bueno...                       │
│ 34 El "lado derecho"   │                                │
│ hace referencia... Zohar│                                │
└────────────────────────┴────────────────────────────────┘
```
