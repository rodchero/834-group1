#!/usr/bin/env python3

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable

STEP_EXTRACT = ("scripts/firefoxExtract.py", ["commits_raw.jsonl"])
STEP_FILTER = ("scripts/filterCommits.py", ["commits_filtered.jsonl"])

STEP_BUGZILLA = ("scripts/getBugzillaList.py", ["bugzilla_matched.jsonl", "bugzilla_missing_ids.txt"])
STEP_FEATURES = ("scripts/extract_features.py", ["commits_features.csv"])

STEP_SZZ = ("scripts/run_szz.py", ["final_dataset.csv"])


def all_exist(files):
    return all((ROOT / f).exists() for f in files)


def run(script):
    path = ROOT / script
    print(f"\n=== Running {script} ===")

    result = subprocess.run(
        [PYTHON, str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True
    )

    print(f"--- {script} STDOUT ---")
    print(result.stdout if result.stdout.strip() else "(empty)")
    print(f"--- {script} STDERR ---")
    print(result.stderr if result.stderr.strip() else "(empty)")
    print(f"--- {script} Return code: {result.returncode} ---")

    if result.returncode != 0:
        raise SystemExit(result.returncode)


def spawn(script):
    path = ROOT / script
    print(f"\n=== Starting {script} in parallel ===")
    return subprocess.Popen(
        [PYTHON, str(path)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )


def wait_process(name, proc):
    stdout, stderr = proc.communicate()

    print(f"--- {name} STDOUT ---")
    print(stdout if stdout.strip() else "(empty)")
    print(f"--- {name} STDERR ---")
    print(stderr if stderr.strip() else "(empty)")
    print(f"--- {name} Return code: {proc.returncode} ---")

    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def main():
    # Step 1: extract all commits
    script, outputs = STEP_EXTRACT
    if all_exist(outputs):
        print(f"Skipping {script}, outputs exist")
    else:
        run(script)

    # Step 2: filter target dataset
    script, outputs = STEP_FILTER
    if all_exist(outputs):
        print(f"Skipping {script}, outputs exist")
    else:
        run(script)

    # Step 3 + 4 in parallel:
    # - Bugzilla fetch depends on filtered commits
    # - Feature extraction depends on raw + filtered commits
    bugzilla_script, bugzilla_outputs = STEP_BUGZILLA
    features_script, features_outputs = STEP_FEATURES

    bugzilla_done = all_exist(bugzilla_outputs)
    features_done = all_exist(features_outputs)

    procs = []

    if bugzilla_done:
        print(f"Skipping {bugzilla_script}, outputs exist")
    else:
        procs.append((bugzilla_script, spawn(bugzilla_script)))

    if features_done:
        print(f"Skipping {features_script}, outputs exist")
    else:
        procs.append((features_script, spawn(features_script)))

    for name, proc in procs:
        wait_process(name, proc)

    # Step 5: only run SZZ once both feature + bugzilla artifacts exist
    if not all_exist(bugzilla_outputs):
        raise RuntimeError("Bugzilla artifacts missing; cannot run SZZ")
    if not all_exist(features_outputs):
        raise RuntimeError("Feature artifacts missing; cannot run SZZ")

    script, outputs = STEP_SZZ
    if all_exist(outputs):
        print(f"Skipping {script}, outputs exist")
    else:
        run(script)

    print("\nPipeline complete.")


if __name__ == "__main__":
    main()