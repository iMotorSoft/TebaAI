-- Rollback script for Breslov ES/EN Ready Promotion 2026-07-05
-- Run BEFORE any subsequent changes, while backup snapshot is valid
-- Usage: psql -d tebaai -f rollback_promotion_2026-07-05.sql

BEGIN;

-- 1. Revert document status back to test_candidate
UPDATE library_documents SET status = 'test_candidate', updated_at = NOW()
WHERE id IN (
    '27f175ea-bc8b-40e4-bf2d-4ba3ab321dda',  -- KITZUR
    '0bad063c-f7a8-429c-a0ac-c01af224d5cb',  -- Cruzando el Puente
    '987bd9d3-bee7-4c1a-91d6-dd11aee8e856',  -- El Alma del Rebe Najmán
    '76f2adbc-b79a-4432-9ea5-521a337a5502',  -- El Jardín de las Almas
    'c7c10741-c324-4916-93a7-61070863e3f9',  -- Kokhavey Ohr
    '43ba4f4b-d3ee-49b6-8d09-dfa152379893',  -- La Potencia de la Plegaria
    '56ddcc3b-8296-4832-ac95-2bfe032cd4c6',  -- Likutey Halajot LM II 8
    'a852721d-ae41-4226-8cbb-b4419c0cabe9'   -- Un Día en la Vida
);

-- 2. Restore bibliographic_metadata from backup (manual restore needed from JSON)
-- Run separately: use backup_pre_promotion_2026-07-05.json to restore per-document metadata

-- 3. Verify
SELECT id, title, status FROM library_documents 
WHERE id IN ('27f175ea-...', '0bad063c-...', '987bd9d3-...', '76f2adbc-...', 
             'c7c10741-...', '43ba4f4b-...', '56ddcc3b-...', 'a852721d-...');

COMMIT;

-- For Milvus rollback, see rollback_plan in promotion report
-- Milvus: delete entities by document_id filter
-- Example via pymilvus:
--   collection.delete(expr="document_id in ['27f175ea-bc8b-...', '0bad063c-f7a8-...', ...]")
