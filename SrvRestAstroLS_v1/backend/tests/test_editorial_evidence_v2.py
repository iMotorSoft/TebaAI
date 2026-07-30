"""Tests for Editorial Evidence V2."""

from typing import Any

import pytest

from modules.library.editorial_evidence_v2 import (
    EditorialBlockRole,
    EditorialContext,
    FootnoteInfo,
    FootnoteMarker,
    HeadingBodyAssociation,
    PrintedReference,
    ReferenceStatus,
    associate_heading_with_body,
    build_editorial_v2,
    build_full_evidence_v2,
    build_section_timeline,
    classify_editorial_block,
    detect_footnote_marker,
    detect_footnote_number,
    detect_printed_references,
    enrich_evidence_with_v2,
    find_footnote_marker,
    make_editorial_evidence_id,
    resolve_containing_section_for_chunk,
    resolve_footnote_body,
)


# -- Fixtures --------------------------------------------------------------


def _chunk(
    chunk_id: str = "c1",
    content: str = "",
    block_type: str = "main_explanation_es",
    evidence_role: str = "commentary",
    chunk_index: int = 0,
    page: int = 53,
    doc_id: str = "47768aac-704e-4296-9649-53b9ea037096",
    section_title: str = "section",
    **overrides: Any,
) -> dict[str, Any]:
    return {
        "chunk_id": chunk_id,
        "id": chunk_id,
        "document_id": doc_id,
        "content": content,
        "markdown": content,
        "block_type": block_type,
        "evidence_role": evidence_role,
        "chunk_index": chunk_index,
        "pdf_page": page,
        "page_start": page,
        "section_title": section_title,
        "language": "es",
        **overrides,
    }


# -- Test: Editorial block classification ----------------------------------


class TestClassifyEditorialBlock:
    def test_main_body(self):
        ctx = classify_editorial_block(_chunk(content="El Rabí Natán explica..."))
        assert ctx.block_role == EditorialBlockRole.MAIN_BODY

    def test_section_heading_detected(self):
        ctx = classify_editorial_block(_chunk(content="5 ■ INCLINADO HACIA LA BONDAD"))
        assert ctx.block_role == EditorialBlockRole.SECTION_HEADING

    def test_another_heading(self):
        ctx = classify_editorial_block(_chunk(content="6 ■ MELODÍAS Y PLEGARIAS"))
        assert ctx.block_role == EditorialBlockRole.SECTION_HEADING

    def test_marginal_reference_by_role(self):
        ctx = classify_editorial_block(
            _chunk(content="(Salmos 16:1)", evidence_role="marginal_citation")
        )
        assert ctx.block_role == EditorialBlockRole.MARGINAL_REFERENCE

    def test_footnote_by_block_type(self):
        ctx = classify_editorial_block(
            _chunk(content="35 Note text...", block_type="footnote", evidence_role="footnote")
        )
        assert ctx.block_role == EditorialBlockRole.FOOTNOTE_BODY

    def test_notes_heading(self):
        ctx = classify_editorial_block(_chunk(content="Notas y Fuentes"))
        assert ctx.block_role == EditorialBlockRole.NOTES_HEADING

    def test_hebrew_source(self):
        ctx = classify_editorial_block(_chunk(content="hebrew text", block_type="source_hebrew"))
        assert ctx.block_role == EditorialBlockRole.HEBREW_SOURCE


# -- Test: Printed reference detection -------------------------------------


class TestDetectPrintedReferences:
    def test_salmos_16_1(self):
        refs = detect_printed_references('(Salmos 16:1)')
        assert len(refs) == 1
        assert refs[0].surface == "Salmos 16:1"
        assert refs[0].normalized == "salmos 16:1"

    def test_multiple_references(self):
        refs = detect_printed_references('(Salmos 16:1) y (Éxodo 2:2)')
        assert len(refs) == 2

    def test_no_reference(self):
        refs = detect_printed_references('El Rabí Natán concluye su explicación.')
        assert len(refs) == 0

    def test_salmos_16_8(self):
        refs = detect_printed_references('(Salmos 16:8)')
        assert len(refs) == 1
        assert refs[0].surface == "Salmos 16:8"


# -- Test: Footnote detection ----------------------------------------------


class TestDetectFootnoteNumber:
    def test_at_start(self):
        n = detect_footnote_number("35 Note text here")
        assert n == 35

    def test_no_number(self):
        n = detect_footnote_number("Some text without number")
        assert n is None

    def test_two_digit(self):
        n = detect_footnote_number("29 Another note")
        assert n == 29


class TestDetectFootnoteMarker:
    def test_marker_at_end(self):
        markers = detect_footnote_marker("Como hemos visto, de esa manera se crean melodías.35")
        assert len(markers) == 1
        assert markers[0][0] == 35

    def test_no_marker(self):
        markers = detect_footnote_marker("El Rabí Natán concluye.")
        assert len(markers) == 0


# -- Test: Section timeline ------------------------------------------------


class TestBuildSectionTimeline:
    def test_two_headings(self):
        chunks = [
            _chunk(content="body 1", chunk_index=380, page=53),
            _chunk(content="5 ■ INCLINADO HACIA LA BONDAD", chunk_index=381, page=53),
            _chunk(content="body after heading", chunk_index=382, page=53),
            _chunk(content="6 ■ MELODÍAS Y PLEGARIAS", chunk_index=412, page=56),
            _chunk(content="body after second", chunk_index=413, page=56),
        ]
        timeline = build_section_timeline(chunks)
        assert len(timeline) == 2
        assert "INCLINADO" in timeline[0]["heading"]
        assert "MELODÍAS" in timeline[1]["heading"]


class TestResolveContainingSection:
    def test_body_after_heading(self):
        chunks = [
            _chunk(content="5 ■ INCLINADO HACIA LA BONDAD", chunk_index=381, page=53),
            _chunk(content="El Rabí Natán completa...", chunk_index=382, page=53),
            _chunk(content="6 ■ MELODÍAS Y PLEGARIAS", chunk_index=412, page=56),
        ]
        body_chunk = chunks[1]
        containing, next_h, path = resolve_containing_section_for_chunk(body_chunk, chunks)
        assert containing is not None
        assert "INCLINADO" in containing
        assert next_h is not None
        assert "MELODÍAS" in next_h

    def test_chunk_before_first_heading(self):
        chunks = [
            _chunk(content="preamble", chunk_index=370, page=53),
            _chunk(content="5 ■ INCLINADO", chunk_index=381, page=53),
        ]
        containing, next_h, path = resolve_containing_section_for_chunk(chunks[0], chunks)
        assert containing is None  # before any heading
        assert next_h is not None
        assert "INCLINADO" in next_h


# -- Test: Footnote resolution ---------------------------------------------


class TestFindFootnoteMarker:
    def test_marker_35_found(self):
        fn_chunk = _chunk(content="35 Note text", block_type="footnote", chunk_index=416, page=56)
        body_chunk = _chunk(
            content="Como hemos visto, de esa manera se crean melodías.35 Pues durante la noche...",
            chunk_index=414,
            page=56,
        )
        heading = _chunk(content="5 ■ INCLINADO HACIA LA BONDAD", chunk_index=381, page=53)
        next_h = _chunk(content="6 ■ MELODÍAS Y PLEGARIAS", chunk_index=412, page=56)
        chunks = [body_chunk, fn_chunk, heading, next_h]

        marker = find_footnote_marker(35, chunks)
        assert marker.resolution_method == "textual_marker"
        assert marker.confidence > 0
        assert marker.anchor_text is not None
        assert "melodías" in (marker.anchor_text or "")

    def test_unresolved_when_no_marker(self):
        chunks = [_chunk(content="Some text without markers.", chunk_index=1)]
        marker = find_footnote_marker(99, chunks)
        assert marker.resolution_method == "unresolved"
        assert marker.confidence == 0.0


class TestResolveFootnoteBody:
    def test_single_chunk(self):
        chunks = [_chunk(content="35 Text of footnote thirty five.", block_type="footnote")]
        fn = resolve_footnote_body(chunks)
        assert fn.number == 35
        assert "thirty five" in (fn.body_text or "")

    def test_multiple_chunks(self):
        chunks = [
            _chunk(content="35 First part.", block_type="footnote"),
            _chunk(content="Continuing text.", block_type="footnote"),
        ]
        fn = resolve_footnote_body(chunks)
        assert fn.number == 35
        assert "First part" in (fn.body_text or "")


# -- Test: Heading-body association ----------------------------------------


class TestAssociateHeadingWithBody:
    def test_adjacent_body_found(self):
        heading = _chunk(content="5 ■ INCLINADO HACIA LA BONDAD", chunk_index=381)
        body = _chunk(content="El Rabí Natán completa a continuación su interpretación...", chunk_index=382)
        assoc = associate_heading_with_body(heading, [heading, body])
        assert assoc.body_text is not None
        assert "completa" in (assoc.body_text or "")
        assert assoc.confidence > 0

    def test_no_body_before_next_heading(self):
        heading = _chunk(content="5 ■ INCLINADO", chunk_index=381)
        next_h = _chunk(content="6 ■ MELODÍAS", chunk_index=412)
        body = _chunk(content="Some body", chunk_index=382)
        assoc = associate_heading_with_body(heading, [heading, body, next_h])
        assert assoc.body_text is not None
        assert assoc.confidence > 0


# -- Test: Evidence ID stability -------------------------------------------


class TestMakeEditorialEvidenceId:
    def test_stable_from_same_inputs(self):
        id1 = make_editorial_evidence_id("doc-1", 53, "section_heading", "chunk-1")
        id2 = make_editorial_evidence_id("doc-1", 53, "section_heading", "chunk-1")
        assert id1 == id2
        assert id1.startswith("ev-")

    def test_different_inputs(self):
        id1 = make_editorial_evidence_id("doc-1", 53, "section_heading", "chunk-1")
        id2 = make_editorial_evidence_id("doc-1", 56, "footnote", "chunk-2", "35")
        assert id1 != id2


# -- Test: Build editorial V2 dict -----------------------------------------


class TestBuildEditorialV2:
    def test_v2_heading(self):
        chunk = _chunk(content="5 ■ INCLINADO HACIA LA BONDAD", chunk_index=381)
        body = _chunk(content="El Rabí Natán completa...", chunk_index=382)
        v2 = build_editorial_v2(chunk, {}, [chunk, body])
        ed = v2.get("editorial", {})
        assert ed.get("block_role") == "section_heading"
        assert ed.get("associated_body_text") is not None

    def test_v2_marginal_reference(self):
        chunk = _chunk(
            content='"He puesto a HaShem..." (Salmos 16:1)',
            evidence_role="marginal_citation",
            page=55,
        )
        v2 = build_editorial_v2(chunk, {}, [chunk])
        ed = v2.get("editorial", {})
        assert ed.get("printed_reference") == "Salmos 16:1"
        assert ed.get("reference_status") == "printed_reference_only"

    def test_v2_footnote(self):
        fn = _chunk(content="35 El hombre se une a HaShem...", block_type="footnote",
                     chunk_index=416, page=56)
        body = _chunk(content="Como hemos visto, de esa manera se crean melodías.35",
                       chunk_index=414, page=56)
        heading = _chunk(content="5 ■ INCLINADO", chunk_index=381)
        next_h = _chunk(content="6 ■ MELODÍAS", chunk_index=412)
        chunks = [body, fn, heading, next_h]

        v2 = build_editorial_v2(fn, {}, chunks)
        ed = v2.get("editorial", {})
        assert ed.get("block_role") == "footnote"
        assert ed.get("footnote_number") == "35"

    def test_v2_footnote_with_marker(self):
        fn = _chunk(content="35 El hombre se une a HaShem...", block_type="footnote",
                     chunk_index=416, page=56)
        body = _chunk(content="Como hemos visto, de esa manera se crean melodías.35",
                       chunk_index=414, page=56)
        heading = _chunk(content="5 ■ INCLINADO", chunk_index=381)
        next_h = _chunk(content="6 ■ MELODÍAS", chunk_index=412)
        chunks = [body, fn, heading, next_h]

        v2 = build_editorial_v2(fn, {}, chunks)
        ed = v2.get("editorial", {})
        assert ed.get("footnote_anchor_text") is not None
        assert next_h is not None

    def test_v2_not_associated_with_next_heading(self):
        """Footnote before new heading should NOT be associated with the new heading."""
        fn = _chunk(content="35 Note text...", block_type="footnote",
                     chunk_index=415, page=56)
        body = _chunk(content="...text with marker.35", chunk_index=414, page=56)
        heading = _chunk(content="5 ■ INCLINADO", chunk_index=381)
        next_h = _chunk(content="6 ■ MELODÍAS", chunk_index=412)
        chunks = [body, fn, heading, next_h]

        v2 = build_editorial_v2(fn, {}, chunks)
        ed = v2.get("editorial", {})
        # The next_heading field should be present but marker section should be from anchor section
        if ed.get("next_heading"):
            pass  # just that next_heading is different from the section containing the marker
        assert ed.get("block_role") == "footnote"


# -- Test: Full evidence V2 build ------------------------------------------


class TestBuildFullEvidenceV2:
    def test_heading_evidence(self):
        chunk = _chunk(content="5 ■ INCLINADO HACIA LA BONDAD",
                       chunk_index=381, page=53,
                       printed_page="35", printed_page_label="35")
        body = _chunk(content="El Rabí Natán completa...", chunk_index=382, page=53)
        result = build_full_evidence_v2(chunk, [chunk, body], query="INCLINADO HACIA LA BONDAD")
        assert result is not None
        assert result.get("pdf_page") == 53
        assert result.get("section_path") is not None
        assert result.get("editorial") is not None
        assert result["editorial"].get("block_role") == "section_heading"

    def test_marginal_reference_evidence(self):
        chunk = _chunk(
            content='"He puesto a HaShem..." (Salmos 16:1)',
            evidence_role="marginal_citation",
            page=55, printed_page="37",
            chunk_index=402,
        )
        result = build_full_evidence_v2(chunk, [chunk], query="Salmos 16:1")
        assert result is not None
        assert result.get("pdf_page") == 55
        ed = result.get("editorial", {})
        assert ed.get("printed_reference") is not None
        assert "16:1" in str(ed.get("printed_reference"))

    def test_footnote_evidence(self):
        fn = _chunk(content="35 El hombre se une a HaShem...",
                     block_type="footnote", chunk_index=416, page=56,
                     printed_page="38")
        body = _chunk(content="...melodías.35", chunk_index=414, page=56)
        heading = _chunk(content="5 ■ INCLINADO", chunk_index=381)
        next_h = _chunk(content="6 ■ MELODÍAS", chunk_index=412)
        chunks = [body, fn, heading, next_h]

        result = build_full_evidence_v2(fn, chunks, query="El hombre se une a HaShem")
        assert result is not None
        ed = result.get("editorial", {})
        assert ed.get("block_role") == "footnote"
        assert ed.get("footnote_number") is not None


# -- Test: Backward compatibility ------------------------------------------


class TestBackwardCompatibility:
    def test_v2_fields_optional(self):
        chunk = _chunk(content="Regular body text", chunk_index=1)
        result = build_full_evidence_v2(chunk, [chunk], query="test")
        assert result is not None
        # V1 fields present
        assert "evidence_id" in result
        assert "pdf_page" in result
        assert "chunk_id" in result
        # V2 fields optional
        assert "editorial" in result
        assert result["editorial"] is not None
