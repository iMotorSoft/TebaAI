"""Tests for the read-only page mapping failure diagnosis."""

from __future__ import annotations

import inspect
import json

from scripts import diagnose_page_mapping_failures as diagnosis


def _metrics(**overrides):
    values = {
        "pdf_not_found": False,
        "anchor_too_short": False,
        "chunk_too_short": False,
        "chunk_too_long": False,
        "anchor_repeated": False,
        "ambiguous": False,
        "start_anchor_found": False,
        "end_anchor_found": False,
        "cross_page_uncertain": False,
        "hyphenation_improved": False,
        "hyphenation_indicator": False,
        "header_footer_improved": False,
        "full_extraction_anchor_found": False,
        "page_similarity": 0.0,
        "no_text_match": False,
    }
    values.update(overrides)
    return values


def test_categorizes_no_match():
    assert diagnosis._categorize_failure(_metrics(no_text_match=True)) == "NO_TEXT_MATCH"


def test_categorizes_repeated_anchor():
    assert diagnosis._categorize_failure(_metrics(anchor_repeated=True)) == "ANCHOR_REPEATED"


def test_categorizes_start_only():
    assert diagnosis._categorize_failure(_metrics(start_anchor_found=True)) == "START_MATCH_ONLY"


def test_categorizes_end_only():
    assert diagnosis._categorize_failure(_metrics(end_anchor_found=True)) == "END_MATCH_ONLY"


def test_detects_hyphenation_and_linebreak():
    assert diagnosis._has_hyphenation_or_linebreak("inter-\nnacional")
    assert diagnosis._normalize_hyphenation("inter-\nnacional") == "internacional"
    assert diagnosis._categorize_failure(_metrics(hyphenation_improved=True)) == "HYphenation_OR_LINEBREAK"


def test_calculates_strategy_candidate():
    result = diagnosis._strategy_summary(
        "hyphenation_fix",
        [
            {"confidence": "high", "ambiguous": False},
            {"confidence": "medium", "ambiguous": False},
            {"confidence": "none", "ambiguous": False},
            {"confidence": "none", "ambiguous": False},
        ],
        total_chunks=100,
        already_mapped=10,
        total_unmapped=90,
    )
    assert result["candidate_high"] == 1
    assert result["estimated_new_high"] == 22
    assert result["risk"] == "low"
    assert result["recommended"] is False


def test_recommends_only_validated_incremental_low_risk_strategy():
    strategies = []
    counts = {
        "baseline_current_matcher": 0,
        "normalization_plus": 8,
        "hyphenation_fix": 8,
        "header_footer_strip": 8,
        "sliding_window_similarity": 2,
        "relaxed_medium_candidate": 0,
    }
    for name in diagnosis.STRATEGIES:
        item = diagnosis._strategy_summary(
            name,
            ([{"confidence": "high", "ambiguous": False}] * counts[name])
            + ([{"confidence": "none", "ambiguous": False}] * (10 - counts[name])),
            total_chunks=100,
            already_mapped=10,
            total_unmapped=90,
        )
        item["validation_high_predictions"] = 10
        item["validation_high_precision"] = 100.0
        strategies.append(item)
    diagnosis._recommend_strategies(strategies)
    recommended = [item["strategy"] for item in strategies if item["recommended"]]
    assert recommended == ["normalization_plus"]


def test_generates_json_shape(tmp_path):
    baseline = diagnosis._strategy_summary(
        "baseline_current_matcher",
        [{"confidence": "none", "ambiguous": False}],
        total_chunks=1,
        already_mapped=0,
        total_unmapped=1,
    )
    baseline["_raw_results"] = [{"confidence": "none", "ambiguous": False}]
    sample = {
        "chunk_id": "chunk-1",
        "chunk_index": 0,
        "category": "NO_TEXT_MATCH",
        "chunk_length": 250,
        "normalized_chunk_length": 240,
        "best_page_candidate": None,
        "best_page_score": 0.0,
        "start_anchor_found": False,
        "end_anchor_found": False,
        "middle_anchors_found": False,
        "number_of_candidate_pages": 0,
        "linebreak_density": 0.01,
        "hyphenation_indicators": 0,
        "repeated_text_indicators": 0,
        "full_extraction_anchor_found": False,
    }
    report = diagnosis._build_report(
        collection="breslov",
        document={"title": "Test"},
        pdf_path=tmp_path / "test.pdf",
        chunks=[{"page_start": None}],
        diagnosed=[sample],
        strategies=[baseline],
        max_samples_per_category=1,
    )
    output = tmp_path / "report.json"
    diagnosis._write_json(report, str(output))
    parsed = json.loads(output.read_text(encoding="utf-8"))
    assert parsed["collection"] == "breslov"
    assert parsed["summary"]["diagnosed_samples"] == 1
    assert parsed["failure_categories"]["NO_TEXT_MATCH"] == 1
    assert parsed["strategy_candidates"][0]["strategy"] == "baseline_current_matcher"


def test_limits_samples_and_selection():
    rows = [{"chunk_index": index} for index in range(20)]
    selected = diagnosis._select_sample(rows, 5)
    assert len(selected) == 5
    assert selected[0]["chunk_index"] == 0
    assert selected[-1]["chunk_index"] == 19

    samples = [
        {"category": "NO_TEXT_MATCH", "chunk_index": 1},
        {"category": "NO_TEXT_MATCH", "chunk_index": 2},
        {"category": "START_MATCH_ONLY", "chunk_index": 3},
    ]
    limited = diagnosis._limit_samples_by_category(samples, 1)
    assert [sample["chunk_index"] for sample in limited] == [1, 3]


def test_match_helpers_do_not_require_postgresql():
    pages = [diagnosis._normalize_plus("Primera página con texto único suficiente para un anchor estable.")]
    result = diagnosis._match_result(
        "Primera página con texto único suficiente para un anchor estable.",
        pages,
        normalizer=diagnosis._normalize_plus,
    )
    assert result["best_page_candidate"] == 1
    assert result["confidence"] in {"high", "medium"}


def test_runtime_has_no_database_write_statements():
    source = inspect.getsource(diagnosis._run).upper()
    for statement in ("UPDATE ", "INSERT ", "DELETE ", "TRUNCATE ", "DROP "):
        assert statement not in source
    assert "SET TRANSACTION READ ONLY" in source


def test_cli_has_no_apply_mode():
    args = diagnosis._parse_args(
        [
            "--document-title", "Test",
            "--output-md", "/tmp/test.md",
            "--output-json", "/tmp/test.json",
        ]
    )
    assert not hasattr(args, "apply")
