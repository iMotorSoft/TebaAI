"""File extractors for supported document formats."""

from __future__ import annotations

import hashlib
import pathlib

from modules.library.domain import ExtractionMethod, TextFormat
from modules.library.errors import ExtractionError, UnsupportedFileTypeError


SUPPORTED_EXTENSIONS: dict[str, tuple[TextFormat, ExtractionMethod]] = {
    ".md": (TextFormat.MARKDOWN, ExtractionMethod.RAW_MARKDOWN),
    ".markdown": (TextFormat.MARKDOWN, ExtractionMethod.RAW_MARKDOWN),
    ".txt": (TextFormat.PLAIN_TEXT, ExtractionMethod.RAW_TEXT),
    ".pdf": (TextFormat.MARKDOWN, ExtractionMethod.PYMUPDF4LLM),
}


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compute_file_sha256(file_path: str) -> str:
    with open(file_path, "rb") as f:
        return compute_sha256(f.read())


def detect_text_format(extension: str) -> tuple[TextFormat, ExtractionMethod]:
    """Detect text format and extraction method from file extension."""
    ext = extension.lower()
    result = SUPPORTED_EXTENSIONS.get(ext)
    if not result:
        raise UnsupportedFileTypeError(
            f"Unsupported file extension: {ext}. "
            f"Supported: {', '.join(SUPPORTED_EXTENSIONS)}"
        )
    return result


def extract_text(file_path: str) -> tuple[str, TextFormat, ExtractionMethod, dict]:
    """
    Extract text content from a file.

    Returns (content, text_format, extraction_method, metadata).
    """
    path = pathlib.Path(file_path)
    if not path.is_file():
        raise ExtractionError(f"File not found: {file_path}")

    ext = path.suffix.lower()
    text_format, method = detect_text_format(ext)

    metadata: dict = {"filename": path.name, "extension": ext, "size_bytes": path.stat().st_size}

    if method in (ExtractionMethod.RAW_MARKDOWN, ExtractionMethod.RAW_TEXT):
        content = path.read_text(encoding="utf-8")
        return content, text_format, method, metadata

    if method == ExtractionMethod.PYMUPDF4LLM:
        return _extract_pdf(path, metadata)

    raise ExtractionError(f"No extractor available for: {ext}")


def _extract_pdf(path: pathlib.Path, metadata: dict) -> tuple[str, TextFormat, ExtractionMethod, dict]:
    """Extract markdown from PDF using pymupdf4llm."""
    try:
        import pymupdf4llm
    except ImportError:
        raise ExtractionError(
            "pymupdf4llm is required for PDF extraction. Install with: uv add pymupdf4llm"
        )

    try:
        md_text = pymupdf4llm.to_markdown(str(path))
        metadata["extraction_library"] = "pymupdf4llm"
        metadata["extraction_version"] = getattr(pymupdf4llm, "__version__", "unknown")
        return md_text, TextFormat.MARKDOWN, ExtractionMethod.PYMUPDF4LLM, metadata
    except Exception as exc:
        raise ExtractionError(f"PDF extraction failed for {path.name}: {exc}") from exc
