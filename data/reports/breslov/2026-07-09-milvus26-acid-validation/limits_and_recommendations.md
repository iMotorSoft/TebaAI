# Limits and recommendations

## What we know

- Milvus is currently unavailable on `127.0.0.1:19530`.
- PostgreSQL still reports `5102` ready chunks for `breslov_primary`.
- The expected collection is `tebaai_breslov_chunks_v1`.
- Relation QA falls back to lexical retrieval when Milvus raises `MilvusConnectionError`.
- Exact `apply request took too long` was not reproduced, but the related etcd applied-index timeout is present in the logs.

## Limits detected

- No live Milvus health verification is possible while the container is exited.
- No live schema or index verification is possible while the container is exited.
- No live round-trip count parity is possible while the container is exited.
- No live Milvus search latency is possible while the container is exited.
- The embedding baseline is measurable, but it is not a substitute for vector search latency.
- Top-k values above 20 were not validated under a healthy Milvus session in this run.

## What we cannot promise yet

- High availability.
- Automatic recovery.
- Zero fallback to lexical retrieval.
- Stable Milvus search latency under real load.
- Batch editorial throughput without prior health checks.

## Operational rules

- Check Milvus health before batch editorial work.
- If `used_milvus=false`, mark the response as lexical fallback.
- If `MilvusConnectionError` appears, inspect the container and logs before retrying.
- If applied-index timeouts appear, review Milvus and etcd logs together.
- Do not restart Milvus automatically from the app.

## Next improvements

- Internal health endpoint for Milvus.
- `milvus-health` CLI.
- UI warning when `used_milvus=false`.
- Runbook for container exit and etcd timeout handling.
- Periodic latency probes once the service is healthy again.
