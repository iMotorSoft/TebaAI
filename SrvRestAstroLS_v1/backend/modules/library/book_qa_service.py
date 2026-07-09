"""Book QA V2 SQL-only service — grounded in library_pages_v2."""

from __future__ import annotations

import re
from typing import Any

from psycopg import AsyncConnection

from modules.library.book_qa_schemas import (
    BookQAEvidenceSummary,
    BookQAMethod,
    BookQAResponse,
    BookQASource,
)

SNIPPET_CHARS = 400


def classify(question: str) -> tuple[str, str | None, str | None]:
    q = question.strip().rstrip("¿?!.")

    # Phrase lookup
    if '"' in q or "'" in q or re.search(r"busc[áa] la frase|busca la frase|d[oó]nde dice|aparece la frase", q, re.I):
        m = re.search(r'["\']([^"\']+)["\']', q)
        return "phrase_lookup", (m.group(1) if m else q), None

    # Relation lookup
    for pat in [
        r"(?:relaci[oó]n|relacion)\s+entre\s+(.+?)\s+y\s+(.+)$",
        r"(?:c[oó]mo\s+se\s+(?:relacionan|conectan))\s+(.+?)\s+y\s+(.+)$",
        r"(?:qu[eé]\s+(?:relaci[oó]n|conexi[oó]n)\s+(?:hay|existe))\s+entre\s+(.+?)\s+y\s+(.+)$",
        r"(.{3,30}?)\s+y\s+(.{3,30})$",
    ]:
        m = re.search(pat, q, re.I)
        if m:
            a = m.group(1).strip().lower()
            b = m.group(2).strip().lower()
            if len(a) > 2 and len(b) > 2:
                return "relation_lookup", a, b
            break

    # Concept lookup
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


async def run_book_qa(
    conn: AsyncConnection,
    question: str,
    run_id: str,
    scope_code: str,
    top_k: int = 8,
) -> BookQAResponse:
    route, a, b = classify(question)
    sources: list[BookQASource] = []
    seen_pages: set[int] = set()
    warnings: list[str] = []
    doc_id = ""

    # Validate run
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT document_id::text, status FROM library_ingestion_runs_v2 WHERE run_id = %s",
            (run_id,),
        )
        row = await cur.fetchone()
        if not row:
            from litestar.exceptions import HTTPException
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
        doc_id = _v(row, 0)
        status = _v(row, 1)
        if status not in ("completed", "partial"):
            warnings.append(f"run_status_not_completed: {status}")

    async with conn.cursor() as cur:
        if route == "concept_lookup":
            for term in [a]:
                await cur.execute(
                    "SELECT p.page_number, substring(p.text, greatest(position(%s in lower(p.text)) - 80, 1), %s) AS snippet "
                    "FROM library_pages_v2 p WHERE p.run_id = %s AND lower(p.text) LIKE %s "
                    "ORDER BY p.page_number LIMIT %s",
                    (term, SNIPPET_CHARS, run_id, f"%{term}%", top_k),
                )
                rows = await cur.fetchall()
                for r in rows:
                    pg = _v(r, 0)
                    if pg not in seen_pages:
                        seen_pages.add(pg)
                        sources.append(BookQASource(
                            page_number=pg,
                            evidence_type="concept",
                            score=0.9,
                            snippet=(_v(r, 1) or "")[:SNIPPET_CHARS].replace("\n", " ").strip(),
                            matched_terms=[term],
                        ))
                if not rows:
                    warnings.append(f"concept_not_found: '{term}' no encontrado en pages ILIKE")

        if route == "phrase_lookup":
            phrase = a or question
            await cur.execute(
                "SELECT p.page_number, substring(p.text, greatest(position(%s in lower(p.text)) - 80, 1), %s) AS snippet "
                "FROM library_pages_v2 p WHERE p.run_id = %s AND lower(p.text) LIKE %s "
                "ORDER BY p.page_number LIMIT %s",
                (phrase, SNIPPET_CHARS, run_id, f"%{phrase}%", top_k),
            )
            rows = await cur.fetchall()
            for r in rows:
                pg = _v(r, 0)
                if pg not in seen_pages:
                    seen_pages.add(pg)
                    sources.append(BookQASource(
                        page_number=pg,
                        evidence_type="literal",
                        score=1.0,
                        snippet=(_v(r, 1) or "")[:SNIPPET_CHARS].replace("\n", " ").strip(),
                        matched_terms=[phrase[:40]],
                    ))
            if not rows:
                # Token fallback
                tokens = [t for t in re.findall(r"\w{4,}", phrase.lower()) if t not in ("que", "para", "con", "por")]
                for token in tokens[:3]:
                    await cur.execute(
                        "SELECT p.page_number, substring(p.text, greatest(position(%s in lower(p.text)) - 80, 1), 300) "
                        "FROM library_pages_v2 p WHERE p.run_id = %s AND lower(p.text) LIKE %s "
                        "ORDER BY p.page_number LIMIT 3",
                        (token, run_id, f"%{token}%"),
                    )
                    for r in await cur.fetchall():
                        pg = _v(r, 0)
                        if pg not in seen_pages:
                            seen_pages.add(pg)
                            sources.append(BookQASource(
                                page_number=pg,
                                evidence_type="partial_phrase",
                                score=0.5,
                                snippet=(_v(r, 1) or "")[:300].replace("\n", " ").strip(),
                                matched_terms=[token],
                            ))
                if not sources:
                    warnings.append(f"phrase_not_found: '{phrase[:50]}...' no encontrado")

        if route == "relation_lookup" and a and b:
            # Search pages where both terms cooccur
            await cur.execute(
                "SELECT p.page_number, substring(p.text, 1, %s) AS snippet "
                "FROM library_pages_v2 p WHERE p.run_id = %s "
                "AND lower(p.text) LIKE %s AND lower(p.text) LIKE %s "
                "ORDER BY p.page_number LIMIT %s",
                (SNIPPET_CHARS, run_id, f"%{a}%", f"%{b}%", top_k),
            )
            rows = await cur.fetchall()
            for r in rows:
                pg = _v(r, 0)
                if pg not in seen_pages:
                    seen_pages.add(pg)
                    sources.append(BookQASource(
                        page_number=pg,
                        evidence_type="cooccurrence_same_page",
                        score=0.7,
                        snippet=(_v(r, 1) or "")[:SNIPPET_CHARS].replace("\n", " ").strip(),
                        matched_terms=[a, b],
                    ))
            if not sources:
                warnings.append(f"relation_not_found: no se encontraron páginas donde coexistan '{a}' y '{b}'")
            else:
                warnings.append("cooccurrence_is_not_doctrinal_relation")
                warnings.append("relation_is_candidate_not_editorially_reviewed")

        # Enrich with source references
        for src in sources:
            pg = src.page_number
            await cur.execute(
                "SELECT source_type, reference_text FROM library_source_references_v2 sr "
                "WHERE sr.run_id = %s AND sr.page_number = %s LIMIT 3",
                (run_id, pg),
            )
            for r in await cur.fetchall():
                src.source_refs_nearby.append({"type": _v(r, 0), "ref": _v(r, 1)})

    # Add milvus/ai warnings if requested
    from dataclasses import asdict

    # Build response
    answer_type = route
    evidence_type_map = {
        "literal": "literal_matches",
        "partial_phrase": "literal_matches",
        "concept": "concept_matches",
        "relation_candidate": "relation_matches",
        "cooccurrence_same_page": "relation_matches",
    }
    summary = BookQAEvidenceSummary(
        literal_matches=sum(1 for s in sources if s.evidence_type in ("literal", "partial_phrase")),
        concept_matches=sum(1 for s in sources if s.evidence_type == "concept"),
        relation_matches=sum(1 for s in sources if s.evidence_type in ("relation_candidate", "cooccurrence_same_page")),
        source_references=sum(len(s.source_refs_nearby) for s in sources),
        pages=sorted(seen_pages),
    )

    conclusion = ""
    if not sources:
        conclusion = f"No se encontró evidencia en el libro para esta consulta."
        answer_type = "no_evidence"
        warnings.append("no_evidence_found")
    else:
        if route == "concept_lookup":
            conclusion = f"Se encontraron {len(sources)} mención(es) de '{a}' en {len(seen_pages)} página(s)."
        elif route == "relation_lookup":
            conclusion = f"Se encontraron {len(sources)} coincidencia(s) entre '{a}' y '{b}' en {len(seen_pages)} páginas."
        elif route == "phrase_lookup":
            conclusion = f"Se encontraron {len(sources)} ocurrencia(s) de la frase en {len(seen_pages)} páginas."

    return BookQAResponse(
        question=question,
        run_id=run_id,
        document_id=doc_id,
        scope_code=scope_code,
        answer_type=answer_type,
        short_conclusion=conclusion,
        evidence_summary=summary,
        sources=sources[:top_k],
        warnings=warnings,
        method=BookQAMethod(
            run_id=run_id,
            scope_code=scope_code,
        ),
    )
