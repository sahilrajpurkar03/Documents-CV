#!/usr/bin/env bash
# run_job_search.sh — Launch the job search tool via WSL
# Usage from Windows PowerShell:
#   wsl bash job_search/run_job_search.sh [args...]
#   wsl bash job_search/run_job_search.sh --region Germany
#   wsl bash job_search/run_job_search.sh --company Sereact
#   wsl bash job_search/run_job_search.sh web        # open web UI at http://localhost:5052

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CV_PATH="$(dirname "$SCRIPT_DIR")/main.tex"

echo "Installing / updating dependencies..."
python3 -m pip install -q -r "$SCRIPT_DIR/requirements.txt" || true
python3 -m pip install -q flask || true

echo ""
if [ "$1" = "web" ]; then
  python3 "$SCRIPT_DIR/web.py"
else
  python3 "$SCRIPT_DIR/main.py" --cv "$CV_PATH" "$@"
fi
