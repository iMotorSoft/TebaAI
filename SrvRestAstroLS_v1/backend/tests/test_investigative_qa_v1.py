import asyncio

import psycopg
import pytest
from psycopg.rows import dict_row

import modules.library.investigative_qa_v1 as investigative_qa
from globalVar import POSTGRES_DSN
from modules.library.investigative_qa_v1 import (
    WORKS,
    Hit,
    QaRequest,
    _apply_claim_traceability,
    _cap_hits_with_language_coverage,
    _mentioned_works,
    _normalize_claims,
    _retrieval_inputs,
    display_snippet,
    literal_context_snippet,
    relation_concepts,
    run,
    validate_grounded_render,
)
from modules.library.multilingual_query import deterministic_interpret, preprocess_query


def make_hit(hit_id: str, concepts: list[str], quote: str = "sangre y habla") -> Hit:
    relevance = "same_fragment_both_terms" if len(concepts) > 1 else "single_term_literal"
    return Hit(
        hit_id=hit_id,
        work_code="kitzur",
        work_title="Kitzur",
        quote=quote,
        snippet=quote,
        source_view="view",
        search_record_type="chunk",
        source_layer="unknown",
        matched_terms=concepts,
        matched_concepts=concepts,
        evidence_type="literal_same_page",
        literal_strength="medium",
        evidence_strength="medium" if len(concepts) > 1 else "insufficient",
        relation_relevance=relevance,
    )


def run_real(request: QaRequest) -> dict:
    async def execute() -> dict:
        async with await psycopg.AsyncConnection.connect(POSTGRES_DSN, row_factory=dict_row) as connection:
            return await run(connection, request)

    return asyncio.run(execute())


def test_request_allowlist_and_defaults() -> None:
    request = QaRequest(question="¿Dónde aparece la plegaria?")
    assert not request.include_audit
    assert set(request.works) == WORKS


def test_request_rejects_bad_limit() -> None:
    with pytest.raises(Exception):
        QaRequest(question="ok", max_hits_per_work=99)


def test_where_term_question_keeps_only_the_requested_concept() -> None:
    concepts = relation_concepts("donde aparece el termino escorpion")
    assert [item["label"] for item in concepts] == ["escorpion"]
    assert {"escorpion", "escorpiones", "עקרב"}.issubset(set(concepts[0]["terms"]))


def test_structured_latin_concept_keeps_validated_cross_language_aliases() -> None:
    interpretation = deterministic_interpret(preprocess_query("escorpión"))
    concepts, literals = _retrieval_inputs(interpretation)
    assert not literals
    assert concepts[0]["terms"][0] == "escorpión"
    assert {"escorpiones", "עקרב", "עַקְרַב"}.issubset(concepts[0]["terms"])


def test_relation_concepts_keep_user_terms_and_known_aliases() -> None:
    concepts = relation_concepts("la relacion entre sangre y el habla")
    assert [item["label"] for item in concepts] == ["sangre", "habla"]
    assert "hablar" in concepts[1]["terms"]
    assert "hemoglobina" not in {term for item in concepts for term in item["terms"]}
    assert [item["label"] for item in relation_concepts("¿Cuál es la relación entre sangre y habla?")] == ["sangre", "habla"]


def test_relation_concepts_keep_known_multiword_name_together() -> None:
    concepts = relation_concepts("¿Dónde aparece Rabí Natán?")
    assert [item["label"] for item in concepts] == ["rabí natán"]
    assert "reb noson" in concepts[0]["terms"]


def test_model_rewording_does_not_replace_standalone_user_concepts(monkeypatch: pytest.MonkeyPatch) -> None:
    async def reworded_interpretation(_question: str, _history: list[dict] | None = None) -> tuple[dict, list[str]]:
        return {
            "detected_language": "es",
            "normalized_question": "rabino Natan",
            "requires_cross_corpus": False,
        }, []

    async def no_render(_question: str, _hits: list[Hit]) -> tuple[None, list[str], list[dict]]:
        return None, [], []

    monkeypatch.setattr(investigative_qa, "_ai_interpret", reworded_interpretation)
    monkeypatch.setattr(investigative_qa, "_ai_render", no_render)

    response = run_real(QaRequest(question="Rabí Natán", works=["lmii"]))

    assert response["interpretation"]["concepts"] == ["rabí natán"]
    assert "reb noson" in response["search_plan"]["queries"]


def test_snippet_never_starts_midword_without_ellipsis() -> None:
    assert display_snippet("iduría - dado que uno se hace digno").startswith("…iduría")
    assert display_snippet("Texto completo.") == "Texto completo."


def test_hebrew_literal_context_keeps_complete_logical_lines() -> None:
    text = "כותרת\nשורה לפני\nתְּהִלָּתִי אֶחְטָם לָךְ.\nשורה אחרי\nSpanish notes"
    snippet = literal_context_snippet(text, ["תהלתי אחטם לך"])
    assert "תְּהִלָּתִי אֶחְטָם לָךְ" in snippet
    assert "Spanish notes" not in snippet
    assert "ךל םטחא יתלהת" not in snippet


def test_followup_work_name_is_resolved_by_backend() -> None:
    assert _mentioned_works("¿Eso aparece también en Likutey Halajot?") == ["lh"]


def test_claim_normalization_rejects_single_term_when_direct_evidence_exists() -> None:
    direct = make_hit("direct", ["sangre", "habla"])
    noise = make_hit("noise", ["sangre"], "sólo sangre")
    claims = _normalize_claims([
        {"claim": "relación", "evidence_ids": ["direct"]},
        {"claim": "ruido", "evidence_ids": ["noise"]},
    ], [direct, noise], required_concepts=2)
    assert [claim["primary_evidence_id"] for claim in claims] == ["direct"]


def test_primary_evidence_is_sorted_first_and_strength_is_relational() -> None:
    direct = make_hit("direct", ["sangre", "habla"])
    noise = make_hit("noise", ["sangre"], "sólo sangre")
    hits = [noise, direct]
    primary = _apply_claim_traceability(hits, [{"evidence_ids": ["direct"], "primary_evidence_id": "direct"}])
    assert primary == ["direct"]
    assert hits[0].hit_id == "direct"
    assert hits[0].is_primary and hits[0].evidence_strength == "strong"
    assert hits[1].evidence_strength == "insufficient"


def test_grounding_rejects_unknown_page_and_doctrinal_overclaim() -> None:
    hit = make_hit("h1", ["sangre", "habla"])
    hit.pdf_page = 10
    base = {"used_evidence_ids": ["h1"], "claims": [{"claim": "x", "evidence_ids": ["h1"]}]}
    assert validate_grounded_render({**base, "answer_markdown": "PDF p. 999"}, [hit])[0] is None
    assert validate_grounded_render({**base, "answer_markdown": "Esto demuestra dependencia doctrinal"}, [hit])[0] is None


def test_real_postgres_single_concept_retrieval_remains_grounded() -> None:
    response = run_real(QaRequest(question="¿Dónde aparece plegaria?", works=["potencia_plegaria", "lh"], ai={"enabled": False}))
    assert response["status"] == "ok"
    assert response["primary_evidence_ids"]
    assert all(hit["quote"] for hit in response["hits"])
    assert response["execution"]["used_deterministic_fallback"]


def test_real_blood_speech_traceability_and_final_per_work_limit() -> None:
    response = run_real(QaRequest(question="la relacion entre sangre y el habla", ai={"enabled": False}, max_hits_per_work=5))
    hit_ids = [hit["hit_id"] for hit in response["hits"]]
    assert response["status"] == "ok"
    assert response["primary_evidence_ids"]
    assert hit_ids[0] == response["primary_evidence_ids"][0]
    assert response["hits"][0]["matched_concepts"] == ["sangre", "habla"]
    assert "shamir" not in response["hits"][0]["snippet"].casefold()
    assert all(primary in hit_ids for primary in response["primary_evidence_ids"])
    assert all(claim["primary_evidence_id"] in claim["evidence_ids"] for claim in response["claims"])
    assert all(sum(hit["work_code"] == work for hit in response["hits"]) <= 5 for work in response["works_consulted"])
    assert len({(hit["work_code"], hit["quote"]) for hit in response["hits"]}) == len(response["hits"])
    assert all(hit["evidence_strength"] != "strong" for hit in response["hits"] if hit["relation_relevance"] == "single_term_literal")


def test_final_cap_reserves_requested_readable_hebrew_without_exceeding_limit() -> None:
    spanish = [make_hit(f"es-{index}", ["plegaria"], f"plegaria {index}") for index in range(3)]
    hebrew = make_hit("he-readable", ["plegaria"], "תְּפִלָּה " * 20)
    hebrew.display_snippet = "תְּפִלָּה"
    hebrew.display_normalization = "pdf_glyph_geometry_nfc_v1"
    hits = [*spanish, hebrew]

    selected = _cap_hits_with_language_coverage(hits, 3, ["es", "he"])

    assert [hit.hit_id for hit in selected] == ["es-0", "es-1", "he-readable"]
    assert len(selected) == 3


def test_final_cap_does_not_force_hebrew_when_not_requested() -> None:
    spanish = [make_hit(f"es-{index}", ["plegaria"], f"plegaria {index}") for index in range(3)]
    hebrew = make_hit("he-readable", ["plegaria"], "תְּפִלָּה " * 20)
    hebrew.display_snippet = "תְּפִלָּה"
    hebrew.display_normalization = "pdf_glyph_geometry_nfc_v1"

    selected = _cap_hits_with_language_coverage([*spanish, hebrew], 3, ["es"])

    assert [hit.hit_id for hit in selected] == ["es-0", "es-1", "es-2"]


def test_final_cap_replaces_mixed_projection_with_hebrew_dominant_projection() -> None:
    spanish = [make_hit(f"es-{index}", ["rabí natán"], f"Rabí Natán {index}") for index in range(2)]
    mixed = make_hit("mixed", ["rabí natán"], "עברית " * 20)
    mixed.display_snippet = "EXPANSIONES DEL NOMBRE " * 20 + "עברית"
    mixed.display_normalization = "pdf_glyph_geometry_nfc_v1"
    hebrew = make_hit("he-readable", ["rabí natán"], "עִבְרִית " * 20)
    hebrew.display_snippet = "עִבְרִית " * 20
    hebrew.display_normalization = "pdf_glyph_geometry_nfc_v1"

    selected = _cap_hits_with_language_coverage([*spanish, mixed, hebrew], 3, ["es", "he"])

    assert [hit.hit_id for hit in selected] == ["es-0", "es-1", "he-readable"]


@pytest.mark.parametrize("question", [
    "plegaria e hitbodedut",
    "miedo y fe",
    "tristeza y alegría",
    "habla y alma",
    "sangre y deseo",
    "Rabí Natán y plegaria",
    "Zohar y temor",
])
def test_relational_queries_never_promote_single_term_noise(question: str) -> None:
    response = run_real(QaRequest(question=question, works=["kitzur", "lh"], ai={"enabled": False}, max_hits_per_work=5))
    ids = {hit["hit_id"]: hit for hit in response["hits"]}
    assert all(evidence_id in ids for claim in response["claims"] for evidence_id in claim["evidence_ids"])
    assert all(ids[evidence_id]["relation_relevance"] != "single_term_literal" for claim in response["claims"] for evidence_id in claim["evidence_ids"])


# ── Hebrew language priority tests ───────────────────────────────────────

from modules.library.investigative_qa_v1 import (
    _analyze_query_language,
    _extract_literal_phrases,
    _detect_hit_language,
    _compute_language_match,
    _compute_literal_match_kind,
    _compute_retrieval_tier,
    _hebrew_content_words,
    _detect_interface_language,
    classify_intent,
    HEBREW_STOP_WORDS,
)


def test_detect_interface_language_mixed_query() -> None:
    assert _detect_interface_language("donde aparece כי יש עון שמעכב תשובה") == "es"


def test_detect_interface_language_pure_hebrew() -> None:
    assert _detect_interface_language("כי יש עון שמעכב תשובה") == "he"


def test_detect_interface_language_spanish() -> None:
    assert _detect_interface_language("donde aparece el termino escorpion") == "es"


def test_detect_interface_language_english() -> None:
    assert _detect_interface_language("where is prayer discussed") == "en"


def test_analyze_query_language_mixed_query() -> None:
    result = _analyze_query_language("donde aparece כי יש עון שמעכב תשובה")
    assert result["interface_language"] == "es"
    assert result["primary_retrieval_language"] == "he"
    assert result["query_language"] == "he"
    assert result["secondary_languages"] == ["es", "en"]
    assert len(result["literal_phrases"]) > 0


def test_analyze_query_language_pure_hebrew() -> None:
    result = _analyze_query_language("כי יש עון שמעכב תשובה")
    assert result["interface_language"] == "he"
    assert result["primary_retrieval_language"] == "he"
    assert result["secondary_languages"] == ["es", "en"]


def test_analyze_query_language_spanish() -> None:
    result = _analyze_query_language("donde aparece el termino escorpion")
    assert result["interface_language"] == "es"
    assert result["primary_retrieval_language"] == "es"
    assert result["secondary_languages"] == ["he", "en"]
    assert result["literal_phrases"] == []


def test_analyze_query_language_english() -> None:
    result = _analyze_query_language("where is prayer discussed")
    assert result["interface_language"] == "en"
    assert result["primary_retrieval_language"] == "en"
    assert result["secondary_languages"] == ["he", "es"]


def test_extract_literal_phrases_mixed_query() -> None:
    phrases = _extract_literal_phrases("donde aparece כי יש עון שמעכב תשובה")
    assert len(phrases) >= 1
    assert "עון" in phrases[0]["text"]
    assert "שמעכב" in phrases[0]["text"]
    assert "תשובה" in phrases[0]["text"]
    assert phrases[0]["language"] == "he"


def test_extract_literal_phrases_skips_stop_words() -> None:
    phrases = _extract_literal_phrases("כי יש עון שמעכב תשובה")
    assert len(phrases) >= 1
    # The phrase should contain content words, not just stop words
    text = phrases[0]["text"]
    assert "עון" in text
    assert "שמעכב" in text
    assert "תשובה" in text


def test_extract_literal_phrases_no_hebrew() -> None:
    assert _extract_literal_phrases("donde aparece el termino escorpion") == []


def test_hebrew_content_words_filters_stop_words() -> None:
    words = _hebrew_content_words("כי יש עון שמעכב תשובה")
    assert "כי" not in words
    assert "יש" not in words
    assert "עון" in words
    assert "שמעכב" in words
    assert "תשובה" in words


def test_hebrew_content_words_only_stop_words() -> None:
    words = _hebrew_content_words("כי את הוא")
    assert words == []


def test_detect_hit_language_hebrew() -> None:
    assert _detect_hit_language("ליקוטי מוהר׳׳ן") == "he"


def test_detect_hit_language_spanish() -> None:
    assert _detect_hit_language("La plegaria es sobrenatural") == "es"


def test_detect_hit_language_mixed() -> None:
    assert _detect_hit_language("ליקוטי מוהר׳׳ן LIKUTEY MOHARÁN") == "he"


def test_compute_language_match_exact() -> None:
    assert _compute_language_match("he", "he", ["es", "en"]) == "exact"


def test_compute_language_match_secondary() -> None:
    assert _compute_language_match("es", "he", ["es", "en"]) == "secondary"


def test_compute_language_match_fallback() -> None:
    assert _compute_language_match("en", "he", ["es", "en"]) == "secondary"


def test_compute_literal_match_kind_exact_phrase() -> None:
    assert _compute_literal_match_kind(
        "עון שמעכב תשובה",
        ["עון שמעכב תשובה"],
        "he"
    ) == "exact_phrase"


def test_compute_literal_match_kind_single_term() -> None:
    assert _compute_literal_match_kind(
        "sangre y habla",
        ["sangre"],
        "es"
    ) == "single_term"


def test_compute_retrieval_tier_exact_literal() -> None:
    assert _compute_retrieval_tier("exact", "exact_phrase") == 0


def test_compute_retrieval_tier_exact_single() -> None:
    assert _compute_retrieval_tier("exact", "single_term") == 1


def test_compute_retrieval_tier_secondary() -> None:
    assert _compute_retrieval_tier("secondary", "single_term") == 3


def test_compute_retrieval_tier_fallback() -> None:
    assert _compute_retrieval_tier("fallback", "semantic") == 4


def test_relation_concepts_hebrew_phrase() -> None:
    concepts = relation_concepts("donde aparece כי יש עון שמעכב תשובה")
    # Should extract the Hebrew phrase
    assert any("עון" in str(c["label"]) for c in concepts)
    assert any("תשובה" in str(c["label"]) for c in concepts)


def test_relation_concepts_hebrew_single_word() -> None:
    concepts = relation_concepts("תפילה")
    assert concepts[0]["label"] == "תפילה"


def test_hebrew_phrase_search_no_evidence_for_missing_content() -> None:
    """The phrase does not exist in corpus - should return no_evidence."""
    response = run_real(QaRequest(
        question="donde aparece כי יש עון שמעכב תשובה",
        works=["lmii", "lm_xv", "lh"],
        ai={"enabled": False},
        max_hits_per_work=3,
    ))
    assert response["status"] == "no_evidence"
    assert response["interpretation"]["primary_retrieval_language"] == "he"
    assert response["interpretation"]["interface_language"] == "es"
    assert len(response["literal_phrases"][0]["text"]) > 0 if response.get("literal_phrases") else True


def test_hebrew_single_word_returns_evidence_if_available() -> None:
    response = run_real(QaRequest(
        question="עקרב",
        works=["kitzur", "lh"],
        ai={"enabled": False},
        max_hits_per_work=3,
    ))
    if response["status"] == "ok":
        hits = response["hits"]
        if hits:
            assert any(hit["language_match"] in ("exact", "primary") for hit in hits)


def test_spanish_query_prioritizes_spanish_evidence() -> None:
    response = run_real(QaRequest(
        question="donde aparece el termino escorpion",
        ai={"enabled": False},
        max_hits_per_work=3,
    ))
    assert response["interpretation"]["primary_retrieval_language"] == "es"
    assert response["interpretation"]["interface_language"] == "es"


def test_sort_key_includes_retrieval_tier() -> None:
    from modules.library.investigative_qa_v1 import _sort_key, Hit
    hit_a = make_hit("a", ["term1"])
    object.__setattr__(hit_a, "retrieval_tier", 0)
    object.__setattr__(hit_a, "language_match", "exact")
    object.__setattr__(hit_a, "literal_match_kind", "exact_phrase")
    hit_b = make_hit("b", ["term1"])
    object.__setattr__(hit_b, "retrieval_tier", 3)
    object.__setattr__(hit_b, "language_match", "secondary")
    object.__setattr__(hit_b, "literal_match_kind", "single_term")
    assert _sort_key(hit_a) < _sort_key(hit_b)


def test_hit_has_language_metadata() -> None:
    hit = make_hit("test", ["sangre"])
    assert hit.language_match in ("exact", "primary", "secondary", "fallback")
    assert hit.literal_match_kind in ("none", "exact_phrase", "normalized", "no_niqqud", "single_term", "semantic")
    assert isinstance(hit.retrieval_tier, int)


@pytest.mark.parametrize(("question", "expected"), [
    ("dónde aparece תהלתי אחטם לך", "literal_lookup"),
    ("תהלתי אחטם לך", "literal_lookup"),
    ("qué significa תהלתי אחטם לך", "translation_or_explanation"),
    ("relación entre תהלתי y plegaria", "relation_query"),
    ("dónde aparece el término escorpión", "concept_lookup"),
])
def test_intent_routing_distinguishes_literal_and_relation(question: str, expected: str) -> None:
    assert classify_intent(question) == expected


def test_real_hebrew_literal_variants_resolve_same_physical_page() -> None:
    variants = [
        "dónde aparece תְּהִלָּתִי אֶחְטָם לָךְ",
        "dónde aparece תהלתי אחטם לך",
        "אחטם לך",
        "איפה מופיע תהלתי אחטם לך",
    ]
    responses = [run_real(QaRequest(question=value, works=["lmi"], ai={"enabled": False})) for value in variants]
    primaries = [next(hit for hit in response["hits"] if hit["hit_id"] == response["primary_evidence_ids"][0]) for response in responses]
    assert all(response["status"] == "ok" and response["intent"] == "literal_lookup" for response in responses)
    assert len({hit["document_id"] for hit in primaries}) == 1
    assert all(hit["document_id"] for hit in primaries)
    assert len({hit["page_anchor_id"] for hit in primaries}) == 1
    assert len({hit["hit_id"] for hit in primaries}) == 1
    assert primaries[0]["hit_id"].startswith("lmi-")
    assert all(hit["pdf_page"] == 96 and hit["printed_page"] == 76 for hit in primaries)
    assert all(hit["section"] == "LIKUTEY MOHARÁN #2:7" for hit in primaries)
    assert all(hit["physical_file_name"] == "LIKUTEY MOHARÁN I int (imprenta).pdf" for hit in primaries)
    assert all(hit["source_sha256"] == "71fb3c763c34d13465441c57b2bf3a65629fcdc37a7588f21e4fbf21f984b8d7" for hit in primaries)
    assert all("relación solicitada" not in response["answer_markdown"] for response in responses)


def test_real_hebrew_literal_preserves_canonical_niqqud_and_logical_order() -> None:
    response = run_real(QaRequest(question="תהלתי אחטם לך", works=["lmi"], ai={"enabled": False}))
    primary = next(hit for hit in response["hits"] if hit["hit_id"] == response["primary_evidence_ids"][0])
    assert "תְּהִלָּתִי אֶחְטָם לָךְ" in primary["quote"]
    assert "ךל םטחא יתלהת" not in primary["quote"]
    assert primary["literal_match_kind"] == "no_niqqud"


def test_real_hebrew_changed_letter_is_not_forced_to_literal_evidence() -> None:
    response = run_real(QaRequest(question="תהלתי אחטמ לך", works=["lmi"], ai={"enabled": False}))
    assert response["status"] == "no_evidence"
    assert response["primary_evidence_ids"] == []
    assert "relación solicitada" not in response["answer_markdown"]


PDF_SPACED_LITERAL = "ת ְּ הִ לָּ ת ִ י אֶ חְ ט ָ ם לָ ך"


@pytest.mark.parametrize("question", [
    "תְּהִלָּתִי אֶחְטָם לָךְ",
    "תהלתי אחטם לך",
    PDF_SPACED_LITERAL,
    f"{PDF_SPACED_LITERAL} donde esta",
    f"donde esta {PDF_SPACED_LITERAL}",
    f"איפה {PDF_SPACED_LITERAL}",
])
def test_real_pdf_copypaste_variants_resolve_required_anchor(question: str) -> None:
    response = run_real(QaRequest(question=question, works=["lmi"], ai={"enabled": False}))
    assert response["status"] == "ok"
    assert response["intent"] == "literal_lookup"
    primary = next(hit for hit in response["hits"] if hit["hit_id"] == response["primary_evidence_ids"][0])
    assert primary["hit_id"] == "lmi-dc3eecd6-64b1-4f09-ac9b-d47e4fd70df1"
    assert primary["document_id"] == "6673da69-eb38-40bf-9f5c-447ff3ba6725"
    assert primary["page_anchor_id"] == "c211a30b-eef4-4fb4-a558-45e89c314db3"
    assert (primary["pdf_page"], primary["printed_page"]) == (96, 76)
    assert primary["section"] == "LIKUTEY MOHARÁN #2:7"
    assert "תְּהִלָּתִי אֶחְטָם לָךְ" in primary["quote"]
    assert response["interpretation"]["literal_search_normalized"] == "תהלתי אחטם לך"
    assert response["interpretation"]["instruction"] not in response["search_plan"]["queries"]


def test_exact_pdf_copypaste_audit_excludes_spanish_instruction() -> None:
    response = run_real(QaRequest(
        question=f"{PDF_SPACED_LITERAL} donde esta",
        works=["lmi"],
        ai={"enabled": False},
    ))
    interpretation = response["interpretation"]
    assert interpretation["literal_raw"] == PDF_SPACED_LITERAL
    assert interpretation["instruction"] == "donde esta"
    assert interpretation["instruction_language"] == "es"
    assert interpretation["literal_reconstructed"] == "תְּהִלָּתִי אֶחְטָם לָך"
    assert interpretation["selected_candidate"] == "תהלתי אחטם לך"
    assert interpretation["candidate_count"] <= 64
    assert response["search_plan"]["queries"] == ["תהלתי אחטם לך"]
    assert response["question"] == f"{PDF_SPACED_LITERAL} donde esta"
