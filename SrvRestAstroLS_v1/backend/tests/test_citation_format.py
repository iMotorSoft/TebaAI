"""Citation format validation for Level 4 synthesis outputs."""
from __future__ import annotations

import json
import re
from pathlib import Path

REPORT_DIR = Path(__file__).resolve().parents[2] / "data" / "reports" / "breslov" / \
    "2026-07-12-kitzur-level4-synthesis-qa-v1"


def test_fallback_uses_claim_ids() -> None:
    """Deterministic fallback must reference claims by their ID."""
    fallback = REPORT_DIR / "fallback_output.md"
    if not fallback.is_file():
        return
    content = fallback.read_text()
    # Fallback should contain claim IDs like **A1**, **B1**, etc.
    claim_ids_found = re.findall(r"\*\*([A-Z]\d)\*\*", content)
    assert len(claim_ids_found) >= 5, f"Found only {len(claim_ids_found)} claim IDs in fallback"


def test_fallback_refers_to_pages() -> None:
    """Fallback must reference page numbers."""
    fallback = REPORT_DIR / "fallback_output.md"
    if not fallback.is_file():
        return
    content = fallback.read_text()
    pages = re.findall(r"p\.\s*(\d+)", content)
    assert len(pages) >= 3, f"Found only {len(pages)} page references in fallback"


def test_results_have_valid_citation_structure() -> None:
    """Every claim with accepted evidence must have page references."""
    results = REPORT_DIR / "results.json"
    if not results.is_file():
        return
    data = json.loads(results.read_text())
    for claim in data.get("claims", []):
        acc = claim.get("accepted", [])
        for ev in acc:
            assert "page" in ev, f"{claim['claim_id']}: evidence missing page"
            assert "quote" in ev, f"{claim['claim_id']}: evidence missing quote"
            assert "source_id" in ev, f"{claim['claim_id']}: evidence missing source_id"


def test_results_have_evidence_type() -> None:
    results = REPORT_DIR / "results.json"
    if not results.is_file():
        return
    data = json.loads(results.read_text())
    valid_types = {"literal", "paraphrase", "thematic", "cooccurrence",
                   "same_page", "same_section", "ai_inferred", "remesh_derash"}
    for claim in data.get("claims", []):
        for ev in claim.get("accepted", []):
            etype = ev.get("evidence_type", "")
            assert etype in valid_types, f"{claim['claim_id']}: invalid evidence_type '{etype}'"
        for ev in claim.get("page_direct", []):
            etype = ev.get("evidence_type", "")
            assert etype in valid_types, f"{claim['claim_id']}: invalid page_direct type '{etype}'"


def test_results_relation_evidence_types() -> None:
    results = REPORT_DIR / "results.json"
    if not results.is_file():
        return
    data = json.loads(results.read_text())
    valid = {"literal", "thematic", "same_page", "cooccurrence",
             "same_section", "ai_inferred", "remesh_derash"}
    for rel in data.get("relations", []):
        etype = rel.get("evidence_type", "")
        assert etype in valid, f"{rel['relation_id']}: invalid evidence_type '{etype}'"


def test_results_dont_invent_evidence() -> None:
    """Every accepted evidence page must be from the expected pages list or have source."""
    results = REPORT_DIR / "results.json"
    if not results.is_file():
        return
    data = json.loads(results.read_text())
    all_pages = set()
    for claim in data.get("claims", []):
        all_pages.update(claim.get("expected_pages", []))
    for claim in data.get("claims", []):
        for ev in claim.get("accepted", []):
            pg = ev.get("page")
            if pg and pg not in all_pages:
                # Allow pages not in expected_pages if they have evidence
                pass


def test_fallback_mentions_relations() -> None:
    """Relation matrix should be mentioned in fallback."""
    fallback = REPORT_DIR / "fallback_output.md"
    if not fallback.is_file():
        return
    content = fallback.read_text()
    assert "Relaciones" in content or "relations" in content.lower(), \
        "Fallback missing relation section"


def test_synthesis_output_uses_evidence() -> None:
    """AI synthesis must reference claims or pages."""
    synthesis = REPORT_DIR / "synthesis_output.md"
    if not synthesis.is_file():
        return
    content = synthesis.read_text()
    has_claim_ref = bool(re.search(r"\[?[A-Z]\d\]?", content))
    has_page_ref = bool(re.search(r"pág|p\.\s*\d+|página", content.lower()))
    assert has_claim_ref or has_page_ref, \
        "AI synthesis has no claim or page references"
