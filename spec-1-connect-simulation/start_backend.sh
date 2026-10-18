#!/usr/bin/env bash
# start_backend.sh — spec-1-connect-simulation
#
# Usage:
#   cd spec-1-connect-simulation
#   ./start_backend.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
REQUIREMENTS="$SCRIPT_DIR/requirements.txt"

_venv_ok=false
if [ -f "$VENV_DIR/bin/python" ]; then
  _shebang="$(head -1 "$VENV_DIR/bin/pip" 2>/dev/null || true)"
  if [[ "$_shebang" == *"$VENV_DIR"* ]]; then
    _venv_ok=true
  else
    echo "Venv interpreter path is stale. Recreating .venv/ ..."
    rm -rf "$VENV_DIR"
  fi
fi
if [ "$_venv_ok" = false ]; then
  echo "Creating virtual environment at .venv/ ..."
  python3 -m venv "$VENV_DIR"
fi

PIP="$VENV_DIR/bin/pip"
UVICORN="$VENV_DIR/bin/uvicorn"

echo "Installing requirements ..."
"$PIP" install --quiet --upgrade pip
"$PIP" install --quiet -r "$REQUIREMENTS"

echo "Starting Hive Connect-Simulation Backend on http://localhost:8001 ..."
echo ""
cd "$SCRIPT_DIR"
PYTHONPATH="$SCRIPT_DIR" "$UVICORN" backend.app:app \
  --host localhost --port 8001 --reload \
  --log-config "$SCRIPT_DIR/log_config.json" || {
  echo ""
  echo "ERROR: Backend exited. Check the output above."
  echo ""
}
read -rp "Press Enter to close..." || true
