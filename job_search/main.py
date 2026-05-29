#!/usr/bin/env python3
"""
Job Search Tool
===============
Reads your CV (main.tex), searches LinkedIn / Indeed / Glassdoor / Google Jobs
for matching roles, and ranks them by fit score.

Usage:
  python main.py                        # interactive menu
  python main.py --region Germany       # skip region prompt
  python main.py --region Germany --top 30 --hours 336
  python main.py --help

Requirements:
  pip install -r requirements.txt
"""

from __future__ import annotations

import sys
import os
import argparse
import csv
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# ── Add the job_search package directory to sys.path ──────────────────────
_DIR = Path(__file__).parent
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))

# ── Rich for pretty terminal output ───────────────────────────────────────
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich import print as rprint
    from rich.rule import Rule
    from rich.text import Text
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    print("[ERROR] 'rich' not found. Run: pip install rich")
    sys.exit(1)

from cv_parser import parse_cv, CVProfile
from searcher import REGIONS, DEFAULT_SEARCH_TERMS, search_jobs, JobListing
from scorer import rank_listings, score_label, score_color

console = Console()

BANNER = """
[bold cyan]
 ╔══════════════════════════════════════════════════════╗
 ║          AI-Powered Job Search Tool                  ║
 ║    LinkedIn · Indeed · Glassdoor · Google Jobs       ║
 ╚══════════════════════════════════════════════════════╝
[/bold cyan]
"""

# ---------------------------------------------------------------------------
# CV path resolution
# ---------------------------------------------------------------------------

def find_cv(hint: Optional[str] = None) -> str:
    """Find main.tex relative to the script or parent directory."""
    candidates = [
        hint,
        "main.tex",
        "../main.tex",
        str(Path(__file__).parent.parent / "main.tex"),
    ]
    for c in candidates:
        if c and Path(c).exists():
            return str(Path(c).resolve())
    raise FileNotFoundError(
        "Cannot find main.tex. Run this script from the D:\\Documents-CV folder "
        "or pass --cv <path>."
    )


# ---------------------------------------------------------------------------
# Region selection
# ---------------------------------------------------------------------------

def prompt_regions() -> List[str]:
    """Interactive multi-select region picker."""
    console.print("\n[bold]Available regions:[/bold]")
    region_list = list(REGIONS.keys())
    for i, name in enumerate(region_list, 1):
        r = REGIONS[name]
        console.print(f"  [cyan]{i}[/cyan]. {r['flag']} {name}")
    console.print()

    raw = Prompt.ask(
        "Enter region numbers (comma-separated) or names",
        default="1"
    )

    selected = []
    for token in raw.replace(" ", "").split(","):
        token = token.strip()
        if token.isdigit():
            idx = int(token) - 1
            if 0 <= idx < len(region_list):
                selected.append(region_list[idx])
            else:
                console.print(f"[yellow]Skipping invalid index: {token}[/yellow]")
        elif token in REGIONS:
            selected.append(token)
        else:
            # Case-insensitive match
            for name in region_list:
                if name.lower() == token.lower():
                    selected.append(name)
                    break
            else:
                console.print(f"[yellow]Unknown region '{token}', skipping.[/yellow]")

    if not selected:
        console.print("[red]No valid regions selected. Defaulting to Germany.[/red]")
        selected = ["Germany"]
    return list(dict.fromkeys(selected))  # deduplicate, preserve order


# ---------------------------------------------------------------------------
# Results display
# ---------------------------------------------------------------------------

def display_results(listings: List[JobListing], region_name: str, top_n: int):
    """Print a rich ranked table of job listings."""
    if not listings:
        console.print(f"\n[yellow]No results found for {region_name}.[/yellow]")
        return

    console.print(Rule(f"[bold]{REGIONS[region_name]['flag']} {region_name} — Top {min(top_n, len(listings))} Matches[/bold]"))

    table = Table(
        show_header=True,
        header_style="bold magenta",
        border_style="dim",
        row_styles=["", "dim"],
        expand=True,
    )
    table.add_column("#", width=4, justify="right")
    table.add_column("Score", width=7, justify="center")
    table.add_column("Match", width=10)
    table.add_column("Job Title", min_width=28)
    table.add_column("Company", min_width=20)
    table.add_column("Location", min_width=16)
    table.add_column("Posted", width=11)
    table.add_column("Source", width=10)
    table.add_column("Salary", min_width=12)

    for i, job in enumerate(listings[:top_n], 1):
        color = score_color(job.score)
        label = score_label(job.score)
        table.add_row(
            str(i),
            f"[{color}]{job.score:.0f}/100[/{color}]",
            f"[{color}]{label}[/{color}]",
            job.title or "—",
            job.company or "—",
            job.location or "—",
            job.date_posted[:10] if job.date_posted else "—",
            job.source or "—",
            job.salary or "—",
        )

    console.print(table)


def display_detail(job: JobListing):
    """Show full details for a single job."""
    color = score_color(job.score)
    label = score_label(job.score)
    console.print(Panel(
        f"[bold]{job.title}[/bold]\n"
        f"[cyan]{job.company}[/cyan] · {job.location}\n"
        f"Score: [{color}]{job.score:.0f}/100 ({label})[/{color}]\n"
        f"Source: {job.source}  |  Posted: {job.date_posted}\n"
        f"Salary: {job.salary or 'Not listed'}\n\n"
        f"[bold]Matched Keywords:[/bold] {', '.join(job.matched_keywords[:15]) or 'None'}\n\n"
        f"[bold]Description (excerpt):[/bold]\n"
        f"{(job.description or '')[:800]}{'...' if len(job.description or '') > 800 else ''}",
        title="[bold magenta]Job Detail[/bold magenta]",
        expand=False,
    ))
    if job.url:
        console.print(f"[blue underline]Apply: {job.url}[/blue underline]")


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_csv(listings: List[JobListing], region_name: str, output_dir: Path):
    """Save ranked results to a CSV file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    fname = output_dir / f"jobs_{region_name.lower()}_{timestamp}.csv"
    if not listings:
        return None

    fieldnames = ["score", "match_quality", "title", "company", "location",
                  "source", "date_posted", "salary", "matched_keywords", "url"]
    with open(fname, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for job in listings:
            row = job.to_dict()
            row["match_quality"] = score_label(job.score)
            writer.writerow({k: row.get(k, "") for k in fieldnames})
    return fname


def export_html(listings: List[JobListing], region_name: str, output_dir: Path, cv: CVProfile):
    """Save a styled HTML report."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    fname = output_dir / f"jobs_{region_name.lower()}_{timestamp}.html"
    flag = REGIONS[region_name]["flag"]

    rows_html = []
    for i, job in enumerate(listings, 1):
        color_map = {
            "Excellent": "#22c55e",
            "Very Good": "#86efac",
            "Good": "#fbbf24",
            "Fair": "#f97316",
            "Low": "#ef4444",
        }
        label = score_label(job.score)
        color = color_map.get(label, "#888")
        apply_link = (f'<a href="{job.url}" target="_blank">Apply ↗</a>'
                      if job.url else "—")
        rows_html.append(f"""
        <tr>
          <td>{i}</td>
          <td style="color:{color};font-weight:bold">{job.score:.0f}/100</td>
          <td style="color:{color}">{label}</td>
          <td><strong>{job.title or '—'}</strong></td>
          <td>{job.company or '—'}</td>
          <td>{job.location or '—'}</td>
          <td>{job.date_posted[:10] if job.date_posted else '—'}</td>
          <td>{job.source or '—'}</td>
          <td>{job.salary or '—'}</td>
          <td style="font-size:0.8em">{', '.join(job.matched_keywords[:8])}</td>
          <td>{apply_link}</td>
        </tr>""")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Job Results — {flag} {region_name}</title>
<style>
  body {{ font-family: 'Segoe UI', sans-serif; background:#0f172a; color:#e2e8f0; padding:24px; }}
  h1 {{ color:#7dd3fc; }}
  .meta {{ color:#94a3b8; margin-bottom:16px; font-size:0.9em; }}
  table {{ border-collapse:collapse; width:100%; font-size:0.88em; }}
  th {{ background:#1e3a5f; color:#7dd3fc; padding:8px 12px; text-align:left;
        position:sticky; top:0; }}
  td {{ padding:6px 12px; border-bottom:1px solid #1e293b; vertical-align:top; }}
  tr:hover td {{ background:#1e293b; }}
  a {{ color:#38bdf8; }}
  .badge {{ display:inline-block; padding:2px 8px; border-radius:4px;
            background:#1e3a5f; font-size:0.78em; margin:1px; }}
</style>
</head>
<body>
<h1>{flag} Job Search Results — {region_name}</h1>
<div class="meta">
  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} &nbsp;|&nbsp;
  Candidate: {cv.name} &nbsp;|&nbsp;
  Total results: {len(listings)}
</div>
<table>
  <thead>
    <tr>
      <th>#</th><th>Score</th><th>Match</th><th>Title</th><th>Company</th>
      <th>Location</th><th>Posted</th><th>Source</th><th>Salary</th>
      <th>Matched Skills</th><th>Link</th>
    </tr>
  </thead>
  <tbody>
    {''.join(rows_html)}
  </tbody>
</table>
</body>
</html>"""

    fname.write_text(html, encoding="utf-8")
    return fname


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------

def run(
    regions: List[str],
    cv_path: str,
    top_n: int = 40,
    results_per_term: int = 15,
    hours_old: int = 504,   # 3 weeks
    export: bool = True,
    open_html: bool = False,
    sites: Optional[List[str]] = None,
):
    console.print(BANNER)

    # ── Parse CV ────────────────────────────────────────────────────────
    console.print(f"[bold]Reading CV:[/bold] {cv_path}")
    try:
        cv = parse_cv(cv_path)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    console.print(Panel(
        f"[bold cyan]{cv.name}[/bold cyan]\n"
        f"Location: {cv.location}  |  Education: {cv.education_level}\n"
        f"Experience: ~{cv.experience_years} years\n"
        f"Top skills: {', '.join(list(cv.all_keywords())[:12])}",
        title="CV Profile",
        expand=False,
    ))

    # ── Derive search terms from CV keywords + defaults ────────────────
    search_terms = DEFAULT_SEARCH_TERMS  # already tailored for this profile

    output_dir = Path(cv_path).parent
    all_exported = []

    for region_name in regions:
        console.print(f"\n[bold cyan]{'─'*50}[/bold cyan]")
        console.print(f"[bold]{REGIONS[region_name]['flag']}  Searching in {region_name}...[/bold]")
        console.print(f"[dim]Sites: {sites or ['linkedin','indeed','glassdoor','google']} | "
                      f"Terms: {len(search_terms)} | Per term: {results_per_term}[/dim]\n")

        # ── Search ──────────────────────────────────────────────────────
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
            console=console,
        ) as progress:
            task = progress.add_task("Fetching jobs...", total=None)
            listings = search_jobs(
                region_name=region_name,
                search_terms=search_terms,
                results_per_term=results_per_term,
                sites=sites,
                hours_old=hours_old,
                verbose=True,
            )
            progress.update(task, description="Scoring & ranking...")
            ranked = rank_listings(listings, cv, top_n=top_n)

        # ── Display ─────────────────────────────────────────────────────
        display_results(ranked, region_name, top_n)

        # ── Score distribution summary ───────────────────────────────────
        if ranked:
            buckets = {"Excellent": 0, "Very Good": 0, "Good": 0, "Fair": 0, "Low": 0}
            for job in ranked:
                buckets[score_label(job.score)] += 1
            console.print(
                f"\n[dim]Distribution: "
                + "  ".join(f"{k}: {v}" for k, v in buckets.items() if v > 0)
                + "[/dim]"
            )

        # ── Export ──────────────────────────────────────────────────────
        if export and ranked:
            csv_path = export_csv(ranked, region_name, output_dir)
            html_path = export_html(ranked, region_name, output_dir, cv)
            if csv_path:
                console.print(f"[green]CSV saved:[/green] {csv_path.name}")
            if html_path:
                console.print(f"[green]HTML saved:[/green] {html_path.name}")
                all_exported.append(html_path)
                if open_html:
                    webbrowser.open(html_path.as_uri())

    # ── Interactive detail viewer ────────────────────────────────────────
    if ranked and sys.stdin.isatty():
        console.print()
        if Confirm.ask("[bold]View details for a specific job?[/bold]", default=False):
            idx_str = Prompt.ask("Enter job number (from last region)")
            try:
                idx = int(idx_str) - 1
                if 0 <= idx < len(ranked):
                    display_detail(ranked[idx])
                else:
                    console.print("[red]Invalid number.[/red]")
            except ValueError:
                console.print("[red]Please enter a number.[/red]")

    if all_exported:
        console.print(f"\n[bold green]Reports saved to:[/bold green] {output_dir}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Job search tool powered by your CV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--region", "-r",
        nargs="*",
        help=f"Region(s) to search. Choices: {list(REGIONS)}. "
             "Omit for interactive selection.",
    )
    p.add_argument("--cv", default=None, help="Path to main.tex (auto-detected if omitted)")
    p.add_argument("--top", type=int, default=40, help="Number of top results per region (default 40)")
    p.add_argument("--per-term", type=int, default=15, help="Results fetched per search term (default 15)")
    p.add_argument("--hours", type=int, default=504, help="Maximum age of listings in hours (default 504 = 3 weeks)")
    p.add_argument(
        "--sites", nargs="*",
        default=["linkedin", "indeed", "glassdoor", "google"],
        help="Job sites to query (default: linkedin indeed glassdoor google)",
    )
    p.add_argument("--no-export", action="store_true", help="Skip saving CSV/HTML reports")
    p.add_argument("--open", action="store_true", help="Open HTML report in browser automatically")
    return p


def main():
    parser = build_parser()
    args = parser.parse_args()

    # ── CV path ──────────────────────────────────────────────────────────
    try:
        cv_path = find_cv(args.cv)
    except FileNotFoundError:
        # Try running from D:\Documents-CV
        fallback = Path(__file__).parent.parent / "main.tex"
        if fallback.exists():
            cv_path = str(fallback)
        else:
            console.print("[red]Cannot find main.tex. Pass --cv <path>[/red]")
            sys.exit(1)

    # ── Regions ──────────────────────────────────────────────────────────
    if args.region:
        regions = []
        for r in args.region:
            if r in REGIONS:
                regions.append(r)
            else:
                console.print(f"[yellow]Unknown region '{r}', skipping.[/yellow]")
        if not regions:
            console.print("[red]No valid regions given.[/red]")
            sys.exit(1)
    else:
        regions = prompt_regions()

    run(
        regions=regions,
        cv_path=cv_path,
        top_n=args.top,
        results_per_term=args.per_term,
        hours_old=args.hours,
        export=not args.no_export,
        open_html=args.open,
        sites=args.sites,
    )


if __name__ == "__main__":
    main()
