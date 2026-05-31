# Job Application Toolkit

A self-hosted, privacy-first toolkit for job seekers — built around your **own CV in LaTeX**. Three tools work together: find matching jobs, generate tailored cover letters, and track your applications.

---

## Quick Start

### 1. Add Your CV
Edit `main.tex` with your CV content (moderncv banking style). All tools read from this file automatically.

### 2. Add Your Cover Letter Data
```bash
cp cover_letter/cv_data.example.py cover_letter/cv_data.py
# then edit cv_data.py with your personal info, experience prose, and projects
```

### 3. Run the Tools

| Tool | Web UI | CLI |
|---|---|---|
| **Job Search** | `wsl bash job_search/run_job_search.sh web` → http://localhost:5052 | `wsl bash job_search/run_job_search.sh` |
| **Cover Letter** | `wsl bash cover_letter/run.sh web` → http://localhost:5051 | `wsl bash cover_letter/run.sh` |
| **Application Log** | `wsl bash log/run.sh web` → http://localhost:5050 | `wsl bash log/run.sh list` |

> **Note:** The `wsl` prefix is needed on Windows with WSL. On Linux/macOS, use `bash ...` directly.

---

## Tools

### 🔍 Job Search (`job_search/`)

Scrapes LinkedIn, Indeed, Glassdoor, and Google Jobs. Scores each job 0–110 pts against your CV profile parsed from `main.tex`.

**Features:**
- Parallel scraping (4 workers) with cross-batch deduplication
- Relevance pre-filter (removes non-tech roles automatically)
- Negative keyword filter (removes sales, HR, finance, etc.)
- Score breakdown: keywords · title · seniority · recency · description · location · job type
- Company-specific search (e.g. search all open roles at a specific company)
- Exports to CSV

**Web UI tabs:**
- **Region Search** — search by role + location, see ranked results with score tooltip
- **Company Search** — search all open roles at a specific company
- **Browse Reports** — view previously saved CSV reports

### ✉️ Cover Letter Generator (`cover_letter/`)

Generates tailored cover letters in plain text and LaTeX (compiles to PDF).

**Features:**
- Two modes: *general* (broader fit) and *specific* (targeted, with metrics)
- Matches job keywords to your CV experiences automatically
- Two input methods: pick from a job search report, or paste a job URL

**Setup:** Copy `cv_data.example.py` to `cv_data.py` and fill in your info.

### 🗂 Application Log (`log/`)

Track your job applications through the hiring pipeline.

**Features:**
- Status pipeline: saved → applied → awaiting → interview → assessment → offer → rejected / withdrawn
- Sortable columns (click column headers): Status (default), Title, Company, Applied date
- Default sort: most actionable applications first (offer → interview → assessment → ...)
- Detail panel with full history of status changes
- Two input methods: pick from a job search report, or paste a job URL

---

## File Structure

```
├── main.tex                    ← YOUR CV (edit this)
├── photo.png                   ← Your photo for the CV (replace this)
│
├── job_search/
│   ├── cv_parser.py            ← Parses main.tex automatically
│   ├── searcher.py             ← Scraping engine (python-jobspy)
│   ├── scorer.py               ← CV-match scoring logic
│   ├── web.py                  ← Flask server (port 5052)
│   ├── main.py                 ← CLI entry point
│   ├── index.html              ← Web UI
│   └── run_job_search.sh       ← Launch script
│
├── cover_letter/
│   ├── cv_data.example.py      ← TEMPLATE — copy to cv_data.py and edit
│   ├── cv_data.py              ← YOUR DATA (gitignored, created from example)
│   ├── generator.py            ← Cover letter generation logic
│   ├── job_fetcher.py          ← Fetches job info from URLs
│   ├── web.py                  ← Flask server (port 5051)
│   ├── main.py                 ← CLI entry point
│   ├── index.html              ← Web UI
│   └── run.sh                  ← Launch script
│
└── log/
    ├── tracker.py              ← JSON-backed application store
    ├── web.py                  ← Flask server (port 5050)
    ├── main.py                 ← CLI entry point
    ├── index.html              ← Web UI
    ├── applications.json       ← YOUR DATA (gitignored)
    └── run.sh                  ← Launch script
```

---

## Requirements

- Python 3.10+
- `pip install python-jobspy flask requests beautifulsoup4 pandas rich`
- (Optional) `pdflatex` for compiling cover letter PDFs

Dependencies are auto-installed by each tool's `run.sh` on first run.

---

## Personal Data & Privacy

The following files are **gitignored** and stay on your machine only:

| File | Contains |
|---|---|
| `log/applications.json` | Your application history |
| `cover_letter/cv_data.py` | Your personal info + experience prose |
| `photo.png` | Your CV photo |
| `cl_*.pdf/tex/txt` | Generated cover letters |
| `cv_*.pdf` | Compiled CV PDF |
| `jobs_*.csv` | Job search reports |

---

## Scoring System

Jobs are scored against your CV profile (parsed from `main.tex`):

| Component | Max pts |
|---|---|
| Keyword match (CV skills vs job description) | 40 |
| Title match (role-specific weighted terms) | 25 |
| Seniority match | 15 |
| Recency (how recently posted) | 10 |
| Description length/quality | 10 |
| Location (Germany / remote / hybrid bonus) | 5 |
| Job type (full-time / intern match) | 5 |

Hover over any score in the Job Search web UI to see the breakdown.
