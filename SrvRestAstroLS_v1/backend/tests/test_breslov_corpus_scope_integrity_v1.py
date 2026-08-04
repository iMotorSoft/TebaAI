"""Regression evidence for the blocked corpus-scope identity hypothesis."""

from __future__ import annotations

import json
from pathlib import Path

from modules.library.work_identity import resolve_from_filename

FIXTURE = Path(__file__).parent / "fixtures" / "breslov_corpus_scope_integrity_v1.json"


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_disputed_filename_is_likutey_halajot_not_likutey_moharan_ii() -> None:
    fixture = load_fixture()
    disputed = fixture["identity_cases"][0]

    code, _metadata = resolve_from_filename(disputed["filename"])

    assert code == disputed["expected_work_code"] == "lh"
    assert disputed["expected_family"] == "likutey_halajot"
    assert disputed["related_source_lesson"] == "likutey_moharan_ii_8"


def test_likutey_moharan_ii_filename_remains_separate() -> None:
    fixture = load_fixture()
    lmii = fixture["identity_cases"][2]

    code, metadata = resolve_from_filename(lmii["filename"])

    assert code == lmii["expected_work_code"] == "lmii"
    assert metadata["part"] == "II"


def test_technical_version_and_internal_lesson_are_not_work_family() -> None:
    fixture = load_fixture()

    assert fixture["negative_identity_cases"] == [
        {
            "surface": "LM II, 8",
            "rule": (
                "an internal source-lesson reference must not overwrite a "
                "containing Likutey Halajot work identity"
            ),
        }
    ]
    assert fixture["gate"].endswith("_BLOCKED")
