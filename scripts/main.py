import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PYTHON = sys.executable

STEPS = [
    {
        "name": "extract commits from firefox",
        "script": "firefoxExtract.py",
        "outputs": ["commits_raw.jsonl"],
    },
    {
        "name": "filter commits from firefox",
        "script": "filterCommits.py",
        "outputs": ["commits_filtered.jsonl"],
    },
    {
        "name": "match commits from bugzilla",
        "script": "getBugzillaList.py",
        "outputs": ["bugzilla_matched.jsonl", "bugzilla_missing_ids.txt"],
    },
    {
        "name": "extract features from commits",
        "script": "extract_features.py",
        "outputs": ["commits_features.csv"],
    },
    {
        "name": "run szz to label dataset",
        "script": "run_szz.py",
        "outputs": ["final_dataset.csv"],
    },
]


def outputs_exist(outputs):
    return all((ROOT / out).exists() for out in outputs)


def run_step(step):
    script_path = ROOT / step["script"]
    if not script_path.exists():
        raise FileNotFoundError(f"Missing script: {script_path}")

    print(f"\n=== Running: {step['name']} ===")
    result = subprocess.run([PYTHON, str(script_path)], cwd=ROOT)
    if result.returncode != 0:
        raise RuntimeError(f"Step failed: {step['name']}")


def main():
    print("Data pipeline.\n")
    for step in STEPS:
        if outputs_exist(step["outputs"]):
            print(f"[SKIP] {step['name']} -> outputs already exist")
        else:
            run_step(step)

    print("\nPipeline complete.")


if __name__ == "__main__":
    main()