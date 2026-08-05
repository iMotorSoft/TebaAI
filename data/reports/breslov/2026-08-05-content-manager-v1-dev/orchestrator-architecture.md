# Orchestrator architecture — partial hardening

The continuation adds a PostgreSQL-durable orchestration boundary without pretending that the ingestion pipeline is complete.

## Implemented

- canonical transition graph in `content_manager_state.py`;
- atomic `FOR UPDATE SKIP LOCKED` claim;
- `claimed_by`, claim timestamp, lease expiry and heartbeat;
- compare-and-swap worker-owned transitions and transition audit;
- expired lease recovery: untouched attempts requeue, attempts with manifest-owned partial writes fail closed as `manual_review_required`;
- normalized attempts, manifests and exact resource IDs;
- atomic active-job idempotency index and `ON CONFLICT` creation;
- tenant-scoped resource reads and mutations;
- abstract durable worker runner independent of HTTP/client lifetime.

## Still missing (gate blockers)

There is no concrete `PageFirstPipeline` implementation that composes canonical PyMuPDF4LLM page extraction, editorial detectors, page/chunk persistence, LiteLLM embeddings, isolated Milvus indexing, attempt-scoped reconciliation and compensating cleanup. Existing executable pipelines remain document-specific scripts with incompatible assumptions. Connecting those scripts directly would violate the typed reusable service requirement and could contaminate `breslov_primary`.

No worker launcher was added because launching an abstract worker that cannot safely execute a job would only move jobs from `queued` to `failed`.
