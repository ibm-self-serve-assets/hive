#!/usr/bin/env bash
# start_backend.sh
# ────────────────
# Starts the spec_1 local backend inside the project venv.
# Creates and populates the venv if it doesn't exist yet.
#
# Usage:
#   cd spec-3-hive-dashboard
#   ./start_backend.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
REQUIREMENTS="$SCRIPT_DIR/requirements.txt"

# ── 1. Create venv (recreate if the interpreter shebang is stale) ────────────
_venv_ok=false
if [ -f "$VENV_DIR/bin/python" ]; then
  # Check the shebang in the venv's pip points at the current venv path.
  # If it references a different directory the venv was created elsewhere and
  # must be rebuilt (common after a folder rename).
  _shebang="$(head -1 "$VENV_DIR/bin/pip" 2>/dev/null || true)"
  if [[ "$_shebang" == *"$VENV_DIR"* ]]; then
    _venv_ok=true
  else
    echo "Venv interpreter path is stale (folder was renamed). Recreating .venv/ ..."
    rm -rf "$VENV_DIR"
  fi
fi
if [ "$_venv_ok" = false ]; then
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
echo "Starting Local Hive Controls Backend on http://localhost:8000 ..."
echo ""
cd "$SCRIPT_DIR"
PYTHONPATH="$SCRIPT_DIR" "$UVICORN" backend.app:app \
  --host localhost --port 8000 --reload \
  --log-config "$SCRIPT_DIR/log_config.json" || {
  echo ""
  echo "ERROR: Backend exited with code $?. Check the output above for details."
  echo ""
}
read -rp "Press Enter to close..." || true
