# W-36: End-to-end session headline benchmark — stock walnutpie vs session tip, both at DEFAULTS

One table quantifying the TOTAL sampler-side win of session 3:
**stock** `dev/init-robustness` @ `3eddfc4` (pre-session state) vs
**exp tip** `exp/safe-adapt-defaults` @ `43b6435`, both binaries run at
their CLI defaults, across the 10-model pathfinder grid.

## Setup

- Both arms: warmup=1000, draws=1000, 4 chains, 3 reps, seeds
  `20260819+1000*rep+c`. Everything else DEFAULT (metric window off, no
  `--fixed-warmup`, no `--early-exit`). Only `--warmup/--samples/--seed/
  --init-file/--output` (+`--chains 4 --chain-exec threads` for the
  parallel arm) passed.
- Binaries: exp built from the untouched submodule worktree
  (`external/walnutpie/build_w36exp`); stock built from a SEPARATE git
  worktree at `3eddfc4` (`external/walnutpie_stock_w36/build_w36stock`),
  submodule branch never switched.
- Arms: `stock_seq` = stock binary, 4 SEQUENTIAL single-chain invocations
  (pre-session status quo workflow; wall = batch elapsed);
  `exp_par` = exp binary, `--chains 4 --chain-exec threads`;
  `exp_seq` = exp binary, 4 sequential single-chain invocations
  (isolates endpoint-threading from parallelism).
- Model .so: `bs_models_threads/` STAN_THREADS=true builds for all 10
  models (8 newly compiled from per-model scratch copies — W-27 cache
  gotcha avoided), each verified via `model_info()`; the SAME .so per
  model in every arm.
- Inits (identical across arms): `inits_w25/` Pathfinder inits for
  hier_2pl + lsat_model; deterministic normal(0,1) unconstrained draws
  (`random.Random(f'{model}-{seed}-{c}').normalvariate`, dimension from
  BridgeStan) in `inits_w36/` for the other 8. Generator:
  `harness/gen_w36_inits.py`.
- Machine otherwise idle; sequential arms 1 process at a time; `exp_par`
  = 4 worker threads (within the 4-thread budget).

## Headline: wall (medians of 3 reps)

| model                            | stock_seq (s) | exp_par (s) | par/stock | exp_seq (s) | seq/stock |
|----------------------------------|--------------:|------------:|----------:|------------:|----------:|
| radon_partially_pooled_noncentered | 66.91  | 20.85 | 0.312 | 64.44 | 0.963 |
| bym2_offset_only                 | 116.23 | 44.92 | 0.386 | 113.47 | 0.976 |
| hier_2pl                         | 161.18 | 45.26 | **0.281** | 155.06 | 0.962 |
| diamonds                         | 11.10 | 4.79 | 0.432 | 9.68 | 0.872 |
| lsat_model                       | 38.23 | 11.90 | 0.311 | 36.57 | 0.957 |
| accel_gp                         | 5.50 | 2.19 | 0.398 | 5.30 | 0.965 |
| kronecker_gp *                   | 70.36 | 24.21 | 0.344 | 65.14 | 0.926 |
| pilots                           | 1.03 | 0.35 | 0.341 | 0.98 | 0.951 |
| eight_schools_centered           | 0.58 | 0.20 | 0.340 | 0.58 | 1.000 |
| lotka_volterra *                 | 9.84 | 2.94 | 0.299 | 8.89 | 0.903 |
| **GEOMEAN (10 models)**          |        |       | **0.341** |        | **0.947** |

**exp_par / stock_seq geomean = 0.341 (2.93x faster end-to-end at the
defaults a user gets without passing a single new flag).** Sum of
per-model medians: 481.0 s -> 157.6 s (0.328). Per-rep walls are tight on
the multi-second models (e.g. hier_2pl stock 160.0/161.2/164.1,
exp_par 43.7/45.3/46.5).

(*) kronecker_gp rep0 and lotka_volterra rep1 aborted deterministically in
ALL THREE arms (see Failures) — medians over the remaining 2 reps.

## Attribution: parallelism vs threading vs nothing

- **Parallelism (W-25 mc path + W-30 event-driven threads) is the whole
  headline**: exp_par/exp_seq geomean = 0.361 (2.77x). The honest cost:
  per-call logp_grad time under 4-way concurrency is +10–25% vs solo
  (e.g. hier_2pl 1200 vs 966 µs/call warmup; radon 454 vs 394; bym2 168
  vs 146 — shared memory bandwidth/cache), which is why the speedup is
  2.8–2.9x rather than the theoretical 4x, together with slowest-chain
  skew and the serial non-gradient remainder.
- **Endpoint-gradient threading (W-23) contributes 0.947 geomean
  (~5.6%) on top**: per-chain total logp_grad calls drop by EXACTLY
  warmup+draws−1 = 1999 on every completed chain of every model
  (verified chain-by-chain, e.g. hier_2pl rep2: 38270/39120/38908/40163
  -> 36271/37121/36909/38164). µs/call unchanged (exp_seq vs stock_seq
  within ±3%). Call-count fraction saved is model-dependent (hier 5.2%,
  pilots 4.5%, bym2 3.1% of calls).
- **Nothing else changed**: see canary below — draws are bit-identical.

Multiplicative check: 1.056 (threading) x 2.77 (parallelism) = 2.93x =
1/0.341.

exp_par vs exp_seq per-chain call totals differ by at most ±3 calls
(controller stop diagnostics evaluate logp at chain states); draws are
md5-identical regardless (below).

## Quality (non-negotiable gate)

arviz rank-normalized bulk/tail ESS-min and max rank R-hat per model
(median over reps; chains trimmed to min length — all chains 1000 draws):

| model                     | bulk ESS-min | tail ESS-min | R-hat max |
|---------------------------|-------------:|-------------:|----------:|
| radon_partially_pooled_nc | 74.0 | 206.7 | 1.0624 |
| bym2_offset_only †        | 4.2 | 4.0 | 4.9345 |
| hier_2pl                  | 624.7 | 800.2 | 1.0093 |
| diamonds †                | 4.4 | 11.1 | 3.6341 |
| lsat_model                | 730.1 | 1255.0 | 1.0112 |
| accel_gp †                | 4.3 | 4.0 | 4.1769 |
| kronecker_gp              | 48.1 | 67.0 | 1.0894 |
| pilots †                  | 4.6 | 11.5 | 3.0478 |
| eight_schools_centered    | 101.3 | 153.9 | 1.0380 |
| lotka_volterra            | 174.2 | 268.4 | 1.0199 |

**Every number is IDENTICAL across stock_seq / exp_par / exp_seq** — not
statistically matched but exactly equal, because the draws are
bit-identical:

- **Canary (pre-registered)**: stock_seq vs exp_seq chain CSVs md5-equal
  **28/28** completed cells (spot-checked before the grid on
  eight_schools_centered + lsat_model rep0, then on every cell).
- **Bonus (stronger)**: stock_seq vs exp_par chain CSVs md5-equal
  **28/28** — the exp binary's default `--chains 4` THREADED run
  reproduces the stock binary's sequential single-chain draws
  byte-for-byte on the whole grid. The session changed execution
  topology and removed redundant evaluations; it changed zero draws.

(†) The pathological rows are INIT-QUALITY artifacts, present identically
in every arm: the 8 non-pf models use plain normal(0,1) draws, and
bym2/diamonds/accel_gp/pilots chains get stuck in separated
regions/modes from such inits (the cmdstan pathfinder grid with pf inits
had e.g. bym2 ESS 346 / R-hat 1.009). This is a property of the init
protocol, not of any arm; it is visible here because both arms share the
identical files. hier_2pl/lsat_model (pf inits) are healthy.

## Gates

- (a) Safe default posture: every exp_par run printed
  `controller exit_iter=1000 early_exit=0` — 28/28 runs (W-31 default
  verified end-to-end at the tip).
- (b) Canary bit-identity: PASS 28/28 (above); the full-session chain of
  per-change canaries (W-23 24/24, W-30 12/12, W-31 12/12) composes to
  an end-to-end 3eddfc4 -> 43b6435 identity on this grid.
- (c) Quality: PASS by exact identity (above).
- (d) Walls: 3-rep medians with per-rep values in runs/w36/*/rows.csv.

## Failures (recorded, not arm-attributable)

kronecker_gp/rep0 and lotka_volterra/rep1 abort deterministically at
chain 0 after exactly 32001 logp_grad calls with
`terminate called ... std::invalid_argument: macro_time must be in
(0, inf)` — in the STOCK binary and identically in both exp arms (same
seed+init). This is a pre-existing warmup-adaptation robustness limit of
the sampler on these (seed, init) pairs, unchanged by the session;
medians for those two models use the remaining 2 reps. Worth a queued
item: guard non-finite adaptation state.

## Raw artifacts

- Runner/analysis: `harness/run_w36.py`, `harness/analyze_w36.py`,
  inits `harness/gen_w36_inits.py` + `inits_w36/`.
- Raw runs: `runs/w36/<arm>/<model>/rep<r>/` (chain CSVs + logs +
  rows.csv), md5 ledger `results/w36_md5.json`, walls
  `results/w36_wall.json`, quality `results/w36_ess.json`.
- Binaries: `external/walnutpie/build_w36exp/examples/stan_cli`,
  `external/walnutpie_stock_w36/build_w36stock/examples/stan_cli`
  (worktree removed after measurements were committed).
