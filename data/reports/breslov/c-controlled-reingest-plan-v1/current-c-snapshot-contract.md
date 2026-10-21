# Logical snapshot contract — immediately before future ingestion

This is a design, not a restore backup or permission to modify stores. Current inventory uses `inventory_readonly.py before/after`, `globalVar.POSTGRES_DSN`, local DEV guards, psycopg 3 async, connection-level `default_transaction_read_only=on`, `REPEATABLE READ READ ONLY`, and explicit rollback. Exact executed SELECTs/parameters are in queries-before.json and queries-after.json. Schema discovery was also a SELECT over information_schema.columns. No lifecycle/migration/application import.

## Scope/seal

Approved source SHA `440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a`, OLD doc `ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa`, run `6c1a19b8-b60b-52de-b709-5496f4c6e937`. Reconfirm identity/active visibility and no other same-source generations immediately before snapshot. Establish externally approved per-C writer fence or coherent export window; read-only transaction alone cannot make PostgreSQL+Milvus atomic. Re-enumerate before/after, compare per-record digests and manifests; any drift aborts snapshot. Never pause/reconfigure services silently.

## Future read-only SQL (bound parameters, never interpolated IDs)

Within a single `SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY` transaction, with `did`, `run_id` bound to revalidated OLD:

```sql
SELECT * FROM library_documents WHERE id=%(did)s;
SELECT * FROM library_document_texts WHERE document_id=%(did)s ORDER BY id;
SELECT * FROM library_ingestion_runs_v2 WHERE document_id=%(did)s ORDER BY created_at,run_id;
SELECT * FROM library_pages_v2 WHERE document_id=%(did)s ORDER BY run_id,page_number;
SELECT * FROM library_document_chunks WHERE document_id=%(did)s ORDER BY id;
SELECT e.* FROM library_chunk_embeddings e JOIN library_document_chunks c ON c.id=e.chunk_id
 WHERE c.document_id=%(did)s ORDER BY e.id;
SELECT * FROM library_embedding_runs WHERE id IN (
 SELECT e.embedding_run_id FROM library_chunk_embeddings e
 JOIN library_document_chunks c ON c.id=e.chunk_id WHERE c.document_id=%(did)s);
SELECT * FROM content_manager_jobs WHERE document_id=%(did)s ORDER BY created_at,id;
SELECT * FROM content_manager_job_attempts WHERE job_id IN (
 SELECT id FROM content_manager_jobs WHERE document_id=%(did)s);
SELECT * FROM content_manager_ingestion_manifests WHERE document_id=%(did)s;
SELECT r.* FROM content_manager_manifest_resources r
 JOIN content_manager_ingestion_manifests m ON m.id=r.manifest_id WHERE m.document_id=%(did)s;
SELECT * FROM library_document_references WHERE document_id=%(did)s;
SELECT * FROM knowledge_scopes WHERE id=(SELECT knowledge_scope_id FROM library_documents WHERE id=%(did)s);
```

Read related structured page/source/citation nodes if present by document/run FK after schema inventory, not title heuristics. Preserve complete original Markdown/search fields/metadata; the planning report only hashes page text and does not export full chunk text. Export raw snapshots to access-controlled offline storage; sanitize public evidence. No auth/session/password tables are needed. Seal row counts and deterministic ordered row/content SHA256, schema/FK/index definitions, source files and all artifact hashes. Commit no store writes; rollback read-only transaction.

## Milvus snapshot

Use only list_collections, describe_collection, get_load_state, get_collection_stats and Strong query_iterator. Do not flush/load/release or ensure/create_collection. Enumerate primary entire live collection to reveal untracked C vectors; additionally enumerate all already-loaded TebaAI collections to catch cross-collection leftovers. Select C by exact document_id, cross-check approved source SHA and PG embedding PKs/chunks. Store full float vectors + primary key, chunk_id, document_id, source/content hashes, page bounds, collection_code/language/model dimension contract and all dynamic metadata. Preserve schema/index descriptions and embedding alias 1536-dimensional contract. Hash canonical vector bytes/serialization with algorithm version; round-trip export/import representation offline. No insert/delete/upsert in snapshot.

An unloaded collection cannot be assumed live-empty from stats alone; current bm25_test_v2 is NotLoad with row_count=0. If attribution safety requires it, require a separately authorized infrastructure/read-access precondition or independent audited empty proof; never silently load/flush it. No relevant C vector mismatch was found in loaded stores. Future gate must close residual visibility/collection-attribution uncertainty before GO.

## Source, pages, regions, viewer and citations

Read source via filesystem `sha256sum -- <approved path>` and a read-only PyMuPDF open/page count. Verify durable OLD reference and NEW future reference separately. Expected PDF is external `/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf`; 284 pages, 4550267 bytes. Current OLD source_path/source_uri NULL and durable file absent: approved prerequisite must repair OLD durability before taking execution snapshot. Do not call preserve_source in this planning gate.

Export `layout_notes.region_publication` and region geometry/certificates where persisted; OLD currently has none, so record LEGACY_UNCLASSIFIED and explicit unknown regions. Build/seal source geometry/lineage for matching in a future offline harness, not fake persisted region IDs. Preserve chunk->page/source/citation mappings, reference labels, bibliographic metadata, current status/version, viewer/source routes and editorial entity evidence IDs (derived in code, not a standalone citation table). Route format is `/library/documents/{document_id}/source#page={physical_page}`; publication metadata route `/library/documents/{document_id}/pages/{page}/publication` must be generation-bound. Archive cited OLD evidence lineage; do not assume IDs survive NEW.

Capture baseline retrieval/citation results with exact query fixtures, permitted evidence spans, identities and mode/config. Snapshot all physical pages including blanks; source availability must be checked for accepted and quarantined regions. Restore feasibility is demonstrated by checking retained OLD rows/PK/vector/content hashes and readable original, not by writing a restore into current stores. Real restore rehearsal must use a separately approved disposable environment.
