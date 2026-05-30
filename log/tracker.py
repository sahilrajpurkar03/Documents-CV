"""
Application Tracker — persistent JSON store.
Handles add, update, load, save, and query of job applications.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

DB_FILE = Path(__file__).parent / "applications.json"

# ── Valid statuses (ordered by pipeline stage) ────────────────────────────
STATUSES = [
    "saved",           # found but not yet applied
    "applied",         # application submitted
    "awaiting",        # waiting for response
    "interview",       # interview scheduled or ongoing
    "assessment",      # technical test / take-home
    "offer",           # received an offer
    "rejected",        # explicitly rejected
    "withdrawn",       # you withdrew the application
]

STATUS_COLOR = {
    "saved":      "dim",
    "applied":    "cyan",
    "awaiting":   "yellow",
    "interview":  "bold green",
    "assessment": "bold yellow",
    "offer":      "bold magenta",
    "rejected":   "red",
    "withdrawn":  "dim red",
}

STATUS_EMOJI = {
    "saved":      "📌",
    "applied":    "📤",
    "awaiting":   "⏳",
    "interview":  "🎯",
    "assessment": "🧪",
    "offer":      "🎉",
    "rejected":   "❌",
    "withdrawn":  "↩️ ",
}

ACTIVE_STATUSES = {"saved", "applied", "awaiting", "interview", "assessment"}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def load_db() -> List[dict]:
    if DB_FILE.exists():
        try:
            return json.loads(DB_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def save_db(entries: List[dict]) -> None:
    DB_FILE.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def next_id(entries: List[dict]) -> int:
    return max((e.get("id", 0) for e in entries), default=0) + 1


def add_entry(
    title: str,
    company: str,
    url: str = "",
    location: str = "",
    source: str = "",
    notes: str = "",
    status: str = "applied",
) -> dict:
    entries = load_db()
    entry = {
        "id":           next_id(entries),
        "title":        title.strip(),
        "company":      company.strip(),
        "url":          url.strip(),
        "location":     location.strip(),
        "source":       source.strip(),
        "status":       status,
        "date_applied": _today(),
        "last_updated": _now(),
        "notes":        notes.strip(),
        "history":      [{"status": status, "date": _now(), "note": "Added"}],
    }
    entries.append(entry)
    save_db(entries)
    return entry


def update_status(
    entry_id: int,
    new_status: str,
    note: str = "",
) -> Optional[dict]:
    entries = load_db()
    for entry in entries:
        if entry["id"] == entry_id:
            entry["status"] = new_status
            entry["last_updated"] = _now()
            entry["history"].append({
                "status": new_status,
                "date": _now(),
                "note": note,
            })
            if note:
                entry["notes"] = note
            save_db(entries)
            return entry
    return None


def update_notes(entry_id: int, note: str) -> Optional[dict]:
    entries = load_db()
    for entry in entries:
        if entry["id"] == entry_id:
            entry["notes"] = note
            entry["last_updated"] = _now()
            save_db(entries)
            return entry
    return None


def delete_entry(entry_id: int) -> bool:
    entries = load_db()
    new = [e for e in entries if e["id"] != entry_id]
    if len(new) < len(entries):
        save_db(new)
        return True
    return False


def get_entry(entry_id: int) -> Optional[dict]:
    for e in load_db():
        if e["id"] == entry_id:
            return e
    return None


def filter_entries(
    status: Optional[str] = None,
    active_only: bool = False,
    company: Optional[str] = None,
) -> List[dict]:
    entries = load_db()
    if status:
        entries = [e for e in entries if e["status"] == status]
    if active_only:
        entries = [e for e in entries if e["status"] in ACTIVE_STATUSES]
    if company:
        entries = [e for e in entries
                   if company.lower() in e.get("company", "").lower()]
    return sorted(entries, key=lambda e: e.get("date_applied", ""), reverse=True)


def pending_count() -> dict:
    """Return count per active status."""
    entries = load_db()
    counts = {s: 0 for s in STATUSES}
    for e in entries:
        s = e.get("status", "applied")
        if s in counts:
            counts[s] += 1
    return counts
