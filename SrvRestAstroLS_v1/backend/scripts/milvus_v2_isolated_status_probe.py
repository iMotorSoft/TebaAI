#!/usr/bin/env python3
"""Read-only Milvus state probe. It deliberately never calls Collection.load()."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import psycopg
from pymilvus import Collection, connections, utility

from globalVar import MILVUS_CONNECT_TIMEOUT_SECONDS, MILVUS_HOST, MILVUS_PORT

DEFAULTS = [
    "tebaai_breslov_chunks_v1",
    "tebaai_breslov_test_chunks_v1",
    "tebaai_breslov_bookqa_v2_kitzur_test_pages_v1",
]


def _json(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_json(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _json(v) for k, v in value.items()}
    return str(value)


def inspect_collection(name: str, collections: set[str], limit: int) -> dict[str, Any]:
    row: dict[str, Any] = {"collection": name, "collection_exists": name in collections}
    if name not in collections:
        row.update({"status": "COLLECTION_NOT_FOUND", "load_state": "unknown", "query_sample_ok": "skipped", "search_ok": "skipped"})
        return row
    try:
        col = Collection(name=name)  # metadata object only; no load()
        state = utility.load_state(name)
        fields = []
        vector_field = None
        vector_dim = None
        for field in col.schema.fields:
            item = {"name": field.name, "dtype": str(field.dtype), "primary": field.is_primary, "params": _json(field.params)}
            fields.append(item)
            if field.name == "embedding" or "VECTOR" in str(field.dtype) or "dim" in (field.params or {}):
                vector_field = field.name
                vector_dim = (field.params or {}).get("dim")
        indexes = [{"field_name": idx.field_name, "params": _json(idx.params)} for idx in col.indexes]
        loaded = str(state).casefold().endswith("loaded") or str(state).casefold() == "loaded"
        sample = None
        query_ok: str | bool = "skipped"
        if loaded:
            scalar_fields = [field.name for field in col.schema.fields if field.name != vector_field]
            try:
                sample = col.query(expr="pk != ''", output_fields=scalar_fields, limit=limit)
                query_ok = True
            except Exception as exc:
                query_ok = False
                row["query_error"] = f"{type(exc).__name__}: {exc}"
        row.update({
            "status": "READY_METADATA" if loaded else "EXISTS_NOT_LOADED",
            "load_state": str(state), "num_entities": col.num_entities,
            "fields": fields, "vector_field": vector_field, "vector_dim": vector_dim,
            "indexes": indexes, "index_exists": bool(indexes),
            "query_sample_ok": "skipped" if not loaded else query_ok,
            "metadata_sample": _json(sample) if sample is not None else None,
            "search_ok": "skipped" if not loaded else "skipped_no_query_vector",
            "limit": limit,
        })
    except Exception as exc:
        row.update({"status": "METADATA_ERROR", "error": f"{type(exc).__name__}: {exc}", "query_sample_ok": "skipped", "search_ok": "skipped"})
    return row


def postgres_expected(run_id: str | None, scope: str | None) -> dict[str, Any]:
    result: dict[str, Any] = {"run_id_requested": run_id, "scope_requested": scope}
    conf = {"user": os.environ["DB_PG_USER"], "password": os.environ["DB_PG_PASS"], "host": os.environ.get("DB_PG_IP", "localhost"), "port": int(os.environ.get("DB_PG_PORT", "5432")), "dbname": "tebaai"}
    with psycopg.connect(**conf) as conn, conn.cursor() as cur:
        if run_id:
            cur.execute("SELECT document_id::text, scope_code, status, pipeline_version FROM library_ingestion_runs_v2 WHERE run_id=%s", (run_id,))
            run = cur.fetchone()
            result["run"] = {"document_id": run[0], "scope_code": run[1], "status": run[2], "pipeline_version": run[3]} if run else None
            if run:
                cur.execute("SELECT count(*) FROM library_pages_v2 WHERE run_id=%s", (run_id,))
                result["v2_pages"] = cur.fetchone()[0]
                cur.execute("SELECT count(*) FROM library_concept_mentions_v2 WHERE run_id=%s", (run_id,))
                result["v2_concept_mentions"] = cur.fetchone()[0]
        if scope:
            cur.execute("SELECT id::text, knowledge_scope_code FROM knowledge_scopes WHERE knowledge_scope_code=%s", (scope,))
            scope_row = cur.fetchone()
            result["knowledge_scope"] = {"id": scope_row[0], "code": scope_row[1]} if scope_row else None
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", action="append", default=[])
    parser.add_argument("--scope", default="breslov_primary")
    parser.add_argument("--run-id")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--json-out", type=Path, required=True)
    args = parser.parse_args()
    names = list(dict.fromkeys(args.collection or DEFAULTS))
    report: dict[str, Any] = {"connection_ok": False, "host": MILVUS_HOST, "port": MILVUS_PORT, "collections": [], "postgres_expected": None, "errors": []}
    try:
        connections.connect(alias="milvus_status_probe", host=MILVUS_HOST, port=MILVUS_PORT, timeout=MILVUS_CONNECT_TIMEOUT_SECONDS)
        # pymilvus utility APIs use the default alias, so connect it only for this read-only process.
        connections.connect(alias="default", host=MILVUS_HOST, port=MILVUS_PORT, timeout=MILVUS_CONNECT_TIMEOUT_SECONDS)
        report["connection_ok"] = True
        all_collections = set(utility.list_collections())
        report["all_collections"] = sorted(all_collections)
        report["collections"] = [inspect_collection(name, all_collections, args.limit) for name in names]
    except Exception as exc:
        report["errors"].append(f"milvus_connection_or_metadata:{type(exc).__name__}:{exc}")
    finally:
        try:
            connections.disconnect("default")
            connections.disconnect("milvus_status_probe")
        except Exception:
            pass
    try:
        report["postgres_expected"] = postgres_expected(args.run_id, args.scope)
    except Exception as exc:
        report["errors"].append(f"postgres_read_only:{type(exc).__name__}:{exc}")
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    args.json_out.with_name("collections.json").write_text(json.dumps(report.get("collections", []), ensure_ascii=False, indent=2))
    args.json_out.with_name("schema.json").write_text(json.dumps({item.get("collection"): {"fields": item.get("fields", []), "indexes": item.get("indexes", [])} for item in report.get("collections", [])}, ensure_ascii=False, indent=2))
    args.json_out.with_name("postgres_expected.json").write_text(json.dumps(report.get("postgres_expected"), ensure_ascii=False, indent=2))
    args.json_out.with_name("probe_errors.log").write_text("\n".join(report.get("errors", [])) + ("\n" if report.get("errors") else ""))
    print(json.dumps({"connection_ok": report["connection_ok"], "collections": [(x["collection"], x["status"]) for x in report["collections"]], "errors": report["errors"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
