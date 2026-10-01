-- Legacy collection IDs are compatibility metadata, not cross-scope identity.
-- Preserve the previous uniqueness within each scope and for unscoped rows.
CREATE UNIQUE INDEX IF NOT EXISTS uq_library_documents_scope_collection_sha256
    ON library_documents (knowledge_scope_id, collection_id, source_sha256)
    WHERE knowledge_scope_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_library_documents_unscoped_collection_sha256
    ON library_documents (collection_id, source_sha256)
    WHERE knowledge_scope_id IS NULL;

DROP INDEX IF EXISTS uq_library_documents_collection_sha256;
