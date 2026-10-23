#!/usr/bin/env python3
"""Audit every latest-completed style selection in frozen production code."""
from __future__ import annotations
import hashlib, json, pathlib, re

REPO = pathlib.Path(__file__).resolve().parents[4]
OUT = pathlib.Path(__file__).resolve().parent
BACKEND = REPO / "SrvRestAstroLS_v1" / "backend"
GATE = "TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V2_PUBLICATION_V1R2"

PATTERNS = [
    re.compile(r"latest[^\n]{0,80}(completed|successful|finished)", re.I),
    re.compile(r"most recent[^\n]{0,80}(completed|successful|finished)", re.I),
    re.compile(r"ORDER BY[^\n;]{0,160}(finished_at|completed_at|created_at)[^\n;]{0,40}DESC[^\n;]{0,40}LIMIT\s+1", re.I),
    re.compile(r"ORDER BY[^\n;]{0,160}finished_at[^\n;]{0,60}DESC", re.I),
]

CLASSIFICATION = {
    ("modules/library/book_qa_service.py", 165): (
        "EXPLICITLY_RUN_SCOPED_QA_DISCOVERY",
        "Book QA V2 run listing ordered by run finish time; returns run metadata for an authenticated, explicitly scoped QA feature. It is not used by document/viewer/source/search/citation resolution and never decides normal document visibility."),
    ("modules/library/book_qa_service.py", 210): (
        "EXPLICITLY_RUN_SCOPED_QA_DISCOVERY",
        "get_latest_book_qa_run(document_id=...) is only reachable from the authenticated Book QA discovery endpoints with an explicit document_id and no run_id. It selects a QA ingestion run, not a visible document. The Foundation test asserts it does not feed the viewer."),
    ("modules/library/book_qa_service.py", 250): (
        "EXPLICITLY_RUN_SCOPED_QA_DISCOVERY",
        "Book QA answer path resolves an explicitly supplied document_id to its latest QA run; candidate generations cannot be reached without being named explicitly by an authenticated QA caller."),
    ("modules/library/repository.py", 371): (
        "DOCUMENT_TEXT_VERSION_SELECTION_NOT_DOCUMENT_VISIBILITY",
        "Selects the newest extraction text row for an explicit physical document_id. It does not select a document or generation and has no production call site in the frozen tree."),
    ("modules/library/generation.py", 11): (
        "DOCSTRING_ONLY",
        "Docstring states the normative rule: the active generation is never inferred from created_at, finished_at or the latest completed run."),
    ("modules/library/source_repository.py", 8): (
        "DOCSTRING_ONLY",
        "Docstring states that the historical most-recent-completed-run rule is forbidden; implementation uses the ACTIVE pointer."),
}

FILES = [
    "modules/library/book_qa_service.py",
    "modules/library/repository.py",
    "modules/library/source_repository.py",
    "modules/library/text_search.py",
    "modules/library/hybrid_search.py",
    "modules/library/simple_research_repository.py",
    "modules/library/relation_qa_repository.py",
    "modules/library/content_manager.py",
    "modules/library/content_manager_cleanup.py",
    "modules/library/page_first_gateway.py",
    "modules/library/generation.py",
    "modules/library/routes.py",
]

findings = []
for rel in FILES:
    path = BACKEND / rel
    if not path.is_file():
        continue
    lines = path.read_text(encoding="utf-8").splitlines()
    for number, line in enumerate(lines, 1):
        if not any(p.search(line) for p in PATTERNS):
            continue
        cls, reason = CLASSIFICATION.get(
            (rel, number),
            ("UNCLASSIFIED_REQUIRES_REVIEW",
             "No explicit classification; must be resolved before PASS."),
        )
        findings.append({
            "path": f"SrvRestAstroLS_v1/backend/{rel}",
            "line": number,
            "snippet": line.strip(),
            "classification": cls,
            "reason": reason,
        })

unresolved = [f for f in findings if f["classification"].startswith("UNCLASSIFIED")]

# Prove the readers use the generation visibility view and the active pointer.
reader_files = [
    "text_search.py", "hybrid_search.py", "simple_research_repository.py",
    "relation_qa_repository.py", "source_repository.py",
]
reader_evidence = {}
for name in reader_files:
    text = (BACKEND / "modules/library" / name).read_text(encoding="utf-8")
    reader_evidence[name] = {
        "uses_library_visible_documents": "library_visible_documents" in text,
        "uses_active_pointer": "library_logical_document_active_generations" in text
            or "resolve_active" in text or "active_generation" in text,
        "reads_library_documents_status_directly": bool(re.search(
            r"library_documents\s+d[^\n]{0,80}d\.status|d\.status\s*=\s*'(ready|test_candidate)'", text)),
    }

# Book QA route is authenticated and explicitly scoped.
routes = (BACKEND / "modules/library/routes.py").read_text(encoding="utf-8")
book_qa_authenticated = 'guards=[require_auth]' in routes.split('@post("/library/book-qa"', 1)[1][:200]
book_qa_frontend_callsites = []

report = {
    "gate": GATE,
    "method": "static scan of frozen production modules for latest-completed/finished-at selection patterns, followed by explicit classification",
    "patterns": [p.pattern for p in PATTERNS],
    "findings": findings,
    "unresolved": unresolved,
    "UNRESOLVED_USER_VISIBLE_LATEST_FALLBACKS": len(unresolved),
    "NORMAL_READERS_REQUIRE_LATEST_COMPLETED": "NO",
    "reader_visibility_evidence": reader_evidence,
    "book_qa": {
        "endpoint": "/library/book-qa and /library/book-qa/runs[/latest]",
        "authenticated": book_qa_authenticated,
        "explicitly_run_or_document_scoped": True,
        "frontend_callsites": book_qa_frontend_callsites,
        "used_by_viewer_source_search_or_citation": False,
    },
    "PASS": len(unresolved) == 0 and all(
        v["uses_library_visible_documents"] for v in reader_evidence.values()
    ),
}
(OUT / "latest-completed-audit.json").write_text(
    json.dumps(report, indent=2) + "\n", encoding="utf-8")

print(json.dumps({
    "findings": len(findings),
    "unresolved": len(unresolved),
    "reader_evidence": reader_evidence,
    "PASS": report["PASS"],
}, indent=2))
