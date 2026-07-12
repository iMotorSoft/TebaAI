"""Standardized citation format for synthesis QA outputs.

Canonical format:

  [claim A1, p. 471]
  [relation R13, p. 312]

All citations must reference entries in the evidence matrix.
AI synthesis is restricted to citing only known claim/relation IDs with verified pages.
"""
from __future__ import annotations

import re
from typing import Any


CITATION_PATTERN = re.compile(r"\[(claim|relation)\s+([A-Z]\d+),\s*p\.\s*(\d+)\]")
CLAIM_ID_PATTERN = re.compile(r"^[A-H]\d$")
RELATION_ID_PATTERN = re.compile(r"^R\d{1,2}$")


def format_claim_citation(claim_id: str, page: int) -> str:
    return f"[claim {claim_id}, p. {page}]"


def format_relation_citation(relation_id: str, page: int) -> str:
    return f"[relation {relation_id}, p. {page}]"


def extract_citations(text: str) -> list[dict[str, Any]]:
    """Extract structured citations from text."""
    citations = []
    for match in CITATION_PATTERN.finditer(text):
        citations.append({
            "type": match.group(1),
            "id": match.group(2),
            "page": int(match.group(3)),
            "full": match.group(0),
        })
    return citations


def validate_citation(citation: dict[str, Any],
                      claim_ids: set[str],
                      relation_ids: set[str],
                      valid_pages: set[int]) -> dict[str, Any]:
    """Validate a single citation against known IDs and pages."""
    issues = []
    ctype = citation["type"]
    cid = citation["id"]
    page = citation["page"]

    if ctype == "claim" and cid not in claim_ids:
        issues.append(f"unknown_claim_id:{cid}")
    if ctype == "relation" and cid not in relation_ids:
        issues.append(f"unknown_relation_id:{cid}")
    if page not in valid_pages:
        issues.append(f"unknown_page:{page}")

    return {
        **citation,
        "valid": len(issues) == 0,
        "issues": issues,
    }


def validate_citations_in_text(
    text: str,
    claim_ids: set[str],
    relation_ids: set[str],
    valid_pages: set[int],
) -> list[dict[str, Any]]:
    citations = extract_citations(text)
    return [validate_citation(c, claim_ids, relation_ids, valid_pages) for c in citations]


def build_citation_block(claims: list[dict[str, Any]],
                         relations: list[dict[str, Any]] | None = None) -> str:
    """Build a structured citation block from evidence matrix."""
    lines: list[str] = []
    for c in claims:
        for ev in c.get("accepted", [])[:1]:
            pg = ev.get("page")
            if pg:
                lines.append(format_claim_citation(c["claim_id"], pg))
    if relations:
        for r in relations:
            if r.get("status") == "PASS" and r.get("shared_pages"):
                for pg in r["shared_pages"][:1]:
                    lines.append(format_relation_citation(r["relation_id"], pg))
    return "\n".join(lines)


def ai_synthesis_prompt_suffix() -> str:
    """Return the standard citation instructions to append to AI system prompts."""
    return (
        "\n\nREGLAS DE CITACION:\n"
        "- Toda afirmación factual debe citarse usando EXACTAMENTE este formato: [claim X, p. N]\n"
        "- Para relaciones: [relation X, p. N]\n"
        "- Solo puedes usar IDs de claim (A1-H2) y relation (R1-R15) que aparezcan en las fuentes.\n"
        "- NO inventes citas. Si no hay fuente, escribí SIN_EVIDENCIA.\n"
        "- Cada claim_id citado debe existir en la lista de fuentes.\n"
        "- Cada página citada debe corresponder a la fuente del claim."
    )
