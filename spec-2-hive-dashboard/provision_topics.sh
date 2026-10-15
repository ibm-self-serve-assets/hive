#!/usr/bin/env bash
# provision_topics.sh
# ───────────────────
# Creates (or verifies) the 6 Confluent Cloud topics for this attendee.
#
# Usage:
#   ./provision_topics.sh
#
# This script:
#   1. Creates (or reuses) a Python venv at .venv/
#   2. Installs requirements.txt into the venv (idempotent, cached by pip)
#   3. Runs provision_topics.py inside that venv using certifi for SSL
#
# Run from the spec-2-hive-dashboard/ directory:
#   cd spec-2-hive-dashboard
#   chmod +x provision_topics.sh
#   ./provision_topics.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
REQUIREMENTS="$SCRIPT_DIR/requirements.txt"
SCRIPT="$SCRIPT_DIR/provision_topics.py"

# ── 1. Create venv if it doesn't exist ───────────────────────────────────────
if [ ! -f "$VENV_DIR/bin/python" ]; then
  echo "Creating virtual environment at .venv/ ..."
  python3 -m venv "$VENV_DIR"
fi

PYTHON="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"

# ── 2. Install / sync requirements ───────────────────────────────────────────
echo "Installing requirements (certifi, confluent-kafka, python-dotenv, ...) ..."
"$PIP" install --quiet --upgrade pip
"$PIP" install --quiet -r "$REQUIREMENTS"

# ── 3. Run the provisioner ───────────────────────────────────────────────────
echo ""
"$PYTHON" "$SCRIPT" "$@"
