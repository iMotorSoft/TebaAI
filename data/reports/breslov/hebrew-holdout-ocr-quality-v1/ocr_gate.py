"""Conservative experimental gate. Never receives a golden or expected label.
No certified base-text reference => UNCERTAIN => reject, even with high confidence.
"""
import re
import unicodedata as ud

POLICY = {
    'version': 1,
    'search': 'Requires independently trusted base text/order/boundaries, structural numbers intact, valid Unicode, geometry and fixed-config agreement.',
    'display': 'Search conditions plus independently trusted full pointed transcript and NFC equality.',
    'confidence': 'Diagnostic only, never an acceptance authority.',
    'thresholds': 'Zero material discrepancy against independently trusted reference; no fitted confidence/ratio cutoff.',
    'missing_evidence': 'Reject; golden/expected labels unavailable to decide().',
}

def fold(s):
    return ' '.join(''.join(c for c in ud.normalize('NFD',s) if not ud.category(c).startswith('M') and ud.category(c)!='Cf').split())

def decide(signals):
    text=signals['text']; reference=signals.get('trusted_reference')
    codes=[]
    if signals.get('source_visual')=='BAD': codes.append('SOURCE_PDF_ERROR')
    if signals.get('trusted_digits') is not None and re.findall(r'\d+',text)!=signals['trusted_digits']:
        codes.append('OCR_DIGIT_LOSS')
    if '\ufffd' in text or any(ud.category(c) in ('Co','Cs') for c in text): codes.append('OCR_UNICODE_INVALID')
    if not signals.get('geometry_verified'):codes.append('OCR_GEOMETRY_MISMATCH')
    if not signals.get('fixed_config_agreement'):codes.append('OCR_CONFIG_DISAGREEMENT')
    if reference is None:
        codes.append('OCR_UNCERTAIN')
    elif fold(reference)!=fold(text):
        r,t=fold(reference),fold(text)
        if ''.join(r.split())==''.join(t.split()):
            codes.append('OCR_WORD_MERGE' if len(t.split())<len(r.split()) else 'OCR_WORD_SPLIT')
        else:codes.append('OCR_BASE_LETTER_ERROR')
    search=not codes
    display=search and signals.get('trusted_display_reference') is not None and ud.normalize('NFC',text)==ud.normalize('NFC',signals['trusted_display_reference'])
    if search:codes.append('OCR_ACCEPT_SEARCH')
    if display:codes.append('OCR_ACCEPT_DISPLAY')
    elif search:codes.append('OCR_DISPLAY_UNCERTAIN')
    return dict(decision_search='SEARCH_ACCEPT' if search else 'SEARCH_REJECT',
                decision_display='DISPLAY_ACCEPT' if display else 'DISPLAY_REJECT',reason_codes=codes,
                fallback='KEEP_NATIVE_RECONSTRUCTION_OR_UNRESOLVED',replacement_authorized=False)
