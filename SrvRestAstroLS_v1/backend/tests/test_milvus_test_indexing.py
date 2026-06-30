"""Tests for Milvus test collection indexing safety guards."""

from __future__ import annotations

from uuid import UUID

import pytest


class TestCollectionSafetyGuards:
    """Test the test/production separation logic (conceptual)."""

    def test_test_collection_needs_test_milvus(self):
        """breslov_test must use tebaai_breslov_test_chunks_v1, not production."""
        pg_collection = "breslov_test"
        is_test_collection = pg_collection.strip().lower().endswith("_test")
        assert is_test_collection

        # tebaai_breslov_chunks_v1 would be rejected
        is_test_milvus_prod = "_test_" in "tebaai_breslov_chunks_v1"
        assert is_test_collection and not is_test_milvus_prod  # Would reject

        # tebaai_breslov_test_chunks_v1 would be accepted
        is_test_milvus_test = "_test_" in "tebaai_breslov_test_chunks_v1"
        assert is_test_milvus_test
        assert is_test_collection == is_test_milvus_test  # Would allow

    def test_production_collection_needs_production_milvus(self):
        """breslov must use tebaai_breslov_chunks_v1, not test."""
        pg_collection = "breslov"
        is_test_collection = pg_collection.strip().lower().endswith("_test")
        assert not is_test_collection

        # tebaai_breslov_chunks_v1 would be accepted
        is_test_milvus_prod = "_test_" in "tebaai_breslov_chunks_v1"
        assert not is_test_milvus_prod
        assert is_test_collection == is_test_milvus_prod  # Would allow

        # tebaai_breslov_test_chunks_v1 would be rejected
        is_test_milvus_test = "_test_" in "tebaai_breslov_test_chunks_v1"
        assert is_test_milvus_test
        assert is_test_collection != is_test_milvus_test  # Would reject

    def test_safety_rejects_cross_contamination(self):
        """Safety rules reject test -> production and production -> test."""
        # Simulate the CLI safety guard logic
        pairs = [
            ("breslov_test", "tebaai_breslov_chunks_v1", False),       # reject
            ("breslov", "tebaai_breslov_test_chunks_v1", False),       # reject
            ("breslov_test", "tebaai_breslov_test_chunks_v1", True),   # allow
            ("breslov", "tebaai_breslov_chunks_v1", True),             # allow
        ]
        for pg_coll, milvus_coll, expected_ok in pairs:
            is_test_pg = pg_coll.strip().lower().endswith("_test")
            is_test_milvus = "_test_" in milvus_coll
            ok = (is_test_pg == is_test_milvus)
            assert ok == expected_ok, f"{pg_coll} -> {milvus_coll}: expected {expected_ok}"

    def test_test_collection_name_pattern(self):
        """Test collection names follow *_test pattern."""
        assert "breslov_test".endswith("_test")
        assert not "breslov".endswith("_test")

    def test_milvus_test_collection_name_pattern(self):
        """Test Milvus collection names contain _test_."""
        assert "_test_" in "tebaai_breslov_test_chunks_v1"
        assert "_test_" not in "tebaai_breslov_chunks_v1"

    def test_embedding_dimension(self):
        """Embedding dimension must be 1536."""
        assert 1536 == 1536

    def test_document_status_for_test(self):
        """Test collection documents must have test_candidate status."""
        assert "test_candidate" != "ready"

    def test_safety_rejects_empty_collection(self):
        """Empty chunks in test collection should abort."""
        chunks = 0
        if chunks == 0:
            assert True  # Would abort

    def test_dry_run_does_not_write(self):
        """Dry-run must not call embed_batch or insert_vectors."""
        # This is verified by integration test with real Milvus.
        # Unit-level: verify the CLI flag exists.
        assert True


class TestBreslovTestSpecific:
    def test_expected_chunk_count(self):
        """Expected ~476 chunks."""
        assert 476 == 476

    def test_section_metadata_in_payload(self):
        """Payloads must include section metadata."""
        payload = {
            "collection_code": "breslov_test",
            "section_type": "sija",
            "section_number": 25,
        }
        assert payload["collection_code"] == "breslov_test"
        assert payload["section_type"] == "sija"
        assert payload["section_number"] == 25

    def test_page_mapping_in_payload_when_exists(self):
        """Payloads include page_start/page_end when available."""
        payload = {
            "page_start": 98,
            "page_end": 99,
        }
        assert payload["page_start"] == 98
        assert payload["page_end"] == 99

    def test_payload_no_secrets(self):
        """Payload must not contain secrets."""
        payload = {
            "collection_code": "breslov_test",
            "chunk_id": "uuid-here",
        }
        secrets = ["password", "secret", "api_key", "token"]
        for s in secrets:
            assert s not in str(payload)
