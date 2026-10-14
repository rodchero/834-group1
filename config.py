"""Shared paths and parameters for the dataset pipeline.

Stage scripts import this as a top-level module, so run them from the project
root as modules, e.g. `python3 -m scripts.filterCommits` (main.py does this).
"""

import os
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT / "firefox"

# Pipeline artifacts, in the order they are produced
ARTIFACTS = ROOT / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)

COMMITS_RAW = ARTIFACTS / "commits_raw.jsonl"
NUMSTAT = ARTIFACTS / "commits_numstat.jsonl"
COMMITS_FILTERED = ARTIFACTS / "commits_filtered.jsonl"
BUGS_MATCHED = ARTIFACTS / "bugzilla_matched.jsonl"
BUGS_MISSING_IDS = ARTIFACTS / "bugzilla_missing_ids.txt"
AI_CANDIDATES = ARTIFACTS / "ai_candidates.csv"
FEATURES = ARTIFACTS / "commits_features.csv"
FINAL_DATASET = ARTIFACTS / "final_dataset.csv"
SZZ_REPORT = ARTIFACTS / "szz_report.json"

# Study windows as [since, until). until=None means up to the clone's HEAD.
# Every filtered commit is tagged with the name of the window it falls in.
WINDOWS = {
    "human": (datetime(2024, 11, 1, tzinfo=timezone.utc),
              datetime(2025, 11, 1, tzinfo=timezone.utc)),
    "ai": (datetime(2025, 11, 1, tzinfo=timezone.utc), 
           datetime(2026, 10, 10, tzinfo=timezone.utc)),
}

# Thread pool size for git subprocess work (numstat caching, SZZ blame)
MAX_WORKERS = min(16, os.cpu_count() or 4)

# Bugzilla REST API; requests are throttled on purpose
BUGZILLA_URL = "https://bugzilla.mozilla.org/rest/bug"
BUGZILLA_BATCH_SIZE = 200
BUGZILLA_SLEEP = 0.25

# Bugzilla bug references in commit text, e.g. "Bug 1234567"
BUG_RE = re.compile(r"\bbug\s*(\d+)\b", re.I)
