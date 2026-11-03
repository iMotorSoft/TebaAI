"""Source-only inventory for the V5 safety holdout.

No certifier (V4 or V5) is imported or executed. Selection is fixed before
annotation. The holdout is intentionally safety-only: the development set
already contains the proven cross-page positives.
"""
import json
from pathlib import Path

import pymupdf
from pymupdf4llm.helpers.document_layout import parse_document

OUT = Path(__file__).resolve().parent
SOURCE = "/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf"
PAGES = [
    121, 129, 135, 142, 148, 155, 160, 181,
    186, 187, 189, 192, 197, 198, 199, 214,
    222, 224, 228, 232, 236, 245, 246, 247,
    251, 252, 253, 254, 183, 239, 240, 255,
]
CROSS_PAGE_NEGATIVES = [
    [186, 187, 108, 109],
    [197, 198, 137, 138],
    [198, 199, 139, 140],
    [245, 246, 2, 3],
    [246, 247, 3, 4],
    [251, 252, 11, 12],
    [252, 253, 13, 14],
    [253, 254, 18, 19],
]


def main():
    previous = set(json.loads(
        (OUT / "previous-opened-pages.json").read_text()
    )["opened_pages"])
    development = set(json.loads(
        (OUT / "development-opened-pages.json").read_text()
    )["pages"])
    assert len(PAGES) == len(set(PAGES)), "duplicate selected page"
    assert not set(PAGES) & previous, "holdout overlaps previously opened pages"
    assert not set(PAGES) & development, "holdout overlaps development pages"
    with pymupdf.open(SOURCE) as document:
        parsed = parse_document(
            document, pages=[number - 1 for number in PAGES], use_ocr=False
        )
        rows = []
        for page in parsed.pages:
            rows.append({
                "page": page.page_number,
                "width": page.width,
                "height": page.height,
                "boxes": [
                    {
                        "index": index,
                        "class": box.boxclass,
                        "bbox": [box.x0, box.y0, box.x1, box.y1],
                        "lines": [
                            {
                                "bbox": list(line["bbox"]),
                                "ids": list(dict.fromkeys(
                                    (span["block"], span["line"])
                                    for span in line["spans"]
                                )),
                                "text": "".join(
                                    span["text"] for span in line["spans"]
                                ),
                                "styles": sorted({
                                    (span["font"], span["size"])
                                    for span in line["spans"]
                                }),
                            }
                            for line in box.textlines or []
                        ],
                    }
                    for index, box in enumerate(page.boxes)
                ],
            })
    (OUT / "holdout-source-inventory.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n"
    )
    review = []
    for page in rows:
        review.append(f"PAGE {page['page']}")
        for box in page["boxes"]:
            review.append(
                f"{box['index']} {box['class']} "
                f"y={box['bbox'][1]:.1f}-{box['bbox'][3]:.1f} "
                f"x={box['bbox'][0]:.1f}-{box['bbox'][2]:.1f} "
                + " / ".join(line["text"] for line in box["lines"])
            )
    (OUT / "holdout-source-review.txt").write_text("\n".join(review) + "\n")
    selection = {
        "version": "automatic-region-provenance-certification-v5-holdout-v1",
        "source_sha256": "440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a",
        "physical_pages": PAGES,
        "page_count": len(PAGES),
        "scope": "SAFETY_ONLY_FRESH",
        "cross_page_positives": [],
        "cross_page_negatives": CROSS_PAGE_NEGATIVES,
        "cross_page_negative_count": len(CROSS_PAGE_NEGATIVES),
        "cross_page_positive_source": "development-regression-only",
        "notes": (
            "No fresh cross-page positives remain: every source-only true "
            "continuation candidate was opened during V4/V5 development. The "
            "sealed holdout therefore tests safety, column lineage, full-width "
            "note continuations, one-unit/two-column notes and no-note pages."
        ),
    }
    (OUT / "holdout-selection.json").write_text(
        json.dumps(selection, ensure_ascii=False, indent=2) + "\n"
    )
    print(len(rows), "pages inventoried;", len(CROSS_PAGE_NEGATIVES), "negative pairs")


if __name__ == "__main__":
    main()
