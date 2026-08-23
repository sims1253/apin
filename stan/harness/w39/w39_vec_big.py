import random, statistics, time
from pathlib import Path
import numpy as np
import bridgestan

ROOT = Path('/home/m0hawk/Documents/apin/stan')
a = bridgestan.StanModel(str(ROOT / 'scratch/w39/vec/vec_normal_big_O1/vec_normal_model.so'), str(ROOT / 'scratch/w39/vec_normal_big.data.json'))
b = bridgestan.StanModel(str(ROOT / 'scratch/w39/vec/vec_normal_big_Oexp/vec_normal_model.so'), str(ROOT / 'scratch/w39/vec_normal_big.data.json'))
n = a.param_unc_num()
rng = random.Random('w39-vecbig')
pts = [np.array([rng.gauss(0.0, 1.0) for _ in range(n)]) for _ in range(20)]
lps, l2w, bit = 0.0, 0.0, True
for x in pts:
    lp1, g1 = a.log_density_gradient(x)
    lp2, g2 = b.log_density_gradient(x)
    bit &= (lp1 == lp2) and bool(np.array_equal(g1, g2))
    lps = max(lps, abs(lp1 - lp2) / max(abs(lp1), 1e-300))
    l2w = max(l2w, np.linalg.norm(g1 - g2) / max(np.linalg.norm(g1), 1e-300))
print(f'N=200000: max rel logp {lps:.2e}, worst rel-L2 {l2w:.2e}, bit-identical {bit}')
reps = {'O1': [], 'Oexp': []}
for rep in range(3):
    arms = [('O1', a), ('Oexp', b)]
    for name, model in (arms if rep % 2 == 0 else arms[::-1]):
        for x in pts[:3]:
            model.log_density_gradient(x)
        t0 = time.perf_counter()
        for x in pts:
            model.log_density_gradient(x)
        reps[name].append((time.perf_counter() - t0) / len(pts) * 1e6)
ma, mb = statistics.median(reps['O1']), statistics.median(reps['Oexp'])
print(f'O1 median {ma:.1f} us/call, Oexp median {mb:.1f} us/call, ratio {mb/ma:.3f}')
print('reps O1:', [f"{v:.1f}" for v in reps['O1']], 'Oexp:', [f"{v:.1f}" for v in reps['Oexp']])
