"""
Scoring & Ranking — scores job listings against the CV profile.

Scoring model (110 points total, normalised to 100):
  40 pts  — Skill / keyword overlap  (matched keywords / total keywords)
  25 pts  — Title relevance           (known role keyword in title)
  15 pts  — Seniority match           (avoids "Senior/Lead" if fresh grad)
  10 pts  — Recency bonus             (posted within 7 days)
  10 pts  — Description depth         (longer descriptions = more signal)
   5 pts  — Location bonus            (Germany / home region)
   5 pts  — Job-type bonus            (full-time / internship match)
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
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
    "ai engineer", "research engineer", "robot", "imitation learning",
    "reinforcement learning", "slam", "navigation", "localization",
]

# Weighted title terms — more specific = higher value
HIGH_VALUE_TITLE_WEIGHTS = {
    "ros2": 2, "ros": 2, "humanoid": 2, "sensor fusion": 2,
    "robotics": 1.5, "robot": 1.5, "autonomous": 1.5,
    "computer vision": 1.5, "machine learning": 1.5, "perception": 1.5,
    "embedded": 1, "automation": 1, "slam": 1.5, "navigation": 1,
    "ai engineer": 1, "research engineer": 1, "manipulation": 1.5,
    "imitation learning": 2, "reinforcement learning": 1.5, "localization": 1,
}

NEGATIVE_TITLE_TERMS = [
    "senior", "lead", "head of", "director", "principal", "staff",
    "vp ", "chief", "manager",
]

POSITIVE_LEVEL_TERMS = [
    "junior", "entry", "graduate", "intern", "werkstudent", "praktikant",
    "associate", "engineer i", "engineer ii", "entry-level",
]

# Keyword synonyms/stems — maps a search pattern to canonical keyword
KEYWORD_SYNONYMS: List[Tuple[str, str]] = [
    (r"ros\s*2?\b", "ROS/ROS2"),
    (r"robot(?:ics)?\b", "Robotics"),
    (r"autonomous\b", "Autonomous"),
    (r"computer\s+vision\b", "Computer Vision"),
    (r"deep\s+learning\b", "Machine Learning"),
    (r"neural\s+network\b", "Machine Learning"),
    (r"tensorflow\b|tf\b", "TensorFlow"),
    (r"pytorch\b", "PyTorch"),
    (r"object\s+detection\b", "Object Detection"),
    (r"point\s+cloud\b", "Point Cloud"),
    (r"li[Dd]ar\b", "LiDAR"),
    (r"slam\b", "SLAM"),
    (r"sensor\s+fusion\b", "Sensor Fusion"),
    (r"embedded\b", "Embedded"),
    (r"stm32\b", "STM32"),
    (r"rtos\b", "RTOS"),
    (r"docker\b", "Docker"),
    (r"git\b", "Git"),
    (r"linux\b", "Linux"),
    (r"c\+\+\b", "C++"),
    (r"python\b", "Python"),
    (r"matlab\b", "MATLAB"),
    (r"moveit\b", "MoveIt"),
    (r"gazebo\b|rviz\b", "Gazebo/RViz"),
    (r"isaac\s*(?:sim|lab)\b", "Isaac Sim"),
    (r"mujoco\b", "MuJoCo"),
    (r"yolo\b|yolov\d", "YOLO"),
    (r"opencv\b", "OpenCV"),
    (r"humanoid\b", "Humanoid"),
    (r"manipulat", "Manipulation"),
    (r"navigation\b", "Navigation"),
    (r"localiz", "Localization"),
    (r"imitation\s+learning\b", "Imitation Learning"),
    (r"diffusion\s+policy\b", "Diffusion Policy"),
    (r"reinforce\w*\s+learning\b", "Reinforcement Learning"),
    (r"websoket\b|websocket\b|dds\b", "DDS/WebSocket"),
]

# Preferred locations — bonus if job is here
PREFERRED_LOCATIONS = [
    "germany", "deutschland", "münchen", "munich", "berlin", "stuttgart",
    "hamburg", "dortmund", "frankfurt", "cologne", "köln", "hannover",
    "remote", "hybrid",
]


def _normalize(text: str) -> str:
    return text.lower()


def _keyword_score(listing: JobListing, profile: CVProfile) -> Tuple[float, List[str]]:
    """
    40-point keyword overlap score.
    Uses both exact CV keywords AND synonym/stem patterns for broader matching.
    """
    if not profile.all_keywords():
        return 0.0, []

    haystack = _normalize(f"{listing.title} {listing.description}")
    matched_set: set = set()

    # 1. Exact CV keyword matching (with word boundaries)
    for kw in profile.all_keywords():
        if re.search(r"\b" + re.escape(kw.lower()) + r"\b", haystack):
            matched_set.add(kw)

    # 2. Synonym / stem pattern matching
    for pattern, canonical in KEYWORD_SYNONYMS:
        if re.search(pattern, haystack, re.IGNORECASE):
            matched_set.add(canonical)

    matched = sorted(matched_set)
    total_unique = max(len(set(profile.all_keywords())), 1)
    ratio = len(matched) / total_unique
    # Scale generously — partial matches still deserve credit
    score = min(ratio * 40 * 2.2, 40.0)
    return round(score, 2), matched


def _title_score(listing: JobListing) -> float:
    """25-point title relevance score using weighted term matching."""
    title_lower = _normalize(listing.title)
    weight_sum = 0.0
    for term, weight in HIGH_VALUE_TITLE_WEIGHTS.items():
        if term in title_lower:
            weight_sum += weight
    # Max realistic weight ~8 → full 25 pts
    return round(min(weight_sum / 8.0, 1.0) * 25.0, 2)


def _seniority_score(listing: JobListing, profile: CVProfile) -> float:
    """
    15-point seniority match.
    Penalise 'Senior/Lead/Director' titles for ~5 yr experience level.
    Boost 'Junior/Graduate/Intern/Werkstudent'.
    """
    title_lower = _normalize(listing.title)
    desc_lower  = _normalize(listing.description[:600])

    if any(t in title_lower for t in NEGATIVE_TITLE_TERMS):
        return 3.0  # low — might still be worth it

    if any(t in title_lower or t in desc_lower for t in POSITIVE_LEVEL_TERMS):
        return 15.0  # perfect match for career stage

    return 11.0  # mid-level / unspecified — still a good match


def _recency_score(listing: JobListing) -> float:
    """10-point recency score. Full points if posted within 3 days."""
    if not listing.date_posted:
        return 5.0

    try:
        if hasattr(listing.date_posted, "date"):
            posted = listing.date_posted
        else:
            posted = datetime.fromisoformat(str(listing.date_posted).split("T")[0])
        posted = posted.replace(tzinfo=timezone.utc)
        delta = (datetime.now(timezone.utc) - posted).days
        if delta <= 3:   return 10.0
        if delta <= 7:   return 8.0
        if delta <= 14:  return 6.0
        if delta <= 21:  return 4.0
        return 2.0
    except Exception:
        return 5.0


def _location_score(listing: JobListing) -> float:
    """5-point location bonus for Germany / remote / hybrid."""
    loc = _normalize(f"{listing.location} {listing.description[:300]}")
    if any(p in loc for p in PREFERRED_LOCATIONS):
        return 5.0
    return 0.0


def _job_type_score(listing: JobListing) -> float:
    """5-point job-type bonus: full-time and internships are both valid."""
    jt = _normalize(listing.job_type or "")
    title = _normalize(listing.title)
    if "intern" in jt or "intern" in title or "praktikum" in title or "werkstudent" in title:
        return 5.0
    if "full" in jt or "full-time" in jt:
        return 5.0
    if "contract" in jt or "freelance" in jt:
        return 3.0
    return 2.0


def _description_depth_score(listing: JobListing) -> float:
    """10-point score based on description availability and length."""
    desc_len = len(listing.description or "")
    if desc_len > 1000: return 10.0
    if desc_len > 400:  return 7.0
    if desc_len > 100:  return 4.0
    return 1.0


def score_listing(listing: JobListing, profile: CVProfile) -> JobListing:
    """Compute composite score and attach matched keywords to the listing."""
    kw_score, matched = _keyword_score(listing, profile)
    t_score  = _title_score(listing)
    s_score  = _seniority_score(listing, profile)
    r_score  = _recency_score(listing)
    d_score  = _description_depth_score(listing)
    l_score  = _location_score(listing)
    jt_score = _job_type_score(listing)

    listing.score = kw_score + t_score + s_score + r_score + d_score + l_score + jt_score
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
