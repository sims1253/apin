#!/usr/bin/env python
"""W-34 gate (c): sampler-level sanity, stock vs armB hier_2pl.

W-30 par4 protocol: 4 parallel single-chain stan_cli procs per rep, warmup
1000 draws 1000, --metric-window 50, seeds 20260819+1000*rep+c, pf inits
from inits_w25/hier_2pl/rep{r}/chain_{c}.txt. Binary:
external/walnutpie/build/examples/stan_cli @ 43b6435 (read-only, NOT rebuilt).
ESS via arviz (W-25 procedure). Usage:
  uv run python harness/w34/w34_gatec.py run     # sampling (2 arms x 3 reps)
  uv run python harness/w34/w34_gatec.py analyze # ESS + walls -> results/w34_*.json
"""
import json, os, re, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CLI = ROOT / 'external/walnutpie/build/examples/stan_cli'
DATA = ROOT / 'data/hier_2pl.json'
ARMS = {'stock': ROOT / 'scratch/w34/stock_build/hier_2pl_model.so',
        'armB': ROOT / 'scratch/w34/armB_build/hier_2pl_model.so'}
RUNS = ROOT / 'runs/w34'
CHAINS, REPS, WARMUP, DRAWS, BASE_SEED = 4, 3, 1000, 1000, 20260819


def run():
    env = {**os.environ, 'OMP_NUM_THREADS': '1'}
    for rep in range(REPS):
        for arm, so in ARMS.items():
            out = RUNS / arm / f'rep{rep}'
            out.mkdir(parents=True, exist_ok=True)
            if (out / 'DONE').exists():
                print(f'skip {arm}/rep{rep}', flush=True)
                continue
            seed = BASE_SEED + 1000 * rep
            procs = []
            t0 = time.time()
            for c in range(CHAINS):
                cmd = [str(CLI), str(so), str(DATA), '--seed', str(seed + c),
                       '--init-file', str(ROOT / f'inits_w25/hier_2pl/rep{rep}/chain_{c}.txt'),
                       '--warmup', str(WARMUP), '--samples', str(DRAWS),
                       '--metric-window', '50',
                       '--output', str(out / f'chain_{c}.csv')]
                lf = (out / f'chain_{c}.log').open('w')
                procs.append((c, subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT, env=env), lf))
            for c, pr, lf in procs:
                pr.wait()
                lf.close()
                if pr.returncode != 0:
                    raise RuntimeError(f'{arm}/rep{rep} c{c} rc={pr.returncode}')
            wall = time.time() - t0
            (out / 'DONE').write_text(f'{wall:.2f}\n')
            print(f'{arm}/rep{rep}: wall {wall:.1f}s', flush=True)


def parse_sc(text):
    m = re.findall(r'total time: ([\d.eE+-]+)s?\s*\n'
                   r'logp_grad time: ([\d.eE+-]+)s?\s*\n'
                   r'logp_grad fraction: ([\d.eE+-]+)\s*\n'
                   r'\s*logp_grad calls: (\d+)\s*\n'
                   r'\s*time per call: ([\d.eE+-]+)s\s*', text)
    return [dict(zip(['total', 'logp_time', 'logp_frac', 'calls', 'per_call'],
                     (float(g) for g in row))) for row in m]


def analyze():
    import arviz as az
    import numpy as np
    import pandas as pd
    DROPS = {'lp__', 'accept_stat__', 'stepsize__', 'treedepth__', 'n_leapfrog__',
             'divergent__', 'energy__', 'X'}
    out_e, out_w = {}, {}
    for arm in ARMS:
        per_e, per_w = [], []
        for rep in range(REPS):
            d = RUNS / arm / f'rep{rep}'
            files = sorted(d.glob('chain_[0-9]*.csv'))
            dfs = [pd.read_csv(f, comment='#') for f in files]
            keep = [k for k in dfs[0].columns if k not in DROPS]
            n = min(len(x) for x in dfs)
            eb = [float(az.ess(np.stack([x[k].to_numpy()[:n] for x in dfs], axis=0), method='bulk'))
                  for k in keep]
            et = [float(az.ess(np.stack([x[k].to_numpy()[:n] for x in dfs], axis=0),
                               method='tail', prob=0.05)) for k in keep]
            rh = [float(az.rhat(np.stack([x[k].to_numpy()[:n] for x in dfs], axis=0))) for k in keep]
            stanzas = []
            for c in range(CHAINS):
                stanzas += parse_sc((d / f'chain_{c}.log').read_text())
            warm = [s for s in stanzas[:len(stanzas) // 2]] if stanzas else []
            wall = float((d / 'DONE').read_text())
            per_e.append(dict(rep=rep, ess_bulk_min=round(min(eb), 1),
                              ess_tail_min=round(min(et), 1), rhat_max=round(max(rh), 4),
                              argmin_bulk=keep[int(np.argmin(eb))]))
            per_w.append(dict(rep=rep, wall_s=round(wall, 2),
                              logp_grad_us_sampling=round(float(np.median(
                                  [s['per_call'] for s in stanzas[len(stanzas)//2:]])) * 1e6, 1)
                              if len(stanzas) >= 2 else None,
                              grad_calls_sampling=sum(
                                  s['calls'] for s in stanzas[len(stanzas)//2:])))
        out_e[arm] = dict(per_rep=per_e,
                          ess_bulk_min_med=float(np.median([p['ess_bulk_min'] for p in per_e])),
                          ess_tail_min_med=float(np.median([p['ess_tail_min'] for p in per_e])),
                          rhat_max_med=float(np.median([p['rhat_max'] for p in per_e])))
        out_w[arm] = dict(per_rep=per_w, wall_med_s=float(np.median([p['wall_s'] for p in per_w])))
    (ROOT / 'results/w34_ess.json').write_text(json.dumps(out_e, indent=1))
    (ROOT / 'results/w34_wall.json').write_text(json.dumps(out_w, indent=1))
    print(json.dumps(out_e, indent=1))
    print(json.dumps(out_w, indent=1))


if __name__ == '__main__':
    {'run': run, 'analyze': analyze}[sys.argv[1]]()
