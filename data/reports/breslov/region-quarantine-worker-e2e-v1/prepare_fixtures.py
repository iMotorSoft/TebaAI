"""Prepare immutable expected controlled cases BEFORE real extraction. No stores."""
import hashlib
import json
from pathlib import Path
import sys
import argparse

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'SrvRestAstroLS_v1/backend'))
import pymupdf

OUT = Path(__file__).parent
FONT = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
assert FONT.is_file()
GOOD_A = 'Quarantineworker alfariver trusted neighboring Spanish source region.'
GOOD_B = 'Quarantineworker omegagarden accepted neighboring citation evidence.'
BAD = 'אב\ufffdגד ש\ufffdלום'
CASES = [
    ('A', [GOOD_A], ['ACCEPTED']),
    ('B', [BAD], ['QUARANTINED']),
    ('C', [GOOD_A, BAD, GOOD_B], ['ACCEPTED','QUARANTINED','ACCEPTED']),
    ('D', [BAD, GOOD_A, BAD], ['QUARANTINED','ACCEPTED','QUARANTINED']),
    ('E', [BAD, BAD], ['QUARANTINED','QUARANTINED']),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    records = []
    for code, texts, expected in CASES:
        path = OUT / 'fixtures' / f'case-{code}.pdf'
        path.parent.mkdir(exist_ok=True)
        doc = pymupdf.open()
        page = doc.new_page(width=600, height=800)
        page.insert_font(fontname='DejaVu', fontfile=str(FONT))
        for index, text in enumerate(texts):
            page.insert_text((40, 100 + index * 150), text, fontname='DejaVu', fontsize=10)
        doc.set_metadata({'title': f'region-quarantine-worker-e2e-v1-{code}',
                          'subject': 'isolated DEV controlled fixture, expected truth frozen before extraction; run='+args.run_id})
        doc.save(path, no_new_id=True)
        doc.close()
        records.append({'case':code,'path':str(path.relative_to(ROOT)),
                        'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                        'physical_pages':1,'expected_region_publication':expected,
                        'texts':texts,'expected_accepted':expected.count('ACCEPTED'),
                        'expected_quarantined':expected.count('QUARANTINED')})
    (OUT / 'controlled-test-cases.json').write_text(json.dumps(records, indent=2, ensure_ascii=False)+'\n')
    original = Path('/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf')
    assert hashlib.sha256(original.read_bytes()).hexdigest() == '440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a'
    with pymupdf.open(original) as source, pymupdf.open() as isolated:
        isolated.insert_pdf(source, from_page=53, to_page=55)
        isolated.set_metadata({'title':'region-quarantine-worker-e2e-v1-real-p54-p56',
            'subject':'Original physical pages 54,55,56; isolated page +53; run='+args.run_id})
        isolated.save(OUT / 'fixtures/real-p54-p56.pdf', no_new_id=True)


if __name__ == '__main__': main()
