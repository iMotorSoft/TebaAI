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

    monkeypatch.setattr(rag, "resolve_ready_documents", documents)
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
            "answer_markdown": "Según la página 999.",
            "claims": [{
                "text": "Grounded",
                "evidence_ids": ["ev-real"],
                "relation_type": "direct",
                "confidence": "high",
            }],
        }, [chunk])


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
async def test_missing_canonical_chunk_is_honest_no_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _install_retrieval_fakes(monkeypatch)

    async def missing_chunks(*args, **kwargs):
        return []

    monkeypatch.setattr(rag, "fetch_canonical_chunks", missing_chunks)
    response = await rag.run_simple_rag(object(), _request())
    assert response["research_status"] == "no_evidence"
    assert response["retrieval"]["semantic_status"] == "ok"
    assert response["retrieval"]["literal_status"] == "ok"
    assert response["evidence"] == []


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
