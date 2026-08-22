import random, statistics, time
from pathlib import Path
import numpy as np
import bridgestan

ROOT = Path('/home/m0hawk/Documents/apin/stan')
DATA = str(ROOT / 'data/kronecker_gp.json')
stock = bridgestan.StanModel(str(ROOT / 'scratch/w32/stock_build/kronecker_gp_model.so'), DATA)
patch = bridgestan.StanModel(str(ROOT / 'scratch/w32/patched_build/kronecker_gp_model.so'), DATA)
n = stock.param_unc_num()
x0 = np.loadtxt(str(ROOT / 'inits_w27/kronecker_gp/rep0/chain_0.txt'))
rng = random.Random('w32-timing-0')
pts = [x0 + np.array([rng.gauss(0.0, 0.25) for _ in range(n)]) for _ in range(100)]

reps = {'stock': [], 'patch': []}
for rep in range(3):
    # interleave arms within each rep, alternate who goes first
    arms = [('stock', stock), ('patch', patch)] if rep % 2 == 0 else [('patch', patch), ('stock', stock)]
    for name, model in arms:
        for x in pts[:5]:
            model.log_density_gradient(x)
        t0 = time.perf_counter()
        for x in pts:
            model.log_density_gradient(x)
        reps[name].append((time.perf_counter() - t0) / len(pts) * 1e6)
for a in ('stock', 'patch'):
    med = statistics.median(reps[a])
    print(f'{a:6s} us/call reps: {[f"{v:.1f}" for v in reps[a]]}  median {med:.1f}')
ms, mp = statistics.median(reps['stock']), statistics.median(reps['patch'])
print(f'ratio patched/stock: {mp/ms:.4f}  -> saved {1 - mp/ms:.1%}')
