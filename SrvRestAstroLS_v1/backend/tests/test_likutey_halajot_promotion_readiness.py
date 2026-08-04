"""Pure, non-persistent gate for Likutey Halajot promotion readiness V1."""

from __future__ import annotations

import json
from pathlib import Path

from modules.library.simple_research_rag import merge_results

FIXTURE = Path(__file__).parent / "fixtures" / "likutey_halajot_promotion_readiness_v1.json"


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _retrievable(status: str, *, include_test_candidates: bool) -> bool:
    """Mirror the repository status predicate without touching PostgreSQL."""
    return status == "ready" or (include_test_candidates and status == "test_candidate")


def test_readiness_fixture_resolves_identity_without_document_id() -> None:
    fixture = _fixture()
    identity = fixture["document_identity"]
    assert "document_id" not in identity
    assert identity["sha256"] == "440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a"
    assert identity["filename"] == "LIKUTEY HALAJOT (Interior Final).pdf"
    assert identity["status_before"] == identity["status_after_audit"] == "test_candidate"


def test_readiness_fixture_has_complete_non_promoting_contract() -> None:
    fixture = _fixture()
    integrity = fixture["integrity_expectations"]
    assert (integrity["physical_pages"], integrity["chunks"], integrity["embeddings"]) == (284, 268, 268)
    assert len(fixture["editorial_goldens"]) == 5
    assert all(value == 0 for value in (
        integrity["missing_vectors"],
        integrity["orphan_vectors"],
        integrity["duplicate_vectors"],
    ))
    recommendation = fixture["promotion_recommendation"]
    assert recommendation["result"] == "NOT_READY_FOR_PROMOTION"
    assert recommendation["promotion_executed"] is False
    assert recommendation["status_change_authorized"] is False


def test_status_change_only_expands_normal_retrievability() -> None:
    assert _retrievable("test_candidate", include_test_candidates=True)
    assert not _retrievable("test_candidate", include_test_candidates=False)
    assert _retrievable("ready", include_test_candidates=True)
    assert _retrievable("ready", include_test_candidates=False)


def test_exact_editorial_evidence_outranks_ready_semantic_candidate() -> None:
    semantic = [{
        "chunk_id": "ready-semantic",
        "document_id": "ready-document",
        "document_status": "ready",
        "semantic_score": 0.99,
        "semantic_rank": 1,
    }]
    literal = [{
        "chunk_id": "candidate-exact",
        "document_id": "candidate-document",
        "document_status": "test_candidate",
        "literal_score": 2.0,
        "literal_match_type": "structural_heading_exact",
        "exact_match": True,
        "exact_variant_count": 1,
    }]
    ranked = merge_results(semantic, literal, query_language="es")
    assert ranked[0]["chunk_id"] == "candidate-exact"


def test_simulated_ready_status_does_not_change_scores_or_tie_breaks() -> None:
    def ranked(status: str) -> list[tuple[str, float]]:
        rows = merge_results([], [{
            "chunk_id": "same-editorial-evidence",
            "document_id": "same-document",
            "document_status": status,
            "literal_score": 2.0,
            "literal_match_type": "footnote_literal_exact",
            "exact_match": True,
            "exact_variant_count": 1,
        }], query_language="es")
        return [(row["chunk_id"], row["combined_score"]) for row in rows]

    assert ranked("test_candidate") == ranked("ready")


def test_tomo_two_cannot_be_inferred_from_ingestion_version() -> None:
    expectation = _fixture()["bibliographic_expectations"]
    assert expectation["planner_required_volume_number"] is None
    assert expectation["planner_required_volume_source"] == "unresolved"
    assert "_v2" in expectation["forbidden_inference"]
