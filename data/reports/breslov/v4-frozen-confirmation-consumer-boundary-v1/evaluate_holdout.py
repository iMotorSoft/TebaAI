"""Single sealed V4 opening for V4_FROZEN_CONFIRMATION_HOLDOUT_V1.

The holdout, its annotation, the evaluator semantics and V4 are frozen before
this script runs. It refuses to run twice.
"""
import hashlib
import json
from pathlib import Path
import sys
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(ROOT / "SrvRestAstroLS_v1/backend"))
from modules.library.automatic_region_certification_v4 import (  # noqa: E402
    extract_pdf_region_certificates,
)

SOURCE = "/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf"
SAFETY_KEYS = [
    "unsafe_false_certifications",
    "unsafe_false_provenance_certifications",
    "false_body_certifications",
    "unsafe_false_continuations",
    "false_editorial_completions",
]


def parts_key(parts, actual=False):
    if actual:
        return [(part.source_line_ids, part.bbox) for part in parts]
    return [
        (tuple(tuple(pair) for pair in part["ids"]), tuple(part["bbox"]))
        for part in parts
    ]


def main():
    first_open = OUT / "holdout-first-open.json"
    assert not first_open.exists(), "Holdout already opened; do not rerun or reseal"
    seal = OUT / "holdout-sealed-hash.txt"
    for line in seal.read_text().splitlines():
        sha, path = line.split("  ", 1)
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == sha, path
    definition = json.loads((OUT / "holdout-definition.json").read_text())
    assert hashlib.sha256(Path(SOURCE).read_bytes()).hexdigest() == definition["source_sha256"]
    first_open.write_text(json.dumps({
        "seal_sha256": hashlib.sha256(seal.read_bytes()).hexdigest(),
        "definition_sha256": hashlib.sha256(
            (OUT / "holdout-definition.json").read_bytes()
        ).hexdigest(),
        "start_unix": time.time(),
        "no_post_evaluation_tuning": True,
        "single_open": True,
    }, indent=2) + "\n")

    start = time.monotonic()
    pages = extract_pdf_region_certificates(SOURCE, pages=definition["physical_pages"])
    actual = {c.region_id: c for page in pages for c in page.certificates}
    metrics = {
        "pages": len(pages),
        "regions": sum(len(page.certificates) for page in pages),
        "correct_certifications": 0,
        "correct_unresolved": 0,
        "correct_accepted": 0,
        "unsafe_false_certifications": 0,
        "unsafe_false_provenance_certifications": 0,
        "false_body_certifications": 0,
        "unsafe_false_continuations": 0,
        "false_editorial_completions": 0,
        "body_supported": 0,
        "body_certified": 0,
        "body_accepted": 0,
        "body_unresolved": 0,
        "notes_supported": 0,
        "notes_certified": 0,
        "notes_accepted": 0,
        "notes_unresolved": 0,
        "cross_page_units": len(definition["cross_page_units"]),
        "cross_page_linked": 0,
        "cross_page_unresolved": 0,
    }
    rows = []
    matched = {}
    for page, expected_page in zip(pages, definition["pages"], strict=True):
        assert page.provenance.pdf_page == expected_page["pdf_page"]
        units = {unit.region_id: unit for unit in page.provenance.units}
        results = []
        for cert in page.certificates:
            provenance_unit = units[cert.region_id]
            matches = [
                (index, expected)
                for index, expected in enumerate(expected_page["units"])
                if parts_key(provenance_unit.parts, True) == parts_key(expected["parts"])
            ]
            index, expected = matches[0] if len(matches) == 1 else (None, None)
            proven = bool(
                expected
                and expected["expected_certifiable"]
                and cert.zone_type == expected["expected_zone"]
                and cert.note_number == expected["note_number"]
            )
            certified = cert.provenance_status == "CERTIFIED"
            wrong_provenance = certified and not proven
            wrong_accepted = (
                certified
                and cert.quality_status == "ACCEPTED"
                and (not proven or expected["expected_quality"] != "ACCEPTED")
            )
            metrics["unsafe_false_provenance_certifications"] += wrong_provenance
            metrics["unsafe_false_certifications"] += wrong_accepted
            metrics["false_body_certifications"] += (
                wrong_provenance and cert.zone_type == "MAIN_BODY"
            )
            metrics["correct_certifications"] += certified and proven
            metrics["correct_accepted"] += (
                certified and proven and cert.quality_status == "ACCEPTED"
            )
            metrics["correct_unresolved"] += (
                not certified and not (expected and expected["expected_certifiable"])
            )
            if certified and proven:
                matched[page.provenance.pdf_page, index] = cert

            false_link = False
            expected_link = expected.get("expected_link") if expected else None
            if cert.linked_region_ids:
                target = actual.get(cert.linked_region_ids[0])
                false_link = not bool(
                    proven
                    and expected_link
                    and target
                    and target.pdf_page == expected_link["page"]
                    and target.note_number == expected_link["note"]
                    and target.editorial_unit_id == cert.editorial_unit_id
                )
                metrics["unsafe_false_continuations"] += false_link
            completion = (
                cert.continuation_state == "COMPLETE_LOCAL"
                or cert.continuation_status == "CROSS_PAGE_COMPLETE"
            )
            false_completion = bool(
                completion
                and not (
                    expected
                    and (
                        expected["expected_continuation_state"] == "COMPLETE_LOCAL"
                        or (
                            expected_link
                            and not false_link
                            and cert.linked_region_ids
                        )
                    )
                )
            )
            metrics["false_editorial_completions"] += false_completion
            results.append({
                "pdf_page": page.provenance.pdf_page,
                "region_id": cert.region_id,
                "zone": cert.zone_type,
                "note": cert.note_number,
                "certified": cert.provenance_status,
                "quality": cert.quality_status,
                "expected_index": index,
                "expected_zone": expected["expected_zone"] if expected else None,
                "expected_certifiable": (
                    expected["expected_certifiable"] if expected else None
                ),
                "unsafe_provenance": wrong_provenance,
                "unsafe_acceptance": wrong_accepted,
                "false_link": false_link,
                "false_completion": false_completion,
                "linked": cert.linked_region_ids,
                "editorial_unit_id": cert.editorial_unit_id,
            })
        rows.append({"pdf_page": page.provenance.pdf_page, "regions": results})
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
    for link in definition["cross_page_units"]:
        candidates = [
            cert for cert in actual.values()
            if cert.pdf_page == link["from"]
            and cert.note_number == link["note"]
            and cert.linked_region_ids
        ]
        linked = bool(
            len(candidates) == 1
            and actual[candidates[0].linked_region_ids[0]].pdf_page == link["to"]
            and actual[candidates[0].linked_region_ids[0]].note_number == link["note"]
            and actual[candidates[0].linked_region_ids[0]].editorial_unit_id
            == candidates[0].editorial_unit_id
        )
        metrics["cross_page_linked"] += linked
    metrics["body_unresolved"] = metrics["body_supported"] - metrics["body_certified"]
    metrics["notes_unresolved"] = metrics["notes_supported"] - metrics["notes_certified"]
    metrics["cross_page_unresolved"] = (
        metrics["cross_page_units"] - metrics["cross_page_linked"]
    )
    metrics["body_coverage"] = (
        f"{metrics['body_certified']}/{metrics['body_supported']}"
    )
    metrics["notes_coverage"] = (
        f"{metrics['notes_certified']}/{metrics['notes_supported']}"
    )
    metrics["cross_page_coverage"] = (
        f"{metrics['cross_page_linked']}/{metrics['cross_page_units']}"
    )
    metrics["seconds"] = time.monotonic() - start
    safety = not any(metrics[key] for key in SAFETY_KEYS)
    utility = bool(
        metrics["body_certified"] > metrics["body_unresolved"]
        and metrics["body_certified"] > 0
        and metrics["body_accepted"] > 1
        and metrics["notes_certified"] > metrics["notes_unresolved"]
        and metrics["notes_certified"] > 0
        and metrics["cross_page_linked"] >= 2
    )
    output = {
        "gate": "PASS" if safety and utility else "FAIL",
        "safety_pass": safety,
        "utility_pass": utility,
        "sealed_before_evaluation": True,
        "single_open": True,
        "rules_changed_after_evaluation": False,
        "metrics": metrics,
        "pages": rows,
    }
    (OUT / "holdout-results.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps({key: value for key, value in output.items() if key != "pages"},
                     indent=2))


if __name__ == "__main__":
    main()
