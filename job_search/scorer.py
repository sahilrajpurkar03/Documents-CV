"""
Scoring & Ranking — scores job listings against the CV profile.

Scoring model (100 points total):
  40 pts  — Skill / keyword overlap  (matched keywords / total keywords)
  25 pts  — Title relevance           (known role keyword in title)
  15 pts  — Seniority match           (avoids "Senior/Lead" if fresh grad)
  10 pts  — Recency bonus             (posted within 7 days)
  10 pts  — Description depth         (longer descriptions = more signal)
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import List, Tuple

from cv_parser import CVProfile
from searcher import JobListing


# ---------------------------------------------------------------------------
# Title-level role keywords (high-weight matches)
# ---------------------------------------------------------------------------
HIGH_VALUE_TITLE_TERMS = [
    "robotics", "ros", "ros2", "autonomous", "automation",
    "embedded", "computer vision", "machine learning", "perception",
    "sensor fusion", "humanoid", "mobile robot", "manipulation",
    "ai engineer", "research engineer", "robot",
]

NEGATIVE_TITLE_TERMS = [
    "senior", "lead", "head of", "director", "principal", "staff",
    "vp ", "chief", "manager", "c++"  # c++ alone often means game dev
]

POSITIVE_LEVEL_TERMS = [
    "junior", "entry", "graduate", "intern", "werkstudent", "praktikant",
    "associate", "engineer i", "engineer ii",
]


def _normalize(text: str) -> str:
    return text.lower()


def _keyword_score(listing: JobListing, profile: CVProfile) -> Tuple[float, List[str]]:
    """
    40-point keyword overlap score.
    Searches title + description for every CV keyword.
    """
    if not profile.all_keywords():
        return 0.0, []

    haystack = _normalize(f"{listing.title} {listing.description}")
    matched = []
    for kw in profile.all_keywords():
        # Allow partial word boundary matching
        if re.search(r"\b" + re.escape(kw.lower()) + r"\b", haystack):
            if kw not in matched:
                matched.append(kw)

    ratio = len(matched) / max(len(set(profile.all_keywords())), 1)
    score = min(ratio * 40 * 1.8, 40.0)  # scale up so partial matches still score well
    return round(score, 2), matched


def _title_score(listing: JobListing) -> float:
    """25-point title relevance score."""
    title_lower = _normalize(listing.title)
    hits = sum(1 for t in HIGH_VALUE_TITLE_TERMS if t in title_lower)
    # Cap at 5 hits → full 25 pts
    return round(min(hits / 5.0, 1.0) * 25.0, 2)


def _seniority_score(listing: JobListing, profile: CVProfile) -> float:
    """
    15-point seniority match.
    Penalise 'Senior/Lead/Director' titles for ~5 yr experience level.
    Boost 'Junior/Graduate/Intern/Werkstudent'.
    """
    title_lower = _normalize(listing.title)
    desc_lower = _normalize(listing.description[:500])

    if any(t in title_lower for t in NEGATIVE_TITLE_TERMS):
        return 3.0  # low but not zero — might still be worth applying

    if any(t in title_lower or t in desc_lower for t in POSITIVE_LEVEL_TERMS):
        return 15.0  # perfect match for career stage

    # "mid-level" or unspecified — good match for ~5 yr experience
    return 12.0


def _recency_score(listing: JobListing) -> float:
    """10-point recency score.  Full points if posted within 7 days."""
    if not listing.date_posted:
        return 5.0  # unknown date → average

    try:
        # jobspy returns dates as strings like "2025-05-20" or datetime objects
        if hasattr(listing.date_posted, "date"):
            posted = listing.date_posted
        else:
            posted = datetime.fromisoformat(str(listing.date_posted).split("T")[0])
        posted = posted.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = (now - posted).days
        if delta <= 3:
            return 10.0
        if delta <= 7:
            return 8.0
        if delta <= 14:
            return 6.0
        if delta <= 21:
            return 4.0
        return 2.0
    except Exception:
        return 5.0


def _description_depth_score(listing: JobListing) -> float:
    """10-point score based on description availability and length."""
    desc_len = len(listing.description or "")
    if desc_len > 1000:
        return 10.0
    if desc_len > 400:
        return 7.0
    if desc_len > 100:
        return 4.0
    return 1.0


def score_listing(listing: JobListing, profile: CVProfile) -> JobListing:
    """Compute composite score and attach matched keywords to the listing."""
    kw_score, matched = _keyword_score(listing, profile)
    t_score = _title_score(listing)
    s_score = _seniority_score(listing, profile)
    r_score = _recency_score(listing)
    d_score = _description_depth_score(listing)

    listing.score = kw_score + t_score + s_score + r_score + d_score
    listing.matched_keywords = matched
    return listing


def rank_listings(
    listings: List[JobListing], profile: CVProfile, top_n: int = 50
) -> List[JobListing]:
    """Score all listings, return top_n sorted by score descending."""
    scored = [score_listing(j, profile) for j in listings]
    scored.sort(key=lambda j: j.score, reverse=True)
    return scored[:top_n]


def score_label(score: float) -> str:
    """Human-readable match quality label."""
    if score >= 75:
        return "Excellent"
    if score >= 60:
        return "Very Good"
    if score >= 45:
        return "Good"
    if score >= 30:
        return "Fair"
    return "Low"


def score_color(score: float) -> str:
    """Rich color string for the score."""
    if score >= 75:
        return "bold green"
    if score >= 60:
        return "green"
    if score >= 45:
        return "yellow"
    if score >= 30:
        return "orange3"
    return "red"
