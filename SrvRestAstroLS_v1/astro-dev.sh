#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# astro-dev.sh - TebaAI Astro development launcher
#
# Usage:
#   ./SrvRestAstroLS_v1/astro-dev.sh [start|stop|restart|status]
#
# Development only. Production serving must be configured separately.
# ---------------------------------------------------------------------------
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ASTRO_DIR="$SCRIPT_DIR/astro"
ASTRO_HOST="${TEBAAI_ASTRO_HOST:-127.0.0.1}"
ASTRO_PORT="${TEBAAI_ASTRO_PORT:-3008}"
ACTION="${1:-start}"

# ---- Logging ---------------------------------------------------------------

_log() { printf '[astro-dev] %s\n' "$*"; }
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

PID_DIR="$SCRIPT_DIR/.dev-pids"
LOG_DIR="$SCRIPT_DIR/.dev-logs"
PID_FILE="$PID_DIR/tebaai-astro-${ASTRO_PORT}.pid"
LOG_FILE="$LOG_DIR/astro-${ASTRO_PORT}.log"
ASTRO_BIN="$ASTRO_DIR/node_modules/.bin/astro"

if [[ ! -d "$ASTRO_DIR" ]]; then
  _die "Astro directory not found at $ASTRO_DIR"
fi

if [[ ! -f "$ASTRO_DIR/package.json" ]]; then
  _die "package.json not found at $ASTRO_DIR/package.json"
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

_is_expected_astro_command() {
  local cmd="$1"

  [[ "$cmd" == *"astro"* ]] \
    && [[ "$cmd" == *"$ASTRO_DIR"* ]] \
    && [[ "$cmd" == *"dev"* ]] \
    && [[ "$cmd" == *"--port ${ASTRO_PORT}"* ]]
}

_port_listener_lines() {
  ss -H -ltnp "sport = :${ASTRO_PORT}" 2>/dev/null || true
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
    _log "Listeners on port ${ASTRO_PORT}:"
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
    _warn "Removing stale PID file for stopped Astro PID ${pid}."
    rm -f "$PID_FILE"
    return 0
  fi

  local cmd
  cmd="$(_pid_command "$pid")"

  if ! _is_expected_astro_command "$cmd"; then
    _die "PID file points to a non-Astro process. PID ${pid}: ${cmd:-unknown}. Refusing to continue."
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
      _die "port ${ASTRO_PORT} is occupied, but no listener PID could be identified safely"
    fi

    return 0
  fi

  for pid in "${listener_pids[@]}"; do
    cmd="$(_pid_command "$pid")"

    if ! _is_expected_astro_command "$cmd"; then
      _show_listeners
      _die "port ${ASTRO_PORT} is occupied by an unknown process. PID ${pid}: ${cmd:-unknown}. Stop it manually or choose an explicit local override."
    fi
  done

  pid="${listener_pids[0]}"
  printf '%s\n' "$pid" >"$PID_FILE"
  _log "Astro already appears to be running on port ${ASTRO_PORT}."
  _log "PID file: $PID_FILE"
  _log "PID ${pid}: $(_pid_command "$pid")"
  exit 0
}

_stop_validated_pid() {
  local pid="$1"
  local cmd
  cmd="$(_pid_command "$pid")"

  if ! _is_expected_astro_command "$cmd"; then
    _die "Refusing to stop PID ${pid}; command does not match TebaAI Astro: ${cmd:-unknown}"
  fi

  _log "Stopping Astro PID ${pid}: ${cmd}"
  kill -TERM "$pid" 2>/dev/null || true

  local waited=0

  while [[ "$waited" -lt 10 ]]; do
    if ! _pid_is_alive "$pid"; then
      rm -f "$PID_FILE"
      _log "Astro stopped."
      return 0
    fi

    sleep 1
    waited=$((waited + 1))
  done

  _warn "Astro PID ${pid} did not stop after 10 seconds; sending SIGKILL."
  kill -KILL "$pid" 2>/dev/null || true
  sleep 1

  if _pid_is_alive "$pid"; then
    _die "could not stop Astro PID ${pid}"
  fi

  rm -f "$PID_FILE"
  _log "Astro stopped with SIGKILL."
}

# ---- Actions ---------------------------------------------------------------

_start() {
  _prepare_runtime_dirs
  _cleanup_stale_pid_file

  local pid
  local cmd

  if pid="$(_read_pid_file)"; then
    cmd="$(_pid_command "$pid")"
    _log "Astro already running."
    _log "PID file: $PID_FILE"
    _log "PID ${pid}: ${cmd}"
    _log "URL: http://${ASTRO_HOST}:${ASTRO_PORT}"
    return 0
  fi

  _ensure_port_available_or_owned

  if [[ ! -x "$ASTRO_BIN" ]]; then
    _log "ERROR: Astro executable not found or not executable at:"
    _log "       ${ASTRO_BIN}"
    _log "Prepare the frontend environment with:"
    _log "       cd \"$ASTRO_DIR\" && corepack pnpm install"
    exit 1
  fi

  {
    printf '\n[%s] Starting TebaAI Astro on %s:%s\n' "$(date -Is)" "$ASTRO_HOST" "$ASTRO_PORT"
  } >>"$LOG_FILE"

  (
    cd "$ASTRO_DIR"
    nohup "$ASTRO_BIN" dev \
      --host "$ASTRO_HOST" \
      --port "$ASTRO_PORT" \
      >>"$LOG_FILE" 2>&1 &
    printf '%s\n' "$!" >"$PID_FILE"
  )

  sleep 1

  pid="$(_read_pid_file)"

  if ! _pid_is_alive "$pid"; then
    rm -f "$PID_FILE"
    _warn "Astro process exited during startup. Last log lines:"
    tail -n 20 "$LOG_FILE" || true
    exit 1
  fi

  cmd="$(_pid_command "$pid")"

  if ! _is_expected_astro_command "$cmd"; then
    _die "Astro started with unexpected command. PID ${pid}: ${cmd:-unknown}"
  fi

  _log "Started TebaAI Astro."
  _log "PID file: $PID_FILE"
  _log "Log file: $LOG_FILE"
  _log "URL: http://${ASTRO_HOST}:${ASTRO_PORT}"
}

_stop() {
  local pid

  if ! pid="$(_read_pid_file)"; then
    if [[ -f "$PID_FILE" ]]; then
      _warn "Astro PID file is invalid; removing it."
      rm -f "$PID_FILE"
      return 0
    fi

    _log "No Astro PID file found at $PID_FILE."
    _show_listeners
    return 0
  fi

  if ! _pid_is_alive "$pid"; then
    _warn "Astro PID ${pid} is not running; removing stale PID file."
    rm -f "$PID_FILE"
    return 0
  fi

  _stop_validated_pid "$pid"
}

_status() {
  _log "Astro status"
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

      if _is_expected_astro_command "$cmd"; then
        _log "PID validation: expected Astro command"
      else
        _warn "PID validation: command does not match expected Astro"
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
      _warn "Port ${ASTRO_PORT}: listening, but PID is unavailable"
      _show_listeners
    else
      _log "Port ${ASTRO_PORT}: free"
    fi
    return 0
  fi

  _log "Port ${ASTRO_PORT}: listening"

  for pid in "${listener_pids[@]}"; do
    cmd="$(_pid_command "$pid")"
    _log "Listener PID ${pid}: ${cmd:-unknown}"

    if [[ -n "$file_pid" && "$pid" != "$file_pid" ]]; then
      _warn "Mismatch: listener PID ${pid} differs from PID file ${file_pid}"
    fi

    if _is_expected_astro_command "$cmd"; then
      _log "Listener validation: expected Astro command"
    else
      _warn "Listener validation: unknown process on Astro port"
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
