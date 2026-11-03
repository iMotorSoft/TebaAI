# Historical extraction solution recovery / regression audit V1

> Snapshot de auditoría previa preservado. Cierre posterior por trazabilidad de
> las 11 capacidades, divergencias y plan de integración:
> [closure/README.md](closure/README.md) — HISTORICAL_SOLUTION_AUDIT_PASS.
> READY_FOR_C_REINGEST sigue NO; este texto conserva el estado anterior.

## A. Veredicto y alcance

**HISTORICAL_SOLUTION_AUDIT_BLOCKED** — inventario y comparación sustanciales,
pero NO se emite `TEBAAI_BRESLOV_HISTORICAL_EXTRACTION_SOLUTION_AUDIT_V1_PASS`.

Motivo concreto: la búsqueda localizó 1368 archivos tracked, incluidos 839
archivos de reportes y 74 archivos de tests backend. Se leyeron y trazaron los
componentes centrales indicados abajo, no todos los reportes/ADRs/goldens
localizados. `located-inventory.json` es un inventario de LOCALIZADOS, no una
certificación de lectura exhaustiva. Tampoco se reprodujo el runtime histórico
con sus dependencias originales ni se interrogó el corpus actual por API/PG.
No afirmar exhaustividad, cero regresiones adicionales ni fidelidad integral.

Sí se demuestran bypasses, conocimiento reutilizable, riesgos de reutilización
y dos regresiones de compatibilidad offline en las mismas páginas. No son una
certificación del resultado actual de retrieval end-to-end.

Gates de reconstrucción, extracción visible e ingesta limpia: abiertos.
`READY_FOR_C_REINGEST = NO`.

## Evidencia reproducida

- `same-pages-offline.json`: outputs completos, bloques, spans, métricas,
  señales y probes de compatibilidad para PDF 2/41/51/53/55/56/143.
- Fuente local original: SHA-256
  `440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a`.
- Algoritmos antiguos **replay con dependencias instaladas**, no snapshots
  ejecutables del entorno antiguo. Parser layout y proyección geométrica sin
  cambios; extracción V2 equivalente a `get_text('text')` + limpieza de NUL.
- Actual: `page_markdown` canónico del worktree, sin persistencia.
- Experimental: Markdown guardado por la fase previa; NO se regeneró ni se
  integró. Presente para las cinco páginas solicitadas, no 51/53.
- Tests focalizados: **317 PASS**, 16 suites, sin servicios externos.
- `history-search.txt`: búsqueda `git log --all` por Breslov/Hebrew/Likutey/PDF/
  page-first/layout. Además se inspeccionaron `git show`, `git blame`,
  `git log --follow` y búsqueda histórica `-G` de ToUnicode/texttrace/overpaint/
  white rectangle/fontmap/glyph mapping en Python.
- `git grep` cubrió todos los conceptos mínimos pedidos en archivos tracked;
  `find`/`rg` incluyeron variantes Halakhot/Halajot, untracked y probes.

## B. Artefactos históricos centrales

Paths backend relativos a `SrvRestAstroLS_v1/backend/`.

| Artefacto | Tipo / capa | Commit/path | Propósito probado | Vigencia |
|---|---|---|---|---|
| SI-960/Tiqwah decoder | código / NORMALIZATION | `modules/library/hebrew_tex_decoder.py`, `e76c9d2`, `c917c4e` | TeX/HE8 a Unicode; reversa por palabra | Presente, NO safe as-is para C |
| Parser LH layout-aware | código / EXTRACTION + STRUCTURE | `scripts/likutey_layout_parser.py`, `8f5fe0b` | bbox, roles, folio, referencias, decoder selectivo | PRESENT_BUT_BYPASSED por worker |
| Ingestor LH layout-aware | script | `scripts/ingest_likutey_halajot_layout_aware.py` | bloques→chunks, roles/citable/metadata | Referencia; no ejecutar writes |
| Auditoría layout LH | reporte | `data/reports/breslov/2026-07-05-likutey-layout/` | 2652 bloques, 2222 vectores; goldens acotados | Evidencia histórica, no certificación Unicode |
| Geometry Hebrew projection | código / proyección y EXTRACTION en LMI | `modules/library/hebrew_pdf_layout.py`, `35e266f` | rawdict, clusters, X descendente, marcas, gaps | Activo en consumidores históricos; bypass worker |
| LMI literal ingestion | script / EXTRACTION + INDEXING | `scripts/ingest_likutey_moharan_i_literal.py` | usa readable_page/readable_line | No es parser LH |
| LMII layout projection | código / proyección | `modules/library/likutey_moharan_ii_layout.py` | usa readable_line, roles por página | No es decoder CID |
| LH page-first V1 | script/ADR | `scripts/ingest_likutey_halajot_page_first.py`, `d22f3ed`; reporte 2026-07-14 initial-inventory | página completa antes de clasificar | Referencia; estructura inicialmente unresolved |
| Detectores LH estructura/zonas/notas | scripts / STRUCTURE | `likutey_halajot_structural_detector.py`, `likutey_halajot_fine_zone_detector.py`, `likutey_halajot_note_source_detector.py`; `2301d60`, `9cf9046`, `f9bbe1b` | etiquetas visibles, offsets/hash, números de nota | PRESENT_BUT_BYPASSED por worker |
| Nominal reference detector | script / STRUCTURE + RETRIEVAL | `likutey_halajot_nominal_reference_detector.py`, ADR-006/007/008 | fuentes nominales y resolución investigativa | Localizado; revisión completa pendiente |
| LH page-first V2 | script / EXTRACTION + STRUCTURE | `scripts/ingest_likutey_halajot_page_first_v2.py`, `e31520d` | full page, headings/notas/folios, 268 chunks | Presente; no llamado por worker |
| Page-first/editorial contracts | ADR/docs | ADR-011/013/014, `docs/breslov/page-first-and-editorial-retrieval-conventions.md` | páginas antes de chunks, roles y asociaciones | Vigentes; implementación no equivale al contrato |
| Heading literal recovery | código / RETRIEVAL | `71af4a2`, ADR-010, `simple_research_rag.py`, `simple_research_repository.py` | título real vs evidencia temática | Activo; no decodifica PDF |
| Canonical editorial evidence | código / RETRIEVAL | `b8d5a26`, cierre `34b1e17`, ADR-016 | deterministic PRIMARY, verso exacto, folio RTL | Activo; presupone superficies compatibles |
| Ligature literal normalization | código / NORMALIZATION + RETRIEVAL | `9431d0e`, cierre `31a1f65`, ADR-020, `pdf_ligature_normalization.py` | NFKC, ligaduras, variantes/glosas para matching | REUSE AS-IS; importado por nueva ingesta |
| Hebrew search normalization | código / NORMALIZATION + RETRIEVAL | `hebrew_lexical_normalizer.py`, ADR-007, `126b678` | NFC/NFKC, variantes sin niqqud, spacing, matching | Activo; NO restaura CID ni texto citado |
| LM XV columns | scripts/reportes | `688e1d8`, `likutey_moharan_xv_kdp_layout_profile.py`, `ingest_likutey_moharan_xv_kdp_page_first_column_aware.py` | detectar posibles columnas y guardar bbox/order labels | Parcial; no certifica lectura column-major |
| Worker generic page-first | código | `0b364cc`, `page_first_pipeline.py`, `page_first_gateway.py`, ADR-022 | servicio reusable, Markdown, paragraphs, manifest | Activo; divergencia deliberada de scripts |
| Source-backed boundary repairs | código / EXTRACTION | `1fa9290`, `pdf_hebrew_fidelity.py` | metadata/geometría: espacios sintéticos, niqqud acotado, ecuaciones | Activo; no soluciona C integralmente |
| CID/font program recovery | experimento / EXTRACTION | untracked `pdf_font_unicode.py` + profiles JSON | ToUnicode en memoria por hash exacto de font | No integrado; mecanismo distinto a SI-960 |

Los cuatro commits obligatorios existen y fueron inspeccionados; sus cierres
son docs/evidencia, no implementaciones adicionales. ADR-016 y ADR-020 se
leyeron completos. También ADR-010, ADR-014, ADR-007 Hebrew y ADR-022, las
convenciones y ADRs de reportes layout/page-first/estructura/fine zones/LM XV.
ADR-011/013 y los ADRs nominales están localizados, no certificados como lectura
completa en esta fase.

## C. Matriz de problemas: una clasificación por problema

Clasificación de trabajo sustentada abajo. `PRESENT_BUT_BYPASSED` describe
conexión, NO es una segunda clasificación del problema.

| Problema actual | ¿Estudiado? | Clasificación | Solución histórica / capa | Tests | Acción / estado |
|---|---|---|---|---|---|
| U+FFFD / CID | Sí, codificaciones antiguas, no mismo CID | PARTIALLY_SOLVED | SI-960/HE8; no font-program ToUnicode histórico hallado | test_hebrew_tex_decoder | ADAPT conocimiento; no aplicar tabla TeX a C |
| Hebrew logical order | Sí | OLD_SOLUTION_NEEDS_ADAPTATION | hebrew_pdf_layout readable_line: clusters/X descendente | test_likutey_moharan_ii_layout | ADAPT; bypass worker, no CID ni inverse bidi |
| Niqqud ownership | Sí | OLD_SOLUTION_NEEDS_ADAPTATION | preceding-cluster/nearest-X antiguo; geometry repair reciente | test_likutey_moharan_ii_layout, test_pdf_hebrew_fidelity | ADAPT conservador; no nearest-owner global |
| RTL/LTR mixed refs | Sí, matching/render | PARTIALLY_SOLVED | ADR-016 límites 16:1, frontend aislamiento; no inverse-bidi extractor | test_canonical_editorial_evidence_selection | REUSE matching; referencia extraction sigue pendiente |
| Printed pages RTL | Sí | REGRESSION | _resolve_printed_page y _canonical_printed_page, ADR-016 | test_canonical_editorial_evidence_selection | ADAPT contrato Markdown / metadata; offline FAIL actual |
| Headings | Sí | ALREADY_SOLVED_AND_REUSABLE | ADR-010/016; líneas Markdown/content y canonical PRIMARY | test_canonical_editorial_evidence_selection | REUSE AS-IS + revalidar chunk boundaries |
| Footnotes | Sí | REGRESSION | marker/body/anchor, notas 35/36; helper embedded note | test_editorial_evidence_v2, tests ligaduras | PORT estructura mínima; note35 offline reconocimiento perdido |
| Columns | Sí | PARTIALLY_SOLVED | roles/márgenes LH; LM XV x-clusters, bbox/order labels | test_lm_xv_kdp_page_first_column_aware | REFERENCE ONLY + TEST ONLY, no solver completo demostrado |
| Reading/block order | Sí | OLD_SOLUTION_NEEDS_ADAPTATION | blocks sort=True, proyección top-to-bottom, LH bbox roles | layout tests + validadores | ADAPT fronteras; seqno no es orden lector |
| Ligatures | Sí | ALREADY_SOLVED_AND_REUSABLE | ADR-020 normalize_pdf_search_text/variantes | test_pdf_ligature_normalization | REUSE AS-IS; ya conectado |
| Hidden white overlays | No antecedente suficiente encontrado | TRULY_NEW | candidato actual paint-order + ink containment | test_pdf_text_visibility + conservative regression | conservar aislado, certificar antes de integrar |

Conteo de trabajo: **2 reutilizables, 3 requieren adaptación, 2 regresiones de
compatibilidad offline, 3 parcialmente resueltos, 1 nuevo**. No significa que
existan siete/once fixes listos, ni que las páginas hebreas fueran PASS antes.
La etiqueta nuevo está acotada a las búsquedas realizadas: la lectura exhaustiva
del inventario sigue pendiente, por eso no se cierra el gate de auditoría.

## D. Pipeline histórico: NO había un único camino

### Layout LH

`PDF → PyMuPDF dict/spans + blocks sort=True → decoder SI-960 selectivo →
roles por bbox + referencias + printed page → bloques → chunks por bloque →
embeddings → evidence/retrieval`.

LH coords: PAGE_W=496, PAGE_H=694; header y<9%; margen derecho x>70%,
width<25% (alternativa x>65%, x1>85%, width<20%); notas y>82%; hebreo
upper-mid 9–34% + señal de idioma. **No segmentador general de columnas**.
`parse_page` usa blocks sort=True, no custom bidi ni font program/CID map.

### Page-first LH V1 y detectores

`PDF → página completa → page anchor/citable_page_text unclassified →
detectores estructurales → zonas → notas/fuentes → referencias → retrieval`.
Reporte notas: 203 bloques analizados, 406 notas, 68 block_only. Conserva
límites conocidos; no completa notas ambiguas mediante inferencia.

### Page-first LH V2 real

`PDF → get_text('text') + remove NUL → full page → heading/note/reference
signals → page/zones/chunk full-page normalizado → embeddings → editorial
matching/evidence`.

**Discrepancia histórica explícita:** ADR-014 describe PyMuPDF4LLM/Markdown y
bloques→chunks, pero el script V2 usa get_text('text') y full-page chunks.
No reconstruir la historia solo desde el ADR o el status. V2 no llama al
SI-960 decoder ni a readable_page. Sus PASS de Salmos/heading/notas no
certifican el hebreo.

### Geometry Hebrew (otras obras)

`rawdict → readable_line/readable_block/readable_page → Unicode projection`.
Consumidores: LMII projection, investigative_qa_v1 y LMI literal ingestion.
Proyección cita/consulta histórica ≠ extracción canónica LH V2.

## E. Pipeline actual del Gestor

`UI upload → Content Manager API/job → durable worker →
ConcretePageFirstPipeline → extract_pdf_page_first → page_markdown →
PyMuPDF4LLM.to_markdown + repair_markdown(rawdict) → analyze_page →
original_markdown + normalize_pdf_search_text separado → library_pages_v2 →
paragraph_chunks(1400,150,1) → library_document_chunks → embeddings → Milvus`.

`page_first_gateway.py` persiste headings/footnotes/references en layout_notes
pero no bloques editoriales/relaciones; chunks reciben `block_type=page_first_v1`,
`evidence_role=page_text`, sin printed_page_label/section_title específicos.
El texto de página sí se conserva antes de chunking. No decir que toda la
arquitectura page-first se perdió.

## F. Divergencias / respuesta central

**¿Dejó de utilizar capas especializadas? PARTIAL.**

- YES para worker vs camino layout LH: no imports/calls a likutey_layout_parser,
  decoder, detectores de zonas/notas ni relaciones.
- YES respecto de capacidades geométricas existentes en LMI/LMII; worker no
  llama a hebrew_pdf_layout. NO prueba que LH V2 dependiera de ellas.
- NO para normalización de ligaduras: importada en pipeline y gateway y sigue
  presente en carriles de matching.
- NO para almacenamiento page-first y normalización separada.
- PARTIAL para estructura: señales prudentes en page metadata, sin transferencia
  íntegra de roles y asociaciones a los chunks actuales.
- Retrieval histórico permanece en simple_research_rag/repository y
  page_first_evidence; no modifica los strings dañados de extracción.

Desde qué cambio: `0b364cc` creó el servicio reusable con PyMuPDF4LLM por página,
no dispatch documental. Su inventario/ADR-022 explican por qué los scripts con
paths/codes/SQL/IDs específicos no se adoptaron. `1fa9290` agregó page_markdown
source-backed; git blame confirma que NO reconectó los parsers antiguos.
No hay evidencia de eliminación de estos módulos: siguen en HEAD. Búsqueda
`git log --all --diff-filter=D` en módulos/scripts no encontró commits de
borrado; `--follow` del parser apunta a su incorporación en `8f5fe0b`.
Refactors o código equivalente eliminado fuera de esos paths requieren terminar
la revisión histórica antes de certificar ausencia global.

## G. Regresiones y comparación misma página

| Caso | Antes | Ahora offline | Causa probada / límite |
|---|---|---|---|
| PDF55 / printed37 | Histórico ADR-016 20/20 PASS; replay raw→ambos resolvers=37 | Markdown actual→ambos resolvers=None | Header `����� ... **37**`; reglas esperan control/binario o número sin markup; gateway no persiste folio |
| PDF56 / nota35 | Golden histórico PRIMARY note35; replay raw→embedded helper=35 | Markdown actual→embedded helper=None, analyze_page no identifica footnotes | Markdown/superíndices/estructura alteran formas previstas; NO prueba de FAIL del API actual |

Otras páginas con folio offline perdido: 41/23, 51/33, 53/35, 56/38, 143/125.
Son probes de compatibilidad, no PG actualizado ni API end-to-end.

| PDF | U+FFFD old layout replay | U+FFFD canonical actual | U+FFFD experimento guardado | Resultado |
|---|---:|---:|---:|---|
| 2 | 0 | 24 | 0 | old también tiene 0 letras HE: Latin/control ≠ recuperación |
| 41 | 0 | 804 | 4 | old false-decoding convierte incluso ES; candidato mixto unresolved |
| 55 | 0 | 630 | 4 | old folio=37; actual matching Salmos sigue presente; lógico no certificado |
| 56 | 0 | 1047 | 2 | old false-decoding afecta nota35; actual helper no la reconoce |
| 143 | 0 | 865 | 4 | artifact header conocido ya en revisión editorial histórica |

Cero U+FFFD antiguo **NO** equivale a Unicode correcto: el raw antiguo contiene
Latin Extended/control y el decoder puede convertir español indiscriminadamente.
No clasificar Unicode/logical order integral como regresión PASS→FAIL sin un
PASS histórico de ese mismo texto.

Ejemplos conservados en JSON:
- PDF41 raw `en sí al menos algún punto bueno...` termina pseudohebreo.
- PDF51 raw `Y así HaShem se volvió favorablemente hacia Moshé...` también.
- PDF55 `Y esta idea, de que el encontrar los propios puntos buenos...` también.
- PDF56 `35 Ver §1 más arriba... El hombre se une a HaShem...` también.
La detección SI-960 por distribución de letras/high-byte es insuficiente para C.

## H. Soluciones reutilizables / plan mínimo

**Reuse as-is:** pdf_ligature_normalization y carriles exactos de referencias,
ranking determinista, estabilidad editorial (sin alterar cita).

**Adapt:** geometría/clusters de hebrew_pdf_layout; contrato de página impresa
para representación Markdown; límites y asociaciones de notas/roles históricos.
No copiar las heurísticas nearest-owner ni threshold fijo de espacio sin QA.

**Reconnect / port:** capacidades genéricas de metadata de folio/rol/anchor,
no orquestadores SQL/documentales enteros. Primero reproducir sin servicios la
compatibilidad Markdown de los helpers históricos.

**Test only:** goldens existentes 51/33,53/35,55/37,56/38, notas35/36; LMII/LMI
para niqqud; usar fixtures existentes antes de crear duplicados.

**Reference only:** perfiles LH/LM XV y ADRs work-specific.

**Do not reuse as-is:** decoder SI-960 sobre C; ingestors históricos con
paths/IDs/SQL; `extract_pdf_columns_with_page_markers` como supuesto solver
column-major (su propio docstring admite interleaving); proyección global
nearest-mark y reversa de strings; seqno como reading order.

## I. Truly new, acotado a búsqueda

Filtrado probado de texto oculto por rectángulos blancos posteriores usando
paint order + trace/ink + opacidad/compositing. No apareció implementación
histórica equivalente en rg actual ni git log -G Python. En contraste, glyph
mapping, orden geométrico y niqqud NO son temas nuevos. La recuperación actual
por hash de programa Type0/Identity-H sin ToUnicode es un mecanismo no hallado
en el decoder TeX antiguo; no afirmar que ya fue resuelto por SI-960.

## J. Experimentos actuales

### pdf_text_visibility.py

- duplicates old work: **NO encontrado**.
- genuinely new: **YES, dentro del alcance buscado**.
- recommendation: mantener aislado. 385 exclusiones/286 retenidos provienen de
  reporte anterior; no certifican cero texto visible perdido. Falta ablación
  exacta/render certificate. No integrar ni aumentar supresión por heurística.

### pdf_text_reconstruction.py

- duplicates old work: **YES, parcialmente** (X descendente, graphemes, niqqud,
  raw geometry ya en hebrew_pdf_layout).
- genuinely new: **YES en salvaguardas**, no como primer parser hebreo:
  texttrace/seqno+baseline, owner único, Counter conservation, mixed-direction
  diagnostic/fail-closed, sin normalización ni inserción de espacios.
- conflicts: el antiguo normaliza NFKC/NFC, quita espacios y agrega por gap,
  adjunta anterior/nearest; el nuevo conserva codepoints/espacios y exige owner
  único. Mezclarlos directamente cambia el contrato.
- recommendation: comparar sobre fixture histórico LMII + C actual, extraer
  conocimiento reusable solo después de completar auditoría. No fusionar código.

## K. Tests / fixtures / goldens recuperados

Todos los paths backend siguientes son `tests/`. Las 16 suites de esta tabla
se ejecutaron ahora; relevancia vigente sí, con los límites señalados.

| Suite | Qué prueba / qué NO prueba | Casos/fixture |
|---|---|---|
| test_hebrew_tex_decoder.py (46) | SI-960, mappings/niqqud presentes/orden de palabras; NO C font program ni ownership integral | inline Tiqwah, pág704/29, Mybwtk |
| test_hebrew_lexical_normalizer.py (52) | search variants/spacing/niqqud; no extracción | inline Unicode/copy-paste |
| test_hebrew_pipeline_contract.py (12) | contratos path/fallback/guard/decoder; no ingesta real actual | inline |
| test_likutey_moharan_ii_layout.py (6) | glyph geometry `אָמַר לִ`; layout LMII; real projection conditional | inline rawdict, LMII28 |
| test_likutey_moharan_xv_kdp_layout_profile.py (1) | reporte perfil; no columna semántica | report layout_profile_pages.json |
| test_lm_xv_kdp_page_first_column_aware.py (3) | source hash/rules514/historical QA; no literal reading-order golden | column_rules_report.json, lm_xv_page_first_qa_results.json |
| test_canonical_editorial_evidence_selection.py (21) | headings, verso boundary, deterministic ranks, RTL binary37 | inline + fixtures/likutey_halajot_page_first_v2_acceptance.json |
| test_page_first_evidence.py (27) | page/evidence location metadata | inline page/heading fixtures |
| test_editorial_evidence_v2.py (36) | roles, footnote marker/body/heading associations | inline note35/36/ref |
| test_pdf_ligature_normalization.py (14) | NFKC/variants/glosas/original/niqqud | fixtures/pdf_ligature_literal_normalization_v1.json |
| test_page_first_pipeline.py (13) | extractor/service stages/adapters/signals/normalization | synthetic PDF, fake gateway |
| test_pdf_hebrew_fidelity.py (23) | boundary repairs source-backed; current local extension | fixtures/hebrew_pdf_fidelity/case_a.json, case_b.json |
| test_pdf_font_unicode.py (10) | C candidate hash-map guard/recovery | existing untracked profiles |
| test_pdf_text_reconstruction.py (20) | conservation/owner/fallback; no full bidi | fixtures/likutey_halajot_reconstruction_v1.json |
| test_pdf_text_visibility.py (26) | conservative paint occlusion | synthetic/offline |
| test_pdf_visibility_conservative_regression.py (7) | ambiguous/blend retained | synthetic/offline |

Comando: desde backend, `PYTHONDONTWRITEBYTECODE=1 uv run pytest -p
no:cacheprovider` seguido por las 16 suites anteriores. 317 passed en 4.98s.

### Goldens históricos (sin duplicar fixtures)

- `fixtures/likutey_halajot_page_first_v2_acceptance.json`: Mishkán51/33,
  Bondad53/35, Salmos55/37, nota35 y Melodías56/38; match types/source layers,
  expected PRIMARY y stable IDs (IDs son de representación histórica).
- `fixtures/pdf_ligature_literal_normalization_v1.json`: nota36, `reﬁ namiento`,
  `Inﬁ nito`, Salmos16:1 vs16:10/16:11/116:1; preserving original.
- `data/reports/breslov/2026-08-03-canonical-editorial-evidence-selection-v1-dev/`:
  case-salmos.json, case-mishkan/bondad/melodias, api-five-cases-5x.json,
  salmos-determinism-20x.json, negatives.json.
- `data/reports/breslov/2026-08-04-pdf-ligature-literal-normalization-v1-dev/`:
  literal-batch-25.json, note-36-before/after, Hebrew/editorial regressions,
  inventory, negative joins, offset mapping.
- Hebrew with/without niqqud golden `וּמִצְרַיִם נָסִים לִקְרָאתוֹ` / `ומצרים
  נסים לקראתו`: **LMII PDF14**, mismo ev-f0990f7b1498aaf4, NO golden LH.
- `data/reports/breslov/2026-07-16-research-workspace-v1/`: grapheme/copy-paste
  contracts, Unicode/HTTP/DOM batches; copy-paste fuente **LMI PDF96/printed76**,
  NO LH. Esta capa era query parsing/matching, no canonical PDF repair.
- Probes LH históricos en `2026-07-05-likutey-layout/probe/`:
  page_054_printed_037 = PDF55; page_055_printed_038 = PDF56;
  page_050_printed_033 = PDF51. Naming zero-index: no off-by-one en comparación.
  `page_001_text.txt` = PDF2 muestra Latin/control, no Unicode HE correcto.
- E2E `astro/e2e/research-hebrew.spec.ts`: 4 casos `skip` explícitos por era/
  selección/semántica; no deben contarse como gate actual ejecutado.
- E2E `research-structural-heading.spec.ts` y
  `research-pdf-ligature-normalization.spec.ts`: activos condicionados a
  credenciales, NO ejecutados ahora (sin app/servicios).

No se creó fixture de tests. `same-pages-offline.json` es evidencia de auditoría,
no un nuevo golden aprobado.

## L. Siguiente paso concreto (aún auditoría, no fix)

1. Terminar lectura/trace del inventario localizado, prioritariamente ADR-011/
   013/nominales, reportes readiness, goldens de estructuras y historial de
   extractors/normalización; distinguir located de examined.
2. Recuperar outputs históricos guardados para PDF41/143 (cuando existan) y
   dependencia/versiones históricas; replay actual no reemplaza esas pruebas.
3. Completar matrix de suites restantes y rutas de SQL/retrieval hacia el
   corpus nuevo **sin writes ni reingesta**. No hace falta conectar servicios
   para terminar el trace estático; cualquier lectura viva necesita mantener
   el alcance read-only explícito.
4. Solo al cerrar el audit gate, diseñar adaptación mínima de folio/nota35 y
   metadata/roles, reutilizando código existente. NO escribir otro parser HE.
5. Conservar candidato visibility y seguridad de reconstruction; no integrar
   ninguno ni certificar corpus hasta QA real de las mismas cinco páginas.

## M. Git / validación / impacto / riesgos

Branch: `feature/console-backend-core`.
HEAD initial/final: `1fa9290bdc7840e7277a998aa3ca66345c6080ee`.
Code modifications por esta auditoría: **NO**.
Archivos nuevos: únicamente este directorio de reportes (README, inventory,
history-search, same-pages-offline). Cambios experimentales previos preservados.
Commit/push/rebase/reset/clean/stash/merge/reingest: **NO**.
`git diff --check`: PASS. Sin LAT ni @lat edits; lat check no aplica.
Frontend sin cambios por esta auditoría; check/build/E2E no re-ejecutados.
Impacto: evidencia read-only y mapa de reutilización; runtime/corpus intactos.
Riesgos: pseudohebreo antiguo puede parecer mejora; counts de U+FFFD no prueban
fidelidad; tests históricos con PASS no cubren surfaces Markdown nuevas;
classification de ausencia histórica aún acotada por lectura pendiente.

## N. Producción y servicios

Production modified: **NO**. PG/Milvus writes: **NO**.
Sin conexiones PG/Milvus/LiteLLM, reset, reingesta ni gestión de servicios.

## Respuestas obligatorias

| Pregunta | Respuesta con alcance |
|---|---|
| ¿Solución histórica Unicode/CID? | PARCIAL: TeX Unicode sí; mismo font/CID C no demostrado |
| ¿Orden lógico hebreo? | SÍ, geometry y TeX; necesita adaptación para C |
| ¿Niqqud? | PARCIAL: mapping/preservación/query y geometry; owner C integral no |
| ¿Columnas/layout? | PARCIAL: bbox/roles/perfil/order labels, no general column solver probado |
| ¿Páginas impresas RTL? | SÍ: ADR-016/helper/tests; incompatibilidad Markdown reproducida |
| ¿Goldens reales LH? | SÍ: 51/33,53/35,55/37,56/38, notas35/36 |
| ¿Pipeline nuevo reutiliza soluciones? | PARCIAL: NFKC/ligaduras/page-first sí; parsers/roles/decoder no |
| ¿Presentes pero bypassed? | SÍ: layout parser, Hebrew geometry, detectores estructurales |
| ¿White overlays realmente nuevo? | NO DETERMINADO exhaustivamente; TRULY_NEW en alcance buscado |
| ¿Reimplementamos algo resuelto? | SÍ parcialmente: geometría/graphemes ya existían; C completo no resuelto |
