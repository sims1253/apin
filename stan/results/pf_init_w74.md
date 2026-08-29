# W-74 — pf-inits-for-all arm (Pathfinder inits on every model vs default normal inits)

**Verdict: largest measured win of the session cluster (+81.8% aggregate
geoESS at 5.1% wall overhead), but the pre-registered ADOPT gate fails on
two ess_bulk_min drops and two new accel_gp aborts — recommendation is a
CONDITIONAL promote: pf-init workflow + the pending robustness fixes,
then re-gate.** User decision required (workflow change, not sampler code).

## Results (median over reps, pfall vs runs/w36/exp_par baseline)

| model | base geoESS | pfall geoESS | Δ |
|---|---:|---:|---:|
| radon_pp_nc | 2204.7 | 3877.0 | +75.8% |
| bym2_offset_only | 5.9 | 793.2 | **+13274%** |
| hier_2pl | 2673.1 | 2673.1 | 0 (pipeline cross-check ✓) |
| diamonds | 60.3 | 234.3 | **+288.8%** |
| lsat_model | 3128.9 | 3128.9 | 0 (cross-check ✓) |
| accel_gp | 42.6 | 27.3 | −35.9% (2 new aborts) |
| kronecker_gp | 369.7 | 285.7 | −22.7% |
| pilots | 426.4 | 353.3 | −17.1% |
| eight_schools_c | 237.0 | 270.7 | +14.2% |
| lotka_volterra | 1463.4 | 1348.6 | −7.8% |
| **AGGREGATE** | 330.1 | **600.1** | **+81.8%** |

## Gate outcomes

1. Aggregate ≥+20% → PASS (+81.8%).
2. No model ess_bulk_min drop >20% → FAIL (kronecker −47%, eight_schools −45.5%
   medians; both are single-stuck-coordinate metrics, and kronecker's
   baseline median came from only 2 valid reps vs pfall's 3 — noisy, but
   the gate is the gate).
3. PF overhead ≤10% of wall → PASS (29.1s gen amortized vs 569s arm = 5.1%).

## New robustness finding

accel_gp rep0/rep2 ABORT under pf inits (baseline aborted none there):
all four chains complete sampling, then `std::invalid_argument: macro_time
must be in (0, inf)` throws at finalization — i.e., warmup adapted the
step size to a degenerate value on some chain and the freeze validation
kills the whole run AFTER the compute is spent. This is precisely what
draft PR #8 (freeze clamp) exists to convert into an auditable fallback.
Also note: the known normal-init abort cells (kronecker rep0, lotka rep1)
COMPLETED under pf inits, confirming the LKJ-boundary dead-init diagnosis.

## Reading

- The init posture is worth more ESS than every sampler knob tested this
  cluster combined (~20 levers, all ≤ noise or redistributed). bym2 alone
  goes from unusable (5.9) to healthy (793).
- Losses are concentrated where robustness PRs already exist unmerged:
  #8 freeze clamp (accel finalize abort), #9 step-heuristic fix,
  #10 NaN guard, #7 init fail-fast/retry.
- Caveat: pfall bym2 (793) is below the historical pf_full arm (4722);
  different configs, do not equate. Both orders of magnitude above the
  normal-init baseline.

## Recommended decision package for the user

Promote as a workflow default: generate pf inits per suite run (cost ~5%
wall), keep normal-init fallback for trivial models if desired — AND
merge the walnutpie robustness draft PRs (#7/#8/#9/#10) so the residual
failure modes are clamped. Then re-run this grid to re-gate.
