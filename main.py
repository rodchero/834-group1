import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable

STEPS = [
    ("scripts/firefoxExtract.py", ["commits_raw.jsonl"]),
    ("scripts/filterCommits.py", ["commits_filtered.jsonl"]),
    ("scripts/getBugzillaList.py", ["bugzilla_matched.jsonl", "bugzilla_missing_ids.txt"]),
    ("scripts/extract_features.py", ["commits_features.csv"]),
    ("scripts/run_szz.py", ["final_dataset.csv"]),
]


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

    print("--- STDOUT ---")
    print(result.stdout if result.stdout.strip() else "(empty)")
    print("--- STDERR ---")
    print(result.stderr if result.stderr.strip() else "(empty)")
    print(f"--- Return code: {result.returncode} ---")

    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main():
    for script, outputs in STEPS:
        if all_exist(outputs):
            print(f"Skipping {script}, outputs exist")
        else:
            run(script)


if __name__ == "__main__":
    main()