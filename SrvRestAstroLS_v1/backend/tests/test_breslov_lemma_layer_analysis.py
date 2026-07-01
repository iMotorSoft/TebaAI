"""Tests for Breslov lemma/shoresh layer analysis."""

from __future__ import annotations

from scripts.analyze_breslov_lemma_layer import (
    SEED_LEXICON,
    _expand_query_terms,
    _assemble_expanded_query,
    _normalize,
)


class TestNormalization:
    def test_unaccent(self):
        assert _normalize("emuná") == "emuna"
        assert _normalize("tefilá") == "tefila"
        assert _normalize("teshuvá") == "teshuva"

    def test_lowercase(self):
        assert _normalize("HaShem") == "hashem"

    def test_removes_punctuation(self):
        assert _normalize("yetzer hará,") == "yetzer hara"


class TestLexiconSeed:
    def test_has_expected_concepts(self):
        expected = {"emunah", "tefillah", "teshuvah", "hitbodedut",
                    "tzadik", "yetzer_hara", "hashem", "rebbe_nachman"}
        for e in expected:
            assert e in SEED_LEXICON, f"Missing: {e}"

    def test_minimum_concepts(self):
        assert len(SEED_LEXICON) >= 8

    def test_each_concept_has_labels(self):
        for cid, entry in SEED_LEXICON.items():
            assert "labels" in entry, f"{cid} missing labels"
            assert "confidence" in entry, f"{cid} missing confidence"

    def test_confidence_valid(self):
        for entry in SEED_LEXICON.values():
            assert entry["confidence"] in ("curated", "candidate")


class TestQueryExpansion:
    def test_expand_returns_list(self):
        terms = _expand_query_terms("emunah")
        assert len(terms) > 0
        assert isinstance(terms, list)

    def test_expand_includes_primary(self):
        terms = _expand_query_terms("emunah")
        assert "emuná" in terms or "emuna" in terms

    def test_expand_includes_transliterations(self):
        terms = _expand_query_terms("rebbe_nachman")
        assert any("nachman" in t.lower() for t in terms)

    def test_assemble_query(self):
        q = _assemble_expanded_query("emunah", "emuná")
        assert "emuná" in q

    def test_assemble_includes_or(self):
        q = _assemble_expanded_query("emunah", "emuná")
        assert "OR" in q


class TestSafety:
    def test_no_db_writes(self):
        import inspect
        from scripts import analyze_breslov_lemma_layer
        src = inspect.getsource(analyze_breslov_lemma_layer)
        assert "INSERT" not in src.upper()
        assert "UPDATE" not in src.upper()
        assert "DELETE" not in src.upper()
        assert "UPSERT" not in src.upper()

    def test_no_milvus_writes(self):
        import inspect
        from scripts import analyze_breslov_lemma_layer
        src = inspect.getsource(analyze_breslov_lemma_layer)
        assert "insert_vectors" not in src
        assert "create_collection" not in src.lower()

    def test_no_openai_key(self):
        import inspect
        from scripts import analyze_breslov_lemma_layer
        src = inspect.getsource(analyze_breslov_lemma_layer)
        assert "OpenAI_Key_JAI_query" not in src
        assert "TEBAAI_EMBEDDINGS_API_KEY" not in src
