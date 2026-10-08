
"""

Once a developer has disclosed AI use, every later commit of theirs is
tagged ai_exposed. 

Adoption is a property of the DEVELOPER, not of a window, so the adoption
map is built from seeds in both windows and then applied to both. A
developer who first disclosed in March 2025 is exposed for the rest of the
human window AND all of the AI window.


Do smn like this to run:
python3 merge_labels.py labelling_sheet_T.csv labelling_sheet_?.csv --resolved resolved.csv <- use resolved part ones you resolve differences

\/ This will automatically read from ^
python3 tag_exposure.py --include-borderline
"""

import argparse, csv, json
from datetime import datetime

WINDOWS = {
    "human": ("commits_filtered.jsonl", "ai_candidates_human.csv"),
    "ai": ("commits_filtered_AI.jsonl", "ai_candidates_ai.csv"),
}

# B_disclosed will come when we finish labeling and comparing the self disclosure file
DISCLOSED = {"AI_DISCLOSED", "B_DISCLOSED"}


# if we need more data, use AI_BORDERLINE commits as well. I used this to get the 3k measure
ap = argparse.ArgumentParser()
ap.add_argument("--include-borderline", action="store_true",
                help="also treat AI_BORDERLINE as a Type B seed")
args = ap.parse_args()

if args.include_borderline:
    DISCLOSED = DISCLOSED | {"AI_BORDERLINE"}


def load(path):
    commits = []
    for line in open(path):
        commits.append(json.loads(line))
    return commits


def commit_date(c):
    return c["commit_date"]


def get_count(pair):
    return pair[1]


# Seeds collected before tagging as it needs to go across windows
tier_a = set()
tier_b = set()
for window, (_, candidates) in WINDOWS.items():
    for r in csv.DictReader(open(candidates)):
        if r["kind"] == "agent-authored":
            tier_a.add(r["hash"])
        elif r.get("label", "") in DISCLOSED:
            tier_b.add(r["hash"])

print("seeds: ", str(len(tier_a)), " Type A (signed), ", str(len(tier_b)), " Type B (confirmed)")



commits = []
for window, (path, _) in WINDOWS.items():
    for c in load(path):
        c["_window"] = window
        c["_short"] = c["hash"][:12]
        commits.append(c)

commits.sort(key=commit_date)
print(str(len(commits)) + " commits across " + str(len(WINDOWS)) + " windows")


adopted = {}
for c in commits:
    if c["_short"] in tier_a or c["_short"] in tier_b:
        a = c["author_email"]
        if a not in adopted or c["commit_date"] < adopted[a]:
            adopted[a] = c["commit_date"]

print(str(len(adopted)) + " developers have an adoption point")



def within_window(author, when):
    """Is `when` inside this author's exposure period?"""
    start = adopted.get(author)
    if not start or when < start:
        return False
    return True


rows = []
tiers = {}
for c in commits:
    short = c["_short"]
    if short in tier_a:
        tier = "A"
    elif short in tier_b:
        tier = "B"
    elif within_window(c["author_email"], c["commit_date"]):
        tier = "C"
    else:
        tier = "-"

    c["_tier"] = tier
    tiers[tier] = tiers.get(tier, 0) + 1

    start = adopted.get(c["author_email"])
    days = ""
    if start:
        delta = (datetime.fromisoformat(c["commit_date"])
                 - datetime.fromisoformat(start)).days
        days = delta

    rows.append({
        "hash": c["hash"],
        "window": c["_window"],
        "date": c["commit_date"][:10],
        "author": c["author_email"],
        "tier": tier,
        "days_since_adoption": days,
    })


with open("ai_tiers.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)


def dump(name, keep):
    n = 0
    with open(name, "w") as f:
        for c in commits:
            if c["_tier"] in keep:
                out = {}
                for k, v in c.items():
                    if not k.startswith("_"):
                        out[k] = v
                f.write(json.dumps(out, ensure_ascii=False) + "\n")
                n += 1
    return n


n_exposed = dump("ai_exposed.jsonl", {"A", "B", "C"})
n_strict = dump("ai_strict.jsonl", {"A", "B"})
n_clean = dump("human_clean.jsonl", {"-"})
labels = {"A": "A  agent-signed", "B": "B  self-admitted (confirmed)",
          "C": "C  ai_exposed", "-": "-  no evidence"}

print()
for t in ["A", "B", "C", "-"]:
    n = tiers.get(t, 0)
    pct = round(100 * n / len(commits), 2)
    print(labels[t], "-", n, "commits,", pct, "%")

print()
print("ai_exposed.jsonl  ", n_exposed, " (A+B+C -- the Type C dataset)")
print("ai_strict.jsonl   ", n_strict, " (A+B only)")
print("human_clean.jsonl ", n_clean, " (no evidence at any tier)")
print("ai_tiers.csv      ", len(rows), " (hash -> tier, join key)")

# Per window, since we need dataset 2 and dataset 3 separately.
print("")
print("window    A     B     C        -")
per = {}
for r in rows:
    w = r["window"]
    t = r["tier"]
    if w not in per:
        per[w] = {}
    per[w][t] = per[w].get(t, 0) + 1

for window in WINDOWS:
    p = per.get(window, {})
    print(window + "  " + str(p.get("A", 0)) + "  " + str(p.get("B", 0)) +
          "  " + str(p.get("C", 0)) + "  " + str(p.get("-", 0)))

# lets check if any developers dominate, incase its like 2 of them
share = {}
for r in rows:
    if r["tier"] == "C":
        share[r["author"]] = share.get(r["author"], 0) + 1

if share:
    ranked = sorted(share.items(), key=get_count, reverse=True)
    top, n_top = ranked[0]
    print("")
    print(str(len(share)) + " developers contribute Type C commits")
    pct_top = round(100 * n_top / tiers.get("C", 0), 0)
    print("largest share: " + str(n_top) + " commits (" + str(pct_top) +
          "%) -- " + top)
    for author, n in ranked[:5]:
        print("   " + str(n) + "  " + author)


# Following is helped by claude


# Kamei fits logistic regression on 14 metrics; at 10 events per predictor and
# a ~5% defect rate that needs roughly 2,800 commits for a general model.
need = 2800
print(f"\nEPV check (14 predictors x 10 events / ~5% defect rate = ~{need:,}):")
for name, n in [("A+B strict", n_strict), ("A+B+C exposed", n_exposed)]:
    print(f"  {name:<16} {n:>8,}  {'sufficient' if n >= need else 'too small'}")
