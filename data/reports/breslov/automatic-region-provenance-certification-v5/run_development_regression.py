"""Development regression for V5 positive identity.

These pages were opened during V4/V5 development and are not part of the
sealed safety holdout. They prove that the positive contract still links the
known true continuations.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "SrvRestAstroLS_v1/backend"))
from modules.library.automatic_region_certification_v5 import (  # noqa: E402
    extract_pdf_region_certificates,
)

OUT = Path(__file__).resolve().parent
SOURCE = "/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf"
POSITIVES = [
    (206, 207, 5),
    (56, 57, 36),
    (167, 168, 66),
    (16, 17, 1),
]
NEGATIVES = [(108, 109, 8), (164, 165, 63), (226, 227, 78)]


def main():
    pages = extract_pdf_region_certificates(
        SOURCE, pages=sorted({p for pair in POSITIVES + NEGATIVES for p in pair[:2]})
    )
    by_page = {page.provenance.pdf_page: page for page in pages}
    actual = {c.region_id: c for page in pages for c in page.certificates}
    rows = []
    failures = []
    for source, target, note in POSITIVES:
        certs = [
            c for c in by_page[source].certificates
            if c.note_number == note and c.linked_region_ids
        ]
        ok = False
        detail = None
        if len(certs) == 1:
            cert = certs[0]
            linked = actual.get(cert.linked_region_ids[0])
            ok = bool(
                cert.identity_state == "IDENTITY_PROVEN"
                and cert.continuation_state == "CONTINUES_NEXT_PAGE"
                and linked is not None
                and linked.pdf_page == target
                and linked.note_number == note
                and linked.editorial_unit_id == cert.editorial_unit_id
                and linked.identity_state == "IDENTITY_PROVEN"
            )
            detail = {
                "source": source, "target": target, "note": note,
                "identity_state": cert.identity_state,
                "linked_page": linked.pdf_page if linked else None,
                "linked_note": linked.note_number if linked else None,
                "same_editorial_id": bool(
                    linked and linked.editorial_unit_id == cert.editorial_unit_id
                ),
                "proofs": [str(proof) for proof in cert.identity_proof],
            }
        rows.append({"kind": "positive", "ok": ok, "detail": detail})
        if not ok:
            failures.append(detail or {"source": source, "target": target, "note": note})
    for source, target, note in NEGATIVES:
        candidates = [
            c for c in by_page[source].certificates
            if c.note_number == note
        ]
        linked = [
            c for c in candidates if c.linked_region_ids
        ]
        proven = [c for c in candidates if c.identity_state == "IDENTITY_PROVEN"]
        ok = not linked and not proven
        detail = {
            "source": source, "target": target, "note": note,
            "linked": [c.region_id for c in linked],
            "identity_states": sorted({c.identity_state for c in candidates}),
        }
        rows.append({"kind": "negative", "ok": ok, "detail": detail})
        if not ok:
            failures.append(detail)
    output = {
        "status": "PASS" if not failures else "FAIL",
        "positives": len(POSITIVES),
        "negatives": len(NEGATIVES),
        "failures": failures,
        "rows": rows,
    }
    (OUT / "development-regression-results.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps({key: value for key, value in output.items() if key != "rows"},
                     indent=2))


if __name__ == "__main__":
    main()
