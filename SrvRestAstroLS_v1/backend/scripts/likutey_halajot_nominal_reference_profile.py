"""Read-only profile of literal nominal references in Likutey Halajot source zones."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from likutey_halajot_nominal_reference_detector import classify_script, fetch_parents, find_candidates, quote_context
import psycopg
from psycopg.rows import dict_row
from globalVar import POSTGRES_DSN


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=Path(__file__).resolve().parents[3] / "data/reports/breslov" / f"{date.today():%Y-%m-%d}-likutey-halajot-nominal-reference-extraction-v1" / "nominal_reference_profile_report.md")
    args = parser.parse_args()
    rows: list[dict] = []
    async with await psycopg.AsyncConnection.connect(POSTGRES_DSN, row_factory=dict_row) as conn:
        async with conn.cursor() as cur:
            for parent in await fetch_parents(cur):
                for candidate in find_candidates(parent["parent_literal"] or ""):
                    context = quote_context(parent["parent_literal"], candidate.char_start, candidate.char_end)
                    language, script = classify_script(candidate.surface_form)
                    rows.append({"pdf_page": parent["pdf_page"], "printed_page": parent["printed_page"], "parent_note_unit_id": str(parent["parent_note_source_unit_id"]) if parent["parent_note_source_unit_id"] else None,
                                 "parent_fine_zone_id": str(parent["parent_fine_zone_id"]) if parent["parent_fine_zone_id"] else None, "visible_note_number": parent["visible_note_number"],
                                 "halakhah_header_hint": parent["halakhah_header_hint"], "candidate_reference_text": candidate.surface_form,
                                 "quote_context": context, "reference_kind_candidate": candidate.reference_kind, "source_table": "library_likutey_halajot_note_source_units_v1" if parent["parent_note_source_unit_id"] else "library_likutey_halajot_fine_zones_v1",
                                 "language": language, "script": script,
                                 "appears_exactly_in_parent": context in parent["parent_literal"], "appears_exactly_in_page_first": context in parent["page_literal"], "initial_confidence": candidate.confidence, "ambiguous": candidate.ambiguous})
    kinds = Counter(row["reference_kind_candidate"] for row in rows)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("# Likutey Halajot nominal reference profile V1\n\n"
                           f"- Candidates: {len(rows)}\n- AI: `ai_not_required_for_v1`\n- All candidates below remain literal-only metadata; no relationships or authorship are asserted.\n\n"
                           "## By conservative kind\n\n" + "\n".join(f"- `{kind}`: {count}" for kind, count in sorted(kinds.items())) +
                           "\n\n## Candidate sample\n\n```json\n" + json.dumps(rows[:50], ensure_ascii=False, indent=2) + "\n```\n", encoding="utf-8")
    print(json.dumps({"report": str(args.report), "candidates": len(rows), "by_kind": kinds}, default=dict, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
