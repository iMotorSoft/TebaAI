"""Build pre-run contracts for the V5 hybrid independent confirmation gate.

Source-only. No certifier is imported or executed. Every page/contract is fixed
before the first V5 opening.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "SrvRestAstroLS_v1/backend"))
from modules.library.annotation_preseal_validation import canonical_document

OUT = Path(__file__).resolve().parent
SOURCE = "/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf"
SOURCE_SHA = "440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a"

# Frozen pre-gate inventory: 198 pages opened by prior work, 86 unseen.
OPENED_RANGES = [
    "2", "13-18", "20-28", "30", "32", "34", "40-43", "45-52", "54-71",
    "73-78", "80-98", "100", "104-114", "120-133", "135-140", "142-143",
    "148-151", "153-155", "160-181", "183-187", "189-190", "192", "194-195",
    "197-200", "205-208", "211-212", "214-247", "249-255",
]


def expand(ranges):
    pages = set()
    for value in ranges:
        if "-" in value:
            start, end = (int(part) for part in value.split("-"))
            pages.update(range(start, end + 1))
        else:
            pages.add(int(value))
    return sorted(pages)


OPENED = expand(OPENED_RANGES)
UNSEEN = [page for page in range(1, 285) if page not in set(OPENED)]
# Page 1 is in the frozen unseen inventory but was opened by the V5 consumer
# test (test_consumer_region_certificates_v5.py). It is therefore not virgin.
VIRGIN_PAGES = [page for page in UNSEEN if page != 1]

# Part B: true continuations previously observed by an earlier certifier gate
# but never used to design, debug, test or select V5 proofs/thresholds.
ELIGIBLE_B = [
    {"from": 42, "to": 43, "note": 7, "prior_observation": "V2 certifier holdout"},
    {"from": 60, "to": 61, "note": 49, "prior_observation": "V4/V2 certifier holdouts"},
    {"from": 64, "to": 65, "note": 58, "prior_observation": "V3 certifier holdout"},
    {"from": 70, "to": 71, "note": 74, "prior_observation": "V1/V4 certifier holdouts"},
    {"from": 73, "to": 74, "note": 86, "prior_observation": "V3 certifier holdout"},
    {"from": 104, "to": 105, "note": 7, "prior_observation": "V4 certifier holdout"},
    {"from": 122, "to": 123, "note": 12, "prior_observation": "V4 certifier holdout"},
    {"from": 123, "to": 124, "note": 20, "prior_observation": "V4 certifier holdout"},
    {"from": 130, "to": 131, "note": 44, "prior_observation": "V1/V4 certifier holdouts"},
    {"from": 139, "to": 140, "note": 71, "prior_observation": "V4 frozen confirmation / V1 holdout"},
    {"from": 149, "to": 150, "note": 8, "prior_observation": "V4 certifier holdout"},
    {"from": 150, "to": 151, "note": 16, "prior_observation": "V4 certifier holdout"},
]

# Explicitly investigated from the blocked gate. Each has at least one page that
# was never previously opened, or was opened during V5 development.
NAMED_CANDIDATES = [
    {"from": 44, "to": 45, "note": 12, "classification": "ONLY_PREVIOUSLY_OBSERVED",
     "eligible": False, "reason": "MIXED_VIRGINITY: page 44 never previously opened"},
    {"from": 78, "to": 79, "note": 101, "classification": "ONLY_PREVIOUSLY_OBSERVED",
     "eligible": False,
     "reason": "MIXED_VIRGINITY and inline next marker 102, structurally ambiguous"},
    {"from": 133, "to": 134, "note": 51, "classification": "USED_TO_DEBUG_V5",
     "eligible": False, "reason": "page 133 is in the V5 development probe set"},
    {"from": 140, "to": 141, "note": 75, "classification": "ONLY_PREVIOUSLY_OBSERVED",
     "eligible": False, "reason": "MIXED_VIRGINITY: page 141 never previously opened"},
    {"from": 210, "to": 211, "note": 28, "classification": "ONLY_PREVIOUSLY_OBSERVED",
     "eligible": False, "reason": "MIXED_VIRGINITY: page 210 never previously opened"},
]

DEV_POSITIVES = [
    {"from": 206, "to": 207, "note": 5, "expected": "LINK"},
    {"from": 56, "to": 57, "note": 36, "expected": "LINK"},
    {"from": 167, "to": 168, "note": 66, "expected": "LINK"},
    {"from": 16, "to": 17, "note": 1, "expected": "LINK"},
]
DEV_NEGATIVES = [
    {"from": 108, "to": 109, "note": 8, "expected": "NO_LINK"},
    {"from": 164, "to": 165, "note": 63, "expected": "NO_LINK"},
    {"from": 226, "to": 227, "note": 78, "expected": "NO_LINK"},
]

VIRGIN_PAIRS = [
    {"from": 156, "to": 157, "note": 34, "expected": "NO_LINK"},
    {"from": 157, "to": 158, "note": 37, "expected": "NO_LINK"},
    {"from": 209, "to": 210, "note": 22, "expected": "NO_LINK"},
]


def write(name, payload):
    (OUT / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    inventory = json.loads((OUT / "all-pages-source-inventory.json").read_text())
    canonical, errors = canonical_document(inventory)
    by_page = {page["page"]: page for page in inventory}

    write("previous-opened-pages.json", {
        "version": "v5-hybrid-independent-confirmation-v1-open-page-inventory",
        "source_pdf_pages": 284,
        "source_sha256": SOURCE_SHA,
        "opened_ranges": OPENED_RANGES,
        "opened_pages": OPENED,
        "opened_pages_count": len(OPENED),
        "unseen_pages": UNSEEN,
        "unseen_pages_count": len(UNSEEN),
        "virgin_pages": VIRGIN_PAGES,
        "virgin_pages_count": len(VIRGIN_PAGES),
        "note": "Inherited unchanged from the blocked V5 revalidation inventory.",
    })

    write("virgin-safety-set.json", {
        "version": "v5-hybrid-independent-confirmation-v1-virgin-safety",
        "source_sha256": SOURCE_SHA,
        "pages": VIRGIN_PAGES,
        "page_count": len(VIRGIN_PAGES),
        "selection": "ALL_NEVER_PREVIOUSLY_OPENED_PAGES_EXCEPT_PAGE_1_OPENED_BY_V5_CONSUMER_TEST",
        "no_positive_requirement": True,
        "mandatory_cross_page_pairs": VIRGIN_PAIRS,
        "expected_cross_page_links": 0,
        "note": "Safety only. Source adjudication found no true continuation among the three consecutive unseen note pairs.",
    })

    write("virgin-safety-contract.json", {
        "version": "v5-hybrid-independent-confirmation-v1-virgin-contract",
        "source_sha256": SOURCE_SHA,
        "pages": VIRGIN_PAGES,
        "absolute_zero": [
            "unsafe_false_certifications",
            "unsafe_false_provenance_certifications",
            "false_body_certifications",
            "false_cross_page_links",
            "false_editorial_completions",
            "false_identity_proven",
            "inconsistent_identity_state",
        ],
        "mandatory_pairs": VIRGIN_PAIRS,
        "coverage_thresholds": None,
        "majority_rules": None,
        "note": "No coverage or majority threshold exists in this contract.",
    })

    eligible = []
    for item in ELIGIBLE_B:
        pair = dict(item)
        pair["classification"] = "ONLY_PREVIOUSLY_OBSERVED"
        pair["eligible"] = True
        pair["v5_influence"] = "NONE_DETECTED"
        pair["expected"] = "LINK"
        pair["terminal_tail"] = canonical[item["from"]][-1]["parts"][-1]["text"][-160:]
        pair["leading_head"] = canonical[item["to"]][0]["parts"][0]["text"][:160]
        pair["terminal_note"] = canonical[item["from"]][-1]["note_number"]
        pair["leading_note"] = canonical[item["to"]][0]["note_number"]
        next_units = [u["note_number"] for u in canonical[item["to"]]
                      if u["note_number"] is not None]
        pair["next_explicit_marker"] = next_units[1] if len(next_units) > 1 else None
        eligible.append(pair)

    write("eligible-positive-set.json", {
        "version": "v5-hybrid-independent-confirmation-v1-eligible-positives",
        "source_sha256": SOURCE_SHA,
        "selection_rule": (
            "Source-adjudicated true continuation; both pages previously opened; "
            "neither page used to design, debug, test, tune or hold out V5."
        ),
        "pairs": eligible,
        "pair_count": len(eligible),
        "named_candidates": NAMED_CANDIDATES,
    })

    write("positive-confirmation-contract.json", {
        "version": "v5-hybrid-independent-confirmation-v1-positive-contract",
        "source_sha256": SOURCE_SHA,
        "pairs": [
            {key: pair[key] for key in
             ("from", "to", "note", "classification", "eligible", "expected",
              "prior_observation", "terminal_tail", "leading_head",
              "next_explicit_marker")}
            for pair in eligible
        ],
        "expected_links": len(eligible),
        "minimum_correct_links": 3,
        "no_post_output_label_change": True,
    })

    write("development-regression-contract.json", {
        "version": "v5-hybrid-independent-confirmation-v1-development-contract",
        "source_sha256": SOURCE_SHA,
        "positive": DEV_POSITIVES,
        "negative": DEV_NEGATIVES,
        "expected_result": "7/7",
        "evidence_class": "DEVELOPMENT_REGRESSION_ONLY",
        "note": "206->207 note 5 is a definitive true continuation and expected LINK.",
    })

    write("candidate-positive-lineage.json", {
        "version": "v5-hybrid-independent-confirmation-v1-candidate-lineage",
        "source_sha256": SOURCE_SHA,
        "named_candidates": NAMED_CANDIDATES,
        "source_adjudication": {
            "44->45": "note 12 terminal 'El' continues 'tormento del alma...' (unmarked leading).",
            "78->79": "note 101 terminal 'Korbán' continues 'Pesaj...' with inline marker 102.",
            "133->134": "note 51 terminal 'destructoras' continues 'que gobiernan...'.",
            "140->141": "note 75 terminal 'La expansión' continues 'de los jasadim...'.",
            "210->211": "note 28 terminal 'cuya guía' continues 'moral instila...'.",
        },
        "eligible_positive_count": len(eligible),
        "eligible_positive_pairs": [[p["from"], p["to"]] for p in eligible],
        "canonical_errors": len(errors),
    })

    # Full page-level influence inventory.
    v5_dev = {16, 17, 56, 57, 108, 109, 132, 133, 153, 154, 164, 165, 167,
              168, 178, 179, 184, 185, 194, 195, 206, 207, 226, 227, 229,
              230, 234, 235, 237, 238, 249, 250}
    v5_holdout = {121, 129, 135, 142, 148, 155, 160, 181, 183, 186, 187, 189,
                  192, 197, 198, 199, 214, 222, 224, 228, 232, 236, 239, 240,
                  245, 246, 247, 251, 252, 253, 254, 255}
    v5_manual = set(range(205, 209)) | set(range(54, 60)) | set(range(165, 171)) | set(range(106, 112))
    v5_tests = {1}
    dev_regression = {16, 17, 56, 57, 167, 168, 206, 207}
    prior_v = {
        "V1_HOLDOUT": {70, 80, 90, 100, 110, 120, 130, 140, 150, 180, 190, 200},
        "V2_HOLDOUT": {21, 22, 23, 24, 41, 42, 43, 61, 62, 63, 81, 82, 83, 161, 162, 163, 211, 212},
        "V3_HOLDOUT": {25, 26, 27, 28, 45, 46, 47, 48, 58, 59, 64, 65, 73, 74, 85, 86, 87, 88, 171, 172, 173, 174, 215, 216, 217, 218, 241, 242, 243, 244},
        "V4_HOLDOUT": {49, 50, 51, 52, 60, 66, 67, 68, 75, 76, 77, 89, 90, 91, 104, 105, 111, 112, 122, 123, 124, 130, 131, 149, 150, 151, 175, 176, 177, 219, 220, 221},
        "V4_FROZEN_CONFIRMATION_HOLDOUT": {13, 14, 15, 20, 40, 54, 69, 71, 78, 84, 92, 93, 94, 95, 96, 97, 98, 108, 109, 113, 114, 125, 126, 127, 128, 136, 137, 138, 139, 164, 165, 206, 207, 226, 227},
        "PRIOR_CERTIFIER_DEVELOPMENT": {55, 56, 57, 80, 140, 167, 168, 200},
    }
    rows = []
    for page in range(1, 285):
        if page in v5_holdout:
            classification, influence = "USED_IN_V5_HOLDOUT", "SEALED_V5_HOLDOUT"
        elif page in dev_regression:
            classification, influence = "USED_AS_V5_DEVELOPMENT_REGRESSION", "V5_DEVELOPMENT_REGRESSION"
        elif page in v5_dev or page in v5_manual:
            classification, influence = "USED_TO_DEBUG_V5", "V5_DEVELOPMENT_OR_MANUAL_REVIEW"
        elif page in v5_tests:
            classification, influence = "USED_IN_V5_TESTS", "V5_CONSUMER_TEST"
        else:
            prior_gates = [name for name, pages in prior_v.items() if page in pages]
            if prior_gates:
                classification = "ONLY_PREVIOUSLY_OBSERVED"
                influence = "NONE_DETECTED"
            elif page in OPENED:
                classification = "ONLY_PREVIOUSLY_OBSERVED"
                influence = "NONE_DETECTED"
            else:
                classification = "VIRGIN"
                influence = "NONE"
            rows_entry = {
                "page": page,
                "classification": classification,
                "v5_influence": influence,
                "previously_opened": page in OPENED,
                "prior_gate_observations": prior_gates,
            }
            rows.append(rows_entry)
            continue
        rows.append({
            "page": page,
            "classification": classification,
            "v5_influence": influence,
            "previously_opened": page in OPENED,
            "prior_gate_observations": [name for name, pages in prior_v.items() if page in pages],
        })
    write("v5-influence-inventory.json", {
        "version": "v5-hybrid-independent-confirmation-v1-influence-inventory",
        "source_sha256": SOURCE_SHA,
        "sources": [
            "automatic-region-provenance-certification-v1/holdout-definition.json",
            "automatic-region-provenance-certification-v1/holdout-annotations.json",
            "automatic-region-provenance-certification-v2/holdout-v2-definition.json",
            "automatic-region-provenance-certification-v2/development-pages.json",
            "automatic-region-provenance-certification-v3/holdout-v3-definition.json",
            "automatic-region-provenance-certification-v3/development-pages.json",
            "automatic-region-provenance-certification-v4/holdout-v4-definition.json",
            "automatic-region-provenance-certification-v4/development-v3-holdout.json",
            "v4-frozen-confirmation-consumer-boundary-v1/holdout-definition.json",
            "automatic-region-provenance-certification-v5/holdout-selection.json",
            "automatic-region-provenance-certification-v5/development-opened-pages.json",
            "v5-frozen-revalidation-v1/holdout-source-discovery.json",
            "tests/test_automatic_region_certification_v5.py",
            "tests/test_consumer_region_certificates_v5.py",
        ],
        "pages": rows,
        "summary": {
            "USED_IN_V5_HOLDOUT": sum(1 for r in rows if r["classification"] == "USED_IN_V5_HOLDOUT"),
            "USED_TO_DEBUG_V5": sum(1 for r in rows if r["classification"] == "USED_TO_DEBUG_V5"),
            "USED_IN_V5_TESTS": sum(1 for r in rows if r["classification"] == "USED_IN_V5_TESTS"),
            "USED_AS_V5_DEVELOPMENT_REGRESSION": sum(1 for r in rows if r["classification"] == "USED_AS_V5_DEVELOPMENT_REGRESSION"),
            "ONLY_PREVIOUSLY_OBSERVED": sum(1 for r in rows if r["classification"] == "ONLY_PREVIOUSLY_OBSERVED"),
            "VIRGIN": sum(1 for r in rows if r["classification"] == "VIRGIN"),
        },
    })

    print("contracts built:", len(eligible), "eligible positives,", len(VIRGIN_PAGES), "virgin pages")


if __name__ == "__main__":
    main()
