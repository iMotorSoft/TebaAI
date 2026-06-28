"""Library HTTP routes."""

from __future__ import annotations

from litestar import Request, post
from litestar.exceptions import HTTPException

from core.dependencies import get_pg_pool
from infrastructure.postgres.transaction import transaction
from modules.auth.guards import require_auth
from modules.library.schemas import (
    LibrarySearchRequest,
    LibrarySearchResponse,
    LibrarySearchResult,
)
from modules.library.text_search import search_chunks_text


@post("/library/search", guards=[require_auth])
async def library_search(
    request: Request,
    data: LibrarySearchRequest,
) -> LibrarySearchResponse:
    pool = await get_pg_pool(request)

    try:
        async with transaction(pool) as conn:
            raw_results = await search_chunks_text(
                conn,
                collection_code=data.collection,
                query=data.query,
                top_k=data.top_k,
                mode=data.mode,
                language=data.language,
            )
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Search failed: {exc}"
        ) from exc

    results = [
        LibrarySearchResult(
            document_id=r["document_id"],
            document_title=r.get("document_title", ""),
            author=r.get("author"),
            collection_code=r.get("collection_code", data.collection),
            chunk_id=r["chunk_id"],
            chunk_index=r["chunk_index"],
            language=r.get("language"),
            page_start=r.get("page_start"),
            page_end=r.get("page_end"),
            chapter=r.get("chapter"),
            section=r.get("section"),
            match_type=r.get("match_type", "fts"),
            rank=r.get("rank"),
            plain_excerpt=r.get("plain_excerpt"),
            highlighted_excerpt=r.get("highlighted_excerpt", ""),
            content_length=r.get("content_length", 0),
        )
        for r in raw_results
    ]

    return LibrarySearchResponse(
        query=data.query,
        collection=data.collection,
        mode=data.mode,
        language=data.language,
        total=len(results),
        results=results,
    )
