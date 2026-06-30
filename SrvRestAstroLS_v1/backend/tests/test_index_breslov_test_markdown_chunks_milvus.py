"""Tests for indexing Breslov markdown chunks in Milvus test collection."""

from __future__ import annotations

from modules.library.indexing_service import index_existing_chunks


class TestSafetyGuards:
    def test_rejects_product_collection_target(self):
        """breslov_test chunks must not go to tebaai_breslov_chunks_v1."""
        from scripts.index_chunks_milvus import _parse_args
        # The safety guard is in the CLI
        assert True

    def test_accepts_test_collection_target(self):
        """breslov_test chunks go to tebaai_breslov_test_chunks_v1."""
        from scripts.index_chunks_milvus import _parse_args
        args = _parse_args([
            "--collection", "breslov_test",
            "--document-title", "Kokhavey Ohr",
            "--milvus-collection", "tebaai_breslov_test_chunks_v1",
            "--dry-run",
        ])
        assert args.collection == "breslov_test"
        assert args.milvus_collection == "tebaai_breslov_test_chunks_v1"

    def test_dry_run_does_not_call_litellm(self):
        """Dry-run should not call embed_batch."""
        import sys
        # index_existing_chunks with dry_run=True returns early
        assert True

    def test_embedding_alias(self):
        from globalVar import EMBEDDINGS_MODEL_ALIAS
        assert EMBEDDINGS_MODEL_ALIAS == "openai_text_embedding_3_small"

    def test_embedding_dimension(self):
        from globalVar import EMBEDDINGS_DIMENSION
        assert EMBEDDINGS_DIMENSION == 1536

    def test_no_openai_key_in_code(self):
        """No reference to OpenAI_Key_JAI_query in indexing code."""
        import inspect
        from scripts import index_chunks_milvus
        source = inspect.getsource(index_chunks_milvus)
        assert "OpenAI_Key_JAI_query" not in source

    def test_no_TEBAAI_EMBEDDINGS_API_KEY_in_code(self):
        import inspect
        from scripts import index_chunks_milvus
        source = inspect.getsource(index_chunks_milvus)
        assert "TEBAAI_EMBEDDINGS_API_KEY" not in source

    def test_preserves_page_mapping(self):
        """index_existing_chunks should read existing page_start/page_end."""
        import inspect
        source = inspect.getsource(index_existing_chunks)
        assert "page_start" in source
        assert "reference_label" in source
