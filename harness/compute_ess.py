#!/usr/bin/env python
"""Compute rank-normalized ESS/R-hat (R posterior pkg) for every completed config.

Walks runs/<variant>/<model>/rep<r>/ dirs with DONE marker, runs harness/ess.R,
caches to results/ess/<variant>__<model>__rep<r>.json. Parallelism: 2 (R jobs
each use a couple threads; keep total cores <=4).
"""
import json, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / 'runs'; ESS = ROOT / 'results/ess'
ESS.mkdir(parents=True, exist_ok=True)

jobs = []
for variant_dir in sorted(RUNS.iterdir()):
    if not variant_dir.is_dir():
        continue
    for model_dir in sorted(variant_dir.iterdir()):
        for rep_dir in sorted(model_dir.iterdir()):
            if not (rep_dir / 'DONE').exists():
                continue
            out = ESS / f'{variant_dir.name}__{model_dir.name}__{rep_dir.name}.json'
            if out.exists():
                continue
            jobs.append((rep_dir, out))
print(f'{len(jobs)} ESS jobs', flush=True)

def run(job):
    d, out = job
    r = subprocess.run(['Rscript', str(ROOT/'harness/ess.R'), str(d), str(out)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return f'FAIL {d}: {r.stderr[-300:]}'
    return r.stdout.strip()

with ThreadPoolExecutor(max_workers=2) as ex:
    for msg in ex.map(run, jobs):
        print(msg, flush=True)
print('ESS DONE', flush=True)
