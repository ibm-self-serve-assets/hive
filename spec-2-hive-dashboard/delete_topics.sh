#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt

.venv/bin/python delete_topics.py "$@" || true

echo ""
read -rp "Press Enter to close..." || true
