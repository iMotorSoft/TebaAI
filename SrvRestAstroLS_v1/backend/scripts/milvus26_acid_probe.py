#!/usr/bin/env python3
"""Read-only Milvus 2.6 acid probe for TebaAI.

Collects:
- Milvus container-relevant runtime probe
- collection schema/index/load state
- PG ready chunk count and deterministic sample
- PG <-> Milvus round-trip by chunk_id metadata
- embedding + search latency
- direct Relation QA fallback behavior without HTTP server

The script never inserts, deletes, drops, recreates, compacts or reindexes.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import globalVar as gv

DEFAULT_QUERIES = [
    "tristeza",
    "miedo",
    "alegría plegaria",
    "sangre habla",
    "ruaj habla",
    "hitbodedut",
    "emuná",
]

DEFAULT_RELATION_QUESTIONS = [
    "Qué relación hay entre alegría y plegaria",
    "Qué relación hay entre sangre y habla",
]


@dataclass
class ProbeError:
    stage: str
    kind: str
    message: str
    detail: dict[str, Any] = field(default_factory=dict)


def _ms(seconds: float | None) -> int | None:
    if seconds is None:
        return None
    return int(round(seconds * 1000))


def _now_ms() -> float:
    return time.perf_counter()


def _safe_obj_attrs(obj: Any, names: list[str]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for name in names:
        try:
            value = getattr(obj, name)
        except Exception:
            value = None
        if callable(value):
            try:
                value = value()
            except Exception:
                value = None
        if value is not None:
            if hasattr(value, "value"):
                value = getattr(value, "value")
        data[name] = value
    return data


def _serialize_value(value: Any) -> Any:
    if hasattr(value, "value"):
        return getattr(value, "value")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, set):
        return sorted(_serialize_value(item) for item in value)
    if isinstance(value, tuple):
        return [_serialize_value(item) for item in value]
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize_value(val) for key, val in value.items()}
    return value


def _query_expr_for_chunk_ids(chunk_ids: list[str]) -> str:
    return f'chunk_id in {json.dumps(chunk_ids, ensure_ascii=False)}'


def _collection_schema_summary(collection: Any) -> dict[str, Any]:
    schema = getattr(collection, "schema", None)
    if schema is None:
        return {"schema_ok": False, "fields": [], "description": None}

    fields: list[dict[str, Any]] = []
    for field in getattr(schema, "fields", []) or []:
        params = getattr(field, "params", None)
        fields.append(
            {
                "name": getattr(field, "name", ""),
                "dtype": _serialize_value(getattr(field, "dtype", None)),
                "is_primary": bool(getattr(field, "is_primary", False)),
                "auto_id": bool(getattr(field, "auto_id", False)),
                "dim": (params or {}).get("dim") if isinstance(params, dict) else None,
                "max_length": (params or {}).get("max_length") if isinstance(params, dict) else None,
            }
        )

    return {
        "schema_ok": bool(fields),
        "description": getattr(schema, "description", None),
        "fields": fields,
    }


def _collection_index_summary(collection: Any) -> list[dict[str, Any]]:
    indexes: list[dict[str, Any]] = []
    for idx in getattr(collection, "indexes", []) or []:
        params = getattr(idx, "params", None)
        indexes.append(
            {
                "field_name": getattr(idx, "field_name", ""),
                "index_name": getattr(idx, "index_name", ""),
                "index_type": getattr(idx, "index_type", ""),
                "metric_type": getattr(idx, "metric_type", ""),
                "params": params if isinstance(params, dict) else _serialize_value(params),
            }
        )
    return indexes


def _stringify_error(exc: BaseException) -> dict[str, Any]:
    return {
        "kind": type(exc).__name__,
        "message": str(exc),
    }


async def _collect_pg_probe(scope_code: str, sample_size: int) -> dict[str, Any]:
    from core.config import get_settings

    result: dict[str, Any] = {
        "enabled": False,
        "connected": False,
        "ready_chunks": None,
        "sample_size": sample_size,
        "sample_chunks": [],
        "errors": [],
        "latency_ms": {},
    }

    settings = get_settings()
    if not settings.postgres_enabled:
        result["errors"].append(
            {
                "stage": "postgres",
                "kind": "NotConfigured",
                "message": "PostgreSQL is not enabled in settings",
            }
        )
        return result

    result["enabled"] = True
    from infrastructure.postgres.pool import close_pool, create_pool_from_settings, open_pool

    pool = create_pool_from_settings()
    start = _now_ms()
    try:
        await open_pool(pool)
        result["latency_ms"]["connect"] = int(round((_now_ms() - start) * 1000))
        result["connected"] = True
    except Exception as exc:
        result["latency_ms"]["connect"] = int(round((_now_ms() - start) * 1000))
        result["errors"].append({"stage": "postgres.connect", **_stringify_error(exc)})
        return result

    try:
        async with pool.connection() as conn:
            from psycopg.rows import dict_row

            conn.row_factory = dict_row
            query = """
                SELECT
                    ch.id::text AS chunk_id,
                    ch.chunk_uid,
                    ch.document_id::text AS document_id,
                    ch.content_sha256,
                    ch.chunk_index,
                    d.title AS document_title,
                    d.status AS document_status,
                    ks.knowledge_scope_code
                FROM library_document_chunks ch
                JOIN library_documents d ON d.id = ch.document_id
                JOIN knowledge_scopes ks ON ks.id = d.knowledge_scope_id
                WHERE ks.knowledge_scope_code = %(scope_code)s
                  AND d.status = 'ready'
                ORDER BY ch.id::text
            """
            start = _now_ms()
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT COUNT(*) AS cnt FROM library_document_chunks ch "
                    "JOIN library_documents d ON d.id = ch.document_id "
                    "JOIN knowledge_scopes ks ON ks.id = d.knowledge_scope_id "
                    "WHERE ks.knowledge_scope_code = %(scope_code)s AND d.status = 'ready'",
                    {"scope_code": scope_code},
                )
                row = await cur.fetchone()
                result["latency_ms"]["count_ready"] = int(round((_now_ms() - start) * 1000))
                result["ready_chunks"] = int(row["cnt"]) if row else 0

                start = _now_ms()
                await cur.execute(query + "LIMIT %(limit)s", {"scope_code": scope_code, "limit": sample_size})
                rows = await cur.fetchall()
                result["latency_ms"]["sample_fetch"] = int(round((_now_ms() - start) * 1000))
                result["sample_chunks"] = [dict(row) for row in rows]
    except Exception as exc:
        result["errors"].append({"stage": "postgres.query", **_stringify_error(exc)})
    finally:
        try:
            await close_pool(pool)
        except Exception:
            pass

    return result


def _collect_milvus_probe(collection_name: str) -> dict[str, Any]:
    from infrastructure.milvus.client import create_connection, close_connection
    from pymilvus import Collection, utility

    result: dict[str, Any] = {
        "host": gv.MILVUS_HOST,
        "port": gv.MILVUS_PORT,
        "collection": collection_name,
        "connected": False,
        "collections": [],
        "collection_exists": False,
        "num_entities": None,
        "schema_ok": False,
        "schema": {"fields": []},
        "indexes": [],
        "loaded": False,
        "load_state": None,
        "latency_ms": {},
        "errors": [],
    }

    start = _now_ms()
    try:
        create_connection()
        result["latency_ms"]["connect"] = int(round((_now_ms() - start) * 1000))
        result["connected"] = True
    except Exception as exc:
        result["latency_ms"]["connect"] = int(round((_now_ms() - start) * 1000))
        result["errors"].append({"stage": "milvus.connect", **_stringify_error(exc)})
        return result

    try:
        start = _now_ms()
        collections = utility.list_collections()
        result["latency_ms"]["list_collections"] = int(round((_now_ms() - start) * 1000))
        result["collections"] = list(collections)
        result["collection_exists"] = collection_name in collections
    except Exception as exc:
        result["errors"].append({"stage": "milvus.list_collections", **_stringify_error(exc)})
        close_connection()
        return result

    if not result["collection_exists"]:
        close_connection()
        return result

    try:
        collection = Collection(collection_name)

        try:
            from pymilvus import utility as milvus_utility

            load_state = milvus_utility.load_state(collection_name)
            result["load_state"] = _serialize_value(load_state)
            result["loaded"] = "Loaded" in str(load_state)
        except Exception as exc:
            result["errors"].append({"stage": "milvus.load_state", **_stringify_error(exc)})

        try:
            start = _now_ms()
            collection.load()
            result["latency_ms"]["load"] = int(round((_now_ms() - start) * 1000))
            result["loaded"] = True
        except Exception as exc:
            result["latency_ms"]["load"] = int(round((_now_ms() - start) * 1000))
            result["errors"].append({"stage": "milvus.load", **_stringify_error(exc)})

        try:
            start = _now_ms()
            result["num_entities"] = int(collection.num_entities)
            result["latency_ms"]["num_entities"] = int(round((_now_ms() - start) * 1000))
        except Exception as exc:
            result["latency_ms"]["num_entities"] = int(round((_now_ms() - start) * 1000))
            result["errors"].append({"stage": "milvus.num_entities", **_stringify_error(exc)})

        try:
            start = _now_ms()
            schema_summary = _collection_schema_summary(collection)
            result["latency_ms"]["describe_collection"] = int(round((_now_ms() - start) * 1000))
            result["schema_ok"] = schema_summary.pop("schema_ok", False)
            result["schema"] = schema_summary
        except Exception as exc:
            result["latency_ms"]["describe_collection"] = int(round((_now_ms() - start) * 1000))
            result["errors"].append({"stage": "milvus.describe_collection", **_stringify_error(exc)})

        try:
            result["indexes"] = _collection_index_summary(collection)
        except Exception as exc:
            result["errors"].append({"stage": "milvus.indexes", **_stringify_error(exc)})
    finally:
        close_connection()

    return result


async def _run_relation_qa_local(
    *,
    conn,
    scope,
    questions: list[str],
) -> list[dict[str, Any]]:
    from modules.library.relation_qa_schemas import RelationQARequest
    from modules.library.relation_qa_service import run_relation_qa

    async def _run_one(question: str) -> dict[str, Any]:
        start = _now_ms()
        response = await run_relation_qa(
            conn,
            RelationQARequest(
                question=question,
                language="auto",
                top_k=20,
                use_ai=False,
                knowledge_scope_code=scope.knowledge_scope_code,
                evidence_depth="standard",
                return_markdown=True,
                debug=False,
            ),
            scope,
        )
        elapsed = int(round((_now_ms() - start) * 1000))
        return {
            "question": question,
            "elapsed_ms": elapsed,
            "used_milvus": response.method.used_milvus,
            "retrieval": response.method.retrieval,
            "warnings": response.warnings,
            "fallback_used": response.method.fallback_used,
            "fallback_reason": response.method.fallback_reason,
            "synthesis_mode": response.method.synthesis_mode,
            "source_count": len(response.sources),
            "source_titles": [source.document_title for source in response.sources[:5]],
        }

    return [await _run_one(question) for question in questions]


async def _collect_roundtrip(
    *,
    pg_probe: dict[str, Any],
    milvus_probe: dict[str, Any],
    collection_name: str,
    scope_code: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "blocked",
        "pg_count": pg_probe.get("ready_chunks"),
        "milvus_count": None,
        "sample_size": pg_probe.get("sample_size"),
        "sample_found": 0,
        "sample_missing": 0,
        "duplicates": 0,
        "mismatches": [],
        "latency_ms": {},
        "errors": [],
    }

    sample = pg_probe.get("sample_chunks") or []
    if not sample:
        result["errors"].append(
            {
                "stage": "roundtrip.sample",
                "kind": "NoSample",
                "message": "PG sample was not available",
            }
        )
        return result

    if not milvus_probe.get("connected") or not milvus_probe.get("collection_exists"):
        result["errors"].append(
            {
                "stage": "roundtrip.milvus",
                "kind": "MilvusUnavailable",
                "message": "Milvus is not connected or the collection does not exist",
            }
        )
        return result

    from pymilvus import Collection

    sample_ids = [row["chunk_id"] for row in sample if row.get("chunk_id")]
    if not sample_ids:
        result["errors"].append(
            {
                "stage": "roundtrip.sample_ids",
                "kind": "EmptySampleIds",
                "message": "Sample chunks did not contain chunk_id values",
            }
        )
        return result

    from infrastructure.milvus.client import close_connection, create_connection

    start = _now_ms()
    try:
        create_connection()
        collection = Collection(collection_name)
        collection.load()
        expr = _query_expr_for_chunk_ids(sample_ids)
        hits = collection.query(
            expr=expr,
            output_fields=["chunk_id", "document_id", "collection_code", "content_sha256", "chunk_index"],
            limit=len(sample_ids) * 4,
        )
        result["latency_ms"]["milvus_query"] = int(round((_now_ms() - start) * 1000))
    except Exception as exc:
        result["latency_ms"]["milvus_query"] = int(round((_now_ms() - start) * 1000))
        result["errors"].append({"stage": "roundtrip.milvus_query", **_stringify_error(exc)})
        try:
            close_connection()
        except Exception:
            pass
        return result
    finally:
        try:
            close_connection()
        except Exception:
            pass

    by_chunk: dict[str, list[dict[str, Any]]] = {}
    for hit in hits:
        cid = str(hit.get("chunk_id") or "")
        if not cid:
            continue
        by_chunk.setdefault(cid, []).append(hit)

    found = 0
    missing = 0
    mismatches: list[dict[str, Any]] = []
    duplicates = 0
    for row in sample:
        cid = row["chunk_id"]
        matches = by_chunk.get(cid, [])
        if not matches:
            missing += 1
            mismatches.append({"chunk_id": cid, "reason": "missing"})
            continue
        found += 1
        if len(matches) > 1:
            duplicates += len(matches) - 1
        hit = matches[0]
        row_mismatch: dict[str, Any] = {"chunk_id": cid, "issues": []}
        if str(hit.get("document_id") or "") != str(row.get("document_id") or ""):
            row_mismatch["issues"].append("document_id")
        if str(hit.get("collection_code") or "") != scope_code:
            row_mismatch["issues"].append("collection_code")
        if str(hit.get("content_sha256") or "") != str(row.get("content_sha256") or ""):
            row_mismatch["issues"].append("content_sha256")
        if row_mismatch["issues"]:
            mismatches.append(row_mismatch)

    result.update(
        {
            "status": "pass" if found == len(sample) and not mismatches and duplicates == 0 else "warn",
            "milvus_count": milvus_probe.get("num_entities"),
            "sample_found": found,
            "sample_missing": missing,
            "duplicates": duplicates,
            "mismatches": mismatches,
        }
    )
    return result


def _search_latency_section(
    *,
    milvus_probe: dict[str, Any],
    collection_name: str,
    scope_code: str,
    queries: list[str],
    top_ks: list[int],
    embedding_model: str,
) -> dict[str, Any]:
    from modules.embeddings.client import embed_text
    from infrastructure.milvus.client import close_connection, create_connection, search_vectors

    result: dict[str, Any] = {
        "status": "blocked",
        "collection": collection_name,
        "scope_code": scope_code,
        "embedding_model": embedding_model,
        "runs": [],
        "errors": [],
        "summary": {},
    }

    if milvus_probe.get("connected") and milvus_probe.get("collection_exists"):
        try:
            create_connection()
        except Exception as exc:
            result["errors"].append(
                {
                    "stage": "milvus.connect_search",
                    "kind": type(exc).__name__,
                    "message": str(exc),
                }
            )
            return result

    for query in queries:
        embedding_ms: int | None = None
        vector: list[float] | None = None
        emb_error: str | None = None
        start = _now_ms()
        try:
            vector = embed_text(query, model=embedding_model)
            embedding_ms = int(round((_now_ms() - start) * 1000))
        except Exception as exc:
            embedding_ms = int(round((_now_ms() - start) * 1000))
            emb_error = f"{type(exc).__name__}: {exc}"
            result["errors"].append(
                {
                    "stage": "embedding",
                    "query": query,
                    "kind": type(exc).__name__,
                    "message": str(exc),
                }
            )

        for top_k in top_ks:
            run: dict[str, Any] = {
                "query": query,
                "top_k": top_k,
                "embedding_ms": embedding_ms,
                "milvus_search_ms": None,
                "total_ms": None,
                "hits": 0,
                "error": emb_error,
            }
            if vector is None or not milvus_probe.get("connected") or not milvus_probe.get("collection_exists"):
                run["error"] = run["error"] or "Milvus unavailable"
                result["runs"].append(run)
                continue

            start = _now_ms()
            try:
                hits = search_vectors(
                    collection_name=collection_name,
                    query_embedding=vector,
                    top_k=top_k,
                    expr=f'collection_code == "{scope_code}"',
                    output_fields=["chunk_id", "document_id", "title", "chunk_index", "content_preview"],
                )
                run["milvus_search_ms"] = int(round((_now_ms() - start) * 1000))
                run["total_ms"] = (embedding_ms or 0) + (run["milvus_search_ms"] or 0)
                run["hits"] = len(hits)
            except Exception as exc:
                run["milvus_search_ms"] = int(round((_now_ms() - start) * 1000))
                run["total_ms"] = (embedding_ms or 0) + (run["milvus_search_ms"] or 0)
                run["error"] = f"{type(exc).__name__}: {exc}"
                result["errors"].append(
                    {
                        "stage": "milvus.search",
                        "query": query,
                        "top_k": top_k,
                        "kind": type(exc).__name__,
                        "message": str(exc),
                    }
                )
            result["runs"].append(run)

    try:
        close_connection()
    except Exception:
        pass

    if result["runs"] and not result["errors"] and any(run["hits"] for run in result["runs"]):
        result["status"] = "pass"
    elif result["runs"]:
        result["status"] = "warn"
    return result


async def _collect_rel_qa_behavior(
    *,
    scope_code: str,
    questions: list[str],
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "blocked",
        "scope_code": scope_code,
        "runs": [],
        "errors": [],
    }

    from core.config import get_settings
    settings = get_settings()
    if not settings.postgres_enabled:
        result["errors"].append(
            {
                "stage": "relation_qa",
                "kind": "NotConfigured",
                "message": "PostgreSQL is not enabled in settings",
            }
        )
        return result

    from infrastructure.postgres.pool import close_pool, create_pool_from_settings, open_pool
    from modules.library.repository import get_scope_by_code

    pool = create_pool_from_settings()
    try:
        await open_pool(pool)
    except Exception as exc:
        result["errors"].append({"stage": "relation_qa.pg_connect", **_stringify_error(exc)})
        return result

    try:
        async with pool.connection() as conn:
            scope = await get_scope_by_code(conn, scope_code)
            if scope is None:
                result["errors"].append(
                    {
                        "stage": "relation_qa.scope",
                        "kind": "ScopeNotFound",
                        "message": f"Knowledge scope '{scope_code}' was not found",
                    }
                )
                return result

            result["runs"] = await _run_relation_qa_local(conn=conn, scope=scope, questions=questions)
            result["status"] = "warn" if result["runs"] else "blocked"
    except Exception as exc:
        result["errors"].append({"stage": "relation_qa.run", **_stringify_error(exc)})
    finally:
        try:
            await close_pool(pool)
        except Exception:
            pass

    return result


def _markdown_lines(report: dict[str, Any]) -> list[str]:
    lines = [
        "# Milvus 2.6 acid validation",
        "",
        f"- Milvus collection: `{report['milvus']['collection']}`",
        f"- Scope code: `{report['pg'].get('scope_code', 'breslov_primary')}`",
        f"- Milvus connected: `{report['milvus']['connected']}`",
        f"- PG connected: `{report['pg']['connected']}`",
        "",
        "## Milvus",
        f"- collections: {len(report['milvus'].get('collections', []))}",
        f"- collection_exists: {report['milvus'].get('collection_exists')}",
        f"- num_entities: {report['milvus'].get('num_entities')}",
        f"- loaded: {report['milvus'].get('loaded')}",
        "",
        "## PG",
        f"- ready_chunks: {report['pg'].get('ready_chunks')}",
        f"- sample_size: {report['pg'].get('sample_size')}",
        "",
        "## Round-trip",
        f"- status: {report['roundtrip'].get('status')}",
        f"- sample_found: {report['roundtrip'].get('sample_found')}",
        f"- sample_missing: {report['roundtrip'].get('sample_missing')}",
        f"- duplicates: {report['roundtrip'].get('duplicates')}",
        "",
        "## Search latency",
        f"- status: {report['search_latency'].get('status')}",
        f"- runs: {len(report['search_latency'].get('runs', []))}",
        "",
        "## Relation QA fallback",
        f"- status: {report['relation_qa'].get('status')}",
        f"- runs: {len(report['relation_qa'].get('runs', []))}",
    ]
    if report.get("errors"):
        lines += ["", "## Errors"]
        for err in report["errors"]:
            lines.append(f"- {err['stage']}: {err['kind']} - {err['message']}")
    return lines


async def _build_report(args: argparse.Namespace) -> dict[str, Any]:
    pg_probe = await _collect_pg_probe(args.scope_code, args.sample_size)
    milvus_probe = _collect_milvus_probe(args.collection)
    roundtrip_probe = await _collect_roundtrip(
        pg_probe=pg_probe,
        milvus_probe=milvus_probe,
        collection_name=args.collection,
        scope_code=args.scope_code,
    )
    search_latency = _search_latency_section(
        milvus_probe=milvus_probe,
        collection_name=args.collection,
        scope_code=args.scope_code,
        queries=args.queries,
        top_ks=args.top_ks,
        embedding_model=args.embedding_model,
    )
    relation_qa = await _collect_rel_qa_behavior(
        scope_code=args.scope_code,
        questions=args.relation_qa_questions,
    )

    report = {
        "milvus": milvus_probe,
        "pg": {**pg_probe, "scope_code": args.scope_code},
        "roundtrip": roundtrip_probe,
        "search_latency": search_latency,
        "relation_qa": relation_qa,
        "errors": [
            *milvus_probe.get("errors", []),
            *pg_probe.get("errors", []),
            *roundtrip_probe.get("errors", []),
            *search_latency.get("errors", []),
            *relation_qa.get("errors", []),
        ],
    }
    return report


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Milvus 2.6 acid validation probe")
    parser.add_argument("--collection", default=gv.MILVUS_COLLECTION_BRESLOV)
    parser.add_argument("--scope-code", default="breslov_primary")
    parser.add_argument("--sample-size", type=int, default=20)
    parser.add_argument("--embedding-model", default=gv.EMBEDDINGS_MODEL_ALIAS)
    parser.add_argument("--top-ks", default="5,10,20,50")
    parser.add_argument("--queries", nargs="*", default=DEFAULT_QUERIES)
    parser.add_argument(
        "--relation-qa-questions",
        nargs="*",
        default=DEFAULT_RELATION_QUESTIONS,
    )
    parser.add_argument("--output-json")
    parser.add_argument("--output-md")
    return parser.parse_args(argv)


def main() -> int:
    args = _parse_args()
    args.top_ks = [int(item) for item in str(args.top_ks).split(",") if item.strip()]
    report = asyncio.run(_build_report(args))

    if args.output_json:
        path = Path(args.output_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    else:
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))

    if args.output_md:
        path = Path(args.output_md)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(_markdown_lines(report)) + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
