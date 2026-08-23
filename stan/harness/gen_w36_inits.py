#!/usr/bin/env python
"""W-36 inits: deterministic normal(0,1) UNCONSTRAINED init files for the
8 grid models not covered by inits_w25 (which keeps hier_2pl + lsat_model
pf inits for W-36).

Method (recorded in WORKLOG W-36): per (model, rep, chain), rng =
random.Random(f'{model}-{seed}-{c}') with seed = 20260819+1000*rep; one
normalvariate(0,1) draw per unconstrained coordinate; dimension from
BridgeStan num_unconstrained_parameters (bs_models .so + data json —
dimension is .so-build-independent). Output: one coordinate per line,
consumable by stan_cli --init-file. Identical files are used by ALL arms.
"""
import random
from pathlib import Path

import bridgestan

ROOT = Path(__file__).resolve().parent.parent
BASE_SEED = 20260819
REPS = 3
CHAINS = 4
MODELS = ['radon_partially_pooled_noncentered', 'bym2_offset_only',
          'diamonds', 'accel_gp', 'kronecker_gp', 'pilots',
          'eight_schools_centered', 'lotka_volterra']


def main():
    out_root = ROOT / 'inits_w36'
    for model in MODELS:
        so = ROOT / 'bs_models' / f'model_{model}.so'
        sm = bridgestan.StanModel(str(so), str(ROOT / f'data/{model}.json'))
        n = sm.param_unc_num()
        print(model, 'n_unc =', n, flush=True)
        for rep in range(REPS):
            seed = BASE_SEED + 1000 * rep
            od = out_root / model / f'rep{rep}'
            od.mkdir(parents=True, exist_ok=True)
            for c in range(CHAINS):
                rng = random.Random(f'{model}-{seed}-{c}')
                vals = [rng.normalvariate(0.0, 1.0) for _ in range(n)]
                (od / f'chain_{c}.txt').write_text(
                    '\n'.join(repr(v) for v in vals) + '\n')
        print(model, 'ok', flush=True)


if __name__ == '__main__':
    main()
