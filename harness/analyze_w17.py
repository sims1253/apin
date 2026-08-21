#!/usr/bin/env python
"""W-17: post-freeze-fix validation of rank modes (rec / fold / auto).
Per-model medians over reps; compares vs w6_pf_chop50 (pre-fix best) and
cmdstan default. Ragged chains trimmed to min; generic headers OK for ESS."""
import subprocess, statistics as st, sys, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARMS = ['rec', 'fold', 'auto']
def ess_of(d):
    files = sorted(d.glob('chain_[0-9].csv'))
    if len(files) < 4: return None
    try:
        lens = [len(f.read_text().splitlines())-1 for f in files]
        mn = min(lens)
        if mn < 50: return None
        for f in files:
            l2 = f.read_text().splitlines()
            ncol = len(l2[1].split(','))
            f.write_text(','.join(f'x{k}' for k in range(ncol))+'\n'+'\n'.join(l2[1:mn+1])+'\n')
        r = subprocess.run(['Rscript', str(ROOT/'harness/ess.R'), str(d), str(d/'e.json')],
                           capture_output=True, text=True)
        if r.returncode != 0: return None
        m = re.search(r'min=([\d.]+) geomean=([\d.]+) rhat_max=([\d.]+)', r.stdout)
        return (float(m.group(1)), float(m.group(2)), float(m.group(3))) if m else None
    except Exception:
        return None

models = [l.strip() for l in open(ROOT/'/tmp/core_models.txt')] if Path('/tmp/core_models.txt').exists() else sorted({d.name.split('_',2)[2] for d in ROOT.glob('runs/w17_rec_*')})
out = {}
for arm in ARMS:
    for m in models:
        vals, missing = [], 0
        for rep in range(3):
            d = ROOT/f'runs/w17_{arm}_{m}/rep{rep}'
            if not (d/'chain_3.csv').exists(): missing += 1; continue
            v = ess_of(d)
            vals.append(v if v else None)
        good = [v for v in vals if v]
        if good:
            out[(arm, m)] = dict(ess_med=st.median(v[0] for v in good), geo_med=st.median(v[1] for v in good),
                                 rhat_med=st.median(v[2] for v in good), n_reps=len(good), missing=missing)
        else:
            out[(arm, m)] = dict(ess_med=None, missing=3)

rows = []
hdr = f"{'model':36s} {'rec':>18s} {'fold':>18s} {'auto':>18s}"
print(hdr); print('-'*len(hdr))
fails = {a: 0 for a in ARMS}
for m in models:
    cells = []
    for arm in ARMS:
        o = out.get((arm, m), {})
        if o.get('ess_med') is None:
            cells.append('ABORT'.rjust(18)); fails[arm] += 1
        else:
            cells.append(f"{o['ess_med']:6.0f}/{o['rhat_med']:.3f}".rjust(18))
            if o['rhat_med'] > 1.01: fails[arm] += 1
    print(f"{m:36s} {cells[0]} {cells[1]} {cells[2]}")
print(f"\nR-hat>1.01 or abort: rec={fails['rec']} fold={fails['fold']} auto={fails['auto']} (of {len(models)})")
# geomean ESS over passing models
import math
for arm in ARMS:
    gs = [out[(arm,m)]['geo_med'] for m in models if out.get((arm,m),{}).get('geo_med') and out[(arm,m)]['rhat_med']<=1.01]
    if gs: print(f"{arm}: geo ESS over {len(gs)} passing = {math.exp(sum(math.log(g) for g in gs)/len(gs)):.0f}")
json.dump({f"{a}__{m}": v for (a,m),v in out.items()}, open(ROOT/'results/w17_summary.json','w'), indent=1)
print("saved results/w17_summary.json")
