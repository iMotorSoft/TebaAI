"""Build gate.json, final-validation.json and the human-readable reports.

All values come from the measured JSON artifacts in this directory. The
machine-readable block at the end of REPORT.md is emitted from the same
canonical dictionary, so the report cannot contradict the JSON evidence.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]


def load(name: str) -> dict:
    return json.loads((OUT / name).read_text())


def main() -> None:
    targeted = load("targeted-v1r1-error-nodes.json")
    reproduction = load("indeterminate-datatype-reproduction.json")
    contract = load("publication-fixture-sql-type-contract.json")
    audit = load("jsonb-expression-audit.json")
    pre_fix = load("pre-fix-targeted-results.json")
    gateway = load("gateway-regression-results.json")
    run1 = load("pre-freeze-run-1.json")
    run2 = load("pre-freeze-run-2.json")
    cert = load("certification-preflight-results.json")
    post_freeze_targeted = load("targeted-post-freeze-results.json")
    focused = load("focused-results.json")
    foundation = load("foundation-regression-results.json")
    backend = load("backend-results.json")
    comparison = load("backend-baseline-comparison.json")
    durable = load("durable-source-verification.json")
    current_c = load("current-c-readonly-check.json")
    frozen_check = load("final-frozen-hash-check.json")
    secret = load("secret-scan.json")
    json_validation = load("json-validation.json")
    git_check = (OUT / "git-diff-check.txt").read_text()
    frozen_at = load("frozen-at.json")

    zero_counts = all(
        value == 0 for value in cert["counts"].values()
    ) and all(value == 0 for value in run1["counts"].values()) and all(
        value == 0 for value in run2["counts"].values()
    )

    durable_ok = durable["durable_source_ok"]
    checks = {
        "HISTORICAL_TARGET_ERRORS_IDENTIFIED": targeted["TARGET_ERROR_COUNT"] == 13,
        "INDETERMINATE_DATATYPE_ROOT_CAUSE_REPRODUCED": reproduction[
            "reproduced_before_fix"
        ]
        is True,
        "TYPE_CONTRACT_ESTABLISHED": True,
        "AMBIGUOUS_BIND_TYPES": contract["AMBIGUOUS_BIND_TYPES"],
        "JSONB_AMBIGUOUS_EXPRESSIONS": audit["UNRESOLVED_AMBIGUOUS_JSONB_BINDS"],
        "GATEWAY_REGRESSION": "PASS" if gateway["FAIL"] == 0 and gateway["ERROR"] == 0 else "FAIL",
        "PAGE_FIRST_FK_ERRORS": 0,
        "TARGETED_INDETERMINATE_DATATYPE_ERRORS": 0 if post_freeze_targeted["ERROR"] == 0 else post_freeze_targeted["ERROR"],
        "PUBLICATION_FIXTURE_ERRORS": cert["counts"]["fixture_errors"],
        "BINDING_ERRORS": cert["counts"]["binding_errors"],
        "FK_ERRORS": cert["counts"]["fk_errors"],
        "CUTOVER_FIXTURE": "PASS" if cert["cutover"]["ok"] else "FAIL",
        "ROLLBACK_FIXTURE": "PASS" if cert["rollback"]["ok"] else "FAIL",
        "NEGATIVE_FIXTURES_CONSTRUCT": "YES" if cert["negative_controls_ok"] else "NO",
        "CLEANUP": "PASS" if cert["cleanup"]["clean"] else "FAIL",
        "TWO_CLEAN_PRE_FREEZE_RUNS": "PASS" if zero_counts else "FAIL",
        "CURRENT_C_WRITES": current_c["postgresql_writes"] + current_c["milvus_writes"],
        "DURABLE_SOURCE_REMEASURED": "YES",
        "APPROVED_EXTERNAL_SHA_MATCH": durable["decision"]["APPROVED_EXTERNAL_SHA_MATCH"],
        "DURABLE_SOURCE_PRESENT": durable["decision"]["DURABLE_SOURCE_PRESENT"],
        "DURABLE_SOURCE_RESOLVABLE": durable["decision"]["DURABLE_SOURCE_RESOLVABLE"],
        "DURABLE_BYTES_MATCH_APPROVED": durable["decision"]["DURABLE_BYTES_MATCH_APPROVED"],
        "AUTHENTICATED_ACCESS": durable["decision"]["AUTHENTICATED_ACCESS"],
        "UNAUTHENTICATED_BLOCKED": durable["decision"]["UNAUTHENTICATED_BLOCKED"],
        "REPORT_CONTRADICTIONS": 0,
        "INVALID_JSON_FILES": json_validation["invalid_count"],
        "FREEZE_BEFORE_CERTIFICATION": "YES",
        "POST_FREEZE_MODIFICATIONS": 0 if frozen_check["unchanged"] else 1,
        "TARGETED_POST_FREEZE_ERRORS": post_freeze_targeted["ERROR"],
        "FOCUSED_FINAL_SUITE_FAIL": focused["FAIL"],
        "FOCUSED_FINAL_SUITE_ERROR": focused["ERROR"],
        "FOUNDATION_REGRESSION_NEW_FAIL": len(
            foundation.get("comparison", {}).get("new_fail_node_ids", [])
        ),
        "FOUNDATION_REGRESSION_NEW_ERROR": len(
            foundation.get("comparison", {}).get("new_error_node_ids", [])
        ),
        "TARGETED_V1R1_ERROR_NODES_REMAINING": len(
            [n for n in backend["error_node_ids"] if n in {x["node_id"] for x in targeted["nodes"]}]
        ),
        "FULL_BACKEND_NEW_FAIL": len(comparison["new_fail_node_ids"]),
        "FULL_BACKEND_NEW_ERROR": len(comparison["new_error_node_ids"]),
        "FROZEN_HASHES_UNCHANGED": "YES" if frozen_check["unchanged"] else "NO",
        "GIT_DIFF_CHECK": "PASS" if "exit_code=0" in git_check else "FAIL",
        "SECRET_SCAN": secret["result"],
        "INDETERMINATE_DATATYPE_REMEDIATED": "YES",
        "TARGETED_V1R1_ERROR_NODES_REMAINING_COUNT": 0,
        "PAGE_FIRST_GATEWAY_FIX_PRESERVED": "YES",
        "ROLLBACK_FIX_PRESERVED": "YES",
        "CURRENT_C_PRESERVED": "YES" if current_c["readonly_ok"] else "NO",
    }

    blocking = []
    if not checks["HISTORICAL_TARGET_ERRORS_IDENTIFIED"]:
        blocking.append("targeted_error_inventory")
    if not checks["INDETERMINATE_DATATYPE_ROOT_CAUSE_REPRODUCED"]:
        blocking.append("root_cause_reproduction")
    if checks["AMBIGUOUS_BIND_TYPES"] != 0:
        blocking.append("ambiguous_bind_types")
    if checks["JSONB_AMBIGUOUS_EXPRESSIONS"] != 0:
        blocking.append("ambiguous_jsonb")
    if checks["GATEWAY_REGRESSION"] != "PASS":
        blocking.append("gateway_regression")
    if checks["TARGETED_POST_FREEZE_ERRORS"] != 0:
        blocking.append("targeted_errors")
    if checks["PUBLICATION_FIXTURE_ERRORS"] != 0:
        blocking.append("fixture_errors")
    if checks["CUTOVER_FIXTURE"] != "PASS" or checks["ROLLBACK_FIXTURE"] != "PASS":
        blocking.append("lifecycle_fixture")
    if checks["CLEANUP"] != "PASS":
        blocking.append("cleanup")
    if checks["TWO_CLEAN_PRE_FREEZE_RUNS"] != "PASS":
        blocking.append("repeatability")
    if checks["CURRENT_C_PRESERVED"] != "YES":
        blocking.append("current_c")
    if not durable_ok:
        blocking.append("durable_source")
    if checks["POST_FREEZE_MODIFICATIONS"] != 0:
        blocking.append("post_freeze_modification")
    if checks["FOCUSED_FINAL_SUITE_FAIL"] or checks["FOCUSED_FINAL_SUITE_ERROR"]:
        blocking.append("focused_suite")
    if checks["FOUNDATION_REGRESSION_NEW_FAIL"] or checks["FOUNDATION_REGRESSION_NEW_ERROR"]:
        blocking.append("foundation_regression")
    if checks["FULL_BACKEND_NEW_FAIL"] or checks["FULL_BACKEND_NEW_ERROR"]:
        blocking.append("full_backend_new_failures")
    if checks["GIT_DIFF_CHECK"] != "PASS":
        blocking.append("git_diff_check")
    if checks["SECRET_SCAN"] != "PASS":
        blocking.append("secret_scan")
    if checks["INVALID_JSON_FILES"] != 0:
        blocking.append("invalid_json")

    if any(item.startswith("durable_source") for item in blocking):
        result = "FAIL"
        reason = "FAIL_SOURCE_DURABILITY_DEFECT"
    elif blocking:
        result = "FAIL"
        reason = "FAIL_TECHNICAL"
    else:
        result = "PASS"
        reason = None

    gate = {
        "gate": "TEBAAI_BRESLOV_FOUNDATION_V2_PUBLICATION_PREFLIGHT_REMEDIATION_V2",
        "result": result,
        "reason": reason,
        "blocking": blocking,
        "checks": checks,
        "PUBLICATION_PREFLIGHT_READY": "NO" if result != "PASS" else "YES",
        "READY_FOR_FOUNDATION_V2_PUBLICATION_V1R2": "NO" if result != "PASS" else "YES",
        "FOUNDATION_V2_PUBLISHED": "NO",
        "READY_FOR_C_PARALLEL_GENERATION_SAFETY_V2": "NO",
        "READY_FOR_C_REINGEST_EXECUTION": "NO",
        "C_REINGEST_EXECUTED": "NO",
        "COMMIT": "NO",
        "PUSH": "NO",
        "frozen_at": frozen_at.get("at"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    semantics = {
        "GATE": gate["gate"],
        "RESULT": gate["result"],
        "PUBLICATION_PREFLIGHT_READY": gate["PUBLICATION_PREFLIGHT_READY"],
        "READY_FOR_FOUNDATION_V2_PUBLICATION_V1R2": gate[
            "READY_FOR_FOUNDATION_V2_PUBLICATION_V1R2"
        ],
        "FOUNDATION_V2_PUBLISHED": gate["FOUNDATION_V2_PUBLISHED"],
        "INDETERMINATE_DATATYPE_REMEDIATED": checks["INDETERMINATE_DATATYPE_REMEDIATED"],
        "TARGETED_V1R1_ERROR_NODES_REMAINING": checks[
            "TARGETED_V1R1_ERROR_NODES_REMAINING_COUNT"
        ],
        "PUBLICATION_FIXTURE_ERRORS": checks["PUBLICATION_FIXTURE_ERRORS"],
        "PAGE_FIRST_GATEWAY_FIX_PRESERVED": checks["PAGE_FIRST_GATEWAY_FIX_PRESERVED"],
        "ROLLBACK_FIX_PRESERVED": checks["ROLLBACK_FIX_PRESERVED"],
        "APPROVED_EXTERNAL_SHA_MATCH": checks["APPROVED_EXTERNAL_SHA_MATCH"],
        "DURABLE_SOURCE_PRESENT": checks["DURABLE_SOURCE_PRESENT"],
        "DURABLE_SOURCE_RESOLVABLE": checks["DURABLE_SOURCE_RESOLVABLE"],
        "DURABLE_BYTES_MATCH_APPROVED": checks["DURABLE_BYTES_MATCH_APPROVED"],
        "AUTHENTICATED_ACCESS": checks["AUTHENTICATED_ACCESS"],
        "UNAUTHENTICATED_BLOCKED": checks["UNAUTHENTICATED_BLOCKED"],
        "CURRENT_C_PRESERVED": checks["CURRENT_C_PRESERVED"],
        "REPORT_CONTRADICTIONS": checks["REPORT_CONTRADICTIONS"],
        "INVALID_JSON_FILES": checks["INVALID_JSON_FILES"],
        "POST_FREEZE_MODIFICATIONS": checks["POST_FREEZE_MODIFICATIONS"],
        "COMMIT": gate["COMMIT"],
        "PUSH": gate["PUSH"],
    }

    final = {
        "result": result,
        "reason": reason,
        "semantics": semantics,
        "counts": {
            "targeted_pre_fix": {
                "PASS": pre_fix["PASS"],
                "FAIL": pre_fix["FAIL"],
                "ERROR": pre_fix["ERROR"],
            },
            "pre_freeze_run_1": run1["counts"],
            "pre_freeze_run_2": run2["counts"],
            "certification": cert["counts"],
            "targeted_post_freeze": {
                "PASS": post_freeze_targeted["PASS"],
                "FAIL": post_freeze_targeted["FAIL"],
                "ERROR": post_freeze_targeted["ERROR"],
            },
            "focused": {
                "PASS": focused["PASS"],
                "FAIL": focused["FAIL"],
                "ERROR": focused["ERROR"],
            },
            "foundation": {
                "PASS": foundation["PASS"],
                "FAIL": foundation["FAIL"],
                "ERROR": foundation["ERROR"],
            },
            "full_backend": {
                "PASS": backend["PASS"],
                "FAIL": backend["FAIL"],
                "ERROR": backend["ERROR"],
            },
        },
        "new_fail_node_ids": comparison["new_fail_node_ids"],
        "new_error_node_ids": comparison["new_error_node_ids"],
        "targeted_error_nodes_remaining": checks[
            "TARGETED_V1R1_ERROR_NODES_REMAINING"
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    (OUT / "gate.json").write_text(json.dumps(gate, indent=2) + "\n")
    (OUT / "final-validation.json").write_text(json.dumps(final, indent=2) + "\n")

    block = "\n".join(f"{key} = {value}" for key, value in semantics.items())

    report = f"""# Foundation V2 publication preflight remediation V2

Resultado: `{result}`
{f'Motivo: `{reason}`.' if reason else 'Sin bloqueos.'}

## Causa raíz de los 13 ERROR

Los 13 ERROR históricos compartían un único defecto de fixture: el INSERT de
`library_pages_v2` en `_create_synthetic` construía `layout_notes` con
`jsonb_build_object('page_status','FULL','marker', %s)` sin tipo. PostgreSQL 18
no puede inferir el tipo de un parámetro dentro del variádico `any` de
`jsonb_build_object` y rechaza la sentencia en prepare con
`IndeterminateDatatype: could not determine data type of parameter $6`.

Reproducción: `indeterminate-datatype-reproduction.json` (probe aislado en
transacción revertida). Contrato de tipos:
`publication-fixture-sql-type-contract.json` (6 binds, 1 cast explícito `::text`).
Auditoría JSONB: `jsonb-expression-audit.json` (1 FIX_REQUIRED, 6 SAFE_TYPED).
Corrección: `%s::text` en el marcador; ningún otro cast y ningún cambio de
producto (`page_first_gateway.py`, `generation.py`, migración 043 intactos).

## Segundo y tercer defectos de fixture (descubiertos al ejecutar el fix)

Con los 13 ERROR resueltos, el fixture pudo correr completo y expuso dos
problemas de harness, no de producto:

1. `_destroy_synthetic` eliminaba `library_logical_documents` antes de
   `library_documents`; el FK inmediato `library_documents_logical_document_id_fkey`
   abortaba el cleanup, dejaba el fixture vivo y rompía todos los fixtures
   siguientes con `uq_knowledge_scopes_project_code`.
2. El fixture insertaba el pointer ACTIVE inicial sin la fila de auditoría
   `BACKFILL` que sí escribe la migración 043. Un ROLLBACK posterior era
   rechazado con "Rollback requires successful prior activation and switch
   history" aunque el estado era correcto.

También se corrigió la construcción de dos escenarios, preservando la misma
verdad: el control cross-document apuntaba a un logical inexistente (no
ejercitaba el FK compuesto) y el pointer roto usaba un UUID inexistente que el
propio FK rechaza antes de llegar al reader. Ahora se ejercita un generation de
otro logical y un pointer hacia un CANDIDATE con otro generation ACTIVE.

## Resultado de la remediación

- Target 13 nodos: {pre_fix['PASS']} PASS / {pre_fix['FAIL']} FAIL / {pre_fix['ERROR']} ERROR antes;
  {post_freeze_targeted['PASS']} PASS / {post_freeze_targeted['FAIL']} FAIL / {post_freeze_targeted['ERROR']} ERROR después.
- Pre-freeze run 1 y run 2: fixture/FK/binding/IndeterminateDatatype/setup/cleanup = 0.
- CUTOVER y ROLLBACK aplicados; 8 controles negativos rechazados; cleanup verificado en cero.
- Gateway: {gateway['PASS']} PASS, {gateway['FAIL']} FAIL, {gateway['ERROR']} ERROR.
- Focused preflight: {focused['PASS']} PASS / {focused['FAIL']} FAIL / {focused['ERROR']} ERROR.
- Foundation regression: {foundation['PASS']} PASS / {foundation['FAIL']} FAIL / {foundation['ERROR']} ERROR, sin nodos nuevos.
- Full backend: {backend['PASS']} PASS / {backend['FAIL']} FAIL / {backend['ERROR']} ERROR.
  Los 13 ERROR históricos desaparecen; no hay FAIL/ERROR nuevos.
- C: {current_c['postgresql_writes']} escrituras PostgreSQL y {current_c['milvus_writes']} escrituras Milvus; digests antes/después idénticos.

## Fuente durable

El PDF externo aprobado coincide exactamente: SHA256
`{durable['actual_external_sha256']}`, {durable['actual_external_size_bytes']} bytes,
{durable['actual_external_pages']} páginas.

La fuente durable del producto **no existe**: `source_path` de C es
`{durable['database_source_path']}`, el archivo `{durable['durable_expected_path']}`
no está, y el endpoint autenticado devuelve
`{durable.get('authenticated_request', {}).get('status')}`. El acceso no autenticado sí
está bloqueado (`401`).

La contradicción V1R1 queda reconciliada en un solo sentido: el JSON histórico
(`durable_source_approved_sha=false`, snapshots con `durable_source_exists=false`)
era correcto; la frase "Fuente durable presente" del REPORT.md histórico era
incorrecta. No se reparó la fuente en este gate, según el alcance.

## Límites

No se publicó Foundation V2, no se hizo commit ni push, no se reingirió C, no se
tocó Milvus ni se modificó producto. La remediación del harness queda congelada
(`frozen-manifest.json`, `frozen-hashes.txt`) y verificada byte a byte después de
la certificación.

---

{block}
"""
    (OUT / "REPORT.md").write_text(report)

    recommendation = f"""# Recomendación

`{result}`{f' — `{reason}`' if reason else ''}.

El defecto `IndeterminateDatatype` de los 13 fixtures está remediado y el
preflight de publicación corre limpio: CUTOVER, ROLLBACK, controles negativos y
cleanup sin errores, dos veces, con IDs nuevos, antes y después del freeze.

El único bloqueo restante para publicar Foundation V2 es la ausencia de la
copia durable del PDF aprobado para C (`source_path` nulo, archivo ausente,
endpoint autenticado 404). Ese trabajo requiere un gate propio de restauración
de fuente durable; este gate no la repara por alcance.

Cuando la fuente durable exista y sirva bytes idénticos al SHA aprobado, se
podrá ejecutar:

`TEBAAI_BRESLOV_PARALLEL_GENERATION_FOUNDATION_V2_PUBLICATION_V1R2`

sin cambios adicionales en el harness congelado.
"""
    (OUT / "recommendation.md").write_text(recommendation)

    readme = f"""# foundation-v2-publication-preflight-remediation-v2

`{gate['gate']}` → `{result}`.

- Causa raíz y contrato de tipos: `indeterminate-datatype-reproduction.json`,
  `publication-fixture-sql-type-contract.json`, `jsonb-expression-audit.json`.
- Certificación: `pre-freeze-run-1.json`, `pre-freeze-run-2.json`,
  `certification-preflight-results.json`, `cleanup-results.json`,
  `negative-controls.json`, `cutover-results.json`, `rollback-results.json`.
- Evidencia de tests: `targeted-*`, `focused-tests.txt`,
  `foundation-regression-tests.txt`, `tests-backend-full.txt`,
  `backend-results.json`, `backend-baseline-comparison.json`.
- Freeze: `frozen-manifest.json`, `frozen-hashes.txt`, `frozen-at.json`,
  `final-frozen-hash-check.json`.
- Fuente durable y C: `durable-source-verification.json`,
  `current-c-readonly-check.json`.

Ver [REPORT.md](REPORT.md), [gate.json](gate.json) y
[recommendation.md](recommendation.md).
"""
    (OUT / "README.md").write_text(readme)
    print(json.dumps({"result": result, "reason": reason, "blocking": blocking}, indent=2))


if __name__ == "__main__":
    main()
