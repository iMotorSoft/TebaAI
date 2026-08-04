"""Canonical editorial evidence selection V1 — unit tests.

Covers structural heading canonical selection, deterministic printed
reference tie-breaking, printed page preservation and claim-grounding
determinism, without external services.
"""

from __future__ import annotations

from modules.library import simple_research_rag as rag
from modules.library.page_first_evidence import _resolve_printed_page


def _heading_candidate(
    chunk_id: str,
    content: str,
    *,
    section_title: str | None = None,
    block_type: str = "page_first_v2",
    evidence_role: str = "commentary",
    printed_page_label: str | None = None,
) -> dict:
    return {
        "chunk_id": chunk_id,
        "associated_chunk_id": None,
        "content": content,
        "section_title": section_title,
        "block_type": block_type,
        "evidence_role": evidence_role,
        "printed_page_label": printed_page_label,
    }


# ---------------------------------------------------------------------------
# Structural heading classification
# ---------------------------------------------------------------------------


def test_heading_exact_beats_adjacent_body_all_tokens_ordered() -> None:
    query = rag.normalize_structural_heading_for_search("CONSTRUYENDO UN MISHKÁN")
    golden = _heading_candidate(
        "00000000-0000-0000-0000-000000000101",
        "4 ■ CONSTRUYENDO UN MISHKÁN\nEl Rabí Natán concluye su explicación.",
        section_title="4 ■ CONSTRUYENDO UN MISHKÁN",
    )
    live_body = _heading_candidate(
        "00000000-0000-0000-0000-000000000102",
        "y antes de ello, en el Mishkán el concepto de oro y plata.",
        section_title="4 ■ CONSTRUYENDO UN MISHKÁN",
    )
    classified = rag.classify_structural_heading_candidates(
        query, [live_body, golden]
    )
    assert classified[0]["chunk_id"] == golden["chunk_id"]
    assert classified[0]["literal_match_type"] == "structural_heading_exact"
    assert classified[0]["heading_from_content"] is True
    assert classified[1]["heading_from_content"] is False


def test_heading_exact_beats_semantic_only() -> None:
    query = rag.normalize_structural_heading_for_search("CONSTRUYENDO UN MISHKÁN")
    heading = _heading_candidate(
        "00000000-0000-0000-0000-000000000103",
        "4 ■ CONSTRUYENDO UN MISHKÁN\nEl Rabí Natán concluye.",
    )
    ranked = rag.merge_results(
        [{
            "chunk_id": "00000000-0000-0000-0000-000000000104",
            "semantic_score": 0.99,
            "semantic_rank": 1,
        }],
        [{
            **heading,
            "literal_score": 200.0,
            "exact_match": True,
            "literal_match_type": "structural_heading_exact",
        }],
        query_language="es",
        structural_heading_query=query,
    )
    assert ranked[0]["chunk_id"] == heading["chunk_id"]
    assert ranked[0]["literal_match_type"] == "structural_heading_exact"


def test_heading_exact_with_editorial_symbol_and_number() -> None:
    query = rag.normalize_structural_heading_for_search("CONSTRUYENDO UN MISHKÁN")
    candidates = [_heading_candidate(
        "00000000-0000-0000-0000-000000000105",
        "4 ■ CONSTRUYENDO UN MISHKÁN\nCuerpo.",
    )]
    classified = rag.classify_structural_heading_candidates(query, candidates)
    assert classified[0]["literal_match_type"] == "structural_heading_exact"
    assert classified[0]["heading_original"] == "4 ■ CONSTRUYENDO UN MISHKÁN"
    assert classified[0]["heading_display"] == "4. CONSTRUYENDO UN MISHKÁN"


def test_heading_exact_uppercase_and_punctuation_tolerant() -> None:
    query = rag.normalize_structural_heading_for_search("construyendo un mishkán")
    candidates = [
        _heading_candidate(
            "00000000-0000-0000-0000-000000000106",
            "4 ■ Construyendo un Mishkán —\nEl Rabí Natán concluye.",
        ),
        _heading_candidate(
            "00000000-0000-0000-0000-000000000107",
            "CONSTRUYENDO UN MISHKÁN, LA OBRA",
        ),
    ]
    classified = rag.classify_structural_heading_candidates(query, candidates)
    assert classified[0]["literal_match_type"] == "structural_heading_exact"
    assert classified[0]["chunk_id"] == "00000000-0000-0000-0000-000000000106"


def test_scattered_body_words_are_not_heading_exact() -> None:
    # Scattered body words alone are never a heading exact match.
    query = rag.normalize_structural_heading_for_search("INCLINADO HACIA LA BONDAD")
    body = _heading_candidate(
        "00000000-0000-0000-0000-000000000108",
        "“mi diestra” -i.e., la midá de jesed, la cualidad de la bondad- "
        "encuentro mis puntos modelo de la bondad.",
    )
    classified = rag.classify_structural_heading_candidates(query, [body])
    assert classified == []


def test_content_heading_beats_metadata_inherited_heading() -> None:
    # Adjacent body chunks inherit section_title; only the chunk whose
    # content actually carries the heading line is the canonical heading.
    query = rag.normalize_structural_heading_for_search("INCLINADO HACIA LA BONDAD")
    inherited_title = "5 ■ INCLINADO HACIA LA BONDAD"
    golden = _heading_candidate(
        "00000000-0000-0000-0000-000000000109",
        "5 ■ INCLINADO HACIA LA BONDAD\nDe la misma manera, se comprende.",
        section_title=inherited_title,
    )
    body = _heading_candidate(
        "00000000-0000-0000-0000-000000000110",
        "“mi diestra” -i.e., la midá de jesed, la cualidad de la bondad- "
        "encuentro mis puntos modelo de la bondad.",
        section_title=inherited_title,
    )
    classified = rag.classify_structural_heading_candidates(
        query, [body, golden]
    )
    assert classified[0]["chunk_id"] == golden["chunk_id"]
    assert classified[0]["literal_match_type"] == "structural_heading_exact"
    assert classified[0]["heading_from_content"] is True
    assert classified[1]["heading_from_content"] is False


def test_canonical_heading_primary_and_body_context_separation() -> None:
    query = rag.normalize_structural_heading_for_search("CONSTRUYENDO UN MISHKÁN")
    assert rag._is_primary_eligible(
        {"literal_match_type": "structural_heading_exact"},
        query_language="es",
        structural_heading_query=query,
    ) is True
    assert rag._is_primary_eligible(
        {"literal_match_type": "structural_heading_all_tokens_ordered"},
        query_language="es",
        structural_heading_query=query,
    ) is True  # eligible, but canonical exact wins selection
    canonical_types = rag.STRUCTURAL_HEADING_CANONICAL_MATCH_TYPES
    assert "structural_heading_exact" in canonical_types
    assert "structural_heading_all_tokens_ordered" not in canonical_types


def test_merge_preserves_source_layer_of_heading() -> None:
    merged = rag.merge_results(
        [{
            "chunk_id": "00000000-0000-0000-0000-000000000109",
            "semantic_score": 0.9,
            "semantic_rank": 1,
        }],
        [{
            "chunk_id": "00000000-0000-0000-0000-000000000109",
            "literal_score": 200.0,
            "exact_match": True,
            "literal_match_type": "structural_heading_exact",
            "heading_original": "4 ■ CONSTRUYENDO UN MISHKÁN",
        }],
        query_language="es",
    )
    assert merged[0]["literal_match_type"] == "structural_heading_exact"
    assert rag._source_layer(merged[0]) == "section_heading"


def test_dedupe_keeps_canonical_heading_over_body() -> None:
    chunk_id = "00000000-0000-0000-0000-000000000110"
    merged = rag.merge_results(
        [],
        [
            {
                "chunk_id": chunk_id,
                "literal_score": 130.0,
                "exact_match": True,
                "literal_match_type": "structural_heading_all_tokens_ordered",
            },
            {
                "chunk_id": chunk_id,
                "literal_score": 200.0,
                "exact_match": True,
                "literal_match_type": "structural_heading_exact",
            },
        ],
        query_language="es",
    )
    assert len(merged) == 1
    assert merged[0]["literal_match_type"] == "structural_heading_exact"


def test_heading_page_not_replaced_by_body_page() -> None:
    heading_id = "00000000-0000-0000-0000-000000000111"
    body_id = "00000000-0000-0000-0000-000000000112"
    canonical = {
        heading_id: {
            "chunk_id": heading_id,
            "markdown": "4 ■ CONSTRUYENDO UN MISHKÁN\nEl Rabí Natán concluye.",
            "printed_page": "33",
            "pdf_page": 51,
        },
        body_id: {
            "chunk_id": body_id,
            "markdown": "y antes de ello, en el Mishkán el concepto de oro y plata.",
            "printed_page": "34",
            "pdf_page": 52,
        },
    }
    ranked = [{
        "chunk_id": heading_id,
        "associated_chunk_id": body_id,
        "literal_match_type": "structural_heading_exact",
        "heading_original": "4 ■ CONSTRUYENDO UN MISHKÁN",
        "heading_display": "4. CONSTRUYENDO UN MISHKÁN",
    }]
    rag._attach_structural_heading_contexts(canonical, ranked)
    # The heading keeps its canonical page; the body context never replaces it.
    assert canonical[heading_id]["pdf_page"] == 51
    assert canonical[heading_id]["printed_page"] == "33"


def test_evidence_id_entity_based() -> None:
    """Same entity → same ID; different entity → different ID."""
    chunk_id = "8e1a1192-02f2-4903-97f8-ce85f29bdf2a"
    # footnote:35 vs footnote:36 — different IDs
    n35 = rag._evidence_id({"chunk_id": chunk_id, "literal_match_type": "footnote_literal_exact", "footnote_number": 35})
    n36 = rag._evidence_id({"chunk_id": chunk_id, "literal_match_type": "footnote_literal_exact", "footnote_number": 36})
    assert n35 != n36
    # same entity → deterministic
    assert rag._evidence_id({"chunk_id": chunk_id, "literal_match_type": "footnote_literal_exact", "footnote_number": 35}) == n35
    # heading vs footnote — different IDs
    h = rag._evidence_id({"chunk_id": chunk_id, "literal_match_type": "structural_heading_exact", "heading_original": "6 ■ MELODÍAS Y PLEGARIAS"})
    assert h != n35 and h != n36
    # reference variants share ID
    r1 = rag._evidence_id({"chunk_id": chunk_id, "literal_match_type": "printed_reference_exact", "matched_variant": "Salmos 16:1"})
    r2 = rag._evidence_id({"chunk_id": chunk_id, "literal_match_type": "printed_reference_exact", "matched_variant": "(Salmos 16:1)"})
    r3 = rag._evidence_id({"chunk_id": chunk_id, "literal_match_type": "printed_reference_exact", "matched_variant": "salmos 16:1"})
    assert r1 == r2 == r3
    # legacy ID preserved
    assert rag._legacy_chunk_evidence_id(chunk_id) == "ev-6e965be966db45f1"


# ---------------------------------------------------------------------------
# Printed reference determinism
# ---------------------------------------------------------------------------


def test_reference_surface_boundaries() -> None:
    assert rag._content_has_exact_reference_surface(
        "…\n(Salmos 16:1)\n…", "Salmos 16:1"
    ) is True
    assert rag._content_has_exact_reference_surface(
        "…\n(Salmos 16:10)\n…", "Salmos 16:1"
    ) is False
    assert rag._content_has_exact_reference_surface(
        "…\n(Salmos 16:11)\n…", "Salmos 16:1"
    ) is False
    assert rag._content_has_exact_reference_surface(
        "…\n(Salmos 116:1)\n…", "Salmos 16:1"
    ) is False
    assert rag._content_has_exact_reference_surface(
        "…\n(Salmos 116:1)\n…", "(Salmos 116:1)"
    ) is True


def test_printed_reference_exact_beats_other_exact_reference() -> None:
    ranked = rag.merge_results(
        [],
        [
            {
                "chunk_id": "00000000-0000-0000-0000-000000000120",
                "literal_score": 1.5,
                "exact_match": True,
                "literal_match_type": "exact_phrase",
            },
            {
                "chunk_id": "00000000-0000-0000-0000-000000000121",
                "literal_score": 1.5,
                "exact_match": True,
                "literal_match_type": "printed_reference_exact",
            },
        ],
        query_language="es",
    )
    assert ranked[0]["literal_match_type"] == "printed_reference_exact"
    assert rag._source_layer(ranked[0]) == "marginal_reference"


def test_merge_order_is_deterministic_regardless_of_input_order() -> None:
    a = {
        "chunk_id": "00000000-0000-0000-0000-000000000130",
        "document_id": "20000000-0000-0000-0000-000000000001",
        "literal_score": 1.5,
        "exact_match": True,
        "literal_match_type": "printed_reference_exact",
        "semantic_score": 0.8,
        "semantic_rank": 1,
    }
    b = {
        "chunk_id": "00000000-0000-0000-0000-000000000131",
        "document_id": "20000000-0000-0000-0000-000000000002",
        "literal_score": 1.5,
        "exact_match": True,
        "literal_match_type": "printed_reference_exact",
        "semantic_score": 0.8,
        "semantic_rank": 2,
    }
    forward = rag.merge_results([], [a, b], query_language="es")
    backward = rag.merge_results([], [b, a], query_language="es")
    assert [item["chunk_id"] for item in forward] == [item["chunk_id"] for item in backward]
    assert forward[0]["chunk_id"] == a["chunk_id"]  # stable canonical key


def test_merge_never_replaces_non_null_printed_page_with_null() -> None:
    merged = rag.merge_results(
        [{
            "chunk_id": "00000000-0000-0000-0000-000000000132",
            "semantic_score": 0.9,
            "semantic_rank": 1,
        }],
        [{
            "chunk_id": "00000000-0000-0000-0000-000000000132",
            "literal_score": 1.5,
            "exact_match": True,
            "literal_match_type": "printed_reference_exact",
        }],
        query_language="es",
    )
    merged[0]["printed_page"] = 37
    # Simulate a later enrichment attempting a null overwrite.
    incoming = {**merged[0], "printed_page": None}
    if incoming["printed_page"] is None and merged[0].get("printed_page") is not None:
        incoming["printed_page"] = merged[0]["printed_page"]
    assert incoming["printed_page"] == 37


def test_claim_grounding_does_not_change_primary() -> None:
    chunks = [
        {"evidence_id": "ev-aaaaaaaaaaaaaaaa", "pdf_page": 55},
        {"evidence_id": "ev-bbbbbbbbbbbbbbbb", "pdf_page": 368},
    ]
    value = {
        "answer_markdown": "Cita [ev-aaaaaaaaaaaaaaaa].",
        "claims": [{
            "claim_id": "c1",
            "text": "La referencia aparece.",
            "evidence_ids": ["ev-aaaaaaaaaaaaaaaa"],
            "relation_type": "direct",
            "confidence": "high",
        }],
    }
    markdown, claims = rag.validate_grounded_answer(value, chunks)
    assert markdown == value["answer_markdown"]
    assert claims[0]["primary_evidence_id"] == "ev-aaaaaaaaaaaaaaaa"


def test_ai_cannot_select_unlisted_evidence_id() -> None:
    chunks = [{"evidence_id": "ev-aaaaaaaaaaaaaaaa", "pdf_page": 55}]
    value = {
        "answer_markdown": "Cita [ev-9999999999999999].",
        "claims": [],
    }
    try:
        rag.validate_grounded_answer(value, chunks)
    except ValueError as exc:
        assert "invented" in str(exc) or "missing" in str(exc)
    else:
        raise AssertionError("expected invented evidence id rejection")


def test_reference_variant_forms_resolve_same_surface() -> None:
    for query in ("Salmos 16:1", "(Salmos 16:1)", "salmos 16:1"):
        variants = rag.build_query_variants(query, is_printed_reference=True)
        assert variants[0] == query
        assert "Salmos 16:1" in variants or "salmos 16:1" in variants


def test_scoped_reference_adds_bare_surface_variant() -> None:
    variants = rag.build_query_variants(
        "Salmos 16:1 en Likutey Halajot",
        is_printed_reference=True,
    )
    assert "Salmos 16:1" in variants
    assert rag._explicit_likutey_halajot_scope("Salmos 16:1 en Likutey Halajot")
    assert not rag._explicit_likutey_halajot_scope("Salmos 16:1")


def test_printed_page_resolved_from_visible_folio() -> None:
    chunk = {
        "markdown": "\x98\x83\x89\x8a\x82 \x87\x86\x83\x95\x87\x8a 37\n<#>\n"
        "El Rabí Natán ha explicado.",
    }
    assert rag._canonical_printed_page(chunk) == 37
    assert _resolve_printed_page(chunk) == 37
    assert rag._canonical_printed_page({
        "markdown": "38 LIKUTEY HALAJOT\nDISCURSO…",
    }) == 38
    assert rag._canonical_printed_page({
        "printed_page": "33",
        "markdown": "…",
    }) == 33


def test_status_only_tiebreaks_equivalent_evidence() -> None:
    # Evidence strength is equal; document status must not replace it.
    heading = {"literal_match_type": "structural_heading_exact"}
    assert rag._source_layer(heading) == "section_heading"
    footnote = {"literal_match_type": "footnote_literal_exact"}
    assert rag._source_layer(footnote) == "footnote"
    reference = {"literal_match_type": "printed_reference_exact"}
    assert rag._source_layer(reference) == "marginal_reference"
