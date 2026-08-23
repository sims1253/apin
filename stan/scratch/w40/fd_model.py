#!/usr/bin/env python3
"""W-40 gate (b), model level: Richardson central FD of logp vs logp_grad AD
at the W-35 parity points (seed 20260822), unconstrained coordinates.
Reports per-component reldiff for the previously-failing components
(var1, bw1, sigma1) plus a full-vector scan on the failing points.
usage: fd_model.py <a.so> [label]
"""
import sys
import numpy as np
import bridgestan

so_path = sys.argv[1]
label = sys.argv[2] if len(sys.argv) > 2 else so_path.split('/')[-2]
ROOT = '/home/m0hawk/Documents/apin/stan'
sm = bridgestan.StanModel(so_path, f'{ROOT}/data/kronecker_gp.json')
d = sm.param_unc_num()
rng = np.random.default_rng(20260822)
pts = rng.standard_normal((20, d))

# previously-failing points from W-35 (FD-inconsistent var1/bw1): 1, 2, 7, 14
FAIL_PTS = [1, 2, 7, 14]
BLOCKS = [('var1', 0), ('bw1', 1), ('sigma1', 437)]
# L components to spot check (largest |g| ones)
def logp(p):
    return float(sm.log_density(p, propto=True, jacobian=False))

def grad(p):
    return sm.log_density_gradient(p, propto=True, jacobian=False)[1]

print(f'== {label} ==')
rows = []
for i in FAIL_PTS:
    p = pts[i]
    g = grad(p)
    for name, idx in BLOCKS:
        for h0 in (1e-4,):
            d1 = (logp(p + h0*np.eye(1, d, idx)[0]) - logp(p - h0*np.eye(1, d, idx)[0])) / (2*h0)
            h1 = h0/2
            d2 = (logp(p + h1*np.eye(1, d, idx)[0]) - logp(p - h1*np.eye(1, d, idx)[0])) / (2*h1)
            rich = (4*d2 - d1)/3
            ad = g[idx]
            rel = abs(rich - ad)/max(1.0, abs(ad))
            rows.append((f'pt{i}', name, rich, ad, rel))
            print(f'pt{i} {name:7s} fd {rich:12.6g}  ad {ad:12.6g}  reldiff {rel:.3e}')
# full-vector scan on pt7: max reldiff over all comps with |ad|>1e-3
i = 7
p = pts[i]
g = grad(p)
mx, mxk = 0.0, None
for idx in range(d):
    if abs(g[idx]) < 1e-3:
        continue
    h = 1e-4
    d1 = (logp(p + h*np.eye(1, d, idx)[0]) - logp(p - h*np.eye(1, d, idx)[0])) / (2*h)
    h1 = h/2
    d2 = (logp(p + h1*np.eye(1, d, idx)[0]) - logp(p - h1*np.eye(1, d, idx)[0])) / (2*h1)
    rich = (4*d2 - d1)/3
    rel = abs(rich - g[idx])/max(1.0, abs(g[idx]))
    if rel > mx:
        mx, mxk = rel, idx
print(f'pt{i} full-scan(|ad|>1e-3): max reldiff {mx:.3e} at comp {mxk}')
