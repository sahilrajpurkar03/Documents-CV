# Job Application Log

Track every application, update its status, and always know what is pending.

---

## Quick Start

```powershell
# Web UI — view pipeline, add from job report, update status in browser
wsl bash log/run.sh web
```
Opens **http://localhost:5050** in your browser.

```powershell
# CLI — interactive dashboard
wsl bash log/run.sh

# List all active applications
wsl bash log/run.sh list --active

# Update status of application #1
wsl bash log/run.sh update 1

# Full detail + history for application #3
wsl bash log/run.sh detail 3
```

---

## All Commands

| Command | Description |
|---------|-------------|
| *(no args)* | Interactive dashboard — summary + active list |
| `add` | Log a new application (interactive or via flags) |
| `update <id>` | Update status / add a note (interactive or via flags) |
| `list` | List all applications |
| `list --active` | Only active (not rejected / withdrawn) |
| `list --status interview` | Filter by a specific status |
| `list --company KUKA` | Filter by company name |
| `detail <id>` | Full record + full status history |
| `delete <id>` | Remove an entry (asks for confirmation) |
| `summary` | Pipeline count overview only |

**Non-interactive flags for `add`:**
```powershell
wsl bash log/run.sh add \
  --title "Robotics Engineer" \
  --company "KUKA AG" \
  --url "https://..." \
  --source linkedin \
  --status applied \
  --notes "Cover letter sent, specific mode"
```

**Non-interactive flags for `update`:**
```powershell
wsl bash log/run.sh update 2 --status interview --notes "Interview on 15 June, 14:00"
```

---

## Pipeline Statuses

| # | Status | Meaning |
|---|--------|---------|
| 1 | 📌 `saved` | Found but not yet applied |
| 2 | 📤 `applied` | Application submitted |
| 3 | ⏳ `awaiting` | Waiting for response |
| 4 | 🎯 `interview` | Interview scheduled or in progress |
| 5 | 🧪 `assessment` | Technical test / take-home task |
| 6 | 🎉 `offer` | Offer received |
| — | ❌ `rejected` | Explicitly rejected |
| — | ↩️  `withdrawn` | You withdrew the application |

`saved → applied → awaiting → interview → assessment → offer` is the normal flow.  
`rejected` and `withdrawn` are terminal states (excluded from `--active` view).

---

## Data Storage

All applications are stored locally in `log/applications.json`.  
This file is listed in `.gitignore` — your personal application data is **never pushed to GitHub**.

---

## File Structure

```
log/
├── web.py            ← Flask web server (http://localhost:5050)
├── index.html        ← Single-page UI — pipeline view, add from job report, edit, delete
├── main.py           ← CLI entry point
├── tracker.py        ← JSON store: add, update, query, delete
├── run.sh            ← Bash launcher  (`web` subcommand starts the UI)
└── README.md         ← This file
```

---

## Typical Workflow

```powershell
# 1. Run the job search tool and find a good match
wsl bash job_search/run.sh --region Germany

# 2. Generate a cover letter for it
wsl bash cover_letter/run.sh --url "https://..." --length specific

# 3. Log the application (web UI: click + Add Application, pick from table)
#    or CLI:
wsl bash log/run.sh add --title "Robotics Engineer" --company "KUKA" --url "https://..." --source linkedin --status applied

# 4. After hearing back, update the status
wsl bash log/run.sh update 1 --status interview --notes "Phone screen 10 June"

# 5. Check what needs follow-up
wsl bash log/run.sh list --active
```
