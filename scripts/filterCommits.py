import json
import re
from datetime import datetime, timezone

from config import COMMITS_RAW, COMMITS_FILTERED, WINDOWS, BUG_RE


def parse_iso8601(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def window_of(dt):
    for name, (since, until) in WINDOWS.items():
        if since <= dt and (until is None or dt < until):
            return name
    return None


FUNNEL = [
    # Done by bots / imported automation
    ("wpt import", lambda c: "[wpt PR" in c["subject"]),

    # Undoing patches
    ("backout", lambda c: re.match(r"(backed out|back out|revert)", c["subject"], re.I)),

    # Third-party code
    ("third-party", lambda c: re.search(r"vendor .* from|cherry-pick upstream", c["subject"], re.I)),

    # Require Bugzilla bug ID in subject
    ("no bug ID", lambda c: not BUG_RE.search(c["subject"])),
]


def main():
    if not COMMITS_RAW.exists():
        raise FileNotFoundError(f"Missing input: {COMMITS_RAW}")

    by_window = {name: [] for name in WINDOWS}
    n_raw = 0
    with open(COMMITS_RAW, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            n_raw += 1
            c = json.loads(line)
            window = window_of(parse_iso8601(c["commit_date"]))
            if window:
                c["window"] = window
                by_window[window].append(c)

    print(f"Loaded {n_raw} raw commits")
    print(f"{'outside all windows':<20} -{n_raw - sum(map(len, by_window.values()))}")

    kept_all = []
    for window, kept in by_window.items():
        since, until = WINDOWS[window]
        until_s = until.date() if until else "HEAD"
        print(f"\n[{window}] {since.date()} .. {until_s}: {len(kept)} commits in window")

        for name, test in FUNNEL:
            survivors = []
            removed = 0
            for commit in kept:
                if test(commit):
                    removed += 1
                else:
                    survivors.append(commit)
            kept = survivors
            print(f"  {name:<18} -{removed:<8} remaining={len(kept)}")

        if not kept:
            raise RuntimeError(f"Filtering produced no commits for window '{window}'")
        kept_all.extend(kept)

    with open(COMMITS_FILTERED, "w", encoding="utf-8") as f:
        for c in kept_all:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"\nWrote {len(kept_all)} filtered commits to {COMMITS_FILTERED}")


if __name__ == "__main__":
    main()
