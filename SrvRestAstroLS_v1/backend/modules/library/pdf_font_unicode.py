"""Source-backed Unicode recovery for exact, audited embedded font programs.

Some PDFs render Hebrew correctly but omit ToUnicode on Identity-H fonts.
Never guess by a font name or glyph-ID range. An exact font-program checksum
selects a reviewed CID map. Only the in-memory document is amended; the input
PDF remains byte-for-byte unchanged and PyMuPDF4LLM remains the extractor.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def profiles() -> dict:
    return json.loads((Path(__file__).parent / 'data/pdf_font_unicode_profiles.json').read_text())['fonts']


def unicode_cmap(mapping: dict[str, str]) -> bytes:
    entries = sorted((int(cid), text) for cid, text in mapping.items())
    if any(not 0 <= cid <= 65535 or not text for cid, text in entries):
        raise ValueError('Invalid audited CID map')
    parts = ['/CIDInit /ProcSet findresource begin 12 dict begin begincmap',
             '/CIDSystemInfo << /Registry (TebaAI) /Ordering (Unicode) /Supplement 0 >> def',
             '/CMapName /TebaAI-Audited-Font def /CMapType 2 def',
             '1 begincodespacerange <0000> <FFFF> endcodespacerange']
    for start in range(0, len(entries), 100):
        batch = entries[start:start + 100]
        parts.append(f'{len(batch)} beginbfchar')
        parts.extend(f'<{cid:04X}> <{text.encode("utf-16-be").hex().upper()}>' for cid, text in batch)
        parts.append('endbfchar')
    parts.append('endcmap CMapName currentdict /CMap defineresource pop end end')
    return '\n'.join(parts).encode('ascii')


def repair_missing_font_unicode_maps(document) -> list[dict]:
    if getattr(document, '_tebaai_unicode_fonts_prepared', False):
        return []
    known = profiles()
    found = {}
    for page in document:
        for font in page.get_fonts():
            found[font[0]] = font
    changes = []
    for xref, font in sorted(found.items()):
        if font[2] != 'Type0' or font[5] != 'Identity-H':
            continue
        if document.xref_get_key(xref, 'ToUnicode')[0] != 'null':
            continue
        program = document.extract_font(xref)[3]
        fingerprint = hashlib.sha256(program).hexdigest()
        profile = known.get(fingerprint)
        if not profile:
            continue
        cmap_xref = document.get_new_xref()
        document.update_object(cmap_xref, '<<>>')
        document.update_stream(cmap_xref, unicode_cmap(profile['mappings']))
        document.xref_set_key(xref, 'ToUnicode', f'{cmap_xref} 0 R')
        changes.append({'font_program_sha256': fingerprint, 'mapped_cids': len(profile['mappings']),
                        'font_xref': xref, 'source_pdf_modified': False})
    document._tebaai_unicode_fonts_prepared = True
    return changes
