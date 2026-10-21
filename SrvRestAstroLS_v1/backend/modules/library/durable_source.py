"""Original PDFs under the existing Content Manager storage root, never public paths."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import tempfile
from uuid import UUID

from globalVar import CONTENT_MANAGER_STORAGE_DIR


def source_path(document_id: UUID) -> Path:
    return Path(CONTENT_MANAGER_STORAGE_DIR).resolve() / "sources" / str(document_id) / "original.pdf"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def preserve_source(original: Path, document_id: UUID, expected_sha256: str) -> Path:
    """Atomic, hash-checked copy; a failed copy never removes the upload."""
    target = source_path(document_id)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if target.exists():
        if file_sha256(target) != expected_sha256:
            raise ValueError("Durable source hash mismatch")
        return target
    fd, temporary = tempfile.mkstemp(dir=target.parent, prefix=".source-")
    temporary = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as out, original.open("rb") as stream:
            shutil.copyfileobj(stream, out)
            out.flush()
            os.fsync(out.fileno())
        if file_sha256(temporary) != expected_sha256:
            raise ValueError("Source changed before durable preservation")
        os.replace(temporary, target)
        directory = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def remove_source(document_id: UUID) -> None:
    """Only the deterministic document-owned file, never a database-supplied path."""
    target = source_path(document_id)
    target.unlink(missing_ok=True)
    try:
        target.parent.rmdir()
    except OSError:
        pass


def source_reference(document_id: UUID, page: int | None = None) -> str:
    base = f"/library/documents/{document_id}/source"
    return f"{base}#page={page}" if page else base
