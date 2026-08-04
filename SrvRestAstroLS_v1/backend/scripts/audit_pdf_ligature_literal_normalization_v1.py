#!/usr/bin/env python3
"""Read-only DEV audit for PDF ligature literal normalization (v1).

Covers:
- ligature inventory (U+FB00..U+FB06) over canonical PostgreSQL chunks;
- compatibility-character inventory (NBSP, SHY, zero-width characters);
- note 36 before/after (before read from the previous readiness report);
- the 25-query literal batch;
- negative cases (no invented joins, no reference false positives);
- Hebrew regressions (same evidence with and without niqqud);
- offset/citation checks (original quote preserves the ligature);
- idempotence checks of the normalization functions.

Exits non-zero when note 36 is not a literal exact footnote, the batch is
not 25/25, real words are joined, Hebrew degrades, the original citation
changes, or normalization is not idempotent.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import httpx
import psycopg
from psycopg.rows import dict_row

from modules.library.pdf_ligature_normalization import (
    build_pdf_literal_match_variants,
    elide_parenthetical_glosses,
    expand_pdf_compatibility_characters,
    normalize_pdf_search_text,
)
import globalVar

BASE = "http://127.0.0.1:7008"
FILENAME = "LIKUTEY HALAJOT (Interior Final).pdf"
NOTE36 = "Birur hace referencia a la extracción y refinamiento de las chispas"
NOTE35 = "El hombre se une a HaShem desde este mundo físico principalmente a través de la melodía y de la canción"

LIGATURE_CHARS = {
    0xFB00: "LATIN SMALL LIGATURE FF",
    0xFB01: "LATIN SMALL LIGATURE FI",
    0xFB02: "LATIN SMALL LIGATURE FL",
    0xFB03: "LATIN SMALL LIGATURE FFI",
    0xFB04: "LATIN SMALL LIGATURE FFL",
    0xFB05: "LATIN SMALL LIGATURE LONG S T",
    0xFB06: "LATIN SMALL LIGATURE ST",
}
COMPAT_CHARS = {
    0x00AD: "SOFT HYPHEN",
    0x00A0: "NO-BREAK SPACE",
    0x202F: "NARROW NO-BREAK SPACE",
    0x200B: "ZERO WIDTH SPACE",
    0x2060: "WORD JOINER",
    0x200C: "ZERO WIDTH NON-JOINER",
    0x200D: "ZERO WIDTH JOINER",
}

BATCH = [
    ("LOS ZAPATOS Y LA SABIDURÍA INFERIOR", 166),
    ("DESPERTÁNDOSE DEL SUEÑO ESPIRITUAL", 44),
    ("DESPERTANDO LOS PUNTOS BUENOS", 47),
    ("CONSTRUYENDO UN MISHKÁN", 51),
    ("INCLINADO HACIA LA BONDAD", 53),
    ("MELODÍAS Y PLEGARIAS", 56),
    ("ELEVANDO EL HABLA", 59),
    ("DIVIDIENDO LA NOCHE", 88),
    ("PERFECCIÓN DE LA PLEGARIA Y DEL HABLA", 68),
    ("VISTIENDO EL CUERPO", 72),
    ("He puesto a HaShem siempre delante de mí", 156),
    ("Tu jesed, HaShem, me sustentará", 56),
    ("el despertar el alba alude a levantarse del sueño espiritual", 55),
    ("el menos digno de los judíos", 48),
    ("Rabí Natán concluye su explicación", 51),
    ("Explicado y Anotado por Moshé Mykoff con Dov Grant", 3),
    ("Traducción al Español Guillermo Beilinson", 3),
    (NOTE36, 56),
    ("durante la noche la Shejiná desciende hacia los mundos inferiores", 57),
    ("Hashkamat Haboker Levantándose por la Mañana", 2),
    (NOTE35, 56),
    ("Salmos 16:1", 55),
    ("salmos 16:1", 55),
    ("Construyendo un Mishkan", 51),
    ("melodias y plegarias", 56),
]
NEGATIVES = [
    "CONSTRUYENDO UN TEMPLO INEXISTENTE",
    "Salmos 16:99",
    "Salmos 99:99",
    "Salmos 116:1 en Likutey Halajot",
    "nota 9999 de melodías",
    "GEDALIA DE MARTE",
    "frase fabricada que nunca aparece en el corpus xyzzy",
]
HEBREW = ["וּמִצְרַיִם נָסִים לִקְרָאתוֹ", "ומצרים נסים לקראתו"]


def dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def primary_of(body: dict[str, Any]) -> dict[str, Any] | None:
    return next((h for h in body.get("hits", []) if h.get("is_primary")), None)


async def pg_inventories(conn: Any) -> dict[str, Any]:
    counts: dict[str, dict[str, int]] = {}
    for code in {**LIGATURE_CHARS, **COMPAT_CHARS}:
        ch = chr(code)
        cur = await conn.execute(
            "SELECT count(*) AS n FROM library_document_chunks WHERE content LIKE %(p)s",
            {"p": f"%{ch}%"},
        )
        row = await cur.fetchone()
        counts[code] = {"count": int(row["n"])}
    return counts


async def main(output: Path, previous_report: Path | None) -> int:
    failures: list[str] = []
    report: dict[str, Any] = {"phase": "TEBAAI_PDF_LIGATURE_LITERAL_NORMALIZATION_V1_DEV"}

    # ── Idempotence / purity (pure functions) ──────────────────────────
    idempotence = []
    for text in ["reﬁnamiento", "reﬁ namiento", "oﬁ cina", "ﬂor", "aﬀecto", "oﬃcina", "וּמִצְרַיִם נָסִים לִקְרָאתוֹ", "refinamiento"]:
        once = normalize_pdf_search_text(text)
        twice = normalize_pdf_search_text(once)
        idempotence.append({"text": text, "once": once, "idempotent": once == twice})
    report["idempotence"] = idempotence
    if not all(item["idempotent"] for item in idempotence):
        failures.append("idempotence")

    # ── Negative join protections (pure) ───────────────────────────────
    join_cases = [
        ("la flor", ["laflor"]),
        ("por fin", ["porfin"]),
        ("fi nal", ["final"]),
        ("refi namiento", ["refinamiento"]),
    ]
    joins = []
    for query, forbidden in join_cases:
        variants = build_pdf_literal_match_variants(query)
        joins.append({"query": query, "variants": variants, "forbidden": forbidden, "pass": not any(f in variants for f in forbidden)})
    report["negative_joins"] = joins
    if not all(item["pass"] for item in joins):
        failures.append("real_words_joined")

    # ── PostgreSQL inventories ─────────────────────────────────────────
    dsn = globalVar.POSTGRES_DSN
    if not dsn:
        raise RuntimeError("POSTGRES_DSN is not configured")
    async with await psycopg.AsyncConnection.connect(dsn, row_factory=dict_row) as conn:
        await conn.execute("set default_transaction_read_only=on")
        report["ligature_inventory"] = await pg_inventories(conn)

    # ── API checks ─────────────────────────────────────────────────────
    email = os.environ.get("TEBAAI_E2E_ADMIN_EMAIL")
    password = os.environ.get("TEBAAI_E2E_ADMIN_PASSWORD")
    if not email or not password:
        raise RuntimeError("TEBAAI_E2E_ADMIN_EMAIL/PASSWORD are required")
    async with httpx.AsyncClient(timeout=240) as client:
        login = await client.post(f"{BASE}/auth/login", json={"email": email, "password": password})
        login.raise_for_status()
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        async def ask(question: str) -> dict[str, Any]:
            body = (await client.post(
                f"{BASE}/library/investigative-qa/v1", headers=headers,
                json={"question": question, "ai": {"enabled": False}},
            )).json()
            return body

        # Note 36 after
        runs = [primary_of(await ask(NOTE36)) for _ in range(10)]
        report["note_36_after"] = {
            "query": NOTE36,
            "runs": runs,
            "unique_signatures": len({json.dumps(r, sort_keys=True, default=str) for r in runs if r}),
            "pass": all(
                r and r.get("physical_file_name") == FILENAME
                and r.get("physical_pdf_page") == 56
                and r.get("footnote_number") == 36
                and r.get("literal_match_kind") == "footnote_literal_exact"
                and r.get("source_layer") == "footnote"
                and r.get("block_role") == "footnote_body"
                for r in runs
            ),
        }
        note36_pass = bool(report["note_36_after"]["pass"])
        if not note36_pass:
            failures.append("note_36_not_literal_exact")

        # Original quote preserved
        first = runs[0]
        quote = str(first.get("quote") or "") if first else ""
        report["note_36_quote"] = {
            "has_ligature": "reﬁ" in quote and "Inﬁ nito" in quote,
            "quote_head": quote[:160],
            "matched_normalized_text": first.get("matched_normalized_text") if first else None,
        }
        if not report["note_36_quote"]["has_ligature"]:
            failures.append("original_citation_modified")

        # Note 36 before (previous report)
        before: dict[str, Any] = {"available": False}
        if previous_report and previous_report.exists():
            try:
                data = json.loads(previous_report.read_text(encoding="utf-8"))
                for row in data.get("literal_batch", []):
                    if row.get("query") == NOTE36:
                        before = {"available": True, "primary": row.get("primary")}
                        break
            except Exception:
                before = {"available": False, "error": "unreadable"}
        report["note_36_before"] = before

        # 25-case batch
        batch_rows = []
        for query, expected_page in BATCH:
            body = await ask(query)
            primary = primary_of(body)
            row = {
                "query": query,
                "expected_page": expected_page,
                "actual_page": primary.get("physical_pdf_page") if primary else None,
                "match_type": primary.get("literal_match_kind") if primary else None,
                "source_layer": primary.get("source_layer") if primary else None,
                "pass": bool(primary and primary.get("physical_file_name") == FILENAME and primary.get("physical_pdf_page") == expected_page),
            }
            batch_rows.append(row)
        report["literal_batch_25"] = {"rows": batch_rows, "passed": sum(1 for r in batch_rows if r["pass"]), "total": len(batch_rows)}
        if report["literal_batch_25"]["passed"] != 25:
            failures.append("batch_not_25_of_25")

        # Negatives
        neg_rows = []
        for query in NEGATIVES:
            body = await ask(query)
            primary = primary_of(body)
            neg_rows.append({
                "query": query,
                "research_status": body.get("research_status"),
                "match_type": primary.get("literal_match_kind") if primary else None,
                "pass": body.get("research_status") == "no_evidence" or not (primary and str(primary.get("literal_match_kind") or "").endswith("exact")),
            })
        report["negatives"] = neg_rows
        if not all(r["pass"] for r in neg_rows):
            failures.append("negative_false_positive")

        # Hebrew regressions
        hebrew_rows = []
        for query in HEBREW:
            primary = primary_of(await ask(query))
            hebrew_rows.append({
                "query": query,
                "evidence_id": primary.get("evidence_id") if primary else None,
                "document": primary.get("physical_file_name") if primary else None,
                "page": primary.get("physical_pdf_page") if primary else None,
                "match": primary.get("literal_match_kind") if primary else None,
            })
        report["hebrew_regressions"] = {"rows": hebrew_rows, "same_evidence": hebrew_rows[0].get("evidence_id") == hebrew_rows[1].get("evidence_id")}
        if not report["hebrew_regressions"]["same_evidence"]:
            failures.append("hebrew_degraded")

    report["pass"] = not failures
    report["failures"] = failures
    dump(output / "audit-results.json", report)
    print(json.dumps({"pass": report["pass"], "failures": failures, "batch": report["literal_batch_25"]["passed"], "note36": note36_pass}, ensure_ascii=False))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--previous-report", type=Path, default=None)
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.output, args.previous_report)))
