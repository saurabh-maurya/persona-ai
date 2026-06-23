#!/usr/bin/env bash
# =============================================================================
# Persona AI Studio — Local Setup Script (no Docker)
# Run once: ./setup.sh
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
echo -e "${BOLD}${CYAN}║    Persona AI Studio — Local Setup     ║${RESET}"
echo -e "${BOLD}${CYAN}╚════════════════════════════════════════╝${RESET}"
echo ""

# ── Step 1: OS check ─────────────────────────────────────────────────────────
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

# ── Step 2: Check / install Homebrew (macOS only) ─────────────────────────────
if [[ "$PKG_MANAGER" == "brew" ]]; then
  step "Checking Homebrew"
  if command -v brew &>/dev/null; then
    success "Homebrew found"
  else
    warn "Homebrew not found. Installing..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    success "Homebrew installed"
  fi
fi

# ── Step 3: Python 3.12 ───────────────────────────────────────────────────────
step "Checking Python 3.12+"

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
  warn "Python 3.11+ not found. Installing Python 3.12..."
  if [[ "$PKG_MANAGER" == "brew" ]]; then
    brew install python@3.12
    PYTHON="python3.12"
  else
    sudo apt-get update && sudo apt-get install -y python3.12 python3.12-venv python3.12-dev
    PYTHON="python3.12"
  fi
fi

success "Using Python: $($PYTHON --version)"

# ── Step 4: Redis ─────────────────────────────────────────────────────────────
step "Checking Redis"

if command -v redis-server &>/dev/null; then
  success "Redis found: $(redis-server --version | grep -oE 'v=[0-9.]+')"
else
  warn "Redis not found. Installing..."
  if [[ "$PKG_MANAGER" == "brew" ]]; then
    brew install redis
    success "Redis installed"
  else
    sudo apt-get install -y redis-server
    success "Redis installed"
  fi
fi

# ── Step 5: Python virtual environment ────────────────────────────────────────
step "Setting up Python virtual environment"

if [ -d "$VENV_DIR" ]; then
  warn "Virtual environment already exists at backend/.venv"
  echo -e "  Recreate it? [y/N]"
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

VENV_PYTHON="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

# ── Step 6: Install Python dependencies ───────────────────────────────────────
step "Installing Python dependencies"

"$VENV_PIP" install --upgrade pip --quiet
"$VENV_PIP" install -r "$BACKEND_DIR/requirements.txt"
success "Python dependencies installed"

# ── Step 7: Install Playwright browser ────────────────────────────────────────
step "Installing Playwright Chromium browser"

"$VENV_DIR/bin/playwright" install chromium
success "Playwright Chromium installed"

# ── Step 8: Create .env ───────────────────────────────────────────────────────
step "Configuring environment"

if [ -f "$ENV_FILE" ]; then
  warn ".env already exists."
  echo -e "  Overwrite with fresh configuration? [y/N]"
  read -r overwrite
  if [[ "$overwrite" =~ ^[Yy]$ ]]; then
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    info "Copied fresh .env from .env.example"
    SKIP_CONFIG=0
  else
    info "Keeping existing .env — skipping credential prompts."
    SKIP_CONFIG=1
  fi
else
  cp "$ENV_EXAMPLE" "$ENV_FILE"
  success "Created .env from .env.example"
  SKIP_CONFIG=0
fi

# Helper to write a key into .env
set_env() {
  local key="$1"
  local value="$2"
  [ -z "$value" ] && return
  if grep -q "^${key}=" "$ENV_FILE"; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
      sed -i '' "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
    else
      sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
    fi
  else
    echo "${key}=${value}" >> "$ENV_FILE"
  fi
}

if [ "${SKIP_CONFIG:-0}" -eq 0 ]; then
  echo ""
  echo -e "  Enter credentials below. Press ${CYAN}Enter${RESET} to skip any field and fill .env manually."
  echo ""

  # MongoDB URL
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

  # Gemini
  echo ""
  echo -e "${BOLD}  Gemini API Key${RESET} — https://aistudio.google.com/"
  echo -n "  GEMINI_API_KEY: "
  read -r gemini_key
  set_env "GEMINI_API_KEY" "$gemini_key"
  [ -n "$gemini_key" ] && success "Gemini API key saved" || warn "Skipped — set GEMINI_API_KEY in .env"

  # Google Service Account
  echo ""
  echo -e "${BOLD}  Google Service Account JSON${RESET} — https://console.cloud.google.com/"
  echo -e "  Convert key file: ${CYAN}cat key.json | python3 -c \"import sys,json; print(json.dumps(json.load(sys.stdin)))\"${RESET}"
  echo -n "  GOOGLE_SERVICE_ACCOUNT_JSON (single-line JSON): "
  read -r sa_json
  set_env "GOOGLE_SERVICE_ACCOUNT_JSON" "$sa_json"
  [ -n "$sa_json" ] && success "Service account JSON saved" || warn "Skipped — set GOOGLE_SERVICE_ACCOUNT_JSON in .env"

  # Google credentials for ImageFX
  echo ""
  echo -e "${BOLD}  Google Account for ImageFX automation${RESET}"
  echo -n "  GOOGLE_EMAIL: "
  read -r google_email
  set_env "GOOGLE_EMAIL" "$google_email"

  echo -e "  Tip: use an App Password — myaccount.google.com → Security → App passwords"
  echo -n "  GOOGLE_PASSWORD: "
  read -rs google_password
  echo ""
  set_env "GOOGLE_PASSWORD" "$google_password"
  [ -n "$google_email" ] && success "Google credentials saved" || warn "Skipped — set GOOGLE_EMAIL and GOOGLE_PASSWORD in .env"
fi

# ── Step 9: Create runtime directories ────────────────────────────────────────
step "Creating runtime directories"

mkdir -p "$SCRIPT_DIR/.run"
mkdir -p "$SCRIPT_DIR/logs"
mkdir -p /tmp/persona_images
success "Runtime directories ready (.run/, logs/, /tmp/persona_images)"

# ── Step 10: Validate .env ────────────────────────────────────────────────────
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

check_var "GEMINI_API_KEY"
check_var "GOOGLE_OAUTH_CLIENT_ID"
check_var "GOOGLE_OAUTH_CLIENT_SECRET"
check_var "GOOGLE_EMAIL"
check_var "GOOGLE_PASSWORD"

# Check MongoDB connectivity
MONGO_URL=$(grep "^MONGODB_URL=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d '"') || true
MONGO_URL="${MONGO_URL:-mongodb://localhost:27017}"
if [[ "$MONGO_URL" == mongodb+srv://* ]]; then
  # SRV URI — extract hostname only (no port; DNS resolves it)
  MONGO_HOST=$(echo "$MONGO_URL" | sed -E 's|mongodb\+srv://[^@]+@([^/?]+).*|\1|')
  MONGO_PORT=27017
else
  MONGO_HOST=$(echo "$MONGO_URL" | sed -E 's|mongodb://([^/:@]+@)?([^/:]+).*|\2|')
  MONGO_PORT=$(echo "$MONGO_URL" | sed -E 's|.*:([0-9]+)(/.*)?$|\1|')
  MONGO_PORT="${MONGO_PORT:-27017}"
fi
echo -n "  Checking MongoDB at ${MONGO_HOST} ... "
if nc -z "$MONGO_HOST" "$MONGO_PORT" 2>/dev/null; then
  echo -e "${GREEN}reachable${RESET}"
else
  echo -e "${YELLOW}unreachable (Atlas or firewall — OK if DNS resolves)${RESET}"
fi

if [ ${#MISSING[@]} -gt 0 ]; then
  echo ""
  warn "${#MISSING[@]} credential(s) are missing. Edit ${CYAN}.env${RESET} before running ./start.sh"
  warn "Image generation and Drive upload will not work until these are set."
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}╔═══════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}${GREEN}║  Setup complete!                          ║${RESET}"
echo -e "${BOLD}${GREEN}╚═══════════════════════════════════════════╝${RESET}"
echo ""
echo -e "  ${BOLD}Next step:${RESET} ${CYAN}./start.sh${RESET}"
echo ""
echo -e "  What start.sh does:"
echo -e "    • Verifies MongoDB is reachable (configure MONGODB_URL in .env)"
echo -e "    • Starts Redis if available (optional — enables image generation queue)"
echo -e "    • Launches the FastAPI backend on port 8000"
echo -e "    • Launches the BullMQ worker (if Redis is available)"
echo -e "    • Opens the dashboard at http://localhost:8000"
echo ""
