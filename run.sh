#!/usr/bin/env bash
# Rejection Feedback Engine — one-command setup for macOS / Linux.
#
# Checks prerequisites, sets up an isolated environment, starts the server,
# and opens the web UI. Safe to re-run (idempotent).
#
#   ./run.sh
#
set -euo pipefail
cd "$(dirname "$0")"

PORT="${RFE_PORT:-8000}"
LLM_MODEL="${RFE_LLM_MODEL:-llama3}"

say()  { printf '\n\033[1;36m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m!  %s\033[0m\n' "$1"; }
die()  { printf '\033[1;31mX  %s\033[0m\n' "$1" >&2; exit 1; }

# --- 1. Python ---------------------------------------------------------------
say "Checking for Python 3.12+"
PY=""
for c in python3.13 python3.12 python3; do
  if command -v "$c" >/dev/null 2>&1; then
    if "$c" -c 'import sys; raise SystemExit(0 if sys.version_info>=(3,12) else 1)'; then
      PY="$c"; break
    fi
  fi
done
if [ -z "$PY" ]; then
  warn "Python 3.12+ not found."
  if [ "$(uname)" = "Darwin" ] && command -v brew >/dev/null 2>&1; then
    say "Installing Python via Homebrew"
    brew install python@3.12
    PY="python3.12"
  else
    die "Please install Python 3.12+ from https://www.python.org/downloads/ then re-run ./run.sh"
  fi
fi
echo "   using $($PY --version)"

# --- 2. Virtualenv + dependencies -------------------------------------------
if [ ! -d .venv ]; then
  say "Creating virtual environment (.venv)"
  "$PY" -m venv .venv
fi
say "Installing dependencies (first run downloads packages, please wait)"
./.venv/bin/pip install --quiet --upgrade pip
./.venv/bin/pip install --quiet -e . uvicorn

# --- 3. Local LLM (Ollama) — optional but recommended ------------------------
if command -v ollama >/dev/null 2>&1; then
  if ! curl -fs http://localhost:11434/api/version >/dev/null 2>&1; then
    say "Starting Ollama"
    (ollama serve >/dev/null 2>&1 &) ; sleep 2
  fi
  if ! ollama list 2>/dev/null | grep -q "^${LLM_MODEL}"; then
    say "Downloading the '${LLM_MODEL}' model (one-time, a few GB)"
    ollama pull "$LLM_MODEL"
  fi
  export RFE_LLM_BASE_URL="http://localhost:11434/v1"
  export RFE_LLM_MODEL="$LLM_MODEL"
  echo "   LLM: local Ollama ($LLM_MODEL) — free, private"
else
  warn "Ollama not found (the engine needs an LLM to write feedback)."
  warn "Easiest free option: install from https://ollama.com/download then re-run ./run.sh"
  warn "Or point at any OpenAI-compatible API by setting before running:"
  warn "  export RFE_LLM_BASE_URL=...  RFE_LLM_API_KEY=...  RFE_LLM_MODEL=..."
  if [ -z "${RFE_LLM_BASE_URL:-}" ]; then
    die "No LLM configured. Install Ollama or set RFE_LLM_BASE_URL, then re-run."
  fi
fi

# --- 4. Start the server + open the browser ----------------------------------
URL="http://localhost:${PORT}"
say "Starting the Rejection Feedback Engine at ${URL}"
echo "   The web page will open in your browser. Press Ctrl+C here to stop."

( # open browser shortly after the server comes up
  for _ in $(seq 1 30); do
    if curl -fs "$URL" >/dev/null 2>&1; then
      if   command -v open    >/dev/null 2>&1; then open "$URL"
      elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL"
      fi
      break
    fi
    sleep 1
  done
) &

exec ./.venv/bin/uvicorn rfe.main:app --port "$PORT"
