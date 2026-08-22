"""W-34 gate (a): correctness of arm B (GEMM formulation) vs stock hier_2pl.

100 random unconstrained N(0,1) points + 100 posterior-cloud points (pf init
+ sigma 0.25), deterministic rng (W-32 scheme). FD spot-checks (Richardson,
W-27/W-32 method) on both arms.
"""
import random
import numpy as np
import bridgestan

ROOT = '/home/m0hawk/Documents/apin/stan'
DATA = f'{ROOT}/data/hier_2pl.json'

stock = bridgestan.StanModel(f'{ROOT}/scratch/w34/stock_build/hier_2pl_model.so', DATA)
armb = bridgestan.StanModel(f'{ROOT}/scratch/w34/armB_build/hier_2pl_model.so', DATA)
assert stock.param_unc_num() == armb.param_unc_num()
n = stock.param_unc_num()
print(f'n_unc = {n}')
print('names equal:', stock.param_names() == armb.param_names())

x0 = np.loadtxt(f'{ROOT}/inits_w25/hier_2pl/rep0/chain_0.txt')
assert x0.shape[0] == n, (x0.shape, n)

rng = random.Random('w34-parity-0')
pts_rand = [np.array([rng.gauss(0.0, 1.0) for _ in range(n)]) for _ in range(100)]
pts_post = [x0 + np.array([rng.gauss(0.0, 0.25) for _ in range(n)]) for _ in range(100)]


def compare(pts, label):
    lp_max = 0.0
    rel_l2_worst = 0.0
    cos_worst = 1.0
    comp_worst = 0.0  # max abs rel per-component (vs component scale)
    for x in pts:
        lp1, g1 = stock.log_density_gradient(x)
        lp2, g2 = armb.log_density_gradient(x)
        lp_max = max(lp_max, abs(lp1 - lp2) / max(abs(lp1), 1e-300))
        rel_l2_worst = max(rel_l2_worst, np.linalg.norm(g1 - g2) / np.linalg.norm(g1))
        cos_worst = min(cos_worst, float(g1 @ g2 / (np.linalg.norm(g1) * np.linalg.norm(g2))))
        scale = np.maximum(np.abs(g1), 1.0)
        comp_worst = max(comp_worst, float(np.max(np.abs(g1 - g2) / scale)))
    print(f'{label}: max rel logp {lp_max:.3e} | grad rel-L2 worst {rel_l2_worst:.3e} | '
          f'cos worst {cos_worst:.12f} | max rel comp (|g|>1 floor) {comp_worst:.3e}')


compare(pts_rand, '100 random N(0,1) pts ')
compare(pts_post, '100 posterior-cloud pts ')

# absolute logp diff too (the gate is ~1e-12)
lp_abs = 0.0
for x in pts_rand[:20]:
    lp1 = stock.log_density(x)
    lp2 = armb.log_density(x)
    lp_abs = max(lp_abs, abs(lp1 - lp2))
print(f'max ABS logp diff (20 random pts): {lp_abs:.3e}')

# FD spot-checks: Richardson central differences, both arms, matched components
# blocks: theta[0], theta[599], xi1[0], xi2[7], mu[0], mu[1], tau[0](log-space), L_Omega[0]
comps = [0, 599, 600, 600 + 31 + 7, 664, 665, 666, 668]
print('FD spot-check (Richardson h, h/2): comp  stock_AD   armB_AD    FD_stock   FD_armB   |stock-FD| |armB-FD|')
rngfd = random.Random('w34-fd-0')
for trial in range(3):
    x = pts_rand[trial]
    for c in comps:
        def fd(model, h):
            xp = x.copy(); xp[c] += h
            xm = x.copy(); xm[c] -= h
            return (model.log_density(xp) - model.log_density(xm)) / (2 * h)
        h = 1e-4 * max(1.0, abs(x[c]))
        _, g1 = stock.log_density_gradient(x)
        _, g2 = armb.log_density_gradient(x)
        f1 = (4 * fd(stock, h) - fd(stock, 2 * h)) / 3.0
        f2 = (4 * fd(armb, h) - fd(armb, 2 * h)) / 3.0
        print(f'  t{trial} c{c:4d}  {g1[c]:+10.5f} {g2[c]:+10.5f} {f1:+10.5f} {f2:+10.5f} '
              f'  {abs(g1[c]-f1):.2e}  {abs(g2[c]-f2):.2e}')
