"""Unified Job Hunt Dashboard — web.py
=====================================
Single Flask server at http://localhost:5000

Merges:
  job_search/web.py     — job scraping, ranking, streaming SSE
  cover_letter/web.py   — cover letter generation + PDF compilation
  log/web.py            — application tracking

Routes:
  GET  /                              → serve index.html
  GET  /api/regions                   → available search regions
  GET  /api/job-files                 → list saved jobs_*.csv files
  GET  /api/jobs?file=                → parse a CSV file
  POST /api/search                    → region job search (SSE)
  POST /api/search-company            → company job search (SSE)
  GET  /api/robotics-companies        → robotics company catalogue
  POST /api/search-robotics-companies → robotics career page scan (SSE)
  POST /api/generate                  → generate cover letter text + LaTeX
  POST /api/save-letter               → write cl_sahil.tex + compile PDF
  GET  /api/statuses                  → application status list
  GET  /api/applications              → list all logged applications
  POST /api/applications              → add a new application
  GET  /api/applications/<id>         → get one application
  PATCH /api/applications/<id>        → update status / notes
  DELETE /api/applications/<id>       → delete an application
  GET  /api/summary                   → pipeline counts per status
  GET  /api/config                    → name from CV
  GET  /api/fetch-job?url=            → scrape job info from URL
"""

from __future__ import annotations

import csv
import json
import re
import sys
import threading
import webbrowser
from pathlib import Path
from typing import List

_ROOT = Path(__file__).parent

# ── Add all sub-module directories to import path ──────────────────────────
for _sub in ("job_search", "cover_letter", "log"):
    _p = str(_ROOT / _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from flask import (Flask, jsonify, request, send_from_directory,
                       Response, stream_with_context)
except ImportError:
    print("[ERROR] Flask not installed. Run: pip install flask")
    sys.exit(1)

# ── Job search imports ─────────────────────────────────────────────────────
from searcher import (
    REGIONS, build_search_terms_from_cv, deduplicate_by_title,
    ROBOTICS_COMPANIES, _scrape_one_term, _scrape_greenhouse, _scrape_lever,
    search_company,
)
from scorer    import rank_listings, score_label, is_relevant
from cv_parser import parse_cv

# ── Cover letter imports ───────────────────────────────────────────────────
from generator   import render_text, render_latex, compile_pdf
from job_fetcher import fetch_job

# ── Log / tracker imports ──────────────────────────────────────────────────
from tracker import (
    STATUSES, STATUS_EMOJI,
    load_db, add_entry, update_status, update_notes,
    delete_entry, get_entry, filter_entries, pending_count,
)

app = Flask(__name__)

_CV_PATH  = str(_ROOT / "main.tex")
_LOG_FILE = _ROOT / "log" / "applications.json"
_CL_TEX   = _ROOT / "cl_sahil.tex"   # canonical cover letter file

# ── Helpers ────────────────────────────────────────────────────────────────

def _load_cv():
    return parse_cv(_CV_PATH)


def _applied_set():
    """Return (applied_urls, applied_keys) from the log."""
    applied_urls: set = set()
    applied_keys: set = set()
    if not _LOG_FILE.exists():
        return applied_urls, applied_keys
    try:
        for e in json.loads(_LOG_FILE.read_text(encoding="utf-8")):
            # Don't exclude 'saved' jobs — only exclude actively tracked ones
            if (e.get("status") or "") == "saved":
                continue
            u = (e.get("url") or "").strip()
            if u:
                applied_urls.add(u)
            co = (e.get("company") or "").strip().lower()
            ti = re.sub(r'\s*\([mfwd\/]+\)', '',
                        (e.get("title") or "").strip().lower())
            if co and ti:
                applied_keys.add((co, ti))
    except Exception:
        pass
    return applied_urls, applied_keys


def _is_applied(job: dict, applied_urls: set, applied_keys: set) -> bool:
    url = (job.get("url") or "").strip()
    if url and url in applied_urls:
        return True
    co = (job.get("company") or "").strip().lower()
    ti = re.sub(r'\s*\([mfwd\/]+\)', '', (job.get("title") or "").strip().lower())
    return bool(co and ti and (co, ti) in applied_keys)


def _job_out(j, rank: int) -> dict:
    """Convert a ranked JobListing to a serialisable dict."""
    d = j.to_dict()
    d.update({
        "rank":            rank,
        "match_quality":   score_label(j.score),
        "applied":         False,
        "score_breakdown": getattr(j, "_score_breakdown", {}),
    })
    return d


def _send(msg_type: str, payload: dict) -> str:
    return f"data: {json.dumps({'type': msg_type, **payload})}\n\n"


# ── SPA ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(str(_ROOT), "index.html")


# ══════════════════════════ JOB SEARCH ════════════════════════════════════

@app.route("/api/regions")
def api_regions():
    return jsonify([{"name": k, "flag": v["flag"]} for k, v in REGIONS.items()])


@app.route("/api/job-files")
def api_job_files():
    return jsonify([f.name for f in sorted(_ROOT.glob("jobs_*.csv"), reverse=True)])


@app.route("/api/jobs")
def api_jobs():
    fn = request.args.get("file", "").strip()
    if not fn or "/" in fn or "\\" in fn or not fn.startswith("jobs_"):
        return jsonify({"error": "Invalid filename"}), 400
    path = _ROOT / fn
    if not path.exists():
        return jsonify({"error": "File not found"}), 404
    applied_urls, applied_keys = _applied_set()
    jobs = []
    with open(path, encoding="utf-8", newline="") as f:
        for i, row in enumerate(csv.DictReader(f), 1):
            job = {k: row.get(k, "") for k in [
                "rank", "score", "match_quality", "title", "company",
                "location", "source", "job_type", "date_posted",
                "salary", "matched_keywords", "url",
            ]}
            job["rank"]    = job["rank"] or i
            job["applied"] = _is_applied(job, applied_urls, applied_keys)
            jobs.append(job)
    return jsonify(jobs)


# ── Region search (SSE) ────────────────────────────────────────────────────

@app.route("/api/search", methods=["POST"])
def api_search():
    data      = request.json or {}
    region    = data.get("region", "Germany")
    top_n     = int(data.get("top_n", 40))
    per_term  = int(data.get("per_term", 15))
    hours_old = int(data.get("hours_old", 504))
    sites     = data.get("sites") or ["linkedin", "indeed", "google", "stepstone", "xing"]

    if region not in REGIONS:
        return jsonify({"error": f"Unknown region '{region}'"}), 400

    def stream():
        yield _send("status", {"text": "Parsing CV…"})
        try:
            cv = _load_cv()
        except Exception as e:
            yield _send("error", {"text": str(e)}); return

        region_cfg   = REGIONS[region]
        search_terms = build_search_terms_from_cv(cv)
        yield _send("status", {"text": f"Launching {len(search_terms)} searches "
                               f"({region}, {', '.join(sites)})…"})

        from concurrent.futures import ThreadPoolExecutor, as_completed as _asc
        listings_raw: List = []
        seen_urls:    set  = set()
        errors:       List = []

        def _run(term):
            return _scrape_one_term(
                term=term, sites=sites,
                location_str=region_cfg["cities"][0],
                results_per_term=per_term, hours_old=hours_old,
                country_indeed=region_cfg["country_indeed"],
                verbose=False, region_flag=region_cfg["flag"],
            )

        with ThreadPoolExecutor(max_workers=4) as ex:
            futs = {ex.submit(_run, t): t for t in search_terms}
            done = 0
            for fut in _asc(futs):
                term = futs[fut]; done += 1
                try:
                    new = 0
                    for listing in fut.result():
                        if not listing.url or listing.url not in seen_urls:
                            if listing.url:
                                seen_urls.add(listing.url)
                            listings_raw.append(listing)
                            new += 1
                    yield _send("progress", {"text": f'[{done}/{len(search_terms)}] '
                                                     f'"{term}" → {new} new'})
                except Exception as e:
                    errors.append(str(e))
                    yield _send("progress", {"text": f'[{done}/{len(search_terms)}] '
                                                     f'"{term}" → error'})

        listings       = deduplicate_by_title(listings_raw)
        applied_urls, applied_keys = _applied_set()
        fresh          = [j for j in listings
                          if not _is_applied(j.to_dict(), applied_urls, applied_keys)]
        applied_excl   = len(listings) - len(fresh)
        relevant       = [j for j in fresh if is_relevant(j)]
        excl           = f" ({applied_excl} applied excluded)" if applied_excl else ""
        yield _send("status", {"text": f"Scoring {len(relevant)}/{len(fresh)} relevant{excl}…"})

        ranked = rank_listings(fresh, cv, top_n=top_n)
        yield _send("done", {
            "jobs":             [_job_out(j, i) for i, j in enumerate(ranked, 1)],
            "total":            len(listings_raw),
            "unique":           len(listings),
            "relevant":         len(relevant),
            "applied_excluded": applied_excl,
            "errors":           errors,
        })

    return Response(stream_with_context(stream()),
                    mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Company search (SSE) ───────────────────────────────────────────────────

@app.route("/api/search-company", methods=["POST"])
def api_search_company():
    data         = request.json or {}
    company_name = (data.get("company") or "").strip()
    region       = data.get("region", "Germany")
    top_n        = int(data.get("top_n", 40))
    sites        = data.get("sites") or ["linkedin", "indeed", "google", "stepstone", "xing"]

    if not company_name:
        return jsonify({"error": "Company name required"}), 400
    if region not in REGIONS:
        region = "Germany"

    def stream():
        yield _send("status", {"text": "Parsing CV…"})
        try:
            cv = _load_cv()
        except Exception as e:
            yield _send("error", {"text": str(e)}); return

        yield _send("status", {"text": f"Searching all roles at {company_name}…"})
        try:
            listings = search_company(company_name=company_name, region_name=region,
                                      results=top_n, sites=sites, verbose=True)
        except Exception as e:
            yield _send("error", {"text": str(e)}); return

        applied_urls, applied_keys = _applied_set()
        fresh      = [j for j in listings
                      if not _is_applied(j.to_dict(), applied_urls, applied_keys)]
        applied_excl = len(listings) - len(fresh)
        excl         = f" ({applied_excl} excluded)" if applied_excl else ""
        yield _send("progress", {"text": f"Found {len(fresh)} fresh listings{excl} — scoring…"})

        ranked = rank_listings(fresh, cv, top_n=top_n)
        yield _send("done", {
            "jobs":             [_job_out(j, i) for i, j in enumerate(ranked, 1)],
            "total":            len(listings),
            "applied_excluded": applied_excl,
        })

    return Response(stream_with_context(stream()),
                    mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Robotics companies catalogue ───────────────────────────────────────────

@app.route("/api/robotics-companies")
def api_robotics_companies():
    country   = request.args.get("country", "All").strip()
    companies = ROBOTICS_COMPANIES
    if country and country != "All":
        companies = [c for c in companies if c.get("country") == country]
    return jsonify(companies)


# ── Robotics companies batch career-page scan (SSE) ────────────────────────

@app.route("/api/search-robotics-companies", methods=["POST"])
def api_search_robotics_companies():
    data    = request.json or {}
    country = (data.get("country") or "All").strip()
    top_n   = int(data.get("top_n", 40))

    def stream():
        yield _send("status", {"text": "Parsing CV…"})
        try:
            cv = _load_cv()
        except Exception as e:
            yield _send("error", {"text": str(e)}); return

        companies = ROBOTICS_COMPANIES
        if country and country != "All":
            companies = [c for c in companies if c.get("country") == country]

        yield _send("status", {"text": f"Scanning {len(companies)} robotics company career pages…"})

        all_listings: List = []
        seen_urls:    set  = set()

        for co in companies:
            name = co["name"]
            ats  = co.get("ats")
            slug = co.get("slug", "")

            yield _send("progress", {"text": f"🔍 {name} ({co.get('country', '')})…"})
            batch: List = []

            if ats == "greenhouse" and slug:
                batch = _scrape_greenhouse(slug, 40)
                for j in batch:
                    j.company = name
                if not batch:
                    try:
                        batch = search_company(name, "Germany", 20,
                                               ["linkedin", "indeed", "google"], verbose=False)
                    except Exception:
                        pass

            elif ats == "lever" and slug:
                batch = _scrape_lever(slug, 40)
                for j in batch:
                    j.company = name
                if not batch:
                    try:
                        batch = search_company(name, "Germany", 20,
                                               ["linkedin", "indeed", "google"], verbose=False)
                    except Exception:
                        pass
            else:
                try:
                    batch = search_company(name, "Germany", 20,
                                           ["linkedin", "indeed", "google"], verbose=False)
                except Exception:
                    pass

            added = 0
            for listing in batch:
                if listing.url and listing.url not in seen_urls:
                    seen_urls.add(listing.url)
                    all_listings.append(listing)
                    added += 1
                elif not listing.url:
                    all_listings.append(listing)
                    added += 1
            yield _send("progress", {"text": f"   → {added} jobs at {name}"})

        listings     = deduplicate_by_title(all_listings)
        applied_urls, applied_keys = _applied_set()
        fresh        = [j for j in listings
                        if not _is_applied(j.to_dict(), applied_urls, applied_keys)]
        applied_excl = len(listings) - len(fresh)
        relevant     = [j for j in fresh if is_relevant(j)]
        excl         = f" ({applied_excl} excluded)" if applied_excl else ""
        yield _send("status", {"text": f"Scoring {len(relevant)}/{len(fresh)} relevant{excl}…"})

        ranked = rank_listings(fresh, cv, top_n=top_n)
        yield _send("done", {
            "jobs":             [_job_out(j, i) for i, j in enumerate(ranked, 1)],
            "total":            len(all_listings),
            "unique":           len(listings),
            "relevant":         len(relevant),
            "applied_excluded": applied_excl,
        })

    return Response(stream_with_context(stream()),
                    mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ══════════════════════════ COVER LETTER ══════════════════════════════════

@app.route("/api/generate", methods=["POST"])
def api_generate():
    data         = request.json or {}
    url          = (data.get("url")              or "").strip()
    title        = (data.get("title")            or "").strip()
    company      = (data.get("company")          or "").strip()
    location     = (data.get("location")         or "").strip()
    keywords_raw = (data.get("matched_keywords") or "").strip()
    mode         = (data.get("mode")             or "specific").strip()
    availability = (data.get("availability")     or "1 October 2026").strip()
    ref          = (data.get("ref")              or "").strip()

    if mode not in ("general", "specific"):
        mode = "specific"

    keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]
    job = {
        "title": title, "company": company, "location": location,
        "keywords": keywords, "description": "", "url": url,
    }

    if url:
        try:
            fetched = fetch_job(url, _ROOT)
            if fetched:
                if not title:    job["title"]       = fetched.get("title", title)
                if not company:  job["company"]     = fetched.get("company", company)
                if not location: job["location"]    = fetched.get("location", location)
                if not keywords: job["keywords"]    = fetched.get("keywords", [])
                job["description"] = fetched.get("description", "")
        except Exception:
            pass

    if not job["title"] or not job["company"]:
        return jsonify({"error": "Could not determine job title or company. "
                                 "Provide them manually."}), 400

    # Generate content but do NOT write to disk — leave that to /api/save-letter
    text = render_text(job, mode, availability, ref)
    tex  = render_latex(job, mode, availability, ref)

    return jsonify({
        "text":    text,
        "tex":     tex,
        "title":   job["title"],
        "company": job["company"],
    })


@app.route("/api/save-letter", methods=["POST"])
def api_save_letter():
    data        = request.json or {}
    tex_content = data.get("tex", "")
    if not tex_content:
        return jsonify({"error": "No LaTeX content provided"}), 400

    try:
        _CL_TEX.write_text(tex_content, encoding="utf-8")
    except Exception as e:
        return jsonify({"error": f"Could not write {_CL_TEX.name}: {e}"}), 500

    pdf = compile_pdf(_CL_TEX)
    return jsonify({
        "saved_tex": _CL_TEX.name,
        "saved_pdf": _CL_TEX.with_suffix(".pdf").name if pdf else None,
        "compiled":  pdf is not None,
    })


# ══════════════════════════ APPLICATION LOG ════════════════════════════════

@app.route("/api/statuses")
def api_statuses():
    return jsonify([{"value": s, "emoji": STATUS_EMOJI.get(s, "")} for s in STATUSES])


@app.route("/api/export-csv", methods=["POST"])
def api_export_csv():
    data     = request.get_json(force=True)
    filename = (data.get("filename") or "jobs_export.csv").strip()
    content  = data.get("content", "")
    # Sanitise filename — allow only safe chars
    import re as _re
    filename = _re.sub(r'[^\w\-.]', '_', filename)
    if not filename.endswith('.csv'):
        filename += '.csv'
    dest = _ROOT / filename
    try:
        dest.write_text(content, encoding="utf-8")
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"path": str(dest), "filename": filename})


@app.route("/api/applied-set")
def api_applied_set():
    """Return the sets of URLs and (company, title) keys that are in the log
    (excluding 'saved' status), for the client to mark jobs already applied to."""
    applied_urls: set[str] = set()
    applied_keys: list[list[str]] = []
    try:
        for e in json.loads(_LOG_FILE.read_text(encoding="utf-8")):
            if (e.get("status") or "") == "saved":
                continue
            u = (e.get("url") or "").strip()
            if u:
                applied_urls.add(u)
            co = (e.get("company") or "").strip().lower()
            ti = re.sub(r'\s*\([mfwd\/]+\)', '',
                        (e.get("title") or "").strip().lower())
            if co and ti:
                applied_keys.append([co, ti])
    except Exception:
        pass
    return jsonify({"urls": list(applied_urls), "keys": applied_keys})


@app.route("/api/applications", methods=["GET"])
def api_list():
    status  = request.args.get("status")
    active  = request.args.get("active") == "1"
    company = request.args.get("company")
    return jsonify(filter_entries(status=status, active_only=active, company=company))


@app.route("/api/applications", methods=["POST"])
def api_add():
    data  = request.get_json(force=True)
    entry = add_entry(
        title    = data.get("title",    ""),
        company  = data.get("company",  ""),
        url      = data.get("url",      ""),
        location = data.get("location", ""),
        source   = data.get("source",   ""),
        notes    = data.get("notes",    ""),
        status   = data.get("status",   "applied"),
    )
    return jsonify(entry), 201


@app.route("/api/applications/<int:entry_id>", methods=["GET"])
def api_detail(entry_id):
    entry = get_entry(entry_id)
    if not entry:
        return jsonify({"error": "Not found"}), 404
    return jsonify(entry)


@app.route("/api/applications/<int:entry_id>", methods=["PATCH"])
def api_update(entry_id):
    data       = request.get_json(force=True)
    new_status = data.get("status")
    note       = data.get("notes", "")
    if new_status:
        entry = update_status(entry_id, new_status, note)
    elif note:
        entry = update_notes(entry_id, note)
    else:
        entry = get_entry(entry_id)
    if not entry:
        return jsonify({"error": "Not found"}), 404
    return jsonify(entry)


@app.route("/api/applications/<int:entry_id>", methods=["DELETE"])
def api_delete(entry_id):
    if delete_entry(entry_id):
        return jsonify({"deleted": entry_id})
    return jsonify({"error": "Not found"}), 404


@app.route("/api/summary")
def api_summary():
    return jsonify(pending_count())


@app.route("/api/config")
def api_config():
    name = ""
    try:
        profile = parse_cv(_CV_PATH)
        name    = profile.name or ""
    except Exception:
        pass
    return jsonify({"name": name})


@app.route("/api/fetch-job")
def api_fetch_job():
    url = request.args.get("url", "").strip()
    if not url:
        return jsonify({"error": "URL required"}), 400
    try:
        result = fetch_job(url, _ROOT)
        if result:
            return jsonify(result)
        return jsonify({"error": "Could not fetch job info. Fill manually."}), 404
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ══════════════════════════ LAUNCH ════════════════════════════════════════

def _open_browser():
    import time
    time.sleep(1.2)
    webbrowser.open("http://localhost:5000")


if __name__ == "__main__":
    threading.Thread(target=_open_browser, daemon=True).start()
    print()
    print("  ┌─────────────────────────────────────────────────────┐")
    print("  │   Job Hunt Dashboard  →  http://localhost:5000      │")
    print("  │   Press Ctrl+C to stop                               │")
    print("  └─────────────────────────────────────────────────────┘")
    print()
    app.run(host="127.0.0.1", port=5000, debug=False)
