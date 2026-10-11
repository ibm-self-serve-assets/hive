#!/usr/bin/env bash
# start_backend.sh
# ────────────────
# Starts the spec_2 local backend inside the project venv.
# Creates and populates the venv if it doesn't exist yet.
#
# Usage:
#   cd spec_2_hive_controls
#   ./start_backend.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
REQUIREMENTS="$SCRIPT_DIR/requirements.txt"

# ── 1. Create venv if it doesn't exist ───────────────────────────────────────
if [ ! -f "$VENV_DIR/bin/python" ]; then
  echo "Creating virtual environment at .venv/ ..."
  python3 -m venv "$VENV_DIR"
fi

PIP="$VENV_DIR/bin/pip"
UVICORN="$VENV_DIR/bin/uvicorn"

# ── 2. Install / sync requirements ───────────────────────────────────────────
echo "Installing requirements ..."
"$PIP" install --quiet --upgrade pip
"$PIP" install --quiet -r "$REQUIREMENTS"

# ── 3. Start the backend ─────────────────────────────────────────────────────
echo "Starting Local Hive Controls Backend on http://127.0.0.1:8000 ..."
echo ""
cd "$SCRIPT_DIR"
PYTHONPATH="$SCRIPT_DIR" "$UVICORN" backend.app:app --host 127.0.0.1 --port 8000 --reload
