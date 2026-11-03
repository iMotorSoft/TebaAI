# Retrieval isolation contract — NOT SATISFIED

Required normal mode: resolve one authorized active document generation per logical identity and visibility epoch, filter Milvus **before top-k**, filter every PG lexical/page/hydration path, bind citations/viewer and caches to the same request identity. Missing/ambiguous identity must fail closed. Revalidate or discard stale responses; do not splice epochs.

Required candidate mode: explicitly select one authorized candidate document+run, never a broad `include_test_candidates=true` over all ready and candidate documents. Historical citation/source inspection must be distinct from normal search.

Implemented: `/library/search` hybrid discards vector candidates when PG cannot rehydrate them or their index document identity disagrees with PG. Emitted document/title/chunk_index use PG authority; index 0 is no longer replaced by index metadata. A real Litestar handler + actual hybrid orchestration test confirms an unrehydrated `NEW_ONLY_MARKER` does not serialize (stores/auth/model faked).

Not implemented: common active-generation predicate, active-ID Milvus prefilter, explicit candidate admission/authorization, normal viewer resolution, assistant/relation/Book QA generation pinning, cache epochs. `text_search` lacks status/active filtering; `simple_research_repository` and relation QA use status/boolean candidate opt-in; Book QA/source publication select latest run in some paths. The hybrid fix alone does **not** isolate candidates. A PG row for an inactive candidate can still be hydrated today.

Cross-route status and concrete symbols: [implementation-map](implementation-map.md). Browser E2E and complete A–L/cross-route isolation proofs were not executed. No normal production experience was deliberately changed to a half-implemented generation model.

Regional contract unchanged: source SHA + physical page + generation/run ownership; only ACCEPTED+CERTIFIED evidence is searchable in new regional ingestion. OLD has no regional certificates and must remain LEGACY_UNCLASSIFIED. Page number or equivalent region name cannot transfer acceptance across generations. Counts OLD=NEW are not required.
