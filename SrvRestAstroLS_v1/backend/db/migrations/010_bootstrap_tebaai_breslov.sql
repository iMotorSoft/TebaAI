-- 010_bootstrap_tebaai_breslov.sql
-- Bootstrap TebaAI/Breslov organization, workspace, project and knowledge_scope.

-- ============================================================
-- 1. ORGANIZATION: tebaai
-- ============================================================

INSERT INTO organizations (organization_code, name, status, metadata)
SELECT 'tebaai', 'Teba AI', 'active',
    '{"description": "TebaAI — Plataforma de conocimiento Breslov", "brand": "Teba AI"}'
WHERE NOT EXISTS (SELECT 1 FROM organizations WHERE organization_code = 'tebaai');

-- ============================================================
-- 2. WORKSPACE: breslov
-- ============================================================

INSERT INTO workspaces (organization_id, workspace_code, name, status)
SELECT o.id, 'breslov', 'Breslov', 'active'
FROM organizations o
WHERE o.organization_code = 'tebaai'
  AND NOT EXISTS (SELECT 1 FROM workspaces WHERE workspace_code = 'breslov' AND organization_id = o.id);

-- ============================================================
-- 3. PROJECT: breslov_library
-- ============================================================

INSERT INTO projects (organization_id, workspace_id, project_code, name, project_type, status)
SELECT o.id, w.id, 'breslov_library', 'Breslov Bibliographic Library', 'bibliographic_library', 'active'
FROM organizations o
JOIN workspaces w ON w.organization_id = o.id AND w.workspace_code = 'breslov'
WHERE o.organization_code = 'tebaai'
  AND NOT EXISTS (
    SELECT 1 FROM projects WHERE project_code = 'breslov_library' AND workspace_id = w.id
  );

-- ============================================================
-- 4. KNOWLEDGE SCOPE: breslov_primary (main multi-lingual corpus)
-- ============================================================

INSERT INTO knowledge_scopes (organization_id, workspace_id, project_id, knowledge_scope_code, name, description, scope_type, language_policy, status)
SELECT o.id, w.id, p.id, 'breslov_primary', 'Breslov Primary Corpus',
    'Corpus principal multilingüe (ES/EN/HE) de la bibliografía Breslov',
    'bibliographic_corpus', 'es,en,he', 'active'
FROM organizations o
JOIN workspaces w ON w.organization_id = o.id AND w.workspace_code = 'breslov'
JOIN projects p ON p.workspace_id = w.id AND p.project_code = 'breslov_library'
WHERE o.organization_code = 'tebaai'
  AND NOT EXISTS (
    SELECT 1 FROM knowledge_scopes WHERE knowledge_scope_code = 'breslov_primary' AND project_id = p.id
  );

-- ============================================================
-- 5. Link existing library_collections to project/scope
-- ============================================================

UPDATE library_collections lc
SET metadata = metadata || jsonb_build_object(
    'knowledge_scope_code', 'breslov_primary',
    'project_code', 'breslov_library',
    'workspace_code', 'breslov',
    'organization_code', 'tebaai'
)
WHERE lc.code IN ('breslov', 'breslov_test')
  AND NOT (metadata ? 'knowledge_scope_code');

-- ============================================================
-- 6. Assign admin user to tebaai org (if any exists)
-- ============================================================

INSERT INTO organization_members (organization_id, user_id, role)
SELECT o.id, u.id, 'admin'
FROM organizations o, users u
WHERE o.organization_code = 'tebaai'
  AND u.role IN ('admin')
  AND NOT EXISTS (
    SELECT 1 FROM organization_members om
    WHERE om.organization_id = o.id AND om.user_id = u.id
  );

-- ============================================================
-- 7. Sync existing library_documents to knowledge_scopes
--    (set knowledge_scope_id for documents in breslov/breslov_test)
-- ============================================================

UPDATE library_documents ld
SET knowledge_scope_id = ks.id,
    organization_id = ks.organization_id,
    workspace_id = ks.workspace_id,
    project_id = ks.project_id
FROM library_collections lc
JOIN knowledge_scopes ks ON ks.knowledge_scope_code = 'breslov_primary'
WHERE ld.collection_id = lc.id
  AND lc.code IN ('breslov', 'breslov_test')
  AND ld.knowledge_scope_id IS NULL;
