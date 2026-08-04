#!/usr/bin/env python3
"""Authenticated API gate for canonical metadata V1; no writes."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

import httpx

BASE = "http://127.0.0.1:7008"
INTERIOR_SHA = "440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a"
CASES = [
    ("family", "¿Dónde habla Likutey Halajot sobre la plegaria?", {}),
    ("edition", "¿Dónde aparece MELODÍAS Y PLEGARIAS en Interior Final?", {}),
    ("document", "MELODÍAS Y PLEGARIAS", {"scope_document_sha256": INTERIOR_SHA}),
    ("source", "¿Dónde desarrolla Likutey Halajot la lección 8 de Likutey Moharán II?", {}),
    ("original", "¿Dónde está la lección 8 de Likutey Moharán II?", {}),
    ("cross", "Compará Likutey Moharán II 8 con Likutey Halajot.", {}),
    ("planner", "Azamra, ¿en qué tomo de Likutey Halajot está?", {}),
    ("ambiguous", "Likutey", {}),
]


def summarize(name: str, query: str, response: httpx.Response) -> dict[str, Any]:
    body = response.json()
    hits = body.get("hits") or []
    return {
        "case": name,
        "query": query,
        "http_status": response.status_code,
        "research_status": body.get("research_status"),
        "warnings": body.get("warnings") or [],
        "canonical_scope": (body.get("retrieval") or {}).get("canonical_scope"),
        "answer_markdown": body.get("answer_markdown") if name == "planner" else None,
        "families": sorted({hit.get("work_family_code") for hit in hits if hit.get("work_family_code")}),
        "documents": sorted({hit.get("physical_file_name") for hit in hits if hit.get("physical_file_name")}),
        "primaries": [
            {
                key: hit.get(key)
                for key in (
                    "work_family_code", "work_family", "canonical_work", "edition",
                    "volume_number", "source_work_code", "source_work", "source_lesson",
                    "source_relation", "technical_version", "physical_file_name",
                    "physical_pdf_page", "printed_page", "match_kind",
                )
            }
            for hit in hits if hit.get("is_primary")
        ],
    }


def passed(row: dict[str, Any]) -> bool:
    name = row["case"]
    scope = row.get("canonical_scope") or {}
    if row["http_status"] != 200:
        return False
    if name == "family":
        return row["research_status"] in {"complete", "partial"} and row["families"] == ["likutey_halajot"]
    if name in {"edition", "document"}:
        return bool(row["primaries"]) and all(item["edition"] == "Interior Final" for item in row["primaries"])
    if name == "source":
        return bool(row["primaries"]) and all(
            item["work_family_code"] == "likutey_halajot"
            and item["source_work_code"] == "likutey_moharan_ii"
            and item["source_lesson"] == 8
            for item in row["primaries"]
        )
    if name == "original":
        return bool(row["primaries"]) and all(item["work_family_code"] == "likutey_moharan_ii" for item in row["primaries"])
    if name == "cross":
        return set(row["families"]) == {"likutey_halajot", "likutey_moharan_ii"} and scope.get("cross_family") is True
    if name == "planner":
        answer = row.get("answer_markdown") or ""
        return "Tomo no resuelto" in answer and "Tomo 2" not in answer
    if name == "ambiguous":
        return row["research_status"] == "no_evidence" and "scope_ambiguous" in row["warnings"]
    return False


async def role_run(role: str, email: str, password: str) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=240) as client:
        login = await client.post(f"{BASE}/auth/login", json={"email": email, "password": password})
        login.raise_for_status()
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        output = []
        for name, query, extra in CASES:
            response = await client.post(
                f"{BASE}/library/investigative-qa/v1",
                headers=headers,
                json={"question": query, "ai": {"enabled": False}, **extra},
            )
            row = summarize(name, query, response)
            row["role"] = role
            row["pass"] = passed(row)
            output.append(row)
        return output


async def main(output: Path) -> None:
    credentials = {
        "admin": (
            os.environ.get("TEBAAI_E2E_ADMIN_EMAIL"),
            os.environ.get("TEBAAI_E2E_ADMIN_PASSWORD"),
        ),
        "guest": (
            os.environ.get("TEBAAI_E2E_GUEST_EMAIL"),
            os.environ.get("TEBAAI_E2E_GUEST_PASSWORD"),
        ),
    }
    if any(not email or not password for email, password in credentials.values()):
        raise RuntimeError("admin and guest E2E credentials are required")
    rows = []
    for role, (email, password) in credentials.items():
        rows.extend(await role_run(role, str(email), str(password)))
    result = {
        "rows": rows,
        "passed": sum(row["pass"] for row in rows),
        "total": len(rows),
        "all_pass": all(row["pass"] for row in rows),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not result["all_pass"]:
        raise SystemExit(f"API gate failed: {result['passed']}/{result['total']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(main(args.output))
