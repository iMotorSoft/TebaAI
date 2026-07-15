-- Likutey Halajot is searchable page-first before any structural promotion.
-- This derives only from the safe source run; it never creates classifications.
CREATE OR REPLACE VIEW library_likutey_halajot_page_final_status_v2 AS
SELECT
    d.id AS document_id,
    d.document_code,
    a.pdf_page_number AS pdf_page,
    a.printed_page_number AS printed_page,
    n.content_node_id IS NOT NULL AS has_text,
    n.content_node_id IS NULL AS is_blank,
    'unknown'::text AS document_part,
    CASE WHEN n.content_node_id IS NULL THEN 'blank_page' ELSE 'unclassified' END AS structural_status,
    NULL::integer AS unit_number,
    CASE
        WHEN n.content_node_id IS NULL THEN 'blank_page'
        ELSE 'page_literal_only_unclassified'
    END AS final_page_status,
    true AS searchable_by_page,
    n.content_node_id IS NOT NULL AS searchable_by_literal,
    false AS searchable_by_structure,
    false AS searchable_by_zone,
    CASE WHEN n.content_node_id IS NULL THEN ARRAY['no embedded text extracted']::text[] ELSE ARRAY[]::text[] END AS warnings
FROM library_page_anchors_v2 a
JOIN library_documents d ON d.id = a.document_id
LEFT JOIN library_content_nodes_v2 n
  ON n.page_anchor_id = a.page_anchor_id
 AND n.metadata_json->>'source_run_id' = 'likutey_halajot_page_first_v1'
WHERE d.document_code = 'likutey_halajot_interior_final'
  AND a.edition_id = 'likutey_halajot_page_first_v1';

CREATE OR REPLACE VIEW library_likutey_halajot_search_ready_v2 AS
SELECT
    d.id AS document_id,
    d.document_code,
    n.content_node_id,
    a.pdf_page_number AS pdf_page,
    a.printed_page_number AS printed_page,
    n.literal_text AS page_text,
    n.normalized_text,
    n.literal_hash AS page_literal_hash,
    n.metadata_json->>'source_run_id' AS source_run_id,
    'unknown'::text AS document_part,
    'unclassified'::text AS structural_status,
    NULL::text AS unit_type,
    NULL::text AS unit_label,
    NULL::integer AS unit_number,
    n.content_type,
    n.node_role,
    n.authority_level,
    n.marker_kind,
    n.marker_value,
    n.visible_note_number,
    n.note_start_status,
    n.link_status,
    n.review_status,
    'page_literal_only'::text AS final_ingestion_decision,
    n.literal_text AS literal_snippet
FROM library_content_nodes_v2 n
JOIN library_page_anchors_v2 a ON a.page_anchor_id = n.page_anchor_id
JOIN library_documents d ON d.id = a.document_id
WHERE d.document_code = 'likutey_halajot_interior_final'
  AND n.metadata_json->>'source_run_id' = 'likutey_halajot_page_first_v1';
