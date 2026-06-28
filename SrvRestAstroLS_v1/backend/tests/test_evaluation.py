"""Tests for bibliographic search evaluation harness."""

from __future__ import annotations

import json
import pathlib
import tempfile
from unittest.mock import patch

import pytest

FIXTURE_PATH = pathlib.Path(__file__).resolve().parent / "fixtures" / "breslov_validation_cases.json"


# ── Fixture tests ────────────────────────────────────────────────────────


class TestFixture:
    def test_fixture_exists(self):
        assert FIXTURE_PATH.is_file()

    def test_fixture_valid_json(self):
        data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) > 0

    def test_fixture_all_have_id(self):
        data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        for c in data:
            assert "id" in c, f"Missing id in case: {c.get('question', '?')[:40]}"

    def test_fixture_unique_ids(self):
        data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        ids = [c["id"] for c in data]
        assert len(ids) == len(set(ids)), f"Duplicate IDs: {[id for id in ids if ids.count(id) > 1]}"

    def test_fixture_expected_terms_not_empty(self):
        data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        for c in data:
            terms = c.get("expected_terms", [])
            assert len(terms) > 0, f"Empty expected_terms in {c['id']}"

    def test_fixture_query_terms_not_empty(self):
        data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        for c in data:
            terms = c.get("query_terms", [])
            assert len(terms) > 0, f"Empty query_terms in {c['id']}"

    def test_fixture_level_valid(self):
        data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        for c in data:
            assert c.get("level") in (1, 2, 3, 4), f"Invalid level in {c['id']}: {c.get('level')}"

    def test_fixture_category_valid(self):
        data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        valid = {"literal", "comprehension", "synthesis", "complex", "intertextual"}
        for c in data:
            assert c.get("category") in valid, f"Invalid category in {c['id']}: {c.get('category')}"


# ── Evaluator tests ──────────────────────────────────────────────────────


class TestEvaluator:
    def test_evaluate_pass_fuerte(self):
        from scripts.evaluate_bibliographic_search import evaluate_case

        case = {
            "id": "test_01",
            "expected_document_title": "El Jardín de las Almas",
            "expected_terms": ["Shlomo Efraim"],
        }
        results = [
            {"document_title": "El Jardín de las Almas", "match_type": "fts", "rank": 0.5,
             "plain_excerpt": "Shlomo Efraim hijo del Rebe", "highlighted_excerpt": "<mark>Shlomo Efraim</mark>"},
        ]
        eval_result = evaluate_case(case, results, top_k=10, mode="auto")
        assert eval_result["status"] == "PASS"
        assert eval_result["found_rank_position"] == 1

    def test_evaluate_partial(self):
        from scripts.evaluate_bibliographic_search import evaluate_case

        case = {
            "id": "test_02",
            "expected_document_title": "El Jardín de las Almas",
            "expected_terms": ["Shlomo Efraim"],
        }
        results = [
            {"document_title": "El Jardín de las Almas", "match_type": "fts", "rank": 0.3,
             "plain_excerpt": "palabras sin termino esperado", "highlighted_excerpt": ""},
        ]
        eval_result = evaluate_case(case, results, top_k=10, mode="auto")
        assert eval_result["status"] == "PARTIAL"

    def test_evaluate_fail(self):
        from scripts.evaluate_bibliographic_search import evaluate_case

        case = {
            "id": "test_03",
            "expected_document_title": "Libro Inexistente",
            "expected_terms": ["termino_inexistente_xyz"],
        }
        results = [
            {"document_title": "Otro Libro", "match_type": "fts", "rank": 0.1,
             "plain_excerpt": "contenido sin relación", "highlighted_excerpt": ""},
        ]
        eval_result = evaluate_case(case, results, top_k=10, mode="auto")
        assert eval_result["status"] == "FAIL"

    def test_evaluate_empty_results(self):
        from scripts.evaluate_bibliographic_search import evaluate_case

        case = {"id": "test_04", "expected_document_title": "Libro", "expected_terms": ["algo"]}
        eval_result = evaluate_case(case, [], top_k=10, mode="auto")
        assert eval_result["status"] == "FAIL"
        assert "no matching" in eval_result["reason"]

    def test_evaluate_term_in_wrong_doc(self):
        from scripts.evaluate_bibliographic_search import evaluate_case

        case = {
            "id": "test_05",
            "expected_document_title": "Libro A",
            "expected_terms": ["termino"],
        }
        results = [
            {"document_title": "Libro B", "match_type": "phrase", "rank": 0.9,
             "plain_excerpt": "contiene el termino esperado", "highlighted_excerpt": ""},
        ]
        eval_result = evaluate_case(case, results, top_k=10, mode="auto")
        assert eval_result["status"] == "PARTIAL"
        assert "different document" in eval_result["reason"]


# ── Filter tests ─────────────────────────────────────────────────────────


class TestFilterCases:
    def test_filter_level(self):
        from scripts.evaluate_bibliographic_search import filter_cases

        cases = [
            {"id": "a", "level": 1, "category": "literal", "book": "X"},
            {"id": "b", "level": 2, "category": "literal", "book": "X"},
            {"id": "c", "level": 1, "category": "comprehension", "book": "X"},
        ]
        args = type("Args", (), {"only_level": 1, "only_category": None, "only_book": None})()
        filtered = filter_cases(cases, args)
        assert len(filtered) == 2
        assert all(c["level"] == 1 for c in filtered)

    def test_filter_category(self):
        from scripts.evaluate_bibliographic_search import filter_cases

        cases = [
            {"id": "a", "level": 1, "category": "literal", "book": "X"},
            {"id": "b", "level": 2, "category": "comprehension", "book": "X"},
        ]
        args = type("Args", (), {"only_level": None, "only_category": "literal", "only_book": None})()
        filtered = filter_cases(cases, args)
        assert len(filtered) == 1
        assert filtered[0]["category"] == "literal"

    def test_filter_book(self):
        from scripts.evaluate_bibliographic_search import filter_cases

        cases = [
            {"id": "a", "level": 1, "category": "literal", "book": "X"},
            {"id": "b", "level": 2, "category": "literal", "book": "Y"},
            {"id": "c", "level": 1, "category": "literal", "book": "X"},
        ]
        args = type("Args", (), {"only_level": None, "only_category": None, "only_book": "X"})()
        filtered = filter_cases(cases, args)
        assert len(filtered) == 2
        assert all(c["book"] == "X" for c in filtered)


# ── CLI tests ────────────────────────────────────────────────────────────


class TestCLI:
    def test_parse_args_required(self):
        from scripts.evaluate_bibliographic_search import _parse_args

        args = _parse_args(["--cases", "/tmp/cases.json"])
        assert args.cases == "/tmp/cases.json"
        assert args.top_k == 10
        assert args.mode == "auto"

    def test_parse_args_all(self):
        from scripts.evaluate_bibliographic_search import _parse_args

        args = _parse_args([
            "--cases", "/tmp/cases.json",
            "--collection", "test",
            "--top-k", "5",
            "--mode", "phrase",
            "--language", "en",
            "--output-json", "/tmp/out.json",
            "--output-md", "/tmp/out.md",
            "--fail-under", "50",
            "--only-level", "2",
            "--only-category", "literal",
            "--only-book", "Test Book",
            "--verbose",
        ])
        assert args.top_k == 5
        assert args.mode == "phrase"
        assert args.only_level == 2
        assert args.verbose is True

    def test_load_cases_valid(self):
        from scripts.evaluate_bibliographic_search import load_cases

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([{"id": "test"}], f)
            p = f.name
        try:
            cases = load_cases(p)
            assert len(cases) == 1
            assert cases[0]["id"] == "test"
        finally:
            pathlib.Path(p).unlink()

    def test_load_cases_invalid(self):
        from scripts.evaluate_bibliographic_search import load_cases

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"not": "array"}')
            p = f.name
        try:
            with pytest.raises(ValueError):
                load_cases(p)
        finally:
            pathlib.Path(p).unlink()

    def test_file_not_found(self):
        from scripts.evaluate_bibliographic_search import load_cases

        with pytest.raises(FileNotFoundError):
            load_cases("/tmp/nonexistent_file_99999.json")
