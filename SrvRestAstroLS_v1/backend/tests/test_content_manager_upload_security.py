from __future__ import annotations

import pymupdf
import pytest

from modules.library.content_manager import _inspect_pdf, validate_and_store_upload


def test_corrupt_pdf_with_magic_header_is_rejected(tmp_path):
    path = tmp_path / "corrupt.pdf"
    path.write_bytes(b"%PDF-1.7\nnot-a-real-pdf")
    with pytest.raises(ValueError, match="corrupto"):
        _inspect_pdf(str(path))


def test_encrypted_pdf_is_rejected(tmp_path):
    path = tmp_path / "protected.pdf"
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "contenido protegido")
    document.save(
        path,
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw="owner-secret",
        user_pw="reader-secret",
    )
    document.close()
    with pytest.raises(ValueError, match="protegido o cifrado"):
        _inspect_pdf(str(path))


@pytest.mark.asyncio
async def test_upload_rejects_extension_and_declared_mime_before_persistence():
    with pytest.raises(ValueError, match="extensión"):
        await validate_and_store_upload(
            None,
            file_content=b"%PDF-1.7",
            original_filename="payload.exe",
            declared_mime_type="application/pdf",
            actor_user_id="actor",
        )
    with pytest.raises(ValueError, match="MIME"):
        await validate_and_store_upload(
            None,
            file_content=b"%PDF-1.7",
            original_filename="payload.pdf",
            declared_mime_type="application/octet-stream",
            actor_user_id="actor",
        )
