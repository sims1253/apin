# W-76: Depth-cap pin battery (P3 stage-2) — CLOSE-OUT: ALL ARMS REJECT on the pre-registered rule (0/15 cells advance); the W-73 mechanical bounds were arithmetically sound but the ESS-flatness assumption behind them is FALSE everywhere the cap binds

Pre-registration: WORKLOG "W-76 PRE-REGISTRATION" (2026-08-25, before any
run). Binary: `external/walnutpie_lowrank/build_gates/examples/stan_cli`
(the W-63 A0 binary; unchanged). Exact CLI flag spellings (from `--help`):

- `--max-trajectory-doublings UINT:POSITIVE [5]` — "Maximum depth for Nuts
  trajectory doublings" (default 5)
- `--min-micro-steps UINT:POSITIVE [1]` — "Minimum micro steps per macro
  step" (default 1)

Both flags exist, so all three pre-registered arms ran (180 runs, not the
120-run fallback).

## Design (as pre-registered)

- Arms: **C4** = `--max-trajectory-doublings 4`; **C5** = 5 (= the default
  cap — config-identical to baseline, doubles as a bit-determinism canary);
  **C5MM2** = 5 + `--min-micro-steps 2`. All on `--metric-window 50`,
  default everything else.
- Models (W-73 conditional-GO set + negative control): blr,
  eight_schools_centered (8sch_c), logmesquite_logvash,
  radon_partially_pooled_noncentered (radon_pp), hier_2pl (control,
  8.6%-class bound, expected null).
- Grid: 3 arms x 5 models x 3 reps x 4 chains = 180 single-chain runs,
  pf inits (manifest init_dirs), w1000 s1000, seeds 20260819+1000*rep+chain,
  `env -u LD_LIBRARY_PATH`, `OMP_NUM_THREADS=1`, 4 workers, resume-capable
  driver at `scratch/w76/driver.py`.
- Baseline: REUSED W-63 A0 grid `scratch/w63/runs/A0/<model>/w1000_pf/`
  (default cap 5, min-micro 1; identical seeds/args otherwise).
- Completion: 180/180, 0 failures, 21 min wall (23:32:57-23:54:02) under
  co-load (one W-75 single-core sampler + 4 W-76 workers on 12 cores).

## Conventions (reused from w63/w74)

ESS_min = min over parameters of rank-normalized Geyer ess_bulk on the
combined 4 chains per rep; rep medians reported. grads/draw = total
`logp_grad calls:` (BOTH stanzas, warmup+sampling) / 1000 draws; a
sampling-only variant is also reported (bound-relevant). Wall = sum of
`total time:` stanzas over the 4 chains.

## Headline table (rep medians; ratios vs A0 baseline)

| model | arm | ESS_min | grads/draw | ESS ratio | grads/draw ratio | sampling grads ratio | ESS/s ratio (wall) | verdict |
|---|---|---|---|---|---|---|---|---|
| blr | A0 | 346.6 | 216.7 | 1 | 1 | 1 | 1 | — |
| blr | C4 | 150.6 | 173.8 | **0.435** | 0.802 | 0.680 | 0.389 | reject |
| blr | C5 | 346.6 | 216.7 | 1.000 | 1.000 | 1.000 | 0.816 | reject (control) |
| blr | C5MM2 | 491.4 | 374.9 | 1.417 | 1.730 | 1.698 | 0.645 | reject |
| 8sch_c | A0 | 103.5 | 145.6 | 1 | 1 | 1 | 1 | — |
| 8sch_c | C4 | 43.5 | 147.3 | **0.420** | 1.011 | 0.972 | 0.322 | reject |
| 8sch_c | C5 | 103.5 | 145.6 | 1.000 | 1.000 | 1.000 | 0.731 | reject (control) |
| 8sch_c | C5MM2 | 79.6 | 215.3 | 0.769 | 1.478 | 1.371 | 0.540 | reject |
| logmesquite | A0 | 102.4 | 143.2 | 1 | 1 | 1 | 1 | — |
| logmesquite | C4 | 54.5 | 122.6 | **0.532** | 0.856 | 0.821 | 0.418 | reject |
| logmesquite | C5 | 102.4 | 143.2 | 1.000 | 1.000 | 1.000 | 0.672 | reject (control) |
| logmesquite | C5MM2 | 158.7 | 193.6 | 1.551 | 1.352 | 1.250 | 1.022 | reject |
| radon_pp | A0 | 216.7 | 157.6 | 1 | 1 | 1 | 1 | — |
| radon_pp | C4 | 151.9 | 147.1 | **0.701** | 0.933 | 0.892 | 0.560 | reject |
| radon_pp | C5 | 216.7 | 157.6 | 1.000 | 1.000 | 1.000 | 0.788 | reject (control) |
| radon_pp | C5MM2 | 384.3 | 248.1 | 1.773 | 1.574 | 1.439 | 0.926 | reject |
| hier_2pl | A0 | 493.4 | 160.2 | 1 | 1 | 1 | 1 | — |
| hier_2pl | C4 | 519.5 | 160.2 | 1.053 | 1.000 | 1.000 | 0.942 | reject (null as predicted) |
| hier_2pl | C5 | 493.4 | 160.2 | 1.000 | 1.000 | 1.000 | 0.805 | reject (control) |
| hier_2pl | C5MM2 | 1556.6 | 288.6 | 3.155 | 1.801 | 1.938 | 1.551 | reject |

Pre-registered verdict rule (BINDING): per model, ADVANCE iff ESS ratio
>= 0.95 AND grads/draw ratio <= 0.9. **0 of 15 model-arm cells advance.**

## C5 determinism canary

C5 is config-identical to the reused A0 baseline (default cap 5) with
identical seeds. All 60 C5 runs are md5-identical to their W-63 baseline
CSVs (0 mismatches); ESS/grads ratios are exactly 1.000 by construction.
This (a) validates reusing the W-63 baseline and (b) isolates the >1 C5
WALL ratios (1.23-1.49) as pure co-load (a W-75 sampler + 4 W-76 workers;
the W-74 load-confound lesson applies) — wall-based ESS/s ratios in this
session are load-confounded; grads-based ratios are load-invariant and are
the trustworthy economics.

## Bound comparison (W-73 rung arithmetic: blr <= 33%, 8sch_c <= 23%, others <= 8% grads saving, ESS-flat assumption)

- **blr**: C4 realizes 19.8% total / **32.0% sampling-only** grads saving —
  right AT the 33% mechanical bound, i.e. the arithmetic was correct — but
  ESS collapses to 0.435x. The bound's ESS-flatness assumption is FALSE:
  the capped trajectories were doing real mixing work. ESS/grad ratio 0.542.
- **8sch_c**: essentially ZERO saving (−1.1% total / 2.8% sampling) despite
  a 23% bound — the W-73 "exact-32 always-reject cap signature" chains do
  not release grads when capped (rejection-limited, not depth-limited);
  plus ESS 0.420x and rhat>1.02 count 3.0 vs 1.0. Double fail.
- **logmesquite / radon_pp**: sampling-only savings 17.9% / 10.8% EXCEED
  the 8% bounds — indirect adaptation effects (cap changes warmup ->
  different adapted step/macro -> cheaper sampling), not rung arithmetic;
  honest flag that the W-73 bounds under-predict when adaptation couples.
  ESS still drops to 0.53x / 0.70x. Reject.
- **hier_2pl (control)**: clean null — 0.0% saving, ESS ratio 1.053,
  exactly as the 8%-class bound predicted for a non-saturating model.

## Observed (NOT pre-registered): the min-micro direction inverts the story

C5MM2 fails the grads gate everywhere (1.35-1.80x total grads cost) but
BUYS ESS on 4 of 5 models; per-model ESS/grad ratios (ESS ratio / grads
ratio, load-invariant): **hier_2pl 1.75x**, radon_pp 1.13x, logmesquite
1.15x, blr 0.82x, 8sch_c 0.52x. hier_2pl's 3.16x ESS at 1.80x grads is a
strong per-model lead for `--min-micro-steps 2` as a QUALITY lever (same
family as the W-73/W-74 easy-hard split: hierarchical gainers, funnel
losers). Any such use must be screened per-model (W-21/W-74 lesson); it is
not a default-change candidate and was not a registered gate here.

## ESS/s per model (wall-based; LOAD-CONFOUNDED — see canary)

A0 medians: blr 574/s, 8sch_c 984/s, logmesquite 278/s, radon_pp 3.2/s,
hier_2pl 1.9/s. Session ran under a co-resident W-75 sampler; C5's
identical-compute wall ratio 1.23-1.49 calibrates the confound. Use the
grads-ratio columns for decisions.

## Selector mining addendum (W-76 follow-up, 2026-08-25; zero runs, zero builds)

Question: the unregistered C5MM2 (min-micro 2) quality direction is per-model
(hier_2pl 1.75x ESS/grad vs 8sch_c 0.52x) — is there a selector in EXISTING
data that predicts which side a model falls on? Labeled sample = the 5 models
above (that is ALL models with a C5MM2 arm; n=5, not 10). Label = C5MM2
ESS ratio / grads ratio (load-invariant; the wall ESS/s column is
co-load-confounded per the C5 canary). Features mined from the reused W-63
A0 logs (re-parsed all 60 logs for these 5 models; independent parse
reproduces the W-73 calls/draw values exactly). D note: the CSV header
column count OVERCOUNTS param_unc_num for models that write raw+transformed
params (radon_pp CSV = 775 cols = `alpha_raw.*`+`alpha.*`; hier_2pl 804 =
raw pairs + expanded `Omega.i.j`) — the mass-matrix diagonal LENGTH is the
true unconstrained count (389 / 669, matching W-73) and is used below.

### Joined table (A0 features | C5MM2 verdicts)

| model | family | D | A0 samp calls/draw | A0 macro-time CV | A0 ESS/draw | p32 lb | ESS ratio | grads ratio | ESS/grad | side |
|---|---|---|---|---|---|---|---|---|---|---|
| hier_2pl | hierarchical | 669 | 16.7 | 0.02 | 0.123 | 0.05 | 3.155 | 1.801 | **1.752** | benefit |
| logmesquite | GLM | 7 | 17.4 | 0.04 | 0.026 | 0.08 | 1.551 | 1.352 | **1.147** | benefit |
| radon_pp | hierarchical | 389 | 17.1 | 0.14 | 0.054 | 0.07 | 1.773 | 1.574 | **1.127** | benefit |
| blr | easy/small | 6 | 23.9 | 0.03 | 0.087 | 0.49 | 1.417 | 1.730 | **0.819** | harm |
| 8sch_c | stiff/funnel | 10 | 20.9 | 0.47 | 0.026 | 0.30 | 0.769 | 1.478 | **0.520** | harm |

### Selector tests (n=5, exploratory only — no gate claims)

- **D (threshold): FAILS.** harm {6, 10} vs benefit {7, 389, 669} —
  logmesquite (D=7) benefits while 8sch_c (D=10) is harmed; no threshold
  separates. Spearman +0.50, point-biserial +0.67, exact perm p=0.30.
  (The D>=big story only holds if logmesquite is ignored.)
- **A0 sampling calls/draw: CLEAN 5/5.** harm {20.9, 23.9} vs benefit
  {16.7, 17.1, 17.4}; any threshold t in (17.4, 20.9] separates (midgap
  19.1). Point-biserial r = -0.936; exact p over the 10 unique 3/2 label
  splits = 0.10 (the best achievable at n=5 with a 3/2 split).
- **p32 two-rung lower bound (affine in calls/draw): CLEAN 5/5**, and the
  two harmed models are EXACTLY the two W-73 depth-cap-saturated models
  (p32 >= 0.30: blr 0.49, 8sch_c 0.30) vs all benefits <= 0.085. Same
  variable as calls/draw, but the mechanistic reading is cleaner: where
  the depth-5 cap binds, min-micro 2 adds grads without adding trajectory
  length; where trajectories are U-turn-limited, forced micro refinement
  buys ESS faster than it buys grads.
- **A0 macro-time CV: FAILS** (blr 0.03 sits inside the benefit range
  {0.02, 0.04, 0.14}; only 8sch_c 0.47 stands out). Spearman -0.10, p=1.0.
- **A0 ESS_min/draw: FAILS** (logmesq 0.026 benefit = 8sch_c 0.026 harm).
- **Family: consistent but unfalsifiable here** — hierarchical 2/2 benefit,
  GLM 1/1 benefit, easy/small 1/1 harm, funnel 1/1 harm (the W-21/W-74
  hierarchical-gainer / funnel-loser pattern); every non-hierarchical
  family has n=1 and family is fully confounded with calls/draw on 5 points.

### Candidate rule + stability

**Rule (candidate, NOT adopted): a model benefits from `--min-micro-steps 2`
iff its default-arm sampling calls/draw <= ~18 (equivalently p32 lower
bound <= ~0.1, i.e. not depth-cap saturated).** Leave-one-out on the 5-model
sample: 5/5 folds retain perfect separation; the midgap threshold drifts
only 18.98-20.62. Honest weaknesses, all load-bearing: (a) n=5, exact
permutation p=0.10 — even a perfect split cannot reach p<0.10 at this n;
(b) the 20% margin (17.4 vs 20.9) brackets near-neutral labels — the
boundary models' ESS/grad are 1.15 (benefit side) and 0.82 (harm side),
both close to 1; (c) per-rep label votes are UNSTABLE at the boundary
(paired per-rep ESS/grad ratios: blr 0.77/0.82/1.10 = nnY, 8sch_c
0.44/0.32/1.04 = nnY, radon_pp 0.90/1.24/1.56 = nYY; only hier_2pl
1.60/1.79/1.74 and logmesquite 1.72/1.16/1.48 are YYY) — the median
split is real but rep noise is ±30%; (d) calls/draw, p32 and family are
mutually confounded at n=5, so WHICH feature is causal is not identifiable.

### Protocol to close it (needs measurements, not more mining)

Extrapolating the rule to the 16 unlabeled CORE_SET models: predicted harm
= pilots, bym2, accel_gp, diamonds (calls/draw 26-33 — all four ESS-dead at
A0, so moot) and predicted benefit = every healthy unlabeled model (lsat
16.7, radon_var_slope 16.6, kidscore 11.7, garch 11.3, ldgm 10.7, 8sch_nc
8.7, wells 6.9, arma 6.8, gp_regr 6.6, dogs 5.7) + the dead kronecker/lotka
(moot). Consequence: CORE_SET contains NO healthy unlabeled model on the
predicted-harm side — the rule's harm branch is untestable within the
current set. Minimal next batch: C5MM2 on {lsat_model,
radon_variable_intercept_slope_nc, dogs_hierarchical, gp_regr} (boundary-
adjacent spendy + low-spend extremes, all predicted benefit; a single
ESS/grad < 0.9 falsifies the rule) + 1-2 NEW spendy healthy models from
outside CORE_SET to occupy the harm side. Same harness/protocol as W-76
(~5 models x 12 chain-runs, minutes each).

## Files

- Driver: `scratch/w76/driver.py` (log: `scratch/w76/driver.log`)
- Runs: `scratch/w76/runs/{C4,C5,C5MM2}/<model>/rep<r>_c<chain>.{csv,log}`
- Analyzer: `scratch/w76/analyze_w76.py` (JSON: `scratch/w76/w76_results.json`)
- Baseline: `scratch/w63/runs/A0/<model>/w1000_pf/` (reused, canary-proven)

## Conclusion

P3 (trajectory-policy pins) closes NEGATIVE on the cap side: per-model
`--max-trajectory-doublings 4` cannot pass ESS >= 0.95x at grads <= 0.9x
on any of the five models — where the cap binds it destroys ESS faster
than it saves grads (blr, the best case, is 0.435x ESS for 0.80x grads);
where it does not bind it saves nothing (hier_2pl null as designed). The
W-73 conditional GO is answered: the rung bounds were real but the
ESS-flatness premise was wrong. The only surviving signal from this
battery is the unregistered min-micro-2 quality direction on hier_2pl
(1.75x ESS/grad), which joins the per-model screening queue, not defaults.
