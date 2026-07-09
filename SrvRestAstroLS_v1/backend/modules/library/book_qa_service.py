"""Book QA V2 service — discovery + SQL-only answers."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from psycopg import AsyncConnection

from modules.library.book_qa_schemas import (
    BookQAEvidenceSummary,
    BookQAMethod,
    BookQAResponse,
    BookQARunSummary,
    BookQASource,
)

SNIPPET_CHARS = 400


def classify(question: str) -> tuple[str, str | None, str | None]:
    q = question.strip().rstrip("¿?!.")
    if '"' in q or "'" in q or re.search(r"busc[áa] la frase|busca la frase|d[oó]nde dice|aparece la frase", q, re.I):
        m = re.search(r'["\']([^"\']+)["\']', q)
        return "phrase_lookup", (m.group(1) if m else q), None
    for pat in [
        r"(?:relaci[oó]n|relacion)\s+entre\s+(.+?)\s+y\s+(.+)$",
        r"(?:c[oó]mo\s+se\s+(?:relacionan|conectan))\s+(.+?)\s+y\s+(.+)$",
        r"(?:qu[eé]\s+(?:relaci[oó]n|conexi[oó]n)\s+(?:hay|existe))\s+entre\s+(.+?)\s+y\s+(.+)$",
        r"(.{3,30}?)\s+y\s+(.{3,30})$",
    ]:
        m = re.search(pat, q, re.I)
        if m:
            a, b = m.group(1).strip().lower(), m.group(2).strip().lower()
            if len(a) > 2 and len(b) > 2:
                return "relation_lookup", a, b
    for pat in [
        r"(?:d[oó]nde\s+(?:aparece|est[áa]|dice|habla))\s+(?:de\s+|del\s+|la\s+|el\s+)?(.+?)$",
        r"(?:qu[eé]\s+(?:dice|aparece|enseña))\s+(?:sobre\s+)?(.+?)$",
        r"(?:en\s+qu[eé]\s+(?:p[áa]ginas|secci[oó]n))\s+(?:aparece\s+)?(.+?)$",
    ]:
        m = re.search(pat, q, re.I)
        if m:
            c = m.group(1).strip().lower()
            if len(c) > 2:
                return "concept_lookup", c, None
    return "concept_lookup", q[:30], None


def _v(row, idx=0):
    if row is None:
        return None
    if isinstance(row, dict):
        keys = list(row.keys())
        return row[keys[idx]]
    return row[idx]


# ── Helpers (avoiding circular imports) ────────────────────────────────────


def _missing_run_id() -> BookQAResponse:
    return BookQAResponse(
        question="", answer_type="no_evidence",
        warnings=["missing_run_id_or_document_id"],
    )


def _run_not_found(rid_or_doc: str) -> BookQAResponse:
    return BookQAResponse(
        question="", answer_type="no_evidence",
        warnings=["book_qa_run_not_found"],
    )


# ── Discovery ──────────────────────────────────────────────────────────────


async def list_book_qa_runs(
    conn: AsyncConnection,
    scope_code: str | None = None,
    document_id: str | None = None,
    status_filter: str | None = None,
    limit: int = 20,
) -> list[BookQARunSummary]:
    clauses = ["1=1"]
    params: list[Any] = []
    if scope_code:
        clauses.append("r.scope_code = %s"); params.append(scope_code)
    if document_id:
        clauses.append("r.document_id::text = %s"); params.append(document_id)
    if status_filter:
        clauses.append("r.status = ANY(%s)"); params.append(status_filter.split(","))
    else:
        clauses.append("r.status != 'failed'")

    sql = f"""
        SELECT r.run_id::text, r.document_id::text, r.scope_code, r.pipeline_version,
               r.status, r.created_at, r.finished_at,
               (SELECT count(*) FROM library_pages_v2 p WHERE p.run_id = r.run_id) AS pages_count,
               (SELECT count(*) FROM library_pages_v2 p WHERE p.run_id = r.run_id AND p.char_count > 0) AS pages_with_text,
               (SELECT count(*) FROM library_concept_mentions_v2 c WHERE c.run_id = r.run_id) AS concepts_count,
               (SELECT count(*) FROM library_source_references_v2 s WHERE s.run_id = r.run_id) AS src_count,
               (SELECT count(*) FROM library_internal_relations_v2 i WHERE i.run_id = r.run_id) AS rel_count,
               (SELECT count(*) FROM library_document_wiki_v2 w WHERE w.run_id = r.run_id) AS wiki_count
        FROM library_ingestion_runs_v2 r
        WHERE {' AND '.join(clauses)}
        ORDER BY r.finished_at DESC NULLS LAST, r.created_at DESC
        LIMIT %s
    """
    params.append(limit)
    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        rows = await cur.fetchall()
        results = []
        for r in rows:
            results.append(BookQARunSummary(
                run_id=str(_v(r, 0)),
                document_id=str(_v(r, 1)),
                scope_code=_v(r, 2) or "",
                pipeline_version=_v(r, 3) or "",
                status=_v(r, 4) or "",
                created_at=_v(r, 5),
                finished_at=_v(r, 6),
                pages_count=_v(r, 7) or 0,
                pages_with_text=_v(r, 8) or 0,
                concept_mentions_count=_v(r, 9) or 0,
                source_references_count=_v(r, 10) or 0,
                internal_relations_count=_v(r, 11) or 0,
                wiki_exists=(_v(r, 12) or 0) > 0,
            ))
        return results


async def get_latest_book_qa_run(
    conn: AsyncConnection,
    scope_code: str | None = None,
    document_id: str | None = None,
    pipeline_version: str | None = None,
) -> BookQARunSummary | None:
    clauses = ["r.status != 'failed'"]
    params: list[Any] = []
    if scope_code:
        clauses.append("r.scope_code = %s"); params.append(scope_code)
    if document_id:
        clauses.append("r.document_id::text = %s"); params.append(document_id)
    if pipeline_version:
        clauses.append("r.pipeline_version = %s"); params.append(pipeline_version)

    sql = f"""
        SELECT r.run_id::text FROM library_ingestion_runs_v2 r
        WHERE {' AND '.join(clauses)}
        ORDER BY r.finished_at DESC NULLS LAST, r.created_at DESC LIMIT 1
    """
    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        row = await cur.fetchone()
        if not row:
            return None
        rid = str(_v(row, 0))
        runs = await list_book_qa_runs(conn, limit=1, scope_code="")
        # Filter by run_id manually
        for r in runs:
            if r.run_id == rid:
                return r
        return None


async def resolve_run(
    conn: AsyncConnection,
    run_id: str | None = None,
    document_id: str | None = None,
    scope_code: str | None = None,
) -> tuple[str, str, str, list[str]]:
    """Resolve run_id from explicit id or latest by document_id."""
    warnings: list[str] = []
    resolved_run_id = run_id
    resolved_doc_id = document_id or ""

    if resolved_run_id:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT document_id::text, status FROM library_ingestion_runs_v2 WHERE run_id = %s",
                (resolved_run_id,),
            )
            row = await cur.fetchone()
            if not row:
                return "", "", [], ["book_qa_run_not_found"]
            resolved_doc_id = _v(row, 0) or ""
            if _v(row, 1) == "failed":
                return "", "", [], ["book_qa_run_not_usable"]
    elif document_id:
        latest = await get_latest_book_qa_run(conn, scope_code=scope_code, document_id=document_id)
        if not latest:
            return "", "", [], ["book_qa_run_not_found"]
        resolved_run_id = latest.run_id
        resolved_doc_id = latest.document_id
        warnings.append(f"run_resolved_by_document_id: {resolved_run_id[:12]}...")
    else:
        return "", "", [], ["missing_run_id_or_document_id"]

    return resolved_run_id, resolved_doc_id, scope_code or "", warnings


# ── QA Answer ──────────────────────────────────────────────────────────────


async def run_book_qa(
    conn: AsyncConnection,
    question: str,
    run_id: str | None = None,
    document_id: str | None = None,
    scope_code: str = "breslov_test",
    top_k: int = 8,
    options: Any | None = None,
) -> BookQAResponse:
    # Resolve run
    resolved_run_id, resolved_doc_id, resolved_scope, resolve_warnings = await resolve_run(
        conn, run_id, document_id, scope_code,
    )
    if not resolved_run_id:
        resp = _missing_run_id() if not run_id and not document_id else _run_not_found(run_id or document_id or "")
        resp.warnings = resolve_warnings
        return resp

    rid = resolved_run_id
    route, a, b = classify(question)
    sources: list[BookQASource] = []
    seen_pages: set[int] = set()
    warnings = list(resolve_warnings)
    doc_id = resolved_doc_id

    # Check options
    opt = options or {}
    if opt.get("allow_milvus"):
        warnings.append("milvus_disabled_in_sql_only_endpoint")
    if opt.get("allow_ai_synthesis"):
        warnings.append("ai_synthesis_disabled_in_sql_only_endpoint")

    async with conn.cursor() as cur:
        # Validate run exists
        await cur.execute(
            "SELECT document_id::text, status FROM library_ingestion_runs_v2 WHERE run_id = %s",
            (rid,),
        )
        row = await cur.fetchone()
        if not row:
            return BookQAResponse(question=question, warnings=["book_qa_run_not_found"])
        doc_id = _v(row, 0) or doc_id

        # Check scope mismatch
        if scope_code:
            await cur.execute("SELECT scope_code FROM library_ingestion_runs_v2 WHERE run_id = %s", (rid,))
            rr = await cur.fetchone()
            if rr and scope_code != _v(rr):
                warnings.append(f"book_qa_scope_mismatch: requested {scope_code}, run has {_v(rr)}")

        # Concept lookup
        if route == "concept_lookup" and a:
            await cur.execute(
                "SELECT p.page_number, substring(p.text, greatest(position(%s in lower(p.text)) - 80, 1), %s) "
                "FROM library_pages_v2 p WHERE p.run_id = %s AND lower(p.text) LIKE %s "
                "ORDER BY p.page_number LIMIT %s",
                (a, SNIPPET_CHARS, rid, f"%{a}%", top_k),
            )
            for r in await cur.fetchall():
                pg = _v(r, 0)
                if pg not in seen_pages:
                    seen_pages.add(pg)
                    sources.append(BookQASource(
                        page_number=pg, evidence_type="concept", score=0.9,
                        snippet=(_v(r, 1) or "")[:SNIPPET_CHARS].replace("\n", " ").strip(),
                        matched_terms=[a],
                    ))
            if not sources:
                warnings.append(f"concept_not_found: '{a}'")

        # Phrase lookup
        if route == "phrase_lookup":
            phrase = a or question
            await cur.execute(
                "SELECT p.page_number, substring(p.text, greatest(position(%s in lower(p.text)) - 80, 1), %s) "
                "FROM library_pages_v2 p WHERE p.run_id = %s AND lower(p.text) LIKE %s "
                "ORDER BY p.page_number LIMIT %s",
                (phrase, SNIPPET_CHARS, rid, f"%{phrase}%", top_k),
            )
            for r in await cur.fetchall():
                pg = _v(r, 0)
                if pg not in seen_pages:
                    seen_pages.add(pg)
                    sources.append(BookQASource(
                        page_number=pg, evidence_type="literal", score=1.0,
                        snippet=(_v(r, 1) or "")[:SNIPPET_CHARS].replace("\n", " ").strip(),
                        matched_terms=[phrase[:40]],
                    ))
            if not sources:
                tokens = [t for t in re.findall(r"\w{4,}", phrase.lower()) if t not in ("que", "para", "con", "por")]
                for token in tokens[:3]:
                    await cur.execute(
                        "SELECT p.page_number, substring(p.text, greatest(position(%s in lower(p.text)) - 80, 1), 300) "
                        "FROM library_pages_v2 p WHERE p.run_id = %s AND lower(p.text) LIKE %s ORDER BY p.page_number LIMIT 3",
                        (token, rid, f"%{token}%"),
                    )
                    for r in await cur.fetchall():
                        pg = _v(r, 0)
                        if pg not in seen_pages:
                            seen_pages.add(pg)
                            sources.append(BookQASource(
                                page_number=pg, evidence_type="partial_phrase", score=0.5,
                                snippet=(_v(r, 1) or "")[:300].replace("\n", " ").strip(),
                                matched_terms=[token],
                            ))
                if not sources:
                    warnings.append(f"phrase_not_found: '{phrase[:50]}...'")

        # Relation lookup
        if route == "relation_lookup" and a and b:
            await cur.execute(
                "SELECT p.page_number, substring(p.text, 1, %s) "
                "FROM library_pages_v2 p WHERE p.run_id = %s "
                "AND lower(p.text) LIKE %s AND lower(p.text) LIKE %s "
                "ORDER BY p.page_number LIMIT %s",
                (SNIPPET_CHARS, rid, f"%{a}%", f"%{b}%", top_k),
            )
            for r in await cur.fetchall():
                pg = _v(r, 0)
                if pg not in seen_pages:
                    seen_pages.add(pg)
                    sources.append(BookQASource(
                        page_number=pg, evidence_type="cooccurrence_same_page", score=0.7,
                        snippet=(_v(r, 1) or "")[:SNIPPET_CHARS].replace("\n", " ").strip(),
                        matched_terms=[a, b],
                    ))
            if not sources:
                warnings.append(f"relation_not_found: '{a}' y '{b}' no coexisten en ninguna página")
            else:
                warnings.append("cooccurrence_is_not_doctrinal_relation")
                warnings.append("relation_is_candidate_not_editorially_reviewed")

        # Enrich with source refs
        for src in sources:
            await cur.execute(
                "SELECT source_type, reference_text FROM library_source_references_v2 sr "
                "WHERE sr.run_id = %s AND sr.page_number = %s LIMIT 3",
                (rid, src.page_number),
            )
            for r in await cur.fetchall():
                src.source_refs_nearby.append({"type": _v(r, 0) or "", "ref": _v(r, 1) or ""})

    # Build response
    answer_type = route
    conclusion = ""
    if not sources:
        answer_type = "no_evidence"
        warnings.append("no_evidence_found")
    else:
        pages_sorted = sorted(seen_pages)
        if route == "relation_lookup":
            conclusion = f"Se encontraron {len(sources)} coincidencia(s) entre '{a}' y '{b}' en {len(pages_sorted)} páginas."
        elif route == "concept_lookup":
            conclusion = f"Se encontraron {len(sources)} mención(es) de '{a}' en {len(pages_sorted)} página(s)."
        else:
            conclusion = f"Se encontraron {len(sources)} ocurrencia(s) en {len(pages_sorted)} páginas."

    run_resolution = "explicit_run_id" if run_id else "latest_by_document_id" if document_id else ""

    return BookQAResponse(
        question=question,
        run_id=rid,
        document_id=doc_id,
        scope_code=scope_code,
        answer_type=answer_type,
        short_conclusion=conclusion,
        evidence_summary=BookQAEvidenceSummary(
            literal_matches=sum(1 for s in sources if s.evidence_type in ("literal", "partial_phrase")),
            concept_matches=sum(1 for s in sources if s.evidence_type == "concept"),
            relation_matches=sum(1 for s in sources if s.evidence_type in ("relation_candidate", "cooccurrence_same_page")),
            source_references=sum(len(s.source_refs_nearby) for s in sources),
            pages=sorted(seen_pages),
        ),
        sources=sources[:top_k],
        warnings=warnings,
        method=BookQAMethod(
            run_id=rid, scope_code=scope_code,
            run_resolution=run_resolution,
        ),
    )
