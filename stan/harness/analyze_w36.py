#!/usr/bin/env python
"""W-36 analysis: wall medians/geomeans, quality (arviz ESS/R-hat),
call-count deltas, md5 canary/bonus report.

Inputs: runs/w36/<arm>/<model>/rep<r>/{rows.csv,chain_<c>.csv},
results/w36_md5.json. Outputs: results/w36_wall.json, results/w36_ess.json
+ printed tables. Same estimator/procedure as analyze_w31.py (rank-
normalized bulk/tail ESS, arviz; chains trimmed to min length; max
rank-normalized R-hat over parameters).
"""
import csv, json, math, sys
from pathlib import Path

import arviz as az
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / 'runs' / 'w36'
MODELS = ['radon_partially_pooled_noncentered', 'bym2_offset_only', 'hier_2pl',
          'diamonds', 'lsat_model', 'accel_gp', 'kronecker_gp', 'pilots',
          'eight_schools_centered', 'lotka_volterra']
ARMS = ['stock_seq', 'exp_par', 'exp_seq']
DROPS = {'lp__', 'accept_stat__', 'stepsize__', 'treedepth__', 'n_leapfrog__',
         'divergent__', 'energy__', 'X'}
WARMUP, DRAWS = 1000, 1000


def load_rows(arm, model, rep):
    p = RUNS / arm / model / f'rep{rep}' / 'rows.csv'
    if not p.exists():
        return None
    return list(csv.DictReader(p.open()))


def wall_table(reps):
    out = {}
    for model in MODELS:
        rec = {'per_rep': {}}
        walls = {a: [] for a in ARMS}
        calls = {a: [] for a in ARMS}
        uspc = {a: [] for a in ARMS}
        for rep in range(reps):
            pr = {}
            for arm in ARMS:
                rows = load_rows(arm, model, rep)
                if not rows:
                    continue
                w = float(rows[0]['wall_batch_s'])
                walls[arm].append(w)
                pr[arm] = w
                tot_calls = sum(int(r['logp_calls_warm']) + int(r['logp_calls_samp'])
                                for r in rows) / len(rows)
                calls[arm].append(tot_calls)
                uw = [float(r['us_per_logp_warm']) for r in rows
                      if r.get('us_per_logp_warm')]
                us = [float(r['us_per_logp_samp']) for r in rows
                      if r.get('us_per_logp_samp')]
                if uw and us:
                    uspc[arm].append((float(np.median(uw)), float(np.median(us))))
            rec['per_rep'][f'rep{rep}'] = pr
        for arm in ARMS:
            if walls[arm]:
                rec[f'{arm}_wall_med'] = float(np.median(walls[arm]))
                rec[f'{arm}_calls_med'] = float(np.median(calls[arm]))
                rec[f'{arm}_uspc_med'] = [float(np.median([x[0] for x in uspc[arm]])),
                                          float(np.median([x[1] for x in uspc[arm]]))]
        if walls['stock_seq'] and walls['exp_par']:
            rec['ratio_par_over_stock'] = (rec['exp_par_wall_med'] /
                                           rec['stock_seq_wall_med'])
        if walls['stock_seq'] and walls['exp_seq']:
            rec['ratio_seq_over_stock'] = (rec['exp_seq_wall_med'] /
                                           rec['stock_seq_wall_med'])
        out[model] = rec
    # geomeans over models that have both arms
    for ratio_key in ('ratio_par_over_stock', 'ratio_seq_over_stock'):
        rs = [out[m][ratio_key] for m in MODELS if ratio_key in out[m]]
        if rs:
            out[f'GEOMEAN_{ratio_key}'] = math.exp(
                sum(math.log(r) for r in rs) / len(rs))
            out[f'N_{ratio_key}'] = len(rs)
    return out


def ess_for(rep_dir):
    files = sorted(rep_dir.glob('chain_[0-9]*.csv'))
    if not files:
        return None
    dfs = [pd.read_csv(f, comment='#') for f in files]
    keep = [c for c in dfs[0].columns if c not in DROPS]
    n = min(len(d) for d in dfs)
    stack = lambda k: np.stack([d[k].to_numpy()[:n] for d in dfs], axis=0)
    eb = [float(az.ess(stack(k), method='bulk')) for k in keep]
    et = [float(az.ess(stack(k), method='tail', prob=0.05)) for k in keep]
    rh = [float(az.rhat(stack(k))) for k in keep]
    return dict(ess_bulk_min=min(eb), ess_tail_min=min(et), rhat_max=max(rh),
                n_draws=n, n_chains=len(files))


def ess_table(reps):
    out = {}
    for model in MODELS:
        rec = {}
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
                rec[arm] = dict(
                    n=len(per),
                    ess_bulk_min_med=float(np.median([p['ess_bulk_min'] for p in per])),
                    ess_tail_min_med=float(np.median([p['ess_tail_min'] for p in per])),
                    rhat_max_med=float(np.median([p['rhat_max'] for p in per])),
                    per_rep_bulk=[round(p['ess_bulk_min'], 1) for p in per],
                    per_rep_tail=[round(p['ess_tail_min'], 1) for p in per],
                    per_rep_rhat=[round(p['rhat_max'], 4) for p in per])
        out[model] = rec
    return out


def main():
    reps = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    wall = wall_table(reps)
    (ROOT / 'results/w36_wall.json').write_text(json.dumps(wall, indent=1))
    ess = ess_table(reps)
    (ROOT / 'results/w36_ess.json').write_text(json.dumps(ess, indent=1))

    print('=== WALL (median of reps, seconds) ===')
    hdr = f"{'model':38s} {'stock_seq':>10s} {'exp_par':>9s} {'par/stock':>9s}"
    if any('exp_seq' in v for v in wall.values() if isinstance(v, dict)):
        hdr += f" {'exp_seq':>9s} {'seq/stock':>9s}"
    print(hdr)
    for m in MODELS:
        r = wall[m]
        if 'stock_seq_wall_med' not in r:
            continue
        line = (f"{m:38s} {r['stock_seq_wall_med']:10.2f} "
                f"{r.get('exp_par_wall_med', float('nan')):9.2f} "
                f"{r.get('ratio_par_over_stock', float('nan')):9.3f}")
        if 'exp_seq_wall_med' in r:
            line += (f" {r['exp_seq_wall_med']:9.2f} "
                     f"{r.get('ratio_seq_over_stock', float('nan')):9.3f}")
        print(line)
    print(f"GEOMEAN par/stock: {wall.get('GEOMEAN_ratio_par_over_stock')}")
    if 'GEOMEAN_ratio_seq_over_stock' in wall:
        print(f"GEOMEAN seq/stock: {wall.get('GEOMEAN_ratio_seq_over_stock')}")

    print('\n=== CALLS per chain (median over reps/chains) + us/call ===')
    for m in MODELS:
        r = wall[m]
        parts = [f"{a}: {r.get(f'{a}_calls_med', float('nan')):.0f} "
                 f"({r.get(f'{a}_uspc_med', [float('nan')]*2)[0]:.1f}/"
                 f"{r.get(f'{a}_uspc_med', [float('nan')]*2)[1]:.1f}us)"
                 for a in ARMS if f'{a}_calls_med' in r]
        print(f"{m:38s} " + '  '.join(parts))

    print('\n=== QUALITY (median over reps) ===')
    print(f"{'model':38s} {'arm':9s} {'bulk_min':>9s} {'tail_min':>9s} {'rhat_max':>8s}")
    for m in MODELS:
        for arm in ARMS:
            e = ess[m].get(arm)
            if e:
                print(f"{m:38s} {arm:9s} {e['ess_bulk_min_med']:9.1f} "
                      f"{e['ess_tail_min_med']:9.1f} {e['rhat_max_med']:8.4f}")

    mdp = ROOT / 'results/w36_md5.json'
    if mdp.exists():
        md = json.loads(mdp.read_text())
        can = [k for k, v in md.items() if v.get('canary_stock_vs_exp_seq')]
        canf = [k for k, v in md.items()
                if v.get('canary_stock_vs_exp_seq') is False]
        bon = [k for k, v in md.items() if v.get('bonus_stock_vs_exp_par')]
        bonf = [k for k, v in md.items()
                if v.get('bonus_stock_vs_exp_par') is False]
        print(f"\nmd5 canary stock_seq==exp_seq: {len(can)} equal, "
              f"{len(canf)} differ {canf if canf else ''}")
        print(f"md5 bonus stock_seq==exp_par:  {len(bon)} equal, "
              f"{len(bonf)} differ {bonf if bonf else ''}")


if __name__ == '__main__':
    main()
