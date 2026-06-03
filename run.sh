#!/usr/bin/env bash
# run.sh — Unified Job Hunt Dashboard
# =====================================
# Starts a single web server at http://localhost:5000 with:
#   🌍 Region Search · 🏢 Company Search · 🤖 Robotics Cos · 📋 Application Log
#   ✉️  Cover Letter generation integrated per job
#
# Usage (from Windows PowerShell):
#   wsl bash run.sh
#
# Usage (Linux / macOS):
#   bash run.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "  ┌────────────────────────────────────────────────────────────────┐"
echo "  │   Job Hunt Dashboard                                           │"
echo "  ├────────────────────────────────────────────────────────────────┤"
echo "  │   Installing / checking Python dependencies…                   │"
echo "  └────────────────────────────────────────────────────────────────┘"
echo ""

python3 - <<'PYCHECK'
import importlib, subprocess, sys
needed = ["flask", "requests", "bs4", "jobspy", "rich"]
missing = [p for p in needed if importlib.util.find_spec(p) is None]
if missing:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q",
        "flask", "requests", "beautifulsoup4", "python-jobspy", "rich"])
PYCHECK

echo ""
echo "  ┌────────────────────────────────────────────────────────────────┐"
echo "  │   Starting server  →  http://localhost:5000                    │"
echo "  │   Press Ctrl+C to stop                                         │"
echo "  └────────────────────────────────────────────────────────────────┘"
echo ""

python3 "$SCRIPT_DIR/web.py"
