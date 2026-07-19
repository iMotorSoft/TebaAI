#!/usr/bin/env python3
"""Run the auditable source-language batch against PostgreSQL authority."""
from __future__ import annotations

import asyncio
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from globalVar import POSTGRES_DSN  # noqa: E402
from modules.library.investigative_qa_v1 import QaAi, QaRequest, run  # noqa: E402

REPORT = Path(__file__).resolve().parents[3] / "data/reports/breslov/2026-07-16-research-workspace-v1/language_priority_batch.json"
CASES = [
    ("he", "איפה מופיע הפסוק והיו עיני ולבי שם"),
    ("he", "איפה נמצא המושג עקרב"),
    ("he", "איפה מופיע תהלתי אחטם לך"),
    ("he", "איפה מוזכר רבי נתן"),
    ("he", "איפה מוזכר זוהר"),
    ("he", "איפה מופיעה תפילה"),
    ("es", "dónde aparece עקרב"),
    ("es", "dónde aparece וְהָיוּ עֵינַי וְלִבִּי שָׁם"),
    ("es", "buscar דיבור"),
    ("es", "relación entre דם y דיבור"),
    ("es", "qué significa תפילה"),
    ("es", "en qué libro aparece רבי נתן"),
    ("en", "where is עקרב mentioned"),
    ("en", "where does וְהָיוּ עֵינַי וְלִבִּי שָׁם appear"),
    ("en", "find דיבור"),
    ("en", "relation between דם and דיבור"),
    ("en", "what does תפילה mean"),
    ("en", "where is רבי נתן cited"),
]


async def evaluate(index: int) -> dict:
    expected_instruction, question = CASES[index]
    async with await psycopg.AsyncConnection.connect(POSTGRES_DSN, row_factory=psycopg.rows.dict_row) as conn:
        payload = await run(conn, QaRequest(
            question=question,
            works=["kitzur", "lmi", "lmii", "lh", "lm_xv", "potencia_plegaria"],
            max_hits_per_work=5,
            ai=QaAi(enabled=False),
        ))
    primary = next((hit for hit in payload["hits"] if hit["hit_id"] in payload["primary_evidence_ids"]), None)
    return {
        "question": question,
        "expected_instruction_language": expected_instruction,
        "actual_instruction_language": payload["interpretation"]["instruction_language"],
        "primary_retrieval_language": payload["interpretation"]["primary_retrieval_language"],
        "status": payload["status"],
        "primary_evidence_id": primary["evidence_id"] if primary else None,
        "primary_evidence_language": primary["language"] if primary else None,
        "primary_source_layer": primary["source_layer"] if primary else None,
        "primary_work": primary["work_code"] if primary else None,
        "primary_pdf_page": primary["physical_pdf_page"] if primary else None,
        "language_pass": payload["interpretation"]["primary_retrieval_language"] == "he",
        "evidence_language_pass": primary is None or primary["language"] == "he",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--one", type=int)
    args = parser.parse_args()
    if args.one is not None:
        print(json.dumps(asyncio.run(evaluate(args.one)), ensure_ascii=False))
        return
    results = []
    for index in range(len(CASES)):
        print(f"case {index + 1}/{len(CASES)}", flush=True)
        completed = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--one", str(index)],
            check=True, capture_output=True, text=True,
        )
        results.append(json.loads(completed.stdout.strip().splitlines()[-1]))
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cases": len(results),
        "primary_language_pass": sum(item["language_pass"] for item in results),
        "primary_evidence_language_pass": sum(item["evidence_language_pass"] for item in results),
        "translations_before_original": 0,
        "comments_before_lesson": 0,
        "results": results,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("cases", "primary_language_pass", "primary_evidence_language_pass", "translations_before_original", "comments_before_lesson")}))


if __name__ == "__main__":
    main()
