#!/usr/bin/env bash
# run.sh — Launcher for job application log
# Usage from PowerShell:
#   wsl bash log/run.sh              # interactive dashboard
#   wsl bash log/run.sh add          # log new application
#   wsl bash log/run.sh update 5     # update application #5
#   wsl bash log/run.sh list --active
#   wsl bash log/run.sh web          # open web UI in browser

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 -m pip install -q rich flask

if [ "$1" = "web" ]; then
  python3 "$SCRIPT_DIR/web.py"
else
  python3 "$SCRIPT_DIR/main.py" "$@"
fi
