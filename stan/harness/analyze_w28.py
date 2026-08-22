#!/usr/bin/env python
"""W-28 analysis: 3 arms — full-warmup base / early-exit-no-pilot (mc_gate05,
the refuted static gate, reference) / pilot-burst gate (mc_pilot50).

base + mc_gate05 reuse the W-25 runs (runs/base, runs/mc_gate05): the
unchanged code paths are canary-verified (single-chain bit-identical; the
multi-chain controller path is untouched when --pilot-burst 0, and it is
inherently run-to-run nondeterministic, which is why medians are used).
ESS via arviz (R posterior absent on this machine), same estimator across
all arms. Writes results/w28_{ess,wall,pilot}.json.
"""
import json
import re
import sys
from pathlib import Path

import arviz as az
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / 'runs'
MODELS = ['arma11', 'lsat_model', 'hier_2pl', 'blr', 'eight_schools_noncentered']
ARMS = ['base', 'mc_gate05', 'mc_pilot50']
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
                    per_rep_bulk=[round(p['ess_bulk_min'], 1) for p in per],
                    per_rep_tail=[round(p['ess_tail_min'], 1) for p in per])
    (ROOT / 'results').mkdir(exist_ok=True)
    (ROOT / 'results/w28_ess.json').write_text(json.dumps(out, indent=1))

    walls, pilots = {}, {}
    for model in MODELS:
        for arm in ARMS:
            vals, exits = [], []
            for rep in range(reps):
                f = RUNS / arm / model / f'rep{rep}' / 'rows.csv'
                if not f.exists():
                    continue
                rows = list(pd.read_csv(f).to_dict('records'))
                vals.append(float(rows[0]['wall_batch_s']))
                ex = rows[0].get('exit_iter')
                exits.append(int(ex) if ex == ex else None)
                if arm == 'mc_pilot50':
                    pl = rows[0]
                    pilots.setdefault(model, []).append(dict(
                        rep=rep, wall=rows[0]['wall_batch_s'],
                        exit_iter=(int(ex) if ex == ex else None),
                        pilot_checks=pl.get('pilot_checks'),
                        rho1_max=pl.get('pilot_last_rho1_max'),
                        rhat_lp=pl.get('pilot_last_rhat_lp'),
                        decision=pl.get('pilot_last_decision')))
            if vals:
                walls[f'{arm}/{model}'] = dict(
                    wall_med_s=float(np.median(vals)),
                    per_rep_wall=[round(v, 1) for v in vals],
                    exit_iter_med=(float(np.median([e for e in exits if e is not None]))
                                   if any(e is not None for e in exits) else None))
    (ROOT / 'results/w28_wall.json').write_text(json.dumps(walls, indent=1))
    (ROOT / 'results/w28_pilot.json').write_text(json.dumps(pilots, indent=1))

    print(f"{'model':26s} {'metric':12s} " +
          ' '.join(f'{a:>12s}' for a in ARMS))
    for model in MODELS:
        for metric, key in [('bulk_min', 'ess_bulk_min_med'),
                            ('tail_min', 'ess_tail_min_med'),
                            ('wall_med_s', 'wall_med_s'),
                            ('exit_iter', 'exit_iter_med')]:
            row = []
            for a in ARMS:
                src = out if key.startswith('ess') else walls
                v = src.get(f'{a}/{model}', {}).get(key)
                row.append(v)
            print(f"{model:26s} {metric:12s} " + ' '.join(
                f"{v:12.1f}" if v is not None else f"{'--':>12s}" for v in row))
        print()
    # base rep spread (noise band) for the quality gate
    print('base per-rep bulk/tail (noise band):')
    for model in MODELS:
        e = out.get(f'base/{model}')
        if e:
            print(f"  {model:26s} bulk {e['per_rep_bulk']} tail {e['per_rep_tail']}")
    print('\npilot arm per-rep checks:')
    for model, lst in pilots.items():
        for p in lst:
            print(f"  {model:26s} rep{p['rep']} exit={p['exit_iter']} "
                  f"checks={p['pilot_checks']} rho1={p['rho1_max']} "
                  f"rhat={p['rhat_lp']} {p['decision']}")


if __name__ == '__main__':
    main()
