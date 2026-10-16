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
# Firefox snapshot the study uses (2026-10-08), so a newer clone gives the same
# commits, fix candidates and blame-ignore list. The numstat cache matches it.
REPO_REF = "098e537cc4338b343383540dd7e7907fece986b7"

# Pipeline artifacts, in the order they are produced
ARTIFACTS = ROOT / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)

COMMITS_RAW = ARTIFACTS / "commits_raw.jsonl"
NUMSTAT = ARTIFACTS / "commits_numstat.jsonl"
COMMITS_FILTERED = ARTIFACTS / "commits_filtered.jsonl"
FILTER_REPORT = ARTIFACTS / "filter_report.json"              # commits removed by each filter
# SZZ fix candidates: same quality filters, from the earliest window start
# onward with no end date, so fixes landing after a window are still traced
COMMITS_FIX_CANDIDATES = ARTIFACTS / "commits_fix_candidates.jsonl"
BUGS_MATCHED = ARTIFACTS / "bugzilla_matched.jsonl"
BUGS_MISSING_IDS = ARTIFACTS / "bugzilla_missing_ids.txt"
AI_CANDIDATES = ARTIFACTS / "ai_candidates.csv"
AI_LABELS = ARTIFACTS / "ai_labels.csv"                       # merged manual labels
LABELLING_TODO = ARTIFACTS / "labelling_todo.csv"             # rows still needing labels
LABEL_DISAGREEMENTS = ARTIFACTS / "label_disagreements.csv"   # for the third-person pass
AI_TIERS = ARTIFACTS / "ai_tiers.csv"                         # hash -> AI evidence tier
FEATURES = ARTIFACTS / "commits_features.csv"
FINAL_DATASET = ARTIFACTS / "final_dataset.csv"
SZZ_REPORT = ARTIFACTS / "szz_report.json"
BLAME_IGNORE_REVS = ARTIFACTS / "blame_ignore_revs.txt"       # Firefox's cosmetic commits, skipped by SZZ blame
DATASETS_SUMMARY = ARTIFACTS / "datasets_summary.csv"         # size and defect rate per dataset

# Replication package: the R scripts run from R_DIR and read ../input/<project>.csv,
# write ../output. Datasets in INPUT_DIR are kept in git (lfs); of output/, only
# the combined results and the R logs are.
R_DIR = ROOT / "ReplicationPackageScript"
INPUT_DIR = ROOT / "input"
OUTPUT_DIR = ROOT / "output"
R_LOG_DIR = OUTPUT_DIR / "logs"                               # one R log per dataset
MOZILLA_ORIGINAL = "mozilla_original"                         # the paper's data, input/mozilla_original.csv
# Combined R results, one row per dataset: RQ1 prediction, RQ2 effort-aware
# prediction, RQ3 logistic and effort-aware (EALR) coefficients
R_RESULTS = {kind: OUTPUT_DIR / f"results_{kind}.csv"
             for kind in ("pred", "pred_effort", "factor", "factor_effort")}
# Datasets with fewer defective commits are not modelled (too few to fit).
# Results near this size are unstable: the package's AUC counts a test fold
# without defective commits as 0, which pulls the average down.
MIN_DEFECTIVE = 10

# Study windows as [since, until). until=None means up to REPO_REF.
# Every filtered commit is tagged with the name of the window it falls in.
WINDOWS = {
    "human": (datetime(2024, 11, 1, tzinfo=timezone.utc),
              datetime(2025, 11, 1, tzinfo=timezone.utc)),
    "ai": (datetime(2025, 11, 1, tzinfo=timezone.utc), 
           datetime(2026, 10, 1, tzinfo=timezone.utc)),
}

# Manual AI-disclosure labelling (inputs, kept in git).
# Rater sheets are labelling_sheet_<rater>.csv or labelling_sheet_<rater>_<batch>.csv;
# the bare labelling_sheet.csv is the blank template and is ignored.
LABELLING_DIR = ROOT / "scripts" / "AIDetectionScripts"
LABELLING_KEY = LABELLING_DIR / "labelling_key.csv"       # row_id -> hash for old sheets
RESOLVED_LABELS = LABELLING_DIR / "resolved_labels.csv"   # third-person decisions (hash,label)

# AI evidence tiers: A = agent-authored, B = manually confirmed disclosure,
# C = exposed (any later commit by a developer with an A or B commit), - = none.
# Set True to also count AI_BORDERLINE labels as tier B seeds.
EXPOSURE_INCLUDE_BORDERLINE = True

# Replication datasets: name -> (window, tiers kept). Names become the R
# project names, so input/<name>.csv and input/<name>_<product>.csv.
# Human: commits with no AI evidence at any tier. AI: the exposed set (A+B+C).
DATASETS = {
    "ff_human": ("human", {"-"}),
    "ff_ai": ("ai", {"A", "B", "C"}),
}

# Per-product models: one for each of the N_PRODUCTS Bugzilla products with the
# most commits in each dataset, so the products can differ between datasets
N_PRODUCTS = 5

# Thread pool size for git subprocess work (numstat caching, SZZ blame)
MAX_WORKERS = min(16, os.cpu_count() or 4)

# Bugzilla REST API; requests are throttled on purpose
BUGZILLA_URL = "https://bugzilla.mozilla.org/rest/bug"
BUGZILLA_BATCH_SIZE = 200
BUGZILLA_SLEEP = 0.25

# Bugzilla bug references in commit text, e.g. "Bug 1234567"
BUG_RE = re.compile(r"\bbug\s*(\d+)\b", re.I)

# Vendored third-party code (e.g. third_party/rust/...). Commits touching only
# these paths are filtered out, and SZZ does not blame lines in them.
VENDORED_RE = re.compile(r"(^|/)(third_party|vendor)/")
