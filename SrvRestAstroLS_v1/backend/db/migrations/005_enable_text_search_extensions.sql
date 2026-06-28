-- 005_enable_text_search_extensions.sql
-- Enable PostgreSQL extensions required for TebaAI library text search.
-- Full Text Search itself is PostgreSQL core; these extensions improve
-- accent-insensitive and fuzzy textual search.
--
-- unaccent: removes diacritic marks (accents) for accent-tolerant search.
-- pg_trgm:  provides trigram-based similarity and fuzzy matching.
--
-- SCHEMA public ensures functions are available without schema qualification.
-- DROP + CREATE handles the case where extensions were previously installed
-- in a non-public schema.

DROP EXTENSION IF EXISTS unaccent;
DROP EXTENSION IF EXISTS pg_trgm;

CREATE EXTENSION IF NOT EXISTS unaccent SCHEMA public;
CREATE EXTENSION IF NOT EXISTS pg_trgm SCHEMA public;
