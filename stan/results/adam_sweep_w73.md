# W-73 — Adam hyperparameter sweep (step-learning-rate {0.02, 0.15}, accept-target 0.7)

**Verdict: REJECT all arms; defaults confirmed.** Date 2026-08-25 evening.
Prereg in WORKLOG (W-73); runner `harness/run_arms.py`, analysis
`harness/analyze_arms.py`, raw JSON `results/w73_ess.json`. Baseline =
runs/w36/exp_par (lr=0.05, accept-target=0.8).

## Results (median geoESS Δ vs baseline)

| model | lr_hi (0.15) | lr_lo (0.02) | target07 |
|---|---:|---:|---:|
| radon_pp_nc | **+42.2%** | −99.2% | −44.9% |
| bym2_offset_only | +30.2% | −32.0% | −3.4% |
| hier_2pl | +2.7% | −31.7% | −52.9% |
| diamonds | **+89.1%** | −92.1% | +7.1% |
| lsat_model | +6.9% | −34.8% | −51.1% |
| accel_gp | −33.8% | −84.8% | −14.5% |
| kronecker_gp | −16.6% | −35.1% | −51.9% |
| pilots | −10.7% | −9.9% | −4.1% |
| eight_schools_c | +1.4% | +31.1% | −4.4% |
| lotka_volterra | −53.1% | −49.6% | −12.9% |
| **AGGREGATE** | **−1.0%** | **−67.8%** | **−27.0%** |

## Gate outcomes

- lr_hi: aggregate noise-band AND ess_bulk_min drops >20% on
  kronecker/eight_schools/lotka incl. a lotka collapse → no-adopt.
- lr_lo: catastrophic (−67.8%; radon/diamonds/accel collapse). Adam's
  0.05 learning rate is doing real work — 1000 warmup iterations are not
  enough for 0.02 to converge the log-step estimate.
- target07: −27.0% with three collapsed models → lower acceptance does
  NOT buy ESS/s here; quality loss dominates the eval-count saving.

## Pattern worth naming

Across this whole session cluster (~20 measured levers), improvements
are always concentrated on the SAME easy models (diamonds/radon/bym2)
and harm ALWAYS concentrates on lotka_volterra / kronecker_gp /
hier_2pl-class targets. lr_hi is the cleanest demonstration yet:
+89%/+42% on the easy end, −53% on the hard end, zero net. A global
default change cannot exploit this spread; only per-model adaptation
could, and every cheap selector tried so far (low-rank screen W-66,
window_cross_ratio) has come out inverted or blind. The residual ESS/s
headroom lives in that unsolved selection problem, or in the one open
algorithmic lead: two-phase warmup.
