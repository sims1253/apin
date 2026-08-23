#!/usr/bin/env python
"""W-38-E2 analysis: canary md5, call/wall medians, quality gates
(arviz ESS/R-hat vs the base noise band), blr probe pin check.

Run: uv run --with arviz,pandas python harness/analyze_w38e2.py [reps]
Inputs: runs/w38e2/. Outputs: results/w38e2_calls.json,
results/w38e2_ess.json, results/w38e2_probe.json + printed tables.
"""
import csv, hashlib, json, math, sys
from pathlib import Path

import arviz as az
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / 'runs' / 'w38e2'
MODELS = ['arma11', 'lsat_model', 'hier_2pl', 'blr', 'kronecker_gp']
MARGINAL = ['arma11', 'lsat_model', 'hier_2pl']
OVERHEAD = ['hier_2pl', 'kronecker_gp', 'blr']
ARMS = ['base', 'e2a', 'e2b', 'e2c']
PROBE_ARMS = ['probe_base', 'probe_e2a5', 'probe_e2a8']
CANARY_MODELS = ['arma11', 'blr', 'hier_2pl']
CHAINS = 4
DROPS = {'lp__', 'accept_stat__', 'stepsize__', 'treedepth__', 'n_leapfrog__',
         'divergent__', 'energy__', 'X'}


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def load_rows(arm, model, rep, root=RUNS):
    p = root / arm / model / f'rep{rep}' / 'rows.csv'
    if not p.exists():
        return None
    return list(csv.DictReader(p.open()))


def canary(reps=1):
    out = {}
    ok_all = True
    for m in CANARY_MODELS:
        rec = {}
        for c in range(CHAINS):
            b = RUNS / 'base' / m / 'rep0' / f'chain_{c}.csv'
            r = RUNS / 'refcanary' / m / 'rep0' / f'chain_{c}.csv'
            if b.exists() and r.exists():
                mb, mr = md5(b), md5(r)
                rec[f'chain_{c}'] = (mb == mr, mb[:8], mr[:8])
                ok_all &= (mb == mr)
        out[m] = rec
        print(f"canary {m}: "
              f"{sum(v[0] for v in rec.values())}/{len(rec)} identical")
    out['ALL_IDENTICAL'] = ok_all
    print(f"CANARY: {'PASS' if ok_all else 'FAIL'}")
    return out


def calls_wall(reps):
    out = {}
    for m in MODELS:
        rec = {}
        for arm in ARMS:
            calls, walls = [], []
            for rep in range(reps):
                rows = load_rows(arm, m, rep)
                if not rows:
                    continue
                per_chain = [int(r['logp_calls_warm']) +
                             int(r['logp_calls_samp']) for r in rows]
                calls.append(sum(per_chain) / len(per_chain))
                walls.append(float(rows[0]['wall_batch_s']))
            if calls:
                rec[arm] = dict(
                    calls_med=float(np.median(calls)),
                    wall_med=float(np.median(walls)),
                    calls_per_rep=[round(c) for c in calls],
                    wall_per_rep=[round(w, 1) for w in walls])
        if 'base' in rec:
            for arm in ARMS:
                if arm in rec:
                    rec[f'{arm}_calls_ratio'] = (rec[arm]['calls_med'] /
                                                 rec['base']['calls_med'])
                    rec[f'{arm}_wall_ratio'] = (rec[arm]['wall_med'] /
                                                rec['base']['wall_med'])
        out[m] = rec
    return out


def ess_for(rep_dir):
    files = sorted(rep_dir.glob('chain_[0-9]*.csv'))
    if not files:
        return None
    dfs = [pd.read_csv(f, comment='#') for f in files]
    keep = [c for c in dfs[0].columns if c not in DROPS]
    n = min(len(d) for d in dfs)
    arrs = [d[keep].to_numpy()[:n] for d in dfs]
    # Exclude STRUCTURALLY CONSTANT columns (constant in every chain:
    # Cholesky identities / correlation-matrix diagonal GQ columns, e.g.
    # hier_2pl L_Omega.1.1=1, kronecker_gp L.1.2=0 — 4 and 466 of them).
    # They are not parameters; their R-hat is nan and would read as inf.
    varying = [j for j in range(len(keep))
               if any(len(set(a[:, j].tolist())) > 1 for a in arrs)]
    arr = np.stack([a[:, varying] for a in arrs], axis=0)
    # One 3D variable (chain, draw, param): arviz vectorizes diagnostics
    # over the extra param dim — identical to a per-param loop (validated
    # exact on blr: max abs diff 0.0) but ~1000x faster on wide models.
    ds = az.convert_to_dataset({'p': arr})
    eb = np.nan_to_num(az.ess(ds, method='bulk')['p'].values, nan=0.0)
    et = np.nan_to_num(az.ess(ds, method='tail')['p'].values, nan=0.0)
    rh = az.rhat(ds)['p'].values
    rh = np.where(np.isnan(rh), np.inf, rh)
    uniq = [len({tuple(r) for r in a}) for a in arrs]  # per-chain uniq rows
    return dict(ess_bulk_min=float(eb.min()), ess_tail_min=float(et.min()),
                rhat_max=float(rh.max()), uniq_per_chain=uniq,
                pinned_chains=int(sum(u == 1 for u in uniq)),
                n_draws=n, n_chains=len(files))


def quality(reps):
    out = {}
    for m in MODELS:
        rec = {}
        for arm in ARMS:
            per = []
            for rep in range(reps):
                d = RUNS / arm / m / f'rep{rep}'
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
        # gate vs base band (medians of 3 reps within base per-rep spread)
        if 'base' in rec:
            bb = rec['base']['per_rep_bulk']
            bt = rec['base']['per_rep_tail']
            br = rec['base']['per_rep_rhat']
            for arm in ARMS:
                if arm == 'base' or arm not in rec:
                    continue
                e = rec[arm]
                e['gate_pass'] = bool(
                    e['ess_bulk_min_med'] >= min(bb) and
                    e['ess_tail_min_med'] >= min(bt) and
                    e['rhat_max_med'] <= max(br))
        out[m] = rec
    return out


def probe(reps):
    out = {}
    for arm in PROBE_ARMS:
        per = []
        for rep in range(reps):
            d = RUNS / 'probe' / arm / 'blr' / f'rep{rep}'
            if not (d / 'DONE').exists():
                continue
            e = ess_for(d)
            if e:
                rows = load_rows(arm, 'blr', rep, root=RUNS / 'probe')
                calls = [int(r['logp_calls_warm']) + int(r['logp_calls_samp'])
                         for r in rows] if rows else []
                e['calls_per_chain'] = calls
                per.append(e)
        if per:
            out[arm] = dict(
                n=len(per),
                ess_bulk_min_med=float(np.median([p['ess_bulk_min'] for p in per])),
                ess_tail_min_med=float(np.median([p['ess_tail_min'] for p in per])),
                rhat_max_med=float(np.median([p['rhat_max'] for p in per])),
                uniq_med=int(np.median([min(p['uniq_per_chain'])
                                        for p in per])),
                pinned_chains_tot=int(sum(p['pinned_chains'] for p in per)),
                calls_med=float(np.median([np.mean(p['calls_per_chain'])
                                           for p in per])),
                per_rep_bulk=[round(p['ess_bulk_min'], 1) for p in per],
                per_rep_uniq=[min(p['uniq_per_chain']) for p in per])
    return out


def main():
    reps = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    can = canary()
    (ROOT / 'results/w38e2_canary.json').write_text(json.dumps(can, indent=1))
    cw = calls_wall(reps)
    (ROOT / 'results/w38e2_calls.json').write_text(json.dumps(cw, indent=1))
    q = quality(reps)
    (ROOT / 'results/w38e2_ess.json').write_text(json.dumps(q, indent=1))
    pr = probe(reps)
    (ROOT / 'results/w38e2_probe.json').write_text(json.dumps(pr, indent=1))

    print('\n=== CALLS per chain (median of reps) / ratio vs base ===')
    print(f"{'model':14s} " + ' '.join(f'{a:>13s}' for a in ARMS) +
          '   wall-ratios')
    for m in MODELS:
        r = cw[m]
        cells = ' '.join(f"{r[a]['calls_med']:6.0f} ({r[f'{a}_calls_ratio']:.3f})"
                         for a in ARMS if a in r)
        wr = ' '.join(f"{r[f'{a}_wall_ratio']:.3f}" for a in ARMS
                      if f'{a}_wall_ratio' in r)
        print(f"{m:14s} {cells}   {wr}")

    print('\n=== QUALITY (medians of reps; gate = within base rep spread) ===')
    print(f"{'model':14s} {'arm':5s} {'bulk_min':>9s} {'tail_min':>9s} "
          f"{'rhat_max':>8s}  gate")
    for m in MODELS:
        for arm in ARMS:
            e = q[m].get(arm)
            if e:
                g = ('PASS' if e.get('gate_pass') else
                     'n/a' if arm == 'base' else 'FAIL')
                print(f"{m:14s} {arm:5s} {e['ess_bulk_min_med']:9.1f} "
                      f"{e['ess_tail_min_med']:9.1f} {e['rhat_max_med']:8.4f}"
                      f"  {g}")

    print('\n=== BLR SHORT-WARMUP PROBE (warmup=400) ===')
    for arm, e in pr.items():
        pin = 'UNPINNED' if e['pinned_chains_tot'] == 0 else \
            f"PINNED x{e['pinned_chains_tot']}/12 chains"
        print(f"{arm:12s} bulk_min_med={e['ess_bulk_min_med']:8.1f} "
              f"tail_min_med={e['ess_tail_min_med']:8.1f} "
              f"uniq_med={e['uniq_med']:5d} calls_med={e['calls_med']:8.0f} "
              f"-> {pin}")


if __name__ == '__main__':
    main()
