#!/usr/bin/env python3
"""W-53 gate (a): exact-zero gradient parity, stock vs patched .so.
One .so per process (ChainableStack is process-global; layouts differ).
Usage: gate_parity.py <model> <ref|test>   (ref dumps, test compares)
100 deterministic points per model (W-27 scheme).
"""
import sys
import numpy as np
import bridgestan

MODEL, MODE = sys.argv[1], sys.argv[2]
BASE = "/home/m0hawk/Documents/apin/stan/scratch/w53"
DATA = f"/home/m0hawk/Documents/apin/stan/data/{MODEL}.json"
SO = f"{BASE}/model_{MODEL}_{{}}/{MODEL}_model.so"
REF = f"/tmp/w53_ref_{MODEL}.npz"

so = bridgestan.StanModel(SO.format("stock") if MODE == "ref" else SO.format("patched"), DATA)
D = so.param_unc_num()
rng = np.random.default_rng(20260822)
pts = [rng.standard_normal(D) * 0.5 for _ in range(100)]

vals, grads = [], []
for x in pts:
    v, g = so.log_density_gradient(x, propto=True, jacobian=False)
    vals.append(v)
    grads.append(g)

if MODE == "ref":
    np.savez(REF, vals=np.array(vals), grads=np.array(grads))
    print(f"{MODEL} ref saved ({len(pts)} pts, D={D})")
else:
    ref = np.load(REF)
    nv = sum(1 for i in range(len(pts)) if vals[i] != ref["vals"][i])
    ng = sum(1 for i in range(len(pts)) if not np.array_equal(grads[i], ref["grads"][i]))
    status = "PASS" if (nv == 0 and ng == 0) else "FAIL"
    print(f"{MODEL} {status}: value_mismatch={nv}/100 grad_mismatch={ng}/100 (exact-zero gate)")
    sys.exit(0 if status == "PASS" else 1)
