#!/usr/bin/env python3
"""Generate a tiny authorized PDF fixture; the PDF itself is never versioned."""
from __future__ import annotations
import argparse, hashlib
from pathlib import Path
import pymupdf as fitz

SPANISH = "FUENTE DOCUMENTAL DE PRUEBA\n\nTexto español para validar la ingesta page-first y el reﬁ namiento.\nReferencia impresa: Salmos 16:1.\n1 Nota editorial breve."
HEBREW = "טֶקְסְט עִבְרִי לִבְדִיקָה\n\nContenido mixto preservado con niqqud."

def generate(path: Path) -> dict:
    doc=fitz.open(); doc.set_metadata({'title':'TebaAI E2E Fixture','author':'Teba AI','creationDate':'D:20260805000000Z','modDate':'D:20260805000000Z'})
    p=doc.new_page(width=595,height=842); p.insert_textbox(fitz.Rect(72,72,523,770),SPANISH,fontsize=12,fontname='helv')
    p=doc.new_page(width=595,height=842)
    hebrew_font=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    if not hebrew_font.is_file(): raise RuntimeError('Authorized fixture font is unavailable')
    p.insert_font(fontname='FixtureHebrew',fontfile=str(hebrew_font))
    p.insert_textbox(fitz.Rect(72,72,523,770),HEBREW,fontsize=12,fontname='FixtureHebrew')
    doc.new_page(width=595,height=842)
    path.parent.mkdir(parents=True,exist_ok=True); doc.save(path,garbage=4,deflate=True,no_new_id=True); doc.close()
    sha=hashlib.sha256(path.read_bytes()).hexdigest()
    return {'filename':path.name,'sha256':sha,'pages':3,'size_bytes':path.stat().st_size}

def main():
    p=argparse.ArgumentParser(); p.add_argument('output',type=Path); args=p.parse_args(); print(generate(args.output))
if __name__=='__main__': main()
