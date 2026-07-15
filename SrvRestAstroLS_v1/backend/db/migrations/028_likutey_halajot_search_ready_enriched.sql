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
  s.content_node_id IS NOT NULL AND s.structural_status <> 'blank_page' AS searchable_by_structure,
  jsonb_array_length(COALESCE(s.zone_hints, '[]'::jsonb)) > 0 AS searchable_by_zone,
  CASE WHEN s.content_node_id IS NULL THEN ARRAY['no embedded text extracted']::text[] ELSE ARRAY[]::text[] END AS warnings
FROM library_likutey_halajot_structural_v2 s;
