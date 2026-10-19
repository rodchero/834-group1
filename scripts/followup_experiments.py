"""Audit follow-up hypotheses against the data already in this package.

The current input CSVs are commit-level model datasets. This script computes
commit/day and path-level churn summaries from those CSVs plus the numstat
cache, and can export a conservative human dataset with commits touching
administrative paths removed. It explicitly reports tests that need missing
PR, prediction, future-snapshot, raw-metric, or identity-alias data.

Example:
    python -m scripts.followup_experiments \
        --write-human-filtered input/ff_human_no_admin_paths.csv

Then, if R is installed, run:
    python -m scripts.run_experiments ff_human_no_admin_paths
"""

import argparse
import csv
import json
import re
import statistics
from collections import Counter
from datetime import datetime
from pathlib import Path

from config import INPUT_DIR, NUMSTAT, OUTPUT_DIR

LOCKFILE_NAMES = {
    "cargo.lock", "package-lock.json", "npm-shrinkwrap.json", "yarn.lock",
    "pnpm-lock.yaml", "composer.lock", "gemfile.lock", "poetry.lock",
    "pipfile.lock", "gradle.lockfile", "go.sum",
}
ADMIN_PATH_RE = re.compile(
    r"(^|/)(third_party|vendor|wpt)(/|$)"
    r"|(^|/)testing/web-platform-tests(/|$)"
    r"|(^|/)testing/web-platform/meta(/|$)", re.I
)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--human", type=Path, default=INPUT_DIR / "ff_human.csv")
    parser.add_argument("--ai", type=Path, default=INPUT_DIR / "ff_ai.csv")
    parser.add_argument("--numstat", type=Path, default=NUMSTAT)
    parser.add_argument(
        "--output-dir", type=Path, default=OUTPUT_DIR / "followup",
        help="directory for reports and churn summaries",
    )
    parser.add_argument(
        "--write-human-filtered", type=Path,
        help="optional replication-format CSV excluding every human commit that touches an administrative path",
    )
    return parser.parse_args()


def read_rows(path):
    with path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames:
            raise ValueError(f"No CSV header in {path}")
        return reader.fieldnames, list(reader)


def is_lockfile(path):
    name = path.rsplit("/", 1)[-1].lower()
    return name in LOCKFILE_NAMES or name.endswith(".lock")


def is_admin_path(path):
    normalized = path.replace("\\", "/").lstrip("./")
    return bool(ADMIN_PATH_RE.search(normalized)) or is_lockfile(normalized)


def load_numstat(path, wanted_hashes):
    result = {}
    with path.open(encoding="utf-8") as source:
        for line in source:
            if not line.strip():
                continue
            record = json.loads(line)
            commit_hash = record["hash"]
            if commit_hash not in wanted_hashes:
                continue
            all_churn = 0
            admin_churn = 0
            paths = []
            for item in record.get("files", []):
                file_path = item.get("path", "")
                churn = int(item.get("added", 0)) + int(item.get("deleted", 0))
                all_churn += churn
                paths.append(file_path)
                if is_admin_path(file_path):
                    admin_churn += churn
            result[commit_hash] = {
                "churn": all_churn,
                "admin_churn": admin_churn,
                "paths": paths,
                "touches_admin": any(is_admin_path(file_path) for file_path in paths),
            }
    missing = wanted_hashes - result.keys()
    if missing:
        example = next(iter(missing))
        raise RuntimeError(
            f"{len(missing)} target commits missing from {path.name} (e.g. {example}); "
            "do not interpret churn results until the cache is complete"
        )
    return result


def percentile(values, fraction):
    if not values:
        return 0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * fraction + 0.999999)))
    return ordered[index]


def concentration(churn_by_hash):
    values = sorted(churn_by_hash.values(), reverse=True)
    total = sum(values)
    top_n = max(1, (len(values) + 99) // 100) if values else 0
    return {
        "commits": len(values),
        "total_lines_added_plus_deleted": total,
        "top_1pct_commit_count": top_n,
        "top_1pct_churn_share": sum(values[:top_n]) / total if total else 0.0,
        "median_commit_churn": statistics.median(values) if values else 0,
        "p95_commit_churn": percentile(values, 0.95),
        "max_commit_churn": max(values, default=0),
    }


def smallest_first_recall(rows, numstat, effort_fraction=0.20):
    ordered = sorted(
        rows,
        key=lambda row: (numstat[row["transactionid"]]["churn"], row["transactionid"]),
    )
    total_effort = sum(numstat[row["transactionid"]]["churn"] for row in ordered)
    total_defects = sum(int(float(row["bug"])) for row in ordered)
    if not ordered or not total_effort or not total_defects:
        return 0.0

    effort = 0
    defects = 0
    best_distance = float("inf")
    best_recall = 0.0
    for row in ordered:
        effort += numstat[row["transactionid"]]["churn"]
        defects += int(float(row["bug"]))
        distance = abs(effort / total_effort - effort_fraction)
        if distance < best_distance:
            best_distance = distance
            best_recall = defects / total_defects
    return best_recall


def dataset_summary(name, rows, numstat):
    by_day = Counter()
    day_defects = Counter()
    defects = 0
    churn = {}
    non_admin_path_churn = {}
    touches_admin = set()
    for row in rows:
        commit_hash = row["transactionid"]
        date = datetime.strptime(row["commitdate"].split()[0], "%Y/%m/%d").date().isoformat()
        bug = int(float(row["bug"]))
        by_day[date] += 1
        day_defects[date] += bug
        defects += bug
        item = numstat[commit_hash]
        churn[commit_hash] = item["churn"]
        non_admin_path_churn[commit_hash] = item["churn"] - item["admin_churn"]
        if item["touches_admin"]:
            touches_admin.add(commit_hash)

    daily = list(by_day.values())
    return {
        "dataset": name,
        "commits": len(rows),
        "defective_commits": defects,
        "defect_rate": defects / len(rows) if rows else 0.0,
        "days_with_commits": len(by_day),
        "mean_commits_per_active_day": statistics.mean(daily) if daily else 0.0,
        "median_commits_per_active_day": statistics.median(daily) if daily else 0.0,
        "p95_commits_per_active_day": percentile(daily, 0.95),
        "max_commits_per_day": max(daily, default=0),
        "admin_path_touch_commits": len(touches_admin),
        "admin_path_touch_share": len(touches_admin) / len(rows) if rows else 0.0,
        "admin_path_churn_share": (
            sum(numstat[commit_hash]["admin_churn"] for commit_hash in churn)
            / sum(churn.values()) if sum(churn.values()) else 0.0
        ),
        "smallest_first_defect_recall_at_20pct_effort": smallest_first_recall(rows, numstat),
        "all_path_churn": concentration(churn),
        "non_admin_path_churn_on_same_commits": concentration(non_admin_path_churn),
        "admin_commit_exclusion_churn": concentration(
            {h: churn[h] for h in churn if h not in touches_admin}
        ),
        "daily_commit_counts": by_day,
        "daily_defect_counts": day_defects,
        "touches_admin": touches_admin,
    }


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def build_markdown_report(summaries, unavailable):
    human, ai = summaries
    filtered = human["admin_commit_exclusion_churn"]
    human_full = human["all_path_churn"]
    ai_full = ai["all_path_churn"]
    return "\n".join([
        "# Follow-up Experiment Evidence",
        "",
        "Generated from the attached replication inputs and numstat cache. These results are descriptive/sensitivity evidence, not causal proof.",
        "",
        "## 1. Commit Velocity and False Alarms",
        "",
        "**Status: Partial descriptive evidence; PR-level test unavailable.**",
        "",
        f"- Human: {human['commits']:,} commits over {human['days_with_commits']} active days; mean {human['mean_commits_per_active_day']:.1f}, median {human['median_commits_per_active_day']:.1f}, p95 {human['p95_commits_per_active_day']}, maximum {human['max_commits_per_day']} commits per active day.",
        f"- AI: {ai['commits']:,} commits over {ai['days_with_commits']} active days; mean {ai['mean_commits_per_active_day']:.1f}, median {ai['median_commits_per_active_day']:.1f}, p95 {ai['p95_commits_per_active_day']}, maximum {ai['max_commits_per_day']} commits per active day.",
        f"- Limitation: {unavailable['pr_level_false_alarm_rate']}",
        "- Needed to test the hypothesis: PR/MR ID for each commit and saved model predictions/false-positive labels; compare daily commit-level and PR-level counts and false-alarm rates.",
        "",
        "## 2. Administrative Churn and Baseline",
        "",
        "**Status: Path-filter sensitivity available; bot-author and model-dominance tests incomplete.**",
        "",
        f"- Human top-1% churn share: {human_full['top_1pct_churn_share']:.1%} before filtering; {filtered['top_1pct_churn_share']:.1%} after excluding whole commits touching identified administrative paths.",
        f"- {human['admin_path_touch_commits']:,} human commits ({human['admin_path_touch_share']:.1%}) touch those paths; they account for {human['admin_path_churn_share']:.1%} of measured churn.",
        f"- AI top-1% churn share: {ai_full['top_1pct_churn_share']:.1%}; admin-path churn share: {ai['admin_path_churn_share']:.1%}.",
        f"- Human smallest-first baseline finds {human['smallest_first_defect_recall_at_20pct_effort']:.1%} of defects at approximately 20% of measured effort; AI baseline: {ai['smallest_first_defect_recall_at_20pct_effort']:.1%}.",
        f"- Limitation: {unavailable['bot_author_exclusion']}",
        "- The filtered CSV excludes entire mixed commits that touch an admin path; this is a conservative sensitivity set, not a file-level recomputation. Re-run the R models on it (requires Rscript) to compare model rankings.",
        "",
        "## 3. AI Cohort Right-Censoring",
        "",
        "**Status: Not testable with the current snapshot.**",
        "",
        f"- Current AI set: {ai['commits']:,} commits, {ai['defective_commits']:,} labeled defective ({ai['defect_rate']:.1%}) at the existing snapshot.",
        f"- Limitation: {unavailable['future_right_censoring']}",
        "- Needed: later Firefox repository snapshot, SZZ relabeling of the exact same AI commit hashes, and a fixed-cohort model comparison using the same metrics and evaluation procedure.",
        "",
        "## 4. AGE and FIX Methodology",
        "",
        "**Status: Corrected metric implementation is documented; flawed-method comparison is not testable from the attached aggregates.**",
        "",
        "- Current feature extractor calculates AGE (`pd`) as mean days since each modified file's last change and FIX (`fix`) from Bugzilla issue metadata.",
        f"- Limitation: {unavailable['legacy_age_and_fix_recalculation']}",
        "- Needed: per-file age inputs and complete commit messages; then recompute both definitions while holding cohort, labels, model, and folds fixed.",
        "",
        "## 5. Developer Identity and SEXP",
        "",
        "**Status: Not testable with current model CSVs.**",
        "",
        f"- Limitation: {unavailable['identity_aliasing_sexp']}",
        "- Needed: author identity per historical commit plus a reviewed email-alias mapping. Recompute SEXP and rerun the same models; do not infer person identity from name/domain heuristics alone.",
        "",
        "## Generated Files",
        "",
        "- `daily_volume.csv`: per-day commit and labeled-defect counts.",
        "- `churn_concentration.csv`: all-path, non-admin-path, and admin-commit-exclusion churn distributions.",
        "- `followup_report.json`: full machine-readable dataset statistics and limitations.",
        "- `followup_report.md`: this human-readable summary.",
        "",
        "The data do not establish that the original theory is true or false. A change in an aggregate or model score is evidence for a follow-up analysis, not proof of the proposed cause.",
        "",
    ])


def main():
    args = parse_args()
    for path in (args.human, args.ai, args.numstat):
        if not path.exists():
            raise FileNotFoundError(f"Required file not found: {path}")

    human_fields, human_rows = read_rows(args.human)
    ai_fields, ai_rows = read_rows(args.ai)
    if human_fields != ai_fields:
        raise ValueError("Human and AI CSV schemas differ; this audit expects matching replication schemas")
    required = {"transactionid", "commitdate", "bug"}
    if not required.issubset(human_fields):
        raise ValueError(f"Input CSV lacks required columns: {sorted(required - set(human_fields))}")

    hashes = {row["transactionid"] for row in human_rows + ai_rows}
    numstat = load_numstat(args.numstat, hashes)
    summaries = [
        dataset_summary("ff_human", human_rows, numstat),
        dataset_summary("ff_ai", ai_rows, numstat),
    ]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    daily_rows = []
    churn_rows = []
    report_summaries = []
    human_admin_hashes = summaries[0]["touches_admin"]
    for summary in summaries:
        daily_counts = summary.pop("daily_commit_counts")
        daily_defects = summary.pop("daily_defect_counts")
        touches_admin = summary.pop("touches_admin")
        for day, count in sorted(daily_counts.items()):
            daily_rows.append({
                "dataset": summary["dataset"], "date": day,
                "commit_count": count, "defective_commit_count": daily_defects[day],
            })
        for population_name in (
            "all_path_churn", "non_admin_path_churn_on_same_commits", "admin_commit_exclusion_churn",
        ):
            values = summary[population_name]
            churn_rows.append({
                "dataset": summary["dataset"], "population": population_name,
                **values,
            })
        report_summaries.append(summary)

    write_csv(
        args.output_dir / "daily_volume.csv",
        ["dataset", "date", "commit_count", "defective_commit_count"], daily_rows,
    )
    write_csv(
        args.output_dir / "churn_concentration.csv",
        ["dataset", "population", "commits", "total_lines_added_plus_deleted",
         "top_1pct_commit_count", "top_1pct_churn_share", "median_commit_churn",
         "p95_commit_churn", "max_commit_churn"], churn_rows,
    )

    if args.write_human_filtered:
        filtered = [row for row in human_rows if row["transactionid"] not in human_admin_hashes]
        write_csv(args.write_human_filtered, human_fields, filtered)
        print(f"Wrote {len(filtered)} of {len(human_rows)} human commits to {args.write_human_filtered}")
        print("This excludes whole commits touching an administrative path; it is a sensitivity dataset, not a path-level feature reconstruction.")

    report = {
        "available_data_findings": report_summaries,
        "not_testable_from_attached_data": {
            "pr_level_false_alarm_rate": "No PR/MR identifier or saved per-commit prediction/false-positive output is present. Daily commit counts are descriptive only.",
            "bot_author_exclusion": "The replication CSVs omit author identity. No author/committer metadata file is included in the attached artifacts.",
            "future_right_censoring": "The current SZZ labels stop at the 2026-10-08 snapshot. A later snapshot and re-run of SZZ are required to relabel this fixed cohort.",
            "legacy_age_and_fix_recalculation": "The input CSV has aggregate metrics only; per-file ages and full commit messages needed for the 2013 sum/keyword rules are not in the attached inputs.",
            "identity_aliasing_sexp": "The replication CSVs omit developer identifiers, and no vetted email-alias map is supplied. Re-extract SEXP after applying a reviewed identity map.",
        },
        "interpretation_warning": "These are sensitivity/descriptive analyses. A shift toward a target value does not by itself prove causation or validate the original theory.",
    }
    with (args.output_dir / "followup_report.json").open("w", encoding="utf-8") as target:
        json.dump(report, target, indent=2)

    markdown = build_markdown_report(report_summaries, report["not_testable_from_attached_data"])
    markdown_path = args.output_dir / "followup_report.md"
    markdown_path.write_text(markdown, encoding="utf-8")
    print(markdown)
    print(f"Machine-readable results: {args.output_dir / 'followup_report.json'}")
    print(f"Daily and churn CSVs: {args.output_dir}")


if __name__ == "__main__":
    main()
