#!/usr/bin/env python
"""W-21: fixed vs early-exit warmup. ESS + wall per model, medians over reps."""
import subprocess, re, statistics as st, json, math
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
MODELS = ['blr','arma11','dogs_hierarchical','lsat_model','garch11','gp_regr',
          'hier_2pl','kronecker_gp','diamonds','low_dim_gauss_mix',
          'wells_dist100_model','eight_schools_noncentered']
def ess_of(d):
    files = sorted(d.glob('chain_[0-9].csv'))
    if len(files) < 4: return None
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
def wall_of(d):
    f = d/'wall.txt'
    if not f.exists(): return None
    m = re.search(r'wall ([\d.]+)', f.read_text())
    return float(m.group(1)) if m else None
def exit_iter_of(d):
    f = d/'chain_0.log'
    if not f.exists(): return None
    m = re.search(r'Early warmup exit at iteration (\d+)', f.read_text())
    return int(m.group(1)) if m else 1000
out = {}
print(f"{'model':26s} {'fixed ESS/rhat':>16s} {'early ESS/rhat':>16s} {'exit@':>6s} {'wall fx/ea':>14s} {'wallx':>6s}")
ratios = []
for m in MODELS:
    row = {}
    for arm in ['fixed','early']:
        e, w, x = [], [], []
        for rep in range(3):
            d = ROOT/f'runs/w21_{arm}_{m}/rep{rep}'
            if not (d/'DONE').exists(): continue
            v = ess_of(d)
            if v: e.append(v)
            ww = wall_of(d); x.append(exit_iter_of(d))
            if ww: w.append(ww)
        if e:
            row[arm] = (st.median(v[0] for v in e), st.median(v[2] for v in e),
                        st.median(w) if w else None, st.median(x))
    if 'fixed' in row and 'early' in row:
        f, e = row['fixed'], row['early']
        wr = (f[2]/e[2]) if (f[2] and e[2] and e[2] > 0) else None
        if wr: ratios.append(wr)
        print(f"{m:26s} {f[0]:6.0f}/{f[1]:.3f}{'':>4s} {e[0]:6.0f}/{e[1]:.3f}{'':>4s} {e[3]:6.0f} "
              f"{f[2] or 0:6.1f}/{e[2] or 0:6.1f} {wr or 0:6.2f}x")
        out[m] = dict(fixed=row['fixed'], early=row['early'], wall_speedup=wr)
if ratios:
    print(f"\ngeomean wall speedup: {math.exp(sum(math.log(r) for r in ratios)/len(ratios)):.2f}x over {len(ratios)} models")
json.dump(out, open(ROOT/'results/w21_summary.json','w'), indent=1)
print('saved results/w21_summary.json')
