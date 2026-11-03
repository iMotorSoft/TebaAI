"""Source-only inventory for the new V4 frozen-confirmation holdout.

No certifier is imported or executed here. This must run before annotation and
before any V4 evaluation.
"""
import json
from pathlib import Path

import pymupdf
from pymupdf4llm.helpers.document_layout import parse_document

OUT = Path(__file__).resolve().parent
SOURCE = "/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf"
PAGES = [
    13, 14, 15, 20,
    40, 54, 69, 71, 78,
    84, 92, 93, 94, 95, 96, 97, 98,
    108, 109,
    113, 114,
    125, 126, 127, 128,
    136, 137, 138, 139,
    164, 165,
    206, 207,
    226, 227,
]


def main():
    previous = json.loads(
        (OUT / "previous-holdout-page-inventory.json").read_text()
    )["opened_pages"]
    assert not set(PAGES) & set(previous), "holdout overlaps previously opened pages"
    assert len(PAGES) == len(set(PAGES)), "duplicate selected page"
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
                                    (span["block"], span["line"]) for span in line["spans"]
                                )),
                                "text": "".join(span["text"] for span in line["spans"]),
                                "styles": sorted({
                                    (span["font"], span["size"]) for span in line["spans"]
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
                f"{box['index']} {box['class']} y={box['bbox'][1]:.1f}-{box['bbox'][3]:.1f} "
                f"x={box['bbox'][0]:.1f}-{box['bbox'][2]:.1f} "
                + " / ".join(line["text"] for line in box["lines"])
            )
    (OUT / "holdout-source-review.txt").write_text("\n".join(review) + "\n")
    print(len(rows), "pages inventoried")


if __name__ == "__main__":
    main()
