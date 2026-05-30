"""
Cover Letter Generator
======================
Matches job keywords against CV entries, fills a fixed template,
and outputs:
  - Plain .txt  (ATS-safe, copy-paste ready)
  - LaTeX .tex  (compile with pdflatex for a PDF submission)
"""

from __future__ import annotations

import re
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional

from cv_data import (
    PERSONAL, EXPERIENCES, PROJECTS, SKILL_PHRASES,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Matching
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _score(entry: dict, job_keywords: List[str]) -> float:
    """
    Score a CV entry against job keywords.
    Each tag match scores 1 point, weighted by base_weight.
    """
    kw_lower = {k.lower() for k in job_keywords}
    matches = sum(1 for tag in entry["tags"] if tag.lower() in kw_lower)
    return matches * entry.get("base_weight", 1) + entry.get("base_weight", 1) * 0.1


def select_experiences(job_keywords: List[str], n: int = 2) -> List[dict]:
    """Return top-n experiences sorted by match score."""
    scored = sorted(EXPERIENCES, key=lambda e: _score(e, job_keywords), reverse=True)
    return scored[:n]


def select_projects(job_keywords: List[str], n: int = 2) -> List[dict]:
    """Return top-n projects/thesis entries sorted by match score."""
    scored = sorted(PROJECTS, key=lambda p: _score(p, job_keywords), reverse=True)
    return scored[:n]


def top_skill_phrases(job_keywords: List[str], n: int = 3) -> List[str]:
    """
    Pick the n best matching canonical skill phrases from SKILL_PHRASES,
    falling back to the first n entries if no match.
    """
    kw_lower = {k.lower() for k in job_keywords}
    matched = [phrase for tag, phrase in SKILL_PHRASES if tag in kw_lower]
    # Deduplicate while preserving order
    seen, unique = set(), []
    for p in matched:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    # Fallback: pull from top of SKILL_PHRASES
    if len(unique) < n:
        for _, phrase in SKILL_PHRASES:
            if phrase not in seen:
                seen.add(phrase)
                unique.append(phrase)
            if len(unique) >= n:
                break
    return unique[:n]


def _skill_list(phrases: List[str]) -> str:
    """Format ['A', 'B', 'C'] → 'A, B, and C'"""
    if not phrases:
        return "robotics software development"
    if len(phrases) == 1:
        return phrases[0]
    return ", ".join(phrases[:-1]) + f", and {phrases[-1]}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Template — FIXED STRUCTURE, variable content slots
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# Paragraph 1 — Opening       (job title, company, top 3 matched skills)
# Paragraph 2 — Experience    (1-2 entries from EXPERIENCES)
# Paragraph 3 — Project/Thesis(1-2 entries from PROJECTS)
# Paragraph 4 — Closing       (location, availability, call to action)
#
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _opening(job_title: str, company: str, skill_phrase: str, mode: str) -> str:
    if mode == "general":
        return (
            f"I am writing to apply for the {job_title} position at {company}. "
            f"With a {PERSONAL['degree_short']} from {PERSONAL['university']} and "
            f"over five years of experience spanning research and applied engineering, "
            f"I offer a strong foundation in {skill_phrase}."
        )
    else:  # specific
        return (
            f"I am writing to apply for the {job_title} position at {company}. "
            f"My hands-on experience in {skill_phrase} — built across industry "
            f"internships and three years of research — directly addresses the "
            f"core technical requirements outlined in your job posting."
        )


def _experience_block(experiences: List[dict], mode: str) -> str:
    key = "text_specific" if mode == "specific" else "text_general"
    # Always put the most recent role (highest base_weight) first
    ordered = sorted(experiences, key=lambda e: e.get("base_weight", 0), reverse=True)
    parts = [e[key] for e in ordered]
    if len(parts) == 1:
        return parts[0]
    # Join two entries with a paragraph break
    return parts[0] + "\n\n" + parts[1]


def _project_block(projects: List[dict], mode: str) -> str:
    key = "text_specific" if mode == "specific" else "text_general"
    n = 2 if mode == "specific" else 1
    parts = [p[key] for p in projects[:n]]
    return " ".join(parts)


def _closing(company: str, availability: str) -> str:
    return (
        f"I am currently based in Dortmund, Germany, with no relocation required. "
        f"I am available {availability} and would welcome the opportunity to discuss "
        f"my application in a personal interview. Thank you for your consideration."
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Plain-text renderer
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def render_text(
    job: dict,
    mode: str,
    availability: str,
    ref: str = "",
) -> str:
    """Build the ATS-safe plain-text cover letter."""
    p = PERSONAL
    today = datetime.now().strftime("%d %B %Y")

    title = job.get("title", "")
    company = job.get("company", "")
    location = job.get("location", "")

    job_keywords = job.get("keywords", [])
    n_exp = 2 if mode == "specific" else 1
    n_proj = 2 if mode == "specific" else 1

    exps = select_experiences(job_keywords, n=n_exp)
    projs = select_projects(job_keywords, n=n_proj)
    skills = top_skill_phrases(job_keywords, n=3)
    skill_str = _skill_list(skills)

    subject_ref = f" (Ref: {ref})" if ref else ""
    subject = f"Application for {title}{subject_ref}"

    lines = [
        p["name"],
        p["address"],
        p["phone"],
        p["email"],
        p["linkedin"],
        "",
        today,
        "",
    ]

    if company:
        lines.append(company)
    if location and location != "—":
        lines.append(location)
    lines += ["", f"Subject: {subject}", "", "Dear Hiring Team,", ""]

    # Paragraphs
    lines.append(_opening(title, company, skill_str, mode))
    lines.append("")
    lines.append(_experience_block(exps, mode))
    lines.append("")
    lines.append(_project_block(projs, mode))
    lines.append("")
    lines.append(_closing(company, availability))
    lines += ["", "Sincerely,", "", p["name"]]

    return "\n".join(lines)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LaTeX renderer
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _tex_escape(text: str) -> str:
    """Escape special LaTeX characters in plain text."""
    replacements = [
        ("\\", r"\textbackslash{}"),
        ("&",  r"\&"),
        ("%",  r"\%"),
        ("$",  r"\$"),
        ("#",  r"\#"),
        ("_",  r"\_"),
        ("{",  r"\{"),
        ("}",  r"\}"),
        ("~",  r"\textasciitilde{}"),
        ("^",  r"\textasciicircum{}"),
        ("–",  r"--"),
        ("—",  r"---"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def render_latex(
    job: dict,
    mode: str,
    availability: str,
    ref: str = "",
) -> str:
    """Build the LaTeX source for a professional cover letter."""
    p = PERSONAL

    title = job.get("title", "")
    company = job.get("company", "")
    location = job.get("location", "")

    job_keywords = job.get("keywords", [])
    n_exp = 2 if mode == "specific" else 1
    n_proj = 2 if mode == "specific" else 1

    exps = select_experiences(job_keywords, n=n_exp)
    projs = select_projects(job_keywords, n=n_proj)
    skills = top_skill_phrases(job_keywords, n=3)
    skill_str = _skill_list(skills)

    subject_ref = f" (Ref: {_tex_escape(ref)})" if ref else ""
    subject = f"Application for {_tex_escape(title)}{subject_ref}"

    opening   = _tex_escape(_opening(title, company, skill_str, mode))
    exp_block = _tex_escape(_experience_block(exps, mode))
    proj_block = _tex_escape(_project_block(projs, mode))
    closing   = _tex_escape(_closing(company, availability))

    recipient_lines = []
    if company and company != "—":
        recipient_lines.append(_tex_escape(company))
    if location and location not in ("—", ""):
        recipient_lines.append(_tex_escape(location))
    recipient_block = " \\\\\n".join(recipient_lines) if recipient_lines else ""

    tex = r"""\documentclass[a4paper,11pt]{article}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[top=2.5cm, bottom=2.5cm, left=2.8cm, right=2.8cm]{geometry}
\usepackage{parskip}
\usepackage{lmodern}
\usepackage[hidelinks]{hyperref}
\pagestyle{empty}
\setlength{\parskip}{0.9em}

\begin{document}

%% ── Header ──────────────────────────────────────────────────────────────
\begin{flushright}
  \textbf{""" + _tex_escape(p["name"]) + r"""} \\
  """ + _tex_escape(p["address"]) + r""" \\
  """ + _tex_escape(p["phone"]) + r""" \\
  \href{mailto:""" + p["email"] + r"""}{""" + _tex_escape(p["email"]) + r"""} \\
  \href{https://""" + p["linkedin"] + r"""}{""" + _tex_escape(p["linkedin"]) + r"""}
\end{flushright}

\today

%% ── Recipient ───────────────────────────────────────────────────────────
""" + (recipient_block + "\n\n" if recipient_block else "") + r"""
\textbf{""" + subject + r"""}

Dear Hiring Team,

""" + opening + r"""

""" + exp_block + r"""

""" + proj_block + r"""

""" + closing + r"""

\vspace{1.2em}
Sincerely,

\vspace{1.5em}
\textbf{""" + _tex_escape(p["name"]) + r"""}

\end{document}
"""
    return tex


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Compile LaTeX → PDF
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def compile_pdf(tex_path: Path) -> Optional[Path]:
    """
    Run pdflatex on tex_path.  Returns the PDF path on success, else None.
    Tries pdflatex from PATH (works in WSL if texlive is installed,
    or via MiKTeX if on Windows PATH).
    """
    pdflatex = shutil.which("pdflatex")
    if not pdflatex:
        return None

    try:
        result = subprocess.run(
            [pdflatex, "-interaction=nonstopmode", "-output-directory",
             str(tex_path.parent), str(tex_path)],
            capture_output=True, text=True, timeout=60
        )
        pdf = tex_path.with_suffix(".pdf")
        if result.returncode == 0 and pdf.exists():
            # Remove auxiliary files
            for ext in (".aux", ".log", ".out"):
                tex_path.with_suffix(ext).unlink(missing_ok=True)
            return pdf
    except Exception:
        pass
    return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Main entry point
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _safe_filename(text: str, max_len: int = 30) -> str:
    """Convert arbitrary text to a safe filename component."""
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[\s_-]+", "_", text)
    return text[:max_len]


def generate(
    job: dict,
    mode: str,
    availability: str,
    ref: str,
    output_dir: Path,
) -> dict:
    """
    Generate cover letter files and return a dict of paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    company_slug = _safe_filename(job.get("company", "company"))
    title_slug   = _safe_filename(job.get("title", "role"))
    base_name    = f"cover_letter_{company_slug}_{title_slug}"

    # Plain text
    txt_path = output_dir / f"{base_name}.txt"
    txt_path.write_text(render_text(job, mode, availability, ref), encoding="utf-8")

    # LaTeX
    tex_path = output_dir / f"{base_name}.tex"
    tex_path.write_text(render_latex(job, mode, availability, ref), encoding="utf-8")

    # Try to compile PDF
    pdf_path = compile_pdf(tex_path)

    return {
        "txt": txt_path,
        "tex": tex_path,
        "pdf": pdf_path,
        "base_name": base_name,
    }
