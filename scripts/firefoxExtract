# Dump Firefox commits in a date window to JSONL, one commit per line.
import json, subprocess, sys

FIELDS = ["%H", "%cI", "%ae", "%ce", "%s", "%B"]
NAMES = ["hash", "commit_date", "author_email", "committer_email",
         "subject", "message"] # using the committer date
OUT = "commits_raw.jsonl"


log = subprocess.run(
    ["git", "-C", "firefox", "log",
     "--no-merges",                 #ignoring merge commits, they have no changes of their own
     "--since=2024-11-01",             
     "--until=2025-11-01",
     "--pretty=format:\x1e" + "\x1f".join(FIELDS)], #commits start with \x1e, fields separated by \x1f
    capture_output=True, text=True, encoding="utf-8", errors="replace")

n = 0
with open(OUT, "w", encoding="utf-8") as out:
    for chunk in log.stdout.split("\x1e"):
        if not chunk.strip():    
            continue
        
        commit = dict(zip(NAMES, chunk.split("\x1f")))
        commit["message"] = commit["message"].strip()

        out.write(json.dumps(commit, ensure_ascii=False) + "\n")
        n += 1

print(n, "commits")
print("Path: ", OUT)