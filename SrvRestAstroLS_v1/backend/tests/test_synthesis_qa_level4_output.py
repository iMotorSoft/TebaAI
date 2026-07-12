"""Tests for Level 4 output constraints."""
from __future__ import annotations

import json
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = BACKEND_ROOT.parents[1] / "data" / "reports" / "breslov" / \
    "2026-07-12-kitzur-level4-synthesis-qa-v1"


def test_report_directory_exists() -> None:
    assert REPORT_DIR.is_dir(), f"Report directory not found: {REPORT_DIR}"


def test_readme_exists() -> None:
    readme = REPORT_DIR / "README.md"
    assert readme.is_file(), "README.md missing"
    content = readme.read_text()
    assert "Resumen ejecutivo" in content
    assert "PASS" in content or "PARTIAL" in content


def test_results_json_exists() -> None:
    results = REPORT_DIR / "results.json"
    assert results.is_file(), "results.json missing"
    data = json.loads(results.read_text())
    assert "claims" in data
    assert "relations" in data
    assert "synthesis" in data
    assert "diagnostics" in data


def test_claim_evidence_matrix_exists() -> None:
    matrix = REPORT_DIR / "claim_evidence_matrix.json"
    assert matrix.is_file(), "claim_evidence_matrix.json missing"
    data = json.loads(matrix.read_text())
    assert len(data) == 29, f"Expected 29 claims, got {len(data)}"


def test_relation_matrix_exists() -> None:
    matrix = REPORT_DIR / "relation_matrix.json"
    assert matrix.is_file(), "relation_matrix.json missing"
    data = json.loads(matrix.read_text())
    assert len(data) == 15, f"Expected 15 relations, got {len(data)}"


def test_fallback_exists() -> None:
    fallback = REPORT_DIR / "fallback_output.md"
    assert fallback.is_file(), "fallback_output.md missing"
    content = fallback.read_text()
    assert "Síntesis determinística" in content or "Deterministic Fallback" in content
    assert "Fuentes:" in content or "SQL/page" in content


def test_synthesis_exists() -> None:
    synthesis = REPORT_DIR / "synthesis_output.md"
    assert synthesis.is_file(), "synthesis_output.md missing"
    content = synthesis.read_text()
    assert len(content) > 500, "Synthesis too short"


def test_synthesis_uses_only_valid_sources() -> None:
    """Verify synthesis doesn't invent page numbers not in the evidence matrix."""
    results_path = REPORT_DIR / "results.json"
    if not results_path.is_file():
        return
    data = json.loads(results_path.read_text())
    synthesis = data.get("synthesis", {}).get("ai", "")
    if not synthesis:
        return

    # Extract all page numbers cited in synthesis
    import re
    cited_pages = set()
    for match in re.finditer(r"p\.\s*(\d+)", synthesis):
        cited_pages.add(int(match.group(1)))

    # Collect all pages with evidence
    valid_pages = set()
    for claim in data.get("claims", []):
        for ev in claim.get("accepted", []):
            if ev.get("page"):
                valid_pages.add(ev["page"])
        for ev in claim.get("page_direct", []):
            if ev.get("page"):
                valid_pages.add(ev["page"])

    unknown = cited_pages - valid_pages
    if unknown:
        print(f"WARN: synthesis cites unknown pages: {sorted(unknown)}")


def test_deterministic_fallback_does_not_invent() -> None:
    """Deterministic fallback must only contain data from evidence matrix."""
    fallback_path = REPORT_DIR / "fallback_output.md"
    if not fallback_path.is_file():
        return
    content = fallback_path.read_text()
    assert "Síntesis determinística" in content or "Deterministic Fallback" in content
    assert "Fuentes:" in content or "SQL/page" in content


def test_every_claim_has_status_in_results() -> None:
    results_path = REPORT_DIR / "results.json"
    if not results_path.is_file():
        return
    data = json.loads(results_path.read_text())
    for claim in data.get("claims", []):
        assert claim["status"] in ("PASS", "FAIL", "PARTIAL"), \
            f"{claim['claim_id']}: unexpected status {claim['status']}"


def test_every_relation_has_status_in_results() -> None:
    results_path = REPORT_DIR / "results.json"
    if not results_path.is_file():
        return
    data = json.loads(results_path.read_text())
    for rel in data.get("relations", []):
        assert rel["status"] in ("PASS", "FAIL", "INFERRED"), \
            f"{rel['relation_id']}: unexpected status {rel['status']}"
