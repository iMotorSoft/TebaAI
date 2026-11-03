"""Offline geometric reconstruction experiment; never used by ingestion.

Scope: horizontal, single-script lines within a PDF text paint operation.
Operation IDs are retained as structural boundaries: no vertical-only joining
of columns/cells. Mixed strong RTL/LTR lines and ambiguous marks fail closed
by returning their source sequence with diagnostics, never dropping characters.
This is NOT a complete inverse bidi algorithm or canonical Markdown extractor.
"""
from __future__ import annotations

from collections import Counter
import unicodedata


def hebrew(c: str) -> bool:
    return '\u05d0' <= c <= '\u05ea'


def reconstruct_line(chars: list, *, size: float) -> dict:
    """Chars are texttrace tuples (codepoint, glyph ID, origin, metric bbox).

    Same baseline: caller groups within 0.04 em of a fixed baseline (not
    transitive). Same word: explicit PDF spaces only; no synthetic insertion.
    Same line/run: same paint seqno and baseline. Hebrew bases follow decreasing
    x; Latin/digits follow increasing x. Marks attach only with a unique
    Hebrew owner: same origin (zero-advance marks) or strictly inside the base
    metric interval (positioned vowels). Edges/ties are unresolved, not guessed.
    No normalization: all input codepoints, including repeated marks, survive.
    """
    source = ''.join(chr(c[0]) for c in chars)
    diagnostics = []
    bases = [i for i, c in enumerate(chars) if not unicodedata.category(chr(c[0])).startswith('M')]
    rtl = any(hebrew(chr(chars[i][0])) for i in bases)
    if rtl and any(unicodedata.bidirectional(chr(chars[i][0])) in ('L', 'EN', 'AN') for i in bases):
        diagnostics.append('mixed_direction_requires_segment_reconstruction')
    if '\ufffd' in source:
        diagnostics.append('unmapped_unicode')
    owners = {}
    for i, char in enumerate(chars):
        if not unicodedata.category(chr(char[0])).startswith('M'):
            continue
        x, y = char[2]
        eligible = [j for j in bases if hebrew(chr(chars[j][0])) and abs(chars[j][2][1] - y) <= size * .04]
        exact = [j for j in eligible if abs(chars[j][2][0] - x) <= size * .002]
        inside = [j for j in eligible if chars[j][3][0] + size * .002 < x < chars[j][3][2] - size * .002]
        candidates = exact or inside
        if len(candidates) != 1:
            diagnostics.append(f'ambiguous_mark:{i}')
        else:
            owners[i] = candidates[0]
    # Mirrored delimiters need a source-level inverse-bidi model. Keep them
    # explicitly unresolved rather than replacing punctuation to look right.
    if rtl and any(unicodedata.mirrored(c) for c in source):
        diagnostics.append('mirrored_punctuation_requires_inverse_bidi')
    if diagnostics:
        logical = source
    else:
        ordered = sorted(bases, key=lambda i: ((-1 if rtl else 1) * chars[i][2][0], i))
        logical = ''.join(chr(chars[i][0]) + ''.join(chr(chars[j][0]) for j in owners if owners[j] == i)
                          for i in ordered)
    assert Counter(logical) == Counter(source), 'Codepoint conservation violated'
    return {'source': source, 'text': logical, 'diagnostics': diagnostics,
            'mark_owners': owners, 'direction': 'rtl' if rtl else 'ltr',
            'input_nfc': unicodedata.is_normalized('NFC', source),
            'output_nfc': unicodedata.is_normalized('NFC', logical),
            'input_nfd': unicodedata.is_normalized('NFD', source),
            'output_nfd': unicodedata.is_normalized('NFD', logical)}


def reconstruct_runs(runs: list[dict]) -> list[dict]:
    """Keep operation boundaries; explicitly expose unresolved layout.

    One seqno can have several spans and baselines; one span can contain many
    lines. Neither span order nor a whole-span reversal defines reading order.
    """
    groups = []
    for run in runs:
        for char in run['chars']:
            group = next((g for g in groups if g['seqno'] == run['seqno']
                          and abs(g['baseline'] - char[2][1]) <= min(g['size'], run['size']) * .04), None)
            if group is None:
                group = dict(seqno=run['seqno'], baseline=char[2][1], size=run['size'], chars=[])
                groups.append(group)
            group['chars'].append(char)
    for group in groups:
        group.update(reconstruct_line(group['chars'], size=group['size']))
        group['bbox'] = [min(c[3][0] for c in group['chars']), min(c[3][1] for c in group['chars']),
                         max(c[3][2] for c in group['chars']), max(c[3][3] for c in group['chars'])]
    # Only intra-operation baseline ordering is supported. Cross-operation
    # reading order/paragraphs are NOT certified by this experimental result.
    return sorted(groups, key=lambda g: (g['seqno'], g['baseline']))
