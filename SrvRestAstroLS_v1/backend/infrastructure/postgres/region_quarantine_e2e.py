"""Read-only snapshots/probes for isolated regional worker DEV validation.

No corpus-wide mutations. Cleanup is exclusively the normal ingestion manifest.
"""
import hashlib
import json
from infrastructure.postgres.transaction import fetch_all, fetch_one

TABLES = ('library_documents','library_document_texts','library_pages_v2',
          'library_document_chunks','library_chunk_embeddings','content_manager_jobs')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


async def snapshot(conn, controlled_jobs=()):
    """Full-row fingerprints of preexisting corpus, not just aggregate counts."""
    result = {}
    for table in TABLES:
        rows = await fetch_all(conn, f'SELECT to_jsonb(t) row FROM {table} t', {})
        all_rows = [r['row'] for r in rows]
        real_rows = []
        for row in all_rows:
            # Exclusion is by the exact IDs registered for this run, never title.
            marker_ids = {str(x) for x in controlled_jobs}
            if table == 'content_manager_jobs' and str(row.get('id')) in marker_ids:
                continue
            if any(str(row.get(key)) in marker_ids for key in ('document_id','id')):
                continue
            if table == 'library_chunk_embeddings':
                if str(row.get('chunk_id')) in marker_ids:
                    continue
            real_rows.append(row)
        encoded = sorted(json.dumps(row,sort_keys=True,default=str) for row in real_rows)
        result[table] = {'total_count':len(all_rows),'existing_count':len(real_rows),
                         'existing_full_rows_sha256':digest(encoded)}
    return result


async def context(conn):
    return await fetch_one(conn, """
        SELECT u.id actor_user_id,u.role,ks.* FROM users u
        JOIN project_members pm ON pm.user_id=u.id AND pm.status='active'
        JOIN knowledge_scopes ks ON ks.project_id=pm.project_id
        JOIN workspace_members wm ON wm.user_id=u.id AND wm.workspace_id=ks.workspace_id AND wm.status='active'
        JOIN organization_members om ON om.user_id=u.id AND om.organization_id=ks.organization_id AND om.status='active'
        WHERE u.is_active AND u.role='admin' AND ks.knowledge_scope_code='breslov_e2e'
        ORDER BY u.id LIMIT 1
        """, {})


async def probe_job(conn, job_id):
    job = await fetch_one(conn,'SELECT id,status,document_id,diagnostic,error_code FROM content_manager_jobs WHERE id=%(id)s',{'id':job_id})
    if not job or not job['document_id']:
        return {'job': job, 'pages': [], 'chunks': [], 'embeddings': [], 'texts': []}
    args = {'id':job['document_id']}
    pages = await fetch_all(conn,'SELECT * FROM library_pages_v2 WHERE document_id=%(id)s ORDER BY page_number',args)
    chunks = await fetch_all(conn,'SELECT * FROM library_document_chunks WHERE document_id=%(id)s ORDER BY chunk_index',args)
    embeddings = await fetch_all(conn,'''SELECT e.* FROM library_chunk_embeddings e JOIN library_document_chunks c ON c.id=e.chunk_id WHERE c.document_id=%(id)s''',args)
    texts = await fetch_all(conn,'SELECT content FROM library_document_texts WHERE document_id=%(id)s',args)
    return {'job':job,'pages':pages,'chunks':chunks,'embeddings':embeddings,'texts':texts}
