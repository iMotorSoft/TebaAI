"""Common V2 vector-search backends for derived development stores.

PostgreSQL remains authoritative for text; these backends only return ranked,
metadata-filtered candidates.  The ``auto`` backend records its selected store
on every hit and falls back without hiding the preceding error.
"""
from __future__ import annotations

import asyncio
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx
import psycopg
from pymilvus import Collection, connections, utility

from globalVar import (
    LITELLM_API_KEY,
    LITELLM_BASE_URL,
    MILVUS_HOST,
    MILVUS_PORT,
    RESEARCH_EMBEDDING_MODEL_ALIAS,
)


PGVECTOR_TABLE = "library_vector_embeddings_v2_dev"
MILVUS_COLLECTION = "tebaai_breslov_chunks_v2_dev"


@dataclass
class VectorHit:
    backend: str
    chunk_id: str
    document_id: str
    page: int
    language: str
    score: float
    distance: float
    evidence_text: str
    metadata: dict[str, Any]


class VectorSearchBackend(ABC):
    """Shared contract implemented by every selectable vector backend."""

    name: str

    @abstractmethod
    async def health(self) -> dict[str, Any]: ...

    @abstractmethod
    async def ensure_ready(self, timeout_seconds: float = 10.0) -> dict[str, Any]: ...

    @abstractmethod
    async def search(self, query: str, scope: str, top_k: int = 10, filters: dict[str, Any] | None = None) -> list[VectorHit]: ...


async def query_embedding(query: str) -> list[float]:
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{LITELLM_BASE_URL}/v1/embeddings",
            headers={"Authorization": f"Bearer {LITELLM_API_KEY}"},
            json={"model": RESEARCH_EMBEDDING_MODEL_ALIAS, "input": query},
        )
        response.raise_for_status()
        return response.json()["data"][0]["embedding"]


def _pg_config() -> dict[str, Any]:
    return {
        "user": os.environ["DB_PG_USER"],
        "password": os.environ["DB_PG_PASS"],
        "host": os.environ.get("DB_PG_IP", "localhost"),
        "port": int(os.environ.get("DB_PG_PORT", "5432")),
        "dbname": "tebaai",
    }


class PgvectorVectorBackend(VectorSearchBackend):
    name = "pgvector"

    def __init__(self, table: str = PGVECTOR_TABLE) -> None:
        self.table = table

    async def health(self) -> dict[str, Any]:
        try:
            with psycopg.connect(**_pg_config()) as conn, conn.cursor() as cursor:
                cursor.execute(f"SELECT count(*) FROM {self.table}")
                count = cursor.fetchone()[0]
            return {"backend": self.name, "status": "ready", "details": {"table": self.table, "rows": count}, "error": None}
        except Exception as exc:
            return {"backend": self.name, "status": "error", "details": {"table": self.table}, "error": f"{type(exc).__name__}: {exc}"}

    async def ensure_ready(self, timeout_seconds: float = 10.0) -> dict[str, Any]:
        return await self.health()

    async def search(self, query: str, scope: str, top_k: int = 10, filters: dict[str, Any] | None = None) -> list[VectorHit]:
        filters = filters or {}
        vector = await query_embedding(query)
        literal = "[" + ",".join(map(str, vector)) + "]"
        sql = f"""
            SELECT chunk_id, document_id::text, page, language, text_preview,
                   embedding <=> %s::vector AS distance
              FROM {self.table}
             WHERE knowledge_scope_code = %s
               AND (%s::text IS NULL OR collection_code = %s)
               AND (%s::text IS NULL OR run_id = %s::uuid)
               AND (%s::text IS NULL OR document_id = %s::uuid)
               AND (%s::text IS NULL OR language = %s)
             ORDER BY embedding <=> %s::vector
             LIMIT %s
        """
        params = (
            literal, scope,
            filters.get("collection_code"), filters.get("collection_code"),
            filters.get("run_id"), filters.get("run_id"),
            filters.get("document_id"), filters.get("document_id"),
            filters.get("language"), filters.get("language"),
            literal, top_k,
        )
        with psycopg.connect(**_pg_config()) as conn, conn.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
        return [
            VectorHit(
                backend=self.name,
                chunk_id=row[0], document_id=row[1], page=row[2], language=row[3],
                score=1 - float(row[5]), distance=float(row[5]), evidence_text=row[4], metadata={},
            )
            for row in rows
        ]


class MilvusVectorBackend(VectorSearchBackend):
    name = "milvus"

    def __init__(self, collection: str = MILVUS_COLLECTION) -> None:
        self.collection = collection

    def _connect(self) -> None:
        connections.connect(alias="default", host=MILVUS_HOST, port=MILVUS_PORT, timeout=10)

    async def ensure_loaded(self, timeout_seconds: float = 10.0, poll_interval_seconds: float = 0.25) -> dict[str, Any]:
        started = time.monotonic()
        requested = False
        before = "unknown"
        try:
            self._connect()
            before = str(utility.load_state(self.collection))
            if "Loaded" not in before:
                Collection(self.collection).load()
                requested = True
            after = before
            while time.monotonic() - started < timeout_seconds:
                after = str(utility.load_state(self.collection))
                if "Loaded" in after:
                    return {
                        "backend": self.name, "status": "ready",
                        "details": {
                            "load_state_before": before, "load_requested": requested,
                            "load_state_after": after,
                            "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
                            "timeout": False,
                        }, "error": None,
                    }
                await asyncio.sleep(poll_interval_seconds)
            return {
                "backend": self.name, "status": "not_ready",
                "details": {
                    "load_state_before": before, "load_requested": requested,
                    "load_state_after": after,
                    "elapsed_ms": round((time.monotonic() - started) * 1000, 2), "timeout": True,
                }, "error": "load_timeout",
            }
        except Exception as exc:
            return {
                "backend": self.name, "status": "error",
                "details": {"load_state_before": before, "load_requested": requested,
                            "elapsed_ms": round((time.monotonic() - started) * 1000, 2), "timeout": False},
                "error": f"{type(exc).__name__}: {exc}",
            }

    async def health(self) -> dict[str, Any]:
        return await self.ensure_loaded()

    async def ensure_ready(self, timeout_seconds: float = 10.0) -> dict[str, Any]:
        return await self.ensure_loaded(timeout_seconds=timeout_seconds)

    async def search(self, query: str, scope: str, top_k: int = 10, filters: dict[str, Any] | None = None) -> list[VectorHit]:
        ready = await self.ensure_loaded()
        if ready["status"] != "ready":
            raise RuntimeError(ready["error"] or "milvus_not_ready")
        filters = filters or {}
        clauses = [f'knowledge_scope_code == "{scope}"']
        for key in ("collection_code", "run_id", "document_id", "language"):
            if filters.get(key):
                clauses.append(f'{key} == "{filters[key]}"')
        vector = await query_embedding(query)
        hits = Collection(self.collection).search(
            data=[vector], anns_field="embedding", param={"metric_type": "COSINE", "params": {"ef": 64}},
            limit=top_k, expr=" and ".join(clauses),
            output_fields=["chunk_id", "document_id", "page", "language", "text_preview"],
        )
        return [
            VectorHit(
                backend=self.name, chunk_id=hit.entity.get("chunk_id"), document_id=hit.entity.get("document_id"),
                page=hit.entity.get("page"), language=hit.entity.get("language"),
                score=float(hit.distance), distance=float(hit.distance), evidence_text=hit.entity.get("text_preview"),
                metadata={"load": ready["details"]},
            )
            for hit in hits[0]
        ]


class DisabledVectorBackend(VectorSearchBackend):
    name = "disabled"

    async def health(self) -> dict[str, Any]:
        return {"backend": self.name, "status": "disabled", "details": {}, "error": None}

    async def ensure_ready(self, timeout_seconds: float = 10.0) -> dict[str, Any]:
        return await self.health()

    async def search(self, *args: Any, **kwargs: Any) -> list[VectorHit]:
        return []


class AutoVectorBackend(VectorSearchBackend):
    name = "auto"

    def __init__(self, milvus: MilvusVectorBackend | None = None, pgvector: PgvectorVectorBackend | None = None) -> None:
        self.milvus = milvus or MilvusVectorBackend()
        self.pgvector = pgvector or PgvectorVectorBackend()
        self.last_error: str | None = None
        self.backend_used = "disabled"

    async def health(self) -> dict[str, Any]:
        milvus = await self.milvus.health()
        if milvus["status"] == "ready":
            return {**milvus, "backend": self.name, "details": {"backend_used": "milvus", **milvus["details"]}}
        pgvector = await self.pgvector.health()
        return {**pgvector, "backend": self.name, "details": {"backend_used": "pgvector", "milvus_error": milvus["error"], **pgvector["details"]}}

    async def ensure_ready(self, timeout_seconds: float = 10.0) -> dict[str, Any]:
        return await self.health()

    async def search(self, *args: Any, **kwargs: Any) -> list[VectorHit]:
        self.last_error = None
        try:
            hits = await self.milvus.search(*args, **kwargs)
            self.backend_used = "milvus"
            return hits
        except Exception as exc:
            self.last_error = f"milvus:{type(exc).__name__}"
        try:
            hits = await self.pgvector.search(*args, **kwargs)
            self.backend_used = "pgvector"
            return hits
        except Exception as exc:
            self.last_error = f"{self.last_error};pgvector:{type(exc).__name__}"
            self.backend_used = "disabled"
            return []


def get_vector_backend(name: str = "auto") -> Any:
    return {"milvus": MilvusVectorBackend, "pgvector": PgvectorVectorBackend, "disabled": DisabledVectorBackend, "auto": AutoVectorBackend}.get(name, AutoVectorBackend)()
