#!/usr/bin/env python3
"""W-38-E4 analysis: canary md5, micro-search table, grid quality gates
(arviz ESS/R-hat vs the base noise band, base = W-38-E2 base arm),
efficiency metrics (evals/draw, ESS/wall), mechanism histograms.

Run: uv run --with arviz,pandas python harness/analyze_w38e4.py [reps]
Inputs: runs/w38e4/ + runs/w38e2/base. Outputs:
results/w38e4_{canary,micro,grid,mech}.json + printed tables.
"""
import csv, hashlib, json, sys
from pathlib import Path

import arviz as az
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / 'runs' / 'w38e4'
BASE_ROOT = ROOT / 'runs' / 'w38e2'  # base arm cells: BASE_ROOT/base/...
MODELS = ['arma11', 'lsat_model', 'hier_2pl', 'blr', 'kronecker_gp']
CANARY_MODELS = MODELS
MICRO_ARMS = ['g1', 'g2', 'g3', 't4', 't2']
CHAINS = 4
DRAWS = 1000
DROPS = {'lp__', 'accept_stat__', 'stepsize__', 'treedepth__', 'n_leapfrog__',
         'divergent__', 'energy__', 'X'}


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def load_rows(arm, model, rep, root):
    p = root / arm / model / f'rep{rep}' / 'rows.csv'
    if not p.exists():
        return None
    return list(csv.DictReader(p.open()))


def canary():
    out = {}
    ok_all = True
    for m in CANARY_MODELS:
        rec = {}
        for c in range(CHAINS):
            a = RUNS / 'canary' / 'default' / m / 'rep0' / f'chain_{c}.csv'
            b = BASE_ROOT / 'base' / m / 'rep0' / f'chain_{c}.csv'
            if a.exists() and b.exists():
                ma, mb = md5(a), md5(b)
                rec[f'chain_{c}'] = (ma == mb, ma[:8], mb[:8])
                ok_all &= (ma == mb)
        out[m] = rec
        print(f"canary {m}: {sum(v[0] for v in rec.values())}/{len(rec)} "
              f"identical (vs W-38-E2 base arm == safe-adapt binary)")
    out['ALL_IDENTICAL'] = ok_all
    print(f"CANARY: {'PASS' if ok_all else 'FAIL'}")
    return out


def cell_metrics(rows):
    """evals/draw (sampling) + total calls/draw + wall, per cell."""
    epd = [int(r['logp_calls_samp']) / DRAWS for r in rows]
    tpd = [(int(r['logp_calls_warm']) + int(r['logp_calls_samp'])) / DRAWS
           for r in rows]
    chain_wall = [float(r['warmup_s']) + float(r['sampling_s'])
                  for r in rows if r['warmup_s'] and r['sampling_s']]
    return dict(evals_draw_med=float(np.median(epd)),
                evals_draw_per_chain=[round(x, 1) for x in epd],
                total_draw_med=float(np.median(tpd)),
                chain_wall_s=[round(w, 2) for w in chain_wall],
                wall_sum_s=round(sum(chain_wall), 2))


def micro(reps):
    out = {}
    for arm in MICRO_ARMS:
        cells = []
        for rep in range(reps):
            rows = load_rows(arm, 'blr', rep, RUNS / 'micro')
            if rows:
                cells.append((rep, cell_metrics(rows)))
        if cells:
            out[arm] = dict(
                n=len(cells),
                reps=[r for r, _ in cells],
                evals_draw_med=float(np.median([c['evals_draw_med']
                                                for _, c in cells])),
                total_draw_med=float(np.median([c['total_draw_med']
                                                for _, c in cells])),
                wall_sum=[c['wall_sum_s'] for _, c in cells])
        else:
            out[arm] = dict(n=0, note='ALL CELLS ABORTED (rc=-6, nan-grad '
                                      'macro_time abort)')
    base_rows = [load_rows('base', 'blr', r, BASE_ROOT) for r in range(reps)]
    base_cells = [cell_metrics(rows) for rows in base_rows if rows]
    out['base(E2)'] = dict(n=len(base_cells),
                           evals_draw_med=float(np.median(
                               [c['evals_draw_med'] for c in base_cells])),
                           total_draw_med=float(np.median(
                               [c['total_draw_med'] for c in base_cells])),
                           wall_sum=[c['wall_sum_s'] for c in base_cells])
    return out


def ess_for(rep_dir):
    files = sorted(rep_dir.glob('chain_[0-9]*.csv'))
    if not files:
        return None
    dfs = [pd.read_csv(f, comment='#') for f in files]
    keep = [c for c in dfs[0].columns if c not in DROPS]
    n = min(len(d) for d in dfs)
    arrs = [d[keep].to_numpy()[:n] for d in dfs]
    varying = [j for j in range(len(keep))
               if any(len(set(a[:, j].tolist())) > 1 for a in arrs)]
    arr = np.stack([a[:, varying] for a in arrs], axis=0)
    ds = az.convert_to_dataset({'p': arr})
    eb = np.nan_to_num(az.ess(ds, method='bulk')['p'].values, nan=0.0)
    et = np.nan_to_num(az.ess(ds, method='tail')['p'].values, nan=0.0)
    rh = az.rhat(ds)['p'].values
    rh = np.where(np.isnan(rh), np.inf, rh)
    return dict(ess_bulk_min=float(eb.min()), ess_tail_min=float(et.min()),
                rhat_max=float(rh.max()), n_draws=n, n_chains=len(files))


def grid(reps):
    out = {}
    for m in MODELS:
        rec = {}
        for arm, root in [('base', BASE_ROOT), ('grow', RUNS / 'grid')]:
            per = []
            for rep in range(reps):
                d = root / arm / m / f'rep{rep}'
                if not (d / 'DONE').exists():
                    continue
                e = ess_for(d)
                rows = load_rows(arm, m, rep, root)
                if e and rows:
                    e.update(cell_metrics(rows))
                    per.append(e)
            if per:
                rec[arm] = dict(
                    n=len(per),
                    ess_bulk_min_med=float(np.median(
                        [p['ess_bulk_min'] for p in per])),
                    ess_tail_min_med=float(np.median(
                        [p['ess_tail_min'] for p in per])),
                    rhat_max_med=float(np.median(
                        [p['rhat_max'] for p in per])),
                    evals_draw_med=float(np.median(
                        [p['evals_draw_med'] for p in per])),
                    total_draw_med=float(np.median(
                        [p['total_draw_med'] for p in per])),
                    ess_per_wall=float(np.median(
                        [p['ess_bulk_min'] / p['wall_sum_s'] for p in per])),
                    per_rep_bulk=[round(p['ess_bulk_min'], 1) for p in per],
                    per_rep_tail=[round(p['ess_tail_min'], 1) for p in per],
                    per_rep_rhat=[round(p['rhat_max'], 4) for p in per],
                    per_rep_evals_draw=[round(p['evals_draw_med'], 1)
                                        for p in per])
        b, g = rec.get('base'), rec.get('grow')
        if b and g:
            g['gate_pass'] = bool(
                g['ess_bulk_min_med'] >= min(b['per_rep_bulk']) and
                g['ess_tail_min_med'] >= min(b['per_rep_tail']) and
                g['rhat_max_med'] <= max(b['per_rep_rhat']))
            g['evals_draw_ratio'] = g['evals_draw_med'] / b['evals_draw_med']
            g['total_draw_ratio'] = g['total_draw_med'] / b['total_draw_med']
            g['ess_per_wall_ratio'] = g['ess_per_wall'] / b['ess_per_wall']
        out[m] = rec
    return out


def parse_accounting_log(log_path):
    import re
    KV = re.compile(r'(\S+)=(\S+)')
    out, phase = {}, None
    for line in Path(log_path).read_text().splitlines():
        if not line.startswith('[grad-accounting]'):
            continue
        payload = line[len('[grad-accounting]'):].strip()
        if payload.startswith('phase='):
            phase = payload.split('=', 1)[1]
            out[phase] = {}
        elif phase is not None:
            out[phase].update({k: int(v) for k, v in KV.findall(payload)})
    # evals/draw from the CLI stanzas
    import re as _re
    calls = [int(x) for x in
             _re.findall(r'logp_grad calls: (\d+)',
                         Path(log_path).read_text())]
    out['cli_calls'] = calls
    return out


def mech():
    out = {}
    for model in ['blr', 'hier_2pl']:
        rec = {}
        for arm in ['off', 'grow']:
            log = RUNS / 'mech' / arm / model / 'chain_0.log'
            if log.exists():
                a = parse_accounting_log(log)
                s = a.get('sampling', {})
                w = a.get('warmup', {})
                tot = sum(a['cli_calls']) if a.get('cli_calls') else None
                samp_calls = a['cli_calls'][1] if len(
                    a.get('cli_calls', [])) > 1 else None
                rec[arm] = dict(
                    warmup=w, sampling=s,
                    evals_draw=samp_calls / 1000.0 if samp_calls else None,
                    total_calls=tot)
        # h-histogram + bucket shares side by side
        out[model] = rec
    return out


def main():
    reps = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    can = canary()
    (ROOT / 'results/w38e4_canary.json').write_text(json.dumps(can, indent=1))
    mi = micro(reps)
    (ROOT / 'results/w38e4_micro.json').write_text(json.dumps(mi, indent=1))
    g = grid(reps)
    (ROOT / 'results/w38e4_grid.json').write_text(json.dumps(g, indent=1))
    me = mech()
    (ROOT / 'results/w38e4_mech.json').write_text(json.dumps(me, indent=1))

    print('\n=== MICRO-SEARCH (blr, evals/draw sampling | total/draw) ===')
    b = mi['base(E2)']
    print(f"base(E2): {b['evals_draw_med']:.1f} | {b['total_draw_med']:.1f}")
    for arm in MICRO_ARMS:
        e = mi[arm]
        if e.get('n', 0):
            print(f"{arm:4s}: {e['evals_draw_med']:8.1f} | "
                  f"{e['total_draw_med']:8.1f}  (n={e['n']})")
        else:
            print(f"{arm:4s}: {e.get('note', 'no cells')}")

    print('\n=== GRID quality + efficiency (grow = winner variant) ===')
    print(f"{'model':14s} {'arm':5s} {'bulk':>8s} {'tail':>8s} {'rhat':>7s} "
          f"{'ev/draw':>8s} {'tot/draw':>9s} {'ESS/wall':>9s}  gate")
    for m in MODELS:
        for arm in ['base', 'grow']:
            e = g[m].get(arm)
            if not e:
                continue
            gate = ('' if arm == 'base' else
                    'PASS' if e.get('gate_pass') else 'FAIL')
            print(f"{m:14s} {arm:5s} {e['ess_bulk_min_med']:8.1f} "
                  f"{e['ess_tail_min_med']:8.1f} {e['rhat_max_med']:7.4f} "
                  f"{e['evals_draw_med']:8.1f} {e['total_draw_med']:9.1f} "
                  f"{e['ess_per_wall']:9.2f}  {gate}"
                  + (f"  (ev ratio {e['evals_draw_ratio']:.3f}, "
                     f"ESS/wall ratio {e['ess_per_wall_ratio']:.3f})"
                     if arm == 'grow' else ''))

    print('\n=== MECHANISM (1 chain, 1000+1000, seed 20260819) ===')
    for model, rec in me.items():
        for arm, e in rec.items():
            s = e['sampling']
            hs = {k: v for k, v in s.items() if k.startswith('h')
                  and k[1:].isdigit() and v > 0}
            kt = s.get('kernel_total', 0)
            print(f"{model:9s} {arm:5s} evals/draw={e['evals_draw']:.1f} "
                  f"samp_h={hs} "
                  f"fw={s.get('forward_wasted', 0)} bl={s.get('backward_ladder', 0)} "
                  f"dl={s.get('discarded_leaf', 0)} / kt={kt} "
                  f"m_hist={({k: v for k, v in s.items() if k.startswith('m') and k[1:].isdigit() and v > 0})}")


if __name__ == '__main__':
    main()
