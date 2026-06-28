-- 006_add_library_chunk_full_text_search.sql
-- Add PostgreSQL Full Text Search columns and indexes to library_document_chunks.
--
-- These columns enable accent-insensitive and lexical text search over chunk
-- content using PostgreSQL's built-in FTS (tsvector/tsquery), unaccent for
-- accent tolerance, and pg_trgm for fuzzy trigram matching.
--
-- search_text_normalized:   unaccent(content) — for ILIKE/trigram searches
-- search_vector_es:         to_tsvector('spanish', unaccent(content)) — Spanish FTS
-- search_vector_simple:     to_tsvector('simple', unaccent(content)) — simple FTS for names
--
-- Idempotent: safe for re-run via schema_migrations.

-- ── Columns ───────────────────────────────────────────────────────────────────

ALTER TABLE library_document_chunks
ADD COLUMN IF NOT EXISTS search_text_normalized TEXT,
ADD COLUMN IF NOT EXISTS search_vector_es TSVECTOR,
ADD COLUMN IF NOT EXISTS search_vector_simple TSVECTOR;

-- ── Indexes ───────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_library_chunks_search_vector_es
ON library_document_chunks USING GIN (search_vector_es);

CREATE INDEX IF NOT EXISTS idx_library_chunks_search_vector_simple
ON library_document_chunks USING GIN (search_vector_simple);

CREATE INDEX IF NOT EXISTS idx_library_chunks_search_text_trgm
ON library_document_chunks USING GIN (search_text_normalized gin_trgm_ops);

-- ── Backfill existing chunks ──────────────────────────────────────────────────

UPDATE library_document_chunks
SET
  search_text_normalized = public.unaccent(content),
  search_vector_es = to_tsvector('spanish', public.unaccent(content)),
  search_vector_simple = to_tsvector('simple', public.unaccent(content))
WHERE search_vector_es IS NULL
   OR search_vector_simple IS NULL
   OR search_text_normalized IS NULL;
