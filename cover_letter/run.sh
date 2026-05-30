#!/usr/bin/env bash
# run.sh — Launcher for cover letter generator
# Run from D:\Documents-CV via PowerShell:
#   wsl bash cover_letter/run.sh --url "https://..." --length specific
#   wsl bash cover_letter/run.sh web          # open web UI in browser

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

python3 -m pip install -q requests beautifulsoup4 rich flask

if [ "$1" = "web" ]; then
  python3 "$SCRIPT_DIR/web.py"
else
  python3 "$SCRIPT_DIR/main.py" "$@"
fi
