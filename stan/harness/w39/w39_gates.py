import random, statistics, time
from pathlib import Path
import numpy as np
import bridgestan

ROOT = Path('/home/m0hawk/Documents/apin/stan')
DATA = str(ROOT / 'data/kronecker_gp.json')
stock = bridgestan.StanModel(str(ROOT / 'scratch/w39/so_stock/kronecker_gp_model.so'), DATA)
fused = bridgestan.StanModel(str(ROOT / 'scratch/w39/so_fused/kronecker_gp_model.so'), DATA)
n = stock.param_unc_num()
rng = random.Random('w39-parity-0')
pts = [np.array([rng.gauss(0.0, 1.0) for _ in range(n)]) for _ in range(50)]

# gate (a) parity: fused (patched stanc --O1) vs stock (vanilla develop --O1)
# pre-registered bar: bit-identical (max rel-L2 exactly 0.0)
lps, l2w, cosw, bitexact_g, bitexact_lp = 0.0, 0.0, 1.0, True, True
for x in pts:
    lp1, g1 = stock.log_density_gradient(x)
    lp2, g2 = fused.log_density_gradient(x)
    bitexact_lp &= (lp1 == lp2)
    bitexact_g &= bool(np.array_equal(g1, g2))
    lps = max(lps, abs(lp1 - lp2) / max(abs(lp1), 1e-300))
    l2w = max(l2w, np.linalg.norm(g1 - g2) / np.linalg.norm(g1))
    cosw = min(cosw, float(g1 @ g2 / (np.linalg.norm(g1) * np.linalg.norm(g2))))
print(f'fused vs stock (50 random pts): max rel logp {lps:.2e}, worst rel-L2 {l2w:.2e}, worst cos {cosw:.12f}')
print(f'bit-identical: logp {bitexact_lp}, gradient {bitexact_g}')

# constrained outputs too (write_array path shares the fused code)
for x in pts[:10]:
    q1 = stock.param_constrain(x)
    q2 = fused.param_constrain(x)
    assert np.array_equal(q1, q2), 'constrained draws differ!'
print('constrained outputs bit-identical on 10 pts: True')

# gate (c) timing: 2 arms interleaved, 3 reps, posterior-cloud points
pts_t = [pts[0] + np.array([rng.gauss(0.0, 0.25) for _ in range(n)]) for _ in range(100)]
reps = {'stock': [], 'fused': []}
for rep in range(3):
    arms = [('stock', stock), ('fused', fused)]
    for name, model in (arms if rep % 2 == 0 else arms[::-1]):
        for x in pts_t[:5]:
            model.log_density_gradient(x)
        t0 = time.perf_counter()
        for x in pts_t:
            model.log_density_gradient(x)
        reps[name].append((time.perf_counter() - t0) / len(pts_t) * 1e6)
meds = {}
for a in ('stock', 'fused'):
    meds[a] = statistics.median(reps[a])
    print(f'{a:6s} us/call reps: {[f"{v:.1f}" for v in reps[a]]}  median {meds[a]:.1f}')
print(f'fused/stock {meds["fused"]/meds["stock"]:.4f}')
