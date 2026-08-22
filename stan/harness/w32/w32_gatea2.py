import random
from pathlib import Path
import numpy as np
import bridgestan

ROOT = Path('/home/m0hawk/Documents/apin/stan')
DATA = str(ROOT / 'data/kronecker_gp.json')
stock = bridgestan.StanModel(str(ROOT / 'scratch/w32/stock_build/kronecker_gp_model.so'), DATA)
patch = bridgestan.StanModel(str(ROOT / 'scratch/w32/patched_build/kronecker_gp_model.so'), DATA)
n = stock.param_unc_num()
x0 = np.loadtxt(str(ROOT / 'inits_w27/kronecker_gp/rep0/chain_0.txt'))

def fd(model, x, c, h=1e-5):
    xp = x.copy(); xp[c] += h
    xm = x.copy(); xm[c] -= h
    return (model.log_density_gradient(xp)[0] - model.log_density_gradient(xm)[0]) / (2 * h)

def relmax(a, b):
    m = np.maximum.reduce([np.abs(a), np.abs(b), np.full(n, 1e-12)])
    return float((np.abs(a - b) / m).max())

print('sigma   stock-vs-patch   FD-vs-stock   FD-vs-patch   (matched pts/comps: 5 pts x 8 comps)')
for sigma in (0.0, 0.01, 0.05, 0.1, 0.25):
    rng = random.Random(f'w32-triple-{sigma}')
    pts = [x0 if sigma == 0 else x0 + np.array([rng.gauss(0, sigma) for _ in range(n)]) for _ in range(5)]
    sp = fs = fp_ = 0.0
    for x in pts:
        _, gs = stock.log_density_gradient(x)
        _, gp = patch.log_density_gradient(x)
        sp = max(sp, relmax(gs, gp))
        for c in rng.sample(range(n), 8):
            h = 1e-5 * max(1.0, abs(x[c]))
            f = fd(stock, x, c, h)
            fs = max(fs, abs(f - gs[c]) / max(abs(f), abs(gs[c]), 1e-8))
            fp_ = max(fp_, abs(f - gp[c]) / max(abs(f), abs(gp[c]), 1e-8))
    print(f'{sigma:<7} {sp:<16.2e} {fs:<13.2e} {fp_:<13.2e}')
