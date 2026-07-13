-- Canonical investigative document model. PostgreSQL remains the source of truth.
-- Legacy pages/chunks stay read-only compatibility inputs during the V2→V3 transition.

CREATE TABLE IF NOT EXISTS library_content_units_v2 (
    content_unit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_content_unit_id UUID REFERENCES library_content_units_v2(content_unit_id),
    document_id UUID NOT NULL REFERENCES library_documents(id),
    unit_type TEXT NOT NULL,
    canonical_ref TEXT,
    title TEXT NOT NULL,
    order_index INTEGER NOT NULL,
    language_original TEXT,
    is_breslov_primary_source BOOLEAN NOT NULL DEFAULT FALSE,
    is_direct_rebbe_nachman BOOLEAN NOT NULL DEFAULT FALSE,
    is_rabbi_natan BOOLEAN NOT NULL DEFAULT FALSE,
    is_commentary_or_derivative BOOLEAN NOT NULL DEFAULT FALSE,
    source_run_id UUID REFERENCES library_ingestion_runs_v2(run_id),
    metadata_json JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (unit_type IN ('work','part','volume','lesson','lesson_section','halakhic_discourse','chapter','story','prayer','sicha','letter','introduction','appendix','glossary','diagram_collection','note_collection','section','page')),
    CHECK (NOT (is_direct_rebbe_nachman AND is_rabbi_natan))
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_content_units_document_ref ON library_content_units_v2(document_id, canonical_ref) WHERE canonical_ref IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_content_units_parent ON library_content_units_v2(parent_content_unit_id);

CREATE OR REPLACE FUNCTION library_content_unit_no_cycle() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.parent_content_unit_id IS NULL THEN RETURN NEW; END IF;
  IF NEW.parent_content_unit_id = NEW.content_unit_id THEN RAISE EXCEPTION 'content unit cannot parent itself'; END IF;
  IF EXISTS (WITH RECURSIVE ancestors(id) AS (
      SELECT NEW.parent_content_unit_id
      UNION ALL SELECT u.parent_content_unit_id FROM library_content_units_v2 u JOIN ancestors a ON u.content_unit_id=a.id WHERE u.parent_content_unit_id IS NOT NULL
  ) SELECT 1 FROM ancestors WHERE id=NEW.content_unit_id) THEN
    RAISE EXCEPTION 'content unit parent would create a cycle';
  END IF;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_content_unit_no_cycle ON library_content_units_v2;
CREATE TRIGGER trg_content_unit_no_cycle BEFORE INSERT OR UPDATE OF parent_content_unit_id ON library_content_units_v2 FOR EACH ROW EXECUTE FUNCTION library_content_unit_no_cycle();

CREATE TABLE IF NOT EXISTS library_page_anchors_v2 (
    page_anchor_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_file_id UUID NOT NULL REFERENCES library_documents(id),
    document_id UUID NOT NULL REFERENCES library_documents(id),
    edition_id TEXT,
    pdf_page_number INTEGER NOT NULL CHECK (pdf_page_number > 0),
    printed_page_number INTEGER,
    page_label TEXT,
    section_page_label TEXT,
    legacy_page_id UUID REFERENCES library_pages_v2(page_id),
    bbox_json JSONB,
    char_start INTEGER CHECK (char_start IS NULL OR char_start >= 0),
    char_end INTEGER CHECK (char_end IS NULL OR char_end >= char_start),
    confidence NUMERIC NOT NULL DEFAULT 1 CHECK (confidence >= 0 AND confidence <= 1),
    metadata_json JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(document_id, pdf_page_number, edition_id)
);
CREATE INDEX IF NOT EXISTS idx_page_anchors_document_page ON library_page_anchors_v2(document_id, pdf_page_number);

CREATE TABLE IF NOT EXISTS library_content_nodes_v2 (
    content_node_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_unit_id UUID NOT NULL REFERENCES library_content_units_v2(content_unit_id),
    node_role TEXT NOT NULL,
    content_type TEXT NOT NULL,
    relation_to_primary TEXT,
    authority_level TEXT NOT NULL,
    language TEXT NOT NULL,
    script TEXT,
    literal_text TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    literal_hash TEXT NOT NULL,
    page_anchor_id UUID REFERENCES library_page_anchors_v2(page_anchor_id),
    node_order INTEGER NOT NULL,
    citable BOOLEAN NOT NULL DEFAULT TRUE,
    layout_json JSONB,
    source_run_id UUID REFERENCES library_ingestion_runs_v2(run_id),
    metadata_json JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (node_role IN ('primary','satellite')),
    CHECK (node_role = 'primary' OR relation_to_primary IS NOT NULL),
    CHECK (content_type IN ('hebrew_main_text','spanish_main_text','english_main_text','spanish_translation','english_translation','main_explanation','rabbi_natan_commentary','rebbe_nachman_teaching','halakhic_body','story_text','prayer_text','editorial_note','translator_note','numbered_footnote','marginal_source','marginal_commentary','biblical_quote','talmudic_quote','midrash_quote','zohar_quote','halakhic_source_quote','kabbalistic_source_quote','source_reference','cross_reference','glossary_entry','diagram','summary','index_entry','page_header','section_marker','appendix_material','bibliography','copyright','dedication','blank','unknown')),
    CHECK (authority_level IN ('primary_original','primary_translation','primary_parallel','rabbi_natan_primary_commentary','source_cited_by_primary','rabbinic_source','rabbinic_commentary','secondary_explanatory','editorial_support','translator_support','bibliographic_support','visual_support','navigational','non_evidential','unknown')),
    CHECK (NOT citable OR page_anchor_id IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_content_nodes_unit ON library_content_nodes_v2(content_unit_id, node_order);
CREATE INDEX IF NOT EXISTS idx_content_nodes_anchor ON library_content_nodes_v2(page_anchor_id);
CREATE INDEX IF NOT EXISTS idx_content_nodes_search ON library_content_nodes_v2 USING gin (to_tsvector('simple', normalized_text));

CREATE TABLE IF NOT EXISTS library_literal_spans_v2 (
    literal_span_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_node_id UUID NOT NULL REFERENCES library_content_nodes_v2(content_node_id) ON DELETE CASCADE,
    start_char INTEGER NOT NULL CHECK (start_char >= 0),
    end_char INTEGER NOT NULL CHECK (end_char > start_char),
    literal_text TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    hash TEXT NOT NULL,
    detected_terms_json JSONB NOT NULL DEFAULT '[]',
    metadata_json JSONB NOT NULL DEFAULT '{}',
    UNIQUE(content_node_id, start_char, end_char)
);
CREATE TABLE IF NOT EXISTS library_semantic_units_v2 (
    semantic_unit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_node_id UUID NOT NULL REFERENCES library_content_nodes_v2(content_node_id) ON DELETE CASCADE,
    literal_span_id UUID REFERENCES library_literal_spans_v2(literal_span_id),
    text TEXT NOT NULL,
    text_hash TEXT NOT NULL,
    chunk_order INTEGER NOT NULL,
    chunker_name TEXT NOT NULL,
    chunker_config_json JSONB NOT NULL DEFAULT '{}',
    token_count_estimate INTEGER,
    language TEXT NOT NULL,
    source_run_id UUID REFERENCES library_ingestion_runs_v2(run_id),
    metadata_json JSONB NOT NULL DEFAULT '{}',
    UNIQUE(content_node_id, chunk_order)
);
CREATE INDEX IF NOT EXISTS idx_semantic_units_node ON library_semantic_units_v2(content_node_id);

CREATE TABLE IF NOT EXISTS library_content_relations_v2 (
    relation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_content_unit_id UUID REFERENCES library_content_units_v2(content_unit_id),
    target_content_unit_id UUID REFERENCES library_content_units_v2(content_unit_id),
    source_content_node_id UUID REFERENCES library_content_nodes_v2(content_node_id),
    target_content_node_id UUID REFERENCES library_content_nodes_v2(content_node_id),
    relation_type TEXT NOT NULL,
    evidence_type TEXT NOT NULL,
    confidence NUMERIC NOT NULL DEFAULT 1 CHECK (confidence >= 0 AND confidence <= 1),
    authority_delta INTEGER NOT NULL DEFAULT 0,
    explanation TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (source_content_unit_id IS NOT NULL OR source_content_node_id IS NOT NULL),
    CHECK (target_content_unit_id IS NOT NULL OR target_content_node_id IS NOT NULL),
    CHECK (relation_type IN ('parent_child','is_part_of','is_primary_text_of','is_satellite_of','translates','parallel_translation','explains','comments_on','quotes','cites','derives_from','applies','summarizes','defines_term','visualizes','cross_references','same_lesson_section','same_page','same_node','same_semantic_unit','literal_cooccurrence','thematic_relation','bechina_relation','remez_relation','derash_relation','ai_inferred','editorial_only')),
    CHECK (evidence_type IN ('literal','literal_same_span','literal_same_node','same_page','same_section','semantic','thematic','cited_source','editorial_explanation','translation_alignment','inferred','remesh_derash','weak_contextual'))
);
CREATE INDEX IF NOT EXISTS idx_content_relations_source_node ON library_content_relations_v2(source_content_node_id);
CREATE INDEX IF NOT EXISTS idx_content_relations_target_node ON library_content_relations_v2(target_content_node_id);

CREATE TABLE IF NOT EXISTS library_multilingual_terms_v2 (
    term_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_term TEXT NOT NULL UNIQUE,
    language TEXT NOT NULL,
    aliases_json JSONB NOT NULL DEFAULT '[]',
    transliterations_json JSONB NOT NULL DEFAULT '[]',
    metadata_json JSONB NOT NULL DEFAULT '{}'
);

CREATE OR REPLACE VIEW library_investigative_evidence_view AS
SELECT n.content_node_id, u.document_id, u.canonical_ref, u.title AS content_unit_title,
       n.content_type, n.node_role, n.authority_level, n.language, n.literal_text,
       a.pdf_page_number, a.printed_page_number, a.page_label, n.citable,
       n.source_run_id, n.metadata_json
FROM library_content_nodes_v2 n
JOIN library_content_units_v2 u ON u.content_unit_id=n.content_unit_id
LEFT JOIN library_page_anchors_v2 a ON a.page_anchor_id=n.page_anchor_id;
