#!/usr/bin/env python3
"""W-53 measurement: hier_2pl per-call logp_grad microseconds.
Interleaved: 3 rounds x (stock, patched) subprocesses, each 3 internal
reps of 50 deterministic points. One arm per process (ChainableStack
layout differs). Protocol adapted from W-47 model_probe.py.
"""
import subprocess, sys, statistics

BASE = "/home/m0hawk/Documents/apin/stan/scratch/w53"

CHILD = '''
import sys, time, statistics
import numpy as np
import bridgestan
arm = sys.argv[1]
BASE = "/home/m0hawk/Documents/apin/stan/scratch/w53"
so = bridgestan.StanModel(f"{BASE}/model_hier_2pl_{arm}/hier_2pl_model.so",
                          "/home/m0hawk/Documents/apin/stan/data/hier_2pl.json")
D = so.param_unc_num()
rng = np.random.default_rng(20260822)
pts = [rng.standard_normal(D) * 0.5 for _ in range(50)]
for x in pts:  # warm
    so.log_density_gradient(x, propto=True, jacobian=False)
reps = []
for rep in range(3):
    t0 = time.perf_counter()
    for x in pts:
        so.log_density_gradient(x, propto=True, jacobian=False)
    reps.append((time.perf_counter() - t0) / len(pts) * 1e6)
print(arm, " ".join(f"{r:.1f}" for r in reps), statistics.median(reps))
'''

results = {}
for rep in range(3):  # interleave at the process level
    for arm in ["stock", "patched"]:
        r = subprocess.run([sys.executable, "-c", CHILD, arm],
                           capture_output=True, text=True, check=True)
        parts = r.stdout.strip().split("\n")[-1].split()
        results.setdefault(arm, []).extend(float(x) for x in parts[1:4])

for arm in ["stock", "patched"]:
    v = sorted(results[arm])
    print(f"{arm:8s} us/call median {statistics.median(v):8.1f}  reps " +
          " ".join(f"{x:.1f}" for x in v))
s, p = statistics.median(results["stock"]), statistics.median(results["patched"])
print(f"ratio {p/s:.4f}  delta {100*(p/s-1):+.1f}%")
