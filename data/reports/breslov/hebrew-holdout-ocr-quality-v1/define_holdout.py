"""Corpus-grounded annotation, executed before any holdout rule evaluation."""
from pathlib import Path
import hashlib
import json

OUT = Path(__file__).resolve().parent
SOURCE = Path('/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY MOHARAN II Interior.pdf')

def run():
    assert (OUT/'orthographic-rules-hash.txt').exists()
    # Visual transcription of short words in saved raster crops. Query-side orthographies
    # are editorial probes, not claimed as independently attested second-edition readings.
    positive = [
        (22,'זרע','זרע','EXACT'),(24,'אמת','אמת','EXACT'),
        (26,'נחש','נחש','EXACT'),(34,'מאה','מאה','EXACT'),
        (22,'עצה','עֵצָה','NIQQUD_INSENSITIVE'),(22,'צדיק','צַדִּיק','NIQQUD_INSENSITIVE'),
        (24,'אדם','אָדָם','NIQQUD_INSENSITIVE'),(24,'שמירה','שְׁמִירָה','NIQQUD_INSENSITIVE'),
        (26,'עינים','עֵינַיִם','NIQQUD_INSENSITIVE'),(30,'אמונה','אֱמוּנָה','NIQQUD_INSENSITIVE'),
        (32,'דעה','דֵּעָה','NIQQUD_INSENSITIVE'),(34,'פעמים','פְּעָמִים','NIQQUD_INSENSITIVE'),
        (22,'נישואין','נִשּׂוּאִין','ORTHOGRAPHIC_VARIANT'),
        (22,'זיווג','זִוּוּג','ORTHOGRAPHIC_VARIANT'),
        (22,'תושייה','תּוּשִׁיָּה','ORTHOGRAPHIC_VARIANT'),
        (24,'המוח','הַמֹּחַ','ORTHOGRAPHIC_VARIANT'),
        (24,'טיפי','טִפֵּי','ORTHOGRAPHIC_VARIANT'),
        (24,'כולו','כֻּלּוֹ','ORTHOGRAPHIC_VARIANT'),
        (26,'הניאוף','הַנִּאוּף','ORTHOGRAPHIC_VARIANT'),
        (30,'הגלות','הַגָּלוּת','NIQQUD_INSENSITIVE'),
        (30,'הגאולה','הַגְּאֻלָּה','ORTHOGRAPHIC_VARIANT'),
        (32,'לומדים','לוֹמְדִים','NIQQUD_INSENSITIVE'),
        (32,'תלמוד','תַּלְמוּד','NIQQUD_INSENSITIVE'),
        (32,'כשולחן','כְּשֻׁלְחָן','ORTHOGRAPHIC_VARIANT'),
        (32,'החכמות','הַחָכְמוֹת','NIQQUD_INSENSITIVE'),
        (34,'השיכחה','הַשִּׁכְחָה','ORTHOGRAPHIC_VARIANT')]
    # Two further pointed controls; total 28 positives, 14 adversarial negatives.
    positive += [(24,'מצות','מִצְוַת','NIQQUD_INSENSITIVE'),(34,'אחד','אֶחָד','NIQQUD_INSENSITIVE')]
    negative = [
        (22,'זר','זרע','different noun; seed is not stranger'),
        (22,'אדום','אָדָם','ו insertion changes man to red/Edom'),
        (22,'רעש','רָשָׁע','metathesis changes wicked to noise'),
        (22,'צדק','צַדִּיק','justice is not the righteous person'),
        (24,'שכלו','הַשֵּׂכֶל','possessive morphology is not spelling equivalence'),
        (24,'שומר','שְׁמִירָה','same semantic field, different noun/participle'),
        (24,'ציץ','צִיצִית','different object, not orthographic deletion'),
        (26,'נחוש','נָחָשׁ','ו and vowel change creates a different lexeme'),
        (22,'זוגה','זִוּוּג','not an allowed spelling of union'),
        (26,'עין','עֵינַיִם','singular/plural must not be lexical equivalence'),
        (30,'אומן','אֱמוּנָה','similar skeleton, craftsman is not faith'),
        (32,'שלחן','שֻׁלְחָן','unpointed identical base is ambiguous: see scope below'),
        (34,'אחר','אֶחָד','ר/ד near visual shape, different word'),
        (34,'מעט','מֵאָה','quantity context does not establish identity')]
    # Do not demand semantic disambiguation of an identical base spelling as a negative.
    negative[11] = (32,'שולח','שֻׁלְחָן','sender is not table; final-letter loss is material')
    cases=[]
    for page,q,c,kind in positive:
        cases.append(dict(id=f'H{len(cases)+1:02}',page=page,query=q,canonical_source=c,
            expected_match=True,allowed_match_types=[kind],must_not_match=[],
            reason='Same lexical reading in visual source; '+('editorial full/defective spelling probe' if kind=='ORTHOGRAPHIC_VARIANT' else 'exact/base-letter control'),
            transcription='base-only' if kind=='EXACT' else 'pointed short visual fragment'))
    for page,q,c,reason in negative:
        cases.append(dict(id=f'H{len(cases)+1:02}',page=page,query=q,canonical_source=c,
            expected_match=False,allowed_match_types=['NO_MATCH'],must_not_match=[c],reason=reason,
            transcription='short visual fragment; query is an adversarial probe'))
    # Exclude not just the 17 old pairs but every old individual query/canonical base form.
    previous=json.loads((OUT.parent/'hebrew-ocr-orthographic-search-v1/orthographic-fixtures.json').read_text())
    import sys
    sys.path.insert(0,str(OUT.parents[3]/'SrvRestAstroLS_v1/backend'))
    from modules.library.hebrew_lexical_normalizer import normalize_hebrew_search as fold
    excluded={fold(c[k]) for c in previous['cases'] for k in ('query','canonical_source')}
    assert all(fold(c[k]) not in excluded for c in cases for k in ('query','canonical_source'))
    artifact=dict(status='ANNOTATED_BEFORE_EXECUTION',source=str(SOURCE),source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        annotation='Assistant visual review of saved original PDF raster crops; no human Hebrew editorial signoff. Short pointed transcriptions are benchmark labels, not publishable citations.',
        independence='New source document/pages/lexemes; zero normalized old query or source terms. Same agent knows frozen design: not blinded independent human annotation.',
        limitations=['Query-side full/defective spellings are editorial probes; not a corpus of independently attested paired editions.','One source document, correlated lexemes/pages; 40 cases cannot support a population safety guarantee.','No new manual lexeme_guard supplied. Ground truth is evaluator-only.'],
        cases=cases)
    target=OUT/'holdout-definition.json'
    if target.exists():raise SystemExit('Refusing to overwrite annotated holdout')
    target.write_text(json.dumps(artifact,ensure_ascii=False,indent=2)+'\n')
    (OUT/'holdout-definition-hash.txt').write_text(hashlib.sha256(target.read_bytes()).hexdigest()+'\n')

if __name__=='__main__':run()
