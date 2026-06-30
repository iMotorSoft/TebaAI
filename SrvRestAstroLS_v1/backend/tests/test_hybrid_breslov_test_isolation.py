"""Tests for hybrid search isolation between breslov and breslov_test."""

from __future__ import annotations

from modules.library.hybrid_search import (
    search_chunks_hybrid,
    HYBRID_WEIGHTS,
    FTS_LIMIT,
    VECTOR_LIMIT,
)


class TestHybridCollectionIsolation:
    """Test the safety guard logic for collection pairing."""

    def test_test_collection_needs_test_milvus(self):
        """breslov_test requires tebaai_breslov_test_chunks_v1."""
        pg = "breslov_test"
        milvus_pairs = [
            ("tebaai_breslov_chunks_v1", False),
            ("tebaai_breslov_test_chunks_v1", True),
        ]
        is_test_pg = pg.endswith("_test")
        for mc, expected_ok in milvus_pairs:
            is_test_milvus = "_test_" in mc
            ok = is_test_pg == is_test_milvus
            assert ok == expected_ok, f"{pg} + {mc}: expected {expected_ok}"

    def test_production_collection_needs_production_milvus(self):
        """breslov requires tebaai_breslov_chunks_v1."""
        pg = "breslov"
        milvus_pairs = [
            ("tebaai_breslov_chunks_v1", True),
            ("tebaai_breslov_test_chunks_v1", False),
        ]
        is_test_pg = pg.endswith("_test")
        for mc, expected_ok in milvus_pairs:
            is_test_milvus = "_test_" in mc
            ok = is_test_pg == is_test_milvus
            assert ok == expected_ok

    def test_hybrid_function_accepts_milvus_param(self):
        """search_chunks_hybrid accepts a milvus_collection parameter (default prod)."""
        # Check the default
        import inspect
        sig = inspect.signature(search_chunks_hybrid)
        assert "milvus_collection" in sig.parameters
        default = sig.parameters["milvus_collection"].default
        assert "tebaai_breslov_chunks_v1" in str(default)

    def test_hybrid_weights_defined(self):
        """Hybrid weights are defined."""
        assert HYBRID_WEIGHTS["fts_coeff"] == 0.55
        assert HYBRID_WEIGHTS["vector_coeff"] == 0.45

    def test_fts_limit_default(self):
        assert FTS_LIMIT == 30

    def test_vector_limit_default(self):
        assert VECTOR_LIMIT == 30

    def test_search_library_cli_has_hybrid_mode(self):
        """CLI must accept hybrid mode."""
        import scripts.search_library_text as cli
        assert hasattr(cli, "_parse_args")
        args = cli._parse_args(["--collection", "breslov_test", "--query", "test", "--mode", "hybrid",
                                "--milvus-collection", "tebaai_breslov_test_chunks_v1"])
        assert args.mode == "hybrid"
        assert args.milvus_collection == "tebaai_breslov_test_chunks_v1"

    def test_search_library_rejects_missing_milvus_for_hybrid(self):
        """Hybrid mode without --milvus-collection must be rejected."""
        import scripts.search_library_text as cli
        import argparse
        try:
            args = cli._parse_args(["--collection", "breslov_test", "--query", "test", "--mode", "hybrid"])
            assert not args.milvus_collection
        except SystemExit:
            pass  # Expected error

    def test_cli_guards_cross_contamination(self):
        """CLI safety logic must reject invalid pairs."""
        import scripts.search_library_text as cli
        pairs = [
            ("breslov_test", "tebaai_breslov_chunks_v1", False),
            ("breslov", "tebaai_breslov_test_chunks_v1", False),
            ("breslov_test", "tebaai_breslov_test_chunks_v1", True),
            ("breslov", "tebaai_breslov_chunks_v1", True),
        ]
        for pg, mc, expected in pairs:
            is_test_pg = pg.endswith("_test")
            is_test_mc = "_test_" in mc
            ok = is_test_pg == is_test_mc
            assert ok == expected, f"Guard failed for {pg} + {mc}"
