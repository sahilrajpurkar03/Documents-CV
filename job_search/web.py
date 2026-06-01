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

from searcher import REGIONS, search_jobs, search_company, build_search_terms_from_cv, deduplicate_by_title
from scorer   import rank_listings, score_label, is_relevant
from cv_parser import parse_cv

app = Flask(__name__)

_CV_PATH  = str(_ROOT / "main.tex")
_LOG_FILE = _ROOT / "log" / "applications.json"

def _load_cv():
    return parse_cv(_CV_PATH)

def _applied_set():
    """Return (applied_urls, applied_keys) from the log.
    applied_urls — set of job URLs already logged
    applied_keys — set of (company_lower, title_lower_normalised) pairs
    """
    applied_urls: set = set()
    applied_keys: set = set()
    if not _LOG_FILE.exists():
        return applied_urls, applied_keys
    try:
        entries = json.loads(_LOG_FILE.read_text(encoding="utf-8"))
        for e in entries:
            u = (e.get("url") or "").strip()
            if u:
                applied_urls.add(u)
            co = (e.get("company") or "").strip().lower()
            ti = (e.get("title")   or "").strip().lower()
            # strip gender suffixes like (m/f/d)
            import re as _re
            ti = _re.sub(r'\s*\([mfwd\/]+\)', '', ti).strip()
            if co and ti:
                applied_keys.add((co, ti))
    except Exception:
        pass
    return applied_urls, applied_keys

def _is_applied(job: dict, applied_urls: set, applied_keys: set) -> bool:
    url = (job.get("url") or "").strip()
    if url and url in applied_urls:
        return True
    co  = (job.get("company") or "").strip().lower()
    import re as _re
    ti  = _re.sub(r'\s*\([mfwd\/]+\)', '', (job.get("title") or "").strip().lower())
    return bool(co and ti and (co, ti) in applied_keys)

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
    applied_urls, applied_keys = _applied_set()
    jobs = []
    with open(path, encoding="utf-8", newline="") as f:
        for i, row in enumerate(csv.DictReader(f), 1):
            job = {
                "rank":             row.get("rank", i),
                "score":            row.get("score", ""),
                "match_quality":    row.get("match_quality", ""),
                "title":            row.get("title", ""),
                "company":          row.get("company", ""),
                "location":         row.get("location", ""),
                "source":           row.get("source", ""),
                "job_type":         row.get("job_type", ""),
                "date_posted":      row.get("date_posted", ""),
                "salary":           row.get("salary", ""),
                "matched_keywords": row.get("matched_keywords", ""),
                "url":              row.get("url", ""),
            }
            job["applied"] = _is_applied(job, applied_urls, applied_keys)
            jobs.append(job)
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

        search_terms = build_search_terms_from_cv(cv)
        progress_log = []

        def on_prog(term: str):
            progress_log.append(term)

        yield from send("status", {"text": f"Launching {len(search_terms)} parallel searches (max 4 threads)..."})

        # Run all terms in parallel — dedup happens after all complete
        from concurrent.futures import ThreadPoolExecutor, as_completed as _as_completed
        listings_raw: List = []
        seen_urls: set = set()
        errors: List[str] = []

        try:
            from searcher import _scrape_one_term
            region_cfg = REGIONS[region]
            def _run(term):
                return _scrape_one_term(
                    term=term,
                    sites=sites,
                    location_str=region_cfg["cities"][0],
                    results_per_term=per_term,
                    hours_old=hours_old,
                    country_indeed=region_cfg["country_indeed"],
                    verbose=False,
                    region_flag=region_cfg["flag"],
                )
            with ThreadPoolExecutor(max_workers=4) as ex:
                futs = {ex.submit(_run, t): t for t in search_terms}
                done = 0
                for fut in _as_completed(futs):
                    term = futs[fut]
                    done += 1
                    try:
                        batch = fut.result()
                        new = 0
                        for listing in batch:
                            if listing.url and listing.url not in seen_urls:
                                seen_urls.add(listing.url)
                                listings_raw.append(listing)
                                new += 1
                            elif not listing.url:
                                listings_raw.append(listing)
                                new += 1
                        yield from send("progress", {"text": f'[{done}/{len(search_terms)}] "{term}" → {new} new jobs'})
                    except Exception as e:
                        errors.append(str(e))
                        yield from send("progress", {"text": f'[{done}/{len(search_terms)}] "{term}" → error'})
        except Exception as e:
            yield from send("error", {"text": str(e)}); return

        # Cross-search deduplication
        listings = deduplicate_by_title(listings_raw)
        relevant = [j for j in listings if is_relevant(j)]
        yield from send("status", {"text": f"Scoring {len(relevant)}/{len(listings)} relevant listings..."})
        ranked = rank_listings(listings, cv, top_n=top_n)

        # Save CSV
        from datetime import datetime as _dt
        ts   = _dt.now().strftime("%Y%m%d_%H%M")
        slug = region.lower()
        csv_file = _ROOT / f"jobs_{slug}_{ts}.csv"
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "rank","score","match_quality","title","company","location",
                "source","job_type","date_posted","salary","matched_keywords","url",
            ])
            writer.writeheader()
            for i, j in enumerate(ranked, 1):
                row = j.to_dict()
                row["match_quality"] = score_label(j.score)
                row["rank"] = i
                writer.writerow(row)

        applied_urls, applied_keys = _applied_set()
        jobs_out = []
        for i, j in enumerate(ranked, 1):
            jd = {
                "rank": i, "score": round(j.score, 1),
                "match_quality": score_label(j.score),
                "title": j.title, "company": j.company,
                "location": j.location, "source": j.source,
                "job_type": j.job_type, "date_posted": j.date_posted,
                "salary": j.salary,
                "matched_keywords": ", ".join(j.matched_keywords[:10]),
                "url": j.url,
                "score_breakdown": getattr(j, "_score_breakdown", {}),
            }
            jd["applied"] = _is_applied(jd, applied_urls, applied_keys)
            jobs_out.append(jd)
        yield from send("done", {
            "jobs": jobs_out, "csv_file": csv_file.name,
            "total": len(listings_raw), "unique": len(listings),
            "relevant": len(relevant), "errors": errors,
        })

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

        yield from send("status", {"text": f"Searching all roles at {company_name} (3 variants)..."})
        try:
            listings = search_company(
                company_name=company_name,
                region_name=region,
                results=top_n,
                sites=sites,
                verbose=True,
            )
        except Exception as e:
            yield from send("error", {"text": str(e)}); return

        yield from send("progress", {"text": f"Found {len(listings)} listings — scoring..."})
        ranked = rank_listings(listings, cv, top_n=top_n)

        # Save CSV
        from datetime import datetime as _dt
        ts   = _dt.now().strftime("%Y%m%d_%H%M")
        slug = company_name.lower().replace(" ", "_")
        csv_file = _ROOT / f"jobs_{slug}_{ts}.csv"
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "rank","score","match_quality","title","company","location",
                "source","job_type","date_posted","salary","matched_keywords","url",
            ])
            writer.writeheader()
            for i, j in enumerate(ranked, 1):
                row = j.to_dict()
                row["match_quality"] = score_label(j.score)
                row["rank"] = i
                writer.writerow(row)

        applied_urls, applied_keys = _applied_set()
        jobs_out = []
        for i, j in enumerate(ranked, 1):
            jd = {
                "rank": i, "score": round(j.score, 1),
                "match_quality": score_label(j.score),
                "title": j.title, "company": j.company,
                "location": j.location, "source": j.source,
                "job_type": j.job_type, "date_posted": j.date_posted,
                "salary": j.salary,
                "matched_keywords": ", ".join(j.matched_keywords[:10]),
                "url": j.url,
                "score_breakdown": getattr(j, "_score_breakdown", {}),
            }
            jd["applied"] = _is_applied(jd, applied_urls, applied_keys)
            jobs_out.append(jd)
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
