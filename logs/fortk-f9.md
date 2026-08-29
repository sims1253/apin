# F-9 — Pathfinder-init vs the WALNUTS stuck chains (pre-registered)

Status: BOOTING. Protocol: WORKLOG "F-9 pre-registered BEFORE running";
reference arms from F-8 (logs/fortk-f8.md, bench/fortk_f8/); pf protocol
harness/run_pathfinder.py. Worktree /tmp/stanli-b7a3fd5 @ d4801b5 detached.

Plan (from registration):
- Arms C_pf (fused nuts + pf), D_pf (fused walnuts + pf), A_pf (CmdStan nuts
  + pf) on the same 6 phase-1 models; existing A/B/C/D rows are the reference.
- Tool gains --init pf: multi-path pathfinder over the FUSED executor,
  CmdStan-default knobs (num_paths=4, 1000 draws/path, 1000 PSIS draws),
  chain init = one PSIS draw picked by a documented (pf-seed, seed,
  chain-id)-keyed rng. Wall includes pf (per protocol).
- Gates: (a) D_pf blr+kidscore rhat<1.01 all-chain AND ESS_bulk/draw>=0.1;
  (b) no regression D_pf esnc/esc/logmesq vs D-or-better, C_pf no worse than
  C; (c) report D_pf vs C_pf and D_pf vs C geomean ESS/s.

## Log

- (boot) log created; read WORKLOG F-8 verdict + F-9 pre-reg, logs/fortk-f8.md,
  harness/run_pathfinder.py. Key mechanics from F-8 to reuse: runner shape
  (bench/fortk_f8/run_f8.py), seeds 20260826+1000*rep+c w/ chain_id=1,
  canonical-CSV filter + ess.R pooled 4-chain ESS, region_cache prewarm,
  load+cc1plus per rep, SAMPLE_WALL exec1_s = sampler wall.
- (read) stanli runtime: stanli::run_pathfinder (runtime/src/pathfinder.cpp)
  drives stan::services::pathfinder::pathfinder_lbfgs_single<false,false>
  over an ExecutorModel with identity write_array => PathfinderResult.draws
  are UNCONSTRAINED (exactly NutsConfig::init's contract), with lp and
  lp_approx per draw. estimate.hpp: multi-path service itself needs real
  TBB (parallel_for) which this build stubs => stanli has no multi-path
  wrapper. Stan's own multi algorithm (deps/stan .../pathfinder/multi.hpp,
  psis.hpp): N single paths at stride_id+iter (CmdStan: id=1, num_paths=4),
  pool num_paths*1000 lp-ratios (lp - lp_approx), tail_len =
  min(0.2*N, 3*sqrt(N)), psis_weights (HEADER-only, no TBB calls in it),
  resample num_psis_draws=1000 indices via create_rng(seed, stride_id=1)
  + boost discrete_distribution, sorted. CmdStan 2.39 defaults confirmed in
  arg_pathfinder.hpp: num_paths 4, num_draws 1000, num_elbo_draws 25,
  num_psis_draws 1000, max_lbfgs_iters 1000, history_size 5 (arg_lbfgs) —
  all equal to PathfinderConfig defaults.
- (read) run_nuts AND run_walnuts honor cfg.init (const double*,
  unconstrained; validated finite lp+grad via initialize_point /
  cmdstan_init_point). Walnuts arm: run_walnuts(ex1, cfgw) at
  tools/fortk/regions.cpp:2510; nuts arm runs BOTH ex0 and ex1 with the
  same cfg (bitwise self-check) — with pf init both get the SAME init
  point, keeping that comparison same-init.
- (design, stated) IMPLEMENTATION of num_paths=4 without real TBB: new
  runtime API stanli::run_pathfinder_multi (runtime/src/pathfinder.cpp +
  estimate.hpp) = multi.hpp's psis_resample=true path run sequentially:
  4 x stanli::run_pathfinder over the SAME executor at chain_id 1..4
  (= multi's stride_id+iter), pooled ratios, stan::services::psis::
  psis_weights, create_rng(seed,1)+discrete_distribution resample of 1000,
  sorted exactly as multi.hpp. Only the parallelism is lost, not the
  algorithm. Tool side: --init pf runs it ONCE over the FUSED executor
  (ex1); every chain process of a (model,rep) uses the same pf seed so all
  chains share ONE pf run's draws (bit-identical; verified in smoke), and
  chain c's init = draws[pick] with pick = splitmix64((pf_seed<<32) ^
  (seed<<8) ^ chain_id) % 1000 — mirrors run_pathfinder.py's
  random.Random(f'{seed}-{c}') pick, which is Python-MT and not portable
  to C++; splitmix64 is the stated substitute. NEW FLAG --pf-seed N
  (default: follow --seed) so the runner can pin pf to the rep base seed
  20260826+1000*rep while chains keep their per-chain --seed base+c.
  Wall: tool prints PF_WALL pf_s (measured around run_pathfinder_multi);
  campaign wall = pf_s + SAMPLE_WALL exec1_s (pf once per max-chain wall —
  matches run_pathfinder.py's batch convention where pf_secs is added once
  while 4 chains run concurrently). Default (no flag) path byte-identical:
  verified vs the F-8 binary below.
- (design, stated) A_pf wiring cribbed from harness/run_pathfinder.py:
  CmdStan exe method=pathfinder (defaults => num_paths=4, PSIS-resampled
  CSV) per (model, rep) with seed=20260826+1000*rep, id=1; chain c init
  JSON = random.Random(f'{base}-{c}') draw unflattened to the parameters
  block (their exact code, incl. param_names regex); then 4 concurrent
  single-chain sample runs (id=c+1, seed=base). wall = max-chain
  "Elapsed Time (Total)" + pf_secs.
- (impl) runtime: stanli::run_pathfinder_multi added (runtime/src/
  pathfinder.cpp + estimate.hpp). Tool: --init pf / --pf-seed in
  tools/fortk/regions.cpp; PF_INIT + PF_WALL lines; pf_draws CSV per
  invocation; both sampler branches set cfg.init. Build -j2 while F-7 was
  compiling (4 cc1plus, load 4.4) — build is untimed; campaign-time
  hygiene re-checked per rep.
- (identity) default path byte-identical: old binary (fortk_t1r.f8bak
  snapshot) vs new, blr --sample 1 1 --seed 20260826: sample CSV
  byte-identical, log identical modulo timing lines, 0 PF_ lines. One
  regression caught + fixed here: first cut appended "init=u" to the CSV
  comment unconditionally, breaking byte-identity; now only "init=pf"
  appears when the flag is on.
- (smoke, blr) walnuts+pf 2 chains (seeds ...26/27, pf-seed ...26, full
  1000+1000): BOTH chains in the same sigma basin, quarter means
  1.02-1.06, last200 sd 0.07 — vs D's parked 4.8/2.2/1.7/0.7. Pooled
  2-chain ess: geomean 281 (ESS/draw 0.14), rhat 1.012. nuts+pf: sigma
  ~1.03, statistical fallback worst_z 1.4-2.3 (normal).
- (pf validation, blr) paths_ok=2/4 (paths 2,4 fail with "Line search
  failed ... Optimization failed to start") — CmdStan's own pathfinder on
  the same seed fails the SAME two paths. Our PSIS sigma marginal vs
  CmdStan pf.csv: mean 1.0398/sd 0.0777 vs 1.0400/0.0733, q10/q90 match
  to 0.007. pf wall ~2 ms (blr), draws bit-identical across the chain
  processes sharing pf-seed.
- (smoke, kidscore) walnuts+pf 4 chains (seeds ...26-29): paths_ok=4/4,
  pooled ESS geomean 333 (ESS/draw 0.083, min 0.057), rhat 1.013, worst
  beta.1/beta.2/sigma. vs D's ESS/draw ~0.0013, rhat 1.62: a ~60x ESS
  rescue, but MARGINAL vs gate (a) thresholds (0.1 / 1.01) at this seed
  set — campaign decides.
- (campaign) ran 19:42:38-19:45 (3 reps, model-major, A_pf/C_pf/D_pf
  adjacent per model; loads at rep starts 1.34/3.74/4.15, cc1plus=0 at
  EVERY rep start — no F-7 build overlap; the load ramp is our own
  <=4-proc arms, same character as F-8's 2.23/4.40/4.44). Runner
  bench/fortk_f9/run_f9.py (F-8 conventions, F-8 cols/region cache/exes
  reused); analyze_f9.py; raw under bench/fortk_f9/<model>/rep<r>/
  {A_pf,C_fused_nuts_pf,D_fused_walnuts_pf}/. Mini validation (blr
  200+200 x 3 reps incl. ess.R) passed before the real run; validation
  outputs wiped.

## FINAL TABLE (extended F-8; medians of 3 reps; wall = max-chain sampler
wall PLUS pathfinder per protocol — C_pf/D_pf: PF_WALL+SAMPLE_WALL
exec1_s; A_pf: CmdStan Elapsed(Total)+pf_secs; ESS via harness/ess.R
pooled 4 chains; div/1k summed over 4 chains; walnuts stats n/a by design)

| model | arm | wall_s | ESS_bulk/s | ESS/draw | div/1k | td/4k | rhat_max |
|---|---|---|---|---|---|---|---|
| esnc | A cmdstan nuts | 0.0320 | 141,603 | 1.090 | 0 | 0 | 1.002 |
| esnc | C fused nuts | 0.0122 | 329,847 | 0.999 | 0 | 0 | 1.003 |
| esnc | D fused walnuts | 0.0047 | 696,974 | 0.812 | n/a | n/a | 1.003 |
| esnc | A_pf | 0.0386 | 107,766 | 1.007 | 0.5 | 0 | 1.003 |
| esnc | C_pf | 0.0154 | 249,232 | 1.007 | 0.25 | 0 | 1.002 |
| esnc | D_pf | 0.0084 | 335,922 | 0.762 | n/a | n/a | 1.003 |
| esc | A | 0.0480 | 3,709 | 0.044 | 43 | 0 | 1.079 |
| esc | C | 0.0314 | 19,213 | 0.171 | 14 | 0 | 1.029 |
| esc | D | 0.0118 | 24,269 | 0.075 | n/a | n/a | 1.084 |
| esc | A_pf | 0.1762 | 3,984 | 0.167 | 20.5 | 0 | 1.028 |
| esc | C_pf | 0.0419 | 14,091 | 0.176 | 22 | 0 | 1.022 |
| esc | D_pf | 0.0171 | 20,923 | 0.089 | n/a | n/a | 1.074 |
| blr | A | 0.0620 | 21,983 | 0.341 | 0 | 0 | 1.006 |
| blr | C | 0.0242 | 60,787 | 0.349 | 0 | 0 | 1.004 |
| blr | D | 0.0353 | 176 | 0.003 | n/a | n/a | 4.32 NON-CONV |
| blr | A_pf | 0.0796 | 17,621 | 0.351 | 0 | 0 | 1.003 |
| blr | C_pf | 0.0382 | 42,906 | 0.384 | 0 | 0 | 1.004 |
| blr | D_pf | 0.0157 | 39,280 | 0.149 | n/a | n/a | 1.006 |
| pilots | A | 1.2520 | 32 | 0.010 | 180 | 653 | 1.315 |
| pilots | C | 0.6142 | 96 | 0.018 | 139 | 310 | 1.069 |
| pilots | D | 0.0245 | 565 | 0.003 | n/a | n/a | 1.81 NON-CONV |
| pilots | A_pf | 1.2525 | 100 | 0.029 | 126 | 523 | 1.049 |
| pilots | C_pf | 0.7674 | 148 | 0.025 | 148 | 297 | 1.063 |
| pilots | D_pf | 0.0572 | 178 | 0.003 | n/a | n/a | 2.59 NON-CONV |
| kidscore | A | 0.3710 | 3,490 | 0.324 | 0 | 0 | 1.003 |
| kidscore | C | 0.1076 | 13,177 | 0.348 | 0 | 0 | 1.003 |
| kidscore | D | 0.1162 | 46 | 0.002 | n/a | n/a | 1.62 NON-CONV |
| kidscore | A_pf | 0.4280 | 2,982 | 0.337 | 0 | 0 | 1.002 |
| kidscore | C_pf | 0.1321 | 10,215 | 0.319 | 0 | 0 | 1.005 |
| kidscore | D_pf | 0.0304 | 12,185 | 0.093 | n/a | n/a | 1.014 |
| logmesq | A | 0.2130 | 9,133 | 0.454 | 0 | 0 | 1.002 |
| logmesq | C | 0.0824 | 23,634 | 0.484 | 0 | 0 | 1.002 |
| logmesq | D | 0.0167 | 24,879 | 0.104 | n/a | n/a | 1.017 |
| logmesq | A_pf | 0.2280 | 8,045 | 0.466 | 0 | 0 | 1.002 |
| logmesq | C_pf | 0.0892 | 21,644 | 0.448 | 0 | 0 | 1.004 |
| logmesq | D_pf | 0.0219 | 19,628 | 0.106 | n/a | n/a | 1.026 |

Geomeans (6 models): A 4,772 | C 15,022 | D 3,524 || A_pf 5,130 (1.07x A)
| C_pf 13,047 (0.87x C) | D_pf 15,079. D_pf vs C_pf = 1.16x; D_pf vs C
= 1.00x; C_pf vs C = 0.87x.

Wall decomposition (median sampler-only vs pf): C_pf sampler walls are
parity-to-slower vs C (esnc 12.3 vs 12.2ms; blr 34.7 vs 24.2ms; esc 26.5
vs 31.4; kidscore 126 vs 108; pilots 726 vs 614; logmesq 85 vs 82) and pf
adds 3.2-40ms — C_pf's ESS/s loss vs C is pf-time-counted + longer NUTS
warmup from a typical-set start. D_pf sampler walls are parity vs D where
D worked (esnc 4.9/4.7ms, logmesq 16.8/16.7ms) and dramatically cheaper
where D thrashed (blr 12.2 vs 35.3ms; kidscore 24.0 vs 116.2ms).

## GATES

(a) FAIL (split): blr D_pf PASS — rhat reps 1.011/1.004/1.006 (med
1.006 < 1.01), ESS/draw 0.149/0.157/0.138 (med 0.149 >= 0.1), min-ESS/
draw med 0.145; posterior matches A_pf (sigma 1.0339±0.0743 vs
1.0350±0.0734). kidscore D_pf FAIL — rhat reps 1.013/1.018/1.014 (med
1.014 >= 1.01), ESS/draw 0.083/0.100/0.093 (med 0.093 < 0.1), min 0.064.
→ per pre-registration: the kidscore residual is ADAPTATION-NOT-INIT,
walnutpie-lane evidence. Where the chains go: all 4 kidscore D_pf chains
are in the CORRECT basin (per-chain means rep0: beta.1 25.2-26.2,
beta.2 0.606-0.616, sigma 18.25-18.35 vs A_pf 25.8-25.9/0.609-0.610/
18.27-18.30) — no more parking; they autocorrelate (slow within-basin
mixing, worst params beta.1/beta.2/sigma). blr's chains went from parked
sigma 4.8/2.2/1.7/0.7 to one basin sigma~1.03. pilots D_pf remains
NON-CONV (rhat 2.59, worse than D's 1.81): its four chains sit in
DIFFERENT basins of pilots' known multimodality (a-bar per chain ~0.4/
1.6/-0.1/1.1) — init cannot fix between-basin mixing walnuts never had.

(b) FAIL (partial, honest): D_pf on esnc = 335,922 ESS/s vs D reps
480,912-807,283 (0.70x D's WORST rep; 0.48x D median) — beyond D's own
noise, driven ~half by protocol-counted pf time (3.6ms on an 8.4ms wall)
and ~half by slightly lower ESS/draw (0.762 vs 0.812); esc 0.97x D-min
(20,923 vs 21,506, inside noise); logmesq 1.09x D-min (within noise,
D's own spread 18,007-33,311). C_pf no-worse-than-C FAILS on 4/6 models
(C_pf/C medians: esnc 0.76x, esc 0.73x, blr 0.71x, kidscore 0.78x;
pilots 1.55x, logmesq 0.92x) — ESS/draw parity-or-better everywhere, so
the loss is wall (pf counted per protocol + slower NUTS warmup), not
statistics.

(c) headline: D_pf vs C_pf geomean ESS/s = 1.16x; D_pf vs C = 1.00x.
pf-init walnuts lifts D from 0.74x CmdStan (3,524 vs A 4,772) to 3.16x
(D_pf 15,079 vs A), 2.94x A_pf — it becomes CmdStan-competitive and
C-parity as a default, but NOT the new best arm, and its kidscore/pilots
residuals keep it from being a safe default.

## READ

The F-9 hypothesis is HALF-RIGHT, decisively on the model where it was
cleanest: blr's stuck chains were an INIT problem (rhat 4.32→1.006,
ESS/draw 0.003→0.149, correct posterior) and pf-init also rescued
kidscore from wrong-basin parking into the right basin (ESS/draw
0.002→0.093, ~40x) — but not over the pre-registered bar: kidscore's
chains now mix too SLOWLY within the correct basin, which is warmup/
adaptation (walnutpie's Adam step), not initialization. The honest gate
line: (a) FAIL. pf-init is necessary-but-not-sufficient for walnuts on
this class; the remaining lever is in walnuts' own warmup. For the fortk
question (best default arm): C stays the recommendation — D_pf only ties
C (1.00x) at the aggregate and still carries two non-converged models;
C_pf is strictly worse than C end-to-end (pf cost + slower warmup), so
pf-init buys NUTS nothing here; A_pf shows pf-init alone helps CmdStan
modestly (1.07x geomean; pilots rhat 1.315→1.049, esc divs 43→20.5).

## Deviations / notes

- pathfinder paths sometimes fail at start (blr 2/4 ok: L-BFGS "line
  search failed... failed to start") — CmdStan's own pathfinder fails
  the SAME paths on the same seed; the algorithm proceeds with the
  survivors exactly as multi.hpp does. paths_ok recorded per run in
  results_raw.json.
- esc A_pf ESS/s spread 3,984/4,245/2,057 (>2x) — traced to CmdStan's
  own esc divergence noise (div/rep 82/63/250), the same adaptation-
  internals effect F-8 reported for arm A; NOT load (cc1plus=0, loads
  low at rep starts). No re-run.
- B arm not re-run (registration: existing rows are the reference).
- pf draws bit-identical across the 4 chain processes of each (model,
  rep) (verified in smoke; same mechanism in campaign: shared pf-seed,
  fully-seeded single paths).
- Commits (pinned worktree /tmp/stanli-b7a3fd5, detached, never merge):
  833d8de (tool --init pf + stanli::run_pathfinder_multi) on d4801b5.
  Harness/analysis live uncommitted in the main workspace under
  bench/fortk_f9/ (same arrangement as F-8).
- Old binary preserved: build-f8/fortk_t1r.f8bak (F-8 binary snapshot).
