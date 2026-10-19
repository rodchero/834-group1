# Experiment analysis: JIT defect prediction on Firefox (human vs AI)

Summary of the final run (pipeline at `REPO_REF` 098e537c, Firefox snapshot 2026-10-08; R replication package via `scripts/run_experiments.py`). Sources: `output/results_*.csv`, `output/logs/`, `artifacts/datasets_summary.csv`, `artifacts/filter_report.json`, `artifacts/szz_report.json`, `artifacts/run_log.txt`. Written by Claude to support the report; numbers should be cross-checked against those files before quoting.

## 1. Data

### Commit filtering (`filter_report.json`)
| | Human (2024-11-01 – 2025-11-01) | AI window (2025-11-01 – 2026-10-01) |
|---|---|---|
| Non-merge commits in window | 53,282 | 64,901 |
| WPT imports removed | 6,897 | 7,893 |
| Backouts / reverts removed | 3,468 | 4,573 |
| Third-party (by message) removed | 2,402 | 3,455 |
| Vendored-only (third_party/, vendor/) removed | 460 | 389 |
| No bug ID in subject removed | 1,964 | 1,929 |
| **Kept** | **38,091** | **46,662** |

SZZ fix candidates: 85,935 commits from 2024-11-01 up to the snapshot (no end date, so bugs introduced in a window but fixed later are still traced).

### SZZ (`szz_report.json`)
- Of 85,935 fix candidates: 54,544 linked to non-defect bugs (task/enhancement), 1,277 to bugs missing from Bugzilla (807 distinct missing IDs, mostly restricted security bugs), 139 to meta bugs, 27 not fix-like → **29,948 validated fix commits**.
- Tracing: 20,039 traced to ≥1 inducing commit; 5,468 had no deleted lines (pure additions, untraceable); 4,423 found no inducing commit; 18 deleted only vendored lines.
- Blamed commits: 47,721 unique inducing commits; **8,814 rejected** because they were committed after the bug report was created (the assignment's report-date rule); 9 with unknown dates.

### AI labelling and tiers
- 993 self-admitted candidates, each labelled by one human (T: 600, E: 393) and by an LLM labeller (Jev); 8 disagreements resolved by a third person. Agreement (Cohen's κ, all FP labels collapsed / AI_DISCLOSED vs rest): Jev–T 0.915 / 0.934 (n=591), Jev–E 0.799 / 1.000 (n=391). No human–human overlap.
- Seeds: 28 agent-authored (tier A), 46 confirmed disclosures incl. borderline (tier B); 25 developers with an adoption point.
- Tiers per window: human 12 A / 6 B / 178 C / 37,895 none; AI 16 A / 40 B / 3,015 C / 43,591 none.
- Tier C is concentrated: 20 developers; the largest contributes 20% of tier C commits, the top two 38%.

### Final datasets (`datasets_summary.csv`)
| Dataset | Commits | Defective | Rate |
|---|---|---|---|
| mozilla_original (paper) | 98,275 | 5,149 | 5.2% |
| **ff_human** | 37,895 | 7,638 | 20.2% |
| ff_human_core | 18,672 | 3,499 | 18.7% |
| ff_human_firefox | 5,569 | 1,484 | 26.6% |
| ff_human_firefox_for_android | 4,058 | 951 | 23.4% |
| ff_human_toolkit | 2,652 | 449 | 16.9% |
| ff_human_devtools | 1,350 | 212 | 15.7% |
| **ff_ai** | 3,071 | 234 | 7.6% |
| ff_ai_core | 1,707 | 111 | 6.5% |
| ff_ai_firefox_build_system | 518 | 35 | 6.8% |
| ff_ai_firefox | 256 | 35 | 13.7% |
| ff_ai_release_engineering | 147 | 14 | 9.5% |
| ff_ai_toolkit | 109 | 17 | 15.6% |

The top-5 products differ between datasets (assignment: "most commits in each dataset"): AI work concentrates in build/release infrastructure.

## 2. Reproduction of the original Mozilla results
`mozilla_original` reproduces the paper's Mozilla rows almost exactly, so the R pipeline and the package are used correctly:

| | Acc | Prec | Recall | F1 | AUC | LR@20% | LR Popt | EALR@20% | EALR Popt |
|---|---|---|---|---|---|---|---|---|---|
| Paper (Tables 4–5) | .77 | .13 | .63 | .22 | .77 | .06 | .38 | .15 | .45 |
| Our run | .764 | .134 | .639 | .221 | .774 | .061 | .382 | .144 | .453 |

RQ3 odds ratios also match Table 6 within sampling noise (NF 3.92 vs 4.29, FIX 2.11 vs 2.07, AGE 0.86 vs 0.85, NUC/NF 2.68 vs 3.20, EXP 0.88 vs 0.92).

## 3. RQ1 – prediction performance and comparison with the original study

RQ1 asks whether the change metrics in the JIT prediction model still distinguish defect-inducing changes when applied to modern Firefox commits, and whether performance differs between the modern human and AI-exposed cohorts. The original Mozilla dataset is included as a replication control. It contains 98,275 commits, of which 5,149 (5.2%) are labelled defective. The modern human cohort contains 37,895 commits, with 7,638 defective (20.2%); the AI-exposed cohort contains 3,071 commits, with 234 defective (7.6%). These base-rate differences matter: precision is affected by how common defects are, so it should not be interpreted as a measure of discrimination by itself.

### Reproduction control

The original Mozilla results are reproduced closely. The paper reports approximately 0.77 accuracy, 0.13 precision, 0.63 recall, 0.22 F1, and 0.77 AUC for its Mozilla dataset. This run reports 0.764, 0.134, 0.639, 0.221, and 0.774. This agreement is evidence that the replication package and the configured experiment can recover the original Mozilla result; it does not establish that any difference between Mozilla and modern Firefox is caused by a particular tooling change.

### Results

| Dataset | Commits | Defective | Defect rate | Accuracy | Precision | Recall | F1 | AUC |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Paper Mozilla (reported, approximate) | 98,275 | 5,149 | 5.2% | .77 | .13 | .63 | .22 | .77 |
| Mozilla original (this run) | 98,275 | 5,149 | 5.2% | .764 | .134 | .639 | .221 | .774 |
| Firefox human, all products | 37,895 | 7,638 | 20.2% | .642 | .308 | .627 | .413 | .683 |
| Firefox human, Core | 18,672 | 3,499 | 18.7% | .639 | .284 | .605 | .386 | .671 |
| Firefox human, DevTools | 1,350 | 212 | 15.7% | .664 | .266 | .656 | .376 | .703 |
| Firefox human, Firefox desktop | 5,569 | 1,484 | 26.6% | .607 | .362 | .623 | .458 | .658 |
| Firefox human, Firefox for Android | 4,058 | 951 | 23.4% | .651 | .367 | .678 | .475 | .714 |
| Firefox human, Toolkit | 2,652 | 449 | 16.9% | .623 | .247 | .601 | .349 | .651 |
| Firefox AI-exposed, all products | 3,071 | 234 | 7.6% | .623 | .113 | .577 | .188 | .646 |
| Firefox AI-exposed, Core | 1,707 | 111 | 6.5% | .626 | .089 | .523 | .151 | .626 |
| Firefox AI-exposed, Firefox desktop | 256 | 35 | 13.7% | .688 | .247 | .658 | .352 | .679 |
| Firefox AI-exposed, Firefox Build System* | 518 | 35 | 6.8% | .735 | .462 | .317 | not stable | .556 |
| Firefox AI-exposed, Release Engineering* | 147 | 14 | 9.5% | .466 | .124 | .625 | not stable | .542 |
| Firefox AI-exposed, Toolkit* | 109 | 17 | 15.6% | .523 | .193 | .550 | not stable | .532 |

The three starred AI product datasets have only 14–35 defective commits. Their metrics are unstable and should not be used to make product-level claims. F1 is NaN in the saved results because the package averages fold-level F1 values and some folds have undefined/zero precision-recall combinations; an F1 calculated from the averaged precision and recall would be a different summary and is not substituted here.

### Interpretation and relation to the hypothesis

The modern human model retains substantial discrimination: its AUC is .683 versus .774 on the original Mozilla data, while recall is .627 versus .639. Thus the model continues to identify a similar fraction of labelled defective commits at the chosen threshold, but ranks defective commits less well overall by AUC. Human Firefox precision is higher (.308 versus .134), but its defect rate is also much higher (20.2% versus 5.2%). This precision difference is therefore not evidence that the modern model is intrinsically more accurate; it is consistent with a larger positive class.

For the AI-exposed cohort, the all-products model has lower AUC (.646) and recall (.577) than the modern human model (.683 and .627). Precision is .113, compared with .308 for human Firefox. The AI cohort is also much smaller and has a lower observed defect rate. In addition, it covers a later period and has less time for defects to be discovered and linked by SZZ before the 2026-10-08 snapshot. These factors are confounded in the current comparison; the results do not isolate an effect of AI assistance.

The operational-velocity explanation is not tested by these RQ1 metrics. The daily-volume analysis reports 105.6 human commits per active day on average (median 123, p95 204, maximum 251) and 12.2 AI-exposed commits per active day (median 9, p95 34, maximum 94). These are cohort commit counts, not model false alarms. The replication files contain neither saved per-commit false-positive predictions nor PR/MR identifiers, and they do not provide comparable original-study daily false-alarm counts normalized for team size. Therefore, the claims of 30 versus 2 false alarms per day, and the hypothesis that PR-level aggregation would remove excess noise, cannot be evaluated from this package.

**RQ1 conclusion.** The original Mozilla result is reproduced, and modern human Firefox retains comparable recall but lower AUC. AI-exposed Firefox has weaker aggregate prediction metrics than modern human Firefox, but cohort size, base rate, time-at-risk, product mix, and AI exposure differ. These results motivate a PR-level and fixed-time-at-risk follow-up; they do not establish that modern delivery velocity caused false alarms or that the original prediction theory has failed.

## 4. RQ2 – effort-aware prediction and comparison with the original study

RQ2 evaluates how many labelled defects are found when inspection is limited to a fixed fraction of change effort. In this replication, effort is derived from estimated changed lines using the `la`, `ld`, `lt`, and `nf` metrics. The reported `@20%` value is the fraction of all labelled defects encountered by the point at which the ranked inspection order has consumed approximately 20% of total estimated effort. It is not a false-alarm rate, a daily count, or a claim that 20% of commits were inspected. `Popt` summarizes the effort-aware curve relative to optimal and worst orderings; larger values indicate a better ordering under the package's definition.

The table distinguishes ordinary logistic-regression ranking (`LR`) from the effort-aware linear-regression method (`EALR`). They are not interchangeable: a statement about “the model” must identify which ranking it refers to.

### Results

| Dataset | Commits | Defective | LR defects found at 20% effort | LR Popt | EALR defects found at 20% effort | EALR Popt |
|---|---:|---:|---:|---:|---:|---:|
| Paper Mozilla (reported, approximate) | 98,275 | 5,149 | 6% | .38 | 15% | .45 |
| Mozilla original (this run) | 98,275 | 5,149 | 6.1% | .382 | 14.4% | .453 |
| Firefox human, all products | 37,895 | 7,638 | 0.7% | .170 | 70.2% | .860 |
| Firefox human, Core | 18,672 | 3,499 | 1.2% | .144 | 73.8% | .872 |
| Firefox human, DevTools | 1,350 | 212 | 11.5% | .316 | 48.7% | .714 |
| Firefox human, Firefox desktop | 5,569 | 1,484 | 4.3% | .285 | 52.6% | .779 |
| Firefox human, Firefox for Android | 4,058 | 951 | 5.4% | .326 | 42.5% | .717 |
| Firefox human, Toolkit | 2,652 | 449 | 1.0% | .166 | 66.5% | .819 |
| Firefox AI-exposed, all products | 3,071 | 234 | 4.3% | .280 | 51.2% | .731 |
| Firefox AI-exposed, Core | 1,707 | 111 | 16.6% | .331 | 54.6% | .768 |
| Firefox AI-exposed, Firefox desktop | 256 | 35 | 5.8% | .513 | 20.8% | .543 |
| Firefox AI-exposed, Firefox Build System* | 518 | 35 | 24.0% | .567 | 22.0% | .538 |
| Firefox AI-exposed, Release Engineering* | 147 | 14 | not estimable | not estimable | not estimable | not estimable |
| Firefox AI-exposed, Toolkit* | 109 | 17 | not estimable | not estimable | not estimable | not estimable |

The Release Engineering and Toolkit AI datasets each exceed the runner's 10-defect skip threshold, but their saved metrics are NaN. They were not skipped by that threshold; the NaN results are undefined in the saved output, and their precise cause should be checked in the per-dataset R logs before assigning an explanation. The Build System and AI desktop Firefox datasets each have only 35 defective commits, so their estimates are highly uncertain and should be treated as exploratory.

### Interpreting model ranking and the smallest-first control

The 2013 Mozilla result shows that effort-aware ranking improves over ordinary LR: at 20% effort the original study reports about 6% of defects for LR and 15% for EALR; this replication obtains 6.1% and 14.4%. Modern Firefox shows the same direction for the all-product datasets: EALR exceeds ordinary LR, reaching 70.2% versus 0.7% on human Firefox and 51.2% versus 4.3% on AI-exposed Firefox. The human product-level EALR values range from 42.5% to 73.8%; AI product results vary widely and most are based on small defective samples.

However, the modern EALR result is not enough to conclude that a complex model is the best review policy. A separate smallest-first ordering based directly on measured commit churn finds approximately 87.0% of human Firefox defects and 80.3% of AI-exposed Firefox defects at around 20% of effort. For human Firefox, smallest-first exceeds the saved EALR result (87.0% versus 70.2%). This means the complex effort-aware model improves greatly over ordinary LR but does not beat the size-only control in this cohort. It is therefore inaccurate to say simply that “the old model flags massive files and catches almost no bugs”: ordinary LR performs poorly at 20% effort, but EALR finds 70.2% of human Firefox defects.

The evidence also indicates concentrated churn: the top 1% of human Firefox commits account for 62.5% of added-plus-deleted lines in the numstat data; the top 1% of AI-exposed commits account for 66.2%. When administrative paths are excluded from churn but the same human commits are retained, top-1% concentration falls to 55.3%. When every human commit touching an identified administrative path is removed, it falls to 51.5%; that stricter sensitivity removes 2,672 commits (7.1% of the human cohort). These checks show that the selected path filters affect concentration, but they do not reproduce the proposed 42% value. Nor do they prove the changes were made by bots: the replication CSVs omit author and committer identities, and mixed commits can contain both administrative and product changes.

For the current Firefox human and AI cohorts, the smallest-first baseline is thus a useful benchmark and performs strongly. The available stored model results do not include a fitted EALR result for the admin-path-filtered dataset, so the hypothesis that bot filtering restores predictive dominance to a complex model remains untested. The paper-era smallest-first baseline is also not included in the current output tables; do not claim a direct controlled 2013-versus-modern comparison for that heuristic unless it is recomputed using the same procedure on `mozilla_original`.

### What the 20% comparison does and does not mean

The 20% budget is a normalized share of estimated code churn, not a fixed number of review hours. A project with more engineers or different review tooling may tolerate more alerts, but those organizational costs are not measured here. The current data also do not identify the false-positive commits in the 20% ranking, so they cannot show whether wasted effort was spent on tiny or massive false positives. The `Popt` and defects-at-20% figures summarize ordering over labelled commits; they do not measure team capacity, review duration, interruption cost, or defect severity.

**RQ2 conclusion.** Effort-aware EALR substantially outperforms ordinary LR in the modern all-product cohorts, but the simple smallest-first control performs better than EALR on the current human cohort. Modern churn is concentrated, and path-based exclusions reduce but do not eliminate that concentration. The evidence supports reporting effort distributions and naive baselines alongside model scores. It does not establish that automated bots are the cause, that large changes have lower defect density, or that PR-level evaluation would solve the issue. To test those claims, retrieve author identities and PR/MR grouping, remove or reweight administrative work at file level, then rerun both model rankings and the same effort-baseline evaluation on the adjusted cohort.

## 5. RQ3 – characteristics of defect-inducing changes (`results_factor*.csv`)
Odds ratios of the logistic models fitted on the whole (undersampled) dataset; blank = removed by correlation/VIF filtering or BIC stepwise selection. pd = AGE, npt = NUC/NF.

| Factor | Mozilla | ff_human | Core | DevTools | Firefox | Android | Toolkit | ff_ai | AI Core | AI Firefox |
|---|---|---|---|---|---|---|---|---|---|---|
| NS | | 0.86 | | | 0.56 | | | | | |
| NF | 3.92 | 2.13 | 1.77 | 1.57 | 1.81 | 2.56 | 1.67 | 1.64 | | 2.87 |
| Entropy | 0.61 | | | | | | | | | |
| LA/LT | 2.64 | 1.24 | | 3.36 | | 1.44 | | | 0.34 | |
| LT/NF | 1.13 | 1.13 | 1.09 | | 1.10 | 1.47 | | | | |
| FIX | 2.11 | 1.44 | 1.44 | | | 1.45 | | | | |
| NDEV | | 0.94 | | 1.47 | | 0.75 | | | | |
| AGE | 0.86 | 0.88 | 0.90 | | 0.88 | 0.91 | | | 1.22 | |
| NUC/NF | 2.68 | 1.95 | | | | | | | 0.12 | |
| EXP | 0.88 | 0.89 | | | 0.81 | 0.71 | | | | |
| SEXP | | 1.10 | | | 1.28 | 1.32 | | | | |

(The three small AI products produced degenerate coefficients — 0, Inf, ~1e205 — typical of complete separation; excluded.)

Observations:
- **The paper's main open-source findings replicate on human Firefox**: NF and FIX are risk-increasing, AGE is risk-decreasing (0.88 vs Mozilla 0.86), EXP is risk-decreasing. NF is the one factor selected in every human and general model, as in the paper.
- **AI models keep far fewer factors** (BIC with ~470 training rows in ff_ai): only NF (1.64) survives in the general AI model. Fewer factors partly reflects sample size, not only different behaviour.
- **AI Core reverses AGE** (1.22, risk-increasing, vs ≤0.91 in every human model) and has LA/LT and NUC/NF below 1. Interesting contrast but based on 111 defective commits; present as tentative.
- EALR coefficients (`results_factor_effort.csv`) follow the paper's pattern: NF and AGE/NUC negative, FIX positive in human models (FIX +0.017, NF −0.008, AGE −0.002).

## 6. Conclusions supported by the data
1. **The replication package reproduces the original Mozilla results.**
2. **JIT prediction transfers to modern human-written Firefox** with similar recall and the same main risk factors (NF, FIX, AGE, EXP); precision is higher because the defect rate is higher.
3. **AI-assisted commits are harder to predict** (lower AUC, precision, F1, EALR) in the general model and in Core; only the two largest AI products give interpretable models.
4. **Effort-aware results on Firefox are driven by extreme churn concentration**; compare EALR against a smallest-first baseline.

## 7. Threats and caveats to discuss
- **Right-censoring**: AI commits (up to 2026-10-01) had at most ~1 year, often weeks, for bugs to be found and fixed before the 2026-10-08 snapshot; human commits had ≥11 months more. This likely explains part of the 7.6% vs 20.2% defect-rate gap and biases AI models.
- **Defect rate vs the paper**: 20% (human) vs 5% (Mozilla). Plausible causes: SZZ traces every deleted/modified line of 29,948 validated fixes up to the snapshot; modern rapid regression fixing; SZZ over-attribution. Within the paper's range across projects (5–36%).
- **AI label uncertainty**: AI exposure (tier C, 98% of the AI dataset) assumes a developer keeps using AI after first disclosure; disclosure is voluntary; tier C is dominated by a few developers (top two 38%); second rater was an LLM, so κ is human-vs-model.
- **Small AI datasets**: 3,071 commits / 234 defective overall; three of five AI products unusable; RQ3 for AI is sample-size-limited (BIC drops most factors). The package's AUC counts folds without defective commits as 0, biasing small datasets down.
- **Metric definitions**: AGE is the average days since last change (paper text); the package's Mozilla data appears to store the sum, so AGE odds ratios are not strictly comparable with mozilla_original. FIX uses Bugzilla type = defect rather than keyword search.
- **SZZ limitations**: 5,468 fixes with no deleted lines untraceable; backed-out commits never labelled; 1,277 fix candidates link only to bugs missing from Bugzilla; 8,814 blamed commits rejected by the report-date rule.
- **Time period and composition**: 2000s CVS Mozilla vs 2024–2026 git Firefox; product mix differs (AI work concentrated in build/release infrastructure).
