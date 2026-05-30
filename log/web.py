"""
Flask web server for the job application log.
Provides a REST API consumed by the single-page UI.
"""

from __future__ import annotations

import sys
from pathlib import Path

_DIR = Path(__file__).parent
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))

from flask import Flask, jsonify, request, send_from_directory
from tracker import (
    STATUSES, STATUS_EMOJI,
    load_db, add_entry, update_status, update_notes,
    delete_entry, get_entry, filter_entries, pending_count,
)

app = Flask(__name__, static_folder=str(_DIR / "static"))

# ── Serve the SPA ─────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(str(_DIR), "index.html")


# ── API ───────────────────────────────────────────────────────────────────

@app.route("/api/statuses")
def api_statuses():
    return jsonify([
        {"value": s, "emoji": STATUS_EMOJI.get(s, "")}
        for s in STATUSES
    ])


@app.route("/api/applications", methods=["GET"])
def api_list():
    status  = request.args.get("status")
    active  = request.args.get("active") == "1"
    company = request.args.get("company")
    entries = filter_entries(status=status, active_only=active, company=company)
    return jsonify(entries)


@app.route("/api/applications", methods=["POST"])
def api_add():
    data  = request.get_json(force=True)
    entry = add_entry(
        title    = data.get("title", ""),
        company  = data.get("company", ""),
        url      = data.get("url", ""),
        location = data.get("location", ""),
        source   = data.get("source", ""),
        notes    = data.get("notes", ""),
        status   = data.get("status", "applied"),
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
    data = request.get_json(force=True)
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


if __name__ == "__main__":
    import webbrowser, threading
    port = 5050
    url  = f"http://localhost:{port}"
    print(f"\n  Job Log running at {url}\n  Press Ctrl+C to stop.\n")
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=port, debug=False)
