"""Determinism, page/box/line permutation and repeated-run checks for V5."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(ROOT / "SrvRestAstroLS_v1/backend"))
import pymupdf  # noqa: E402
from pymupdf4llm.helpers.document_layout import parse_document  # noqa: E402
from modules.library.automatic_region_certification_v5 import (  # noqa: E402
    certify_document,
    extract_pdf_region_certificates,
)

SOURCE = "/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf"
PAGES = [186, 187, 245, 246]


def signature(pages):
    rows = []
    for page in sorted(pages, key=lambda item: item.provenance.pdf_page):
        for cert in sorted(page.certificates, key=lambda item: item.region_id):
            rows.append([
                page.provenance.pdf_page,
                cert.region_id,
                cert.zone_type,
                cert.note_number,
                cert.provenance_status,
                cert.quality_status,
                cert.continuation_state,
                cert.continuation_status,
                cert.identity_state,
                sorted(cert.linked_region_ids),
                cert.editorial_unit_id,
                [proof.name + ":" + str(proof.passed) for proof in cert.identity_proof],
            ])
    return rows


def main():
    first = extract_pdf_region_certificates(SOURCE, pages=PAGES)
    second = extract_pdf_region_certificates(SOURCE, pages=PAGES)
    repeated_equal = signature(first) == signature(second)
    sha = hashlib.sha256(Path(SOURCE).read_bytes()).hexdigest()
    with pymupdf.open(SOURCE) as document:
        parsed = parse_document(
            document, pages=[number - 1 for number in PAGES], use_ocr=False
        )
        natives = {number: document[number - 1] for number in PAGES}
        baseline = certify_document(parsed, sha, native_pages=natives)
        shuffled = deepcopy(parsed)
        rng = random.Random(20261020)
        rng.shuffle(shuffled.pages)
        for page in shuffled.pages:
            rng.shuffle(page.boxes)
            for box in page.boxes:
                if box.textlines:
                    rng.shuffle(box.textlines)
        permuted = certify_document(shuffled, sha, native_pages=natives)
    permutation_equal = signature(baseline) == signature(permuted)
    output = {
        "status": "PASS" if repeated_equal and permutation_equal else "FAIL",
        "pages": PAGES,
        "repeated_run_equal": repeated_equal,
        "permutation_equal": permutation_equal,
        "regions": sum(len(page.certificates) for page in first),
        "signature_sha256": hashlib.sha256(
            json.dumps(signature(first), separators=(",", ":")).encode()
        ).hexdigest(),
    }
    (OUT / "determinism-results.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
