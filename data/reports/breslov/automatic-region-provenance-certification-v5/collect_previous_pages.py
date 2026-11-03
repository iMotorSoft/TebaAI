"""Collect every page opened by prior provenance evidence and manual reviews.

Source-only: no certifier is imported or executed. The goal is a conservative
exclusion set for the V5 sealed holdout, not a claim about unrelated reports.
"""
import glob
import json
import re
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
BASE = ROOT / "data/reports/breslov"

PAGE_KEYS = {"pdf_page", "page", "physical_page"}
PAGE_LIST_KEYS = {"pages", "physical_pages"}
NAME_TOKENS = ("holdout", "golden", "ocr", "annotation", "manual",
               "region-provenance", "region-certification", "source-inventory",
               "source-review", "development", "cross-page")

# Windows inspected manually while diagnosing the V4 frozen holdout.
MANUAL_WINDOWS = [(205, 208), (54, 59), (165, 170), (106, 111)]
EXPLICIT_FILES = [
    "v4-frozen-confirmation-consumer-boundary-v1/previous-holdout-page-inventory.json",
    "v4-frozen-confirmation-consumer-boundary-v1/holdout-definition.json",
    "v4-frozen-confirmation-consumer-boundary-v1/holdout-source-inventory.json",
]


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


def add_path(path, sources):
    pages = set()
    try:
        text = path.read_text(errors="ignore")
    except OSError:
        return
    if path.suffix == ".json":
        try:
            visit(json.loads(text), pages)
        except ValueError:
            return
    else:
        for match in re.finditer(
                r"(?:p[aá]g(?:ina)?\.?\s*|p\.\s*|page\s+)(\d{1,3})\b",
                text, re.I):
            pages.add(int(match.group(1)))
    for page in pages:
        if 1 <= page <= 284:
            sources.setdefault(page, set()).add(str(path.relative_to(ROOT)))


def main():
    sources = {}
    for relative in EXPLICIT_FILES:
        add_path(BASE / relative, sources)
    for directory in sorted(BASE.iterdir()):
        if not directory.is_dir() or directory == OUT:
            continue
        name = directory.name.lower()
        if not any(token in name for token in NAME_TOKENS):
            continue
        for pattern in ("*.json", "*.txt", "*.md"):
            for raw in glob.glob(str(directory / "**" / pattern), recursive=True):
                add_path(Path(raw), sources)
    for start, end in MANUAL_WINDOWS:
        for page in range(start, end + 1):
            sources.setdefault(page, set()).add("manual-source-review-window")
    pages = sorted(sources)
    payload = {
        "source_pdf_pages": 284,
        "opened_pages": pages,
        "unseen_pages": [page for page in range(1, 285) if page not in sources],
        "page_sources": {str(page): sorted(values)
                         for page, values in sorted(sources.items())},
        "manual_windows": MANUAL_WINDOWS,
    }
    (OUT / "previous-opened-pages.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    )
    print(len(pages), "opened pages;", len(payload["unseen_pages"]), "unseen")


if __name__ == "__main__":
    main()
