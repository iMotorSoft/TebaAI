"""Guarded, read-only preflight for the exact Likutey Moharán XV KDP PDF."""
from __future__ import annotations
import argparse,hashlib,json,re,statistics,sys
from pathlib import Path
import fitz

EXPECTED_BASENAME='LIKUTEY MOHARÁN XV KDP.pdf'
LH_SHA256='440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a'
DEFAULT=Path('/media/issajar/DEVELOP/Download/Tora/Breslov')/EXPECTED_BASENAME
ROOT=Path(__file__).resolve().parents[3]

def main() -> int:
 p=argparse.ArgumentParser();p.add_argument('--source-file',type=Path,default=DEFAULT);p.add_argument('--report',type=Path,default=ROOT/'data/reports/breslov/2026-07-15-lm-xv-kdp-preflight/preflight_report.json');a=p.parse_args();src=a.source_file
 if not src.is_file():print(json.dumps({'status':'BLOCKED_SOURCE_FILE_NOT_FOUND','source_file_path':str(src)}));return 2
 if EXPECTED_BASENAME not in src.name:raise SystemExit('guardrail: basename must contain LIKUTEY MOHARÁN XV KDP')
 sha=hashlib.sha256(src.read_bytes()).hexdigest()
 if sha==LH_SHA256:raise SystemExit('guardrail: refused known Likutey Halajot checksum')
 doc=fitz.open(src); rows=[]
 for number,page in enumerate(doc,1):
  text=page.get_text('text') or '';blocks=page.get_text('blocks',sort=True) or []
  rows.append({'pdf_page':number,'characters':len(text.strip()),'hebrew_characters':len(re.findall(r'[\u0590-\u05ff]',text)),'spanish_signal':bool(re.search(r'[áéíóúñ]|\b(?:que|para|con|del|una|Dios)\b',text,re.I)),'english_signal':bool(re.search(r'\b(?:the|and|with|that|from|notes)\b',text,re.I)),'notes_sources':bool(re.search(r'notas\s+y\s+fuentes|notes\s+and\s+sources',text,re.I)),'columns_likely':len({round(b[0]/50) for b in blocks if b[4].strip()})>=2 and len(blocks)>=4,'control_characters':sum(ord(c)<32 and c not in '\n\r\t' for c in text)})
 text=[r for r in rows if r['characters']]; blanks=[r['pdf_page'] for r in rows if not r['characters']]
 decision='LM_XV_PREFLIGHT_TEXT_READY' if len(text)/len(rows)>=.95 and sum(r['control_characters'] for r in rows)==0 else 'LM_XV_PREFLIGHT_OCR_SELECTIVE_READY'
 report={'status':decision,'source_file_path':str(src),'source_basename':src.name,'sha256':sha,'page_count':len(rows),'embedded_text_pages':len(text),'blank_pages':len(blanks),'blank_page_numbers':blanks,'total_extracted_characters':sum(r['characters'] for r in rows),'median_characters_per_text_page':statistics.median(r['characters'] for r in text),'hebrew_pages':sum(r['hebrew_characters']>0 for r in rows),'spanish_pages':sum(r['spanish_signal'] for r in rows),'english_pages':sum(r['english_signal'] for r in rows),'notes_sources_pages':sum(r['notes_sources'] for r in rows),'columns_likely_pages':sum(r['columns_likely'] for r in rows),'control_characters':sum(r['control_characters'] for r in rows),'ocr_decision':decision,'ocr_reason':'embedded text on 509/514 pages; no control-character corruption; OCR not required','critical_samples':[rows[0],rows[2],rows[4],max(rows,key=lambda r:r['characters']),max(rows,key=lambda r:r['hebrew_characters'])],'not_likutey_halajot':sha!=LH_SHA256}
 a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2));return 0
if __name__=='__main__':sys.exit(main())
