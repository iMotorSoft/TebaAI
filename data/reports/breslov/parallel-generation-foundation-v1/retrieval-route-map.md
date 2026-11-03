# Cross-route audit — isolation NOT demonstrated

Paths relative to `SrvRestAstroLS_v1/backend/`. Static map plus six new synthetic reproductions, not a completed cross-route acceptance suite. [Symbols](route-symbol-audit.txt), [predecessor detailed map](../c-parallel-generation-safety-v1/implementation-map.md).

| Route / service | Current generation behavior | Required change |
|---|---|---|
| `/library/search`, text modes; `text_search.py` `_search_fts/_search_phrase/_search_trigram` | Scope-only; no active or status predicate. All three SQL branches reproduced offline. | Resolve active context first; SQL restrict exact physical IDs before LIMIT. |
| `/library/search`, hybrid; `hybrid_search.py` | Scope-only vector filter; valid PG inactive candidate can surface. Orphan/misattributed PG hydration is rejected. New top-1 reproduction passes by demonstrating leak. | Active-ID Milvus prefilter before ranking + same context PG hydration + lexical isolation. |
| Semantic CLI `scripts/search_milvus.py` | Independent direct vector search surface; not certified generation-aware. | Explicit normal/candidate resolver or disable normal evidence export until adapted. |
| `/library/investigative-qa/v1`, `simple_research_rag.py`, `simple_research_repository.py` | Ready/candidate flags/work resolution, not explicit generation pointer; helper lookups/enrichment have independent queries. | One pinned context through semantic/literal/heading/reference/neighbor expansion and serialization. |
| Advanced/compare investigative and `research_service.py` | Separate retrieval/hydration implementations; not certified isolated. | Shared active/candidate context in every branch; no fallback to broad corpus. |
| `/library/relation-qa`, `relation_qa_service.py`, `relation_qa_repository.py` | Status sets and candidate opt-in; semantic and lexical paths distinct. | Exact context in FTS/ILIKE/pattern/cooccurrence/vector/hydration before limits; restrict candidate authorization. |
| Book QA and run routes, `book_qa_service.py` | Latest completed/created or explicit run, not logical active pointer. | Bind run to selected generation provenance; explicit candidate/historical permission, never latest. |
| Original source viewer, `source_repository.py.get_authorized_source` | Exact physical ID + ready/test_candidate + scope. Broad candidate acceptance; archived citations unavailable. | Normal logical resolver + explicit candidate/historical policies preserving pinned physical URLs. |
| Page publication viewer, `get_page_publication` | Latest completed run by finished_at; new reproduction confirms SQL. | Exact selected generation and provenance run, fail closed. |
| Chunk lookup, `vector_repository.py`, `repository.py` | Physical document/chunk ownership, no common active-context requirement. | Separate internal ownership reads from evidence reads; evidence lookup must enforce selected context. |
| Canonical assistant hydration, `fetch_canonical_chunks`, relation `get_chunks_by_ids` | Caller/status-based selection, not uniform pointer/epoch validation. | Context membership on every chunk/page/neighbor access, including arbitrary IDs from conversation/model responses. |
| Citations, `editorial_evidence_v2.py`, `citation_policy.py` | Chunk/entity hash already generation-specific indirectly; document+page alone is insufficient. | Carry logical/generation/run/epoch in source map; preserve historical chunk evidence IDs and forbid cross-generation joins. |
| Document listing/get/text/SHA lookup, `repository.py` | Physical IDs; SHA lookup may become ambiguous after parallel admission. | Keep physical APIs compatible; separate logical normal listing, exact-generation inspection, and source-reservation duplicate lookup. |
| Internal/legacy indexing and ingestion scripts | Document-wide destructive rebuild paths, not lifecycle-fenced. | Common lifecycle protection for active/retained generations; do not execute them during retention. |

## Required result matrix

| Routes | OLD active result | NEW candidate leak | NEW active result | Missing pointer behavior |
|---|---|---|---|---|
| Literal/FTS/trigram | NOT TESTED with generations | SQL lacks fence (3 reproductions) | NOT TESTED | No resolver |
| Hybrid | NOT TESTED with valid OLD/NEW pair | YES in synthetic canonically hydrated top-1 reproduction | NOT TESTED | No resolver |
| Investigative/simple/advanced/relation | Existing regressions only | NOT CERTIFIED absent | NOT TESTED | No shared resolver |
| Book/page-first/run QA | Existing implementation only | NOT CERTIFIED absent | NOT TESTED | Latest-run behavior |
| Viewer/source/publication | Existing auth tests only | NOT CERTIFIED absent | NOT TESTED | Latest-run page behavior |
| Chunk/document/citation/internal/CLI | Static audit only | NOT CERTIFIED absent | NOT TESTED | No uniform resolver |

ROUTES_ISOLATED = 0 certified by this attempt. No real parallel candidate was admitted. Existing one-generation regressions do not prove cross-route isolation.

## Milvus

Existing primary schema includes physical document_id; this is sufficient to filter the chosen generation before ranking without rewriting historical vectors. It has no primary ingestion-run field, so using C's run UUID as vector generation ID would fail. Build an allowlisted document_id expression from the PG context plus existing scope->collection alias. Empty active set must short-circuit, not omit filtering. Current hybrid expression only contains collection_code. No actual Milvus mutation/search isolation test was executed; inventories used read-only Strong queries over already loaded collections. No unloaded collection was loaded/flushed.
