# Milvus 2.6 acid validation

## Current verdict

Milvus is down on `127.0.0.1:19530` and the container is `Exited (1)`.
PostgreSQL remains reachable and reports `5102` ready chunks for `breslov_primary`.
Relation QA falls back to lexical retrieval when Milvus fails.

## Key files

- `service_status.md`
- `collection_health.md`
- `pg_milvus_roundtrip.md`
- `search_latency.md`
- `error_catalog.md`
- `apply_request_took_too_long.md`
- `relation_qa_fallback_behavior.md`
- `limits_and_recommendations.md`
- `docker_status.txt`
- `docker_logs_tail.txt`
- `milvus_probe.json`

## Summary

- Milvus connected: `false`
- Milvus collection exists: `false`
- PG connected: `true`
- PG ready chunks: `5102`
- Round-trip status: `blocked`
- Search latency status: `warn`
- Relation QA status: `warn`

## Notes

- Exact `apply request took too long` was not reproduced.
- The related etcd applied-index timeout is present in the captured tail.
- No destructive action was taken.
