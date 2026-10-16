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

## 3. RQ1 – prediction performance (`results_pred.csv`)
| Dataset | Acc | Prec | Recall | F1 | AUC |
|---|---|---|---|---|---|
| mozilla_original | .764 | .134 | .639 | .221 | .774 |
| ff_human | .642 | .308 | .627 | .413 | .683 |
| ff_human_core | .639 | .284 | .605 | .386 | .671 |
| ff_human_devtools | .664 | .266 | .656 | .376 | .703 |
| ff_human_firefox | .607 | .362 | .623 | .458 | .658 |
| ff_human_firefox_for_android | .651 | .367 | .678 | .475 | .714 |
| ff_human_toolkit | .623 | .247 | .601 | .349 | .651 |
| ff_ai | .623 | .113 | .577 | .188 | .646 |
| ff_ai_core | .626 | .089 | .523 | .151 | .626 |
| ff_ai_firefox | .688 | .247 | .658 | .352 | .679 |
| ff_ai_firefox_build_system* | .735 | .462 | .317 | NaN (≈.37) | .556 |
| ff_ai_release_engineering* | .466 | .124 | .625 | NaN (≈.21) | .542 |
| ff_ai_toolkit* | .523 | .193 | .550 | NaN (≈.29) | .532 |

\* Unreliable (14–35 defective commits). F1 is NaN because some folds had precision = recall = 0 and the package averages per-fold F1; the value in brackets is F1 of the averaged precision and recall.

Observations:
- **Human models perform close to the paper's open-source average** (paper: acc 71%, prec 37%, recall 67%, F1 45%, AUC 76%). Recall is stable at ~0.60–0.68 everywhere, as in the paper. Precision is much higher than Mozilla's (.31 vs .13), consistent with the paper's note that precision tracks the defect rate (20% vs 5%). AUC is somewhat lower than Mozilla (.68 vs .77).
- **AI models predict worse**: general AUC .65 (vs .68 human), precision .11 (expected at a 7.6% defect rate). AI Core is the weakest (AUC .63, F1 .15). AI Firefox (AUC .68) is comparable to the human models but rests on 35 defective commits.
- The three smallest AI product models are near random (AUC .53–.56) and should be reported as attempted but not interpretable.

## 4. RQ2 – effort-aware prediction (`results_pred_effort.csv`)
| Dataset | LR@20% | LR Popt | EALR@20% | EALR Popt |
|---|---|---|---|---|
| mozilla_original | .061 | .382 | .144 | .453 |
| ff_human | .007 | .170 | .702 | .860 |
| ff_human_core | .012 | .144 | .738 | .872 |
| ff_human_devtools | .115 | .316 | .487 | .714 |
| ff_human_firefox | .043 | .285 | .526 | .779 |
| ff_human_firefox_for_android | .054 | .326 | .425 | .717 |
| ff_human_toolkit | .010 | .166 | .665 | .819 |
| ff_ai | .043 | .280 | .512 | .731 |
| ff_ai_core | .166 | .331 | .546 | .768 |
| ff_ai_firefox | .058 | .513 | .208 | .543 |
| ff_ai_firefox_build_system* | .240 | .567 | .220 | .538 |
| ff_ai_release_engineering* | NaN | NaN | NaN | NaN |
| ff_ai_toolkit* | NaN | NaN | NaN | NaN |

Observations:
- **The paper's qualitative RQ2 finding holds**: plain LR ranking is poor at 20% effort (human .007–.115, below the random baseline of .20), and EALR is far better.
- **EALR numbers are much higher than in the paper** (human 70% of defects at 20% effort vs 15% for Mozilla, 35% paper average). This is not a modelling artefact but a property of Firefox change sizes: churn is extremely concentrated (top 1% of commits hold 62% of churn in ff_human, 66% in ff_ai, vs 41% in mozilla_original). A trivial "smallest change first" ordering already reaches 87% of defects at 20% effort in ff_human (80% ff_ai, 60% mozilla_original). The report should present EALR relative to this baseline: EALR does not beat smallest-first on Firefox, so the effort-aware gains mostly come from effort concentration.
- AI vs human: EALR@20% .51 (AI) vs .70 (human), Popt .73 vs .86 — effort-aware ranking is less effective on AI commits.

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
