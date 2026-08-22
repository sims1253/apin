#!/usr/bin/env python3
"""W-32 diagnostics: is the patched-model gradient wrong, or is this FP
cancellation + FD noise? Controls:
 1. FD (central) vs STOCK model on the exact points/components where patched
    looked off — if stock shows the same FD gaps, it's FD truncation.
 2. stock-vs-patched: abs diff + component magnitudes (cancellation check).
 3. Richardson-extrapolated FD (h, h/2) on the worst components.
"""
import random
from pathlib import Path

import numpy as np
import bridgestan

ROOT = Path('/home/m0hawk/Documents/apin/stan')
DATA = str(ROOT / 'data/kronecker_gp.json')
stock = bridgestan.StanModel(str(ROOT / 'scratch/w32/stock_build/kronecker_gp_model.so'), DATA)
patch = bridgestan.StanModel(str(ROOT / 'scratch/w32/patched_build/kronecker_gp_model.so'), DATA)
n = stock.param_unc_num()

rng = random.Random('w32-parity-0')
pts = [np.array([rng.gauss(0.0, 1.0) for _ in range(n)]) for _ in range(100)]

# --- stock vs patched: full picture ---
worst = []
for i, x in enumerate(pts):
    lp1, g1 = stock.log_density_gradient(x)
    lp2, g2 = patch.log_density_gradient(x)
    d = np.abs(g1 - g2)
    scale = np.maximum.reduce([np.abs(g1), np.abs(g2), np.full(n, 1e-12)])
    r = d / scale
    j = int(np.argmax(r))
    worst.append((r[j], i, j, g1[j], g2[j], d[j]))
worst.sort(reverse=True)
print('top stock-vs-patched rel diffs (rel, pt, comp, g_stock, g_patch, absdiff):')
for w in worst[:8]:
    print(f'  {w[0]:.3e}  pt {w[1]:3d} comp {w[2]:3d}: {w[3]:+.6e} {w[4]:+.6e} abs {w[5]:.3e}')

# gradient magnitude distribution at the worst point
r0, i0, j0, *_ = worst[0]
x = pts[i0]
lp, g = stock.log_density_gradient(x)
print(f'\npt {i0}: |g| max {np.abs(g).max():.3e}, median {np.median(np.abs(g)):.3e}')

# --- FD control on stock AND patched, worst components ---
def fd(model, x, c, h):
    xp = x.copy(); xp[c] += h
    xm = x.copy(); xm[c] -= h
    return (model.log_density_gradient(xp)[0] - model.log_density_gradient(xm)[0]) / (2 * h)

print('\nFD control (central, h=1e-5): comp: ad_stock, ad_patch, fd_stock, fd_patch')
for rel, i, j, *_ in worst[:6]:
    x = pts[i]
    _, gs = stock.log_density_gradient(x)
    _, gp = patch.log_density_gradient(x)
    h = 1e-5 * max(1.0, abs(x[j]))
    print(f'  pt {i:3d} comp {j:3d}: ad_s {gs[j]:+.6e} ad_p {gp[j]:+.6e} '
          f'fd_s {fd(stock, x, j, h):+.6e} fd_p {fd(patch, x, j, h):+.6e}')

# --- Richardson on the single worst component, both models ---
rel, i, j, *_ = worst[0]
x = pts[i]
print(f'\nRichardson FD at pt {i} comp {j}:')
_, gs = stock.log_density_gradient(x)
_, gp = patch.log_density_gradient(x)
print(f'  ad_stock {gs[j]:+.8e}  ad_patch {gp[j]:+.8e}')
for base in (1e-3, 1e-4):
    f1s, f2s = fd(stock, x, j, base), fd(stock, x, j, base / 2)
    f1p, f2p = fd(patch, x, j, base), fd(patch, x, j, base / 2)
    rich_s = (4 * f2s - f1s) / 3
    rich_p = (4 * f2p - f1p) / 3
    print(f'  h={base:.0e}: fd_stock {f1s:+.6e}->{rich_s:+.6e}  fd_patch {f1p:+.6e}->{rich_p:+.6e}')
