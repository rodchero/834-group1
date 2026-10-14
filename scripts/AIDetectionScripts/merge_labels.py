"""
Merge the manual AI-disclosure labels from every rater into one file.

Rater sheets live in LABELLING_DIR as labelling_sheet_<rater>.csv, or
labelling_sheet_<rater>_<batch>.csv when a rater labels in several batches.
Rows are matched to candidates by commit hash (first 12 characters), so labels
survive regenerating ai_candidates.csv. Old sheets without a hash column are
mapped through labelling_key.csv (row_id -> hash).

Outputs:
  ai_labels.csv            one row per candidate with its final label and source
  labelling_todo.csv       self-admitted candidates with fewer than 2 labels
  label_disagreements.csv  rows where raters disagree, for a third person to
                           resolve into resolved_labels.csv (hash,label)

Cohen's kappa is printed for every pair of raters that share labelled rows,
on the collapsed classes (all FP_* labels count as one class, as in the analysis)
and on the binary AI_DISCLOSED vs everything else.
"""

import csv
import re
from collections import Counter, defaultdict
from itertools import combinations

from config import (
    AI_CANDIDATES, AI_LABELS, LABELLING_DIR, LABELLING_KEY, RESOLVED_LABELS,
    LABELLING_TODO, LABEL_DISAGREEMENTS,
)

VALID = {"AI_DISCLOSED", "AI_BORDERLINE", "FP_FEATURE", "FP_TOOLING", "FP_NOISE", "FP_OTHER", "UNSURE"}
SHEET_RE = re.compile(r"^labelling_sheet_([A-Za-z0-9]+)(?:_.+)?\.csv$")
TODO_FIELDS = ["hash", "window", "date", "author", "component", "matched", "context",
               "subject", "labelled_by", "label", "notes"]


def short(h):
    return h.strip()[:12]


def collapse(label):
    return "FP" if label.startswith("FP_") else label


def binary(label):
    return "AI" if label == "AI_DISCLOSED" else "NOT_AI"


def load_key():
    if not LABELLING_KEY.exists():
        return {}
    with open(LABELLING_KEY, encoding="utf-8") as f:
        return {r["row_id"]: short(r["hash"]) for r in csv.DictReader(f)}


def load_rater_sheets(key):
    """Returns {rater: {hash12: label}} and warns about bad rows."""
    labels = defaultdict(dict)
    for path in sorted(LABELLING_DIR.glob("labelling_sheet_*.csv")):
        m = SHEET_RE.match(path.name)
        if not m:
            continue
        rater = m.group(1)
        n_rows = n_labelled = 0
        with open(path, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                n_rows += 1
                label = (r.get("label") or "").strip()
                if not label:
                    continue
                if label not in VALID:
                    print(f"  [WARN] {path.name}: unknown label {label!r}, ignored")
                    continue
                h = short(r["hash"]) if r.get("hash") else key.get(r.get("row_id", ""))
                if not h:
                    print(f"  [WARN] {path.name}: row {r.get('row_id')} has no hash and is not in the key")
                    continue
                if h in labels[rater] and labels[rater][h] != label:
                    print(f"  [WARN] {path.name}: {h} labelled twice by {rater}, keeping the later label")
                labels[rater][h] = label
                n_labelled += 1
        print(f"  {path.name}: rater {rater}, {n_labelled}/{n_rows} rows labelled")
    return labels


def load_resolved():
    if not RESOLVED_LABELS.exists():
        return {}
    resolved = {}
    with open(RESOLVED_LABELS, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            label = (r.get("label") or "").strip()
            if label in VALID:
                resolved[short(r["hash"])] = label
            elif label:
                print(f"  [WARN] {RESOLVED_LABELS.name}: unknown label {label!r}, ignored")
    return resolved


def cohen_kappa(pairs):
    n = len(pairs)
    if n == 0:
        return None
    observed = sum(a == b for a, b in pairs) / n
    count_a = Counter(a for a, _ in pairs)
    count_b = Counter(b for _, b in pairs)
    expected = sum(count_a[c] * count_b[c] for c in count_a) / (n * n)
    if expected == 1:
        return 1.0
    return (observed - expected) / (1 - expected)


def report_kappa(labels, candidate_hashes):
    raters = sorted(labels)
    if len(raters) < 2:
        print("\nKappa: needs at least two raters with labels")
        return
    print("\nCohen's kappa (rows labelled by both raters, current candidates only):")
    for a, b in combinations(raters, 2):
        shared = sorted(set(labels[a]) & set(labels[b]) & candidate_hashes)
        if not shared:
            print(f"  {a} vs {b}: no shared rows")
            continue
        k_coll = cohen_kappa([(collapse(labels[a][h]), collapse(labels[b][h])) for h in shared])
        k_bin = cohen_kappa([(binary(labels[a][h]), binary(labels[b][h])) for h in shared])
        print(f"  {a} vs {b}: n={len(shared)}  collapsed={k_coll:.3f}  AI_DISCLOSED-vs-rest={k_bin:.3f}")


def final_label(given, resolved_label):
    """Returns (label, source) for one self-admitted candidate."""
    if resolved_label:
        return resolved_label, "resolved"
    if not given:
        return "", "unlabelled"
    if len(given) == 1:
        return next(iter(given.values())), "single"
    distinct = set(given.values())
    if len(distinct) == 1:
        return distinct.pop(), "agreed"
    if len({collapse(l) for l in distinct}) == 1:
        # Only the FP sub-type differs, which the analysis collapses anyway
        return collapse(distinct.pop()), "agreed"
    return "", "unresolved"


def write_csv(path, fieldnames, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def main():
    if not AI_CANDIDATES.exists():
        raise FileNotFoundError(f"Missing input file: {AI_CANDIDATES}")

    with open(AI_CANDIDATES, encoding="utf-8") as f:
        candidates = list(csv.DictReader(f))
    candidate_hashes = {short(c["hash"]) for c in candidates}

    print("Rater sheets:")
    labels = load_rater_sheets(load_key())
    resolved = load_resolved()

    stale = {h for rater in labels.values() for h in rater} - candidate_hashes
    if stale:
        print(f"  {len(stale)} labelled rows are no longer candidates and are ignored")

    report_kappa(labels, candidate_hashes)

    out_rows, todo_rows, disagreement_rows = [], [], []
    sources = Counter()
    final_counts = Counter()

    for c in candidates:
        h = short(c["hash"])
        given = {rater: labels[rater][h] for rater in sorted(labels) if h in labels[rater]}

        if c["kind"] == "agent-authored":
            label, source = "AGENT_AUTHORED", "auto"
        else:
            label, source = final_label(given, resolved.get(h))
            if len(given) < 2:
                todo_rows.append({k: c.get(k, "") for k in TODO_FIELDS if k in c}
                                 | {"labelled_by": ",".join(given), "label": "", "notes": ""})
            if source == "unresolved":
                disagreement_rows.append({
                    "hash": c["hash"], "window": c["window"], "subject": c["subject"],
                    "context": c["context"],
                    "rater_labels": "; ".join(f"{r}={l}" for r, l in given.items()),
                    "label": "",
                })

        sources[source] += 1
        final_counts[label or "(none)"] += 1
        out_rows.append({
            "hash": c["hash"], "window": c["window"], "kind": c["kind"],
            "label": label, "source": source,
            "rater_labels": "; ".join(f"{r}={l}" for r, l in given.items()),
        })

    write_csv(AI_LABELS, ["hash", "window", "kind", "label", "source", "rater_labels"], out_rows)
    write_csv(LABELLING_TODO, TODO_FIELDS, todo_rows)
    write_csv(LABEL_DISAGREEMENTS, ["hash", "window", "subject", "context", "rater_labels", "label"],
              disagreement_rows)

    print(f"\nFinal label sources: {dict(sources)}")
    print(f"Final labels: {dict(final_counts)}")
    print(f"\nWrote {len(out_rows)} rows to {AI_LABELS}")
    print(f"Wrote {len(todo_rows)} rows needing more labels to {LABELLING_TODO}")
    print(f"Wrote {len(disagreement_rows)} unresolved disagreements to {LABEL_DISAGREEMENTS}")


if __name__ == "__main__":
    main()
