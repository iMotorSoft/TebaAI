"""Idempotent compensating cleanup bounded by one ingestion manifest."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from globalVar import CONTENT_MANAGER_E2E_COLLECTION, CONTENT_MANAGER_E2E_SCOPE
from infrastructure.postgres.transaction import transaction
from modules.library.page_first_gateway import E2EIsolationError, MilvusAttemptIndex


@dataclass(frozen=True)
class CleanupItem:
    resource_type: str
    resource_id: str
    result: str
    error: str | None = None


@dataclass(frozen=True)
class ManifestCleanupResult:
    job_id: UUID
    attempt_number: int
    status: str
    items: tuple[CleanupItem, ...]


class ManifestCleanupService:
    def __init__(self, pool: AsyncConnectionPool, *, index_factory=MilvusAttemptIndex) -> None:
        self.pool = pool
        self.index_factory = index_factory

    async def cleanup(
        self, job_id: UUID, attempt_number: int, *, remove_temporary: bool = True,
    ) -> ManifestCleanupResult:
        manifest = await self._load(job_id, attempt_number)
        if not manifest:
            raise ValueError("Manifest not found")
        if manifest["scope_code"] != CONTENT_MANAGER_E2E_SCOPE or manifest["collection_code"] != CONTENT_MANAGER_E2E_COLLECTION:
            raise E2EIsolationError("Cleanup rejected a non-E2E scope or collection")
        items: list[CleanupItem] = []
        await self._set_status(manifest["manifest_id"], "running")

        # Milvus first. Querying by attempt_key catches an insert that happened
        # immediately before a worker crash and before the manifest record.
        # The manifest's own vector IDs are also deleted by exact ID: delete is
        # idempotent and does not depend on scalar-filter query consistency,
        # which can silently return zero rows for fresh segments.
        try:
            index = self.index_factory(manifest["collection_code"])
            found = await asyncio.to_thread(index.list_attempt, manifest["attempt_key"])
            vector_ids = [str(row["pk"]) for row in found]
            if vector_ids:
                await asyncio.to_thread(index.delete_ids, vector_ids)
            for vector_id in vector_ids:
                items.append(CleanupItem("vector", vector_id, "deleted"))
            manifest_vectors = set(manifest["resources"].get("vector", []))
            stale_vectors = sorted(manifest_vectors - set(vector_ids))
            if stale_vectors:
                deleted = await asyncio.to_thread(index.delete_ids, stale_vectors)
                for vector_id in stale_vectors:
                    items.append(CleanupItem("vector", vector_id, "deleted" if deleted else "already_absent"))
        except Exception as exc:
            items.append(CleanupItem("vector", "attempt", "failed", type(exc).__name__))
            await self._finish(manifest["manifest_id"], items, "failed")
            return ManifestCleanupResult(job_id, attempt_number, "failed", tuple(items))

        order = ["embedding", "embedding_run", "chunk", "page", "document_text", "ingestion_run", "document"]
        for resource_type in order:
            for resource_id in manifest["resources"].get(resource_type, []):
                item = await self._delete_pg(manifest, resource_type, resource_id)
                items.append(item)

        if remove_temporary:
            temp_ids = manifest["resources"].get("temporary_file", [])
            for upload_id in temp_ids:
                items.append(await self._delete_temp(manifest, upload_id))

        status = "completed_with_warnings" if any(item.result == "failed" for item in items) else "completed"
        await self._finish(manifest["manifest_id"], items, status)
        return ManifestCleanupResult(job_id, attempt_number, status, tuple(items))

    async def _load(self, job_id: UUID, attempt_number: int):
        async with transaction(self.pool) as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT m.id manifest_id,m.document_id,m.job_id,m.attempt_number,j.collection_code,ks.knowledge_scope_code scope_code
                    FROM content_manager_ingestion_manifests m
                    JOIN content_manager_jobs j ON j.id=m.job_id
                    JOIN knowledge_scopes ks ON ks.id=j.knowledge_scope_id
                    WHERE m.job_id=%s AND m.attempt_number=%s
                    """, (job_id, attempt_number),
                )
                row = await cur.fetchone()
                if not row:
                    return None
                await cur.execute(
                    """SELECT resource_type,resource_id FROM content_manager_manifest_resources
                       WHERE manifest_id=%s AND was_preexisting=false ORDER BY resource_type,resource_id""",
                    (row["manifest_id"],),
                )
                resources: dict[str, list[str]] = {}
                for resource in await cur.fetchall():
                    resources.setdefault(resource["resource_type"], []).append(resource["resource_id"])
                row["resources"] = resources
                row["attempt_key"] = f"{job_id}:{attempt_number}"
                row["collection_code"] = row["collection_code"]
                return row

    async def _delete_pg(self, manifest, resource_type: str, resource_id: str) -> CleanupItem:
        table = {
            "embedding": ("library_chunk_embeddings", "id"),
            "embedding_run": ("library_embedding_runs", "id"),
            "chunk": ("library_document_chunks", "id"),
            "page": ("library_pages_v2", "page_id"),
            "document_text": ("library_document_texts", "id"),
            "ingestion_run": ("library_ingestion_runs_v2", "run_id"),
            "document": ("library_documents", "id"),
        }[resource_type]
        async with transaction(self.pool) as conn:
            async with conn.cursor() as cur:
                # Every deletion is both manifest-owned and document bounded.
                if resource_type == "document":
                    await cur.execute(
                        f"DELETE FROM {table[0]} WHERE {table[1]}=%s AND id=%s AND status IN ('draft','ingestion_failed','test_candidate')",
                        (resource_id, manifest["document_id"]),
                    )
                elif resource_type in {"chunk", "page", "document_text", "ingestion_run"}:
                    document_column = "document_id"
                    await cur.execute(
                        f"DELETE FROM {table[0]} WHERE {table[1]}=%s AND {document_column}=%s",
                        (resource_id, manifest["document_id"]),
                    )
                elif resource_type == "embedding":
                    await cur.execute(
                        """DELETE FROM library_chunk_embeddings e USING library_document_chunks c
                           WHERE e.id=%s AND e.chunk_id=c.id AND c.document_id=%s""",
                        (resource_id, manifest["document_id"]),
                    )
                else:  # embedding_run: ownership is in metadata, not title/time.
                    await cur.execute(
                        """DELETE FROM library_embedding_runs
                           WHERE id=%s AND metadata->>'job_id'=%s AND metadata->>'attempt'=%s""",
                        (resource_id, str(manifest["job_id"]), str(manifest["attempt_number"])),
                    )
                result = "deleted" if cur.rowcount else "already_absent"
        return CleanupItem(resource_type, resource_id, result)

    async def _delete_temp(self, manifest, upload_id: str) -> CleanupItem:
        async with transaction(self.pool) as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """SELECT temp_path FROM content_manager_uploads
                       WHERE id=%s AND id=(SELECT upload_id FROM content_manager_jobs WHERE id=%s)""",
                    (upload_id, manifest["job_id"]),
                )
                row = await cur.fetchone()
                if not row or not row["temp_path"]:
                    return CleanupItem("temporary_file", upload_id, "already_absent")
                path = Path(row["temp_path"])
                if path.exists():
                    await asyncio.to_thread(path.unlink)
                try:
                    await asyncio.to_thread(path.parent.rmdir)
                except OSError:
                    pass
                await cur.execute(
                    """UPDATE content_manager_uploads SET temp_path=NULL,cleanup_status='completed',cleaned_at=now()
                       WHERE id=%s""", (upload_id,),
                )
        return CleanupItem("temporary_file", upload_id, "deleted")

    async def _set_status(self, manifest_id: UUID, status: str) -> None:
        async with transaction(self.pool) as conn:
            await conn.execute("UPDATE content_manager_ingestion_manifests SET cleanup_status=%s WHERE id=%s", (status, manifest_id))

    async def _finish(self, manifest_id: UUID, items: list[CleanupItem], status: str) -> None:
        async with transaction(self.pool) as conn:
            async with conn.cursor() as cur:
                for item in items:
                    await cur.execute(
                        """INSERT INTO content_manager_cleanup_events(
                           manifest_id,resource_type,resource_id,action,result,error_detail)
                           VALUES(%s,%s,%s,'delete',%s,%s)""",
                        (manifest_id, item.resource_type, item.resource_id, item.result, item.error),
                    )
                    if item.result in {"deleted", "already_absent"}:
                        await cur.execute(
                            """UPDATE content_manager_manifest_resources SET cleaned_at=COALESCE(cleaned_at,now()),cleanup_error=NULL
                               WHERE manifest_id=%s AND resource_type=%s AND resource_id=%s""",
                            (manifest_id, item.resource_type, item.resource_id),
                        )
                await cur.execute("UPDATE content_manager_ingestion_manifests SET cleanup_status=%s WHERE id=%s", (status, manifest_id))
                await cur.execute(
                    """UPDATE content_manager_jobs SET cleanup_status=%s,
                       recovery_status=CASE WHEN %s='completed' THEN 'cleaned' ELSE recovery_status END
                       WHERE id=(SELECT job_id FROM content_manager_ingestion_manifests WHERE id=%s)""",
                    (status, status, manifest_id),
                )
