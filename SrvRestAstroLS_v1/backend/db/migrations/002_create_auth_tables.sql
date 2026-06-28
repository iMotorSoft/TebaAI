-- 002_create_auth_tables.sql
-- TebaAI auth module: users and refresh-token sessions.
--
-- Prerequisite: schema_migrations table exists (created by the runner).
-- Guard: application must verify current_database() == 'tebaai' before running.

-- ── Users ────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS users (
    id                  uuid        NOT NULL PRIMARY KEY,
    email               text        NOT NULL,
    username            text,
    password_hash       text        NOT NULL,
    role                text        NOT NULL DEFAULT 'viewer',
    is_active           boolean     NOT NULL DEFAULT TRUE,
    last_login_at       timestamptz,
    password_changed_at timestamptz NOT NULL DEFAULT now(),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT users_email_not_empty CHECK (email <> ''),
    CONSTRAINT users_role_valid CHECK (role IN ('admin', 'editor', 'viewer'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_lower ON users (lower(email));
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_username_lower ON users (lower(username)) WHERE username IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_users_role ON users (role);
CREATE INDEX IF NOT EXISTS ix_users_is_active ON users (is_active);

-- ── Auth sessions (refresh-token store) ──────────────────────────────────────

CREATE TABLE IF NOT EXISTS auth_sessions (
    id                    uuid        NOT NULL PRIMARY KEY,
    user_id               uuid        NOT NULL REFERENCES users(id),
    refresh_token_hash    text        NOT NULL,
    token_family_id       uuid        NOT NULL,
    expires_at            timestamptz NOT NULL,
    revoked_at            timestamptz,
    replaced_by_session_id uuid       REFERENCES auth_sessions(id),
    created_at            timestamptz NOT NULL DEFAULT now(),
    last_used_at          timestamptz,
    user_agent            text,
    ip_address            text
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_auth_sessions_refresh_hash ON auth_sessions (refresh_token_hash);
CREATE INDEX IF NOT EXISTS ix_auth_sessions_user_id ON auth_sessions (user_id);
CREATE INDEX IF NOT EXISTS ix_auth_sessions_token_family ON auth_sessions (token_family_id);
CREATE INDEX IF NOT EXISTS ix_auth_sessions_expires_at ON auth_sessions (expires_at);
CREATE INDEX IF NOT EXISTS ix_auth_sessions_revoked_at ON auth_sessions (revoked_at);
