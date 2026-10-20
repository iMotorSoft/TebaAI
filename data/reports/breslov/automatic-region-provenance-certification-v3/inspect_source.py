"""Source-only inventory; no certifier imported or executed."""
import json
from pathlib import Path
import pymupdf
from pymupdf4llm.helpers.document_layout import parse_document

OUT=Path(__file__).resolve().parent
SOURCE='/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf'
PAGES=[25,26,27,28,45,46,47,48,58,59,64,65,73,74,85,86,87,88,171,172,173,174,215,216,217,218,241,242,243,244]

def main():
    with pymupdf.open(SOURCE) as doc:
        parsed=parse_document(doc,pages=[n-1 for n in PAGES],use_ocr=False)
        rows=[]
        for p in parsed.pages:
            rows.append({'page':p.page_number,'width':p.width,'height':p.height,'boxes':[
                {'index':i,'class':b.boxclass,'bbox':[b.x0,b.y0,b.x1,b.y1],
                 'lines':[{'bbox':list(l['bbox']),'ids':list(dict.fromkeys((s['block'],s['line']) for s in l['spans'])),
                           'text':''.join(s['text'] for s in l['spans']),
                           'styles':sorted(set((s['font'],s['size']) for s in l['spans']))} for l in b.textlines or []]}
                for i,b in enumerate(p.boxes)]})
        (OUT/'holdout-source-inventory.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
        (OUT/'holdout-source-review.txt').write_text('\n'.join(f"PAGE {p['page']}\n"+'\n'.join(
            f"{b['index']} {b['class']} y={b['bbox'][1]:.1f}-{b['bbox'][3]:.1f} x={b['bbox'][0]:.1f}-{b['bbox'][2]:.1f} "+' / '.join(l['text'] for l in b['lines']) for b in p['boxes']) for p in rows)+'\n')
if __name__=='__main__':main()
