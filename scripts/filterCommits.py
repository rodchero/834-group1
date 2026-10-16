import json
import re
from datetime import datetime, timezone

from config import (
    COMMITS_RAW, NUMSTAT, COMMITS_FILTERED, COMMITS_FIX_CANDIDATES, FILTER_REPORT,
    WINDOWS, BUG_RE, VENDORED_RE,
)

# SZZ fix candidates have no upper date bound: a bug introduced inside a
# window may only be fixed after it, and that fix must still be traced back.
EARLIEST_START = min(since for since, _ in WINDOWS.values())

HASH_PREFIX = '{"hash": "'


def parse_iso8601(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def window_of(dt):
    for name, (since, until) in WINDOWS.items():
        if since <= dt and (until is None or dt < until):
            return name
    return None


def load_vendored_only(hashes):
    """Returns the subset of hashes whose changed files are all vendored code,
    read from the numstat cache (which cache_numstat.py fills before this stage)."""
    vendored = set()
    with open(NUMSTAT, encoding="utf-8") as f:
        for line in f:
            # Slice out the hash so only the needed lines are JSON-parsed
            if line.startswith(HASH_PREFIX):
                h = line[len(HASH_PREFIX):len(HASH_PREFIX) + 40]
            else:
                h = json.loads(line)["hash"] if line.strip() else ""
            if h not in hashes:
                continue
            files = json.loads(line)["files"]
            # Raw paths keep both sides of a rename ("dir/{old => new}"); a rename
            # counts as vendored when the path matches on either side
            if files and all(VENDORED_RE.search(item["path"]) for item in files):
                vendored.add(h)
    return vendored


def quality_filters(vendored_only):
    return [
        # Done by bots / imported automation
        ("wpt import", lambda c: "[wpt PR" in c["subject"]),

        # Undoing patches
        ("backout", lambda c: re.match(r"(backed out|back out|revert)", c["subject"], re.I)),

        # Third-party code, by commit message
        ("third-party", lambda c: re.search(r"vendor .* from|cherry-pick upstream", c["subject"], re.I)),

        # Third-party code, by path: every changed file is vendored (third_party/, vendor/)
        ("vendored only", lambda c: c["hash"] in vendored_only),

        # Require Bugzilla bug ID in subject
        ("no bug ID", lambda c: not BUG_RE.search(c["subject"])),
    ]


def run_funnel(commits, funnel):
    """Returns the surviving commits and {filter name: commits removed}."""
    kept = commits
    removed_by = {}
    for name, test in funnel:
        survivors = []
        removed = 0
        for commit in kept:
            if test(commit):
                removed += 1
            else:
                survivors.append(commit)
        kept = survivors
        removed_by[name] = removed
        print(f"  {name:<18} -{removed:<8} remaining={len(kept)}")
    return kept, removed_by


def write_commits(commits, path):
    with open(path, "w", encoding="utf-8") as f:
        for c in commits:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")


def main():
    for path in (COMMITS_RAW, NUMSTAT):
        if not path.exists():
            raise FileNotFoundError(f"Missing input: {path}")

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

    vendored_only = load_vendored_only({c["hash"] for c in since_start})
    print(f"{len(vendored_only)} of them change only vendored code")
    filters = quality_filters(vendored_only)

    report = {"raw_commits": n_raw, "windows": {}}
    kept_all = []
    for window, (since, until) in WINDOWS.items():
        in_window = [c for c in since_start if c.get("window") == window]
        until_s = until.date() if until else "REPO_REF"
        print(f"\n[{window}] {since.date()} .. {until_s}: {len(in_window)} commits in window")

        kept, removed_by = run_funnel(in_window, filters)
        if not kept:
            raise RuntimeError(f"Filtering produced no commits for window '{window}'")
        kept_all.extend(kept)
        report["windows"][window] = {
            "since": str(since.date()), "until": str(until_s),
            "in_window": len(in_window), "removed": removed_by, "kept": len(kept),
        }

    write_commits(kept_all, COMMITS_FILTERED)
    print(f"\nWrote {len(kept_all)} filtered commits to {COMMITS_FILTERED}")

    print(f"\nSZZ fix candidates ({EARLIEST_START.date()} onward, no end date): {len(since_start)} commits")
    candidates, removed_by = run_funnel(since_start, filters)
    write_commits(candidates, COMMITS_FIX_CANDIDATES)
    print(f"Wrote {len(candidates)} fix candidates to {COMMITS_FIX_CANDIDATES}")
    report["fix_candidates"] = {
        "since": str(EARLIEST_START.date()), "until": "REPO_REF",
        "in_range": len(since_start), "removed": removed_by, "kept": len(candidates),
    }

    with open(FILTER_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Wrote filter counts to {FILTER_REPORT}")


if __name__ == "__main__":
    main()
