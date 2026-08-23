# W-41: freeze-time step clamp — warmup-freeze abort fix (results)

Branch `exp/freeze-clamp` (worktree `external/walnutpie_w41`), off
`exp/safe-adapt-defaults` @ 43b6435. Commit 53daa3e. Pre-change binary =
same worktree built at 43b6435 before the edit (identical compiler,
flags, Eigen fetch).

## Diagnosis (verified against the two W-36 aborting cells)

`AdaptiveWalnuts::sampler()` froze the tuning with the raw
`step_size()` (= `exp(theta_)` of the step adapter) as the frozen
sampler's `macro_time`; `WalnutsSampler`'s ctor runs
`detail::validate_positive(macro_time)` and throws. On both W-36
aborted cells the failure mode is:

- the model returns **lp = -inf at the init position** (no exception —
  `on_logp_exception` never fires; the models legitimately evaluate to
  -inf in an invalid region: kronecker_gp at the rep0/chain_0 init,
  lotka_volterra (ODE) at the rep1/chain_0 init);
- the within-orbit acceptance statistic becomes `exp(-(h1 - h0))` with
  both Hamiltonians +inf → **NaN**; the adapter (Adam) NaNs on its very
  first update — `step = -nan` from warmup iteration 0 (WALNUTPIE_
  DEBUG_WARMUP trace: step=-nan, lp=-inf, position constant for all
  1000 iterations — the chain is pinned at the init);
- at the freeze (end of iteration 1000 = 32001 logp_grad calls),
  `validate_positive(NaN)` throws `macro_time must be in (0, inf)` →
  `std::terminate` → whole-run abort.

So the exact degenerate value is **NaN** on both cells (not 0, not inf).
Same-family exposure: `walnuts_with_reinit` (api.hpp) reseeds outlier
chains with `ar.step_bar` = geometric mean of per-chain `exp(log_step)`
— degenerate if any chain's log step underflowed to -inf/NaN.

## Fix (minimal, init-robustness-clamp spirit)

At freeze in `sampler()`: validate `step_size()`; if not finite-positive,
fall back in order:
(a) the last finite-positive step observed during warmup — tracked per
iteration (`note_step_()`, a pure read of `opt_.step_size()`, no warmup
arithmetic changed), seeded with the init step;
(b) `find_reasonable_step` re-derivation at the current position with the
current metric, init step as probe seed;
(c) documented hard floor `1000 * DBL_MIN` (~2.2e-305).

Computed once and cached (repeated `sampler()` calls, e.g. the W-28 pilot
gate, stay stable); `on_warmup_complete` reports the value actually
frozen; one stderr line `WALNUTS WARNING: freeze step size degenerate
(step_size()=...); falling back to ... (source); warmup iterations=...`
(harness logs capture stderr; ChainHandler has no warning hook — the
stderr channel is the deliberate auditable choice, pre-registered).

api.hpp reinit path: degenerate `ar.step_bar` → geometric mean of the
just-frozen per-chain `macro_time()` (finite positive by construction
post-clamp), else the round's init step, else the floor; same warning.
(Library-only path — not exercised by the CLI grid; guarded by
inspection + compile.)

Healthy freezes are untouched: the clamp branch is dead code when
`step_size()` is finite-positive.

## Gate (a): bit-identity canary — PASS

Default single-chain runs (warmup=1000 draws=1000, CLI defaults),
seeds 20260819+c, inits per W-36 protocol; md5 of draw CSVs pre vs post:

| model (init source)                | chains | md5 identical | warnings post |
|------------------------------------|--------|---------------|---------------|
| hier_2pl (inits_w25 pf)            | 4      | 4/4           | 0             |
| lsat_model (inits_w25 pf)          | 4      | 4/4           | 0             |
| radon_partially_pooled (inits_w36) | 4      | 4/4           | 0             |
| **total**                          | **12** | **12/12**     | **0**         |

## Gate (b): recovery of the two aborting cells — PASS (completion)

CLI defaults, warmup=1000 draws=1000, inits_w36 chain_0.txt,
seeds 20260819+1000·rep+0. Pre-change: rc=134 (std::invalid_argument).
Post-change:

| cell                    | seed    | rc | draws | degenerate value | fallback used                        |
|-------------------------|---------|----|-------|------------------|--------------------------------------|
| kronecker_gp rep0 c0    | 20260819| 0  | 1000  | NaN (`-nan`)     | 1 = "last finite warmup step size"   |
| lotka_volterra rep1 c0  | 20261819| 0  | 1000  | NaN (`-nan`)     | 1 = "last finite warmup step size"   |

Warning line (both cells):
`WALNUTS WARNING: freeze step size degenerate (step_size()=-nan); falling back to 1 (last finite warmup step size); warmup iterations=1000`
— fallback (a) resolves to the init-step seed (1.0, the CLI default)
because the adapter NaN'd at iteration 0, before any finite warmup step
existed. Chains 1–3 of both cells rerun post-change: rc=0, **zero
warnings** (clamp dead code on healthy chains).

Quality of the recovered 4-chain sets (informational, honestly garbage —
the recovered chain 0 never left its -inf init):
- kronecker_gp rep0: bulk-ESS min 5.34, tail-ESS min 4.03, R-hat max
  2.125. Recovered chain 0 is fully pinned (all 5463 constrained columns
  constant). Healthy W-36 reps of this model: bulk-ESS min ~48, R-hat
  ~1.09.
- lotka_volterra rep1: ESS/R-hat = **NaN** — recovered chain 0 moves
  through the -inf region but every constrained draw is NaN
  (constrain_draw fails there), so the estimator is undefined. Healthy
  W-36 reps: bulk-ESS min ~174, R-hat ~1.02.
A pinned/NaN chain that completes (and is flagged by one loud warning)
beats a silent whole-run abort: the other 3 chains' draws now land
instead of being destroyed. The root pathology is the init protocol
hitting a -inf region, not adaptation — recorded for the init-policy
backlog.

## Gate (c): no collateral changes — PASS

Two healthy cells outside the canary set, md5 pre vs post binary:

| cell                                   | md5      | warnings post |
|----------------------------------------|----------|---------------|
| eight_schools_centered rep1 c2 (20261821) | IDENTICAL | 0          |
| diamonds rep2 c1 (20262820)            | IDENTICAL | 0            |

## Repro

```
# abort (pre-change binary at 43b6435) / recovery (post-change):
OMP_NUM_THREADS=1 external/walnutpie_w41/build_w41/examples/stan_cli \
  bs_models_threads/model_kronecker_gp.so data/kronecker_gp.json \
  --seed 20260819 --init-file inits_w36/kronecker_gp/rep0/chain_0.txt \
  --output <out>.csv --warmup 1000 --samples 1000
# step trajectory evidence: WALNUTPIE_DEBUG_WARMUP=25 in the env
```
Raw runs: runs/w41/{pre,post}/ (untracked). ESS script:
scratch/w41_ess.py (arviz, same procedure as analyze_w36.py).
