import random, statistics, time
from pathlib import Path
import numpy as np
import bridgestan

ROOT = Path('/home/m0hawk/Documents/apin/stan')
for m, data in (('vec_normal', 'vec_normal.data.json'), ('vec_bern', 'vec_bern.data.json')):
    a = bridgestan.StanModel(str(ROOT / f'scratch/w39/vec/{m}_O1/{m}_model.so'), str(ROOT / f'scratch/w39/{data}'))
    b = bridgestan.StanModel(str(ROOT / f'scratch/w39/vec/{m}_Oexp/{m}_model.so'), str(ROOT / f'scratch/w39/{data}'))
    n = a.param_unc_num()
    rng = random.Random(f'w39-vec-{m}')
    pts = [np.array([rng.gauss(0.0, 1.0) for _ in range(n)]) for _ in range(50)]
    lps, l2w, bit = 0.0, 0.0, True
    for x in pts:
        lp1, g1 = a.log_density_gradient(x)
        lp2, g2 = b.log_density_gradient(x)
        bit &= (lp1 == lp2) and bool(np.array_equal(g1, g2))
        lps = max(lps, abs(lp1 - lp2) / max(abs(lp1), 1e-300))
        l2w = max(l2w, np.linalg.norm(g1 - g2) / max(np.linalg.norm(g1), 1e-300))
    print(f'{m}: O1 vs Oexp on 50 pts: max rel logp {lps:.2e}, worst rel-L2 {l2w:.2e}, bit-identical {bit}')
    reps = {'O1': [], 'Oexp': []}
    for rep in range(3):
        arms = [('O1', a), ('Oexp', b)]
        for name, model in (arms if rep % 2 == 0 else arms[::-1]):
            for x in pts[:5]:
                model.log_density_gradient(x)
            t0 = time.perf_counter()
            for _ in range(10):
                for x in pts:
                    model.log_density_gradient(x)
            reps[name].append((time.perf_counter() - t0) / (10 * len(pts)) * 1e6)
    ma, mb = statistics.median(reps['O1']), statistics.median(reps['Oexp'])
    print(f'{m}: us/call O1 median {ma:.2f} (reps {[f"{v:.2f}" for v in reps["O1"]]}), Oexp median {mb:.2f} (reps {[f"{v:.2f}" for v in reps["Oexp"]]}), ratio {mb/ma:.3f}')
