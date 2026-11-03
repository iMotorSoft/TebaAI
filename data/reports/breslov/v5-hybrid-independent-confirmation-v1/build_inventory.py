"""Build a source-only inventory for all physical pages (no certifier)."""
import json
from pathlib import Path

import pymupdf
from pymupdf4llm.helpers.document_layout import parse_document

OUT = Path(__file__).resolve().parent
SOURCE = "/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf"

def main():
    with pymupdf.open(SOURCE) as document:
        parsed = parse_document(document, pages=list(range(len(document))), use_ocr=False)
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
                                "text": "".join(span["text"] for span in line["spans"]),
                            }
                            for line in box.textlines or []
                        ],
                    }
                    for index, box in enumerate(page.boxes)
                ],
            })
    (OUT / "all-pages-source-inventory.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
    print(len(rows), "pages")

if __name__ == "__main__":
    main()
