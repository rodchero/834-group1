"""
Stylometric comparison of agent-authored vs ordinary commit messages.

Compares agent-authored vs ordinary commit messages for style (length,
bullets, etc.)  Descriptive only, currently too few positives (probably around 70 when labeling is done) to
train a classifier
"""

import csv, json, random, re, statistics as st
from pathlib import Path

random.seed(1)
CONTROL_N = 500          # random strategy
PER_AUTHOR_CAP = 25      # cap per author so prolific devs don't dominate

WINDOWS = {
    "human": ("commits_raw.jsonl", "ai_candidates_human-raw.csv",
              "bugzilla_matched.jsonl"),
    "ai": ("commits_raw_AI.jsonl", "ai_candidates_ai-raw.csv",
           "bugzilla_matched_AI.jsonl"),
}

OUT = "stylometry.csv"


#   Mozilla boilerplate (Differential Revision, Reviewed-by, Bug)gets dropped, as it measures how many reviewers signed off, not style  
TRAILER = re.compile(r"^[A-Za-z][A-Za-z0-9-]{2,30}:\s+\S")

#  The agent's own attribution also gets dropped, so the style of the commit message itself is measured, not the signature
SIGNATURE = re.compile(
    r"co-authored-by|noreply@anthropic|codex@openai|claude-session"
    r"|generated (with|using)|🤖|on the cli", re.I)

# finds bullet points and bugs
BULLET = re.compile(r"^\s*([-*•]|\d+[.)])\s+")
BUG_RE = re.compile(r"bug ?(\d+)", re.I)


def features(msg):
    lines = msg.splitlines()
    if lines:
        subject = lines[0]
    else:
        subject = ""

    body = []
    for line in lines[1:]:
        stripped = line.strip()
        if stripped and not TRAILER.match(stripped) and not SIGNATURE.search(line):
            body.append(line)

    bullets = 0
    body_chars = 0
    for line in body:
        if BULLET.match(line):
            bullets += 1
        body_chars += len(line)

    return {
        "subject_chars": len(subject),
        "body_chars": body_chars,
        "body_lines": len(body),
        "bullet_lines": bullets,
        "has_bullets": int(bullets > 0),
    }


def cliffs_delta(a, b):
    """Nonparametric effect size"""
    if not a or not b:
        return 0.0

    gt = 0
    lt = 0
    for x in a:
        for y in b:
            if x > y:
                gt += 1
            elif x < y:
                lt += 1

    return (gt - lt) / (len(a) * len(b))


def magnitude(d):  #Based on Roman e al. (2006) thresholds
    d = abs(d)
    if d < 0.147:
        return "negligible"
    if d < 0.33:
        return "small"
    if d < 0.474:
        return "medium"
    return "large"


def report(label, agents, controls):
    if not agents or not controls:
        print("  " + label + ": not enough data (" + str(len(agents)) +
              " vs " + str(len(controls)) + ")")
        return []

    agent_features = []
    for c in agents:
        agent_features.append(features(c["message"]))

    control_features = []
    for c in controls:
        control_features.append(features(c["message"]))

    print("")
    print("  " + label + ": " + str(len(agents)) + " agent vs " +
          str(len(controls)) + " control")
    print("    feature            agent     control    delta   magnitude")

    for key in agent_features[0]:
        a = []
        for f in agent_features:
            a.append(f[key])
        b = []
        for f in control_features:
            b.append(f[key])

        d = cliffs_delta(a, b)
        print("    " + key + "  " + str(round(st.median(a), 1)) + "  " +
              str(round(st.median(b), 1)) + "  " + str(round(d, 2)) +
              "  " + magnitude(d))

    rows = []
    for f in agent_features:
        rows.append(("agent", f))
    for f in control_features:
        rows.append(("control", f))
    return rows


def component_lookup(bugs_path):
    components = {}
    if not Path(bugs_path).exists():
        return components
    
    for line in open(bugs_path):
        b = json.loads(line)
        comp = b.get("product", "") + " :: " + b.get("component", "")
        components[str(b["id"])] = comp

    return components


def component_of(commit, components):
    m = BUG_RE.search(commit["subject"])
    if not m:
        return ""
    return components.get(m.group(1), "")


all_rows = []

for window, (commits_path, candidates_path, bugs_path) in WINDOWS.items():

    agent_hashes = set()
    flagged_hashes = set()
    for r in csv.DictReader(open(candidates_path)):
        flagged_hashes.add(r["hash"])
        if r["kind"] == "agent-authored":
            agent_hashes.add(r["hash"])

    components = component_lookup(bugs_path)

    agents = []
    pool = []
    for line in open(commits_path):
        c = json.loads(line)
        short = c["hash"][:12]
        if short in agent_hashes:
            agents.append(c)
        elif short not in flagged_hashes:
            pool.append(c)


    print(window + ": " + str(len(agents)) + " agent-authored, " +
          str(len(pool)) + " eligible controls")
    if not agents:
        continue

    # 1. random
    random_controls = random.sample(pool, min(CONTROL_N, len(pool)))
    random_rows = report("random", agents, random_controls)

    # 2. component-matched: controls drawn only from components the agents actually touched
    agent_comps = set()
    for c in agents:
        comp = component_of(c, components)
        if comp:
            agent_comps.add(comp)

    if agent_comps:
        comp_agents = []
        for c in agents:
            if component_of(c, components) in agent_comps:
                comp_agents.append(c)

        comp_pool = []
        for c in pool:
            if component_of(c, components) in agent_comps:
                comp_pool.append(c)

        print("")
        print("  [" + str(len(agent_comps)) + " components, " +
              str(len(agents) - len(comp_agents)) + " agents dropped for no bug id]")
        comp_controls = random.sample(comp_pool, min(CONTROL_N, len(comp_pool)))
        report("component", comp_agents, comp_controls)

    # 3. author-matched: each agent commit against that same developer's other commits
    by_author = {}
    for c in pool:
        author = c["author_email"]
        if author not in by_author:
            by_author[author] = []
        by_author[author].append(c)

    auth_agents = []
    auth_controls = []
    no_peers = 0
    for c in agents:
        peers = by_author.get(c["author_email"], [])
        if not peers:
            no_peers += 1
            continue
        auth_agents.append(c)
        auth_controls.extend(random.sample(peers, min(PER_AUTHOR_CAP, len(peers))))

    auth_authors = set()
    for c in auth_agents:
        auth_authors.add(c["author_email"])


    print("  [" + str(len(auth_authors)) + " authors, " + str(no_peers) +
          " agents dropped with no other commits]")
    report("author", auth_agents, auth_controls)

    for group, f in random_rows:
        row = {"window": window, "group": group}
        row.update(f)
        all_rows.append(row)

with open(OUT, "w", newline="") as f:
    if all_rows:
        w = csv.DictWriter(f, fieldnames=list(all_rows[0]))
        w.writeheader()
        w.writerows(all_rows)

print("")
print("per-commit features (random strategy): " + OUT)