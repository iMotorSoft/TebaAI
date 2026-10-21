"""Independent pre-seal validation of region-annotation ground truth.

This module never imports a certifier and never reads certifier output. It uses
only the source inventory (native layout lines) and the proposed annotation.
The goal is to reject impossible or spurious expected units before a holdout is
sealed, so annotation defects cannot be misread later as certifier defects.

The canonical note grouping is derived from the source alone:
  * explicit notes separator;
  * connected x-projection columns (never visual centre);
  * reading order columns, then vertical line order;
  * line-start editorial markers only;
  * a leading unmarked note segment may inherit the previous page terminal note.
"""
from __future__ import annotations

import re

SEPARATORS = {"Notas y Fuentes", "Notas y Fuentes:", "Notes and Sources"}
NOTE_CLASSES = {"text", "footnote", "page-footer", "section-header"}
MARKER = re.compile(r"^\s*(\d{1,3})(?![.,]\d)[.)]?\s+\S")
CONTINUES = "CONTINUES_NEXT_PAGE"
CONTINUED = "CONTINUED_FROM_PREVIOUS"


def _line_key(line):
    return (tuple(tuple(pair) for pair in line["ids"]), tuple(line["bbox"]))


def _text(line):
    return line.get("text", "")


def _clean(text):
    return text.replace("\ufffd", "").strip()


def _separator(page):
    found = [line for box in page["boxes"] for line in box["lines"]
             if _clean(_text(line)) in SEPARATORS]
    return found[0] if len(found) == 1 else None


def _note_lines(page):
    separator = _separator(page)
    if separator is None:
        return None
    separator_key = _line_key(separator)
    lines = []
    for box in page["boxes"]:
        if box["class"] not in NOTE_CLASSES:
            continue
        for line in box["lines"]:
            if _line_key(line) == separator_key:
                continue
            if line["bbox"][1] < separator["bbox"][3] - 1:
                continue
            lines.append(line)
    return lines


def _columns(lines):
    columns = []
    for line in sorted(lines, key=lambda item: tuple(item["bbox"])):
        x0, _, x1, _ = line["bbox"]
        hits = [column for column in columns if x0 < column[1] and column[0] < x1]
        if len(hits) > 1:
            return None
        if hits:
            column = hits[0]
            column[0] = min(column[0], x0)
            column[1] = max(column[1], x1)
            column[2].append(line)
        else:
            columns.append([x0, x1, [line]])
    columns.sort(key=lambda column: column[0])
    return columns


def marker_number(text):
    match = MARKER.match(text)
    return int(match.group(1)) if match else None


def _ends_sentence(text):
    stripped = text.rstrip()
    return bool(stripped) and stripped[-1] in '.!?;:"”’)]'


def _real_marker(text, previous_text, previous_number):
    """Reject a line-start number that continues an unfinished reference."""
    value = marker_number(text)
    if value is None:
        return None
    if previous_text is not None and not _ends_sentence(previous_text):
        if previous_number is not None and value <= previous_number:
            return None
    return value


def canonical_page_units(page, previous_units=None):
    """Source-only note grouping. Returns (units, error_codes)."""
    lines = _note_lines(page)
    if lines is None:
        return [], ["PAGE_WITHOUT_UNIQUE_NOTES_SEPARATOR"]
    columns = _columns(lines)
    if columns is None:
        return [], ["LINE_BRIDGES_NOTE_COLUMNS"]
    ordered = [
        line
        for _, _, members in columns
        for line in sorted(members, key=lambda item: (item["bbox"][1], item["bbox"][0],
                                                      _line_key(item)))
    ]
    if not ordered:
        return [], []
    seed = None
    continuation = False
    if marker_number(_text(ordered[0])) is None and previous_units:
        terminal = previous_units[-1]
        if terminal["end_reason"] == "PAGE_BOUNDARY" and terminal["note_number"] is not None:
            seed = terminal["note_number"]
            continuation = True
    groups = []
    current = []
    number = seed
    previous_text = None
    for line in ordered:
        text = _text(line)
        value = _real_marker(text, previous_text, number)
        if value is not None:
            if current:
                groups.append((number, current, "NEXT_NOTE_IN_COLUMN_FLOW"))
            current = []
            number = value
        current.append(line)
        previous_text = text
    if current:
        groups.append((number, current, "PAGE_BOUNDARY"))
    units = []
    for index, (value, members, end_reason) in enumerate(groups):
        units.append({
            "note_number": value,
            "keys": tuple(sorted(_line_key(line) for line in members)),
            "parts": [
                {"ids": line["ids"], "bbox": list(line["bbox"]), "text": _text(line)}
                for line in members
            ],
            "end_reason": end_reason,
            "continuation_of_page": (
                page["page"] - 1 if continuation and index == 0 else None
            ),
        })
    return units, []


def canonical_document(inventory):
    by_page = {page["page"]: page for page in inventory}
    result = {}
    errors = []
    for number in sorted(by_page):
        previous = result.get(number - 1)
        units, page_errors = canonical_page_units(by_page[number], previous)
        result[number] = units
        errors.extend({"code": code, "page": number} for code in page_errors)
    return result, errors


def _annotation_units(definition):
    return {
        page["pdf_page"]: [unit for unit in page["units"] if unit["expected_zone"] == "note"]
        for page in definition["pages"]
    }


def _all_units(definition):
    return {
        page["pdf_page"]: list(page["units"]) for page in definition["pages"]
    }


def _keys(unit):
    return tuple(sorted(
        (tuple(tuple(pair) for pair in part["ids"]), tuple(part["bbox"]))
        for part in unit["parts"]
    ))


def _inventory_keys(page):
    return {
        _line_key(line)
        for box in page["boxes"] for line in box["lines"]
    }


def validate(inventory, definition):
    """Return a deterministic pre-seal report. status PASS means safe to seal."""
    errors = []
    warnings = []
    canonical, canonical_errors = canonical_document(inventory)
    inventory_by_page = {page["page"]: page for page in inventory}
    annotated = _annotation_units(definition)
    all_units = _all_units(definition)
    for error in canonical_errors:
        if (error["code"] == "PAGE_WITHOUT_UNIQUE_NOTES_SEPARATOR"
                and not annotated.get(error["page"])):
            warnings.append({**error, "code": "PAGE_WITHOUT_NOTES"})
        else:
            errors.append(error)

    for page_number in sorted(set(annotated) | set(canonical)):
        if page_number not in inventory_by_page:
            errors.append({"code": "PAGE_NOT_IN_SOURCE_INVENTORY", "page": page_number})
            continue
        source_keys = _inventory_keys(inventory_by_page[page_number])
        units = annotated.get(page_number, [])
        seen = {}
        for index, unit in enumerate(units):
            keys = _keys(unit)
            for key in keys:
                if key not in source_keys:
                    errors.append({"code": "PART_NOT_IN_SOURCE", "page": page_number,
                                   "unit": index, "key": list(key)})
                if key in seen:
                    errors.append({"code": "DUPLICATE_SOURCE_OWNERSHIP", "page": page_number,
                                   "units": [seen[key], index], "key": list(key)})
                seen[key] = index
            if set(keys) and all(key in source_keys for key in keys):
                for left, right in zip(keys, keys[1:]):
                    if left[1][1] > right[1][1] + 1:
                        warnings.append({"code": "NON_VERTICAL_UNIT_ORDER",
                                         "page": page_number, "unit": index})
            first = unit["parts"][0] if unit["parts"] else None
            state = unit.get("expected_continuation_state")
            if state == CONTINUED:
                if first is not None and marker_number(_text(first)) is not None:
                    errors.append({"code": "CONTINUATION_HAS_MARKER",
                                   "page": page_number, "unit": index})
                if index != 0:
                    errors.append({"code": "CONTINUATION_IS_NOT_FIRST_NOTE",
                                   "page": page_number, "unit": index})
            else:
                if unit.get("note_number") is None:
                    errors.append({"code": "UNMARKED_NOTE_UNIT_WITHOUT_CONTINUATION",
                                   "page": page_number, "unit": index})
                elif first is not None:
                    value = marker_number(_text(first))
                    if value != unit["note_number"]:
                        errors.append({"code": "NOTE_MARKER_MISMATCH",
                                       "page": page_number, "unit": index,
                                       "expected": unit["note_number"], "found": value})
                for part in unit["parts"][1:]:
                    if marker_number(_text(part)) is not None:
                        errors.append({"code": "MARKER_INSIDE_UNIT",
                                       "page": page_number, "unit": index})

        canonical_units = canonical.get(page_number, [])
        canonical_by_keys = {unit["keys"]: unit for unit in canonical_units}
        annotated_by_keys = {_keys(unit): unit for unit in units}
        for keys, canonical_unit in canonical_by_keys.items():
            annotated_unit = annotated_by_keys.get(keys)
            if annotated_unit is None:
                errors.append({"code": "MISSING_ANNOTATED_NOTE_UNIT",
                               "page": page_number,
                               "note_number": canonical_unit["note_number"],
                               "continuation": canonical_unit["continuation_of_page"]})
                continue
            if annotated_unit.get("note_number") != canonical_unit["note_number"]:
                errors.append({"code": "NOTE_NUMBER_MISMATCH", "page": page_number,
                               "expected": canonical_unit["note_number"],
                               "found": annotated_unit.get("note_number")})
            if canonical_unit["continuation_of_page"] is not None:
                if annotated_unit.get("expected_continuation_state") != CONTINUED:
                    errors.append({"code": "UNANNOTATED_LEADING_CONTINUATION",
                                   "page": page_number,
                                   "note_number": canonical_unit["note_number"]})
                link = annotated_unit.get("expected_link") or {}
                if link.get("page") != canonical_unit["continuation_of_page"]:
                    errors.append({"code": "WRONG_CONTINUATION_SOURCE_PAGE",
                                   "page": page_number,
                                   "expected": canonical_unit["continuation_of_page"],
                                   "found": link.get("page")})
        for keys, annotated_unit in annotated_by_keys.items():
            if keys in canonical_by_keys:
                continue
            subset = [unit for unit in canonical_units if set(keys) < set(unit["keys"])]
            superset = [unit for unit in canonical_units if set(keys) > set(unit["keys"])]
            if subset:
                errors.append({"code": "INCOMPLETE_NOTE_UNIT", "page": page_number,
                               "note_number": annotated_unit.get("note_number"),
                               "canonical_note_number": subset[0]["note_number"]})
            elif superset:
                errors.append({"code": "MERGED_NOTE_UNITS", "page": page_number,
                               "note_number": annotated_unit.get("note_number")})
            else:
                errors.append({"code": "SPURIOUS_ANNOTATED_NOTE_UNIT",
                               "page": page_number,
                               "note_number": annotated_unit.get("note_number")})

    # Cross-page declarations must be real, adjacent, and mutually consistent.
    by_page_units = all_units
    for page_number, units in sorted(by_page_units.items()):
        for index, unit in enumerate(units):
            state = unit.get("expected_continuation_state")
            link = unit.get("expected_link")
            if state == CONTINUES:
                if not link:
                    errors.append({"code": "MISSING_CROSS_PAGE_LINK", "page": page_number,
                                   "unit": index})
                    continue
                if link.get("page") != page_number + 1:
                    errors.append({"code": "CROSS_PAGE_NOT_ADJACENT", "page": page_number,
                                   "unit": index})
                    continue
                targets = [entry for entry in by_page_units.get(page_number + 1, [])
                           if entry.get("expected_continuation_state") == CONTINUED
                           and entry.get("note_number") == unit.get("note_number")]
                if len(targets) != 1:
                    errors.append({"code": "UNMATCHED_CROSS_PAGE_LINK", "page": page_number,
                                   "unit": index})
                else:
                    back = targets[0].get("expected_link") or {}
                    if back.get("page") != page_number or back.get("note") != unit.get("note_number"):
                        errors.append({"code": "ASYMMETRIC_CROSS_PAGE_LINK",
                                       "page": page_number, "unit": index})
            elif state == CONTINUED:
                if not link:
                    errors.append({"code": "MISSING_CROSS_PAGE_SOURCE", "page": page_number,
                                   "unit": index})
                    continue
                if link.get("page") != page_number - 1:
                    errors.append({"code": "CROSS_PAGE_NOT_ADJACENT", "page": page_number,
                                   "unit": index})
                    continue
                sources = [entry for entry in by_page_units.get(page_number - 1, [])
                           if entry.get("expected_continuation_state") == CONTINUES
                           and entry.get("note_number") == unit.get("note_number")]
                if len(sources) != 1:
                    errors.append({"code": "UNMATCHED_CONTINUATION_SOURCE",
                                   "page": page_number, "unit": index})

    declared_cross = {
        (page["pdf_page"], unit.get("note_number"))
        for page in definition["pages"] for unit in page["units"]
        if unit.get("expected_continuation_state") == CONTINUES
    }
    canonical_cross = {
        (page_number, unit["note_number"])
        for page_number, units in canonical.items() for unit in units
        if unit["continuation_of_page"] is not None
    }
    for page_number, note_number in sorted(canonical_cross - declared_cross):
        errors.append({"code": "CANONICAL_CONTINUATION_NOT_DECLARED",
                       "page": page_number, "note_number": note_number})

    return {
        "status": "PASS" if not errors else "FAIL",
        "pages_checked": len(inventory),
        "canonical_note_units": sum(len(units) for units in canonical.values()),
        "annotated_note_units": sum(len(units) for units in annotated.values()),
        "canonical_cross_page_units": len(canonical_cross),
        "declared_cross_page_units": len(declared_cross),
        "errors": errors,
        "warnings": warnings,
    }
