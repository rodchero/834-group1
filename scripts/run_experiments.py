"""
Run the replication package's R experiments (RQ1-RQ3) on every dataset.

Datasets: input/mozilla_original.csv, then input/<dataset>.csv and every
input/<dataset>_<product>.csv for config.DATASETS (written by build_datasets).
Datasets with fewer than MIN_DEFECTIVE defective commits are skipped.

R is called once per dataset and script (exeExperimentPred.r for RQ1/RQ2,
exeExperimentFactor.r for RQ3), with the dataset passed in JIT_PROJECTS and
JIT_TARGET, so one dataset failing does not stop the others. Each dataset's R
console output goes to output/logs/<dataset>.log, and the per-dataset result
files are combined into output/results_<kind>.csv.

Run a subset by naming datasets: python -m scripts.run_experiments mozilla_original ff_ai
"""

import csv
import os
import subprocess
import sys
import time

from config import (
    R_DIR, INPUT_DIR, OUTPUT_DIR, R_LOG_DIR, R_RESULTS, MOZILLA_ORIGINAL,
    DATASETS, MIN_DEFECTIVE,
)

R_SCRIPTS = ["exeExperimentPred.r", "exeExperimentFactor.r"]


def dataset_names():
    names = [MOZILLA_ORIGINAL]
    for name in DATASETS:
        names += [name] + sorted(p.stem for p in INPUT_DIR.glob(f"{name}_*.csv"))
    return names


def count_defective(path):
    with open(path, newline="", encoding="utf-8") as f:
        return sum(r["bug"] == "1" for r in csv.DictReader(f))


def result_file(name, kind):
    """Per-dataset result file written by the R scripts (factor ones via mergeFactor.pl)."""
    return OUTPUT_DIR / f"all_{name}_{kind}.csv"


def run_r(name):
    env = os.environ | {"JIT_PROJECTS": name, "JIT_TARGET": name}
    with open(R_LOG_DIR / f"{name}.log", "w", encoding="utf-8") as log:
        for script in R_SCRIPTS:
            log.write(f"===== {script} =====\n")
            log.flush()
            result = subprocess.run(["Rscript", "-e", f'source("{script}")'],
                                    cwd=R_DIR, env=env, stdout=log, stderr=subprocess.STDOUT)
            if result.returncode != 0:
                return f"{script} failed (exit {result.returncode})"
    missing = [kind for kind in R_RESULTS if not result_file(name, kind).exists()]
    return f"no result for {', '.join(missing)}" if missing else None


def combine(names):
    for kind, out_path in R_RESULTS.items():
        header, rows = None, []
        for name in names:
            with open(result_file(name, kind), newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = ["dataset"] + next(reader)[1:]
                rows += [row for row in reader if row]
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)
        print(f"Wrote {len(rows)} rows to {out_path}")


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    R_LOG_DIR.mkdir(exist_ok=True)

    names = sys.argv[1:] or dataset_names()
    done, problems = [], []
    for name in names:
        path = INPUT_DIR / f"{name}.csv"
        if not path.exists():
            problems.append((name, "missing input file"))
            print(f"[{name}] missing {path}, skipped", flush=True)
            continue
        n_bug = count_defective(path)
        if n_bug < MIN_DEFECTIVE:
            problems.append((name, f"skipped, {n_bug} defective < {MIN_DEFECTIVE}"))
            print(f"[{name}] only {n_bug} defective commits, skipped", flush=True)
            continue

        # Remove old results so a failed run cannot be mistaken for a finished one
        for kind in R_RESULTS:
            result_file(name, kind).unlink(missing_ok=True)

        print(f"[{name}] running R ({n_bug} defective commits)...", flush=True)
        start = time.perf_counter()
        error = run_r(name)
        elapsed = time.perf_counter() - start
        if error:
            problems.append((name, f"{error}, see {R_LOG_DIR / (name + '.log')}"))
            print(f"[{name}] FAILED after {elapsed:.0f}s: {error}", flush=True)
        else:
            done.append(name)
            print(f"[{name}] done in {elapsed:.0f}s", flush=True)

    if done:
        print()
        combine(done)

    print(f"\n{len(done)} of {len(names)} datasets modelled")
    for name, problem in problems:
        print(f"  {name}: {problem}")
    if any("failed" in p or "no result" in p for _, p in problems):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
