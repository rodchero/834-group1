import json
import re
from datetime import datetime, timezone

from config import COMMITS_RAW, COMMITS_FILTERED, COMMITS_FIX_CANDIDATES, WINDOWS, BUG_RE

# SZZ fix candidates have no upper date bound: a bug introduced inside a
# window may only be fixed after it, and that fix must still be traced back.
EARLIEST_START = min(since for since, _ in WINDOWS.values())


def parse_iso8601(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def window_of(dt):
    for name, (since, until) in WINDOWS.items():
        if since <= dt and (until is None or dt < until):
            return name
    return None


QUALITY_FILTERS = [
    # Done by bots / imported automation
    ("wpt import", lambda c: "[wpt PR" in c["subject"]),

    # Undoing patches
    ("backout", lambda c: re.match(r"(backed out|back out|revert)", c["subject"], re.I)),

    # Third-party code
    ("third-party", lambda c: re.search(r"vendor .* from|cherry-pick upstream", c["subject"], re.I)),

    # Require Bugzilla bug ID in subject
    ("no bug ID", lambda c: not BUG_RE.search(c["subject"])),
]


def run_funnel(commits, funnel):
    kept = commits
    for name, test in funnel:
        survivors = []
        removed = 0
        for commit in kept:
            if test(commit):
                removed += 1
            else:
                survivors.append(commit)
        kept = survivors
        print(f"  {name:<18} -{removed:<8} remaining={len(kept)}")
    return kept


def write_commits(commits, path):
    with open(path, "w", encoding="utf-8") as f:
        for c in commits:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")


def main():
    if not COMMITS_RAW.exists():
        raise FileNotFoundError(f"Missing input: {COMMITS_RAW}")

    # Only commits from the earliest window start onward are needed, by either output
    since_start = []
    n_raw = 0
    with open(COMMITS_RAW, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            n_raw += 1
            c = json.loads(line)
            dt = parse_iso8601(c["commit_date"])
            if dt >= EARLIEST_START:
                window = window_of(dt)
                if window:
                    c["window"] = window
                since_start.append(c)

    print(f"Loaded {n_raw} raw commits, {len(since_start)} since {EARLIEST_START.date()}")

    kept_all = []
    for window, (since, until) in WINDOWS.items():
        in_window = [c for c in since_start if c.get("window") == window]
        until_s = until.date() if until else "HEAD"
        print(f"\n[{window}] {since.date()} .. {until_s}: {len(in_window)} commits in window")

        kept = run_funnel(in_window, QUALITY_FILTERS)
        if not kept:
            raise RuntimeError(f"Filtering produced no commits for window '{window}'")
        kept_all.extend(kept)

    write_commits(kept_all, COMMITS_FILTERED)
    print(f"\nWrote {len(kept_all)} filtered commits to {COMMITS_FILTERED}")

    print(f"\nSZZ fix candidates ({EARLIEST_START.date()} onward, no end date): {len(since_start)} commits")
    candidates = run_funnel(since_start, QUALITY_FILTERS)
    write_commits(candidates, COMMITS_FIX_CANDIDATES)
    print(f"Wrote {len(candidates)} fix candidates to {COMMITS_FIX_CANDIDATES}")


if __name__ == "__main__":
    main()
