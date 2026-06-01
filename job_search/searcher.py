"""
Job Search Engine — queries LinkedIn, Indeed, Google Jobs, StepStone, Xing
Uses the `python-jobspy` library for LinkedIn/Indeed/Google and
custom scrapers for StepStone.de and Xing.
"""

from __future__ import annotations

import re
import time
import random
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Callable
import pandas as pd

# ---------------------------------------------------------------------------
# Region config: country_indeed, linkedin_country_id, major cities
# ---------------------------------------------------------------------------
REGIONS: Dict[str, Dict[str, Any]] = {
    "Germany": {
        "country_indeed": "germany",
        "linkedin_country": "de",
        "cities": ["Germany", "Berlin", "Munich", "Hamburg", "Stuttgart",
                   "Frankfurt", "Dortmund", "Cologne", "Hannover"],
        "extra_sites": ["stepstone.de"],
        "currency": "EUR",
        "flag": "🇩🇪",
    },
    "Switzerland": {
        "country_indeed": "switzerland",
        "linkedin_country": "ch",
        "cities": ["Switzerland", "Zurich", "Basel", "Bern", "Geneva", "Lausanne"],
        "extra_sites": ["jobs.ch"],
        "currency": "CHF",
        "flag": "🇨🇭",
    },
    "Netherlands": {
        "country_indeed": "netherlands",
        "linkedin_country": "nl",
        "cities": ["Netherlands", "Amsterdam", "Eindhoven", "Rotterdam",
                   "Delft", "Utrecht"],
        "extra_sites": ["nationalevacaturebank.nl"],
        "currency": "EUR",
        "flag": "🇳🇱",
    },
    "India": {
        "country_indeed": "india",
        "linkedin_country": "in",
        "cities": ["India", "Bangalore", "Mumbai", "Hyderabad", "Pune",
                   "Chennai", "Delhi", "Noida"],
        "extra_sites": ["naukri.com"],
        "currency": "INR",
        "flag": "🇮🇳",
    },
    "USA": {
        "country_indeed": "usa",
        "linkedin_country": "us",
        "cities": ["United States", "San Francisco", "Boston", "Pittsburgh",
                   "Seattle", "New York", "Austin"],
        "extra_sites": [],
        "currency": "USD",
        "flag": "🇺🇸",
    },
    "UK": {
        "country_indeed": "uk",
        "linkedin_country": "gb",
        "cities": ["United Kingdom", "London", "Cambridge", "Bristol", "Edinburgh"],
        "extra_sites": [],
        "currency": "GBP",
        "flag": "🇬🇧",
    },
    "Canada": {
        "country_indeed": "canada",
        "linkedin_country": "ca",
        "cities": ["Canada", "Toronto", "Vancouver", "Montreal", "Waterloo"],
        "extra_sites": [],
        "currency": "CAD",
        "flag": "🇨🇦",
    },
}

# ---------------------------------------------------------------------------
# Search terms derived from a Robotics/Automation profile
# ---------------------------------------------------------------------------
DEFAULT_SEARCH_TERMS = [
    "Robotics Software Engineer",
    "ROS2 Developer",
    "Autonomous Systems Engineer",
    "Robot Perception Engineer",
    "Embedded Systems Engineer",
    "Computer Vision Engineer",
    "Machine Learning Engineer Robotics",
    "Automation Engineer",
    "Humanoid Robotics Engineer",
    "Sensor Fusion Engineer",
    "Imitation Learning Engineer",
    "AI Robotics Engineer",
    "SLAM Engineer",
    "Robot Learning",
    "Legged Robotics Engineer",
]


def build_search_terms_from_cv(profile) -> List[str]:
    """
    Build a dynamic search term list from the parsed CV profile.
    Merges DEFAULT_SEARCH_TERMS with role keywords from the profile.
    """
    terms = list(DEFAULT_SEARCH_TERMS)
    for role in getattr(profile, 'roles', []):
        if role not in terms:
            terms.append(role)
    # Deduplicate preserving order
    seen: set = set()
    unique = []
    for t in terms:
        if t.lower() not in seen:
            seen.add(t.lower())
            unique.append(t)
    return unique


@dataclass
class JobListing:
    title: str = ""
    company: str = ""
    location: str = ""
    description: str = ""
    url: str = ""
    source: str = ""
    date_posted: str = ""
    job_type: str = ""
    salary: str = ""
    score: float = 0.0
    matched_keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "score": round(self.score, 1),
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "source": self.source,
            "job_type": self.job_type,
            "salary": self.salary,
            "date_posted": self.date_posted,
            "matched_keywords": ", ".join(self.matched_keywords[:10]),
            "url": self.url,
        }


def _df_to_listings(df: pd.DataFrame) -> List[JobListing]:
    """Convert a jobspy DataFrame to a list of JobListing objects."""
    listings = []
    for _, row in df.iterrows():
        def safe(col: str, default: str = "") -> str:
            val = row.get(col, default)
            return str(val) if pd.notna(val) else default

        salary_parts = []
        if pd.notna(row.get("min_amount")):
            salary_parts.append(f"{row['min_amount']:,.0f}")
        if pd.notna(row.get("max_amount")):
            salary_parts.append(f"{row['max_amount']:,.0f}")
        salary_str = " – ".join(salary_parts)
        if salary_str and pd.notna(row.get("currency")):
            salary_str = f"{salary_str} {row['currency']}"

        listings.append(JobListing(
            title=safe("title"),
            company=safe("company"),
            location=safe("location"),
            description=safe("description"),
            url=safe("job_url"),
            source=safe("site"),
            date_posted=safe("date_posted"),
            job_type=safe("job_type"),
            salary=salary_str,
        ))
    return listings


def _scrape_stepstone(
    term: str,
    location: str = "Deutschland",
    results_wanted: int = 15,
    hours_old: int = 504,
) -> List[JobListing]:
    """Scrape StepStone.de for a given search term."""
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        return []

    listings: List[JobListing] = []
    try:
        params = {
            "q":    term,
            "l":    location,
            "sort": "date",
        }
        url = "https://www.stepstone.de/jobs/?" + urllib.parse.urlencode(params)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")

        # StepStone article cards: data-at="job-item"
        cards = soup.select("article[data-at='job-item']")
        for card in cards[:results_wanted]:
            title_el = card.select_one("[data-at='job-item-title']")
            company_el = card.select_one("[data-at='job-item-company-name']")
            location_el = card.select_one("[data-at='job-item-location']")
            link_el = card.select_one("a[data-at='job-item-title']")
            date_el = card.select_one("time")

            title   = title_el.get_text(strip=True) if title_el else ""
            company = company_el.get_text(strip=True) if company_el else ""
            loc     = location_el.get_text(strip=True) if location_el else location
            href    = link_el.get("href", "") if link_el else ""
            job_url = ("https://www.stepstone.de" + href) if href.startswith("/") else href
            date    = date_el.get("datetime", "")[:10] if date_el else ""

            if title and company:
                listings.append(JobListing(
                    title=title, company=company, location=loc,
                    url=job_url, source="stepstone",
                    date_posted=date,
                ))
    except Exception:
        pass
    return listings


def _scrape_xing(
    term: str,
    location: str = "Deutschland",
    results_wanted: int = 15,
    hours_old: int = 504,
) -> List[JobListing]:
    """Scrape Xing jobs for a given search term via their JSON search API."""
    try:
        import requests
    except ImportError:
        return []

    listings: List[JobListing] = []
    try:
        params = {
            "keywords": term,
            "location": location,
            "sort":     "date",
            "limit":    results_wanted,
            "offset":   0,
        }
        # Xing public JSON API (no auth required for basic search)
        api_url = "https://www.xing.com/jobs/api/search?" + urllib.parse.urlencode(params)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        }
        resp = requests.get(api_url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return []
        data = resp.json()

        # Response structure: data.jobs.collection or data.collection
        collection = (
            data.get("jobs", {}).get("collection")
            or data.get("collection")
            or []
        )
        for job in collection[:results_wanted]:
            title   = job.get("title", "") or job.get("name", "")
            company = (job.get("company") or {}).get("name", "")
            loc_obj = job.get("location") or {}
            loc     = loc_obj.get("city", "") or location
            slug    = job.get("slug") or job.get("id", "")
            job_url = f"https://www.xing.com/jobs/{slug}" if slug else ""
            date    = (job.get("publishedAt") or "")[:10]

            if title and company:
                listings.append(JobListing(
                    title=title, company=company, location=loc,
                    url=job_url, source="xing",
                    date_posted=date,
                ))
    except Exception:
        pass
    return listings


def _scrape_one_term(
    term: str,
    sites: List[str],
    location_str: str,
    results_per_term: int,
    hours_old: int,
    country_indeed: str,
    verbose: bool,
    region_flag: str,
    on_progress: Optional[Callable[[str], None]] = None,
) -> List[JobListing]:
    """Scrape a single search term. Designed for use in ThreadPoolExecutor."""
    if on_progress:
        on_progress(term)

    # Stagger threads slightly to avoid simultaneous connection bursts
    time.sleep(random.uniform(0.2, 1.2))

    results: List[JobListing] = []

    # ── jobspy sites ──────────────────────────────────────────────────────
    jobspy_sites = [s for s in sites if s not in ("stepstone", "xing")]
    if jobspy_sites:
        try:
            from jobspy import scrape_jobs
            df = scrape_jobs(
                site_name=jobspy_sites,
                search_term=term,
                location=location_str,
                results_wanted=results_per_term,
                hours_old=hours_old,
                country_indeed=country_indeed,
                linkedin_fetch_description=True,
                verbose=0,
            )
            if df is not None and len(df) > 0:
                results.extend(_df_to_listings(df))
        except Exception as exc:
            if verbose:
                print(f"    [warn] jobspy {term}: {exc}")

    # ── StepStone ─────────────────────────────────────────────────────────
    if "stepstone" in sites:
        try:
            results.extend(_scrape_stepstone(term, location_str, results_per_term, hours_old))
        except Exception as exc:
            if verbose:
                print(f"    [warn] stepstone {term}: {exc}")

    # ── Xing ──────────────────────────────────────────────────────────────
    if "xing" in sites:
        try:
            results.extend(_scrape_xing(term, location_str, results_per_term, hours_old))
        except Exception as exc:
            if verbose:
                print(f"    [warn] xing {term}: {exc}")

    return results


def search_jobs(
    region_name: str,
    search_terms: List[str],
    results_per_term: int = 20,
    sites: Optional[List[str]] = None,
    hours_old: int = 72 * 7,  # 3 weeks
    verbose: bool = True,
    on_progress: Optional[Callable[[str], None]] = None,
    max_workers: int = 4,
) -> List[JobListing]:
    """
    Run job searches across LinkedIn, Indeed, and Glassdoor for the given
    region and search terms.  Uses parallel threads for speed.
    Returns a flat list of deduplicated JobListings.
    """
    try:
        from jobspy import scrape_jobs  # noqa — just check it's installed
    except ImportError:
        raise ImportError("python-jobspy not installed. Run: pip install python-jobspy")

    if region_name not in REGIONS:
        raise ValueError(f"Unknown region '{region_name}'. Choose from: {list(REGIONS)}")

    region = REGIONS[region_name]
    if sites is None:
        sites = ["linkedin", "indeed", "google", "stepstone", "xing"]

    location_str = region["cities"][0]

    all_listings: List[JobListing] = []
    seen_urls: set = set()
    lock_seen: set = seen_urls  # reference, used below

    def _collect(term: str) -> List[JobListing]:
        return _scrape_one_term(
            term=term,
            sites=sites,
            location_str=location_str,
            results_per_term=results_per_term,
            hours_old=hours_old,
            country_indeed=region["country_indeed"],
            verbose=verbose,
            region_flag=region["flag"],
            on_progress=on_progress,
        )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_collect, term): term for term in search_terms}
        for future in as_completed(futures):
            batch = future.result()
            for listing in batch:
                if listing.url and listing.url not in lock_seen:
                    lock_seen.add(listing.url)
                    all_listings.append(listing)
                elif not listing.url:
                    all_listings.append(listing)

    if verbose:
        print(f"\n  Found {len(all_listings)} unique listings.")
    return deduplicate_by_title(all_listings)


def deduplicate_by_title(listings: List[JobListing]) -> List[JobListing]:
    """
    Remove near-duplicate listings with the same (company, normalised title).
    When a job appears on multiple sites, merges the source names (e.g. "linkedin, indeed").
    Keeps the entry with the longer description (more data = better scoring).
    """
    seen: dict = {}   # key → index in result list
    result: List[JobListing] = []
    for listing in listings:
        norm = re.sub(r"\(m/f/d\)|\(f/m/d\)|\(all genders\)", "", listing.title, flags=re.IGNORECASE)
        norm = re.sub(r"\s+", " ", norm).strip().lower()
        key = (listing.company.lower().strip(), norm)
        if key in seen:
            idx = seen[key]
            existing = result[idx]
            # Merge source names so user sees all sites this job appeared on
            existing_sources = {s.strip() for s in existing.source.split(",")}
            new_source = listing.source.strip()
            if new_source and new_source not in existing_sources:
                existing.source = existing.source + ", " + new_source
            # Prefer the entry with more description text
            if len(listing.description) > len(existing.description):
                existing.description = listing.description
                if listing.url:
                    existing.url = listing.url
        else:
            seen[key] = len(result)
            result.append(listing)
    return result


# ---------------------------------------------------------------------------
# Greenhouse ATS scraper (public JSON API — no auth required)
# ---------------------------------------------------------------------------
def _scrape_greenhouse(slug: str, results_wanted: int = 40) -> List[JobListing]:
    """Scrape jobs from a Greenhouse-powered career page via their public API."""
    try:
        import requests
        import re as _re
    except ImportError:
        return []
    listings: List[JobListing] = []
    try:
        url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        if resp.status_code != 200:
            return []
        jobs = resp.json().get("jobs", [])
        for job in jobs[:results_wanted]:
            title = job.get("title", "")
            if not title:
                continue
            offices = job.get("offices") or []
            loc = ", ".join(o.get("name", "") for o in offices if o.get("name")) or "—"
            job_url = job.get("absolute_url", "")
            updated = (job.get("updated_at") or "")[:10]
            content = job.get("content", "") or ""
            desc = _re.sub(r"<[^>]+>", " ", content)[:600].strip()
            listings.append(JobListing(
                title=title, company=slug, location=loc, description=desc,
                url=job_url, source="greenhouse", date_posted=updated,
                job_type="Full-time",
            ))
    except Exception:
        pass
    return listings


# ---------------------------------------------------------------------------
# Lever ATS scraper (public JSON API — no auth required)
# ---------------------------------------------------------------------------
def _scrape_lever(slug: str, results_wanted: int = 40) -> List[JobListing]:
    """Scrape jobs from a Lever-powered career page via their public JSON API."""
    try:
        import requests
        import re as _re
    except ImportError:
        return []
    listings: List[JobListing] = []
    try:
        url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        if resp.status_code != 200:
            return []
        jobs = resp.json()
        if not isinstance(jobs, list):
            return []
        for job in jobs[:results_wanted]:
            title = job.get("text", "")
            if not title:
                continue
            cats = job.get("categories", {}) or {}
            loc  = cats.get("location", "") or cats.get("allLocations", [""])[0] if cats.get("allLocations") else ""
            job_url = job.get("hostedUrl", "") or job.get("applyUrl", "")
            created = job.get("createdAt", 0) or 0
            date_str = ""
            if created:
                try:
                    from datetime import datetime as _dt
                    date_str = _dt.fromtimestamp(created / 1000).strftime("%Y-%m-%d")
                except Exception:
                    pass
            desc_html = (job.get("descriptionBody") or job.get("description") or "")
            desc = _re.sub(r"<[^>]+>", " ", desc_html)[:600].strip()
            listings.append(JobListing(
                title=title, company=slug, location=loc or "—", description=desc,
                url=job_url, source="lever", date_posted=date_str,
                job_type="Full-time",
            ))
    except Exception:
        pass
    return listings


# ---------------------------------------------------------------------------
# Robotics companies catalogue
# ---------------------------------------------------------------------------
ROBOTICS_COMPANIES: List[Dict[str, Any]] = [
    # ── Germany ──────────────────────────────────────────────────────────────
    {"name": "KUKA",                "country": "Germany",  "city": "Augsburg",           "ats": None,         "slug": "",                  "website": "https://www.kuka.com"},
    {"name": "Franka Robotics",     "country": "Germany",  "city": "Munich",             "ats": None,         "slug": "",                  "website": "https://www.franka.de"},
    {"name": "Sereact",             "country": "Germany",  "city": "Stuttgart",          "ats": "greenhouse", "slug": "sereact",            "website": "https://sereact.ai"},
    {"name": "Magazino",            "country": "Germany",  "city": "Munich",             "ats": "greenhouse", "slug": "magazino",           "website": "https://www.magazino.eu"},
    {"name": "Neura Robotics",      "country": "Germany",  "city": "Metzingen",          "ats": None,         "slug": "",                  "website": "https://www.neura-robotics.com"},
    {"name": "Wandelbots",          "country": "Germany",  "city": "Dresden",            "ats": None,         "slug": "",                  "website": "https://wandelbots.com"},
    {"name": "Agile Robots",        "country": "Germany",  "city": "Munich",             "ats": None,         "slug": "",                  "website": "https://www.agile-robots.de"},
    {"name": "DLR",                 "country": "Germany",  "city": "Oberpfaffenhofen",   "ats": None,         "slug": "",                  "website": "https://www.dlr.de"},
    {"name": "Reactive Robotics",   "country": "Germany",  "city": "Munich",             "ats": None,         "slug": "",                  "website": "https://www.reactive-robotics.com"},
    {"name": "Schunk",              "country": "Germany",  "city": "Lauffen am Neckar",  "ats": None,         "slug": "",                  "website": "https://schunk.com"},
    {"name": "igus",                "country": "Germany",  "city": "Cologne",            "ats": None,         "slug": "",                  "website": "https://www.igus.de"},
    {"name": "Siemens",             "country": "Germany",  "city": "Munich",             "ats": None,         "slug": "",                  "website": "https://new.siemens.com"},
    {"name": "Bosch",               "country": "Germany",  "city": "Stuttgart",          "ats": None,         "slug": "",                  "website": "https://www.bosch.com"},
    {"name": "BMW Group",           "country": "Germany",  "city": "Munich",             "ats": None,         "slug": "",                  "website": "https://www.bmw.com"},
    {"name": "Mercedes-Benz",       "country": "Germany",  "city": "Stuttgart",          "ats": None,         "slug": "",                  "website": "https://www.mercedes-benz.com"},
    {"name": "ABB Robotics",        "country": "Germany",  "city": "Friedberg",          "ats": None,         "slug": "",                  "website": "https://new.abb.com"},
    {"name": "Fanuc Germany",       "country": "Germany",  "city": "Neuhausen ob Eck",   "ats": None,         "slug": "",                  "website": "https://www.fanuc.eu"},
    {"name": "Rethink Robotics",    "country": "Germany",  "city": "Frankfurt",          "ats": None,         "slug": "",                  "website": "https://www.rethinkrobotics.com"},
    {"name": "Intrinsic",           "country": "Germany",  "city": "Munich",             "ats": "greenhouse", "slug": "intrinsic",          "website": "https://intrinsic.ai"},
    # ── Scandinavia / Europe ─────────────────────────────────────────────────
    {"name": "Universal Robots",    "country": "Denmark",  "city": "Odense",             "ats": "greenhouse", "slug": "universalrobots",    "website": "https://www.universal-robots.com"},
    {"name": "1X Technologies",     "country": "Norway",   "city": "Oslo",               "ats": "lever",      "slug": "1xtechnologies",     "website": "https://www.1x.tech"},
    # ── USA (often hire remote / EU offices) ─────────────────────────────────
    {"name": "Boston Dynamics",     "country": "USA",      "city": "Waltham, MA",        "ats": "greenhouse", "slug": "bostondynamics",     "website": "https://www.bostondynamics.com"},
    {"name": "Agility Robotics",    "country": "USA",      "city": "Corvallis, OR",      "ats": "greenhouse", "slug": "agilityrobotics",    "website": "https://agilityrobotics.com"},
    {"name": "Figure AI",           "country": "USA",      "city": "Sunnyvale, CA",      "ats": "lever",      "slug": "figureai",           "website": "https://figure.ai"},
    {"name": "Apptronik",           "country": "USA",      "city": "Austin, TX",         "ats": "greenhouse", "slug": "apptronik",          "website": "https://apptronik.com"},
    {"name": "Physical Intelligence","country": "USA",     "city": "San Francisco, CA",  "ats": None,         "slug": "",                  "website": "https://www.physicalintelligence.company"},
    {"name": "Skild AI",            "country": "USA",      "city": "Pittsburgh, PA",     "ats": "greenhouse", "slug": "skildai",            "website": "https://www.skild.ai"},
    {"name": "Clearpath Robotics",  "country": "Canada",   "city": "Waterloo, ON",       "ats": "greenhouse", "slug": "clearpathrobotics",  "website": "https://clearpathrobotics.com"},
    {"name": "NVIDIA Robotics",     "country": "USA",      "city": "Santa Clara, CA",    "ats": None,         "slug": "",                  "website": "https://www.nvidia.com"},
    {"name": "Piaggio Fast Forward","country": "USA",      "city": "Boston, MA",         "ats": None,         "slug": "",                  "website": "https://piaggiofastforward.com"},
]


def search_company(
    company_name: str,
    region_name: str = "Germany",
    results: int = 50,
    sites: Optional[List[str]] = None,
    verbose: bool = True,
    on_progress: Optional[Callable[[str], None]] = None,
) -> List[JobListing]:
    """
    Search all open roles at a specific company, ranked by CV fit score.
    Uses a broad search term so we catch all roles, then filters by company name.
    """
    try:
        from jobspy import scrape_jobs
    except ImportError:
        raise ImportError("python-jobspy not installed. Run: pip install python-jobspy")

    if region_name not in REGIONS:
        region_name = "Germany"
    region = REGIONS[region_name]

    if sites is None:
        sites = ["linkedin", "indeed", "google", "stepstone", "xing"]

    if verbose:
        print(f"  Searching company: \"{company_name}\" [{region['flag']} {region_name}] ...", flush=True)

    all_listings: List[JobListing] = []
    seen_urls: set = set()

    # Try multiple search variants to maximise coverage
    search_variants = [
        company_name,
        f"{company_name} engineer",
        f"{company_name} robotics",
    ]

    for term in search_variants:
        if verbose:
            print(f"  Trying: \"{term}\" ...", flush=True)
        if on_progress:
            on_progress(f"Trying: \"{term}\"")
        try:
            df = scrape_jobs(
                site_name=sites,
                search_term=term,
                location=region["cities"][0],
                results_wanted=results,
                hours_old=60 * 24 * 90,  # 90-day window — wider for company search
                country_indeed=region["country_indeed"],
                linkedin_fetch_description=True,
                verbose=0,
            )
            if df is not None and len(df) > 0:
                for listing in _df_to_listings(df):
                    if listing.url and listing.url not in seen_urls:
                        seen_urls.add(listing.url)
                        all_listings.append(listing)
        except Exception as exc:
            if verbose:
                print(f"    [warn] {exc}")

        time.sleep(random.uniform(1.5, 3.0))

    # Filter to only rows where company name roughly matches
    name_lower = company_name.lower()
    filtered = [
        j for j in all_listings
        if name_lower in (j.company or "").lower()
        or (j.company or "").lower() in name_lower
    ]
    # Fallback: if filter is too aggressive, return all
    if not filtered:
        filtered = all_listings

    # Remove near-duplicate titles from the same company
    filtered = deduplicate_by_title(filtered)

    if verbose:
        print(f"  Found {len(filtered)} listings for {company_name}.")
    return filtered
