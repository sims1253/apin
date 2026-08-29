# F-18 — closing ESS/s confirmation (pre-registered in WORKLOG)

Status: BOOTING — charter = WORKLOG "F-18 pre-registered" + "F-17 VERDICT" +
"F-8 PHASE 1 VERDICT" (baseline table + conventions).

Plan (from registration):
- 6 phase-1 models, arms A (CmdStan nuts, cmdstanpy ~/.cmdstan/cmdstan-2.39.0)
  + C (trunk fortk/t2-coverage @ 2bc451a, build-f7 fortk_t1r, default init u).
  B/D NOT re-run — reuse F-8 rows for context.
- Exactly F-8 conventions: 4 chains x 1000+1000, seeds 20260826+1000*rep+c
  (stanli chain_id=1; arm A seed=base+1000*rep, chain_id 1..4 — identical
  streams), 3 reps medians, arms interleaved per rep (model-major),
  ESS via harness/ess.R (geomean per-param ESS_bulk pooled 4 chains;
  ESS_bulk/draw sanity), divergences, td-hits, wall = max-chain sampler wall
  (A: CmdStan CSV "Elapsed Time (Total)"; C: SAMPLE_WALL exec1_s).
- EXTRA (charter): record per-model grads/iter from tool GRAD_COUNTER to
  confirm the F-17 endpoint-threading effect is present in the campaign
  binary (expect exec1 ≈ transitions-1 relative to evals; hits1 -> 0).
- Rules: <=4 concurrent sampling procs, quiet box, CPU only, no upstream,
  no git changes, raw under bench/fortk_f18/.
- No adoption gate: final-state measurement. Expected (registered): C vs
  F-8's C ~1.3-1.7x ESS/s on bookkeeping-dominated small class; measured
  not assumed.

## Log

- (boot) log created. Read WORKLOG F-17 VERDICT + F-18 pre-reg + F-8 VERDICT;
  logs/fortk-f8.md in full (conventions cribbed verbatim from its runner).
- Environment verified: worktree external/stanli-f7 @ 2bc451a, clean, no git
  changes (measurement only); build-f7/fortk_t1r (Aug 27 06:00) newer than
  tools/fortk/regions.cpp (Aug 26 22:18) = current; quiet box (load 1.47,
  cc1plus=0, no fortk/cmdstan procs); F-8's CmdStan 2.39.0 model exes reused
  (compile-once doctrine, models/<name> Aug 26 vintage); all 6 model+data
  pairs present; cmdstanpy 1.3.0 via .venv (uv), cmdstan_path 2.39.0.
- THREADING SMOKE (pre-campaign, campaign binary vs F-17's fortk_t1r.pre,
  esnc --sample 200 200 --seed 20260826 --chain-id 1):
  pre exec0=4093/71 exec1=4079/61 -> cur exec0=3765/0 exec1=3741/0.
  exec1 drop = 338 = (iters-1=399) - 61 pre cache hits, EXACT; hits -> 0.
  Threading effect (F-17 lever d) CONFIRMED present in the campaign binary.
  (Walls from this smoke not comparable: pre ran cache-cold.)
- Runner: bench/fortk_f18/run_f18.py — adapted from F-8's run_f8.py, arms
  A + C only, model-major arms-adjacent per rep (F-8 order), <=4 concurrent
  sampling procs (A: cmdstanpy parallel_chains=4; C: 4 tool procs), fresh
  region_cache under bench/fortk_f18/ prewarmed --sample 1 1 seed 9999,
  canonical CSVs on F-8's 4-arm-intersection column basis (headers read
  from bench/fortk_f8/<m>/rep0/ess_A) so ESS is directly comparable to the
  published F-8 rows; GRAD_COUNTER parsed per chain (exec/hits/gpi).
- Mini validation (esnc+pilots 200+200 x 3 reps via env overrides): end-to-end
  OK incl. ess.R; hits1=[0,0,0,0] on all chains; smoke dirs then removed.
- (process note) first full-campaign launch aborted on a stale 2-model
  exes.json left by the smoke (prewarm skipped by marker) — state cleaned
  (region cache kept warm), relaunched fresh. No measurement data was kept
  from the aborted launch except rep0/esnc which was also discarded.
- CAMPAIGN: ran 06:15:49-06:17:45, 3 reps, model-major, arms A then C
  adjacent per model; loads 2.06/3.59/4.06 at rep starts, cc1plus=0
  throughout (own 4 procs included in load; foreign load ~1.5-3 present).
  All 18 (model,rep) cells, rc=0. Raw: bench/fortk_f18/{<model>/rep<r>/
  {A_cmdstan,C_fused_nuts}/chain<c>/, results_raw.json, campaign.out}.

## DRAW-IDENTITY VALIDATION (the strongest check of the campaign)

Arm A reuses F-8's CmdStan 2.39.0 exes + the pre-registered seed formula →
same streams as F-8's A; arm C's F-17 levers are draws-byte-identical by
gate → same draws as F-8's C. Both CONFIRMED at campaign scale:
- A today: per-rep ESS_bulk geomeans IDENTICAL to F-8's A (rel diff 0.0000
  on all 6 models; div/td/rhat rows identical too, e.g. esc A 43 div/1k,
  pilots A 180/653).
- C today: per-rep ESS values identical to F-8's C to full precision
  (e.g. esnc [3841.73, 3996.09, 4226.46] both days).
=> C/F8-C ratios below are PURE WALL effects; ESS/draw, divergences, td,
rhat are unchanged from F-8's C rows (geomean ESS/draw 0.238 as published).
The wall difference on arm A between days (today 1.15-1.41x F-8's A walls)
is therefore pure environment (box load), NOT a sampling difference.

## CLOSING TABLE (medians of 3 reps; ESS_bulk/s = geomean per-param ESS /
max-chain sampler wall; F-8 columns quoted from its published table)

| model | A today | C today | C/F8-C (loop pkg) | C/A today | F8 A | F8 B | F8 C | F8 D |
|---|---|---|---|---|---|---|---|---|
| esnc | 89,249 | 470,858 | 1.43x | 5.28x | 141,603 | 135,032 | 329,847 | 696,974 |
| esc | 3,058 | 35,247 | 1.83x | 11.52x | 3,709 | 17,436 | 19,213 | 24,269 |
| blr | 19,178 | 101,660 | 1.67x | 5.30x | 21,983 | 33,006 | 60,787 | 176 NON-CONV |
| pilots | 29 | 187 | 1.96x | 6.37x | 32 | 69 | 96 | 565* stuck |
| kidscore | 2,936 | 13,891 | 1.05x | 4.73x | 3,490 | 5,226 | 13,177 | 46 NON-CONV |
| logmesq | 6,807 | 41,536 | 1.76x | 6.10x | 9,133 | 11,751 | 23,634 | 24,879 |
| GEOMEAN | 3,814 | 23,817 | **1.59x** | **6.24x** | 4,772 | 8,302 | 15,022 | 3,524 |

C sampler walls (median s, F-8 -> today): esnc .0122->.0082 (1.49x), esc
.0314->.0194 (1.62x), blr .0242->.0134 (1.81x), pilots .6142->.3853 (1.59x),
kidscore .1076->.1029 (1.05x), logmesq .0824->.0497 (1.66x).

C/A headline honesty: both arms measured today, interleaved, same box state
=> 6.24x is a fair paired ratio. But A's walls today run 1.15-1.41x F-8's A
walls (draws identical => environment): cross-normalizing to F-8's A day
gives C_today/F8-A geomean = **4.99x**. Headline range: 5.0x (F-8-A-day
normalized) to 6.24x (paired today). F-8's published C/A was 3.15x.

## GRADS/ITER (charter item; fused exec1, GRAD_COUNTER, 12 chains x 2000 iters/model)

| model | med gpi1 | med exec1 | sum hits1 (of 24,000 iters) |
|---|---|---|---|
| esnc | 8.741 | 17,482 | 8 |
| esc | 20.447 | 40,894 | 3 |
| blr | 16.412 | 32,824 | 6 |
| pilots | 276.353 | 552,706 | 0 |
| kidscore | 31.920 | 63,840 | 3 |
| logmesq | 45.823 | 91,646 | 4 |

Endpoint-cache hits ~0.05% (warmup-boundary re-evals; sampling-phase hits
are 0). Pre-vs-cur binary check (esnc 200+200, above): exec1 drop 338 =
399 - 61 pre-hits, EXACT. Threading effect present in the campaign binary.

## HONEST READ

F-17's 1.886x esnc loop ratio translated into 1.59x geomean ESS/s on the
phase-1 class — inside the registered 1.3-1.7x band, and the translation
is pure wall (draws bit-identical, ESS/div/td unchanged from F-8's C).
Where it landed vs the microbench: blr 1.67x and esc/logmesq/pilots
1.8-2.0x bracket the expectation; esnc 1.43x is diluted because the
campaign wall includes 1000 warmup iters of adaptation machinery the
levers never touched (and its 8 ms walls are timer-noise sensitive), and
because the microbench's 1.886x was sampling-transitions-only. The one
miss is kidscore at 1.05x — statistically flat: it is the most
gradient-bound model of the six (med 31.9 grads/iter at ~1.6-1.7 us/eval
vs esnc's ~0.6), so the ~2.3 us/transition bookkeeping F-17 removed is
<5% of its per-iter budget; the predicted gain from the measured per-eval
seam saving (~6 us/iter) matches the observed ~5%. Loop-package gains
scale with bookkeeping share, exactly as the attribution said they would.
Net lane picture after F-18: fused NUTS on trunk 2bc451a delivers
5.0-6.2x CmdStan ESS/s geomean (vs 3.15x at F-8, 1.74x for the unfused
loop at F-8) at ESS/draw parity-or-better (0.238 vs 0.169), with the
known esc adaptation-internals divergence difference reproduced
identically (A 43 vs C 14 div/1k) and pilots hard for everyone.

## Deviations / notes

- None from the F-8 conventions. B/D not re-run (F-8 rows quoted); A/C
  only, as registered. No adoption gate; closing measurement.
- git: no changes (WORKLOG.md was already modified before this session
  started — mtime 06:09 vs first command 06:10; the +1148 lines are the
  uncommitted F-1..F-17 lane history, not mine). stanli-f7 clean @ 2bc451a.
- Analysis: bench/fortk_f18/analyze_f18.py -> analysis.json/analysis.out.
- Per-rep spreads flagged (esnc/esc/blr/pilots C >2x, tiny-ESS pilots
  expected; medians reported per convention).
