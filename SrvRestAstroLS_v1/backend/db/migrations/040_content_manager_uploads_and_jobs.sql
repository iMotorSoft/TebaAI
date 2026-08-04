-- 040_content_manager_uploads_and_jobs.sql
-- Content Manager V1: controlled upload and ingestion job tracking.

CREATE TABLE IF NOT EXISTS content_manager_uploads (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid,
    workspace_id    uuid,
    project_id      uuid,
    actor_user_id   uuid,
    filename        text        NOT NULL,
    original_filename text      NOT NULL,
    size_bytes      bigint      NOT NULL,
    sha256          text        NOT NULL,
    mime_type       text        NOT NULL DEFAULT 'application/pdf',
    page_count      int,
    validation_status text      NOT NULL DEFAULT 'pending',
    validation_errors jsonb     DEFAULT '[]',
    duplicate_status text       NOT NULL DEFAULT 'new_document',
    existing_document_id uuid,
    temp_path       text,
    metadata        jsonb       DEFAULT '{}',
    warnings        jsonb       DEFAULT '[]',
    limits          jsonb       DEFAULT '{}',
    created_at      timestamptz NOT NULL DEFAULT now(),
    expires_at      timestamptz
);

CREATE TABLE IF NOT EXISTS content_manager_jobs (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    upload_id           uuid        NOT NULL REFERENCES content_manager_uploads(id),
    organization_id     uuid,
    workspace_id        uuid,
    project_id          uuid,
    actor_user_id       uuid,
    document_id         uuid,
    title               text        NOT NULL,
    language            text        NOT NULL DEFAULT 'auto',
    work_family         text,
    administrative_notes text,
    ingestion_profile   text        NOT NULL DEFAULT 'auto',
    requested_status    text        NOT NULL DEFAULT 'test_candidate',
    status              text        NOT NULL DEFAULT 'uploaded',
    current_stage       text,
    progress_percent    real        DEFAULT 0.0,
    stage_states        jsonb       DEFAULT '{}',
    error_code          text,
    error_message       text,
    warning_codes       jsonb       DEFAULT '[]',
    attempt_number      int         NOT NULL DEFAULT 1,
    diagnostic          jsonb       DEFAULT '{}',
    stage_timings       jsonb       DEFAULT '{}',
    technical_details   jsonb       DEFAULT '{}',
    created_at          timestamptz NOT NULL DEFAULT now(),
    started_at          timestamptz,
    updated_at          timestamptz NOT NULL DEFAULT now(),
    finished_at         timestamptz,
    expires_at          timestamptz
);

CREATE INDEX IF NOT EXISTS idx_cm_uploads_sha256 ON content_manager_uploads(sha256);
CREATE INDEX IF NOT EXISTS idx_cm_uploads_org ON content_manager_uploads(organization_id);
CREATE INDEX IF NOT EXISTS idx_cm_jobs_upload ON content_manager_jobs(upload_id);
CREATE INDEX IF NOT EXISTS idx_cm_jobs_status ON content_manager_jobs(status);
CREATE INDEX IF NOT EXISTS idx_cm_jobs_org ON content_manager_jobs(organization_id);
CREATE INDEX IF NOT EXISTS idx_cm_jobs_document ON content_manager_jobs(document_id);
