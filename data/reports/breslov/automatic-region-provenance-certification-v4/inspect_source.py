"""Source-only inventory for the V4 sealed holdout; no certifier imported or executed."""
import json
from pathlib import Path
import pymupdf
from pymupdf4llm.helpers.document_layout import parse_document

OUT=Path(__file__).resolve().parent
SOURCE='/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf'
PAGES=[49,50,51,52,60,66,67,68,75,76,77,89,90,91,104,105,111,112,122,123,124,
       130,131,149,150,151,175,176,177,219,220,221]

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
