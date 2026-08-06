#!/usr/bin/env python3
"""Generate a tiny authorized PDF fixture; the PDF itself is never versioned."""
from __future__ import annotations
import argparse, hashlib
from pathlib import Path
import pymupdf as fitz

SPANISH = "FUENTE DOCUMENTAL DE PRUEBA\n\nTexto español para validar la ingesta page-first y el reﬁ namiento.\nReferencia impresa: Salmos 16:1.\n1 Nota editorial breve."
HEBREW = "טֶקְסְט עִבְרִי לִבְדִיקָה\n\nContenido mixto preservado con niqqud."
V2_SPANISH = "FUENTE DOCUMENTAL DE PRUEBA V2\n\nTexto español para validar el flujo premium del Gestor.\nReferencia impresa: Salmos 16:1.\n1 Nota editorial breve."
V2_HEBREW = "לִיקּוּטֵי מוֹהֲרַ״ן\n\nContenido hebreo con niqqud para validar RTL local."
V3_SPANISH = "FUENTE DOCUMENTAL DE PRUEBA V3\n\nTexto español para validar retry y cancelación del Gestor.\nReferencia impresa: Salmos 16:1.\n1 Nota editorial breve."
V3_HEBREW = "טֶקְסְט עִבְרִי לִבְדִיקָה v3\n\nContenido mixto preservado con niqqud."
V4_SPANISH = "FUENTE DOCUMENTAL DE PRUEBA V4\n\nTexto español para validar cancelación y reintento del Gestor.\nReferencia impresa: Salmos 16:1.\n1 Nota editorial breve."
V4_HEBREW = "טֶקְסְט עִבְרִי לִבְדִיקָה v4\n\nContenido mixto preservado con niqqud."

def generate(path: Path, variant: str = "v1") -> dict:
    table = {
        "v1": (SPANISH, HEBREW),
        "v2": (V2_SPANISH, V2_HEBREW),
        "v3": (V3_SPANISH, V3_HEBREW),
        "v4": (V4_SPANISH, V4_HEBREW),
    }
    if variant == "unique":
        # Non-deterministic content: unique sha per run so the E2E always
        # gets a fresh idempotency key (one active job per scope+sha).
        import uuid
        marker = f"\n\nRun marker: {uuid.uuid4().hex}"
        spanish = f"{V4_SPANISH}{marker}"
        hebrew = f"{V4_HEBREW}{marker}"
    else:
        spanish, hebrew = table[variant]
    doc=fitz.open(); doc.set_metadata({'title':'TebaAI E2E Fixture','author':'Teba AI','creationDate':'D:20260805000000Z','modDate':'D:20260805000000Z'})
    p=doc.new_page(width=595,height=842); p.insert_textbox(fitz.Rect(72,72,523,770),spanish,fontsize=12,fontname='helv')
    p=doc.new_page(width=595,height=842)
    hebrew_font=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    if not hebrew_font.is_file(): raise RuntimeError('Authorized fixture font is unavailable')
    p.insert_font(fontname='FixtureHebrew',fontfile=str(hebrew_font))
    p.insert_textbox(fitz.Rect(72,72,523,770),hebrew,fontsize=12,fontname='FixtureHebrew')
    doc.new_page(width=595,height=842)
    path.parent.mkdir(parents=True,exist_ok=True); doc.save(path,garbage=4,deflate=True,no_new_id=True); doc.close()
    sha=hashlib.sha256(path.read_bytes()).hexdigest()
    return {'filename':path.name,'sha256':sha,'pages':3,'size_bytes':path.stat().st_size,'variant':variant}

def main():
    p=argparse.ArgumentParser(); p.add_argument('output',type=Path); p.add_argument('--variant',default='v1',choices=['v1','v2','v3','v4','unique']); args=p.parse_args(); print(generate(args.output,args.variant))
if __name__=='__main__': main()
