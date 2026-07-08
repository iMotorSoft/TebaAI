#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# backend-dev.sh - TebaAI backend development launcher
#
# Usage:
#   ./SrvRestAstroLS_v1/backend-dev.sh [start|stop|restart|status]
#
# Responsibilities:
# - Load optional local overrides.
# - Start, stop and report only the TebaAI backend dev process.
# - Refuse to kill unknown processes that happen to use the backend port.
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
ACTION="${1:-start}"

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

for command_name in date grep kill mkdir ps rm sed sleep sort ss tail; do
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

PID_DIR="$SCRIPT_DIR/.dev-pids"
LOG_DIR="$SCRIPT_DIR/.dev-logs"
PID_FILE="$PID_DIR/tebaai-backend-${BACKEND_PORT}.pid"
LOG_FILE="$LOG_DIR/backend-${BACKEND_PORT}.log"
UVICORN="$BACKEND_DIR/.venv/bin/uvicorn"

if [[ ! -d "$BACKEND_DIR" ]]; then
  _die "Backend directory not found at $BACKEND_DIR"
fi

if [[ ! -f "$BACKEND_DIR/ls_iMotorSoft_Srv01.py" ]]; then
  _die "Backend entrypoint not found at $BACKEND_DIR/ls_iMotorSoft_Srv01.py"
fi

# ---- Process helpers -------------------------------------------------------

_prepare_runtime_dirs() {
  mkdir -p "$PID_DIR" "$LOG_DIR"
}

_read_pid_file() {
  if [[ -f "$PID_FILE" ]]; then
    local pid
    pid="$(<"$PID_FILE")"

    if [[ "$pid" =~ ^[0-9]+$ ]]; then
      printf '%s\n' "$pid"
      return 0
    fi
  fi

  return 1
}

_pid_is_alive() {
  local pid="$1"
  kill -0 "$pid" 2>/dev/null
}

_pid_command() {
  local pid="$1"
  ps -p "$pid" -o args= 2>/dev/null || true
}

_is_expected_backend_command() {
  local cmd="$1"

  [[ "$cmd" == *"uvicorn"* ]] \
    && [[ "$cmd" == *"$BACKEND_DIR"* ]] \
    && [[ "$cmd" == *"ls_iMotorSoft_Srv01:app"* ]] \
    && [[ "$cmd" == *"--port ${BACKEND_PORT}"* ]]
}

_port_listener_lines() {
  ss -H -ltnp "sport = :${BACKEND_PORT}" 2>/dev/null || true
}

_listener_pids() {
  local listeners
  listeners="$(_port_listener_lines)"

  if [[ -z "$listeners" ]]; then
    return 0
  fi

  printf '%s\n' "$listeners" \
    | grep -oE 'pid=[0-9]+' \
    | sed 's/^pid=//' \
    | sort -u \
    || true
}

_show_listeners() {
  local listeners
  listeners="$(_port_listener_lines)"

  if [[ -n "$listeners" ]]; then
    _log "Listeners on port ${BACKEND_PORT}:"
    printf '%s\n' "$listeners"
  fi
}

_cleanup_stale_pid_file() {
  local pid

  if ! pid="$(_read_pid_file)"; then
    if [[ -f "$PID_FILE" ]]; then
      _warn "Removing invalid PID file at $PID_FILE."
      rm -f "$PID_FILE"
    fi

    return 0
  fi

  if ! _pid_is_alive "$pid"; then
    _warn "Removing stale PID file for stopped backend PID ${pid}."
    rm -f "$PID_FILE"
    return 0
  fi

  local cmd
  cmd="$(_pid_command "$pid")"

  if ! _is_expected_backend_command "$cmd"; then
    _die "PID file points to a non-backend process. PID ${pid}: ${cmd:-unknown}. Refusing to continue."
  fi
}

_ensure_port_available_or_owned() {
  local listener_pids=()
  local pid
  local cmd

  mapfile -t listener_pids < <(_listener_pids)

  if [[ "${#listener_pids[@]}" -eq 0 ]]; then
    if [[ -n "$(_port_listener_lines)" ]]; then
      _show_listeners
      _die "port ${BACKEND_PORT} is occupied, but no listener PID could be identified safely"
    fi

    return 0
  fi

  for pid in "${listener_pids[@]}"; do
    cmd="$(_pid_command "$pid")"

    if ! _is_expected_backend_command "$cmd"; then
      _show_listeners
      _die "port ${BACKEND_PORT} is occupied by an unknown process. PID ${pid}: ${cmd:-unknown}. Stop it manually or choose an explicit local override."
    fi
  done

  pid="${listener_pids[0]}"
  printf '%s\n' "$pid" >"$PID_FILE"
  _log "Backend already appears to be running on port ${BACKEND_PORT}."
  _log "PID file: $PID_FILE"
  _log "PID ${pid}: $(_pid_command "$pid")"
  exit 0
}

_stop_validated_pid() {
  local pid="$1"
  local cmd
  cmd="$(_pid_command "$pid")"

  if ! _is_expected_backend_command "$cmd"; then
    _die "Refusing to stop PID ${pid}; command does not match TebaAI backend: ${cmd:-unknown}"
  fi

  _log "Stopping backend PID ${pid}: ${cmd}"
  kill -TERM "$pid" 2>/dev/null || true

  local waited=0

  while [[ "$waited" -lt 10 ]]; do
    if ! _pid_is_alive "$pid"; then
      rm -f "$PID_FILE"
      _log "Backend stopped."
      return 0
    fi

    sleep 1
    waited=$((waited + 1))
  done

  _warn "Backend PID ${pid} did not stop after 10 seconds; sending SIGKILL."
  kill -KILL "$pid" 2>/dev/null || true
  sleep 1

  if _pid_is_alive "$pid"; then
    _die "could not stop backend PID ${pid}"
  fi

  rm -f "$PID_FILE"
  _log "Backend stopped with SIGKILL."
}

# ---- Actions ---------------------------------------------------------------

_start() {
  _prepare_runtime_dirs
  _cleanup_stale_pid_file

  local pid
  local cmd

  if pid="$(_read_pid_file)"; then
    cmd="$(_pid_command "$pid")"
    _log "Backend already running."
    _log "PID file: $PID_FILE"
    _log "PID ${pid}: ${cmd}"
    _log "URL: http://${BACKEND_HOST}:${BACKEND_PORT}"
    return 0
  fi

  _ensure_port_available_or_owned

  if [[ ! -x "$UVICORN" ]]; then
    _log "ERROR: uvicorn not found or not executable at:"
    _log "       ${UVICORN}"
    _log "Prepare the backend environment with:"
    _log "       cd \"$BACKEND_DIR\" && uv sync"
    exit 1
  fi

  {
    printf '\n[%s] Starting TebaAI backend on %s:%s\n' "$(date -Is)" "$BACKEND_HOST" "$BACKEND_PORT"
  } >>"$LOG_FILE"

  (
    cd "$BACKEND_DIR"
    nohup "$UVICORN" ls_iMotorSoft_Srv01:app \
      --host "$BACKEND_HOST" \
      --port "$BACKEND_PORT" \
      >>"$LOG_FILE" 2>&1 &
    printf '%s\n' "$!" >"$PID_FILE"
  )

  sleep 1

  pid="$(_read_pid_file)"

  if ! _pid_is_alive "$pid"; then
    rm -f "$PID_FILE"
    _warn "Backend process exited during startup. Last log lines:"
    tail -n 20 "$LOG_FILE" || true
    exit 1
  fi

  cmd="$(_pid_command "$pid")"

  if ! _is_expected_backend_command "$cmd"; then
    _die "Backend started with unexpected command. PID ${pid}: ${cmd:-unknown}"
  fi

  _log "Started TebaAI backend."
  _log "PID file: $PID_FILE"
  _log "Log file: $LOG_FILE"
  _log "URL: http://${BACKEND_HOST}:${BACKEND_PORT}"
}

_stop() {
  local pid

  if ! pid="$(_read_pid_file)"; then
    if [[ -f "$PID_FILE" ]]; then
      _warn "Backend PID file is invalid; removing it."
      rm -f "$PID_FILE"
      return 0
    fi

    _log "No backend PID file found at $PID_FILE."
    _show_listeners
    return 0
  fi

  if ! _pid_is_alive "$pid"; then
    _warn "Backend PID ${pid} is not running; removing stale PID file."
    rm -f "$PID_FILE"
    return 0
  fi

  _stop_validated_pid "$pid"
}

_status() {
  _log "Backend status"
  _log "PID file: $PID_FILE"

  local file_pid=""
  local listener_pids=()
  local pid
  local cmd

  if file_pid="$(_read_pid_file)"; then
    if _pid_is_alive "$file_pid"; then
      cmd="$(_pid_command "$file_pid")"
      _log "PID file process: alive"
      _log "PID ${file_pid}: ${cmd:-unknown}"

      if _is_expected_backend_command "$cmd"; then
        _log "PID validation: expected backend command"
      else
        _warn "PID validation: command does not match expected backend"
      fi
    else
      _warn "PID file process is not alive: ${file_pid}"
    fi
  else
    if [[ -f "$PID_FILE" ]]; then
      _warn "PID file process: invalid PID file content"
    else
      _log "PID file process: none"
    fi
  fi

  mapfile -t listener_pids < <(_listener_pids)

  if [[ "${#listener_pids[@]}" -eq 0 ]]; then
    if [[ -n "$(_port_listener_lines)" ]]; then
      _warn "Port ${BACKEND_PORT}: listening, but PID is unavailable"
      _show_listeners
    else
      _log "Port ${BACKEND_PORT}: free"
    fi
    return 0
  fi

  _log "Port ${BACKEND_PORT}: listening"

  for pid in "${listener_pids[@]}"; do
    cmd="$(_pid_command "$pid")"
    _log "Listener PID ${pid}: ${cmd:-unknown}"

    if [[ -n "$file_pid" && "$pid" != "$file_pid" ]]; then
      _warn "Mismatch: listener PID ${pid} differs from PID file ${file_pid}"
    fi

    if _is_expected_backend_command "$cmd"; then
      _log "Listener validation: expected backend command"
    else
      _warn "Listener validation: unknown process on backend port"
    fi
  done
}

case "$ACTION" in
  start)
    _start
    ;;
  stop)
    _stop
    ;;
  restart)
    _stop
    _start
    ;;
  status)
    _status
    ;;
  *)
    _die "unknown action: ${ACTION}. Expected start, stop, restart or status."
    ;;
esac
