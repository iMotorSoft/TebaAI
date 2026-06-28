-- 007_add_library_chunk_bibliographic_metadata.sql
-- Add bibliographic metadata columns to library_document_chunks.
--
-- These columns store page ranges and structural metadata derived from
-- page-aware PDF auditing. Only high-confidence mappings are populated.
--
-- Idempotent: safe for re-run via schema_migrations.

-- ── Columns ───────────────────────────────────────────────────────────────────

ALTER TABLE library_document_chunks
ADD COLUMN IF NOT EXISTS page_start           INTEGER,
ADD COLUMN IF NOT EXISTS page_end             INTEGER,
ADD COLUMN IF NOT EXISTS chapter              TEXT,
ADD COLUMN IF NOT EXISTS section              TEXT,
ADD COLUMN IF NOT EXISTS paragraph_index      INTEGER,
ADD COLUMN IF NOT EXISTS reference_label      TEXT,
ADD COLUMN IF NOT EXISTS bibliographic_metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

-- ── Constraints ───────────────────────────────────────────────────────────────

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_library_chunks_page_start_positive'
    ) THEN
        ALTER TABLE library_document_chunks
        ADD CONSTRAINT chk_library_chunks_page_start_positive
        CHECK (page_start IS NULL OR page_start > 0);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_library_chunks_page_end_positive'
    ) THEN
        ALTER TABLE library_document_chunks
        ADD CONSTRAINT chk_library_chunks_page_end_positive
        CHECK (page_end IS NULL OR page_end > 0);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_library_chunks_page_range'
    ) THEN
        ALTER TABLE library_document_chunks
        ADD CONSTRAINT chk_library_chunks_page_range
        CHECK (
            page_start IS NULL
            OR page_end IS NULL
            OR page_end >= page_start
        );
    END IF;
END $$;

-- ── Indexes ───────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_library_chunks_document_page
ON library_document_chunks (document_id, page_start, page_end);

CREATE INDEX IF NOT EXISTS idx_library_chunks_reference_label
ON library_document_chunks (reference_label)
WHERE reference_label IS NOT NULL;
