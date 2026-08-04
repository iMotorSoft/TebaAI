"""Canonical work/edition/source metadata V1 contract tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from modules.library.canonical_metadata import (
    CanonicalValue,
    content_query_without_scope_surfaces,
    document_matches_scope,
    filter_documents_for_scope,
    identity_from_document,
    resolve_canonical_scope,
    resolve_family_mentions,
)

FIXTURE = Path(__file__).parent / "fixtures" / "canonical_work_edition_source_metadata_v1.json"


def fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def contract(
    family: str,
    label: str,
    *,
    edition: str | None = None,
    edition_confidence: str = "unresolved",
    source: bool = False,
    technical_version: str | None = None,
) -> dict:
    return {
        "work_identity": {
            "family_code": family,
            "family_label": label,
            "canonical_work_code": family,
            "canonical_work_label": label,
        },
        "edition_identity": {
            "edition_label": edition,
            "edition_confidence": edition_confidence,
            "edition_source": "fixture" if edition else "unresolved",
            "volume_number": None,
            "volume_confidence": "unresolved",
            "volume_source": "unresolved",
        },
        "source_identities": ([{
            "source_work_code": "likutey_moharan_ii",
            "source_work_label": "Likutey Moharán II",
            "source_lesson": 8,
            "source_relation": "develops",
            "confidence": "explicit",
            "source": "fixture_front_matter",
        }] if source else []),
        "technical_identity": {
            "version": technical_version,
            "confidence": "derived" if technical_version else "unresolved",
            "source": "fixture_pipeline" if technical_version else "unresolved",
        },
    }


def row(
    key: str,
    family: str,
    label: str,
    *,
    edition: str | None = None,
    edition_confidence: str = "unresolved",
    source: bool = False,
    technical_version: str | None = None,
) -> dict:
    return {
        "document_id": key,
        "title": label if not edition else f"{label} — {edition}",
        "source_filename": f"{key}.pdf",
        "source_sha256": key * 64 if len(key) == 1 else key.ljust(64, "0")[:64],
        "status": "test_candidate" if key == "i" else "ready",
        "document_code": f"{family}_{technical_version}" if technical_version else None,
        "metadata": {"pipeline": f"page_first_{technical_version}"} if technical_version else {},
        "bibliographic_metadata": {
            "canonical_identity_v1": contract(
                family,
                label,
                edition=edition,
                edition_confidence=edition_confidence,
                source=source,
                technical_version=technical_version,
            )
        },
    }


def identities() -> tuple[list[dict], list]:
    rows = [
        row("r", "likutey_halajot", "Likutey Halajot", edition="The Rosenberg Edition", edition_confidence="explicit", source=True),
        row("i", "likutey_halajot", "Likutey Halajot", edition="Interior Final", edition_confidence="derived", technical_version="v2"),
        row("m", "likutey_moharan_ii", "Likutey Moharán II", edition="Edición española BRI", edition_confidence="derived", technical_version="layout_v1"),
    ]
    return rows, [identity_from_document(item) for item in rows]


@pytest.mark.parametrize("alias", fixture()["work_families"]["likutey_halajot"]["aliases"])
def test_lh_aliases_are_exact_and_canonical(alias: str) -> None:
    assert resolve_family_mentions(alias) == ("likutey_halajot",)


@pytest.mark.parametrize("alias", fixture()["work_families"]["likutey_moharan_ii"]["aliases"])
def test_lmii_aliases_are_exact_and_canonical(alias: str) -> None:
    assert resolve_family_mentions(alias) == ("likutey_moharan_ii",)


def test_likutey_shared_token_does_not_resolve_family() -> None:
    assert resolve_family_mentions("Likutey") == ()


def test_lh_document_can_explicitly_develop_lmii_lesson_8() -> None:
    rows, _identities = identities()
    identity = identity_from_document(rows[0])

    assert identity.family_code == "likutey_halajot"
    assert identity.source_identities[0].work_code == "likutey_moharan_ii"
    assert identity.source_identities[0].lesson_number == 8
    assert identity.source_identities[0].relation == "develops"
    assert identity.volume.value is None


def test_interior_final_keeps_technical_v2_separate_from_volume() -> None:
    rows, _identities = identities()
    identity = identity_from_document(rows[1])

    assert identity.family_code == "likutey_halajot"
    assert identity.edition.value == "Interior Final"
    assert identity.edition.confidence == "derived"
    assert identity.technical_version.value == "v2"
    assert identity.volume.public() == {
        "value": None,
        "confidence": "unresolved",
        "source": "unresolved",
        "warnings": [],
    }


def test_metadata_confidence_invariants() -> None:
    with pytest.raises(ValueError, match="non-null"):
        CanonicalValue(2, "unresolved", "unresolved")
    with pytest.raises(ValueError, match="null"):
        CanonicalValue(None, "explicit", "pdf_page_10")


def test_volume_rejects_technical_or_source_lesson_provenance() -> None:
    bad = row("x", "likutey_halajot", "Likutey Halajot")
    edition = bad["bibliographic_metadata"]["canonical_identity_v1"]["edition_identity"]
    edition.update({"volume_number": 2, "volume_confidence": "derived", "volume_source": "technical_version_v2"})
    with pytest.raises(ValueError, match="volume cannot"):
        identity_from_document(bad)


def test_family_scope_includes_multiple_lh_editions_only() -> None:
    rows, available = identities()
    scope = resolve_canonical_scope("¿Dónde habla Likutey Halajot?", available)
    selected, _ = filter_documents_for_scope(rows, scope)

    assert {item["document_id"] for item in selected} == {"r", "i"}


def test_edition_scope_restricts_interior_final() -> None:
    rows, available = identities()
    scope = resolve_canonical_scope("Buscá esto solo en Interior Final", available)
    selected, _ = filter_documents_for_scope(rows, scope)

    assert scope.edition == "Interior Final"
    assert [item["document_id"] for item in selected] == ["i"]


def test_edition_scope_surface_is_not_part_of_heading_lookup() -> None:
    _rows, available = identities()
    query = "¿Dónde aparece MELODÍAS Y PLEGARIAS en Interior Final?"
    scope = resolve_canonical_scope(query, available)

    assert content_query_without_scope_surfaces(query, scope, available) == "MELODÍAS Y PLEGARIAS"


def test_document_scope_restricts_one_instance() -> None:
    rows, available = identities()
    target = rows[1]["source_sha256"]
    scope = resolve_canonical_scope("consulta", available, scope_document_sha256=target)
    selected, _ = filter_documents_for_scope(rows, scope)

    assert [item["document_id"] for item in selected] == ["i"]


def test_lh_source_scope_selects_commentary_not_original() -> None:
    rows, available = identities()
    scope = resolve_canonical_scope(
        "¿Dónde desarrolla Likutey Halajot la lección 8 de Likutey Moharán II?",
        available,
    )
    selected, _ = filter_documents_for_scope(rows, scope)

    assert scope.family_codes == ("likutey_halajot",)
    assert scope.source_work_code == "likutey_moharan_ii"
    assert scope.source_lesson == 8
    assert [item["document_id"] for item in selected] == ["r"]


def test_original_lmii_scope_excludes_lh_commentary() -> None:
    rows, available = identities()
    scope = resolve_canonical_scope("¿Dónde está la lección 8 de Likutey Moharán II?", available)
    selected, _ = filter_documents_for_scope(rows, scope)

    assert scope.family_codes == ("likutey_moharan_ii",)
    assert [item["document_id"] for item in selected] == ["m"]


def test_explicit_source_scope_can_cross_original_and_commentary() -> None:
    rows, available = identities()
    scope = resolve_canonical_scope(
        "plegaria",
        available,
        scope_source_work="Likutey Moharán II",
        scope_source_lesson=8,
    )
    selected, _ = filter_documents_for_scope(rows, scope)

    assert scope.family_codes == ()
    assert {item["document_id"] for item in selected} == {"m", "r"}


def test_cross_source_scope_includes_original_and_explicit_commentary() -> None:
    rows, available = identities()
    scope = resolve_canonical_scope("Compará Likutey Moharán II 8 con Likutey Halajot", available)
    selected, selected_identities = filter_documents_for_scope(rows, scope)

    assert scope.cross_family is True
    assert {item["document_id"] for item in selected} == {"m", "r"}
    assert selected_identities["r"].source_identities[0].relation == "develops"


@pytest.mark.parametrize("query", ["Likutey", "LM"])
def test_ambiguous_scope_returns_no_documents_and_warning(query: str) -> None:
    rows, available = identities()
    scope = resolve_canonical_scope(query, available)
    selected, _ = filter_documents_for_scope(rows, scope)

    assert scope.ambiguous is True
    assert "scope_ambiguous" in scope.warnings
    assert selected == []


def test_source_lesson_and_technical_version_never_change_family() -> None:
    rows, _available = identities()
    lh = identity_from_document(rows[0])
    interior = identity_from_document(rows[1])

    assert lh.family_code == interior.family_code == "likutey_halajot"
    assert lh.source_identities[0].lesson_number == 8
    assert interior.technical_version.value == "v2"
    assert lh.volume.value is interior.volume.value is None
