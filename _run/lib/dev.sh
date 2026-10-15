#!/usr/bin/env bash
# dev.sh - starts the API (FastAPI/uvicorn) and the frontend (Vite) in dev mode (macOS/Linux).
# Before starting, it makes sure the environment is ready: creates missing .env files,
# the API venv and node_modules, and reinstalls when a dependency manifest changed.
# Each service opens in its own Terminal window (one for the API, one for the frontend).
# To stop: close each window or press Ctrl+C inside it.
#
# Do NOT run this file directly - use the clickable _run/mac.command (double-click).

set -euo pipefail

# Project root is two levels above this script (_run/lib/).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
API_DIR="$ROOT/backend"
FRONT_DIR="$ROOT/frontend"
API_PYTHON="$API_DIR/.venv/bin/python"

# ---------------------------------------------------------------------------
# 1) .env files (copied from .env.example when missing)
# ---------------------------------------------------------------------------
for DIR in "$API_DIR" "$FRONT_DIR"; do
  if [ -f "$DIR/.env.example" ] && [ ! -f "$DIR/.env" ]; then
    echo "[setup] missing .env in $DIR - creating it from .env.example..."
    cp "$DIR/.env.example" "$DIR/.env"
  fi
done

# ---------------------------------------------------------------------------
# 2) API venv + dependencies.
#    Creates the venv when missing and REINSTALLS when requirements.txt changed
#    (e.g. a pull from another machine added a package).
#    Marker: .venv/.requirements.stamp (touched after every install).
# ---------------------------------------------------------------------------
REQ_FILE="$API_DIR/requirements.txt"
REQ_STAMP="$API_DIR/.venv/.requirements.stamp"
if [ ! -x "$API_PYTHON" ]; then
  echo "[setup] API venv missing - creating it..."
  PY=""
  for c in python3.13 python3.14 python3; do
    if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
  done
  if [ -z "$PY" ]; then
    echo "Python 3.13+ not found. Install it and run again." >&2
    exit 1
  fi
  ( cd "$API_DIR" \
      && "$PY" -m venv .venv \
      && .venv/bin/pip install --upgrade pip \
      && .venv/bin/pip install -r requirements.txt )
  touch "$REQ_STAMP"
elif [ -f "$REQ_FILE" ] && { [ ! -f "$REQ_STAMP" ] || [ "$REQ_FILE" -nt "$REQ_STAMP" ]; }; then
  echo "[setup] requirements.txt changed - updating API dependencies..."
  "$API_PYTHON" -m pip install -r "$REQ_FILE"
  touch "$REQ_STAMP"
fi

# ---------------------------------------------------------------------------
# 3) Frontend node_modules.
#    Reinstalls when package-lock.json is newer than npm's own install record
#    (node_modules/.package-lock.json) - e.g. a pull added a dependency.
# ---------------------------------------------------------------------------
INSTALLED_LOCK="$FRONT_DIR/node_modules/.package-lock.json"
LOCK_FILE="$FRONT_DIR/package-lock.json"
if [ ! -d "$FRONT_DIR/node_modules" ] || [ ! -f "$INSTALLED_LOCK" ] || \
   { [ -f "$LOCK_FILE" ] && [ "$LOCK_FILE" -nt "$INSTALLED_LOCK" ]; }; then
  echo "[setup] frontend dependencies out of date - running npm install..."
  ( cd "$FRONT_DIR" && npm install )
fi

# ---------------------------------------------------------------------------
# 4) Start both services, each in its own Terminal window
# ---------------------------------------------------------------------------
API_CMD="cd $(printf %q "$API_DIR") && $(printf %q "$API_PYTHON") -m uvicorn app.main:app --reload --port 8000"
FRONT_CMD="cd $(printf %q "$FRONT_DIR") && npm run dev"

if command -v osascript >/dev/null 2>&1; then
  # macOS: two Terminal.app windows via AppleScript.
  echo "Opening API   -> http://localhost:8000  (docs at /docs)"
  echo "Opening Front -> http://localhost:5173"
  osascript \
    -e 'tell application "Terminal"' \
    -e "do script \"$API_CMD\"" \
    -e "do script \"$FRONT_CMD\"" \
    -e 'activate' \
    -e 'end tell' >/dev/null
  echo ""
  echo "Two Terminal windows were opened (API and Frontend). Close them to stop."
else
  # Linux (no osascript): single window, Ctrl+C stops both.
  cleanup() { kill 0; }
  trap cleanup EXIT INT TERM
  echo "API   -> http://localhost:8000  (docs at /docs)"
  ( cd "$API_DIR" && "$API_PYTHON" -m uvicorn app.main:app --reload --port 8000 ) &
  echo "Front -> http://localhost:5173"
  ( cd "$FRONT_DIR" && npm run dev ) &
  wait
fi
