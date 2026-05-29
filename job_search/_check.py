#!/usr/bin/env python3
import sys
sys.path.insert(0, "/mnt/d/Documents-CV/job_search")
from cv_parser import parse_cv
from searcher import REGIONS, search_jobs
from scorer import rank_listings, score_label, score_color

cv = parse_cv("/mnt/d/Documents-CV/main.tex")
print("All imports OK")
print("Name:", cv.name)
print("Keywords:", len(cv.all_keywords()))
print("Regions:", list(REGIONS.keys()))
