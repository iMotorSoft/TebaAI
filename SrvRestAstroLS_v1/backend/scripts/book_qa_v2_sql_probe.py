#!/usr/bin/env python3
"""Book QA V2 SQL-only probe. Reads library_pages_v2 + concept_mentions + relations + source_refs."""

from __future__ import annotations

import argparse, asyncio, json, os, re, sys
from pathlib import Path
from typing import Any

import psycopg

PG_CONF = {
    "user": os.environ["DB_PG_USER"],
    "password": os.environ["DB_PG_PASS"],
    "host": os.environ.get("DB_PG_IP", "localhost"),
    "port": int(os.environ.get("DB_PG_PORT", "5432")),
    "dbname": "tebaai",
}
SNIPPET_CHARS = 500


def classify(question: str) -> tuple[str, str, str | None, str | None]:
    """Classify question into lookup type and extract concepts."""
    q = question.strip().rstrip("¿?!.")

    # Phrase lookup (contains quotes or explicit phrase request)
    if '"' in q or "'" in q or re.search(r"busc[áa] la frase|dónde dice|aparece la frase", q, re.I):
        # Extract the phrase
        m = re.search(r'["\']([^"\']+)["\']', q)
        if m:
            return "phrase_lookup", q, None, None
        return "phrase_lookup", q, None, None

    # Relation lookup
    for pat in [
        r"(?:relación|relacion)\s+entre\s+(.+?)\s+y\s+(.+)$",
        r"(?:c[oó]mo\s+se\s+(?:relacionan|conectan))\s+(.+?)\s+y\s+(.+)$",
        r"(?:qu[eé]\s+(?:relaci[oó]n|conexi[oó]n)\s+(?:hay|existe))\s+entre\s+(.+?)\s+y\s+(.+)$",
        r"(.+?)\s+y\s+(.+)"  # broad fallback: "A y B"
    ]:
        m = re.search(pat, q, re.I)
        if m:
            a = m.group(1).strip().lower()
            b = m.group(2).strip().lower()
            if len(a) > 2 and len(b) > 2:
                return "relation_lookup", q, a, b

    # Concept lookup
    for pat in [
        r"(?:d[oó]nde\s+(?:aparece|est[áa]|dice|habla))\s+(?:de\s+|del\s+|la\s+|el\s+)?(.+)$",
        r"(?:qu[eé]\s+(?:dice|aparece|enseña))\s+(?:sobre\s+)?(.+)$",
        r"(?:en\s+qu[eé]\s+(?:p[áa]ginas|[áa]mbito|secci[oó]n))\s+(?:aparece\s+)?(.+)$",
        r"(.+)",  # catch-all
    ]:
        m = re.search(pat, q, re.I)
        if m:
            concept = m.group(1).strip().lower()
            if len(concept) > 2:
                return "concept_lookup", q, concept, None

    return "concept_lookup", q, q[:30], None


def _v(row, idx=0):
    if row is None:
        return None
    if isinstance(row, dict):
        keys = list(row.keys())
        return row[keys[idx]]
    return row[idx]


async def probe(question: str, run_id: str, top_k: int = 10) -> dict[str, Any]:
    conn = await psycopg.AsyncConnection.connect(**PG_CONF)

    route, q, a, b = classify(question)
    evidence: list[dict[str, Any]] = []
    warnings: list[str] = []
    sources_count = 0

    async with conn.cursor() as cur:
        # Get run info
        await cur.execute(
            "SELECT document_id, scope_code, pipeline_version FROM library_ingestion_runs_v2 WHERE run_id = %s",
            (run_id,),
        )
        run_row = await cur.fetchone()
        if not run_row:
            await conn.close()
            return {"error": f"Run {run_id} not found"}
        doc_id = str(_v(run_row, 0))

        if route in ("concept_lookup", "relation_lookup"):
            concept_terms = [a]
            if b:
                concept_terms.append(b)

            for ct in concept_terms:
                # 1. Get all pages from concept_mentions table
                concept_pages = set()
                await cur.execute(
                    "SELECT cm.page_number FROM library_concept_mentions_v2 cm "
                    "WHERE cm.run_id = %s AND cm.normalized_label = %s ORDER BY cm.page_number LIMIT %s",
                    (run_id, ct, top_k),
                )
                for r in await cur.fetchall():
                    concept_pages.add(_v(r))

                # 2. Also search pages_v2 text directly (more comprehensive)
                await cur.execute(
                    "SELECT p.page_number, substring(p.text, greatest(position(%s in lower(p.text)) - 80, 1), %s) AS snippet "
                    "FROM library_pages_v2 p WHERE p.run_id = %s AND lower(p.text) LIKE %s "
                    "ORDER BY p.page_number LIMIT %s",
                    (ct, SNIPPET_CHARS, run_id, f"%{ct}%", top_k),
                )
                rows = await cur.fetchall()
                for r in rows:
                    pg = _v(r, 0)
                    concept_pages.add(pg)
                    evidence.append({
                        "page_number": pg,
                        "evidence_type": "concept",
                        "score": 0.9,
                        "matched_terms": [ct],
                        "snippet": _v(r, 1) or "",
                        "source_refs_nearby": [],
                    })

                if not concept_pages:
                    warnings.append(f"concept_not_found_in_v2: '{ct}' no encontrado en concept_mentions ni pages ILIKE")

        if route == "phrase_lookup":
            # ILIKE exacta
            await cur.execute(
                "SELECT p.page_number, substring(p.text, greatest(position(%s in lower(p.text)) - 100, 1), %s) AS snippet "
                "FROM library_pages_v2 p WHERE p.run_id = %s AND lower(p.text) LIKE %s "
                "ORDER BY p.page_number LIMIT %s",
                (q, SNIPPET_CHARS, run_id, f"%{q.lower()}%", top_k),
            )
            rows = await cur.fetchall()
            for r in rows:
                evidence.append({
                    "page_number": _v(r, 0),
                    "evidence_type": "literal",
                    "score": 1.0,
                    "matched_terms": [q[:40]],
                    "snippet": _v(r, 1) or "",
                    "source_refs_nearby": [],
                })
            if not rows:
                # Token fallback
                tokens = [t for t in re.findall(r"\w{3,}", q.lower()) if t not in ("que", "para", "con", "por", "las", "los")]
                for token in tokens[:3]:
                    await cur.execute(
                        "SELECT p.page_number, substring(p.text, greatest(position(%s in lower(p.text)) - 80, 1), 300) AS snippet "
                        "FROM library_pages_v2 p WHERE p.run_id = %s AND lower(p.text) LIKE %s "
                        "ORDER BY p.page_number LIMIT 5",
                        (token, run_id, f"%{token}%"),
                    )
                    rows = await cur.fetchall()
                    for r in rows:
                        evidence.append({
                            "page_number": _v(r, 0),
                            "evidence_type": "token_match",
                            "score": 0.5,
                            "matched_terms": [token],
                            "snippet": _v(r, 1) or "",
                            "source_refs_nearby": [],
                        })
                if not evidence:
                    warnings.append(f"phrase_not_found: '{q[:50]}...' no encontrado en pages ILIKE")

        if route == "relation_lookup" and a and b:
            # Try explicit relation candidate
            await cur.execute(
                "SELECT ir.page_start, ir.page_end, ir.snippet, ir.relation_type, ir.evidence_type, ir.concept_a, ir.concept_b "
                "FROM library_internal_relations_v2 ir "
                "WHERE ir.run_id = %s AND ((lower(ir.concept_a) = %s AND lower(ir.concept_b) = %s) "
                "OR (lower(ir.concept_a) = %s AND lower(ir.concept_b) = %s)) "
                "LIMIT 5",
                (run_id, a, b, b, a),
            )
            rows = await cur.fetchall()
            if rows:
                for r in rows:
                    evidence.append({
                        "page_number": _v(r, 0),
                        "page_end": _v(r, 1),
                        "evidence_type": "relation_candidate",
                        "relation_type": _v(r, 3),
                        "score": 0.9,
                        "matched_terms": [a, b],
                        "snippet": (_v(r, 2) or "")[:SNIPPET_CHARS],
                        "source_refs_nearby": [],
                    })
            else:
                # Fallback: coocurrence in pages
                await cur.execute(
                    "SELECT p.page_number, substring(p.text, 1, %s) AS snippet "
                    "FROM library_pages_v2 p WHERE p.run_id = %s "
                    "AND lower(p.text) LIKE %s AND lower(p.text) LIKE %s "
                    "ORDER BY p.page_number LIMIT %s",
                    (SNIPPET_CHARS, run_id, f"%{a}%", f"%{b}%", top_k),
                )
                rows = await cur.fetchall()
                for r in rows:
                    evidence.append({
                        "page_number": _v(r, 0),
                        "evidence_type": "cooccurrence_same_page",
                        "score": 0.6,
                        "matched_terms": [a, b],
                        "snippet": (_v(r, 1) or "")[:SNIPPET_CHARS],
                        "source_refs_nearby": [],
                    })
                if not rows:
                    warnings.append(f"relation_not_found: no se encontraron páginas donde coexistan '{a}' y '{b}'")

        # Enrich with source references nearby
        for ev in evidence:
            pg = ev.get("page_number")
            if pg:
                await cur.execute(
                    "SELECT source_type, reference_text FROM library_source_references_v2 sr "
                    "WHERE sr.run_id = %s AND sr.page_number = %s LIMIT 3",
                    (run_id, pg),
                )
                src_rows = await cur.fetchall()
                for sr in src_rows:
                    ev["source_refs_nearby"].append({"type": _v(sr, 0), "ref": _v(sr, 1)})

        # Get page text for each evidence item (if snippet empty)
        for ev in evidence:
            if not ev.get("snippet"):
                pg = ev.get("page_number")
                if pg:
                    await cur.execute(
                        "SELECT substring(p.text, 1, %s) FROM library_pages_v2 p WHERE p.run_id = %s AND p.page_number = %s",
                        (SNIPPET_CHARS, run_id, pg),
                    )
                    row = await cur.fetchone()
                    if row:
                        ev["snippet"] = (_v(row) or "")[:SNIPPET_CHARS]

        # Build summary
        pages_set = set()
        for ev in evidence:
            pg = ev.get("page_number")
            if pg:
                pages_set.add(pg)

        answer_type = route
        type_map = {"concept_lookup": "concept_lookup", "phrase_lookup": "phrase_lookup", "relation_lookup": "relation_lookup"}
        conclusion = ""
        if not evidence:
            conclusion = f"No se encontró evidencia en el libro para esta consulta."
            warnings.append("no_evidence_found")
        else:
            pages_list = sorted(pages_set)[:20]
            total = len(evidence)
            if route == "concept_lookup":
                conclusion = f"Se encontraron {total} menciones de '{a}' en {len(pages_list)} página(s): {pages_list[:10]}..."
            elif route == "relation_lookup":
                conclusion = f"Se encontraron {total} coincidencias entre '{a}' y '{b}' en {len(pages_list)} páginas."
            elif route == "phrase_lookup":
                conclusion = f"Se encontraron {total} ocurrencias de la frase en {len(pages_list)} páginas."

        result = {
            "question": question,
            "route": answer_type,
            "run_id": run_id,
            "document_id": doc_id,
            "answer_type": answer_type,
            "short_conclusion": conclusion,
            "evidence_summary": {
                "literal_matches": sum(1 for e in evidence if e.get("evidence_type") == "literal"),
                "concept_matches": sum(1 for e in evidence if e.get("evidence_type") == "concept"),
                "relation_matches": sum(1 for e in evidence if e.get("evidence_type") in ("relation_candidate", "cooccurrence_same_page")),
                "source_references": sum(len(e.get("source_refs_nearby", [])) for e in evidence),
                "pages": sorted(pages_set),
            },
            "sources": evidence[:top_k],
            "warnings": warnings,
            "method": {
                "retrieval": "postgres_v2_sql_only",
                "used_milvus": False,
                "used_embeddings": False,
                "used_ai": False,
            },
        }

    await conn.close()
    return result


def format_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Book QA V2 SQL Probe",
        "",
        f"## Pregunta",
        result.get("question", ""),
        "",
        f"## Conclusión",
        result.get("short_conclusion", ""),
        "",
        "## Método",
        f"- retrieval: {result.get('method', {}).get('retrieval', '?')}",
        f"- Milvus: no",
        f"- Embeddings: no",
        f"- IA: no",
        f"- Ruta: {result.get('route', '?')}",
        "",
        "## Evidencia",
    ]

    for i, src in enumerate(result.get("sources", [])[:10], 1):
        snippet = (src.get("snippet") or " — ")[:300].replace("\n", " ")
        lines += [
            f"### Página {src.get('page_number', '?')} — {src.get('evidence_type', '?')}",
            "",
            f"Snippet: {snippet}",
            "",
        ]
        refs = src.get("source_refs_nearby", [])
        if refs:
            for ref in refs:
                lines.append(f"  - Fuente: {ref.get('type', '?')} — {ref.get('ref', '?')}")
            lines.append("")

    es = result.get("evidence_summary", {})
    lines += [
        "## Resumen de evidencia",
        f"- Literales: {es.get('literal_matches', 0)}",
        f"- Conceptos: {es.get('concept_matches', 0)}",
        f"- Relaciones: {es.get('relation_matches', 0)}",
        f"- Fuentes cercanas: {es.get('source_references', 0)}",
        f"- Páginas: {es.get('pages', [])}",
        "",
    ]

    if result.get("warnings"):
        lines += ["## Advertencias"]
        for w in result["warnings"]:
            lines.append(f"- {w}")
        lines.append("")

    lines += [
        f"## JSON",
        f"```json",
        f"{json.dumps(result, indent=2, ensure_ascii=False)[:2000]}...",
        f"```",
    ]
    return "\n".join(lines)


async def main() -> int:
    parser = argparse.ArgumentParser(description="Book QA V2 SQL Probe")
    parser.add_argument("--run-id", required=True, help="V2 run ID")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--json", action="store_true", help="Output raw JSON only")
    parser.add_argument("--report-dir", type=Path)
    parser.add_argument("question", nargs="*", help="Question text")
    args = parser.parse_args()

    if not args.question:
        print("ERROR: question required")
        return 1

    question = " ".join(args.question)
    result = await probe(question, args.run_id, args.top_k)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(format_markdown(result))

    if args.report_dir:
        args.report_dir.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "-", question.lower().strip())[:40].strip("-")
        (args.report_dir / f"probe_{slug}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
