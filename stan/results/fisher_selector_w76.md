# W-76: Fisher-ratio selector (end-of-warmup log(Var_draw·Var_score)) — KILLED

Pre-registered in WORKLOG 2026-08-26 ("Fisher-ratio selector feasibility",
overnight-3 session). Ground truth: results/labels_policy_w76.md. Classes:
winners {diamonds, radon_pp_nc, bym2} + lsat (winner-leaning) vs harmed
{lotka_volterra, kronecker_gp, accel_gp} + pilots (harmed-leaning);
eight_schools_c / hier_2pl mixed (never counted as errors).

## Setup

- Tracer: #11 branch exp/warmup-trace @7621584, private worktree
  external_w76/walnutpie_w76 (build_w76). Dumps raw per-warmup-iteration
  theta/grad/invmass/step/lp/depth per chain (single-chain mode; 4 chains
  = 4 sequential CLI calls, per-chain seed = 20260819+1000·rep+c, matching
  the multi-chain seed+c convention). Wrapper harness/run_w76_traces.py.
- Grid: 10 models × 3 reps × 4 chains, warmup 1000, samples 100, normal
  inits_w36 except hier_2pl/lsat pf inits_w25 (per run_arms.py defaults).
- Signal: per coordinate x_i = log(Var_draw_i · Var_score_i) over the
  final 200 warmup iterations (ddof=1, per chain; coordinates pooled over
  the 4 chains for aggregates). Pinned coordinates (Var=0 → x=-inf) are
  counted in frac1, tracked as frac_degen, and excluded from moment/range
  stats (finite-only).
- Aggregates per model/rep: mean, median, std, IQR, frac(|x|>1),
  frac_degen, max|x|. Model medians across reps feed the separation search
  (both directions tried; prereg fixed no direction).

## Collection status: 30/30 cells, 120/120 chain traces complete

Two chains aborted at SAMPLING START with the known macro_time throw
(chain_0 of kronecker_gp/rep0 and chain_0 of lotka_volterra/rep1) —
the same cells documented in W-81 ("kronecker rep0 + lotka rep1 abort").
The tracer flushes before the sampling-phase throw, so both warmup traces
are complete; chains 1–3 were run normally. No cell is missing.

Init provenance note: per the task's instruction the grid followed
run_arms.py defaults, i.e. pf inits_w25 for hier_2pl and lsat. Every
model in the primary 3+3 classes (plus pilots and eight_schools_c) ran
under NORMAL inits_w36, so the counted separation satisfies the prereg's
"selector must work WITHOUT pf" requirement; the only pf-init model in
the scored set is lsat (secondary). The verdict is unchanged if lsat is
dropped entirely: winners {radon 0.024, bym2 0.182, diamonds 0.559} vs
harmed {accel 0.219, kronecker 0.534, pilots 1.513, lotka 1.934} still
cannot be split by any median threshold (diamonds vs accel/kronecker
overlap).

Machine note: a sibling stream held load ~3 (12-core box) throughout; I
waited 37 min for load<2 (never came), confirmed the orchestrator's
comms.md entry queued these runs next and that no sibling wall was
announced, then ran strictly sequential single-core (load +1). This
experiment measures no wall/CPU times, so contention cannot affect the
signal.

## Per-model medians (w=200) and labels

| model | label | mean | median | std | iqr | frac1 | frac_degen | maxabs |
|---|---|---|---|---|---|---|---|---|
| lsat | winner-lean | −0.027 | −0.030 | 0.366 | 0.495 | 0.007 | 0 | 1.62 |
| radon_pp_nc | WINNER | 0.021 | 0.024 | 0.404 | 0.487 | 0.013 | 0 | 2.92 |
| bym2 | WINNER | −25.3 | 0.182 | 53.3 | 10.2 | 0.672 | 0.013–0.048 | 150 |
| diamonds | WINNER | 1.81 | 0.559 | 2.68 | 3.30 | 0.346 | 0 | 10.1 |
| hier_2pl | mixed | 0.101 | 0.053 | 0.487 | 0.528 | 0.049 | 0 | 2.78 |
| eight_schools_c | mixed | 2.90 | 2.61 | 1.01 | 1.22 | 0.975 | 0 | 5.44 |
| accel_gp | HARMED | −29.3 | 0.219 | 57.0 | 3.88 | 0.708 | 0–0.019 | 154 |
| kronecker_gp | HARMED | 0.547 | 0.534 | 0.538 | 0.683 | 0.211 | 0–0.25 | 4.9 |
| pilots | harmed-lean | 2.16 | 1.51 | 1.90 | 2.71 | 0.694 | 0 | 7.3 |
| lotka | HARMED | 1.79 | 1.93 | 1.31 | 2.44 | 0.688 | 0–0.25 | 3.9 |

(rep ranges in scratch/w76_analysis.json; per-rep table below in appendix.)

## Separation analysis (winners+lsat vs harmed+pilots, model medians)

| statistic | best direction | best threshold | misclassifications | rep violations at that threshold |
|---|---|---|---|---|
| mean | winners < thr | 0.294 | **2/8** | 6 (bym2r0, diamonds r0-r2, accel r0-r1) |
| **median** | winners < thr | 0.200 | **1/8** | **5** (bym2r0, diamonds r0-r2, accelr0) |
| std | winners < thr | 0.467 | 2/8 | 6 |
| iqr | winners < thr | 0.587 | 2/8 | 6 |
| frac(|x|>1) | winners < thr | 0.680 | 1/8 | 7 |
| frac_degen | winners < thr | 0.016 | 3/8 | 9 |
| max abs(x) | winners > thr | 3.38 | 2/8 | 18 |

Best case (median, w=200): threshold 0.200 leaves diamonds (median 0.559)
on the harmed side next to kronecker (0.534) and above accel (0.219);
raising the threshold above 0.56 to capture diamonds pushes bym2 (0.182)
and accel (0.219) across — ≥1 misclassification for ANY threshold. The
same holds at windows 100 and 500 (overlap-violations 3–6 per statistic).
AUC-equivalent of the best statistic: 14/16 correctly ordered winner-vs-
harmed pairs = 0.875 — nominally above the preregistered weak-expectation
0.8, but the direction is INVERTED (winners have SMALL log(Var·Var)) and
rep consistency fails outright.

## GATE (pre-registered): GO iff zero misclassifications AND 3/3 rep consistency → **KILL**

Decisive numbers: best statistic (median x) = 1/8 model-median
misclassifications (diamonds) and 5 rep violations at its best threshold
(bym2 rep0 median 2.09 vs reps 1–2 at 0.18/−120; diamonds 0.53–0.64 all
three reps; accel rep0 0.10 vs rep2 0.54). No statistic, no window
(100/200/500), no direction reaches zero.

Why it fails, mechanistically:
1. The spread statistics separate TIGHT from BROAD posteriors
   ({radon, lsat, hier_2pl, kronecker} tight vs {diamonds, pilots, lotka,
   eight_schools, bym2, accel} broad) — a real axis, but it is NOT the
   policy axis: harmed kronecker is as tight as winner radon, winner
   diamonds is as broad as harmed lotka/pilots.
2. Direction inversion vs the Fisher-misfit reading (winners LOW
   log(Var·Var)) — same pathology family as W-66's window_cross_ratio
   inversion.
3. Rep instability from pinned coordinates: exact-zero Var_draw coords
   appear on BOTH sides (winner bym2 r1/r2; harmed accel r0/r1,
   kronecker r0, lotka r1) and flip medians by orders of magnitude
   between reps of the same model.

This is the fourth selector candidate killed on this label set (after
W-28 lp-autocorr, W-37 windowed stats, W-66 window_cross_ratio). The
cheap end-of-warmup selector lane for conditional policies is now closed
on every candidate tried; any future selector needs a different signal
family (e.g. trajectory-depth or cross-chain dispersion detectors, cf.
W-85's ridgeF).

## Appendix: per-rep aggregates (w=200, chain-pooled)

| model/rep | mean | median | std | iqr | frac1 | frac_degen | maxabs |
|---|---|---|---|---|---|---|---|
| radon r0/r1/r2 | 0.04 / 0.04 / −0.02 | 0.03 / 0.02 / −0.02 | 0.39 / 0.39 / 0.43 | 0.49 / 0.45 / 0.52 | 0.009 / 0.013 / 0.029 | 0 / 0 / 0 | 2.9 / 2.9 / 3.0 |
| bym2 r0/r1/r2 | 5.3 / −120.3 / −25.3 | 2.09 / −120.6 / 0.18 | 6.0 / 7.6 / 53.3 | 10.5 / 9.6 / 10.2 | 0.63 / 1.00 / 0.67 | 0 / 0.048 / 0.013 | 29 / 150 / 150 |
| diamonds r0/r1/r2 | 1.71 / 1.87 / 1.86 | 0.56 / 0.53 / 0.64 | 2.45 / 2.76 / 2.84 | 3.33 / 3.79 / 1.79 | 0.33 / 0.35 / 0.39 | 0 / 0 / 0 | 8.9 / 10.3 / 10.9 |
| lsat r0/r1/r2 | −0.03 ×3 | −0.03 ×3 | 0.36–0.38 | 0.49–0.51 | 0.005–0.008 | 0 | 1.5–1.7 |
| hier_2pl r0/r1/r2 | 0.10 ×3 | 0.04–0.06 | 0.48–0.49 | 0.52–0.54 | 0.048–0.050 | 0 | 2.6–2.9 |
| eight_schools r0/r1/r2 | 2.2 / 2.9 / 3.0 | 2.2 / 2.6 / 3.1 | 0.72 / 1.43 / 0.87 | 0.91 / 2.55 / 1.22 | 0.975 / 0.975 / 1.0 | 0 | 4.6 / 6.3 / 5.3 |
| accel r0/r1/r2 | −29.3 / −30.6 / 0.76 | 0.10 / 0.22 / 0.54 | 54.8 / 57.3 / 6.0 | 1.88 / 9.48 / 3.88 | 0.50 / 0.71 / 0.71 | 0.019 / 0.019 / 0 | 153 / 154 / 30 |
| kronecker r0/r1/r2 | 0.53 ×3 | 0.50–0.56 | 0.51–0.56 | 0.67–0.73 | 0.38 / 0.19 / 0.21 | 0.25 / 0 / 0 | 5.9 / 4.9 / 3.8 |
| pilots r0/r1/r2 | 2.5 / 2.2 / 2.0 | 1.41 / 1.51 / 1.67 | 2.3 / 2.0 / 1.7 | 2.9 / 2.7 / 2.5 | 0.74 / 0.69 / 0.61 | 0 | 8.8 / 7.3 / 6.7 |
| lotka r0/r1/r2 | 1.7 / 1.6 / 1.9 | 1.93 / 1.77 / 2.06 | 1.4 / 1.2 / 1.3 | 2.4 / 1.8 / 2.7 | 0.69 / 0.72 / 0.63 | 0 / 0.25 / 0 | 3.9 / 3.5 / 3.8 |

Artifacts: runs/w76/traces/ (30 cells × 4 chain dirs: theta/grad/invmass/
step/lp/depth + meta.json), harness/run_w76_traces.py (collection wrapper,
per-chain resume), scratch/w76_analyze.py (this analysis),
scratch/w76_analysis.json (machine-readable per-cell values + thresholds).
