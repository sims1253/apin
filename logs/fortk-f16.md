# F-16 — GRAND CAMPAIGN (pre-registered; the day's capstone measurement)

Status: BOOTING. Binding charter: WORKLOG "F-16 pre-registered" (2026-08-26).
Conventions cribbed from F-8 (logs/fortk-f8.md) + F-9 (logs/fortk-f9.md):
4 chains x (1000 warmup + 1000 draws), seeds 20260826+1000*rep+c (chain_id=1
on stanli arms; CmdStan chain_id 1..4 off the rep base), arms interleaved
within each rep, load+cc1plus recorded per rep, quiet-box rules, ESS via
harness/ess.R (per-param geomean, pooled 4 chains), ESS/draw = ESS/4000,
divergences + td-hits recorded, wall = max-chain sampler wall (A: CmdStan
"Elapsed Time (Total)"; C/D: tool SAMPLE_WALL exec1_s [+PF_WALL for pf arms];
B: proc wall minus pipeline0, derived+flagged as in F-8), medians of 3 reps.

PLAN (from registration):
- SETUP: worktree external/stanli-f7, trunk fortk/t2-coverage @ f47f001.
  1. Merge fortk/f14-batch (c37b623, --fits addition, default-off) into trunk.
     Gate: ctest 64/64 + esnc --sample 200 200 byte-identical vs premerge.
  2. Rebuild if needed (-j2, serialized, only lane running).
  3. Stage F-13 fused stanc for kronecker: /tmp/f16-stage with deps/stanc3/stanc
     -> external/stanc3/_build/default/src/stanc/stanc.exe + model/data copies;
     kronecker arms run from that cwd, all other models from normal cwd.
- CAMPAIGN: 8 models (radon_pp = radon_partially_pooled_noncentered,
  radon_var_slope = radon_variable_intercept_slope_noncentered, bym2_offset_only,
  hier_2pl, lsat_model, diamonds, arma11, kronecker_gp) x 5 arms:
  A cmdstan nuts (cmdstanpy, ~/.cmdstan/cmdstan-2.39.0); B stanli unfused
  (build-rel/stanli_run in external/stanli main checkout, run in place, NOT
  rebuilt); C trunk fused nuts (fortk_t1r default init); D trunk fused walnuts
  default knobs + pf-init; D_b10 walnuts --w-batch 10 + pf-init.
- DELTA x DEPTH sweep: fused nuts, delta {0.5,0.7,0.8,0.9,0.95} x depth
  {8,10,12} on 6 phase-1 models (esnc, esc, blr, pilots, kidscore, logmesquite)
  + hier_2pl. CmdStan interaction control at delta {0.7,0.9} on esnc/blr/
  hier_2pl. Adoption rule (pre-stated, verbatim): >=3% geo ESS/s, no model
  >10% regression, divergences not worse, td-hits <=5%.
- CAPSTONE ATTRIBUTION: per model measured (C vs A ESS/s) vs product of
  individually-measured layer gains (interpreter-vs-cmdstan F-8 B-arm;
  fusion F-8 C/B; T2 + loop from F-7/F-10 census ratios where available).
- BUDGET: ~2-4h wall. Fallback if >5h: cut sweep to delta-grid-only at depth 10.
  Checkpoint raw under bench/fortk_f16/; resumed agent skips completed cells
  by reading this log + the raw dir. <=6 concurrent sampling procs; CPU only;
  no upstream; never git add -A; do not touch other worktrees, /tmp/stanli-b7a3fd5,
  WORKLOG.md, other logs.

## Log

- [setup] Worktree external/stanli-f7 @ f47f001 clean; build-f7/fortk_t1r
  verified current (make: nothing to do). Binary snapshotted to
  build-f7/fortk_t1r.premerge_f16; premerge reference esnc --sample 200 200
  captured at bench/fortk_f16/gate_merge/pre/.
- [merge] git merge fortk/f14-batch -> 2 conflicts in tools/fortk/regions.cpp
  (usage string + arg-parse chain), both trivial UNION resolutions (f112
  walnuts knobs + f14 --fits/--chains coexist; --fits block guarded by
  sample_fits>0 BEFORE the normal --sample path => default-off). One leftover
  conflict marker caught by the build (compiler treats it as error) — removed.
- [gate] ctest 64/64 PASS. esnc --sample 200 200 seed 20260826 chain 1:
  BYTE-IDENTICAL vs premerge (GRAD_COUNTER exec1=4079 hits1=61 = F-10/F-15
  recorded values exactly). Merge committed as 921a6fc.
- [flags] Tool lacked delta/depth CLI (NutsConfig.delta/max_depth already
  runtime-consumed end-to-end per F-11 inventory). Added --delta / --max-depth
  (minimal, override-only-when-non-default, default 0.8/10). Gates: default
  path esnc BYTE-IDENTICAL vs premerge; --delta 0.5 --max-depth 8 bites
  (SAMPLE_ADAPT delta=0.5 max_depth=8); ctest 64/64. Commit 4690a00.
- [stage] /tmp/f16-stage: deps/stanc3/stanc -> F-13 stanc.exe + kronecker
  model/data copies. Smoke through trunk binary: FORTK ops=221->94 regions=33,
  VERIFY grad/logp 0.0/0.0 BITWISE PASS, --sample works (matches F-15).
- [runner] bench/fortk_f16/run_f16.py (F-8 runner shape; per-cell done
  markers + results_partial.json for resume; ess.R per (model,rep,arm) on
  intersection columns; pipeline0 for B; F16_BENCH env for validation bench).
  Mini validation (200+200, hier_2pl + kronecker, scratch bench): all 5 arms
  + ESS end-to-end PASS. Validation findings: (i) kronecker B (stanli_run,
  stock stanc) vs C (trunk tool, F-13 stanc, staged cwd) draws BIT-IDENTICAL
  (same ESS/div/td to the digit) — the F-13.2 fused-lowering bit-identity
  holding end-to-end through NUTS sampling; (ii) 200+200 walls kronecker
  A 147s B 132s C 102s D 4.2s D_b10 6.3s -> full-run extrapolation ~730/660/
  ~530(ex1)+660(ex0 proc) -> kronecker dominates campaign budget (~44
  min/rep, arms must stay sequential per interleave doctrine).
- [launch] CAMPAIGN launched (3 reps x 8 models x 5 arms, model-major,
  arms adjacent).
- [campaign, rep0 through arma11] Arms A/B/C/D/D_b10 per model; load at cell
  starts 3.9-5.6 (our own 4-chain arms), cc1plus=0 throughout. Early cells
  (sampler walls, s): radon_pp A 30.0 B 6.4 C 4.1 D 3.2 D_b10 4.9;
  radon_vs fast; bym2 A 37.5 B 33.9 C 17.7 D 12.8 D_b10 20.5 (D ESS 557
  vs A 4011 rhat 1.055; D_b10 1115 rhat 1.066 — walnuts weak on bym2);
  hier_2pl A 75.5 B 37.2 C 16.2 (C/A = 4.7x wall) D 30.0; lsat B 7.6 C 3.3;
  diamonds A 64.9 B 68.6 (B NOT faster on diamonds) C ~78 (0.85x kernel)
  D 15.4 D_b10 25.3 (D rhat 1.108, D_b10 1.030 — again weak ESS);
  arma11 A 0.19 B 12.8 C 2.67 D 0.027 D_b10 0.054.
- [finding, arma11] B AND C arm chain 1 (seed 20260827) BOTH stuck at the
  identical far-off position (lp -2.53e5, stepsize 1.2e-7, td 10; ESS 8,
  rhat ~1.58-1.59 both arms). Seed-specific failure of stanli's NUTS on
  arma11 from a far init — NOT a fusion artifact (identical stuck position
  in the unfused interpreter AND the fused regions; ex0-vs-ex1 in-tool
  bitwise=NO on that chain, max_abs_diff 1.2e-5, both equally stuck).
  CmdStan with the same stream mixes fine (A: ESS 4081, rhat 1.0009).
  Reported honestly; medians over 3 reps decide whether it's one rep or
  systematic (reps use different seeds).
- [sweep prep] Sweep runner bench/fortk_f16/run_f16_sweep.py. Validation on
  blr (100+100, scratch bench): first run hit a 4-way concurrent region-cache
  miss race (chain rc=3 mid-emit; all four chains emit+clang the same fresh
  key) -> added single-process per-model cache prewarm (the campaign runner's
  own doctrine); revalidation clean end-to-end (cells, ESS, div/td, cmdstan
  control, resume markers). NOTE (honesty): the ~3 min of sweep validation
  overlapped campaign kronecker rep0 arm A (recorded load in that cell's
  state field); no further concurrent work during campaign arms from here.
- [CAMPAIGN DONE 03:18; 22:53-03:18 = 4h25m; all 120 cells; loads 3.9-5.6
  at cell starts (own arms), cc1plus=0 throughout; done markers + raw under
  bench/fortk_f16/{<model>/rep<r>/<arm>/, results_partial.json,
  ess_partial.json, pipeline0.json, campaign.out}]

  PHASE-2 TABLE (medians of 3 reps; ESS_bulk/s = per-param geomean ESS /
  max-chain sampler wall; ratios vs A):

  | model     | A cmdstan | B unfused    | C fused nuts | D walnuts+pf     | D_b10 b10+pf     |
  |-----------|-----------|--------------|--------------|------------------|------------------|
  | radon_pp  | 121       | 602 (4.98x)  | 1,029 (8.51x)| 956 (7.90x)      | 938 (7.76x)      |
  | radon_vs  | 1,288     | 4,178 (3.24x)| 6,541 (5.08x)| 5,899 (4.58x)    | 6,094 (4.73x)    |
  | bym2      | 116       | 121 (1.04x)  | 218 (1.88x)  | 44 (0.38x NC)    | 54 (0.47x, rh1.03)|
  | hier_2pl  | 104       | 186 (1.80x)  | 483 (4.67x)  | 103 (1.00x)      | 100 (0.97x)      |
  | lsat      | 649       | 909 (1.40x)  | 1,648 (2.54x)| 936 (1.44x)      | 1,010 (1.56x)    |
  | diamonds  | 52        | 46 (0.88x)   | 40 (0.77x)   | 30 (0.58x NC)    | 31 (0.59x, rh1.05)|
  | arma11    | 24,758    | 31,539(1.27x)| 100,248(4.05x)| 128,985 (5.21x) | 62,618 (2.53x)   |
  | kronecker | 2         | 2 (1.13x)    | 3 (1.40x)    | 23 (10.5x NC rh1.11)| 18 (8.21x NC rh1.34)|
  | GEOMEAN   | 1.00x     | 1.65x        | 2.84x        | 2.23x            | 2.06x            |

  ESS/draw geomean per arm: A 0.94, B 0.99, C 0.99, D 0.47, D_b10 0.68
  (per-model: C parity-or-better vs A on 7/8; diamonds 0.80 vs 0.85).
  Divergences: 0 everywhere except kronecker (A 19, B/C 24 per 1k; known
  stiff geometry) — div reported n/a for walnuts (NaN by design).
  td-hits/4k: kronecker ~3980 for A/B/C (99.5%, phase-0 confirmed);
  diamonds ~3232/3439/3368; others 0. Walls: kronecker A 708s / B 655 /
  C 532 (sampler) — C proc 1047s (tool runs ex0+ex1; wall metric unaffected).

  KEY READS: (1) C (fused nuts) = best default on 7/8 models (all but
  diamonds, where B/A/C all ~parity and C 0.77x — the known bandwidth
  negative); geomean 2.84x. (2) B (unfused) beats cmdstan 1.65x geomean —
  the interpreter+sampler loop alone. (3) D walnuts wins radon_pp (7.90x,
  ESS/draw 0.78) and arma11 (5.21x) but fails bym2/diamonds/kronecker
  (rhat 1.05-1.34, ESS/draw 0.07-0.29); D_b10 fixes bym2 to borderline
  (rhat 1.027, ESS/draw 0.29) but not kronecker. (4) kronecker B==C draws
  BIT-IDENTICAL all 3 reps (F-13.2 eigh-fusion bit-identity through NUTS);
  C/A 1.40x from wall alone. (5) arma11 rep0 seed-specific stuck chain
  (see finding above) — median absorbs; reps 1-2 healthy all arms.

- [attribution, consistent medians] measured C/A vs product of layers
  (interp=B/A today; kernel=F-6/F-7/F-13.2 census fused/unfused µs/call;
  loop=F-10 wall gain, hier_2pl only; F-8 sampling-level fusion = GAP):

  | model     | B/A   | kernel | loop | product | C/A meas | meas/prod |
  |-----------|-------|--------|------|---------|----------|-----------|
  | radon_pp  | 4.98x | 1.58x  | 1.0* | 7.87x   | 8.51x    | 1.08x     |
  | radon_vs  | 3.24x | 1.88x  | 1.0* | 6.10x   | 5.08x    | 0.83x     |
  | bym2      | 1.04x | 1.28x  | 1.0* | 1.33x   | 1.88x    | 1.41x     |
  | hier_2pl  | 1.80x | 2.20x  | 0.98 | 3.90x   | 4.67x    | 1.20x     |
  | lsat      | 1.40x | 1.84x  | 1.0* | 2.58x   | 2.54x    | 0.99x     |
  | diamonds  | 0.88x | 0.85x  | 1.0* | 0.75x   | 0.77x    | 1.03x     |
  | arma11    | 1.27x | 5.47x  | 1.0* | 6.97x   | 4.05x    | 0.58x     |
  | kronecker | 1.13x | 1.24x  | 1.0* | 1.40x   | 1.40x    | 1.00x     |
  | GEOMEAN   | 1.65x | 1.75x  |      | 2.88x   | 2.84x    | 0.99x     |

- [SWEEP DONE 04:42; 03:19-04:42 = 1h23m; fallback grid (delta 5 x depth 10)
  x 7 models x 3 reps + cmdstan control {0.7,0.8,0.9} x 3 models x 3 reps;
  raw bench/fortk_f16/sweep/]

  FUSED NUTS delta sweep @ depth 10 — ESS/s ratio vs (0.8,10) per model
  (medians of 3 reps):

  | model    | d0.5        | d0.7        | d0.8 | d0.9        | d0.95       |
  |----------|-------------|-------------|------|-------------|-------------|
  | esnc     | 1.00x       | 1.60x       | 1.00 | 0.88x       | 0.42x       |
  | esc      | 0.67x       | 2.06x       | 1.00 | 1.07x       | 0.94x       |
  | blr      | 1.76x       | 1.05x       | 1.00 | 0.67x       | 0.56x       |
  | pilots   | 0.70x       | 2.20x       | 1.00 | 0.88x       | 0.26x       |
  | kidscore | 1.23x       | 1.19x       | 1.00 | 0.90x       | 0.71x       |
  | logmesq  | 0.27x       | 0.73x       | 1.00 | 0.68x       | 0.52x       |
  | hier_2pl | 1.33x       | 0.71x       | 1.00 | 0.95x       | 0.52x       |
  | GEOMEAN  | 0.865x      | 1.247x      | 1.00 | 0.850x      | 0.524x      |

  Divergences (median, per 1k draws summed 4 chains): d0.5 explodes
  (esnc 205, esc 232, logmesq 304, pilots 1321 vs 0/56/0/557 at d0.8);
  pilots td-rate rises monotonically with delta: 5.2% (0.5) / 9.8% (0.7) /
  7.8% (0.8) / 26% (0.9) / 38.5% (0.95); hier_2pl div 0 everywhere.

  ADOPTION VERDICT (pre-stated rule verbatim: >=3% geo ESS/s, no model >10%
  regression, divergences not worse, td-hits <=5%):
  - d0.7: geo 1.247x PASSES the 3% bar, FAILS the other three — logmesq
    0.73x (27% regression), div worse (esnc 3>0, esc 79>56, pilots 679>557),
    pilots td 9.8% > 5%. NO ADOPTION.
  - d0.5 / d0.9 / d0.95: fail the geo bar outright (0.865x / 0.850x / 0.524x).
  => delta stays 0.8 (default). The F-11 hypothesis that cheap fused
  gradients shift the optimum toward HIGHER accept targets is REFUTED
  (0.9 = 0.85x geo, worse everywhere that matters); if anything the grid
  leans 0.7-ward (1.25x geo) but the safety criteria kill it.

  CMDSTAN interaction control (adapt_delta @ depth 10, ESS/s vs own d0.8):
  esnc 0.81x (0.7) / 0.98x (0.9); blr 1.31x / 1.15x; hier_2pl 0.69x / 0.77x.
  CmdStan's optimum is also d0.8 on 2/3 (blr mildly 0.7). The delta-response
  SHAPE is similar across engines: no interaction effect between fusion and
  delta — the fused advantage is delta-invariant to first order.

- [close-out] Session totals: campaign 4h25m + sweep 1h23m = 5h49m wall
  (fallback was engaged pre-sweep per the pre-stated >5h trigger; campaign
  alone was 4.4h and untouchable). Trunk @ 4690a00 (merge 921a6fc + delta/
  depth plumbing). Everything committed; raw under bench/fortk_f16/; this
  log is the ledger. Honest caveats carried: (1) kronecker C arm sampler
  wall is the fused executor's; the tool ALSO samples ex0 unfused in-process
  (proc 1047s) — wall metric unaffected; (2) walnuts div/td structurally
  n/a (NaN stats by design); (3) arma11 rep0 seed-specific stuck chain in
  BOTH stanli arms (medians absorb); (4) bym2 D_b10 rhat median 1.027 —
  borderline, ESS/draw 0.29; not marked NON-CONV at the 1.05 threshold.
