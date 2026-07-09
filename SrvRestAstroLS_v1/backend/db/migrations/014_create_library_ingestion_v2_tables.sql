-- 014_create_library_ingestion_v2_tables.sql
-- Non-destructive V2 tables for structured document ingestion.
-- All tables are new; no existing tables are modified.

-- ── library_ingestion_runs_v2 ──────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS library_ingestion_runs_v2 (
    run_id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID        NOT NULL,
    pipeline_version TEXT       NOT NULL,
    scope_code      TEXT        NOT NULL,
    status          TEXT        NOT NULL DEFAULT 'started',
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    metrics_json    JSONB       NOT NULL DEFAULT '{}',
    warnings_json   JSONB       NOT NULL DEFAULT '[]',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE  library_ingestion_runs_v2 IS 'Registro de ejecuciones de ingesta V2';
COMMENT ON COLUMN library_ingestion_runs_v2.status IS 'started | completed | failed | partial';

-- ── library_pages_v2 ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS library_pages_v2 (
    page_id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id           UUID        NOT NULL REFERENCES library_ingestion_runs_v2(run_id),
    document_id      UUID        NOT NULL,
    page_number      INTEGER     NOT NULL,
    text             TEXT        NOT NULL,
    char_count       INTEGER     NOT NULL DEFAULT 0,
    extraction_method TEXT       NOT NULL DEFAULT 'reconstructed',
    confidence       NUMERIC,
    layout_notes     JSONB       NOT NULL DEFAULT '{}',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, page_number, run_id)
);

CREATE INDEX IF NOT EXISTS idx_pages_v2_doc_page ON library_pages_v2(document_id, page_number);
CREATE INDEX IF NOT EXISTS idx_pages_v2_doc     ON library_pages_v2(document_id);

COMMENT ON TABLE  library_pages_v2 IS 'Páginas físicas del documento extraídas o reconstruidas';

-- ── library_sections_v2 ─────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS library_sections_v2 (
    section_id       UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id           UUID        NOT NULL REFERENCES library_ingestion_runs_v2(run_id),
    document_id      UUID        NOT NULL,
    parent_section_id UUID       REFERENCES library_sections_v2(section_id),
    title            TEXT        NOT NULL,
    section_type     TEXT        NOT NULL DEFAULT 'chapter',
    page_start       INTEGER,
    page_end         INTEGER,
    order_index      INTEGER     NOT NULL,
    path             TEXT        NOT NULL,
    confidence       NUMERIC,
    extraction_method TEXT       NOT NULL DEFAULT 'heuristic',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sections_v2_doc_page ON library_sections_v2(document_id, page_start);
CREATE INDEX IF NOT EXISTS idx_sections_v2_doc_path  ON library_sections_v2(document_id, path);

COMMENT ON TABLE  library_sections_v2 IS 'Secciones/capítulos jerárquicos del documento';
COMMENT ON COLUMN library_sections_v2.section_type IS 'chapter | section | subsection | introduction | appendix | glossary | other';

-- ── library_concept_mentions_v2 ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS library_concept_mentions_v2 (
    concept_mention_id UUID       PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id             UUID       NOT NULL REFERENCES library_ingestion_runs_v2(run_id),
    document_id        UUID       NOT NULL,
    chunk_id           UUID,
    page_number        INTEGER,
    section_id         UUID       REFERENCES library_sections_v2(section_id),
    label              TEXT       NOT NULL,
    normalized_label   TEXT       NOT NULL,
    variants           JSONB      NOT NULL DEFAULT '[]',
    language           TEXT,
    span_start         INTEGER,
    span_end           INTEGER,
    confidence         NUMERIC,
    concept_type       TEXT       NOT NULL DEFAULT 'topic',
    extraction_method  TEXT       NOT NULL DEFAULT 'auto',
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_concept_mentions_v2_label   ON library_concept_mentions_v2(document_id, normalized_label);
CREATE INDEX IF NOT EXISTS idx_concept_mentions_v2_page    ON library_concept_mentions_v2(document_id, page_number);
CREATE INDEX IF NOT EXISTS idx_concept_mentions_v2_section ON library_concept_mentions_v2(document_id, section_id);

COMMENT ON TABLE  library_concept_mentions_v2 IS 'Menciones de conceptos por chunk/página/sección';
COMMENT ON COLUMN library_concept_mentions_v2.concept_type IS 'topic | person | place | event | object | abstract | other';

-- ── library_source_references_v2 ────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS library_source_references_v2 (
    source_ref_id    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id           UUID        NOT NULL REFERENCES library_ingestion_runs_v2(run_id),
    document_id      UUID        NOT NULL,
    chunk_id         UUID,
    page_number      INTEGER,
    section_id       UUID        REFERENCES library_sections_v2(section_id),
    reference_text   TEXT        NOT NULL,
    source_type      TEXT        NOT NULL,
    normalized_ref   TEXT,
    citation_target  TEXT,
    evidence_type    TEXT        NOT NULL DEFAULT 'source_reference',
    confidence       NUMERIC,
    extraction_method TEXT       NOT NULL DEFAULT 'auto',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_source_refs_v2_type     ON library_source_references_v2(document_id, source_type);
CREATE INDEX IF NOT EXISTS idx_source_refs_v2_page     ON library_source_references_v2(document_id, page_number);
CREATE INDEX IF NOT EXISTS idx_source_refs_v2_normref  ON library_source_references_v2(document_id, normalized_ref);

COMMENT ON TABLE  library_source_references_v2 IS 'Referencias a fuentes externas (bíblicas, rabínicas, talmúdicas)';

-- ── library_internal_relations_v2 ───────────────────────────────────────────

CREATE TABLE IF NOT EXISTS library_internal_relations_v2 (
    relation_id      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id           UUID        NOT NULL REFERENCES library_ingestion_runs_v2(run_id),
    document_id      UUID        NOT NULL,
    concept_a        TEXT        NOT NULL,
    concept_b        TEXT        NOT NULL,
    relation_type    TEXT        NOT NULL,
    evidence_type    TEXT        NOT NULL DEFAULT 'thematic_relation',
    page_start       INTEGER,
    page_end         INTEGER,
    chunk_ids        JSONB       NOT NULL DEFAULT '[]',
    snippet          TEXT,
    confidence       NUMERIC,
    extraction_method TEXT       NOT NULL DEFAULT 'auto',
    editorial_status TEXT       NOT NULL DEFAULT 'auto_extracted',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_internal_rels_v2_concepts  ON library_internal_relations_v2(document_id, concept_a, concept_b);
CREATE INDEX IF NOT EXISTS idx_internal_rels_v2_type       ON library_internal_relations_v2(document_id, relation_type);
CREATE INDEX IF NOT EXISTS idx_internal_rels_v2_page       ON library_internal_relations_v2(document_id, page_start);

COMMENT ON TABLE  library_internal_relations_v2 IS 'Relaciones conceptuales internas del documento';
COMMENT ON COLUMN library_internal_relations_v2.relation_type IS 'literal_relation | explicit_relation | thematic_relation | cooccurrence | inference | structural';
COMMENT ON COLUMN library_internal_relations_v2.editorial_status IS 'auto_extracted | reviewed | confirmed | rejected';

-- ── library_document_wiki_v2 ────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS library_document_wiki_v2 (
    document_wiki_id     UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id               UUID        NOT NULL REFERENCES library_ingestion_runs_v2(run_id),
    document_id          UUID        NOT NULL,
    overview             TEXT,
    structure_summary    TEXT,
    main_topics          JSONB       NOT NULL DEFAULT '[]',
    key_concepts         JSONB       NOT NULL DEFAULT '[]',
    source_map           JSONB       NOT NULL DEFAULT '{}',
    internal_relations_summary JSONB  NOT NULL DEFAULT '[]',
    questions_it_can_answer JSONB    NOT NULL DEFAULT '[]',
    warnings             JSONB       NOT NULL DEFAULT '[]',
    review_status        TEXT        NOT NULL DEFAULT 'auto_generated',
    generated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_wiki_v2_doc ON library_document_wiki_v2(document_id, generated_at);

COMMENT ON TABLE  library_document_wiki_v2 IS 'Resumen editorial generado por documento';
COMMENT ON COLUMN library_document_wiki_v2.review_status IS 'auto_generated | reviewed | approved';
