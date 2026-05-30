"""
Job Search Web Server
=====================
Flask REST API + SPA at http://localhost:5052

Routes:
  GET  /                         -> serve index.html
  GET  /api/regions              -> list available regions
  GET  /api/job-files            -> list existing jobs_*.csv files
  GET  /api/jobs?file=<name>     -> parse CSV, return job list
  POST /api/search               -> run region search (SSE streaming progress)
  POST /api/search-company       -> search a specific company
"""

from __future__ import annotations

import csv
import json
import sys
import threading
import webbrowser
from pathlib import Path

_DIR  = Path(__file__).parent
_ROOT = _DIR.parent

if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))

try:
    from flask import Flask, jsonify, request, send_from_directory, Response, stream_with_context
except ImportError:
    print("[ERROR] Flask not installed. Run: pip install flask"); sys.exit(1)

from searcher import REGIONS, DEFAULT_SEARCH_TERMS, search_jobs, search_company
from scorer   import rank_listings, score_label
from cv_parser import parse_cv

app = Flask(__name__)

_CV_PATH = str(_ROOT / "main.tex")

def _load_cv():
    return parse_cv(_CV_PATH)

# ── Serve SPA ─────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(str(_DIR), "index.html")

# ── Regions ────────────────────────────────────────────────────────────────
@app.route("/api/regions")
def api_regions():
    return jsonify([
        {"name": k, "flag": v["flag"]}
        for k, v in REGIONS.items()
    ])

# ── List existing result files ─────────────────────────────────────────────
@app.route("/api/job-files")
def api_job_files():
    files = sorted(_ROOT.glob("jobs_*.csv"), reverse=True)
    return jsonify([f.name for f in files])

# ── Parse a CSV ────────────────────────────────────────────────────────────
@app.route("/api/jobs")
def api_jobs():
    filename = request.args.get("file", "").strip()
    if not filename or "/" in filename or "\\" in filename or not filename.startswith("jobs_"):
        return jsonify({"error": "Invalid filename"}), 400
    path = _ROOT / filename
    if not path.exists():
        return jsonify({"error": "File not found"}), 404
    jobs = []
    with open(path, encoding="utf-8", newline="") as f:
        for i, row in enumerate(csv.DictReader(f), 1):
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

# ── Region search (streaming SSE so browser sees live progress) ────────────
@app.route("/api/search", methods=["POST"])
def api_search():
    data       = request.json or {}
    region     = data.get("region", "Germany")
    top_n      = int(data.get("top_n", 40))
    per_term   = int(data.get("per_term", 15))
    hours_old  = int(data.get("hours_old", 504))
    sites      = data.get("sites") or ["linkedin","indeed","glassdoor","google"]

    if region not in REGIONS:
        return jsonify({"error": f"Unknown region '{region}'"}), 400

    def generate():
        def send(msg_type, payload):
            yield f"data: {json.dumps({'type': msg_type, **payload})}\n\n"

        yield from send("status", {"text": f"Parsing CV..."})
        try:
            cv = _load_cv()
        except Exception as e:
            yield from send("error", {"text": str(e)}); return

        yield from send("status", {"text": f"Searching {region} across {', '.join(sites)}..."})

        listings = []
        errors   = []
        for term in DEFAULT_SEARCH_TERMS:
            yield from send("progress", {"text": f'Searching: "{term}"'})
            try:
                batch = search_jobs(
                    region_name=region,
                    search_terms=[term],
                    results_per_term=per_term,
                    sites=sites,
                    hours_old=hours_old,
                    verbose=False,
                )
                listings.extend(batch)
            except Exception as e:
                errors.append(str(e))

        yield from send("status", {"text": f"Scoring {len(listings)} listings..."})
        ranked = rank_listings(listings, cv, top_n=top_n)

        # Save CSV
        from datetime import datetime as _dt
        ts   = _dt.now().strftime("%Y%m%d_%H%M")
        slug = region.lower()
        csv_file = _ROOT / f"jobs_{slug}_{ts}.csv"
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "score","match_quality","title","company","location",
                "source","date_posted","salary","matched_keywords","url",
            ])
            writer.writeheader()
            for j in ranked:
                row = j.to_dict()
                row["match_quality"] = score_label(j.score)
                writer.writerow(row)

        jobs_out = []
        for i, j in enumerate(ranked, 1):
            jobs_out.append({
                "rank": i, "score": round(j.score, 1),
                "match_quality": score_label(j.score),
                "title": j.title, "company": j.company,
                "location": j.location, "source": j.source,
                "date_posted": j.date_posted, "salary": j.salary,
                "matched_keywords": ", ".join(j.matched_keywords[:8]),
                "url": j.url,
            })
        yield from send("done", {"jobs": jobs_out, "csv_file": csv_file.name,
                                  "total": len(listings), "errors": errors})

    return Response(stream_with_context(generate()),
                    mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Company search ─────────────────────────────────────────────────────────
@app.route("/api/search-company", methods=["POST"])
def api_search_company():
    data         = request.json or {}
    company_name = (data.get("company") or "").strip()
    region       = data.get("region", "Germany")
    top_n        = int(data.get("top_n", 40))
    sites        = data.get("sites") or ["linkedin","indeed","glassdoor","google"]

    if not company_name:
        return jsonify({"error": "Company name required"}), 400
    if region not in REGIONS:
        region = "Germany"

    def generate():
        def send(msg_type, payload):
            yield f"data: {json.dumps({'type': msg_type, **payload})}\n\n"

        yield from send("status", {"text": f"Parsing CV..."})
        try:
            cv = _load_cv()
        except Exception as e:
            yield from send("error", {"text": str(e)}); return

        yield from send("status", {"text": f"Searching all roles at {company_name}..."})
        try:
            listings = search_company(
                company_name=company_name,
                region_name=region,
                results=top_n,
                sites=sites,
                verbose=False,
            )
        except Exception as e:
            yield from send("error", {"text": str(e)}); return

        yield from send("status", {"text": f"Scoring {len(listings)} listings..."})
        ranked = rank_listings(listings, cv, top_n=top_n)

        # Save CSV
        from datetime import datetime as _dt
        ts   = _dt.now().strftime("%Y%m%d_%H%M")
        slug = company_name.lower().replace(" ", "_")
        csv_file = _ROOT / f"jobs_{slug}_{ts}.csv"
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "score","match_quality","title","company","location",
                "source","date_posted","salary","matched_keywords","url",
            ])
            writer.writeheader()
            for j in ranked:
                row = j.to_dict()
                row["match_quality"] = score_label(j.score)
                writer.writerow(row)

        jobs_out = []
        for i, j in enumerate(ranked, 1):
            jobs_out.append({
                "rank": i, "score": round(j.score, 1),
                "match_quality": score_label(j.score),
                "title": j.title, "company": j.company,
                "location": j.location, "source": j.source,
                "date_posted": j.date_posted, "salary": j.salary,
                "matched_keywords": ", ".join(j.matched_keywords[:8]),
                "url": j.url,
            })
        yield from send("done", {"jobs": jobs_out, "csv_file": csv_file.name,
                                  "total": len(listings)})

    return Response(stream_with_context(generate()),
                    mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Launch ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    threading.Thread(
        target=lambda: __import__("time").sleep(1.2) or webbrowser.open("http://localhost:5052"),
        daemon=True,
    ).start()
    print("\n  Job Search Web UI  ->  http://localhost:5052")
    print("  Press Ctrl+C to stop\n")
    app.run(host="127.0.0.1", port=5052, debug=False, threaded=True)
