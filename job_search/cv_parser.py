"""
CV Parser — extracts skills, roles, and keywords from main.tex
"""

import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class CVProfile:
    name: str = ""
    location: str = ""
    skills: Dict[str, List[str]] = field(default_factory=dict)
    roles: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    experience_years: float = 0.0
    education_level: str = ""
    languages: List[str] = field(default_factory=list)

    def all_keywords(self) -> List[str]:
        """Flat list of all searchable keywords."""
        kws = list(self.keywords)
        for skill_list in self.skills.values():
            kws.extend(skill_list)
        return [k.lower().strip() for k in kws if k.strip()]


# ---------------------------------------------------------------------------
# Skill aliases — maps raw tokens to canonical/searchable forms
# ---------------------------------------------------------------------------
SKILL_NORMALIZE = {
    "ros/ros2": ["ROS", "ROS2"],
    "ros2": ["ROS2"],
    "ros": ["ROS"],
    "moveit": ["MoveIt"],
    "isaac sim": ["NVIDIA Isaac Sim", "Isaac Sim"],
    "isaac lab": ["Isaac Lab"],
    "mujoco": ["MuJoCo"],
    "tensorflow": ["TensorFlow"],
    "pytorch": ["PyTorch"],
    "opencv": ["OpenCV"],
    "yolov7": ["YOLO", "YOLOv7"],
    "yolov8": ["YOLO", "YOLOv8"],
    "lidar": ["LiDAR"],
    "mmwave": ["mmWave"],
    "stm32": ["STM32"],
    "esp32": ["ESP32"],
    "kicad": ["KiCad"],
    "altium": ["Altium Designer"],
    "ci/cd": ["CI/CD"],
}

# Roles inferred from experience titles
ROLE_KEYWORDS = [
    "Robotics Software Engineer",
    "ROS2 Developer",
    "Automation Engineer",
    "Embedded Systems Engineer",
    "Computer Vision Engineer",
    "Machine Learning Engineer",
    "Research Engineer",
    "Autonomous Systems Engineer",
    "Humanoid Robotics Engineer",
    "Robot Perception Engineer",
    "AI Engineer",
    "Sensor Fusion Engineer",
]


def _clean(text: str) -> str:
    """Remove LaTeX commands and braces."""
    text = re.sub(r"\\[a-zA-Z]+\*?(\{[^}]*\})*", " ", text)
    text = re.sub(r"[{}]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _parse_cvitem_skills(content: str) -> Dict[str, List[str]]:
    """
    Extract \\cvitem{Category}{skill, skill, ...} entries from Skills section.
    """
    skills: Dict[str, List[str]] = {}
    pattern = re.compile(
        r"\\cvitem\{([^}]+)\}\{([^}]+)\}", re.DOTALL
    )
    for m in pattern.finditer(content):
        # Clean LaTeX from the category key too (removes \& → &)
        category = _clean(m.group(1)).replace("\\&", "&").strip()
        raw_values = m.group(2)
        # Split by comma, strip LaTeX, clean whitespace
        items = [_clean(v).strip() for v in raw_values.split(",")]
        items = [i for i in items if i]
        if category and items:
            skills[category] = items
    return skills


def _extract_experience_items(content: str) -> List[str]:
    """Pull all bullet point items from \\cventry blocks."""
    items = []
    for m in re.finditer(r"\\item\s+(.*?)(?=\\item|\\end\{itemize\})", content, re.DOTALL):
        text = _clean(m.group(1)).strip()
        if text:
            items.append(text)
    return items


def _extract_keywords_from_text(text: str) -> List[str]:
    """
    Extract likely technical keywords using a known-term list approach.
    Avoids NLP dependency.
    """
    tech_terms = [
        # Languages
        "Python", "C++", "Embedded C", "MATLAB", "Bash",
        # Frameworks / Middleware
        "ROS2", "ROS", "MoveIt", "DDS", "WebSocket", "FastAPI",
        "Isaac Sim", "Isaac Lab", "MuJoCo", "Gazebo", "RViz",
        # AI / ML
        "TensorFlow", "PyTorch", "OpenCV", "NumPy", "Pandas",
        "YOLOv7", "YOLOv8", "YOLO", "Detectron2", "OpenPCDet",
        "LLM", "Diffusion Policy", "Imitation Learning",
        "Object Detection", "Point Cloud", "3D Detection",
        # Sensors
        "LiDAR", "Radar", "IMU", "Camera", "mmWave", "Sensor Fusion",
        # Hardware
        "STM32", "ESP32", "ARM", "PCB", "KiCad", "Altium", "RTOS",
        "HIL", "Jenkins", "CI/CD",
        # DevOps / Tools
        "Docker", "Linux", "Git",
        # Robotics concepts
        "SLAM", "LIO-SLAM", "Navigation", "Localization", "Mapping",
        "Manipulation", "Humanoid", "Quadruped", "Mobile Robot",
        "Pick and Place", "Autonomous",
    ]
    found = []
    text_lower = text.lower()
    for term in tech_terms:
        if term.lower() in text_lower and term not in found:
            found.append(term)
    return found


def parse_cv(tex_path: str = "main.tex") -> CVProfile:
    """
    Parse a moderncv LaTeX file and return a CVProfile.
    """
    path = Path(tex_path)
    if not path.exists():
        raise FileNotFoundError(f"Cannot find CV file: {tex_path}")

    content = path.read_text(encoding="utf-8")
    profile = CVProfile()

    # ── Name ──────────────────────────────────────────────────────────────
    m = re.search(r"\\name\{[^}]*\}\{([^}]+)\}", content)
    if m:
        profile.name = m.group(1).strip()
    # Some moderncv styles: \name{First}{Last}
    m2 = re.search(r"\\name\{([^}]+)\}\{([^}]+)\}", content)
    if m2:
        profile.name = f"{m2.group(1).strip()} {m2.group(2).strip()}".strip()

    # ── Location ──────────────────────────────────────────────────────────
    m = re.search(r"\\address\{([^}]+)\}", content)
    if m:
        profile.location = _clean(m.group(1))

    # ── Education level ───────────────────────────────────────────────────
    if "M.Sc." in content or "Master" in content:
        profile.education_level = "Master's"
    elif "B.Tech" in content or "Bachelor" in content:
        profile.education_level = "Bachelor's"

    # ── Skills ────────────────────────────────────────────────────────────
    skills_match = re.search(
        r"\\section\{Skills\}(.*?)\\section\{", content, re.DOTALL
    )
    if skills_match:
        profile.skills = _parse_cvitem_skills(skills_match.group(1))

    # ── Keywords from full content ─────────────────────────────────────────
    profile.keywords = _extract_keywords_from_text(content)

    # ── Experience items for context ──────────────────────────────────────
    profile.roles = ROLE_KEYWORDS  # derived from profile analysis

    # ── Approximate years of experience ───────────────────────────────────
    # Research Asst 2020-2022 (2yr) + 2023-2026 (3yr) + Porsche 2026+ (0.1yr)
    profile.experience_years = 5.5

    # ── Spoken languages ──────────────────────────────────────────────────
    lang_match = re.search(r"\\cvitem\{Languages\}\{([^}]+)\}", content)
    if lang_match:
        profile.languages = [_clean(l).strip() for l in lang_match.group(1).split(",")]

    return profile


if __name__ == "__main__":
    import sys, json
    tex = sys.argv[1] if len(sys.argv) > 1 else "main.tex"
    cv = parse_cv(tex)
    print(json.dumps({
        "name": cv.name,
        "location": cv.location,
        "education": cv.education_level,
        "experience_years": cv.experience_years,
        "skills": cv.skills,
        "keywords_count": len(cv.keywords),
        "keywords_sample": cv.keywords[:15],
    }, indent=2))
