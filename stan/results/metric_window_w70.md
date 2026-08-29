# W-70 — metric-window sensitivity {250, 500}

**Verdict: NO-ADOPT; noise-recovery hypothesis REFUTED.** Date 2026-08-25.
Prereg in WORKLOG (W-70); runner `harness/run_arms.py`, analysis
`harness/analyze_arms.py`, raw JSON `results/w70_ess.json`. Baseline =
runs/w36/exp_par (Adam default, metric_window=0).

## Results (median geoESS, Δ vs baseline)

| model | base | mw100 (W-63) | mw250 | mw500 |
|---|---:|---:|---:|---:|
| radon_pp_nc | 2204.7 | +6.8% | **+36.9%** | **+59.8%** |
| bym2_offset_only | 5.9 | +29.2% | +12.1% | −3.0% |
| hier_2pl | 2673.1 | +9.3% | +2.0% | +0.4% |
| diamonds | 60.3 | +43.1% | **+55.1%** | −22.8% |
| lsat_model | 3128.9 | +35.8% | +24.8% | **+28.4%** |
| accel_gp | 42.6 | −62.6% | **−69.2%** | **−63.7%** |
| kronecker_gp | 369.7 | −10.5% | −3.9% | −5.3% |
| pilots | 426.4 | −89.7% | −16.3% | −16.0% |
| eight_schools_centered | 237.0 | +22.4% | +32.6% | −25.1% |
| lotka_volterra | 1463.4 | −51.3% | −44.3% | −8.7% |
| **AGGREGATE** | 330.1 | −24.5% | **−5.7%** | **−11.2%** |

## Gate outcomes

- No window passes ADOPT (need ≥+5% aggregate AND no >20% ess_bulk_min
  drops): mw250 −5.7%, mw500 −11.2%; drops present in both.
- Pre-registered mechanism check (monotone recovery with window):
  **FAILED** — mw500 is worse than mw250 overall, and diamonds /
  eight_schools flip sign between adjacent windows (+55→−23%, +33→−25%).
- accel_gp collapses at every window (it never recovers): its problem is
  not estimate noise.
- The "reject entire direction" trigger (both ≥20% below baseline) did
  not fire — but nothing approaches adoption either.

## Reading

Chopping on this suite is a high-variance redistribution of ESS across
models, not a recoverable win: which models win changes non-monotonically
with window size, so there is no stable tuning to adopt. Default
(metric_window=0) confirmed twice now (W-63, W-70). The persistent
winners (radon, lsat — data-heavy hierarchies with drift-contaminated
early warmup) would need a MODEL-ADAPTIVE screen to be usable, which is
a different experiment with no a-priori selector identified here.

Known deterministic aborts per arm (same cells as baseline): kronecker
rep0, lotka rep1 → 2-rep medians for those. Machine quiet throughout;
walls roughly parity.
