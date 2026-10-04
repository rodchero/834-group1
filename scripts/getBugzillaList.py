# Fetch Bugzilla bugs by the exact bug IDs referenced in commits_filtered.jsonl.
# This is better for SZZ prep than date-window crawling, because commits may
# reference bugs created long before the commit date.
#
# Outputs:
#   bugzilla_matched.jsonl   - one JSON Bugzilla bug per line, for found IDs
#   bugzilla_missing_ids.txt - bug IDs referenced by commits but not returned
#
# Assumptions:
# - commits_filtered.jsonl contains one JSON object per line
# - commit subject/message contains patterns like "Bug 1234567"
#
# Notes:
# - Queries Bugzilla in ID batches to avoid giant requests
# - Keeps raw Bugzilla fields useful for later bug filtering and SZZ prep

import json
import re
import time
import requests

COMMITS_IN = "commits_filtered.jsonl"
BUGS_OUT = "bugzilla_matched.jsonl"
MISSING_IDS_OUT = "bugzilla_missing_ids.txt"

BUGZILLA_URL = "https://bugzilla.mozilla.org/rest/bug"
BATCH_SIZE = 200
SLEEP_BETWEEN_REQUESTS = 0.25

INCLUDE_FIELDS = [
    "id",
    "summary",
    "product",
    "component",
    "type",
    "creation_time",
    "last_change_time",
    "status",
    "resolution",
    "severity",
    "priority",
    "keywords",
    "whiteboard",
    "creator",
    "assigned_to",
    "cf_last_resolved",
    "blocks",
    "depends_on",
]

BUG_RE = re.compile(r"\bbug\s*(\d+)\b", re.I)


def chunks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def load_bug_ids_from_commits(path):
    bug_ids = set()
    commit_count = 0

    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            commit_count += 1
            c = json.loads(line)

            text = " ".join([
                c.get("subject", "") or "",
                c.get("message", "") or "",
            ])

            for m in BUG_RE.finditer(text):
                bug_ids.add(int(m.group(1)))

    return sorted(bug_ids), commit_count


def fetch_bug_batch(session, bug_ids, retries=3):
    params = [("include_fields", ",".join(INCLUDE_FIELDS))]
    for bug_id in bug_ids:
        params.append(("id", str(bug_id)))

    for attempt in range(1, retries + 1):
        try:
            r = session.get(BUGZILLA_URL, params=params, timeout=120)
            r.raise_for_status()
            data = r.json()
            return data.get("bugs", [])
        except Exception as e:
            if attempt == retries:
                raise
            wait = attempt * 1.5
            print(f"Retry {attempt}/{retries} for batch starting with {bug_ids[0]} after error: {e}")
            time.sleep(wait)

    return []


def main():
    print("Loading bug IDs from commits...")
    bug_ids, commit_count = load_bug_ids_from_commits(COMMITS_IN)
    print(f"Loaded {commit_count} commits")
    print(f"Found {len(bug_ids)} unique bug IDs")

    session = requests.Session()
    session.headers.update({
        "User-Agent": "firefox-bugzilla-miner/1.0"
    })

    fetched = {}
    total_batches = (len(bug_ids) + BATCH_SIZE - 1) // BATCH_SIZE

    for i, batch in enumerate(chunks(bug_ids, BATCH_SIZE), start=1):
        print(f"Fetching batch {i}/{total_batches} ({len(batch)} bug IDs)")
        bugs = fetch_bug_batch(session, batch)

        for bug in bugs:
            fetched[int(bug["id"])] = bug

        print(f"  returned {len(bugs)} bugs")
        time.sleep(SLEEP_BETWEEN_REQUESTS)

    with open(BUGS_OUT, "w", encoding="utf-8") as out:
        for bug_id in bug_ids:
            bug = fetched.get(bug_id)
            if bug is not None:
                out.write(json.dumps(bug, ensure_ascii=False) + "\n")

    missing_ids = [bug_id for bug_id in bug_ids if bug_id not in fetched]
    with open(MISSING_IDS_OUT, "w", encoding="utf-8") as f:
        for bug_id in missing_ids:
            f.write(str(bug_id) + "\n")

    print(f"\nWrote {len(fetched)} found bugs to {BUGS_OUT}")
    print(f"Wrote {len(missing_ids)} missing bug IDs to {MISSING_IDS_OUT}")

    if missing_ids:
        print("\nSome referenced bug IDs were not returned by Bugzilla.")
        print("Possible reasons:")
        print("- malformed bug ID extraction from commit text")
        print("- restricted/deleted/unavailable Bugzilla records")
        print("- transient API issues")


if __name__ == "__main__":
    main()