# Historical Solution Recovery → Regression Trace → Reuse / Adapt / Reconnect

## A. VEREDICTO

**HISTORICAL_SOLUTION_AUDIT_PASS**

`TEBAAI_BRESLOV_HISTORICAL_EXTRACTION_SOLUTION_AUDIT_V1_PASS`

`READY_FOR_C_REINGEST = NO`

Cierre **de trazabilidad de las 11 capacidades**, no de fidelidad del producto.
La [auditoría previa](../README.md) queda preservada como snapshot BLOCKED;
este informe la sucede. Los 839 reportes son universo de búsqueda, no checklist.
No se certifica que Likutey Halajot esté corregido ni que no existan otros bugs.
No se implementó el plan. No ingestion, servicios ni producción.

Evidencia reproducible:

- [problems.json](problems.json): **11/11**, nombres EXACTOS de la matriz C
  anterior, con los 13 campos obligatorios por problema, clasificación única
  y acción. Sin UNKNOWN; ausencias históricas se declaran expresamente.
- [trace_offline.py](trace_offline.py), [trace.json](trace.json): mismo PDF
  verificado por SHA, cuatro páginas, raw histórico/V2, raw **con flags reales
  del extractor actual**, Markdown antes de reparación, canónico, chunks y
  helpers reales. Archivos `pdf-{51,53,55,56}-*.txt` conservan los inputs completos.
- [tests.txt](tests.txt): **425 PASS**, 20 suites existentes; ningún test nuevo.
- [helper-provenance.json](helper-provenance.json): AST idéntico al commit
  histórico para ambos resolvers, ambos helpers embedded, get_page_text y
  parse_page. La regresión no procede de modificar esos helpers.
- [visibility-history.txt](visibility-history.txt),
  [visibility-current-search.txt](visibility-current-search.txt),
  [decoder-history.txt](decoder-history.txt), [deletions.txt](deletions.txt).
- Evidencia histórica persistida: probes reales 2026-07-05; casos canónicos
  2026-08-03; nota36 y batch literal 2026-08-04. No se inventó un PASS antiguo.

Replay con PyMuPDF / PyMuPDF4LLM **1.27.2.3**, `_use_layout=True` instalado.
No es reproducción del entorno/dependencias antiguos ni lectura del corpus vivo.
Las regresiones demostradas son **contratos offline del código que llama el
worker actual**, no una nueva medición del API/PG/Milvus. Ese límite no impide
cerrar esta auditoría de integración: implementación, fixture/test, evidencia
histórica y ruta actual identificados para cada dependencia material.

**Does the new Content Manager ingestion preserve the historical Likutey
Halajot extraction contract? PARTIAL.** Conserva páginas físicas antes de
chunks, Markdown original y search normalization separado. NO conserva el
contrato completo de folio, inicio/límites/marcadores de notas, roles marginales
ni asociaciones editoriales. No se puede responder YES por conservar page-first.

## B. LOS 11 PROBLEMAS

| # | Problem | Historical status | Current status | Classification | Action |
|---|---|---|---|---|---|
| P01 | U+FFFD / CID | TeX/HE8 decoder; no C CID-font-map completo probado | U+FFFD ya en raw layout; candidato hash-map aislado | PARTIALLY_SOLVED | Reusar tablas por font/encoding positivo; adaptar recuperación por hash; NO SI-960 global |
| P02 | Hebrew logical order | Graphemes / X descendente en geometry | Proyección histórica bypassed; candidato conserva caracteres | OLD_SOLUTION_NEEDS_ADAPTATION | Adaptar `hebrew_pdf_layout` con salvaguardas nuevas |
| P03 | Niqqud ownership | Mapping/query/ownership simple; nearest-owner inseguro | Reparación activa no aplica en estas páginas; C owner ambiguo | OLD_SOLUTION_NEEDS_ADAPTATION | Reusar graphemes; exigir owner único; separar búsqueda/cita |
| P04 | RTL/LTR mixed refs | Boundary-aware matching y ranking; no inverse-bidi genérico | Salmos literal preservado; rol/quote degradado; mixed C unresolved | PARTIALLY_SOLVED | Reusar ranking; reconectar marginal role y adaptar segmentos |
| P05 | Printed pages RTL | Resolver Cc/bare folio y 55/37 probado | Raw actual y Markdown → None; sin metadata folio | REGRESSION | Restaurar contrato explícito de folio por página/chunk |
| P06 | Headings | Goldens 51/53/56 exactos | Clasificadores aún exactos incluso en chunks; duplicación por overlap | ALREADY_SOLVED_AND_REUSABLE | Reusar as-is; preservar entidades/associations y dedupe |
| P07 | Footnotes | Nota35/36 numbered-region helpers y goldens | `> 35`, `> 36 _Birur_`, `[35]` rompen inputs | REGRESSION | Adaptar parsing Markdown con offsets originales y roles antes de chunks |
| P08 | Columns | Bbox/role/profile parcial; labels ≠ solver | Layout genérico; candidate seqno no resuelve columnas | PARTIALLY_SOLVED | Reusar segmentación; completar composición de regiones, no otro parser entero |
| P09 | Reading/block order | Límites por bloque y timeline; V2 raw order limitado | Header/margin/body cambian de orden; seqno no lector | OLD_SOLUTION_NEEDS_ADAPTATION | Adaptar boundaries/timeline y orden geométrico de regiones |
| P10 | Ligatures | ADR020/matching/cita separado probado | Sigue conectado; note36 falla por estructura, no ligaduras | ALREADY_SOLVED_AND_REUSABLE | No modificar normalizer; reparar P07 |
| P11 | Hidden white overlays | Sin solución equivalente histórica | Nueva capability aislada, canonical no la llama | TRULY_NEW | KEEP visibility conservadora; certificar antes de integrar |

Resultado: 2 reutilizables, 3 adaptaciones, 2 regresiones, 3 parciales, 1 nuevo.
La descomposición A–F solicitada es una explicación del mecanismo, NO otra
clasificación: P05/P07=B+C+E (`INPUT_CONTRACT_REGRESSION`); P02/P03=A+B;
P04/P08/P09=A y límites históricos; P10 sin regresión; P11=F. No D demostrado.

## C. HISTORICAL PIPELINE REAL

Paths en las tablas relativos a `SrvRestAstroLS_v1/backend/` (**B/**).
Reportes relativos a `data/reports/breslov/` (**R/**).

**No existía un único pipeline histórico ni una composición decoder→layout→V2.**
No sumar capacidades de diferentes fases como si todos sus goldens hubieran
pasado con esa composición. En particular el PASS de Salmos/nota35 de V2 no
prueba Hebrew Unicode ni column order integral.

### C1. LH layout-aware, 2026-07-05 (`8f5fe0b`)

PDF → `scripts/ingest_likutey_halajot_layout_aware.py:main`
→ `scripts/likutey_layout_parser.py:parse_pdf/parse_page`
→ dict/spans + blocks `sort=True` → decoder selectivo por bloque
→ roles bbox/header/folio/reference → chunks por bloque
→ LiteLLM embeddings → Milvus test → retrieval con texto rehidratado.

| Etapa | Archivo / símbolo real | Input → output |
|---|---|---|
| Entry | `scripts/ingest_likutey_halajot_layout_aware.py:main` | PDF local validado → parse/persist/index |
| Raw | `scripts/likutey_layout_parser.py:parse_page` | PDF page zero-index → dict spans/font/bbox y blocks sort=True |
| Decoder | mismo `decode_hebrew_if_needed`; `modules/library/hebrew_tex_decoder.py:decode_hebrew_text` | block string + heuristic high-byte → string, decoder/confidence/review |
| Layout | `classify_block`, `extract_node_path_from_header`, `find_sources`, `find_crossrefs` | texto+bbox → `LayoutBlock` y node/folio/refs/citable |
| Page/boundaries | `parse_pdf`; `build_composite_page_context` | bloques por página → contexto; ingestor descarta composites no citables |
| Chunk | ingestor `main`, loop bloques | `LayoutBlock` → `library_document_chunks` con role/bbox/printed label |
| Embedding | ingestor `main` / `modules/embeddings/client.py:embed_batch`; también `scripts/embed_likutey_full_batch.py:main` | chunk text → vectores y tracking |
| Index | ingestor `main` / `indexing_service.ensure_collection` y Milvus insert | vectors+metadata → test index |
| Retrieval | histórico audit/retrieval; posteriormente `simple_research_rag.run_simple_rag` / repository | IDs candidatos → citas desde PG, no decoder en búsqueda |

`embed_likutey_full_batch.py` es de la era **2222 bloques / doc47768aac**,
NO el launcher de los 268 chunks V2. Además trunca input a1200: referencia
histórica, NO copiar su orquestación ni importar/ejecutar ese script.

### C2. Page-first V1 y detectores, 2026-07-14

`scripts/ingest_likutey_halajot_page_first.py:main` → página completa,
page anchor / `citable_page_text` inicialmente unclassified
→ `likutey_halajot_structural_detector.py:classify/hints`
→ `likutey_halajot_fine_zone_detector.py:zones`
→ `likutey_halajot_note_source_detector.py:main`
→ nominal reference/resolution scripts.

`zones(text,part)` entrega quote+offset+role+confidence; note-source `main`
segmenta números explícitos en región notes y conserva `block_only` cuando
no puede segmentar. Estos scripts tienen `asyncio.run(main())` con SQL:
**se inspeccionaron, NO se importaron ni ejecutaron**.
No inferir que su note-source scan posterior a `Notas y Fuentes` resuelve V2
PDF56: el raw guardado sitúa el heading de notas DESPUÉS de los cuerpos35/36.
La prueba central es el helper embedded que trabaja directamente en página.

### C3. Page-first V2 real de los goldens (`e31520d`, luego ADR015/016/020)

PDF → `scripts/ingest_likutey_halajot_page_first_v2.py:main/get_page_text`
→ `page.get_text('text')` → remove NUL/strip
→ full page → señales → page anchors/nodes/full-page chunk
→ embedding/index resultado histórico268/268
→ retrieval/evidence→printed-page fallback/embedded notes/ranking.

| Etapa | Archivo / símbolo | Input → output |
|---|---|---|
| Raw | V2 `get_page_text` | page → raw text (incluye códigos C1) |
| Decoder / geometry | **NO llamados por V2** | raw intacto; no Unicode decoder ni `readable_page` |
| Headings | V2 `detect_headings` | raw → número/title/position; hereda current_heading |
| Printed | V2 `extract_printed_page` | primeras5 líneas → solo dígitos solos; falla37 histórico |
| Notes/markers | V2 `detect_footnote_zone/detect_footnote_markers` | regex notes header/número/.N → señales (limitadas) |
| Page-first | V2 `main` | full_text → pages_v2 / anchors / nodes / literal spans |
| Search | V2 `main` `casefold`; luego ADR020 | original separado de normalized |
| Chunk | V2 `main` | una página textual → chunk `page_first_v2`;268 chunks |
| Embedding/index | resultado attested `R/2026-07-31-likutey-halajot-embedding-retrieval-completion-v2-dev/README.md` | 268chunks → LiteLLM model1536 →268 embeddings/268Milvus |
| Retrieval | `simple_research_rag.run_simple_rag`; `simple_research_repository.search_literal_candidates/fetch_canonical_chunks`; `merge_results` | candidatos scoped+texto original → PRIMARY determinista |
| Evidence folio | `page_first_evidence._resolve_printed_page` / `simple_research_rag._canonical_printed_page` | opening raw o metadata →37 (ADR016, no ingesta nueva) |
| Evidence nota | `simple_research_rag._embedded_footnote_number/_body`; `editorial_evidence_v2` | región numerada+query →35/36, body/marker/anchor |

Precisión de procedencia: el reporte268/268 conserva runID
`90ac0fe8-11bf-464f-b1a8-ecef557677e6`, modelo, batches y reconciliación, pero
NO guarda el comando/launcher de esa ejecución. No adjudicarlo a un script
2222-block ni afirmar llamada de `index_collection` sin evidencia. Los
componentes backend reales de embedding/indexing están en
`modules/embeddings/client.py:embed_batch`, `modules/library/indexing_service.py:index_collection`
y `vector_repository.py`; el resultado histórico está corroborado por el
reporte/readiness. Esa limitación de launcher no cambia ninguna decisión de
reutilización de extracción ni justifica restaurar un orquestador antiguo.

Discrepancia importante: ADR014 describe Markdown/PyMuPDF4LLM; **el script
V2 real usa plain `get_text('text')`**. No recomendar restaurarlo como fuente
canónica: la política vigente exige PyMuPDF4LLM→Markdown.

### C4. Geometry histórica reutilizable, NO dependencia LH V2

`modules/library/hebrew_pdf_layout.py:readable_line/readable_block/readable_page`
rawdict Unicode → clusters/X descendente → NFC logical text.
Consumidores: `scripts/ingest_likutey_moharan_i_literal.py`,
`modules/library/likutey_moharan_ii_layout.py` y proyección investigative.
`test_likutey_moharan_ii_layout` prueba `אָמַר לִ`. El diagnóstico recupera
**la misma fixture inline por AST**, sin crear golden duplicado; ambos métodos
la pasan con adapter explícito. No es evidencia de ownership correcto en C.

## D. CURRENT PIPELINE REAL

| Etapa | Path / función o clase | Input → output |
|---|---|---|
| UI | `astro/src/components/admin/ContentManager.svelte`; `contentManagerClient.ts:uploadFile/createJob` | File+metadata → FormData/uploadID/job request |
| API upload | `B/modules/library/routes.py:content_manager_upload` → `content_manager.py:validate_and_store_upload` | PDF → validación/hash/temp file/upload row |
| Queue | `routes.py:content_manager_create_job` → `content_manager.create_job` | authorized upload → queued durable job |
| Worker wiring | `B/scripts/content_manager_worker.py:main` | pool/store → `ConcretePageFirstPipeline(PostgresMilvusPageFirstGateway(pool))` |
| Claim | `content_manager_runtime.PsycopgWorkerStore.claim` → repository `claim_next_job`; `content_manager_worker.ContentManagerWorker.run_once` | lease-scoped claimed job → pipeline.run |
| Extract | `page_first_pipeline.ConcretePageFirstPipeline.run/extract_pdf_page_first` | path+language → physical pages in tuple order |
| Raw/layout | `pdf_hebrew_fidelity.page_markdown` → `pymupdf4llm.to_markdown` → installed `helpers/document_layout.py:parse_document`, FLAGS36420 | page → layout textpage (CID fallback omitted) / layout boxes |
| Markdown | installed `ParsedDocument.to_markdown`; then `pdf_hebrew_fidelity.repair_markdown` | boxes/styles → Markdown; rawdict source-backed boundary repair |
| Canonical | `page_first_pipeline.analyze_page` | Markdown → `ExtractedPage(original_markdown, search_text_normalized, language, headings, footnote_numbers, printed_references)` |
| Pages | `page_first_gateway.PostgresMilvusPageFirstGateway.persist_document_and_pages` | extracted document → document_texts Markdown+`## Page N`, pages_v2 text/layout_notes; manifest |
| Chunks | gateway `persist_chunks` → `chunking.paragraph_chunks(page.original_markdown,1400,150,1)` | each full page → overlap chunks; page_start=end=N; generic role page_text |
| Embedding | gateway `embed` → `modules/embeddings/client.py:embed_batch` | chunk.content → vectors; dimension guard; persist_embeddings tracking |
| Milvus | gateway `index_vectors` → `MilvusAttemptIndex.upsert` | manifest IDs recorded BEFORE external write → exact vectors |
| Result | gateway `reconcile/finalize`; worker `attach_result` | sets match → `test_candidate`, completed(_with_warnings) |
| Publication | client `publishJob` → `routes.content_manager_publish_job` → Milvus list_ids → `content_manager.publish_document` | separate editorial action, exact recheck → ready/CAS |
| Retrieval | routes investigative pipeline → `simple_research_rag.run_simple_rag` / repository | literal+semantic candidates → PG chunk rehydration → editorial enrichment/cites |

Trace is static outside extraction/helpers/tests: NO gateway instances or
service operations ran. Publication never proves text quality; reconciliation
proves entity/vector consistency, not Unicode/layout correctness.

**Page-first connected: PARTIAL.** Page boundaries/order/full-page canonical
storage precede chunks; blank pages preserved. But `ExtractedPage` has no
printed folio/bbox-role spans/anchors. Gateway puts signals in page layout_notes
only; chunk `block_type=page_first_v1`, `evidence_role=page_text`, without
printed_page_label/section_title/editorial node relationships. Retrieval
`fetch_canonical_chunks` reads `ch.content`, `ch.printed_page_label`, section and
role; it does not magically rehydrate these from page layout_notes. Thus it
consumes **degraded representation**, not the complete historical contract.

## E. PIPELINE DIFF / BYPASS

| Capability | Histórico | Actual | Estado |
|---|---|---|---|
| Hebrew/CID decode | Tiqwah SI-960/HE8 selectivo; no same-C CID proof | font-map candidate only; canonical no decoder | BYPASSED |
| Geometry reconstruction | `hebrew_pdf_layout` clusters/rawdict | repair acotado A/B activo; generalized projection not called | BYPASSED (projection), ADAPTED (boundary repairs) |
| Layout-aware parsing | LH bbox roles/header/margin/note | PyMuPDF4LLM generic layout, no LH role export | ADAPTED, historical roles BYPASSED |
| Column separation | LH regions, LMXV probable-columns labels | generic layout / no certified region order | ADAPTED, partial—not solved |
| Page-first | full page before chunks | physical pages before chunks | REUSED, downstream contract degraded |
| Printed page | Cc/header resolver and explicit labels | helper active on new incompatible text, labels absent | INPUT_INCOMPATIBLE |
| Footnotes/notes | .35 and line-start35/body36; associations | [35], >35, >36 _Birur_; generic role | INPUT_INCOMPATIBLE; associations BYPASSED |
| Headings | content-derived canonical classifier | still recognizes ## **N** ■ **TITLE** | REUSED |
| Ligature normalization | ADR020 original/search separate | same normalizer pipeline/gateway/retrieval | REUSED |
| Hebrew/niqqud preservation | query normalizer and simple geometry; no C full proof | query preserved; extraction C unresolved | REUSED (search), BYPASSED/ADAPTED (geometry) |
| Visibility/overlays | no equivalent | new isolated experiment | NEW |

REMOVED: **none demonstrated**. Directed `git log --all --diff-filter=D`
on backend library/modules and scripts returns no deleted paths. This does
not prove no equivalent code changed anywhere; it establishes existing
capabilities are present, not that restoration from deletion is needed.

| PRESENT_BUT_BYPASSED function | Historical caller | Current caller | Why bypassed / action |
|---|---|---|---|
| `likutey_layout_parser.parse_page/parse_pdf` | layout-aware ingestor | none in worker | ADR022 generic pipeline selected; port capability, not script |
| `decode_hebrew_if_needed/decode_hebrew_text` | LH parser; TeX tooling | none in worker | generic Markdown extractor; old activation unsafe; add font provenance first |
| `hebrew_pdf_layout.readable_line/block/page` | LMI/LMII/investigative projection | no canonical worker call | presentation/other-source module; adapt safely, don't pretend LH V2 used it |
| structural `classify/hints`, fine `zones`, note-source regex | V1 metadata scripts | none in worker | SQL/document-specific orchestrators not adopted; port safe pure span/role logic |
| V2 editorial page anchors/units/nodes | V2 main | gateway does not persist equivalents | modern adapter only generic pages/chunks; reconnect metadata contract, not legacy SQL |

Active but broken-input helpers: `_resolve_printed_page`,
`_canonical_printed_page`, `_embedded_footnote_number/_body`,
`editorial_evidence_v2.detect_footnote_marker`. Not all losses are bypasses.

## F. PDF 55 — FIRST DIVERGENCE EXACTA / SALMOS CAPAS

Source SHA `440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a`.
Historical printed page: **37**. Current offline: **None**.

```text
Historical raw (saved probe and V2 replay):
'\x98\x83\x89\x8a\x82 \x87\x86\x83\x95\x87\x8a 37\n'
  C1 codepoints = category Cc; bare trailing digits

Current raw (actual layout FLAGS36420):
'����� ������37\n'
  U+FFFD = category So; bare digits still present

Current Markdown / canonical:
'����� ������ **37** \n'
```

**FIRST_DIVERGENCE_STAGE = CURRENT RAW LAYOUT TEXTPAGE**, not merely Markdown.
`get_text('text')` flags195 include bit128 CID_FOR_UNKNOWN_UNICODE; layout
FLAGS36420 omit it. Missing font Unicode produces U+FFFD instead of numerical
fallback characters. Thus the historical resolver's condition
`any(category(c)=='Cc' for c in line)` stops being true **before serialization**.
It returnsNone on the first nonmatching readable line. Markdown then adds
`**` so its trailing `\d{1,4}\s*$` would fail even if a Cc marker survived.
Removing only numeric bold wrappers does NOT restore37 (diagnostic ablation).
Controlled flag ablation: `FLAGS36420 | CID_FOR_UNKNOWN128` sobre la misma
página devuelve el preámbulo C1 y ambos resolvers recuperan37 (también33/35/38
para51/53/56). Está guardado como `current_layout_raw_cid_diagnostic`; NO
recomendación de activar globalmente numeric-CID fallback, que no decodifica
hebreo. Both resolvers fail even on current raw; historical input succeeds
with the same current unchanged helpers (AST probado en helper-provenance).
Gateway stores no explicit folio fallback.

Historical layout decoder output also retains the header folio; historical
V2 **does not decode** the raw. ADR016 recovered37 at evidence time after
V2's weaker ingestion resolver returnedNULL. Decoder was NOT the prerequisite
of that fix: reconnecting SI-960 cannot fix the actual integration boundary.

| Layer for Salmos16:1 | Historical | Current offline | Action |
|---|---|---|---|
| Extraction surface | '(Salmos16:1)' and quote in marginal block | exact reference remains, quote/body interleaved by layout | preserve region+quote, not string correction |
| Printed page | resolver37;20/20 history | raw and MarkdownNone, all4generated chunksNone | P05 metadata contract |
| Reference detection | verse boundary/variants | `_content_has_exact_reference_surface=True` on both | reuse unchanged |
| Literal normalization | exact/whitespace normalization | still connected | no new Hebrew fix |
| Retrieval ranking | deterministic exact scoped PRIMARY20/20 | existing21canonical selection testsPASS; no live rank run | keep algorithm; role/folio/chunk-boundary revalidation |

Targeted repository SQL requires marginal_citation/marginal_source. Generic
page_text chunks don't satisfy that lane; literal fallback can still find
Salmos. **Reference text survives ≠ historical source_layer/associated quote
survives**. No attribution of these distinct failures to one ranking fix.

## G. PDF 56 — NOTES 35/36 / EXACT CONTRACT BREAK

Same PDF/SHA. Historical note35 detected; current Markdown/page/chunks not.

```text
Historical raw AND current layout raw:
... melodías.35 Pues ... birurim,36
35 Ver §1 más arriba. Escribe el Rabí Natán en otra instancia:
El hombre se une a HaShem desde este mundo físico ...
36 Birur (pl. birurim; lit. “tamizar”) hace referencia ... reﬁ namiento ...

Current Markdown:
... melodías.**[35] ... _**birurim**_ **,**[36]
~~_Notas y Fuentes���������������_~~
> 35 Ver §1 más arriba. ... El hombre se une a HaShem ...
> 36 _Birur_ (pl. _birurim_ ; lit. “tamizar”) ... refi namiento ...
```

**FIRST_DIVERGENCE_STAGE = LAYOUT→MARKDOWN SERIALIZATION.** Current raw
helpers still35/36; note-body Latin text has NOT disappeared. Historical
helper unchanged (`a90bf44` regex; matching expanded `9431d0e`) expects:

```regex
(?m)^\s*(?P<number>\d{1,3})\s+(?=[^\n]*[a-záéíóúüñ])(?=[A-Za-zÁÉÍÓÚÜÑ])
```

1. At line start `>` (U+003E) is neither whitespace nor digit; zero note starts.
2. For36 even after removing `> `, `_` (U+005F) before `Birur` fails the
   immediate Latin-letter lookahead. Italic gloss tokens are a separate
   matching surface concern, not ligature recovery.
3. In body `.35` became `[35]`, with `**` between punctuation/digits; historical
   marker helper no longer detects35. Historical marker36 after comma was
   already NOT covered by the .N helper; don't call that a new regression.
4. `Notas y Fuentes` moves before note bodies in Markdown and acquires
   strike/italic wrappers; it is not lost. Embedded note35 helper does not
   depend on that heading or on `MELODÍAS Y PLEGARIAS` being absent.
5. `repair_markdown` changes **nothing** on these pages. `analyze_page` also
   requires a numbered line and sees zero notes. Generic chunks add no note roles.

Minimal **diagnostic-only** ablations on the SAME input:

| Input to unchanged helper | Note35 | Note36 |
|---|---|---|
| historical raw |35|36|
| actual current raw flags |35|36|
| current Markdown/canonical |None|None|
| only remove line-leading `> ` |35|None|
| remove `> ` + initial `_Birur_` wrapper |35|36|

This proves the first necessary input break; these perturbations are NOT a
production fix. Recognizing35 alone while36 remains unrecognized can make
`_embedded_footnote_body` consume36 as part of35. Preserve BOTH boundaries.
Historical36-after citation itself includes following unrelated Hebrew/header/
reference content after36 (no final-region terminator): retain the proven
matching contract, not pretend historical full body segmentation was perfect.

| Layer | Note35 | Note36 |
|---|---|---|
| Marker | .35 old recognized, [35] new not | raw comma36 already outside .N coverage |
| Body | wording survives; prefix prevents detection | wording survives; prefix+initial italics block detection |
| Printed page |38→None|38→None|
| Ligature | not root cause | existing split/gloss normalizer works after structural ablation |
| Retrieval | historical footnote PRIMARY; now classification loses note layer | historical36PRIMARY; now loses numbered identity |

Printed38 has an additional order break: historical/current raw begins
`38 LIKUTEY HALAJOT`; Markdown begins `DISCURSO SOBRE...`, then
`**38** LIKUTEY HALAJOT`. Resolver stops on the first nonmatching line;
merely stripping bold does not fix it. Keep source-backed page folio metadata.

### Lighter comparisons PDF51/53

| PDF / golden | Historical helper | Current helper/page | Current chunks |
|---|---|---|---|
|51/33 Mishkán|folio33;heading_exact|folioNone;heading_exact|4chunks;2heading-exact occurrences|
|53/35 Bondad|folio35;heading_exact|folioNone;heading_exact|3chunks;2heading-exact occurrences|
|56/38 Melodías|folio38;heading_exact|folioNone;heading_exact|4chunks;2heading-exact occurrences|

Silent folio regressions confirmed. Headings' **textual/structural matching
contract** is compatible; duplicate overlap/entity identity and runtime
PRIMARY still need validation after integration. Do not reuse historical
chunk/evidence IDs as immutable across different chunk representations.

## H. HISTORICAL CAPABILITIES / TEST MATRIX

| Capability | Source path (B/) | Commit | Existing tests/contracts | Action |
|---|---|---|---|---|
| Encoded glyph mappings | modules/library/hebrew_tex_decoder.py |e76c9d2,c917c4e|test_hebrew_tex_decoder, test_hebrew_pipeline_contract|conditional reuse, unsafe activation replace|
| Grapheme geometry | modules/library/hebrew_pdf_layout.py |35e266f|test_likutey_moharan_ii_layout|adapt with conservation/unique-owner guards|
| LH layout roles | scripts/likutey_layout_parser.py |8f5fe0b|real LH probe blocks/text; layout audit15/15|port generic capabilities, no whole ingestor|
| Page-first anchors | scripts/ingest_likutey_halajot_page_first_v2.py |e31520d|existing acceptance fixture + real268/268report|restore metadata contract, NOT plain-text canonical|
| Printed page | modules/library/page_first_evidence.py / simple_research_rag.py |b8d5a26|canonical-selection21 + real55/37|adapt input/explicit metadata|
| Notes/anchors | modules/library/editorial_evidence_v2.py / simple_research_rag.py |2e100c8,a90bf44|editorial36/simple89; note35fixture|Markdown-token adapter + role/offset reconnect|
| Heading/reference PRIMARY | modules/library/simple_research_rag.py / simple_research_repository.py |71af4a2,b8d5a26|canonical21 / real51/53/55/56|reuse algorithm|
| Ligatures | modules/library/pdf_ligature_normalization.py |9431d0e|ligature14 + note36fixture/live history|keep unchanged|
| Hebrew search | modules/library/hebrew_lexical_normalizer.py |126b678|lexical52 / LMII14pointed-unpointed|keep search only|
| Column profile | scripts/likutey_moharan_xv_kdp_column_rules.py and ingestion |edb809b,688e1d8|profile1/column3; ordered_block_ids=[]|reuse diagnostics, not column solver|

### Recovered contract matrix (same helpers, actual inputs)

| Historical test / fixture contract | Historical result | Current result | Classification |
|---|---|---|---|
| canonical selection `test_printed_page_resolved_from_visible_folio` / raw55 |PASS37|unitPASS; real current raw/MarkdownFAILNone|REGRESSION input|
| simple RAG embedded note / acceptance note35 |PASS35|unitPASS; current rawPASS; Markdown/chunksFAIL|REGRESSION input|
| ADR020note36 / fixture |PASS36|unitPASS; rawPASS; MarkdownFAIL; structure-ablationPASS|REGRESSION note contract, normalizer reusable|
| canonical headings51/53/56 |PASSexact|same classifierPASS on actual page AND chunks|ALREADY_SOLVED_AND_REUSABLE|
| reference verse boundary16:1 vs16:10/11/116:1 |PASS|unitPASS and PDF55exact surfacePASS|ALREADY_SOLVED matching; mixed extraction partial|
| rawdict `אָמַר לִ` |PASS|oldPASS, candidatePASS via explicit adapter|OLD_SOLUTION_NEEDS_ADAPTATION|
| decoder HE8/TeX inline tables |PASS|46PASS, not C source Unicode proof|PARTIALLY_SOLVED|
| niqqud with/without/combining forms |PASSsearch|52lexicalPASS; citation preservation/fidelity suitesPASS|same search problem; different C ownership; partial reuse|
| LMXV column labels/QA |PASSlabels/pages|4PASS, no exact LH55/56order fixture|PARTIALLY_SOLVED|
| historical overlays suppression |no test or implementation|33new candidate testsPASS, canonical bypass|TRULY_NEW|

425 current suite tests comprise historical unit contracts, current worker
contracts and **existing local experiments**, not425 historical E2E passes.
Historical-suite outcomes documented in prior audit/ADR; new candidate suites
have no historical result. Focused run includes20suites, adding simple RAG89,
editorial granularity12, reference resolution3 and nominal catalog4 to317.
No services; full backend/frontend/E2E not run. Full command is the suite list
in tests.txt, invoked `PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider`.

## I. UNSAFE HISTORICAL CODE — SI-960 DECOMPOSED

| Component | Valid scope / reuse | Unsafe as-is / reason |
|---|---|---|
| SI960_TO_HEBREW | reusable **encoding table** for verified Tiqwah/tq font encoding | not a C CID/font-program map; ordinary a-z map too |
| HE8_NIQQUD/LETTERS | mapping/preservation knowledge + inline tests | á/í/É also Spanish; mapping without font discrimination corrupts prose |
| LATIN_EXT_A | reference table only, best-effort annotated HE8 analysis | not verified authoritative C-font cmap; uncertain glyph variants |
| is_likely_si960_encoded | diagnostic signals | text-only midword/quote/marker scoring, no font verification; threshold is not provenance |
| LH decode_hebrew_if_needed | skip real Unicode branch useful | high-byte>max(2%,2) then classifier; block spans'font available but NOT used to gate decoding |
| _reverse_word | historical TeX visual-order assumption | codepoint reversal can separate/reorder combining marks; not generic Unicode bidi |
| KNOWN_UNMAPPED | fail-preserve unknowns useful | never claim full decoding; Í/¿/ő unresolved |

Mapping source is the **inline SI-960/Tiqwah/HE8 tables and annotations**,
not an inspected C font cmap/hash. Activation conditions: existing Hebrew>10%
returnsunicode_direct; otherwise high-byte threshold then distributed SI-960
signals (`score>=4` etc.). `min_chars=5` in LH caller. No positive font-family,
encoding CMap, font-program hash or language-per-span requirement.

Missing discriminator: **font/encoding provenance at span/glyph scope**,
not more Spanish-vs-Hebrew guesses over a merged block. Saved prior same-pages
outputs show Spanish LH51 `Y así HaShem...`, LH55 `Y esta idea...`, LH56
`35 Ver §1...` converted into pseudohebrew. ZeroU+FFFD ≠ correct Hebrew.

Other unsafe wholesale reuse: SQL/document-ID ingestors; fixed LH bbox
thresholds as generic truth; nearest-owner geometry; `sort=True` declared
column-aware despite interleaving; seqno declared reading order.

## J. NEW EXPERIMENTS — DECISIÓN

### `B/modules/library/pdf_text_visibility.py`

Historical duplicate: **NO**. New capability: **YES**. Recommend: **KEEP**.
Keep conservative API isolated until source-visible retention certificate and
raw-span→Markdown integration validated. Uses later opaque simple white
rectangles + trace AND entire paint ink containment + opacity/order/layer/clip
and compositing guards. It is not a complete PDF graphics-state interpreter.
No increase of suppression;286ambiguousKEEP. NO visual/product PASS.

Negative recovery evidence, stopping criterion met:

1. Current tree code/scripts/tests: exact directed concepts overlay/overpaint/
   covered/hidden/occlusion/rectangle/white/draw-order/seqno/opacity/clip/mask
   located **only new candidates/probes** for equivalent suppression.
2. `git log --all -G '(overpaint|occlusion|seqno|get_drawings|get_bboxlog|fill_opacity|draw_order|white.{0,25}(rectangle|overlay)|covered.{0,25}text)'`
   across Python/JS/TS/Svelte/JSON/MD:3hits, reviewed. `edb809b` counts drawings
   for layout/diagram hints; `126b678` Hebrew retrieval; `1fa9290` boundary
   repair. None suppresses covered text. Narrow search also included texttrace.
3. Historical tests/fixtures: drawing counts/layout profiles only; no paint-order
   suppression contract. New visibility tests untracked are NOT historical.
4. ADR/relevant report directed matches: no equivalent old solution;
   current2026-10-01 visibility/reconstruction artifacts are explicit new experiments.

Conclusion scoped to repository/all available refs, not a claim about external
unavailable archives. It does NOT require reading unrelated839reports.

### `B/modules/library/pdf_text_reconstruction.py`

Historical duplicate: **PARTIAL**. Recommend: **ADAPT_HISTORICAL**.

| Old | Candidate | Integration consequence |
|---|---|---|
| rawdict, X-descending Hebrew clusters | trace tuples, same geometric direction | core idea already exists; no wholesale replacement |
| NFKC perchar then NFC output | no normalization | preserve immutable codepoints for citation |
| remove spaces then insert ifgap>2.2 | explicit source spaces only | keep word-boundary evidence, no threshold guessing |
| previous cluster then nearest owner | unique same-origin/strict-inside owner; ambiguousfail-closed | adopt safeguard; don't port nearest-owner globally |
| block / baseline grouping | seqno + fixedbaseline .04em, no transitive joins | safeguard against cross-operation/cell merging |
| mixed majority45% may reorder whole line | mixed strongRTL/LTR/mirrors unresolved | avoid silent reference corruption |
| no character conservation assertion | Counter(source)==Counter(output) | adopt invariant |

Candidate also reports U+FFFD and Unicode normalization status. These are new
**safeguards on existing geometry capability**, not proof a complete new Hebrew
parser was required. Its cross-operation `(seqno,baseline)` order is explicitly
uncertified. Keep file as isolated comparison harness during adaptation, not a
production replacement or an instruction to merge code now.

## K. TRULY NEW — EXCLUSIVELY

**P11 visibility/white-overlay suppression** has no equivalent historical
implementation/test. This is the sole TRULY_NEW problem among the11.

Missing sub-capabilities still require development inside partial/adaptation
problems: positively discriminated C font-program→CID Unicode maps (not SI-960),
uncertainty-aware segmented bidi/region order, and Markdown/editorial-span
adapters. Their surrounding Hebrew/geometry/reference capabilities already
exist; do not label the entire problem new or write another pipeline.

## L. REUSE / INTEGRATION PLAN (NO IMPLEMENTACIÓN)

Target remains **GENERIC USER UPLOAD PIPELINE**, no hardcoded LH IDs/pages/fixes.
Use source-evidenced capability activation and immutable original Markdown.

| Capability | Source (B/) | Target (B/) | Exact action |
|---|---|---|---|
| Safe literal/search behavior | modules/library/pdf_ligature_normalization.py; simple_research_rag.py | existing pipeline/gateway/retrieval callers | KEEP unchanged; reuse current suites/goldens |
| Printed folio | page_first_evidence.py:_resolve_printed_page; simple_research_rag.py:_canonical_printed_page; layout parser header bbox | page_first_pipeline.py:ExtractedPage/analyze_page; page_first_gateway.py:persist_document_and_pages/persist_chunks; simple_research_repository.py:fetch_canonical_chunks | ADAPT source-backed opening-header extraction into explicit page folio; propagate to every chunk; fallback Markdown-aware only |
| Note identity/boundaries | simple_research_rag.py:_embedded_footnote_*; editorial_evidence_v2.py marker/anchor/timeline; V1 zones | page_first_pipeline.py signals; gateway chunk metadata; same evidence helpers | ADAPT Markdown-token input preserving original offsets; reconnect number/body/marker/anchor/next_heading, both35and36; don't depend on terminal heading |
| Editorial role/reading regions | scripts/likutey_layout_parser.py pure bbox roles; hebrew_pdf_layout.py block boundaries | pdf_hebrew_fidelity.py:page_markdown and page_first_pipeline.py canonical page metadata | EXTRACT reusable capability, normalized to page dimensions; layout confidence/source spans; no SQL script import |
| TeX mapping | modules/library/hebrew_tex_decoder.py tables | font-aware extraction capability behind page_markdown | REUSE only positive font/encoding identification; REPLACE unsafe block heuristic; preserve unknown |
| C CID maps | local modules/library/pdf_font_unicode.py + data/pdf_font_unicode_profiles.json | same pre-Markdown source-backed font capability | ADAPT separately: exact font hash/missingToUnicode/Identity-H guard, no source-file rewrite or decoder guess |
| Logical graphemes/niqqud | modules/library/hebrew_pdf_layout.py + candidate pdf_text_reconstruction.py safeguards | source-backed extractor before Markdown serialization | ADAPT_HISTORICAL with unique owners/conservation/mixed-direction fail-closed; preserve raw spans/regions |
| Visibility | local modules/library/pdf_text_visibility.py | source-backed pre-canonical extraction/Markdown provenance boundary | KEEP new conservative capability; filter only proven hidden operations; ensure converter cannot reintroduce removed spans |
| Chunk/editorial entities | historical page-first/evidence contracts, not old SQL | page_first_gateway.py:persist_chunks and simple_research_rag.py enrichment | reconnect full-page entities through overlap, dedupe aliases; preserve body/quote boundaries, role and section |
| Regression contracts | existing acceptance/ligature/LMII/raw probes | existing tests + offline diagnostic harness | reuse old expectations; real sameSHA55/56/51/53, no duplicate golden files |

Order, derived from traces:

1. **Freeze/reuse working search, headings, exact-reference boundaries and ranking.**
   No new retrieval boosts and no global Unicode normalization of citations.
2. **Restore folio and note input contracts plus explicit page/chunk metadata.**
   P05/P07 isolated from CID correction: raw55folio and35Latin bodies prove this
   can be validated independently. Restore35AND36boundaries/marker/anchor;
   keep original Markdown and source offsets, not global stripping.
3. **Adapt safe font decoding and historical grapheme geometry together with
   source-region order.** Positive font discrimination is prerequisite to
   ordering decoded Hebrew; don't nearest-attach marks before correct glyphs.
   Use existing LMII fixture and C candidate fixtures as contract/harness.
4. **Integrate certified visibility at the source-span boundary**, upstream of
   canonical serialization. Font/geometry/visibility share provenance; converter
   must consume retained spans rather than silently re-extract hidden raw text.
   Coordinate3/4 in design; reject a patch that filters trace then lets unfiltered
   PyMuPDF4LLM regenerate the same hidden content.
5. **Revalidate entity-aware chunks and all historical retrieval/evidence goldens**
   before any C ingestion: printed33/35/37/38; headings51/53/56; Salmos reference+
   quote+scope+ranking separately; notes35/36body/marker/anchors; niqqud/search
   preservation; conservative visibility no-visible-text-loss certificate.
6. **Only after implementation gates and explicit authorization: DEV C reingest.**
   No corpus/production action authorized by this audit PASS. READY remainsNO.

No target file changes now. If page metadata/schema needs migration, design
and authorize separately; do not execute it under audit. The product gate
still needs same-PDF visible Unicode/order/niqqud and authenticated E2E evidence.

## M. GIT / VALIDACIÓN / RIESGOS

```text
Branch: feature/console-backend-core
HEAD initial: 1fa9290bdc7840e7277a998aa3ca66345c6080ee
HEAD final:   1fa9290bdc7840e7277a998aa3ca66345c6080ee
Production code changed by this phase: NO
Commit: NO
Push: NO
```

Modified/added by this continuation: **only report artifacts under this
`closure/` directory and an additive pointer in prior README**. All existing
experimental code/UI/status changes preserved. `git diff --check`PASS; final
report/script diff reviewed; focused425PASS. No LAT or @latchanges, latcheck
not applicable. No frontend changes, check/build/browserE2E not run.

Impact: complete implementation→contract→historical evidence→current path→
loss→action map. Risk: confusing offline recognition with runtime fidelity;
old false decoder output can look better than U+FFFD; candidate tests preserve
characters but don't certify page order/visual truth. Reusing a mapping table
without font evidence is still unsafe. Next step: approve file-by-file plan,
then implement/validate offline capabilities—**not reingest**.

## N. PROD / CORPUS

```text
Reset: NO
Reingest: NO
PG writes: NO
Milvus writes: NO
Production modified: NO
PG/Milvus/LiteLLM connections by diagnostic: NO
External services started/stopped/reconfigured: NO
READY_FOR_C_REINGEST: NO
```

## RESPUESTAS OBLIGATORIAS

| Pregunta | Respuesta |
|---|---|
| ¿Tenemos ya código histórico reutilizable para Hebrew/CID? | PARCIAL: encoding tables sí; mismo C CID completo no |
| ¿Tenemos reconstrucción geométrica reutilizable? | SÍ, requiere adaptación conservadora |
| ¿Tenemos layout/column handling reutilizable? | PARCIAL: regiones/roles sí; complete column order no |
| ¿Printed page es una regresión del contrato actual? | SÍ |
| ¿Nota35 es una regresión del contrato actual? | SÍ |
| ¿Page-first sigue conectado correctamente? | PARCIAL, downstream representation degraded |
| ¿El nuevo worker está saltando capacidades existentes? | SÍ, sin atribuir al antiguo LH V2 dependencias que no llamó |
| ¿Hay código histórico que NO debe reactivarse tal cual? | SÍ, SI-960 activation/reversal/nearest-owner/SQL ingestors |
| ¿Visibility/white overlays es realmente nuevo? | SÍ, en repo/all available Git refs dirigidamente auditados |
| ¿pdf_text_reconstruction.py duplica trabajo histórico? | PARCIAL, salvaguardas nuevas sobre geometría existente |
| ¿Sabemos exactamente qué reutilizar y qué adaptar? | SÍ, matrizL; requiere implementación/QA, no búsqueda exhaustiva |

**11/11 clasificados y con acción; PDF55/56 primeras divergencias conocidas;
pipelines reales separados; reutilización/bypass/inseguridad/nuevo identificado;
plan archivo por archivo producido. AUDIT PASS ≠ LIKUTEY HALAJOT FIXED.**
