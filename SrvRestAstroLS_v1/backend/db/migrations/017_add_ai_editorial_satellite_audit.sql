ALTER TABLE library_content_nodes_v2 ADD COLUMN IF NOT EXISTS link_status TEXT NOT NULL DEFAULT 'linked_deterministic';
ALTER TABLE library_content_nodes_v2 ADD COLUMN IF NOT EXISTS review_status TEXT NOT NULL DEFAULT 'deterministic';
ALTER TABLE library_content_nodes_v2 ADD COLUMN IF NOT EXISTS ai_confidence NUMERIC;
ALTER TABLE library_content_nodes_v2 ADD COLUMN IF NOT EXISTS ai_rationale TEXT;
ALTER TABLE library_content_nodes_v2 ADD COLUMN IF NOT EXISTS ai_prompt_version TEXT;
ALTER TABLE library_content_relations_v2 ADD COLUMN IF NOT EXISTS relation_origin TEXT NOT NULL DEFAULT 'deterministic';
ALTER TABLE library_content_relations_v2 ADD COLUMN IF NOT EXISTS rationale TEXT;
ALTER TABLE library_content_relations_v2 ADD COLUMN IF NOT EXISTS prompt_version TEXT;
ALTER TABLE library_content_relations_v2 ADD COLUMN IF NOT EXISTS model_name TEXT;
