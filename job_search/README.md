# Job Search Tool

Reads your `main.tex` CV, searches **LinkedIn · Indeed · Glassdoor · Google Jobs** for matching roles, scores each listing against your skills, and ranks them so you know exactly where to apply first.

---

## Quick Start

**From Windows PowerShell (uses WSL Ubuntu):**
```powershell
# Interactive — prompts you to pick regions
wsl bash job_search/run_job_search.sh

# Direct — one or more regions
wsl bash job_search/run_job_search.sh --region Germany
wsl bash job_search/run_job_search.sh --region Germany Switzerland Netherlands
wsl bash job_search/run_job_search.sh --region India Germany --top 50
```

**From a WSL terminal:**
```bash
bash job_search/run_job_search.sh --region Germany
```

---

## Supported Regions

| Flag | Region | Key Cities |
|------|--------|------------|
| 🇩🇪 | Germany | Dortmund, Berlin, Munich, Hamburg, Stuttgart, Frankfurt |
| 🇨🇭 | Switzerland | Zurich, Basel, Bern, Geneva |
| 🇳🇱 | Netherlands | Amsterdam, Eindhoven, Rotterdam, Delft |
| 🇮🇳 | India | Bangalore, Mumbai, Hyderabad, Pune, Chennai |
| 🇺🇸 | USA | San Francisco, Boston, Pittsburgh, Seattle |
| 🇬🇧 | UK | London, Cambridge, Bristol |
| 🇨🇦 | Canada | Toronto, Vancouver, Montreal |

---

## All Options

```
--region   Germany Switzerland ...   Regions to search (omit for interactive menu)
--cv       /path/to/main.tex         CV path (auto-detected if omitted)
--top      40                        Top N results per region  (default: 40)
--per-term 15                        Results fetched per search term (default: 15)
--hours    504                       Max age of listings in hours (default: 504 = 3 weeks)
--sites    linkedin indeed glassdoor google   Sites to query
--no-export                          Skip saving CSV + HTML reports
--open                               Auto-open HTML report in browser
```

---

## Scoring Model (100 pts total)

| Component | Points | Logic |
|-----------|--------|-------|
| Skill / keyword overlap | 40 | Your CV keywords matched in title + description |
| Title relevance | 25 | Robotics, ROS, autonomous, embedded, etc. in job title |
| Seniority match | 15 | Boosts Junior/Graduate/Werkstudent; penalises Senior/Lead |
| Recency | 10 | Full points if posted ≤ 3 days ago |
| Description depth | 10 | Rewards detailed postings (more data = better scoring) |

**Match quality labels:**

| Score | Label |
|-------|-------|
| ≥ 75 | Excellent |
| ≥ 60 | Very Good |
| ≥ 45 | Good |
| ≥ 30 | Fair |
| < 30 | Low |

---

## Output Files

After each run, two files are saved next to `main.tex`:

- `jobs_germany_20260529_1430.csv` — spreadsheet of all ranked results
- `jobs_germany_20260529_1430.html` — styled dark-theme HTML report (open in browser)

---

## File Structure

```
job_search/
├── main.py           ← Entry point / CLI
├── cv_parser.py      ← Parses main.tex, extracts skills & keywords
├── searcher.py       ← Queries LinkedIn, Indeed, Glassdoor, Google Jobs
├── scorer.py         ← Scores & ranks job listings against CV profile
├── requirements.txt  ← Python dependencies
├── run_job_search.sh ← Bash launcher (auto-installs deps)
└── README.md         ← This file
```

---

## Requirements

- **WSL** with Ubuntu (already installed on this machine)
- Python 3.10+ (already in WSL)
- Internet connection (scrapes live job boards)

Dependencies are installed automatically by `run_job_search.sh`.

Manual install:
```bash
python3 -m pip install python-jobspy rich pandas
```
