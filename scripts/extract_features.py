#!/usr/bin/env python3

import csv
import json
import math
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT / "firefox"

RAW_COMMITS_IN = ROOT / "commits_raw.jsonl"
TARGET_COMMITS_IN = ROOT / "commits_filtered.jsonl"
OUT = ROOT / "commits_features.csv"

FIELDNAMES = [
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
]


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


def format_commitdate(dt):
    return f"{dt.year}/{dt.month}/{dt.day} {dt.hour}:{dt.minute:02d}"


def years_old(prior_dt, current_dt):
    days = (current_dt - prior_dt).total_seconds() / 86400.0
    if days < 0:
        return 0
    return int(days // 365.0)


def subsystem_of(path):
    parts = path.split("/")
    return parts[0] if parts else ""


def directory_of(path):
    parts = path.split("/")
    if len(parts) <= 1:
        return ""
    return "/".join(parts[:-1])


def normalized_entropy(churns):
    churns = [c for c in churns if c > 0]
    n = len(churns)
    total = sum(churns)

    if total == 0 or n <= 1:
        return 0.0

    ent = 0.0
    for c in churns:
        p = c / total
        ent -= p * math.log2(p)

    return ent / math.log2(n)


def fix_heuristic(subject, message):
    text = f"{subject}\n{message}".lower()
    keywords = ["bug", "fix", "fixed", "defect", "patch"]
    return 1 if any(k in text for k in keywords) else 0


def load_commits(path):
    commits = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            c = json.loads(line)
            c["_dt"] = parse_iso8601(c["commit_date"])
            commits.append(c)

    commits.sort(key=lambda c: c["_dt"])
    return commits


def get_parent_from_commit(commit):
    parents = (commit.get("parents") or "").strip().split()
    if parents:
        return parents[0]
    return None


def parse_numstat(commit_hash):
    out = run_git(["show", "--numstat", "--format=", commit_hash])
    rows = []

    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue

        a, d, path = parts

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

        rows.append((a, d, path))

    return rows


_line_count_cache = {}


def count_lines_in_parent(parent_hash, path):
    if not parent_hash:
        return 0

    key = (parent_hash, path)
    if key in _line_count_cache:
        return _line_count_cache[key]

    try:
        content = run_git(["show", f"{parent_hash}:{path}"])
        n = len(content.splitlines())
    except Exception:
        n = 0

    _line_count_cache[key] = n
    return n


def normalize_features(la_raw, ld_raw, lt_raw, nf, npt_raw, entropy):
    if lt_raw >= 1:
        la = la_raw / lt_raw
        ld = ld_raw / lt_raw
    else:
        la = la_raw
        ld = ld_raw

    if nf >= 1:
        lt = lt_raw / nf
        npt = npt_raw / nf
    else:
        lt = lt_raw
        npt = npt_raw

    return la, ld, lt, npt, entropy


def main():
    if not REPO.exists():
        raise FileNotFoundError(f"Firefox repo not found: {REPO}")
    if not RAW_COMMITS_IN.exists():
        raise FileNotFoundError(f"Missing input file: {RAW_COMMITS_IN}")
    if not TARGET_COMMITS_IN.exists():
        raise FileNotFoundError(f"Missing input file: {TARGET_COMMITS_IN}")

    all_commits = load_commits(RAW_COMMITS_IN)
    target_commits = load_commits(TARGET_COMMITS_IN)

    if not all_commits:
        raise RuntimeError("No commits found in commits_raw.jsonl")
    if not target_commits:
        raise RuntimeError("No commits found in commits_filtered.jsonl")

    target_hashes = {c["hash"] for c in target_commits}

    # Historical state built from ALL commits
    file_developers = defaultdict(set)
    file_change_count = defaultdict(int)
    file_dev_change_count = defaultdict(int)
    dev_prior_commit_dates = defaultdict(list)
    subsystem_dev_count = defaultdict(int)

    emitted = 0

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()

        for i, commit in enumerate(all_commits, start=1):
            commit_hash = commit["hash"]
            commit_date = commit["_dt"]
            author = (commit.get("author_email") or "").strip().lower()
            subject = commit.get("subject", "") or ""
            message = commit.get("message", "") or ""

            try:
                parent = get_parent_from_commit(commit)
                numstat = parse_numstat(commit_hash)
            except subprocess.CalledProcessError as e:
                print(f"[WARN] Skipping {commit_hash}: {e}")
                continue

            seen_paths = set()
            deduped = []
            for a, d, path in numstat:
                if path in seen_paths:
                    continue
                seen_paths.add(path)
                deduped.append((a, d, path))
            numstat = deduped

            files = [path for _, _, path in numstat]
            subsystems = {subsystem_of(path) for path in files if path}
            directories = {directory_of(path) for path in files if path}

            # Emit feature row only for target commits,
            # but compute using history from ALL previous commits.
            if commit_hash in target_hashes:
                ns = len(subsystems)
                nm = len(directories)
                nf = len(files)

                la_raw = sum(a for a, _, _ in numstat)
                ld_raw = sum(d for _, d, _ in numstat)
                lt_raw = sum(count_lines_in_parent(parent, path) for _, _, path in numstat)

                churns = [a + d for a, d, _ in numstat]
                entropy = normalized_entropy(churns)

                fix = fix_heuristic(subject, message)

                prior_devs = set()
                prior_changes_per_file = []
                prior_author_changes_per_file = []

                for _, _, path in numstat:
                    prior_devs.update(file_developers[path])
                    prior_changes_per_file.append(file_change_count[path])
                    prior_author_changes_per_file.append(file_dev_change_count[(path, author)])

                ndev = len(prior_devs)
                pd = sum(prior_changes_per_file) if prior_changes_per_file else 0
                npt_raw = sum(prior_author_changes_per_file)

                exp = len(dev_prior_commit_dates[author])

                rexp = 0.0
                for prior_dt in dev_prior_commit_dates[author]:
                    n = years_old(prior_dt, commit_date)
                    rexp += 1.0 / (n + 1)

                sexp = sum(subsystem_dev_count[(author, s)] for s in subsystems)

                la, ld, lt, npt, entropy = normalize_features(
                    la_raw, ld_raw, lt_raw, nf, npt_raw, entropy
                )

                row = {
                    "transactionid": commit_hash,
                    "commitdate": format_commitdate(commit_date),
                    "ns": ns,
                    "nm": nm,
                    "nf": nf,
                    "entropy": entropy,
                    "la": la,
                    "ld": ld,
                    "lt": lt,
                    "fix": fix,
                    "ndev": ndev,
                    "pd": pd,
                    "npt": npt,
                    "exp": exp,
                    "rexp": rexp,
                    "sexp": sexp,
                }

                writer.writerow(row)
                emitted += 1

            # Update history state for ALL commits after computing current row
            for _, _, path in numstat:
                file_developers[path].add(author)
                file_change_count[path] += 1
                file_dev_change_count[(path, author)] += 1

            dev_prior_commit_dates[author].append(commit_date)

            for s in subsystems:
                subsystem_dev_count[(author, s)] += 1

            if i % 1000 == 0 or i == len(all_commits):
                print(f"Scanned {i}/{len(all_commits)} commits, emitted {emitted} target rows", flush=True)

    if OUT.stat().st_size == 0:
        raise RuntimeError("Feature extraction produced an empty file")

    print(f"Wrote feature dataset to: {OUT}")
    print(f"Emitted {emitted} target commits")


if __name__ == "__main__":
    main()