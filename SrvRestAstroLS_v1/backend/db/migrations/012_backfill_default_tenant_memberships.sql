-- 012_backfill_default_tenant_memberships.sql
-- Backfill the existing TebaAI bootstrap users into the complete active tenant chain.

UPDATE projects p
SET metadata = p.metadata || '{"default_user_context": true}'::jsonb,
    updated_at = now()
FROM workspaces w
JOIN organizations o ON o.id = w.organization_id
WHERE p.workspace_id = w.id
  AND o.organization_code = 'tebaai'
  AND w.workspace_code = 'breslov'
  AND p.project_code = 'breslov_library';

WITH default_context AS (
    SELECT
        o.id AS organization_id,
        w.id AS workspace_id,
        p.id AS project_id
    FROM organizations o
    JOIN workspaces w
      ON w.organization_id = o.id
     AND w.workspace_code = 'breslov'
    JOIN projects p
      ON p.workspace_id = w.id
     AND p.project_code = 'breslov_library'
    WHERE o.organization_code = 'tebaai'
)
INSERT INTO organization_members (organization_id, user_id, role, status)
SELECT
    c.organization_id,
    u.id,
    CASE
        WHEN u.role = 'admin' THEN 'admin'
        WHEN u.role = 'viewer' THEN 'viewer'
        ELSE 'member'
    END::member_role,
    'active'
FROM default_context c
CROSS JOIN users u
WHERE u.is_active = true
ON CONFLICT (organization_id, user_id) DO NOTHING;

WITH default_context AS (
    SELECT w.id AS workspace_id
    FROM organizations o
    JOIN workspaces w
      ON w.organization_id = o.id
     AND w.workspace_code = 'breslov'
    WHERE o.organization_code = 'tebaai'
)
INSERT INTO workspace_members (workspace_id, user_id, role, status)
SELECT
    c.workspace_id,
    u.id,
    CASE
        WHEN u.role = 'admin' THEN 'admin'
        WHEN u.role = 'viewer' THEN 'viewer'
        ELSE 'member'
    END::member_role,
    'active'
FROM default_context c
CROSS JOIN users u
WHERE u.is_active = true
ON CONFLICT (workspace_id, user_id) DO NOTHING;

WITH default_context AS (
    SELECT p.id AS project_id
    FROM organizations o
    JOIN workspaces w
      ON w.organization_id = o.id
     AND w.workspace_code = 'breslov'
    JOIN projects p
      ON p.workspace_id = w.id
     AND p.project_code = 'breslov_library'
    WHERE o.organization_code = 'tebaai'
)
INSERT INTO project_members (project_id, user_id, role, status)
SELECT
    c.project_id,
    u.id,
    CASE
        WHEN u.role = 'admin' THEN 'admin'
        WHEN u.role = 'viewer' THEN 'viewer'
        ELSE 'member'
    END::member_role,
    'active'
FROM default_context c
CROSS JOIN users u
WHERE u.is_active = true
ON CONFLICT (project_id, user_id) DO NOTHING;
