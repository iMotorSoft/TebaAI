"""Tests for Level 4 relation matrix."""
from __future__ import annotations

from scripts.library_synthesis_qa_level4_decomposition import (
    DECOMPOSITION,
    RELATIONS,
    get_claim_by_id,
    get_relations_for_claim,
)


def test_relation_count() -> None:
    assert len(RELATIONS) == 15


def test_relation_ids_are_unique() -> None:
    ids = [r["relation_id"] for r in RELATIONS]
    assert len(ids) == len(set(ids))


def test_every_relation_has_description() -> None:
    for r in RELATIONS:
        assert r["description"], f"{r['relation_id']} has no description"
        assert "→" in r["description"], f"{r['relation_id']} description missing →"


def test_every_relation_has_expected_type() -> None:
    valid = {"literal", "thematic"}
    for r in RELATIONS:
        assert r["expected_relation_type"] in valid, \
            f"{r['relation_id']}: invalid type {r['expected_relation_type']}"


def test_relations_reference_existing_claims() -> None:
    for r in RELATIONS:
        from_c = get_claim_by_id(r["from_claim_id"])
        to_c = get_claim_by_id(r["to_claim_id"])
        assert from_c is not None, f"{r['relation_id']} references missing from {r['from_claim_id']}"
        assert to_c is not None, f"{r['relation_id']} references missing to {r['to_claim_id']}"


def test_get_relations_for_claim_returns_correct_relations() -> None:
    r1 = get_relations_for_claim("B1")
    assert len(r1) >= 1
    assert any(r["relation_id"] == "R1" for r in r1)

    r_e2 = get_relations_for_claim("E2")
    assert any(r["relation_id"] == "R14" for r in r_e2)


def test_no_relation_uses_unknown_claim_id() -> None:
    all_ids = {c["claim_id"] for c in DECOMPOSITION}
    for r in RELATIONS:
        assert r["from_claim_id"] in all_ids, f"{r['relation_id']}: unknown {r['from_claim_id']}"
        assert r["to_claim_id"] in all_ids, f"{r['relation_id']}: unknown {r['to_claim_id']}"


def test_relations_cover_all_concepts() -> None:
    """At least one relation per concept category."""
    categories = {"proposito_final", "humildad", "verdad", "alegria",
                  "daat", "pureza_sexual", "tzadikim", "reconocer_tzadik"}
    related_claim_ids = set()
    for r in RELATIONS:
        related_claim_ids.add(r["from_claim_id"])
        related_claim_ids.add(r["to_claim_id"])
    covered_categories = set()
    for c in DECOMPOSITION:
        if c["claim_id"] in related_claim_ids:
            covered_categories.add(c["category"])
    uncovered = categories - covered_categories
    assert not uncovered, f"Categories without relations: {uncovered}"


def test_literal_relations_have_expected_type() -> None:
    """Literal relations should have from = to or same page expectation."""
    for r in RELATIONS:
        if r["expected_relation_type"] == "literal":
            from_c = get_claim_by_id(r["from_claim_id"])
            to_c = get_claim_by_id(r["to_claim_id"])
            assert from_c is not None and to_c is not None
            assert r["from_claim_id"] == r["to_claim_id"] or \
                   from_c["category"] == to_c["category"], \
                f"{r['relation_id']}: literal but claims are in different categories"
