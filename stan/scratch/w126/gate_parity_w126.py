#!/usr/bin/env python3
"""W-126 gate (b) parity: increment-2 hand-edit (value-only tp + scatter
likelihood) gpcm .so vs the STOCK .so (same bundle lineage, same
flags), ctypes C ABI, 100 deterministic points (W-103 scheme:
default_rng(20260822), standard_normal(D) * 0.5).

Also captures the CONSTRAINED output (params + transformed parameters,
i.e. the 11,566 y_hat columns) at each point via bs_param_constrain --
the y_hat output-values-bitwise check, independent of the sampler.

One .so per process (ChainableStack is global).

Usage: gate_parity_w129.py <ref|test>
  ref  -> evaluates the STOCK .so, saves scratch/w129/parity_ref.npz
  test -> evaluates the I2 .so, compares bitwise (np.array_equal)
"""
import ctypes
import sys

import numpy as np

W = "/home/m0hawk/Documents/apin/stan/scratch/w126"
DATA = "/home/m0hawk/Documents/apin/stan/scratch/w80/model_gpcm_latent_reg_irt/data.json"
REF = f"{W}/parity_ref.npz"
SOS = {"ref": W + "/model_gpcm_stock/gpcm_model.so",
       "test": W + "/model_gpcm_prim/gpcm_model.so"}

mode = sys.argv[1]

lib = ctypes.CDLL(SOS[mode])
lib.bs_model_construct.restype = ctypes.c_void_p
lib.bs_model_construct.argtypes = [ctypes.c_char_p, ctypes.c_uint,
                                   ctypes.POINTER(ctypes.c_char_p)]
err = ctypes.c_char_p()
m = lib.bs_model_construct(DATA.encode(), 20260819, ctypes.byref(err))
if not m:
    raise SystemExit(f"construct failed: {err.value}")

lib.bs_param_unc_num.restype = ctypes.c_int
lib.bs_param_unc_num.argtypes = [ctypes.c_void_p]
D = lib.bs_param_unc_num(m)

lib.bs_param_num.restype = ctypes.c_int
lib.bs_param_num.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_bool]
DC = lib.bs_param_num(m, True, False)  # params + tp (y_hat), no gq

lib.bs_log_density_gradient.restype = ctypes.c_int
lib.bs_log_density_gradient.argtypes = [
    ctypes.c_void_p, ctypes.c_bool, ctypes.c_bool,
    ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double),
    ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_char_p)]

lib.bs_param_constrain.restype = ctypes.c_int
lib.bs_param_constrain.argtypes = [
    ctypes.c_void_p, ctypes.c_bool, ctypes.c_bool,
    ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double),
    ctypes.c_void_p, ctypes.POINTER(ctypes.c_char_p)]

rng = np.random.default_rng(20260822)
pts = [rng.standard_normal(D) * 0.5 for _ in range(100)]
vals, grads, cons = [], [], []
for x in pts:
    xv = np.ascontiguousarray(x, dtype=np.float64)
    val = ctypes.c_double()
    grad = np.zeros(D, dtype=np.float64)
    rc = lib.bs_log_density_gradient(
        m, True, False, xv.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        ctypes.byref(val), grad.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        ctypes.byref(err))
    if rc != 0:
        raise SystemExit(f"grad failed rc={rc}: {err.value}")
    vals.append(val.value)
    grads.append(grad.copy())
    out = np.zeros(DC, dtype=np.float64)
    rc = lib.bs_param_constrain(
        m, True, False, xv.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        out.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
        None, ctypes.byref(err))
    if rc != 0:
        raise SystemExit(f"constrain failed rc={rc}: {err.value}")
    cons.append(out)

if mode == "ref":
    np.savez(REF, vals=vals, grads=np.array(grads), cons=np.array(cons))
    print(f"ref saved: {len(vals)} pts, D={D}, DC={DC}")
else:
    r = np.load(REF)
    v_bad = [i for i in range(100) if r["vals"][i] != vals[i]]
    g_bad = [i for i in range(100)
             if not np.array_equal(r["grads"][i], grads[i])]
    c_bad = [i for i in range(100) if not np.array_equal(r["cons"][i], cons[i])]
    print(f"lp bitwise mismatches: {len(v_bad)}/100")
    print(f"gradient-vector bitwise mismatches: {len(g_bad)}/100")
    print(f"constrained-output (incl y_hat) mismatches: {len(c_bad)}/100")
    if g_bad:
        i = g_bad[0]
        d = np.nonzero(r["grads"][i] != grads[i])[0]
        ulps = np.abs(r["grads"][i][d] - grads[i][d]) / np.spacing(
            np.abs(r["grads"][i][d]))
        print(f"first bad pt {i}: {len(d)} components differ, max ulp {ulps.max():.3g}")
        print("differing component indices:", d[:50])
    if c_bad:
        i = c_bad[0]
        d = np.nonzero(r["cons"][i] != cons[i])[0]
        print(f"first bad constrained pt {i}: {len(d)} cols differ (first 10: {d[:10]})")
