#!/bin/bash
# =============================================================================
# Persona AI Studio — Linux Startup Script (no Docker)
#
# Usage:
#   bash start-linux.sh            — kill any existing instance, then start
#   bash start-linux.sh stop       — stop running instance
#   bash start-linux.sh restart    — stop + start
#   bash start-linux.sh status     — show process and API health
#   bash start-linux.sh logs       — tail the backend log
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
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
NC='\033[0m'

info()    { printf "${CYAN}[INFO]${NC}  %s\n" "$*"; }
success() { printf "${GREEN}[OK]${NC}    %s\n" "$*"; }
warn()    { printf "${YELLOW}[WARN]${NC}  %s\n" "$*"; }
err()     { printf "${RED}[ERROR]${NC} %s\n" "$*" >&2; }

CMD="${1:-start}"

# ── Helpers ───────────────────────────────────────────────────────────────────

load_env() {
    if [ ! -f "$ENV_FILE" ]; then
        err ".env not found at $ENV_FILE — run: bash setup.sh"
        exit 1
    fi
    set -o allexport
    . "$ENV_FILE"
    set +o allexport
}

check_venv() {
    if [ ! -x "$VENV_DIR/bin/uvicorn" ]; then
        err "Virtual environment not found at $VENV_DIR — run: bash setup.sh"
        exit 1
    fi
}

kill_existing() {
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            info "Killing existing API process (pid $pid)..."
            kill "$pid" 2>/dev/null || true
            waited=0
            while kill -0 "$pid" 2>/dev/null && [ "$waited" -lt 8 ]; do
                sleep 1
                waited=$((waited + 1))
            done
            kill -9 "$pid" 2>/dev/null || true
            success "Stopped pid $pid"
        fi
        rm -f "$PID_FILE"
    fi

    # Also kill anything still holding the port
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
    printf "  Waiting for API to be ready"
    i=0
    while [ "$i" -lt 30 ]; do
        if curl -sf "http://localhost:${API_PORT}/api/health" >/dev/null 2>&1; then
            printf " ${GREEN}✓${NC}\n"
            return 0
        fi
        printf "."
        sleep 1
        i=$((i + 1))
    done
    printf " ${RED}✗ timed out${NC}\n"
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

    printf "\n"
    printf "${BOLD}${GREEN}Persona AI Studio is running${NC}\n"
    printf "  Dashboard : ${CYAN}http://localhost:${API_PORT}${NC}\n"
    printf "  API docs  : ${CYAN}http://localhost:${API_PORT}/api/docs${NC}\n"
    printf "  Log       : ${CYAN}%s${NC}\n" "$LOG_FILE"
    printf "  Stop      : ${CYAN}bash start-linux.sh stop${NC}\n"
    printf "\n"
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
    printf "\n"
    if is_running; then
        printf "  ${GREEN}●${NC} API   running  (pid %s)\n" "$(cat "$PID_FILE")"
    else
        printf "  ${RED}●${NC} API   stopped\n"
    fi
    if curl -sf "http://localhost:${API_PORT}/api/health" >/dev/null 2>&1; then
        printf "  ${GREEN}●${NC} Health check passed\n"
    else
        printf "  ${RED}●${NC} Health check failed\n"
    fi
    printf "\n"
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
        printf "\nUsage: ${CYAN}bash start-linux.sh${NC} [start|stop|restart|status|logs]\n\n"
        exit 1
        ;;
esac
