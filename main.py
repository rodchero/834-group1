#!/usr/bin/env python3

import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable

STEP_EXTRACT = ("scripts/firefoxExtract.py", ["commits_raw.jsonl"])
STEP_FILTER = ("scripts/filterCommits.py", ["commits_filtered.jsonl"])

STEP_BUGZILLA = ("scripts/getBugzillaList.py", ["bugzilla_matched.jsonl", "bugzilla_missing_ids.txt"])
STEP_FEATURES = ("scripts/extract_features.py", ["commits_features.csv"])

STEP_SZZ = ("scripts/run_szz.py", ["final_dataset.csv"])


def all_exist(files):
    return all((ROOT / f).exists() for f in files)


def run(script):
    path = ROOT / script
    print(f"\n=== Running {script} ===", flush=True)

    result = subprocess.run(
        [PYTHON, "-u", str(path)],   # -u = unbuffered python output
        cwd=ROOT
    )

    print(f"--- {script} Return code: {result.returncode} ---", flush=True)

    if result.returncode != 0:
        raise SystemExit(result.returncode)


def stream_pipe(pipe, prefix, target_stream):
    try:
        for line in iter(pipe.readline, ''):
            target_stream.write(f"[{prefix}] {line}")
            target_stream.flush()
    finally:
        pipe.close()


def spawn(script):
    path = ROOT / script
    print(f"\n=== Starting {script} in parallel ===", flush=True)

    proc = subprocess.Popen(
        [PYTHON, "-u", str(path)],   # unbuffered child output
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1  # line-buffered
    )

    t_out = threading.Thread(
        target=stream_pipe,
        args=(proc.stdout, Path(script).name, sys.stdout),
        daemon=True
    )
    t_err = threading.Thread(
        target=stream_pipe,
        args=(proc.stderr, Path(script).name + " STDERR", sys.stderr),
        daemon=True
    )

    t_out.start()
    t_err.start()

    return proc, t_out, t_err


def wait_process(name, proc, t_out, t_err):
    rc = proc.wait()
    t_out.join()
    t_err.join()

    print(f"--- {name} Return code: {rc} ---", flush=True)

    if rc != 0:
        raise SystemExit(rc)


def main():
    # Step 1: extract all commits
    script, outputs = STEP_EXTRACT
    if all_exist(outputs):
        print(f"Skipping {script}, outputs exist", flush=True)
    else:
        run(script)

    # Step 2: filter target dataset
    script, outputs = STEP_FILTER
    if all_exist(outputs):
        print(f"Skipping {script}, outputs exist", flush=True)
    else:
        run(script)

    # Step 3 + 4 in parallel
    bugzilla_script, bugzilla_outputs = STEP_BUGZILLA
    features_script, features_outputs = STEP_FEATURES

    jobs = []

    if all_exist(bugzilla_outputs):
        print(f"Skipping {bugzilla_script}, outputs exist", flush=True)
    else:
        proc, t_out, t_err = spawn(bugzilla_script)
        jobs.append((bugzilla_script, proc, t_out, t_err))

    if all_exist(features_outputs):
        print(f"Skipping {features_script}, outputs exist", flush=True)
    else:
        proc, t_out, t_err = spawn(features_script)
        jobs.append((features_script, proc, t_out, t_err))

    for name, proc, t_out, t_err in jobs:
        wait_process(name, proc, t_out, t_err)

    # Step 5: run SZZ only when both prerequisites exist
    if not all_exist(bugzilla_outputs):
        raise RuntimeError("Bugzilla artifacts missing; cannot run SZZ")
    if not all_exist(features_outputs):
        raise RuntimeError("Feature artifacts missing; cannot run SZZ")

    script, outputs = STEP_SZZ
    if all_exist(outputs):
        print(f"Skipping {script}, outputs exist", flush=True)
    else:
        run(script)

    print("\nPipeline complete.", flush=True)


if __name__ == "__main__":
    main()