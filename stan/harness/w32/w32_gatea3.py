import numpy as np
import bridgestan
from pathlib import Path

ROOT = Path('/home/m0hawk/Documents/apin/stan')
DATA = str(ROOT / 'data/kronecker_gp.json')
stock = bridgestan.StanModel(str(ROOT / 'scratch/w32/stock_build/kronecker_gp_model.so'), DATA)
patch = bridgestan.StanModel(str(ROOT / 'scratch/w32/patched_build/kronecker_gp_model.so'), DATA)
n = stock.param_unc_num()
x0 = np.loadtxt(str(ROOT / 'inits_w27/kronecker_gp/rep0/chain_0.txt'))

lp1, g1 = stock.log_density_gradient(x0)
lp2, g2 = patch.log_density_gradient(x0)
d = np.abs(g1 - g2)
order = np.argsort(-d)[:10]
print(f'init point: lp identical {lp1 == lp2}; |g|max {np.abs(g1).max():.3e}, |g| median {np.median(np.abs(g1)):.3e}')
print('top ABS diffs: comp  g_stock          g_patch          absdiff         reldiff')
for j in order:
    r = abs(g1[j]-g2[j]) / max(abs(g1[j]), abs(g2[j]), 1e-12)
    print(f'{j:5d}  {g1[j]:+.6e}  {g2[j]:+.6e}  {d[j]:.3e}  {r:.2e}')
print(f'\nabs diffs: max {d.max():.3e}, p99 {np.percentile(d,99):.3e}, median {np.median(d):.3e}')
print(f'abs diff / |g|max: {d.max()/np.abs(g1).max():.2e}')
# named components 0=var1,1=bw1,last=sigma1
for nm, j in (('var1', 0), ('bw1', 1), ('sigma1', n-1)):
    print(f'{nm} (comp {j}): stock {g1[j]:+.6e} patch {g2[j]:+.6e} rel {abs(g1[j]-g2[j])/max(abs(g1[j]),abs(g2[j])):.2e}')

# vector-level equivalence metrics over the posterior cloud
import random
rng = random.Random('w32-vec-0')
for sigma in (0.05, 0.25):
    worst_l2, worst_cos = 0.0, 1.0
    for k in range(10):
        x = x0 + np.array([rng.gauss(0, sigma) for _ in range(n)])
        _, g1 = stock.log_density_gradient(x)
        _, g2 = patch.log_density_gradient(x)
        l2 = np.linalg.norm(g1 - g2) / np.linalg.norm(g1)
        cos = float(g1 @ g2 / (np.linalg.norm(g1) * np.linalg.norm(g2)))
        worst_l2 = max(worst_l2, l2); worst_cos = min(worst_cos, cos)
    print(f'sigma={sigma}: worst rel-L2 {worst_l2:.2e}, worst cos-sim {worst_cos:.12f}')
