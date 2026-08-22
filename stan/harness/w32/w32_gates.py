#!/usr/bin/env python3
"""W-32 gate (a) correctness + gate (b) per-call timing for the eigh-reuse
prototype on kronecker_gp.

Stock arm:   scratch/w32/stock_build/kronecker_gp_model.so  (fresh default build)
Patched arm: scratch/w32/patched_build/kronecker_gp_model.so (w32_eigh combined)

Gate a: 100 random unconstrained points (deterministic W-27-style scheme):
  - logp and gradient max REL diff stock vs patched (gate < 1e-9)
  - pipeline sanity: stock_build vs bs_models/model_kronecker_gp.so
  - finite-difference (central) spot-check of the PATCHED gradients
Gate b: serial per-call logp_grad timing, identical points, 3 repeats,
  medians (us/call).
"""
import random
import statistics
import time
from pathlib import Path

import numpy as np
import bridgestan

ROOT = Path('/home/m0hawk/Documents/apin/stan')
W32 = ROOT / 'scratch/w32'
DATA = str(ROOT / 'data/kronecker_gp.json')

SO_STOCK = str(W32 / 'stock_build/kronecker_gp_model.so')
SO_PATCH = str(W32 / 'patched_build/kronecker_gp_model.so')
SO_REPO = str(ROOT / 'bs_models/model_kronecker_gp.so')


def rel_diff(a, b):
    denom = np.maximum(np.abs(a) + np.abs(b), 1e-300)
    return float(np.max(np.abs(a - b) / denom))


def abs_rel(a, b):
    """per-element |a-b| / max(|a|,|b|,tiny) summary"""
    m = np.maximum.reduce([np.abs(a), np.abs(b), np.full_like(a, 1e-12)])
    d = np.abs(a - b) / m
    return float(d.max()), float(np.median(d))


def main():
    stock = bridgestan.StanModel(SO_STOCK, DATA)
    patch = bridgestan.StanModel(SO_PATCH, DATA)
    repo = bridgestan.StanModel(SO_REPO, DATA)
    n = stock.param_unc_num()
    print(f'unconstrained dim: {n}')

    rng = random.Random('w32-parity-0')
    pts = [np.array([rng.gauss(0.0, 1.0) for _ in range(n)]) for _ in range(100)]

    # ---- pipeline sanity: fresh stock vs repo bs_models .so ----
    max_lp = 0.0
    max_g = 0.0
    for x in pts:
        lp1, g1 = repo.log_density_gradient(x)
        lp2, g2 = stock.log_density_gradient(x)
        max_lp = max(max_lp, abs(lp1 - lp2) / max(abs(lp1), 1e-300))
        max_g = max(max_g, rel_diff(g1, g2))
    print(f'[sanity] repo vs fresh stock: max rel logp {max_lp:.3e}, max rel grad {max_g:.3e}')

    # ---- gate a: stock vs patched ----
    lps, gmax, gmed, nbad = 0.0, 0.0, 0.0, 0
    for x in pts:
        lp1, g1 = stock.log_density_gradient(x)
        lp2, g2 = patch.log_density_gradient(x)
        if not np.all(np.isfinite(g2)) or not np.isfinite(lp2):
            nbad += 1
            continue
        lps = max(lps, abs(lp1 - lp2) / max(abs(lp1), 1e-300))
        mx, md = abs_rel(g1, g2)
        gmax = max(gmax, mx)
        gmed = max(gmed, md)
    print(f'[gate a] stock vs patched, 100 pts: max rel logp {lps:.3e}, '
          f'max rel grad {gmax:.3e} (median elem rel {gmed:.3e}), nonfinite {nbad}')

    # ---- finite differences on the PATCHED model (central, W-27 style) ----
    rngfd = random.Random('w32-fd-0')
    worst = 0.0
    details = []
    for pi in (0, 17, 42, 99):
        x = pts[pi].copy()
        _, g = patch.log_density_gradient(x)
        comps = sorted(rngfd.sample(range(n), 12))
        for c in comps:
            h = 1e-5 * max(1.0, abs(x[c]))
            xp = x.copy(); xp[c] += h
            xm = x.copy(); xm[c] -= h
            lp_p, _ = patch.log_density_gradient(xp)   # need logp only; logp_grad ok
            lp_m, _ = patch.log_density_gradient(xm)
            fd = (lp_p - lp_m) / (2 * h)
            ad = g[c]
            r = abs(fd - ad) / max(abs(fd), abs(ad), 1e-8)
            worst = max(worst, r)
            details.append((pi, c, fd, ad, r))
    print(f'[gate a fd] patched vs central FD, 4 pts x 12 comps: worst rel {worst:.3e}')
    for pi, c, fd, ad, r in sorted(details, key=lambda t: -t[-1])[:5]:
        print(f'   pt {pi:3d} comp {c:3d}: fd {fd:+.6e} ad {ad:+.6e} rel {r:.2e}')

    # ---- gate b: serial per-call timing ----
    # identical points for both arms, interleaved arms per repeat, 3 repeats
    tim_pts = pts[:50]
    reps = {'stock': [], 'patch': []}
    for rep in range(3):
        for arm, model in (('stock', stock), ('patch', patch)):
            for x in tim_pts[:5]:
                model.log_density_gradient(x)  # warm pages/touch
            t0 = time.perf_counter()
            for x in tim_pts:
                model.log_density_gradient(x)
            dt = time.perf_counter() - t0
            reps[arm].append(dt / len(tim_pts) * 1e6)
    med_s = statistics.median(reps['stock'])
    med_p = statistics.median(reps['patch'])
    print(f'[gate b] us/call stock   reps {[f"{v:.1f}" for v in reps["stock"]]} median {med_s:.1f}')
    print(f'[gate b] us/call patched reps {[f"{v:.1f}" for v in reps["patch"]]} median {med_p:.1f}')
    print(f'[gate b] ratio patched/stock {med_p/med_s:.4f}  (1 - ratio = {1 - med_p/med_s:.1%} saved)')


if __name__ == '__main__':
    main()
