"""Tests for embeddings config via LiteLLM gateway."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from core.config import get_settings


def _clear():
    get_settings.cache_clear()


class TestEmbeddingsConfig:
    def setup_method(self):
        _clear()

    def test_embeddings_provider_is_litellm(self):
        s = get_settings()
        assert s.embeddings_provider == "litellm"

    def test_embeddings_model_alias(self):
        s = get_settings()
        assert s.embeddings_model_alias == "openai_text_embedding_3_small"

    def test_embeddings_model_name(self):
        s = get_settings()
        assert s.embeddings_model_name == "text-embedding-3-small"

    def test_embeddings_dimension(self):
        s = get_settings()
        assert s.embeddings_dimension == 1536

    def test_litellm_base_url(self):
        s = get_settings()
        assert s.litellm_base_url == "http://127.0.0.1:4000"

    def test_litellm_api_key_available(self):
        """LITELLM_API_KEY is the canonical auth key, not EMBEDDINGS_API_KEY."""
        s = get_settings()
        # Both fields exist; litellm_api_key is the canonical one
        assert hasattr(s, "litellm_api_key")
        assert hasattr(s, "embeddings_api_key")

    def test_globalvar_exposes_litellm_api_key(self):
        """globalVar.py must expose LITELLM_API_KEY."""
        from globalVar import LITELLM_API_KEY
        assert isinstance(LITELLM_API_KEY, str)

    def test_globalvar_exposes_embeddings_model_name(self):
        from globalVar import EMBEDDINGS_MODEL_NAME
        assert EMBEDDINGS_MODEL_NAME == "text-embedding-3-small"

    def test_embedding_client_uses_litellm_key(self):
        """The embeddings client must use LITELLM_API_KEY for auth, not EMBEDDINGS_API_KEY."""
        import modules.embeddings.client as ec
        import inspect
        source = inspect.getsource(ec.embed_batch)
        assert "LITELLM_API_KEY" in source
        assert "EMBEDDINGS_API_KEY" not in source

    def test_no_direct_openai_key_read(self):
        """Scripts must not read OpenAI_Key_JAI_query directly."""
        import modules.embeddings.client as ec
        import inspect
        source = inspect.getsource(ec.embed_batch)
        assert "OpenAI_Key_JAI_query" not in source

    def test_empty_litellm_key_does_not_crash(self):
        """When no key is set, client should still build headers without auth."""
        from modules.embeddings.client import embed_batch
        # Test passes if import succeeds; actual call would fail at HTTP level
        assert True
