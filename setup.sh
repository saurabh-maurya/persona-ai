#!/usr/bin/env bash
# =============================================================================
# Persona AI Studio — Setup Script
# Supports: Ubuntu/Debian (apt) · macOS (Homebrew)
# Run once before first launch: ./setup.sh
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
ENV_EXAMPLE="$SCRIPT_DIR/.env.example"

echo ""
echo -e "${BOLD}${CYAN}╔════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}${CYAN}║    Persona AI Studio — Setup           ║${RESET}"
echo -e "${BOLD}${CYAN}╚════════════════════════════════════════╝${RESET}"
echo ""

# ── Step 1: Detect OS ─────────────────────────────────────────────────────────
step "Detecting environment"

OS="$(uname -s)"
if [[ "$OS" == "Darwin" ]]; then
    info "macOS detected"
    PKG_MANAGER="brew"
elif [[ "$OS" == "Linux" ]]; then
    info "Linux detected"
    PKG_MANAGER="apt"
else
    error "Unsupported OS: $OS"
    exit 1
fi

# ── Step 2: Homebrew (macOS only) ─────────────────────────────────────────────
if [[ "$PKG_MANAGER" == "brew" ]]; then
    step "Checking Homebrew"
    if command -v brew &>/dev/null; then
        success "Homebrew found"
    else
        warn "Homebrew not found — installing..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        success "Homebrew installed"
    fi
fi

# ── Step 3: Python 3.11+ ──────────────────────────────────────────────────────
step "Checking Python 3.11+"

PYTHON=""
for candidate in python3.12 python3.13 python3.11 python3; do
    if command -v "$candidate" &>/dev/null; then
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
    if [[ "$PKG_MANAGER" == "brew" ]]; then
        brew install python@3.12
        PYTHON="python3.12"
    else
        # Add deadsnakes PPA for Ubuntu if python3.12 isn't in the default repos
        sudo apt-get update -qq
        if ! apt-cache show python3.12 &>/dev/null 2>&1; then
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

# ── Step 4: System build tools (Linux only) ───────────────────────────────────
if [[ "$PKG_MANAGER" == "apt" ]]; then
    step "Installing system build tools"
    sudo apt-get update -qq
    sudo apt-get install -y build-essential curl netcat-openbsd 2>/dev/null \
        || sudo apt-get install -y build-essential curl netcat 2>/dev/null \
        || true
    success "System build tools ready"
fi

# ── Step 5: Python virtual environment ────────────────────────────────────────
step "Setting up Python virtual environment"

if [ -d "$VENV_DIR" ]; then
    warn "Virtual environment already exists at backend/.venv"
    echo -e "  Recreate it? [y/N] "
    read -r recreate
    if [[ "$recreate" =~ ^[Yy]$ ]]; then
        rm -rf "$VENV_DIR"
        $PYTHON -m venv "$VENV_DIR"
        success "Virtual environment recreated"
    else
        success "Keeping existing virtual environment"
    fi
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
        echo "${key}=${value}" >> "$ENV_FILE"
    fi
}

SKIP_CONFIG=0
if [ -f "$ENV_FILE" ]; then
    warn ".env already exists."
    echo -e "  Overwrite with fresh configuration? [y/N] "
    read -r overwrite
    if [[ "$overwrite" =~ ^[Yy]$ ]]; then
        cp "$ENV_EXAMPLE" "$ENV_FILE"
        info "Copied fresh .env from .env.example"
    else
        info "Keeping existing .env — skipping credential prompts."
        SKIP_CONFIG=1
    fi
else
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    success "Created .env from .env.example"
fi

if [ "$SKIP_CONFIG" -eq 0 ]; then
    echo ""
    echo -e "  Enter credentials below. Press ${CYAN}Enter${RESET} to skip and fill .env manually later."
    echo ""

    echo -e "${BOLD}  MongoDB Connection URI${RESET}"
    echo -e "  Default: mongodb://localhost:27017 (press Enter to accept)"
    echo -n "  MONGODB_URL: "
    read -r mongodb_url
    if [ -n "$mongodb_url" ]; then
        set_env "MONGODB_URL" "$mongodb_url"
        success "MongoDB URL saved"
    else
        info "Using default: mongodb://localhost:27017"
    fi

    echo ""
    echo -e "${BOLD}  Groq API Key${RESET} — https://console.groq.com/"
    echo -n "  GROQ_API_KEY: "
    read -r groq_key
    set_env "GROQ_API_KEY" "$groq_key"
    [ -n "$groq_key" ] && success "Groq API key saved" || warn "Skipped — set GROQ_API_KEY in .env"

    echo ""
    echo -e "${BOLD}  Gemini API Key (optional)${RESET} — https://aistudio.google.com/"
    echo -n "  GEMINI_API_KEY: "
    read -r gemini_key
    set_env "GEMINI_API_KEY" "$gemini_key"
    [ -n "$gemini_key" ] && success "Gemini API key saved" || info "Skipped — Groq will be used as primary"
fi

# ── Step 8: Runtime directories ───────────────────────────────────────────────
step "Creating runtime directories"

mkdir -p "$SCRIPT_DIR/.run"
mkdir -p "$SCRIPT_DIR/logs"
success "Runtime directories ready (.run/, logs/)"

# ── Step 9: Validate .env ─────────────────────────────────────────────────────
step "Validating .env"

MISSING=()
check_var() {
    local key="$1"
    local val
    val=$(grep "^${key}=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d '"') || true
    if [ -z "$val" ] || [[ "$val" == *"your_"* ]] || [[ "$val" == *"_here"* ]]; then
        MISSING+=("$key")
        warn "$key — NOT SET"
    else
        success "$key is set"
    fi
}

check_var "MONGODB_URL"
check_var "GROQ_API_KEY"

# MongoDB connectivity check
MONGO_URL=$(grep "^MONGODB_URL=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d '"') || true
MONGO_URL="${MONGO_URL:-mongodb://localhost:27017}"

if [[ "$MONGO_URL" == mongodb+srv://* ]]; then
    MONGO_HOST=$(echo "$MONGO_URL" | sed -E 's|mongodb\+srv://([^@]+@)?([^/?]+).*|\2|')
    info "MongoDB Atlas URI configured (${MONGO_HOST})"
else
    MONGO_HOST=$(echo "$MONGO_URL" | sed -E 's|mongodb://([^@]+@)?([^/:]+).*|\2|')
    MONGO_PORT=$(echo "$MONGO_URL" | grep -oE ':[0-9]+' | tail -1 | tr -d ':')
    MONGO_PORT="${MONGO_PORT:-27017}"
    echo -n "  Checking MongoDB at ${MONGO_HOST}:${MONGO_PORT} ... "
    if nc -z "$MONGO_HOST" "$MONGO_PORT" 2>/dev/null; then
        echo -e "${GREEN}reachable${RESET}"
    else
        echo -e "${YELLOW}unreachable — ensure MongoDB is running${RESET}"
    fi
fi

if [ ${#MISSING[@]} -gt 0 ]; then
    echo ""
    warn "${#MISSING[@]} credential(s) missing — edit ${CYAN}.env${RESET} before starting."
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}╔═══════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}${GREEN}║  Setup complete!                          ║${RESET}"
echo -e "${BOLD}${GREEN}╚═══════════════════════════════════════════╝${RESET}"
echo ""
echo -e "  ${BOLD}Next step:${RESET} ${CYAN}./start-linux.sh${RESET}"
echo ""
echo -e "  Commands:"
echo -e "    ${CYAN}./start-linux.sh${RESET}          — start the app (kills existing, starts fresh)"
echo -e "    ${CYAN}./start-linux.sh stop${RESET}     — stop"
echo -e "    ${CYAN}./start-linux.sh status${RESET}   — health check"
echo -e "    ${CYAN}./start-linux.sh logs${RESET}     — tail logs/api.log"
echo ""
