#!/usr/bin/env bash
# run_job_search.sh — Launch the job search tool via WSL
# Usage from Windows PowerShell: wsl bash job_search/run_job_search.sh [args...]
# Usage from WSL terminal:       bash job_search/run_job_search.sh [args...]

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CV_PATH="$(dirname "$SCRIPT_DIR")/main.tex"

echo "Installing / updating dependencies..."
python3 -m pip install -q -r "$SCRIPT_DIR/requirements.txt"

echo ""
python3 "$SCRIPT_DIR/main.py" --cv "$CV_PATH" "$@"
