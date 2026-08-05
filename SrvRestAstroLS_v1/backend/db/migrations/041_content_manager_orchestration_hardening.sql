-- 041_content_manager_orchestration_hardening.sql
-- Durable claims, attempts, transition audit, manifests and atomic idempotency.

ALTER TABLE content_manager_uploads
    ADD COLUMN IF NOT EXISTS knowledge_scope_id uuid,
    ADD COLUMN IF NOT EXISTS cleanup_status text NOT NULL DEFAULT 'not_required',
    ADD COLUMN IF NOT EXISTS cleaned_at timestamptz;

ALTER TABLE content_manager_jobs
    ADD COLUMN IF NOT EXISTS knowledge_scope_id uuid,
    ADD COLUMN IF NOT EXISTS pipeline_version text NOT NULL DEFAULT 'content_page_first_v1',
    ADD COLUMN IF NOT EXISTS document_schema_version text NOT NULL DEFAULT 'page_first_v2',
    ADD COLUMN IF NOT EXISTS embedding_model text NOT NULL DEFAULT 'openai_text_embedding_3_small',
    ADD COLUMN IF NOT EXISTS collection_code text,
    ADD COLUMN IF NOT EXISTS idempotency_key text,
    ADD COLUMN IF NOT EXISTS claimed_by text,
    ADD COLUMN IF NOT EXISTS claimed_at timestamptz,
    ADD COLUMN IF NOT EXISTS lease_expires_at timestamptz,
    ADD COLUMN IF NOT EXISTS heartbeat_at timestamptz,
    ADD COLUMN IF NOT EXISTS recovery_status text,
    ADD COLUMN IF NOT EXISTS cleanup_status text NOT NULL DEFAULT 'not_required';

UPDATE content_manager_jobs j
SET idempotency_key = md5(
        concat_ws(':', COALESCE(j.organization_id::text, 'legacy'), u.sha256,
                  j.pipeline_version, j.ingestion_profile))
FROM content_manager_uploads u
WHERE u.id = j.upload_id AND j.idempotency_key IS NULL;

ALTER TABLE content_manager_jobs ALTER COLUMN idempotency_key SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_cm_jobs_active_idempotency
    ON content_manager_jobs(idempotency_key)
    WHERE status NOT IN ('failed', 'cancelled', 'validation_failed');
CREATE INDEX IF NOT EXISTS idx_cm_jobs_claimable
    ON content_manager_jobs(status, lease_expires_at, created_at);

DO $$ BEGIN
    ALTER TABLE content_manager_uploads
        ADD CONSTRAINT fk_cm_upload_org FOREIGN KEY (organization_id) REFERENCES organizations(id) NOT VALID;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE content_manager_uploads
        ADD CONSTRAINT fk_cm_upload_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id) NOT VALID;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE content_manager_uploads
        ADD CONSTRAINT fk_cm_upload_project FOREIGN KEY (project_id) REFERENCES projects(id) NOT VALID;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE content_manager_uploads
        ADD CONSTRAINT fk_cm_upload_scope FOREIGN KEY (knowledge_scope_id) REFERENCES knowledge_scopes(id) NOT VALID;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE content_manager_uploads
        ADD CONSTRAINT fk_cm_upload_actor FOREIGN KEY (actor_user_id) REFERENCES users(id) NOT VALID;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE content_manager_jobs
        ADD CONSTRAINT fk_cm_job_scope FOREIGN KEY (knowledge_scope_id) REFERENCES knowledge_scopes(id) NOT VALID;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE content_manager_jobs
        ADD CONSTRAINT chk_cm_requested_test_candidate CHECK (requested_status = 'test_candidate');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE content_manager_jobs
        ADD CONSTRAINT chk_cm_cleanup_status CHECK (cleanup_status IN
            ('not_required','pending','running','completed','completed_with_warnings','failed'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- A failed Content Manager attempt is distinct from a legacy generic error.
ALTER TABLE library_documents DROP CONSTRAINT IF EXISTS library_documents_status_valid;
ALTER TABLE library_documents ADD CONSTRAINT library_documents_status_valid
    CHECK (status IN ('draft','ready','test_candidate','archived','error','ingestion_failed'));

CREATE TABLE IF NOT EXISTS content_manager_job_attempts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id uuid NOT NULL REFERENCES content_manager_jobs(id),
    attempt_number integer NOT NULL CHECK (attempt_number > 0),
    previous_attempt_id uuid REFERENCES content_manager_job_attempts(id),
    worker_id text,
    status text NOT NULL DEFAULT 'pending',
    started_at timestamptz,
    finished_at timestamptz,
    cleanup_status text NOT NULL DEFAULT 'not_required',
    recovery_action text,
    failure_stage text,
    error_code text,
    error_detail text,
    UNIQUE(job_id, attempt_number)
);

CREATE TABLE IF NOT EXISTS content_manager_job_transitions (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_id uuid NOT NULL REFERENCES content_manager_jobs(id),
    attempt_number integer NOT NULL,
    from_status text NOT NULL,
    to_status text NOT NULL,
    stage text NOT NULL,
    actor_id text NOT NULL,
    reason text NOT NULL,
    occurred_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cm_transitions_job ON content_manager_job_transitions(job_id, occurred_at);

CREATE TABLE IF NOT EXISTS content_manager_ingestion_manifests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id uuid NOT NULL REFERENCES content_manager_jobs(id),
    attempt_number integer NOT NULL,
    document_id uuid REFERENCES library_documents(id) ON DELETE SET NULL,
    ingestion_run_id uuid,
    temporary_file_id uuid,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    cleanup_status text NOT NULL DEFAULT 'not_required',
    reconciliation jsonb NOT NULL DEFAULT '{}',
    UNIQUE(job_id, attempt_number)
);

CREATE TABLE IF NOT EXISTS content_manager_manifest_resources (
    manifest_id uuid NOT NULL REFERENCES content_manager_ingestion_manifests(id) ON DELETE CASCADE,
    resource_type text NOT NULL CHECK (resource_type IN
        ('document','document_text','ingestion_run','embedding_run','page','chunk','embedding','vector','temporary_file')),
    resource_id text NOT NULL,
    was_preexisting boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    cleaned_at timestamptz,
    cleanup_error text,
    PRIMARY KEY(manifest_id, resource_type, resource_id)
);
CREATE INDEX IF NOT EXISTS idx_cm_manifest_resources_type
    ON content_manager_manifest_resources(manifest_id, resource_type);

CREATE TABLE IF NOT EXISTS content_manager_cleanup_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    manifest_id uuid NOT NULL REFERENCES content_manager_ingestion_manifests(id) ON DELETE CASCADE,
    resource_type text NOT NULL,
    resource_id text NOT NULL,
    action text NOT NULL,
    result text NOT NULL CHECK (result IN ('deleted','already_absent','not_owned_by_attempt','failed')),
    error_detail text,
    occurred_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cm_cleanup_events_manifest
    ON content_manager_cleanup_events(manifest_id, occurred_at);
