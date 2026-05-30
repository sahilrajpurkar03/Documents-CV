#!/usr/bin/env python3
"""
Job Application Log
===================
Track every application, update its status, and see what is pending.

Usage:
  wsl bash log/run.sh                          # interactive dashboard
  wsl bash log/run.sh add                      # log a new application
  wsl bash log/run.sh update 5                 # update status of application #5
  wsl bash log/run.sh list                     # show all applications
  wsl bash log/run.sh list --status applied    # filter by status
  wsl bash log/run.sh list --active            # show only active (non-closed)
  wsl bash log/run.sh detail 5                 # full detail + history for #5
  wsl bash log/run.sh delete 5                 # remove an entry

Statuses (in pipeline order):
  saved → applied → awaiting → interview → assessment → offer
  rejected / withdrawn  (closed)
"""

from __future__ import annotations

import sys
import argparse
import webbrowser
from pathlib import Path

_DIR = Path(__file__).parent
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.rule import Rule
    from rich.text import Text
except ImportError:
    print("[ERROR] Install rich: pip install rich")
    sys.exit(1)

from tracker import (
    STATUSES, STATUS_COLOR, STATUS_EMOJI, ACTIVE_STATUSES,
    load_db, add_entry, update_status, update_notes,
    delete_entry, get_entry, filter_entries, pending_count,
)

console = Console()

BANNER = """[bold cyan]
 ╔══════════════════════════════════════════════╗
 ║        Job Application Log                   ║
 ║   Track · Update · Never Miss a Follow-up    ║
 ╚══════════════════════════════════════════════╝
[/bold cyan]"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Display helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _status_text(status: str) -> Text:
    color = STATUS_COLOR.get(status, "white")
    emoji = STATUS_EMOJI.get(status, "")
    return Text(f"{emoji} {status}", style=color)


def print_table(entries: list, title: str = "Applications"):
    if not entries:
        console.print("[dim]No entries found.[/dim]")
        return

    table = Table(
        title=title,
        show_header=True,
        header_style="bold magenta",
        border_style="dim",
        row_styles=["", "dim"],
        expand=True,
    )
    table.add_column("#",            width=4,  justify="right")
    table.add_column("Status",       width=14)
    table.add_column("Job Title",    min_width=26)
    table.add_column("Company",      min_width=18)
    table.add_column("Location",     min_width=14)
    table.add_column("Source",       width=10)
    table.add_column("Applied",      width=11)
    table.add_column("Last Updated", width=17)
    table.add_column("Notes",        min_width=20)

    for e in entries:
        table.add_row(
            str(e["id"]),
            _status_text(e.get("status", "")),
            e.get("title", ""),
            e.get("company", ""),
            e.get("location", "") or "—",
            e.get("source", "") or "—",
            e.get("date_applied", ""),
            e.get("last_updated", "")[:16],
            (e.get("notes", "") or "")[:45],
        )

    console.print(table)


def print_summary():
    """Print a compact status-count dashboard."""
    counts = pending_count()
    total = sum(counts.values())
    active = sum(counts[s] for s in ACTIVE_STATUSES)

    console.print(Rule("[bold]Application Pipeline[/bold]"))
    parts = []
    for status in STATUSES:
        n = counts[status]
        if n == 0:
            continue
        color = STATUS_COLOR.get(status, "white")
        emoji = STATUS_EMOJI.get(status, "")
        parts.append(f"[{color}]{emoji} {status}: {n}[/{color}]")
    console.print("  " + "   ".join(parts))
    console.print(f"\n  [bold]Total:[/bold] {total}   [bold]Active:[/bold] {active}")


def print_detail(entry: dict):
    color = STATUS_COLOR.get(entry["status"], "white")
    emoji = STATUS_EMOJI.get(entry["status"], "")

    history_lines = "\n".join(
        f"  {h['date']}  [{STATUS_COLOR.get(h['status'],'white')}]{h['status']}[/{STATUS_COLOR.get(h['status'],'white')}]"
        + (f"  — {h['note']}" if h.get("note") and h["note"] != "Added" else "")
        for h in entry.get("history", [])
    )

    console.print(Panel(
        f"[bold]{entry['title']}[/bold]  @  [cyan]{entry['company']}[/cyan]\n"
        f"Location:     {entry.get('location') or '—'}\n"
        f"Status:       [{color}]{emoji} {entry['status']}[/{color}]\n"
        f"Applied:      {entry.get('date_applied', '—')}\n"
        f"Last updated: {entry.get('last_updated', '—')}\n"
        f"Source:       {entry.get('source') or '—'}\n"
        f"URL:          {entry.get('url') or '—'}\n"
        f"Notes:        {entry.get('notes') or '—'}\n\n"
        f"[bold]History:[/bold]\n{history_lines or '  (none)'}",
        title=f"[bold magenta]Application #{entry['id']}[/bold magenta]",
        expand=False,
    ))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Interactive flows
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def interactive_add():
    console.print(Rule("[bold]Log New Application[/bold]"))
    title   = Prompt.ask("[bold]Job title[/bold]")
    company = Prompt.ask("[bold]Company[/bold]")
    url     = Prompt.ask("URL (press Enter to skip)", default="")
    location= Prompt.ask("Location (press Enter to skip)", default="")
    source  = Prompt.ask("Source", choices=["linkedin","indeed","glassdoor","google","company","other"], default="linkedin")
    notes   = Prompt.ask("Notes (press Enter to skip)", default="")

    console.print("\n[bold]Status:[/bold]")
    for i, s in enumerate(STATUSES, 1):
        color = STATUS_COLOR[s]
        console.print(f"  [{color}]{i}. {STATUS_EMOJI[s]} {s}[/{color}]")
    status_idx = Prompt.ask("Status number", default="2")
    try:
        status = STATUSES[int(status_idx) - 1]
    except (ValueError, IndexError):
        status = "applied"

    entry = add_entry(title, company, url, location, source, notes, status)
    console.print(f"\n[bold green]Logged application #{entry['id']}:[/bold green] {title} @ {company}  [{STATUS_COLOR[status]}]{STATUS_EMOJI[status]} {status}[/{STATUS_COLOR[status]}]")


def interactive_update(entry_id: int):
    entry = get_entry(entry_id)
    if not entry:
        console.print(f"[red]No application with ID {entry_id}.[/red]")
        return

    print_detail(entry)
    console.print("\n[bold]New status:[/bold]")
    for i, s in enumerate(STATUSES, 1):
        color = STATUS_COLOR[s]
        current = " [bold]← current[/bold]" if s == entry["status"] else ""
        console.print(f"  [{color}]{i}. {STATUS_EMOJI[s]} {s}[/{color}]{current}")

    status_idx = Prompt.ask("Status number (Enter to keep current)", default="")
    if status_idx.strip():
        try:
            new_status = STATUSES[int(status_idx) - 1]
        except (ValueError, IndexError):
            console.print("[red]Invalid choice, keeping current status.[/red]")
            new_status = entry["status"]
    else:
        new_status = entry["status"]

    note = Prompt.ask("Add a note (press Enter to skip)", default="")
    entry = update_status(entry_id, new_status, note)
    console.print(f"\n[bold green]Updated #{entry_id}:[/bold green] {entry['title']} @ {entry['company']} → [{STATUS_COLOR[new_status]}]{STATUS_EMOJI[new_status]} {new_status}[/{STATUS_COLOR[new_status]}]")


def interactive_dashboard():
    """Default view: summary + active applications."""
    console.print(BANNER)
    print_summary()
    console.print()
    entries = filter_entries(active_only=True)
    print_table(entries, title="Active Applications")

    if not entries:
        return

    console.print()
    action = Prompt.ask(
        "[bold]Action[/bold]  [dim](a=add · u <id>=update · d <id>=detail · Enter=quit)[/dim]",
        default=""
    )
    if action.lower().startswith("a"):
        interactive_add()
    elif action.lower().startswith("u "):
        try:
            interactive_update(int(action.split()[1]))
        except (IndexError, ValueError):
            console.print("[red]Usage: u <id>[/red]")
    elif action.lower().startswith("d "):
        try:
            entry = get_entry(int(action.split()[1]))
            if entry:
                print_detail(entry)
            else:
                console.print("[red]Not found.[/red]")
        except (IndexError, ValueError):
            console.print("[red]Usage: d <id>[/red]")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CLI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Job application tracker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = p.add_subparsers(dest="command")

    # ── add ────────────────────────────────────────────────────────────────
    a = sub.add_parser("add", help="Log a new application")
    a.add_argument("--title",    "-t", default="")
    a.add_argument("--company",  "-c", default="")
    a.add_argument("--url",      "-u", default="")
    a.add_argument("--location", "-l", default="")
    a.add_argument("--source",   "-s", default="linkedin",
                   choices=["linkedin","indeed","glassdoor","google","company","other"])
    a.add_argument("--notes",    "-n", default="")
    a.add_argument("--status",   default="applied", choices=STATUSES)

    # ── update ─────────────────────────────────────────────────────────────
    u = sub.add_parser("update", help="Update status of an application")
    u.add_argument("id", type=int)
    u.add_argument("--status", "-s", choices=STATUSES, default=None)
    u.add_argument("--notes",  "-n", default="")

    # ── list ───────────────────────────────────────────────────────────────
    ls = sub.add_parser("list", help="List applications")
    ls.add_argument("--status",  "-s", choices=STATUSES, default=None)
    ls.add_argument("--active",  "-a", action="store_true",
                    help="Show only active (non-closed) applications")
    ls.add_argument("--company", "-c", default=None)

    # ── detail ─────────────────────────────────────────────────────────────
    d = sub.add_parser("detail", help="Full detail + history for one application")
    d.add_argument("id", type=int)

    # ── delete ─────────────────────────────────────────────────────────────
    dl = sub.add_parser("delete", help="Remove an application entry")
    dl.add_argument("id", type=int)

    # ── summary ────────────────────────────────────────────────────────────
    sub.add_parser("summary", help="Pipeline summary counts")

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        interactive_dashboard()
        return

    if args.command == "add":
        if args.title and args.company:
            entry = add_entry(
                args.title, args.company, args.url,
                args.location, args.source, args.notes, args.status,
            )
            color = STATUS_COLOR[entry["status"]]
            console.print(
                f"[bold green]Logged #{entry['id']}:[/bold green] "
                f"{entry['title']} @ {entry['company']}  "
                f"[{color}]{STATUS_EMOJI[entry['status']]} {entry['status']}[/{color}]"
            )
        else:
            interactive_add()

    elif args.command == "update":
        if args.status:
            entry = update_status(args.id, args.status, args.notes)
            if entry:
                color = STATUS_COLOR[entry["status"]]
                console.print(
                    f"[bold green]Updated #{args.id}:[/bold green] "
                    f"{entry['title']} @ {entry['company']} "
                    f"→ [{color}]{STATUS_EMOJI[entry['status']]} {entry['status']}[/{color}]"
                )
            else:
                console.print(f"[red]No application with ID {args.id}.[/red]")
        else:
            interactive_update(args.id)

    elif args.command == "list":
        entries = filter_entries(
            status=args.status,
            active_only=args.active,
            company=args.company,
        )
        label = args.status or ("active" if args.active else "all")
        print_table(entries, title=f"Applications — {label}")

    elif args.command == "detail":
        entry = get_entry(args.id)
        if entry:
            print_detail(entry)
        else:
            console.print(f"[red]No application with ID {args.id}.[/red]")

    elif args.command == "delete":
        entry = get_entry(args.id)
        if not entry:
            console.print(f"[red]No application with ID {args.id}.[/red]")
            return
        if Confirm.ask(f"Delete #{args.id}: {entry['title']} @ {entry['company']}?"):
            delete_entry(args.id)
            console.print(f"[green]Deleted #{args.id}.[/green]")

    elif args.command == "summary":
        print_summary()


if __name__ == "__main__":
    main()
