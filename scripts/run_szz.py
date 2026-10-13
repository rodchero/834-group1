#!/usr/bin/env python3

import csv
import json
import re
import subprocess
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT / "firefox"

RAW_COMMITS_IN = ROOT / "commits_raw.jsonl"
COMMITS_IN = ROOT / "commits_filtered.jsonl"
BUGS_IN = ROOT / "bugzilla_matched.jsonl"
FEATURES_IN = ROOT / "commits_features.csv"
OUT = ROOT / "final_dataset.csv"

BUG_RE = re.compile(r"\bbug\s*(\d+)\b", re.I)

BLAME_WORKERS = 6

_blame_range_cache = {}


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


def parse_iso8601(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def load_commits(path):
    commits = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                c = json.loads(line)
                c["_dt"] = parse_iso8601(c["commit_date"])
                commits.append(c)
    return commits


def load_bugs(path):
    bugs = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                b = json.loads(line)
                bugs[int(b["id"])] = b
    return bugs


def load_features(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def extract_bug_ids(commit):
    text = " ".join([
        commit.get("subject", "") or "",
        commit.get("message", "") or "",
    ])
    return [int(m.group(1)) for m in BUG_RE.finditer(text)]


def is_actual_bug(bug):
    bug_type = (bug.get("type") or "").lower()
    summary = (bug.get("summary") or "").lower()

    if bug_type and bug_type not in {"defect", "bug"}:
        return False

    if "meta" in summary or "[meta]" in summary:
        return False

    return True


def get_parent_from_commit(commit):
    parents = (commit.get("parents") or "").strip().split()
    if parents:
        return parents[0]
    return None


def build_commit_date_map_from_raw(path):
    m = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                c = json.loads(line)
                m[c["hash"]] = parse_iso8601(c["commit_date"])
    return m


def get_fix_commits(commits, bugs_by_id):
    fix_commits = []

    for c in commits:
        bug_ids = extract_bug_ids(c)
        linked_bugs = []

        for bug_id in bug_ids:
            bug = bugs_by_id.get(bug_id)
            if not bug:
                continue
            if not is_actual_bug(bug):
                continue
            linked_bugs.append((bug_id, bug))

        if not linked_bugs:
            continue

        creation_times = []
        for _, bug in linked_bugs:
            creation = bug.get("creation_time")
            if creation:
                creation_times.append(parse_iso8601(creation))

        if not creation_times:
            continue

        report_date = min(creation_times)

        fix_commits.append({
            "commit": c,
            "bug_ids": [bug_id for bug_id, _ in linked_bugs],
            "bugs": [bug for _, bug in linked_bugs],
            "report_date": report_date,
        })

    return fix_commits


def parse_deleted_lines_from_patch(commit_hash):
    """
    Returns list of tuples:
      (old_path, old_line_number, deleted_line_text)
    """
    out = run_git(["show", "--format=", "--unified=0", commit_hash])

    deleted = []
    current_old_path = None
    old_line = None

    for line in out.splitlines():
        if line.startswith("--- "):
            path = line[4:].strip()
            if path.startswith("a/"):
                path = path[2:]
            current_old_path = None if path == "/dev/null" else path

        elif line.startswith("@@ "):
            m = re.search(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
            if not m:
                old_line = None
                continue
            old_start = int(m.group(1))
            old_line = old_start

        elif line.startswith("-") and not line.startswith("---"):
            if current_old_path is not None and old_line is not None:
                deleted.append((current_old_path, old_line, line[1:]))
            if old_line is not None:
                old_line += 1

        elif line.startswith("+") and not line.startswith("+++"):
            pass

        else:
            if old_line is not None and not line.startswith("\\"):
                old_line += 1

    return deleted


def group_contiguous_lines(deleted_lines):
    """
    Input: iterable of (path, line_number)
    Output: dict[path] = [(start, end), ...]
    """
    by_path = defaultdict(list)
    for path, line_number in deleted_lines:
        by_path[path].append(line_number)

    ranges = {}
    for path, nums in by_path.items():
        nums = sorted(set(nums))
        if not nums:
            ranges[path] = []
            continue

        grouped = []
        start = prev = nums[0]
        for n in nums[1:]:
            if n == prev + 1:
                prev = n
            else:
                grouped.append((start, prev))
                start = prev = n
        grouped.append((start, prev))
        ranges[path] = grouped

    return ranges


def blame_range(parent_hash, path, start, end):
    key = (parent_hash, path, start, end)
    if key in _blame_range_cache:
        return _blame_range_cache[key]

    try:
        out = run_git([
            "blame",
            parent_hash,
            "-L", f"{start},{end}",
            "--porcelain",
            "--",
            path
        ])
    except subprocess.CalledProcessError:
        _blame_range_cache[key] = set()
        return set()

    commits = set()
    for line in out.splitlines():
        m = re.match(r"^([0-9a-f]{7,40})\s", line)
        if m:
            commits.add(m.group(1))

    _blame_range_cache[key] = commits
    return commits


def run_szz(fix_commits, commit_dates):
    inducing_commits = set()

    for idx, item in enumerate(fix_commits, start=1):
        fix_commit = item["commit"]
        fix_hash = fix_commit["hash"]
        parent = get_parent_from_commit(fix_commit)
        report_date = item["report_date"]

        if not parent:
            continue

        try:
            deleted_lines = parse_deleted_lines_from_patch(fix_hash)
        except subprocess.CalledProcessError as e:
            print(f"[WARN] Could not parse patch for fix commit {fix_hash}: {e}", flush=True)
            continue

        deleted_pairs = [(path, line_number) for path, line_number, _ in deleted_lines]
        if not deleted_pairs:
            if idx % 100 == 0 or idx == len(fix_commits):
                print(
                    f"SZZ processed {idx}/{len(fix_commits)} fix commits; inducing so far={len(inducing_commits)}",
                    flush=True
                )
            continue

        ranges_by_path = group_contiguous_lines(deleted_pairs)

        tasks = []
        for path, ranges in ranges_by_path.items():
            for start, end in ranges:
                tasks.append((path, start, end))

        blamed = set()

        with ThreadPoolExecutor(max_workers=BLAME_WORKERS) as ex:
            future_map = {
                ex.submit(blame_range, parent, path, start, end): (path, start, end)
                for path, start, end in tasks
            }

            for fut in as_completed(future_map):
                try:
                    blamed_hashes = fut.result()
                except Exception:
                    continue

                for blamed_hash in blamed_hashes:
                    if blamed_hash == fix_hash:
                        continue

                    cand_date = commit_dates.get(blamed_hash)
                    if cand_date is None:
                        continue

                    if cand_date <= report_date:
                        blamed.add(blamed_hash)

        inducing_commits.update(blamed)

        if idx % 100 == 0 or idx == len(fix_commits):
            print(
                f"SZZ processed {idx}/{len(fix_commits)} fix commits; inducing so far={len(inducing_commits)}",
                flush=True
            )

    return inducing_commits


def write_final_dataset(feature_rows, inducing_commits, out_path):
    fieldnames = [
        "transactionid",
        "commitdate",
        "ns",
        "nm",
        "nf",
        "entropy",
        "la",
        "ld",
        "lt",
        "fix",
        "ndev",
        "pd",
        "npt",
        "exp",
        "rexp",
        "sexp",
        "bug",
    ]

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in feature_rows:
            txid = row["transactionid"]
            row["bug"] = 1 if txid in inducing_commits else 0
            writer.writerow(row)


def main():
    if not REPO.exists():
        raise FileNotFoundError(f"Firefox repo not found: {REPO}")
    if not RAW_COMMITS_IN.exists():
        raise FileNotFoundError(f"Missing input file: {RAW_COMMITS_IN}")
    if not COMMITS_IN.exists():
        raise FileNotFoundError(f"Missing input file: {COMMITS_IN}")
    if not BUGS_IN.exists():
        raise FileNotFoundError(f"Missing input file: {BUGS_IN}")
    if not FEATURES_IN.exists():
        raise FileNotFoundError(f"Missing input file: {FEATURES_IN}")

    commits = load_commits(COMMITS_IN)
    bugs_by_id = load_bugs(BUGS_IN)
    feature_rows = load_features(FEATURES_IN)
    commit_dates = build_commit_date_map_from_raw(RAW_COMMITS_IN)

    if not commits:
        raise RuntimeError("No commits found in commits_filtered.jsonl")
    if not feature_rows:
        raise RuntimeError("No rows found in commits_features.csv")

    print("Identifying validated bug-fixing commits...", flush=True)
    fix_commits = get_fix_commits(commits, bugs_by_id)
    print(f"Found {len(fix_commits)} validated bug-fixing commits", flush=True)

    print("Running SZZ...", flush=True)
    inducing_commits = run_szz(fix_commits, commit_dates)
    print(f"Identified {len(inducing_commits)} inducing commits", flush=True)

    write_final_dataset(feature_rows, inducing_commits, OUT)
    print(f"Wrote labeled dataset to: {OUT}", flush=True)


if __name__ == "__main__":
    main()