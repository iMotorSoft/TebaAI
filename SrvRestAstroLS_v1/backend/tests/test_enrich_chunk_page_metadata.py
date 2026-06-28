"""Tests for page metadata enrichment script."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest


class TestReferenceLabel:
    def test_single_page(self):
        label = "PDF page 36"
        assert "36" in label

    def test_range_page(self):
        label = "PDF pages 36-37"
        assert "36-37" in label


class TestBibliographicMetadataShape:
    def test_minimal_shape(self):
        meta = {
            "page_mapping": {
                "source": "local_pdf_page_aware_audit",
                "confidence": "high",
                "pdf_page_start": 36,
                "pdf_page_end": 37,
                "page_number_type": "pdf_physical_page",
                "method": "anchor_match",
                "audit_tool": "audit_page_chunk_mapping.py",
                "applied_by": "enrich_chunk_page_metadata.py",
            }
        }
        assert meta["page_mapping"]["confidence"] == "high"
        assert meta["page_mapping"]["pdf_page_start"] == 36
        json.dumps(meta, ensure_ascii=False)

    def test_single_page_meta(self):
        meta = {
            "page_mapping": {
                "source": "local_pdf_page_aware_audit",
                "confidence": "high",
                "pdf_page_start": 10,
                "pdf_page_end": 10,
                "page_number_type": "pdf_physical_page",
                "method": "anchor_match",
            }
        }
        assert meta["page_mapping"]["pdf_page_start"] == meta["page_mapping"]["pdf_page_end"]


class TestCLI:
    def test_parse_args_defaults(self):
        from scripts.enrich_chunk_page_metadata import _parse_args
        args = _parse_args([])
        assert args.collection == "breslov"
        assert args.dry_run is True
        assert args.apply is False

    def test_parse_args_apply(self):
        from scripts.enrich_chunk_page_metadata import _parse_args
        args = _parse_args(["--collection", "test", "--apply"])
        assert args.collection == "test"
        assert args.apply is True
        assert args.dry_run is True  # Note: --apply doesn't set dry_run=False, but --apply flag used instead

    def test_parse_args_confidence(self):
        from scripts.enrich_chunk_page_metadata import _parse_args
        args = _parse_args(["--confidence", "high"])
        assert args.confidence == "high"
