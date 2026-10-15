"""
Build the replication package's input files from the labelled dataset.

Joins each commit's features and SZZ bug label (final_dataset.csv) with its
window and AI tier (ai_tiers.csv) and its Bugzilla product (first bug ID in the
subject), then writes, for every dataset in config.DATASETS:

  input/<dataset>.csv            general model, every commit in the dataset
  input/<dataset>_<product>.csv  one per product, for the N_PRODUCTS products
                                 with the most commits in that dataset

in the format the R scripts read (transactionid as the first column, which R
uses as row names). Sizes and defect rates go to datasets_summary.csv.
"""

import csv
import json
import re
from collections import Counter

from config import (
    FINAL_DATASET, AI_TIERS, COMMITS_FILTERED, BUGS_MATCHED, DATASETS_SUMMARY,
    INPUT_DIR, DATASETS, N_PRODUCTS, BUG_RE, MIN_DEFECTIVE,
)


def load_products():
    """Returns {hash: Bugzilla product}, from the first bug ID in each subject."""
    bug_product = {}
    with open(BUGS_MATCHED, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                b = json.loads(line)
                bug_product[int(b["id"])] = b["product"]

    products = {}
    with open(COMMITS_FILTERED, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                c = json.loads(line)
                m = BUG_RE.search(c["subject"])
                products[c["hash"]] = bug_product.get(int(m.group(1))) if m else None
    return products


def slug(product):
    """File-name form of a product, e.g. "Firefox for Android" -> "firefox_for_android"."""
    return re.sub(r"[^a-z0-9]+", "_", product.lower()).strip("_")


def write_rows(path, fieldnames, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def main():
    for path in (FINAL_DATASET, AI_TIERS, COMMITS_FILTERED, BUGS_MATCHED):
        if not path.exists():
            raise FileNotFoundError(f"Missing input file: {path}")
    INPUT_DIR.mkdir(exist_ok=True)

    with open(FINAL_DATASET, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    with open(AI_TIERS, newline="", encoding="utf-8") as f:
        tiers = {r["hash"]: (r["window"], r["tier"]) for r in csv.DictReader(f)}
    products = load_products()

    missing = [r["transactionid"] for r in rows if r["transactionid"] not in tiers]
    if missing:
        raise RuntimeError(f"{len(missing)} commits in {FINAL_DATASET.name} have no tier "
                           f"in {AI_TIERS.name} (e.g. {missing[0]}); re-run tag_exposure")

    summary = []
    for name, (window, keep_tiers) in DATASETS.items():
        in_window = [r for r in rows if tiers[r["transactionid"]][0] == window]
        kept = [r for r in in_window if tiers[r["transactionid"]][1] in keep_tiers]
        tier_counts = Counter(tiers[r["transactionid"]][1] for r in kept)
        print(f"\n[{name}] window={window}, tiers={sorted(keep_tiers)}: "
              f"{len(kept)} of {len(in_window)} commits kept "
              f"({len(in_window) - len(kept)} excluded by tier), by tier {dict(sorted(tier_counts.items()))}")

        # Per-product models: the N_PRODUCTS products with the most commits in this dataset
        product_counts = Counter(products.get(r["transactionid"]) for r in kept)
        no_product = product_counts.pop(None, 0)
        top = [p for p, _ in product_counts.most_common(N_PRODUCTS)]
        subsets = [(name, "(all)", kept)]
        for product in top:
            subsets.append((f"{name}_{slug(product)}", product,
                            [r for r in kept if products.get(r["transactionid"]) == product]))

        other = len(kept) - no_product - sum(product_counts[p] for p in top)
        print(f"  not in a product dataset: {no_product} with no Bugzilla bug, {other} in other products")

        # Remove product files from earlier builds, whose top products may differ
        for old in INPUT_DIR.glob(f"{name}_*.csv"):
            old.unlink()

        for out_name, product, subset in subsets:
            n_bug = sum(r["bug"] == "1" for r in subset)
            rate = n_bug / len(subset) if subset else 0
            write_rows(INPUT_DIR / f"{out_name}.csv", fieldnames, subset)
            summary.append({"dataset": out_name, "window": window, "product": product,
                            "commits": len(subset), "defective": n_bug, "defect_rate": f"{rate:.4f}"})
            warn = "  [WARN] too few defective commits to model" if n_bug < MIN_DEFECTIVE else ""
            print(f"  {out_name + '.csv':<36} {product:<26} {len(subset):>7} commits "
                  f"{n_bug:>6} defective ({rate:.1%}){warn}")

    write_rows(DATASETS_SUMMARY, list(summary[0]), summary)
    print(f"\nWrote {len(summary)} datasets to {INPUT_DIR}, summary in {DATASETS_SUMMARY}")


if __name__ == "__main__":
    main()
