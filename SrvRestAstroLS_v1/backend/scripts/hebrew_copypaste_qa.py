"""Sanitized real-DB/HTTP gate for Hebrew PDF glyph-spaced copy/paste."""
from __future__ import annotations

import asyncio
import json
import os
import unicodedata
from pathlib import Path

import httpx
import psycopg
from psycopg.rows import dict_row

from globalVar import POSTGRES_DSN
from modules.library.hebrew_lexical_normalizer import extract_literal_segments
from modules.library.investigative_qa_v1 import QaRequest, run

ROOT = Path(__file__).resolve().parents[3]
REPORT = ROOT / "data/reports/breslov/2026-07-16-research-workspace-v1"
SPACED = "ת ְּ הִ לָּ ת ִ י אֶ חְ ט ָ ם לָ ך"
EXPECTED = {
    "hit_id": "lmi-dc3eecd6-64b1-4f09-ac9b-d47e4fd70df1",
    "document_id": "6673da69-eb38-40bf-9f5c-447ff3ba6725",
    "page_anchor_id": "c211a30b-eef4-4fb4-a558-45e89c314db3",
    "pdf_page": 96,
    "printed_page": 76,
    "section": "LIKUTEY MOHARÁN #2:7",
}
POSITIVES = [
    "תְּהִלָּתִי אֶחְטָם לָךְ",
    "תהלתי אחטם לך",
    SPACED,
    f"{SPACED} donde esta",
    f"donde esta {SPACED}",
    f"{SPACED} where is",
    f"where does it appear {SPACED}",
    f"איפה {SPACED}",
    f"היכן מופיע {SPACED}",
    SPACED.replace(" ", "\u00a0"),
    SPACED.replace(" ", "\u2009"),
    SPACED.replace(" ", "  "),
    SPACED.replace(" ", "\n"),
    f'“{SPACED}” donde esta',
    f'{SPACED}, donde esta',
    "אחטם לך",
    "תהלתי",
    "הנשמות עם התפלה",
    "לא בקשתי אבטח",
    "תהלים",
]
POSITIVE_WORKS = {"תהלים": ["lmii"]}
POSITIVE_OVERRIDES = {
    "לא בקשתי אבטח": {"work_code": "lmi", "physical_page": 76, "printed_page": 56},
    "תהלים": {"work_code": "lmii", "physical_page": 14},
}
NEGATIVES = [
    "תהלתי אחטמ לך",
    "תהלתז אחטם לך",
    "לך אחטם תהלתי",
    "תהלתי עקרב אחטם",
    "אבגדהוזחטיכ",
    "ת א x ח ט ם where is",
    "נשמות עקרבים אחטם",
    "ץ ק ר ש ת אקראי",
]


def dump(name: str, value: object) -> None:
    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def primary(response: dict) -> dict | None:
    ids = set(response.get("primary_evidence_ids", []))
    return next((hit for hit in response.get("hits", []) if hit["hit_id"] in ids), None)


def row(query: str, response: dict) -> dict:
    hit = primary(response)
    interpretation = response.get("interpretation", {})
    return {
        "query": query,
        "status": response.get("status"),
        "intent": response.get("intent"),
        "literal_raw": interpretation.get("literal_raw"),
        "instruction": interpretation.get("instruction"),
        "literal_reconstructed": interpretation.get("literal_reconstructed"),
        "normalized_query": interpretation.get("literal_search_normalized"),
        "candidate_count": interpretation.get("candidate_count"),
        "selected_candidate": interpretation.get("selected_candidate"),
        "evidence_id": hit and hit.get("hit_id"),
        "work_code": hit and hit.get("work_code"),
        "document_id": hit and hit.get("document_id"),
        "page_anchor_id": hit and hit.get("page_anchor_id"),
        "physical_page": hit and hit.get("pdf_page"),
        "printed_page": hit and hit.get("printed_page"),
        "section": hit and hit.get("section"),
        "canonical_phrase_present": bool(hit and "תְּהִלָּתִי אֶחְטָם לָךְ" in hit.get("quote", "")),
        "vector_used": response.get("execution", {}).get("used_vector"),
    }


def expected(row_value: dict) -> bool:
    override = POSITIVE_OVERRIDES.get(row_value["query"])
    if override:
        return (
            row_value["status"] == "ok"
            and row_value["intent"] == "literal_lookup"
            and row_value["evidence_id"] is not None
            and all(row_value.get(key) == value for key, value in override.items())
            and row_value["vector_used"] is False
        )
    return (
        row_value["status"] == "ok"
        and row_value["intent"] == "literal_lookup"
        and row_value["evidence_id"] == EXPECTED["hit_id"]
        and row_value["document_id"] == EXPECTED["document_id"]
        and row_value["page_anchor_id"] == EXPECTED["page_anchor_id"]
        and row_value["physical_page"] == EXPECTED["pdf_page"]
        and row_value["printed_page"] == EXPECTED["printed_page"]
        and row_value["section"] == EXPECTED["section"]
        and row_value["canonical_phrase_present"]
        and row_value["vector_used"] is False
    )


async def http_gate() -> list[dict]:
    email = os.environ.get("TEBAAI_E2E_ADMIN_EMAIL")
    password = os.environ.get("TEBAAI_E2E_ADMIN_PASSWORD")
    if not email or not password:
        raise RuntimeError("E2E credential variables are not configured")
    queries = [POSITIVES[index] for index in (0, 1, 2, 3, 4, 7)]
    async with httpx.AsyncClient(timeout=90) as client:
        login = await client.post("http://127.0.0.1:7008/auth/login", json={"email": email, "password": password})
        login.raise_for_status()
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        results = []
        for query in queries:
            response = await client.post(
                "http://127.0.0.1:7008/library/investigative-qa/v1",
                headers=headers,
                json={"question": query, "works": ["lmi"], "languages": ["he", "es"], "ai": {"enabled": False}},
            )
            value = row(query, response.json())
            value["http_status"] = response.status_code
            value["pass"] = response.status_code == 200 and expected(value)
            results.append(value)
        return results


async def main() -> None:
    async with await psycopg.AsyncConnection.connect(POSTGRES_DSN, row_factory=dict_row) as conn:
        positive_rows = []
        for query in POSITIVES:
            response = await run(conn, QaRequest(
                question=query,
                works=POSITIVE_WORKS.get(query, ["lmi"]),
                ai={"enabled": False},
            ))
            value = row(query, response)
            value["pass"] = expected(value)
            positive_rows.append(value)
        negative_rows = []
        for query in NEGATIVES:
            response = await run(conn, QaRequest(question=query, works=["lmi"], ai={"enabled": False}))
            value = row(query, response)
            value["pass"] = value["status"] == "no_evidence" and value["evidence_id"] is None
            negative_rows.append(value)
        async with conn.cursor() as cursor:
            await cursor.execute(
                """SELECT count(*) literal_hits FROM library_lmi_literal_search_v1
                   WHERE normalized_text LIKE '%תהלתי אחטם לך%'"""
            )
            sql_literal = await cursor.fetchone()
            await cursor.execute(
                """SELECT count(*) fts_hits FROM library_lmi_literal_search_v1
                   WHERE to_tsvector('simple',normalized_text)
                   @@ phraseto_tsquery('simple','תהלתי אחטם לך')"""
            )
            fts = await cursor.fetchone()
            await cursor.execute(
                """SELECT count(*) trigram_hits,max(word_similarity('תהלתי אחטם לך',normalized_text)) max_similarity
                   FROM library_lmi_literal_search_v1
                   WHERE word_similarity('תהלתי אחטם לך',normalized_text) > 0.3"""
            )
            trigram = await cursor.fetchone()

    exact = extract_literal_segments(f"{SPACED} donde esta")
    unicode_analysis = {
        "raw": f"{SPACED} donde esta",
        "nfc": unicodedata.normalize("NFC", f"{SPACED} donde esta"),
        "codepoints": [
            {"character": char, "codepoint": f"U+{ord(char):04X}", "category": unicodedata.category(char), "name": unicodedata.name(char, "UNKNOWN")}
            for char in f"{SPACED} donde esta"
        ],
        "graphemes_reassociated": list(exact.graphemes) if exact else [],
        "ascii_spaces": (f"{SPACED} donde esta").count(" "),
        "bidi_controls": [char for char in f"{SPACED} donde esta" if unicodedata.category(char) == "Cf"],
    }
    http_rows = await http_gate()
    dump("hebrew_copypaste_unicode_analysis.json", unicode_analysis)
    dump("hebrew_candidate_segmentation_results.json", {
        "limit": 64,
        "candidate_count": len(exact.candidates) if exact else 0,
        "candidates": list(exact.candidates) if exact else [],
        "selected_by_corpus": "תהלתי אחטם לך",
        "strategy": "compact Hebrew letter match selects word boundaries; indexed phrase retrieval ranks evidence",
    })
    dump("hebrew_copypaste_batch.json", {
        "gate": "PASS" if all(item["pass"] for item in positive_rows) else "FAIL",
        "passed": sum(item["pass"] for item in positive_rows),
        "total": len(positive_rows),
        "results": positive_rows,
    })
    dump("hebrew_copypaste_negative_batch.json", {
        "gate": "PASS" if all(item["pass"] for item in negative_rows) else "FAIL",
        "passed": sum(item["pass"] for item in negative_rows),
        "total": len(negative_rows),
        "results": negative_rows,
    })
    dump("hebrew_copypaste_http_results.json", {
        "gate": "PASS" if all(item["pass"] for item in http_rows) else "FAIL",
        "passed": sum(item["pass"] for item in http_rows),
        "total": len(http_rows),
        "results": http_rows,
    })
    dump("hebrew_copypaste_search_layers.json", {
        "normalized_query": "תהלתי אחטם לך",
        "sql_literal": sql_literal,
        "fts": fts,
        "trigram": trigram,
        "vector_required": False,
        "vector_used": False,
    })
    print(json.dumps({
        "batch": f"{sum(item['pass'] for item in positive_rows)}/{len(positive_rows)}",
        "negative": f"{sum(item['pass'] for item in negative_rows)}/{len(negative_rows)}",
        "http": f"{sum(item['pass'] for item in http_rows)}/{len(http_rows)}",
    }))


if __name__ == "__main__":
    asyncio.run(main())
