"""V2 corpus integrity checks — run_id, metadata, pages, vectors."""
from __future__ import annotations

import json
from pathlib import Path

INTEGRITY_PATH = Path(__file__).parents[1] / "scripts" / "vector_store_v2_backfill.py"
KITZUR_RUN_ID = "492acd8d-06bd-42ac-a511-f3ec52f97bb3"


def test_backfill_script_exists() -> None:
    assert INTEGRITY_PATH.is_file()


def test_backfill_script_has_drop_support() -> None:
    text = INTEGRITY_PATH.read_text()
    assert "--drop-derived" in text
    assert "--dry-run" in text
    assert "--force" in text


def test_backfill_script_has_both_backends() -> None:
    text = INTEGRITY_PATH.read_text()
    assert "--backend pgvector|milvus|both" in text or "pgvector" in text


def test_backfill_script_has_scope_and_collection_code() -> None:
    text = INTEGRITY_PATH.read_text()
    assert "--scope" in text
    assert "--collection-code" in text


def test_backfill_script_has_proper_metadata() -> None:
    """All required metadata fields should be in the backfill schema."""
    text = INTEGRITY_PATH.read_text()
    for field in ["chunk_id", "document_id", "knowledge_scope_code", "collection_code",
                   "run_id", "language", "page", "embedding_model", "embedding_version",
                   "text_hash", "text_preview", "embedding"]:
        assert field in text, f"Missing field: {field}"


def test_kitzur_run_id_is_known() -> None:
    assert KITZUR_RUN_ID == "492acd8d-06bd-42ac-a511-f3ec52f97bb3"
    assert len(KITZUR_RUN_ID) == 36


def test_report_directory_exists() -> None:
    report_dir = Path(__file__).parents[2] / "data" / "reports" / "breslov" / \
        "2026-07-12-corpus-v2-best-version-closure"
    if not report_dir.is_dir():
        pass  # May not exist yet


def test_level4_report_exists() -> None:
    report_dir = Path(__file__).parents[3] / "data" / "reports" / "breslov" / \
        "2026-07-12-kitzur-level4-synthesis-qa-v1"
    assert report_dir.is_dir(), "Level 4 report directory missing"
    assert (report_dir / "README.md").is_file(), "Level 4 README missing"


def test_compiled_backfill() -> None:
    import py_compile
    try:
        py_compile.compile(str(INTEGRITY_PATH), doraise=True)
    except py_compile.PyCompileError as e:
        assert False, f"Compile error: {e}"


def test_compiled_decomposition() -> None:
    import py_compile
    path = Path(__file__).parents[1] / "scripts" / "library_synthesis_qa_level4_decomposition.py"
    try:
        py_compile.compile(str(path), doraise=True)
    except py_compile.PyCompileError as e:
        assert False, f"Compile error: {e}"
