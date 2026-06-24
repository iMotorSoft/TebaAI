#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# backend-dev.sh - TebaAI backend development launcher
#
# Responsibilities:
# - Load optional local overrides.
# - Safely release the backend port.
# - Start the Litestar backend in the foreground.
#
# This script does NOT start, stop, restart, reconfigure or migrate:
# - PostgreSQL
# - Milvus
# - LiteLLM
# ---------------------------------------------------------------------------
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
BACKEND_HOST="${TEBAAI_BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${TEBAAI_BACKEND_PORT:-7008}"

# ---- Logging ---------------------------------------------------------------

_log() { printf '[backend-dev] %s\n' "$*"; }
_warn() { printf '  [warn] %s\n' "$*"; }

_die() {
  _log "ERROR: $*"
  exit 1
}

_on_error() {
  local exit_code=$?
  local line_number="${1:-unknown}"

  _log "ERROR: command failed at line ${line_number} with exit code ${exit_code}."
  exit "$exit_code"
}

trap '_on_error "$LINENO"' ERR

# ---- Required commands -----------------------------------------------------

_require_command() {
  local command_name="$1"

  if ! command -v "$command_name" >/dev/null 2>&1; then
    _die "required command not found: ${command_name}"
  fi
}

for command_name in ss grep sed sort ps kill sleep; do
  _require_command "$command_name"
done

# ---- Local overrides -------------------------------------------------------

LOCAL_ENV_FILE="$SCRIPT_DIR/.env.backend-dev.local"

if [[ -f "$LOCAL_ENV_FILE" ]]; then
  _log "Loading local overrides from .env.backend-dev.local"

  set -a
  # shellcheck disable=SC1090
  source "$LOCAL_ENV_FILE"
  set +a
fi

if [[ ! -d "$BACKEND_DIR" ]]; then
  _die "Backend directory not found at $BACKEND_DIR"
fi

if [[ ! -f "$BACKEND_DIR/ls_iMotorSoft_Srv01.py" ]]; then
  _die "Backend entrypoint not found at $BACKEND_DIR/ls_iMotorSoft_Srv01.py"
fi

# ---- Port helpers ----------------------------------------------------------

_port_listener_lines() {
  ss -H -ltnp "sport = :${BACKEND_PORT}" 2>/dev/null || true
}

_port_is_in_use() {
  [[ -n "$(_port_listener_lines)" ]]
}

_listener_pids() {
  _port_listener_lines \
    | grep -oE 'pid=[0-9]+' \
    | sed 's/^pid=//' \
    | sort -u
}

_show_remaining_listeners() {
  local listeners
  listeners="$(_port_listener_lines)"

  if [[ -n "$listeners" ]]; then
    _log "Remaining listeners on port ${BACKEND_PORT}:"
    printf '%s\n' "$listeners" >&2
  fi
}

# ---- Safely release backend port ------------------------------------------

_free_backend_port() {
  if ! _port_is_in_use; then
    _log "Port ${BACKEND_PORT} is free."
    return 0
  fi

  local pids=()
  local pid
  local cmd

  mapfile -t pids < <(_listener_pids)

  if [[ "${#pids[@]}" -eq 0 ]]; then
    _show_remaining_listeners
    _die "port ${BACKEND_PORT} is occupied, but its listener PID could not be identified safely"
  fi

  _log "Port ${BACKEND_PORT} is occupied."

  for pid in "${pids[@]}"; do
    cmd="$(ps -p "$pid" -o args= 2>/dev/null || true)"
    cmd="${cmd:-unknown}"

    _log "Listener PID ${pid}: ${cmd}"
  done

  for pid in "${pids[@]}"; do
    _log "Sending SIGTERM to PID ${pid}..."
    kill -TERM "$pid" 2>/dev/null || true
  done

  local waited=0

  while [[ "$waited" -lt 10 ]]; do
    if ! _port_is_in_use; then
      _log "Port ${BACKEND_PORT} freed gracefully."
      return 0
    fi

    sleep 1
    waited=$((waited + 1))
  done

  _warn "Graceful stop did not release port ${BACKEND_PORT} after 10 seconds."

  mapfile -t pids < <(_listener_pids)

  if [[ "${#pids[@]}" -eq 0 ]]; then
    _show_remaining_listeners
    _die "port ${BACKEND_PORT} remains occupied, but its listener PID cannot be identified safely"
  fi

  for pid in "${pids[@]}"; do
    cmd="$(ps -p "$pid" -o args= 2>/dev/null || true)"
    cmd="${cmd:-unknown}"

    _warn "Sending SIGKILL to PID ${pid}: ${cmd}"
    kill -KILL "$pid" 2>/dev/null || true
  done

  sleep 1

  if _port_is_in_use; then
    _show_remaining_listeners
    _die "could not free port ${BACKEND_PORT}"
  fi

  _log "Port ${BACKEND_PORT} freed with SIGKILL."
}

_free_backend_port

# ---- Validate backend environment -----------------------------------------

UVICORN="$BACKEND_DIR/.venv/bin/uvicorn"

if [[ ! -x "$UVICORN" ]]; then
  _log "ERROR: uvicorn not found or not executable at:"
  _log "       ${UVICORN}"
  _log "Prepare the backend environment with:"
  _log "       cd \"$BACKEND_DIR\" && uv sync"
  exit 1
fi

# ---- Configuration summary ------------------------------------------------

printf '\n'
_log "TebaAI backend development launcher"
_log "Application: ls_iMotorSoft_Srv01:app"
_log "Backend directory: $BACKEND_DIR"
_log "Listening: http://${BACKEND_HOST}:${BACKEND_PORT}"
printf '\n'

# ---- Start backend ---------------------------------------------------------

cd "$BACKEND_DIR"
exec "$UVICORN" ls_iMotorSoft_Srv01:app \
  --host "$BACKEND_HOST" \
  --port "$BACKEND_PORT"
