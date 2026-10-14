#!/usr/bin/env python3

import subprocess
import sys
import time

from config import (
    ROOT, COMMITS_RAW, NUMSTAT, COMMITS_FILTERED, BUGS_MATCHED, BUGS_MISSING_IDS,
    AI_CANDIDATES, FEATURES, FINAL_DATASET, SZZ_REPORT,
)

PYTHON = sys.executable

# (module, outputs). Stages run in order; each depends on the ones before it.
# A stage is skipped when all of its outputs already exist.
STAGES = [
    ("scripts.firefoxExtract", [COMMITS_RAW]),
    ("scripts.cache_numstat", [NUMSTAT]),
    ("scripts.filterCommits", [COMMITS_FILTERED]),
    ("scripts.getBugzillaList", [BUGS_MATCHED, BUGS_MISSING_IDS]),
    ("scripts.AIDetectionScripts.CommitsAIDetect", [AI_CANDIDATES]),
    ("scripts.extract_features", [FEATURES]),
    ("scripts.run_szz", [FINAL_DATASET, SZZ_REPORT]),
]


def fmt_duration(seconds):
    m, s = divmod(int(round(seconds)), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}"


def run(module):
    print(f"\n=== Running {module} ===", flush=True)
    start = time.perf_counter()

    result = subprocess.run(
        [PYTHON, "-u", "-m", module],   # -u = unbuffered python output
        cwd=ROOT
    )

    elapsed = time.perf_counter() - start
    print(f"--- {module} return code: {result.returncode}, took {fmt_duration(elapsed)} ---", flush=True)

    if result.returncode != 0:
        raise SystemExit(result.returncode)

    return elapsed


def main():
    timings = []
    pipeline_start = time.perf_counter()

    for module, outputs in STAGES:
        if all(p.exists() for p in outputs):
            print(f"Skipping {module}, outputs exist", flush=True)
            timings.append((module, None))
        else:
            timings.append((module, run(module)))

    total = time.perf_counter() - pipeline_start

    print("\nStage timings:", flush=True)
    for module, elapsed in timings:
        shown = "skipped" if elapsed is None else fmt_duration(elapsed)
        print(f"  {module:<46} {shown}", flush=True)
    print(f"  {'total':<46} {fmt_duration(total)}", flush=True)

    print("\nPipeline complete.", flush=True)


if __name__ == "__main__":
    main()
