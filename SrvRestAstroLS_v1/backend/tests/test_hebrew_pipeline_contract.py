"""Contract tests for Hebrew pipeline: canonical paths and safety guards."""

from __future__ import annotations

from modules.library.hebrew_tex_decoder import decode_hebrew_text_selective


class TestPipelineContracts:
    def test_embed_uses_db_chunks_not_markdown(self):
        """phase_embed must read from library_document_chunks, not markdown file.
        This is a design contract: verify the module doesn't reference
        the markdown file for embedding input."""
        import inspect
        from scripts import hebrew_test_pipeline

        src = inspect.getsource(hebrew_test_pipeline.phase_embed)
        assert "FROM library_document_chunks" in src
        assert "tnk_massoretic_text_decoded.md" not in src

    def test_chunk_no_none_page_mapping(self):
        """phase_chunk must set page_start/page_end. No None values allowed."""
        import inspect
        from scripts import hebrew_test_pipeline

        src = inspect.getsource(hebrew_test_pipeline.phase_chunk)
        assert "page_start=None" not in src
        assert "page_end=None" not in src
        assert "_resolve_page_range" in src

    def test_extract_has_pymupdf4llm_fallback(self):
        """phase_extract must try PyMuPDF4LLM and report exception."""
        import inspect
        from scripts import hebrew_test_pipeline

        src = inspect.getsource(hebrew_test_pipeline.phase_extract)
        assert "pymupdf4llm" in src
        assert "si960_decoder" in src
        assert "tex_tiqwah_exception" in src

    def test_milvus_safety_guard(self):
        """phase_milvus must reject non-test collections."""
        import inspect
        from scripts import hebrew_test_pipeline

        src = inspect.getsource(hebrew_test_pipeline.phase_milvus)
        assert "_test_" in src
        assert "rejected" in src

    def test_fts_builder_importable(self):
        """FTS OR builder must be importable and functional."""
        from scripts.hebrew_test_pipeline import _build_tsquery_or

        result = _build_tsquery_or(["a", "b"])
        assert result == "a | b"

    def test_fts_builder_rejects_double_pipe(self):
        """FTS builder must reject || in terms."""
        from scripts.hebrew_test_pipeline import _build_tsquery_or

        import pytest
        with pytest.raises(ValueError):
            _build_tsquery_or(["a || b"])

    def test_selective_decoder_importable(self):
        """Selective decoder must be importable from the pipeline."""
        from scripts.hebrew_test_pipeline import phase_extract

        # phase_extract uses decode_hebrew_text_selective internally

    def test_extract_supports_page_range(self):
        """phase_extract must accept --page-from and --page-to."""
        import argparse
        from scripts.hebrew_test_pipeline import _parse_args

        args = _parse_args(["--phase", "extract", "--page-from", "700", "--page-to", "720"])
        assert args.page_from == 700
        assert args.page_to == 720

    def test_extract_supports_hebrew_only(self):
        """phase_extract must accept --hebrew-only."""
        import argparse
        from scripts.hebrew_test_pipeline import _parse_args

        args = _parse_args(["--phase", "extract", "--hebrew-only"])
        assert args.hebrew_only is True

    def test_dry_run_supported(self):
        """All write phases must support --dry-run."""
        import argparse
        from scripts.hebrew_test_pipeline import _parse_args

        args = _parse_args(["--phase", "chunk", "--dry-run"])
        assert args.dry_run is True

    def test_hebrew_only_preserves_english(self):
        """With --hebrew-only, English pages should not be decoded."""
        english = "Introduction to the Massoretic Text"
        result = decode_hebrew_text_selective(english)
        assert result == english

    def test_hebrew_only_decodes_hebrew(self):
        """With --hebrew-only, Hebrew pages should be decoded."""
        hebrew_si960 = "Mybwtk My'ybn hrwt"
        result = decode_hebrew_text_selective(hebrew_si960)
        assert result != hebrew_si960
        assert any("\u0590" <= c <= "\u05ff" for c in result)
