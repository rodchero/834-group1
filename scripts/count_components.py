"""Count Bugzilla products and product::components over bugzilla_matched.jsonl
and print the top N of each, to pick the per-product/component datasets."""

import json
from collections import Counter

from config import BUGS_MATCHED

TOP_N = 5

products = Counter()
components = Counter()
with open(BUGS_MATCHED, encoding="utf-8") as f:
    for line in f:
        if line.strip():
            bug = json.loads(line)
            products[bug["product"]] += 1
            components[f"{bug['product']} :: {bug['component']}"] += 1

total = sum(products.values())
for title, counter in [("Product", products), ("Product :: Component", components)]:
    print(f"\n{'#':<3} {title:<55} {'bugs':>7} {'share':>7}")
    for i, (name, n) in enumerate(counter.most_common(TOP_N), 1):
        print(f"{i:<3} {name:<55} {n:>7} {n / total:>7.1%}")
print(f"\n{total} bugs, {len(products)} products, {len(components)} components")
