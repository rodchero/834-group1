# 834-group1

Replication of Kamei et al., "A Large-Scale Empirical Study of Just-in-Time Quality Assurance" (TSE 2013), RQ1–RQ3, on recent Mozilla Firefox data: one year of human-written commits before November 2025, and AI-generated/assisted commits from November 2025 on.

## Repository layout

| Path | Contents |
|---|---|
| `main.py` | Runs the dataset pipeline end to end |
| `config.py` | Shared paths, study windows, worker counts, Bugzilla settings |
| `scripts/` | Pipeline stages (see below) |
| `scripts/AIDetectionScripts/` | AI-disclosure detection, manual labelling sheets and helpers |
| `artifacts/` | Pipeline outputs. Gitignored except `commits_numstat.jsonl` (git lfs) |
| `ReplicationPackageScript/` | R scripts from the paper's replication package (RQ1–RQ3 models) |
| `firefox/` | Local clone of the Firefox repo (not tracked, see Setup) |

## Setup

1. Clone the Firefox repo into the project root (next to this README). This takes a while, about 6 GB:
   ```
   git clone --no-checkout https://github.com/mozilla-firefox/firefox
   ```

2. Install git lfs to fetch the numstat cache:
   - install git lfs on the computer (apt/brew or tarball)
   - run `git lfs install` in this repo
   - if `artifacts/commits_numstat.jsonl` is still just a pointer, run `git lfs pull`

3. Create a virtual environment and install the dependencies (Python 3.10+):
   ```
   python3 -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
   Keep the venv activated when running the pipeline. `main.py` launches each stage with the same interpreter it was started with, so every stage runs inside the venv.

   If you add a third-party dependency, install it into the venv and regenerate the pinned list with `pip freeze > requirements.txt`.

## Running the pipeline

```
python main.py
```

Stages run in order. A stage is skipped when all of its outputs already exist in `artifacts/`, so delete an artifact to regenerate it and everything that depends on it. The numstat cache and label merge stages always run (they are incremental or cheap). Each stage's runtime is printed, with a summary at the end. The Bugzilla stage takes a while, because requests are throttled on purpose.

| # | Stage | Output (`artifacts/`) | What it does |
|---|---|---|---|
| 1 | `scripts/firefoxExtract.py` | `commits_raw.jsonl` | All non-merge commits from the clone |
| 2 | `scripts/cache_numstat.py` | `commits_numstat.jsonl` | Per-file added/deleted lines per commit (tracked in git lfs). Incremental: only appends commits missing from the cache |
| 3 | `scripts/filterCommits.py` | `commits_filtered.jsonl`, `commits_fix_candidates.jsonl` | Keeps commits inside a study window, tags each with `window` (`human`/`ai`), removes WPT imports, backouts, vendored code and commits without a bug ID. Also writes SZZ fix candidates: the same filters from the earliest window start with no end date, so fixes landing after a window are still traced |
| 4 | `scripts/getBugzillaList.py` | `bugzilla_matched.jsonl`, `bugzilla_missing_ids.txt` | Fetches every Bugzilla bug referenced by the filtered commits and fix candidates |
| 5 | `scripts/AIDetectionScripts/CommitsAIDetect.py` | `ai_candidates.csv` | Flags agent-signed and self-admitted AI commits for labelling (Phabricator reviewer groups such as `r=ai-models-reviewers` are ignored) |
| 6 | `scripts/AIDetectionScripts/merge_labels.py` | `ai_labels.csv`, `labelling_todo.csv`, `label_disagreements.csv` | Merges the raters' sheets by commit hash, prints Cohen's κ, lists rows still needing labels and unresolved disagreements |
| 7 | `scripts/extract_features.py` | `commits_features.csv` | Kamei change metrics for every filtered commit (column names follow the replication package). File history follows renames |
| 8 | `scripts/run_szz.py` | `final_dataset.csv`, `szz_report.json` | SZZ labelling of defect-inducing commits; the report counts every exclusion |

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

Still to come: tagging AI exposure per developer (`tag_exposure.py`), and building the final per-dataset CSVs in the replication package's input format.

## Replication package

The R scripts in `ReplicationPackageScript/` need R and the `MASS` package (`install.packages("MASS")`). See `ReplicationPackageScript/ReadMe.txt` for how to run them.

# TODO
- finish AI labelling
- choose products/components for the 10 sub-datasets
- make a "build_datasets.py" script
- automate replication package runner (could also be a python script)


