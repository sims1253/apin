#!/usr/bin/env python
"""W-25 analysis: arviz rank-normalized ESS per arm/model/rep, medians over reps.

R `posterior` is unavailable on this machine; arviz implements the same
rank-normalized bulk/tail ESS estimators (Vehtari et al. 2021). Identical
procedure across all arms, so comparisons are internally consistent.
"""
import json, sys
from pathlib import Path

import arviz as az
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / 'runs'
MODELS = ['arma11', 'lsat_model', 'hier_2pl', 'blr', 'eight_schools_noncentered']
ARMS = ['base', 'mc_nogate', 'mc_gate05']
DROPS = {'lp__', 'accept_stat__', 'stepsize__', 'treedepth__', 'n_leapfrog__',
         'divergent__', 'energy__', 'X'}

def ess_for(rep_dir):
    files = sorted(rep_dir.glob('chain_[0-9]*.csv'))
    if not files:
        return None
    dfs = [pd.read_csv(f, comment='#') for f in files]
    keep = [c for c in dfs[0].columns if c not in DROPS]
    n = min(len(d) for d in dfs)
    # per-param (chain, draw) arrays; arviz 1.3 ess/rhat accept them directly
    eb = [float(az.ess(np.stack([d[k].to_numpy()[:n] for d in dfs], axis=0),
                       method='bulk')) for k in keep]
    et = [float(az.ess(np.stack([d[k].to_numpy()[:n] for d in dfs], axis=0),
                       method='tail', prob=0.05)) for k in keep]
    rh = [float(az.rhat(np.stack([d[k].to_numpy()[:n] for d in dfs], axis=0)))
          for k in keep]
    return dict(ess_bulk_min=min(eb),
                ess_tail_min=min(et),
                rhat_max=max(rh),
                n_draws=n, n_chains=len(files))

def main():
    reps = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    out = {}
    for model in MODELS:
        for arm in ARMS:
            per = []
            for rep in range(reps):
                d = RUNS / arm / model / f'rep{rep}'
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
                    rhat_max_med=float(np.median([p['rhat_max'] for p in per])),
                    per_rep_bulk=[round(p['ess_bulk_min'], 1) for p in per],
                    per_rep_tail=[round(p['ess_tail_min'], 1) for p in per])
    (ROOT / 'results').mkdir(exist_ok=True)
    (ROOT / 'results/w25_ess.json').write_text(json.dumps(out, indent=1))
    # wall + exit iters from rows
    walls = {}
    for model in MODELS:
        for arm in ARMS:
            vals, exits = [], []
            for rep in range(reps):
                f = RUNS / arm / model / f'rep{rep}' / 'rows.csv'
                if not f.exists():
                    continue
                rows = list(pd.read_csv(f).to_dict('records'))
                vals.append(float(rows[0]['wall_batch_s']))
                exits.append(int(rows[0]['exit_iter']) if rows[0].get('exit_iter') == rows[0].get('exit_iter') else None)
            if vals:
                walls[f'{arm}/{model}'] = dict(
                    wall_med_s=float(np.median(vals)),
                    exit_iter_med=(float(np.median([e for e in exits if e is not None]))
                                   if any(e is not None for e in exits) else None))
    (ROOT / 'results/w25_wall.json').write_text(json.dumps(walls, indent=1))

    print(f"{'model':28s} {'metric':14s} {'base':>10s} {'mc_nogate':>10s} {'mc_gate05':>10s}")
    for model in MODELS:
        for metric, key in [('bulk_min', 'ess_bulk_min_med'), ('tail_min', 'ess_tail_min_med')]:
            row = [out.get(f'{a}/{model}', {}).get(key) for a in ARMS]
            print(f"{model:28s} {metric:14s} " + ' '.join(
                f"{v:10.0f}" if v is not None else f"{'--':>10s}" for v in row))
        row = [walls.get(f'{a}/{model}', {}).get('wall_med_s') for a in ARMS]
        print(f"{model:28s} {'wall_med_s':14s} " + ' '.join(
            f"{v:10.1f}" if v is not None else f"{'--':>10s}" for v in row))
        row = [walls.get(f'{a}/{model}', {}).get('exit_iter_med') for a in ARMS]
        print(f"{model:28s} {'exit_iter_med':14s} " + ' '.join(
            f"{v:10.0f}" if v is not None else f"{'--':>10s}" for v in row))
        print()

if __name__ == '__main__':
    main()
