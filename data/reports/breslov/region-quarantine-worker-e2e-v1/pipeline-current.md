# Pipeline inspected before changes

- Entrypoint: `backend/scripts/content_manager_worker.py` constructs `ContentManagerWorker`, `PsycopgWorkerStore` and `ConcretePageFirstPipeline(PostgresMilvusPageFirstGateway)`.
- Upload: authenticated `/admin/content/uploads`, validated PDF in `CONTENT_MANAGER_STORAGE_DIR`; upload row holds temporary path/hash/expiry. `/admin/content/jobs` creates durable queued job.
- Claim/state/lease: `content_manager_repository.py`; job/attempt rows, targeted claim supported. Worker catches unexpected errors, records failure, compensates manifest resources.
- Extraction: `page_first_pipeline.extract_pdf_page_first` uses page Markdown serializer, not regional certificates. No regional enforcement exists before this gate.
- Persistence: gateway writes canonical `library_document_texts`, `library_pages_v2` and ingestion manifest. `persist_chunks` previously chunks entire page with overlap.
- Embeddings: gateway embeds chunk content through LiteLLM; PostgreSQL tracks embeddings. `MilvusAttemptIndex` writes exact IDs to isolated E2E collection.
- Retrieval: `/library/search` authorizes knowledge scope then invokes real PostgreSQL text search / hybrid (Milvus + PG rehydration). Citations use canonical PG chunks via evidence builders.
- Source lifecycle defect: gateway `finalize` deletes upload file and clears temp path. No durable source copy or document source_path is written here.
- Existing storage: configured Content Manager local storage root is available; existing library_documents.source_path supports server-side location. No protected original-PDF download route found. Existing SourcePanel displays textual evidence, not an original-PDF endpoint.

Required changes: consume existing V5 certificates via region_publication BEFORE canonical persistence/chunks; retain audit metadata in page layout_notes; chunk each accepted region independently; preserve PDF under existing storage root and expose scope-authorized original + page metadata endpoints. No changes to certification, lineage, evaluator, embedding model or search ranking.
