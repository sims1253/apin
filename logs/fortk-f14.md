# F-14 log — batch/simulation-study throughput: fits/hour INCLUDING compilation

Started: 2026-08-26 ~20:15. Binding charter: WORKLOG "F-14 pre-registered"
(### F-13.2/F-14 section). Motivation: F-4b VERDICT — stanli_run
whole-process esnc walls 0.02-0.05 s with ~85-90% fixed pipeline cost;
the simulation-study workload metric (hundreds of small fits) is NOT the
single-fit sampler metric of F-8.

## Pre-registered design (from charter + WORKLOG)

- Worktree: external/stanli-f14, branch fortk/f14-batch off 9b2bf80
  (F-12 consolidated trunk). Own build dir build-f14 (Release, -j4).
  deps/{math,stan,stanc3} symlinked individually to ../../stanli/deps/*.
- COORDINATION: F-10 patches shared deps/stan atomically at its session
  start; first build only after logs/fortk-f10.md shows the apply (or
  deps/stan diff settled).
- Models: blr, eight_schools_noncentered (esnc). .stan in models/, data
  in data/ (bs_models corpus of apin workspace).
- ARMS (200 fits each, 4 chains x 200 warmup + 200 draws per fit,
  seed = 20260826 + i per fit, CmdStan stream convention where reachable):
  (a)  cmdstanpy per-fit subprocess loop (~/.cmdstan/cmdstan-2.39.0,
       `uv run python` from apin root). Two variants: a1 = model compiled
       ONCE per process, fresh sample() call per fit (honest best case);
       a2 = with-recompile per fit (simulation-study reality when models
       change; each fit re-runs stanc + make on a fresh exe).
  (b)  stanli python binding in-process loop: same Model object, 200
       sample() calls (unfused; _bin binding pattern).
  (c)  fortk_t1r CLI per fit, fused tier, process spawn each. Two
       variants: c-cold (fresh cache dir per fit = cold clang per fit)
       and c-warm (cache shared + prewarmed across fits).
  (d)  fused in-process multi-seed: NEW --fits N mode on my branch —
       model + emit + dlopen ONCE, then N sampling runs in-process
       (seeds 20260826+i). Minimal, flag-gated; committed.
- METRICS: fits/hour (headline), median per-fit wall (decompose
  compile+load vs sampling), (a2) compile share. 3 reps of the 200-fit
  batches where affordable; 1 rep stated otherwise. Timing hygiene:
  taskset the loops, quiet-box checks (pgrep before timing; re-run on
  >5% spread). <=4 concurrent processes per arm.
- PRE-STATED ORDER (a violation is a finding): b > a1; a1 > a2;
  d > c-cold; d >> a2.
- Deliverables: table + order verdicts + branch commits; raw under
  bench/fortk_f14/; this incremental log.

## Log

- (boot) log created FIRST; read WORKLOG fortk lane (F-14 charter,
  F-4b VERDICT, F-12/F-10 sections), logs/fortk-f8.md (campaign
  conventions), python/stanli/__init__.py (ctypes binding: embedded
  stanc3 when built into libstanli, else _bin/stanc subprocess;
  sample() = stanli_sample_multi + per-draw constrain loop in Python).
- F-10 status at session start: logs/fortk-f10.md placeholder (plan
  recorded, build of PRE-PATCH stock binary in flight in
  external/stanli-f7/build-f7); deps/stan diff EMPTY (patch not yet
  applied). Prep without building until it lands.
- Worktree created: external/stanli-f14 @ 9b2bf80, NEW branch
  fortk/f14-batch; deps/{math,stan,stanc3} symlinked individually to
  ../../stanli/deps/* (same shape as stanli-f7's).
- F-10 atomic apply CONFIRMED at 20:22 (log entry + verified myself:
  deps/stan status = exactly ` M base_nuts.hpp`, +63/-13, settled).
- Tool addition committed FIRST (code-before-build doctrine): c37b623
  `fortk_t1r: --fits N batch mode (F-14 arm d)` — flag-gated (default 0
  = byte-identical), --fits N --chains C: after the one
  stanc+lower+carve+emit+clang+dlopen pipeline, N fits in-process, fit i
  = C chains x (--sample W S), seed --seed+i, chains 1..C via
  create_rng, threads where the build allows; draws in memory; FITS_SUMMARY
  line (total/med/min/max fit wall + fits/hour). Arm (c) uses the same
  mode with N=1 per process spawn (production shape; the old --sample
  path runs unfused+paired+statistical-fallback diagnostics, not a fit —
  stated deviation, --no-verify --no-bench --no-direct since sampling
  consumes none of them).
- Build: first `cmake --build -j4` KILLED (cc1plus Terminated — memory
  pressure: 8 foreign cc1plus, 36/47 GB used, load 9.7 from F-10/F-11.2
  builds). Retried -j2.
- Runners written: bench/fortk_f14/{common,run_a,run_b,run_c,run_d,
  analyze}.py. Conventions encoded: 4 chains x 200+200, seed=20260826+i,
  per-arm parallelism = 4 (cmdstanpy parallel_chains=4, binding threads,
  tool threads) — every fit occupies exactly 4 cores; taskset -c 2-5 on
  every timed loop; quiet_check (loadavg + builder pgrep) recorded per
  record. Arm (a) builds cmdstan exes in bench/fortk_f14/cmdstan_src/
  (copies of the .stan sources — models/ dirs left untouched).
- Build round 2 (-j2): fortk_t1r + stanli_run BUILT 20:32/20:33.
  stanli_shared killed again by memory pressure mid-TU; round 3 resumed.
- SMOKE (taskset 2-5, build @ c37b623 + F-10's patched shared deps/stan):
  default path unchanged (fixture GATE_CORRECTNESS=PASS bitwise, both
  gates); --fits 3 esnc: 4 chains x 200+200 per fit, walls 2.7-3.1 ms,
  FITS_SUMMARY sane (fits/hour 1.25M sampling-only); --fits 2 blr:
  8.0-8.8 ms/fit. Draw equivalence to the --sample path is by
  construction (same run_nuts_chains call, chain_id=1 => ids 1..4 =
  CmdStan stream convention).

## CAMPAIGN (2026-08-26 20:52-21:45)

- stanli_shared finished at -j1 (20:56; the -j4/-j2 attempts were OOM-
  killed by foreign-build memory pressure, 8 cc1plus / 36 GB at peak).
  python/stanli/_bin populated with build-f14/libstanli.so +
  deps/stanc3/stanc (non-embedded fallback: Model() shells ONE stanc
  subprocess per construction; build_id abi1-c37b623b0a76).
- ctest --test-dir build-f14: **63/63 PASS**.
- Arm (b) smoke: Model 26 ms, fit(4x200+200) 29 ms, draws (4,200,6),
  beta.1 mean 0.9997 — pipeline valid.
- Loaded-box pass first (loadavg 6.6-10.6, foreign builds; spreads 5-29%
  — archived as results_loadedbox_evidence.json), then FULL quiet re-run
  (loadavg 1.4-4.0; spreads <=5% except c_warm-blr rep1 outlier which 6
  reps mediate). Load cost was real: d-blr 342k->508k, b-blr 135k->200k
  fits/hour between regimes. Reported numbers = quiet pass only.
- a2 aggregation bug caught + fixed + re-run (per-fit recompile walls
  initially excluded from batch total; the bad records were dropped, the
  fixed script re-measured: 458/445 fits/hour, compile share 99.6-99.7%).

## FINAL TABLE (fits/hour INCLUDING each arm's compile strategy;
200 fits/batch; medians of 3 reps — a2: 1 rep x 20 fits, compile-bound
so linear; per-fit = 4 chains x 200+200, seed 20260826+i, delta 0.8,
max_depth 10, 4-way parallel per fit on every arm; taskset -c 2-5)

| arm | blr | esnc | notes |
|---|---|---|---|
| a1 cmdstanpy compile-once (steady) | 117,386 | 166,707 | exe reused; ~30/21 ms per fit (4 chain procs + CSV + readback) |
| a1 first-batch incl one compile (derived) | ~52,000 | ~60,000 | 7.8-7.9 s compile (quiet a2 median) + 200 fits |
| a2 cmdstanpy recompile-per-fit | 458 | 445 | compile med 7.79/7.94 s = 99.6/99.7% of fit wall |
| b stanli binding in-process | 200,594 | 392,882 | 17.3/8.9 ms per fit; compile once 23 ms |
| c-cold fortk CLI, cold cache | 16,701 | 20,383 | 215/175 ms per fit; clang = 185/149 ms = 85-86% |
| c-warm fortk CLI, warm cache | 118,119 | 135,199 | 30.2/26.4 ms per fit; stanc subprocess = 20 ms = 66-76% |
| d fortk --fits 200 in-process | 508,260 | 1,156,832 | 7.08/3.11 ms per fit; 0.19/0.14 ms amortized compile |

Sampling-only decompositions (per-fit medians): d blr 6.94 ms / esnc
2.97 ms (FITS_SUMMARY); c arms sample 6.6/2.9 ms; b fit wall includes
the binding's per-draw constrain loop (800 ctypes calls).

## ORDER VERDICTS (all pre-stated orders HOLD, both models)

- b > a1: 1.71x (blr), 2.36x (esnc) — OK
- a1 > a2: 256x (blr), 374x (esnc) — OK
- d > c-cold: 30.4x (blr), 56.8x (esnc) — OK
- d >> a2: **1109x (blr), 2598x (esnc)** — OK (the headline)

## HONEST READ / surprises

1. The compile question IS the simulation-study question: a2's fit wall
   is 99.6-99.7% stanc+make. Every arm that avoids recompiling wins by
   2-3.5 orders of magnitude before any sampler speed matters.
2. c-warm ≈ a1 (118k vs 117k blr; 135k vs 167k esnc — a1 WINS esnc):
   per-fit process spawn of fortk re-runs stanc+lower every invocation
   (23 ms of 26-30 ms), which costs about what cmdstanpy's 4-proc
   spawn + CSV roundtrip costs. NOT a pre-stated order, reported as a
   finding: the CLI's per-fit win requires the cache AND still pays
   stanc; the real win is staying in-process (b) and amortizing the
   whole pipeline (d).
3. c-cold = 86% clang: the emitted region compiles in 149-187 ms —
   fortk's cold-compile-per-fit worst case is still 36-46x a2's
   7.8-7.9 s cmdstan recompile.
4. b's in-process loop beats a1 1.7-2.4x with UNFUSED gradients — the
   binding's single-process shape (no chain subprocesses, no CSV I/O)
   is worth more than fusion at this fit size; fusion then adds another
   2.5-2.9x through d (508k/1.16M vs 200k/393k).
5. Load sensitivity: all arms measured 30-45% faster after the foreign
   builds stopped (numbers above are the quiet pass; loaded pass kept
   as evidence of the bias).

## Provenance

- Branch fortk/f14-batch @ c37b623 (= 9b2bf80 + the --fits tool commit,
  64 lines added, flag-gated, default-off byte-identical — fixture gate
  bitwise PASS). NOT pushed. Worktree external/stanli-f14 clean.
- Built against F-10's ATOMICALLY-patched shared deps/stan (2a
  scratch-hoist, applied 20:22) — confirmed before first build.
- Raw: bench/fortk_f14/{results.json (quiet, reported),
  results_loadedbox_evidence.json, <model>/<arm>/rep<r>/fit*.out,
  warm_cache/, cmdstan_src/}; runners: run_{a,b,c,d}.py, analyze.py,
  common.py. 70 MB total.
- Reps: a1/b/c-cold/c-warm/d = 3 quiet reps (c_warm 6 — outlier pass
  included); a2 = 1 rep x 20 fits (time-bound; compile-dominated so
  extrapolation linear).
