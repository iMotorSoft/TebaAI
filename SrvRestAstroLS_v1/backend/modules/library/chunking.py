"""Document chunking — split text into chunks by paragraphs."""

from __future__ import annotations

import hashlib
from uuid import UUID, uuid4


DEFAULT_CHUNK_SIZE = 1800
DEFAULT_CHUNK_OVERLAP = 250
DEFAULT_MIN_CHUNK = 200


def make_chunk_uid(document_id: UUID, text_id: UUID, index: int) -> str:
    """Deterministic chunk UID."""
    raw = f"{document_id}/{text_id}/{index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def paragraph_chunks(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
    min_chunk: int = DEFAULT_MIN_CHUNK,
) -> list[dict]:
    """
    Split text into chunks by paragraphs.

    Returns list of dicts with keys: content, char_start, char_end.
    Tries to break on paragraph boundaries (double newline).
    """
    if not text.strip():
        return []

    # Split into paragraphs
    paragraphs = text.split("\n\n")
    chunks: list[dict] = []
    current = ""
    current_start = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # If adding this paragraph exceeds chunk_size, save current and start new
        if current and len(current) + len(para) + 2 > chunk_size:
            if len(current) >= min_chunk:
                end = current_start + len(current)
                chunks.append({
                    "content": current.strip(),
                    "char_start": current_start,
                    "char_end": end,
                })
            current_start = max(0, end - overlap) if chunks else 0
            # Carry overlap text from previous chunk
            overlap_text = current[-(overlap):] if overlap > 0 and len(current) > overlap else ""
            current = overlap_text
            current_start = max(0, end - overlap) if overlap > 0 else end

        if current:
            current += "\n\n" + para
        else:
            current = para

    # Last chunk
    if current.strip() and len(current.strip()) >= min_chunk:
        end = current_start + len(current)
        chunks.append({
            "content": current.strip(),
            "char_start": current_start,
            "char_end": end,
        })

    return chunks


def chunk_text(
    text: str,
    document_id: UUID,
    text_id: UUID,
    language: str = "es",
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
    min_chunk: int = DEFAULT_MIN_CHUNK,
) -> list[dict]:
    """
    Full chunking pipeline. Returns list of dicts ready for DB insert.

    Each dict has:
      id, document_id, document_text_id, chunk_index, chunk_uid,
      language, content, content_sha256, content_length,
      char_start, char_end
    """
    raw_chunks = paragraph_chunks(text, chunk_size, overlap, min_chunk)
    result: list[dict] = []

    for idx, raw in enumerate(raw_chunks):
        content = raw["content"]
        content_bytes = content.encode("utf-8")
        sha256 = hashlib.sha256(content_bytes).hexdigest()

        result.append({
            "id": uuid4(),
            "document_id": document_id,
            "document_text_id": text_id,
            "chunk_index": idx,
            "chunk_uid": make_chunk_uid(document_id, text_id, idx),
            "language": language,
            "content": content,
            "content_sha256": sha256,
            "content_length": len(content),
            "char_start": raw["char_start"],
            "char_end": raw["char_end"],
            "token_count_estimate": max(1, len(content) // 4),
        })

    return result
