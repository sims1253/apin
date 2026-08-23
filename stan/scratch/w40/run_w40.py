#!/usr/bin/env python3
"""W-40 gate (d): kronecker_gp sampling sanity, patched vs stock .so.
One fixed binary (walnutpie exp/freeze-clamp stan_cli), 3 reps x 4 chains,
warmup=1000 draws=1000, seeds 20260819+1000*rep+c, inits_w36 deterministic
inits. Outputs runs/w40/<arm>/rep<r>/chain_<c>.csv (+log)."""
import os, subprocess, sys, time
from pathlib import Path
ROOT = Path('/home/m0hawk/Documents/apin/stan')
CLI = ROOT / 'external/walnutpie_w41/build_w41/examples/stan_cli'
SO = {'stock': ROOT / 'bs_models_threads/model_kronecker_gp.so',
      'patched': ROOT / 'scratch/w40/builds/patched_threads/kronecker_gp_model.so'}
DATA = ROOT / 'data/kronecker_gp.json'
OUT = ROOT / 'runs/w40'
WARMUP, DRAWS, CHAINS = 1000, 1000, 4
BASE_SEED = 20260819
arm = sys.argv[1]
env = {**os.environ, 'OMP_NUM_THREADS': '1'}
for rep in range(3):
    for c in range(CHAINS):
        out_dir = OUT / arm / f'rep{rep}'
        out_dir.mkdir(parents=True, exist_ok=True)
        csv = out_dir / f'chain_{c}.csv'
        if csv.exists():
            print(f'[w40] {arm}/rep{rep}/c{c}: cached', flush=True)
            continue
        cmd = [str(CLI), str(SO[arm]), str(DATA), '--seed',
               str(BASE_SEED + 1000 * rep + c),
               '--init-file', str(ROOT / f'inits_w36/kronecker_gp/rep{rep}/chain_{c}.txt'),
               '--output', str(csv), '--warmup', str(WARMUP), '--samples', str(DRAWS)]
        t0 = time.time()
        with (out_dir / f'chain_{c}.log').open('w') as lf:
            p = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, env=env)
        print(f'[w40] {arm}/rep{rep}/c{c}: rc={p.returncode} {time.time()-t0:.1f}s', flush=True)
