import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT / "firefox"
OUT = ROOT / "commits_raw.jsonl"

FIELDS = ["%H", "%cI", "%ae", "%ce", "%s", "%B"]
NAMES = ["hash", "commit_date", "author_email", "committer_email", "subject", "message"]


def main():
    if not REPO.exists():
        raise FileNotFoundError(f"Firefox repo not found: {REPO}")

    # now captures ALL commits; filting by date too early torpedoes the later feature calculations - I need the entire commit history for that. - Roman
    # e.g., prior commits influences the developer experience category (rexp, sexp, exp)
    log = subprocess.run(
        [
            "git", "-C", str(REPO), "log",
            "--no-merges",
            "--pretty=format:\x1e" + "\x1f".join(FIELDS),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )

    n = 0
    with open(OUT, "w", encoding="utf-8") as out:
        for chunk in log.stdout.split("\x1e"):
            if not chunk.strip():
                continue

            parts = chunk.split("\x1f")
            if len(parts) != len(NAMES):
                continue

            commit = dict(zip(NAMES, parts))
            commit["message"] = commit["message"].strip()

            out.write(json.dumps(commit, ensure_ascii=False) + "\n")
            n += 1

    print(f"{n} commits")
    print(f"Path: {OUT}")

    if n == 0:
        raise RuntimeError("No commits extracted from Firefox repository")


if __name__ == "__main__":
    main()