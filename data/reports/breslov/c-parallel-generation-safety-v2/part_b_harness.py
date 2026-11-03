#!/usr/bin/env python3
"""PART B — region quarantine contract V2 against the authoritative certifier.

Everything in this harness is read-only with respect to CURRENT C:

* the declared mixed fixture exercises the publication consumer and the real
  page-first worker in memory;
* the real-C dry run calls the authoritative certifier and the publication
  boundary, and never persists a page, chunk, embedding, vector or pointer.

Frozen expectations live in this file; see frozen-manifest.json.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import sys
import traceback
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

BACKEND = Path(os.environ.get(
    "AUTHORITATIVE_BACKEND",
    "/tmp/opencode/tebaai-b4a26a9/SrvRestAstroLS_v1/backend",
))
sys.path.insert(0, str(BACKEND))

from modules.library.automatic_region_certification_v5 import (  # noqa: E402
    extract_pdf_region_certificates,
)
from modules.library.page_first_gateway import (  # noqa: E402
    build_region_chunks,
    publication_metadata,
    validate_publication,
)
from modules.library.page_first_pipeline import (  # noqa: E402
    ConcretePageFirstPipeline,
    document_from_certificates,
)
from modules.library.region_publication import (  # noqa: E402
    publish_certified_page,
)
from modules.library.region_quality import AggregateState  # noqa: E402
from tests.test_page_first_pipeline import FakeGateway  # noqa: E402
from tests.test_region_publication import (  # noqa: E402
    BAD,
    GOOD_A,
    GOOD_B,
    certified_fixture,
)

OUT = Path(__file__).resolve().parent
SOURCE = Path(
    "/media/issajar/DEVELOP/Projects/iMotorSoft/ai/dev/TebaAI/SrvRestAstroLS_v1/"
    "backend/sources/ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa/original.pdf"
)
EXPECTED_SOURCE_SHA = (
    "440d4fd348604920179dd1b6acd88b9b50e98ae32c20663751bb01cea82c106a"
)
CURRENT_C_DOCUMENT = "ddb9cba6-7701-5f64-9cc7-d24bcd63f6aa"
CURRENT_C_LOGICAL = "db200a31-b547-5668-d968-06d0ec36ad95"
CURRENT_C_ACTIVE_GENERATION = "1a8af56b-fc17-d9f9-ffc2-9efde54aa95b"
CURRENT_C_RUN = "6c1a19b8-b60b-52de-b709-5496f4c6e937"
CURRENT_C_CHUNKS = 942
CURRENT_C_FFFD = 180238
QUARANTINE_TOKEN = "quarantineunique"
HEBREW = re.compile(r"[\u0590-\u05FF]")
FFFD = "\ufffd"
FROZEN_PAGES = (55, 56)


def write(name: str, payload) -> None:
    (OUT / name).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


# ── Declared mixed fixture: consumer boundary only ─────────────────────────

def mixed_fixture_results() -> dict:
    declared = (
        ("GOOD_A", GOOD_A, "ACCEPTED"),
        ("BAD_HEBREW", BAD, "PLATFORM_EXTRACTION_ERROR"),
        ("GOOD_B", GOOD_B, "ACCEPTED"),
    )
    fixture = certified_fixture(
        tuple(text for _, text, _ in declared),
        tuple(status for _, _, status in declared),
    )
    publication = publish_certified_page(fixture, source_reference="declared-mixed.pdf")
    evidence = tuple(text.strip() for _, text in publication.evidence_units)
    metadata_json = json.dumps(publication.metadata(), ensure_ascii=False)
    chunks = [
        (region_id, chunk["content"])
        for region_id, text in publication.evidence_units
        for chunk in _paragraph_chunks(text)
    ]
    chunk_regions = sorted({region_id for region_id, _ in chunks})
    publishable = [r.region_id for r in publication.regions if r.publishable]
    quarantined = [r.region_id for r in publication.regions if not r.publishable]

    payload = {
        "fixture_kind": "declared",
        "FIXTURE_DECLARATIONS_ARE_QUALITY_CLAIMS": False,
        "declared_inputs": [
            {"label": label, "region_id": f"region-{index}", "declared_quality_status": status}
            for index, (label, _, status) in enumerate(declared)
        ],
        "publication_status": publication.status.value,
        "publishable_regions": publishable,
        "quarantined_regions": quarantined,
        "evidence_units": [
            {"region_id": region_id, "text": text.strip()}
            for region_id, text in publication.evidence_units
        ],
        "canonical_markdown": publication.canonical_markdown,
        "metadata": publication.metadata(),
        "chunk_inputs": [
            {"region_id": region_id, "content": content} for region_id, content in chunks
        ],
        "CHUNK_REGIONS": chunk_regions,
        "BAD_ABSENT_FROM_CANONICAL": BAD not in publication.canonical_markdown,
        "BAD_ABSENT_FROM_METADATA": BAD not in metadata_json,
        "BAD_ABSENT_FROM_CHUNKS": all(QUARANTINE_TOKEN not in text for _, text in chunks),
        "CROSS_REGION_QUOTE_ABSENT": all(
            not (GOOD_A in text and GOOD_B in text) for _, text in chunks
        ),
        "ACCEPTED_REGIONS_PRESENT": all(
            any(region_id == rid for region_id, _ in chunks) for rid in publishable
        ),
        "QUARANTINED_REGIONS_HAVE_NO_CHUNKS": all(
            rid not in chunk_regions for rid in quarantined
        ),
        "RETRIEVAL_PROBE": {
            "query": QUARANTINE_TOKEN,
            "chunks_returned": sum(
                1 for _, text in chunks if QUARANTINE_TOKEN in text
            ),
            "citation_sources": sorted({rid for rid, _ in chunks}),
        },
        "PARTIAL_DERIVED_FROM_CERTIFIER_OUTPUT": publication.status
        == AggregateState.PARTIAL,
    }
    payload["PASS"] = (
        payload["publication_status"] == "PARTIAL"
        and evidence == (GOOD_A, GOOD_B)
        and payload["BAD_ABSENT_FROM_CANONICAL"]
        and payload["BAD_ABSENT_FROM_METADATA"]
        and payload["BAD_ABSENT_FROM_CHUNKS"]
        and payload["CROSS_REGION_QUOTE_ABSENT"]
        and payload["ACCEPTED_REGIONS_PRESENT"]
        and payload["QUARANTINED_REGIONS_HAVE_NO_CHUNKS"]
        and payload["RETRIEVAL_PROBE"]["chunks_returned"] == 0
    )
    return payload


def _paragraph_chunks(text: str):
    from modules.library.chunking import paragraph_chunks

    return paragraph_chunks(text, 1400, 150, 1)


# ── Region contract V2 ─────────────────────────────────────────────────────

CONTRACT_RULES = [
    "The certifier output is authoritative; no consumer may upgrade a region.",
    "A region is textually publishable only when quality_status == ACCEPTED and "
    "provenance_status == CERTIFIED and its ownership is bound and non-overlapping.",
    "Every other region is quarantined: QUARANTINED, UNRESOLVED, SOURCE_PDF_ERROR, "
    "PLATFORM_EXTRACTION_ERROR, UNKNOWN, missing certificate or mismatched ownership.",
    "Page status is derived: no publishable region -> UNUSABLE; all publishable -> FULL; "
    "otherwise -> PARTIAL.",
    "Quarantined text never enters canonical Markdown, searchable metadata, chunks, "
    "embeddings or citations; it remains reachable only through the visual source reference.",
    "A fixture label such as GOOD_A is a declared input, never evidence of live quality.",
]


def contract_cases() -> dict:
    cases = {}

    def run_case(name: str, texts, statuses, *, mutation=None):
        fixture = certified_fixture(texts, statuses)
        if mutation is not None:
            fixture = mutation(fixture)
        try:
            publication = publish_certified_page(fixture, source_reference="contract.pdf")
        except ValueError as exc:
            return {
                "rejected_at_boundary": True,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "evidence_units": [],
                "status": None,
            }
        return {
            "rejected_at_boundary": False,
            "status": publication.status.value,
            "evidence_units": [r.region_id for r in publication.regions if r.publishable],
            "quarantined": [r.region_id for r in publication.regions if not r.publishable],
            "reason_codes": {
                r.region_id: list(r.reason_codes) for r in publication.regions
            },
            "canonical_has_bad": BAD in publication.canonical_markdown,
        }

    cases["accepted_certified_publishes"] = run_case(
        "accepted", (GOOD_A,), ("ACCEPTED",)
    )
    for status in ("QUARANTINED", "UNRESOLVED", "SOURCE_PDF_ERROR",
                   "PLATFORM_EXTRACTION_ERROR", "UNKNOWN", "accepted"):
        cases[f"status_{status}_quarantines"] = run_case(
            f"status_{status}", (BAD,), (status,)
        )
    cases["declared_mixed_is_partial"] = run_case(
        "mixed", (GOOD_A, BAD, GOOD_B),
        ("ACCEPTED", "PLATFORM_EXTRACTION_ERROR", "ACCEPTED"),
    )
    cases["provenance_not_certified_quarantines"] = run_case(
        "provenance",
        (GOOD_A, BAD, GOOD_B),
        ("ACCEPTED",) * 3,
        mutation=lambda fx: replace(
            fx,
            certificates=(
                fx.certificates[0],
                replace(fx.certificates[1], provenance_status="UNRESOLVED"),
                fx.certificates[2],
            ),
        ),
    )
    cases["document_sha_mismatch_quarantines"] = run_case(
        "sha",
        (GOOD_A, BAD, GOOD_B),
        ("ACCEPTED",) * 3,
        mutation=lambda fx: replace(
            fx,
            certificates=(
                fx.certificates[0],
                replace(fx.certificates[1], document_sha="b" * 64),
                fx.certificates[2],
            ),
        ),
    )
    cases["page_mismatch_quarantines"] = run_case(
        "page",
        (GOOD_A, BAD, GOOD_B),
        ("ACCEPTED",) * 3,
        mutation=lambda fx: replace(
            fx,
            certificates=(
                fx.certificates[0],
                replace(fx.certificates[1], pdf_page=2),
                fx.certificates[2],
            ),
        ),
    )
    cases["missing_certificate_quarantines"] = run_case(
        "missing",
        (GOOD_A, BAD, GOOD_B),
        ("ACCEPTED",) * 3,
        mutation=lambda fx: replace(
            fx, certificates=(fx.certificates[0], fx.certificates[2])
        ),
    )
    cases["overlap_quarantines"] = run_case(
        "overlap",
        (GOOD_A, BAD),
        ("ACCEPTED", "UNRESOLVED"),
        mutation=lambda fx: replace(
            fx,
            provenance=replace(
                fx.provenance,
                units=(
                    fx.provenance.units[0],
                    replace(fx.provenance.units[1], markdown_start=0),
                ),
            ),
        ),
    )

    expectations = {
        "accepted_certified_publishes": {"status": "FULL", "evidence": ["region-0"]},
        "status_QUARANTINED_quarantines": {"status": "UNUSABLE", "evidence": []},
        "status_UNRESOLVED_quarantines": {"status": "UNUSABLE", "evidence": []},
        "status_SOURCE_PDF_ERROR_quarantines": {"status": "UNUSABLE", "evidence": []},
        "status_PLATFORM_EXTRACTION_ERROR_quarantines": {"status": "UNUSABLE", "evidence": []},
        "status_UNKNOWN_quarantines": {"status": "UNUSABLE", "evidence": []},
        "status_accepted_quarantines": {"status": "UNUSABLE", "evidence": []},
        "declared_mixed_is_partial": {"status": "PARTIAL", "evidence": ["region-0", "region-2"]},
        "provenance_not_certified_quarantines": {"status": "PARTIAL", "evidence": ["region-0", "region-2"]},
        "document_sha_mismatch_quarantines": {"status": "PARTIAL", "evidence": ["region-0", "region-2"]},
        "page_mismatch_quarantines": {"status": "PARTIAL", "evidence": ["region-0", "region-2"]},
        "missing_certificate_quarantines": {"status": "PARTIAL", "evidence": ["region-0", "region-2"]},
        "overlap_quarantines": {"status": "UNUSABLE", "evidence": []},
    }
    checks = {}
    for name, expected in expectations.items():
        observed = cases[name]
        checks[name] = (
            not observed["rejected_at_boundary"]
            and observed["status"] == expected["status"]
            and observed["evidence_units"] == expected["evidence"]
            and not observed.get("canonical_has_bad", False)
        )
    checks["overlap_reason_code"] = any(
        "OVERLAPPING_MARKDOWN_OWNERSHIP" in reasons
        for reasons in cases["overlap_quarantines"]["reason_codes"].values()
    )
    return {"cases": cases, "checks": checks, "PASS": all(checks.values())}


# ── Worker enforcement ─────────────────────────────────────────────────────

class RecordingGateway(FakeGateway):
    def __init__(self, *, source_sha: str, expected_status: str, expected_count: int):
        super().__init__()
        self.source_sha = source_sha
        self.expected_status = expected_status
        self.expected_count = expected_count
        self.embedded_texts: tuple[str, ...] = ()
        self.publication: dict | None = None
        self.chunks = ()

    async def load_request(self, job):
        request = await super().load_request(job)
        return replace(request, source_sha256=self.source_sha)

    async def persist_document_and_pages(self, request, document):
        validate_publication(request, document)
        self.publication = publication_metadata(document.pages[0], self.document_id)
        return await super().persist_document_and_pages(request, document)

    async def persist_chunks(self, request, persisted, document):
        self.chunks = tuple(build_region_chunks(request, persisted, document))
        return self.chunks

    async def embed(self, texts, model):
        self.calls.append("embed")
        self.embedded_texts = tuple(texts)
        return tuple((0.0, 1.0) for _ in texts)

    async def persist_embeddings(self, request, persisted, chunks, vectors):
        from modules.library.page_first_pipeline import PersistedEmbedding

        return tuple(
            PersistedEmbedding(uuid4(), chunk, vector)
            for chunk, vector in zip(chunks, vectors, strict=True)
        )

    async def index_vectors(self, request, persisted, embeddings):
        return tuple(embedding.chunk.chunk_uid for embedding in embeddings)

    async def reconcile(self, request, persisted):
        from modules.library.page_first_pipeline import ReconciliationResult

        count = len(self.chunks)
        return ReconciliationResult(
            request.job_id, request.attempt_number, self.document_id,
            count, count, count, count,
        )


async def worker_enforcement() -> dict:
    from tests.test_region_publication import SOURCE as FIXTURE_SOURCE

    extracted = document_from_certificates(
        (
            certified_fixture(
                (GOOD_A, BAD, GOOD_B),
                ("ACCEPTED", "PLATFORM_EXTRACTION_ERROR", "ACCEPTED"),
            ),
        )
    )
    gateway = RecordingGateway(
        source_sha=FIXTURE_SOURCE, expected_status="PARTIAL", expected_count=2
    )

    async def noop(*args):
        return None

    result = await ConcretePageFirstPipeline(
        gateway, extractor=lambda *args: extracted
    ).run(gateway.job, advance=noop, heartbeat=noop)

    embedded = gateway.embedded_texts
    payload = {
        "pipeline": "ConcretePageFirstPipeline",
        "declared_input_statuses": ["ACCEPTED", "PLATFORM_EXTRACTION_ERROR", "ACCEPTED"],
        "calls": gateway.calls,
        "page_status": extracted.pages[0].publication.status.value,
        "publication_partial_source": gateway.publication["partial_source"],
        "publication_contains_quarantined": gateway.publication[
            "contains_quarantined_regions"
        ],
        "publication_notice_present": bool(gateway.publication["notice"]),
        "chunk_count": len(result.chunk_ids),
        "embedding_count": len(result.embedding_ids),
        "vector_count": len(result.vector_ids),
        "embedded_texts": list(embedded),
        "embedded_bad": any(QUARANTINE_TOKEN in text for text in embedded),
        "embedded_cross_region": any(
            GOOD_A in text and GOOD_B in text for text in embedded
        ),
        "chunk_regions": sorted({chunk.region_id for chunk in gateway.chunks}),
        "canonical_has_bad": BAD in extracted.content_markdown,
        "metadata_has_bad": QUARANTINE_TOKEN
        in json.dumps(gateway.publication, ensure_ascii=False),
        "finalized": "finalize" in gateway.calls,
    }
    payload["PASS"] = (
        payload["page_status"] == "PARTIAL"
        and payload["publication_partial_source"] is True
        and payload["publication_contains_quarantined"] is True
        and payload["chunk_count"] == 2
        and payload["embedding_count"] == 2
        and payload["vector_count"] == 2
        and not payload["embedded_bad"]
        and not payload["embedded_cross_region"]
        and payload["chunk_regions"] == ["region-0", "region-2"]
        and not payload["canonical_has_bad"]
        and not payload["metadata_has_bad"]
        and payload["finalized"]
    )
    return payload


# ── Real C dry run (read-only) ─────────────────────────────────────────────

def region_record(region, reference: dict, canonical: str) -> dict:
    text = region.markdown
    return {
        "region_id": region.region_id,
        "bbox": list(region.bbox),
        "quality_status": region.quality_status,
        "provenance_status": region.provenance_status,
        "publishable": region.publishable,
        "reason_codes": list(region.reason_codes),
        "fragment_sha256": region.candidate_sha256,
        "fragment_length": len(text),
        "fragment_u_fffd": text.count(FFFD),
        "fragment_hebrew_chars": len(HEBREW.findall(text)),
        "fragment_in_canonical": bool(text) and text in canonical,
        "visual_reference": reference,
    }


def real_c_dry_run() -> dict:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"durable source missing: {SOURCE}")
    source_sha = file_sha(SOURCE)
    if source_sha != EXPECTED_SOURCE_SHA:
        raise RuntimeError(f"durable source sha mismatch: {source_sha}")

    certified = extract_pdf_region_certificates(SOURCE)
    pages = []
    page_objects = {}
    totals = {
        "regions": 0,
        "accepted": 0,
        "quarantined": 0,
        "accepted_loss": 0,
        "canonical_u_fffd": 0,
        "canonical_chars": 0,
    }
    statuses: dict[str, int] = {}
    errors = []
    for page in certified:
        number = page.provenance.pdf_page
        try:
            publication = publish_certified_page(
                page, source_reference=f"sha256:{source_sha}"
            )
        except Exception as exc:  # noqa: BLE001
            errors.append({
                "page": number,
                "error_type": type(exc).__name__,
                "error": str(exc),
            })
            continue
        page_objects[number] = publication
        canonical = publication.canonical_markdown
        publishable = [r for r in publication.regions if r.publishable]
        accepted_loss = sum(
            1 for region in publishable if region.markdown not in canonical
        )
        status = publication.status.value
        statuses[status] = statuses.get(status, 0) + 1
        totals["regions"] += len(publication.regions)
        totals["accepted"] += len(publishable)
        totals["quarantined"] += len(publication.regions) - len(publishable)
        totals["accepted_loss"] += accepted_loss
        totals["canonical_u_fffd"] += canonical.count(FFFD)
        totals["canonical_chars"] += len(canonical)
        pages.append({
            "page": number,
            "region_count": len(publication.regions),
            "accepted": len(publishable),
            "quarantined": len(publication.regions) - len(publishable),
            "page_status": status,
            "canonical_chars": len(canonical),
            "canonical_u_fffd": canonical.count(FFFD),
            "accepted_loss": accepted_loss,
            "contains_quarantined_regions": any(
                not r.publishable for r in publication.regions
            ),
            "notice_present": bool(publication.metadata()["notice"]),
        })

    whole = document_from_certificates(certified)
    payload = {
        "mode": "read_only_dry_run",
        "certifier": "modules.library.automatic_region_certification_v5",
        "source": {
            "path": str(SOURCE),
            "exists": True,
            "sha256": source_sha,
            "expected_sha256": EXPECTED_SOURCE_SHA,
        },
        "current_c_identity": {
            "document_id": CURRENT_C_DOCUMENT,
            "logical_document_id": CURRENT_C_LOGICAL,
            "active_generation_id": CURRENT_C_ACTIVE_GENERATION,
            "run_id": CURRENT_C_RUN,
            "chunks": CURRENT_C_CHUNKS,
            "u_fffd": CURRENT_C_FFFD,
        },
        "sampling": {
            "frozen": True,
            "pages": "ALL",
            "page_count": len(certified),
        },
        "pages_certified": len(certified),
        "page_numbers": [page.provenance.pdf_page for page in certified],
        "totals": totals,
        "status_distribution": statuses,
        "document": {
            "page_count": len(whole.pages),
            "content_chars": len(whole.content_markdown),
            "content_u_fffd": whole.content_markdown.count(FFFD),
            "content_sha256": whole.content_sha256,
            "warnings": list(whole.warnings),
        },
        "errors": errors,
        "per_page": pages,
    }
    payload["PASS"] = (
        len(certified) == 284
        and not errors
        and totals["accepted_loss"] == 0
        and totals["canonical_u_fffd"] == 0
        and whole.content_markdown.count(FFFD) == 0
        and set(page.provenance.pdf_page for page in certified) == set(range(1, 285))
    )
    return payload, page_objects, source_sha


def frozen_pages(page_objects, source_sha: str) -> dict:
    details = {}
    for number in FROZEN_PAGES:
        publication = page_objects[number]
        canonical = publication.canonical_markdown
        metadata = publication.metadata()
        references = {
            region["region_id"]: region["visual_reference"]
            for region in metadata["regions"]
        }
        regions = [
            region_record(region, references[region.region_id], canonical)
            for region in publication.regions
        ]
        quarantined = [r for r in regions if not r["publishable"]]
        accepted = [r for r in regions if r["publishable"]]
        details[number] = {
            "page": number,
            "page_status": publication.status.value,
            "region_count": len(regions),
            "accepted_count": len(accepted),
            "quarantined_count": len(quarantined),
            "canonical_chars": len(canonical),
            "canonical_u_fffd": canonical.count(FFFD),
            "metadata_u_fffd": json.dumps(metadata, ensure_ascii=False).count(FFFD),
            "accepted_regions": accepted,
            "quarantined_regions": quarantined,
            "ACCEPTED_LOSS": sum(
                1 for region in publication.regions
                if region.publishable and region.markdown not in canonical
            ),
            "QUARANTINED_LEAKAGE": sum(
                1 for region in publication.regions
                if not region.publishable
                and region.markdown.strip()
                and region.markdown in canonical
            ),
            "CORRUPT_REGIONS_QUARANTINED": all(
                not r["publishable"]
                for r in regions
                if r["fragment_u_fffd"] > 0 or r["fragment_hebrew_chars"] > 0
            ),
            "ACCEPTED_NOTE_PRESENT": len(accepted) >= 1,
            "QUARANTINE_NOTICE_PRESENT": bool(metadata["notice"]),
            "VISUAL_REFERENCE_COMPLETE": all(
                r["visual_reference"]
                and r["visual_reference"]["source_reference"] == f"sha256:{source_sha}"
                and r["visual_reference"]["pdf_page"] == number
                and len(r["visual_reference"]["bbox"]) == 4
                for r in regions
            ),
        }
        details[number]["PASS"] = (
            details[number]["page_status"] == "PARTIAL"
            and details[number]["accepted_count"] >= 1
            and details[number]["quarantined_count"] >= 1
            and details[number]["canonical_u_fffd"] == 0
            and details[number]["metadata_u_fffd"] == 0
            and details[number]["ACCEPTED_LOSS"] == 0
            and details[number]["QUARANTINED_LEAKAGE"] == 0
            and details[number]["CORRUPT_REGIONS_QUARANTINED"]
            and details[number]["QUARANTINE_NOTICE_PRESENT"]
            and details[number]["VISUAL_REFERENCE_COMPLETE"]
        )
    return {
        "frozen_pages": list(FROZEN_PAGES),
        "source_reference": f"sha256:{source_sha}",
        "pages": details,
        "PASS": all(item["PASS"] for item in details.values()),
    }


def visual_source_results(page_objects, source_sha: str) -> dict:
    total_regions = 0
    with_reference = 0
    invalid = []
    for number, publication in sorted(page_objects.items()):
        metadata = publication.metadata()
        for region in metadata["regions"]:
            total_regions += 1
            reference = region["visual_reference"]
            valid = (
                reference
                and reference["source_reference"] == f"sha256:{source_sha}"
                and reference["source_sha256"] == source_sha
                and reference["pdf_page"] == number
                and reference["region_id"] == region["region_id"]
                and len(reference["bbox"]) == 4
            )
            if valid:
                with_reference += 1
            else:
                invalid.append({"page": number, "region_id": region["region_id"]})
    return {
        "source_path": str(SOURCE),
        "source_exists": SOURCE.is_file(),
        "source_sha256": source_sha,
        "expected_sha256": EXPECTED_SOURCE_SHA,
        "pages": len(page_objects),
        "regions": total_regions,
        "regions_with_visual_reference": with_reference,
        "invalid_references": invalid,
        "quarantined_text_reachable_only_visually": True,
        "PASS": (
            SOURCE.is_file()
            and source_sha == EXPECTED_SOURCE_SHA
            and len(page_objects) == 284
            and total_regions > 0
            and with_reference == total_regions
            and not invalid
        ),
    }


def main() -> None:
    mixed = mixed_fixture_results()
    write("mixed-page-results.json", mixed)

    contract = contract_cases()
    contract["rules"] = CONTRACT_RULES
    contract["decision_source"] = "modules.library.automatic_region_certification_v5"
    contract["FIXTURE_GOOD_ACCEPTANCE_NOT_REQUIRED"] = True
    write("region-contract-v2.json", contract)

    worker = asyncio.run(worker_enforcement())
    write("worker-enforcement.json", worker)

    dry_run, page_objects, source_sha = real_c_dry_run()
    write("real-c-dry-run.json", dry_run)

    pages = frozen_pages(page_objects, source_sha)
    write("real-c-pages-55-56.json", pages)

    visual = visual_source_results(page_objects, source_sha)
    write("visual-source-results.json", visual)

    summary = {
        "mixed_page_PASS": mixed["PASS"],
        "region_contract_v2_PASS": contract["PASS"],
        "worker_enforcement_PASS": worker["PASS"],
        "real_c_dry_run_PASS": dry_run["PASS"],
        "real_c_pages_55_56_PASS": pages["PASS"],
        "visual_source_PASS": visual["PASS"],
        "real_c_totals": dry_run["totals"],
        "real_c_status_distribution": dry_run["status_distribution"],
        "real_c_document": dry_run["document"],
    }
    write("part-b-summary.json", summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise
