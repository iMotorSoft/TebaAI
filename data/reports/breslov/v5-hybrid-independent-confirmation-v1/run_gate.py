"""Single frozen-gate execution of V5 on Parts A, B and C."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "SrvRestAstroLS_v1/backend"))
from evaluator import source_audit  # Standalone evaluator; no certifier dependency.

OUT = Path(__file__).resolve().parent
SOURCE = "/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf"
SOURCE_SHA = "440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a"
TERMINAL = (".", "!", "?", "。", "！", "？")


def write(name, payload):
    (OUT / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def load(name):
    return json.loads((OUT / name).read_text())


def page_source(inventory, number):
    return next(page for page in inventory if page["page"] == number)


def line_keys(page):
    return {
        tuple(line["ids"][0]) if len(line["ids"]) == 1 else tuple(tuple(pair) for pair in line["ids"])
        for box in page["boxes"] for line in box["lines"]
    }


def flat_line_ids(page):
    result = set()
    for box in page["boxes"]:
        for line in box["lines"]:
            for identifier in line["ids"]:
                result.add(tuple(identifier))
    return result


def unit_text(unit):
    return "\n".join(part.source_text for part in unit.parts)


def separator_y(page):
    for box in page["boxes"]:
        for line in box["lines"]:
            if line["text"].replace("\ufffd", "").strip() in (
                    "Notas y Fuentes", "Notas y Fuentes:", "Notes and Sources"):
                return line["bbox"][1]
    return None


def certificate_rows(pages):
    rows = []
    for page in pages:
        units = {unit.region_id: unit for unit in page.provenance.units}
        for cert in page.certificates:
            unit = units.get(cert.region_id)
            rows.append({
                "pdf_page": page.provenance.pdf_page,
                "region_id": cert.region_id,
                "zone_type": cert.zone_type,
                "note_number": cert.note_number,
                "provenance_status": cert.provenance_status,
                "quality_status": cert.quality_status,
                "continuation_state": cert.continuation_state,
                "continuation_status": cert.continuation_status,
                "identity_state": cert.identity_state,
                "linked_region_ids": list(cert.linked_region_ids),
                "editorial_unit_id": cert.editorial_unit_id,
                "source_line_ids": [list(item) for item in cert.source_line_ids],
                "unit_text": unit_text(unit) if unit else None,
                "unit_end_reason": unit.end_reason if unit else None,
                "identity_proof": [
                    {"name": proof.name, "passed": proof.passed,
                     "evidence": list(proof.evidence)}
                    for proof in cert.identity_proof
                ],
                "identity_evidence": list(cert.identity_evidence),
            })
    return rows


def main():
    from modules.library.automatic_region_certification_v5 import extract_pdf_region_certificates

    assert hashlib.sha256(Path(SOURCE).read_bytes()).hexdigest() == SOURCE_SHA
    inventory = load("all-pages-source-inventory.json")
    from modules.library.annotation_preseal_validation import canonical_document
    canonical, canonical_errors = canonical_document(inventory)

    virgin = load("virgin-safety-set.json")
    eligible = load("eligible-positive-set.json")
    development = load("development-regression-contract.json")

    virgin_pages = extract_pdf_region_certificates(SOURCE, pages=virgin["pages"])
    virgin_rows = certificate_rows(virgin_pages)
    virgin_metrics, virgin_violations, virgin_links = source_audit(
        virgin_pages, virgin_rows, inventory, canonical, part="A")
    virgin_pair_results = []
    for pair in virgin["mandatory_pairs"]:
        source = next((row for row in virgin_rows
                       if row["pdf_page"] == pair["from"]
                       and row["note_number"] == pair["note"]), None)
        linked = bool(source and source["linked_region_ids"])
        virgin_pair_results.append({**pair, "linked": linked, "ok": not linked})
        if linked:
            virgin_metrics["false_cross_page_links"] += 1
    virgin_output = {
        "part": "A",
        "status": "PASS" if (
            not virgin_violations
            and all(item["ok"] for item in virgin_pair_results)
            and all(value == 0 for key, value in virgin_metrics.items()
                    if key not in ("valid_cross_page_relations", "missed_true_links"))
        ) else "FAIL",
        "pages": len(virgin["pages"]),
        "regions": len(virgin_rows),
        "metrics": virgin_metrics,
        "mandatory_pairs": virgin_pair_results,
        "linked_pairs": virgin_links,
        "violations": virgin_violations[:20],
        "certificates": virgin_rows,
    }
    write("virgin-safety-results.json", virgin_output)

    eligible_pages = sorted({page for pair in eligible["pairs"]
                             for page in (pair["from"], pair["to"])})
    positive_pages = extract_pdf_region_certificates(SOURCE, pages=eligible_pages)
    positive_rows = certificate_rows(positive_pages)
    by_key = {(row["pdf_page"], row["region_id"]): row for row in positive_rows}
    positive_metrics = {
        "expected_links": len(eligible["pairs"]),
        "correct_links": 0,
        "missed_links": 0,
        "false_identity_state": 0,
        "wrong_target_links": 0,
    }
    positive_results = []
    for pair in eligible["pairs"]:
        candidates = [
            row for row in positive_rows
            if row["pdf_page"] == pair["from"]
            and row["note_number"] == pair["note"]
            and row["linked_region_ids"]
        ]
        ok = False
        detail = None
        if len(candidates) == 1:
            source = candidates[0]
            target = by_key.get((pair["to"], source["linked_region_ids"][0]))
            ok = bool(
                source["identity_state"] == "IDENTITY_PROVEN"
                and source["continuation_state"] == "CONTINUES_NEXT_PAGE"
                and target
                and target["pdf_page"] == pair["to"]
                and target["note_number"] == pair["note"]
                and target["identity_state"] == "IDENTITY_PROVEN"
                and target["editorial_unit_id"] == source["editorial_unit_id"]
            )
            detail = {
                "from": pair["from"], "to": pair["to"], "note": pair["note"],
                "identity_state": source["identity_state"],
                "linked_page": target["pdf_page"] if target else None,
                "linked_note": target["note_number"] if target else None,
                "same_editorial_id": bool(
                    target and target["editorial_unit_id"] == source["editorial_unit_id"]),
                "proofs": [proof["name"] for proof in source["identity_proof"] if proof["passed"]],
            }
            if not ok:
                positive_metrics["wrong_target_links"] += 1
        else:
            detail = {
                "from": pair["from"], "to": pair["to"], "note": pair["note"],
                "identity_states": sorted({
                    row["identity_state"] for row in positive_rows
                    if row["pdf_page"] == pair["from"]
                    and row["note_number"] == pair["note"]
                }),
                "linked_candidates": len(candidates),
            }
        if ok:
            positive_metrics["correct_links"] += 1
        else:
            positive_metrics["missed_links"] += 1
        positive_results.append({**pair, "ok": ok, "detail": detail})
    false_proven = [
        row for row in positive_rows
        if row["identity_state"] == "IDENTITY_PROVEN"
        and not row["linked_region_ids"]
    ]
    positive_metrics["false_identity_state"] = len(false_proven)
    positive_output = {
        "part": "B",
        "status": "PASS" if (
            positive_metrics["correct_links"] >= 3
            and positive_metrics["correct_links"] > 0
            and positive_metrics["false_identity_state"] == 0
        ) else "BLOCKED",
        "pages": len(eligible_pages),
        "regions": len(positive_rows),
        "metrics": positive_metrics,
        "pairs": positive_results,
        "certificates": positive_rows,
    }
    write("untuned-positive-results.json", positive_output)

    development_pages_list = sorted({
        page for item in development["positive"] + development["negative"]
        for page in (item["from"], item["to"])
    })
    development_pages = extract_pdf_region_certificates(
        SOURCE, pages=development_pages_list)
    development_rows = certificate_rows(development_pages)
    dev_by_page = {}
    for row in development_rows:
        dev_by_page.setdefault(row["pdf_page"], []).append(row)
    dev_results = []
    dev_ok = 0
    for item in development["positive"]:
        candidates = [
            row for row in dev_by_page.get(item["from"], [])
            if row["note_number"] == item["note"] and row["linked_region_ids"]
        ]
        ok = False
        detail = None
        if len(candidates) == 1:
            source = candidates[0]
            target = next((row for row in development_rows
                           if row["pdf_page"] == item["to"]
                           and row["region_id"] == source["linked_region_ids"][0]), None)
            ok = bool(
                source["identity_state"] == "IDENTITY_PROVEN"
                and source["continuation_state"] == "CONTINUES_NEXT_PAGE"
                and target
                and target["pdf_page"] == item["to"]
                and target["note_number"] == item["note"]
                and target["identity_state"] == "IDENTITY_PROVEN"
                and target["editorial_unit_id"] == source["editorial_unit_id"]
            )
            detail = {
                "identity_state": source["identity_state"],
                "linked_page": target["pdf_page"] if target else None,
                "linked_note": target["note_number"] if target else None,
            }
        else:
            detail = {"linked_candidates": len(candidates)}
        dev_results.append({**item, "ok": ok, "detail": detail})
        dev_ok += ok
    for item in development["negative"]:
        candidates = [
            row for row in dev_by_page.get(item["from"], [])
            if row["note_number"] == item["note"]
        ]
        linked = [row for row in candidates if row["linked_region_ids"]]
        proven = [row for row in candidates if row["identity_state"] == "IDENTITY_PROVEN"]
        ok = not linked and not proven
        dev_results.append({
            **item, "ok": ok,
            "detail": {
                "linked": [row["region_id"] for row in linked],
                "identity_states": sorted({row["identity_state"] for row in candidates}),
            },
        })
        dev_ok += ok
    development_output = {
        "part": "C",
        "status": "PASS" if dev_ok == 7 else "FAIL",
        "result": f"{dev_ok}/7",
        "cases": dev_results,
        "regions": len(development_rows),
    }
    write("development-regression-results.json", development_output)

    summary = {
        "source_sha256": SOURCE_SHA,
        "canonical_errors": canonical_errors,
        "part_a": {key: virgin_output[key] for key in ("status", "metrics", "pages", "regions")},
        "part_b": {key: positive_output[key] for key in ("status", "metrics", "pages", "regions")},
        "part_c": {key: development_output[key] for key in ("status", "result", "regions")},
    }
    write("gate-run-summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
