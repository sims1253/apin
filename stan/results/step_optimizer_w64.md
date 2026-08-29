# W-64 — step-optimizer head-to-head (Adam vs DualAveraging vs AdaBelief)

**Verdict: CONFIRM DEFAULT** — Adam stays. Both alternatives REJECT per
pre-registered gates. Date: 2026-08-25. Preregistration in WORKLOG
(W-64); runner `harness/run_w64.py`, analysis `harness/analyze_w64.py`,
raw JSON `results/step_optimizer_w64_ess.json`.

## Design

Binary `build_w36exp` @43b6435, same grid/seeds/inits as W-36 `exp_par`;
only delta is `--step-optimizer {da,belief}`. All wrapper knobs at CLI
defaults (`batch_stride=1`, `anti-windup=0`, clip off) — verified these
defaults apply uniformly to ALL optimizers including the baseline's Adam,
so this isolates base optimizer choice (stan_cli.cpp:1428–1466 dispatch).
Baseline = existing runs/w36/exp_par. 30 new cells per arm.

## Results (median geoESS over available reps; full data in JSON)

| model | adam | da | Δda | belief | Δbelief |
|---|---:|---:|---:|---:|---:|
| radon_pp_nc | 2204.7 | 1891.6 | −14.2% | 2673.3 | +21.3% |
| bym2_offset_only | 5.9 | ABORT×3 | — | 8.0 | +35.1% |
| hier_2pl | 2673.1 | 1519.3 | −43.2% | 2627.2 | −1.7% |
| diamonds | 60.3 | 201.2 | **+233.8%** | 103.4 | **+71.6%** |
| lsat_model | 3128.9 | ABORT×3 | — | 3834.3 | +22.5% |
| accel_gp | 42.6 | ABORT×3 | — | 27.3 | −35.9% |
| kronecker_gp | 369.7 | 294.2 | −20.4% | 309.1 | −16.4% |
| pilots | 426.4 | ABORT×3 | — | 406.2 | −4.7% |
| eight_schools_centered | 237.0 | ABORT×3 | — | 304.9 | +28.6% |
| lotka_volterra | 1463.4 | 1455.3 | −0.6% | 831.9 | −43.2% |
| **AGG (shared models)** | — | +5.2% (n=5) | | **+2.4% (n=10)** | |

## Gate outcomes

- **DA: catastrophic.** Lost 5 of 10 models entirely (all 3 reps abort
  with `macro_time must be in (0, inf)`), hier_2pl −43% where it
  survives, ess_bulk_min drops >80% broadly. Gate 2 fails everywhere.
  Mechanism consistent with pre-registered expectation #2: naked dual
  averaging on saturated-alpha chains drives log-step to −∞ → step=0 →
  freeze-validate throw. walnutpie ships wrappers (batch/clip/
  anti-windup) that would mask this, but they are OFF at CLI defaults
  for every optimizer — and the Adam default survives them OFF.
- **Belief: completes everywhere but noise.** Aggregate +2.4% (inside
  the ±3% noise band) with large per-model dispersion (+72% diamonds,
  −43% lotka) and ess_bulk_min drops >20% on 10/10 models. Gate 1 fails.
- Wall numbers usable (quiet machine): roughly parity, not adoption-
  relevant given ESS verdict.

## Findings worth keeping

1. Adam-on-log-stepsize is the right default for walnutpie's raw CLI
   posture; it is the only base optimizer that completes this grid
   without wrappers. First recorded head-to-head evidence for a choice
   the optimizer scans noted was never benched.
2. **Diamonds-class targets**: BOTH alternatives beat Adam hugely
   (+234%/+72% geoESS). Adam's constant learning rate appears to leave
   ESS on the table on easy, well-conditioned targets. A conditional or
   wrapped variant (e.g. DA behind AntiWindup+Clip) could be a follow-up
   one-decision experiment — NOT part of this closed test.
3. The `macro_time` abort class fires under all three optimizers and now
   on 6 distinct model/repro cells across arms — it is a generic
   robustness hole (dead-init → alpha poison path), corroborating the
   rob/nan-alpha-guard triage; that guard branch is the fix vehicle,
   not this experiment.
