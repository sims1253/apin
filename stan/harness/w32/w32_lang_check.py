import random, statistics, time
from pathlib import Path
import numpy as np
import bridgestan

ROOT = Path('/home/m0hawk/Documents/apin/stan')
DATA = str(ROOT / 'data/kronecker_gp.json')
stock = bridgestan.StanModel(str(ROOT / 'scratch/w32/stock_build/kronecker_gp_model.so'), DATA)
patch = bridgestan.StanModel(str(ROOT / 'scratch/w32/patched_build/kronecker_gp_model.so'), DATA)
lang = bridgestan.StanModel(str(ROOT / 'scratch/w32/lang_build/kronecker_gp_model.so'), DATA)
n = stock.param_unc_num()
x0 = np.loadtxt(str(ROOT / 'inits_w27/kronecker_gp/rep0/chain_0.txt'))
rng = random.Random('w32-parity-0')
pts = [np.array([rng.gauss(0.0, 1.0) for _ in range(n)]) for _ in range(100)]

# parity: lang vs stock, and lang vs hand-patched (logp + gradient vector metrics)
for name, other in (('lang', lang),):
    lps, l2w, cosw = 0.0, 0.0, 1.0
    for x in pts:
        lp1, g1 = stock.log_density_gradient(x)
        lp2, g2 = other.log_density_gradient(x)
        lps = max(lps, abs(lp1 - lp2) / max(abs(lp1), 1e-300))
        l2w = max(l2w, np.linalg.norm(g1 - g2) / np.linalg.norm(g1))
        cosw = min(cosw, float(g1 @ g2 / (np.linalg.norm(g1) * np.linalg.norm(g2))))
    print(f'lang vs stock (100 random pts): max rel logp {lps:.2e}, worst rel-L2 {l2w:.2e}, worst cos {cosw:.12f}')
# lang vs patched agreement at the init
lp1, g1 = patch.log_density_gradient(x0)
lp2, g2 = lang.log_density_gradient(x0)
print(f'lang vs handpatch at init: lp equal {lp1 == lp2}, rel-L2 {np.linalg.norm(g1-g2)/np.linalg.norm(g1):.2e}')

# timing: 3 arms interleaved, 3 reps
pts_t = [x0 + np.array([rng.gauss(0.0, 0.25) for _ in range(n)]) for _ in range(100)]
reps = {'stock': [], 'patch': [], 'lang': []}
for rep in range(3):
    arms = [('stock', stock), ('patch', patch), ('lang', lang)]
    for name, model in (arms if rep % 2 == 0 else arms[::-1]):
        for x in pts_t[:5]:
            model.log_density_gradient(x)
        t0 = time.perf_counter()
        for x in pts_t:
            model.log_density_gradient(x)
        reps[name].append((time.perf_counter() - t0) / len(pts_t) * 1e6)
meds = {}
for a in ('stock', 'patch', 'lang'):
    meds[a] = statistics.median(reps[a])
    print(f'{a:6s} us/call reps: {[f"{v:.1f}" for v in reps[a]]}  median {meds[a]:.1f}')
print(f'patched/stock {meds["patch"]/meds["stock"]:.4f}  lang/stock {meds["lang"]/meds["stock"]:.4f}')
