"""Collect every page opened by previous holdouts, development runs and goldens.

Source-only: this script never imports a certifier.
"""
import glob
import json
import os
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
BASE = ROOT / "data/reports/breslov"

EXPLICIT = [
    "automatic-region-provenance-certification-v1/holdout-definition.json",
    "automatic-region-provenance-certification-v1/holdout-annotations.json",
    "automatic-region-provenance-certification-v1/supporting-pages-results.json",
    "automatic-region-provenance-certification-v2/holdout-v2-definition.json",
    "automatic-region-provenance-certification-v2/development-pages.json",
    "automatic-region-provenance-certification-v2/development-boundary-checks.json",
    "automatic-region-provenance-certification-v2/v1-unsafe-certifications.json",
    "automatic-region-provenance-certification-v3/holdout-v3-definition.json",
    "automatic-region-provenance-certification-v3/development-pages.json",
    "automatic-region-provenance-certification-v3/cross-page-development-cases.json",
    "automatic-region-provenance-certification-v4/holdout-v4-definition.json",
    "automatic-region-provenance-certification-v4/holdout-v4-definition-first-open-invalid.json",
    "automatic-region-provenance-certification-v4/permutation-analysis.json",
    "automatic-region-provenance-certification-v4/stability-results.json",
]

PAGE_KEYS = {"pdf_page", "page"}
PAGE_LIST_KEYS = {"pages", "physical_pages"}


def visit(value, pages):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in PAGE_KEYS and isinstance(item, int):
                pages.add(item)
            elif key in PAGE_LIST_KEYS and isinstance(item, list):
                for entry in item:
                    if isinstance(entry, int):
                        pages.add(entry)
                    elif isinstance(entry, dict):
                        for page_key in PAGE_KEYS:
                            if isinstance(entry.get(page_key), int):
                                pages.add(entry[page_key])
                    else:
                        visit(entry, pages)
            else:
                visit(item, pages)
    elif isinstance(value, list):
        for item in value:
            visit(item, pages)


def collect(path):
    pages = set()
    try:
        visit(json.loads(path.read_text()), pages)
    except (ValueError, OSError):
        return pages
    return {page for page in pages if 1 <= page <= 284}


def main():
    inventory = {}
    for relative in EXPLICIT:
        path = BASE / relative
        for page in collect(path):
            inventory.setdefault(page, set()).add(str(path.relative_to(ROOT)))
    for path in sorted(glob.glob(str(BASE / "*/*.json"))):
        current = Path(path)
        if OUT in current.parents:
            continue
        name = current.name
        if not any(token in name for token in ("golden", "ocr", "annotation", "manual")):
            continue
        for page in collect(current):
            inventory.setdefault(page, set()).add(str(current.relative_to(ROOT)))
    payload = {
        "source_pdf_pages": 284,
        "opened_pages": sorted(inventory),
        "page_sources": {str(page): sorted(sources) for page, sources in sorted(inventory.items())},
    }
    (OUT / "previous-holdout-page-inventory.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    )
    print(len(payload["opened_pages"]), "previously opened pages")


if __name__ == "__main__":
    main()
