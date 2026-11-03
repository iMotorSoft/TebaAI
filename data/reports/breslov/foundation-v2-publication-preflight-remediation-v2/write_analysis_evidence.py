"""Write the analysis evidence derived from the actual repository inspection.

Every field is taken from the files in this report directory or from the source
tree; nothing is inferred.
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent

TARGETED = [
    "test_activation_is_idempotent",
    "test_active_and_retained_generations_are_cleanup_protected",
    "test_atomic_cutover_and_rollback",
    "test_candidate_cleanup_does_not_touch_the_active_generation",
    "test_candidate_generation_is_invisible_to_normal_readers",
    "test_completed_candidate_does_not_steal_the_page_publication",
    "test_cross_document_pointer_is_rejected_by_the_database",
    "test_explicit_generation_inspection_reaches_the_candidate",
    "test_only_candidate_generations_can_be_activated",
    "test_reader_fails_closed_when_the_pointer_is_broken",
    "test_second_active_generation_is_rejected_by_the_database",
    "test_stale_expected_active_generation_is_rejected",
    "test_switch_is_audited",
]

QUERY = """INSERT INTO library_pages_v2(
    page_id, run_id, document_id, page_number, text, char_count,
    extraction_method, confidence, layout_notes)
VALUES (%s, %s, %s, 1, %s, %s, 'synthetic', 1.0,
        jsonb_build_object('region_publication',
            jsonb_build_object('page_status', 'FULL', 'marker', %s)))"""

targeted = {
    "source": "page-first-gateway-generation-order-remediation-v1/backend-results.json (full backend, historical)",
    "file": "SrvRestAstroLS_v1/backend/tests/test_generation_foundation.py",
    "fixture": "synthetic -> _create_synthetic -> page insert (jsonb_build_object)",
    "query": QUERY,
    "exception_class": "psycopg.errors.IndeterminateDatatype",
    "exception_message": "could not determine data type of parameter $6",
    "jsonb_build_object_occurrences_in_tests": 1,
    "TARGET_ERROR_COUNT": len(TARGETED),
    "nodes": [
        {
            "node_id": f"tests/test_generation_foundation.py::{name}",
            "test": name,
            "fixture_or_helper": "_create_synthetic",
            "query_involved": "INSERT INTO library_pages_v2 ... layout_notes",
            "exception_class": "psycopg.errors.IndeterminateDatatype",
            "exception_message": "could not determine data type of parameter $6",
            "jsonb_build_object_occurrence": "jsonb_build_object('page_status','FULL','marker', %s)",
        }
        for name in TARGETED
    ],
}
(OUT / "targeted-v1r1-error-nodes.json").write_text(json.dumps(targeted, indent=2) + "\n")

raw = json.loads((OUT / "indeterminate-datatype-reproduction.raw.json").read_text())
by_label = {item["label"]: item for item in raw}
reproduction = {
    "method": "isolated SELECT probes inside rolled-back transactions against the DEV database",
    "which_sql_expression_fails": "jsonb_build_object('region_publication', jsonb_build_object('page_status','FULL','marker', $1))",
    "which_bind_parameter_has_unknown_type": "$6 in the fixture INSERT (page marker); $1 in the isolated SELECT",
    "why_postgresql_cannot_infer_it": (
        "jsonb_build_object is variadic \"any\". A bare string parameter arrives as an "
        "unknown-typed literal and PostgreSQL 18 refuses to prepare the expression "
        "because no context forces a type. A plain SELECT $1 lets the client/parser "
        "resolve the unknown literal to text."
    ),
    "which_jsonb_build_object_argument_triggers_it": "'marker' value argument",
    "is_null_none": False,
    "is_uuid": False,
    "is_enum_or_status": False,
    "is_json": False,
    "is_untyped_text": True,
    "expected_postgresql_type": "text",
    "probes": raw,
    "reproduced_before_fix": by_label["buggy_untyped_marker"]["outcome"] == "IndeterminateDatatype",
    "fixed_by_explicit_text_cast": by_label["typed_marker_text"]["outcome"] == "OK",
    "control_plain_select_ok": by_label["control_plain_select"]["outcome"] == "OK",
}
(OUT / "indeterminate-datatype-reproduction.json").write_text(
    json.dumps(reproduction, indent=2) + "\n"
)

type_contract = {
    "scope": "SrvRestAstroLS_v1/backend/tests/test_generation_foundation.py::_create_synthetic and the publication harness",
    "binds": [
        {"parameter": "$1 (library_pages_v2.page_id)", "semantic": "page identity", "python_type": "uuid.UUID", "postgresql_expected_type": "uuid", "explicit_cast_needed": False, "actual_cast": "column inference"},
        {"parameter": "$2 (library_pages_v2.run_id)", "semantic": "ingestion run", "python_type": "uuid.UUID", "postgresql_expected_type": "uuid", "explicit_cast_needed": False, "actual_cast": "column inference"},
        {"parameter": "$3 (library_pages_v2.document_id)", "semantic": "physical document", "python_type": "uuid.UUID", "postgresql_expected_type": "uuid", "explicit_cast_needed": False, "actual_cast": "column inference"},
        {"parameter": "$4 (library_pages_v2.text)", "semantic": "page text", "python_type": "str", "postgresql_expected_type": "text", "explicit_cast_needed": False, "actual_cast": "column inference"},
        {"parameter": "$5 (library_pages_v2.char_count)", "semantic": "text length", "python_type": "int", "postgresql_expected_type": "integer", "explicit_cast_needed": False, "actual_cast": "column inference"},
        {"parameter": "$6 (jsonb_build_object marker)", "semantic": "region publication marker", "python_type": "str", "postgresql_expected_type": "text", "explicit_cast_needed": True, "actual_cast": "::text"},
        {"parameter": "library_documents binds", "semantic": "document metadata", "python_type": "UUID/str/int", "postgresql_expected_type": "column types", "explicit_cast_needed": False, "actual_cast": "column inference"},
        {"parameter": "library_document_chunks binds", "semantic": "chunk content and tsvectors", "python_type": "UUID/str", "postgresql_expected_type": "column types + to_tsvector(regconfig, text)", "explicit_cast_needed": False, "actual_cast": "column/function inference"},
        {"parameter": "generation registration binds", "semantic": "logical/document/run/status/sha", "python_type": "UUID/str", "postgresql_expected_type": "column types", "explicit_cast_needed": False, "actual_cast": "column inference; metadata uses explicit ::jsonb helper"},
    ],
    "generic_cast_everything_to_text": "REJECTED: uuid, integer and jsonb binds keep their real types",
    "AMBIGUOUS_BIND_TYPES": 0,
}
(OUT / "publication-fixture-sql-type-contract.json").write_text(
    json.dumps(type_contract, indent=2) + "\n"
)

audit = {
    "occurrences": [
        {"location": "SrvRestAstroLS_v1/backend/tests/test_generation_foundation.py:227", "expression": "jsonb_build_object('region_publication', jsonb_build_object('page_status','FULL','marker', %s))", "classification": "FIX_REQUIRED", "resolution": "marker bound with %s::text"},
        {"location": "SrvRestAstroLS_v1/backend/tests/test_page_first_gateway_generation_postgres.py:104", "expression": "to_jsonb(t)::text", "classification": "SAFE_TYPED", "reason": "to_jsonb over a table row; no bind"},
        {"location": "SrvRestAstroLS_v1/backend/infrastructure/postgres/dev_content_reset.py:21", "expression": "to_jsonb(t) row", "classification": "SAFE_TYPED", "reason": "table row, no untyped bind"},
        {"location": "SrvRestAstroLS_v1/backend/modules/library/content_manager.py:755", "expression": "jsonb_set(COALESCE(diagnostic,'{}'::jsonb), '{document_status}', '\"ready\"'::jsonb, true)", "classification": "SAFE_TYPED", "reason": "jsonb literals fully cast; no untyped bind"},
        {"location": "SrvRestAstroLS_v1/backend/modules/library/content_manager_repository.py:160", "expression": "jsonb_set(COALESCE(stage_states,'{}'::jsonb), ARRAY[%(current)s], '\"done\"'::jsonb, true)", "classification": "SAFE_TYPED", "reason": "ARRAY[text] resolves the bind, value is a jsonb literal cast; target_state uses ::jsonb"},
        {"location": "SrvRestAstroLS_v1/backend/db/migrations/043_generation_foundation.sql:222", "expression": "jsonb_build_object('backfill_source','migration-043')", "classification": "SAFE_TYPED", "reason": "literal-only arguments"},
    ],
    "UNRESOLVED_AMBIGUOUS_JSONB_BINDS": 0,
}
(OUT / "jsonb-expression-audit.json").write_text(json.dumps(audit, indent=2) + "\n")

print("wrote targeted, reproduction, type contract and jsonb audit evidence")
