"""Create chart files and a plain-language guide for the five follow-up hypotheses.

Run after `python -m scripts.followup_experiments`:
    python -m scripts.followup_charts

Outputs are written to output/followup/charts/ with an explanatory Markdown
file at output/followup/chart_interpretation.md.
"""

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

from config import INPUT_DIR, OUTPUT_DIR

FOLLOWUP_DIR = OUTPUT_DIR / "followup"
CHART_DIR = FOLLOWUP_DIR / "charts"
COLORS = {
    "human": "#167D8D",
    "ai": "#D97941",
    "paper": "#596579",
    "light": "#DCE7E8",
    "accent": "#C64D5B",
    "ink": "#202B32",
    "muted": "#61717A",
}


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as source:
        return list(csv.DictReader(source))


def number(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if np.isfinite(result) else None


def style_axis(axis):
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.spines["left"].set_color("#B7C3C5")
    axis.spines["bottom"].set_color("#B7C3C5")
    axis.tick_params(colors=COLORS["muted"], labelsize=9)
    axis.grid(axis="y", color="#E7ECEC", linewidth=0.8)
    axis.set_axisbelow(True)


def save_chart(figure, name):
    figure.savefig(CHART_DIR / name, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(figure)


def chart_daily_volume(daily_rows):
    figure, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=False)
    for axis, dataset, title, color in (
        (axes[0], "ff_human", "Human, AI-unexposed commits", COLORS["human"]),
        (axes[1], "ff_ai", "AI-exposed commits", COLORS["ai"]),
    ):
        records = [row for row in daily_rows if row["dataset"] == dataset]
        dates = [row["date"] for row in records]
        counts = np.array([int(row["commit_count"]) for row in records])
        x = np.arange(len(counts))
        rolling = np.convolve(counts, np.ones(7) / 7, mode="valid") if len(counts) >= 7 else counts
        rolling_x = x[6:] if len(counts) >= 7 else x
        axis.plot(x, counts, color=color, linewidth=0.8, alpha=0.24, label="Daily count")
        axis.plot(rolling_x, rolling, color=color, linewidth=2.0, label="7-active-day average")
        axis.set_title(title, loc="left", color=COLORS["ink"], fontsize=11, fontweight="bold")
        axis.set_ylabel("Commits/day")
        axis.set_xlim(0, max(0, len(counts) - 1))
        if len(dates) > 1:
            tick_positions = np.linspace(0, len(dates) - 1, 6, dtype=int)
            axis.set_xticks(tick_positions, [dates[i][:7] for i in tick_positions])
        style_axis(axis)
        axis.legend(frameon=False, loc="upper right", fontsize=8, ncol=2)
    figure.suptitle("Daily volume in the available commit cohorts", x=0.08, ha="left",
                    fontsize=16, fontweight="bold", color=COLORS["ink"])
    figure.text(0.08, 0.925,
                "Counts are commits, not predictions or false alarms. Cohorts and date ranges differ.",
                fontsize=9, color=COLORS["muted"])
    figure.tight_layout(rect=(0, 0, 1, 0.91))
    save_chart(figure, "01_daily_commit_volume.png")


def chart_churn(churn_rows):
    populations = [
        ("all_path_churn", "All changed paths"),
        ("non_admin_path_churn_on_same_commits", "Exclude admin-path churn"),
        ("admin_commit_exclusion_churn", "Drop commits touching admin paths"),
    ]
    datasets = {
        (row["dataset"], row["population"]): row
        for row in churn_rows
    }
    x = np.arange(len(populations))
    width = 0.34
    figure, axis = plt.subplots(figsize=(10, 5.6))
    for offset, dataset, label, color in (
        (-width / 2, "ff_human", "Human", COLORS["human"]),
        (width / 2, "ff_ai", "AI-exposed", COLORS["ai"]),
    ):
        values = [
            number(datasets[(dataset, population)]["top_1pct_churn_share"]) * 100
            for population, _ in populations
        ]
        bars = axis.bar(x + offset, values, width, label=label, color=color, zorder=3)
        axis.bar_label(bars, fmt="%.1f%%", padding=4, fontsize=9, color=COLORS["ink"])
    axis.set_xticks(x, [label for _, label in populations])
    axis.set_ylabel("Share of total churn in top 1% of commits")
    axis.set_ylim(0, 82)
    figure.suptitle("Path filtering reduces human churn concentration, but not to 42%",
                    x=0.08, y=0.99, ha="left", fontsize=14, fontweight="bold",
                    color=COLORS["ink"])
    figure.text(0.08, 0.92,
                "Two sensitivities: remove churn from paths vs remove entire mixed commits.",
                color=COLORS["muted"], fontsize=9)
    axis.legend(frameon=False, loc="upper right")
    style_axis(axis)
    figure.tight_layout(rect=(0, 0, 1, 0.87))
    save_chart(figure, "02_churn_path_sensitivity.png")


def chart_effort(effort_rows, summaries):
    by_name = {row["dataset"]: row for row in effort_rows}
    summary_by_name = {row["dataset"]: row for row in summaries}
    names = ["mozilla_original", "ff_human", "ff_ai"]
    labels = ["Paper Mozilla", "Firefox human", "Firefox AI-exposed"]
    series = [
        ("LR", "LRTwenty", COLORS["paper"]),
        ("Effort-aware LR", "EALRTwenty", COLORS["human"]),
    ]
    figure, axis = plt.subplots(figsize=(9, 5.4))
    x = np.arange(len(names))
    width = 0.24
    for i, (label, key, color) in enumerate(series):
        vals = [number(by_name[name][key]) * 100 for name in names]
        bars = axis.bar(x + (i - 0.5) * width, vals, width, label=label, color=color, zorder=3)
        axis.bar_label(bars, fmt="%.1f%%", padding=3, fontsize=8)
    baseline_values = [
        None,
        summary_by_name["ff_human"]["smallest_first_defect_recall_at_20pct_effort"] * 100,
        summary_by_name["ff_ai"]["smallest_first_defect_recall_at_20pct_effort"] * 100,
    ]
    for i, value in enumerate(baseline_values):
        if value is not None:
            axis.scatter(x[i] + width * 0.65, value, marker="D", s=58,
                         color=COLORS["accent"], edgecolor="white", linewidth=0.8,
                         zorder=5, label="Smallest-first baseline" if i == 1 else None)
            axis.annotate(f"{value:.1f}%", (x[i] + width * 0.65, value), xytext=(0, 8),
                          textcoords="offset points", ha="center", fontsize=8,
                          color=COLORS["accent"], fontweight="bold")
    axis.axhline(20, color=COLORS["muted"], linestyle="--", linewidth=1,
                 label="Random-ranking reference (20%)")
    axis.set_xticks(x, labels)
    axis.set_ylabel("Defects found by 20% effort")
    axis.yaxis.set_major_formatter(ticker.PercentFormatter(xmax=100))
    axis.set_ylim(0, 100)
    figure.suptitle("Effort-aware ranking vs the smallest-first baseline",
                    x=0.08, y=0.99, ha="left", fontsize=14, fontweight="bold",
                    color=COLORS["ink"])
    figure.text(0.08, 0.92,
                "Smallest-first points are available only for current Firefox cohorts; filtered model rerun is pending.",
                color=COLORS["muted"], fontsize=9)
    axis.legend(frameon=False, loc="upper left", ncol=2, fontsize=8)
    style_axis(axis)
    figure.tight_layout(rect=(0, 0, 1, 0.87))
    save_chart(figure, "03_effort_ranking_baselines.png")


def chart_defect_and_auc(pred_rows, dataset_rows, original_rows):
    pred = {row["dataset"]: row for row in pred_rows}
    summary = {row["dataset"]: row for row in dataset_rows}
    names = ["mozilla_original", "ff_human", "ff_ai"]
    labels = ["Paper Mozilla", "Firefox human", "Firefox AI-exposed"]
    rates = [
        sum(int(float(row["bug"])) for row in original_rows) / len(original_rows) * 100,
        number(summary[names[1]]["defect_rate"]) * 100,
        number(summary[names[2]]["defect_rate"]) * 100,
    ]
    aucs = [number(pred[name]["roc"]) for name in names]
    figure, (left, right) = plt.subplots(1, 2, figsize=(10, 4.8))
    bars = left.bar(labels, rates, color=[COLORS["paper"], COLORS["human"], COLORS["ai"]], zorder=3)
    left.bar_label(bars, fmt="%.1f%%", padding=4, fontsize=9)
    left.set_ylabel("Labeled defective commits")
    left.yaxis.set_major_formatter(ticker.PercentFormatter(xmax=100))
    left.set_ylim(0, max(rates) * 1.35)
    left.set_title("Observed defect rate", loc="left", fontsize=12, fontweight="bold")
    for label in left.get_xticklabels():
        label.set_rotation(15)
        label.set_ha("right")
    auc_bars = right.bar(labels, aucs, color=[COLORS["paper"], COLORS["human"], COLORS["ai"]], zorder=3)
    right.bar_label(auc_bars, fmt="%.3f", padding=4, fontsize=9)
    right.axhline(0.5, linestyle="--", color=COLORS["muted"], linewidth=1, label="Chance reference")
    right.set_ylabel("AUC")
    right.set_ylim(0.45, max(aucs) * 1.2)
    right.set_title("Commit-level model discrimination", loc="left", fontsize=12, fontweight="bold")
    right.legend(frameon=False, fontsize=8)
    for axis in (left, right):
        style_axis(axis)
    figure.suptitle("AI defect-rate gap is observed; time-at-risk is not controlled",
                    x=0.07, ha="left", fontsize=14, fontweight="bold", color=COLORS["ink"])
    figure.text(0.07, 0.91,
                "AI cohort is newer and smaller; the chart does not isolate right-censoring or AI effects.",
                fontsize=9, color=COLORS["muted"])
    figure.tight_layout(rect=(0, 0, 1, 0.86))
    save_chart(figure, "04_defect_rate_and_auc.png")


def chart_age_fix(factor_rows):
    rows = {row["dataset"]: row for row in factor_rows}
    datasets = ["mozilla_original", "ff_human", "ff_ai_core"]
    labels = ["Paper Mozilla", "Firefox human", "Firefox AI Core"]
    metrics = [("FIX", "fix", COLORS["human"]), ("AGE", "pd", COLORS["ai"])]
    figure, axis = plt.subplots(figsize=(9, 5.2))
    x = np.arange(len(datasets))
    offsets = [-0.12, 0.12]
    for offset, (label, column, color) in zip(offsets, metrics):
        values = [number(rows[name].get(column)) for name in datasets]
        for index, value in enumerate(values):
            if value is not None:
                axis.scatter(index + offset, value, s=80, color=color, edgecolor="white",
                             linewidth=0.9, zorder=4, label=label if index == 0 else None)
                axis.annotate(f"{value:.2f}", (index + offset, value), xytext=(0, 8),
                              textcoords="offset points", ha="center", fontsize=8, color=color)
            else:
                axis.text(index + offset, 1.03, "not selected", rotation=90,
                          ha="center", va="bottom", fontsize=7, color=COLORS["muted"])
    axis.axhline(1, color=COLORS["ink"], linestyle="--", linewidth=1.1,
                 label="Odds ratio = 1 (no direction)")
    axis.set_xticks(x, labels)
    axis.set_ylabel("Selected-model odds ratio (log scale)")
    axis.set_yscale("log")
    axis.set_ylim(0.08, 4)
    figure.suptitle("Current AGE/FIX coefficients vary by fitted model",
                    x=0.08, y=0.99, ha="left", fontsize=14, fontweight="bold",
                    color=COLORS["ink"])
    figure.text(0.08, 0.92,
                "Not a legacy-method comparison: 2013-style metrics were not recomputed on this cohort.",
                color=COLORS["muted"], fontsize=9)
    axis.legend(frameon=False, loc="upper left", ncol=3, fontsize=8)
    style_axis(axis)
    figure.tight_layout(rect=(0, 0, 1, 0.87))
    save_chart(figure, "05_age_fix_odds_ratios.png")


def chart_sexp(factor_rows):
    rows = {row["dataset"]: row for row in factor_rows}
    datasets = ["ff_human", "ff_human_firefox", "ff_human_firefox_for_android", "ff_ai"]
    labels = ["Human overall", "Human Firefox", "Human Android", "AI-exposed overall"]
    values = [number(rows[name].get("sexp")) for name in datasets]
    figure, axis = plt.subplots(figsize=(9, 4.8))
    for index, value in enumerate(values):
        if value is None:
            axis.text(index, 1.62, "not selected", ha="center", va="center",
                      fontsize=8, color=COLORS["muted"])
        else:
            color = COLORS["human"] if index < 3 else COLORS["ai"]
            axis.scatter(index, value, s=100, color=color, edgecolor="white", linewidth=1,
                         zorder=4)
            axis.annotate(f"{value:.2f}", (index, value), xytext=(0, 9),
                          textcoords="offset points", ha="center", fontsize=9, color=color)
    axis.axhline(1, color=COLORS["ink"], linestyle="--", linewidth=1.1,
                 label="Odds ratio = 1")
    axis.set_xticks(np.arange(len(labels)), labels)
    axis.set_ylabel("SEXP odds ratio (log scale)")
    axis.set_yscale("log")
    axis.set_ylim(0.8, 1.8)
    figure.suptitle("Current SEXP estimates are weakly risk-increasing where selected",
                    x=0.08, y=0.99, ha="left", fontsize=13, fontweight="bold",
                    color=COLORS["ink"])
    figure.text(0.08, 0.92,
                "No alias-merged estimate exists; an unselected coefficient is not evidence of no effect.",
                color=COLORS["muted"], fontsize=9)
    axis.legend(frameon=False, loc="upper left")
    style_axis(axis)
    figure.tight_layout(rect=(0, 0, 1, 0.87))
    save_chart(figure, "06_sexp_odds_ratios.png")


def write_interpretation(report, output_path):
    human, ai = report["available_data_findings"]
    missing = report["not_testable_from_attached_data"]
    text = f"""# Follow-up Hypotheses: Charts and Interpretation

Generated from the current replication package. The figures are evidence summaries, not causal proof. Open the PNG files in this folder or use the links below.

## 1. Operational velocity and false alarms

![Daily commit volume](charts/01_daily_commit_volume.png)

The plot counts commits by day for the available human and AI-exposed cohorts. It shows that daily activity is not constant, but does **not** count model false alarms. Daily volume is also not comparable to the proposed 30 false alarms/day without model predictions and a PR/MR mapping. Current gap: {missing['pr_level_false_alarm_rate']}

**Meaning:** the chart is context for evaluation volume only. It neither validates nor rejects the claim that Git micro-commits cause excess false alarms. Required next evidence is per-commit predictions plus PR/MR membership, followed by the exact same prediction labels aggregated to PR level.

## 2. Churn concentration and administrative work

![Churn sensitivity](charts/02_churn_path_sensitivity.png)

For human commits, the top 1% accounts for {human['all_path_churn']['top_1pct_churn_share']:.1%} of churn. Removing admin-path churn from those same commits gives {human['non_admin_path_churn_on_same_commits']['top_1pct_churn_share']:.1%}; dropping all commits that touch an admin path gives {human['admin_commit_exclusion_churn']['top_1pct_churn_share']:.1%}. The latter removes {human['admin_path_touch_commits']:,} commits, so it is a broad sensitivity check. AI-exposed top-1% churn is {ai['all_path_churn']['top_1pct_churn_share']:.1%}.

![Effort baselines](charts/03_effort_ranking_baselines.png)

In the current human cohort, smallest-first finds {human['smallest_first_defect_recall_at_20pct_effort']:.1%} of labeled defects at around 20% effort; the current effort-aware model value is in the chart. The AI-exposed smallest-first figure is {ai['smallest_first_defect_recall_at_20pct_effort']:.1%}. These values show why a model must be compared with a simple size-based baseline. The excluded-path cohort has **not** been refit, so do not infer that complex models regain dominance from this chart. Author data is also missing: {missing['bot_author_exclusion']}

**Meaning:** path filtering reduces concentration somewhat, but not to the stated ~42%; measured path filters also do not identify bot authors. The available evidence supports testing administrative churn as a contributor, not the full proposed explanation.

## 3. AI performance and right-censoring

![Defect rates and AUC](charts/04_defect_rate_and_auc.png)

At the current snapshot, the AI-exposed cohort has {ai['defect_rate']:.1%} labeled defective commits; the human cohort has {human['defect_rate']:.1%}. Existing commit-level AUCs are approximately 0.646 for AI-exposed and 0.683 for human. But these cohorts differ in calendar time, size, composition, and exposure; the current design does not hold time-at-risk constant. {missing['future_right_censoring']}

**Meaning:** the lower current defect rate is compatible with right-censoring, but is not evidence that censoring caused it. The needed test follows exactly the same AI commit hashes to a later snapshot and reruns defect labeling.

## 4. AGE and FIX calculation methods

![AGE and FIX odds ratios](charts/05_age_fix_odds_ratios.png)

These are selected odds ratios from existing fitted models. Values above 1 indicate higher estimated odds with larger metric values; values below 1 indicate lower estimated odds. A missing/not-selected coefficient means the model did not retain that metric, not that its effect is zero. AI Core is a smaller subset, not the full AI cohort. {missing['legacy_age_and_fix_recalculation']}

**Meaning:** the chart compares currently reported fits only. It cannot establish that legacy AGE-as-sum or keyword FIX would reproduce 2013 results. That requires recomputing both metric definitions on the same commits, labels, and folds.

## 5. Identity fragmentation and SEXP

![SEXP odds ratios](charts/06_sexp_odds_ratios.png)

Existing selected SEXP odds ratios are about 1.10 in human overall, 1.28 in desktop Firefox, and 1.32 in Firefox for Android. Those estimates are risk-increasing in the fitted models, but are not alias-corrected. AI overall did not select SEXP. {missing['identity_aliasing_sexp']}

**Meaning:** current data show the anomaly the hypothesis is trying to explain, but cannot attribute it to email fragmentation. Alias merging requires a reviewed identity map and recomputation of developer experience before fitting the same model again.

## Chart files

1. `charts/01_daily_commit_volume.png`
2. `charts/02_churn_path_sensitivity.png`
3. `charts/03_effort_ranking_baselines.png`
4. `charts/04_defect_rate_and_auc.png`
5. `charts/05_age_fix_odds_ratios.png`
6. `charts/06_sexp_odds_ratios.png`

For the underlying numbers, see `followup_report.json`, `daily_volume.csv`, and `churn_concentration.csv` in the parent folder.
"""
    output_path.write_text(text, encoding="utf-8")


def main():
    required = [
        FOLLOWUP_DIR / "daily_volume.csv",
        FOLLOWUP_DIR / "churn_concentration.csv",
        FOLLOWUP_DIR / "followup_report.json",
        OUTPUT_DIR / "results_pred.csv",
        OUTPUT_DIR / "results_pred_effort.csv",
        OUTPUT_DIR / "results_factor.csv",
        INPUT_DIR / "mozilla_original.csv",
    ]
    missing = [path for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing chart inputs. Run `python -m scripts.followup_experiments` first. "
            + ", ".join(str(path) for path in missing)
        )

    CHART_DIR.mkdir(parents=True, exist_ok=True)
    daily = read_csv(required[0])
    churn = read_csv(required[1])
    with required[2].open(encoding="utf-8") as source:
        report = json.load(source)
    pred = read_csv(required[3])
    effort = read_csv(required[4])
    factors = read_csv(required[5])
    original_rows = read_csv(required[6])
    dataset_summary = report["available_data_findings"]

    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "axes.titlecolor": COLORS["ink"],
        "axes.labelcolor": COLORS["muted"],
        "figure.facecolor": "white",
        "savefig.facecolor": "white",
    })
    chart_daily_volume(daily)
    chart_churn(churn)
    chart_effort(effort, dataset_summary)
    chart_defect_and_auc(pred, dataset_summary, original_rows)
    chart_age_fix(factors)
    chart_sexp(factors)
    interpretation_path = FOLLOWUP_DIR / "chart_interpretation.md"
    write_interpretation(report, interpretation_path)
    print(f"Wrote six charts to {CHART_DIR}")
    print(f"Wrote explanations to {interpretation_path}")


if __name__ == "__main__":
    main()