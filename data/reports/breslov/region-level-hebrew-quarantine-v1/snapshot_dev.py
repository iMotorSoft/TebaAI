"""Read-only DEV snapshots. No E2E records are created by this script.

Run from backend with one argument: before / after / after-cleanup.
SQL is delegated to the existing infrastructure inventory, in a read-only
transaction. No reset/apply/flush/load/start/stop method is invoked.
"""
import asyncio
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "SrvRestAstroLS_v1/backend"))
import globalVar as g
from infrastructure.postgres.dev_content_reset import pg_inventory
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from pymilvus import MilvusClient


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


async def main(label):
    if g.TEBAAI_ENV != "development" or g.POSTGRES_HOST not in {"127.0.0.1", "localhost"}:
        raise RuntimeError("Only local DEV inventory is allowed")
    if g.MILVUS_HOST not in {"127.0.0.1", "localhost"}:
        raise RuntimeError("Only local DEV Milvus inventory is allowed")
    result = {"scope": "Read-only snapshot; no controlled worker E2E was run", "test_ids": [],
              "isolated_records_created": False}
    async with await AsyncConnection.connect(g.POSTGRES_DSN, row_factory=dict_row, connect_timeout=5) as conn:
        await conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        pg = await pg_inventory(conn)
        result["postgres"] = {"database": pg["identity"]["db"],
            "tables": {name: {"count": row["count"], "sha256": row["sha256"]}
                       for name, row in pg["tables"].items() if name in {
                           "library_documents", "library_document_texts", "library_document_chunks",
                           "library_pages_v2", "library_chunk_embeddings", "content_manager_jobs"}},
            "schema_sha256": pg["schema_sha256"]}
    client = MilvusClient(uri=f"http://{g.MILVUS_HOST}:{g.MILVUS_PORT}")
    try:
        result["milvus"] = {}
        for name in (g.MILVUS_COLLECTION_BRESLOV, g.CONTENT_MANAGER_E2E_COLLECTION):
            if name not in client.list_collections(timeout=10):
                result["milvus"][name] = {"exists": False}
                continue
            state = str(client.get_load_state(name, timeout=10)["state"])
            if not state.endswith("Loaded"):
                result["milvus"][name] = {"state": state, "live_inventory": "NOT_RUN_UNLOADED"}
                continue
            rows = []
            iterator = client.query_iterator(collection_name=name, filter="", batch_size=500,
                output_fields=["pk", "chunk_id", "document_id"], consistency_level="Strong", timeout=20)
            try:
                while batch := iterator.next():
                    rows.extend(dict(r) for r in batch)
            finally:
                iterator.close()
            rows.sort(key=lambda r: str(r["pk"]))
            result["milvus"][name] = {"state": state, "live_count": len(rows),
                                      "identity_sha256": digest(rows)}
    finally:
        client.close()
    path = Path(__file__).with_name(f"dev-store-{label}.json")
    path.write_text(json.dumps(result, indent=2, default=str) + "\n")
    print(path.name, "READ_ONLY_SNAPSHOT_OK")


if __name__ == "__main__":
    label = sys.argv[1]
    if label not in {"before", "after", "after-cleanup"}:
        raise ValueError("Invalid snapshot label")
    asyncio.run(main(label))
