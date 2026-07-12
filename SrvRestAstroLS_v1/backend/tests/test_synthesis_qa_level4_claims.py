"""Tests for Level 4 claim decomposition."""
from __future__ import annotations

from scripts.library_synthesis_qa_level4_decomposition import (
    DECOMPOSITION,
    LEVEL4_QUESTION_ID,
    RELATIONS,
    all_expected_pages,
    get_claim_by_id,
    get_claims_by_category,
)


def test_question_id_is_defined() -> None:
    assert LEVEL4_QUESTION_ID == "kitzur_level4_interconnection_01"


def test_decomposition_has_expected_claims() -> None:
    assert len(DECOMPOSITION) == 29


def test_all_categories_are_present() -> None:
    expected = {"proposito_final", "humildad", "verdad", "alegria", "daat",
                "pureza_sexual", "tzadikim", "reconocer_tzadik"}
    actual = {c["category"] for c in DECOMPOSITION}
    assert actual == expected, f"Missing: {expected - actual}"


def test_proposito_final_has_three_claims() -> None:
    claims = get_claims_by_category("proposito_final")
    assert len(claims) == 3
    assert claims[0]["claim_id"] == "A1"
    assert claims[2]["claim_id"] == "A3"


def test_humildad_has_three_claims() -> None:
    claims = get_claims_by_category("humildad")
    assert len(claims) == 3
    assert claims[0]["claim_id"] == "B1"


def test_verdad_has_three_claims() -> None:
    claims = get_claims_by_category("verdad")
    assert len(claims) == 3
    assert claims[0]["claim_id"] == "C1"


def test_alegria_has_four_claims() -> None:
    claims = get_claims_by_category("alegria")
    assert len(claims) == 4
    assert {c["claim_id"] for c in claims} == {"D1", "D2", "D3", "D4"}


def test_daat_has_three_claims() -> None:
    claims = get_claims_by_category("daat")
    assert len(claims) == 3
    assert claims[0]["claim_id"] == "E1"


def test_pureza_sexual_has_four_claims() -> None:
    claims = get_claims_by_category("pureza_sexual")
    assert len(claims) == 4
    assert {c["claim_id"] for c in claims} == {"F1", "F2", "F3", "F4"}


def test_tzadikim_has_seven_claims() -> None:
    claims = get_claims_by_category("tzadikim")
    assert len(claims) == 7
    assert claims[0]["claim_id"] == "G1"
    assert claims[6]["claim_id"] == "G7"


def test_reconocer_tzadik_has_two_claims() -> None:
    claims = get_claims_by_category("reconocer_tzadik")
    assert len(claims) == 2
    assert {c["claim_id"] for c in claims} == {"H1", "H2"}


def test_every_claim_has_expected_pages() -> None:
    for c in DECOMPOSITION:
        assert c["expected_pages"], f"{c['claim_id']} has no expected_pages"


def test_every_claim_has_search_terms() -> None:
    for c in DECOMPOSITION:
        assert c["search_terms"], f"{c['claim_id']} has no search_terms"


def test_all_expected_pages_are_valid() -> None:
    pages = all_expected_pages()
    assert len(pages) == 21
    assert 471 in pages
    assert 103 in pages
    assert 22 in pages
    assert 33 in pages
    assert 363 in pages
    assert 41 in pages
    assert 209 in pages
    assert 462 in pages
    assert 148 in pages
    assert 149 in pages
    assert 82 in pages
    assert 145 in pages
    assert 53 in pages
    assert 54 in pages
    assert 70 in pages
    assert 71 in pages
    assert 177 in pages
    assert 178 in pages
    assert 236 in pages
    assert 237 in pages
    assert 312 in pages


def test_get_claim_by_id_found() -> None:
    c = get_claim_by_id("A1")
    assert c is not None
    assert c["claim_id"] == "A1"


def test_get_claim_by_id_not_found() -> None:
    assert get_claim_by_id("ZZ") is None


def test_relations_defined() -> None:
    assert len(RELATIONS) == 15


def test_every_relation_references_valid_claims() -> None:
    for r in RELATIONS:
        assert get_claim_by_id(r["from_claim_id"]) is not None, \
            f"{r['relation_id']}: from {r['from_claim_id']} not found"
        assert get_claim_by_id(r["to_claim_id"]) is not None, \
            f"{r['relation_id']}: to {r['to_claim_id']} not found"


def test_every_claim_has_search_terms_not_empty() -> None:
    for c in DECOMPOSITION:
        terms = c["search_terms"]
        assert len(terms) > 0, f"{c['claim_id']} has no search terms"
        assert any(len(t) > 3 for t in terms), \
            f"{c['claim_id']} has only short search terms: {terms}"
