"""Likutey Halajot / LM II 8 identity conflict regression tests V1.

The disputed `ready` row `Likutey Halajot LM II 8` (The Rosenberg Edition) is a
Likutey Halajot anthology that develops Likutey Moharán II, lesson 8. These
tests lock the persisted canonical identity contract (ADR-019) so that any
future re-classification, metadata removal or scope heuristic regression fails
immediately. The live-DB re-verification is performed by
`scripts/audit_likutey_halajot_lmii8_conflict_v1.py`; this file uses the
captured 2026-08-06 snapshot.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from modules.library.canonical_metadata import (
    document_matches_scope,
    identity_from_document,
    resolve_canonical_scope,
)

FIXTURE = Path(__file__).parent / "fixtures" / "likutey_halajot_lmii8_conflict_v1.json"

ROSENBERG = "56ddcc3b-8296-4832-ac95-2bfe032cd4c6"
INTERIOR_FINAL = "132a791a-d12b-45bc-9b34-dd143605de12"
LMII = "3715c6e0-db56-49a1-82df-62d0a4d0b5cd"


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _rows() -> tuple[list[dict], dict]:
    fixture = _fixture()
    rows = list(fixture["documents"].values())
    identities = {str(r["document_id"]): identity_from_document(r) for r in rows}
    return rows, identities


@pytest.fixture(scope="module")
def available() -> dict:
    _rows_all, identities = _rows()
    return identities


def test_rosenberg_identity_is_persisted_lh_developing_lmii_8(available: dict) -> None:
    """The disputed row keeps work_family=LH and source=LM II:8 (ADR-019)."""
    ident = available[ROSENBERG]
    assert ident.family_code == "likutey_halajot"
    assert ident.canonical_work_code == "likutey_halajot"
    assert ident.edition.value == "The Rosenberg Edition"
    assert ident.edition.confidence == "explicit"
    assert ident.volume.value is None
    assert ident.volume.confidence == "unresolved"
    assert len(ident.source_identities) == 1
    source = ident.source_identities[0]
    assert source.work_code == "likutey_moharan_ii"
    assert source.lesson_number == 8
    assert source.relation == "develops"
    assert source.confidence == "explicit"


def test_interior_final_keeps_lh_family_and_technical_version_not_volume(available: dict) -> None:
    ident = available[INTERIOR_FINAL]
    assert ident.family_code == "likutey_halajot"
    assert ident.edition.value == "Interior Final"
    assert ident.edition.confidence == "derived"
    assert ident.volume.value is None
    # `v2` is the page-first pipeline technical version, never volume 2.
    assert ident.technical_version.value == "v2"
    assert not ident.source_identities  # source relations stay at section/chunk level


def test_original_lmii_keeps_its_own_family(available: dict) -> None:
    ident = available[LMII]
    assert ident.family_code == "likutey_moharan_ii"
    assert ident.canonical_work_code == "likutey_moharan_ii"
    assert ident.technical_version.value == "layout_v1"


def test_lh_lmii8_query_scopes_only_rosenberg(available: dict) -> None:
    """`Likutey Halajot LM II 8` selects only the anthology that declares the
    lmii:8 source relation; Interior Final must not be pulled in."""
    _rows_all, identities = _rows()
    scope = resolve_canonical_scope("Likutey Halajot LM II 8", list(identities.values()))
    assert scope.family_codes == ("likutey_halajot",)
    assert scope.source_work_code == "likutey_moharan_ii"
    assert scope.source_lesson == 8
    selected = [did for did, ident in identities.items() if document_matches_scope(ident, scope)]
    assert selected == [ROSENBERG]


def test_lmii_scope_excludes_lh_commentary(available: dict) -> None:
    """A plain LM II query must NOT contaminate the scope with the LH anthology."""
    _rows_all, identities = _rows()
    scope = resolve_canonical_scope("Likutey Moharán II", list(identities.values()))
    assert scope.family_codes == ("likutey_moharan_ii",)
    selected = [did for did, ident in identities.items() if document_matches_scope(ident, scope)]
    assert selected == [LMII]
    assert ROSENBERG not in selected


def test_ambiguous_short_queries_return_no_documents(available: dict) -> None:
    _rows_all, identities = _rows()
    for query in ("Likutey", "LM"):
        scope = resolve_canonical_scope(query, list(identities.values()))
        assert scope.ambiguous is True
        assert "scope_ambiguous" in scope.warnings
        assert document_matches_scope(
            identities[ROSENBERG], scope
        ) is False  # never auto-select an arbitrary family


def test_lesson_number_never_becomes_volume_or_edition(available: dict) -> None:
    """The `8` in `LM II 8` is a source lesson, not a volume or edition."""
    ident = available[ROSENBERG]
    assert ident.volume.value is None
    assert ident.edition.value == "The Rosenberg Edition"
    assert "8" not in str(ident.volume.value or "")
