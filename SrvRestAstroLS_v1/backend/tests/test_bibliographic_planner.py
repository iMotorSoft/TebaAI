"""Tests for Bibliographic Query Planner V1."""

from __future__ import annotations

from typing import Any

import pytest

from modules.library.bibliographic_planner import (
    BibliographicResult,
    Intent,
    PresenceType,
    VolumeConfidence,
    VolumeSource,
    build_bibliographic_answer,
    build_query_plan,
    classify_intent,
    classify_presence,
    make_bibliographic_evidence_id,
    resolve_subject,
    resolve_volume_for_document,
    resolve_work_scope,
    run_bibliographic_planner,
)


# -- Fixtures --------------------------------------------------------------


def _make_doc(
    doc_id: str = "47768aac-704e-4296-9649-53b9ea037096",
    title: str = "Likutey Halajot Explicado — Interior Final",
    edition: str = "First Edition",
    metadata: dict[str, Any] | None = None,
    document_code: str = "",
    filename: str = "LIKUTEY HALAJOT (Interior Final).pdf",
    status: str = "test_candidate",
) -> dict[str, Any]:
    return {
        "id": doc_id,
        "title": title,
        "edition": edition,
        "document_code": document_code,
        "source_filename": filename,
        "status": status,
        "metadata": metadata or {},
    }


def _make_chunk(
    chunk_id: str = "chunk-azamra-1",
    doc_id: str = "47768aac-704e-4296-9649-53b9ea037096",
    content: str = "Azamra es la enseñanza del Rebe Najmán sobre buscar el bien.",
    page: int = 44,
    printed: str | None = None,
    section_title: str = "Discurso sobre el levantarse",
    work: str = "Likutey Halajot",
    **overrides: Any,
) -> dict[str, Any]:
    return {
        "chunk_id": chunk_id,
        "id": chunk_id,
        "document_id": doc_id,
        "work": work,
        "title": work,
        "content": content,
        "markdown": content,
        "pdf_page": page,
        "page_start": page,
        "printed_page": printed,
        "printed_page_label": printed,
        "section_title": section_title,
        "section": section_title,
        "heading_original": None,
        "heading_text": None,
        "exact_quote": None,
        "literal_match_type": "",
        "language": "es",
        **overrides,
    }


# -- Test: Intent Classification -------------------------------------------


class TestClassifyIntent:
    def test_bibliographic_locator_volume(self):
        intent, info = classify_intent("Azamra, ¿en qué tomo de Likutey Halajot está?")
        assert intent == Intent.BIBLIOGRAPHIC_LOCATOR
        assert info.get("subject", "").lower() == "azamra"
        assert "likutey halajot" in info.get("work", "").lower()

    def test_bibliographic_locator_alternative(self):
        intent, info = classify_intent("¿En qué volumen de Likutey Halajot aparece Azamra?")
        assert intent == Intent.BIBLIOGRAPHIC_LOCATOR
        assert "azamra" in info.get("subject", "").lower()
        assert "likutey halajot" in info.get("work", "").lower()

    def test_bibliographic_locator_donde(self):
        intent, info = classify_intent("¿Dónde está Azamra en Likutey Halajot?")
        assert intent == Intent.BIBLIOGRAPHIC_LOCATOR
        assert "azamra" in info.get("subject", "").lower()

    def test_general_query_not_bibliographic(self):
        intent, info = classify_intent("¿Qué enseña Azamra?")
        assert intent == Intent.GENERAL_QUERY
        # Subject should include 'Azamra' or 'enseña'
        assert len(info.get("subject", "")) >= 2

    def test_unknown_intent(self):
        intent, info = classify_intent("Hola")
        assert intent == Intent.UNKNOWN

    def test_hebrew_query(self):
        intent, info = classify_intent("¿Dónde está אזמרה en Likutey Halajot?")
        assert intent == Intent.BIBLIOGRAPHIC_LOCATOR

    def test_bibliographic_without_explicit_volume(self):
        intent, info = classify_intent("Azamra en Likutey Halajot")
        # No explicit "tomo" keyword, subject found
        assert intent == Intent.GENERAL_QUERY


# -- Test: Subject Resolution ----------------------------------------------


class TestResolveSubject:
    def test_azamra_canonical(self):
        subj = resolve_subject("Azamra")
        assert subj.canonical == "Azamra"
        assert "azamra" in [v.lower() for v in subj.variants]
        assert "אזמרה" in subj.hebrew_variants
        assert "LM 282" in subj.aliases

    def test_azamra_variant(self):
        subj = resolve_subject("AZAMRA")
        assert subj.canonical == "Azamra"

    def test_lm282_alias(self):
        subj = resolve_subject("LM 282")
        assert subj.canonical == "Azamra"
        assert "lM 282" in [a.lower() for a in subj.aliases] or "lm 282" in [a.lower() for a in subj.aliases]

    def test_unknown_subject(self):
        subj = resolve_subject("Concepto Inventado")
        assert subj.canonical == "Concepto Inventado"
        assert subj.hebrew_variants == []


# -- Test: Work Resolution -------------------------------------------------


class TestResolveWorkScope:
    def test_resolves_likutey_halajot(self):
        docs = [
            _make_doc(title="Likutey Halajot Explicado — Interior Final"),
            _make_doc(doc_id="other", title="Other Work"),
        ]
        scope = resolve_work_scope("Likutey Halajot", docs)
        assert scope.canonical_label == "Likutey Halajot"
        assert len(scope.document_ids) == 1
        assert scope.resolution_method == "document_match"

    def test_alias_variant(self):
        docs = [_make_doc(title="Likutey Halajot Explicado")]
        scope = resolve_work_scope("Likutey Halachot", docs)
        assert scope.canonical_label == "Likutey Halajot"

    def test_unknown_work(self):
        docs = [_make_doc(title="Some Other Work")]
        scope = resolve_work_scope("Obra Inexistente", docs)
        assert scope.confidence == 0.0
        assert "work_not_recognized" in scope.warnings

    def test_not_in_corpus(self):
        scope = resolve_work_scope("Likutey Moharán", [_make_doc()])
        # Likutey Moharán is not a family of Likutey Halajot
        assert scope.confidence == 0.0


# -- Test: Volume Resolution -----------------------------------------------


class TestResolveVolume:
    def test_explicit_metadata(self):
        doc = _make_doc(metadata={"volume": "2"})
        vol = resolve_volume_for_document(doc)
        assert vol.volume_number == 2
        assert vol.volume_source == VolumeSource.EXPLICIT_METADATA
        assert vol.volume_confidence == VolumeConfidence.EXACT

    def test_edition_label(self):
        doc = _make_doc(edition="First Edition")
        vol = resolve_volume_for_document(doc)
        assert vol.volume_label == "First Edition"
        assert vol.volume_source == VolumeSource.EDITION_LABEL
        assert vol.volume_confidence == VolumeConfidence.HIGH

    def test_document_title_volume(self):
        doc = _make_doc(title="Likutey Halajot Tomo 2")
        vol = resolve_volume_for_document(doc)
        assert vol.volume_number == 2
        assert vol.volume_source == VolumeSource.DOCUMENT_TITLE

    def test_filename_volume(self):
        doc = _make_doc(filename="LH_Vol_3.pdf", title="Likutey Halajot")
        vol = resolve_volume_for_document(doc)
        assert vol.volume_number == 3
        assert vol.volume_source == VolumeSource.FILENAME
        assert vol.volume_confidence == VolumeConfidence.LOW

    def test_unresolved_default(self):
        doc = _make_doc(title="Likutey Halajot", edition="", metadata={})
        vol = resolve_volume_for_document(doc)
        assert vol.volume_source == VolumeSource.UNRESOLVED
        assert vol.volume_confidence == VolumeConfidence.UNRESOLVED
        assert "volume_not_determined" in vol.warnings


# -- Test: Presence Classification -----------------------------------------


class TestPresenceClassification:
    def test_literal_exact(self):
        subj = resolve_subject("Azamra")
        p = classify_presence("Azamra es una enseñanza importante.", subj)
        assert p == PresenceType.LITERAL_EXACT

    def test_hebrew_exact(self):
        subj = resolve_subject("Azamra")
        p = classify_presence("אזמרה significa cantaré.", subj)
        assert p == PresenceType.HEBREW_EXACT

    def test_bibliographic_reference(self):
        subj = resolve_subject("Azamra")
        p = classify_presence("Ver Likutey Moharán 282 para más detalles.", subj)
        assert p == PresenceType.BIBLIOGRAPHIC_REFERENCE

    def test_thematic_development(self):
        subj = resolve_subject("Azamra")
        p = classify_presence("Buscar el bien en uno mismo y en los demás.", subj)
        assert p == PresenceType.THEMATIC_DEVELOPMENT


# -- Test: Query Plan ------------------------------------------------------


class TestBuildQueryPlan:
    def test_full_plan_for_main_query(self):
        plan = build_query_plan("Azamra, ¿en qué tomo de Likutey Halajot está?")
        assert plan.intent == Intent.BIBLIOGRAPHIC_LOCATOR
        assert plan.subject is not None
        assert plan.subject.canonical == "Azamra"
        assert plan.scope is not None
        assert "likutey halajot" in plan.scope.surface.lower()
        assert "volume" in plan.return_dimensions

    def test_non_bibliographic_plan(self):
        plan = build_query_plan("¿Qué enseña Azamra?")
        assert plan.intent != Intent.BIBLIOGRAPHIC_LOCATOR
        assert "not_a_bibliographic_query" in plan.warnings


# -- Test: Bibliographic Answer Build --------------------------------------


class TestBuildBibliographicAnswer:
    def test_builds_from_occurrences(self):
        from modules.library.bibliographic_planner import (
            BibliographicOccurrence,
            QueryPlan,
            ResolvedVolume,
        )

        plan = build_query_plan("Azamra, ¿en qué tomo de Likutey Halajot está?")
        plan = QueryPlan(
            intent=plan.intent,
            subject=plan.subject,
            scope=plan.scope,
            return_dimensions=plan.return_dimensions,
            group_by=plan.group_by,
        )

        vol = ResolvedVolume(
            volume_id="vol-single",
            volume_number=0,
            volume_label="Obra completa",
            volume_source=VolumeSource.EDITION_LABEL,
            volume_confidence=VolumeConfidence.HIGH,
            document_id="doc-1",
            document_title="Likutey Halajot Explicado",
            edition_label="First Edition",
        )

        occs = [
            BibliographicOccurrence(
                occurrence_id="occ-1",
                document_id="doc-1",
                document_title="Likutey Halajot Explicado",
                volume=vol,
                presence_type=PresenceType.LITERAL_EXACT,
                pdf_page=44,
                section_title="Discurso sobre el levantarse",
                evidence_id="ev-test-1",
            ),
            BibliographicOccurrence(
                occurrence_id="occ-2",
                document_id="doc-1",
                document_title="Likutey Halajot Explicado",
                volume=vol,
                presence_type=PresenceType.HEBREW_EXACT,
                pdf_page=68,
                evidence_id="ev-test-2",
            ),
        ]

        answer = build_bibliographic_answer(plan, occs, "Azamra, ¿en qué tomo de Likutey Halajot está?")
        assert len(answer.results) == 1
        assert answer.results[0].occurrence_count == 2
        assert "literal_exact" in answer.results[0].presence_types
        assert answer.results[0].primary_evidence_id is not None
        assert answer.status == "complete"

    def test_empty_occurrences(self):
        from modules.library.bibliographic_planner import QueryPlan

        plan = QueryPlan(intent=Intent.BIBLIOGRAPHIC_LOCATOR)
        answer = build_bibliographic_answer(plan, [], "test")
        assert answer.status == "no_evidence"
        assert "no_occurrences_found" in answer.warnings


# -- Test: Integration (run_bibliographic_planner) -------------------------


class TestRunBibliographicPlanner:
    def test_runs_on_azamra_chunks(self):
        docs = [_make_doc()]
        chunks = [
            _make_chunk(content="Azamra es la enseñanza.", page=44),
            _make_chunk(chunk_id="chunk-2", content="אזמרה significa cantaré.", page=68),
        ]
        result = run_bibliographic_planner(
            "Azamra, ¿en qué tomo de Likutey Halajot está?",
            chunks,
            docs,
        )
        assert result["bibliographic_active"] is True
        assert result["query_plan"] is not None
        assert result["query_plan"]["intent"] == "bibliographic_locator"
        assert len(result["bibliographic_results"]) >= 1
        br = result["bibliographic_results"][0]
        assert br["occurrence_count"] >= 2
        assert "literal_exact" in br["presence_types"]

    def test_non_bibliographic_returns_inactive(self):
        result = run_bibliographic_planner("¿Qué enseña Azamra?", [], [])
        assert result["bibliographic_active"] is False
        assert result["query_plan"] is None

    def test_no_chunks_returns_no_evidence(self):
        docs = [_make_doc()]
        result = run_bibliographic_planner(
            "Azamra, ¿en qué tomo de Likutey Halajot está?",
            [],
            docs,
        )
        assert result["bibliographic_active"] is False
        assert len(result["bibliographic_results"]) == 0

    def test_deduplicates_identical_content(self):
        docs = [_make_doc()]
        content = "Azamra es una enseñanza."
        chunks = [
            _make_chunk(chunk_id="c1", content=content, page=44),
            _make_chunk(chunk_id="c2", content=content, page=44),  # same content
        ]
        result = run_bibliographic_planner(
            "Azamra, ¿en qué tomo de Likutey Halajot está?",
            chunks,
            docs,
        )
        # Should have deduplicated
        total_occs = sum(r["occurrence_count"] for r in result["bibliographic_results"])
        assert total_occs == 1


# -- Test: Evidence ID Stability -------------------------------------------


class TestEvidenceId:
    def test_stable_from_same_inputs(self):
        id1 = make_bibliographic_evidence_id("doc-1", "chunk-1", "literal_exact")
        id2 = make_bibliographic_evidence_id("doc-1", "chunk-1", "literal_exact")
        assert id1 == id2
        assert id1.startswith("ev-")

    def test_different_inputs_give_different_ids(self):
        id1 = make_bibliographic_evidence_id("doc-1", "chunk-1", "literal_exact")
        id2 = make_bibliographic_evidence_id("doc-1", "chunk-2", "literal_exact")
        assert id1 != id2


# -- Test: Prompt Generation -----------------------------------------------


class TestMakeBibliographicPrompt:
    def test_prompt_contains_evidence(self):
        from modules.library.bibliographic_planner import (
            BibliographicOccurrence,
            QueryPlan,
            ResolvedVolume,
            build_bibliographic_answer,
            make_bibliographic_prompt,
        )

        plan = QueryPlan(intent=Intent.BIBLIOGRAPHIC_LOCATOR)
        vol = ResolvedVolume(
            volume_id="v1", volume_number=0, volume_label="Obra completa",
            volume_source=VolumeSource.EDITION_LABEL, volume_confidence=VolumeConfidence.HIGH,
        )
        occs = [
            BibliographicOccurrence(
                occurrence_id="o1", document_id="d1", document_title="Test",
                volume=vol, presence_type=PresenceType.LITERAL_EXACT,
                pdf_page=44, evidence_id="ev-test",
            )
        ]
        answer = build_bibliographic_answer(plan, occs, "test")
        prompt = make_bibliographic_prompt(plan, answer)
        assert "LITERAL_EXACT" in prompt or "literal_exact" in prompt
        assert "44" in prompt
        assert "Obra completa" in prompt
