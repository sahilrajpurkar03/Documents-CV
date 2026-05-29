"""
Job Search Engine — queries LinkedIn, Indeed, Glassdoor, Google Jobs
Uses the `python-jobspy` library as the unified scraper backend.
"""

from __future__ import annotations

import time
import random
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
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
]


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
            "date_posted": self.date_posted,
            "salary": self.salary,
            "matched_keywords": ", ".join(self.matched_keywords[:8]),
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


def search_jobs(
    region_name: str,
    search_terms: List[str],
    results_per_term: int = 20,
    sites: Optional[List[str]] = None,
    hours_old: int = 72 * 7,  # 3 weeks
    verbose: bool = True,
) -> List[JobListing]:
    """
    Run job searches across LinkedIn, Indeed, and Glassdoor for the given
    region and search terms.  Returns a flat list of deduplicated JobListings.
    """
    try:
        from jobspy import scrape_jobs
    except ImportError:
        raise ImportError(
            "python-jobspy not installed. Run:  pip install python-jobspy"
        )

    if region_name not in REGIONS:
        raise ValueError(f"Unknown region '{region_name}'. "
                         f"Choose from: {list(REGIONS)}")

    region = REGIONS[region_name]
    if sites is None:
        sites = ["linkedin", "indeed", "glassdoor", "google"]

    location_str = region["cities"][0]  # primary location (country name)

    all_listings: List[JobListing] = []
    seen_urls: set = set()

    for term in search_terms:
        if verbose:
            print(f"  Searching [{region['flag']} {region_name}]: \"{term}\" ...", flush=True)

        try:
            df = scrape_jobs(
                site_name=sites,
                search_term=term,
                location=location_str,
                results_wanted=results_per_term,
                hours_old=hours_old,
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
                print(f"    [warn] {term}: {exc}")

        # Polite delay between searches to avoid rate limiting
        time.sleep(random.uniform(2.0, 4.0))

    if verbose:
        print(f"\n  Found {len(all_listings)} unique listings.")
    return all_listings
