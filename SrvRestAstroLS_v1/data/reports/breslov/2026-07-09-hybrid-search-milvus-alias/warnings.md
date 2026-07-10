# Warnings

- `plegaria` had `20` direct vector hits with the alias filter, but `0` vector-signal rows in the top 20 hybrid result because FTS dominated the merged ranking.
- Dense vector search returns nearest neighbors for negative queries; this fix only restores routing, not quality gating.
- PyMilvus emitted deprecation warnings for ORM-style APIs (`connections`, `utility`, `Collection`). Functional behavior passed.
- The fix is intentionally local to general library hybrid search. Relation QA was not changed.
