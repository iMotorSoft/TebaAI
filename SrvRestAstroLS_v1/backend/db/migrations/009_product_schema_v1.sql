-- 009_product_schema_v1.sql
-- PG18 Product Schema v1: multi-tenancy, knowledge_scopes, version tracking, audit.
-- Adds organizations, workspaces, projects, knowledge_scopes, validation_runs,
-- promotion_events. Updates library tables with tenant FKs and version fields.

-- ============================================================
-- 1. ENUMS
-- ============================================================

DO $$ BEGIN
  CREATE TYPE user_status AS ENUM ('active', 'invited', 'disabled', 'deleted');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE member_role AS ENUM ('owner', 'admin', 'member', 'viewer', 'service');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE project_type AS ENUM ('bibliographic_library', 'assistant', 'knowledge_base', 'research');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE scope_type AS ENUM ('bibliographic_corpus', 'product_catalog', 'support_manuals', 'sales_knowledge', 'mixed');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE scope_status AS ENUM ('draft', 'active', 'archived', 'error');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE text_role AS ENUM ('canonical', 'raw_extracted', 'normalized_auxiliary', 'rejected', 'facsimile_only_note');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE page_mapping_status AS ENUM ('mapped', 'partial', 'unmapped', 'not_applicable', 'error');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE vector_status AS ENUM ('pending', 'generated', 'indexed_test', 'validated_test', 'indexed_production', 'stale', 'error');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE index_target AS ENUM ('test', 'production');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE index_run_type AS ENUM ('embedding_generation', 'milvus_test_index', 'milvus_production_index', 'round_trip_validation', 'golden_queries');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE validation_type AS ENUM ('source_quality', 'sha256_round_trip', 'page_mapping', 'chunk_integrity', 'fts_smoke', 'embedding_validation', 'milvus_round_trip', 'golden_queries', 'manual_review', 'promotion_dry_run');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE promotion_decision AS ENUM ('dry_run', 'owner_approved', 'owner_rejected', 'auto_blocked', 'rollback');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE canonical_text_role AS ENUM ('primary', 'candidate', 'auxiliary', 'none');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ============================================================
-- 2. ORGANIZATIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS organizations (
    id                  UUID        NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_code   TEXT        NOT NULL,
    name                TEXT        NOT NULL,
    status              TEXT        NOT NULL DEFAULT 'active',
    metadata            JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_organizations_code UNIQUE (organization_code),
    CONSTRAINT chk_organizations_code_not_empty CHECK (organization_code <> ''),
    CONSTRAINT chk_organizations_name_not_empty CHECK (name <> '')
);

-- ============================================================
-- 3. WORKSPACES
-- ============================================================

CREATE TABLE IF NOT EXISTS workspaces (
    id                  UUID        NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID        NOT NULL REFERENCES organizations(id),
    workspace_code      TEXT        NOT NULL,
    name                TEXT        NOT NULL,
    status              TEXT        NOT NULL DEFAULT 'active',
    metadata            JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_workspaces_org_code UNIQUE (organization_id, workspace_code),
    CONSTRAINT chk_workspaces_code_not_empty CHECK (workspace_code <> ''),
    CONSTRAINT chk_workspaces_name_not_empty CHECK (name <> '')
);

-- ============================================================
-- 4. PROJECTS
-- ============================================================

CREATE TABLE IF NOT EXISTS projects (
    id                  UUID            NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID            NOT NULL REFERENCES organizations(id),
    workspace_id        UUID            NOT NULL REFERENCES workspaces(id),
    project_code        TEXT            NOT NULL,
    name                TEXT            NOT NULL,
    project_type        project_type    NOT NULL DEFAULT 'knowledge_base',
    status              TEXT            NOT NULL DEFAULT 'active',
    metadata            JSONB           NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    CONSTRAINT uq_projects_ws_code UNIQUE (workspace_id, project_code),
    CONSTRAINT chk_projects_code_not_empty CHECK (project_code <> ''),
    CONSTRAINT chk_projects_name_not_empty CHECK (name <> '')
);

-- ============================================================
-- 5. KNOWLEDGE SCOPES
-- ============================================================

CREATE TABLE IF NOT EXISTS knowledge_scopes (
    id                      UUID            NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id         UUID            NOT NULL REFERENCES organizations(id),
    workspace_id            UUID            NOT NULL REFERENCES workspaces(id),
    project_id              UUID            NOT NULL REFERENCES projects(id),
    knowledge_scope_code    TEXT            NOT NULL,
    name                    TEXT            NOT NULL,
    description             TEXT,
    scope_type              scope_type      NOT NULL DEFAULT 'bibliographic_corpus',
    language_policy         TEXT,
    status                  scope_status    NOT NULL DEFAULT 'draft',
    metadata                JSONB           NOT NULL DEFAULT '{}'::jsonb,
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT now(),
    CONSTRAINT uq_knowledge_scopes_project_code UNIQUE (project_id, knowledge_scope_code),
    CONSTRAINT chk_knowledge_scopes_code_not_empty CHECK (knowledge_scope_code <> ''),
    CONSTRAINT chk_knowledge_scopes_name_not_empty CHECK (name <> '')
);

-- ============================================================
-- 6. UPDATE USERS — add normalized_email, status
-- ============================================================

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS email_normalized TEXT NOT NULL DEFAULT '';
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS user_status TEXT NOT NULL DEFAULT 'active';
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS display_name TEXT;

UPDATE users SET email_normalized = lower(email) WHERE email_normalized = '';
UPDATE users SET display_name = COALESCE(username, email) WHERE display_name IS NULL;

ALTER TABLE users
    ADD CONSTRAINT chk_users_status_valid CHECK (user_status IN ('active', 'invited', 'disabled', 'deleted'));

CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_normalized ON users (email_normalized);

-- ============================================================
-- 7. AUTH IDENTITIES (extract from users table)
-- ============================================================

CREATE TABLE IF NOT EXISTS auth_identities (
    id                  UUID        NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID        NOT NULL REFERENCES users(id),
    provider            TEXT        NOT NULL,
    provider_subject    TEXT        NOT NULL,
    email               TEXT,
    password_hash       TEXT,
    status              TEXT        NOT NULL DEFAULT 'active',
    metadata            JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_auth_identities_provider_subject UNIQUE (provider, provider_subject),
    CONSTRAINT chk_auth_identities_provider_valid CHECK (provider IN ('local', 'google', 'github', 'magic_link', 'service'))
);

-- Migrate existing user passwords to auth_identities
INSERT INTO auth_identities (user_id, provider, provider_subject, email, password_hash, status)
SELECT id, 'local', id::text, email, password_hash, 'active'
FROM users u
WHERE u.password_hash IS NOT NULL AND u.password_hash <> ''
ON CONFLICT (provider, provider_subject) DO NOTHING;

-- ============================================================
-- 8. AUTH SESSIONS — add ip_hash, user_agent_hash
-- ============================================================

ALTER TABLE auth_sessions
    ADD COLUMN IF NOT EXISTS ip_hash TEXT;
ALTER TABLE auth_sessions
    ADD COLUMN IF NOT EXISTS user_agent_hash TEXT;

-- ============================================================
-- 9. ORGANIZATION / WORKSPACE / PROJECT MEMBERS
-- ============================================================

CREATE TABLE IF NOT EXISTS organization_members (
    id                  UUID            NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID            NOT NULL REFERENCES organizations(id),
    user_id             UUID            NOT NULL REFERENCES users(id),
    role                member_role     NOT NULL DEFAULT 'member',
    status              TEXT            NOT NULL DEFAULT 'active',
    metadata            JSONB           NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    CONSTRAINT uq_org_members UNIQUE (organization_id, user_id)
);

CREATE TABLE IF NOT EXISTS workspace_members (
    id                  UUID            NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        UUID            NOT NULL REFERENCES workspaces(id),
    user_id             UUID            NOT NULL REFERENCES users(id),
    role                member_role     NOT NULL DEFAULT 'member',
    status              TEXT            NOT NULL DEFAULT 'active',
    metadata            JSONB           NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    CONSTRAINT uq_workspace_members UNIQUE (workspace_id, user_id)
);

CREATE TABLE IF NOT EXISTS project_members (
    id                  UUID            NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID            NOT NULL REFERENCES projects(id),
    user_id             UUID            NOT NULL REFERENCES users(id),
    role                member_role     NOT NULL DEFAULT 'member',
    status              TEXT            NOT NULL DEFAULT 'active',
    metadata            JSONB           NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    CONSTRAINT uq_project_members UNIQUE (project_id, user_id)
);

-- ============================================================
-- 10. UPDATE LIBRARY_DOCUMENTS — add tenant FKs, version fields
-- ============================================================

ALTER TABLE library_documents
    ADD COLUMN IF NOT EXISTS organization_id     UUID REFERENCES organizations(id),
    ADD COLUMN IF NOT EXISTS workspace_id        UUID REFERENCES workspaces(id),
    ADD COLUMN IF NOT EXISTS project_id          UUID REFERENCES projects(id),
    ADD COLUMN IF NOT EXISTS knowledge_scope_id  UUID REFERENCES knowledge_scopes(id),
    ADD COLUMN IF NOT EXISTS document_code       TEXT,
    ADD COLUMN IF NOT EXISTS content_sha256      TEXT,
    ADD COLUMN IF NOT EXISTS canonical_text_role canonical_text_role NOT NULL DEFAULT 'candidate',
    ADD COLUMN IF NOT EXISTS subtitle            TEXT,
    ADD COLUMN IF NOT EXISTS editor              TEXT,
    ADD COLUMN IF NOT EXISTS translator          TEXT,
    ADD COLUMN IF NOT EXISTS edition             TEXT,
    ADD COLUMN IF NOT EXISTS publication_year    INTEGER,
    ADD COLUMN IF NOT EXISTS archived_at         TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS chunk_set_version   INTEGER;

CREATE INDEX IF NOT EXISTS ix_library_documents_org ON library_documents (organization_id);
CREATE INDEX IF NOT EXISTS ix_library_documents_ws ON library_documents (workspace_id);
CREATE INDEX IF NOT EXISTS ix_library_documents_project ON library_documents (project_id);
CREATE INDEX IF NOT EXISTS ix_library_documents_scope ON library_documents (knowledge_scope_id);
CREATE INDEX IF NOT EXISTS ix_library_documents_doc_code ON library_documents (knowledge_scope_id, document_code)
    WHERE document_code IS NOT NULL;

-- ============================================================
-- 11. UPDATE LIBRARY_DOCUMENT_TEXTS — add text_role
-- ============================================================

ALTER TABLE library_document_texts
    ADD COLUMN IF NOT EXISTS text_role text_role NOT NULL DEFAULT 'canonical',
    ADD COLUMN IF NOT EXISTS page_markers_enabled BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS page_count INTEGER,
    ADD COLUMN IF NOT EXISTS knowledge_scope_id UUID REFERENCES knowledge_scopes(id);

CREATE INDEX IF NOT EXISTS ix_library_document_texts_role ON library_document_texts (text_role);

-- ============================================================
-- 12. UPDATE LIBRARY_DOCUMENT_CHUNKS — add version tracking
-- ============================================================

ALTER TABLE library_document_chunks
    ADD COLUMN IF NOT EXISTS chunk_set_version     INTEGER,
    ADD COLUMN IF NOT EXISTS knowledge_scope_id    UUID REFERENCES knowledge_scopes(id),
    ADD COLUMN IF NOT EXISTS organization_id       UUID REFERENCES organizations(id),
    ADD COLUMN IF NOT EXISTS workspace_id          UUID REFERENCES workspaces(id),
    ADD COLUMN IF NOT EXISTS project_id            UUID REFERENCES projects(id),
    ADD COLUMN IF NOT EXISTS page_mapping_status   page_mapping_status,
    ADD COLUMN IF NOT EXISTS section_title         TEXT,
    ADD COLUMN IF NOT EXISTS node_path             TEXT,
    ADD COLUMN IF NOT EXISTS chunking_strategy     TEXT,
    ADD COLUMN IF NOT EXISTS chunking_version      TEXT,
    ADD COLUMN IF NOT EXISTS token_estimate        INTEGER,
    ADD COLUMN IF NOT EXISTS is_empty              BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE library_document_chunks
    ADD CONSTRAINT chk_chunk_set_version_positive CHECK (chunk_set_version IS NULL OR chunk_set_version >= 0);

-- Update existing mapped chunks page_mapping_status
UPDATE library_document_chunks
SET page_mapping_status = CASE
    WHEN page_start IS NOT NULL AND page_end IS NOT NULL THEN 'mapped'::page_mapping_status
    ELSE NULL
END
WHERE page_mapping_status IS NULL;

-- ============================================================
-- 13. UPDATE LIBRARY_CHUNK_EMBEDDINGS — add version tracking
-- ============================================================

ALTER TABLE library_chunk_embeddings
    ADD COLUMN IF NOT EXISTS embedding_model_alias    TEXT,
    ADD COLUMN IF NOT EXISTS embedding_version        INTEGER,
    ADD COLUMN IF NOT EXISTS chunk_set_version        INTEGER,
    ADD COLUMN IF NOT EXISTS knowledge_scope_id       UUID REFERENCES knowledge_scopes(id),
    ADD COLUMN IF NOT EXISTS organization_id          UUID REFERENCES organizations(id),
    ADD COLUMN IF NOT EXISTS workspace_id             UUID REFERENCES workspaces(id),
    ADD COLUMN IF NOT EXISTS project_id               UUID REFERENCES projects(id),
    ADD COLUMN IF NOT EXISTS vector_status            vector_status NOT NULL DEFAULT 'generated';

-- Rename status to vector_status_alias (we keep both for transition)
UPDATE library_chunk_embeddings
SET embedding_model_alias = embedding_model
WHERE embedding_model_alias IS NULL;

-- Add unique constraint for chunk + model + version
DROP INDEX IF EXISTS uq_library_chunk_embeddings_chunk_provider;
CREATE UNIQUE INDEX IF NOT EXISTS uq_library_chunk_embeddings_chunk_model_version
    ON library_chunk_embeddings (chunk_id, embedding_model_alias, COALESCE(chunk_set_version, 0));

-- ============================================================
-- 14. UPDATE LIBRARY_EMBEDDING_RUNS — add tenant FKs
-- ============================================================

ALTER TABLE library_embedding_runs
    ADD COLUMN IF NOT EXISTS organization_id      UUID REFERENCES organizations(id),
    ADD COLUMN IF NOT EXISTS workspace_id         UUID REFERENCES workspaces(id),
    ADD COLUMN IF NOT EXISTS project_id           UUID REFERENCES projects(id),
    ADD COLUMN IF NOT EXISTS knowledge_scope_id   UUID REFERENCES knowledge_scopes(id),
    ADD COLUMN IF NOT EXISTS target               index_target,
    ADD COLUMN IF NOT EXISTS run_type             index_run_type,
    ADD COLUMN IF NOT EXISTS chunk_set_version    INTEGER,
    ADD COLUMN IF NOT EXISTS document_ids         JSONB;

CREATE INDEX IF NOT EXISTS ix_embedding_runs_scope_target ON library_embedding_runs (knowledge_scope_id, target, status);

-- ============================================================
-- 15. VALIDATION RUNS (new)
-- ============================================================

CREATE TABLE IF NOT EXISTS library_validation_runs (
    id                  UUID                NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID                REFERENCES organizations(id),
    workspace_id        UUID                REFERENCES workspaces(id),
    project_id          UUID                REFERENCES projects(id),
    knowledge_scope_id  UUID                REFERENCES knowledge_scopes(id),
    document_id         UUID                REFERENCES library_documents(id),
    validation_type     validation_type     NOT NULL,
    status              TEXT                NOT NULL DEFAULT 'pending',
    summary             JSONB               NOT NULL DEFAULT '{}'::jsonb,
    errors              JSONB               NOT NULL DEFAULT '[]'::jsonb,
    started_at          TIMESTAMPTZ         NOT NULL DEFAULT now(),
    finished_at         TIMESTAMPTZ,
    metadata            JSONB               NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ         NOT NULL DEFAULT now(),
    CONSTRAINT chk_validation_status CHECK (status IN ('pending', 'running', 'completed', 'failed', 'skipped'))
);

CREATE INDEX IF NOT EXISTS ix_validation_runs_scope ON library_validation_runs (knowledge_scope_id);
CREATE INDEX IF NOT EXISTS ix_validation_runs_doc ON library_validation_runs (document_id);
CREATE INDEX IF NOT EXISTS ix_validation_runs_type ON library_validation_runs (validation_type, status);

-- ============================================================
-- 16. PROMOTION EVENTS (new)
-- ============================================================

CREATE TABLE IF NOT EXISTS library_promotion_events (
    id                  UUID                NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID                REFERENCES organizations(id),
    workspace_id        UUID                REFERENCES workspaces(id),
    project_id          UUID                REFERENCES projects(id),
    knowledge_scope_id  UUID                REFERENCES knowledge_scopes(id),
    document_id         UUID                NOT NULL REFERENCES library_documents(id),
    from_status         TEXT                NOT NULL,
    to_status           TEXT                NOT NULL,
    decision            promotion_decision  NOT NULL,
    decided_by          UUID                REFERENCES users(id),
    decided_at          TIMESTAMPTZ         NOT NULL DEFAULT now(),
    reason              TEXT,
    metadata            JSONB               NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ         NOT NULL DEFAULT now(),
    CONSTRAINT chk_promotion_from_status CHECK (from_status IN ('draft', 'test_candidate', 'ready', 'archived', 'error')),
    CONSTRAINT chk_promotion_to_status CHECK (to_status IN ('draft', 'test_candidate', 'ready', 'archived', 'error'))
);

CREATE INDEX IF NOT EXISTS ix_promotion_events_doc ON library_promotion_events (document_id);
CREATE INDEX IF NOT EXISTS ix_promotion_events_scope ON library_promotion_events (knowledge_scope_id);
CREATE INDEX IF NOT EXISTS ix_promotion_events_decision ON library_promotion_events (decision);

-- ============================================================
-- 17. ADD UNIQUE INDEX on library_document_chunks
-- ============================================================

ALTER TABLE library_document_chunks
    DROP CONSTRAINT IF EXISTS uq_library_document_chunks_text_index;
CREATE UNIQUE INDEX IF NOT EXISTS uq_library_chunks_doc_chunk
    ON library_document_chunks (document_id, chunk_index);
