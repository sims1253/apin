# W-74: warmup truncation with pf inits (W400/W700 vs w1000) — ESS/s experiment

Pre-registered in `stan/WORKLOG.md` "W-74 PRE-REGISTRATION" (2026-08-25). Zero code
changes; pure CLI arms on the CORE_SET grid. Gates G1–G3 and the verdict rule there
are binding; this file is the adjudication record.

**VERDICT: NO-GO** (per the pre-registered rule: GO requires G1+G2+G3 all pass; all
three gates FAIL for both arms — G1 alone is decisive and load-independent).
The pre-registered fallback applies: per-class/per-model truncation guidance recorded
below. The two-phase lead (W-45) now has BOTH variants dead: subsample transplant by
mechanism, plain truncation by measured no-harm violation.

## Setup

- Arms: `--warmup 400` (W400) and `--warmup 700` (W700); everything else identical
  to the W-63 A0 grid: `--samples 1000 --metric-window 50`,
  `--seed 20260819+1000*rep+chain`, pf inits from `scratch/w63/manifest.csv`
  (`init rep<r>/chain_<c>.txt`), `env -u LD_LIBRARY_PATH`, `OMP_NUM_THREADS=1`,
  single chain per process, 4 workers.
- 2 arms x 21 models x 3 reps x 4 chains = **504 runs, 504/504 done, 0 failures**
  (driver FINAL 22:55:30; ~46 min total).
- Baseline: REUSED W-63 A0 `w1000_pf` grid (252 chain-runs verified complete on
  disk: csv + "total time:" in every log), same seeds/inits/protocol.
- Binary: `external/walnutpie_lowrank/build_gates/examples/stan_cli` (guarded).
  Sound because these runs use ONLY default-path flags (no `--metric-rank/basis/
  full/auto`), and the guard is canary-proven byte-identical on the default path
  (W-64 close-out: "canary BYTE-IDENTICAL both md5s (guard bit-inert on finite
  paths)"). The W-63 A0 baseline mix of pre-/post-guard cells is likewise
  bit-identical on this path.
- ESS/rhat conventions: reused verbatim from `scratch/w63/analyze_lowrank.py`
  (rank-normalized Geyer initial-monotone `ess_bulk` on combined 4-chain draws per
  rep; rank-normalized split-R-hat; constant-column exclusion). Per rep, total wall
  = sum over the 4 chains of the sum of both `total time:` stanzas (chains run
  sequentially); medians over the 3 reps. Headline ESS/s = ess_min_med / wall_med.

## TIMING CONFOUND (must read before interpreting G2)

The arm runs executed 22:09–22:55 while the machine carried a concurrent 4-thread
W-73 run plus IO load (load average ~14.7 on 12 cores at launch); the W-63 baseline
ran on an idle machine. Per-log gradient timings quantify the speed factor:

| model | µs/call W1000 | µs/call W400 | µs/call W700 | slowdown |
|---|---|---|---|---|
| hier_2pl | 1611 | 2411 | 2619 | 1.50–1.63x |
| kronecker_gp | 480 | 801 | 815 | 1.67–1.70x |
| radon_partially_pooled | 417 | 686 | 726 | 1.65–1.74x |
| bym2_offset_only | 219 | 333 | 314 | 1.43–1.52x |
| lsat_model | 210 | 285 | 284 | 1.35x |
| arma11 | 8.2 | 13.4 | 12.6 | 1.55–1.64x |

The arm runs were ~1.35–1.7x slower per work unit. Raw wall ratios are therefore
CONTAMINATED (this is why W400 "wall ratio" geomean reads 1.207 — a 400-warmup run
cannot be slower than a 1000-warmup run on the same work). The load-invariant
`logp_grad calls` totals deconfound: **calls geomean ratio W400 = 0.695 (30.5%
work saving), W700 = 0.867 (13.3%)**. ESS ratios (G1) and pinned/rhat censuses (G3)
are computed from draws and call counts — unaffected by the confound.

## Gate adjudication (pre-registered)

### G1 no-harm: per-model ESS_min ratio (arm/w1000, rep medians) >= 0.9 EVERYWHERE — **FAIL both arms**

- W400: 7/21 violators. blr 0.56, lotka_volterra 0.41, eight_schools_centered 0.66,
  low_dim_gauss_mix 0.85, radon_partially_pooled 0.88, bym2 0.88, dogs 0.89.
- W700: 5/21 violators. blr 0.42, eight_schools_centered 0.68,
  radon_partially_pooled 0.71, dogs 0.81, bym2 0.90.
- Geomean ESS ratio: W400 0.918, W700 1.042 — aggregate looks fine; the floor is
  what breaks. Per-rep checks confirm these are systematic, not seed noise (same
  seeds as baseline; only warmup horizon differs): blr per-rep ESS
  W400 310/35/195 vs W1000 433/347/199; esc 40/69/124 vs 113/104/85;
  dogs 1527/1394/1410 vs 1592/1594/1377.

### G2 efficacy: geomean wall saving >= 20% — **FAIL as measured (confounded)**

- As pre-registered (log `total time:` walls): geomean wall ratio W400 1.207
  (saving −20.7%), W700 1.546 (−54.6%) — FAIL, but see the confound above.
- Deconfounded work proxy (gradient calls, load-invariant): W400 0.695 → 30.5%
  saving (would satisfy 20% on work-units), W700 0.867 → 13.3% (would not).
- ESS/s as measured: geomean ratio W400 0.761, W700 0.674 (contaminated by the
  same slowdown). Load-invariant efficiency ESS-per-gradient-call geomean ratio:
  **W400 1.321, W700 1.202** — per unit of gradient work, truncated warmup is
  ~20–32% MORE ESS-efficient in aggregate; the sampled-quality floor (G1) is what
  forbids exploiting it blanket-style.

### G3 pathology: no NEW pinned / rhat>1.02 / logp_grad-error pathology vs the w1000 census, like-for-like — **FAIL both arms**

- New pinned chain-runs (unique-row == 1), W400: diamonds +3 (r0c0, r1c3, r2c3),
  bym2 +7 (12/12 pinned vs 5/12 baseline), accel_gp +4 (6/12 vs 2/12),
  radon_partially_pooled +2 (r2c0, r2c1 — rep2 collapses to ESS 2.2 with 775
  rhat>1.02 params vs baseline 149.4), blr +1 (r1c0), pilots +1 (r2c2).
- W700: bym2 +3 (8/12 pinned), accel_gp +2 (4/12).
- rhat>1.02 median-count increases in the already-zombie models (kronecker_gp
  1992→2055/2467 of ~3.8k params; bym2 9598→9610) are marginal but directionally
  consistent; baseline zombies are counted, not excused (like-for-like comparison).
- logp_grad-error increases: blr 28.5k→40.9k (W400); kronecker_gp 65.2k→46k/56k
  and lotka 63.6k→45k/54k actually IMPROVE (fewer warmup iterations = fewer
  error-prone iterations in zombies).

### Dose-response (W400 → W700 → W1000, geomeans over 21 models)

| metric | W400 | W700 | W1000 |
|---|---|---|---|
| ESS_min ratio vs W1000 | 0.918 | 1.042 | 1 |
| grad-call ratio vs W1000 | 0.695 | 0.867 | 1 |
| violators (<0.9 ESS) | 7 | 5 | 0 |
| net new pinned runs | +18 | +5 | 0 |

Truncation trades quality floor for work: quality recovers monotonically with
warmup length while the work saving shrinks; there is no knee that passes G1 and
G2 simultaneously at CORE_SET scale without model screening.

## Per-class breakdown of G1 violators (CORE_SET families)

- easy/small: blr fails hard (0.42–0.56) — but blr is the known sigma-boundary
  pathological model (28.5k baseline logp_grad errors; ESS_min ~350 at w1000);
  the other three (eight_schools_nc 0.96–1.18, kidscore 1.14, lsat 0.95–0.97) pass.
- hierarchical: radon_partially_pooled 0.71–0.88 (+ new zombie rep at W400),
  dogs 0.81–0.89 fail; radon_variable_intercept_slope 1.11–1.31 and hier_2pl
  0.92–1.10 pass. Split verdict within the class.
- GP/spatial: bym2 0.88–0.90 (marginal, zombie-regime) fails; gp_regr passes
  (1.02–1.06); kronecker/accel are zombies like-for-like (kronecker W400 median
  even 1.87x baseline).
- stiff/funnel: eight_schools_centered 0.66–0.68 and lotka W400 0.41 fail;
  lotka W700 reads 6.58x but that is a single-rep effect (rep2: 67.8 vs 10.3;
  rep0/rep1 unchanged ~85/~3) on a bistable posterior — not a systematic gain;
  garch 1.01, ldgm 0.85–1.08, arma 0.91–0.94 marginal-pass.

Honest per-class guidance recorded (fallback outcome per the verdict rule):
truncation to 400–700 warmup is safe-looking ONLY on the benign easy/small and GLM
families minus their pathological members (blr, diamonds pin-risk), and NOT a
class-level property for hierarchical or funnel models — it must be screened
per-model (which is what W-21's marginal-class lesson predicted).

## Full per-model table (rep medians)

ESS_min (combined 4 chains); r = ESS ratio vs W1000; c = grad-call ratio vs W1000
(load-invariant work); pin = pinned chain-runs of 12; lge = "Error in logp_grad"
count (thousands, all 12 runs).

| model | family | ESS W400 | ESS W700 | ESS W1000 | rW400 | rW700 | cW400 | cW700 | pin 400/700/1000 | lge 400/700/1000 |
|---|---|---|---|---|---|---|---|---|---|---|
| eight_schools_noncentered | easy/small | 1405.1 | 1730.6 | 1470.2 | 0.96 | 1.18 | 0.68 | 0.84 | 0/0/0 | 0k/0k/0k |
| blr | easy/small | 194.8 | 144.8 | 346.6 | 0.56 | 0.42 | 0.73 | 0.86 | 1/0/0 | 40k/28k/28k |
| kidscore_momiq | easy/small | 325.0 | 323.0 | 283.4 | 1.15 | 1.14 | 0.68 | 0.83 | 0/0/0 | 0k/0k/0k |
| lsat_model | easy/small | 911.6 | 894.9 | 940.8 | 0.97 | 0.95 | 0.65 | 0.80 | 0/0/0 | 0k/0k/0k |
| logmesquite_logvash | GLM | 110.9 | 93.7 | 102.4 | 1.08 | 0.92 | 0.69 | 0.85 | 0/0/0 | 0k/0k/0k |
| wells_dist100_model | GLM | 763.4 | 762.6 | 749.2 | 1.02 | 1.02 | 0.70 | 0.85 | 0/0/0 | 0k/0k/0k |
| diamonds | GLM | 2.3 | 2.4 | 2.5 | 0.92 | 0.99 | 0.69 | 1.38 | 3/0/0 | 0k/0k/0k |
| radon_partially_pooled_noncentered | hierarchical | 191.3 | 153.0 | 216.7 | 0.88 | 0.71 | 0.73 | 0.86 | 2/0/0 | 0k/0k/0k |
| radon_variable_intercept_slope_noncentered | hierarchical | 295.1 | 349.0 | 267.0 | 1.11 | 1.31 | 0.69 | 0.84 | 0/0/0 | 0k/0k/0k |
| dogs_hierarchical | hierarchical | 1409.7 | 1291.7 | 1592.1 | 0.89 | 0.81 | 0.70 | 0.85 | 0/0/0 | 0k/0k/0k |
| pilots | hierarchical | 2.3 | 2.8 | 2.3 | 0.98 | 1.21 | 0.65 | 0.74 | 1/0/0 | 0k/0k/0k |
| hier_2pl | hierarchical | 451.7 | 542.6 | 493.4 | 0.92 | 1.10 | 0.68 | 0.84 | 0/0/0 | 0k/0k/0k |
| gp_regr | GP/spatial | 2395.5 | 2304.6 | 2261.6 | 1.06 | 1.02 | 0.69 | 0.85 | 0/0/0 | 0k/0k/0k |
| kronecker_gp | GP/spatial | 15.2 | 8.8 | 8.1 | 1.87 | 1.08 | 0.72 | 0.85 | 1/1/1 | 45k/55k/65k |
| accel_gp | GP/spatial | 2.2 | 2.4 | 2.3 | 0.95 | 1.07 | 0.62 | 0.85 | 6/4/2 | 0k/0k/0k |
| bym2_offset_only | GP/spatial | 2.0 | 2.0 | 2.3 | 0.88 | 0.90 | 0.70 | 0.85 | 12/8/5 | 3k/3k/3k |
| eight_schools_centered | stiff/funnel | 68.5 | 70.1 | 103.5 | 0.66 | 0.68 | 0.72 | 0.86 | 0/0/0 | 0k/0k/0k |
| garch11 | stiff/funnel | 757.3 | 760.5 | 747.1 | 1.01 | 1.02 | 0.69 | 0.85 | 0/0/0 | 0k/0k/0k |
| lotka_volterra | stiff/funnel | 4.3 | 67.8 | 10.3 | 0.41 | 6.58 | 0.78 | 0.98 | 0/0/0 | 44k/54k/63k |
| low_dim_gauss_mix | stiff/funnel | 659.3 | 840.7 | 778.6 | 0.85 | 1.08 | 0.70 | 0.86 | 0/0/0 | 0k/0k/0k |
| arma11 | stiff/funnel | 931.9 | 956.3 | 1022.3 | 0.91 | 0.94 | 0.69 | 0.84 | 0/0/0 | 0k/0k/0k |

Measured walls and ESS/s (CONFOUNDED by the 1.35–1.7x slowdown, kept for the
record; JSON has per-rep values):

| model | wall400 | wall700 | wall1000 | ESS/s 400 | ESS/s 700 | ESS/s 1000 |
|---|---|---|---|---|---|---|
| eight_schools_noncentered | 0.1 | 0.1 | 0.1 | 13700.5 | 13210.4 | 16867.9 |
| blr | 0.9 | 0.9 | 0.6 | 224.7 | 163.9 | 574.5 |
| kidscore_momiq | 0.8 | 1.0 | 0.7 | 417.6 | 337.4 | 389.0 |
| lsat_model | 33.4 | 40.5 | 37.5 | 27.33 | 22.10 | 25.10 |
| logmesquite_logvash | 0.4 | 0.6 | 0.4 | 263.9 | 154.0 | 278.2 |
| wells_dist100_model | 3.5 | 5.3 | 3.5 | 221.0 | 143.0 | 215.0 |
| diamonds | 16.7 | 27.6 | 14.2 | 0.136 | 0.089 | 0.175 |
| radon_partially_pooled_noncentered | 82.6 | 106.5 | 68.4 | 2.32 | 1.44 | 3.17 |
| radon_variable_intercept_slope_noncentered | 10.5 | 13.7 | 8.6 | 28.19 | 25.39 | 31.13 |
| dogs_hierarchical | 3.8 | 5.2 | 2.7 | 375.2 | 247.1 | 588.4 |
| pilots | 0.7 | 0.8 | 0.5 | 3.21 | 3.46 | 4.44 |
| hier_2pl | 249.0 | 346.1 | 258.7 | 1.81 | 1.57 | 1.91 |
| gp_regr | 0.6 | 0.6 | 0.3 | 4285.3 | 3603.9 | 6907.6 |
| kronecker_gp | 98.8 | 114.7 | 78.8 | 0.154 | 0.076 | 0.103 |
| accel_gp | 5.6 | 9.9 | 4.7 | 0.392 | 0.246 | 0.492 |
| bym2_offset_only | 62.6 | 70.7 | 57.8 | 0.032 | 0.029 | 0.039 |
| eight_schools_centered | 0.2 | 0.3 | 0.1 | 387.8 | 269.9 | 983.6 |
| garch11 | 3.2 | 3.6 | 2.6 | 240.1 | 210.1 | 292.0 |
| lotka_volterra | 18.9 | 19.5 | 13.6 | 0.226 | 3.48 | 0.756 |
| low_dim_gauss_mix | 19.2 | 24.0 | 18.9 | 34.34 | 35.09 | 41.14 |
| arma11 | 0.6 | 0.6 | 0.5 | 1693.3 | 1504.0 | 2081.0 |

## Mechanism notes

- pf inits already place chains near the typical set, so warmup's remaining job is
  stepsize/metric refinement. Where adaptation is still converging at iter 400–700
  (funnel scales, hierarchical SDs, blr's sigma boundary), truncation freezes a
  worse kernel: lower ESS, more boundary rejections (blr logp_grad errors
  28.5k -> 40.9k at W400), and occasionally a chain that never moves again
  (pinned runs; radon_pp rep2 goes from healthy to 775 rhat>1.02 params).
- diamonds W700 needs MORE gradient calls than w1000 (1.38x): truncated adaptation
  left a smaller stepsize, so the sampling phase pays more leapfrog steps per
  iteration — warmup saving fully eaten. Wall/call inversions of this kind are a
  real mechanism, distinct from the machine-load confound.
- Zombie models (bym2 12/12 pinned at W400 vs 5/12 at w1000) show truncation makes
  the stuck-chain regime MORE likely: whatever slow drift eventually unsticks a
  chain in 1000-iter warmup is cut off at 400.
- The one real improvement, lotka W700 6.6x on rep2, is mode-selection luck on a
  bistable posterior, not a usable effect.

## Artifacts

- Runs: `scratch/w74/runs/{W400,W700}/<model>/rep<r>_c<chain>.{csv,log}` (504 pairs,
  every log with exactly 2 `total time:` stanzas).
- Driver: `scratch/w74/driver.py` (adapted from w63; resume-capable; WORKERS=4);
  `scratch/w74/driver.log` (FINAL done=504/504, 0 FAIL lines).
- Analysis: `scratch/w74/analyze_w74.py`; results `scratch/w74/w74_results.json`
  (per-rep ESS/walls/rhat/pinned census + gates); `scratch/w74/analyze.out|.err`.
