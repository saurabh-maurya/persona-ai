#!/bin/bash
# =============================================================================
# Persona AI Studio — Setup Script
# Supports: Ubuntu/Debian (apt) · macOS (Homebrew)
# Run once before first launch: bash setup.sh
# =============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()    { printf "${BLUE}[INFO]${NC}  %s\n" "$*"; }
success() { printf "${GREEN}[OK]${NC}    %s\n" "$*"; }
warn()    { printf "${YELLOW}[WARN]${NC}  %s\n" "$*"; }
error()   { printf "${RED}[ERROR]${NC} %s\n" "$*" >&2; }
step()    { printf "\n${BOLD}${CYAN}▶ %s${NC}\n" "$*"; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
VENV_DIR="$BACKEND_DIR/.venv"
ENV_FILE="$SCRIPT_DIR/.env"
ENV_EXAMPLE="$SCRIPT_DIR/.env.example"

printf "\n"
printf "${BOLD}${CYAN}╔════════════════════════════════════════╗${NC}\n"
printf "${BOLD}${CYAN}║    Persona AI Studio — Setup           ║${NC}\n"
printf "${BOLD}${CYAN}╚════════════════════════════════════════╝${NC}\n"
printf "\n"

# ── Step 1: Detect OS ─────────────────────────────────────────────────────────
step "Detecting environment"

OS="$(uname -s)"
PKG_MANAGER=""

case "$OS" in
    Darwin)
        info "macOS detected"
        PKG_MANAGER="brew"
        ;;
    Linux)
        info "Linux detected"
        PKG_MANAGER="apt"
        ;;
    *)
        error "Unsupported OS: $OS"
        exit 1
        ;;
esac

# ── Step 2: Homebrew (macOS only) ─────────────────────────────────────────────
if [ "$PKG_MANAGER" = "brew" ]; then
    step "Checking Homebrew"
    if command -v brew >/dev/null 2>&1; then
        success "Homebrew found"
    else
        warn "Homebrew not found — installing..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        success "Homebrew installed"
    fi
fi

# ── Step 3: System build tools (Linux only) ───────────────────────────────────
if [ "$PKG_MANAGER" = "apt" ]; then
    step "Installing system build tools"
    sudo apt-get update -qq
    sudo apt-get install -y build-essential curl netcat-openbsd 2>/dev/null || \
        sudo apt-get install -y build-essential curl netcat 2>/dev/null || true
    success "System build tools ready"
fi

# ── Step 4: Python 3.11+ ──────────────────────────────────────────────────────
step "Checking Python 3.11+"

PYTHON=""
for candidate in python3.12 python3.13 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
        ver=$("$candidate" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
        major="${ver%%.*}"
        minor="${ver##*.}"
        if [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    warn "Python 3.11+ not found — installing Python 3.12..."
    if [ "$PKG_MANAGER" = "brew" ]; then
        brew install python@3.12
        PYTHON="python3.12"
    else
        # Add deadsnakes PPA if python3.12 not in default repos (Ubuntu 20.04/22.04)
        if ! apt-cache show python3.12 >/dev/null 2>&1; then
            info "Adding deadsnakes PPA for Python 3.12..."
            sudo apt-get install -y software-properties-common
            sudo add-apt-repository -y ppa:deadsnakes/ppa
            sudo apt-get update -qq
        fi
        sudo apt-get install -y python3.12 python3.12-venv python3.12-dev
        PYTHON="python3.12"
    fi
fi

success "Using Python: $($PYTHON --version)"

# ── Step 5: Python virtual environment ────────────────────────────────────────
step "Setting up Python virtual environment"

if [ -d "$VENV_DIR" ]; then
    warn "Virtual environment already exists at backend/.venv"
    printf "  Recreate it? [y/N] "
    read -r recreate
    case "$recreate" in
        [Yy]*)
            rm -rf "$VENV_DIR"
            $PYTHON -m venv "$VENV_DIR"
            success "Virtual environment recreated"
            ;;
        *)
            success "Keeping existing virtual environment"
            ;;
    esac
else
    $PYTHON -m venv "$VENV_DIR"
    success "Virtual environment created at backend/.venv"
fi

VENV_PIP="$VENV_DIR/bin/pip"

# ── Step 6: Install Python dependencies ───────────────────────────────────────
step "Installing Python dependencies"

"$VENV_PIP" install --upgrade pip --quiet
"$VENV_PIP" install -r "$BACKEND_DIR/requirements.txt"
success "Python dependencies installed"

# ── Step 7: Create .env ───────────────────────────────────────────────────────
step "Configuring environment"

set_env() {
    local key="$1"
    local value="$2"
    [ -z "$value" ] && return
    if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
        sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
    else
        printf "%s=%s\n" "$key" "$value" >> "$ENV_FILE"
    fi
}

SKIP_CONFIG=0
if [ -f "$ENV_FILE" ]; then
    warn ".env already exists."
    printf "  Overwrite with fresh configuration? [y/N] "
    read -r overwrite
    case "$overwrite" in
        [Yy]*)
            cp "$ENV_EXAMPLE" "$ENV_FILE"
            info "Copied fresh .env from .env.example"
            ;;
        *)
            info "Keeping existing .env — skipping credential prompts."
            SKIP_CONFIG=1
            ;;
    esac
else
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    success "Created .env from .env.example"
fi

if [ "$SKIP_CONFIG" -eq 0 ]; then
    printf "\n"
    printf "  Enter credentials below. Press ${CYAN}Enter${NC} to skip and fill .env manually later.\n"
    printf "\n"

    printf "${BOLD}  MongoDB Connection URI${NC}\n"
    printf "  Default: mongodb://localhost:27017 (press Enter to accept)\n"
    printf "  MONGODB_URL: "
    read -r mongodb_url
    if [ -n "$mongodb_url" ]; then
        set_env "MONGODB_URL" "$mongodb_url"
        success "MongoDB URL saved"
    else
        info "Using default: mongodb://localhost:27017"
    fi

    printf "\n"
    printf "${BOLD}  Groq API Key${NC} — https://console.groq.com/\n"
    printf "  GROQ_API_KEY: "
    read -r groq_key
    set_env "GROQ_API_KEY" "$groq_key"
    if [ -n "$groq_key" ]; then
        success "Groq API key saved"
    else
        warn "Skipped — set GROQ_API_KEY in .env"
    fi

    printf "\n"
    printf "${BOLD}  Gemini API Key (optional)${NC} — https://aistudio.google.com/\n"
    printf "  GEMINI_API_KEY: "
    read -r gemini_key
    set_env "GEMINI_API_KEY" "$gemini_key"
    if [ -n "$gemini_key" ]; then
        success "Gemini API key saved"
    else
        info "Skipped — Groq will be used as primary"
    fi
fi

# ── Step 8: Runtime directories ───────────────────────────────────────────────
step "Creating runtime directories"

mkdir -p "$SCRIPT_DIR/.run"
mkdir -p "$SCRIPT_DIR/logs"
success "Runtime directories ready (.run/, logs/)"

# ── Step 9: Validate .env ─────────────────────────────────────────────────────
step "Validating .env"

MISSING_COUNT=0
check_var() {
    local key="$1"
    local val
    val=$(grep "^${key}=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d '"') || true
    case "$val" in
        ""|*your_*|*_here*)
            MISSING_COUNT=$((MISSING_COUNT + 1))
            warn "$key — NOT SET"
            ;;
        *)
            success "$key is set"
            ;;
    esac
}

check_var "MONGODB_URL"
check_var "GROQ_API_KEY"

# MongoDB connectivity check
MONGO_URL=$(grep "^MONGODB_URL=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d '"') || true
MONGO_URL="${MONGO_URL:-mongodb://localhost:27017}"

case "$MONGO_URL" in
    mongodb+srv://*)
        MONGO_HOST=$(printf "%s" "$MONGO_URL" | sed -E 's|mongodb\+srv://([^@]+@)?([^/?]+).*|\2|')
        info "MongoDB Atlas URI configured (${MONGO_HOST})"
        ;;
    *)
        MONGO_HOST=$(printf "%s" "$MONGO_URL" | sed -E 's|mongodb://([^@]+@)?([^/:]+).*|\2|')
        MONGO_PORT=$(printf "%s" "$MONGO_URL" | grep -oE ':[0-9]+' | tail -1 | tr -d ':')
        MONGO_PORT="${MONGO_PORT:-27017}"
        printf "  Checking MongoDB at %s:%s ... " "$MONGO_HOST" "$MONGO_PORT"
        if nc -z "$MONGO_HOST" "$MONGO_PORT" 2>/dev/null; then
            printf "${GREEN}reachable${NC}\n"
        else
            printf "${YELLOW}unreachable — ensure MongoDB is running${NC}\n"
        fi
        ;;
esac

if [ "$MISSING_COUNT" -gt 0 ]; then
    printf "\n"
    warn "${MISSING_COUNT} credential(s) missing — edit .env before starting."
fi

# ── Done ──────────────────────────────────────────────────────────────────────
printf "\n"
printf "${BOLD}${GREEN}╔═══════════════════════════════════════════╗${NC}\n"
printf "${BOLD}${GREEN}║  Setup complete!                          ║${NC}\n"
printf "${BOLD}${GREEN}╚═══════════════════════════════════════════╝${NC}\n"
printf "\n"
printf "  ${BOLD}Next step:${NC} ${CYAN}bash start-linux.sh${NC}\n"
printf "\n"
printf "  Commands:\n"
printf "    ${CYAN}bash start-linux.sh${NC}          — start the app\n"
printf "    ${CYAN}bash start-linux.sh stop${NC}     — stop\n"
printf "    ${CYAN}bash start-linux.sh status${NC}   — health check\n"
printf "    ${CYAN}bash start-linux.sh logs${NC}     — tail logs/api.log\n"
printf "\n"
