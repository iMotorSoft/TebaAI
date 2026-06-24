#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# astro-dev.sh - TebaAI Astro development launcher
#
# Development only. Production serving must be configured separately.
# ---------------------------------------------------------------------------
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ASTRO_DIR="$SCRIPT_DIR/astro"
ASTRO_HOST="${TEBAAI_ASTRO_HOST:-127.0.0.1}"
ASTRO_PORT="${TEBAAI_ASTRO_PORT:-3008}"

# ---- Logging ---------------------------------------------------------------

_log() { printf '[astro-dev] %s\n' "$*"; }
_warn() { printf '  [warn] %s\n' "$*"; }
_fail() { printf '  [fail] %s\n' "$*" >&2; }

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

for command_name in corepack ss grep sed sort ps kill sleep; do
  _require_command "$command_name"
done

if [[ ! -d "$ASTRO_DIR" ]]; then
  _die "Astro directory not found at $ASTRO_DIR"
fi

if [[ ! -f "$ASTRO_DIR/package.json" ]]; then
  _die "package.json not found at $ASTRO_DIR/package.json"
fi

# ---- Port helpers ----------------------------------------------------------

_port_listener_lines() {
  ss -H -ltnp "sport = :${ASTRO_PORT}" 2>/dev/null || true
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
    _log "Remaining listeners on port ${ASTRO_PORT}:"
    printf '%s\n' "$listeners" >&2
  fi
}

# ---- Safely release Astro port --------------------------------------------

_free_astro_port() {
  if ! _port_is_in_use; then
    _log "Port ${ASTRO_PORT} is free."
    return 0
  fi

  local pids=()
  local pid
  local cmd

  mapfile -t pids < <(_listener_pids)

  if [[ "${#pids[@]}" -eq 0 ]]; then
    _show_remaining_listeners
    _die "port ${ASTRO_PORT} is occupied, but its listener PID could not be identified safely"
  fi

  _log "Port ${ASTRO_PORT} is occupied."

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
      _log "Port ${ASTRO_PORT} freed gracefully."
      return 0
    fi

    sleep 1
    waited=$((waited + 1))
  done

  _warn "Graceful stop did not release port ${ASTRO_PORT} after 10 seconds."

  mapfile -t pids < <(_listener_pids)

  if [[ "${#pids[@]}" -eq 0 ]]; then
    _show_remaining_listeners
    _die "port ${ASTRO_PORT} remains occupied, but its listener PID cannot be identified safely"
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
    _die "could not free port ${ASTRO_PORT}"
  fi

  _log "Port ${ASTRO_PORT} freed with SIGKILL."
}

_free_astro_port

# ---- Start Astro -----------------------------------------------------------

_log "TebaAI Astro development launcher"
_log "Astro directory: $ASTRO_DIR"
_log "Listening: http://${ASTRO_HOST}:${ASTRO_PORT}"
printf '\n'

cd "$ASTRO_DIR"
exec corepack pnpm exec astro dev \
  --host "$ASTRO_HOST" \
  --port "$ASTRO_PORT"
