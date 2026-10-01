from __future__ import annotations

import json
from pathlib import Path
import re

import pytest

from modules.library.pdf_hebrew_fidelity import repair_markdown

FIXTURES = Path(__file__).parent / "fixtures" / "hebrew_pdf_fidelity"


@pytest.mark.parametrize("case", ["a", "b"])
def test_real_pdf_pages_preserve_all_non_whitespace_characters(case):
    fixture = json.loads((FIXTURES / f"case_{case}.json").read_text())
    before = fixture["markdown_before"]
    after, changes = repair_markdown(before, fixture["raw"])
    assert changes
    assert after == fixture["markdown_after"]
    # Only source-backed whitespace and explicit cell delimiters may change.
    assert re.sub(r"[\s;]", "", before) == re.sub(r"[\s;]", "", after)
    assert repair_markdown(after, fixture["raw"])[0] == after
    if case == "a":
        assert "יְהִי רָצוֹן מִלְּפָנֶיָך" in after
        assert "יהי רצון שאומרים קודם אמירת תהלים בימות החול:" in after
        assert sum(c["synthetic_spaces_removed"] for c in changes) == 294
    else:
        assert "6 = ו ; 1 = א" in after
        assert "400 = ת ; 80 = פ,ף ; 30 = ל ; 7 = ז ; 2 = ב" in after
        assert "900 = ץ ; 800 = ף ; 700 = ן ; 600 = ם ; 500 = ך" in after
        assert "ו1" not in after and "ת80" not in after


def raw_line(text, *, synthetic=False, gutter=0):
    chars = []
    for i, char in enumerate(text):
        x = i * 10 + (gutter if i >= 5 else 0)
        chars.append({"c": char, "bbox": [x, 0, x + 10, 10], "synthetic": synthetic and char == " "})
    return {"blocks": [{"type": 0, "lines": [{"dir": [1, 0], "spans": [{"size": 10, "chars": chars}]}]}]}


@pytest.mark.parametrize("text", [
    "ברסלב", "שלום עולם", "ב ר ס ל ב", "ו1", "1ו", "ת80",
    "שלום, עולם!", "Texto español: שלום עולם, 80 referencias.",
    "English text, 1.25 and punctuation!", "1 = ו2 = ב",
    "יְהִ י רָ צוֹן",  # Source-authored spaces cannot be discarded.
])
def test_unproven_or_legitimate_boundaries_are_unchanged(text):
    assert repair_markdown(text, raw_line(text)) == (text, [])


def test_large_gutter_in_prose_is_not_a_numeric_table():
    text = "שלום1 referencia"
    assert repair_markdown(text, raw_line(text, gutter=50)) == (text, [])


def test_synthetic_space_without_touching_hebrew_bases_is_preserved():
    text = "יְהִ י"
    assert repair_markdown(text, raw_line(text, synthetic=True, gutter=50)) == (text, [])


def test_markdown_without_source_match_is_not_modified():
    fixture = json.loads((FIXTURES / "case_a.json").read_text())
    assert repair_markdown("Una frase diferente: שלום עולם.", fixture["raw"])[0] == "Una frase diferente: שלום עולם."


def test_duplicate_textual_anchors_are_left_unchanged():
    fixture = json.loads((FIXTURES / "case_a.json").read_text())
    before = fixture["markdown_before"] + "\n\n" + fixture["markdown_before"]
    assert repair_markdown(before, fixture["raw"]) == (before, [])


def test_partial_gutter_evidence_does_not_rewrite_other_cell_boundaries():
    text = "1 = א2 = ב3 = ג"
    raw = raw_line(text)
    chars = raw["blocks"][0]["lines"][0]["spans"][0]["chars"]
    for char in chars[10:]:
        char["bbox"][0] += 40
        char["bbox"][2] += 40
    assert repair_markdown(text, raw) == (text, [])


@pytest.mark.parametrize("case", ["a", "b"])
def test_all_canonical_pdf_entrypoints_use_real_source_geometry(case, tmp_path):
    import pymupdf
    from modules.library.extractors import extract_text, extract_pdf_with_page_markers
    from modules.library.page_first_pipeline import extract_pdf_page_first

    fixture = json.loads((FIXTURES / f"case_{case}.json").read_text())
    source = Path("/media/issajar/DEVELOP/Download/Tora/Breslov") / fixture["source_filename"]
    if not source.is_file():
        pytest.skip("Original local PDF unavailable; offline geometry fixtures are still tested")
    path = tmp_path / "original-page.pdf"
    with pymupdf.open(source) as document, pymupdf.open() as single:
        single.insert_pdf(document, from_page=fixture["pdf_page"] - 1, to_page=fixture["pdf_page"] - 1)
        single.save(path)
    expected = fixture["markdown_after"].strip()
    content, fmt, method, metadata = extract_text(str(path))
    assert content.strip() == expected
    assert fmt.value == "markdown" and method.value == "pymupdf4llm"
    assert metadata["hebrew_boundary_repairs"]
    marked, _, _ = extract_pdf_with_page_markers(str(path))
    assert marked.removeprefix("## Page 1\n\n").strip() == expected
    extracted = extract_pdf_page_first(path)
    assert extracted.pages[0].original_markdown == expected


@pytest.mark.parametrize("layout", [True, False])
def test_header_analysis_only_runs_for_converter_that_uses_it(monkeypatch, layout):
    import pymupdf4llm
    from modules.library.pdf_hebrew_fidelity import document_header_info
    calls = []
    marker = object()
    monkeypatch.setattr(pymupdf4llm, "_use_layout", layout)
    monkeypatch.setattr(pymupdf4llm, "IdentifyHeaders", lambda doc: calls.append(doc) or marker, raising=False)
    document = object()
    assert document_header_info(document) is (None if layout else marker)
    assert calls == ([] if layout else [document])


def test_spanish_english_pdf_entrypoints_preserve_converter_text(tmp_path):
    import pymupdf
    import pymupdf4llm
    from modules.library.extractors import extract_text, extract_pdf_with_page_markers
    from modules.library.page_first_pipeline import extract_pdf_page_first

    path = tmp_path / "non-hebrew-regression.pdf"
    with pymupdf.open() as document:
        for text in ["Texto español (ñ), números 1, 80, 400: ¡sí!", "English punctuation: 1.25, (80), 400; references!"]:
            document.new_page().insert_text((72, 72), text)
        document.save(path)
    baseline = pymupdf4llm.to_markdown(str(path))
    fold = lambda text: re.sub(r"\s+", " ", text).strip()
    content, _, _, metadata = extract_text(str(path))
    assert fold(content) == fold(baseline)
    assert metadata["hebrew_boundary_repairs"] == []
    marked, _, _ = extract_pdf_with_page_markers(str(path))
    assert fold(re.sub(r"## Page [12]\n", "", marked)) == fold(baseline)
    extracted = extract_pdf_page_first(path)
    assert fold("\n\n".join(p.original_markdown for p in extracted.pages)) == fold(baseline)
    for expected in ["español", "números 1, 80, 400", "¡sí!", "1.25, (80), 400; references!"]:
        assert expected in baseline
