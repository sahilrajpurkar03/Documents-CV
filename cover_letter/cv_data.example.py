"""
CV Data for Cover Letter Generation
=====================================
HOW TO USE:
  1. Copy this file to cv_data.py (same folder):
         cp cover_letter/cv_data.example.py cover_letter/cv_data.py
  2. Replace all placeholder values with your real information.
  3. cv_data.py is gitignored — your personal data stays private.

STRUCTURE:
  PERSONAL       → your contact info (name, email, phone, LinkedIn, …)
  EXPERIENCES    → work/internship entries with keyword tags + prose snippets
  PROJECTS       → thesis and personal projects, same format
  SKILL_PHRASES  → (keyword_tag, human-readable phrase) used in CL opening line
"""

# ── Personal info ─────────────────────────────────────────────────────────
PERSONAL = {
    "name":         "Your Full Name",
    "address":      "City, Country",
    "phone":        "+XX XXXXXXXXXXX",
    "email":        "you@example.com",
    "linkedin":     "linkedin.com/in/your-profile",
    "github":       "github.com/your-username",
    "education":    "M.Sc. Your Degree, Your University (YYYY–YYYY)",
    "degree_short": "M.Sc. Your Degree",
    "university":   "Your University",
}

# ── Experience entries ─────────────────────────────────────────────────────
# Each entry needs:
#   id, title, company, period, location
#   tags          → list of lowercase keyword strings (matched against job keywords)
#   text_general  → 1-2 sentence description for broad applications
#   text_specific → 3-4 sentence description with metrics for targeted applications
#   base_weight   → tiebreaker score (higher = shown first); use 3 for current role

EXPERIENCES = [
    {
        "id": "current_role",
        "title": "Your Current Job Title",
        "company": "Your Current Company",
        "period": "Month YYYY – present",
        "location": "City, Country",
        "tags": [
            # Add lowercase keywords that describe what you did/used:
            # "ros2", "python", "c++", "robot", "simulation", "navigation", …
        ],
        "text_general": (
            "One-to-two sentence overview of your current role suitable for any application. "
            "Mention your main tools and responsibilities."
        ),
        "text_specific": (
            "Three-to-four sentence targeted description with specific metrics, tools, and outcomes. "
            "Reference project names, numbers, and technical details. "
            "This version is used when the cover letter mode is set to 'specific'."
        ),
        "base_weight": 3,  # highest priority — current role
    },
    {
        "id": "previous_role",
        "title": "Your Previous Job / Research Title",
        "company": "Previous Company or University",
        "period": "Month YYYY – Month YYYY",
        "location": "City, Country",
        "tags": [
            # "machine learning", "python", "research", "opencv", …
        ],
        "text_general": (
            "Brief overview of your previous role."
        ),
        "text_specific": (
            "Detailed version with specific project names, metrics, and tools used."
        ),
        "base_weight": 2,
    },
    # Add more experiences as needed …
]

# ── Thesis & Project entries ───────────────────────────────────────────────
PROJECTS = [
    {
        "id": "thesis",
        "title": "Master Thesis: Your Thesis Title",
        "period": "Month YYYY – Month YYYY",
        "tags": [
            # keywords matching your thesis topic
        ],
        "text_general": (
            "One sentence summary of your thesis."
        ),
        "text_specific": (
            "Three-to-four sentence detailed description with methodology, datasets, and results."
        ),
        "base_weight": 2,
    },
    {
        "id": "project_1",
        "title": "A Personal or Course Project",
        "tags": [
            # keywords
        ],
        "text_general": (
            "Brief overview of the project."
        ),
        "text_specific": (
            "Detailed description with tools and outcomes."
        ),
        "base_weight": 1,
    },
    # Add more projects as needed …
]

# ── Top-level skill phrases (used in opening paragraph) ───────────────────
# Format: (lowercase_tag, "Human-readable phrase used in cover letter")
# The tag must match something in the job keywords (scraped from the posting).
# Order by relevance to the roles you're targeting most.
SKILL_PHRASES = [
    ("ros2",            "ROS2"),
    ("ros",             "ROS/ROS2"),
    ("python",          "Python"),
    ("c++",             "C++"),
    ("machine learning","machine learning"),
    ("computer vision", "computer vision"),
    ("simulation",      "robot simulation"),
    ("embedded",        "embedded systems"),
    ("docker",          "Docker/Linux"),
    # Add more (tag, phrase) pairs matching your skills …
]
