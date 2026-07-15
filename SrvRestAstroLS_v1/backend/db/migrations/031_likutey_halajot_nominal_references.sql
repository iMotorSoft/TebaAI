CREATE TABLE IF NOT EXISTS library_likutey_halajot_nominal_references_v1 (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 document_id UUID NOT NULL REFERENCES library_documents(id),
 document_code TEXT NOT NULL,
 pdf_page INTEGER NOT NULL,
 printed_page INTEGER,
 page_anchor_id UUID REFERENCES library_page_anchors_v2(page_anchor_id),
 source_run_id TEXT NOT NULL,
 structural_detector_run_id TEXT NOT NULL,
 fine_zone_run_id TEXT NOT NULL,
 note_source_run_id TEXT NOT NULL,
 nominal_reference_run_id TEXT NOT NULL,
 parent_note_source_unit_id UUID REFERENCES library_likutey_halajot_note_source_units_v1(id),
 parent_fine_zone_id UUID REFERENCES library_likutey_halajot_fine_zones_v1(id),
 parent_zone_type TEXT,
 visible_note_number TEXT,
 halakhah_header_hint TEXT,
 surface_form TEXT NOT NULL,
 normalized_reference_name TEXT,
 reference_kind TEXT NOT NULL,
 reference_language TEXT,
 reference_script TEXT,
 marker_kind TEXT,
 marker_value TEXT,
 text_quote TEXT NOT NULL,
 text_start_quote TEXT,
 text_end_quote TEXT,
 quote_hash TEXT NOT NULL,
 char_start INTEGER,
 char_end INTEGER,
 confidence NUMERIC NOT NULL,
 evidence_origin TEXT NOT NULL,
 detection_origin TEXT NOT NULL,
 detection_method TEXT NOT NULL,
 validation_status TEXT NOT NULL CHECK (validation_status IN ('validated','ambiguous_surface_form','rejected','needs_editorial_review')),
 review_status TEXT NOT NULL CHECK (review_status IN ('not_required','needs_review','reviewed','rejected')),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
 raw_detection JSONB NOT NULL DEFAULT '{}'::jsonb,
 CHECK (parent_note_source_unit_id IS NOT NULL OR parent_fine_zone_id IS NOT NULL),
 UNIQUE NULLS NOT DISTINCT (nominal_reference_run_id,parent_note_source_unit_id,parent_fine_zone_id,surface_form,char_start,char_end)
);
CREATE INDEX IF NOT EXISTS idx_lh_nominal_refs_pdf_page ON library_likutey_halajot_nominal_references_v1(pdf_page);
CREATE INDEX IF NOT EXISTS idx_lh_nominal_refs_surface ON library_likutey_halajot_nominal_references_v1(surface_form);
CREATE INDEX IF NOT EXISTS idx_lh_nominal_refs_normalized ON library_likutey_halajot_nominal_references_v1(normalized_reference_name);
CREATE INDEX IF NOT EXISTS idx_lh_nominal_refs_kind ON library_likutey_halajot_nominal_references_v1(reference_kind);
CREATE INDEX IF NOT EXISTS idx_lh_nominal_refs_note ON library_likutey_halajot_nominal_references_v1(visible_note_number);
CREATE INDEX IF NOT EXISTS idx_lh_nominal_refs_halakhah ON library_likutey_halajot_nominal_references_v1(halakhah_header_hint);
CREATE INDEX IF NOT EXISTS idx_lh_nominal_refs_run ON library_likutey_halajot_nominal_references_v1(nominal_reference_run_id);
CREATE INDEX IF NOT EXISTS idx_lh_nominal_refs_validation ON library_likutey_halajot_nominal_references_v1(validation_status);

CREATE OR REPLACE VIEW library_likutey_halajot_nominal_reference_search_v1 AS
SELECT r.document_id,r.document_code,r.pdf_page,r.printed_page,r.halakhah_header_hint,r.visible_note_number,
 r.surface_form,r.normalized_reference_name,r.reference_kind,r.text_quote,r.confidence,
 r.validation_status,r.parent_zone_type,COALESCE(n.unit_type,z.zone_type) AS unit_type,
 s.document_part,r.warnings
FROM library_likutey_halajot_nominal_references_v1 r
LEFT JOIN library_likutey_halajot_note_source_units_v1 n ON n.id=r.parent_note_source_unit_id
LEFT JOIN library_likutey_halajot_fine_zones_v1 z ON z.id=r.parent_fine_zone_id
LEFT JOIN library_likutey_halajot_structural_v2 s ON s.page_anchor_id=r.page_anchor_id;

CREATE OR REPLACE VIEW library_likutey_halajot_search_ready_v6 AS
SELECT 'page_literal_only'::text AS result_type,s.document_id,s.pdf_page,s.printed_page,s.document_part,
 s.unit_label AS halakhah_header_hint,NULL::text AS visible_note_number,NULL::text AS surface_form,
 NULL::text AS normalized_reference_name,NULL::text AS reference_kind,s.page_text AS text_quote,
 NULL::numeric AS confidence,'validated'::text AS validation_status,NULL::text AS parent_zone_type,
 'page_literal'::text AS unit_type,'[]'::jsonb AS warnings
FROM library_likutey_halajot_search_ready_v2 s
UNION ALL
SELECT 'nominal_reference',r.document_id,r.pdf_page,r.printed_page,r.document_part,
 r.halakhah_header_hint,r.visible_note_number,r.surface_form,r.normalized_reference_name,
 r.reference_kind,r.text_quote,r.confidence,r.validation_status,r.parent_zone_type,r.unit_type,r.warnings
FROM library_likutey_halajot_nominal_reference_search_v1 r;
