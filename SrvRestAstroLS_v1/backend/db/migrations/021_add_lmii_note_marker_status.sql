ALTER TABLE library_content_nodes_v2 ADD COLUMN IF NOT EXISTS marker_kind TEXT NOT NULL DEFAULT 'not_applicable';
ALTER TABLE library_content_nodes_v2 ADD COLUMN IF NOT EXISTS marker_value TEXT;
ALTER TABLE library_content_nodes_v2 ADD COLUMN IF NOT EXISTS marker_status TEXT NOT NULL DEFAULT 'not_applicable';
ALTER TABLE library_content_nodes_v2 ADD COLUMN IF NOT EXISTS visible_note_number INTEGER;
ALTER TABLE library_content_nodes_v2 ADD COLUMN IF NOT EXISTS probable_note_number INTEGER;
ALTER TABLE library_content_nodes_v2 ADD COLUMN IF NOT EXISTS note_start_status TEXT NOT NULL DEFAULT 'not_applicable';
ALTER TABLE library_content_nodes_v2 ADD COLUMN IF NOT EXISTS visible_start_text TEXT;
ALTER TABLE library_content_nodes_v2 ADD COLUMN IF NOT EXISTS is_note_start BOOLEAN;
ALTER TABLE library_content_nodes_v2 ADD COLUMN IF NOT EXISTS is_continuation_candidate BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE library_content_nodes_v2 ADD COLUMN IF NOT EXISTS marker_confidence NUMERIC;
ALTER TABLE library_content_nodes_v2 ADD COLUMN IF NOT EXISTS marker_detection_origin TEXT NOT NULL DEFAULT 'unknown';
CREATE INDEX IF NOT EXISTS idx_content_nodes_marker ON library_content_nodes_v2(marker_kind, visible_note_number);
CREATE OR REPLACE VIEW library_investigative_nodes_v2 AS
SELECT n.content_node_id,u.document_id,u.canonical_ref AS section,a.pdf_page_number,a.printed_page_number,a.page_label,n.content_type,n.node_role,n.authority_level,n.link_status,n.review_status,n.ai_confidence AS confidence,n.literal_text,n.normalized_text,n.metadata_json->>'source_or_commentator' AS source_or_commentator,n.citable,n.marker_kind,n.marker_value,n.marker_status,n.visible_note_number AS note_number,n.visible_note_number,n.probable_note_number,n.note_start_status,n.visible_start_text,n.is_note_start,n.is_continuation_candidate,n.marker_confidence,n.marker_detection_origin
FROM library_content_nodes_v2 n JOIN library_content_units_v2 u ON u.content_unit_id=n.content_unit_id JOIN library_page_anchors_v2 a ON a.page_anchor_id=n.page_anchor_id;
