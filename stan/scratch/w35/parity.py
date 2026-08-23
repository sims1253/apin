#!/usr/bin/env python
"""W-35: gradient parity between two kronecker_gp .so builds on N random points.
Reports: logp max rel; grad max rel; per-block stats (var1,bw1 = 2, L = 435,
sigma1 = 1); count wrong (>tol), sign flips; worst components.
usage: parity.py <a.so> <b.so> [N] [seed]
"""
import sys
import numpy as np
import bridgestan

a_so, b_so = sys.argv[1], sys.argv[2]
n = int(sys.argv[3]) if len(sys.argv) > 3 else 20
seed = int(sys.argv[4]) if len(sys.argv) > 4 else 20260822
data = '/home/m0hawk/Documents/apin/stan/data/kronecker_gp.json'
sa = bridgestan.StanModel(a_so, data)
sb = bridgestan.StanModel(b_so, data)
assert sa.param_unc_num() == sb.param_unc_num()
d = sa.param_unc_num()
rng = np.random.default_rng(seed)
pts = rng.standard_normal((n, d))
blocks = [('var1', 0, 1), ('bw1', 1, 2), ('L', 2, 437), ('sigma1', 437, 438)]
worst = []
for i, p in enumerate(pts):
    la, ga = sa.log_density_gradient(p)
    lb, gb = sb.log_density_gradient(p)
    if not np.isfinite(la):
        continue
    dl = abs(lb - la) / max(1.0, abs(la))
    gd = np.abs(gb - ga)
    grel = gd / np.maximum(1.0, np.abs(ga))
    flips = int(np.sum((np.sign(gb) != np.sign(ga)) & (gd > 1e-6)))
    nwrong = int(np.sum(grel > 1e-6))
    for name, lo, hi in blocks:
        sub = grel[lo:hi]
        j = int(np.argmax(sub))
        if sub[j] > 1e-6:
            worst.append((grel[j], i, name, lo + j, float(ga[lo + j]), float(gb[lo + j])))
    if i == 0 or dl > 1e-12 or nwrong:
        print(f'pt{i}: logp_rel {dl:.2e} grad_maxrel {grel.max():.3e} '
              f'nwrong(>1e-6) {nwrong}/{d} signflips {flips}')
worst.sort(reverse=True)
print(f'\n== {n} pts summary == worst 5 (rel, pt, block, comp, a, b):')
for w in worst[:5]:
    print(f'  {w[0]:.3e} pt{w[1]} {w[2]}[{w[3]}] {w[4]:+.6g} -> {w[5]:+.6g}')
import collections
cnt = collections.Counter(w[2] for w in worst)
print('components>1e-6 per block:', dict(cnt))
