#!/usr/bin/env python
"""W-31 analysis: arviz ESS for runs/w31 arms vs the W-25 base arm.

Same estimator/procedure as harness/analyze_w25.py (rank-normalized
bulk/tail ESS, arviz 1.3). Also md5-compares the mc_default per-chain
CSVs against runs/base (W-25 base arm = single-chain fixed warmup 1000,
same seeds/inits) — bit-identity makes the ESS gate exact.
"""
import hashlib, json, sys
from pathlib import Path

import arviz as az
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / 'runs'
MODELS = ['eight_schools_noncentered', 'hier_2pl']
ARMS = ['mc_default', 'mc_earlyexit']
DROPS = {'lp__', 'accept_stat__', 'stepsize__', 'treedepth__', 'n_leapfrog__',
         'divergent__', 'energy__', 'X'}


def ess_for(rep_dir):
    files = sorted(rep_dir.glob('chain_[0-9]*.csv'))
    if not files:
        return None
    dfs = [pd.read_csv(f, comment='#') for f in files]
    keep = [c for c in dfs[0].columns if c not in DROPS]
    n = min(len(d) for d in dfs)
    eb = [float(az.ess(np.stack([d[k].to_numpy()[:n] for d in dfs], axis=0),
                       method='bulk')) for k in keep]
    et = [float(az.ess(np.stack([d[k].to_numpy()[:n] for d in dfs], axis=0),
                       method='tail', prob=0.05)) for k in keep]
    return dict(ess_bulk_min=min(eb), ess_tail_min=min(et), n_draws=n,
                n_chains=len(files))


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def main():
    reps = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    out = {}
    for model in MODELS:
        for arm in ARMS + ['base']:
            per = []
            for rep in range(reps):
                d = RUNS / arm / model / f'rep{rep}'
                if arm == 'w31':
                    continue
                d = (RUNS / 'w31' / arm / model / f'rep{rep}'
                     if arm in ARMS else d)
                if not (d / 'DONE').exists():
                    continue
                e = ess_for(d)
                if e:
                    per.append(e)
            if per:
                out[f'{arm}/{model}'] = dict(
                    n=len(per),
                    ess_bulk_min_med=float(np.median([p['ess_bulk_min'] for p in per])),
                    ess_tail_min_med=float(np.median([p['ess_tail_min'] for p in per])),
                    per_rep_bulk=[round(p['ess_bulk_min'], 1) for p in per],
                    per_rep_tail=[round(p['ess_tail_min'], 1) for p in per])
    (ROOT / 'results/w31_ess.json').write_text(json.dumps(out, indent=1))

    # md5: mc_default chain CSVs vs the base arm's (same seeds/inits).
    md5_out = {}
    for model in MODELS:
        for rep in range(reps):
            for c in range(4):
                a = RUNS / 'w31/mc_default' / model / f'rep{rep}' / f'chain_{c}.csv'
                b = RUNS / 'base' / model / f'rep{rep}' / f'chain_{c}.csv'
                if a.exists() and b.exists():
                    md5_out[f'{model}/rep{rep}/c{c}'] = dict(
                        eq=md5(a) == md5(b))
    n_eq = sum(v['eq'] for v in md5_out.values())
    (ROOT / 'results/w31_md5.json').write_text(json.dumps(md5_out, indent=1))
    print(json.dumps(out, indent=1))
    print(f'md5 mc_default == base: {n_eq}/{len(md5_out)}')


if __name__ == '__main__':
    main()
