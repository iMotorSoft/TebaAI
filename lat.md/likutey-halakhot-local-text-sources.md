# Likutey Halakhot — Phase Closure Documentation

Consolidated documentation of the full technical phase for incorporating ליקוטי הלכות into TebaAI: search, download, preflight, source evaluation, artifact generation, and decision framework.

**Phase type:** Documentary/local — no production writes.
**Status:** Closed — all artifacts generated; ingestion blocked until license review and chunking strategy are decided.
**Date range:** 2026-06-29 – 2026-07-01

## Source Hierarchy

Three tiers of sources were evaluated:

| Tier | Source | Coverage | Text quality | Role |
|------|--------|----------|-------------|------|
| Primary | Sefaria `Likutei Halakhot` | 145 refs (full) | Unicode Hebrew, structured JSON | Canonical textual source for future ingestion |
| Fallback | Hebrew Wikisource | Partial | Unicode Hebrew, less structured | Control/gap checker |
| Visual backup | HebrewBooks (local) | 5 PDFs, 1773 pages | Image-only, no text layer | Page-image reference only |

## HebrewBooks Download and Preflight

Esta sección resume descarga y preflight local de fuentes HebrewBooks.

### Download

Seven HebrewBooks records were evaluated for ליקוטי הלכות.

Five were valid; two (`64972`, `20557`) were false positives discarded. Direct download via `downloadhandler.ashx` was blocked by Cloudflare, so PDFs were reconstructed from official 1200 px page PNGs.

### Preflight Result: Image-Only

The reconstructed HebrewBooks PDFs were image-only and unusable as text sources.

| File | Pages | MB | Text chars | Hebrew | Images | Classification |
|------|------:|----|----------:|------:|------:|---------------|
| `hebrewbooks_43317_likutey_halajot_orach_chayim.pdf` | 343 | 190.7 | 0 | 0% | 343 | `image_only_pdf` |
| `hebrewbooks_67652_likutey_halajot_even_haezer.pdf` | 137 | 63.1 | 0 | 0% | 137 | `image_only_pdf` |
| `hebrewbooks_67653_likutey_halajot_choshen_mishpat_a.pdf` | 420 | 216.5 | 0 | 0% | 420 | `image_only_pdf` |
| `hebrewbooks_67654_likutey_halajot_choshen_mishpat_b.pdf` | 333 | 177.6 | 0 | 0% | 333 | `image_only_pdf` |
| `hebrewbooks_67655_likutey_halajot_yoreh_deah.pdf` | 540 | 306.8 | 0 | 0% | 540 | `image_only_pdf` |

All 5 PDFs returned zero text characters. One image per page. No fonts detected. No OCR layer. Classification: `image_only_pdf` — no decoder possible.

Reports: `preflight_likutey_halajot.md` / `.json` in the PDF directory.

## Source Search

Sources evaluated: Sefaria, Hebrew Wikisource, HebrewBooks, Breslev.org, Breslev.co.il, Internet Archive, Otzar HaChochma, Google Books, GitHub, Dicta, AlHaTorah.

**Decision:** Sefaria is the only source with structured Unicode Hebrew text covering all 4 sections under a consistent API. Wikisource is a secondary unstructured fallback. All other sources lack a usable textual candidate.

## Sefaria Preflight

- **Work:** `Likutei Halakhot` (he: `ליקוטי הלכות`)
- **Author:** Nathan Sternhartz
- **Category:** Chasidut, Breslov
- **Leaf refs (total):** 145
  - Orach Chaim: 42
  - Yoreh Deah: 54
  - Even HaEzer: 8
  - Choshen Mishpat: 41
- **Hebrew versions:** 10 detected
- **Licenses:** Mix of `CC-BY-NC` (BRI 2019, Orach Chaim) and `unknown` (Or Haganuz, other sections)

**Key limitation:** No single uniformly-licensed Hebrew version exists for the full work. Future ingestion must track `source_version_title` and `source_license` per section, not per work.

## Artifact Generation

Script: [[SrvRestAstroLS_v1/backend/scripts/generate_likutey_halakhot_text_sources.py#main]]

Base output directory: `/media/issajar/DEVELOP/Download/Tora/Breslov/LikuteyHalajot/TextSources`

### Artifact tree

The generated artifact tree keeps source JSON, readable formats and manifests separate.

```
TextSources/
├── sefaria_json/
│   ├── likutey_halakhot_orach_chayim_sefaria.json
│   ├── likutey_halakhot_yoreh_deah_sefaria.json
│   ├── likutey_halakhot_even_haezer_sefaria.json
│   └── likutey_halakhot_choshen_mishpat_sefaria.json
├── markdown/
│   ├── likutey_halakhot_orach_chayim_sefaria.md
│   ├── likutey_halakhot_yoreh_deah_sefaria.md
│   ├── likutey_halakhot_even_haezer_sefaria.md
│   └── likutey_halakhot_choshen_mishpat_sefaria.md
├── html/
│   ├── likutey_halakhot_orach_chayim_sefaria.html
│   ├── likutey_halakhot_yoreh_deah_sefaria.html
│   ├── likutey_halakhot_even_haezer_sefaria.html
│   └── likutey_halakhot_choshen_mishpat_sefaria.html
├── pdf/
│   ├── likutey_halakhot_orach_chayim_sefaria.pdf
│   ├── likutey_halakhot_yoreh_deah_sefaria.pdf
│   ├── likutey_halakhot_even_haezer_sefaria.pdf
│   └── likutey_halakhot_choshen_mishpat_sefaria.pdf
├── manifests/
│   ├── likutey_halakhot_text_pdf_manifest.md
│   └── likutey_halakhot_text_pdf_manifest.json
└── reports/
    └── likutey-halakhot-sefaria-preflight.json
```

### Validated coverage

The generated Sefaria artifacts cover all four sections with selectable text.

| Section | Refs | Segments | Hebrew chars | PDF pages | PDF MB | Versions | Licenses | Text selectable |
|---------|:----:|:--------:|:------------:|:---------:|:------:|----------|----------|:---------------:|
| Orach Chaim | 42 | 4,430 | 6,968,427 | 1,888 | 37.0 | 3 versions | CC-BY-NC, unknown | yes |
| Yoreh Deah | 54 | 2,614 | 4,355,381 | 1,205 | 23.4 | 2 versions | unknown | yes |
| Even HaEzer | 8 | 440 | 722,880 | 197 | 3.9 | 2 versions | unknown | yes |
| Choshen Mishpat | 41 | 3,081 | 4,174,608 | 1,217 | 22.4 | 2 versions | unknown | yes |
| **Total** | **145** | **10,565** | **16,221,296** | **4,507** | **86.7** | — | — | **all yes** |

### Format priority for future ingestion

Future ingestion should prefer structured sources over generated PDFs.

1. **JSON** (canonical — preserves refs, versions, licenses, segments, hebrew)
2. **Markdown** (readable intermediate, same information)
3. **Generated PDF** (derivative, searchable, good for study, not canonical)

## Decision Framework

The decision framework separates textual authority from visual backup material.

| Source | Has text? | Use case |
|--------|:---------:|----------|
| HebrewBooks PDFs | No (image-only) | Visual page reference. Not a text source. OCR deferred. |
| Sefaria JSON | Yes | Canonical text source for future PG ingestion. |
| Sefaria MD/HTML | Yes | Readable intermediates for study/QA. |
| Sefaria generated PDFs | Yes | Searchable local PDFs for offline study. |

**OCR:** Postponed. Not needed if Sefaria covers all sections (it does). If page-faithful HebrewBooks alignment is ever required, OCR would be needed for page-image-to-text mapping.

## Boundaries

This phase is artifact generation only and must not mutate production services or runtime collections.

- No PostgreSQL writes
- No Milvus writes
- No LiteLLM calls
- No embeddings
- No OCR executed
- No commits
- No page-faithful mapping claims against HebrewBooks

## License Caveat

Generated artifacts must preserve per-section version and license metadata.

Sefaria serves mixed Hebrew versions: Orach Chaim resolves to `CC-BY-NC` (BRI 2019), while other sections resolve to `unknown` (Or Haganuz). Future ingestion must track this at the section level.

Current `usage_scope`: `internal_study` — no public distribution.

## Next Steps (not executed, documented for future)

These steps remain deferred until licensing and ingestion strategy are decided.

1. **Close and commit this phase** in a dedicated window when time permits.
2. **Before ingestion:**
   - Decide whether the mixed Sefaria version/license set is acceptable.
   - Persist `source_version_title`, `source_license`, `source_ref`, `source_provider`, `usage_scope` per document.
   - Prefer JSON or Markdown as canonical source over generated PDFs.
3. **Preflight the generated Sefaria PDFs** as textual pipeline input if needed.
4. **If HebrewBooks page alignment is required:** design a separate alignment phase (text↔image mapping or OCR).
5. **Keep shoresh/lemas out of scope** until the documentary pipeline, chunking, and search are validated for Likutey Halakhot.
6. **Update [[status_actual]]** once this closure is committed.
