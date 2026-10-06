"""

Document what patterns are actually in the commit messages

Runs on the RAW files, excluded commits (vendored, WPT) may carry agent
signatures in formats not present in cleaned commits
"""

import json, re
from pathlib import Path

INPUTS = ["commits_raw.jsonl", "commits_raw_AI.jsonl"]

COAUTHOR = re.compile(r"^\s*co-authored-by:\s*(.+)$", re.I | re.M)
TRAILER = re.compile(r"^([A-Za-z][A-Za-z0-9-]{2,30}):\s+\S", re.M)

# Phrases agents use that are not trailers
PHRASE = re.compile(
    r"(generated|written|created|authored|assisted|co-?authored)"
    r"[^\n]{0,40}(with|by|using)[^\n]{0,60}", re.I)

def get_count(pair):
    return pair[1]

def top(counts, n):
    """The n pairs with the highest counts"""
    pairs = list(counts.items())
    pairs.sort(key=get_count, reverse=True)
    return pairs[:n]

for path in INPUTS:

    commits = []
    for line in open(path):
        commits.append(json.loads(line))

    coauthors = {}
    trailers = {}
    phrases = {}
    n_coauthored = 0

    for c in commits:
        msg = c["message"]

        found = COAUTHOR.findall(msg)
        if found:
            n_coauthored += 1
            
        for ident in found:
            key = ident.strip().lower()
            coauthors[key] = coauthors.get(key, 0) + 1

        for key in TRAILER.findall(msg):
            key = key.lower()
            trailers[key] = trailers.get(key, 0) + 1

        for m in PHRASE.finditer(msg):
            phrase = m.group(0).strip().lower()[:70]
            phrases[phrase] = phrases.get(phrase, 0) + 1

    pct_coauthored = round(100 * n_coauthored / len(commits), 2)



    print(path, ":", len(commits), "commits")
    print(n_coauthored, "carry a Co-authored-by trailer (", pct_coauthored, "%)")

    print()
    print("trailer keys (", len(trailers), "distinct)")
    for key, n in top(trailers, 25):
        print(" ", n, " ", key)

    print()
    print("co-author identities (", len(coauthors), "distinct)")
    for ident, n in coauthors.items():
        print(" ", n, " ", ident)

    print()
    print("'generated/written with' phrases (", len(phrases), "distinct)")
    for p, n in top(phrases, 30):
        print(" ", n, " ", p)