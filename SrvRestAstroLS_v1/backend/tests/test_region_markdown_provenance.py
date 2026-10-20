"""Small real-source IR regressions plus generic forward-lineage contracts."""
from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path
import random
import re

from markdown_it import MarkdownIt
import pytest
from pymupdf4llm.helpers.document_layout import LayoutBox, PageLayout, ParsedDocument

from modules.library.region_markdown_provenance import (
    UnresolvedLayout, classify_owned_unit, map_layout_page,
)
from modules.library.region_quality import QualityPage

FIXTURES = Path(__file__).parent / "fixtures"
GOLD = json.loads((FIXTURES / "region_markdown_editorial_goldens_v1.json").read_text())
IR = json.loads((FIXTURES / "region_markdown_provenance_v1.json").read_text())
SHA = IR["source_sha256"]


def real_layout(number):
    data = deepcopy(next(p for p in IR["pages"] if p["page_number"] == number))
    data["boxes"] = [LayoutBox(**b) for b in data["boxes"]]
    page = PageLayout(**data)
    return ParsedDocument(pages=[page]), page


def mapped(number):
    parsed, page = real_layout(number)
    return map_layout_page(parsed, page, SHA, note_direction="ltr")


def text(result, unit):
    return result.markdown[unit.markdown_start:unit.markdown_end]


def semantic(markdown):
    parser = MarkdownIt().enable("strikethrough")
    return "".join(child.content for token in parser.parse(markdown)
                   for child in (token.children or []) if child.type in {"text", "code_inline"})


def compact(value):
    # Only whitespace equivalence, never reverse/correct letters/digits/punctuation.
    return re.sub(r"\s+", "", value)


def assert_notes(result, number):
    notes = [u for u in result.units if u.note_number is not None]
    expected = GOLD[str(number)]
    assert [u.note_number for u in notes] == [g["number"] for g in expected]
    for unit, golden in zip(notes, expected, strict=True):
        assert unit.parts[0].source_text == golden["start"]
        assert unit.parts[-1].source_text == golden["end"]
        assert list(dict.fromkeys(p.column for p in unit.parts)) == golden["columns"]
        assert [list(k) for p in unit.parts for k in p.source_line_ids] == golden["source_lines"]
        canonical = result.canonical_text[unit.canonical_start:unit.canonical_end]
        assert compact(semantic(text(result, unit))) == compact(canonical)
        assert result.owners(unit.markdown_start, unit.markdown_end) == (unit,)
        assert result.spans_for_region(unit.region_id) == ((unit.markdown_start, unit.markdown_end),)
        assert unit.end_reason == ("PAGE_BOUNDARY" if unit == notes[-1] else "NEXT_NOTE_IN_COLUMN_FLOW")
        assert len({(p.source_line_ids, p.bbox) for p in unit.parts}) == len(unit.parts)
    # Each input note line must appear once, including cross-column continuations.
    owned = [(p.source_line_ids, p.bbox) for u in notes for p in u.parts]
    assert len(owned) == len(set(owned))


@pytest.mark.parametrize("number", [56, 167])
def test_real_complete_page_local_note_boundaries(number):
    assert_notes(mapped(number), number)


def test_current_serializer_reproduces_wrong_order_then_adapter_corrects_it():
    parsed, _ = real_layout(167)
    broken = parsed.to_markdown()
    # Real labels put right continuation and 66 ahead of left-column 64/65.
    assert broken.index("66 Comentando") < broken.index("64 Ver")
    correct = mapped(167).markdown
    assert correct.index("64 Ver") < correct.index("65 Estudia") < correct.index("se refrena") < correct.index("66 Comentando")


def test_167_body_hebrew_and_notes_have_independent_exact_owners():
    result = mapped(167)
    body = next(u for u in result.units if u.parts[0].source_text.startswith("Por lo tanto"))
    hebrew = next(u for u in result.units if "\ufffd" in u.parts[0].source_text and u.role == "text")
    notes = [u for u in result.units if u.note_number]
    assert "zapato derecho primero" in text(result, body)
    assert "\ufffd" not in text(result, body)
    assert body.region_id != hebrew.region_id
    assert body.region_id not in {n.region_id for n in notes}
    assert not set(p.source_line_ids for p in body.parts) & set(p.source_line_ids for n in notes for p in n.parts)
    assert "\ufffd" not in "".join(s for _, s in result.exclude({hebrew.region_id, next(u.region_id for u in result.units if u.role == 'section-header')}))


def test_55_exclusion_preserves_both_good_neighbors_and_entire_sequence():
    result = mapped(55)
    bad = next(u for u in result.units if u.parts[0].source_text == GOLD["55"]["bad_region_text"])
    index = result.units.index(bad)
    previous, following = result.units[index - 1:index + 2:2]
    assert previous.parts[-1].source_text == GOLD["55"]["previous_good_tail"]
    assert following.parts[0].source_text == GOLD["55"]["next_good_start"]
    expected = tuple((u.region_id, text(result, u)) for u in result.units if u != bad)
    actual = result.exclude({bad.region_id})
    assert actual == expected  # full strings AND sequence, not counts/multiset
    assert text(result, previous) == dict(actual)[previous.region_id]
    assert text(result, following) == dict(actual)[following.region_id]
    assert text(result, bad) not in "".join(s for _, s in actual)
    with pytest.raises(ValueError, match="Untracked"):
        result.exclude({"unknown"})


@pytest.mark.parametrize("number", [55, 56, 167])
def test_idempotence_three_runs_and_immutable_input(number):
    parsed, page = real_layout(number)
    before = asdict(page)
    runs = [map_layout_page(parsed, page, SHA, note_direction="ltr") for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]
    assert asdict(page) == before
    assert "".join(text(runs[0], u) for u in runs[0].units) == runs[0].markdown
    assert runs[0].units[0].markdown_start == 0
    assert runs[0].units[-1].markdown_end == len(runs[0].markdown)


@pytest.mark.parametrize("number", [55, 56, 167])
def test_note_geometry_permutation_does_not_change_ownership(number):
    parsed, page = real_layout(number)
    baseline = map_layout_page(parsed, page, SHA, note_direction="ltr")
    first_note_y = min(b.y0 for b in page.boxes if b.boxclass == "footnote")
    stable = [b for b in page.boxes if b.y0 < first_note_y - 1]
    notes = [b for b in page.boxes if b.y0 >= first_note_y - 1]
    random.Random(42).shuffle(notes)
    for b in notes:
        random.Random(42).shuffle(b.textlines)
    page.boxes = stable + notes
    assert map_layout_page(parsed, page, SHA, note_direction="ltr") == baseline


def synthetic_line(block, line, x, y, content, *, flags=0):
    return {"bbox": [x, y, x + 80, y + 7], "spans": [
        {"text": content, "block": block, "line": line, "flags": flags,
         "char_flags": 0, "font": "Synthetic", "size": 7,
         "origin": [x, y + 7]}]}


def synthetic(*boxes):
    page = PageLayout(1, 300, 500, list(boxes))
    return ParsedDocument(pages=[page]), page


def box(role, *lines):
    return LayoutBox(min(l['bbox'][0] for l in lines), min(l['bbox'][1] for l in lines),
                     max(l['bbox'][2] for l in lines), max(l['bbox'][3] for l in lines),
                     role, textlines=list(lines))


def test_duplicate_text_is_owned_by_identity_not_first_substring():
    parsed, page = synthetic(box("text", synthetic_line(0, 0, 10, 10, "Repeated")),
                             box("text", synthetic_line(1, 0, 10, 30, "Repeated")))
    result = map_layout_page(parsed, page, SHA, note_direction="ltr")
    a, b = result.units
    assert a.region_id != b.region_id
    assert result.owners(b.markdown_start, b.markdown_end) == (b,)
    assert result.exclude({a.region_id}) == ((b.region_id, text(result, b)),)


@pytest.mark.parametrize("flags", [0, 2, 16, 18])
def test_markdown_decoration_emphasis_quote_brackets_and_multiline(flags):
    parsed, page = synthetic(box("footnote", synthetic_line(0, 0, 10, 200, "7 Birur [35]", flags=flags),
                                synthetic_line(0, 1, 10, 210, "continuation", flags=flags)),
                             box("footnote", synthetic_line(0, 2, 10, 220, "8 Next note")))
    result = map_layout_page(parsed, page, SHA, note_direction="ltr")
    first, second = result.units
    assert first.note_number == 7 and second.note_number == 8
    assert "[35]" in text(result, first) and "> " in text(result, first)
    assert len(first.parts) == 2
    assert compact(semantic(text(result, first))) == compact(result.canonical_text[:first.canonical_end])
    assert "Next note" not in text(result, first)
    assert result.owners(first.markdown_end - 1, second.markdown_start + 1) == (first, second)


def test_rtl_column_order_is_explicit_and_not_reversal():
    parsed, page = synthetic(box("footnote", synthetic_line(0, 0, 10, 200, "2 left")),
                             box("footnote", synthetic_line(1, 0, 150, 200, "1 right")))
    result = map_layout_page(parsed, page, SHA, note_direction="rtl")
    assert [u.note_number for u in result.units] == [1, 2]
    assert "right" in text(result, result.units[0])


@pytest.mark.parametrize("problem", ["no_owner", "duplicate_identity", "overlap", "unsupported", "direction", "geometry", "unrecognized_number"])
def test_unsupported_layout_is_explicit_unresolved_not_silent_drop(problem):
    lines = [synthetic_line(0, 0, 10, 200, "7 Start"), synthetic_line(0, 1, 10, 210, "continuation")]
    direction = "ltr"
    role = "footnote"
    if problem == "no_owner":
        lines[0]["spans"][0]["text"] = "Continuation"
    if problem == "duplicate_identity":
        lines[1] = deepcopy(lines[0])
    if problem == "overlap":
        lines[1]["bbox"][1] = 201
    if problem == "unsupported":
        role = "table"
    if problem == "direction":
        direction = "unknown"
    if problem == "geometry":
        lines[0]["bbox"][2] = float("nan")
    if problem == "unrecognized_number":
        lines[1]["spans"][0]["text"] = "100 Unsupported start"
    parsed, page = synthetic(box(role, *lines))
    with pytest.raises(UnresolvedLayout):
        map_layout_page(parsed, page, SHA, note_direction=direction)


def test_existing_quality_contract_consumes_only_exact_owned_units():
    result = mapped(167)
    classified = []
    for u in result.units:
        damaged = "\ufffd" in text(result, u)
        classified.append(classify_owned_unit(
            result, u.region_id, evidence_refs=("manual-golden-v1",),
            visual_good=True, text_verified=not damaged,
            order_verified=True, structure_verified=True))
    quality = QualityPage(tuple(classified))
    assert quality.quality.value == "PARTIAL"
    assert "\ufffd" not in quality.canonical_markdown
    assert [r.candidate.region_id for r in quality.regions if not r.accepted_markdown] == [
        u.region_id for u in result.units if "\ufffd" in text(result, u)]
    assert all(str(n) in quality.canonical_markdown for n in range(60, 67))


def test_unapproved_serializer_hyphenation_cannot_be_certified_safe():
    parsed, page = synthetic(box("text", synthetic_line(0, 0, 10, 10, "example-"),
                                 synthetic_line(0, 1, 10, 20, "word")))
    result = map_layout_page(parsed, page, SHA, note_direction="ltr")
    unit = result.units[0]
    assert unit.transformation_status == "UNRESOLVED"
    quality = classify_owned_unit(result, unit.region_id, evidence_refs=("fixture",),
                                  visual_good=True, text_verified=True,
                                  order_verified=True, structure_verified=True)
    assert not quality.accepted_markdown
    with pytest.raises(ValueError, match="tracked"):
        classify_owned_unit(result, "unknown", evidence_refs=(), visual_good=True,
                            text_verified=True, order_verified=True, structure_verified=True)


@pytest.mark.parametrize("number", [57, 168])
def test_real_cross_page_continuation_reaches_true_editorial_end(number):
    golden = GOLD["continuations"][str(number)]
    prior = mapped(golden["from_page"])
    parsed, page = real_layout(number)
    runs = [map_layout_page(parsed, page, SHA, note_direction="ltr",
                            note_zone_bbox=golden["note_zone_bbox"], continued_from=prior)
            for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]
    result = runs[0]
    notes = [u for u in result.units if u.note_number is not None]
    unit = notes[0]
    assert unit.note_number == golden["number"]
    assert unit.continuation_of == prior.units[-1].region_id
    assert unit.parts[0].source_text == golden["start"]
    assert unit.parts[-1].source_text == golden["end"]
    assert [list(k) for p in unit.parts for k in p.source_line_ids] == golden["source_lines"]
    assert unit.end_reason == "NEXT_NOTE_IN_COLUMN_FLOW"
    assert notes[1].note_number == golden["next_note"]
    assert result.owners(unit.markdown_start, unit.markdown_end) == (unit,)
    assert compact(semantic(text(result, unit))) == compact(
        result.canonical_text[unit.canonical_start:unit.canonical_end])
    assert not notes[1].continuation_of
    with pytest.raises(UnresolvedLayout, match="adjacent"):
        map_layout_page(parsed, replace(page, page_number=number + 1), SHA,
                        note_direction="ltr", continued_from=prior)


def test_continuation_without_owner_or_zone_is_unresolved():
    parsed, page = real_layout(57)
    with pytest.raises(UnresolvedLayout, match="no page-local owner"):
        map_layout_page(parsed, page, SHA, note_direction="ltr",
                        note_zone_bbox=GOLD["continuations"]["57"]["note_zone_bbox"])
    with pytest.raises(UnresolvedLayout, match="certificate"):
        map_layout_page(parsed, page, SHA, note_direction="ltr", continued_from=mapped(56))


def test_unrelated_footer_cannot_be_absorbed_by_last_note():
    parsed, page = synthetic(box("footnote", synthetic_line(0, 0, 10, 200, "7 Note")),
                             box("page-footer", synthetic_line(9, 0, 10, 230, "Copyright")))
    with pytest.raises(UnresolvedLayout, match="Footer"):
        map_layout_page(parsed, page, SHA, note_direction="ltr")
