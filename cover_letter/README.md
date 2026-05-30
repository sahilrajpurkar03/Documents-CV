# Cover Letter Generator

Generates a tailored, ATS-friendly cover letter by matching your CV against a job posting URL (from your `jobs_*.html` report or any direct link).

---

## Quick Start

```powershell
# Web UI — two tabs: pick from job report CSV, or paste any job URL
wsl bash cover_letter/run.sh web
```
Opens **http://localhost:5051** — two tabs:
- **📋 From Report** — select a `jobs_*.csv` file, browse ranked jobs, click Generate
- **🔗 From URL** — paste any job URL (LinkedIn, Indeed, company site), click Fetch then Generate

```powershell
# CLI — from a job URL
wsl bash cover_letter/run.sh --url "https://www.linkedin.com/jobs/view/4419306282" --length specific

# General (shorter) letter
wsl bash cover_letter/run.sh --url "https://..." --length general

# Without a URL — manual input
wsl bash cover_letter/run.sh --title "Robotics Engineer" --company "KUKA AG" --length specific

# With availability date and job reference number
wsl bash cover_letter/run.sh --url "https://..." --length specific --available "01.08.2026" --ref "REF-2026-042"

# Print letter to terminal as well
wsl bash cover_letter/run.sh --url "https://..." --length specific --print
```

All output is saved to `D:\Documents-CV\cl_sahil.txt / .tex / .pdf`.

---

## All Options

```
--url / -u          Job posting URL (LinkedIn, Indeed, Glassdoor, company site)
--title             Job title (used if --url is omitted or scraping fails)
--company / -c      Company name
--location          Job location (optional)
--keywords          Extra comma-separated keywords to improve matching
--length / -l       general | specific  (see below)
--available / -a    Availability date   (default: "upon agreement")
--ref / -r          Job reference number (shown in subject line)
--output-dir / -o   Output folder       (default: D:\Documents-CV)
--print             Print letter to terminal after saving
```

---

## Length Modes

| Mode | Word count | Experience entries | Project entries |
|------|------------|-------------------|-----------------|
| `general` | ~250 words | 1 most relevant | 1 most relevant |
| `specific` | ~380 words | 2 most relevant | 2 most relevant (with metrics) |

Use **`general`** for broad applications or quick submissions.  
Use **`specific`** for roles that closely match your background.

---

## Fixed Letter Structure

Every letter follows the same 4-paragraph format — only content slots change:

| # | Paragraph | What varies |
|---|-----------|-------------|
| 1 | **Opening** | Job title, company, top 3 matched skills |
| 2 | **Experience** | Most relevant roles from CV (Porsche internship ranked first) |
| 3 | **Projects / Thesis** | Most relevant projects matched to job keywords |
| 4 | **Closing** | Fixed — Mönsheim location, open to relocation across Germany, availability date |

---

## How Job Matching Works

1. **Local HTML cache** — searches all `jobs_*.html` files in `D:\Documents-CV` for the URL, extracting keywords already computed by the job search tool (fastest, no network needed)
2. **Web scrape** — if not in cache, fetches the URL directly and extracts keywords
3. **Manual fallback** — prompts for title and company if both methods fail

Keywords are matched against tagged CV entries in `cv_data.py` to select the most relevant experiences and projects.

---

## Output Files

All files are saved directly to `D:\Documents-CV` (same folder as your CV):

| File | Purpose |
|------|---------|
| `cl_sahil.txt` | ATS-safe plain text — paste directly into application portals |
| `cl_sahil.tex` | LaTeX source — compile to PDF for email/upload submissions |
| `cl_sahil.pdf` | PDF (generated automatically if pdflatex is available) |

Each run overwrites the same three files, so your folder stays clean.

**Compile to PDF manually** (MiKTeX is already installed):
```powershell
# From D:\Documents-CV
pdflatex cl_sahil.tex
```

Or via WSL texlive:
```bash
pdflatex /mnt/d/Documents-CV/cl_sahil.tex
```

---

## File Structure

```
cover_letter/
├── web.py            ← Flask web server (http://localhost:5051)
├── index.html        ← Single-page UI — job picker + generate button
├── main.py           ← CLI entry point
├── cv_data.py        ← All CV content (experiences, projects, skill phrases) with tags
├── job_fetcher.py    ← Fetches job info from local HTML or web scraping
├── generator.py      ← Keyword matching, template filling, LaTeX renderer
├── requirements.txt  ← Python dependencies (auto-installed by run.sh)
└── run.sh            ← Bash launcher  (`web` subcommand starts the UI)
```

Output files in `D:\Documents-CV`:
```
cl_sahil.txt   ← plain text (always overwritten)
cl_sahil.tex   ← LaTeX source
cl_sahil.pdf   ← compiled PDF (if pdflatex available)
```

---

## Updating CV Content

Edit [cover_letter/cv_data.py](cv_data.py) to:
- Add/edit experience text (`text_general`, `text_specific`)
- Add new projects
- Adjust `tags` to improve keyword matching for specific roles
- Update `PERSONAL` if contact details change
