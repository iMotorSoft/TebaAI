# Official pipeline trace — inspected, not modified

Paths below are relative to `SrvRestAstroLS_v1/backend/`.

1. Editor: existing Content Manager calls authenticated `POST /admin/content/uploads`
   and `POST /admin/content/jobs` in `modules/library/routes.py`. Role and active
   tenant/scope resolution remain mandatory. `content_manager.py:create_job`
   rejects exact duplicates and requested status other than `test_candidate`.
   Its idempotency key includes scope, source hash, pipeline version, profile.
2. `scripts/content_manager_worker.py` wires `ContentManagerWorker`,
   `PsycopgWorkerStore`, `ConcretePageFirstPipeline`,
   `PostgresMilvusPageFirstGateway`. It supports `--job-id ... --once` without
   recovering unrelated jobs. This is the official worker, not a new worker.
3. Durable claim/lease and transitions: `content_manager_repository.py` and
   `content_manager_runtime.py`. `load_request` validates tenant/upload chain,
   exact file SHA and configured primary/E2E guards.
4. `page_first_pipeline.py:extract_pdf_page_first` calls
   `pdf_hebrew_fidelity.py:page_markdown`, which calls canonical
   `pymupdf4llm.to_markdown` and the preexisting boundary repair. Only strings
   and conservative signals return; layout ownership is not transported.
5. `ConcretePageFirstPipeline.run`: extracting → normalizing →
   `persist_document_and_pages` → `persist_chunks` → embed → persist embeddings
   → index → reconcile → finalize. **There is currently no region quality call.**
6. `page_first_gateway.py:persist_document_and_pages` stores document/text/pages,
   run and manifest. `persist_chunks` paragraph-chunks each entire page
   (1400 chars, overlap 150), with `citable=true`. IDs are deterministic.
7. `embed` calls LiteLLM, validates dimension; `index_vectors` records exact
   resource IDs before Milvus upsert; reconcile checks sets/metadata. It does
   not inspect quality, so count consistency alone cannot certify safety.
8. `finalize` moves draft → test_candidate; worker terminal is completed or
   completed_with_warnings. The upload is removed after success.
9. Authenticated `/admin/content/jobs/{job_id}/publish` uses
   `get_publish_candidate` + exact vector revalidation + CAS `publish_document`.
   Only `breslov_primary` is publishable; isolated `breslov_e2e` is not.
10. Search/RAG rehydrate canonical chunks from PostgreSQL (`hybrid_search.py`,
    `simple_research_rag.py`). `page_first_evidence.py` derives exact quote
    locations from canonical text. Quarantine cannot safely be implemented by
    hiding results here after generating chunks/vectors.

## Retry and cleanup constraints

`retry_job` only retries failed/cancelled jobs with retained, unexpired uploads
and verified cleanup; it creates a new job with incremented attempt number.
Successful jobs cannot be retried via this endpoint and have no temp file.
An eventual retry test must force a recoverable failure before success, invoke
manifest cleanup and the official retry API. It must not UPDATE a completed
job to failed. Cleanup is manifest-bounded and Milvus-first.

## No page-only worker

`PageFirstIngestionRequest` has no physical-page selector; extraction loops
through all pages. Offline provenance supports individual pages but is not an
alternative official job pipeline. No real page167 probe was executed.
