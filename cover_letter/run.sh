#!/usr/bin/env bash
# run.sh — Launcher for cover letter generator
# Run from D:\Documents-CV via PowerShell:
#   wsl bash cover_letter/run.sh --url "https://..." --length specific

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

python3 -m pip install -q requests beautifulsoup4 rich

python3 "$SCRIPT_DIR/main.py" "$@"
