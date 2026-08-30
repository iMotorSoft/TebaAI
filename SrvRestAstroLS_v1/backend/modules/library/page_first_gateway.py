"""PostgreSQL, LiteLLM and isolated-Milvus adapters for page-first ingestion."""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, MilvusClient

from globalVar import (
    CONTENT_MANAGER_E2E_COLLECTION,
    CONTENT_MANAGER_E2E_ENABLED,
    CONTENT_MANAGER_E2E_FIXTURE_SHA256,
    CONTENT_MANAGER_E2E_SCOPE,
    CONTENT_MANAGER_PRIMARY_INGESTION_ENABLED,
    EMBEDDINGS_DIMENSION,
    MILVUS_COLLECTION_BRESLOV,
    MILVUS_HOST,
    MILVUS_PORT,
    TEBAAI_ENV,
)
from infrastructure.milvus.client import BRESLOV_FIELDS, BRESLOV_INDEX_PARAMS, create_connection
from infrastructure.postgres.transaction import transaction
from modules.embeddings.client import embed_batch
from modules.library.chunking import paragraph_chunks
from modules.library.content_manager_repository import ClaimedJob
from modules.library.hybrid_search import resolve_milvus_collection_code_for_scope
from modules.library.pdf_ligature_normalization import normalize_pdf_search_text
from modules.library.page_first_pipeline import (
    ExtractedDocument,
    PageFirstIngestionRequest,
    PersistedChunk,
    PersistedDocument,
    PersistedEmbedding,
    ReconciliationResult,
    reconcile_resource_sets,
)


def _uuid(namespace: UUID, value: str) -> UUID:
    return uuid5(namespace, value)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


class E2EIsolationError(RuntimeError):
    error_code = "e2e_isolation_rejected"


class MilvusAttemptIndex:
    """Milvus adapter for isolated attempts and exact-ID primary writes."""

    def __init__(self, collection_name: str) -> None:
        self.collection_name = collection_name
        self.client = MilvusClient(uri=f"http://{MILVUS_HOST}:{MILVUS_PORT}")

    def ensure(self) -> None:
        if self.collection_name not in {CONTENT_MANAGER_E2E_COLLECTION, MILVUS_COLLECTION_BRESLOV}:
            raise E2EIsolationError("Content Manager worker rejected an unknown Milvus collection")
        if self.collection_name in self.client.list_collections():
            fields = {item["name"] for item in self.client.describe_collection(self.collection_name)["fields"]}
            required = {field.name for field in BRESLOV_FIELDS}
            if not required.issubset(fields):
                raise E2EIsolationError("Existing Content Manager collection has an incompatible schema")
            if self.collection_name == CONTENT_MANAGER_E2E_COLLECTION and not {
                "attempt_key", "job_id", "attempt_number"
            }.issubset(fields):
                raise E2EIsolationError("Existing E2E collection has an incompatible attempt schema")
            self.client.load_collection(self.collection_name)
            return
        if self.collection_name == MILVUS_COLLECTION_BRESLOV:
            raise E2EIsolationError("The productive Milvus collection must be provisioned before worker startup")
        create_connection()
        fields = list(BRESLOV_FIELDS) + [
            FieldSchema(name="attempt_key", dtype=DataType.VARCHAR, max_length=96),
            FieldSchema(name="job_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="attempt_number", dtype=DataType.INT64),
        ]
        collection = Collection(
            name=self.collection_name,
            schema=CollectionSchema(fields, description="TebaAI Content Manager isolated write E2E"),
        )
        collection.create_index(field_name="embedding", index_params=BRESLOV_INDEX_PARAMS)
        collection.load()

    def upsert(self, rows: list[dict]) -> tuple[str, ...]:
        self.ensure()
        if rows:
            self.client.upsert(collection_name=self.collection_name, data=rows)
            self.client.flush(collection_name=self.collection_name)
        return tuple(str(row["pk"]) for row in rows)

    def list_attempt(self, attempt_key: str) -> list[dict]:
        self.ensure()
        if self.collection_name != CONTENT_MANAGER_E2E_COLLECTION:
            raise E2EIsolationError("Attempt-key queries are only available in the isolated E2E schema")
        return self.client.query(
            collection_name=self.collection_name,
            filter=f'attempt_key == "{attempt_key}"',
            output_fields=["pk", "chunk_id", "document_id", "attempt_key", "job_id", "attempt_number"],
            limit=16384,
            consistency_level="Strong",
        )

    def list_ids(self, ids: list[str]) -> list[dict]:
        self.ensure()
        if not ids:
            return []
        return self.client.get(
            collection_name=self.collection_name,
            ids=ids,
            output_fields=["pk", "chunk_id", "document_id", "collection_code"],
        )

    def delete_ids(self, ids: list[str]) -> int:
        self.ensure()
        if not ids:
            return 0
        result = self.client.delete(collection_name=self.collection_name, ids=ids)
        return int(result.get("delete_count", 0)) if isinstance(result, dict) else len(ids)

    def count(self) -> int:
        self.ensure()
        return int(self.client.get_collection_stats(self.collection_name).get("row_count", 0))


class PostgresMilvusPageFirstGateway:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self.pool = pool

    async def load_request(self, job: ClaimedJob) -> PageFirstIngestionRequest:
        async with transaction(self.pool) as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT j.actor_user_id, j.work_family, u.temp_path, u.sha256,
                           u.expires_at, ks.knowledge_scope_code
                    FROM content_manager_jobs j
                    JOIN content_manager_uploads u ON u.id=j.upload_id
                    JOIN knowledge_scopes ks ON ks.id=j.knowledge_scope_id
                    WHERE j.id=%s AND j.upload_id=%s AND j.organization_id=%s
                      AND j.workspace_id=%s AND j.project_id=%s AND j.knowledge_scope_id=%s
                    """,
                    (job.job_id, job.upload_id, job.tenant.organization_id, job.tenant.workspace_id,
                     job.tenant.project_id, job.tenant.knowledge_scope_id),
                )
                row = await cur.fetchone()
        if not row:
            raise E2EIsolationError("Job/upload tenant chain is invalid")
        scope_code = row["knowledge_scope_code"]
        self._assert_write_allowed(job, scope_code, row["sha256"])
        path = Path(row["temp_path"] or "")
        if not path.is_file() or _file_sha(path) != row["sha256"]:
            raise E2EIsolationError("Validated fixture is missing or its hash changed")
        return PageFirstIngestionRequest(
            upload_id=job.upload_id, job_id=job.job_id, attempt_number=job.attempt_number,
            source_path=path, source_sha256=row["sha256"], title=job.title,
            language=job.language, work_family=row["work_family"],
            ingestion_profile=job.ingestion_profile, pipeline_version=job.pipeline_version,
            embedding_model=job.embedding_model, collection_code=job.collection_code,
            knowledge_scope_code=scope_code,
            milvus_collection_code=resolve_milvus_collection_code_for_scope(scope_code) or scope_code,
            tenant=job.tenant, actor_user_id=row["actor_user_id"],
        )

    def _assert_write_allowed(self, job: ClaimedJob, scope_code: str, source_sha256: str) -> None:
        if scope_code == CONTENT_MANAGER_E2E_SCOPE:
            self._assert_e2e(job, scope_code, source_sha256)
            return
        if scope_code != "breslov_primary" or job.collection_code != MILVUS_COLLECTION_BRESLOV:
            raise E2EIsolationError("Content Manager worker rejected a mismatched primary scope/collection")
        if not CONTENT_MANAGER_PRIMARY_INGESTION_ENABLED:
            raise E2EIsolationError("Primary Content Manager ingestion is disabled")

    def _assert_e2e(self, job: ClaimedJob, scope_code: str, source_sha256: str) -> None:
        if TEBAAI_ENV != "development" or not CONTENT_MANAGER_E2E_ENABLED:
            raise E2EIsolationError("Content Manager write E2E is disabled outside an explicit DEV run")
        if scope_code != CONTENT_MANAGER_E2E_SCOPE or job.collection_code != CONTENT_MANAGER_E2E_COLLECTION:
            raise E2EIsolationError("E2E worker rejected primary or mismatched scope/collection")
        if not CONTENT_MANAGER_E2E_FIXTURE_SHA256 or source_sha256 != CONTENT_MANAGER_E2E_FIXTURE_SHA256:
            raise E2EIsolationError("Upload hash is not the configured authorized fixture")

    async def persist_document_and_pages(
        self, request: PageFirstIngestionRequest, extracted: ExtractedDocument,
    ) -> PersistedDocument:
        document_id = _uuid(request.tenant.knowledge_scope_id, f"{request.source_sha256}:{request.pipeline_version}")
        text_id = _uuid(document_id, "canonical-markdown")
        run_id = _uuid(document_id, request.attempt_key)
        manifest_id = _uuid(request.job_id, f"manifest:{request.attempt_number}")
        page_ids = tuple(_uuid(run_id, f"page:{page.page_number}") for page in extracted.pages)
        async with transaction(self.pool) as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                legacy_code = (
                    "breslov_test"
                    if request.knowledge_scope_code == CONTENT_MANAGER_E2E_SCOPE
                    else "breslov"
                )
                await cur.execute(
                    "SELECT id FROM library_collections_legacy WHERE code=%s LIMIT 1",
                    (legacy_code,),
                )
                legacy = await cur.fetchone()
                if not legacy:
                    raise RuntimeError("Legacy compatibility collection is unavailable")
                await cur.execute(
                    """
                    INSERT INTO library_documents(
                        id,collection_id,title,language,source_type,source_filename,source_mime_type,
                        source_size_bytes,source_sha256,status,metadata,bibliographic_metadata,created_by,
                        organization_id,workspace_id,project_id,knowledge_scope_id,content_sha256,
                        canonical_text_role,chunk_set_version)
                    VALUES(%s,%s,%s,%s,'pdf',%s,'application/pdf',%s,%s,'draft',%s::jsonb,%s::jsonb,%s,
                           %s,%s,%s,%s,%s,'candidate',1)
                    ON CONFLICT(id) DO NOTHING
                    """,
                    (document_id, legacy["id"], request.title, extracted.language,
                     request.source_path.name, request.source_path.stat().st_size, request.source_sha256,
                     _json({"content_manager_job_id": str(request.job_id), "attempt": request.attempt_number}),
                     _json({
                         "work_family": request.work_family,
                         "content_manager_ingestion": True,
                         "e2e_fixture": request.knowledge_scope_code == CONTENT_MANAGER_E2E_SCOPE,
                     }), request.actor_user_id,
                     request.tenant.organization_id, request.tenant.workspace_id, request.tenant.project_id,
                     request.tenant.knowledge_scope_id, extracted.content_sha256),
                )
                await cur.execute(
                    """INSERT INTO library_ingestion_runs_v2(run_id,document_id,pipeline_version,scope_code,status)
                       VALUES(%s,%s,%s,%s,'started') ON CONFLICT(run_id) DO NOTHING""",
                    (run_id, document_id, request.pipeline_version, request.knowledge_scope_code),
                )
                await cur.execute(
                    """
                    INSERT INTO library_document_texts(
                        id,document_id,text_format,content,content_sha256,content_length,extraction_method,
                        extraction_metadata,text_role,page_markers_enabled,page_count,knowledge_scope_id)
                    VALUES(%s,%s,'markdown',%s,%s,%s,'pymupdf4llm',%s::jsonb,'canonical',true,%s,%s)
                    ON CONFLICT(id) DO NOTHING
                    """,
                    (text_id, document_id, extracted.content_markdown, extracted.content_sha256,
                     len(extracted.content_markdown), _json({"engine": "pymupdf4llm", "format": "markdown",
                     "ocr_required": False, "source": "local_pdf", "page_first": True}),
                     len(extracted.pages), request.tenant.knowledge_scope_id),
                )
                for page_id, page in zip(page_ids, extracted.pages, strict=True):
                    await cur.execute(
                        """
                        INSERT INTO library_pages_v2(page_id,run_id,document_id,page_number,text,char_count,
                            extraction_method,confidence,layout_notes)
                        VALUES(%s,%s,%s,%s,%s,%s,'pymupdf4llm_page_first',0.95,%s::jsonb)
                        ON CONFLICT(page_id) DO NOTHING
                        """,
                        (page_id, run_id, document_id, page.page_number, page.original_markdown,
                         len(page.original_markdown), _json({"language": page.language,
                         "headings": list(page.headings), "footnotes": list(page.footnote_numbers),
                         "printed_references": list(page.printed_references), "is_empty": page.is_empty})),
                    )
                await cur.execute(
                    """INSERT INTO content_manager_ingestion_manifests(
                         id,job_id,attempt_number,document_id,ingestion_run_id,temporary_file_id)
                       VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(job_id,attempt_number) DO NOTHING""",
                    (manifest_id, request.job_id, request.attempt_number, document_id, run_id, request.upload_id),
                )
                resources = [("document", str(document_id)), ("document_text", str(text_id)),
                             ("ingestion_run", str(run_id)), ("temporary_file", str(request.upload_id))]
                resources += [("page", str(item)) for item in page_ids]
                await _record_resources(cur, manifest_id, resources)
                await cur.execute("UPDATE content_manager_jobs SET document_id=%s WHERE id=%s", (document_id, request.job_id))
        return PersistedDocument(document_id, text_id, run_id, manifest_id, page_ids)

    async def persist_chunks(self, request, persisted, extracted) -> tuple[PersistedChunk, ...]:
        result: list[PersistedChunk] = []
        global_index = 0
        for page in extracted.pages:
            for local_index, raw in enumerate(paragraph_chunks(page.original_markdown, 1400, 150, 1)):
                content = raw["content"]
                content_sha = _sha(content)
                chunk_id = _uuid(persisted.document_id, f"chunk:{request.pipeline_version}:{page.page_number}:{local_index}:{content_sha}")
                chunk_uid = hashlib.sha256(str(chunk_id).encode()).hexdigest()[:24]
                result.append(PersistedChunk(chunk_id, chunk_uid, page.page_number, global_index,
                                             content, content_sha, page.language))
                global_index += 1
        async with transaction(self.pool) as conn:
            async with conn.cursor() as cur:
                legacy_code = (
                    "breslov_test"
                    if request.knowledge_scope_code == CONTENT_MANAGER_E2E_SCOPE
                    else "breslov"
                )
                legacy = await cur.execute(
                    "SELECT id FROM library_collections_legacy WHERE code=%s LIMIT 1",
                    (legacy_code,),
                )
                legacy_row = await legacy.fetchone()
                legacy_id = legacy_row["id"]
                for chunk in result:
                    await cur.execute(
                        """
                        INSERT INTO library_document_chunks(
                          id,document_id,document_text_id,collection_id,chunk_index,chunk_uid,language,
                          content,content_sha256,content_length,token_count_estimate,char_start,char_end,
                          page_start,page_end,metadata,search_text_normalized,knowledge_scope_id,
                          organization_id,workspace_id,project_id,chunk_set_version,page_mapping_status,
                          chunking_strategy,chunking_version,token_estimate,is_empty,block_type,evidence_role,
                          citable,ingestion_profile,bibliographic_metadata)
                        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,
                               1,'mapped','page_first','content_page_first_v1',%s,false,'page_first_v1',
                               'page_text',true,%s,%s::jsonb)
                        ON CONFLICT(id) DO NOTHING
                        """,
                        (chunk.chunk_id, persisted.document_id, persisted.document_text_id, legacy_id,
                         chunk.chunk_index, chunk.chunk_uid, chunk.language, chunk.content, chunk.content_sha256,
                         len(chunk.content), max(1, len(chunk.content)//4), len(chunk.content),
                         chunk.page_number, chunk.page_number,
                         _json({"job_id": str(request.job_id), "attempt": request.attempt_number}),
                         normalize_pdf_search_text(chunk.content), request.tenant.knowledge_scope_id,
                         request.tenant.organization_id, request.tenant.workspace_id, request.tenant.project_id,
                         max(1, len(chunk.content)//4), request.ingestion_profile,
                         _json({"work_family": request.work_family, "page_first": True})),
                    )
                await _record_resources(cur, persisted.manifest_id,
                                        [("chunk", str(item.chunk_id)) for item in result])
        return tuple(result)

    async def embed(self, texts: tuple[str, ...], model: str) -> tuple[tuple[float, ...], ...]:
        vectors = await asyncio.to_thread(embed_batch, list(texts), model)
        if any(len(vector) != EMBEDDINGS_DIMENSION for vector in vectors):
            raise RuntimeError("Embedding dimension mismatch")
        return tuple(tuple(vector) for vector in vectors)

    async def persist_embeddings(self, request, persisted, chunks, vectors) -> tuple[PersistedEmbedding, ...]:
        run_id = _uuid(persisted.ingestion_run_id, f"embeddings:{request.embedding_model}")
        items = tuple(PersistedEmbedding(_uuid(chunk.chunk_id, f"embedding:{request.embedding_model}"), chunk, vector)
                      for chunk, vector in zip(chunks, vectors, strict=True))
        async with transaction(self.pool) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """INSERT INTO library_embedding_runs(id,collection_code,milvus_collection,
                       embedding_provider,embedding_model,embedding_dimension,status,chunks_total,metadata)
                       VALUES(%s,%s,%s,'litellm',%s,%s,'running',%s,%s::jsonb) ON CONFLICT(id) DO NOTHING""",
                    (run_id, request.milvus_collection_code, request.collection_code, request.embedding_model,
                     EMBEDDINGS_DIMENSION, len(items), _json({"job_id": str(request.job_id), "attempt": request.attempt_number})),
                )
                for item in items:
                    await cur.execute(
                        """INSERT INTO library_chunk_embeddings(
                           id,chunk_id,embedding_run_id,embedding_provider,embedding_model,embedding_dimension,
                           milvus_collection,milvus_primary_key,content_sha256,status,metadata,
                           embedding_model_alias,embedding_version,chunk_set_version,knowledge_scope_id,
                           organization_id,workspace_id,project_id,vector_status)
                           VALUES(%s,%s,%s,'litellm',%s,%s,%s,%s,%s,'indexed',%s::jsonb,%s,1,1,%s,%s,%s,%s,'generated')
                           ON CONFLICT(id) DO NOTHING""",
                        (item.embedding_id, item.chunk.chunk_id, run_id, request.embedding_model,
                         EMBEDDINGS_DIMENSION, request.collection_code, item.chunk.chunk_uid,
                         item.chunk.content_sha256, _json({"job_id": str(request.job_id), "attempt": request.attempt_number}),
                         request.embedding_model, request.tenant.knowledge_scope_id, request.tenant.organization_id,
                         request.tenant.workspace_id, request.tenant.project_id),
                    )
                await _record_resources(cur, persisted.manifest_id,
                    [("embedding_run", str(run_id)), *(("embedding", str(item.embedding_id)) for item in items)])
        return items

    async def index_vectors(self, request, persisted, embeddings) -> tuple[str, ...]:
        index = MilvusAttemptIndex(request.collection_code)
        rows = [{
            "pk": item.chunk.chunk_uid, "chunk_id": str(item.chunk.chunk_id),
            "document_id": str(persisted.document_id), "collection_code": request.milvus_collection_code,
            "language": item.chunk.language, "title": request.title, "source_type": "pdf",
            "source_sha256": request.source_sha256, "content_sha256": item.chunk.content_sha256,
            "chunk_index": item.chunk.chunk_index, "page_start": item.chunk.page_number,
            "page_end": item.chunk.page_number, "content_preview": item.chunk.content[:1024],
            "embedding": list(item.vector),
        } for item in embeddings]
        if request.knowledge_scope_code == CONTENT_MANAGER_E2E_SCOPE:
            for row in rows:
                row.update({
                    "attempt_key": request.attempt_key,
                    "job_id": str(request.job_id),
                    "attempt_number": request.attempt_number,
                })
        vector_ids = tuple(str(row["pk"]) for row in rows)
        # IDs are deterministic and recorded before the external write. A crash
        # after Milvus accepts the batch can therefore be compensated exactly.
        async with transaction(self.pool) as conn:
            async with conn.cursor() as cur:
                await _record_resources(cur, persisted.manifest_id, [("vector", item) for item in vector_ids])
        await asyncio.to_thread(index.upsert, rows)
        async with transaction(self.pool) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """UPDATE library_chunk_embeddings SET vector_status=%s
                       WHERE id = ANY(%s::uuid[])""",
                    (
                        "indexed_test"
                        if request.knowledge_scope_code == CONTENT_MANAGER_E2E_SCOPE
                        else "indexed_production",
                        [str(item.embedding_id) for item in embeddings],
                    ),
                )
        return vector_ids

    async def reconcile(self, request, persisted) -> ReconciliationResult:
        async with transaction(self.pool) as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """SELECT resource_type,resource_id,count(*) AS n
                       FROM content_manager_manifest_resources WHERE manifest_id=%s
                       GROUP BY resource_type,resource_id""", (persisted.manifest_id,))
                resources = await cur.fetchall()
                expected = {kind: [] for kind in ("chunk", "embedding", "vector")}
                duplicates: list[str] = []
                for row in resources:
                    if row["resource_type"] in expected:
                        expected[row["resource_type"]].append(row["resource_id"])
                    if row["n"] > 1:
                        duplicates.append(row["resource_id"])
                await cur.execute(
                    """SELECT e.id::text embedding_id,c.id::text chunk_id,e.milvus_primary_key
                       FROM library_chunk_embeddings e JOIN library_document_chunks c ON c.id=e.chunk_id
                       WHERE c.document_id=%s AND e.id = ANY(%s::uuid[])""",
                    (persisted.document_id, expected["embedding"] or [str(UUID(int=0))]),
                )
                pg_rows = await cur.fetchall()
        index = MilvusAttemptIndex(request.collection_code)
        if request.knowledge_scope_code == CONTENT_MANAGER_E2E_SCOPE:
            found = await asyncio.to_thread(index.list_attempt, request.attempt_key)
        else:
            found = await asyncio.to_thread(index.list_ids, expected["vector"])
        result = reconcile_resource_sets(
            job_id=request.job_id, attempt_number=request.attempt_number,
            document_id=persisted.document_id,
            chunk_ids=tuple(expected["chunk"]),
            embedding_chunk_ids=tuple(row["chunk_id"] for row in pg_rows),
            expected_vector_ids=tuple(expected["vector"]),
            found_vectors=tuple(found),
            attempt_metadata_required=request.knowledge_scope_code == CONTENT_MANAGER_E2E_SCOPE,
        )
        if duplicates:
            return ReconciliationResult(
                result.job_id, result.attempt_number, result.document_id,
                result.expected_chunks, result.expected_embeddings, result.expected_vectors,
                result.found_vectors, result.missing_vectors, result.orphan_vectors,
                tuple(sorted(set(result.duplicate_vectors) | set(duplicates))),
                result.metadata_mismatches,
            )
        return result

    async def finalize(self, request, persisted, reconciliation, extracted) -> None:
        if not reconciliation.consistent:
            raise RuntimeError("Cannot finalize inconsistent attempt")
        async with transaction(self.pool) as conn:
            async with conn.cursor() as cur:
                await cur.execute("UPDATE library_documents SET status='test_candidate',updated_at=now() WHERE id=%s AND status='draft'", (persisted.document_id,))
                if cur.rowcount != 1:
                    raise RuntimeError("Document did not remain a draft candidate")
                await cur.execute("UPDATE library_ingestion_runs_v2 SET status='completed',finished_at=now(),metrics_json=%s::jsonb,warnings_json=%s::jsonb WHERE run_id=%s",
                    (_json({"pages": len(extracted.pages), "chunks": reconciliation.expected_chunks,
                            "embeddings": reconciliation.expected_embeddings, "vectors": reconciliation.found_vectors}),
                     _json(list(extracted.warnings)), persisted.ingestion_run_id))
                await cur.execute("UPDATE library_embedding_runs SET status='completed',chunks_embedded=%s,chunks_indexed=%s,finished_at=now() WHERE metadata->>'job_id'=%s AND metadata->>'attempt'=%s",
                    (reconciliation.expected_embeddings, reconciliation.found_vectors,
                     str(request.job_id), str(request.attempt_number)))
                await cur.execute("UPDATE content_manager_ingestion_manifests SET reconciliation=%s::jsonb,finished_at=now(),cleanup_status='not_required' WHERE id=%s",
                    (_json({"consistent": True, "missing": [], "orphans": [], "duplicates": []}), persisted.manifest_id))
        await _remove_temporary(request.source_path)
        async with transaction(self.pool) as conn:
            await conn.execute("UPDATE content_manager_uploads SET cleanup_status='completed',cleaned_at=now(),temp_path=NULL WHERE id=%s", (request.upload_id,))
            await conn.execute("UPDATE content_manager_manifest_resources SET cleaned_at=now() WHERE manifest_id=%s AND resource_type='temporary_file'", (persisted.manifest_id,))


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


async def _record_resources(cur, manifest_id: UUID, resources) -> None:
    for resource_type, resource_id in resources:
        await cur.execute(
            """INSERT INTO content_manager_manifest_resources(manifest_id,resource_type,resource_id)
               VALUES(%s,%s,%s) ON CONFLICT DO NOTHING""",
            (manifest_id, resource_type, resource_id),
        )


async def _remove_temporary(path: Path) -> None:
    if path.exists():
        await asyncio.to_thread(path.unlink)
    parent = path.parent
    if parent.name and parent.exists():
        try:
            await asyncio.to_thread(parent.rmdir)
        except OSError:
            pass
