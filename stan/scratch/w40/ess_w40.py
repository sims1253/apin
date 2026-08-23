#!/usr/bin/env python3
"""W-40 gate (d) analysis: bulk/tail ESS-min + R-hat per arm/rep (arviz,
rank-normalized, protocol of harness/analyze_w36.py)."""
import json
from pathlib import Path
import numpy as np
import arviz as az

ROOT = Path('/home/m0hawk/Documents/apin/stan')
RUNS = ROOT / 'runs/w40'


def stack(rep_dir):
    chains = []
    for c in range(4):
        f = rep_dir / f'chain_{c}.csv'
        arr = np.loadtxt(f, delimiter=',', skiprows=1, ndmin=2)
        chains.append(arr)
    n = min(len(c) for c in chains)
    return np.stack([c[:n] for c in chains])  # (chain, draw, col)


def ess_for(rep_dir):
    d = stack(rep_dir)
    # keep only sampled-draw columns (skip lp__ col 0 as w36 does? w36 keeps all
    # constrained params; col0 = lp__ excluded there via keep) — inspect header
    with (rep_dir / 'chain_0.csv').open() as f:
        hdr = f.readline().strip().split(',')
    keep = list(range(1, len(hdr)))  # all constrained params, skip lp__
    eb, et, rh, nconst = [], [], [], 0
    for k in keep:
        col = d[:, :, k]
        if np.all(np.isnan(col)):      # pinned -inf-init chain (W-41)
            nconst += 1
            continue
        eb.append(float(az.ess(col, method='bulk')))
        et.append(float(az.ess(col, method='tail', prob=0.05)))
        rh.append(float(az.rhat(col)))
    return dict(ess_bulk_min=min(eb), ess_tail_min=min(et), rhat_max=max(rh),
                allnan_cols=nconst, cols=len(keep))


out = {}
for arm in ('stock', 'patched'):
    per = []
    for rep in range(3):
        e = ess_for(RUNS / arm / f'rep{rep}')
        per.append(e)
        print(f'{arm} rep{rep}: bulk-min {e["ess_bulk_min"]:8.1f} '
              f'tail-min {e["ess_tail_min"]:8.1f} rhat-max {e["rhat_max"]:.4f} '
              f'allnan-cols {e["allnan_cols"]}')
    for key in ('ess_bulk_min', 'ess_tail_min'):
        v = [p[key] for p in per[1:]]  # healthy reps 1,2
        print(f'{arm} healthy-rep median {key}: {np.median(v):.1f} '
              f'(per-rep: {[round(x,1) for x in v]})')
    out[arm] = per
(ROOT / 'results/w40_ess.json').write_text(json.dumps(out, indent=1))
print('wrote results/w40_ess.json')
