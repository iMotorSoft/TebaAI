"""Forbidden-operation instrumentation for the C durable source restoration.

Installed inside the same process that performs the restoration. Any call to
ingestion, extraction, chunking, embedding, vector-write or generation
activation raises immediately and is counted. SQL write statements are also
recorded verbatim so the gate can prove only the authorized UPDATE ran.
"""
from __future__ import annotations

import json
from pathlib import Path

FORBIDDEN = {
    "ingest_calls": 0,
    "extract_calls": 0,
    "chunk_generation_calls": 0,
    "embedding_calls": 0,
    "vector_insert_delete_calls": 0,
    "generation_activation_calls": 0,
}

PATCHED: list[str] = []
SQL_WRITES: list[dict] = []
INSTALL_ERRORS: list[str] = []


def _raiser(counter: str, label: str):
    def wrapper(*args, **kwargs):
        FORBIDDEN[counter] += 1
        raise RuntimeError(f"forbidden operation attempted during restoration: {label}")

    wrapper.__name__ = f"monitored_{label}"
    return wrapper


def _patch(module_name: str, attr: str, counter: str, label: str) -> None:
    try:
        module = __import__(module_name, fromlist=[attr])
    except Exception as exc:  # noqa: BLE001
        INSTALL_ERRORS.append(f"{module_name}: {type(exc).__name__}: {exc}")
        return
    original = getattr(module, attr, None)
    if original is None:
        INSTALL_ERRORS.append(f"{module_name}.{attr} missing")
        return
    setattr(module, attr, _raiser(counter, label))
    PATCHED.append(f"{module_name}.{attr}")


def _patch_milvus() -> None:
    try:
        from pymilvus import MilvusClient
    except Exception as exc:  # noqa: BLE001
        INSTALL_ERRORS.append(f"pymilvus: {type(exc).__name__}: {exc}")
        return
    for method in ("insert", "upsert", "delete"):
        if hasattr(MilvusClient, method):
            setattr(MilvusClient, method, _raiser("vector_insert_delete_calls", f"milvus.{method}"))
            PATCHED.append(f"pymilvus.MilvusClient.{method}")
        else:
            INSTALL_ERRORS.append(f"pymilvus.MilvusClient.{method} missing")


def _patch_sql() -> None:
    import psycopg

    original = psycopg.AsyncCursor.execute

    async def execute(self, query, params=None, *, prepare=None, binary=None):
        text = query if isinstance(query, str) else getattr(query, "string", str(query))
        first = text.lstrip().split(None, 1)[0].upper() if text.strip() else ""
        if first in {"INSERT", "UPDATE", "DELETE", "TRUNCATE", "MERGE", "CREATE", "ALTER", "DROP"}:
            SQL_WRITES.append({"keyword": first, "statement": " ".join(text.split())})
        if prepare is None and binary is None:
            return await original(self, query, params)
        return await original(self, query, params, prepare=prepare, binary=binary)

    psycopg.AsyncCursor.execute = execute
    PATCHED.append("psycopg.AsyncCursor.execute")


def install() -> None:
    _patch("modules.library.extractors", "extract_text", "extract_calls", "extract_text")
    _patch("modules.library.extractors", "_extract_pdf", "extract_calls", "_extract_pdf")
    _patch("modules.library.extractors", "extract_pdf_with_page_markers", "extract_calls", "extract_pdf_with_page_markers")
    _patch("modules.library.extractors", "extract_pdf_columns_with_page_markers", "extract_calls", "extract_pdf_columns_with_page_markers")
    _patch("modules.library.extractors", "extract_pdf_with_region_certificates", "extract_calls", "extract_pdf_with_region_certificates")
    _patch("modules.library.page_first_pipeline", "extract_pdf_page_first", "extract_calls", "extract_pdf_page_first")
    _patch("modules.library.page_first_pipeline", "extract_pdf_region_published", "extract_calls", "extract_pdf_region_published")
    _patch("modules.library.generation", "ensure_logical_document", "generation_activation_calls", "ensure_logical_document")
    _patch("modules.library.generation", "register_generation", "generation_activation_calls", "register_generation")
    _patch("modules.library.generation", "set_generation_status", "generation_activation_calls", "set_generation_status")
    _patch("modules.library.generation", "activate_generation", "generation_activation_calls", "activate_generation")
    _patch("modules.library.generation", "switch_generation", "generation_activation_calls", "switch_generation")
    _patch("modules.embeddings.client", "embed_text", "embedding_calls", "embed_text")
    _patch("modules.embeddings.client", "embed_batch", "embedding_calls", "embed_batch")
    _patch_milvus()
    _patch_sql()


def report(allowed_writes: list[str]) -> dict:
    unexpected = [
        write for write in SQL_WRITES
        if not any(write["statement"].startswith(prefix) for prefix in allowed_writes)
    ]
    return {
        "instrumentation_process": "same process that performed the restoration",
        "patched_targets": PATCHED,
        "install_errors": INSTALL_ERRORS,
        "counters": FORBIDDEN,
        "sql_write_statements_observed": SQL_WRITES,
        "allowed_write_prefixes": allowed_writes,
        "unexpected_sql_writes": unexpected,
        "zero_forbidden_operations": all(value == 0 for value in FORBIDDEN.values()),
        "zero_unexpected_sql_writes": not unexpected,
        "limitations": (
            "In-process instrumentation covers the product entrypoints patched above; "
            "cross-process vector safety is additionally evidenced by read-only Milvus "
            "population digests before/after."
        ),
    }


def dump(path: Path, allowed_writes: list[str]) -> dict:
    body = report(allowed_writes)
    path.write_text(json.dumps(body, indent=2, allow_nan=False) + "\n")
    return body
