#!/usr/bin/env bash
# Safe DEV launcher for an explicitly scoped Content Manager worker.
set -Eeuo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
ACTION="${1:-start}"
PID_DIR="$SCRIPT_DIR/.dev-pids"
LOG_DIR="$SCRIPT_DIR/.dev-logs"
PID_FILE="$PID_DIR/tebaai-content-worker.pid"
LOG_FILE="$LOG_DIR/content-worker.log"
ENV_FILE="$SCRIPT_DIR/.env.backend-dev.local"
PYTHON="$BACKEND_DIR/.venv/bin/python"

# Explicit process environment overrides the unversioned local E2E file for a
# controlled primary golden run.
_explicit_primary_enabled="${TEBAAI_CONTENT_MANAGER_PRIMARY_INGESTION_ENABLED-}"
_explicit_worker_scope="${TEBAAI_CONTENT_MANAGER_WORKER_SCOPE-}"
_explicit_storage_dir="${TEBAAI_CONTENT_MANAGER_STORAGE_DIR-}"

_log(){ printf '[content-worker-dev] %s\n' "$*"; }
_die(){ _log "ERROR: $*"; exit 1; }
mkdir -p "$PID_DIR" "$LOG_DIR"
if [[ -f "$ENV_FILE" ]]; then set -a; source "$ENV_FILE"; set +a; fi
[[ -z "$_explicit_primary_enabled" ]] || export TEBAAI_CONTENT_MANAGER_PRIMARY_INGESTION_ENABLED="$_explicit_primary_enabled"
[[ -z "$_explicit_worker_scope" ]] || export TEBAAI_CONTENT_MANAGER_WORKER_SCOPE="$_explicit_worker_scope"
[[ -z "$_explicit_storage_dir" ]] || export TEBAAI_CONTENT_MANAGER_STORAGE_DIR="$_explicit_storage_dir"

_pid(){ [[ -f "$PID_FILE" ]] && read -r p <"$PID_FILE" && [[ "$p" =~ ^[0-9]+$ ]] && printf '%s' "$p"; }
_alive(){ kill -0 "$1" 2>/dev/null; }
_cmd(){ ps -p "$1" -o args= 2>/dev/null || true; }
_expected(){ [[ "$1" == *"$BACKEND_DIR/scripts/content_manager_worker.py"* ]]; }

status(){
  local p
  if p="$(_pid)" && _alive "$p" && _expected "$(_cmd "$p")"; then
    _log "active PID $p: $(_cmd "$p")"; return 0
  fi
  _log "inactive"; return 1
}
start(){
  local p
  if p="$(_pid)" && _alive "$p"; then
    _expected "$(_cmd "$p")" || _die "PID file points to an unrelated process"
    _log "already active PID $p"; return 0
  fi
  rm -f "$PID_FILE"
  local worker_scope="${TEBAAI_CONTENT_MANAGER_WORKER_SCOPE:-breslov_e2e}"
  if [[ "$worker_scope" == "breslov_e2e" ]]; then
    [[ "${TEBAAI_ENV:-development}" == "development" ]] || _die "worker is DEV-only"
    [[ "${TEBAAI_CONTENT_MANAGER_E2E_ENABLED:-false}" == "true" ]] || _die "explicit E2E enablement is required"
    [[ -n "${TEBAAI_CONTENT_MANAGER_E2E_FIXTURE_SHA256:-}" ]] || _die "authorized fixture hash is required"
  elif [[ "$worker_scope" == "breslov_primary" ]]; then
    [[ "${TEBAAI_CONTENT_MANAGER_PRIMARY_INGESTION_ENABLED:-false}" == "true" ]] || _die "explicit primary enablement is required"
    [[ -n "${TEBAAI_CONTENT_MANAGER_STORAGE_DIR:-}" ]] || _die "primary storage directory is required"
    [[ "${TEBAAI_CONTENT_MANAGER_STORAGE_DIR}" == /* ]] || _die "primary storage directory must be absolute"
  else
    _die "unsupported worker scope: $worker_scope"
  fi
  cd "$BACKEND_DIR"
  nohup "$PYTHON" "$BACKEND_DIR/scripts/content_manager_worker.py" >>"$LOG_FILE" 2>&1 &
  printf '%s\n' "$!" >"$PID_FILE"
  cd "$SCRIPT_DIR"
  sleep 1
  status || { tail -n 30 "$LOG_FILE"; _die "worker failed to start"; }
}
stop(){
  local p
  p="$(_pid)" || { rm -f "$PID_FILE"; _log "already inactive"; return 0; }
  _alive "$p" || { rm -f "$PID_FILE"; _log "removed stale PID"; return 0; }
  _expected "$(_cmd "$p")" || _die "refusing to stop unrelated PID $p"
  kill -TERM "$p"
  for _ in {1..10}; do _alive "$p" || { rm -f "$PID_FILE"; _log "stopped"; return 0; }; sleep 1; done
  _die "worker did not stop after SIGTERM"
}
case "$ACTION" in
  start) start;; stop) stop;; restart) stop; start;; status) status;; *) _die "usage: $0 [start|stop|restart|status]";;
esac
