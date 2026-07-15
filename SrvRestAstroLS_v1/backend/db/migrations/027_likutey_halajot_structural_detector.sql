-- General-purpose enrichment columns; page-first nodes remain untouched.
ALTER TABLE library_page_structural_classifications_v2
  ADD COLUMN IF NOT EXISTS unit_type TEXT,
  ADD COLUMN IF NOT EXISTS unit_label TEXT,
  ADD COLUMN IF NOT EXISTS unit_number INTEGER,
  ADD COLUMN IF NOT EXISTS zone_hints JSONB NOT NULL DEFAULT '[]'::jsonb;

CREATE INDEX IF NOT EXISTS idx_page_structural_source_run
  ON library_page_structural_classifications_v2(source_run_id, pdf_page);

DROP VIEW IF EXISTS library_likutey_halajot_page_final_status_v2;
DROP VIEW IF EXISTS library_likutey_halajot_search_ready_v2;

CREATE OR REPLACE VIEW library_likutey_halajot_structural_v2 AS
SELECT
  d.id AS document_id,
  d.document_code,
  a.page_anchor_id,
  a.pdf_page_number AS pdf_page,
  COALESCE(c.printed_page, a.printed_page_number) AS printed_page,
  n.content_node_id,
  n.literal_text,
  n.normalized_text,
  c.source_run_id AS detector_run_id,
  c.document_part,
  c.structural_status,
  c.unit_type,
  c.unit_label,
  c.unit_number,
  c.confidence AS structural_confidence,
  c.evidence_origin,
  c.evidence_text,
  c.zone_hints,
  c.classification_action,
  c.review_status,
  c.rationale
FROM library_page_anchors_v2 a
JOIN library_documents d ON d.id = a.document_id
LEFT JOIN library_content_nodes_v2 n
  ON n.page_anchor_id = a.page_anchor_id
 AND n.metadata_json->>'source_run_id' = 'likutey_halajot_page_first_v1'
LEFT JOIN library_page_structural_classifications_v2 c
  ON c.page_anchor_id = a.page_anchor_id
 AND c.source_run_id = 'likutey_halajot_structural_detector_v1_20260714'
WHERE d.document_code = 'likutey_halajot_interior_final'
  AND a.edition_id = 'likutey_halajot_page_first_v1';

CREATE OR REPLACE VIEW library_likutey_halajot_search_ready_v2 AS
SELECT
  s.document_id, s.document_code, s.content_node_id, s.pdf_page, s.printed_page,
  s.literal_text AS page_text, s.normalized_text,
  n.literal_hash AS page_literal_hash,
  n.metadata_json->>'source_run_id' AS source_run_id,
  s.document_part, s.structural_status, s.unit_type, s.unit_label, s.unit_number,
  s.structural_confidence, s.evidence_origin, s.evidence_text, s.zone_hints,
  n.content_type, n.node_role, n.authority_level, n.marker_kind, n.marker_value,
  n.visible_note_number, n.note_start_status, n.link_status, n.review_status,
  'page_literal_only'::text AS final_ingestion_decision,
  n.literal_text AS literal_snippet
FROM library_likutey_halajot_structural_v2 s
JOIN library_content_nodes_v2 n ON n.content_node_id = s.content_node_id;

CREATE OR REPLACE VIEW library_likutey_halajot_page_final_status_v2 AS
SELECT
  s.document_id, s.document_code, s.pdf_page, s.printed_page,
  s.content_node_id IS NOT NULL AS has_text,
  s.content_node_id IS NULL AS is_blank,
  COALESCE(s.document_part, 'unknown') AS document_part,
  COALESCE(s.structural_status, CASE WHEN s.content_node_id IS NULL THEN 'blank_page' ELSE 'unclassified' END) AS structural_status,
  s.unit_type, s.unit_label, s.unit_number,
  CASE
    WHEN s.content_node_id IS NULL THEN 'blank_page'
    WHEN s.document_part IN ('appendix', 'diagram', 'glossary') THEN 'classified_appendix'
    WHEN s.structural_status = 'classified' THEN 'classified_structural_page'
    WHEN s.document_part IN ('front_matter', 'index') THEN 'front_or_index_page_literal_only'
    ELSE 'page_literal_only_unclassified'
  END AS final_page_status,
  true AS searchable_by_page,
  s.content_node_id IS NOT NULL AS searchable_by_literal,
  s.structural_status = 'classified' AS searchable_by_structure,
  jsonb_array_length(COALESCE(s.zone_hints, '[]'::jsonb)) > 0 AS searchable_by_zone,
  CASE WHEN s.content_node_id IS NULL THEN ARRAY['no embedded text extracted']::text[] ELSE ARRAY[]::text[] END AS warnings
FROM library_likutey_halajot_structural_v2 s;
