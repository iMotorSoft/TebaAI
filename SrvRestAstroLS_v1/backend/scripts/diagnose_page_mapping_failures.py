#! /usr/bin/env python3
"""Diagnose low-coverage PDF page mapping without changing persisted data.

The command reads current chunks from PostgreSQL in a read-only transaction,
extracts local PDFs page by page and compares conservative matching variants.
It never calls Milvus or LiteLLM and has no apply mode.
"""

from __future__ import annotations

import argparse
import asyncio
import difflib
import json
import math
import pathlib
import re
import sys
import unicodedata
from collections import Counter
from typing import Any, Callable

import pymupdf as fitz

from scripts.audit_page_chunk_mapping import (
    _find_pdf,
    _make_anchors as _baseline_anchors,
    _match_anchor_in_pages,
    _normalize as _baseline_normalize,
)


FAILURE_CATEGORIES = (
    "NO_TEXT_MATCH",
    "ANCHOR_TOO_SHORT",
    "ANCHOR_REPEATED",
    "START_MATCH_ONLY",
    "END_MATCH_ONLY",
    "CROSS_PAGE_UNCERTAIN",
    "HYphenation_OR_LINEBREAK",
    "HEADER_FOOTER_NOISE",
    "LAYOUT_ORDER_MISMATCH",
    "OCR_OR_EXTRACTION_DIFFERENCE",
    "CHUNK_TOO_LONG",
    "CHUNK_TOO_SHORT",
    "AMBIGUOUS_MULTIPLE_PAGES",
    "PDF_NOT_FOUND",
    "UNKNOWN",
)

STRATEGIES = (
    "baseline_current_matcher",
    "normalization_plus",
    "hyphenation_fix",
    "header_footer_strip",
    "sliding_window_similarity",
    "relaxed_medium_candidate",
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose page mapping failures (read-only).")
    parser.add_argument("--collection", default="breslov")
    parser.add_argument("--pdf-root", default="/media/issajar/DEVELOP/Download/Tora/Breslov")
    parser.add_argument("--document-title", required=True, help="Case-insensitive title substring")
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--sample-size", type=int, default=50)
    parser.add_argument("--max-samples-per-category", type=int, default=5)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    if args.sample_size < 1:
        parser.error("--sample-size must be positive")
    if args.max_samples_per_category < 1:
        parser.error("--max-samples-per-category must be positive")
    return args


def _normalize_plus(text: str) -> str:
    """Normalize accents, punctuation, markdown marks and whitespace."""
    text = unicodedata.normalize("NFKD", text.casefold()).replace("\u00ad", "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[#*_`~\[\](){}<>|]", " ", text)
    text = re.sub(r"[^\w\s\u0590-\u05ff]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _dehyphenate(text: str) -> str:
    """Join words split by a PDF line-ending hyphen."""
    return re.sub(r"(?<=\w)[\-‐‑]\s*\n\s*(?=\w)", "", text)


def _normalize_hyphenation(text: str) -> str:
    return _normalize_plus(_dehyphenate(text))


def _has_hyphenation_or_linebreak(text: str) -> bool:
    return bool(re.search(r"(?<=\w)[\-‐‑]\s*\n\s*(?=\w)", text))


def _make_normalized_anchors(
    text: str,
    normalizer: Callable[[str], str],
    anchor_chars: int = 100,
    minimum: int = 50,
) -> list[str]:
    norm = normalizer(text)
    if len(norm) < minimum:
        return []
    if len(norm) <= anchor_chars * 3:
        return [norm]
    positions = (0, len(norm) // 3, len(norm) // 2, (len(norm) * 2) // 3, len(norm) - anchor_chars)
    anchors: list[str] = []
    for pos in positions:
        anchor = norm[max(0, pos) : max(0, pos) + anchor_chars].strip()
        if len(anchor) >= minimum and anchor not in anchors:
            anchors.append(anchor)
    return anchors


def _match_result(
    content: str,
    page_texts: list[str],
    *,
    normalizer: Callable[[str], str] | None = None,
    anchor_chars: int = 150,
    minimum: int = 50,
) -> dict[str, Any]:
    """Apply the current confidence rules to baseline or normalized text."""
    if normalizer is None:
        anchors = _baseline_anchors(content, n=anchor_chars)
        start_anchors = _baseline_anchors(content[: min(300, len(content))], n=80)
        end_anchors = _baseline_anchors(content[-min(300, len(content)) :], n=80)
        normalized_length = len(_baseline_normalize(content))
    else:
        anchors = _make_normalized_anchors(content, normalizer, anchor_chars, minimum)
        start_anchors = _make_normalized_anchors(content[: min(300, len(content))], normalizer, 80, minimum)
        end_anchors = _make_normalized_anchors(content[-min(300, len(content)) :], normalizer, 80, minimum)
        normalized_length = len(normalizer(content))

    page_hits: Counter[int] = Counter()
    anchor_occurrences: list[int] = []
    for anchor in anchors:
        hits = _match_anchor_in_pages(anchor, page_texts)
        anchor_occurrences.append(len(hits))
        page_hits.update(hits)

    start_pages: set[int] = set()
    end_pages: set[int] = set()
    for anchor in start_anchors:
        start_pages.update(_match_anchor_in_pages(anchor, page_texts))
    for anchor in end_anchors:
        end_pages.update(_match_anchor_in_pages(anchor, page_texts))

    middle_anchors = anchors[1:-1] if len(anchors) > 2 else []
    middle_found = any(_match_anchor_in_pages(anchor, page_texts) for anchor in middle_anchors)
    candidates = sorted(page_hits)
    max_hits = max(page_hits.values(), default=0)
    total_anchors = len(anchors)
    score = max_hits / total_anchors if total_anchors else 0.0
    result: dict[str, Any] = {
        "confidence": "none",
        "page_start": None,
        "page_end": None,
        "best_page_candidate": None,
        "best_page_score": round(score, 4),
        "candidate_pages": candidates,
        "number_of_candidate_pages": len(candidates),
        "start_anchor_found": bool(start_pages),
        "end_anchor_found": bool(end_pages),
        "middle_anchors_found": middle_found,
        "anchor_count": total_anchors,
        "max_anchor_occurrences": max(anchor_occurrences, default=0),
        "ambiguous": False,
        "normalized_length": normalized_length,
    }
    if not page_hits:
        return result

    best_page = sorted(page_hits, key=lambda page: (-page_hits[page], page))[0]
    result["best_page_candidate"] = best_page
    if len(candidates) > 1 and candidates[-1] - candidates[0] > 2:
        result.update(
            confidence="low",
            page_start=candidates[0],
            page_end=candidates[-1],
            ambiguous=True,
        )
        return result

    if start_pages and end_pages:
        page_start = min(start_pages)
        page_end = max(end_pages)
        if page_start != page_end and score >= 0.5:
            result.update(confidence="high", page_start=page_start, page_end=page_end)
            return result
        if page_start == page_end:
            confidence = "high" if score >= 0.6 else "medium"
            result.update(confidence=confidence, page_start=page_start, page_end=page_start)
            return result

    confidence = "medium" if score >= 0.4 else "low"
    result.update(confidence=confidence, page_start=best_page, page_end=best_page)
    return result


def _repeated_boundary_lines(raw_pages: list[str]) -> set[str]:
    """Find short lines repeated near page tops or bottoms."""
    counts: Counter[str] = Counter()
    for page in raw_pages:
        lines = [line.strip() for line in page.splitlines() if line.strip()]
        seen: set[str] = set()
        for line in lines[:3] + lines[-3:]:
            normalized = _normalize_plus(line)
            if 3 <= len(normalized) <= 100 and len(normalized.split()) <= 15:
                seen.add(normalized)
        counts.update(seen)
    threshold = max(3, math.ceil(len(raw_pages) * 0.08))
    return {line for line, count in counts.items() if count >= threshold}


def _strip_boundary_noise(text: str, repeated_lines: set[str]) -> str:
    kept = [line for line in text.splitlines() if _normalize_plus(line) not in repeated_lines]
    return "\n".join(kept)


def _similarity_result(content: str, page_texts: list[str], page_tokens: list[set[str]]) -> dict[str, Any]:
    chunk = _normalize_plus(content)
    chunk_tokens = {word for word in chunk.split() if len(word) >= 3}
    if len(chunk) < 50 or not chunk_tokens:
        return {"confidence": "none", "page_start": None, "page_end": None, "ambiguous": False,
                "best_page_candidate": None, "best_page_score": 0.0, "number_of_candidate_pages": 0}

    overlap_ranking = sorted(
        range(len(page_texts)),
        key=lambda index: len(chunk_tokens & page_tokens[index]) / len(chunk_tokens),
        reverse=True,
    )[:4]
    chunk_words = chunk.split()[:900]
    scores: list[tuple[float, int, int]] = []
    for index in overlap_ranking:
        page = page_texts[index]
        page_words = page.split()[:1200]
        scores.append((difflib.SequenceMatcher(None, chunk_words, page_words).ratio(), index + 1, index + 1))
        if index + 1 < len(page_texts):
            pair = f"{page} {page_texts[index + 1]}"
            pair_words = pair.split()[:1800]
            scores.append((difflib.SequenceMatcher(None, chunk_words, pair_words).ratio(), index + 1, index + 2))
    scores.sort(reverse=True)
    best_score, page_start, page_end = scores[0]
    second_score = scores[1][0] if len(scores) > 1 else 0.0
    ambiguous = best_score - second_score < 0.025
    if best_score >= 0.78 and not ambiguous:
        confidence = "high"
    elif best_score >= 0.58 and best_score - second_score >= 0.03:
        confidence = "medium"
    elif best_score >= 0.40:
        confidence = "low"
    else:
        confidence = "none"
        page_start = page_end = None
    return {
        "confidence": confidence,
        "page_start": page_start,
        "page_end": page_end,
        "best_page_candidate": page_start,
        "best_page_score": round(best_score, 4),
        "number_of_candidate_pages": len(overlap_ranking),
        "ambiguous": ambiguous,
    }


def _confidence_rank(value: str) -> int:
    return {"none": 0, "low": 1, "medium": 2, "high": 3}.get(value, 0)


def _categorize_failure(metrics: dict[str, Any]) -> str:
    """Assign one actionable primary category using deterministic precedence."""
    if metrics.get("pdf_not_found"):
        return "PDF_NOT_FOUND"
    if metrics.get("anchor_too_short"):
        return "ANCHOR_TOO_SHORT"
    if metrics.get("chunk_too_short"):
        return "CHUNK_TOO_SHORT"
    if metrics.get("chunk_too_long"):
        return "CHUNK_TOO_LONG"
    if metrics.get("anchor_repeated"):
        return "ANCHOR_REPEATED"
    if metrics.get("ambiguous"):
        return "AMBIGUOUS_MULTIPLE_PAGES"
    if metrics.get("start_anchor_found") and not metrics.get("end_anchor_found"):
        return "START_MATCH_ONLY"
    if metrics.get("end_anchor_found") and not metrics.get("start_anchor_found"):
        return "END_MATCH_ONLY"
    if metrics.get("cross_page_uncertain"):
        return "CROSS_PAGE_UNCERTAIN"
    if metrics.get("hyphenation_improved") or metrics.get("hyphenation_indicator"):
        return "HYphenation_OR_LINEBREAK"
    if metrics.get("header_footer_improved"):
        return "HEADER_FOOTER_NOISE"
    if metrics.get("full_extraction_anchor_found") and metrics.get("page_similarity", 0) >= 0.35:
        return "LAYOUT_ORDER_MISMATCH"
    if metrics.get("full_extraction_anchor_found"):
        return "OCR_OR_EXTRACTION_DIFFERENCE"
    if metrics.get("no_text_match"):
        return "NO_TEXT_MATCH"
    return "UNKNOWN"


def _select_sample(rows: list[dict[str, Any]], size: int) -> list[dict[str, Any]]:
    """Select deterministic, evenly distributed rows across a document."""
    if size >= len(rows):
        return list(rows)
    if size == 1:
        return [rows[len(rows) // 2]]
    indexes = {round(index * (len(rows) - 1) / (size - 1)) for index in range(size)}
    return [rows[index] for index in sorted(indexes)]


def _limit_samples_by_category(samples: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    limited: list[dict[str, Any]] = []
    for sample in samples:
        category = sample["category"]
        if counts[category] >= limit:
            continue
        counts[category] += 1
        limited.append(sample)
    return limited


def _strategy_summary(
    strategy: str,
    results: list[dict[str, Any]],
    *,
    total_chunks: int,
    already_mapped: int,
    total_unmapped: int,
) -> dict[str, Any]:
    counts = Counter(result["confidence"] for result in results)
    ambiguous = sum(1 for result in results if result.get("ambiguous"))
    denominator = len(results) or 1
    estimated_high = min(total_unmapped, round(counts["high"] / denominator * total_unmapped))
    estimated_medium = min(total_unmapped - estimated_high, round(counts["medium"] / denominator * total_unmapped))
    risk = {
        "baseline_current_matcher": "low",
        "normalization_plus": "low",
        "hyphenation_fix": "low",
        "header_footer_strip": "low",
        "sliding_window_similarity": "medium",
        "relaxed_medium_candidate": "high",
    }[strategy]
    return {
        "strategy": strategy,
        "strategy_name": strategy,
        "candidate_high": counts["high"],
        "candidate_medium": counts["medium"],
        "candidate_low": counts["low"],
        "none": counts["none"],
        "ambiguous": ambiguous,
        "estimated_new_high": estimated_high,
        "estimated_new_medium": estimated_medium,
        "estimated_coverage": round((already_mapped + estimated_high) / total_chunks * 100, 1) if total_chunks else 0.0,
        "estimated_high_medium_coverage": round(
            (already_mapped + estimated_high + estimated_medium) / total_chunks * 100, 1
        ) if total_chunks else 0.0,
        "risk": risk,
        "recommended": False,
        "recommended_apply": False,
    }


def _add_validation(
    summary: dict[str, Any],
    chunks: list[dict[str, Any]],
    results: list[dict[str, Any]],
) -> None:
    predicted = 0
    exact = 0
    high_predicted = 0
    high_exact = 0
    for chunk, result in zip(chunks, results, strict=True):
        confidence = result["confidence"]
        if confidence == "none":
            continue
        predicted += 1
        is_exact = (
            result.get("page_start") == chunk.get("page_start")
            and result.get("page_end") == chunk.get("page_end")
        )
        exact += int(is_exact)
        if confidence == "high":
            high_predicted += 1
            high_exact += int(is_exact)
    summary["validation_sample"] = len(chunks)
    summary["validation_predictions"] = predicted
    summary["validation_exact_accuracy"] = round(exact / predicted * 100, 1) if predicted else 0.0
    summary["validation_high_predictions"] = high_predicted
    summary["validation_high_precision"] = round(high_exact / high_predicted * 100, 1) if high_predicted else 0.0


def _recommend_strategies(strategies: list[dict[str, Any]]) -> None:
    """Recommend only incremental low-risk gains with holdout precision."""
    by_name = {item["strategy"]: item for item in strategies}
    baseline_high = by_name["baseline_current_matcher"]["candidate_high"]
    normalization_high = by_name["normalization_plus"]["candidate_high"]
    hyphenation_high = by_name["hyphenation_fix"]["candidate_high"]
    for item in strategies:
        name = item["strategy"]
        if name == "normalization_plus":
            incremental = item["candidate_high"] > baseline_high
        elif name == "hyphenation_fix":
            incremental = item["candidate_high"] > normalization_high
        elif name == "header_footer_strip":
            incremental = item["candidate_high"] > max(normalization_high, hyphenation_high)
        else:
            incremental = False
        denominator = max(1, item["candidate_high"] + item["candidate_medium"] + item["candidate_low"] + item["none"])
        item["recommended"] = bool(
            item["risk"] == "low"
            and incremental
            and item.get("validation_high_predictions", 0) >= 5
            and item.get("validation_high_precision", 0.0) == 100.0
            and item["ambiguous"] / denominator <= 0.05
        )
        item["recommended_apply"] = item["recommended"]


def _safe_sample(chunk: dict[str, Any], category: str, metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "chunk_id": str(chunk["id"]),
        "chunk_index": chunk["chunk_index"],
        "category": category,
        "chunk_length": metrics["chunk_length"],
        "normalized_chunk_length": metrics["normalized_chunk_length"],
        "best_page_candidate": metrics.get("best_page_candidate"),
        "best_page_score": metrics.get("best_page_score", 0.0),
        "start_anchor_found": metrics.get("start_anchor_found", False),
        "end_anchor_found": metrics.get("end_anchor_found", False),
        "middle_anchors_found": metrics.get("middle_anchors_found", False),
        "number_of_candidate_pages": metrics.get("number_of_candidate_pages", 0),
        "linebreak_density": metrics["linebreak_density"],
        "hyphenation_indicators": metrics["hyphenation_indicators"],
        "repeated_text_indicators": metrics["repeated_text_indicators"],
        "full_extraction_anchor_found": metrics["full_extraction_anchor_found"],
    }


def _diagnose_samples(
    chunks: list[dict[str, Any]],
    raw_pages: list[str],
    full_extraction: str,
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    baseline_pages = [_baseline_normalize(page) for page in raw_pages]
    plus_pages = [_normalize_plus(page) for page in raw_pages]
    hyphen_pages = [_normalize_hyphenation(page) for page in raw_pages]
    repeated_lines = _repeated_boundary_lines(raw_pages)
    stripped_pages = [_normalize_plus(_strip_boundary_noise(page, repeated_lines)) for page in raw_pages]
    page_tokens = [{word for word in page.split() if len(word) >= 3} for page in plus_pages]
    full_norm = _normalize_plus(full_extraction)

    samples: list[dict[str, Any]] = []
    strategy_results: dict[str, list[dict[str, Any]]] = {name: [] for name in STRATEGIES}
    for chunk in chunks:
        content = chunk.get("content") or ""
        baseline = _match_result(content, baseline_pages)
        plus = _match_result(content, plus_pages, normalizer=_normalize_plus, anchor_chars=100)
        hyphen = _match_result(content, hyphen_pages, normalizer=_normalize_hyphenation, anchor_chars=100)
        stripped = _match_result(content, stripped_pages, normalizer=_normalize_plus, anchor_chars=100)
        similarity = _similarity_result(content, plus_pages, page_tokens)
        relaxed = _match_result(content, plus_pages, normalizer=_normalize_plus, anchor_chars=60, minimum=30)
        if relaxed["confidence"] == "high":
            relaxed["confidence"] = "medium"

        strategy_results["baseline_current_matcher"].append(baseline)
        strategy_results["normalization_plus"].append(plus)
        strategy_results["hyphenation_fix"].append(hyphen)
        strategy_results["header_footer_strip"].append(stripped)
        strategy_results["sliding_window_similarity"].append(similarity)
        strategy_results["relaxed_medium_candidate"].append(relaxed)

        norm_length = len(_normalize_plus(content))
        full_anchors = _make_normalized_anchors(content, _normalize_plus, 80, 40)
        full_found = any(anchor in full_norm for anchor in full_anchors)
        candidate_page = similarity.get("best_page_candidate")
        raw_candidate = raw_pages[candidate_page - 1] if candidate_page else ""
        hyphen_count = len(re.findall(r"(?<=\w)[\-‐‑]\s*\n\s*(?=\w)", content + "\n" + raw_candidate))
        repeated_count = sum(1 for line in content.splitlines() if _normalize_plus(line) in repeated_lines)
        metrics = {
            **baseline,
            "chunk_length": len(content),
            "normalized_chunk_length": norm_length,
            "linebreak_density": round(content.count("\n") / max(1, len(content)), 4),
            "hyphenation_indicators": hyphen_count,
            "repeated_text_indicators": repeated_count,
            "anchor_too_short": norm_length < 50,
            "chunk_too_short": len(content) < 200,
            "chunk_too_long": len(content) > 2800,
            "anchor_repeated": baseline["max_anchor_occurrences"] > 1,
            "cross_page_uncertain": (
                baseline["start_anchor_found"] and baseline["end_anchor_found"]
                and baseline["confidence"] in {"low", "none"}
            ),
            "hyphenation_indicator": _has_hyphenation_or_linebreak(content) or hyphen_count > 0,
            "hyphenation_improved": _confidence_rank(hyphen["confidence"]) > _confidence_rank(plus["confidence"]),
            "header_footer_improved": _confidence_rank(stripped["confidence"]) > _confidence_rank(plus["confidence"]),
            "full_extraction_anchor_found": full_found,
            "page_similarity": similarity.get("best_page_score", 0.0),
            "no_text_match": baseline["confidence"] == "none",
        }
        category = _categorize_failure(metrics)
        samples.append(_safe_sample(chunk, category, metrics))
    return samples, strategy_results


def _build_report(
    *,
    collection: str,
    document: dict[str, Any],
    pdf_path: pathlib.Path | None,
    chunks: list[dict[str, Any]],
    diagnosed: list[dict[str, Any]],
    strategies: list[dict[str, Any]],
    max_samples_per_category: int,
    pdf_page_count: int = 0,
) -> dict[str, Any]:
    already_mapped = sum(1 for chunk in chunks if chunk.get("page_start") is not None)
    baseline_counts = (
        Counter(result["confidence"] for result in strategies[0].pop("_raw_results", []))
        if strategies
        else Counter()
    )
    failure_counts = Counter(sample["category"] for sample in diagnosed)
    lengths = sorted(sample.get("chunk_length", 0) for sample in diagnosed)
    median_length = lengths[len(lengths) // 2] if lengths else 0
    page_anchor_found = sum(1 for sample in diagnosed if sample.get("number_of_candidate_pages", 0) > 0)
    full_anchor_found = sum(1 for sample in diagnosed if sample.get("full_extraction_anchor_found"))
    return {
        "collection": collection,
        "document_title": document["title"],
        "pdf_path": str(pdf_path) if pdf_path else None,
        "page_number_type": "pdf_physical_page",
        "pdf_page_count": pdf_page_count,
        "summary": {
            "total_chunks": len(chunks),
            "already_mapped": already_mapped,
            "unmapped": len(chunks) - already_mapped,
            "low_confidence": baseline_counts["low"],
            "medium_confidence": baseline_counts["medium"],
            "ambiguous": sum(1 for sample in diagnosed if sample["category"] == "AMBIGUOUS_MULTIPLE_PAGES"),
            "diagnosed_samples": len(diagnosed),
            "sample_based": True,
        },
        "failure_categories": {category: failure_counts.get(category, 0) for category in FAILURE_CATEGORIES},
        "text_comparison": {
            "full_extraction_anchor_found": full_anchor_found,
            "page_aware_baseline_anchor_found": page_anchor_found,
            "full_extraction_only": sum(
                1 for sample in diagnosed
                if sample.get("full_extraction_anchor_found") and sample.get("number_of_candidate_pages", 0) == 0
            ),
            "start_only": failure_counts["START_MATCH_ONLY"],
            "end_only": failure_counts["END_MATCH_ONLY"],
            "cross_page_uncertain": failure_counts["CROSS_PAGE_UNCERTAIN"],
            "hyphenation_or_linebreak": failure_counts["HYphenation_OR_LINEBREAK"],
            "repeated_text_or_ambiguity": (
                failure_counts["ANCHOR_REPEATED"] + failure_counts["AMBIGUOUS_MULTIPLE_PAGES"]
            ),
            "sample_chunk_length_min": lengths[0] if lengths else 0,
            "sample_chunk_length_median": median_length,
            "sample_chunk_length_max": lengths[-1] if lengths else 0,
        },
        "strategy_candidates": strategies,
        "candidate_improvement_by_strategy": {
            item["strategy"]: {
                "estimated_new_high": item["estimated_new_high"],
                "estimated_new_medium": item["estimated_new_medium"],
                "ambiguous": item["ambiguous"],
            }
            for item in strategies
        },
        "risk_by_strategy": {item["strategy"]: item["risk"] for item in strategies},
        "sample_failures": _limit_samples_by_category(diagnosed, max_samples_per_category),
        "limitations": [
            "diagnosis only; no metadata is applied",
            "strategy estimates are sample-based",
            "page numbers are physical PDF pages",
        ],
    }


def _write_json(report: dict[str, Any], path: str) -> None:
    pathlib.Path(path).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_md(report: dict[str, Any], path: str) -> None:
    summary = report["summary"]
    lines = [
        "# Page Mapping Failure Diagnosis",
        "",
        "## Summary",
        "",
        f"- Document: {report['document_title']}",
        f"- Chunks: {summary['total_chunks']} total; {summary['already_mapped']} already mapped; "
        f"{summary['unmapped']} unmapped.",
        f"- Diagnosed sample: {summary['diagnosed_samples']} unmapped chunks (sample-based estimates).",
        f"- PDF pages: {report['pdf_page_count']}.",
        "- Page references in this report are physical PDF pages.",
        "",
        "## Failure categories",
        "",
        "| Category | Sample count |",
        "| --- | ---: |",
    ]
    lines.extend(f"| {category} | {count} |" for category, count in report["failure_categories"].items() if count)
    comparison = report["text_comparison"]
    lines.extend([
        "",
        "### Text extraction comparison",
        "",
        f"- Full-document anchors found: {comparison['full_extraction_anchor_found']}/{summary['diagnosed_samples']}.",
        f"- Page-aware baseline anchors found: {comparison['page_aware_baseline_anchor_found']}/"
        f"{summary['diagnosed_samples']}.",
        f"- Full-extraction-only gaps: {comparison['full_extraction_only']}.",
        f"- Sample chunk lengths: min={comparison['sample_chunk_length_min']}, "
        f"median={comparison['sample_chunk_length_median']}, max={comparison['sample_chunk_length_max']}.",
        "",
        "## Representative samples",
        "",
    ])
    for sample in report["sample_failures"]:
        lines.append(
            f"- chunk_index={sample['chunk_index']} category={sample['category']} "
            f"best_page={sample['best_page_candidate']} score={sample['best_page_score']} "
            f"candidates={sample['number_of_candidate_pages']}"
        )
    lines.extend([
        "",
        "## Strategy dry-runs",
        "",
        "| Strategy | Sample high | Sample medium | Ambiguous | Estimated new high | "
        "Validation high precision | Risk | Recommended |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ])
    for strategy in report["strategy_candidates"]:
        lines.append(
            f"| {strategy['strategy']} | {strategy['candidate_high']} | {strategy['candidate_medium']} | "
            f"{strategy['ambiguous']} | {strategy['estimated_new_high']} | "
            f"{strategy.get('validation_high_precision', 0.0)}% | {strategy['risk']} | "
            f"{'yes' if strategy['recommended'] else 'no'} |"
        )
    recommended = [item["strategy"] for item in report["strategy_candidates"] if item["recommended"]]
    lines.extend([
        "",
        "## Recommended next step",
        "",
        ("Validate and implement the low-risk strategy: " + ", ".join(recommended) + ".")
        if recommended else "No strategy should be applied automatically; expand validation before changing metadata.",
        "",
        "## Risks",
        "",
        "- Candidate gains are estimates from a deterministic sample, not persisted mappings.",
        "- Similarity and relaxed anchors can increase false positives or ambiguity.",
        "- Header/footer and mixed-layout detection remains heuristic.",
        "- No chunk content, page metadata, vector index or embedding was changed.",
    ])
    pathlib.Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


async def _run(args: argparse.Namespace) -> int:
    from core.config import get_settings
    from infrastructure.postgres.pool import close_pool, create_pool_from_settings, open_pool
    from infrastructure.postgres.transaction import fetch_all

    settings = get_settings()
    if not settings.postgres_enabled:
        print("ERROR: TEBAAI_POSTGRES_ENABLED is not true", file=sys.stderr)
        return 1
    pdf_root = pathlib.Path(args.pdf_root)
    if not pdf_root.is_dir():
        print(f"ERROR: PDF root not found: {pdf_root}", file=sys.stderr)
        return 1

    pool = create_pool_from_settings()
    await open_pool(pool)
    try:
        async with pool.connection() as conn:
            async with conn.transaction():
                await conn.execute("SET TRANSACTION READ ONLY")
                database = await fetch_all(conn, "SELECT current_database() AS database")
                if not database or database[0]["database"] != "tebaai":
                    print("ERROR: expected database tebaai", file=sys.stderr)
                    return 1
                documents = await fetch_all(
                    conn,
                    """
                    SELECT d.id, d.title, d.source_filename, d.author
                    FROM library_documents d
                    JOIN library_collections c ON c.id = d.collection_id
                    WHERE c.code = %(collection)s AND d.status = 'ready'
                      AND LOWER(d.title) LIKE %(title_pattern)s
                    ORDER BY d.title
                    """,
                    {"collection": args.collection, "title_pattern": f"%{args.document_title.casefold()}%"},
                )
                if len(documents) != 1:
                    print(f"ERROR: expected one matching document, found {len(documents)}", file=sys.stderr)
                    return 1
                document = documents[0]
                chunks = await fetch_all(
                    conn,
                    """
                    SELECT id, chunk_index, content, content_length, page_start, page_end
                    FROM library_document_chunks
                    WHERE document_id = %(document_id)s
                    ORDER BY chunk_index
                    """,
                    {"document_id": str(document["id"])},
                )

        pdf_path = _find_pdf(document, pdf_root)
        if not pdf_path:
            missing_sample = {
                "chunk_id": "",
                "chunk_index": -1,
                "category": "PDF_NOT_FOUND",
                "chunk_length": 0,
                "normalized_chunk_length": 0,
                "best_page_candidate": None,
                "best_page_score": 0.0,
                "start_anchor_found": False,
                "end_anchor_found": False,
                "middle_anchors_found": False,
                "number_of_candidate_pages": 0,
                "linebreak_density": 0.0,
                "hyphenation_indicators": 0,
                "repeated_text_indicators": 0,
                "full_extraction_anchor_found": False,
            }
            report = _build_report(
                collection=args.collection,
                document=document,
                pdf_path=None,
                chunks=chunks,
                diagnosed=[missing_sample],
                strategies=[],
                max_samples_per_category=args.max_samples_per_category,
                pdf_page_count=0,
            )
            _write_json(report, args.output_json)
            _write_md(report, args.output_md)
            return 2

        pdf = fitz.open(str(pdf_path))
        try:
            raw_pages = [pdf.load_page(index).get_text() for index in range(pdf.page_count)]
        finally:
            pdf.close()
        try:
            import pymupdf4llm

            full_extraction = pymupdf4llm.to_markdown(str(pdf_path))
        except Exception as exc:
            print(f"WARNING: full-document extraction unavailable: {type(exc).__name__}", file=sys.stderr)
            full_extraction = ""

        unmapped = [chunk for chunk in chunks if chunk.get("page_start") is None]
        sample_chunks = _select_sample(unmapped, args.sample_size)
        diagnosed, raw_strategy_results = _diagnose_samples(sample_chunks, raw_pages, full_extraction)
        strategies = []
        for strategy in STRATEGIES:
            summary = _strategy_summary(
                strategy,
                raw_strategy_results[strategy],
                total_chunks=len(chunks),
                already_mapped=len(chunks) - len(unmapped),
                total_unmapped=len(unmapped),
            )
            if strategy == "baseline_current_matcher":
                summary["_raw_results"] = raw_strategy_results[strategy]
            strategies.append(summary)

        mapped_validation_chunks = _select_sample(
            [chunk for chunk in chunks if chunk.get("page_start") is not None],
            min(25, args.sample_size),
        )
        _, validation_results = _diagnose_samples(mapped_validation_chunks, raw_pages, full_extraction)
        for summary in strategies:
            _add_validation(
                summary,
                mapped_validation_chunks,
                validation_results[summary["strategy"]],
            )
        _recommend_strategies(strategies)

        report = _build_report(
            collection=args.collection,
            document=document,
            pdf_path=pdf_path,
            chunks=chunks,
            diagnosed=diagnosed,
            strategies=strategies,
            max_samples_per_category=args.max_samples_per_category,
            pdf_page_count=len(raw_pages),
        )
        _write_json(report, args.output_json)
        _write_md(report, args.output_md)
        print(
            f"{document['title']}: total={len(chunks)} mapped={len(chunks) - len(unmapped)} "
            f"unmapped={len(unmapped)} diagnosed={len(diagnosed)}"
        )
        print(f"JSON: {args.output_json}")
        print(f"MD:   {args.output_md}")
        if args.verbose:
            for category, count in report["failure_categories"].items():
                if count:
                    print(f"  {category}: {count}")
        return 0
    finally:
        await close_pool(pool)


def main() -> int:
    return asyncio.run(_run(_parse_args()))


if __name__ == "__main__":
    sys.exit(main())
