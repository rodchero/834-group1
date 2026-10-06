import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

IN = ROOT / "commits_raw.jsonl"
OUT = ROOT / "commits_filtered.jsonl"

# Target study window
SINCE = datetime(2024, 11, 1, tzinfo=timezone.utc)
UNTIL = datetime(2025, 11, 1, tzinfo=timezone.utc)  # exclusive


def parse_iso8601(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


FUNNEL = [
    ("outside date range", lambda c: not (SINCE <= parse_iso8601(c["commit_date"]) < UNTIL)),

    # Done by bots / imported automation
    ("wpt import", lambda c: "[wpt PR" in c["subject"]),

    # Undoing patches
    ("backout", lambda c: re.match(r"(backed out|back out|revert)", c["subject"], re.I)),

    # Third-party code
    ("third-party", lambda c: re.search(r"vendor .* from|cherry-pick upstream", c["subject"], re.I)),

    # Require Bugzilla bug ID in subject
    ("no bug ID", lambda c: not re.search(r"\bbug ?\d+\b", c["subject"], re.I)),
]


def main():
    if not IN.exists():
        raise FileNotFoundError(f"Missing input: {IN}")

    commits = [json.loads(l) for l in open(IN, encoding="utf-8") if l.strip()]
    print(f"Loaded {len(commits)} raw commits")

    kept = commits
    for name, test in FUNNEL:
        survivors = []
        removed = 0
        for commit in kept:
            if test(commit):
                removed += 1
            else:
                survivors.append(commit)
        kept = survivors
        print(f"{name:<20} -{removed:<8} remaining={len(kept)}")

    with open(OUT, "w", encoding="utf-8") as f:
        for c in kept:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"Wrote {len(kept)} filtered commits to {OUT}")

    if len(kept) == 0:
        raise RuntimeError("Filtering produced no commits")


if __name__ == "__main__":
    main()