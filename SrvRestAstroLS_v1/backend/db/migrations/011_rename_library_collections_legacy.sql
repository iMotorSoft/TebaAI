-- 011_rename_library_collections_legacy.sql
-- Rename library_collections to library_collections_legacy.
-- knowledge_scopes is the primary container in PG18 Product Schema v1.
-- Drop FK constraints pointing to library_collections first.
-- Preserve all data. No compatibility view is created.

DO $$ BEGIN
    -- 1. Drop FK constraints referencing library_collections
    IF EXISTS (
        SELECT 1 FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        WHERE con.conname = 'library_documents_collection_id_fkey'
    ) THEN
        ALTER TABLE library_documents DROP CONSTRAINT library_documents_collection_id_fkey;
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        WHERE con.conname = 'library_document_chunks_collection_id_fkey'
    ) THEN
        ALTER TABLE library_document_chunks DROP CONSTRAINT library_document_chunks_collection_id_fkey;
    END IF;

    -- 2. Rename table if it exists and legacy doesn't exist yet
    IF EXISTS (
        SELECT 1 FROM pg_class WHERE relname = 'library_collections' AND relkind = 'r'
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_class WHERE relname = 'library_collections_legacy' AND relkind = 'r'
    ) THEN
        ALTER TABLE library_collections RENAME TO library_collections_legacy;

        -- Rename indexes for clarity
        IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'library_collections_pkey') THEN
            ALTER INDEX library_collections_pkey RENAME TO library_collections_legacy_pkey;
        END IF;
        IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'library_collections_code_unique') THEN
            ALTER INDEX library_collections_code_unique RENAME TO library_collections_legacy_code_unique;
        END IF;
        IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_library_collections_is_active') THEN
            ALTER INDEX ix_library_collections_is_active RENAME TO ix_library_collections_legacy_is_active;
        END IF;
        IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_library_collections_metadata') THEN
            ALTER INDEX ix_library_collections_metadata RENAME TO ix_library_collections_legacy_metadata;
        END IF;

        -- 3. Add comment
        COMMENT ON TABLE library_collections_legacy IS
        'DEPRECATED: replaced by knowledge_scopes in PG18 Product Schema v1 (ADR-004). Do not use for new writes. Historical compatibility only.';
    END IF;
END $$;
