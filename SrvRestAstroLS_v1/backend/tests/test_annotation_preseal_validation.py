"""Independent source+annotation validation must reject annotation defects."""
from modules.library.annotation_preseal_validation import validate
from test_region_markdown_provenance import synthetic_line


def line(block, number, x, y, text):
    source = synthetic_line(block, number, x, y, text)
    return {
        "bbox": list(source["bbox"]),
        "ids": [[span["block"], span["line"]] for span in source["spans"]],
        "text": "".join(span["text"] for span in source["spans"]),
        "styles": sorted({
            (span["font"], span["size"]) for span in source["spans"]
        }),
    }


def inventory():
    separator = line(0, 0, 110, 297, "Notas y Fuentes")
    first = line(1, 0, 10, 340, "7 First note")
    second = line(1, 1, 10, 360, "continuation of seven")
    eighth = line(1, 2, 10, 380, "8 Next note")
    return [{
        "page": 1, "width": 300, "height": 500,
        "boxes": [
            {"index": 0, "class": "section-header", "bbox": separator["bbox"],
             "lines": [separator]},
            {"index": 1, "class": "footnote",
             "bbox": [10, 340, 90, 387],
             "lines": [first, second, eighth]},
        ],
    }]


def part(source):
    return {"ids": source["ids"], "bbox": source["bbox"], "text": source["text"]}


def unit(source, number, *, state="COMPLETE_LOCAL", link=None):
    return {
        "parts": [part(source)],
        "expected_zone": "note",
        "expected_certifiable": True,
        "expected_quality": "ACCEPTED",
        "note_number": number,
        "expected_continuation_state": state,
        "expected_link": link,
        "basis": "test",
    }


def definition(units, page=1):
    return {"pages": [{"pdf_page": page, "units": units}]}


def test_validator_rejects_split_note_unit():
    source = inventory()
    notes = source[0]["boxes"][1]["lines"]
    result = validate(source, definition([
        unit(notes[0], 7, state="COMPLETE_LOCAL"),
        unit(notes[1], 7, state="COMPLETE_LOCAL"),
        unit(notes[2], 8, state="COMPLETE_LOCAL"),
    ]))
    # Each half is a strict subset of canonical note 7.
    assert result["status"] == "FAIL"
    assert any(error["code"] == "INCOMPLETE_NOTE_UNIT"
               for error in result["errors"])


def test_validator_accepts_one_unit_per_canonical_note():
    source = inventory()
    notes = source[0]["boxes"][1]["lines"]
    merged = {
        "parts": [part(notes[0]), part(notes[1])],
        "expected_zone": "note",
        "expected_certifiable": True,
        "expected_quality": "ACCEPTED",
        "note_number": 7,
        "expected_continuation_state": "COMPLETE_LOCAL",
        "expected_link": None,
        "basis": "test",
    }
    result = validate(source, definition([merged, unit(notes[2], 8)]))
    assert result["status"] == "PASS"


def test_validator_rejects_missing_note_unit():
    source = inventory()
    notes = source[0]["boxes"][1]["lines"]
    merged = {
        "parts": [part(notes[0]), part(notes[1])],
        "expected_zone": "note", "expected_certifiable": True,
        "expected_quality": "ACCEPTED", "note_number": 7,
        "expected_continuation_state": "COMPLETE_LOCAL",
        "expected_link": None, "basis": "test",
    }
    result = validate(source, definition([merged]))
    assert result["status"] == "FAIL"
    assert any(error["code"] == "MISSING_ANNOTATED_NOTE_UNIT"
               for error in result["errors"])


def test_validator_rejects_incomplete_note_unit():
    source = inventory()
    notes = source[0]["boxes"][1]["lines"]
    result = validate(source, definition([
        unit(notes[0], 7),
        unit(notes[2], 8),
    ]))
    assert result["status"] == "FAIL"
    assert any(error["code"] == "INCOMPLETE_NOTE_UNIT" for error in result["errors"])


def test_validator_rejects_unannotated_leading_continuation():
    first = line(0, 0, 110, 297, "Notas y Fuentes")
    terminal = line(1, 0, 10, 340, "8 Terminal note")
    second_separator = line(2, 0, 110, 297, "Notas y Fuentes")
    leading = line(3, 0, 10, 340, "continued text")
    following = line(3, 1, 10, 360, "9 Next note")
    source = [
        {"page": 1, "width": 300, "height": 500, "boxes": [
            {"index": 0, "class": "section-header", "bbox": first["bbox"],
             "lines": [first]},
            {"index": 1, "class": "footnote", "bbox": [10, 340, 90, 347],
             "lines": [terminal]},
        ]},
        {"page": 2, "width": 300, "height": 500, "boxes": [
            {"index": 0, "class": "section-header", "bbox": second_separator["bbox"],
             "lines": [second_separator]},
            {"index": 1, "class": "footnote", "bbox": [10, 340, 90, 367],
             "lines": [leading, following]},
        ]},
    ]
    page_one = {
        "parts": [part(terminal)],
        "expected_zone": "note", "expected_certifiable": True,
        "expected_quality": "ACCEPTED", "note_number": 8,
        "expected_continuation_state": "COMPLETE_LOCAL",
        "expected_link": None, "basis": "test",
    }
    page_two = {
        "parts": [part(leading)],
        "expected_zone": "note", "expected_certifiable": True,
        "expected_quality": "ACCEPTED", "note_number": 8,
        "expected_continuation_state": "COMPLETE_LOCAL",
        "expected_link": None, "basis": "test",
    }
    next_unit = unit(following, 9)
    result = validate(source, {"pages": [
        {"pdf_page": 1, "units": [page_one]},
        {"pdf_page": 2, "units": [page_two, next_unit]},
    ]})
    assert result["status"] == "FAIL"
    assert any(error["code"] == "UNANNOTATED_LEADING_CONTINUATION"
               for error in result["errors"])


def test_validator_allows_page_without_notes():
    body = line(0, 0, 10, 100, "Ordinary body")
    source = [{
        "page": 1, "width": 300, "height": 500,
        "boxes": [{"index": 0, "class": "text", "bbox": body["bbox"],
                   "lines": [body]}],
    }]
    body_unit = {
        "parts": [part(body)],
        "expected_zone": "MAIN_BODY", "expected_certifiable": True,
        "expected_quality": "ACCEPTED", "note_number": None,
        "expected_continuation_state": "COMPLETE_LOCAL",
        "expected_link": None, "basis": "test",
    }
    result = validate(source, definition([body_unit]))
    assert result["status"] == "PASS"
    assert any(warning["code"] == "PAGE_WITHOUT_NOTES"
               for warning in result["warnings"])


def test_validator_rejects_duplicate_source_ownership():
    source = inventory()
    notes = source[0]["boxes"][1]["lines"]
    result = validate(source, definition([
        unit(notes[0], 7),
        unit(notes[0], 7),
    ]))
    assert result["status"] == "FAIL"
    assert any(error["code"] == "DUPLICATE_SOURCE_OWNERSHIP"
               for error in result["errors"])
