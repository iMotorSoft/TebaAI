-- Hebrew literal retrieval over canonical investigative nodes.
-- Canonical literal_text is untouched; normalized_text is a derived search field.

CREATE INDEX IF NOT EXISTS idx_content_nodes_normalized_text_trgm
ON library_content_nodes_v2 USING GIN (normalized_text gin_trgm_ops);

CREATE OR REPLACE VIEW library_lmi_literal_search_v1 AS
SELECT
    n.content_node_id,
    n.literal_hash,
    n.literal_text,
    n.normalized_text,
    n.language,
    n.source_run_id,
    n.metadata_json,
    a.page_anchor_id,
    a.pdf_page_number,
    a.printed_page_number,
    a.section_page_label,
    d.id AS document_id,
    d.title AS document_title,
    d.source_filename,
    d.source_sha256,
    d.document_code
FROM library_content_nodes_v2 n
JOIN library_page_anchors_v2 a ON a.page_anchor_id = n.page_anchor_id
JOIN library_documents d ON d.id = a.document_id
WHERE d.document_code = 'likutey_moharan_i_spanish_bri'
  AND n.citable = true;

COMMENT ON VIEW library_lmi_literal_search_v1 IS
'Literal-search projection for the physical Likutey Moharan I Spanish BRI PDF; source filename is documentary metadata, never inferred from editorial headers.';
