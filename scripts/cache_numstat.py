#!/usr/bin/env python3

# Incremental: only commits in commits_raw.jsonl that are not yet in the cache
# are processed, and their records are appended. A complete cache is a no-op.

import json
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import REPO, MAX_WORKERS, COMMITS_RAW as COMMITS_IN, NUMSTAT as OUT


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
    # Explicit rename detection, so output does not depend on the user's diff.renames
    out = run_git(["show", "--numstat", "--find-renames", "--format=", commit_hash])

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


def load_cached_hashes(path):
    hashes = set()
    if not path.exists():
        return hashes
    prefix = '{"hash": "'
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            # Records start with the hash; avoid parsing ~800 MB of JSON
            if line.startswith(prefix):
                hashes.add(line[len(prefix):len(prefix) + 40])
            else:
                hashes.add(json.loads(line)["hash"])
    return hashes


def main():
    if not REPO.exists():
        raise FileNotFoundError(f"Firefox repo not found: {REPO}")
    if not COMMITS_IN.exists():
        raise FileNotFoundError(f"Missing input file: {COMMITS_IN}")

    commits = load_commits(COMMITS_IN)
    if not commits:
        raise RuntimeError("No commits found in commits_raw.jsonl")

    cached = load_cached_hashes(OUT)
    todo = [c for c in commits if c["hash"] not in cached]
    print(f"{len(cached)} commits already cached, {len(todo)} to add", flush=True)
    if not todo:
        return

    completed = 0
    failed = 0

    with open(OUT, "a", encoding="utf-8") as out:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(process_commit, c): c["hash"] for c in todo}

            for future in as_completed(futures):
                record = future.result()
                completed += 1

                if record["error"]:
                    # Not written, so the next run retries it
                    print(f"[WARN] Skipping {record['hash']}: {record['error']}", flush=True)
                    failed += 1
                else:
                    out.write(json.dumps({
                        "hash": record["hash"],
                        "files": record["files"],
                    }, ensure_ascii=False) + "\n")

                if completed % 500 == 0 or completed == len(todo):
                    print(f"Cached numstat for {completed}/{len(todo)} commits", flush=True)

    print(f"Appended {completed - failed} commits to numstat cache: {OUT}", flush=True)
    if failed:
        print(f"[WARN] {failed} commits failed and will be retried on the next run", flush=True)


if __name__ == "__main__":
    main()