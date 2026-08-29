# W-63 — metric-window chopping A/B (`--metric-window 100` vs default discounting)

**Verdict: REJECT** (pre-registered gates, both failed). Closed negative result.
Date: 2026-08-24/25. Orchestrated by the ESS/s ideas session (ox-alpha);
preregistration in WORKLOG ("W-63 PRE-REGISTRATION", renumbered from W-60
after a number collision — SoA's blr demonstrator keeps W-60).

## Design

- Binary `build_w36exp` @43b6435, same 10-model grid / seeds / inits /
  `OMP_NUM_THREADS=1` / `--chains 4 --chain-exec threads` / 1000+1000 as
  W-36's `exp_par` arm; only delta is `--metric-window 100`
  (memoryless accumulator reset every 100 warmup iters,
  `adaptive_walnuts.hpp` `reset_to_seeds()`).
- Baseline arm = existing `runs/w36/exp_par` artifacts (bit-identical
  rerun unnecessary). New arm: `runs/w59/mw100/`. Runner
  `harness/run_w60.py`, analysis `harness/analyze_w60.py`,
  raw JSON `results/w60_ess.json`.
- Reps available: kronecker_gp rep0, lotka_volterra rep1, accel_gp rep1
  abort with the known pre-existing `macro_time must be in (0, inf)`
  validation throw (deterministic per seed) → 2-rep medians for those;
  all other cells 3 reps. NOTE: accel_gp rep1 is a NEW instance of this
  anomaly class (W-36 had kronecker rep0 + lotka rep1) — seed-dependent,
  robustness-ledger material.

## Results (median over reps; full table in results/w60_ess.json)

| model | base geoESS | mw100 geoESS | Δ | base ESSmin | mw100 ESSmin | Δ |
|---|---:|---:|---:|---:|---:|---:|
| radon_pp_noncentered | 2204.7 | 2353.9 | +6.8% | 74.0 | 210.0 | +184% |
| bym2_offset_only | 5.9 | 7.7 | +29.2% | 4.2 | 4.5 | +6.5% |
| hier_2pl | 2673.1 | 2922.6 | +9.3% | 624.7 | 580.6 | −7.1% |
| diamonds | 60.3 | 86.3 | +43.1% | 4.4 | 4.4 | +0.3% |
| lsat_model | 3128.9 | 4250.5 | **+35.8%** | 730.1 | 909.6 | +24.6% |
| accel_gp | 42.6 | 15.9 | **−62.6%** | 4.3 | 4.6 | +6.6% |
| kronecker_gp | 369.7 | 330.9 | −10.5% | 48.1 | 21.1 | −56.1% |
| pilots | 426.4 | 43.8 | **−89.7%** | 4.6 | 4.7 | +2.6% |
| eight_schools_centered | 237.0 | 290.2 | +22.4% | 101.3 | 86.7 | −14.4% |
| lotka_volterra | 1463.4 | 712.7 | **−51.3%** | 174.2 | 73.7 | −57.7% |
| **AGGREGATE** | 330.1 | 249.1 | **−24.5%** | 40.0 | 38.0 | −5.0% |

## Gate outcomes (as pre-registered)

1. geomean(ess_bulk_geomean) ≥ baseline+5% → **FAIL** (−24.5%).
2. no model ess_bulk_min drop >20% → **FAIL** (lotka −57.7%, kronecker −56.1%).
3. Hard-model collapse >2× → YES (accel_gp, pilots geoESS; lotka both).
⇒ ADOPT-candidate False; REJECT True.

## Caveats (honest accounting)

- **Wall column contaminated**: the mw100 arm ran during sibling sessions'
  announced wall windows (comms 23:38/23:53); wall deltas (+16..+78%) are
  NOT usable evidence. The verdict rests on ESS/R-hat only, which are
  wall-independent. n_leapfrog is also clean evidence: pilots +49%
  (171k→255k), accel_gp +27% — noisier mass estimates → longer
  trajectories, consistent with the ESS losses.
- R-hat degraded where ESS collapsed (lotka 1.02→1.29, kronecker 1.09→1.16).

## Mechanism reading

Window=100 chops produce variance estimates from ≤100 correlated draws —
too noisy for targets whose mixing doesn't need resetting (pilots,
accel_gp pay pure noise cost), while genuinely drift-contaminated models
(lsat, radon, bym2, diamonds) benefit from discarding stale history. The
published chopping-vs-discounting result does not transfer at window=100
at warmup=1000 on this suite; a larger window (250–500) might keep the
wins without the collapses, but that is a NEW experiment and the
pre-registered single-value test here says REJECT. Default stays
metric_window=0 (pure discounting). No PR warranted.
