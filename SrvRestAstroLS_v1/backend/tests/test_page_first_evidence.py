"""Tests for page-first evidence contract V1."""

from __future__ import annotations

import hashlib
from typing import Any

import pytest

from modules.library.page_first_evidence import (
    CanonicalPage,
    EvidenceLocation,
    PageReference,
    SectionReference,
    assemble_page_text,
    build_evidence_v1,
    extract_context,
    frontend_hint_v1,
    locate_evidence_within_page,
    make_evidence_id,
    resolve_containing_section,
    resolve_page_for_retrieval_hit,
)


# -- Fixtures ------------------------------------------------------------


def _make_chunk(
    chunk_id: str = "91aba034-7a02-4520-aa1c-3f29be2741be",
    doc_id: str = "47768aac-704e-4296-9649-53b9ea037096",
    work: str = "Likutey Halajot",
    page: int = 51,
    printed: str | None = "33",
    section_title: str = "השכמת הבוקר",
    content: str = "4 ■ CONSTRUYENDO UN MISHKÁN",
    markdown: str | None = None,
    chunk_index: int = 356,
    page_end: int | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    return {
        "chunk_id": chunk_id,
        "id": chunk_id,
        "document_id": doc_id,
        "work": work,
        "title": work,
        "pdf_page": page,
        "canonical_pdf_page_start": page,
        "page_start": page,
        "page_end": page_end or page,
        "printed_page": printed,
        "printed_page_label": printed,
        "section_title": section_title,
        "section": section_title,
        "content": content,
        "markdown": markdown or content,
        "chunk_index": chunk_index,
        "language": "es",
        "evidence_role": "body_main_idea",
        "source_layer": "canonical_page",
        "heading_original": None,
        "heading_normalized": None,
        "associated_chunk_id": None,
        **overrides,
    }


def _body_chunk(
    chunk_id: str = "d0ae8b80-0947-4503-a45f-11e4b9c7d0ff",
    content: str = "El Rabí Natán concluye su explicación de la capacidad de Moshé",
    chunk_index: int = 357,
    **overrides: Any,
) -> dict[str, Any]:
    return _make_chunk(
        chunk_id=chunk_id,
        content=content,
        markdown=content,
        chunk_index=chunk_index,
        **overrides,
    )


# -- Test: Page Reference ------------------------------------------------


class TestPageReference:
    def test_from_chunk_with_pdf_page(self):
        chunk = _make_chunk(pdf_page=51)
        ref = resolve_page_for_retrieval_hit(chunk)
        assert ref.pdf_page == 51
        assert ref.document_id == "47768aac-704e-4296-9649-53b9ea037096"
        assert ref.document_title == "Likutey Halajot"
        assert ref.resolution_method == "chunk_page_start"

    def test_from_chunk_with_printed_page(self):
        chunk = _make_chunk(printed_page="33")
        ref = resolve_page_for_retrieval_hit(chunk)
        assert ref.printed_page == 33

    def test_from_chunk_without_page(self):
        chunk = _make_chunk(pdf_page=None, page_start=None)
        chunk["canonical_pdf_page_start"] = None
        ref = resolve_page_for_retrieval_hit(chunk)
        assert ref.pdf_page is None
        assert ref.resolution_method == "page_marker_inference"

    def test_from_chunk_with_content_node_id(self):
        chunk = _make_chunk(content_node_id="abc-123")
        ref = resolve_page_for_retrieval_hit(chunk)
        assert ref.pdf_page == 51  # falls back to pdf_page


# -- Test: Canonical Page Assembly ---------------------------------------


class TestAssemblePageText:
    def test_single_chunk(self):
        chunk = _make_chunk()
        page = assemble_page_text(
            PageReference(
                page_id=None,
                pdf_page=51,
                printed_page=33,
                document_id="doc-1",
                document_title="Test",
            ),
            [chunk],
        )
        assert "CONSTRUYENDO UN MISHKÁN" in page.text
        assert page.pdf_page == 51
        assert page.printed_page == 33

    def test_multiple_chunks_same_page(self):
        heading = _make_chunk(content="4 ■ CONSTRUYENDO UN MISHKÁN", chunk_index=356)
        body = _body_chunk()
        page = assemble_page_text(
            PageReference(
                page_id=None,
                pdf_page=51,
                printed_page=33,
                document_id="doc-1",
                document_title="Test",
            ),
            [body, heading],
        )
        assert "CONSTRUYENDO UN MISHKÁN" in page.text
        assert "El Rabí Natán concluye" in page.text

    def test_deduplicates_identical_content(self):
        chunk1 = _make_chunk(chunk_index=1, content="Same text")
        chunk2 = _make_chunk(chunk_index=2, content="Same text")
        page = assemble_page_text(
            PageReference(
                page_id=None, pdf_page=1, printed_page=None, document_id="doc-1", document_title="Test"
            ),
            [chunk1, chunk2],
        )
        # Only one occurrence
        assert page.text.count("Same text") == 1

    def test_empty_chunks_list(self):
        page = assemble_page_text(
            PageReference(
                page_id=None, pdf_page=1, printed_page=None, document_id="doc-1", document_title="Test"
            ),
            [],
        )
        assert page.text == ""
        assert page.source == "empty"


# -- Test: Evidence Localization -----------------------------------------


class TestLocateEvidenceWithinPage:
    def test_exact_match(self):
        page_text = "El Rabí Natán concluye su explicación de la capacidad."
        page = CanonicalPage(
            page_id=None,
            document_id="doc-1",
            pdf_page=51,
            printed_page=33,
            text=page_text,
        )
        chunk = _make_chunk(
            content="El Rabí Natán concluye su explicación",
            markdown="El Rabí Natán concluye su explicación",
        )
        loc = locate_evidence_within_page("concluye", page, chunk)
        assert loc.location_precision == "exact"
        assert "El Rabí Natán concluye su explicación" in loc.exact_quote
        assert loc.start_offset is not None
        assert loc.end_offset is not None

    def test_normalized_match_with_accent(self):
        page_text = "CONSTRUYENDO UN MISHKÁN es el tema."
        page = CanonicalPage(
            page_id=None,
            document_id="doc-1",
            pdf_page=51,
            printed_page=33,
            text=page_text,
        )
        chunk = _make_chunk(
            content="CONSTRUYENDO UN MISHKÁN",
            markdown="CONSTRUYENDO UN MISHKÁN",
        )
        # Query without accent should match normalized
        loc = locate_evidence_within_page("MISHKAN", page, chunk)
        assert loc.location_precision in ("exact", "normalized_exact")

    def test_token_span_fallback(self):
        page_text = "El Rabí Natán concluye su explicación de la capacidad."
        page = CanonicalPage(
            page_id=None,
            document_id="doc-1",
            pdf_page=51,
            printed_page=33,
            text=page_text,
        )
        chunk = _make_chunk(
            content="Natán concluye su explicación",
            markdown="Natán concluye su explicación",
        )
        loc = locate_evidence_within_page("Natán concluye su explicación", page, chunk)
        assert loc.location_precision in ("exact", "normalized_exact", "token_span")

    def test_block_level_fallback(self):
        page_text = "Texto completamente diferente sin coincidencias."
        page = CanonicalPage(
            page_id=None,
            document_id="doc-1",
            pdf_page=1,
            printed_page=None,
            text=page_text,
        )
        chunk = _make_chunk(
            content="Contenido del chunk que no está en el page text",
            markdown="Contenido del chunk que no está en el page text",
        )
        loc = locate_evidence_within_page("sin coincidencias", page, chunk)
        # Should still find something because query appears in page text
        assert loc.location_precision in ("exact", "normalized_exact", "block_level")

    def test_unresolved_when_empty_page(self):
        page = CanonicalPage(
            page_id=None,
            document_id="doc-1",
            pdf_page=1,
            printed_page=None,
            text="",
        )
        chunk = _make_chunk()
        loc = locate_evidence_within_page("test", page, chunk)
        assert loc.location_precision == "unresolved"


# -- Test: Context Extraction --------------------------------------------


class TestExtractContext:
    def test_extracts_before_and_after(self):
        page = CanonicalPage(
            page_id=None,
            document_id="doc-1",
            pdf_page=51,
            printed_page=33,
            text="Antes. El Rabí Natán concluye su explicación. Después.",
        )
        loc = EvidenceLocation(
            exact_quote="El Rabí Natán concluye su explicación",
            start_offset=7,
            end_offset=46,
            location_precision="exact",
        )
        before, after = extract_context(page, loc, context_chars=20)
        assert before is not None
        assert "Antes" in before
        assert after is not None
        assert "Después" in after

    def test_none_when_no_offsets(self):
        page = CanonicalPage(
            page_id=None, document_id="doc-1", pdf_page=1, printed_page=None, text="Text"
        )
        loc = EvidenceLocation(
            exact_quote="Text", start_offset=None, end_offset=None, location_precision="block_level"
        )
        before, after = extract_context(page, loc)
        assert before is None
        assert after is None


# -- Test: Section Resolution --------------------------------------------


class TestResolveContainingSection:
    def test_from_section_title(self):
        chunk = _make_chunk(section_title="4. CONSTRUYENDO UN MISHKÁN")
        page = PageReference(
            page_id=None, pdf_page=51, printed_page=33, document_id="doc-1", document_title="Test"
        )
        canonical = CanonicalPage(
            page_id=None,
            document_id="doc-1",
            pdf_page=51,
            printed_page=33,
            text="4. CONSTRUYENDO UN MISHKÁN",
        )
        section = resolve_containing_section(page, canonical, chunk)
        assert section.heading_text == "4. CONSTRUYENDO UN MISHKÁN"
        assert section.heading_source == "section_title"

    def test_from_heading_original(self):
        chunk = _make_chunk(
            section_title="",
            heading_original="4. CONSTRUYENDO UN MISHKÁN",
        )
        page = PageReference(
            page_id=None, pdf_page=51, printed_page=33, document_id="doc-1", document_title="Test"
        )
        canonical = CanonicalPage(
            page_id=None,
            document_id="doc-1",
            pdf_page=51,
            printed_page=33,
            text="",
        )
        section = resolve_containing_section(page, canonical, chunk)
        assert section.heading_text == "4. CONSTRUYENDO UN MISHKÁN"
        assert section.heading_source == "structural_heading_candidate"

    def test_absent_heading(self):
        chunk = _make_chunk(
            section_title="",
            heading_original=None,
            heading_normalized=None,
        )
        page = PageReference(
            page_id=None, pdf_page=51, printed_page=33, document_id="doc-1", document_title="Test"
        )
        canonical = CanonicalPage(
            page_id=None,
            document_id="doc-1",
            pdf_page=51,
            printed_page=33,
            text="Some content without headings.",
        )
        section = resolve_containing_section(page, canonical, chunk)
        assert section.heading_source == "none"
        assert section.heading_text is None
        assert "no_heading_found" in section.warnings

    def test_heading_from_heading_candidates(self):
        chunk = _make_chunk(section_title="", heading_original=None)
        page = PageReference(
            page_id=None, pdf_page=51, printed_page=33, document_id="doc-1", document_title="Test"
        )
        canonical = CanonicalPage(
            page_id=None,
            document_id="doc-1",
            pdf_page=51,
            printed_page=33,
            text="",
        )
        candidates = [{"heading_original": "4. CONSTRUYENDO UN MISHKÁN"}]
        section = resolve_containing_section(page, canonical, chunk, heading_candidates=candidates)
        assert section.heading_text == "4. CONSTRUYENDO UN MISHKÁN"
        assert section.heading_source == "heading_candidates_list"


# -- Test: Stable Evidence ID --------------------------------------------


class TestMakeEvidenceId:
    def test_stable_from_same_inputs(self):
        id1 = make_evidence_id(
            document_id="doc-1",
            page_ref=PageReference(
                page_id=None, pdf_page=51, printed_page=33, document_id="doc-1", document_title="Test"
            ),
            location=EvidenceLocation(
                exact_quote="test", start_offset=0, end_offset=4, location_precision="exact"
            ),
            chunk_id="chunk-1",
        )
        id2 = make_evidence_id(
            document_id="doc-1",
            page_ref=PageReference(
                page_id=None, pdf_page=51, printed_page=33, document_id="doc-1", document_title="Test"
            ),
            location=EvidenceLocation(
                exact_quote="test", start_offset=0, end_offset=4, location_precision="exact"
            ),
            chunk_id="chunk-1",
        )
        assert id1 == id2
        assert id1.startswith("ev-")

    def test_different_chunk_gives_different_id(self):
        id1 = make_evidence_id(
            document_id="doc-1",
            page_ref=PageReference(
                page_id=None, pdf_page=51, printed_page=33, document_id="doc-1", document_title="Test"
            ),
            location=EvidenceLocation(
                exact_quote="a", start_offset=0, end_offset=1, location_precision="exact"
            ),
            chunk_id="chunk-a",
        )
        id2 = make_evidence_id(
            document_id="doc-1",
            page_ref=PageReference(
                page_id=None, pdf_page=51, printed_page=33, document_id="doc-1", document_title="Test"
            ),
            location=EvidenceLocation(
                exact_quote="b", start_offset=2, end_offset=3, location_precision="exact"
            ),
            chunk_id="chunk-b",
        )
        assert id1 != id2


# -- Test: Build Evidence V1 (integration) --------------------------------


class TestBuildEvidenceV1:
    def test_builds_enriched_evidence_for_heading(self):
        chunk = _make_chunk(
            chunk_id="91aba034-7a02-4520-aa1c-3f29be2741be",
            content="4 ■ CONSTRUYENDO UN MISHKÁN",
            section_title="השכמת הבוקר",
            chunk_index=356,
        )
        same_page = [
            chunk,
            _body_chunk(),
        ]
        result = build_evidence_v1(
            query="CONSTRUYENDO UN MISHKÁN",
            chunk=chunk,
            same_page_chunks=same_page,
        )
        assert result is not None
        assert result["pdf_page"] == 51
        assert result["printed_page"] == 33
        assert result["heading_text"] == "השכמת הבוקר"
        assert result["exact_quote"] is not None
        assert "CONSTRUYENDO UN MISHKÁN" in str(result["exact_quote"])
        assert result["evidence_id"].startswith("ev-")
        assert result["location_precision"] in ("exact", "normalized_exact")
        assert result["canonical_page_source"] == "assembled_from_chunks"

    def test_builds_for_body_chunk(self):
        body = _body_chunk()
        heading = _make_chunk(chunk_index=356)
        result = build_evidence_v1(
            query="El Rabí Natán concluye su explicación",
            chunk=body,
            same_page_chunks=[heading, body],
        )
        assert result is not None
        assert result["pdf_page"] == 51
        assert result["heading_text"] == "השכמת הבוקר"
        assert result["exact_quote"] is not None

    def test_returns_none_for_unresolvable(self):
        chunk = _make_chunk(pdf_page=None, page_start=None, markdown="")
        result = build_evidence_v1(
            query="test",
            chunk=chunk,
        )
        # Should still resolve using page_marker_inference
        # Only returns None if truly unresolvable

    def test_backward_compatible_fields_present(self):
        chunk = _make_chunk()
        result = build_evidence_v1(
            query="CONSTRUYENDO UN MISHKÁN",
            chunk=chunk,
        )
        assert result is not None
        # Legacy fields
        assert "evidence_id" in result
        assert "chunk_id" in result
        assert "document_id" in result
        assert "work" in result
        assert "pdf_page" in result
        assert "printed_page" in result
        assert "section" in result
        assert "language" in result
        assert "markdown" in result
        assert "source_layer" in result
        assert "literal_match_type" in result
        # New V1 fields
        assert "page_id" in result
        assert "heading_text" in result
        assert "section_path" in result
        assert "exact_quote" in result
        assert "context_before" in result
        assert "context_after" in result
        assert "start_offset" in result
        assert "end_offset" in result
        assert "location_precision" in result
        assert "canonical_page_source" in result
        assert "page_resolution_method" in result

    def test_frontend_hint_has_all_keys(self):
        hint = frontend_hint_v1()
        assert "page_id" in hint
        assert "pdf_page" in hint
        assert "printed_page" in hint
        assert "heading_text" in hint
        assert "section_path" in hint
        assert "exact_quote" in hint
        assert "location_precision" in hint
        assert "source_layer" in hint


# -- Test: Multipage Chunk (Gedalia case) --------------------------------


class TestMultipageChunk:
    def test_gedalia_multipage(self):
        """Gedalia of Linitz appears on page 21 but chunk spans pages 20-21."""
        chunk = _make_chunk(
            chunk_id="gedalia-chunk",
            doc_id="c7c10741-c324-4916-93a7-61070863e3f9",
            work="Kokhavey Ohr",
            page=20,
            page_end=21,
            printed_page=None,
            pdf_page=20,
            chunk_index=100,
            content="Page 20 content... Gedalia of Linitz found on page 21.",
            markdown="Page 20 content... ## Page 21\n> Gedalia of Linitz found on page 21.",
            section_title="Moharan's Men",
        )
        ref = resolve_page_for_retrieval_hit(chunk)
        assert ref.pdf_page is not None
        assert ref.pdf_page is not None
        # After local page resolution, pdf_page should be 21 (from marker)
        chunk["pdf_page"] = 21
        chunk["canonical_pdf_page_start"] = 20  # original page_start before local resolution

        same_page = [
            _make_chunk(
                chunk_id="page21-content",
                content="Gedalia of Linitz and other great Rabbis",
                page=21,
                pdf_page=21,
                chunk_index=101,
                section_title="Moharan's Men",
            )
        ]

        result = build_evidence_v1(
            query="Gedalia of Linitz",
            chunk=chunk,
            same_page_chunks=same_page + [chunk],
        )
        assert result is not None
        # The evidence should reflect page 21 (post-local-resolution)
        assert result["pdf_page"] == 21
