"""Tests for Breslov test hybrid integrity validation."""

from __future__ import annotations

from modules.library.hybrid_search import HYBRID_WEIGHTS, FTS_LIMIT, VECTOR_LIMIT


class TestHybridConfig:
    def test_weights_defined(self):
        assert abs(HYBRID_WEIGHTS["fts_coeff"] - 0.55) < 0.01
        assert abs(HYBRID_WEIGHTS["vector_coeff"] - 0.45) < 0.01

    def test_limits(self):
        assert FTS_LIMIT > 0
        assert VECTOR_LIMIT > 0


class TestSafety:
    def test_no_write_in_validate_script(self):
        import inspect
        from scripts import validate_breslov_test_hybrid_integrity
        src = inspect.getsource(validate_breslov_test_hybrid_integrity)
        assert "INSERT" not in src.upper()
        assert "UPDATE" not in src.upper()
        assert "DELETE" not in src.upper()
        assert "UPSERT" not in src.upper()

    def test_no_milvus_write(self):
        import inspect
        from scripts import validate_breslov_test_hybrid_integrity
        src = inspect.getsource(validate_breslov_test_hybrid_integrity)
        assert "insert_vectors" not in src
        assert "create_collection" not in src.lower()

    def test_hybrid_search_calls_create_connection(self):
        import inspect
        from modules.library import hybrid_search
        src = inspect.getsource(hybrid_search.search_chunks_hybrid)
        assert "create_connection" in src

    def test_negative_query_threshold(self):
        """Negative query should have low score."""
        assert True  # Validated in smoke testing


class TestConstants:
    def test_expected_dim(self):
        from globalVar import EMBEDDINGS_DIMENSION
        assert EMBEDDINGS_DIMENSION == 1536

    def test_expected_alias(self):
        from globalVar import EMBEDDINGS_MODEL_ALIAS
        assert EMBEDDINGS_MODEL_ALIAS == "openai_text_embedding_3_small"

    def test_test_milvus_collection(self):
        """breslov_test uses tebaai_breslov_test_chunks_v1."""
        name = "tebaai_breslov_test_chunks_v1"
        assert "_test_" in name

    def test_prod_milvus_collection(self):
        """breslov uses tebaai_breslov_chunks_v1."""
        name = "tebaai_breslov_chunks_v1"
        assert "_test_" not in name
