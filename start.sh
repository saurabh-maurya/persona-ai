#!/usr/bin/env bash
# =============================================================================
# Persona AI Studio — Local Start Script (no Docker)
# MongoDB is external — configure MONGODB_URL in .env
# Redis is optional — if unavailable, API starts without the image worker
#
# Usage:
#   ./start.sh            — start services
#   ./start.sh stop       — stop API + worker
#   ./start.sh restart    — restart API + worker
#   ./start.sh status     — show process + API + queue status
#   ./start.sh logs       — tail all logs
#   ./start.sh logs api   — tail API log only
#   ./start.sh logs worker— tail worker log only
#   ./start.sh seed       — load sample character & session
# =============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

info()    { echo -e "${BLUE}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*" >&2; }
step()    { echo -e "\n${BOLD}${CYAN}▶ $*${RESET}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
VENV_DIR="$BACKEND_DIR/.venv"
ENV_FILE="$SCRIPT_DIR/.env"
RUN_DIR="$SCRIPT_DIR/.run"
LOG_DIR="$SCRIPT_DIR/logs"

PID_REDIS="$RUN_DIR/redis.pid"
PID_API="$RUN_DIR/api.pid"
PID_WORKER="$RUN_DIR/worker.pid"

LOG_API="$LOG_DIR/api.log"
LOG_WORKER="$LOG_DIR/worker.log"
LOG_REDIS="$LOG_DIR/redis.log"

CMD="${1:-start}"

# ── Guards ────────────────────────────────────────────────────────────────────

check_setup() {
  if [ ! -f "$ENV_FILE" ]; then
    error ".env not found. Run ./setup.sh first."
    exit 1
  fi
  if [ ! -d "$VENV_DIR" ]; then
    error "Python virtual environment not found at backend/.venv — run ./setup.sh first."
    exit 1
  fi
}

load_env() {
  set -o allexport
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +o allexport
}

# ── PID helpers ───────────────────────────────────────────────────────────────

is_running() {
  local pidfile="$1"
  [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null
}

stop_pid() {
  local pidfile="$1"
  local name="$2"
  if [ -f "$pidfile" ]; then
    local pid
    pid=$(cat "$pidfile")
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null
      # Wait up to 5s for graceful exit
      local i=0
      while kill -0 "$pid" 2>/dev/null && [ $i -lt 5 ]; do
        sleep 1; i=$((i+1))
      done
      kill -9 "$pid" 2>/dev/null || true
      success "Stopped $name (pid $pid)"
    else
      info "$name was not running"
    fi
    rm -f "$pidfile"
  else
    info "$name is not managed by this script"
  fi
}

# ── Network helpers ───────────────────────────────────────────────────────────

port_open() {
  local host="$1"
  local port="$2"
  nc -z "$host" "$port" 2>/dev/null
}

wait_http() {
  local url="$1"
  local max="${2:-30}"
  local elapsed=0
  echo -ne "  Waiting for API at ${CYAN}${url}${RESET} "
  while ! curl -sf "$url" &>/dev/null; do
    if [ "$elapsed" -ge "$max" ]; then
      echo -e " ${RED}✗ timed out${RESET}"
      return 1
    fi
    echo -n "."
    sleep 1
    elapsed=$((elapsed + 1))
  done
  echo -e " ${GREEN}✓${RESET}"
}

# Parse host and port from MONGODB_URL (mongodb://host:port or mongodb://host:port/db)
parse_mongo_host() {
  local url="${MONGODB_URL:-mongodb://localhost:27017}"
  # Strip scheme (mongodb:// or mongodb+srv://)
  url="${url#mongodb+srv://}"
  url="${url#mongodb://}"
  # Strip credentials if present (user:pass@host)
  url="${url#*@}"
  # Strip database/options
  url="${url%%/*}"
  # url is now host or host:port
  echo "$url"
}

# Returns true if the URL is an Atlas SRV connection string
is_srv_url() {
  [[ "${MONGODB_URL:-}" == mongodb+srv://* ]]
}

# ── MongoDB connectivity check ────────────────────────────────────────────────
# We do NOT start/stop MongoDB — it is the user's responsibility.
# We just verify the configured MONGODB_URL is reachable before starting the API.

check_mongodb() {
  local hostport
  hostport=$(parse_mongo_host)
  local host="${hostport%%:*}"
  local port="${hostport##*:}"
  [[ "$port" == "$host" ]] && port="27017"  # no port in string
  port="${port:-27017}"

  # For Atlas/SRV URIs, raw TCP check on port 27017 is blocked by design.
  # Trust the URI and let the driver handle DNS resolution.
  if is_srv_url; then
    success "MongoDB Atlas URI configured (${host})"
    return 0
  fi

  if port_open "$host" "$port"; then
    success "MongoDB reachable at ${host}:${port}"
    return 0
  else
    error "Cannot reach MongoDB at ${host}:${port}"
    error "Check that MongoDB is running and MONGODB_URL is correct in .env"
    error "Current MONGODB_URL: ${MONGODB_URL:-mongodb://localhost:27017}"
    return 1
  fi
}

# ── Redis (optional) ──────────────────────────────────────────────────────────

REDIS_AVAILABLE=0

check_or_start_redis() {
  local host="${REDIS_HOST:-localhost}"
  local port="${REDIS_PORT:-6379}"

  # Already reachable?
  if port_open "$host" "$port"; then
    success "Redis reachable at ${host}:${port}"
    REDIS_AVAILABLE=1
    return 0
  fi

  # Only try to auto-start Redis when it's localhost (don't touch remote Redis)
  if [[ "$host" == "localhost" || "$host" == "127.0.0.1" ]]; then
    info "Redis not running — attempting to start..."

    # Try brew services (macOS)
    if command -v brew &>/dev/null && brew list redis &>/dev/null 2>&1; then
      brew services start redis &>/dev/null || true
      sleep 2
      if port_open "$host" "$port"; then
        success "Redis started via brew services"
        REDIS_AVAILABLE=1
        return 0
      fi
    fi

    # Try redis-server directly
    if command -v redis-server &>/dev/null; then
      redis-server --daemonize yes --logfile "$LOG_REDIS" --port "$port" &>/dev/null || true
      sleep 1
      local pid
      pid=$(pgrep -f "redis-server.*${port}" | head -1 || true)
      [ -n "$pid" ] && echo "$pid" > "$PID_REDIS"
      if port_open "$host" "$port"; then
        success "Redis started (pid ${pid:-?})"
        REDIS_AVAILABLE=1
        return 0
      fi
    fi
  fi

  warn "Redis not available at ${host}:${port}"
  warn "Image generation (worker) will be skipped. API will still run."
  warn "To enable the worker: install Redis and restart with ./start.sh"
  REDIS_AVAILABLE=0
  return 0   # not fatal
}

stop_redis_if_local() {
  local host="${REDIS_HOST:-localhost}"
  # Only stop Redis if we started it ourselves (pid file exists) and it's local
  if [[ "$host" == "localhost" || "$host" == "127.0.0.1" ]] && [ -f "$PID_REDIS" ]; then
    # Try brew first
    if command -v brew &>/dev/null && brew services list 2>/dev/null | grep -qE "redis.*started"; then
      brew services stop redis &>/dev/null || true
      rm -f "$PID_REDIS"
      success "Redis stopped (brew services)"
      return
    fi
    stop_pid "$PID_REDIS" "Redis"
  fi
}

# ── API ───────────────────────────────────────────────────────────────────────

start_api() {
  if is_running "$PID_API"; then
    success "API already running (pid $(cat "$PID_API"))"
    return
  fi

  info "Starting FastAPI backend..."
  cd "$BACKEND_DIR"
  nohup "$VENV_DIR/bin/uvicorn" app.main:app \
    --host 0.0.0.0 \
    --port 9001 \
    --workers 1 \
    >> "$LOG_API" 2>&1 &
  echo $! > "$PID_API"
  success "API started  (pid $!  |  log: logs/api.log)"
  cd "$SCRIPT_DIR"
}

stop_api() { stop_pid "$PID_API" "API"; }

# ── Worker ────────────────────────────────────────────────────────────────────

start_worker() {
  if [ "$REDIS_AVAILABLE" -eq 0 ]; then
    warn "Worker skipped — Redis not available"
    return
  fi

  if is_running "$PID_WORKER"; then
    success "Worker already running (pid $(cat "$PID_WORKER"))"
    return
  fi

  info "Starting BullMQ worker..."
  cd "$BACKEND_DIR"
  nohup "$VENV_DIR/bin/python" -m worker.main \
    >> "$LOG_WORKER" 2>&1 &
  echo $! > "$PID_WORKER"
  success "Worker started  (pid $!  |  log: logs/worker.log)"
  cd "$SCRIPT_DIR"
}

stop_worker() { stop_pid "$PID_WORKER" "Worker"; }

# ══ COMMANDS ══════════════════════════════════════════════════════════════════

banner() {
  echo ""
  echo -e "${BOLD}${CYAN}╔════════════════════════════════════════╗${RESET}"
  echo -e "${BOLD}${CYAN}║       Persona AI Studio                ║${RESET}"
  echo -e "${BOLD}${CYAN}╚════════════════════════════════════════╝${RESET}"
  echo ""
}

# ── START ─────────────────────────────────────────────────────────────────────
do_start() {
  banner
  check_setup
  load_env
  mkdir -p "$RUN_DIR" "$LOG_DIR" /tmp/persona_images

  step "Checking MongoDB"
  check_mongodb || exit 1

  step "Checking Redis (optional)"
  check_or_start_redis

  step "Starting application"
  start_api
  start_worker

  step "Waiting for API"
  wait_http "http://localhost:9001/api/health" 30 || {
    error "API did not start. Last 20 lines of logs/api.log:"
    tail -20 "$LOG_API" 2>/dev/null || true
    exit 1
  }

  echo ""
  echo -e "${BOLD}${GREEN}╔═══════════════════════════════════════════════╗${RESET}"
  echo -e "${BOLD}${GREEN}║  Persona AI Studio is running!                ║${RESET}"
  echo -e "${BOLD}${GREEN}╚═══════════════════════════════════════════════╝${RESET}"
  echo ""
  echo -e "  ${BOLD}Dashboard:${RESET}  ${CYAN}http://localhost:9001${RESET}"
  echo -e "  ${BOLD}API Docs:${RESET}   ${CYAN}http://localhost:9001/api/docs${RESET}"
  echo ""
  echo -e "  ${BOLD}MongoDB:${RESET}    ${MONGODB_URL:-mongodb://localhost:27017}  ${YELLOW}(external)${RESET}"
  echo -e "  ${BOLD}Redis:${RESET}      ${REDIS_HOST:-localhost}:${REDIS_PORT:-6379}  $([ "$REDIS_AVAILABLE" -eq 1 ] && echo "${GREEN}✓ connected${RESET}" || echo "${YELLOW}✗ not available (worker disabled)${RESET}")"
  echo ""
  echo -e "  ${BOLD}Processes:${RESET}"
  printf "    %-10s pid %s\n" "API"    "$(cat "$PID_API"    2>/dev/null || echo '—')"
  if [ "$REDIS_AVAILABLE" -eq 1 ]; then
    printf "    %-10s pid %s\n" "Worker" "$(cat "$PID_WORKER" 2>/dev/null || echo '—')"
  else
    printf "    %-10s %s\n"     "Worker" "(disabled — no Redis)"
  fi
  echo ""
  echo -e "  ${BOLD}Logs:${RESET}   ${CYAN}./start.sh logs${RESET}"
  echo -e "  ${BOLD}Stop:${RESET}   ${CYAN}./start.sh stop${RESET}"
  echo ""

  [[ "$OSTYPE" == "darwin"* ]] && { sleep 1; open "http://localhost:9001" 2>/dev/null || true; }
}

# ── STOP ──────────────────────────────────────────────────────────────────────
do_stop() {
  banner
  step "Stopping Persona AI Studio"
  stop_worker
  stop_api
  stop_redis_if_local
  echo ""
  success "Services stopped. MongoDB is external and was not touched."
  echo ""
}

# ── RESTART ───────────────────────────────────────────────────────────────────
do_restart() {
  banner
  check_setup
  load_env

  step "Restarting API + worker"
  stop_worker
  stop_api
  sleep 1

  mkdir -p "$RUN_DIR" "$LOG_DIR"

  # Re-check Redis in case it came online since last start
  check_or_start_redis

  start_api
  start_worker

  wait_http "http://localhost:9001/api/health" 30 \
    && success "API back online — ${CYAN}http://localhost:9001${RESET}" \
    || warn "API may still be starting — ${CYAN}./start.sh logs api${RESET}"
  echo ""
}

# ── STATUS ────────────────────────────────────────────────────────────────────
do_status() {
  banner
  load_env 2>/dev/null || true

  step "Process status"

  show_proc() {
    local label="$1" pidfile="$2"
    if is_running "$pidfile"; then
      echo -e "  ${GREEN}●${RESET} ${BOLD}${label}${RESET}   running  (pid $(cat "$pidfile"))"
    else
      echo -e "  ${RED}●${RESET} ${BOLD}${label}${RESET}   stopped"
    fi
  }

  # MongoDB: just check connectivity
  if is_srv_url; then
    echo -e "  ${GREEN}●${RESET} ${BOLD}MongoDB${RESET}    Atlas (SRV) — ${MONGODB_URL:-}  ${YELLOW}(external)${RESET}"
  else
    local mongo_hostport
    mongo_hostport=$(parse_mongo_host)
    local mhost="${mongo_hostport%%:*}"
    local mport="${mongo_hostport##*:}"
    [[ "$mport" == "$mhost" ]] && mport="27017"
    if port_open "$mhost" "${mport:-27017}"; then
      echo -e "  ${GREEN}●${RESET} ${BOLD}MongoDB${RESET}    reachable at ${MONGODB_URL:-mongodb://localhost:27017}  ${YELLOW}(external)${RESET}"
    else
      echo -e "  ${RED}●${RESET} ${BOLD}MongoDB${RESET}    unreachable — ${MONGODB_URL:-mongodb://localhost:27017}"
    fi
  fi

  # Redis: check connectivity
  local rhost="${REDIS_HOST:-localhost}"
  local rport="${REDIS_PORT:-6379}"
  if port_open "$rhost" "$rport"; then
    echo -e "  ${GREEN}●${RESET} ${BOLD}Redis${RESET}      reachable at ${rhost}:${rport}"
  else
    echo -e "  ${YELLOW}●${RESET} ${BOLD}Redis${RESET}      not available at ${rhost}:${rport}  (optional)"
  fi

  show_proc "API   " "$PID_API"
  show_proc "Worker" "$PID_WORKER"

  echo ""
  step "API health"
  curl -sf "http://localhost:9001/api/health" 2>/dev/null | python3 -m json.tool \
    && success "API is healthy" \
    || warn "API is not responding"

  echo ""
  step "Queue stats"
  curl -sf "http://localhost:9001/api/queue/status" 2>/dev/null | python3 -m json.tool \
    || warn "Could not fetch queue stats"
  echo ""
}

# ── LOGS ──────────────────────────────────────────────────────────────────────
do_logs() {
  local target="${2:-all}"
  case "$target" in
    api)    info "Tailing API log (Ctrl+C to stop)";    tail -f "$LOG_API" ;;
    worker) info "Tailing worker log (Ctrl+C to stop)"; tail -f "$LOG_WORKER" ;;
    redis)  info "Tailing Redis log (Ctrl+C to stop)";  tail -f "$LOG_REDIS" ;;
    all|*)
      info "Tailing API + worker logs (Ctrl+C to stop)"
      echo -e "  Tip: ${CYAN}./start.sh logs api${RESET}  or  ${CYAN}./start.sh logs worker${RESET}\n"
      local files=()
      [ -f "$LOG_API"    ] && files+=("$LOG_API")
      [ -f "$LOG_WORKER" ] && files+=("$LOG_WORKER")
      if [ ${#files[@]} -gt 0 ]; then
        tail -f "${files[@]}"
      else
        warn "No log files yet — start the server first with ./start.sh"
      fi
      ;;
  esac
}

# ── SEED ──────────────────────────────────────────────────────────────────────
do_seed() {
  banner
  check_setup
  load_env

  if ! curl -sf "http://localhost:9001/api/health" &>/dev/null; then
    error "API is not running. Start it first: ./start.sh"
    exit 1
  fi

  step "Loading sample data"
  cd "$BACKEND_DIR"
  "$VENV_DIR/bin/python" scripts/seed.py
  echo ""
  success "Sample data loaded."
  info "Open ${CYAN}http://localhost:9001/sessions.html${RESET} to generate a plan."
  echo ""
}

# ── Dispatch ──────────────────────────────────────────────────────────────────
case "$CMD" in
  start|"")  do_start ;;
  stop)       do_stop ;;
  restart)    do_restart ;;
  logs)       do_logs "$@" ;;
  status)     do_status ;;
  seed)       do_seed ;;
  *)
    echo -e "\nUsage: ${CYAN}./start.sh${RESET} [command]"
    echo ""
    echo -e "  ${CYAN}./start.sh${RESET}               Start API + worker (MongoDB must already be running)"
    echo -e "  ${CYAN}./start.sh stop${RESET}          Stop API + worker"
    echo -e "  ${CYAN}./start.sh restart${RESET}       Restart API + worker"
    echo -e "  ${CYAN}./start.sh status${RESET}        Process + connectivity + queue stats"
    echo -e "  ${CYAN}./start.sh logs${RESET}          Tail API + worker logs"
    echo -e "  ${CYAN}./start.sh logs api${RESET}      Tail API log only"
    echo -e "  ${CYAN}./start.sh logs worker${RESET}   Tail worker log only"
    echo -e "  ${CYAN}./start.sh seed${RESET}          Load sample character & session"
    echo ""
    exit 1
    ;;
esac
