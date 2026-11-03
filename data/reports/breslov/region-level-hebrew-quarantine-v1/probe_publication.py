"""Offline publication-consumer probe; NOT worker, embedding or retrieval E2E.

Run from backend:
  uv run python ../../data/reports/breslov/region-level-hebrew-quarantine-v1/probe_publication.py
"""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "SrvRestAstroLS_v1/backend"))
from modules.library.automatic_region_certification_v5 import extract_pdf_region_certificates
from modules.library.chunking import paragraph_chunks
from modules.library.region_publication import publish_certified_page
from tests.test_region_publication import BAD, GOOD_A, GOOD_B, certified_fixture

OUT = Path(__file__).parent


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


cases = [
    ((GOOD_A,), ("ACCEPTED",)),
    ((BAD,), ("UNRESOLVED",)),
    ((GOOD_A, BAD, GOOD_B), ("ACCEPTED", "PLATFORM_EXTRACTION_ERROR", "ACCEPTED")),
    ((BAD, BAD, GOOD_A), ("SOURCE_PDF_ERROR", "UNRESOLVED", "ACCEPTED")),
    ((BAD, BAD), ("UNRESOLVED", "PLATFORM_EXTRACTION_ERROR")),
]
controlled = []
for number, (texts, statuses) in enumerate(cases, 1):
    original = certified_fixture(texts, statuses)
    published = publish_certified_page(original, source_reference="controlled-fixture.pdf")
    chunks = [(rid, c["content"]) for rid, text in published.evidence_units
              for c in paragraph_chunks(text, 1400, 150, 1)]
    assert BAD not in published.canonical_markdown
    assert all(BAD not in text for _, text in chunks)
    assert len(published.evidence_units) == statuses.count("ACCEPTED")
    assert all(not (GOOD_A in text and GOOD_B in text) for _, text in chunks)
    controlled.append({
        "case": number, "texts": texts, "declared_quality_statuses": statuses,
        "page_status": published.status.value,
        "accepted_region_ids": [rid for rid, _ in published.evidence_units],
        "chunk_count": len(chunks),
        "bad_region_chunk_count": sum(BAD in text for _, text in chunks),
        "accepted_region_loss": statuses.count("ACCEPTED") - len(published.evidence_units),
        "metadata": published.metadata(),
        "quality_evidence": "Declared internal fixture verdicts, not an extraction-quality proof",
        "pdf_exists": False,
    })
write("controlled-fixtures.json", controlled)

source = Path("/media/issajar/DEVELOP/Download/Tora/Breslov/LIKUTEY HALAJOT (Interior Final).pdf")
source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
real = []
for page in extract_pdf_region_certificates(source, pages=[55, 167, 168]):
    published = publish_certified_page(page, source_reference=str(source))
    expected = {
        c.region_id for c in page.certificates
        if c.quality_status == "ACCEPTED" and c.provenance_status == "CERTIFIED"
    }
    accepted = {rid for rid, _ in published.evidence_units}
    assert accepted == expected
    chunk_ids = [rid for rid, text in published.evidence_units
                 for _ in paragraph_chunks(text, 1400, 150, 1)]
    quarantined = set(r.region_id for r in published.regions if not r.publishable)
    assert not (quarantined & set(chunk_ids))
    real.append({
        "pdf_page": published.pdf_page,
        "page_status": published.status.value,
        "accepted_certificate_count": len(expected),
        "accepted_region_loss": len(expected - accepted),
        "quarantined_region_count": len(quarantined),
        "quarantined_region_chunks": len(quarantined & set(chunk_ids)),
        "source_exists_now": source.is_file(),
        "source_hash_matches": source_sha == published.source_sha256,
        "metadata": published.metadata(),
        "certificates": [c.to_dict() for c in page.certificates],
        "scope": "Offline current-source consumer only, not worker enforcement or persistent visual storage",
    })
write("real-source-case.json", {
    "source": str(source), "sha256": source_sha, "pages": real,
    "visual_review": {
        "pages": [55, 167],
        "artifacts": ["source-page-55.png", "source-page-167.png"],
        "observation": "Rendered source has legible Hebrew panels above Spanish body and notes. No transcription, OCR or claim of exact Hebrew recovery.",
    },
    "historical_pages_not_revalidated": [187, 416],
})
write("region-publication-results.json", {
    "scope": "Offline consumer only; NOT real worker",
    "controlled_cases": len(controlled), "controlled_accepted_region_loss": 0,
    "controlled_bad_chunks": 0,
    "real_pages": [p["pdf_page"] for p in real],
    "real_accepted_region_loss": sum(p["accepted_region_loss"] for p in real),
    "real_quarantined_region_chunks": sum(p["quarantined_region_chunks"] for p in real),
    "real_page_statuses": {p["pdf_page"]: p["page_status"] for p in real},
    "good_neighbor_definition": "Existing ACCEPTED + CERTIFIED units only; not all visually valid source regions",
    "worker_integration": "NOT_IMPLEMENTED",
})
write("chunk-results.json", {
    "scope": "Pure paragraph_chunks invoked per accepted evidence unit; not gateway persist_chunks",
    "controlled_counts": [c["chunk_count"] for c in controlled],
    "quarantined_chunks": 0,
    "persistent_chunk_assertion": "NOT_RUN",
})
print("OFFLINE_PUBLICATION_CONSUMER_PROBE_PASS; worker gate remains incomplete")
