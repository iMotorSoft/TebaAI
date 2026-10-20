"""Regenerate SMALL raw-IR fixtures from the read-only real PDF, not Markdown.
Run in backend with uv run python <this file> [PDF]. Golden expectations live
separately and are never regenerated here. No OCR, decoder, or services.
"""
from pathlib import Path
import hashlib
import json
import sys
from copy import deepcopy
from dataclasses import asdict

from pymupdf4llm.helpers.document_layout import parse_document

ROOT = Path(__file__).resolve().parents[4]
SHA = '440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a'
DEFAULT_SOURCE = '/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf'


def source_layout(path):
    if hashlib.sha256(Path(path).read_bytes()).hexdigest() != SHA:
        raise ValueError('Wrong golden PDF hash')
    return parse_document(str(path), pages=[54, 55, 56, 166, 167], use_ocr=False)


def small_fixture(parsed):
    out = {'source_sha256': SHA, 'engine': 'PyMuPDF4LLM layout IR; OCR disabled', 'pages': []}
    for page in parsed.pages:
        # Fixture selection only, never productive layout/ordering rules.
        selection = {55: {7: [-1], 8: None, 9: None, 10: None, 11: None},
                     56: {10: [-2, -1], 11: None, 12: None, 13: None, 14: None},
                     57: {i: None for i, b in enumerate(page.boxes) if b.y0 >= 543},
                     168: {i: None for i, b in enumerate(page.boxes) if b.y0 >= 550},
                     167: {2: [1], 7: None, 10: None, **{i: None for i in range(11, 18)}}}[page.page_number]
        boxes = []
        for index, line_indices in selection.items():
            box = deepcopy(page.boxes[index])
            if line_indices is not None:
                box.textlines = [box.textlines[i] for i in line_indices]
                boxes_xy = [tuple(l['bbox']) for l in box.textlines]
                box.x0, box.y0 = min(b[0] for b in boxes_xy), min(b[1] for b in boxes_xy)
                box.x1, box.y1 = max(b[2] for b in boxes_xy), max(b[3] for b in boxes_xy)
            boxes.append(asdict(box))
        out['pages'].append({'page_number': page.page_number, 'width': page.width,
                             'height': page.height, 'boxes': boxes})
    return out


if __name__ == '__main__':
    fixture = small_fixture(source_layout(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SOURCE))
    def encode(value):
        return list(value)
    target = ROOT / 'SrvRestAstroLS_v1/backend/tests/fixtures/region_markdown_provenance_v1.json'
    target.write_text(json.dumps(fixture, default=encode, ensure_ascii=False, indent=2) + '\n')
