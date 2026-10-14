#!/usr/bin/env python3
# Dump the full commit message for one or more labelling row_ids (old sheets)
# or commit hashes (labelling_todo.csv and newer sheets).
#
# The sheet's `context` column truncates each matching line to 120 characters
# and shows at most 2 matching lines, so a tool mention further into a long
# line or further down the message can be cut off. This prints the whole thing.
#
# Usage, from the project root:
#   python3 ./scripts/AIDetectionScripts/show_commit.py R0084 R0562
#   python3 ./scripts/AIDetectionScripts/show_commit.py fa9c5cdb882a
#   python3 ./scripts/AIDetectionScripts/show_commit.py R0084 --repo firefox



# This script is written by claude

import argparse, csv, json, re, subprocess, sys
from pathlib import Path

KEY = "scripts/AIDetectionScripts/labelling_key.csv"
JSONL = ["artifacts/commits_filtered.jsonl", "artifacts/commits_raw.jsonl"]

ap = argparse.ArgumentParser()
ap.add_argument("row_ids", nargs="+", help="row ids or commit hashes, e.g. R0084 fa9c5cdb882a")
ap.add_argument("--repo", default="firefox", help="path to the clone")
args = ap.parse_args()

if not Path(KEY).exists():
    sys.exit(f"{KEY} not found -- run this from the project root")

key = {r["row_id"]: r for r in csv.DictReader(open(KEY, encoding="utf-8"))}

# Prefer the local JSONL (already extracted, no git needed); fall back to git.
cache = {}
for path in JSONL:
    if not Path(path).exists():
        continue
    for line in open(path, encoding="utf-8"):
        c = json.loads(line)
        cache.setdefault(c["hash"][:12], c)

for rid in args.row_ids:
    row = key.get(rid)
    if not row and re.fullmatch(r"[0-9a-fA-F]{7,40}", rid):
        row = {"hash": rid[:12].lower(), "window": "", "kind": "", "agent": "", "pretag": ""}
    if not row:
        print(f"\n{rid}: not in {KEY} and not a commit hash")
        continue

    short = row["hash"]
    print("\n" + "=" * 72)
    print(f"{rid}   {short}   {row['window']}")
    print(f"kind={row['kind']}  agent={row['agent'] or '-'}  "
          f"pretag={row['pretag'] or '-'}")
    print(f"https://github.com/mozilla-firefox/firefox/commit/{short}")
    print("=" * 72)

    c = cache.get(short)
    if c:
        print(f"author:    {c['author_email']}")
        print(f"committer: {c['committer_email']}")
        print(f"date:      {c['commit_date']}")
        print("-" * 72)
        print(c["message"])
    else:
        out = subprocess.run(
            ["git", "-C", args.repo, "show", "-s",
             "--format=author:    %ae%ncommitter: %ce%ndate:      %cI%n"
             + "-" * 72 + "%n%B", short],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(out.stdout if out.returncode == 0 else out.stderr)