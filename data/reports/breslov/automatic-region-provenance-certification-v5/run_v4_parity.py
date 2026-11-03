"""Post-open V4 parity on the same safety pages.

This does not change the sealed V5 result. It answers whether the observed
body/notes coverage is a V5 regression or the frozen V4 baseline for this
safety-selected page set.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "SrvRestAstroLS_v1/backend"))
from modules.library.automatic_region_certification_v4 import (  # noqa: E402
    extract_pdf_region_certificates,
)

OUT = Path(__file__).resolve().parent
SOURCE = "/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf"


def parts_key(parts, actual=False):
    if actual:
        return [(part.source_line_ids, part.bbox) for part in parts]
    return [
        (tuple(tuple(pair) for pair in part["ids"]), tuple(part["bbox"]))
        for part in parts
    ]


def main():
    definition = json.loads((OUT / "holdout-definition.json").read_text())
    pages = extract_pdf_region_certificates(SOURCE, pages=definition["physical_pages"])
    metrics = {
        "body_supported": 0, "body_certified": 0, "body_accepted": 0,
        "notes_supported": 0, "notes_certified": 0, "notes_accepted": 0,
        "unsafe_false_certifications": 0, "unsafe_false_continuations": 0,
        "false_body_certifications": 0, "false_editorial_completions": 0,
        "regions": 0,
    }
    matched = {}
    for page, expected_page in zip(pages, definition["pages"], strict=True):
        units = {unit.region_id: unit for unit in page.provenance.units}
        for cert in page.certificates:
            metrics["regions"] += 1
            unit = units[cert.region_id]
            matches = [
                (index, expected)
                for index, expected in enumerate(expected_page["units"])
                if parts_key(unit.parts, True) == parts_key(expected["parts"])
            ]
            index, expected = matches[0] if len(matches) == 1 else (None, None)
            proven = bool(
                expected and expected["expected_certifiable"]
                and cert.zone_type == expected["expected_zone"]
                and cert.note_number == expected["note_number"]
            )
            certified = cert.provenance_status == "CERTIFIED"
            wrong_provenance = certified and not proven
            metrics["unsafe_false_certifications"] += (
                certified and cert.quality_status == "ACCEPTED"
                and (not proven or expected["expected_quality"] != "ACCEPTED")
            )
            metrics["false_body_certifications"] += (
                wrong_provenance and cert.zone_type == "MAIN_BODY"
            )
            if cert.linked_region_ids:
                metrics["unsafe_false_continuations"] += not bool(
                    proven and expected and expected.get("expected_link")
                )
            if certified and proven:
                matched[page.provenance.pdf_page, index] = cert
        for index, expected in enumerate(expected_page["units"]):
            if not expected["expected_certifiable"]:
                continue
            cert = matched.get((page.provenance.pdf_page, index))
            if expected["expected_zone"] == "MAIN_BODY":
                metrics["body_supported"] += 1
                metrics["body_certified"] += cert is not None
                metrics["body_accepted"] += bool(
                    cert and cert.quality_status == "ACCEPTED"
                )
            elif expected["expected_zone"] == "note":
                metrics["notes_supported"] += 1
                metrics["notes_certified"] += cert is not None
                metrics["notes_accepted"] += bool(
                    cert and cert.quality_status == "ACCEPTED"
                )
    metrics["body_unresolved"] = metrics["body_supported"] - metrics["body_certified"]
    metrics["notes_unresolved"] = metrics["notes_supported"] - metrics["notes_certified"]
    metrics["body_coverage"] = f"{metrics['body_certified']}/{metrics['body_supported']}"
    metrics["notes_coverage"] = f"{metrics['notes_certified']}/{metrics['notes_supported']}"
    (OUT / "v4-parity-results.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
