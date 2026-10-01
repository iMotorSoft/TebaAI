"""Read-only comparison of canonical DEV pages, chunks and derived vectors."""
import asyncio
import hashlib
import json
from pathlib import Path
import sys

OUTPUT = Path(__file__).resolve().parent
BACKEND = OUTPUT.parents[3] / "SrvRestAstroLS_v1" / "backend"
sys.path.insert(0, str(BACKEND))
import globalVar
import psycopg
from psycopg.rows import dict_row
from pymilvus import MilvusClient


def save(name, data):
    (OUTPUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2))


async def main():
    assert globalVar.TEBAAI_ENV == "development"
    comparisons = []
    client = MilvusClient(uri=f"http://{globalVar.MILVUS_HOST}:{globalVar.MILVUS_PORT}", timeout=15)
    async with await psycopg.AsyncConnection.connect(globalVar.POSTGRES_DSN, row_factory=dict_row) as conn:
        await conn.execute("SET TRANSACTION READ ONLY")
        for case, page in [("a", 187), ("b", 416)]:
            if "--case=a" in sys.argv and case != "a":
                continue
            job = json.loads((OUTPUT / f"{case}-job-final.json").read_text())
            document_id = job["document_id"]
            stored = await (await conn.execute(
                "SELECT page_number,text FROM library_pages_v2 WHERE document_id=%s AND page_number=%s",
                (document_id, page),
            )).fetchone()
            canonical = (OUTPUT / f"{case}-canonical.md").read_text()
            assert stored["text"] == canonical
            save(f"{case}-pg-after.json", stored)
            rows = await (await conn.execute(
                "SELECT id::text,chunk_uid,page_start,page_end,content,content_sha256 FROM library_document_chunks WHERE document_id=%s AND page_start=%s ORDER BY chunk_index",
                (document_id, page),
            )).fetchall()
            assert rows
            save(f"{case}-chunks.json", rows)
            (OUTPUT / f"{case}-chunk-final.txt").write_text("\n\n".join(row["content"] for row in rows))
            vectors = client.get(globalVar.CONTENT_MANAGER_E2E_COLLECTION, ids=[row["chunk_uid"] for row in rows],
                output_fields=["chunk_id", "document_id", "content_sha256", "content_preview", "page_start", "page_end"], timeout=15)
            save(f"{case}-milvus.json", [dict(row) for row in vectors])
            assert len(vectors) == len(rows)
            by_id = {row["id"]: row for row in rows}
            for vector in vectors:
                row = by_id[vector["chunk_id"]]
                assert vector["content_sha256"] == row["content_sha256"]
                assert vector["page_start"] == page == vector["page_end"]
                assert row["content"].startswith(vector["content_preview"])
                assert len(vector["content_preview"].encode("utf-8")) <= 1024
            comparisons.append({"case": case, "pdf_page": page, "document_id": document_id,
                "canonical_equals_PG_page": True, "canonical_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
                "chunks": len(rows), "vectors": len(vectors), "vector_metadata_and_preview_match_PG": True})
        ready = await (await conn.execute(
            "SELECT d.id::text document_id,d.source_sha256,d.status,t.content_sha256 FROM library_documents d JOIN library_document_texts t ON t.document_id=d.id WHERE d.status='ready' ORDER BY d.id,t.id"
        )).fetchall()
        chunks = await (await conn.execute(
            "SELECT c.id::text,c.content_sha256 FROM library_document_chunks c JOIN library_documents d ON d.id=c.document_id WHERE d.status='ready' ORDER BY c.id"
        )).fetchall()
        snapshot = {"ready_documents": ready, "ready_chunks": len(chunks),
            "ready_chunk_fingerprint": hashlib.sha256(json.dumps(chunks, sort_keys=True).encode()).hexdigest()}
        baseline = json.loads((OUTPUT / "ready-baseline.json").read_text())
        assert snapshot == baseline
        save("ready-after.json", snapshot)
        unrelated = await (await conn.execute(
            "SELECT status,current_stage FROM content_manager_jobs WHERE id='7702b865-bfde-4b2c-b752-8156d43c36f1'"
        )).fetchone()
        assert unrelated == {"status": "queued", "current_stage": "queued"}
        save("storage-comparison-a.json" if "--case=a" in sys.argv else "storage-comparison.json", {"cases": comparisons, "ready_corpus_unchanged": True, "unrelated_job_unchanged": True})
    print(json.dumps(comparisons))


asyncio.run(main())
