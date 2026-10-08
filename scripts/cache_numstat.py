#!/usr/bin/env python3

import json
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT / "firefox"

COMMITS_IN = ROOT / "commits_raw.jsonl"
OUT = ROOT / "commits_numstat.jsonl"

MAX_WORKERS = 6


def run_git(args):
    result = subprocess.run(
        ["git", "-C", str(REPO)] + args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return result.stdout


def load_commits(path):
    commits = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                commits.append(json.loads(line))
    return commits


def parse_numstat(commit_hash):
    out = run_git(["show", "--numstat", "--format=", commit_hash])

    files = []
    seen_paths = set()

    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue

        a, d, path = parts

        if path in seen_paths:
            continue
        seen_paths.add(path)

        if a == "-" or d == "-":
            a = 0
            d = 0
        else:
            try:
                a = int(a)
            except ValueError:
                a = 0
            try:
                d = int(d)
            except ValueError:
                d = 0

        files.append({
            "path": path,
            "added": a,
            "deleted": d,
        })

    return files


def process_commit(commit):
    commit_hash = commit["hash"]
    try:
        files = parse_numstat(commit_hash)
        return {
            "hash": commit_hash,
            "files": files,
            "error": None,
        }
    except subprocess.CalledProcessError as e:
        return {
            "hash": commit_hash,
            "files": [],
            "error": str(e),
        }


def main():
    if not REPO.exists():
        raise FileNotFoundError(f"Firefox repo not found: {REPO}")
    if not COMMITS_IN.exists():
        raise FileNotFoundError(f"Missing input file: {COMMITS_IN}")

    commits = load_commits(COMMITS_IN)
    if not commits:
        raise RuntimeError("No commits found in commits_raw.jsonl")

    completed = 0

    with open(OUT, "w", encoding="utf-8") as out:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(process_commit, c): c["hash"] for c in commits}

            for future in as_completed(futures):
                record = future.result()

                if record["error"]:
                    print(f"[WARN] Skipping {record['hash']}: {record['error']}", flush=True)

                out.write(json.dumps({
                    "hash": record["hash"],
                    "files": record["files"],
                }, ensure_ascii=False) + "\n")

                completed += 1
                if completed % 500 == 0 or completed == len(commits):
                    print(f"Cached numstat for {completed}/{len(commits)} commits", flush=True)

    print(f"Wrote numstat cache to: {OUT}", flush=True)


if __name__ == "__main__":
    main()