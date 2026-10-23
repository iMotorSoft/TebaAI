-- ─────────────────────────────────────────────────────────────────────────────
-- Parallel generation foundation (V2)
--
-- MODEL A: one logical document, many explicit generations, one active pointer.
--
--   library_logical_documents            (logical identity: scope+collection+source)
--     └── library_document_generations   (physical generation: document/run/status)
--           └── library_logical_document_active_generations (the active pointer)
--
-- Invariants enforced by the database:
--   * at most one ACTIVE generation per logical document (partial unique index);
--   * at most one active pointer row per logical document (primary key);
--   * the pointer may only reference a generation of the same logical document
--     (composite foreign key);
--   * a generation may only reference a document of the same logical document
--     (composite foreign key).
--
-- Visibility for every normal reader is derived from ONE place: the view
-- library_visible_documents. "Latest completed run" is never used to decide
-- what a reader may see.
--
-- The document-level unique index on (knowledge_scope_id, collection_id,
-- source_sha256) is replaced by the equivalent logical-level reservation, so
-- accidental duplicates stay impossible while OLD and NEW generations of the
-- same approved source can coexist.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS library_logical_documents (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_id       uuid        NOT NULL REFERENCES library_collections_legacy(id),
    knowledge_scope_id  uuid        REFERENCES knowledge_scopes(id),
    organization_id     uuid        REFERENCES organizations(id),
    workspace_id        uuid        REFERENCES workspaces(id),
    project_id          uuid        REFERENCES projects(id),
    title               text        NOT NULL,
    source_sha256       text        NOT NULL,
    source_filename     text,
    source_size_bytes   bigint,
    metadata            jsonb       NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT library_logical_documents_title_not_empty CHECK (title <> ''),
    CONSTRAINT library_logical_documents_sha256_not_empty CHECK (source_sha256 <> '')
);

-- One logical document per tenant scope + legacy collection + approved source.
CREATE UNIQUE INDEX IF NOT EXISTS uq_library_logical_documents_scope_collection_sha256
    ON library_logical_documents (knowledge_scope_id, collection_id, source_sha256)
    WHERE knowledge_scope_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_library_logical_documents_unscoped_collection_sha256
    ON library_logical_documents (collection_id, source_sha256)
    WHERE knowledge_scope_id IS NULL;

CREATE INDEX IF NOT EXISTS ix_library_logical_documents_scope
    ON library_logical_documents (knowledge_scope_id);

ALTER TABLE library_documents
    ADD COLUMN IF NOT EXISTS logical_document_id uuid
        REFERENCES library_logical_documents(id);

-- Required so a generation can be bound to (document, logical document) pairs.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_library_documents_id_logical_document'
          AND conrelid = 'library_documents'::regclass
    ) THEN
        ALTER TABLE library_documents
            ADD CONSTRAINT uq_library_documents_id_logical_document
            UNIQUE (id, logical_document_id);
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS library_document_generations (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    logical_document_id uuid        NOT NULL REFERENCES library_logical_documents(id) ON DELETE CASCADE,
    document_id         uuid        NOT NULL,
    run_id              uuid        REFERENCES library_ingestion_runs_v2(run_id),
    job_id              uuid        REFERENCES content_manager_jobs(id),
    attempt_number      integer,
    pipeline_version    text        NOT NULL,
    status              text        NOT NULL,
    source_sha256       text        NOT NULL,
    retention_hold      boolean     NOT NULL DEFAULT false,
    metadata            jsonb       NOT NULL DEFAULT '{}'::jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    activated_at        timestamptz,
    deactivated_at      timestamptz,
    CONSTRAINT library_document_generations_status_valid
        CHECK (status IN ('BUILDING', 'CANDIDATE', 'ACTIVE', 'INACTIVE', 'FAILED')),
    CONSTRAINT library_document_generations_sha256_not_empty CHECK (source_sha256 <> ''),
    CONSTRAINT library_document_generations_document_unique UNIQUE (document_id),
    CONSTRAINT library_document_generations_logical_pipeline_unique
        UNIQUE (logical_document_id, pipeline_version),
    CONSTRAINT library_document_generations_logical_id_unique
        UNIQUE (logical_document_id, id),
    CONSTRAINT library_document_generations_document_logical_fkey
        FOREIGN KEY (document_id, logical_document_id)
        REFERENCES library_documents (id, logical_document_id)
);

-- Exactly one ACTIVE generation per logical document.
CREATE UNIQUE INDEX IF NOT EXISTS uq_library_document_generations_single_active
    ON library_document_generations (logical_document_id)
    WHERE status = 'ACTIVE';

CREATE INDEX IF NOT EXISTS ix_library_document_generations_logical
    ON library_document_generations (logical_document_id, status);

CREATE TABLE IF NOT EXISTS library_logical_document_active_generations (
    logical_document_id     uuid        PRIMARY KEY
        REFERENCES library_logical_documents(id) ON DELETE CASCADE,
    generation_id           uuid        NOT NULL,
    expected_generation_id  uuid,
    operation               text        NOT NULL DEFAULT 'BACKFILL',
    activated_at            timestamptz NOT NULL DEFAULT now(),
    activated_by            uuid,
    metadata                jsonb       NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT library_logical_document_active_generations_operation_valid
        CHECK (operation IN ('BACKFILL', 'CUTOVER', 'ROLLBACK', 'REGISTER')),
    CONSTRAINT library_logical_document_active_generations_generation_fkey
        FOREIGN KEY (logical_document_id, generation_id)
        REFERENCES library_document_generations (logical_document_id, id)
);

CREATE TABLE IF NOT EXISTS library_generation_activation_audit (
    id                     uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    logical_document_id    uuid        NOT NULL,
    from_generation_id     uuid,
    to_generation_id       uuid,
    expected_generation_id uuid,
    operation              text        NOT NULL,
    result                 text        NOT NULL,
    reason                 text,
    actor_id               uuid,
    created_at             timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT library_generation_activation_audit_operation_valid
        CHECK (operation IN ('CUTOVER', 'ROLLBACK', 'BACKFILL', 'REGISTER')),
    CONSTRAINT library_generation_activation_audit_result_valid
        CHECK (result IN ('APPLIED', 'REJECTED', 'IDEMPOTENT'))
);

CREATE INDEX IF NOT EXISTS ix_library_generation_activation_audit_logical
    ON library_generation_activation_audit (logical_document_id, created_at DESC);

-- ── Deterministic backfill ───────────────────────────────────────────────────
-- Logical identity: one row per (scope, collection, source_sha256).
INSERT INTO library_logical_documents (
    id, collection_id, knowledge_scope_id, organization_id, workspace_id, project_id,
    title, source_sha256, source_filename, source_size_bytes, metadata, created_at, updated_at
)
SELECT
    md5('tebaai.logical_document:' || COALESCE(d.knowledge_scope_id::text, '') || '|'
        || d.collection_id::text || '|' || d.source_sha256)::uuid,
    d.collection_id, d.knowledge_scope_id, d.organization_id, d.workspace_id, d.project_id,
    d.title, d.source_sha256, d.source_filename, d.source_size_bytes,
    jsonb_build_object('backfilled', true, 'backfill_source', 'migration-043'),
    d.created_at, d.updated_at
FROM library_documents d
WHERE d.logical_document_id IS NULL
ON CONFLICT DO NOTHING;

UPDATE library_documents d
SET logical_document_id = ld.id
FROM library_logical_documents ld
WHERE d.logical_document_id IS NULL
  AND ld.collection_id = d.collection_id
  AND ld.source_sha256 = d.source_sha256
  AND ld.knowledge_scope_id IS NOT DISTINCT FROM d.knowledge_scope_id;

-- Generation identity: one generation per existing document, carrying the
-- document's own current content. The run is attached only when it is
-- unambiguous (exactly one completed run); otherwise the generation is created
-- without a run and the ambiguity is recorded, never guessed.
INSERT INTO library_document_generations (
    id, logical_document_id, document_id, run_id, pipeline_version, status,
    source_sha256, retention_hold, metadata, created_at, activated_at
)
SELECT
    md5('tebaai.generation:' || d.id::text)::uuid,
    d.logical_document_id,
    d.id,
    CASE WHEN run_stats.completed_runs = 1 THEN run_stats.only_run_id ELSE NULL END,
    COALESCE(run_stats.only_pipeline, 'legacy_unknown'),
    CASE d.status
        WHEN 'ready' THEN 'ACTIVE'
        WHEN 'test_candidate' THEN 'CANDIDATE'
        WHEN 'archived' THEN 'INACTIVE'
        WHEN 'error' THEN 'FAILED'
        WHEN 'ingestion_failed' THEN 'FAILED'
        ELSE 'BUILDING'
    END,
    d.source_sha256,
    true,
    jsonb_build_object(
        'backfilled', true,
        'document_status', d.status,
        'ambiguous_run', run_stats.completed_runs <> 1,
        'completed_runs', run_stats.completed_runs
    ),
    d.created_at,
    CASE WHEN d.status = 'ready' THEN d.updated_at ELSE NULL END
FROM library_documents d
JOIN LATERAL (
    SELECT
        count(*) FILTER (WHERE r.status = 'completed') AS completed_runs,
        (array_agg(r.run_id) FILTER (WHERE r.status = 'completed'))[1] AS only_run_id,
        (array_agg(r.pipeline_version) FILTER (WHERE r.status = 'completed'))[1] AS only_pipeline
    FROM library_ingestion_runs_v2 r
    WHERE r.document_id = d.id
) run_stats ON true
WHERE d.logical_document_id IS NOT NULL
ON CONFLICT (document_id) DO NOTHING;

-- Active pointer: exactly one pointer per logical document that owns an ACTIVE
-- generation. A logical document without an ACTIVE generation has no pointer and
-- stays invisible to normal readers (fail closed).
INSERT INTO library_logical_document_active_generations (
    logical_document_id, generation_id, expected_generation_id, operation, metadata
)
SELECT g.logical_document_id, g.id, g.id, 'BACKFILL',
       jsonb_build_object('backfill_source', 'migration-043')
FROM library_document_generations g
WHERE g.status = 'ACTIVE'
ON CONFLICT (logical_document_id) DO NOTHING;

INSERT INTO library_generation_activation_audit (
    logical_document_id, from_generation_id, to_generation_id, expected_generation_id,
    operation, result, reason
)
SELECT p.logical_document_id, NULL, p.generation_id, p.generation_id,
       'BACKFILL', 'APPLIED', 'migration-043 deterministic backfill'
FROM library_logical_document_active_generations p
WHERE NOT EXISTS (
    SELECT 1 FROM library_generation_activation_audit a
    WHERE a.logical_document_id = p.logical_document_id AND a.operation = 'BACKFILL'
);

-- The active pointer now carries the uniqueness guarantee that the document
-- level index used to provide.
DROP INDEX IF EXISTS uq_library_documents_scope_collection_sha256;
DROP INDEX IF EXISTS uq_library_documents_unscoped_collection_sha256;

-- ── One authoritative visibility surface ─────────────────────────────────────
-- Every normal reader joins this view. A document is visible only when it is
-- the physical carrier of the ACTIVE generation selected by the active pointer.
CREATE OR REPLACE VIEW library_visible_documents AS
SELECT d.*
FROM library_documents d
JOIN library_document_generations g
  ON g.document_id = d.id AND g.status = 'ACTIVE'
JOIN library_logical_document_active_generations p
  ON p.logical_document_id = g.logical_document_id AND p.generation_id = g.id
UNION ALL
-- Compatibility for documents that were never registered as a generation.
-- They stay visible only while they are explicitly published and ready.
SELECT d.*
FROM library_documents d
WHERE d.logical_document_id IS NULL AND d.status = 'ready';
