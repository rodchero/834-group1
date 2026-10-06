#!/usr/bin/env python3

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT / "firefox"
OUT = ROOT / "commits_raw.jsonl"

FIELDS = ["%H", "%P", "%cI", "%ae", "%ce", "%s", "%B"]
NAMES = ["hash", "parents", "commit_date", "author_email", "committer_email", "subject", "message"]


def main():
    if not REPO.exists():
        raise FileNotFoundError(f"Firefox repo not found: {REPO}")

    log = subprocess.run(
        [
            "git", "-C", str(REPO), "log",
            "--no-merges",
            "--pretty=format:\x1e" + "\x1f".join(FIELDS),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )

    n = 0
    with open(OUT, "w", encoding="utf-8") as out:
        for chunk in log.stdout.split("\x1e"):
            if not chunk.strip():
                continue

            parts = chunk.split("\x1f")
            if len(parts) != len(NAMES):
                continue

            commit = dict(zip(NAMES, parts))
            commit["message"] = commit["message"].strip()

            out.write(json.dumps(commit, ensure_ascii=False) + "\n")
            n += 1

    print(f"{n} commits", flush=True)
    print(f"Path: {OUT}", flush=True)

    if n == 0:
        raise RuntimeError("No commits extracted from Firefox repository")


if __name__ == "__main__":
    main()