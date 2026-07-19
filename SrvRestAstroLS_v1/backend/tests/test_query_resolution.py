"""Tests for query resolution (typo tolerance, transliteration, concept suggestions)."""

from modules.library.query_resolution import (
    normalize_query,
    resolve_query,
    build_suggestion_contract,
)
from modules.library.concept_catalog import (
    CATALOG,
    get_concept,
    lookup_by_form,
    FORM_INDEX,
)


class TestConceptCatalog:
    def test_catalog_has_hitbodedut(self):
        entry = get_concept("hitbodedut")
        assert entry is not None
        assert entry.canonical_label == "Hitbodedut"
        assert entry.hebrew == "התבודדות"

    def test_catalog_hitbodedut_aliases_include_hisbodedus(self):
        entry = get_concept("hitbodedut")
        assert "hisbodedus" in entry.transliterations

    def test_catalog_has_all_required_concepts(self):
        required = [
            "hitbodedut", "tefila", "emuna", "tzadik", "daat",
            "simja", "atzvut", "yirat_shamayim", "brit",
            "tikun_haklali", "likutey_moharan", "rabi_natan",
            "rebe_najman", "zohar", "teshuva",
        ]
        for cid in required:
            assert get_concept(cid) is not None, f"Missing concept: {cid}"

    def test_form_index_has_canonical_label(self):
        assert lookup_by_form("Hitbodedut") == "hitbodedut"

    def test_form_index_has_alias(self):
        assert lookup_by_form("plegaria personal") == "hitbodedut"

    def test_form_index_has_transliteration(self):
        assert lookup_by_form("hisbodedus") == "hitbodedut"

    def test_form_index_has_hebrew(self):
        assert lookup_by_form("התבודדות") == "hitbodedut"


class TestNormalizeQuery:
    def test_lowercase(self):
        assert normalize_query("Hitbodedut") == "hitbodedut"

    def test_diacritics(self):
        assert normalize_query("Hitbodédut") == normalize_query("Hitbodedut")
        assert "é" not in normalize_query("Hitbodédut")

    def test_apostrophe_variants(self):
        assert normalize_query("da'at") == "da'at"
        assert normalize_query("daʻat") == "da'at"

    def test_trim(self):
        assert normalize_query("  Hitbodedut  ") == "hitbodedut"

    def test_nfc(self):
        composed = "Hitbodédut"
        decomposed = composed.replace("é", "e\u0301")
        assert normalize_query(decomposed) == normalize_query(composed)


class TestResolveQuery:
    def test_exact_match_hitbodedut(self):
        norm, candidates, autoapply = resolve_query("Hitbodedut")
        assert len(candidates) == 1
        assert candidates[0].concept_id == "hitbodedut"
        assert candidates[0].suggestion_type == "exact_match"
        assert candidates[0].confidence == 1.0
        assert autoapply == "hitbodedut"

    def test_typo_hitbodedud(self):
        norm, candidates, autoapply = resolve_query("Hitbodedud")
        assert len(candidates) >= 1
        assert candidates[0].concept_id == "hitbodedut"
        assert candidates[0].suggestion_type == "probable_typo"
        assert autoapply == "hitbodedut"

    def test_transliteration_hisbodedus(self):
        norm, candidates, autoapply = resolve_query("Hisbodedus")
        assert candidates[0].concept_id == "hitbodedut"
        assert autoapply == "hitbodedut"

    def test_hebrew_original(self):
        norm, candidates, autoapply = resolve_query("התבודדות")
        assert candidates[0].concept_id == "hitbodedut"
        assert autoapply == "hitbodedut"

    def test_emunah_transliteration(self):
        norm, candidates, autoapply = resolve_query("Emunah")
        assert candidates[0].concept_id == "emuna"
        assert autoapply == "emuna"

    def test_tzadick_typo(self):
        norm, candidates, autoapply = resolve_query("Tzadick")
        assert candidates[0].concept_id == "tzadik"

    def test_simcha_transliteration(self):
        norm, candidates, autoapply = resolve_query("Simcha")
        assert candidates[0].concept_id == "simja"

    def test_unknown_no_suggestion(self):
        norm, candidates, autoapply = resolve_query("xyzunknown")
        assert len(candidates) == 0
        assert autoapply is None

    def test_short_query_no_aggressive_suggestion(self):
        norm, candidates, autoapply = resolve_query("el")
        assert autoapply is None

    def test_likutei_moharan_transliteration(self):
        norm, candidates, autoapply = resolve_query("Likutei Moharan")
        assert candidates[0].concept_id == "likutey_moharan"

    def test_rabi_natan_alias(self):
        norm, candidates, autoapply = resolve_query("Rabi Natan")
        assert candidates[0].concept_id == "rabi_natan"


class TestBuildSuggestionContract:
    def test_exact_match_contract(self):
        norm, candidates, autoapply = resolve_query("Hitbodedut")
        contract = build_suggestion_contract("Hitbodedut", norm, candidates, autoapply)
        assert contract["exact_match"] is True
        assert contract["suggestion_applied"] is False

    def test_typo_contract(self):
        norm, candidates, autoapply = resolve_query("Hitbodedud")
        contract = build_suggestion_contract("Hitbodedud", norm, candidates, autoapply)
        assert contract["exact_match"] is False
        assert contract["suggestion_applied"] is True
        assert contract["suggested_query"] == "Hitbodedut"
        assert contract["original_query"] == "Hitbodedud"
        assert contract["normalized_query"] == "hitbodedud"
        assert len(contract["alternatives"]) > 0
        assert len(contract["related_concepts"]) > 0

    def test_no_suggestion_contract(self):
        norm, candidates, autoapply = resolve_query("xyzunknown")
        contract = build_suggestion_contract("xyzunknown", norm, candidates, autoapply)
        assert contract["suggested_query"] is None
        assert contract["alternatives"] == []
        assert contract["related_concepts"] == []

    def test_alternatives_include_hebrew(self):
        norm, candidates, autoapply = resolve_query("Hitbodedud")
        contract = build_suggestion_contract("Hitbodedud", norm, candidates, autoapply)
        hebrew_alts = [a for a in contract["alternatives"] if a["type"] == "Forma hebrea"]
        assert len(hebrew_alts) >= 1
        assert hebrew_alts[0]["label"] == "התבודדות"

    def test_related_concepts_separated(self):
        norm, candidates, autoapply = resolve_query("Hitbodedud")
        contract = build_suggestion_contract("Hitbodedud", norm, candidates, autoapply)
        assert len(contract["related_concepts"]) > 0
        for rc in contract["related_concepts"]:
            assert "label" in rc
            assert "relation_type" in rc
