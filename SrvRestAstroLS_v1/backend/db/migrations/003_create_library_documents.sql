-- 003_create_library_documents.sql
-- TebaAI library module: collections, documents, text, and references.
--
-- Prerequisite: schema_migrations table exists (created by the runner).
-- Guard: application must verify current_database() == 'tebaai' before running.

-- ── Library collections ───────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS library_collections (
    id               uuid        NOT NULL PRIMARY KEY,
    code             text        NOT NULL,
    name             text        NOT NULL,
    description      text,
    default_language text,
    metadata         jsonb       NOT NULL DEFAULT '{}'::jsonb,
    is_active        boolean     NOT NULL DEFAULT TRUE,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT library_collections_code_not_empty CHECK (code <> ''),
    CONSTRAINT library_collections_code_unique UNIQUE (code),
    CONSTRAINT library_collections_default_language_valid
        CHECK (default_language IS NULL OR default_language IN ('es', 'en', 'he'))
);

CREATE INDEX IF NOT EXISTS ix_library_collections_is_active ON library_collections (is_active);
CREATE INDEX IF NOT EXISTS ix_library_collections_metadata ON library_collections USING GIN (metadata);

-- ── Library documents ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS library_documents (
    id                uuid        NOT NULL PRIMARY KEY,
    collection_id     uuid        NOT NULL REFERENCES library_collections(id),
    title             text        NOT NULL,
    subtitle          text,
    language          text        NOT NULL,
    source_type       text        NOT NULL,
    source_path       text,
    source_uri        text,
    source_filename   text,
    source_mime_type  text,
    source_size_bytes bigint,
    source_sha256     text        NOT NULL,
    bibliographic_ref text,
    author            text,
    publisher         text,
    publication_year  integer,
    version_label     text,
    status            text        NOT NULL DEFAULT 'draft',
    metadata          jsonb       NOT NULL DEFAULT '{}'::jsonb,
    created_by        uuid        REFERENCES users(id),
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT library_documents_title_not_empty CHECK (title <> ''),
    CONSTRAINT library_documents_language_valid CHECK (language IN ('es', 'en', 'he')),
    CONSTRAINT library_documents_source_type_valid
        CHECK (source_type IN ('book', 'article', 'pdf', 'markdown', 'text', 'other')),
    CONSTRAINT library_documents_status_valid
        CHECK (status IN ('draft', 'ready', 'archived', 'error')),
    CONSTRAINT library_documents_sha256_not_empty CHECK (source_sha256 <> '')
);

CREATE INDEX IF NOT EXISTS ix_library_documents_collection_id ON library_documents (collection_id);
CREATE INDEX IF NOT EXISTS ix_library_documents_language ON library_documents (language);
CREATE INDEX IF NOT EXISTS ix_library_documents_status ON library_documents (status);
CREATE INDEX IF NOT EXISTS ix_library_documents_source_sha256 ON library_documents (source_sha256);
CREATE INDEX IF NOT EXISTS ix_library_documents_title_lower ON library_documents (lower(title));
CREATE INDEX IF NOT EXISTS ix_library_documents_metadata ON library_documents USING GIN (metadata);

-- Duplicate prevention: same sha256 within the same collection
CREATE UNIQUE INDEX IF NOT EXISTS uq_library_documents_collection_sha256
    ON library_documents (collection_id, source_sha256);

-- ── Library document texts ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS library_document_texts (
    id                  uuid        NOT NULL PRIMARY KEY,
    document_id         uuid        NOT NULL REFERENCES library_documents(id) ON DELETE CASCADE,
    text_format         text        NOT NULL,
    content             text        NOT NULL,
    content_sha256      text        NOT NULL,
    content_length      integer     NOT NULL,
    extraction_method   text        NOT NULL,
    extraction_metadata jsonb       NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT library_document_texts_format_valid
        CHECK (text_format IN ('markdown', 'plain_text')),
    CONSTRAINT library_document_texts_content_not_empty CHECK (content <> ''),
    CONSTRAINT library_document_texts_sha256_not_empty CHECK (content_sha256 <> ''),
    CONSTRAINT library_document_texts_length_positive CHECK (content_length >= 0)
);

CREATE INDEX IF NOT EXISTS ix_library_document_texts_document_id ON library_document_texts (document_id);
CREATE INDEX IF NOT EXISTS ix_library_document_texts_content_sha256 ON library_document_texts (content_sha256);
CREATE INDEX IF NOT EXISTS ix_library_document_texts_extraction_metadata
    ON library_document_texts USING GIN (extraction_metadata);

-- ── Library document references ───────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS library_document_references (
    id          uuid        NOT NULL PRIMARY KEY,
    document_id uuid        NOT NULL REFERENCES library_documents(id) ON DELETE CASCADE,
    ref_type    text        NOT NULL,
    ref_label   text        NOT NULL,
    ref_value   text,
    page_start  integer,
    page_end    integer,
    chapter     text,
    section     text,
    metadata    jsonb       NOT NULL DEFAULT '{}'::jsonb,
    created_at  timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT library_document_references_type_valid
        CHECK (ref_type IN ('book', 'chapter', 'section', 'page', 'paragraph', 'external')),
    CONSTRAINT library_document_references_label_not_empty CHECK (ref_label <> '')
);

CREATE INDEX IF NOT EXISTS ix_library_document_references_document_id ON library_document_references (document_id);
CREATE INDEX IF NOT EXISTS ix_library_document_references_ref_type ON library_document_references (ref_type);
CREATE INDEX IF NOT EXISTS ix_library_document_references_ref_label ON library_document_references (ref_label);
CREATE INDEX IF NOT EXISTS ix_library_document_references_metadata
    ON library_document_references USING GIN (metadata);
