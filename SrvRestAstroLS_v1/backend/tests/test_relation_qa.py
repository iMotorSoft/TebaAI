from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError

from infrastructure.milvus.errors import MilvusConnectionError
from modules.library.domain import KnowledgeScope
from modules.library.relation_qa_ai import (
    EditorialAIResult,
    RelationQAAIError,
    validate_editorial_ai_result,
)
from modules.library.relation_qa_evidence import (
    build_source_map,
    classify_evidence,
    merge_candidate_rows,
    validate_sources_resolve_to_pg,
)
from modules.library.relation_qa_schemas import (
    EvidenceType,
    RelationQARequest,
    RelationQASource,
)
from modules.library.relation_qa_service import run_relation_qa


def _row(**overrides):
    value = {
        "chunk_id": str(uuid4()),
        "document_id": str(uuid4()),
        "document_title": "Test Breslov",
        "subtitle": "",
        "document_status": "ready",
        "content": "El texto habla de sangre y oración.",
        "language": "es",
        "page_start": 10,
        "page_end": 10,
        "chapter": "",
        "section": "",
        "node_path": "",
        "block_type": "",
        "block_subtype": "",
        "evidence_role": "",
        "citable": True,
        "metadata": {},
        "bibliographic_metadata": {},
        "chunk_index": 1,
        "retrieval_methods": ["fts_websearch"],
        "score": 0.8,
    }
    value.update(overrides)
    return value


class TestRelationQARequest:
    def test_defaults(self) -> None:
        request = RelationQARequest(question="¿Dónde aparece esta relación?")
        assert request.top_k == 20
        assert request.language == "auto"
        assert request.include_test_candidates is False
        assert request.use_ai is True
        assert request.evidence_depth == "standard"

    @pytest.mark.parametrize("language", ["es", "en", "he", "auto"])
    def test_languages(self, language: str) -> None:
        assert RelationQARequest(question="valid question", language=language).language == language

    def test_question_required(self) -> None:
        with pytest.raises(ValidationError):
            RelationQARequest()  # type: ignore[call-arg]

    def test_top_k_maximum(self) -> None:
        with pytest.raises(ValidationError):
            RelationQARequest(question="valid question", top_k=51)


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"content": "La sangre aparece aquí."}, EvidenceType.literal_phrase),
        (
            {"content": "La conexión entre sangre y habla es explícita."},
            EvidenceType.literal_relation,
        ),
        (
            {"metadata": {"source_refs": [{"matched_text": "LM 1"}]}},
            EvidenceType.explicit_reference,
        ),
        ({"content": "Jeremías 1:14 enseña..."}, EvidenceType.biblical_citation),
        ({"content": "Bereshit Rabah 2:1"}, EvidenceType.rabbinic_source),
        ({"block_subtype": "breslov_teaching"}, EvidenceType.breslov_text),
        ({"block_type": "main_explanation_es"}, EvidenceType.editorial_explanation),
        ({"block_type": "footnote"}, EvidenceType.footnote_reference),
        ({"block_type": "marginal_source"}, EvidenceType.marginal_source),
        ({"block_type": "internal_cross_reference"}, EvidenceType.internal_cross_reference),
        ({"block_type": "source_hebrew"}, EvidenceType.source_hebrew),
        ({"content": "Este derash vincula los conceptos."}, EvidenceType.derash_interpretation),
        ({"content": "Hay un remez en el pasaje."}, EvidenceType.remez_hint),
        ({"content": "דבר"}, EvidenceType.ambiguous),
        (
            {"block_type": "composite_page_context", "citable": False},
            EvidenceType.excluded_false_positive,
        ),
    ],
)
def test_evidence_classifier(overrides, expected: EvidenceType) -> None:
    classification = classify_evidence(
        _row(**overrides), ["sangre"], ["habla", "דבר"]
    )
    assert expected in classification.types


def test_ai_inference_type_is_structured() -> None:
    assert EvidenceType.ai_inference.value == "ai_inference"


def test_short_transliteration_dam_does_not_match_inside_spanish_word() -> None:
    classification = classify_evidence(
        _row(content="Podamos alcanzar sabiduría y hablar con claridad."),
        ["sangre", "dam"],
        ["habla", "hablar"],
    )
    assert EvidenceType.cooccurrence_same_chunk not in classification.types


def test_merge_deduplicates_chunk_id_and_preserves_methods() -> None:
    chunk_id = str(uuid4())
    merged = merge_candidate_rows(
        [_row(chunk_id=chunk_id, retrieval_methods=["fts_websearch"])],
        [_row(chunk_id=chunk_id, retrieval_methods=["vector"], score=0.9)],
    )
    assert len(merged) == 1
    assert merged[0]["retrieval_methods"] == ["fts_websearch", "vector"]


def test_source_map_exposes_test_candidate_status() -> None:
    sources = build_source_map(
        [_row(document_status="test_candidate")], ["sangre"], ["habla"], "standard", 20
    )
    assert sources[0].document_status == "test_candidate"


def _source(**overrides) -> RelationQASource:
    value = {
        "source_id": "src_1",
        "document_id": str(uuid4()),
        "document_title": "Book",
        "document_status": "ready",
        "chunk_id": str(uuid4()),
        "evidence_type": EvidenceType.breslov_text,
        "evidence_types": [EvidenceType.breslov_text],
        "retrieval_method": "fts_websearch",
        "snippet": "Canonical PostgreSQL text",
    }
    value.update(overrides)
    return RelationQASource(**value)


def test_source_without_pg_identity_fails() -> None:
    with pytest.raises(ValueError, match="canonical PostgreSQL"):
        validate_sources_resolve_to_pg([_source(document_id="")])


def test_composite_cannot_be_final_citation() -> None:
    with pytest.raises(ValueError, match="composite_page_context"):
        validate_sources_resolve_to_pg(
            [_source(block_type="composite_page_context", is_final_citation=True)]
        )


def test_content_preview_cannot_be_final_source() -> None:
    with pytest.raises(ValueError, match="content_preview"):
        validate_sources_resolve_to_pg([_source(retrieval_method="content_preview")])


def test_duplicate_chunk_id_fails() -> None:
    source = _source()
    with pytest.raises(ValueError, match="Duplicate chunk_id"):
        validate_sources_resolve_to_pg([source, source.model_copy()])


def test_ai_validation_forces_inference_and_low_certainty_without_literal() -> None:
    source = _source(source_id="src_allowed")
    result = validate_editorial_ai_result(
        EditorialAIResult(
            short_conclusion="Hay una lectura temática.",
            editorial_answer_markdown="Lectura editorial [src_allowed].",
            editorial_certainty="high",
            source_ids=["src_allowed"],
        ),
        [source],
        literal_relation_found=False,
    )
    assert result.ai_inference_used is True
    assert result.editorial_certainty == "low"
    assert result.short_conclusion.startswith("No se encontró una relación literal")


def test_ai_validation_rejects_promoted_literal_claim() -> None:
    source = _source(source_id="src_allowed")
    with pytest.raises(RelationQAAIError, match="promoted inference"):
        validate_editorial_ai_result(
            EditorialAIResult(
                short_conclusion="Se encontró una conexión literal entre ambos conceptos.",
                editorial_answer_markdown="Afirmación [src_allowed].",
                source_ids=["src_allowed"],
            ),
            [source],
            literal_relation_found=False,
        )


def test_ai_validation_rejects_non_final_source_id() -> None:
    source = _source(source_id="src_context", is_final_citation=False)
    with pytest.raises(RelationQAAIError, match="unknown or empty"):
        validate_editorial_ai_result(
            EditorialAIResult(
                short_conclusion="Lectura temática.",
                editorial_answer_markdown="Contexto [src_context].",
                source_ids=["src_context"],
            ),
            [source],
            literal_relation_found=False,
        )


def _scope() -> KnowledgeScope:
    return KnowledgeScope(
        id=uuid4(),
        organization_id=uuid4(),
        workspace_id=uuid4(),
        project_id=uuid4(),
        knowledge_scope_code="breslov_primary",
        name="Breslov",
        status="active",
    )


@pytest.mark.asyncio
async def test_ai_guardrail_keeps_literal_false_and_marks_inference() -> None:
    request = RelationQARequest(
        question="¿Dónde está la conexión entre sangre y habla?",
        concept_a="sangre",
        concept_b="habla",
    )
    ai_result = EditorialAIResult(
        short_conclusion="No hay relación literal; lectura INFERIDA_POR_IA [src_test].",
        editorial_answer_markdown="Lectura editorial [src_test].",
        editorial_certainty="low",
        ai_inference_used=True,
        source_ids=["src_test"],
    )
    row = _row(chunk_id="test-0000-0000-0000")
    with (
        patch(
            "modules.library.relation_qa_service.retrieve_relation_evidence",
            new=AsyncMock(return_value=([row], ["postgresql_fts_websearch"], [], True)),
        ),
        patch(
            "modules.library.relation_qa_service.build_editorial_answer_with_ai",
            new=AsyncMock(return_value=ai_result),
        ),
    ):
        response = await run_relation_qa(AsyncMock(), request, _scope())
    assert response.answer.literal_relation_found is False
    assert response.answer.ai_inference_used is True
    assert "ai_inference: INFERIDA_POR_IA" in response.warnings


@pytest.mark.asyncio
async def test_ai_parse_failure_returns_deterministic_fallback() -> None:
    request = RelationQARequest(
        question="¿Dónde está la conexión entre sangre y habla?",
        concept_a="sangre",
        concept_b="habla",
    )
    with (
        patch(
            "modules.library.relation_qa_service.retrieve_relation_evidence",
            new=AsyncMock(return_value=([_row()], ["postgresql_fts_websearch"], [], True)),
        ),
        patch(
            "modules.library.relation_qa_service.build_editorial_answer_with_ai",
            new=AsyncMock(side_effect=RelationQAAIError("bad json")),
        ),
    ):
        response = await run_relation_qa(AsyncMock(), request, _scope())
    assert response.method.used_ai is False
    assert response.answer.ai_inference_used is False
    assert any("ai_response_parse_failed" in warning for warning in response.warnings)


@pytest.mark.asyncio
async def test_milvus_connection_error_falls_back_to_lexical_retrieval() -> None:
    request = RelationQARequest(
        question="¿Qué relación hay entre sangre y habla?",
        concept_a="sangre",
        concept_b="habla",
        use_ai=False,
    )
    row = _row(chunk_id="test-lexical-0001")
    with (
        patch(
            "modules.library.relation_qa_service.search_fts_chunks",
            new=AsyncMock(return_value=[row]),
        ),
        patch(
            "modules.library.relation_qa_service.search_ilike_chunks",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "modules.library.relation_qa_service.search_relation_pattern_chunks",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "modules.library.relation_qa_service.search_cooccurrence_chunks",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "modules.library.relation_qa_service._vector_search_sync",
            side_effect=MilvusConnectionError("Milvus down"),
        ),
    ):
        response = await run_relation_qa(AsyncMock(), request, _scope())

    assert response.method.used_milvus is False
    assert response.sources
    assert any(
        warning.startswith("milvus_unavailable: MilvusConnectionError")
        for warning in response.warnings
    )
