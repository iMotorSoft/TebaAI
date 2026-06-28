-- 004_create_library_chunks_and_embeddings.sql
-- TebaAI library module: chunks, embedding runs, and chunk embeddings tracking.
--
-- Prerequisite: schema_migrations table exists (created by the runner).
-- Guard: application must verify current_database() == 'tebaai' before running.

-- ── Library document chunks ───────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS library_document_chunks (
    id                  uuid        NOT NULL PRIMARY KEY,
    document_id         uuid        NOT NULL REFERENCES library_documents(id) ON DELETE CASCADE,
    document_text_id    uuid        NOT NULL REFERENCES library_document_texts(id) ON DELETE CASCADE,
    collection_id       uuid        NOT NULL REFERENCES library_collections(id),
    chunk_index         integer     NOT NULL,
    chunk_uid           text        NOT NULL,
    language            text        NOT NULL,
    content             text        NOT NULL,
    content_sha256      text        NOT NULL,
    content_length      integer     NOT NULL,
    token_count_estimate integer,
    char_start          integer,
    char_end            integer,
    page_start          integer,
    page_end            integer,
    chapter             text,
    section             text,
    metadata            jsonb       NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT library_document_chunks_index_positive CHECK (chunk_index >= 0),
    CONSTRAINT library_document_chunks_language_valid CHECK (language IN ('es', 'en', 'he')),
    CONSTRAINT library_document_chunks_content_not_empty CHECK (content <> ''),
    CONSTRAINT library_document_chunks_sha256_not_empty CHECK (content_sha256 <> ''),
    CONSTRAINT library_document_chunks_length_positive CHECK (content_length > 0),
    CONSTRAINT library_document_chunks_chars_valid
        CHECK (char_start IS NULL OR char_start >= 0),
    CONSTRAINT library_document_chunks_chars_order
        CHECK (char_end IS NULL OR char_start IS NULL OR char_end >= char_start),
    CONSTRAINT library_document_chunks_uid_unique UNIQUE (chunk_uid)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_library_document_chunks_text_index
    ON library_document_chunks (document_text_id, chunk_index);
CREATE INDEX IF NOT EXISTS ix_library_document_chunks_document_id
    ON library_document_chunks (document_id);
CREATE INDEX IF NOT EXISTS ix_library_document_chunks_collection_id
    ON library_document_chunks (collection_id);
CREATE INDEX IF NOT EXISTS ix_library_document_chunks_language
    ON library_document_chunks (language);
CREATE INDEX IF NOT EXISTS ix_library_document_chunks_content_sha256
    ON library_document_chunks (content_sha256);
CREATE INDEX IF NOT EXISTS ix_library_document_chunks_metadata
    ON library_document_chunks USING GIN (metadata);

-- ── Library embedding runs ───────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS library_embedding_runs (
    id                  uuid        NOT NULL PRIMARY KEY,
    collection_code     text        NOT NULL,
    milvus_collection   text        NOT NULL,
    embedding_provider  text        NOT NULL,
    embedding_model     text        NOT NULL,
    embedding_dimension integer     NOT NULL,
    status              text        NOT NULL DEFAULT 'pending',
    chunks_total        integer     NOT NULL DEFAULT 0,
    chunks_embedded     integer     NOT NULL DEFAULT 0,
    chunks_indexed      integer     NOT NULL DEFAULT 0,
    error_message       text,
    metadata            jsonb       NOT NULL DEFAULT '{}'::jsonb,
    started_at          timestamptz NOT NULL DEFAULT now(),
    finished_at         timestamptz,

    CONSTRAINT library_embedding_runs_status_valid
        CHECK (status IN ('pending', 'running', 'completed', 'failed'))
);

CREATE INDEX IF NOT EXISTS ix_library_embedding_runs_collection_code
    ON library_embedding_runs (collection_code);
CREATE INDEX IF NOT EXISTS ix_library_embedding_runs_milvus_collection
    ON library_embedding_runs (milvus_collection);
CREATE INDEX IF NOT EXISTS ix_library_embedding_runs_status
    ON library_embedding_runs (status);
CREATE INDEX IF NOT EXISTS ix_library_embedding_runs_metadata
    ON library_embedding_runs USING GIN (metadata);

-- ── Library chunk embeddings (tracking of what was indexed in Milvus) ────────

CREATE TABLE IF NOT EXISTS library_chunk_embeddings (
    id                  uuid        NOT NULL PRIMARY KEY,
    chunk_id            uuid        NOT NULL REFERENCES library_document_chunks(id) ON DELETE CASCADE,
    embedding_run_id    uuid        REFERENCES library_embedding_runs(id),
    embedding_provider  text        NOT NULL,
    embedding_model     text        NOT NULL,
    embedding_dimension integer     NOT NULL,
    milvus_collection   text        NOT NULL,
    milvus_primary_key  text        NOT NULL,
    content_sha256      text        NOT NULL,
    status              text        NOT NULL DEFAULT 'indexed',
    metadata            jsonb       NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT library_chunk_embeddings_status_valid
        CHECK (status IN ('indexed', 'failed', 'skipped'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_library_chunk_embeddings_chunk_provider
    ON library_chunk_embeddings (chunk_id, embedding_provider, embedding_model, milvus_collection);
CREATE INDEX IF NOT EXISTS ix_library_chunk_embeddings_embedding_run_id
    ON library_chunk_embeddings (embedding_run_id);
CREATE INDEX IF NOT EXISTS ix_library_chunk_embeddings_content_sha256
    ON library_chunk_embeddings (content_sha256);
CREATE INDEX IF NOT EXISTS ix_library_chunk_embeddings_status
    ON library_chunk_embeddings (status);
CREATE INDEX IF NOT EXISTS ix_library_chunk_embeddings_metadata
    ON library_chunk_embeddings USING GIN (metadata);
