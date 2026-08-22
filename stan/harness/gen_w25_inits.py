#!/usr/bin/env python
"""W-25 inits: Pathfinder draws -> per-chain UNCONSTRAINED text init files.

Replicates the /tmp/winit protocol: per (model, rep, chain) pick a pf draw
with rng=random.Random(f'{seed}-{c}') (seed=20260819+1000*rep), unconstrain
via BridgeStan (bs_models .so), write one coordinate per line to
inits_w25/<model>/rep<r>/chain_<c>.txt (consumable by stan_cli --init-file,
with {c} pattern for multi-chain).
"""
import csv, random, sys
from pathlib import Path

import numpy as np
import bridgestan

ROOT = Path(__file__).resolve().parent.parent
BASE_SEED = 20260819
MODELS = ['arma11', 'lsat_model', 'hier_2pl', 'blr', 'eight_schools_noncentered']
REPS = 3
CHAINS = 4
DROP = {'lp_approx__', 'lp__', 'path__'}

def pf_draws(model):
    path = ROOT / f'runs/w25_pf/{model}_pf.csv'
    lines = [l for l in path.read_text().splitlines() if not l.startswith('#')]
    rdr = csv.DictReader(lines)
    return rdr.fieldnames, list(rdr)

def main():
    out_root = ROOT / 'inits_w25'
    for model in MODELS:
        hdr, draws = pf_draws(model)
        so = ROOT / 'bs_models' / f'model_{model}.so'
        sm = bridgestan.StanModel(str(so), str(ROOT / f'data/{model}.json'))
        names = sm.param_names()  # constrained, dot-indexed
        for rep in range(REPS):
            seed = BASE_SEED + 1000 * rep
            for c in range(CHAINS):
                rng = random.Random(f'{seed}-{c}')
                d = draws[rng.randrange(len(draws))]
                # constrained vector in parameter-block order
                missing = [n for n in names if n not in d]
                assert not missing, f'{model}: pf csv missing {missing[:5]}'
                vals = np.array([float(d[n]) for n in names])
                unc = sm.param_unconstrain(vals)
                od = out_root / model / f'rep{rep}'
                od.mkdir(parents=True, exist_ok=True)
                (od / f'chain_{c}.txt').write_text(
                    '\n'.join(repr(float(v)) for v in unc) + '\n')
        print(model, 'ok', flush=True)

if __name__ == '__main__':
    main()
