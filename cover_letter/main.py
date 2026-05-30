#!/usr/bin/env python3
"""
Cover Letter Generator
======================
Generates a tailored, ATS-friendly cover letter from a job URL.

Usage:
  # From a job URL (found in your jobs_*.html report)
  wsl bash cover_letter/run.sh --url "https://www.linkedin.com/jobs/view/4419306282" --length specific

  # General (shorter, broader) letter
  wsl bash cover_letter/run.sh --url "https://..." --length general

  # Override availability or add reference number
  wsl bash cover_letter/run.sh --url "..." --length specific --available "01.08.2026" --ref "REF-2026-042"

  # Manual input (no URL needed)
  wsl bash cover_letter/run.sh --title "Robotics Engineer" --company "KUKA AG" --length specific
"""

from __future__ import annotations

import sys
import argparse
from pathlib import Path

# ── Ensure cover_letter/ is on sys.path ───────────────────────────────────
_DIR = Path(__file__).parent
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.rule import Rule
except ImportError:
    print("[ERROR] Install rich:  pip install rich")
    sys.exit(1)

from job_fetcher import fetch_job
from generator import generate

console = Console()

BANNER = """[bold cyan]
 ╔══════════════════════════════════════════════╗
 ║        Cover Letter Generator                ║
 ║   ATS-friendly · Germany-ready · Genuine     ║
 ╚══════════════════════════════════════════════╝
[/bold cyan]"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Argument parser
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Generate a tailored cover letter from a job URL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # ── Job source (URL or manual)
    src = p.add_argument_group("Job source (provide --url OR --title + --company)")
    src.add_argument("--url", "-u", default="",
                     help="Job posting URL (LinkedIn, Indeed, Glassdoor, company site)")
    src.add_argument("--title", default="",
                     help="Job title (used if --url is omitted or scraping fails)")
    src.add_argument("--company", "-c", default="",
                     help="Company name (used if --url is omitted or scraping fails)")
    src.add_argument("--location", default="",
                     help="Job location (optional)")
    src.add_argument("--keywords", default="",
                     help="Comma-separated keywords from the job (improves matching)")

    # ── Letter settings
    letter = p.add_argument_group("Letter settings")
    letter.add_argument(
        "--length", "-l",
        choices=["general", "specific"],
        default=None,
        help=(
            "general  = shorter (~250 words), 1 experience + 1 project\n"
            "specific = detailed (~380 words), 2 experiences + 2 projects"
        ),
    )
    letter.add_argument("--available", "-a",
                        default="1 October 2026",
                        help="Availability date (default: '1 October 2026')")
    letter.add_argument("--ref", "-r", default="",
                        help="Job reference number (optional, appears in subject line)")

    # ── Output
    out = p.add_argument_group("Output")
    out.add_argument("--output-dir", "-o", default=None,
                     help="Output directory (default: D:\\Documents-CV)")
    out.add_argument("--print", action="store_true",
                     help="Print the cover letter to the terminal after saving")

    return p


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Interactive prompts for missing fields
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def prompt_missing(job: dict, args: argparse.Namespace) -> dict:
    """Fill in any missing fields interactively."""
    if not job.get("title"):
        job["title"] = args.title or Prompt.ask("[bold]Job title[/bold]")
    if not job.get("company"):
        job["company"] = args.company or Prompt.ask("[bold]Company name[/bold]")
    if not job.get("location") or job["location"] == "—":
        val = args.location or Prompt.ask("[bold]Location[/bold] (press Enter to skip)", default="")
        job["location"] = val

    # Merge any manually provided keywords
    if args.keywords:
        extra = [k.strip() for k in args.keywords.split(",") if k.strip()]
        job["keywords"] = list(set(job.get("keywords", []) + extra))

    return job


def choose_length(args: argparse.Namespace) -> str:
    if args.length:
        return args.length
    if sys.stdin.isatty():
        choice = Prompt.ask(
            "\n[bold]Letter type[/bold]",
            choices=["general", "specific"],
            default="specific",
        )
        return choice
    return "specific"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Main
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main():
    parser = build_parser()
    args = parser.parse_args()

    console.print(BANNER)

    # ── Determine search dir (where jobs_*.html files live) ───────────────
    # Heuristic: parent of this script's directory (D:\Documents-CV)
    search_dir = Path(__file__).parent.parent

    # ── Resolve output directory ──────────────────────────────────────────
    output_dir = Path(args.output_dir) if args.output_dir else search_dir

    # ── Fetch job info ────────────────────────────────────────────────────
    if args.url:
        console.print(f"\n[bold]Fetching job:[/bold] {args.url}")
        job = fetch_job(args.url, search_dir)

        if job.get("found_in", "manual") == "manual":
            console.print("[yellow]Could not fetch automatically — please fill in:[/yellow]")
        else:
            console.print(f"[green]Found in:[/green] {job.get('found_in', 'unknown')}")
    else:
        # No URL — build from manual args
        job = {
            "title": args.title,
            "company": args.company,
            "location": args.location,
            "keywords": [k.strip() for k in args.keywords.split(",") if k.strip()],
            "description": "",
            "url": "",
            "source": "manual",
            "found_in": "manual",
        }

    # ── Fill missing fields ───────────────────────────────────────────────
    job = prompt_missing(job, args)

    if not job.get("title") or not job.get("company"):
        console.print("[red]Job title and company are required. Exiting.[/red]")
        sys.exit(1)

    # ── Length ────────────────────────────────────────────────────────────
    mode = choose_length(args)

    # ── Confirm settings ──────────────────────────────────────────────────
    console.print(Panel(
        f"[bold cyan]{job['title']}[/bold cyan]\n"
        f"Company:      {job['company']}\n"
        f"Location:     {job.get('location') or '—'}\n"
        f"Keywords:     {', '.join(job.get('keywords', [])[:8]) or '(none — generic matching)'}\n"
        f"Mode:         [bold]{mode}[/bold]\n"
        f"Available:    {args.available}\n"
        f"Ref:          {args.ref or '(none)'}",
        title="[bold]Cover Letter Settings[/bold]",
        expand=False,
    ))

    # ── Generate ──────────────────────────────────────────────────────────
    console.print("\nGenerating…")
    result = generate(
        job=job,
        mode=mode,
        availability=args.available,
        ref=args.ref,
        output_dir=output_dir,
    )

    # ── Output summary ────────────────────────────────────────────────────
    console.print(Rule("[bold green]Done[/bold green]"))
    console.print(f"[green]TXT (ATS):[/green]   {result['txt'].name}")
    console.print(f"[green]LaTeX:    [/green]   {result['tex'].name}")
    if result.get("pdf"):
        console.print(f"[green]PDF:      [/green]   {result['pdf'].name}")
    else:
        console.print(
            "[dim]PDF not compiled automatically.\n"
            f"  Compile with:  pdflatex {result['tex'].name}[/dim]"
        )

    # ── Optional: print to terminal ───────────────────────────────────────
    if args.print:
        console.print(Rule("Cover Letter Preview"))
        console.print(result["txt"].read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
