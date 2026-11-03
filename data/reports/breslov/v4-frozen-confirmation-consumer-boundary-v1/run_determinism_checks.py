"""Permutation and repeated-run stability checks for the sealed pages."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "SrvRestAstroLS_v1/backend"))

from modules.library.automatic_region_certification_v4 import (
    extract_pdf_region_certificates,
)

PDF = Path("/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf")
HERE = Path(__file__).resolve().parent
DEFINITION = json.loads((HERE / "holdout-definition.json").read_text())
PAGES = sorted(page["pdf_page"] for page in DEFINITION["pages"])


def by_page(result):
    return {page.provenance.pdf_page: page.to_dict() for page in result}


def main():
    baseline = by_page(extract_pdf_region_certificates(PDF, pages=PAGES))
    repeated = by_page(extract_pdf_region_certificates(PDF, pages=PAGES))
    reversed_order = by_page(
        extract_pdf_region_certificates(PDF, pages=list(reversed(PAGES)))
    )

    stability = {
        "pages": len(PAGES),
        "runs": 2,
        "identical": baseline == repeated,
    }
    permutation = {
        "pages": len(PAGES),
        "orders": ["sorted", "reversed"],
        "identical": baseline == reversed_order,
    }
    for page in PAGES:
        if baseline[page] != repeated[page]:
            stability.setdefault("mismatched_pages", []).append(page)
        if baseline[page] != reversed_order[page]:
            permutation.setdefault("mismatched_pages", []).append(page)

    (HERE / "stability-results.json").write_text(
        json.dumps(stability, indent=2) + "\n"
    )
    (HERE / "permutation-results.json").write_text(
        json.dumps(permutation, indent=2) + "\n"
    )
    print(json.dumps({"stability": stability, "permutation": permutation}, indent=2))
    raise SystemExit(
        0 if stability["identical"] and permutation["identical"] else 1
    )


if __name__ == "__main__":
    main()
