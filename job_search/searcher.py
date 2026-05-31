"""
Job Search Engine — queries LinkedIn, Indeed, Glassdoor, Google Jobs
Uses the `python-jobspy` library as the unified scraper backend.
"""

from __future__ import annotations

import re
import time
import random
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
    try:
        from jobspy import scrape_jobs
    except ImportError:
        return []

    if on_progress:
        on_progress(term)

    # Stagger threads slightly to avoid simultaneous connection bursts
    time.sleep(random.uniform(0.2, 1.2))

    try:
        df = scrape_jobs(
            site_name=sites,
            search_term=term,
            location=location_str,
            results_wanted=results_per_term,
            hours_old=hours_old,
            country_indeed=country_indeed,
            linkedin_fetch_description=True,
            verbose=0,
        )
        if df is not None and len(df) > 0:
            return _df_to_listings(df)
    except Exception as exc:
        if verbose:
            print(f"    [warn] {term}: {exc}")
    return []


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
        sites = ["linkedin", "indeed", "glassdoor", "google"]

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
            if len(listing.description) > len(result[idx].description):
                result[idx] = listing
        else:
            seen[key] = len(result)
            result.append(listing)
    return result


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
        sites = ["linkedin", "indeed", "glassdoor", "google"]

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
