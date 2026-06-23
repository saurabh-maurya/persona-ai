#!/usr/bin/env bash
# =============================================================================
# Persona AI Studio — Linux Startup Script (no Docker)
#
# Usage:
#   ./start-linux.sh            — kill any existing instance, then start
#   ./start-linux.sh stop       — stop running instance
#   ./start-linux.sh restart    — stop + start
#   ./start-linux.sh status     — show process and API health
#   ./start-linux.sh logs       — tail the backend log
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
VENV_DIR="$BACKEND_DIR/.venv"
ENV_FILE="$SCRIPT_DIR/.env"
RUN_DIR="$SCRIPT_DIR/.run"
LOG_DIR="$SCRIPT_DIR/logs"
PID_FILE="$RUN_DIR/api.pid"
LOG_FILE="$LOG_DIR/api.log"
API_PORT="${API_PORT:-9001}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
err()     { echo -e "${RED}[ERROR]${RESET} $*" >&2; }

CMD="${1:-start}"

# ── Helpers ───────────────────────────────────────────────────────────────────

load_env() {
    if [ ! -f "$ENV_FILE" ]; then
        err ".env not found at $ENV_FILE — run ./setup.sh first."
        exit 1
    fi
    set -o allexport
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +o allexport
}

check_venv() {
    if [ ! -x "$VENV_DIR/bin/uvicorn" ]; then
        err "Virtual environment not found at $VENV_DIR — run ./setup.sh first."
        exit 1
    fi
}

# Kill any existing process tracked by PID file, then also sweep by port
kill_existing() {
    # Kill via PID file if present
    if [ -f "$PID_FILE" ]; then
        local pid
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            info "Killing existing API process (pid $pid)..."
            kill "$pid" 2>/dev/null || true
            local waited=0
            while kill -0 "$pid" 2>/dev/null && [ $waited -lt 8 ]; do
                sleep 1; waited=$((waited + 1))
            done
            kill -9 "$pid" 2>/dev/null || true
            success "Stopped pid $pid"
        fi
        rm -f "$PID_FILE"
    fi

    # Also kill anything holding our port (belt-and-suspenders)
    local port_pid
    port_pid=$(ss -tlnp "sport = :${API_PORT}" 2>/dev/null \
        | awk '/LISTEN/{match($0,/pid=([0-9]+)/,a); if(a[1]) print a[1]}' \
        | head -1 || true)
    if [ -n "$port_pid" ] && kill -0 "$port_pid" 2>/dev/null; then
        info "Killing process on port ${API_PORT} (pid $port_pid)..."
        kill -9 "$port_pid" 2>/dev/null || true
        success "Freed port ${API_PORT}"
    fi
}

start_api() {
    mkdir -p "$RUN_DIR" "$LOG_DIR"
    info "Starting backend + frontend (uvicorn) on port ${API_PORT}..."
    cd "$BACKEND_DIR"
    nohup "$VENV_DIR/bin/uvicorn" app.main:app \
        --host 0.0.0.0 \
        --port "$API_PORT" \
        --workers 1 \
        >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    cd "$SCRIPT_DIR"
    success "Started (pid $!)"
    success "Log: $LOG_FILE"
}

wait_healthy() {
    echo -n "  Waiting for API to be ready"
    local i=0
    while [ $i -lt 30 ]; do
        if curl -sf "http://localhost:${API_PORT}/api/health" &>/dev/null; then
            echo -e " ${GREEN}✓${RESET}"
            return 0
        fi
        echo -n "."
        sleep 1
        i=$((i + 1))
    done
    echo -e " ${RED}✗ timed out${RESET}"
    err "API did not become healthy. Last 20 lines of $LOG_FILE:"
    tail -20 "$LOG_FILE" 2>/dev/null || true
    return 1
}

is_running() {
    [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

# ── Commands ──────────────────────────────────────────────────────────────────

do_start() {
    load_env
    check_venv
    kill_existing
    start_api
    wait_healthy

    echo ""
    echo -e "${BOLD}${GREEN}Persona AI Studio is running${RESET}"
    echo -e "  Dashboard : ${CYAN}http://localhost:${API_PORT}${RESET}"
    echo -e "  API docs  : ${CYAN}http://localhost:${API_PORT}/api/docs${RESET}"
    echo -e "  Log       : ${CYAN}$LOG_FILE${RESET}"
    echo -e "  Stop      : ${CYAN}./start-linux.sh stop${RESET}"
    echo ""
}

do_stop() {
    kill_existing
    success "Stopped."
}

do_restart() {
    load_env
    check_venv
    kill_existing
    sleep 1
    start_api
    wait_healthy && success "Restarted — http://localhost:${API_PORT}"
}

do_status() {
    load_env 2>/dev/null || true
    echo ""
    if is_running; then
        echo -e "  ${GREEN}●${RESET} API   running  (pid $(cat "$PID_FILE"))"
    else
        echo -e "  ${RED}●${RESET} API   stopped"
    fi

    if curl -sf "http://localhost:${API_PORT}/api/health" &>/dev/null; then
        echo -e "  ${GREEN}●${RESET} Health check passed"
    else
        echo -e "  ${RED}●${RESET} Health check failed"
    fi
    echo ""
}

do_logs() {
    if [ ! -f "$LOG_FILE" ]; then
        warn "No log file yet — start the server first."
        exit 1
    fi
    info "Tailing $LOG_FILE  (Ctrl+C to stop)"
    tail -f "$LOG_FILE"
}

# ── Dispatch ──────────────────────────────────────────────────────────────────

case "$CMD" in
    start|"")  do_start ;;
    stop)      do_stop ;;
    restart)   do_restart ;;
    status)    do_status ;;
    logs)      do_logs ;;
    *)
        echo ""
        echo -e "Usage: ${CYAN}./start-linux.sh${RESET} [start|stop|restart|status|logs]"
        echo ""
        exit 1
        ;;
esac
