"""W-34 gate (b): per-call logp_grad timing, stock vs arm B (GEMM formulation).

100 posterior-cloud points (pf init + N(0, 0.25)), 3 interleaved reps,
medians. W-32 driver pattern. Run under taskset 0-3, machine otherwise idle.
"""
import os
import random
import statistics
import time
import numpy as np
import bridgestan

ROOT = '/home/m0hawk/Documents/apin/stan'
DATA = f'{ROOT}/data/hier_2pl.json'
stock = bridgestan.StanModel(f'{ROOT}/scratch/w34/stock_build/hier_2pl_model.so', DATA)
armb = bridgestan.StanModel(f'{ROOT}/scratch/w34/armB_build/hier_2pl_model.so', DATA)
n = stock.param_unc_num()
x0 = np.loadtxt(f'{ROOT}/inits_w25/hier_2pl/rep0/chain_0.txt')
rng = random.Random('w34-timing-0')
pts = [x0 + np.array([rng.gauss(0.0, 0.25) for _ in range(n)]) for _ in range(100)]

reps = {'stock': [], 'armB': []}
for rep in range(3):
    arms = [('stock', stock), ('armB', armb)]
    for name, model in (arms if rep % 2 == 0 else arms[::-1]):
        for x in pts[:5]:
            model.log_density_gradient(x)
        t0 = time.perf_counter()
        for x in pts:
            model.log_density_gradient(x)
        reps[name].append((time.perf_counter() - t0) / len(pts) * 1e6)
meds = {}
for a in ('stock', 'armB'):
    meds[a] = statistics.median(reps[a])
    print(f'{a:6s} us/call reps: {[f"{v:.1f}" for v in reps[a]]}  median {meds[a]:.1f}')
print(f'armB/stock {meds["armB"]/meds["stock"]:.4f}  (saving {(1-meds["armB"]/meds["stock"])*100:.1f}%)')
print('loadavg:', open('/proc/loadavg').read().strip())
