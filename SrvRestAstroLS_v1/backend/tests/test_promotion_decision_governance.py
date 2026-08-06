"""Likutey Halajot promotion decision governance tests V1.

Locks the editorial/legal review package contract and the joint promotion
decision rules. No human decision is ever invented: pending states yield
blocked results, and the package defaults must remain pending.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from modules.library.content_manager_schemas import IngestionStage
from modules.library.content_manager_state import ALLOWED_TRANSITIONS, can_cancel

PACKAGE = (
    Path(__file__).resolve().parents[3]
    / "data/reports/breslov/2026-08-06-likutey-halajot-editorial-legal-review-v1/package-contract.json"
)

EDITORIAL_APPROVED = {"EDITORIAL_APPROVED", "EDITORIAL_APPROVED_WITH_NON_BLOCKING_NOTES"}
LEGAL_APPROVED = {"LEGAL_APPROVED_FOR_DEFINED_USE", "LEGAL_APPROVED_WITH_RESTRICTIONS"}


def joint_promotion_decision(editorial_status: str, legal_status: str) -> str:
    """Phase contract: a promotion gate opens only with both human approvals."""
    if editorial_status not in EDITORIAL_APPROVED and legal_status not in LEGAL_APPROVED:
        return "BLOCKED_EDITORIAL_AND_LEGAL_REVIEW_REQUIRED"
    if editorial_status not in EDITORIAL_APPROVED:
        if editorial_status == "EDITORIAL_CHANGES_REQUIRED":
            return "NOT_APPROVED_FOR_PROMOTION"
        return "BLOCKED_EDITORIAL_REVIEW_REQUIRED"
    if legal_status not in LEGAL_APPROVED:
        if legal_status == "LEGAL_NOT_APPROVED":
            return "NOT_APPROVED_FOR_PROMOTION"
        return "BLOCKED_LEGAL_REVIEW_REQUIRED"
    return "APPROVED_TO_OPEN_CONTROLLED_PROMOTION_GATE"


def _contract() -> dict:
    assert PACKAGE.is_file(), f"package contract missing: {PACKAGE}"
    return json.loads(PACKAGE.read_text(encoding="utf-8"))


def test_package_is_read_only_and_not_promoting() -> None:
    contract = _contract()
    assert contract["promotion_executed"] is False
    assert contract["document_id"] == "132a791a-d12b-45bc-9b34-dd143605de12"
    assert contract["technical_result"] == "TECHNICALLY_READY_FOR_EDITORIAL_REVIEW"


def test_editorial_review_pending_by_default_without_invented_reviewer() -> None:
    editorial = _contract()["editorial_review"]
    assert editorial["status"] == "EDITORIAL_REVIEW_PENDING"
    assert editorial["reviewer"] is None
    assert editorial["decision_date"] is None


def test_legal_review_required_by_default_without_invented_reviewer() -> None:
    legal = _contract()["legal_review"]
    assert legal["status"] == "LEGAL_REVIEW_REQUIRED"
    assert legal["reviewer"] is None
    assert legal["decision_date"] is None
    assert isinstance(legal["restrictions"], list)  # serializable


def test_joint_result_defaults_to_blocked_until_human_decisions() -> None:
    contract = _contract()
    decision = joint_promotion_decision(
        contract["editorial_review"]["status"], contract["legal_review"]["status"]
    )
    assert decision == "BLOCKED_EDITORIAL_AND_LEGAL_REVIEW_REQUIRED"
    assert contract["promotion_decision"] == decision


@pytest.mark.parametrize(
    ("editorial", "legal", "expected"),
    [
        ("EDITORIAL_APPROVED", "LEGAL_APPROVED_FOR_DEFINED_USE", "APPROVED_TO_OPEN_CONTROLLED_PROMOTION_GATE"),
        ("EDITORIAL_APPROVED_WITH_NON_BLOCKING_NOTES", "LEGAL_APPROVED_WITH_RESTRICTIONS", "APPROVED_TO_OPEN_CONTROLLED_PROMOTION_GATE"),
        ("EDITORIAL_CHANGES_REQUIRED", "LEGAL_APPROVED_FOR_DEFINED_USE", "NOT_APPROVED_FOR_PROMOTION"),
        ("EDITORIAL_APPROVED", "LEGAL_REVIEW_REQUIRED", "BLOCKED_LEGAL_REVIEW_REQUIRED"),
        ("EDITORIAL_REVIEW_PENDING", "LEGAL_APPROVED_FOR_DEFINED_USE", "BLOCKED_EDITORIAL_REVIEW_REQUIRED"),
        ("EDITORIAL_REVIEW_PENDING", "LEGAL_REVIEW_REQUIRED", "BLOCKED_EDITORIAL_AND_LEGAL_REVIEW_REQUIRED"),
        ("EDITORIAL_APPROVED", "LEGAL_NOT_APPROVED", "NOT_APPROVED_FOR_PROMOTION"),
    ],
)
def test_joint_decision_matrix(editorial: str, legal: str, expected: str) -> None:
    assert joint_promotion_decision(editorial, legal) == expected


def test_human_evidence_required_never_invents_approval() -> None:
    contract = _contract()
    for review in (contract["editorial_review"], contract["legal_review"]):
        # An approval with no reviewer/date/evidence is not a real approval.
        if review["status"].startswith("EDITORIAL_APPROVED") or review["status"].startswith("LEGAL_APPROVED"):
            assert review["reviewer"] is not None
            assert review["decision_date"] is not None


def test_queued_job_with_zero_resources_is_cancellable() -> None:
    # The reconciled orphan job was queued with zero resources (state machine).
    assert can_cancel(IngestionStage.QUEUED)
    assert IngestionStage.CANCELLED in ALLOWED_TRANSITIONS[IngestionStage.QUEUED]


def test_jobs_with_writes_or_active_claim_cannot_be_cancelled() -> None:
    assert not can_cancel(IngestionStage.CLAIMED)      # claimed by a worker
    assert not can_cancel(IngestionStage.EMBEDDING)    # writes started
    assert not can_cancel(IngestionStage.INDEXING)     # writes started
    assert not can_cancel(IngestionStage.COMPLETED)    # terminal
    assert not can_cancel(IngestionStage.FAILED)       # terminal


def test_cancellation_is_a_recorded_transition() -> None:
    # queued -> cancelled must be an allowed, audited transition.
    assert IngestionStage.CANCELLED in ALLOWED_TRANSITIONS[IngestionStage.QUEUED]
    # And it must not be reachable from write states.
    for stage in (IngestionStage.CLAIMED, IngestionStage.EMBEDDING, IngestionStage.INDEXING):
        assert IngestionStage.CANCELLED not in ALLOWED_TRANSITIONS.get(stage, ())
