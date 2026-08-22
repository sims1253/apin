#!/usr/bin/env python3
"""W-32 gate (a), revised after the ill-conditioning finding:

Random N(0,1) unconstrained points put Sigma1 (30x30 exp-quad kernel) in a
numerically rank-deficient regime where EIGENVECTOR ADJOINTS are ill-conditioned
for ANY implementation (stock AD does not match FD there either; see
w32_diag.py). The sampler operates near the posterior, so the gate that matters:

  points = inits_w27 init + Gaussian clouds (sigma = 0.05 / 0.1 / 0.25 / 0.5),
  25 points each (100 total). Gates per sigma:
    - regime validity: stock AD vs central FD on sampled components agrees
    - parity: max rel grad diff stock vs patched < 1e-9 (pre-registered)
    - logp identical
"""
import random
import time
from pathlib import Path

import numpy as np
import bridgestan

ROOT = Path('/home/m0hawk/Documents/apin/stan')
DATA = str(ROOT / 'data/kronecker_gp.json')
stock = bridgestan.StanModel(str(ROOT / 'scratch/w32/stock_build/kronecker_gp_model.so'), DATA)
patch = bridgestan.StanModel(str(ROOT / 'scratch/w32/patched_build/kronecker_gp_model.so'), DATA)
n = stock.param_unc_num()
x0 = np.loadtxt(str(ROOT / 'inits_w27/kronecker_gp/rep0/chain_0.txt'))
assert x0.size == n

rng = random.Random('w32-posterior-0')


def abs_rel(a, b):
    m = np.maximum.reduce([np.abs(a), np.abs(b), np.full_like(a, 1e-12)])
    return np.abs(a - b) / m


for sigma in (0.05, 0.1, 0.25, 0.5):
    lps, gmax, nfin = 0.0, 0.0, 0
    worst = None
    for k in range(25):
        x = x0 + np.array([rng.gauss(0.0, sigma) for _ in range(n)])
        lp1, g1 = stock.log_density_gradient(x)
        lp2, g2 = patch.log_density_gradient(x)
        if not (np.isfinite(lp2) and np.all(np.isfinite(g2))):
            nfin += 1
            continue
        lps = max(lps, abs(lp1 - lp2) / max(abs(lp1), 1e-300))
        r = abs_rel(g1, g2)
        j = int(np.argmax(r))
        if worst is None or r[j] > worst[0]:
            worst = (r[j], k, j, g1[j], g2[j])
        gmax = max(gmax, r[j])
    print(f'sigma={sigma:<5}: max rel logp {lps:.2e}  max rel grad {gmax:.2e}  '
          f'(worst: pt {worst[1]} comp {worst[2]}: {worst[3]:+.4e} vs {worst[4]:+.4e})  nonfinite {nfin}')

# regime validity: FD vs stock AND patched at posterior-region points
print('\nFD regime check (central h=1e-5, 3 pts x 10 comps), sigma=0.1:')
rng2 = random.Random('w32-fdreg-0')
worst_s, worst_p = 0.0, 0.0
for k in range(3):
    x = x0 + np.array([rng2.gauss(0.0, 0.1) for _ in range(n)])
    _, gs = stock.log_density_gradient(x)
    _, gp = patch.log_density_gradient(x)
    for c in rng2.sample(range(n), 10):
        h = 1e-5 * max(1.0, abs(x[c]))
        xp = x.copy(); xp[c] += h
        xm = x.copy(); xm[c] -= h
        fd = (patch.log_density_gradient(xp)[0] - patch.log_density_gradient(xm)[0]) / (2 * h)
        worst_s = max(worst_s, abs(fd - gs[c]) / max(abs(fd), abs(gs[c]), 1e-8))
        worst_p = max(worst_p, abs(fd - gp[c]) / max(abs(fd), abs(gp[c]), 1e-8))
print(f'  worst rel FD-vs-stock {worst_s:.2e}   FD-vs-patched {worst_p:.2e}')
