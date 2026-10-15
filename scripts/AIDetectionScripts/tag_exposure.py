"""
Tag every filtered commit with its AI evidence tier, written to ai_tiers.csv.

  A  agent-authored (signed by a coding agent)
  B  self-admitted, confirmed by the manual labels (AI_DISCLOSED)
  C  ai_exposed: any later commit by a developer who has an A or B commit
  -  no evidence

Once a developer has disclosed AI use, every later commit of theirs is
tagged ai_exposed. Adoption is a property of the DEVELOPER, not of a window,
so the adoption map is built from seeds in both windows and then applied to
both. A developer who first disclosed in March 2025 is exposed for the rest
of the human window AND all of the AI window.

Seeds come from ai_labels.csv (merge_labels.py). Set
EXPOSURE_INCLUDE_BORDERLINE in config.py to also use AI_BORDERLINE as seeds.
"""

import csv
import json
from collections import Counter
from datetime import datetime

from config import COMMITS_FILTERED, AI_LABELS, AI_TIERS, WINDOWS, EXPOSURE_INCLUDE_BORDERLINE

DISCLOSED = {"AI_DISCLOSED"} | ({"AI_BORDERLINE"} if EXPOSURE_INCLUDE_BORDERLINE else set())
TIER_NAMES = {"A": "agent-signed", "B": "self-admitted (confirmed)", "C": "ai_exposed", "-": "no evidence"}


def parse_date(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def load_seeds():
    tier_a, tier_b = set(), set()
    with open(AI_LABELS, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["label"] == "AGENT_AUTHORED":
                tier_a.add(r["hash"])
            elif r["label"] in DISCLOSED:
                tier_b.add(r["hash"])
    return tier_a, tier_b


def main():
    for path in (COMMITS_FILTERED, AI_LABELS):
        if not path.exists():
            raise FileNotFoundError(f"Missing input file: {path}")

    tier_a, tier_b = load_seeds()
    print(f"Seeds: {len(tier_a)} tier A (signed), {len(tier_b)} tier B (confirmed)"
          + (", AI_BORDERLINE included" if EXPOSURE_INCLUDE_BORDERLINE else ""))

    with open(COMMITS_FILTERED, encoding="utf-8") as f:
        commits = [json.loads(line) for line in f if line.strip()]
    for c in commits:
        c["_dt"] = parse_date(c["commit_date"])
    commits.sort(key=lambda c: c["_dt"])

    # Earliest seed commit per developer, across both windows
    adopted = {}
    for c in commits:
        if c["hash"] in tier_a or c["hash"] in tier_b:
            adopted.setdefault(c["author_email"], c["_dt"])
    print(f"{len(adopted)} developers have an adoption point")

    rows = []
    for c in commits:
        start = adopted.get(c["author_email"])
        if c["hash"] in tier_a:
            tier = "A"
        elif c["hash"] in tier_b:
            tier = "B"
        elif start and c["_dt"] >= start:
            tier = "C"
        else:
            tier = "-"
        rows.append({
            "hash": c["hash"],
            "window": c["window"],
            "date": c["commit_date"][:10],
            "author": c["author_email"],
            "tier": tier,
            "days_since_adoption": (c["_dt"] - start).days if start else "",
        })

    with open(AI_TIERS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows to {AI_TIERS}")

    # Per window, since dataset 2 and dataset 3 come from different windows
    per = Counter((r["window"], r["tier"]) for r in rows)
    print(f"\n{'window':<8}" + "".join(f"{t:>8}" for t in TIER_NAMES))
    for window in WINDOWS:
        print(f"{window:<8}" + "".join(f"{per[window, t]:>8}" for t in TIER_NAMES))
    print("  " + ", ".join(f"{t} = {name}" for t, name in TIER_NAMES.items()))

    # Check whether a few developers dominate the exposed set
    share = Counter(r["author"] for r in rows if r["tier"] == "C")
    if share:
        n_c = sum(share.values())
        print(f"\n{len(share)} developers contribute tier C commits; top 5:")
        for author, n in share.most_common(5):
            print(f"  {n:>6} ({n / n_c:.0%})  {author}")


if __name__ == "__main__":
    main()
