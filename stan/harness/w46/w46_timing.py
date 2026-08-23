"""W-46 gate (b) wall timing: per-call logp_grad us, stock vs patched (island)
vs patched_base, 100 identical posterior-cloud points, 3 interleaved reps,
medians. W-34 gate-b protocol."""
import time
import numpy as np
import bridgestan

BASE = "/home/m0hawk/Documents/apin/stan"
models = {
    "stock": f"{BASE}/scratch/w46/stock_build/hier_2pl_model.so",
    "island": f"{BASE}/scratch/w46/patched_build/hier_2pl_model.so",
    "base": f"{BASE}/scratch/w46/patched_base_build/hier_2pl_model.so",
}
sms = {k: bridgestan.StanModel(v, data=f"{BASE}/data/hier_2pl.json")
       for k, v in models.items()}

u0 = np.loadtxt(f"{BASE}/inits_w25/hier_2pl/rep0/chain_0.txt")
rng = np.random.default_rng(3446)
pts = [u0 + 0.25 * rng.standard_normal(u0.size) for _ in range(100)]

# warmup
for sm in sms.values():
    for x in pts[:10]:
        sm.log_density_gradient(x, jacobian=False)

R = 3
times = {k: np.zeros(R) for k in sms}
for rep in range(R):
    for k, sm in sms.items():
        t0 = time.perf_counter()
        for x in pts:
            sm.log_density_gradient(x, jacobian=False)
        times[k][rep] = (time.perf_counter() - t0) / len(pts) * 1e6

med = {k: float(np.median(v)) for k, v in times.items()}
for k in sms:
    print(f"{k:7s} us/call per rep: " + " ".join(f"{t:8.1f}" for t in times[k])
          + f"   median {med[k]:8.1f}")
print(f"island/stock = {med['island']/med['stock']:.3f}x   "
      f"base/stock = {med['base']/med['stock']:.3f}x")
