"""Independent source prevalidation before the first V5 opening.

Uses only the source inventory and the annotation validator's canonical note
grouping. No certifier, embedding or semantic model is consulted.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "SrvRestAstroLS_v1/backend"))
from modules.library.annotation_preseal_validation import (  # noqa: E402
    canonical_document,
    marker_number,
)

OUT = Path(__file__).resolve().parent
MARKER = re.compile(r"^\s*(\d{1,3})(?![.,]\d)[.)]?\s+\S")
TERMINAL = (".", "!", "?", "。", "！", "？")


def write(name, payload):
    (OUT / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def keys(unit):
    return {tuple(tuple(pair) for pair in part["ids"]) for part in unit["parts"]}


def main():
    inventory = json.loads((OUT / "all-pages-source-inventory.json").read_text())
    canonical, errors = canonical_document(inventory)
    by_page = {page["page"]: page for page in inventory}
    eligible = json.loads((OUT / "eligible-positive-set.json").read_text())["pairs"]
    positives = json.loads((OUT / "development-regression-contract.json").read_text())["positive"]
    negatives = json.loads((OUT / "development-regression-contract.json").read_text())["negative"]
    virgin = json.loads((OUT / "virgin-safety-contract.json").read_text())
    checks = []
    failures = []

    def record(name, ok, detail):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})
        if not ok:
            failures.append({"check": name, "detail": detail})

    # Source ownership and duplicate ownership for every page in the gate.
    gate_pages = sorted({
        page for pair in eligible + positives + negatives
        for page in (pair["from"], pair["to"])
    } | set(virgin["pages"]))
    for page in gate_pages:
        units = canonical.get(page, [])
        seen = {}
        duplicated = False
        for index, unit in enumerate(units):
            for key in keys(unit):
                if key in seen:
                    duplicated = True
                seen[key] = index
        record(f"page_{page}_source_units_and_unique_ownership", not duplicated,
               {"page": page, "units": len(units), "duplicate_ownership": duplicated})

    # Positive pairs: adjacency, terminal/leading structure, marker continuity.
    for pair in eligible:
        start, end, note = pair["from"], pair["to"], pair["note"]
        terminal = canonical.get(start, [{}])[-1] if canonical.get(start) else {}
        leading = canonical.get(end, [{}])[0] if canonical.get(end) else {}
        next_units = [unit for unit in canonical.get(end, [])
                      if unit.get("note_number") is not None]
        next_marker = next_units[1]["note_number"] if len(next_units) > 1 else None
        first_text = leading.get("parts", [{}])[0].get("text", "")
        last_text = terminal.get("parts", [{}])[-1].get("text", "").rstrip()
        terminal_marker = marker_number(
            terminal.get("parts", [{}])[0].get("text", "")) if terminal else None
        detail = {
            "from": start,
            "to": end,
            "note": note,
            "adjacent": end == start + 1 and start in by_page and end in by_page,
            "terminal_is_last_note": bool(terminal) and terminal.get("note_number") == note,
            "terminal_marker": terminal_marker,
            "terminal_end_reason": terminal.get("end_reason"),
            "terminal_tail": last_text[-120:],
            "terminal_ends_terminal_punctuation": bool(last_text) and last_text[-1] in TERMINAL,
            "leading_note": leading.get("note_number"),
            "leading_first_line_marked": marker_number(first_text) is not None,
            "leading_head": first_text[:120],
            "next_explicit_marker": next_marker,
            "next_marker_is_n_plus_one": next_marker == note + 1,
            "leading_end_reason": leading.get("end_reason"),
        }
        ok = bool(
            detail["adjacent"]
            and detail["terminal_is_last_note"]
            and detail["terminal_marker"] == note
            and detail["terminal_end_reason"] == "PAGE_BOUNDARY"
            and not detail["leading_first_line_marked"]
            and detail["leading_note"] == note
            and detail["next_marker_is_n_plus_one"]
        )
        record(f"positive_{start}_{end}_source_continuity", ok, detail)

    # Negative notes: the named note must not be a page-boundary continuation.
    for pair in negatives:
        start, end, note = pair["from"], pair["to"], pair["note"]
        candidates = [unit for unit in canonical.get(start, [])
                      if unit.get("note_number") == note]
        leading = canonical.get(end, [{}])[0] if canonical.get(end) else {}
        detail = {
            "from": start, "to": end, "note": note,
            "units_found": len(candidates),
            "end_reasons": [unit.get("end_reason") for unit in candidates],
            "leading_note": leading.get("note_number"),
            "leading_first_line_marked": marker_number(
                leading.get("parts", [{}])[0].get("text", "")) is not None,
        }
        detail["separate"] = not (
            len(candidates) == 1
            and candidates[0].get("end_reason") == "PAGE_BOUNDARY"
            and leading.get("note_number") == note
            and not detail["leading_first_line_marked"]
        )
        record(f"negative_{start}_{end}_note_{note}_separate", detail["separate"], detail)

    # Virgin mandatory pairs: next page leading note is explicitly marked.
    for pair in virgin["mandatory_pairs"]:
        start, end, note = pair["from"], pair["to"], pair["note"]
        terminal = canonical.get(start, [{}])[-1] if canonical.get(start) else {}
        leading = canonical.get(end, [{}])[0] if canonical.get(end) else {}
        first_text = leading.get("parts", [{}])[0].get("text", "")
        terminal_markers = [
            value for part in terminal.get("parts", [])
            for value in (marker_number(part.get("text", "")),)
            if value is not None
        ]
        # A note marker may be inline at the end of the previous note line.
        terminal_text = " ".join(part.get("text", "") for part in terminal.get("parts", []))
        if not terminal_markers or terminal_markers[-1] != note:
            if re.search(rf"(?<!\d){note}(?!\d)", terminal_text):
                terminal_markers.append(note)
        detail = {
            "from": start, "to": end, "note": note,
            "terminal_note": terminal.get("note_number"),
            "terminal_last_marker": terminal_markers[-1] if terminal_markers else None,
            "terminal_end_reason": terminal.get("end_reason"),
            "leading_note": leading.get("note_number"),
            "leading_first_line_marked": marker_number(first_text) is not None,
            "leading_head": first_text[:100],
            "note_34_inline_in_terminal_line": start == 156,
        }
        detail["no_true_continuation"] = bool(
            detail["terminal_last_marker"] == note
            and detail["terminal_end_reason"] == "PAGE_BOUNDARY"
            and detail["leading_first_line_marked"]
            and detail["leading_note"] != note
        )
        record(f"virgin_{start}_{end}_no_continuation", detail["no_true_continuation"], detail)

    output = {
        "status": "PASS" if not failures else "FAIL",
        "source_sha256": json.loads((OUT / "eligible-positive-set.json").read_text())["source_sha256"],
        "gate_pages": len(gate_pages),
        "canonical_errors": len(errors),
        "checks": checks,
        "failures": failures,
        "note": "Source-only. The certifier was not imported or executed.",
    }
    write("prevalidation-results.json", output)
    print(json.dumps({key: output[key] for key in
                      ("status", "gate_pages", "canonical_errors", "failures")}, indent=2))


if __name__ == "__main__":
    main()
