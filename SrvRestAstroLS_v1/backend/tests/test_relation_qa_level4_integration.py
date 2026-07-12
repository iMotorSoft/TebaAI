"""Verifies that Relation QA can be invoked for Level 4 concepts."""
from __future__ import annotations


def test_relation_qa_service_importable() -> None:
    from modules.library.relation_qa_service import run_relation_qa
    assert run_relation_qa is not None


def test_relation_qa_schemas_importable() -> None:
    from modules.library.relation_qa_schemas import RelationQARequest, EvidenceType
    assert RelationQARequest is not None
    assert EvidenceType is not None


def test_relation_qa_evidence_types_cover_level4() -> None:
    from modules.library.relation_qa_schemas import EvidenceType
    expected_evidence = {
        "literal_phrase", "cooccurrence_same_chunk", "cooccurrence_same_page",
        "cooccurrence_same_section", "thematic_relation", "derash_interpretation",
        "ambiguous", "not_found",
    }
    actual = {e.value for e in EvidenceType}
    assert expected_evidence.issubset(actual), f"Missing: {expected_evidence - actual}"


def test_relation_qa_has_expand_variants() -> None:
    from modules.library.relation_qa_evidence import expand_concept_variants
    variants = expand_concept_variants("humildad", "es")
    assert "humildad" in variants
    assert len(variants) >= 1


def test_relation_qa_has_extract_concepts() -> None:
    from modules.library.relation_qa_evidence import extract_concepts_from_question
    a, b = extract_concepts_from_question("relación entre humildad y verdad")
    assert a is not None
    assert b is not None


def test_level4_decomposition_has_relation_pairs() -> None:
    """Every relation in Level 4 decomposition has a from and to claim."""
    from scripts.library_synthesis_qa_level4_decomposition import RELATIONS
    for r in RELATIONS:
        assert r["from_claim_id"] != r["to_claim_id"] or \
               r["expected_relation_type"] == "literal", \
            f"{r['relation_id']}: self-relation should be literal"
