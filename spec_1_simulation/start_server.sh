#!/usr/bin/env bash
# start_server.sh
# ───────────────
# Starts the spec_1 Hive Simulation Server inside the project venv.
# Creates and populates the venv if it doesn't exist yet.
#
# Usage:
#   cd spec_1_simulation
#   ./start_server.sh

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

# ── 3. Start the server ──────────────────────────────────────────────────────
echo "Starting Hive Simulation Server on http://0.0.0.0:8080 ..."
echo ""
cd "$SCRIPT_DIR"
PYTHONPATH="$SCRIPT_DIR" "$UVICORN" server.app:app --host 0.0.0.0 --port 8080 --reload
