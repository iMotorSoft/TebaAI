"""Ablation negatives: remove one positive predicate and require fail-closed."""
from dataclasses import replace
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "SrvRestAstroLS_v1/backend"))
from modules.library.automatic_region_certification_v5 import (  # noqa: E402
    IDENTITY_PROVEN,
    _identity_contract,
    extract_pdf_region_certificates,
)

OUT = Path(__file__).resolve().parent
SOURCE = "/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf"


def main():
    pages = extract_pdf_region_certificates(SOURCE, pages=[206, 207])
    by_page = {page.provenance.pdf_page: page for page in pages}
    previous = by_page[206]
    following = by_page[207]
    terminal = next(u for u in previous.provenance.units if u.note_number == 5)
    first = next(u for u in following.provenance.units if u.note_number == 5)
    import pymupdf
    from pymupdf4llm.helpers.document_layout import parse_document
    with pymupdf.open(SOURCE) as document:
        parsed = parse_document(document, pages=[205, 206], use_ocr=False)
        parsed_pages = {page.page_number: page for page in parsed.pages}
        natives = {206: document[205], 207: document[206]}

        def contract(terminal_unit=terminal, first_unit=first, previous_page=previous,
                     previous_native=natives[206], following_native=natives[207]):
            return _identity_contract(
                previous_page.provenance, parsed_pages[206], previous_native,
                terminal_unit,
                following.provenance, parsed_pages[207], following_native,
                first_unit,
            )

        baseline_state, _, _ = contract()
        checks = []
        state, _, _ = contract(terminal_unit=replace(
            terminal, end_reason="NEXT_NOTE_IN_COLUMN_FLOW"
        ))
        checks.append(("terminal_not_page_boundary", state != IDENTITY_PROVEN, state))
        state, _, _ = contract(first_unit=replace(
            first,
            parts=(replace(first.parts[0], source_text="5 " + first.parts[0].source_text),
                   *first.parts[1:]),
        ))
        checks.append(("leading_is_marked", state != IDENTITY_PROVEN, state))
        state, _, _ = contract(first_unit=replace(first, note_number=6))
        checks.append(("wrong_note_number", state != IDENTITY_PROVEN, state))
        state, _, _ = contract(previous_native=None)
        checks.append(("missing_native_evidence", state != IDENTITY_PROVEN, state))
        state, _, _ = contract(previous_page=replace(
            previous, provenance=replace(
                previous.provenance, source_sha256="0" * 64
            )
        ))
        checks.append(("not_same_document", state != IDENTITY_PROVEN, state))
    output = {
        "status": "PASS" if baseline_state == IDENTITY_PROVEN
        and all(ok for _, ok, _ in checks) else "FAIL",
        "baseline": baseline_state,
        "checks": [{"name": name, "ok": ok, "state": state}
                   for name, ok, state in checks],
    }
    (OUT / "negative-results.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
