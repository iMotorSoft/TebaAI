CREATE TABLE IF NOT EXISTS library_likutey_halajot_nominal_reference_resolution_v1 (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 nominal_reference_id UUID NOT NULL REFERENCES library_likutey_halajot_nominal_references_v1(id),
 document_id UUID NOT NULL REFERENCES library_documents(id), pdf_page INTEGER NOT NULL, printed_page INTEGER,
 visible_note_number TEXT, halakhah_header_hint TEXT,
 surface_form TEXT NOT NULL, original_reference_kind TEXT NOT NULL,
 original_validation_status TEXT NOT NULL, original_normalized_reference_name TEXT,
 original_quote TEXT NOT NULL, resolution_run_id TEXT NOT NULL,
 resolution_decision TEXT NOT NULL CHECK (resolution_decision IN ('resolved_canonical_reference','keep_generic_source','rejected_false_positive','needs_research_review')),
 resolved_reference_kind TEXT, resolved_normalized_reference_name TEXT, resolved_surface_family TEXT,
 resolution_method TEXT NOT NULL CHECK (resolution_method IN ('exact_catalog_match','variant_catalog_match','deterministic_pattern','corpus_cross_match','parent_note_context','halakhah_context','multilingual_literal_match','ai_textual_classification','fallback_keep_generic','false_positive_rule')),
 resolver_chain JSONB NOT NULL DEFAULT '[]'::jsonb, evidence_quote TEXT NOT NULL, evidence_surface_form TEXT NOT NULL,
 evidence_context JSONB NOT NULL DEFAULT '{}'::jsonb, confidence NUMERIC NOT NULL,
 warnings JSONB NOT NULL DEFAULT '[]'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE (resolution_run_id, nominal_reference_id)
);
CREATE INDEX IF NOT EXISTS idx_lh_nominal_resolution_reference ON library_likutey_halajot_nominal_reference_resolution_v1(nominal_reference_id);
CREATE INDEX IF NOT EXISTS idx_lh_nominal_resolution_decision ON library_likutey_halajot_nominal_reference_resolution_v1(resolution_decision);
CREATE INDEX IF NOT EXISTS idx_lh_nominal_resolution_kind ON library_likutey_halajot_nominal_reference_resolution_v1(resolved_reference_kind);
CREATE INDEX IF NOT EXISTS idx_lh_nominal_resolution_name ON library_likutey_halajot_nominal_reference_resolution_v1(resolved_normalized_reference_name);
CREATE OR REPLACE VIEW library_likutey_halajot_nominal_reference_resolution_search_v1 AS
SELECT r.document_id,r.pdf_page,r.printed_page,r.visible_note_number,r.halakhah_header_hint,r.surface_form,
 r.reference_kind AS original_reference_kind,x.resolution_decision,x.resolved_reference_kind,
 x.resolved_normalized_reference_name,x.resolved_surface_family,x.resolution_method,x.confidence,
 x.evidence_quote AS text_quote,x.warnings,x.resolution_run_id
FROM library_likutey_halajot_nominal_references_v1 r
JOIN library_likutey_halajot_nominal_reference_resolution_v1 x ON x.nominal_reference_id=r.id;
CREATE OR REPLACE VIEW library_likutey_halajot_search_ready_v7 AS
SELECT 'page_literal_only'::text AS result_type,s.document_id,s.pdf_page,s.printed_page,s.document_part,
 s.unit_label AS halakhah_header_hint,NULL::text AS visible_note_number,NULL::text AS surface_form,
 NULL::text AS original_reference_kind,NULL::text AS resolution_decision,NULL::text AS resolved_reference_kind,
 NULL::text AS resolved_normalized_reference_name,NULL::text AS resolution_method,
 NULL::numeric AS confidence,s.page_text AS text_quote,'[]'::jsonb AS warnings
FROM library_likutey_halajot_search_ready_v2 s
UNION ALL
SELECT 'reference_resolution',r.document_id,r.pdf_page,r.printed_page,s.document_part,
 r.halakhah_header_hint,r.visible_note_number,r.surface_form,r.original_reference_kind,
 r.resolution_decision,r.resolved_reference_kind,r.resolved_normalized_reference_name,
 r.resolution_method,r.confidence,r.text_quote,r.warnings
FROM library_likutey_halajot_nominal_reference_resolution_search_v1 r
LEFT JOIN library_likutey_halajot_structural_v2 s ON s.pdf_page=r.pdf_page;
