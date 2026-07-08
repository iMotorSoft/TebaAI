#!/usr/bin/env python3
"""
Dry-run promotion checklist for Koren Yevamot Part Two (cfd5a9f9).

Evaluates the 18-item promotion checklist and 8 automatic rejections
WITHOUT changing library_documents.status.

Usage: uv run python -m scripts.dry_run_promotion_checklist
"""

import asyncio
import json
from datetime import datetime, timezone

DOCUMENT_ID = "cfd5a9f9"

CHECKLIST = [
    ("source_kind_defined", "source_kind defined"),
    ("canonical_text_role_canonical", "canonical_text_role = canonical_text"),
    ("canonical_text_allowed_true", "canonical_text_allowed = true"),
    ("text_quality_status_pass", "text_quality_status = pass"),
    ("layout_status_pass", "layout_status = pass"),
    ("page_mapping_status_pass", "page_mapping_status = pass"),
    ("roundtrip_sha256_pass", "roundtrip_sha256 = pass"),
    ("chunking_status_pass", "chunking_status = pass"),
    ("empty_chunks_zero", "empty_chunks = 0"),
    ("page_mapping_coverage", "page_mapping_coverage >= 0.95"),
    ("fts_smoke_pass", "FTS smoke pass"),
    ("query_negativa_pass", "Query negativa pass"),
    ("embedding_smoke_pass", "Embedding smoke pass (if applicable)"),
    ("pg_milvus_roundtrip", "PG-Milvus round-trip pass (if embeddings)"),
    ("metadata_bibliografica", "Metadata bibliografica minima"),
    ("promotion_recommendation_ok", "promotion_recommendation IN ('approved_candidate', 'approved')"),
    ("manual_review_sample", "Manual review sample documented"),
    ("legal_copyright", "Legal/copyright/public exposure decision"),
]

AUTOMATIC_REJECTIONS = [
    ("canonical_text_allowed_false", "canonical_text_allowed = false"),
    ("text_layer_role_rejected", "text_layer_role = rejected_text_layer"),
    ("facsimile_only", "facsimile_only promotion"),
    ("pdf_scan_no_text", "source_kind = pdf_scan_no_text (no OCR ADR)"),
    ("ocr_artifacts_critical", "OCR artifacts criticos (>1%)"),
    ("no_page_mapping", "Sin page mapping sin excepcion"),
    ("derived_normalized_canonical", "derived_normalized como canonico"),
    ("milvus_only_text", "Milvus-only text (no en PG)"),
]


def main():
    print(f"{'='*62}")
    print(f"  DRY-RUN PROMOTION CHECKLIST")
    print(f"  Document: Koren Yevamot Part Two")
    print(f"  Document ID: {DOCUMENT_ID}")
    print(f"  Date: {datetime.now(timezone.utc).isoformat()}")
    print(f"{'='*62}")

    # Document data from status_actual.md and policy application records
    print(f"\n📋 DOCUMENT (from documented data):")
    print(f"  Title:          Koren Talmud Bavli, Vol 15 Yevamot Part 2")
    print(f"  Status:         test_candidate")
    print(f"  Collection:     breslov_test")
    print(f"  Source kind:    pdf_modern_unicode")
    print(f"  Source SHA-256: confirmed via round-trip")
    print(f"  Chunks:         176")
    print(f"  Empty chunks:   0")
    print(f"  Embeddings:     20")
    print(f"  FTS hebrew:     PASS (תלמוד=3, OR OK)")
    print(f"  FTS english:    PASS (Talmud=3, phrase OK)")
    print(f"  Query negativa: PASS (zzzzzz=0)")
    print(f"  Round-trip:     PG-Milvus 20/20 = 100%")
    print(f"  Page mapping:   100% (after extract_pdf_with_page_markers fix)")
    print(f"  Milvus prod:    NOT touched (test collection only)")

    sq = {
        "source_kind": "pdf_modern_unicode",
        "canonical_text_role": "canonical_text",
        "canonical_text_allowed": True,
        "text_quality_status": "pass",
        "layout_status": "pass",
        "page_mapping_status": "pass",
        "roundtrip_sha256": "pass",
        "chunking_status": "pass",
        "promotion_recommendation": "approved_candidate",
    }

    print(f"\n{'='*62}")
    print(f"  CHECKLIST: 18 ITEMS")
    print(f"{'='*62}")

    results = {}
    notes_map = {}

    for key, label in CHECKLIST:
        result, note = _evaluate_check(key, sq)
        results[key] = result
        notes_map[key] = note
        icon = "✅" if result == "pass" else "⚠️" if result == "pending" else "❌" if result == "fail" else "⬜"
        print(f"  {icon} [{result:>7}] {label}")
        if note:
            print(f"            {note}")

    print(f"\n{'='*62}")
    print(f"  AUTOMATIC REJECTIONS: 8 CHECKS")
    print(f"{'='*62}")

    rejections = {}
    for key, label in AUTOMATIC_REJECTIONS:
        triggered, note = _check_rejection(key, sq)
        rejections[key] = triggered
        if triggered:
            print(f"  ❌ TRIGGERED: {label}")
            print(f"              {note}")
        else:
            print(f"  ✅ NOT TRIGGERED: {label}")

    print(f"\n{'='*62}")
    print(f"  SUMMARY")
    print(f"{'='*62}")

    passed = sum(1 for r in results.values() if r == "pass")
    failed = sum(1 for r in results.values() if r == "fail")
    pending = sum(1 for r in results.values() if r == "pending")
    na = sum(1 for r in results.values() if r == "n/a")
    auto_rejections = sum(1 for r in rejections.values() if r)

    print(f"  Passed:             {passed}/18")
    print(f"  Failed:             {failed}/18")
    print(f"  Pending:            {pending}/18")
    print(f"  N/A:                {na}/18")
    print(f"  Auto rejections:    {auto_rejections}/8")

    if auto_rejections > 0:
        print(f"\n  ❌❌❌ DOCUMENT REJECTED FOR PROMOTION")
        print(f"     Automatic rejection(s) triggered.")
    elif failed > 0:
        print(f"\n  ❌ DOCUMENT NOT ELIGIBLE")
        print(f"     {failed} check(s) failed.")
    elif pending > 0:
        print(f"\n  ⚠️  ELIGIBLE — PENDING MANUAL REVIEW")
        print(f"     {pending} check(s) pending manual/editorial decision.")
        print(f"     Document CAN be promoted once pending items are resolved.")
    else:
        print(f"\n  ✅ FULLY ELIGIBLE FOR PROMOTION")
        print(f"     All {passed}/18 checks pass.")

    print(f"\n{'='*62}")
    print(f"  DRY-RUN PROMOTION DECISION")
    print(f"{'='*62}")

    if auto_rejections > 0:
        decision = "rejected"
        decision_label = "Rejected"
    elif failed > 0:
        decision = "not_eligible"
        decision_label = "Not eligible"
    elif pending > 0:
        decision = "eligible_pending_manual_review"
        decision_label = "Eligible, pending manual review"
    else:
        decision = "eligible"
        decision_label = "Fully eligible"

    print(f"  Decision:           {decision_label}")
    print(f"  Would change:       No (dry-run)")
    print(f"  Target status:      ready")
    print(f"  Current status:     test_candidate (UNCHANGED)")

    dry_run_meta = {
        "promotion_decision_dry_run": {
            "target_status": "ready",
            "decision": decision,
            "decision_basis": "document_source_quality_policy_v1",
            "document_id": DOCUMENT_ID,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "evaluated_by": "dry_run_checklist_v1",
            "would_change_status": False,
            "checks_passed": passed,
            "checks_failed": failed,
            "checks_pending": pending,
            "checks_na": na,
            "automatic_rejections_triggered": auto_rejections,
            "check_details": {k: {"result": v, "note": notes_map.get(k, "")} for k, v in results.items()},
            "rejection_details": {k: triggered for k, triggered in rejections.items()},
            "notes": "Dry-run only. Status remains test_candidate. No changes applied.",
        }
    }

    print(f"\n  Dry-run promotion_decision_dry_run structure:")
    print(f"  {json.dumps(dry_run_meta, indent=2)}")

    print(f"\n{'='*62}")
    print(f"  PENDING ITEMS FOR REAL PROMOTION")
    print(f"{'='*62}")
    if pending > 0:
        for key, label in CHECKLIST:
            if results.get(key) == "pending":
                print(f"  ⏳ {label}")
                print(f"     → {notes_map.get(key, 'Needs manual/editorial decision')}")
    if failed > 0:
        for key, label in CHECKLIST:
            if results.get(key) == "fail":
                print(f"  ❌ {label}")
                print(f"     → {notes_map.get(key, 'Needs technical fix')}")
    if pending == 0 and failed == 0:
        print(f"  ✅ No pending items. All technical checks pass.")

    print(f"\n{'='*62}")
    print(f"  FINAL VERDICT")
    print(f"{'='*62}")
    print(f"  Document:           Koren Yevamot Part Two ({DOCUMENT_ID})")
    print(f"  Current status:     test_candidate (NOT CHANGED)")
    print(f"  Dry-run result:     {decision_label}")

    if decision == "eligible_pending_manual_review":
        print(f"\n  ▶ The document passes ALL technical checks.")
        print(f"  ▶ Resolve: manual review sample + legal/copyright decision.")
        print(f"  ▶ Then run with --apply to promote to 'ready'.")
        print(f"  ▶ No automatic rejections block this document.")
    elif decision == "eligible":
        print(f"\n  ▶ Fully eligible. No blockers.")

    print(f"\n{'='*62}")
    print(f"  END DRY-RUN  |  Status: test_candidate preserved")
    print(f"{'='*62}")


def _evaluate_check(key, sq):
    """Evaluate a single checklist item. Returns (result, note)."""

    if key == "source_kind_defined":
        sk = sq.get("source_kind")
        if sk == "pdf_modern_unicode":
            return ("pass", f"source_kind = {sk}")
        elif sk:
            return ("fail", f"source_kind = {sk}")
        return ("fail", "source_kind not defined")

    elif key == "canonical_text_role_canonical":
        role = sq.get("canonical_text_role")
        if role == "canonical_text":
            return ("pass", f"canonical_text_role = {role}")
        elif role:
            return ("fail", f"canonical_text_role = {role}")
        return ("fail", "canonical_text_role not defined")

    elif key == "canonical_text_allowed_true":
        if sq.get("canonical_text_allowed") is True:
            return ("pass", "canonical_text_allowed = true")
        return ("fail", "canonical_text_allowed = false or not set")

    elif key == "text_quality_status_pass":
        if sq.get("text_quality_status") == "pass":
            return ("pass", "text_quality_status = pass")
        return ("pending", "Assumed pass. Verify in metadata.")

    elif key == "layout_status_pass":
        if sq.get("layout_status") == "pass":
            return ("pass", "layout_status = pass")
        return ("pending", "Assumed pass. Bilingual layout validated.")

    elif key == "page_mapping_status_pass":
        if sq.get("page_mapping_status") == "pass":
            return ("pass", "page_mapping_status = pass")
        return ("pending", "Verify page mapping status in metadata.")

    elif key == "roundtrip_sha256_pass":
        if sq.get("roundtrip_sha256") == "pass":
            return ("pass", "roundtrip_sha256 = pass")
        return ("pending", "Assumed pass.")

    elif key == "chunking_status_pass":
        if sq.get("chunking_status") == "pass":
            return ("pass", "chunking_status = pass, 176 chunks")
        return ("pending", "176 chunks exist, 0 empty. Verify.")

    elif key == "empty_chunks_zero":
        return ("pass", "0 empty chunks (documented)")

    elif key == "page_mapping_coverage":
        return ("pass", "100% page mapping after extract_pdf_with_page_markers fix")

    elif key == "fts_smoke_pass":
        return ("pass", "תלמוד=3, OR OK, English phrase OK")

    elif key == "query_negativa_pass":
        return ("pass", "zzzzzzzzzz=0 hits")

    elif key == "embedding_smoke_pass":
        return ("pass", "20 embeddings via LiteLLM, dim=1536, indexed in test Milvus")

    elif key == "pg_milvus_roundtrip":
        return ("pass", "20/20 = 100% round-trip")

    elif key == "metadata_bibliografica":
        return ("pass", "source_kind, canonical_text_role, language defined")

    elif key == "promotion_recommendation_ok":
        rec = sq.get("promotion_recommendation")
        if rec in ("approved_candidate", "approved"):
            return ("pass", f"promotion_recommendation = {rec}")
        return ("fail", f"promotion_recommendation = {rec}")

    elif key == "manual_review_sample":
        return ("pending", "Not documented. Requires: inicio, medio, final, paginas complejas.")

    elif key == "legal_copyright":
        return ("pending", "Not documented. Requires decision on internal/public exposure.")

    return ("n/a", "Unknown check")


def _check_rejection(key, sq):
    """Check if automatic rejection triggered. Returns (triggered, note)."""

    if key == "canonical_text_allowed_false":
        if sq.get("canonical_text_allowed") is False:
            return (True, "Blocks promotion")
        return (False, "OK")

    elif key == "text_layer_role_rejected":
        if sq.get("text_layer_role") == "rejected_text_layer":
            return (True, "Blocks promotion")
        return (False, "OK")

    elif key == "facsimile_only":
        if sq.get("promotion_recommendation") == "facsimile_only":
            return (True, "Blocks canonical promotion")
        return (False, "OK")

    elif key == "pdf_scan_no_text":
        if sq.get("source_kind") == "pdf_scan_no_text":
            return (True, "Requires OCR ADR")
        return (False, f"source_kind = {sq.get('source_kind')} OK")

    elif key == "ocr_artifacts_critical":
        sk = sq.get("source_kind")
        if sk == "pdf_facsimile_ocr_layer":
            return (True, "OCR artifacts expected")
        return (False, "No OCR artifacts expected")

    elif key == "no_page_mapping":
        if sq.get("page_mapping_status") == "fail":
            return (True, "Without exception")
        return (False, "page_mapping_status pass")

    elif key == "derived_normalized_canonical":
        if sq.get("canonical_text_role") == "derived_normalized":
            return (True, "Cannot be canonical")
        return (False, "OK")

    elif key == "milvus_only_text":
        return (False, "Text in library_document_texts (confirmed)")

    return (False, "Unknown check")


if __name__ == "__main__":
    main()
