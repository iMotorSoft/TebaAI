"""Source-only annotation for V4_FROZEN_CONFIRMATION_HOLDOUT_V1.

Ground truth is derived from the source inventory and layout geometry only.
No certifier is imported or executed. Annotation and sanity checks happen
before the seal and before the single V4 opening.
"""
import json
import re
from pathlib import Path

OUT = Path(__file__).resolve().parent
SHA = "440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a"
CAPTION = "Likutey Halajot Explicado"
SEPARATOR = "Notas y Fuentes"
CROSS = [(108, 109, 31), (164, 165, 57), (226, 227, 77)]
LEADING = {next_page: number for _, next_page, number in CROSS}
MARKER = re.compile(r"^\s*(\d{1,3})[.)]?\s+\S")
INLINE = re.compile(r"(?<!^)\b\d{1,3}[.)]?\s")


def mixed(text):
    return any("\u0590" <= char <= "\u05ff" for char in text) or "\ufffd" in text


def text_of(line):
    return line["text"]


def unit(parts, zone, good, *, note=None, state="CONTINUATION_UNRESOLVED",
         link=None, basis=None):
    text = "\n".join(part["text"] for part in parts)
    good = bool(good and not mixed(text))
    return {
        "parts": parts,
        "expected_zone": zone,
        "expected_certifiable": good,
        "expected_quality": "ACCEPTED" if good else "UNRESOLVED",
        "note_number": note,
        "expected_continuation_state": state,
        "expected_link": link,
        "basis": basis or (
            "Manual source review: full main paragraph/inset vs header, "
            "source-language zone, sidebar, ornament or unsupported family."
        ),
    }


def find_caption(page):
    hits = [
        (index, box) for index, box in enumerate(page["boxes"])
        if any(CAPTION in line["text"] for line in box["lines"])
    ]
    return hits[0] if len(hits) == 1 else (None, None)


def find_separator(page):
    hits = [
        (index, box, line)
        for index, box in enumerate(page["boxes"])
        for line in box["lines"]
        if line["text"].lstrip("\ufffd ").startswith(SEPARATOR)
    ]
    return hits[0] if len(hits) == 1 else (None, None, None)


def build_body(page, caption_index, caption, separator_top):
    units = []
    for box in page["boxes"]:
        if box["index"] == caption_index:
            continue
        if box["class"] not in {"text", "section-header"}:
            continue
        if box["bbox"][1] >= separator_top + 2:
            continue
        if caption is not None and box["bbox"][3] < caption["bbox"][1] - 1:
            continue
        if caption is None:
            good = False
        else:
            good = (
                box["class"] == "text"
                and box["bbox"][2] - box["bbox"][0] >= 250
                and not mixed("".join(text_of(line) for line in box["lines"]))
            )
        units.append(unit(
            box["lines"],
            "MAIN_BODY" if good else box["class"],
            good,
            basis=(
                "Manual source review: main translation paragraph vs sidebar, "
                "section header, interleaved source text or ornament."
            ),
        ))
    return units


def build_notes(page, separator_line, separator_index):
    lines = []
    for box in page["boxes"]:
        if box["class"] not in {"text", "footnote", "page-footer", "section-header"}:
            continue
        for line in box["lines"]:
            if line is separator_line or line["bbox"][1] < separator_line["bbox"][3] - 1:
                continue
            lines.append(dict(line, column=(
                0 if (line["bbox"][0] + line["bbox"][2]) / 2 < page["width"] / 2 else 1
            )))
    lines.sort(key=lambda line: (
        line["column"], line["bbox"][1], line["bbox"][0], line["ids"]
    ))
    units = []
    current = []
    number = LEADING.get(page["page"])
    for part in lines:
        marker = MARKER.match(part["text"])
        if marker:
            if current:
                units.append(unit(current, "note", number is not None, note=number,
                                  state="COMPLETE_LOCAL"))
            current = []
            number = int(marker.group(1))
        current.append(part)
    if current:
        units.append(unit(current, "note", number is not None, note=number))
    return units


def apply_cross(pages):
    by_page = {page["pdf_page"]: page for page in pages}
    for first, second, number in CROSS:
        source = by_page[first]["units"]
        target = by_page[second]["units"]
        matches = [entry for entry in source if entry["note_number"] == number]
        assert len(matches) == 1, (first, "terminal note", number)
        leads = [
            entry for entry in target
            if entry["expected_zone"] == "note" and entry["note_number"] == number
        ]
        assert len(leads) == 1, (second, "leading note", number)
        leading = leads[0]
        notes = [entry for entry in target if entry["expected_zone"] == "note"]
        assert notes[0] is leading, (second, "leading note is not first")
        assert leading["expected_link"] is None, (second, "already linked")
        assert not MARKER.match(leading["parts"][0]["text"]), (second, "leading has marker")
        matches[0]["expected_continuation_state"] = "CONTINUES_NEXT_PAGE"
        matches[0]["expected_link"] = {"page": second, "note": number}
        leading["expected_continuation_state"] = "CONTINUED_FROM_PREVIOUS"
        leading["expected_link"] = {"page": first, "note": number}


def sanity(pages):
    oversplit = 0
    unexpected = 0
    inline_lines = 0
    for page in pages:
        for entry in page["units"]:
            if entry["expected_zone"] != "note":
                continue
            first = entry["parts"][0]["text"]
            if entry["expected_continuation_state"] != "CONTINUED_FROM_PREVIOUS":
                match = MARKER.match(first)
                if entry["note_number"] is not None:
                    if match is None or int(match.group(1)) != entry["note_number"]:
                        unexpected += 1
            for part in entry["parts"][1:]:
                if MARKER.match(part["text"]):
                    oversplit += 1
            for part in entry["parts"]:
                if INLINE.search(part["text"]):
                    inline_lines += 1
    return {
        "annotation_inline_digit_oversplit": oversplit,
        "annotation_unexpected_unit_start": unexpected,
        "inline_numeric_reference_lines": inline_lines,
        "status": "PASS" if oversplit == 0 and unexpected == 0 else "FAIL",
        "rule": (
            "Note units split only on line-start editorial markers; inline numeric "
            "references never create a unit boundary."
        ),
    }


def main():
    inventory = json.loads((OUT / "holdout-source-inventory.json").read_text())
    pages = []
    for page in inventory:
        caption_index, caption = find_caption(page)
        separator_index, separator, separator_line = find_separator(page)
        assert separator is not None, f"page {page['page']} lacks notes separator"
        units = build_body(page, caption_index, caption, separator["bbox"][1])
        units += build_notes(page, separator_line, separator_index)
        pages.append({"pdf_page": page["page"], "units": units})
    apply_cross(pages)
    result = sanity(pages)
    (OUT / "holdout-annotation-sanity.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    assert result["status"] == "PASS", result
    definition = {
        "version": "V4_FROZEN_CONFIRMATION_HOLDOUT_V1",
        "physical_pages": [page["page"] for page in inventory],
        "source_sha256": SHA,
        "pages": pages,
        "cross_page_units": [
            {"from": first, "to": second, "note": number}
            for first, second, number in CROSS
        ],
        "selection": (
            "35 disjoint source-reviewed pages excluding every previously opened "
            "holdout, development, permutation and golden page recorded in the "
            "source-artifact inventory."
        ),
        "annotation_scope": (
            "Implementing-agent source/IR review, not independent human adjudication "
            "nor exhaustive rendered glyph QA. Exact source identity, roles, note "
            "column flow and cross-page membership."
        ),
        "utility_rule": (
            "Body certification, note certification and safe cross-page linking must "
            "all show material utility. No arbitrary percentage threshold."
        ),
        "diversity": [
            "preface without caption", "main body", "main body + heading",
            "sidebar interleaving", "single-column notes", "two-column notes",
            "same-page notes", "page-start note continuation",
            "page-end note continuation", "mixed direction", "unsupported layout",
            "ambiguous column layout",
        ],
        "no_post_evaluation_tuning": True,
    }
    (OUT / "holdout-definition.json").write_text(
        json.dumps(definition, ensure_ascii=False, indent=2) + "\n"
    )
    note_units = sum(
        1 for page in pages for entry in page["units"] if entry["expected_zone"] == "note"
    )
    body_units = sum(
        1 for page in pages for entry in page["units"] if entry["expected_zone"] != "note"
    )
    print(f"{len(pages)} pages, {body_units} body/other units, {note_units} note units")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
