"""Reproducible Hebrew literal retrieval batch and sanitized diagnostics."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import unicodedata
from pathlib import Path

import fitz
import httpx
import psycopg
from psycopg.rows import dict_row

from globalVar import POSTGRES_DSN
from modules.library.hebrew_lexical_normalizer import normalize_hebrew_search
from modules.library.hebrew_pdf_layout import readable_page
from modules.library.investigative_qa_v1 import QaRequest, run

ROOT = Path(__file__).resolve().parents[3]
REPORT = ROOT / "data/reports/breslov/2026-07-16-research-workspace-v1"
POSITIVES = [
    "תְּהִלָּתִי אֶחְטָם לָךְ",
    "תהלתי אחטם לך",
    "אחטם לך",
    "תהלתי",
    '"תהלתי אחטם לך"',
    "תהלתי, אחטם לך!",
    "הנשמות עם התפלה",
    "תפלה",
    "יראה",
    "נשמות",
    "דבור",
    "עצבות",
    "יוחנן",
    "dónde aparece כבוד אל",
    "איפה מופיע כבוד אל",
]
NEGATIVES = [
    "אבגדהוזחטיכ",
    "תהלתי אחטמ לך",
    "עקרב תהלתי",
    "לך אחטם תהלתי",
    "פסקה שאינה קיימת בספר הזה",
]


def dump(name: str, value: object) -> None:
    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def primary(response: dict) -> dict | None:
    ids = set(response.get("primary_evidence_ids", []))
    return next((hit for hit in response.get("hits", []) if hit["hit_id"] in ids), None)


def result_row(query: str, response: dict) -> dict:
    hit = primary(response)
    return {
        "query": query,
        "normalized_query": normalize_hebrew_search(query),
        "intent": response.get("intent"),
        "status": response.get("status"),
        "result_count": len(response.get("hits", [])),
        "evidence_id": hit and hit["hit_id"],
        "document_id": hit and hit["document_id"],
        "physical_file": hit and hit["physical_file_name"],
        "physical_page": hit and hit["pdf_page"],
        "printed_page": hit and hit["printed_page"],
        "section": hit and hit["section"],
        "page_anchor_id": hit and hit["page_anchor_id"],
        "match_type": hit and hit["literal_match_kind"],
        "literal_hash": hit and hashlib.sha256(hit["quote"].encode()).hexdigest(),
        "literal_text": hit and hit["quote"],
    }


async def http_results() -> list[dict]:
    email = os.environ.get("TEBAAI_E2E_ADMIN_EMAIL")
    password = os.environ.get("TEBAAI_E2E_ADMIN_PASSWORD")
    if not email or not password:
        return [{"status": "skipped", "reason": "E2E environment variables unavailable"}]
    base = "http://127.0.0.1:7008"
    async with httpx.AsyncClient(timeout=60) as client:
        login = await client.post(f"{base}/auth/login", json={"email": email, "password": password})
        login.raise_for_status()
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        output = []
        for query in POSITIVES[:4] + [POSITIVES[-1]]:
            response = await client.post(
                f"{base}/library/investigative-qa/v1",
                headers=headers,
                json={"question": query, "works": ["lmi"], "languages": ["he", "es"], "ai": {"enabled": False}},
            )
            data = response.json()
            hit = primary(data)
            output.append({
                "query": query,
                "http_status": response.status_code,
                "status": data.get("status"),
                "intent": data.get("intent"),
                "primary_evidence_ids": data.get("primary_evidence_ids", []),
                "document_id": hit and hit.get("document_id"),
                "physical_page": hit and hit.get("pdf_page"),
                "printed_page": hit and hit.get("printed_page"),
                "section": hit and hit.get("section"),
                "match_type": hit and hit.get("literal_match_kind"),
            })
        return output


async def main() -> None:
    async with await psycopg.AsyncConnection.connect(POSTGRES_DSN, row_factory=dict_row) as conn:
        positives = []
        for query in POSITIVES:
            response = await run(conn, QaRequest(question=query, works=["lmi"], ai={"enabled": False}, max_hits_per_work=10))
            positives.append(result_row(query, response))
        negatives = []
        for query in NEGATIVES:
            response = await run(conn, QaRequest(question=query, works=["lmi"], ai={"enabled": False}, max_hits_per_work=10))
            negatives.append(result_row(query, response))

        normalized = normalize_hebrew_search(POSITIVES[0])
        async with conn.cursor() as cur:
            await cur.execute(
                """SELECT document_id::text,source_filename,source_sha256,source_run_id::text,
                          pdf_page_number,printed_page_number,section_page_label,page_anchor_id::text,
                          literal_hash,length(literal_text) literal_chars,length(normalized_text) normalized_chars
                   FROM library_lmi_literal_search_v1 WHERE pdf_page_number=96"""
            )
            physical = await cur.fetchone()
            await cur.execute(
                """SELECT p.text raw_text,n.literal_text,n.normalized_text
                   FROM library_pages_v2 p
                   JOIN library_content_nodes_v2 n ON n.source_run_id=p.run_id
                   JOIN library_page_anchors_v2 a ON a.page_anchor_id=n.page_anchor_id
                   WHERE p.run_id=%s AND p.page_number=96 AND a.pdf_page_number=96""",
                (physical["source_run_id"],),
            )
            stored_layer = await cur.fetchone()
            await cur.execute("SELECT count(*) count FROM library_lmi_literal_search_v1 WHERE normalized_text LIKE %s", (f"%{normalized}%",))
            literal_count = (await cur.fetchone())["count"]
            await cur.execute(
                """SELECT count(*) count FROM library_lmi_literal_search_v1
                   WHERE to_tsvector('simple',normalized_text) @@ phraseto_tsquery('simple',%s)""",
                (normalized,),
            )
            fts_count = (await cur.fetchone())["count"]
            await cur.execute(
                """SELECT count(*) count,max(word_similarity(%s,normalized_text)) max_similarity
                   FROM library_lmi_literal_search_v1 WHERE word_similarity(%s,normalized_text) > 0.3""",
                (normalized, normalized),
            )
            trigram = await cur.fetchone()
            await cur.execute(
                """EXPLAIN (FORMAT JSON,ANALYZE,BUFFERS)
                   SELECT content_node_id FROM library_lmi_literal_search_v1
                   WHERE normalized_text LIKE %s""",
                (f"%{normalized}%",),
            )
            explain = (await cur.fetchone())["QUERY PLAN"]

    stable = positives[:6]
    batch_summary = {
        "gate": "PASS" if all(row["status"] == "ok" and row["evidence_id"] for row in positives) else "FAIL",
        "passed": sum(row["status"] == "ok" and bool(row["evidence_id"]) for row in positives),
        "total": len(positives),
        "main_variants_same_evidence": len({row["evidence_id"] for row in stable}) == 1,
        "main_variants_same_page_anchor": len({row["page_anchor_id"] for row in stable}) == 1,
        "results": positives,
    }
    negative_summary = {
        "gate": "PASS" if all(row["status"] == "no_evidence" and not row["evidence_id"] for row in negatives) else "FAIL",
        "passed": sum(row["status"] == "no_evidence" and not row["evidence_id"] for row in negatives),
        "total": len(negatives),
        "results": negatives,
    }
    dump("hebrew_literal_batch.json", batch_summary)
    dump("hebrew_literal_negative_batch.json", negative_summary)
    dump("hebrew_physical_document_resolution.json", physical)
    source = Path("/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY MOHARÁN I int (imprenta).pdf")
    with fitz.open(source) as pdf:
        projected = readable_page(pdf[95].get_text("rawdict", sort=False))
    canonical_phrase = "תְּהִלָּתִי אֶחְטָם לָךְ"
    dump("hebrew_literal_layer_comparison.json", {
        "physical_pdf_page": 96,
        "printed_page": 76,
        "pdf_text_layer": {
            "characters": len(stored_layer["raw_text"]),
            "sha256": hashlib.sha256(stored_layer["raw_text"].encode()).hexdigest(),
            "sample": stored_layer["raw_text"][:650],
            "defect": "extractor_inserted_spaces_between_hebrew_grapheme_clusters",
        },
        "glyph_geometry_projection": {
            "characters": len(projected),
            "sha256": hashlib.sha256(projected.encode()).hexdigest(),
            "equals_stored_literal": projected == stored_layer["literal_text"],
            "nfc": unicodedata.is_normalized("NFC", projected),
        },
        "stored_canonical": {
            "characters": len(stored_layer["literal_text"]),
            "sha256": hashlib.sha256(stored_layer["literal_text"].encode()).hexdigest(),
            "contains_confirmed_phrase": canonical_phrase in stored_layer["literal_text"],
            "sample": stored_layer["literal_text"][:650],
        },
        "stored_search_normalized": {
            "characters": len(stored_layer["normalized_text"]),
            "normalized_query": normalize_hebrew_search(canonical_phrase),
            "contains_normalized_query": normalize_hebrew_search(canonical_phrase) in stored_layer["normalized_text"],
        },
        "confirmed_phrase": canonical_phrase,
        "confirmed_phrase_codepoints": [
            {"character": char, "codepoint": f"U+{ord(char):04X}", "name": unicodedata.name(char, "UNKNOWN")}
            for char in canonical_phrase
        ],
        "bidi_controls_in_stored_literal": [
            f"U+{ord(char):04X}" for char in stored_layer["literal_text"] if unicodedata.category(char) == "Cf"
        ],
        "manual_string_reversal": False,
        "ocr_used": False,
    })
    dump("hebrew_index_diagnostics.json", {
        "normalized_query": normalized,
        "literal_like_hits": literal_count,
        "fts_phrase_hits": fts_count,
        "trigram": trigram,
        "literal_precedes_vector": True,
        "vector_used": False,
        "explain_literal_like": explain,
    })
    dump("hebrew_literal_http_results.json", await http_results())
    print(json.dumps({"positive": batch_summary["gate"], "positive_count": batch_summary["passed"], "negative": negative_summary["gate"], "negative_count": negative_summary["passed"]}))


if __name__ == "__main__":
    asyncio.run(main())
