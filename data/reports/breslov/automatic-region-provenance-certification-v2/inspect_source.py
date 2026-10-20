"""Pre-evaluation source inventory only: does not import either certifier."""
import json
from pathlib import Path
import pymupdf
from pymupdf4llm.helpers.document_layout import parse_document

OUT = Path(__file__).resolve().parent
SOURCE = '/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf'
PAGES = [21,22,23,24,41,42,43,61,62,63,81,82,83,161,162,163,211,212]

def main():
    with pymupdf.open(SOURCE) as doc:
        parsed = parse_document(doc, pages=[p-1 for p in PAGES], use_ocr=False)
        data=[]
        for p in parsed.pages:
            boxes=[]
            for i,b in enumerate(p.boxes):
                lines=[{'bbox':list(l['bbox']), 'ids':list(dict.fromkeys((s['block'],s['line']) for s in l['spans'])), 'text': ''.join(s['text'] for s in l['spans']), 'sizes':sorted(set(s['size'] for s in l['spans']))} for l in (b.textlines or [])]
                boxes.append({'index':i,'class':b.boxclass,'bbox':[b.x0,b.y0,b.x1,b.y1],'lines':lines})
            data.append({'page':p.page_number,'boxes':boxes})
        (OUT/'holdout-source-inventory.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
        (OUT/'holdout-source-review.txt').write_text('\n'.join(f"PAGE {p['page']}\n"+'\n'.join(f"{b['index']} {b['class']} {b['bbox']} | "+ ' / '.join(l['text'] for l in b['lines']) for b in p['boxes']) for p in data))
if __name__ == '__main__':
    main()
