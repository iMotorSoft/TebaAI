"""Read-only viewer/source smoke for document C.

Confirms that the viewer is still attached to the ACTIVE generation, that the
source endpoint resolves the managed PDF, and that textual retrieval identity is
unchanged (chunk content digest).
"""
from __future__ import annotations

import asyncio
import hashlib

import certlib as c


async def db_view() -> dict:
    async with await c.connect_readonly() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT ap.logical_document_id, ap.generation_id, ap.operation,
                       g.status, g.document_id, g.run_id
                FROM library_logical_document_active_generations ap
                JOIN library_document_generations g ON g.id=ap.generation_id
                WHERE ap.logical_document_id=%s
                """,
                (c.LOGICAL_DOCUMENT_ID,),
            )
            pointer = await cur.fetchone()
            await cur.execute(
                """
                SELECT count(*) AS chunks,
                       md5(COALESCE(string_agg(content_sha256, '' ORDER BY id), '')) AS content_digest
                FROM library_document_chunks WHERE document_id=%s
                """,
                (c.DOCUMENT_ID,),
            )
            chunks = await cur.fetchone()
    return {"active_pointer": pointer, "chunks": chunks}


def main() -> None:
    state = asyncio.run(db_view())
    before = c.load_json("current-c-before.json")
    session = asyncio.run(c.mint_access_token_readonly())
    token = session.pop("token", None)

    pages = {}
    for page in (1, 187, 284):
        raw = c.http_get(
            f"{c.BASE_URL}/library/documents/{c.DOCUMENT_ID}/pages/{page}/publication",
            token=token,
        )
        body = raw.get("body") or b""
        pages[page] = {
            "status": raw.get("status"),
            "body_sha256": hashlib.sha256(body).hexdigest() if body else None,
            "body_bytes": len(body),
            "body_preview": body[:160].decode("utf-8", "replace") if raw.get("status") == 200 else None,
        }
    session.pop("token", None)

    source = c.http_get(c.SOURCE_URL, token=token)
    source_body = source.get("body") or b""
    source_ok = (
        source.get("status") == 200
        and hashlib.sha256(source_body).hexdigest() == c.APPROVED_SHA256
    )

    pointer = state["active_pointer"]
    pointer_generation = str(pointer["generation_id"]) if pointer else None
    chunks_unchanged = state["chunks"]["content_digest"] == before["chunks"]["content_digest"]

    payload = {
        "measured_at": c.now(),
        "document_id": str(c.DOCUMENT_ID),
        "logical_document_id": str(c.LOGICAL_DOCUMENT_ID),
        "viewer_active_pointer": pointer,
        "viewer_generation_id": pointer_generation,
        "viewer_generation_is_expected_active": pointer_generation == c.ACTIVE_GENERATION,
        "viewer_generation_status": pointer["status"] if pointer else None,
        "page_publication_responses": pages,
        "page_publication_all_200": all(item["status"] == 200 for item in pages.values()),
        "page_publication_note": (
            "region publication metadata is optional for C; 404 here means no "
            "layout region_publication is stored, not that the source is unavailable"
        ),
        "source_endpoint_resolves_pdf": source_ok,
        "source_endpoint_status": source.get("status"),
        "chunks_now": state["chunks"],
        "chunks_before": before["chunks"],
        "textual_retrieval_identity_unchanged": chunks_unchanged,
        "read_only": True,
        "token_persisted": False,
    }
    payload["VIEWER_SOURCE_SMOKE"] = (
        "PASS"
        if (
            payload["viewer_generation_is_expected_active"]
            and payload["viewer_generation_status"] == "ACTIVE"
            and payload["source_endpoint_resolves_pdf"]
            and payload["textual_retrieval_identity_unchanged"]
        )
        else "FAIL"
    )
    c.write_json("viewer-source-smoke.json", payload)
    print(
        f"viewer generation={pointer_generation} pages_all_200="
        f"{payload['page_publication_all_200']} textual_unchanged={chunks_unchanged} -> "
        f"{payload['VIEWER_SOURCE_SMOKE']}"
    )


if __name__ == "__main__":
    main()
