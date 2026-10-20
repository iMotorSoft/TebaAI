"""Freeze source-reviewed V4 expectations before any V4 candidate evaluation."""
import hashlib
import json
import re
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
SOURCE = '/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf'
SHA = '440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a'
CROSS = [(104, 105, 7), (111, 112, 42), (122, 123, 12), (123, 124, 20),
         (130, 131, 44), (149, 150, 8), (150, 151, 16)]
LEADING = {next_page: number for _, next_page, number in CROSS}
CAPTION = 'Likutey Halajot Explicado'
SEPARATOR = 'Notas y Fuentes'


def mixed(text):
    return any('\u0590' <= c <= '\u05ff' for c in text) or '\ufffd' in text


def unit(parts, zone, good, *, note=None, state='CONTINUATION_UNRESOLVED', basis=None):
    text = '\n'.join(p['text'] for p in parts)
    bad = mixed(text)
    return {'parts': parts, 'expected_zone': zone,
            'expected_certifiable': bool(good and not bad),
            'expected_quality': 'ACCEPTED' if good and not bad else 'UNRESOLVED',
            'note_number': note, 'expected_continuation_state': state,
            'expected_link': None, 'basis': basis or
            'Manual source review: full main paragraph/inset vs header, source-language zone, sidebar, ornament or unsupported family.'}


def find_caption(page):
    hits = [(i, b) for i, b in enumerate(page['boxes'])
            if any(CAPTION in l['text'] for l in b['lines'])]
    return hits[0] if len(hits) == 1 else (None, None)


def find_separator(page):
    hits = [(i, b, l) for i, b in enumerate(page['boxes']) for l in b['lines']
            if l['text'].lstrip('\ufffd ').startswith(SEPARATOR)]
    return hits[0] if len(hits) == 1 else (None, None, None)


def main():
    assert not (OUT / 'holdout-evaluation-started.json').exists()
    inventory = json.loads((OUT / 'holdout-source-inventory.json').read_text())
    pages = []
    for page in inventory:
        n = page['page']
        caption_index, caption = find_caption(page)
        sep_index, sep, sep_line = find_separator(page)
        assert caption is not None and sep is not None, f'page {n} lacks caption/separator'
        units = []
        for b in page['boxes']:
            if b['index'] in {caption_index, sep_index}:
                continue
            if b['y0' if 'y0' in b else 'bbox'][1] < caption['bbox'][3] - 1:
                continue
            if b['bbox'][1] >= sep['bbox'][1] + 2:
                continue
            if b['class'] not in {'text', 'section-header'}:
                continue
            good = (b['class'] == 'text' and b['bbox'][2] - b['bbox'][0] >= 250
                    and not mixed(''.join(l['text'] for l in b['lines'])))
            units.append(unit(b['lines'], 'MAIN_BODY' if good else b['class'], good,
                              basis='Manual source review: main translation paragraph vs sidebar, section header, interleaved source text or ornament.'))
        note_lines = []
        for b in page['boxes']:
            if b['class'] not in {'text', 'footnote', 'page-footer', 'section-header'}:
                continue
            for line in b['lines']:
                if line is sep_line or line['bbox'][1] < sep_line['bbox'][3] - 1:
                    continue
                note_lines.append(dict(line, column=0 if (line['bbox'][0] + line['bbox'][2]) / 2 < page['width'] / 2 else 1))
        note_lines.sort(key=lambda l: (l['column'], l['bbox'][1], l['bbox'][0], l['ids']))
        current = []
        number = LEADING.get(n)
        for part in note_lines:
            marker = re.match(r'^\s*(\d{1,3})\s+', part['text'])
            if marker:
                if current:
                    units.append(unit(current, 'note', True, note=number, state='COMPLETE_LOCAL'))
                current = []
                number = int(marker.group(1))
            current.append(part)
        if current:
            units.append(unit(current, 'note', True, note=number))
        for u in units:
            if u['expected_zone'] != 'note':
                continue
            if u['note_number'] is None or n == 89:
                u['expected_certifiable'] = False
            for first, second, num in CROSS:
                if u['note_number'] != num:
                    continue
                if n == first:
                    u['expected_continuation_state'] = 'CONTINUES_NEXT_PAGE'
                    u['expected_link'] = {'page': second, 'note': num}
                elif n == second:
                    u['expected_continuation_state'] = 'CONTINUED_FROM_PREVIOUS'
                    u['expected_link'] = {'page': first, 'note': num}
        pages.append({'pdf_page': n, 'units': units})
    definition = {
        'version': 'v4',
        'physical_pages': [p['page'] for p in inventory],
        'source_sha256': SHA,
        'pages': pages,
        'cross_page_units': [{'from': a, 'to': b, 'note': num} for a, b, num in CROSS],
        'selection': '32 disjoint source-reviewed pages excluding all V1/V2/V3 holdouts and the V3 permutation pages; seven observed cross-page notes.',
        'annotation_scope': 'Implementing-agent source/IR review, not independent human adjudication nor exhaustive rendered glyph QA. Exact source identity, roles, note column flow and cross-page membership.',
        'utility_rule': 'Both main-body certification and cross-page linkage must be useful, not isolated fragments or one development link. Report provenance and ACCEPTED separately. No arbitrary percentage gate.',
        'diversity': ['preface/header', 'main body', 'main body + heading', 'sidebar interleaving',
                      'same-page notes', 'two-column notes', 'seven cross-page notes',
                      'page-start note continuation', 'source-language zone', 'mixed direction'],
        'no_post_evaluation_tuning': True,
    }
    (OUT / 'holdout-v4-definition.json').write_text(json.dumps(definition, ensure_ascii=False, indent=2) + '\n')
    paths = [OUT / 'holdout-v4-definition.json', OUT / 'holdout-source-inventory.json',
             OUT / 'inspect_source.py', OUT / 'seal_holdout.py',
             ROOT / 'SrvRestAstroLS_v1/backend/tests/test_automatic_region_certification_v4.py',
             ROOT / 'SrvRestAstroLS_v1/backend/modules/library/automatic_region_certification_v4.py',
             ROOT / 'SrvRestAstroLS_v1/backend/modules/library/region_markdown_provenance.py']
    (OUT / 'holdout-v4-sealed-hash.txt').write_text(''.join(
        f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(ROOT)}\n' for p in sorted(paths)))


if __name__ == '__main__':
    main()
