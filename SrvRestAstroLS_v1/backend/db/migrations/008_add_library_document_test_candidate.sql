-- 008_add_library_document_test_candidate.sql
-- Add isolated test-candidate status and document-level bibliographic metadata.
-- Existing documents and their ready status are preserved.

ALTER TABLE library_documents
ADD COLUMN IF NOT EXISTS bibliographic_metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE library_documents
DROP CONSTRAINT IF EXISTS library_documents_status_valid;

ALTER TABLE library_documents
ADD CONSTRAINT library_documents_status_valid
CHECK (status IN ('draft', 'ready', 'test_candidate', 'archived', 'error'));

CREATE INDEX IF NOT EXISTS ix_library_documents_bibliographic_metadata
ON library_documents USING GIN (bibliographic_metadata);
