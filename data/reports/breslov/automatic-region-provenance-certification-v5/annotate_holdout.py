"""Source-only annotation for the V5 safety holdout.

No certifier is imported or executed. Note units come from the independent
canonical source grouping; body units follow the frozen annotation convention.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "SrvRestAstroLS_v1/backend"))

from modules.library.annotation_preseal_validation import (  # noqa: E402
    canonical_document,
)

OUT = Path(__file__).resolve().parent
SEPARATOR = "Notas y Fuentes"
CAPTION = "Likutey Halajot Explicado"


def mixed(text):
    return any("\u0590" <= char <= "\u05ff" for char in text) or "\ufffd" in text


def unit(parts, zone, good, *, note=None, state="COMPLETE_LOCAL",
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
            "Source-only review: main paragraph/inset vs header, source-language "
            "zone, sidebar, ornament or unsupported family."
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
        if separator_top is not None and box["bbox"][1] >= separator_top + 2:
            continue
        if caption is not None and box["bbox"][3] < caption["bbox"][1] - 1:
            continue
        good = (
            caption is not None
            and box["class"] == "text"
            and box["bbox"][2] - box["bbox"][0] >= 250
            and not mixed("".join(line["text"] for line in box["lines"]))
        )
        units.append(unit(
            box["lines"],
            "MAIN_BODY" if good else box["class"],
            good,
            basis=(
                "Source-only review: main translation paragraph vs sidebar, "
                "section header, interleaved source text or ornament."
            ),
        ))
    return units


def build_notes(page, canonical):
    units = []
    text = "\n".join(part["text"] for part in canonical["parts"])
    continuation = canonical["continuation_of_page"]
    good = canonical["note_number"] is not None and not mixed(text)
    units.append(unit(
        canonical["parts"],
        "note",
        good,
        note=canonical["note_number"],
        state="CONTINUED_FROM_PREVIOUS" if continuation is not None else "COMPLETE_LOCAL",
        link=({"page": continuation, "note": canonical["note_number"]}
              if continuation is not None else None),
        basis=(
            "Source-only canonical note grouping: connected x-projection "
            "columns, line-start marker, page-boundary lineage. No certifier."
        ),
    ))
    return units


def main():
    inventory = json.loads((OUT / "holdout-source-inventory.json").read_text())
    selection = json.loads((OUT / "holdout-selection.json").read_text())
    expected = set(selection["physical_pages"])
    if {page["page"] for page in inventory} != expected:
        raise SystemExit("inventory/selection page mismatch")
    canonical, canonical_errors = canonical_document(inventory)
    no_note_pages = {183, 239, 240, 255}
    canonical_errors = [
        error for error in canonical_errors
        if not (error["code"] == "PAGE_WITHOUT_UNIQUE_NOTES_SEPARATOR"
                and error["page"] in no_note_pages)
    ]
    if canonical_errors:
        raise SystemExit(f"canonical source errors: {canonical_errors}")
    positives = [
        (number, canonical[number][0]["note_number"])
        for number in sorted(canonical)
        if canonical[number] and canonical[number][0]["continuation_of_page"] is not None
    ]
    if positives:
        raise SystemExit(f"safety holdout unexpectedly has positives: {positives}")
    pages = []
    for page in inventory:
        number = page["page"]
        caption_index, caption = find_caption(page)
        _separator_index, _separator_box, separator = find_separator(page)
        separator_top = separator["bbox"][1] if separator is not None else None
        units = build_body(page, caption_index, caption, separator_top)
        for item in canonical.get(number, []):
            units.extend(build_notes(page, item))
        pages.append({"pdf_page": number, "units": units})
    definition = {
        "version": "automatic-region-provenance-certification-v5-holdout-v1",
        "physical_pages": sorted(expected),
        "source_sha256": selection["source_sha256"],
        "pages": pages,
        "cross_page_units": [],
        "selection": selection,
        "annotation_scope": (
            "Source-only safety holdout. No fresh cross-page positives remain; "
            "the development set carries the proven positives."
        ),
        "no_post_evaluation_tuning": True,
    }
    (OUT / "holdout-definition.json").write_text(
        json.dumps(definition, ensure_ascii=False, indent=2) + "\n"
    )
    summary = {
        "pages": len(pages),
        "units": sum(len(page["units"]) for page in pages),
        "note_units": sum(
            1 for page in pages for item in page["units"]
            if item["expected_zone"] == "note"
        ),
        "cross_page_positives": positives,
        "cross_page_negatives": selection["cross_page_negatives"],
    }
    (OUT / "holdout-annotation-sanity.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    print(summary)


if __name__ == "__main__":
    main()
