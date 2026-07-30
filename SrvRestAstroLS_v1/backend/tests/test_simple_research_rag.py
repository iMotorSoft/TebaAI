from __future__ import annotations

from contextlib import asynccontextmanager
from json import JSONDecodeError
from unittest.mock import AsyncMock, patch

import pytest
from litestar import Litestar
from litestar.testing import TestClient

from modules.library.investigative_qa_v1 import QaRequest
from modules.library import simple_research_rag as rag
from modules.library.routes import investigative_qa_v1


QUERIES = [
    "Relación sangre y habla",
    "salmo 19",
    "el término escorpión con qué está relacionado",
    "azamra",
    "qué dice Rebe Najmán sobre la tristeza",
    "qué relación hay entre alegría y emuná",
]


def _request(query: str = QUERIES[0]) -> QaRequest:
    return QaRequest(
        question=query,
        languages=["es", "en", "he"],
        max_hits_per_work=10,
    )


def _canonical(chunk_id: str = "00000000-0000-0000-0000-000000000001") -> dict:
    return {
        "chunk_id": chunk_id,
        "document_id": "10000000-0000-0000-0000-000000000001",
        "document_code": None,
        "work": "La Potencia de la Plegaria",
        "author": "Autor",
        "physical_file_name": "source.pdf",
        "source_sha256": "abc",
        "canonical_text_role": "canonical",
        "language": "es",
        "markdown": "Markdown canónico sobre sangre, voz y la recitación del Shemá.",
        "content_sha256": "content-sha",
        "pdf_page": 207,
        "pdf_page_end": 208,
        "printed_page": "208",
        "section": "Shemá",
        "reference_label": None,
        "block_type": None,
        "evidence_role": "source_text",
        "citable": True,
        "metadata": {},
        "bibliographic_metadata": {},
    }


async def _install_retrieval_fakes(
    monkeypatch: pytest.MonkeyPatch,
    *,
    semantic: bool = True,
    literal: bool = True,
) -> None:
    chunk_id = str(_canonical()["chunk_id"])

    async def documents(*args, **kwargs):
        return [{
            "document_id": _canonical()["document_id"],
            "document_code": None,
            "title": "La Potencia de la Plegaria",
            "language": "es",
        }]

    async def literal_search(*args, **kwargs):
        if not literal:
            return []
        return [{
            "chunk_id": chunk_id,
            "exact_match": True,
            "literal_score": 2.0,
        }]

    async def fetch_chunks(*args, **kwargs):
        return [_canonical()] if chunk_id in kwargs["chunk_ids"] else []

    def semantic_search(original_query, **kwargs):
        if kwargs["simulate_failure"]:
            raise RuntimeError("simulated_milvus_failure")
        hits = [{
            "chunk_id": chunk_id,
            "semantic_score": 0.88,
            "semantic_rank": 1,
        }] if semantic else []
        return hits, {
            "model": "openai_text_embedding_3_small",
            "dimension": 1536,
            "latency_ms": 1.0,
        }

    async def structural_search(*args, **kwargs):
        return []

    monkeypatch.setattr(rag, "resolve_ready_documents", documents)
    monkeypatch.setattr(rag, "search_structural_heading_candidates", structural_search)
    monkeypatch.setattr(rag, "search_literal_candidates", literal_search)
    monkeypatch.setattr(rag, "fetch_canonical_chunks", fetch_chunks)
    monkeypatch.setattr(rag, "_semantic_search", semantic_search)


@pytest.mark.parametrize("query", QUERIES)
@pytest.mark.asyncio
async def test_original_query_survives_retrieval_and_render(
    monkeypatch: pytest.MonkeyPatch,
    query: str,
) -> None:
    await _install_retrieval_fakes(monkeypatch)
    seen: dict[str, str] = {}

    async def render(original_query, filters, chunks, *, simulate_failure):
        seen["query"] = original_query
        evidence_id = chunks[0]["evidence_id"]
        return (
            f"Respuesta grounded [{evidence_id}]",
            [{
                "claim_id": "claim_1",
                "text": "Afirmación grounded",
                "strength": "strong",
                "confidence": "high",
                "relation_type": "thematic",
                "evidence_ids": [evidence_id],
                "primary_evidence_id": evidence_id,
            }],
            True,
        )

    monkeypatch.setattr(rag, "render_grounded_answer", render)
    response = await rag.run_simple_rag(object(), _request(query))

    assert response["original_query"] == query
    assert response["question"] == query
    assert response["query_understanding"]["original_query"] == query
    assert seen["query"] == query
    assert response["retrieval"]["semantic_status"] == "ok"
    assert response["retrieval"]["literal_status"] == "ok"
    assert response["evidence"][0]["markdown"].startswith("Markdown canónico")


def test_semantic_search_embeds_the_complete_original_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    def embed(value: str):
        seen["query"] = value
        return [0.1] * 1536

    monkeypatch.setattr(rag, "embed_text", embed)
    monkeypatch.setattr(rag, "create_connection", lambda: None)
    monkeypatch.setattr(rag, "ensure_collection", lambda *args, **kwargs: None)

    def search(**kwargs):
        seen["expr"] = kwargs["expr"]
        return []

    monkeypatch.setattr(rag, "search_vectors", search)
    rag._semantic_search(
        "Relación sangre y habla",
        scope_code="breslov_primary",
        languages=["es"],
        document_ids=["10000000-0000-0000-0000-000000000001"],
        simulate_failure=False,
    )

    assert seen["query"] == "Relación sangre y habla"
    assert 'collection_code == "breslov"' in str(seen["expr"])
    assert 'language in ["es"]' in str(seen["expr"])
    assert "document_id in" in str(seen["expr"])


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("azamra", "אֲזַמְּרָה"),
        ("escorpión con qué está relacionado", "עקרבים"),
        ("Relación sangre y habla", "impurezas en la sangre"),
        ("salmo 19", "Psalms 19"),
        ("qué relación hay entre alegría y emuná", "אמונה"),
    ],
)
def test_controlled_expansions_never_replace_original(
    query: str,
    expected: str,
) -> None:
    variants = rag.build_query_variants(query)
    assert variants[0] == query
    assert expected in variants


def test_hebrew_literal_exact_outranks_high_semantic_without_tokens() -> None:
    semantic_id = "00000000-0000-0000-0000-000000000010"
    literal_id = "00000000-0000-0000-0000-000000000020"
    ranked = rag.merge_results(
        [{
            "chunk_id": semantic_id,
            "semantic_score": 0.99,
            "semantic_rank": 1,
        }, {
            "chunk_id": literal_id,
            "semantic_score": 0.45,
            "semantic_rank": 20,
        }],
        [{
            "chunk_id": literal_id,
            "literal_score": 100.0,
            "exact_match": True,
            "literal_match_type": "hebrew_exact_normalized",
        }],
        query_language="he",
    )
    assert ranked[0]["chunk_id"] == literal_id
    assert ranked[0]["combined_score"] > ranked[1]["combined_score"]


@pytest.mark.parametrize(
    ("query", "normalized", "tokens"),
    [
        ("Gedalia of Linitz", "gedalia of linitz", ("gedalia", "linitz")),
        ("gedalia  of\nLinitz", "gedalia of linitz", ("gedalia", "linitz")),
        ("Reb Noson", "reb noson", ("reb", "noson")),
        ("Baal Shem Tov", "baal shem tov", ("baal", "shem", "tov")),
        ("Maggid of Mezritch", "maggid of mezritch", ("maggid", "mezritch")),
    ],
)
def test_short_english_name_detection_preserves_nominal_connectors(
    query: str,
    normalized: str,
    tokens: tuple[str, ...],
) -> None:
    detected = rag.detect_short_english_name_query(query)
    assert detected is not None
    assert detected.normalized == normalized
    assert detected.nominal_tokens == tokens


def test_english_search_normalization_handles_typography_and_controls() -> None:
    assert (
        rag.normalize_english_for_search("  GEDALIA\u200f of\nLinitz’s  ")
        == "gedalia of linitz's"
    )


def test_short_name_variants_are_bounded_and_not_person_specific() -> None:
    variants = rag.build_query_variants("Gedalia of Linetz")
    assert variants[0] == "Gedalia of Linetz"
    assert "gedalia of linitz" in variants
    assert len(variants) <= 36


def test_ascii_short_proper_name_is_detected_as_english() -> None:
    assert rag.detect_research_query_language("Gedalia of Linitz") == "en"
    assert rag.detect_research_query_language("Rabí Natán") == "es"
    assert rag.detect_short_english_name_query("Relación sangre y habla") is None


@pytest.mark.parametrize(
    ("query", "normalized", "folded", "number"),
    [
        ("CONSTRUYENDO UN MISHKÁN", "construyendo un mishkán", "construyendo un mishkan", None),
        ("4. CONSTRUYENDO UN MISHKÁN", "construyendo un mishkán", "construyendo un mishkan", "4"),
        ("## 4 ■ Construyendo\u00a0un Mishkan —", "construyendo un mishkan", "construyendo un mishkan", "4"),
    ],
)
def test_structural_heading_normalization(
    query: str,
    normalized: str,
    folded: str,
    number: str | None,
) -> None:
    result = rag.normalize_structural_heading_for_search(query)
    assert result.original == query
    assert result.normalized == normalized
    assert result.accent_folded == folded
    assert result.leading_section_number == number


def test_structural_heading_classification_requires_a_real_heading() -> None:
    query = rag.normalize_structural_heading_for_search("Construyendo un Mishkan")
    candidates = [{
        "chunk_id": "00000000-0000-0000-0000-000000000041",
        "associated_chunk_id": "00000000-0000-0000-0000-000000000042",
        "content": "4 ■ CONSTRUYENDO UN MISHKÁN",
        "section_title": None,
        "block_type": "main_explanation_es",
    }]
    matches = rag.classify_structural_heading_candidates(query, candidates)
    assert matches[0]["literal_match_type"] == "structural_heading_accent_folded"
    assert matches[0]["heading_original"] == "4 ■ CONSTRUYENDO UN MISHKÁN"
    assert matches[0]["heading_display"] == "4. CONSTRUYENDO UN MISHKÁN"
    assert matches[0]["associated_chunk_id"].endswith("42")

    body_only = [{
        **candidates[0],
        "content": "Rabí Natán explica cómo se estaba construyendo un Mishkán.",
    }]
    assert rag.classify_structural_heading_candidates(query, body_only) == []


def test_all_caps_editorial_phrase_is_not_an_english_proper_name() -> None:
    assert rag.detect_short_english_name_query("CONSTRUYENDO UN MISHKÁN") is None
    assert rag.detect_short_english_name_query("CAPÍTULO QUE NO EXISTE") is None
    assert rag.detect_short_english_name_query("Gedalia of Linitz") is not None
    assert rag.has_editorial_heading_form("CONSTRUYENDO UN TEMPLO INEXISTENTE")
    assert rag.has_editorial_heading_form("4. Construyendo un Mishkán")
    assert not rag.has_editorial_heading_form("Relación sangre y habla")


def test_structural_heading_exact_outranks_high_semantic_without_heading() -> None:
    semantic_id = "00000000-0000-0000-0000-000000000043"
    heading_id = "00000000-0000-0000-0000-000000000044"
    structural_query = rag.normalize_structural_heading_for_search(
        "CONSTRUYENDO UN MISHKÁN"
    )
    ranked = rag.merge_results(
        [{"chunk_id": semantic_id, "semantic_score": 0.99, "semantic_rank": 1}],
        [{
            "chunk_id": heading_id,
            "literal_score": 2.0,
            "exact_match": True,
            "literal_match_type": "exact_phrase",
        }, {
            "chunk_id": heading_id,
            "literal_score": 200.0,
            "exact_match": True,
            "literal_match_type": "structural_heading_exact",
            "matched_variant": "4 ■ CONSTRUYENDO UN MISHKÁN",
        }],
        query_language="es",
        structural_heading_query=structural_query,
    )
    assert ranked[0]["chunk_id"] == heading_id
    assert ranked[0]["literal_match_type"] == "structural_heading_exact"
    assert rag._is_primary_eligible(
        ranked[1],
        query_language="es",
        structural_heading_query=structural_query,
    ) is False
    assert rag._is_primary_eligible(
        {"literal_match_type": "structural_heading_all_tokens_ordered"},
        query_language="he",
        structural_heading_query=structural_query,
    ) is True


def test_heading_body_association_preserves_canonical_chunks() -> None:
    heading_id = "00000000-0000-0000-0000-000000000045"
    body_id = "00000000-0000-0000-0000-000000000046"
    canonical = {
        heading_id: {**_canonical(heading_id), "markdown": "4 ■ CONSTRUYENDO UN MISHKÁN"},
        body_id: {**_canonical(body_id), "markdown": "El Rabí Natán concluye su explicación."},
    }
    ranked = [{
        "chunk_id": heading_id,
        "associated_chunk_id": body_id,
        "literal_match_type": "structural_heading_exact",
        "heading_original": "4 ■ CONSTRUYENDO UN MISHKÁN",
        "heading_display": "4. CONSTRUYENDO UN MISHKÁN",
        "heading_normalized": "construyendo un mishkán",
    }]
    rag._attach_structural_heading_contexts(canonical, ranked)
    assert "El Rabí Natán concluye" in canonical[heading_id]["markdown"]
    assert canonical[heading_id]["section"] == "4. CONSTRUYENDO UN MISHKÁN"
    assert canonical[heading_id]["associated_chunk_id"] == body_id


def test_english_name_exact_outranks_high_semantic_without_name_tokens() -> None:
    semantic_id = "00000000-0000-0000-0000-000000000030"
    literal_id = "00000000-0000-0000-0000-000000000040"
    name_query = rag.detect_short_english_name_query("Gedalia of Linitz")
    assert name_query is not None
    ranked = rag.merge_results(
        [{
            "chunk_id": semantic_id,
            "semantic_score": 0.99,
            "semantic_rank": 1,
        }, {
            "chunk_id": literal_id,
            "semantic_score": 0.30,
            "semantic_rank": 25,
        }],
        [{
            "chunk_id": literal_id,
            "literal_score": 2.0,
            "exact_match": True,
            "matched_variant": "Gedalia of Linitz",
        }],
        query_language="en",
        english_name_query=name_query,
    )
    assert ranked[0]["chunk_id"] == literal_id
    assert ranked[0]["literal_match_type"] == "english_name_exact"


def test_semantic_only_english_name_evidence_cannot_be_primary() -> None:
    name_query = rag.detect_short_english_name_query("Gedalia of Linitz")
    assert name_query is not None
    assert rag._is_primary_eligible(
        {"literal_match_type": "semantic_only"},
        query_language="en",
        english_name_query=name_query,
    ) is False
    assert rag._is_primary_eligible(
        {"literal_match_type": "english_name_exact"},
        query_language="en",
        english_name_query=name_query,
    ) is True


def test_literal_match_uses_nearest_canonical_page_marker() -> None:
    assert rag._match_local_pdf_page({
        "markdown": (
            "tail from prior page\n\n## Page 21\n\n"
            "Gedalia of Linitz and other great Rabbis"
        ),
        "matched_variant": "Gedalia of Linitz",
        "pdf_page": 20,
        "pdf_page_end": 21,
    }) == 21


def test_semantic_only_hebrew_evidence_cannot_be_primary() -> None:
    assert rag._is_primary_eligible(
        {"literal_match_type": "semantic_only"},
        query_language="he",
    ) is False
    assert rag._is_primary_eligible(
        {"literal_match_type": "hebrew_exact_normalized"},
        query_language="he",
    ) is True


def test_grounding_rejects_invented_evidence_and_pages() -> None:
    chunk = {**_canonical(), "evidence_id": "ev-real"}
    with pytest.raises(ValueError, match="invalid_evidence_id"):
        rag.validate_grounded_answer({
            "answer_markdown": "Respuesta",
            "claims": [{
                "text": "Inventada",
                "evidence_ids": ["ev-invented"],
                "relation_type": "direct",
                "confidence": "high",
            }],
        }, [chunk])
    with pytest.raises(ValueError, match="invented_page"):
        rag.validate_grounded_answer({
            "answer_markdown": "Según la página 999. [ev-real]",
            "claims": [{
                "text": "Grounded",
                "evidence_ids": ["ev-real"],
                "relation_type": "direct",
                "confidence": "high",
            }],
        }, [chunk])


@pytest.mark.asyncio
async def test_structural_heading_fixture_returns_page_body_and_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    heading_id = "91aba034-7a02-4520-aa1c-3f29be2741be"
    body_id = "d0ae8b80-0947-4503-a45f-11e4b9c7d0ff"
    document_id = "47768aac-704e-4296-9649-53b9ea037096"

    async def documents(*args, **kwargs):
        return [{"document_id": document_id, "title": "Likutey Halajot"}]

    async def structural(*args, **kwargs):
        return [{
            "chunk_id": heading_id,
            "associated_chunk_id": body_id,
            "document_id": document_id,
            "chunk_index": 356,
            "content": "4 ■ CONSTRUYENDO UN MISHKÁN",
            "section_title": "השכמת הבוקר",
            "block_type": "main_explanation_es",
            "page_start": 51,
            "printed_page_label": "33",
        }]

    async def literal(*args, **kwargs):
        return []

    async def fetch(*args, **kwargs):
        common = {
            **_canonical(),
            "document_id": document_id,
            "work": "Likutey Halajot",
            "physical_file_name": "LIKUTEY HALAJOT (Interior Final).pdf",
            "source_sha256": "440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a",
            "pdf_page": 51,
            "pdf_page_end": 51,
            "printed_page": "33",
            "document_status": "test_candidate",
            "section": "השכמת הבוקר",
            "block_type": "main_explanation_es",
            "evidence_role": "commentary",
        }
        values = {
            heading_id: {**common, "chunk_id": heading_id, "markdown": "4 ■ CONSTRUYENDO UN MISHKÁN", "content_sha256": "heading"},
            body_id: {**common, "chunk_id": body_id, "markdown": "El Rabí Natán concluye su explicación de la capacidad de Moshé de encontrar el bien.", "content_sha256": "body"},
        }
        return [values[item] for item in kwargs["chunk_ids"] if item in values]

    def semantic(*args, **kwargs):
        return [], {"dimension": 1536, "latency_ms": 1.0}

    async def render(*args, **kwargs):
        evidence_id = args[2][0]["evidence_id"]
        return f"La sección desarrolla el contexto recuperado. [{evidence_id}]", [{
            "claim_id": "heading",
            "text": "La sección desarrolla el contexto recuperado.",
            "strength": "strong",
            "confidence": "high",
            "relation_type": "direct",
            "evidence_ids": [evidence_id],
            "primary_evidence_id": evidence_id,
        }], True

    monkeypatch.setattr(rag, "resolve_ready_documents", documents)
    monkeypatch.setattr(rag, "search_structural_heading_candidates", structural)
    monkeypatch.setattr(rag, "search_literal_candidates", literal)
    monkeypatch.setattr(rag, "fetch_canonical_chunks", fetch)
    monkeypatch.setattr(rag, "_semantic_search", semantic)
    monkeypatch.setattr(rag, "render_grounded_answer", render)

    response = await rag.run_simple_rag(
        object(),
        _request("CONSTRUYENDO UN MISHKÁN"),
    )
    primary = next(hit for hit in response["hits"] if hit["is_primary"])
    assert response["research_status"] == "complete"
    assert response["retrieval"]["query_shape"] == "structural_heading"
    assert response["retrieval"]["primary_match_type"] == "structural_heading_exact"
    assert primary["work_title"] == "Likutey Halajot"
    assert primary["physical_file_name"] == "LIKUTEY HALAJOT (Interior Final).pdf"
    assert primary["physical_pdf_page"] == 51
    assert primary["printed_page"] == 33
    assert primary["section"] == "4. CONSTRUYENDO UN MISHKÁN"
    assert primary["associated_chunk_id"] == body_id
    assert "El Rabí Natán concluye su explicación" in primary["quote"]
    assert response["primary_evidence_ids"] == ["ev-bf5ac6e2fbf46812"]


@pytest.mark.asyncio
async def test_milvus_failure_uses_literal_and_reports_degradation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _install_retrieval_fakes(monkeypatch, semantic=False, literal=True)

    async def render(*args, **kwargs):
        chunks = args[2]
        evidence_id = chunks[0]["evidence_id"]
        return "Respuesta literal", [{
            "claim_id": "claim",
            "text": "Grounded",
            "strength": "medium",
            "confidence": "medium",
            "relation_type": "thematic",
            "evidence_ids": [evidence_id],
            "primary_evidence_id": evidence_id,
        }], True

    monkeypatch.setattr(rag, "render_grounded_answer", render)
    response = await rag.run_simple_rag(
        object(),
        _request(),
        simulations={"milvus": True},
    )
    assert response["research_status"] == "degraded"
    assert response["retrieval"]["semantic_status"] == "failed"
    assert response["retrieval"]["literal_status"] == "ok"
    assert any("semántica" in warning for warning in response["warnings"])


@pytest.mark.asyncio
async def test_literal_failure_uses_milvus_and_reports_degradation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _install_retrieval_fakes(monkeypatch, semantic=True, literal=False)
    monkeypatch.setattr(
        rag,
        "render_grounded_answer",
        lambda *args, **kwargs: pytest.fail("async render replacement required"),
    )

    async def render(*args, **kwargs):
        evidence_id = args[2][0]["evidence_id"]
        return "Respuesta semántica", [{
            "claim_id": "claim",
            "text": "Grounded",
            "strength": "medium",
            "confidence": "medium",
            "relation_type": "thematic",
            "evidence_ids": [evidence_id],
            "primary_evidence_id": evidence_id,
        }], True

    monkeypatch.setattr(rag, "render_grounded_answer", render)
    response = await rag.run_simple_rag(
        object(),
        _request(),
        simulations={"literal": True},
    )
    assert response["research_status"] == "degraded"
    assert response["retrieval"]["literal_status"] == "failed"
    assert response["retrieval"]["semantic_status"] == "ok"
    assert any("literal" in warning for warning in response["warnings"])


@pytest.mark.asyncio
async def test_ai_failure_returns_sources_instead_of_false_no_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _install_retrieval_fakes(monkeypatch)
    response = await rag.run_simple_rag(
        object(),
        _request(),
        simulations={"ai_render": True},
    )
    assert response["research_status"] == "degraded"
    assert response["status"] == "partial"
    assert response["evidence"]
    assert "Fuentes recuperadas" in response["answer_markdown"]
    assert response["processing"]["fallback_used"] is True


@pytest.mark.asyncio
async def test_total_retrieval_failure_is_not_reported_as_corpus_absence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _install_retrieval_fakes(monkeypatch, semantic=False, literal=False)
    response = await rag.run_simple_rag(
        object(),
        _request(),
        simulations={"milvus": True, "literal": True},
    )
    assert response["research_status"] == "degraded"
    assert response["status"] == "partial"
    assert "problema técnico" in response["answer_markdown"]
    assert "carezca de evidencia" in response["answer_markdown"]


@pytest.mark.asyncio
async def test_interpretation_failure_is_non_blocking_because_simple_rag_does_not_use_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _install_retrieval_fakes(monkeypatch)

    async def render(*args, **kwargs):
        evidence_id = args[2][0]["evidence_id"]
        return "Respuesta grounded", [{
            "claim_id": "claim",
            "text": "Grounded",
            "strength": "strong",
            "confidence": "high",
            "relation_type": "direct",
            "evidence_ids": [evidence_id],
            "primary_evidence_id": evidence_id,
        }], True

    monkeypatch.setattr(rag, "render_grounded_answer", render)
    response = await rag.run_simple_rag(
        object(),
        _request(),
        simulations={"ai_interpretation": True},
    )
    assert response["research_status"] in {"complete", "partial"}
    assert response["processing"]["ai_interpretation_used"] is False


@pytest.mark.asyncio
async def test_invalid_ai_json_returns_recovered_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _install_retrieval_fakes(monkeypatch)

    async def invalid_json(*args, **kwargs):
        raise JSONDecodeError("invalid model JSON", "{", 1)

    monkeypatch.setattr(rag, "render_grounded_answer", invalid_json)
    response = await rag.run_simple_rag(object(), _request())
    assert response["research_status"] == "degraded"
    assert response["evidence"]
    assert "Fuentes recuperadas" in response["answer_markdown"]
    assert "ai_render_failed:JSONDecodeError" in response["warnings"]


@pytest.mark.asyncio
async def test_missing_canonical_chunk_is_reported_as_technical_degradation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _install_retrieval_fakes(monkeypatch)

    async def missing_chunks(*args, **kwargs):
        return []

    monkeypatch.setattr(rag, "fetch_canonical_chunks", missing_chunks)
    response = await rag.run_simple_rag(object(), _request())
    assert response["research_status"] == "degraded"
    assert response["retrieval"]["semantic_status"] == "ok"
    assert response["retrieval"]["literal_status"] == "ok"
    assert response["evidence"] == []
    assert "problema técnico" in response["answer_markdown"]
    assert any("PostgreSQL" in warning for warning in response["warnings"])


@pytest.mark.asyncio
async def test_hebrew_normalizer_failure_preserves_original_and_degrades(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _install_retrieval_fakes(monkeypatch)
    query = "ומצרים נסים לקראתו"

    def broken_normalizer(value: str):
        raise UnicodeError("simulated_normalizer_failure")

    async def render(original_query, filters, chunks, *, simulate_failure):
        evidence_id = chunks[0]["evidence_id"]
        return "Respuesta desde recuperación de respaldo", [{
            "claim_id": "claim",
            "text": "Grounded",
            "strength": "weak",
            "confidence": "low",
            "relation_type": "none",
            "evidence_ids": [evidence_id],
            "primary_evidence_id": evidence_id,
        }], True

    monkeypatch.setattr(rag, "normalize_hebrew_for_search", broken_normalizer)
    monkeypatch.setattr(rag, "render_grounded_answer", render)
    response = await rag.run_simple_rag(object(), _request(query))

    assert response["original_query"] == query
    assert response["research_status"] == "degraded"
    assert response["processing"]["normalization_status"] == "failed"
    assert any("normalización hebrea" in warning for warning in response["warnings"])


@pytest.mark.asyncio
async def test_semantic_timeout_uses_literal_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _install_retrieval_fakes(monkeypatch)

    def timeout(*args, **kwargs):
        raise TimeoutError("simulated semantic timeout")

    async def render(*args, **kwargs):
        evidence_id = args[2][0]["evidence_id"]
        return "Respuesta literal", [{
            "claim_id": "claim",
            "text": "Grounded",
            "strength": "medium",
            "confidence": "medium",
            "relation_type": "thematic",
            "evidence_ids": [evidence_id],
            "primary_evidence_id": evidence_id,
        }], True

    monkeypatch.setattr(rag, "_semantic_search", timeout)
    monkeypatch.setattr(rag, "render_grounded_answer", render)
    response = await rag.run_simple_rag(object(), _request())
    assert response["research_status"] == "degraded"
    assert response["retrieval"]["semantic_status"] == "failed"
    assert response["retrieval"]["literal_status"] == "ok"
    assert any("semántica" in warning for warning in response["warnings"])


@pytest.mark.asyncio
async def test_nonexistent_editorial_heading_does_not_promote_thematic_semantics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _install_retrieval_fakes(monkeypatch, semantic=True, literal=True)
    response = await rag.run_simple_rag(
        object(),
        _request("CONSTRUYENDO UN TEMPLO INEXISTENTE"),
    )
    assert response["research_status"] == "no_evidence"
    assert response["primary_evidence_ids"] == []
    assert response["retrieval"]["query_shape"] == "general"


@pytest.mark.asyncio
async def test_successful_empty_retrieval_is_real_no_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _install_retrieval_fakes(monkeypatch, semantic=False, literal=False)
    response = await rag.run_simple_rag(object(), _request())
    assert response["research_status"] == "no_evidence"
    assert response["status"] == "no_evidence"
    assert response["retrieval"]["semantic_status"] == "ok"
    assert response["retrieval"]["literal_status"] == "ok"
    assert "No se encontró evidencia suficiente" in response["answer_markdown"]


def test_existing_http_endpoint_routes_legacy_requests_to_simple_rag() -> None:
    @asynccontextmanager
    async def fake_transaction(_pool):
        yield object()

    response = {
        "pipeline": "simple_rag",
        "status": "ok",
        "research_status": "complete",
        "original_query": "Relación sangre y habla",
        "answer_markdown": "Respuesta grounded",
        "hits": [],
        "claims": [],
        "primary_evidence_ids": [],
        "warnings": [],
    }
    with (
        patch(
            "modules.library.routes.get_current_user_payload",
            new=AsyncMock(return_value={
                "sub": "10000000-0000-0000-0000-000000000001",
                "role": "admin",
            }),
        ),
        patch(
            "modules.library.routes.get_pg_pool",
            new=AsyncMock(return_value=object()),
        ),
        patch("modules.library.routes.transaction", new=fake_transaction),
        patch(
            "modules.library.routes.run_simple_rag",
            new=AsyncMock(return_value=response),
        ) as simple,
        patch(
            "modules.library.routes.run_investigative_qa_v1",
            new=AsyncMock(),
        ) as advanced,
        TestClient(Litestar(route_handlers=[investigative_qa_v1])) as client,
    ):
        result = client.post(
            "/library/investigative-qa/v1",
            headers={"Authorization": "Bearer test"},
            json={
                "question": "Relación sangre y habla",
                "pipeline": "simple_rag",
            },
        )
    assert result.status_code == 200
    assert result.json()["original_query"] == "Relación sangre y habla"
    simple.assert_awaited_once()
    advanced.assert_not_awaited()


# ---------------------------------------------------------------------------
# Multilingual cross-language variant expansion tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("query", "expected_latin"),
    [
        ("אתה מחפש איפה נמצא מושג העקרב.", "escorpión"),
        ("העקרב", "escorpión"),
        ("עקרב", "escorpión"),
        ("עקרבים", "escorpión"),
        ("דיבור", "habla"),
        ("דם", "sangre"),
        ("פחד", "miedo"),
        ("יראה", "miedo"),
        ("אמונה", "emuná"),
        ("שמחה", "simjá"),
        ("עצבות", "tristeza"),
        ("אזמרה", "azamra"),
    ],
)
def test_hebrew_query_expands_to_latin_variants(query: str, expected_latin: str) -> None:
    variants = rag.build_query_variants(query)
    assert variants[0] == query, "First variant must be original"
    assert expected_latin in variants, f"Expected {expected_latin} in {variants}"


@pytest.mark.parametrize(
    ("query", "expected_hebrew"),
    [
        ("escorpión", "עקרב"),
        ("escorpion", "עקרב"),
        ("escorpiones", "עקרב"),
        ("scorpion", "עקרב"),
        ("scorpions", "עקרב"),
        ("habla", "דיבור"),
        ("speech", "דיבור"),
        ("sangre", "דם"),
        ("blood", "דם"),
        ("miedo", "פחד"),
        ("fear", "פחד"),
        ("emuná", "אמונה"),
        ("emuna", "אמונה"),
        ("faith", "אמונה"),
        ("alegría", "שמחה"),
        ("joy", "שמחה"),
        ("tristeza", "עצבות"),
        ("sadness", "עצבות"),
    ],
)
def test_latin_query_expands_to_hebrew_variants(query: str, expected_hebrew: str) -> None:
    variants = rag.build_query_variants(query)
    assert variants[0] == query, "First variant must be original"
    assert expected_hebrew in variants, f"Expected {expected_hebrew} in {variants}"


def test_unrelated_queries_dont_expand() -> None:
    variants = rag.build_query_variants("qué es la Torá")
    assert variants[0] == "qué es la Torá"


def test_related_concepts_not_merged_as_synonyms() -> None:
    variants = rag.build_query_variants("עקרב")
    assert "serpiente" not in variants  # related_concept, not alias


def test_hebrew_prefix_stripping_expands_scorpion() -> None:
    variants = rag.build_query_variants("העקרב")
    assert "escorpión" in variants
    assert "scorpion" in variants


def test_fold_preserves_latin_and_catalog_lookup_handles_hebrew() -> None:
    assert rag._fold("escorpión") == "escorpion"
    hebrew_cross = rag._hebrew_catalog_cross_language_variants("העקרב")
    assert "escorpión" in hebrew_cross


def test_variant_count_limited() -> None:
    variants = rag.build_query_variants("שמחה אמונה עצבות עקרב דיבור דם פחד")
    assert len(variants) <= 36
    assert variants[0] == "שמחה אמונה עצבות עקרב דיבור דם פחד"
