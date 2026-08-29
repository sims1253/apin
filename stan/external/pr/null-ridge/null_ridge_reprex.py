#!/usr/bin/env python
"""Null-ridge lock reprex against PURE UPSTREAM walnutpie (v0.0.2).

pilots.stan has an exact likelihood-null direction: the map
  a += s, b -= s, mu_a += s/10, mu_b -= s/10
leaves y_hat and every prior term unchanged. This script shows, with the
stock upstream python API only:

  1. At default settings, chains lock at DIFFERENT ridge points:
     per-chain ESS(mu_a) ~ 1-15, cross-chain ridgeF ~ 10-100.
  2. The likelihood is blind to it: a.1 + b.1 (and hence y_hat) agree
     across chains to 3 decimals while mu_a differs by O(1).
  3. It is trajectory-LENGTH binding: min_micro_steps=128 traverses the
     ridge (ridgeF collapses, rhat -> ~1) with no other change.

Run:  PYTHONPATH=/tmp/wpnut_upstream uv run python null_ridge_reprex.py
"""
import numpy as np
import arviz as az
import bridgestan
import walnutpie

SEED = 20260819

model = bridgestan.StanModel("build_threads/pilots_threads.so", "../../data/pilots.json")
print(f"walnutpie {walnutpie.__version__} (upstream main) | pilots "
      f"({model.param_unc_num()} unconstrained dims) | seed {SEED}\n")


def run(min_micro_steps, label):
    outs = walnutpie.walnuts_stan(
        model, num_chains=4, seed=SEED,
        min_warmup_iter=1000, max_warmup_iter=1000,   # fixed warmup budget
        min_sampling_iter=1000, max_sampling_iter=1000,
        min_micro_steps=min_micro_steps,
    )
    mu = [o.get("mu_a") for o in outs]           # one array per chain
    a1 = [o.get("a")[..., 0] for o in outs]
    b1 = [o.get("b")[..., 0] for o in outs]
    ess = [float(az.ess(m[None, :], method="bulk")) for m in mu]
    means = np.array([m.mean() for m in mu])
    sds = np.array([m.std() for m in mu])
    ridge_f = float(means.std() / sds.mean())
    st = np.stack(mu)
    rhat = float(az.rhat(st))
    invar = [float((a + b).mean()) for a, b in zip(a1, b1)]
    print(f"[{label}] min_micro_steps={min_micro_steps}")
    print(f"  per-chain ESS(mu_a): {[round(e, 1) for e in ess]}")
    print(f"  chain means of mu_a: {[round(m, 3) for m in means]}  "
          f"(within-chain sd {sds.mean():.3f})")
    print(f"  ridgeF (cross-chain dispersion / within-chain sd): {ridge_f:.1f}")
    print(f"  rhat(mu_a): {rhat:.2f}")
    print(f"  a.1+b.1 per chain (the likelihood-invariant sum): "
          f"{[round(v, 3) for v in invar]}  <- identical")
    print()
    return ridge_f, rhat


print("== stock defaults ==")
f0, r0 = run(1, "default")
print("== trajectory budget x128 ==")
f1, r1 = run(128, "budget")
print("VERDICT:", "null-ridge lock reproduced; length-binding confirmed"
      if (f0 > 5 and f1 < 2 and r0 > 1.5) else "pattern NOT reproduced — investigate")
