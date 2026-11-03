#!/usr/bin/env bash
# Read-only certification orchestrator. Run exactly once after freeze.py.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="${TEBAAI_CERT_REPO_ROOT:-$(cd "$SCRIPT_DIR/../../../.." && pwd)}"
PY="$REPO_ROOT/SrvRestAstroLS_v1/backend/.venv/bin/python"

export TEBAAI_CERT_OUT="$SCRIPT_DIR"
export TEBAAI_CERT_REPO_ROOT="$REPO_ROOT"

cd "$SCRIPT_DIR"

step() {
  echo "=== $* ==="
  "$@"
  echo "--- exit=$? ---"
}

# Tests run before the zero-write observation window. Their live-DB fixtures use
# isolated synthetic scopes or force-rollback transactions and never address C.
step "$PY" capture_state.py pre_tests current-c-pre-tests.json
step "$PY" run_tests.py

# Zero-write observation window starts here.
step "$PY" capture_state.py before current-c-before.json
step "$PY" capture_fs.py before filesystem-before.json
step "$PY" verify_approved_source.py
step "$PY" verify_durable_file.py
step "$PY" verify_source_metadata.py
step "$PY" verify_endpoint.py initial
step "$PY" viewer_source_smoke.py

# Fresh-process durability: restart only the DEV backend, never data services.
echo "=== fresh process restart ==="
"$REPO_ROOT/SrvRestAstroLS_v1/backend-dev.sh" restart
echo "--- restart exit=$? ---"
health=""
for _ in $(seq 1 60); do
  health="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:7008/health || true)"
  if [ "$health" = "200" ]; then
    break
  fi
  sleep 1
done
echo "--- health=$health ---"

step "$PY" verify_endpoint.py fresh
step "$PY" capture_state.py after current-c-after.json
step "$PY" capture_fs.py after filesystem-after.json
step "$PY" compare_state.py

# Closing checks and report generation.
step "$PY" frozen_hash_check.py
step "$PY" json_validate.py
step "$PY" secret_scan.py
step "$PY" git_diff_check.py
step "$PY" aggregate.py
step "$PY" final_checks.py

echo "=== certification run finished ==="
"$PY" -c "import json; g=json.load(open('gate.json')); print(g['status']); print(json.dumps(g['consistency_keys'], indent=2))"
