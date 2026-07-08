-- 013_add_layout_aware_columns.sql
-- Add layout-aware columns to library_document_chunks for block-level
-- processing (e.g. Likutey Halajot Interior Final).
--
-- These columns support the layout-aware ingestion pipeline without
-- requiring a separate blocks table. Each chunk represents one atomic
-- block (source_hebrew, main_explanation_es, marginal_source, footnote, etc.).

ALTER TABLE library_document_chunks
  ADD COLUMN IF NOT EXISTS block_type          text,
  ADD COLUMN IF NOT EXISTS block_subtype       text,
  ADD COLUMN IF NOT EXISTS evidence_role       text,
  ADD COLUMN IF NOT EXISTS citable             boolean NOT NULL DEFAULT true,
  ADD COLUMN IF NOT EXISTS layout_confidence   real,
  ADD COLUMN IF NOT EXISTS ingestion_profile   text,
  ADD COLUMN IF NOT EXISTS printed_page_label  text;

COMMENT ON COLUMN library_document_chunks.block_type IS 'Layout-aware block type: page_header, source_hebrew, section_marker, main_explanation_es, marginal_source, footnote, internal_cross_reference, composite_page_context, unknown';
COMMENT ON COLUMN library_document_chunks.block_subtype IS 'Optional subtype: biblical_citation, rabbinic_reference, halachic_reference, breslov_teaching, theological_explanation, bibliographic_note, translator_editor_note, cross_page_note, halachic_derash';
COMMENT ON COLUMN library_document_chunks.evidence_role IS 'Evidence classification: source_text, commentary, direct_quote, marginal_citation, bibliographic_note, halachic_derash, thematic_context, composite_for_retrieval';
COMMENT ON COLUMN library_document_chunks.citable IS 'Whether this chunk can be cited as a final source. Composite chunks (composite_page_context) must be citable=false.';
COMMENT ON COLUMN library_document_chunks.layout_confidence IS 'Confidence score (0.0-1.0) of the layout-aware block classification';
COMMENT ON COLUMN library_document_chunks.ingestion_profile IS 'Ingestion pipeline identifier, e.g. layout_aware_likutey_halajot';
COMMENT ON COLUMN library_document_chunks.printed_page_label IS 'The printed page label as it appears in the original document (e.g. "23", "32a")';

-- Widen the language CHECK to include mixed and unknown
ALTER TABLE library_document_chunks
  DROP CONSTRAINT IF EXISTS library_document_chunks_language_valid;

ALTER TABLE library_document_chunks
  ADD CONSTRAINT library_document_chunks_language_valid
    CHECK (language IN ('es', 'en', 'he', 'mixed', 'unknown'));

-- Indexes for the new columns
CREATE INDEX IF NOT EXISTS ix_library_document_chunks_block_type
  ON library_document_chunks (block_type);

CREATE INDEX IF NOT EXISTS ix_library_document_chunks_citable
  ON library_document_chunks (citable);

CREATE INDEX IF NOT EXISTS ix_library_document_chunks_ingestion_profile
  ON library_document_chunks (ingestion_profile);
