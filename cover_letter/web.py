"""
Cover Letter Web Server
=======================
Flask REST API + serves the SPA at http://localhost:5051

Routes:
  GET  /                          -> serve index.html
  GET  /api/job-files             -> list jobs_*.csv files available
  GET  /api/jobs?file=<name>      -> parse CSV, return job list
  POST /api/generate              -> generate cover letter text + save files
"""

from __future__ import annotations

import csv
import sys
import threading
import webbrowser
from pathlib import Path

_DIR  = Path(__file__).parent            # cover_letter/
_ROOT = _DIR.parent                      # D:/Documents-CV  (WSL: /mnt/d/Documents-CV)

if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))

try:
    from flask import Flask, jsonify, request, send_from_directory
except ImportError:
    print("[ERROR] Flask not found.  Run:  pip install flask")
    sys.exit(1)

from job_fetcher import fetch_job
from generator   import generate

app = Flask(__name__)

# ── Serve the SPA ──────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(str(_DIR), "index.html")

# ── List available job CSV files ───────────────────────────────────────────
@app.route("/api/job-files")
def list_job_files():
    files = sorted(_ROOT.glob("jobs_*.csv"), reverse=True)
    return jsonify([f.name for f in files])

# ── Parse a CSV and return job list ───────────────────────────────────────
@app.route("/api/jobs")
def get_jobs():
    filename = request.args.get("file", "").strip()
    # Security: prevent path traversal
    if not filename or "/" in filename or "\\" in filename or not filename.startswith("jobs_"):
        return jsonify({"error": "Invalid filename"}), 400
    path = _ROOT / filename
    if not path.exists():
        return jsonify({"error": "File not found"}), 404

    jobs = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, 1):
            jobs.append({
                "rank":             i,
                "score":            row.get("score", ""),
                "match_quality":    row.get("match_quality", ""),
                "title":            row.get("title", ""),
                "company":          row.get("company", ""),
                "location":         row.get("location", ""),
                "source":           row.get("source", ""),
                "date_posted":      row.get("date_posted", ""),
                "salary":           row.get("salary", ""),
                "matched_keywords": row.get("matched_keywords", ""),
                "url":              row.get("url", ""),
            })
    return jsonify(jobs)

# ── Generate cover letter ──────────────────────────────────────────────────
@app.route("/api/generate", methods=["POST"])
def generate_letter():
    data = request.json or {}

    url          = (data.get("url")          or "").strip()
    title        = (data.get("title")        or "").strip()
    company      = (data.get("company")      or "").strip()
    location     = (data.get("location")     or "").strip()
    keywords_raw = (data.get("matched_keywords") or "").strip()
    mode         = (data.get("mode")         or "specific").strip()
    availability = (data.get("availability") or "1 October 2026").strip()
    ref          = (data.get("ref")          or "").strip()

    if mode not in ("general", "specific"):
        mode = "specific"

    keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]

    job = {
        "title":       title,
        "company":     company,
        "location":    location,
        "keywords":    keywords,
        "description": "",
        "url":         url,
    }

    # Try to enrich from local HTML cache or web if URL provided
    if url:
        fetched = fetch_job(url, _ROOT)
        if fetched:
            if not title:
                job["title"]       = fetched.get("title", title)
            if not company:
                job["company"]     = fetched.get("company", company)
            if not location:
                job["location"]    = fetched.get("location", location)
            if not keywords:
                job["keywords"]    = fetched.get("keywords", [])
            job["description"]     = fetched.get("description", "")

    if not job["title"] or not job["company"]:
        return jsonify({"error": "Could not determine job title or company. Provide them manually."}), 400

    output_dir = _ROOT / "cover_letters"
    result = generate(job, mode, availability, ref, output_dir)

    text = result["txt"].read_text(encoding="utf-8")

    return jsonify({
        "text":       text,
        "saved_txt":  str(result["txt"]),
        "saved_tex":  str(result["tex"]),
        "saved_pdf":  str(result["pdf"]) if result.get("pdf") else None,
        "base_name":  result["base_name"],
    })


# ── Launch ─────────────────────────────────────────────────────────────────
def _open_browser():
    import time
    time.sleep(1.2)
    webbrowser.open("http://localhost:5051")


if __name__ == "__main__":
    threading.Thread(target=_open_browser, daemon=True).start()
    print()
    print("  Cover Letter Web UI  ->  http://localhost:5051")
    print("  Press Ctrl+C to stop")
    print()
    app.run(host="127.0.0.1", port=5051, debug=False)
