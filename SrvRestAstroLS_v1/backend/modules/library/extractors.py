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
        metadata["page_markers"] = False
        return md_text, TextFormat.MARKDOWN, ExtractionMethod.PYMUPDF4LLM, metadata
    except Exception as exc:
        raise ExtractionError(f"PDF extraction failed for {path.name}: {exc}") from exc


def extract_pdf_with_page_markers(
    pdf_path: str,
    page_from: int = 1,
    page_to: int | None = None,
    marker_template: str = "## Page {page}",
) -> tuple[str, list[dict], dict]:
    """Extract PDF page-by-page with controlled page markers.

    Each page is extracted individually via PyMuPDF4LLM and wrapped with
    *marker_template* (default: ``## Page N``). Returns:
      - combined_markdown: str with markers inserted.
      - page_metadata: list of dicts with page_number, char_start, char_end,
        char_count, hebrew_count.
      - extraction_metadata: dict with library version, etc.

    Use this for modern Unicode PDFs where PyMuPDF4LLM bulk extraction
    does not emit page markers.
    """
    import pymupdf as fitz
    try:
        import pymupdf4llm
    except ImportError:
        raise ExtractionError("pymupdf4llm is required for page-by-page extraction")

    doc = fitz.open(pdf_path)
    total_pages = doc.page_count
    page_to = page_to or total_pages
    doc.close()

    pages_md: list[str] = []
    page_metadata: list[dict] = []
    char_offset = 0

    for pg in range(page_from, page_to + 1):
        # PyMuPDF4LLM uses 0-indexed pages internally
        pg_md = pymupdf4llm.to_markdown(pdf_path, pages=[pg - 1])
        marker = marker_template.format(page=pg)
        page_block = f"{marker}\n\n{pg_md}"
        start = char_offset
        end = char_offset + len(page_block)

        he_count = sum(1 for c in pg_md if "\u0590" <= c <= "\u05ff")
        la_count = sum(1 for c in pg_md if c.isascii() and c.isalpha())

        pages_md.append(page_block)
        page_metadata.append({
            "page_number": pg,
            "char_start": start,
            "char_end": end,
            "char_count": len(pg_md),
            "hebrew_count": he_count,
            "latin_count": la_count,
        })
        char_offset = end

    combined = "\n\n".join(pages_md)
    extraction_metadata = {
        "extraction_library": "pymupdf4llm",
        "extraction_method": "page_by_page_with_markers",
        "page_from": page_from,
        "page_to": page_to,
        "pages_processed": page_to - page_from + 1,
        "total_chars": len(combined),
        "total_hebrew": sum(m["hebrew_count"] for m in page_metadata),
        "page_markers": True,
        "marker_template": marker_template,
    }

    return combined, page_metadata, extraction_metadata


def extract_pdf_columns_with_page_markers(
    pdf_path: str,
    page_from: int = 1,
    page_to: int | None = None,
    rtl_columns: bool = True,
) -> tuple[str, list[dict], dict]:
    """Extract Hebrew PDF with column-aware ordering using fitz sorted text.

    Uses ``page.get_text('text', sort=True)`` which returns text sorted by
    (y, x) position. For RTL, this interleaves columns but preserves connected
    Hebrew text within the page's logical reading flow.

    Returns:
      - combined_markdown
      - page_metadata list
      - extraction_metadata dict
    """
    import pymupdf as fitz

    doc = fitz.open(pdf_path)
    total = doc.page_count
    page_to = page_to or total
    page_from = max(1, page_from)
    page_to = min(page_to, total)

    pages_md: list[str] = []
    page_meta: list[dict] = []
    char_offset = 0

    for pg in range(page_from, page_to + 1):
        page = doc.load_page(pg - 1)
        page_text = page.get_text("text", sort=True).strip()
        marker = f"## Page {pg}"
        block = f"{marker}\n\n{page_text}"
        start = char_offset
        end = char_offset + len(block)
        he = sum(1 for c in page_text if "\u0590" <= c <= "\u05ff")
        la = sum(1 for c in page_text if c.isascii() and c.isalpha())

        pages_md.append(block)
        page_meta.append({
            "page_number": pg,
            "char_start": start, "char_end": end,
            "char_count": len(page_text),
            "hebrew_count": he, "latin_count": la,
        })
        char_offset = end

    doc.close()
    combined = "\n\n".join(pages_md)
    xmeta = {
        "extraction_library": "fitz (text, sort=True)",
        "extraction_method": "column_aware",
        "page_from": page_from, "page_to": page_to,
        "pages_processed": page_to - page_from + 1,
        "total_chars": len(combined),
        "page_markers": True,
    }
    return combined, page_meta, xmeta


def resolve_page_range_from_markers(
    char_start: int,
    char_end: int,
    markers: list[dict],
) -> tuple[int | None, int | None]:
    """Resolve page_start/page_end for a char range using marker metadata.

    *markers* must be the list returned by ``extract_pdf_with_page_markers``
    (or equivalent list with ``char_start`` and ``page_number`` keys).
    """
    if not markers:
        return None, None
    sp: int | None = None
    ep: int | None = None
    for m in markers:
        ms = m["char_start"]
        me = m.get("char_end", ms)
        pg = m["page_number"]
        if ms <= char_start:
            sp = pg
        if ms <= char_end:
            ep = pg
        if ms <= char_end < me:
            ep = pg
            break
    return sp, ep
