#!/usr/bin/env python
"""W-45 analyzer: fidelity, quality (ESS/R-hat vs base band), wall, and
state-transfer (gate (c) mechanism evidence). W-38-E2 ESS conventions.

Run: env -u LD_LIBRARY_PATH .venv/bin/python harness/w45/analyze_w45.py
Outputs: results/w45_fidelity.json, results/w45_ess.json,
results/w45_wall.json, results/w45_state.json + printed tables.
"""
import hashlib, json, math, re
from pathlib import Path

import arviz as az
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / 'runs' / 'w45'
RESULTS = ROOT / 'results'
MODELS = ['arma11', 'lsat_model', 'hier_2pl', 'blr']
ALPHAS = ['25', '10']
ARMS = ['base', 'toolbase'] + [f'v1_a{a}' for a in ALPHAS] \
       + [f'v2_a{a}' for a in ALPHAS]
CHAINS = 4
DROPS = {'lp__', 'accept_stat__', 'stepsize__', 'treedepth__', 'n_leapfrog__',
         'divergent__', 'energy__', 'X'}
RETUNE_RE = re.compile(r'Heuristic retuned step size: ([\d.eE+-]+)')


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def fidelity():
    out = {'cells': {}, 'n_ok': 0, 'n_bad': 0}
    for m in MODELS:
        for r in range(3):
            for c in range(CHAINS):
                b = RUNS / 'base' / m / f'rep{r}' / f'chain_{c}.csv'
                t = RUNS / 'toolbase' / m / f'rep{r}' / f'chain_{c}.csv'
                if not (b.exists() and t.exists()):
                    continue
                same = md5(b) == md5(t)
                out['cells'][f'{m}/rep{r}/c{c}'] = same
                out['n_ok' if same else 'n_bad'] += 1
    return out


def ess_for(rep_dir):
    files = sorted(rep_dir.glob('chain_[0-9]*.csv'))
    if not files:
        return None
    dfs = [pd.read_csv(f, comment='#') for f in files]
    keep = [c for c in dfs[0].columns if c not in DROPS]
    n = min(len(d) for d in dfs)
    arrs = [d[keep].to_numpy()[:n] for d in dfs]
    # exclude structurally constant columns (constant in every chain)
    varying = [j for j in range(len(keep))
               if any(len(set(a[:, j].tolist())) > 1 for a in arrs)]
    arr = np.stack([a[:, varying] for a in arrs], axis=0)
    ds = az.convert_to_dataset({'p': arr})
    eb = np.nan_to_num(az.ess(ds, method='bulk')['p'].values, nan=0.0)
    et = np.nan_to_num(az.ess(ds, method='tail')['p'].values, nan=0.0)
    rh = az.rhat(ds)['p'].values
    rh = np.where(np.isnan(rh), np.inf, rh)
    uniq = [len({tuple(r) for r in a}) for a in arrs]
    return dict(ess_bulk_min=float(eb.min()), ess_tail_min=float(et.min()),
                rhat_max=float(rh.max()), pinned_chains=int(sum(u == 1 for u in uniq)),
                n_draws=n, n_chains=len(files))


def quality():
    out = {}
    for m in MODELS:
        rec = {}
        for arm in ARMS:
            per = []
            for r in range(3):
                d = RUNS / arm / m / f'rep{r}'
                if not (d / 'DONE').exists():
                    continue
                e = ess_for(d)
                if e:
                    per.append(e)
            if not per:
                continue
            rec[arm] = dict(
                n=len(per),
                ess_bulk_min_med=float(np.median([p['ess_bulk_min'] for p in per])),
                ess_tail_min_med=float(np.median([p['ess_tail_min'] for p in per])),
                rhat_max_med=float(np.median([p['rhat_max'] for p in per])),
                per_rep_bulk=[round(p['ess_bulk_min'], 1) for p in per],
                per_rep_tail=[round(p['ess_tail_min'], 1) for p in per],
                per_rep_rhat=[round(p['rhat_max'], 4) for p in per],
                pinned_chains=int(sum(p['pinned_chains'] for p in per)))
        if 'base' not in rec:
            continue
        bb = rec['base']['per_rep_bulk']
        bt = rec['base']['per_rep_tail']
        br = rec['base']['per_rep_rhat']
        for arm in rec:
            e = rec[arm]
            e['quality_pass'] = bool(
                e['ess_bulk_min_med'] >= min(bb)
                and e['ess_tail_min_med'] >= min(bt)
                and e['rhat_max_med'] <= max(br))
            e['vs_base_bulk'] = round(
                e['ess_bulk_min_med'] / rec['base']['ess_bulk_min_med'], 3)
            e['vs_base_tail'] = round(
                e['ess_tail_min_med'] / rec['base']['ess_tail_min_med'], 3)
        out[m] = rec
    return out


def load_rows(arm, model):
    rows = []
    for r in range(3):
        f = RUNS / arm / model / f'rep{r}' / 'rows.csv'
        if f.exists():
            rows += list(pd.read_csv(f).to_dict('records'))
    return rows


def wall():
    out = {}
    for m in MODELS:
        base_rows = load_rows('base', m)
        if not base_rows:
            continue
        base_int_w = float(np.median([r['warmup_s'] for r in base_rows]))
        base_int_s = float(np.median([r['sampling_s'] for r in base_rows]))
        base_tot = float(np.median([r['wall_ext_s'] for r in base_rows]))
        rec = {
            'base': {
                'ext_total_med': base_tot,
                'int_warmup_med': base_int_w, 'int_sampling_med': base_int_s,
                'warmup_share_int': round(base_int_w / (base_int_w + base_int_s), 4),
                'logp_calls_warm_med': int(np.median(
                    [r['logp_calls_warm'] for r in base_rows])),
                'logp_calls_samp_med': int(np.median(
                    [r['logp_calls_samp'] for r in base_rows])),
            }, 'arms': {}}
        for a in ALPHAS:
            for v in ('v1', 'v2'):
                arm = f'{v}_a{a}'
                rows = load_rows(arm, m)
                if not rows:
                    continue
                # v2 shares v1's warmup run (same dumped state); its rows
                # record wall_warm_s=0 (the runner's v2 pass skipped the
                # already-complete warmups). Attribute the warmup wall from
                # v1's per-cell rows — the same physical run — so v2 totals
                # are honest.
                warm_w = {}
                if v == 'v2':
                    for r_ in load_rows(f'v1_a{a}', m):
                        warm_w[(int(r_['rep']), int(r_['chain']))] = \
                            r_.get('wall_warm_s', 0.0)
                if v == 'v2' and warm_w:
                    for r_ in rows:
                        r_['wall_ext_s'] = round(
                            r_['wall_ext_s'] + warm_w.get(
                                (int(r_['rep']), int(r_['chain'])), 0.0), 3)
                        r_['wall_warm_s'] = warm_w.get(
                            (int(r_['rep']), int(r_['chain'])), 0.0)
                tot = float(np.median([r['wall_ext_s'] for r in rows]))
                ww = float(np.median([r.get('wall_warm_s', 0.0) for r in rows]))
                ws = float(np.median([r.get('wall_samp_s', 0.0) for r in rows]))
                alpha = int(a) / 100.0
                rec['arms'][arm] = {
                    'ext_total_med': tot,
                    'ext_warm_med': ww, 'ext_samp_med': ws,
                    'ratio_vs_base': round(tot / base_tot, 3),
                    'saving_realized': round(1 - tot / base_tot, 3),
                    'saving_theoretical': round(
                        (1 - alpha) * rec['base']['warmup_share_int'], 3),
                    'logp_calls_samp_med': int(np.median(
                        [r['logp_calls_samp'] for r in rows])),
                    'samp_calls_vs_base': round(float(np.median(
                        [r['logp_calls_samp'] for r in rows]))
                        / rec['base']['logp_calls_samp_med'], 3)}
        # subsample warmup internal stats from state logs
        for a in ALPHAS:
            rows_w = []
            for r in range(3):
                sd = RUNS / 'state' / f'a{a}' / m / f'rep{r}'
                for c in range(CHAINS):
                    lf = sd / f'chain_{c}.log'
                    if lf.exists():
                        txt = lf.read_text()
                        mm = re.search(r'logp_grad calls: (\d+)', txt)
                        tm = re.search(r'total time: ([\d.eE+-]+)s', txt)
                        if mm and tm:
                            rows_w.append((int(mm.group(1)), float(tm.group(1))))
            if rows_w:
                rec.setdefault('sub_warmup', {})[f'a{a}'] = {
                    'logp_calls_med': int(np.median([x[0] for x in rows_w])),
                    'int_wall_med': round(float(np.median([x[1] for x in rows_w])), 3),
                    'calls_vs_base_warmup': round(
                        float(np.median([x[0] for x in rows_w]))
                        / rec['base']['logp_calls_warm_med'], 3)}
        out[m] = rec
    return out


def parse_state(path):
    toks = Path(path).read_text().split()
    d = int(toks[1])
    step = float(toks[3])
    min_micro = int(toks[5])
    lp = float(toks[7])
    i = toks.index('inv_mass')
    inv_mass = np.array([float(x) for x in toks[i + 1:i + 1 + d]])
    i = toks.index('position')
    pos = np.array([float(x) for x in toks[i + 1:i + 1 + d]])
    return dict(step=step, min_micro=min_micro, lp=lp,
                inv_mass=inv_mass, position=pos)


def lsat_theta_index_sets(a):
    """Retained vs prior-only theta unconstrained indices (lsat only)."""
    sub = json.loads((ROOT / 'scratch/w45/data' / f'lsat_model_a{a}.json')
                     .read_text())
    retained = set(sub['student'])  # 1-based
    idx_ret = [4 + s for s in sorted(retained)]          # alpha[5] offset
    idx_prior = [4 + s for s in range(1, sub['N'] + 1) if s not in retained]
    return idx_ret, idx_prior


def state_transfer():
    out = {}
    for m in MODELS:
        for a in ALPHAS:
            cells = []
            for r in range(3):
                for c in range(CHAINS):
                    bp = RUNS / 'state' / 'base' / m / f'rep{r}' / f'chain_{c}.state'
                    sp = RUNS / 'state' / f'a{a}' / m / f'rep{r}' / f'chain_{c}.state'
                    if not (bp.exists() and sp.exists()):
                        continue
                    b, s = parse_state(bp), parse_state(sp)
                    lr = np.log(s['inv_mass']) - np.log(b['inv_mass'])
                    cell = dict(
                        step_logratio=math.log(s['step'] / b['step']),
                        step_sub=s['step'], step_base=b['step'],
                        invm_l2_rel=float(np.linalg.norm(
                            s['inv_mass'] - b['inv_mass'])
                            / np.linalg.norm(b['inv_mass'])),
                        invm_logratio_med=float(np.median(np.abs(lr))),
                        invm_logratio_p90=float(np.percentile(np.abs(lr), 90)),
                        min_micro_sub=s['min_micro'],
                        min_micro_base=b['min_micro'],
                        min_micro_diff=int(s['min_micro'] - b['min_micro']))
                    if m == 'lsat_model':
                        ir, ip = lsat_theta_index_sets(a)
                        cell['invm_logratio_med_retained'] = float(
                            np.median(np.abs(lr[ir])))
                        cell['invm_logratio_med_prioronly'] = float(
                            np.median(np.abs(lr[ip])))
                    # V2 retuned step from the v2 log
                    v2log = RUNS / f'v2_a{a}' / m / f'rep{r}' / f'chain_{c}.log'
                    if v2log.exists():
                        mm = RETUNE_RE.search(v2log.read_text())
                        if mm:
                            cell['retuned_step'] = float(mm.group(1))
                            cell['retuned_logratio_vs_base'] = math.log(
                                float(mm.group(1)) / b['step'])
                    cells.append(cell)
            if cells:
                def med(k):
                    return round(float(np.median([c[k] for c in cells])), 4) \
                        if cells else None
                rec = dict(n=len(cells),
                           step_logratio_med=med('step_logratio'),
                           step_logratio_absmax=round(float(np.max(
                               np.abs([c['step_logratio'] for c in cells]))), 4),
                           invm_l2_rel_med=med('invm_l2_rel'),
                           invm_logratio_med=med('invm_logratio_med'),
                           invm_logratio_p90=med('invm_logratio_p90'),
                           min_micro_base=int(np.median(
                               [c['min_micro_base'] for c in cells])),
                           min_micro_sub=int(np.median(
                               [c['min_micro_sub'] for c in cells])),
                           step_base_med=float(np.median(
                               [c['step_base'] for c in cells])),
                           step_sub_med=float(np.median(
                               [c['step_sub'] for c in cells])))
                if 'invm_logratio_med_retained' in cells[0]:
                    rec['invm_med_retained'] = med('invm_logratio_med_retained')
                    rec['invm_med_prioronly'] = med('invm_logratio_med_prioronly')
                if any('retuned_step' in c for c in cells):
                    rec['retuned_logratio_vs_base_med'] = med(
                        'retuned_logratio_vs_base')
                out[f'{m}/a{a}'] = rec
    return out


def hier_block_split():
    """Per-parameter-block |log inv_mass ratio| for hier_2pl (mechanism):
    theta = per-person (data-dominated, ~alpha*I rows each), xi1/xi2 =
    per-item (alpha*J rows), mu/tau/L = population (aggregates all rows).
    If the story is per-component information scaling, theta should be off
    by ~log(1/alpha) and mu/tau much less."""
    blocks = {'theta': (0, 600), 'xi1': (600, 632), 'xi2': (632, 664),
              'mu': (664, 666), 'tau': (666, 668), 'L_Omega': (668, 669)}
    out = {}
    for a in ALPHAS:
        per = {k: [] for k in blocks}
        for r in range(3):
            for c in range(CHAINS):
                bp = RUNS / 'state' / 'base' / 'hier_2pl' / f'rep{r}' / f'chain_{c}.state'
                sp = RUNS / 'state' / f'a{a}' / 'hier_2pl' / f'rep{r}' / f'chain_{c}.state'
                if not (bp.exists() and sp.exists()):
                    continue
                b, s = parse_state(bp), parse_state(sp)
                lr = np.abs(np.log(s['inv_mass']) - np.log(b['inv_mass']))
                for k, (lo, hi) in blocks.items():
                    per[k].append(float(np.median(lr[lo:hi])))
        out[f'a{a}'] = {k: round(float(np.median(v)), 3)
                        for k, v in per.items() if v}
    return out


def main():
    fid = fidelity()
    qual = quality()
    wl = wall()
    st = state_transfer()
    hb = hier_block_split()
    RESULTS.joinpath('w45_fidelity.json').write_text(json.dumps(fid, indent=1))
    (RESULTS / 'w45_ess.json').write_text(json.dumps(qual, indent=1))
    (RESULTS / 'w45_wall.json').write_text(json.dumps(wl, indent=1))
    (RESULTS / 'w45_state.json').write_text(json.dumps(st, indent=1))
    (RESULTS / 'w45_hierblocks.json').write_text(json.dumps(hb, indent=1))

    print('=== FIDELITY (toolbase vs stan_cli base, md5) ===')
    print(f"{fid['n_ok']} identical / {fid['n_ok'] + fid['n_bad']} cells")

    print('\n=== QUALITY (medians of 3 reps; base band = per-rep extremes) ===')
    for m, rec in qual.items():
        b = rec['base']
        print(f"\n{m}: base bulk-min {b['ess_bulk_min_med']:.0f} "
              f"(reps {b['per_rep_bulk']}), tail-min {b['ess_tail_min_med']:.0f} "
              f"(reps {b['per_rep_tail']}), rhat {b['rhat_max_med']:.4f}")
        for arm, e in rec.items():
            if arm == 'base':
                continue
            print(f"  {arm:8s} bulk {e['ess_bulk_min_med']:7.0f} "
                  f"({e['vs_base_bulk']:5.2f}x) tail {e['ess_tail_min_med']:7.0f} "
                  f"({e['vs_base_tail']:5.2f}x) rhat {e['rhat_max_med']:.4f} "
                  f"pinned={e['pinned_chains']} PASS={e['quality_pass']}")

    print('\n=== WALL (medians of 12 cells, external s) ===')
    for m, rec in wl.items():
        b = rec['base']
        print(f"\n{m}: base total {b['ext_total_med']:.1f}s "
              f"(warm share {b['warmup_share_int']:.2f}, "
              f"warm calls {b['logp_calls_warm_med']}, "
              f"samp calls {b['logp_calls_samp_med']})")
        for arm, e in rec['arms'].items():
            print(f"  {arm:8s} total {e['ext_total_med']:6.1f}s "
                  f"(warm {e['ext_warm_med']:.1f} + samp {e['ext_samp_med']:.1f}) "
                  f"= {e['ratio_vs_base']:.2f}x base; saved "
                  f"{e['saving_realized']*100:.0f}% (theor "
                  f"{e['saving_theoretical']*100:.0f}%); samp calls "
                  f"{e['samp_calls_vs_base']:.2f}x base")
        for a, e in rec.get('sub_warmup', {}).items():
            print(f"  warm a{a}: calls {e['logp_calls_med']} "
                  f"({e['calls_vs_base_warmup']:.2f}x base warmup), "
                  f"int wall {e['int_wall_med']}s")

    print('\n=== STATE TRANSFER (transplanted vs base adapted, 12 cells) ===')
    for k, r in st.items():
        extra = ''
        if 'invm_med_retained' in r:
            extra = (f" | retained {r['invm_med_retained']:.3f} "
                     f"vs prior-only {r['invm_med_prioronly']:.3f}")
        ret = (f" | retuned step logratio {r['retuned_logratio_vs_base_med']:+.3f}"
               if 'retuned_logratio_vs_base_med' in r else '')
        print(f"{k:20s} step logratio {r['step_logratio_med']:+.3f} "
              f"(|max| {r['step_logratio_absmax']:.3f}) "
              f"invm l2 {r['invm_l2_rel_med']:.3f} "
              f"med|lr| {r['invm_logratio_med']:.3f} p90 {r['invm_logratio_p90']:.3f}"
              f" | min_micro base {r['min_micro_base']} sub {r['min_micro_sub']}"
              f"{extra}{ret}")

    print('\n=== HIER_2PL BLOCK SPLIT (median |log inv_mass ratio| by block) ===')
    for a, r in hb.items():
        print(f"hier_2pl/{a}: " + '  '.join(f'{k} {v:.3f}' for k, v in r.items()))


if __name__ == '__main__':
    main()
