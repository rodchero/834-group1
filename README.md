# 834-group1

Replication of Kamei et al., "A Large-Scale Empirical Study of Just-in-Time Quality Assurance" (TSE 2013), RQ1–RQ3, on recent Mozilla Firefox data: one year of human-written commits before November 2025, and AI-generated/assisted commits from November 2025 on.

## Repository layout

| Path | Contents |
|---|---|
| `main.py` | Runs the dataset pipeline end to end |
| `config.py` | Shared paths, study windows, worker counts, Bugzilla settings |
| `scripts/` | Pipeline stages (see below) |
| `scripts/AIDetectionScripts/` | AI-disclosure detection, manual labelling sheets and helpers |
| `artifacts/` | Pipeline outputs. Gitignored except `commits_numstat.jsonl` (git lfs) and the small reports used in the write-up (`filter_report.json`, `szz_report.json`, `datasets_summary.csv`, `bugzilla_missing_ids.txt`, `ai_labels.csv`, `run_log.txt`) |
| `ReplicationPackageScript/` | R scripts from the paper's replication package (RQ1–RQ3 models) |
| `input/` | Replication datasets, including the paper's `mozilla_original.csv` (git lfs) |
| `output/` | R results: the combined `results_*.csv` and `logs/` are tracked, the per-dataset intermediate files are not |
| `firefox/` | Local clone of the Firefox repo (not tracked, see Setup) |

## Setup

1. Clone the Firefox repo into the project root (next to this README). This takes a while, about 6 GB:
   ```
   git clone --no-checkout https://github.com/mozilla-firefox/firefox
   ```
   The pipeline reads the pinned snapshot `REPO_REF` in `config.py` (2026-10-08), not the clone's HEAD, so a newer clone gives the same data. Check that the clone contains it:
   ```
   git -C firefox cat-file -e 098e537cc4338b343383540dd7e7907fece986b7 && echo ok
   ```

2. Install git lfs to fetch the numstat cache:
   - install git lfs on the computer (apt/brew or tarball)
   - run `git lfs install` in this repo
   - if `artifacts/commits_numstat.jsonl` is still just a pointer, run `git lfs pull`

3. Create a virtual environment and install the dependencies (Python 3.10+; also needed: git 2.23+ for `blame --ignore-revs-file`, R with `MASS`, Perl, and about 16 GB of RAM for feature extraction):
   ```
   python3 -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
   Keep the venv activated when running the pipeline. `main.py` launches each stage with the same interpreter it was started with, so every stage runs inside the venv.

   If you add a third-party dependency, install it into the venv and regenerate the pinned list with `pip freeze > requirements.txt`.

## Running the pipeline

```
python main.py 2>&1 | tee artifacts/run_log.txt
```

On a remote machine, run it inside `tmux` or `screen` so it survives a dropped SSH connection. The log is tracked, so the counts it prints (κ, AI tiers, stage timings) are kept with the reports.

Stages run in order. A stage is skipped when all of its outputs already exist in `artifacts/`, so delete an artifact to regenerate it and everything that depends on it. The numstat cache, label merge, exposure and dataset build stages always run (they are incremental or cheap). Each stage's runtime is printed, with a summary at the end. The Bugzilla stage takes a while, because requests are throttled on purpose.

| # | Stage | Output (`artifacts/`) | What it does |
|---|---|---|---|
| 1 | `scripts/firefoxExtract.py` | `commits_raw.jsonl` | All non-merge commits up to `REPO_REF` |
| 2 | `scripts/cache_numstat.py` | `commits_numstat.jsonl` | Per-file added/deleted lines per commit (tracked in git lfs). Incremental: only appends commits missing from the cache |
| 3 | `scripts/filterCommits.py` | `commits_filtered.jsonl`, `commits_fix_candidates.jsonl`, `filter_report.json` | Keeps commits inside a study window, tags each with `window` (`human`/`ai`), removes WPT imports, backouts, vendored code (by message, and commits whose files are all under `third_party/` or `vendor/`) and commits without a bug ID; the report counts each filter's removals. Also writes SZZ fix candidates: the same filters from the earliest window start with no end date, so fixes landing after a window are still traced |
| 4 | `scripts/getBugzillaList.py` | `bugzilla_matched.jsonl`, `bugzilla_missing_ids.txt` | Fetches every Bugzilla bug referenced by the filtered commits and fix candidates |
| 5 | `scripts/AIDetectionScripts/CommitsAIDetect.py` | `ai_candidates.csv` | Flags agent-signed and self-admitted AI commits for labelling (Phabricator reviewer groups such as `r=ai-models-reviewers` are ignored) |
| 6 | `scripts/AIDetectionScripts/merge_labels.py` | `ai_labels.csv`, `labelling_todo.csv`, `label_disagreements.csv` | Merges the raters' sheets by commit hash, prints Cohen's κ, lists rows still needing labels and unresolved disagreements |
| 7 | `scripts/AIDetectionScripts/tag_exposure.py` | `ai_tiers.csv` | AI evidence tier per commit: A agent-authored, B confirmed disclosure, C exposed (later commits of a developer with an A/B commit), `-` none |
| 8 | `scripts/extract_features.py` | `commits_features.csv` | Kamei change metrics for every filtered commit (column names follow the replication package: `pd` = AGE, average days since each file's last change; `npt` = NUC, unique last changes, divided by nf). File history follows renames, and commits landed together with one timestamp are processed parents first |
| 9 | `scripts/run_szz.py` | `final_dataset.csv`, `szz_report.json` | SZZ labelling of defect-inducing commits; the report counts every exclusion. Fixes are linked by the bug ID in the subject, blame skips the commits in Firefox's `.git-blame-ignore-revs` (mass reformatting), and vendored lines are not traced |
| 10 | `scripts/build_datasets.py` | `input/<dataset>[_<product>].csv`, `datasets_summary.csv` | Replication package inputs for each dataset in `config.DATASETS` (human: no AI evidence; AI: tiers A+B+C), general and one per product for the `N_PRODUCTS` (5) products with the most commits in that dataset |
| 11 | `scripts/run_experiments.py` | `output/results_{pred,pred_effort,factor,factor_effort}.csv`, `output/logs/` | Runs the R experiments (RQ1–RQ3) once per dataset, `mozilla_original` first; skips datasets with fewer than `MIN_DEFECTIVE` (10) defective commits |

Study windows and other parameters are set in `config.py`. Stage scripts import it as a top-level module, so to run a single stage, run it as a module from the project root:

```
python -m scripts.filterCommits
```

## AI-disclosure labelling (WIP)

The self-admitted candidates from stage 5 are labelled by hand by two raters; see `scripts/AIDetectionScripts/LABELLING_INSTRUCTIONS.md` for the labels and how to submit a sheet. Rater sheets are `scripts/AIDetectionScripts/labelling_sheet_<rater>[_<batch>].csv`, and third-person decisions on disagreements go in `resolved_labels.csv` next to them. Re-run the merge after adding a sheet:

```
python -m scripts.AIDetectionScripts.merge_labels
```

To print the full message of a row, by old row id or by commit hash:

```
python scripts/AIDetectionScripts/show_commit.py R0084 fa9c5cdb882a
```


## Replication package

The R scripts in `ReplicationPackageScript/` need R (`Rscript` on the PATH), the `MASS` package (`install.packages("MASS")`) and Perl. The only change to them: the project list and output name are read from the `JIT_PROJECTS` and `JIT_TARGET` environment variables, defaulting to the paper's original projects. `run_experiments.py` sets them for one dataset at a time; to run a subset:

```
python -m scripts.run_experiments mozilla_original ff_ai
```

Combined results, one row per dataset:

| File | Contents |
|---|---|
| `results_pred.csv` | RQ1: accuracy, precision, recall, F1, AUC (10-fold CV, undersampled) |
| `results_pred_effort.csv` | RQ2: share of defects found at 20% effort and Popt, for LR and EALR |
| `results_factor.csv` | RQ3: logistic regression odds ratios per metric (blank = removed by VIF/stepwise) |
| `results_factor_effort.csv` | RQ3: EALR coefficients per metric |

Each dataset's R console output is in `output/logs/<dataset>.log`.

# TODO
- finish AI labelling


