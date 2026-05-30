"""
Job Fetcher — retrieves job info from:
  1. Local jobs_*.html reports (fastest, no network)
  2. Direct URL scraping (fallback)
  3. Manual input (final fallback)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

# ── Keyword extractor (duplicated from job_search/cv_parser.py to avoid
#    cross-package imports; kept intentionally minimal) ─────────────────────
_TECH_TERMS = [
    "Python", "C++", "Embedded C", "MATLAB", "Bash",
    "ROS2", "ROS", "MoveIt", "DDS", "WebSocket", "FastAPI",
    "Isaac Sim", "Isaac Lab", "MuJoCo", "Gazebo", "RViz",
    "TensorFlow", "PyTorch", "OpenCV", "NumPy", "Pandas",
    "YOLOv7", "YOLOv8", "YOLO", "Detectron2", "OpenPCDet",
    "LLM", "Diffusion Policy", "Imitation Learning",
    "Object Detection", "Point Cloud", "3D Detection",
    "LiDAR", "Radar", "IMU", "Camera", "mmWave", "Sensor Fusion",
    "STM32", "ESP32", "ARM", "PCB", "KiCad", "Altium", "RTOS",
    "HIL", "Jenkins", "CI/CD", "Docker", "Linux", "Git",
    "SLAM", "LIO-SLAM", "Navigation", "Localization", "Mapping",
    "Manipulation", "Humanoid", "Quadruped", "Mobile Robot",
    "Pick and Place", "Autonomous", "Simulation",
    "Machine Learning", "Deep Learning", "Computer Vision",
    "Embedded Systems", "Firmware", "Real-Time",
    "Signal Integrity", "Power Integrity", "EMC",
]


def extract_keywords(text: str) -> list[str]:
    """Extract known tech keywords from free text."""
    found, text_lower = [], text.lower()
    for term in _TECH_TERMS:
        if term.lower() in text_lower and term not in found:
            found.append(term)
    return found


# ── HTML cell indices in jobs_*.html ──────────────────────────────────────
# 0:rank, 1:score, 2:label, 3:title, 4:company, 5:location,
# 6:date, 7:source, 8:salary, 9:matched_keywords, 10:apply-link

def _find_in_local_html(url: str, search_dir: Path) -> Optional[dict]:
    """
    Search all jobs_*.html files in search_dir for a row whose Apply link
    matches the given URL. Returns a dict of job fields or None.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return None

    for html_file in sorted(search_dir.glob("jobs_*.html"), reverse=True):
        try:
            soup = BeautifulSoup(
                html_file.read_text(encoding="utf-8"), "html.parser"
            )
        except Exception:
            continue

        for a_tag in soup.find_all("a", href=True):
            href = a_tag.get("href", "")
            # Match if the URL appears in the href or href appears in url
            if url.rstrip("/") in href.rstrip("/") or href.rstrip("/") in url.rstrip("/"):
                row = a_tag.find_parent("tr")
                if not row:
                    continue
                cells = row.find_all("td")
                if len(cells) < 10:
                    continue

                title = cells[3].get_text(strip=True)
                company = cells[4].get_text(strip=True)
                location = cells[5].get_text(strip=True)
                source = cells[7].get_text(strip=True)
                matched_kw = cells[9].get_text(strip=True)

                return {
                    "title": title,
                    "company": company,
                    "location": location,
                    "source": source,
                    "keywords": [k.strip() for k in matched_kw.split(",") if k.strip()],
                    "description": "",
                    "url": href,
                    "found_in": str(html_file.name),
                }
    return None


def _fetch_from_web(url: str) -> Optional[dict]:
    """
    Try to scrape a job posting URL directly.
    Returns partial data (may lack description on auth-walled sites).
    """
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        return None

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=12)
    except Exception:
        return None

    if resp.status_code != 200:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # ── Title ──────────────────────────────────────────────────────────
    title = ""
    for sel in [
        "h1.top-card-layout__title",        # LinkedIn
        "h1.jobsearch-JobInfoHeader-title",  # Indeed
        "h1[data-testid='job-title']",       # Glassdoor
        "h1",
    ]:
        elem = soup.select_one(sel)
        if elem:
            title = elem.get_text(strip=True)
            break

    # ── Company ────────────────────────────────────────────────────────
    company = ""
    for sel in [
        "a.topcard__org-name-link",
        "div.jobsearch-InlineCompanyRating > div",
        "[data-testid='employer-name']",
    ]:
        elem = soup.select_one(sel)
        if elem:
            company = elem.get_text(strip=True)
            break

    # ── Description ────────────────────────────────────────────────────
    desc = ""
    for sel in [
        "div.description__text",
        "div#jobDescriptionText",
        "div[data-testid='jobDescriptionSection']",
        "article",
        "main",
    ]:
        elem = soup.select_one(sel)
        if elem:
            desc = elem.get_text(separator=" ", strip=True)[:4000]
            break

    if not desc:
        body = soup.find("body")
        if body:
            desc = body.get_text(separator=" ", strip=True)[:4000]

    keywords = extract_keywords(desc) if desc else []

    return {
        "title": title[:120],
        "company": company[:80],
        "location": "",
        "source": _source_label(url),
        "keywords": keywords,
        "description": desc,
        "url": url,
        "found_in": "web",
    }


def _source_label(url: str) -> str:
    if "linkedin.com" in url:
        return "LinkedIn"
    if "indeed.com" in url:
        return "Indeed"
    if "glassdoor.com" in url:
        return "Glassdoor"
    if "stepstone" in url:
        return "Stepstone"
    if "google.com/search" in url or "jobs.google" in url:
        return "Google Jobs"
    return "Company Site"


def fetch_job(url: str, search_dir: Path) -> dict:
    """
    Fetch job info for a given URL.
    Priority: local HTML cache → web scrape → empty (triggers manual input).
    """
    # 1. Local HTML report
    result = _find_in_local_html(url, search_dir)
    if result and result.get("title"):
        return result

    # 2. Web scrape
    result = _fetch_from_web(url)
    if result and result.get("title"):
        return result

    # 3. Return skeleton — main.py will prompt for missing fields
    return {
        "title": "",
        "company": "",
        "location": "",
        "source": _source_label(url),
        "keywords": [],
        "description": "",
        "url": url,
        "found_in": "manual",
    }
