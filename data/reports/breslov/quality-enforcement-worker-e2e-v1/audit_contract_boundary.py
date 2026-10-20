"""Read-only contract probe, NOT a worker/E2E or page167 probe.
Run from backend: uv run python ../../data/reports/breslov/quality-enforcement-worker-e2e-v1/audit_contract_boundary.py
"""
from dataclasses import fields
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'SrvRestAstroLS_v1/backend'))
from modules.library.content_manager_schemas import CreateJobRequest
from modules.library.page_first_pipeline import PageFirstIngestionRequest, ExtractedPage
from modules.library.region_quality import (
    QUALITY_POLICY_VERSION, RegionCandidate, RegionState, QualityPage, classify_region,
)

# No positive verification flags or claimed visual/source certificates.
# These strings are NOT a PDF fixture and never enter the worker or persistence.
texts = ('GOOD_A qualityboundarygoodalpha',
         'BAD_B qualityboundarybadbeta ' + '\ufffd' * 20,
         'GOOD_C qualityboundarygoodgamma')
source = hashlib.sha256('\n'.join(texts).encode()).hexdigest()
regions = tuple(classify_region(RegionCandidate(
    source, 1, name, text, 'pymupdf4llm', (),
)) for name, text in zip(('GOOD_A', 'BAD_B', 'GOOD_C'), texts, strict=True))
assert all(r.state == RegionState.UNRESOLVED for r in regions)
assert 'replacement_character' in regions[1].reasons
quality = QualityPage(regions)
assert quality.quality.value == 'UNUSABLE'
assert not quality.evidence_units and not quality.canonical_markdown

job_fields = sorted(CreateJobRequest.model_fields)
request_fields = sorted(f.name for f in fields(PageFirstIngestionRequest))
page_fields = sorted(f.name for f in fields(ExtractedPage))
assert not any('certificate' in name or 'quality' in name or 'provenance' in name
               for name in job_fields + request_fields + page_fields)
result = {
    'scope': 'Existing classifier + runtime type boundary ONLY; no PDF/upload/job/worker execution',
    'quality_policy_version': QUALITY_POLICY_VERSION,
    'classifications_without_external_certificates': {r.candidate.region_id: r.state.value for r in regions},
    'bad_region_reasons': list(regions[1].reasons),
    'aggregate_without_external_certificates': quality.quality.value,
    'accepted_units': len(quality.evidence_units),
    'job_fields': job_fields, 'worker_request_fields': request_fields,
    'extracted_page_fields': page_fields,
    'conclusion': 'The existing contract does not certify clean text. Runtime has no certificate transport. Supplying positive flags without evidence would change the safety contract.',
}
Path(__file__).with_name('contract-boundary-probe.json').write_text(json.dumps(result, indent=2) + '\n')
print('CONTRACT_BOUNDARY_PROBE_PASS (not worker enforcement, not E2E)')
