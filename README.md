# Job Application Toolkit

A self-hosted, privacy-first toolkit for job seekers — built around your **own CV in LaTeX**. One dashboard to find matching jobs, generate tailored cover letters, and track your applications.

---

## Quick Start

### 1. Add Your CV
Edit `main.tex` with your CV content (moderncv banking style). All tools read from this file automatically.

### 2. Add Your Cover Letter Data
```bash
cp cover_letter/cv_data.example.py cover_letter/cv_data.py
# then edit cv_data.py with your personal info, experience prose, and projects
```

### 3. Launch the Dashboard

```bash
wsl bash run.sh
```

Opens **http://localhost:5000** — one page with everything:

| Tab | What it does |
|---|---|
| 🌍 **Region Search** | Scrape LinkedIn, Indeed, StepStone, Xing, Google Jobs for your area |
| 🏢 **Company Search** | Find all open roles at a specific company |
| 🤖 **Robotics Cos** | Scan 30+ robotics company career pages directly |
| 📋 **Log** | Track every application through the hiring pipeline |

Per job row, you get four quick-action buttons:
- **📄** Generate a tailored cover letter (preview text, save to `cl_sahil.tex` + compile PDF in one click)
- **💾** Save the job as a bookmark in your log
- **📝** Log it as "applied"
- **Apply ↗** Opens the job posting

> **Note:** The `wsl` prefix is needed on Windows with WSL. On Linux/macOS, use `bash run.sh` directly.

---

## Tools

### 🔍 Job Search

Scrapes LinkedIn, Indeed, StepStone, Xing, and Google Jobs. Scores each job 0–110 pts against your CV profile parsed from `main.tex`.

**Features:**
- Parallel scraping (4 workers) with cross-batch deduplication
- Relevance pre-filter (removes non-tech roles automatically)
- Negative keyword filter (removes sales, HR, finance, etc.)
- Score breakdown tooltip: keywords · title · seniority · recency · description · location · job type
- Company-specific search and robotics company career-page scan

### ✉️ Cover Letter Generator

Generates tailored cover letters in plain text and LaTeX (compiles to PDF).

**Features:**
- Two modes: *general* (broader fit) and *specific* (targeted, with metrics)
- Matches job keywords to your CV experiences automatically
- Click 📄 on any job row → adjust options → Generate → Save & PDF
- Writes `cl_sahil.tex` and compiles `cl_sahil.pdf` automatically

**Setup:** Copy `cv_data.example.py` to `cv_data.py` and fill in your info.

### 🗂 Application Log

Track your job applications through the hiring pipeline.

**Features:**
- Status pipeline: saved → applied → awaiting → interview → assessment → offer → rejected / withdrawn
- Sortable columns (click column headers): Status (default), Title, Company, Applied date
- Default sort: most actionable applications first (offer → interview → assessment → ...)
- Detail panel with full history of status changes

---

## File Structure

```
├── main.tex                    ← YOUR CV (edit this)
├── photo.png                   ← Your photo for the CV (replace this)
├── web.py                      ← Unified Flask server (port 5000)  ← NEW
├── index.html                  ← Unified dashboard UI              ← NEW
├── run.sh                      ← Single launcher: wsl bash run.sh  ← NEW
│
├── job_search/
│   ├── cv_parser.py            ← Parses main.tex automatically
│   ├── searcher.py             ← Scraping engine (python-jobspy + custom)
│   ├── scorer.py               ← CV-match scoring logic
│   ├── web.py                  ← Standalone Flask server (port 5052)
│   └── run_job_search.sh       ← Standalone launch script
│
├── cover_letter/
│   ├── cv_data.example.py      ← TEMPLATE — copy to cv_data.py and edit
│   ├── cv_data.py              ← YOUR DATA (gitignored)
│   ├── generator.py            ← Cover letter generation logic
│   ├── job_fetcher.py          ← Fetches job info from URLs
│   ├── web.py                  ← Standalone Flask server (port 5051)
│   └── run.sh                  ← Standalone launch script
│
└── log/
    ├── tracker.py              ← JSON-backed application store
    ├── web.py                  ← Standalone Flask server (port 5050)
    ├── applications.json       ← YOUR DATA (gitignored)
    └── run.sh                  ← Standalone launch script
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
