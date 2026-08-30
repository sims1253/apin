# WORKLOG — nindan (Stan wall-clock → ESS)

Project: measure where Stan wall-clock goes, cut waste, raise ESS-per-gradient.
Pitch: PITCH.md. Benchmark set: CORE_SET.md (frozen after Phase 0 model selection).

## Environment (recorded once, do not re-derive)

- CPU: AMD Ryzen 9 5900X (12C/24T, Zen 3). **AVX2/256-bit only — 4 FP64 lanes, NO AVX-512.
  Any SIMD work means AVX2+FMA, alignment, unrolling, allocation removal. No zmm paths.**
- RAM: 47 GiB total. Other jobs run on this box (load ~4-6 at session start).
- **Resource policy for this lane: ≤4 single-threaded processes at any time; compile with
  `make -j4`; every sampler chain = 1 thread (STAN_NUM_THREADS=1, OMP_NUM_THREADS=1).**
- OS: Ubuntu 22.04 (WSL2), g++ 11.4, clang 14.0. No `perf` on PATH (use Stan `profile()`
  blocks + valgrind/callgrind for Phase 1 system-level work).
- R 4.6.1 (cmdstanr, posterior, bayesplot, data.table, callr present); Python via uv.
- CmdStan available: 2.37.0, 2.39.0 (~/.cmdstan). LANE PIN: **CmdStan 2.39.0**.
- valgrind 3.x present (callgrind OK for profiling, slow).

## Log format

Newest entries at bottom. Every entry: date, phase, what was done, numbers, decisions.

## 2026-08-19 ~01:40 — Phase 0: environment + harness + CORE_SET frozen

- Toolchain validated: CmdStan **2.39.0** pinned (cmdstan bd4aeedb, stan submodule
  44be14e2), stanc3 v2.39.0. R 4.6.1 + posterior 1.7.0 (rank-normalized ESS via
  `summarise_draws` — NB: posterior 1.7's `ess_bulk(draws)` on a whole draws object
  returns ONE wrong number; must index per-variable. Cost me 30 min; harness now correct.)
- posteriordb: DB clone @ 28f8d3d6 (master) into external/posteriordb; R package from
  stan-dev.r-universe (GitHub PAT in credential store is stale — 404 via install_github).
- **CORE_SET.md frozen: 21 models** (4 easy/small, 3 GLM, 5 hierarchical, 4 GP/spatial,
  5 stiff/funnel-ish). radon disambiguation: partially_pooled→radon_all (N=12573),
  variable_intercept_slope→radon_mn (N=919). diamonds N=5000.
- Harness: harness/run_grid.py (cmdstan, checkpointed, 4 parallel 1-thread chains,
  MAKEFLAGS=-j4 compiles), harness/run_nutpie.py (nutpie 0.16 via bridgestan; API note:
  `compile_stan_model(filename=).with_data(**data)`, returns DataTree), harness/ess.R,
  harness/compute_ess.py, harness/aggregate.py.
- Smoke test: eight_schools_noncentered default — 4 chains ≈ 42 ms wall total (toy model),
  ess_bulk_min=2446, rhat_max=1.004, matches posteriordb gold (mu 4.4±3.3). ✓
- **Finding: stanc3 2.39 `--Oexperimental` emits uncompilable C++** on
  eight_schools_noncentered: `stan::model::assign(x, fma(a,b,c), "desc")` — 3-arg
  overload doesn't exist (candidate wants 4 args). stanc itself accepts all 21 models;
  breakage is C++-level. Compiling oexp variants now to map the blast radius.
  (cmdstanpy note: its `stanc_options` API wants a dict, not list; bypassed with
  direct stanc+make in harness/compile_variant.py.)

## 2026-08-19 ~02:20 — Phase 0: grid launched + profiling copies ready

- Full cmdstan grid (default × 21, oexp × 18, 3 reps) running in background
  (`harness/make_all.sh` = one-command rerun of everything incl. nutpie + ESS + aggregation).
- `harness/compile_variant.py`: direct stanc+make compile (cmdstanpy built MISLABELED
  default binaries when given list stanc_options and then raised — purged and rebuilt).
- **--Oexperimental blast radius (stanc3 2.39): 3/21 CORE models emit uncompilable C++**
  (eight_schools_noncentered, accel_gp, bym2_offset_only; `assign(x, fma(...), "desc")`
  3-arg overload missing). oexp baseline covers the other 18.
- Early wall numbers (default, rep0): diamonds 64.8s, hier_2pl 74.9s, radon_all 30.7s
  (warmup 21.8s vs sampling 6.3s — warmup 3.5x sampling!), kronecker_gp ~13-15min
  (~7000-dim latent field — the heavyweight). Toy models (blr, gp_regr) < 0.5s.
  pilots: 455/4000 divergences (11.4%) — pathology representative confirmed.
- Phase 1 prep: 6 profiled model copies in models_prof/ (diamonds, radon_pp,
  accel_gp, pilots, lsat, kronecker_gp) with profile("tdata"/"tp"/"model") blocks;
  generated programmatically (decl-preserving wrap — constrained types can't move into
  profile{} scope). All 6 stanc-compile OK. Runs pending grid completion (4-core cap).

## 2026-08-19 ~04:00 — Phase 0 grid complete: cmdstan default (21) + oexp (17) x 3 reps

- **--Oexperimental final tally (stanc3 2.39, 21 CORE models): 4 broken.**
  3 emit uncompilable C++ (eight_schools_noncentered, accel_gp, bym2_offset_only —
  `assign(x, fma(...), "desc")` missing 3-arg overload) + **wells_dist100_model
  MISCOMPILES**: runs, then Eigen `DenseBase::resize()` assertion abort. CmdStan
  builds with -DBOOST_DISABLE_ASSERTS but Eigen assertions fire here; with NDEBUG
  this would be silent corruption. Verdict: oexp unsafe as a default; measured only
  on the 17 working models.
- Peak single-model wall (default, median): kronecker_gp ~15 min, hier_2pl ~70s,
  diamonds ~65s, radon_all ~30s (warmup 21.8s = 3.5x its 6.3s sampling!),
  pilots ~1.5s but 11-17% divergences (rep2: 697/4000).
- oexp speedup where it works: hier_2pl 74.9->54.0s (~28% faster wall), same
  leapfrog counts => per-gradient cost drop. Full table pending ESS aggregation.

## 2026-08-19 ~05:30 — Phase 0 COMPLETE: 3 baselines x CORE_SET x 3 reps + nutpie 2x claim localized

Results (results/table_per_model.csv, summary_variants.csv; median of 3 reps):

| variant   | geo wall | geo ESS/s | geo ESS/grad | geomean wall speedup vs default |
|-----------|----------|-----------|--------------|---------------------------------|
| default   | 1.00x    | 1.00x     | 1.00x        | — |
| oexp      | 0.94x    | 0.97x     | 0.98x        | 1.035x (17 models; 4 broken) |
| nutpie    | 0.83x    | 1.02x     | 0.38x        | 1.206x (21 models) |

**nutpie "2x" decomposed (the headline):**
- Wall speedup geomean 1.21x (max 4.8x pilots — but pilots rhat 1.38 under nutpie vs 1.10 cmdstan);
  big models: diamonds 3.18x, hier_2pl 2.18x, kronecker 1.56x.
- Quality-adjusted (ESS_bulk/min per sec, geomean): **0.98x — a wash.** nutpie yields 0.82x ESS overall
  (fewer gradient evals per draw: lf ratio 1.6–4x fewer... i.e. nutpie runs MORE lf on most models but
  produces fewer effective draws — its tree/stepsize adaptation trades gradients for ESS differently).
- **The real, portable win is per-gradient wall: nutpie/bridgestan is 2.6x cheaper per gradient
  (geomean; 3.3x among models with >10µs/grad), same Stan 2.39.0 math** (bridgestan 2.9.0 vendors
  stan 2.39.0 — verified version.hpp). hier_2pl: 585->134 µs/grad, radon_all: 480->92, lsat: 140->35,
  diamonds: 16.4->5.2. THIS is Stan's implementation overhead, now quantified and localized to the
  per-gradient path (model logp+grad evaluation through cmdstan services vs bridgestan direct).
  Phase 1 must attribute those µs: checks / partials / arena / Eigen codegen / kernel bookkeeping.

**oexp verdict:** not shippable (3 uncompilable + 1 miscompile w/ silent-corruption risk), and no
quality-adjusted win (ESS/s 0.97x geomean). Kill as baseline going forward; keep table for evidence.

**Adaptation/quality flags for Phase 3:** warmup is 52.7% of sampler time (median, >1s models);
radon 77%! kronecker_gp: 99.5% iterations at maxdepth=10 (ess 944 of 4000 draws). pilots:
11–17% divergences, ESS 40, rhat 1.10 — pathological family confirmed. 8-schools centered:
cmdstan rhat 1.06 (funnel), nutpie handles it better (3.5x ESS) — worth a Phase 3 case study.

Bonus baselines queued: walnutpie (WALNUTS, arXiv 2506.18746, Flatiron; built stan_cli — reports
logp_grad fraction + per-call µs directly, perfect attribution instrument) + tinystan noted
(WardBrian/tinystan: minimal Stan-services runtime; submodule fetch needed, deferred).

## 2026-08-19 ~06:10 — walnutpie (WALNUTS) baseline complete + parser fix + pathfinder pre-registration

- Fixed walnutpie rows parser (5-line stanza regex; old version misaligned → phantom negative
  times). Rebuilt all walnut rows from chain logs (harness/rebuild_walnut_rows.py);
  wall := max over chains (warm+sample).
- **WALNUTS @ defaults (walnutpie 0.0.1, warmup 1000): wall geomean speedup 1.73x over
  cmdstan default BUT ESS_bulk geomean ratio 0.062x, 17/21 models rhat>1.01 (up to 9.45).
  Quality-adjusted ESS/sec = 0.107x.** Spectacular on diamonds wall (18x, 216k vs 4M grads)
  but chains are badly mixed at these settings. NOT a baseline contender; kept as evidence.
  Attribution value: stan_cli's instrumented logp_grad shows fraction ~0.91–0.99 of its
  wall is model logp+grad — i.e. with service overhead stripped, gradient math dominates.
- (Also: aggregate.py had a dtype bug — None+float mix made rhat_max an object column that
  median(numeric_only) silently dropped. Fixed with explicit to_numeric.)

### PRE-REGISTERED (Phase 3-lite): Pathfinder/LBFGS-seeded warmup ablations

Motivation: warmup is 52.7% of sampler time (median, >1s models; radon 77%).
Hypotheses:
  H1: Pathfinder inits (multi-path PSIS draws) at UNCHANGED warmup (1000) improve early
      adaptation → equal-or-better ESS and fewer divergences at same wall (+ pathfinder cost).
  H2: Pathfinder inits allow SHORTER warmup (200 iters) at equal posterior quality
      (rhat<1.01, ESS within 20% of default) → large wall-to-reliable-posterior win on
      warmup-dominated models (radon, bym2, hier_2pl, diamonds, kronecker).
  H0 (failure mode): init advantage washes out after Stan's windowed adaptation — record
      honestly if so.
Protocol (frozen before running):
  - Variants: pf_full (pathfinder inits + 1000 warmup), pf_w200 (pathfinder inits + 200
    warmup). Baseline = existing default variant (random inits, 1000 warmup).
  - Pathfinder: cmdstan method=pathfinder, num_paths=4 (default), single run per model,
    time counted into wall. Chain c init = random PSIS draw (rng seeded by rep+chain).
  - Models (10, warmup-heavy + pathological): radon_partially_pooled_noncentered,
    bym2_offset_only, hier_2pl, diamonds, lsat_model, accel_gp, kronecker_gp, pilots,
    eight_schools_centered, lotka_volterra. 3 reps, seeds as in CORE_SET.
  - Judged on: ESS_bulk/min per wall-second (incl. pathfinder), rhat, divergence rate,
    adaptation failures (any chain stuck / rhat>1.05).

## 2026-08-19 ~14:00 — Progress dashboard (postplan)

- `harness/make_dashboard.py` regenerates a self-contained HTML status page from
  results/, runs/, logs/, WORKLOG and re-uploads to postplan (stable draft id in
  results/.postplan_draft.json): **https://gbcfyftfncsi.postplan.dev**
  Auto-refreshed by make_all.sh; manual: `python3 harness/make_dashboard.py`.
- postplan API note: POST /api/uploads with Bearer POSTPLAN_API_KEY, JSON
  {html, filename, draftId, description}; 512KB cap; inline <script> allowed,
  external script src blocked; forms/iframes blocked.

## 2026-08-19 ~15:30 — Pathfinder ablation results (pre-registered protocol, judged)

Wall includes the pathfinder run per rep (honest pipeline accounting; pf is cached
across reps but each rep = an independent full pipeline run).

**H1 (pf inits + full 1000 warmup): REJECTED.** Warmup with pf inits is SLOWER
(hier_2pl 0.45x, bym2 0.59x, radon 0.58x wall) and ESS/sec <= 1.19x everywhere.
Starting in the typical set makes early warmup MORE expensive (longer healthy
trajectories), and Stan's windowed adaptation does not exploit it.

**H2 (pf inits + 200 warmup): targeted wins, not a default.**
- lotka_volterra 1.37x ESS/sec, quality held (rhat 1.006, ESS 1.06x).
- eight_schools_centered (funnel): ESS 3.1x (55->170), rhat 1.059->1.017 —
  the known "pathfinder tames funnels via better inits" effect, reproduced.
- accel_gp 1.04x (ESS 0.87x — borderline quality).
- radon: ESS 1.46x and rhat 1.020->1.008 at 0.64x wall (ESS/sec 0.94 per strict
  accounting; pathfinder itself costs ~28s there).
- FAILURES (recorded): pilots degrades badly (rhat 1.10->1.38, ESS 40->9;
  pf inits collapse chain diversity on this pathology). kronecker_gp w200:
  1.64x wall but ESS 0.25x — 200 warmup cannot adapt a 7000-dim mass matrix.
  hier_2pl/bym2/diamonds: pf-dominated cost, no quality win.

Verdict: pathfinder inits are a per-family tool (funnels, slow-mixing inits,
warmup-dominated hier models), NOT a default. An upstream-worthy idea would be
"adaptive warmup budget by early-window diagnostics" rather than fixed 200.

**Tooling decisions (user input):** Stan-source patches explicitly in scope (Phase 2
target confirmed by the 2.6x same-math per-grad gap). callgrind upgraded with
--simulate-cache=yes (I1/D1/LL miss attribution, deterministic, immune to the other
jobs' contention — perf unavailable on WSL2 kernel). memcheck reserved as the Phase 2
patch-correctness harness (would catch oexp-class silent miscompiles). Cache
hypotheses to test, not assume: adjoint-sweep pointer chasing, ps_point copies vs L2
(168KB/copy at 7k dims), Eigen temp churn, 100KB-1MB likelihood arrays.


## 2026-08-19 ~16:30 — Phase 1 measured: atlas complete, instruction gap localized

- profile() shares: diamonds 95.6%, radon 97.6%, lsat 87.7% model block;
  kronecker 80.5% (71% of profiled in transformed-parameters!); accel_gp 29.5%,
  pilots 50% → small/stiff models are kernel/adaptation-bound.
- callgrind (--simulate-cache=yes): steady-state buckets + cache events.
  Checks ≤2.2% (folklore REJECTED). LL misses ≈0 (no DRAM wall; L1/L2 latency
  only: D1 mr 0.6–11%). memcpy/alloc 21% on pilots (kernel copies), 12% accel.
- Microbenches: element-wise var tax 4.3x over double (4.9 vs 1.13 ns/elem);
  streaming floor 42x below checked-AD path; GLM var 1.9x; chained var-op 8.2ns
  (112x double); ps_point copy 30.5µs @7k dims; pointer chase 85x stream (L3).
- **cmdstan-vs-bridgestan instruction gap: 2.10–5.04x per gradient** (table in
  ATLAS §4). Parity: grads identical to 8 decimals, same jacobian behavior.
  → Phase 2 target = per-gradient service path in stan/cmdstan source.
- bench hygiene notes recorded: -D_REENTRANT + tbb link order (lib AFTER objs);
  microbench sinks must be live ((void)s lets GCC delete the work).

## 2026-08-19 ~17:00 — Phase 2c build flags: gcc 11.4 CORRUPTS, clang path open

- **-march=native/-march=znver3/-march=x86-64-v3 with g++ 11.4.0 miscompiles
  cmdstan 2.39 services**: arma11 aborts with invalid free (double free/corruption)
  in hmc_nuts_diag_e_adapt, 3/3 reproducible; valgrind confirms invalid free();
  plain -O3 (cmdstan default) is clean. march_native grid runs QUARANTINED
  (runs/QUARANTINED_march_native_gcc11_corruption; 20/21 models "ran" but the
  binary class corrupts memory — numbers unusable).
- **clang-14 -march=native -O3 (NO_PCH=1): clean** — arma11 runs rc=0 and
  valgrind memcheck reports 0 errors. clang_native variant added to
  harness/compile_variant.py; full CORE_SET clang_native grid running
  (compiles ~2-3x slower without PCH).
- aggregate.py hardened for pathfinder rows (missing columns).
- gcc bug class matches the oexp miscompile pattern: this toolchain's
  aggressive codegen paths are untrustworthy without memcheck. Lesson: every
  Phase 2 binary variant gets a memcheck smoke test before its grid is trusted.

## 2026-08-19 ~17:20 — march=native forensics: GCC×Stan bug, not stale GCC

- User suggested newer g++; extracted g++-12.3 (apt download + dpkg -x into
  ~/opt/gcc12, no root needed). **g++-12.3 -march=native: SAME crash** (3/3,
  invalid free). Jammy has no g++-13. GCC line exhausted.
- Valgrind detail: free() on a pointer 16 bytes INSIDE a 64-byte malloc block;
  alloc site = Eigen VectorXd (CwiseNullaryOp ctor) in base_nuts::transition.
  I.e. a VectorXd's data pointer moved +16 bytes then freed — classic adjacent-
  object corruption consistent with GCC vectorizer misbehavior around Eigen
  stack/heap objects. Only manifests with AVX2 codegen (x86-64-v3, znver3,
  native all crash; -O3 alone clean).
- clang-14 (-O1/-O2/-O3, -march=native, ASan at O1/O2/O3 + valgrind): CLEAN.
  → Phase 2c proceeds on clang_native (grid already running). Upstream bug
  report candidate; needs minimal repro first (deferred; quarantine evidence in
  runs/QUARANTINED_march_native_gcc11_corruption).

## 2026-08-19 ~17:45 — ROOT CAUSE of march-native crashes: mixed-build corruption

- Valgrind on clang-native hier_2pl: same invalid-free class (interior pointer),
  in hmc_nuts_diag_e_adapt — so NOT gcc-specific; both compilers corrupt when
  model TU is vectorized.
- **Mechanism identified**: cmdstan links the DISTRIBUTION-PREBUILT src/cmdstan/main.o
  (and force-includes the prebuilt PCH) compiled WITHOUT -march, against the user's
  -march=native model TU. Eigen objects/packets cross that TU boundary with
  inconsistent alignment/codegen assumptions → heap corruption (VectorXd data
  pointer shifted +16/+32B → invalid free).
- Proof: force-rebuilt main.o with clang -march=native -O3 (PRECOMPILED_HEADERS=false),
  relinked hier_2pl → 3/3 clean runs (was 3/3 aborts).
- Consequences: (1) ALL earlier clang_native links before the main.o rebuild are
  untrustworthy → purge + relink + rerun; (2) this explains scattered "Stan crashes
  with -march=native" reports and is an upstream cmdstan issue (make should rebuild
  main.o/PCH when CXXFLAGS change, or warn); (3) gcc-12 test earlier was ALSO a
  mixed build, so "gcc 12 still crashes" was expected — gcc verdict needs redo with
  consistent rebuild before blaming the compiler.
- NOTE: shared cmdstan tree's main.o is currently clang-native; restore to default
  gcc build after clang lane completes (toolchain hygiene for Phase 2 patch builds).

## 2026-08-19 ~19:00 — PIVOT: walnutpie becomes primary target; optimizer-swap infra built

- Per user (Bob's StanCon talk): walnutpie/WALNUTS is on track to become "the"
  sampler → focus on making IT faster. Phase 2 Stan-source work continues as
  secondary (cmdstan per-grad gap evidence stands).
- Research child spawned (optimizer-scout, zai/glm-5.3): SOTA muon variants,
  Adam alternatives for noisy 1-D + online mass-matrix estimation lit review →
  external/research_optimizer_sota.md.
- **walnutpie optimizer-swap patch (branch nindan-stepopt, patches/walnutpie-stepopt.patch,
  595 lines)**: AdaptiveWalnuts templated on StepSizeAdapter (default Adam — zero behavior
  change); StepAdapterFactory traits; new adapters = DualAveraging (Stan-style, γ/t0/κ
  knobs), AdEMAMix (dual-EMA, scalar), AdaBelief, BatchedAdapter<N> (mean-batching for
  per-micro-step observation streams); stan_cli --step-optimizer/--step-opt-batch-stride/
  --da-* flags. Builds clean; smoke test eight_schools: adam 4.80 / da 4.24 / dem 4.22 /
  belief 4.41 / da+stride50 4.49 (ref 4.4±3.3). 
- Key design insight from source read: walnutpie feeds the step optimizer one
  observation PER MICRO-STEP (hundreds/iteration) — Adam was implicitly calibrated
  for that frequency; classic dual averaging expects ~1/iteration → the
  BatchedAdapter exists to test frequency as a separate axis from algorithm.

### PRE-REGISTERED (Phase W-1): walnutpie step-optimizer ablation

Protocol: same CORE_SET, 4 chains (separate CLI invocations, per-chain seeds),
1000 warmup + 1000 draws, 3 reps, seeds 20260819+1000r (+chain). Variants:
walnut_adam (baseline = existing runs), walnut_da, walnut_dem, walnut_belief,
walnut_da_b50 (dual averaging + batch stride 50). Judged on: ess_bulk_min
geomean + per-model, rhat>1.01 count (walnut-adam currently fails 17/21 —
PRIMARY success metric is fixing mixing at equal-or-less wall), wall, ESS/sec.
Runs sequentially after clang_native grid (4-core discipline).

## 2026-08-19 ~20:30 — Research in; clip/PR-average implemented; W-1 grid launched

- optimizer-scout report landed (external/research_optimizer_sota.md, 570 lines): Muon
  structurally inapplicable (scalar/1-D → every major stack routes to AdamW); top actions
  = grad clip + default batching, Polyak–Ruppert averaged log-ε, two-phase decay,
  mass shrink+floor (Stan n/(n+5) rule), rank-m sparse metric (future).
- Implemented: ClippedAdapter (clip α to [1−c,1]), DualAveraging use_average (PR x_bar
  as step_size output), CLI --step-grad-clip/--da-freeze-average; dispatch composes
  Clip<Batch<Opt>>. Builds clean; smoke tests pass.
- **First pathology confirmed live: plain dual averaging (no averaged iterate) drives
  stepsize → 0 and aborts at freeze on pilots** ("macro_time must be in (0, inf)") —
  the exact stepsize-collapse the research predicted; DA-with-average and clip variants
  run fine. PR-averaging is not optional for DA in walnutpie's per-micro-step regime.
- walnutpie branch updated + patches/walnutpie-stepopt.patch regenerated.
- W-1 variants launched (pre-registered above): da, da_avg, da_b50, dem, belief,
  adam_b50, adam_b50_c3 (adam baseline = existing walnut runs).
- Also: clang_native grid complete → **Phase 2c verdict: no geomean win** (wall ratio
  1.13 = slower, ESS 1.04 ~par; only diamonds gains 0.73x from AVX2 GEMV). Build-flag
  lane closed honestly.

## 2026-08-19 ~22:30 — W-1 results: batching is the fix for half the pathologies

| variant | models ran | rhat>1.01 | geo ESS/s vs walnut | notes |
|---|---|---|---|---|
| walnut (adam) | 21 | **17** | 1.00 | baseline |
| walnut_adam_b50 | 21 | **9** | 0.42 | batching halves failures |
| walnut_adam_b50_c3 | 21 | 10 | 0.44 | clip adds ~nothing |
| walnut_belief | 21 | 15 | 1.89 | faster, still bad |
| walnut_dem | 19 | 15 | 0.19 | worst |
| walnut_da | 11 | 8 | 0.71 | 10 models ABORT (stepsize->0) |
| walnut_da_avg | 14 | 10 | 0.72 | 7 aborts (PR helps marginally) |
| walnut_da_b50 | 21 | 16 | 1.48 | batching eliminates aborts; mixing still bad |

Conclusions: (1) per-micro-step Adam was over-updated — batch 50 is the single
biggest adaptation fix so far; (2) gradient clip redundant once batched; (3) plain
DA unusable without batching (collapse); (4) optimizer choice is SECONDARY to the
mass-matrix estimator quality (discounted geometric-mean estimator, no shrinkage,
no windows). Single-chain probe: --mass-shrink-kappa 5 --mass-var-floor 1e-3 took
arma11 4-chain rhat 9.48 -> ~1.02 (needs full 4-chain confirmation; 3 seeds abort
at freeze without clip — combined stack required).

### PRE-REGISTERED W-2: combined adaptation stack
Variants (adam_b50 base + mass fixes):
  w2_adam_b50_shr: adam, stride 50, mass-shrink-kappa 5, mass-var-floor 1e-3
  w2_adam_b50_shr_c3: + grad clip 0.3 (abort insurance)
  w2_da_b50_shr_avg: da, stride 50, shrink, PR-average
Judged on: rhat>1.01 count (target: <=4 = cmdstan parity), geo ESS_bulk_min,
wall, vs walnut + cmdstan default.

## 2026-08-19 ~23:45 — W-2 + lock-in diagnosis: the sampler, not the optimizer

W-2 (adam_b50 + mass shrink κ=5 + floor 1e-3; ±clip; da variant):
shrinkage does NOT move rhat-bad beyond batching alone (9 → 9). Mass estimator
quality is not the remaining bottleneck.

**Root failure mode isolated — "scale lock-in":** failing chains freeze at
DIFFERENT posterior scales (blr example: per-chain sigma means 1.01 / 2.60 /
7.02 / 0.43, within-chain sd ~0.003-0.13). ess_bulk=4, rhat 3-4.5. 3x warmup
(W=3000) does not unstuck (arma11, blr: ess=4 both) → NOT insufficient
adaptation; the frozen (step, mass, micro-steps) triple cannot traverse scale
modes and within-orbit adaptivity does not recover between-mode movement.
Persistent offenders = hierarchical/multimodal/scale models: radon_vis (3.72),
pilots (3.31), hier_2pl (2.10), kronecker (1.58), lotka (1.57), lsat (1.56),
low_dim_gauss_mix (1.53) + borderline logmesquite/8schools_centered.
Failures are SEED-DEPENDENT (grid median hides some; my fixed-seed probes
reproduce blr/arma11 stuck that 2/3 grid reps report as ok).

**Walnutpie lane scoreboard (4 chains, 1000+1000, 3 reps, median):**
- adaptation reliability: rhat>1.01 models: adam 17/21 → batch-50 9/21 (best);
  clip, shrink, DA/PR/belief/dem: no further gain.
- gradient efficiency even when mixed: ESS/grad ~0.06x cmdstan default
  (e.g. walnut rhat-ok models still need 10-30x more grads per effective draw).
- Wall speedup 1.7x is real (logp_grad fraction 0.91-0.99) but quality-adjusted
  it never beats cmdstan on this CORE_SET.

Implications for "make walnutpie fast(er)": (1) the batching patch is a real,
cheap adaptation win (halves failures) — worth upstreaming with evidence;
(2) scale lock-in is the blocker for walnutpie-as-default and is a SAMPLER
property (needs e.g. mode-aware/jittered restarts, dense/rank-m metric, or
warmup-time multimodality checks — rank-m sparse preconditioner from the
research report is the natural next experiment); (3) per-gradient speed work
(Stan services 2-5x Ir gap) benefits walnutpie equally via bridgestan models.

### PRE-REGISTERED W-3: trajectory length × sample efficiency (ESS/grad)

Motivation: walnutpie logp_grad fraction is 0.91-0.99 (iteration speed is NOT
the bottleneck); ESS/grad is ~0.06x cmdstan. Default target = 15 macro steps
per iteration. Hypothesis: longer orbits raise mixing per restart (and may
break scale lock-in by letting trajectories reach across scale modes).
Variants (all on adam+batch50, the winning adaptation config):
  w3_mst31 / w3_mst63: --max-macro-steps-target 31 / 63
  w3_mdt7: --max-trajectory-doublings 7 (deeper tree search)
Metrics: ESS_bulk_min per logp_grad call (PRIMARY), rhat>1.01 count (lock-in
fix check), wall (cost accounting). 21 models x 4 chains x (1000+1000) x 3 reps.

## 2026-08-20 ~00:30 — W-4: upstream freeze bug diagnosed + init-robustness fix

**Root cause of the "scale lock-in" class (upstream walnutpie 0.0.1):**
For initializations far from the typical set (e.g. blr lp=-8.3e6 at default
uniform [-2,2]^d init):
1. InitConfigBuilder::masses() seeds mass diag from |grad(init)| ~ 1e6 →
   inv_mass ~ 1e-6 → all position updates throttled ~1e6x.
2. No stepsize initialization heuristic: macro step starts at 1.0; every span
   diverges (|Δlogp| ~ 1e6 >> max_error 0.5) → transitions return the INITIAL
   point unchanged (verified: identical draws, sd ~1e-14, [span] valid=0
   always, alphas ≡ 0 via exp(-1e6)=0).
3. The step optimizer grinds macro-step down ~ -0.7/iteration in log (Adam
   lr 0.05), so ~750 of 1000 warmup iterations are burned before the chain
   can move at all; mass estimator degenerates meanwhile (Var_draw≈0).
Warmup length is irrelevant (3x doesn't help) — the chain is pinned.

**Fix implemented (fork dev/init-robustness):**
- mass_init_clamp: clamp gradient-seeded masses to [1/c, c] (config + CLI).
- step_init_heuristic: Stan-style find-reasonable-epsilon probe
  (warmup_heuristics.hpp, doubling/halving on accept of one leapfrog).
Results (5 worst models, batch-50 config, 4 chains, 1000+500):
  lsat_model: rhat 1.57→1.016 ESS 7→409 FIXED; hier_2pl: 15.6→1.05 ESS 4→61;
  blr/arma11/diamonds improved but still stuck (rhat 2.2-4.5) — deeper issue
  (metric degeneracy during early drift; candidates: metric reset windows,
  score-variance robustification). Heuristic eps found: 0.002-0.25.
W-4 grid (batch50+clamp100+heuristic, 21 models x 3 reps) launched.

## 2026-08-20 ~02:30 — freeze-class endgame: estimator rescues all fail; Pathfinder inits fix it

Step-by-step on dev/init-robustness (PR #4 in sims1253/walnutpie), each as a
commit + PR comment:
1. metric drift guard (log-space blend w/ seeds): NEGATIVE (hurts lsat/hier_2pl).
2. mass combine power (p-mean/max vs geometric): NEGATIVE (diamonds rhat -> 18).
3. metric stall/collapse reset: NO EFFECT (trigger self-referential first version;
   raw-draw stall detector second version — one moving coordinate masks the rest).
4. 6x warmup: NO EFFECT (chain reaches typical set by iter 4000 but metric
   stays collapsed: Var_draw feeds on the throttled chain itself — self-locking).
5. **Pathfinder-style typical-set inits via new --init-file: WORKS.**
   blr ESS 4->207 (rhat 1.016), arma11 3->1381 (1.003), lsat 396->736,
   diamonds 2.84->1.90, hier_2pl mixed. Insight: WALNUTS' per-macro-step error
   cap makes far-init traversal dramatically slower than NUTS tree expansion —
   walnutpie-as-default needs typical-set inits (or a drift warmup mode).

Fork PR state: walnutpie #1-#5 (optimizer series + research notes + init
robustness), cmdstan #1 (mixed-build corruption guard, validated 3/3 on
pinned 2.39.0 before shipping). hermes (glm-5.3) pass-2 optimizer research
running; W-4 grid 20/21; W-5 (pf-inits x CORE_SET x 3 reps) queued next.

### PRE-REGISTERED W-5: Pathfinder inits x full CORE_SET (walnutpie)
Variants: w5_pf_init = batch50 + clamp100 + step-heuristic + per-chain pf inits
(3 reps x distinct pf draws). Judged: rhat>1.01 count (target <=4 = cmdstan
parity), geo ESS_bulk_min, wall (pf cost excluded — it's a one-time model-level
artifact here; honest pipeline accounting documented separately).

## 2026-08-20 ~03:30 — W-3 verdict + the coherent picture

W-3 (trajectory length): mst31/mst63/mdt7 leave rhat-bad at 9/21 with ESS
unchanged and wall +23-38%. NEGATIVE — longer orbits buy nothing on the stuck
class (they're init-distance-pinned, not trajectory-starved).

Sample-efficiency ledger for walnutpie so far: optimizer choice = batching
helps (17->9), algorithm itself marginal; mass estimation patches = 0/5 worked;
warmup budget = no; trajectory budget = no; **init distance = the lever**
(pf-inits fix the class). Adaptation is fine once chains start in/near the
typical set; everything else was downstream of init distance.

## 2026-08-20 ~05:00 — W-5/W-6, options (b)/(c), chopping, 2-D casting analysis

- W-5 (pf-inits, full grid): ESS geomean 25.8->295.8 (11x), rhat-bad 9->11 on
  rep-medians (pf draw quality per rep is the new failure source; 4/21 cmdstan
  parity not yet reached).
- Options (b) drift-phase and (c) max-error schedule implemented on
  dev/init-robustness (PR #4 follow-up 3): (b) mixed/negative alone (chain
  arrives with frozen step); (c) helps diamonds (2.84->1.48) + hier_2pl.
  Stacking (b)/(c) with anti-windup re-freezes chains (schedule-induced
  alpha=exp(-100) trips the saturation gate) — documented.
- **Chopping (--metric-window W, Fisher-HMC arXiv:2603.18845): clear win** on
  top of pf-inits: blr 201->401 ESS (rhat 1.007), kronecker 1.046, diamonds
  1.465. W-6 grid (pf+chop50) running; candidate recommended config.
- 2-D casting question (user): analysis in PR #4 — draw-score corr ~ -0.5
  (vs -1 ideal), stacked sv2/sv1=0.70 => large off-diagonal content; low-rank+
  diagonal metric is the principled endpoint (4x published), needs property
  tests first. Wiki/flower reviewed: Aurora/OKLS/CM are matrix-geometry-bound
  (structurally MORE inapplicable to scalar+diagonal than Muon); transferable
  = zero-staleness discipline (informs chopping), Newton-Schulz machinery (for
  the future low-rank metric), Wen et al. LR>optimizer reality check.

### PRE-REGISTERED W-7: warmup-budget sweep — early vs asymptotic behavior

Question (user): do the init-robustness changes only improve EARLY behavior,
with other configs winning at larger n (asymptotic convergence)?
Design: 21 models x 4 chains x 3 reps, draws fixed 1000, warmup in
{250, 500, 1000, 2000, 4000}. Configs:
  w7_stock    : stock (adam, unbatched, random init)   — the "just add iters" arm
  w7_batch    : + batch50 (adaptation fix only)
  w7_full     : + pf-init + clamp + heuristic + chop50  (candidate recommended)
Metrics: rhat>1.01 count and geo ESS_bulk_min PER warmup level; crossover
detection. Asymptotic-convergence caveat: R-hat<1.01 with 4 chains that are
stuck in different modes can STILL be misleading in principle (chains can
agree transiently) — but our stuck-mode signature is ess=chains, which does
not improve with n, so ESS is the primary safety metric here.

## 2026-08-20 ~07:30 — Low-rank Fisher metric: designed, property-tested, integrated (W-8 queued)

- Property-first discipline paid for itself: 2 real math bugs caught in tests
  (non-symmetric sandwich parametrization; sqrt(D) vs D first term, 45% err).
  Final: Woodbury-vs-dense 4e-17, roundtrip 1e-16, SPD, conditioning demo
  24.4 (raw) -> 55.4 (diag-only WORSE = Hird&Livingstone Result 5) -> 19.3 (rank).
- Integration via --metric-rank (marginal fold, hot loop untouched).
  Live: hier_2pl ESS 16->82 (rhat 1.05), kronecker 24->47 (1.06), lsat
  595->764; neutral where cross-structure weak. Lower bound of full operator.
- PR #4 follow-up 4 posted. W-8 (rank10 x CORE_SET x 3 reps) queued behind W-7
  (warmup-budget sweep, in flight).

## 2026-08-20 ~11:00 — W-7 verdict: init-robustness fixes are NOT cosmetic (budget sweep)

Warmup-budget sweep (21 models x 4 chains x 3 reps, draws=1000):
rhat>1.01 (rep-medians) / geo ESS_bulk_min:

  W     stock      batch50    full(pf+clamp+heur+chop50)
  250   11 / 39    9 / 21     13 / 140
  500   14 / 51    9 / 22     10 / 140
  1000  17 / 59    9 / 25     8 / 317
  2000  14 / 85   10 / 41     8 / 385
  4000  15 / 93   10 / 45     9 / 359

KEY FINDINGS (user question answered):
1. NO crossover: stock@4000 (15 bad, ESS 93) << full@1000 (8 bad, ESS 317).
   Stuck chains are absorbing states — extra iterations cannot traverse what
   a collapsed metric forbids. The fixes change the ASYMPTOTE, not just early
   behavior.
2. stock failure count is NON-MONOTONE in W (17->15->15) — noise on stuck
   processes, not convergence trend. "Just add iterations" is a dead end.
3. batch50 alone plateaus at 9-10 regardless of budget: adaptation-frequency
   fixes only the optimizer-caused subset, not init-distance lock-in.
4. full config saturates by W~1000-2000 (8/9 bad, ESS ~360): remaining
   failures are the residual class (pathfinder draw quality, deep funnels).
5. W=250 anomaly: full@250 has 13 bad vs 14 @500 — warmup too short to even
   finish chop windows; not a recommendation point.
Practical: recommended config at W=1000 dominates stock at W=4000 in both
reliability and ESS, i.e. ~4x budget-equivalence.

## 2026-08-20 ~13:00 — W-8 full grid: rank metric = per-geometry tool, not default

w8_lr10 vs w6 (same base, +rank10): wins on correlated geometries (bym2
2.39x, kronecker 1.19x, garch 1.16x, radon 1.14x), regressions on funnels
(8schools_centered 0.19x!, hier_2pl 0.43x, pilots). Aggregate 294->267 geoESS,
rhat-bad 8->9. VERDICT: off by default; per-geometry opt-in (spatial/GP/
hier-correlation). Screening heuristic (rank iff window cross-correlation
sigma2/sigma1 > threshold) = natural follow-up. PR #4 follow-up 6 posted.
Residual gap to cmdstan (8-9 vs 4 bad) is funnel-class: needs mode-aware
warmup (multi-chain controller R-hat-lite + reinit), not metric work.

## 2026-08-20 ~14:30 — cross-chain mode diagnostic + reinit evidence

- AdaptResult.log_mass_dispersion added (cheap O(MD) dispersion of log-mass
  diag across chains) — the hook for mode-aware reinit policies.
- Reinit-from-different-pf-pool demo: 8schools_centered rhat 1.16->1.08,
  pilots 3.37->2.06 (monotone in draw quality). Gap remains: funnels need
  in-sampler multimodality handling (research frontier, documented).

## 2026-08-21 ~09:00 — overnight session wrap-up

Session deliverables (since ~13:00 yesterday):
1. W-7 budget sweep (user question): NO crossover — fixes change the
   asymptote. stock@4000 (15 bad, ESS 93) << full@1000 (8 bad, 317). ~4x
   budget-equivalence. PR #4 follow-up 5.
2. W-8 full-grid rank metric: per-geometry tool (bym2 2.4x, kronecker 1.2x,
   radon 1.14x) but hurts funnels (8schools_centered 0.19x) — off by
   default, documented. PR #4 follow-up 6.
3. Cross-chain log-mass dispersion diagnostic in AdaptResult + reinit-draw
   evidence (8schools 1.16->1.08, pilots 3.37->2.06).
4. Low-rank metric stack complete to math level: low_rank_metric.hpp
   (estimator), low_rank_mass.hpp (exact O(Dr) operator: apply/quad-form/
   EXACT chol momentum sampling/log-det), leapfrog property tests
   (reversibility 3e-17, volume 9e-16, momentum cov 2.5e-3, Woodbury-vs-dense
   4e-17). Hot-loop integration attempted, hit template surgery, REVERTED
   CLEANLY (build green, tests green) — left for a dedicated PR with CI gate.
   Property-first discipline caught 3 real bugs total this session
   (non-symmetric sandwich; sqrt-vs-D factor; wrong sqrt identity ->
   corrected via chol identity).
5. Wiki/flower optimizer research absorbed; Aurora et al. analysis recorded:
   matrix-geometry optimizers structurally inapplicable to scalar/diagonal;
   transferable lessons = zero-staleness, Newton-Schulz for future SVDs,
   LR>optimizer reality check.
State: all fork PRs updated (walnutpie #1-5 + 6 PR comments; cmdstan #1);
W-1..W-8 grids complete; dashboard current; worktree clean on walnutpie.

### PRE-REGISTERED W-9: full low-rank operator vs fold vs diag (post-fix)
After two integration bugs were found+fixed (reversible_lr/uturn_lr consistency;
frozen-sampler dropping the rank part), full-vs-fold is a fair comparison now.
Models (cross-structure set): hier_2pl, kronecker_gp, lsat_model, bym2_offset_only,
radon_partially_pooled_noncentered, garch11. Variants: w9_full (r10+full),
w9_fold (r10), w9_diag (base recommended config). 4 chains, 1000+1000, 3 reps,
seeds/pf-inits per protocol. Judged: geo ESS_bulk_min, rhat, wall per model.

## 2026-08-21 ~10:00 — full low-rank operator: 2 bugs fixed, wired, screening heuristic

- Integration bugs found by analytic-target testing (correlated 3D Gaussian):
  (1) reversible()/uturn() used diagonal lrm.D while trajectories integrated
  with the FULL operator — rejection criterion under wrong Hamiltonian;
  fixed with rank-aware within_tolerance_lr/reversible_lr/uturn_lr.
  (2) sampler() dropped the rank part at freeze — warmup tuned under the rich
  metric, sampling ran with plain diagonal (silent mismatch); fixed via
  WalnutsSampler::set_low_rank.
- Validation: analytic Gaussian moments identical to fold (diag err 0.022,
  offdiag 0.015); hier_2pl min-ESS parity restored (26/26).
- Screening heuristic (--metric-auto): signal = concentration of singular-
  excess in top-5 dirs. INVERTED discrimination discovered empirically:
  spread spectra (frac<0.1: hier_2pl 0.073, kronecker 0.092, bym2 0.057,
  lsat 0.063) = rank HELPS; concentrated (frac=1.0: blr, 8schools_centered)
  = rank HURTS (funnel/spike geometry). Threshold 0.5 separates cleanly.
  Auto probe: 8schools_centered 26/1.13 (protected vs 13/1.24 forced-rank),
  hier_2pl 75/1.05 (allowed). 
- W-9 grid (full vs fold vs diag x 6 cross models x 3 reps) running.

## 2026-08-21 ~12:00 — W-9 verdict: diag strong under good inits; full > fold; rank narrow

W-9 (6 cross models x 3 reps, proper per-rep pf inits):
  geomean ESS_min: fold/diag=0.66, full/diag=0.79, full/fold=1.21
  rhat>1.02: diag 3/6, fold 3/6, full 2/6 (full best R-hat profile)
Reading: (a) with typical-set inits + chopping, the plain diagonal Fisher
metric is already strong — earlier fold wins (W-8) were rep0-only artifacts;
(b) when rank IS used, the exact operator beats the marginal fold (1.21x);
(c) rank pays only on hier_2pl (full/diag 1.24); bym2/radon full regress
(0.38/0.60) — screening still needed, metric-auto remains the right shape.
FINAL RECOMMENDATION: default = diag + batch + pf-init + chop; metric-auto
optional for hier-class; full operator the right impl when rank is on.

## 2026-08-21 ~14:00 — W-10: auto-screening validated end-to-end

w10_auto05 vs w6 base (20 models x 3 reps):
- Screen correctly DISABLED rank on pure-diagonal models (ratio exactly 1.00
  on 8 models incl blr, pilots, diamonds, arma11) — no harm where rank hurts.
- Screen correctly ENABLED where rank pays: bym2 3.46x (ESS 35.7->124, rhat
  1.08->1.03), eight_schools_centered 1.11x (protected AND improved).
- Seed-dependence remains on hier_2pl (0.2x) / kronecker (0.6x): rank fires
  there but net value flips with rep (consistent with W-9's rep spread).
- Aggregate: geo_ess 279.8 (base 294, forced-rank 267.3); rhat-bad 8 = base.
VERDICT: metric-auto is the right shipping shape — protective, never worse
in aggregate, big targeted wins. Default remains diag; --metric-auto 0.5 is
the recommended optional flag.

## 2026-08-21 ~15:00 — Phase 2a first patch: bit-identical, no measurable win (negative)

stan/patch: rho_fwd/rho_bck hoisted out of the NUTS doubling loop (2 heap
allocs/doubling). Validated: bit-identical draws (arma11, seed 42, 200+200
warmup+draws incl warmup), timing within noise (arma11 0.139 vs 0.130 grid
median; pilots 1.513 vs 1.270; blr 0.067 = same). Conclusion matches ATLAS:
the rho pair is a small slice of the allocation story; the real 2a needs the
full set (z_propose copies per leaf + p_sharp* vectors + build_tree temporaries)
in one coordinated change — saved as patches/stan-2a1-rho-hoist.patch with
rationale; pinned tree restored pristine (verified byte-identical).

## 2026-08-21 ~16:00 — session close-out

- FINAL_REPORT.md written (results/FINAL_REPORT.md): baseline atlas,
  adaptation-arc summary with all numbers, optimizer research, patches, open items.
- patches refreshed: walnutpie-stepopt.patch (main..dev/init-robustness,
  includes the whole stack), stan-2a1-rho-hoist.patch (negative result, kept).
- All fork PRs current: walnutpie #1–#5 with 8 evidence comments on #4;
  cmdstan #1. W-1..W-10 grids complete and aggregated; dashboard live.
- No jobs of mine running; cmdstan tree pristine; 4-core discipline held
  throughout (verified repeatedly).

## 2026-08-21 ~17:30 — mode-aware reinit shipped (API layer)

walnuts_with_reinit + adapt_with_stats in api.hpp/adapt.hpp: dispersion check
-> re-draw inits from pool -> re-warmup (max_reinits). Smoke on funnel-ish 2D
target: pathological inits (8,8) rescued (4/4 chains mean y~0, reinit visible
in budget), healthy runs untouched. PR #4 follow-up 9 posted. Concept-fix
notes for future handler authors recorded (on_logp_exception, on_r_hat,
throw_if_interrupted names).

## 2026-08-21 ~19:30 — W-11: mode-aware reinit on the funnel class (random inits, 3 reps)

Arms: nore (random inits, no reinit) vs re (random inits, dispersion 0.5,
max 2 reinits from pf pool). 4 chains, warmup<=1000 adaptive, draws<=500
(adaptive stop, ragged chains trimmed to min for ESS).
- eight_schools_centered: reinit roughly neutral (27-99 both arms; rep2 74->80)
- pilots: neutral-to-mixed (rhat 2.3-4.2 both arms; min-ESS 5 everywhere)
- diamonds: mixed (rep2 4->6 ESS, rhat 3.33->1.77 = best diamonds result yet;
  rep0 geomean down)
HONEST VERDICT: with random inits on the funnel class, dispersion-triggered
reinit is NOT a reliable rescue at these settings — the first warmup often
collapses the stepsize before the dispersion check can fire (lotka aborted
in both arms). The policy's value case remains: healthy-inits + occasional
draw-pool swap (follow-up 2's evidence), and post-collapse restarts need the
drift/metric safeguards ACTIVE during the reinit round (currently default
warmup config, no clamp/heuristic — driver limitation, not API).
Driver lessons recorded: BridgeStan model not thread-safe => mutex in logp;
constrained output includes gq (names must match); ragged chains from
adaptive stop.

## 2026-08-21 ~21:00 — reinit composition: safeguards inherited; ODE-funnel edge case

- api.hpp: reinit rounds now inherit mass_init_clamp via WarmupConfig (new
  config field + builder setter + CLI wiring), so restarted warmups get the
  same init-robustness as round 0.
- W-12 probe (lotka_volterra, random inits): even with clamp + step
  heuristic (eps 0.016 found) the run aborts at macro_time->0: the ODE model's
  invalid-parameter regions cause total rejection cascades; anti-windup is
  the remaining guard but it's a CLI-dispatch feature (adapter template), not
  yet configurable through WarmupConfig — noted as the next API gap.
- Honest state: lotka = documented edge case (CLI also aborts on random
  inits); W-11 verdict unchanged.

## 2026-08-21 ~22:30 — adapter selection moved into WarmupConfig; double-wrap bug fixed

- Anti-windup now library-configurable (WarmupConfig.anti_windup_pass_rate;
  AdaptiveWalnuts default adapter = AntiWindupAdapter<Adam>, rate 0 =
  pass-through => default behavior unchanged, verified blr 137/1.016).
- Found+fixed a real composition bug en route: CLI-side wrapping +
  library-level default wrap => 63/64 observations dropped => sd=0 chains.
  CLI wrapping removed; config drives it everywhere.
- The reinit driver can now request the full safeguard stack through config
  (clamp + heuristic-eps + chop + anti-windup) — the composition W-12 wanted.
  ODE-lotka still aborts (rejection cascade beyond anti-windup's power at
  these settings): documented edge case.

## 2026-08-21 ~23:15 — day-2 close

- Regression check after adapter-default change: recommended config unchanged
  (blr 439/1.014, arma11 536/1.004, kidscore 243/1.033) — pass-through default
  verified on real models.
- patches/walnutpie-stepopt.patch refreshed (full stack through adapter-config
  work). All pushed. Two real bugs found+fixed today (frozen-sampler metric
  drop; anti-windup double-wrap) + one honest negative (W-11 reinit-on-random).

## 2026-08-22 ~00:30 — W-14: composition (full safeguard stack + reinit) on funnel class

Config: driver with mass clamp 100 + step-init heuristic (find_reasonable_step)
+ metric-window 50 + anti-windup 8 (now all selectable through WarmupConfig
after the adapter-selection change) + reinit (dispersion 0.5, <=2 rounds,
pf pool). Random inits, 4 chains, 3 reps — same protocol as W-11.
Results (min-ESS / rhat_max, medians):
- eight_schools_centered: nore 74/1.045, re 32/1.109, FULL 62/1.042
- pilots:                  nore 5/2.91,  re 5/3.25,  FULL 5/2.83
- diamonds:                nore 53/3.26, re 49/2.94, FULL 79/2.24
VERDICT: composition helps the median on 2/3 (diamonds, esc-re-arm) and is
not harmful on pilots, but does NOT rescue the class: pilots min-ESS stays 5
(chain-level mode-lock), diamonds rhat still >2. The residual failure is
single-chain scale/mode lock that no warmup-config stack fixes — confirms
the research-frontier note (needs draw screening at reinit or in-sampler
multimodality handling).

## 2026-08-22 ~02:00 — provenance audit + 4 fixes; W-15; PR #6

- Independent audit (subagent, glm-5.3) of origin/main..dev/init-robustness:
  ALL session bugs ours (introduced+fixed on dev; none upstream). 51 hunks:
  35 pure adds, 16 upstream-touching (all extensions, default-off). No
  upstream fix PRs warranted. Report: external/upstream_audit_walnutpie.md
- Audit caught 2 LIVE bugs at HEAD + 2 housekeeping items, all fixed (6fd6664):
  fold-mode freeze mismatch (since 5302ed8), rank combined-span uturn,
  inert --anti-windup CLI flag, restored Range check. Honest correction of
  the B2 'double-wrap' story (was single-wrap rate-8 semantics).
- Validation: default path BIT-IDENTICAL (blr 439/1266/1.0139); rank modes
  now win hier_2pl: diag 25/1.122 -> fold 38/1.093 -> full 167/1.030 (6.7x).
- PR #6 (fork): upstream/adapt-with-stats — adapt_with_stats + dispersion,
  minimal zero-behavior-change slice, syntax+build validated against main.
- W-15 targeted reinit: neutral on funnel class (mode-lock diagnosis holds).


## 2026-08-22 ~02:45 — W-16: freeze memo; third freeze-mismatch (full-rank D); model trials

- Third freeze-mismatch instance found+fixed (ef3c582): full-rank warmup
  integrates with UNFOLDED lrm.D, frozen sampler rebuilt it from folded
  inv_mass(). Memo now carries the exact mass the last transition used.
- Protocol lesson re-learned: hier_2pl single-rep min-ESS swings 20-420
  across bit-identical reruns; all earlier single-rep rank-mode comparisons
  retracted in favor of 3-rep medians.
- 3-rep medians (hier_2pl, pf inits): diag 16/1.175 -> fold 188/1.024
  (11.75x) -> full 18/1.175. Fold = recommended rank mode.
- Model trials (user-requested): openrouter/stealth/ox-alpha absent from
  daemon registry; opencode zen muse-spark-1.2-contributor-free = 429
  FreeUsageLimitError (quota); x-preview-f-free answers correctly via
  direct HTTP (reasoning model: reasoning_content + content, needs large
  max_tokens) BUT relay 500s on large prompts and the RLM daemon flattens
  its output to empty messages. Documented; zai/glm-5.3 remains the default.


## 2026-08-22 ~03:30 — ESS/grad evidence package: 0.06x claim corrected to 0.31x

- Found two metric-definition asymmetries in the per-variant table:
  walnutpie's n_leapfrog_total includes WARMUP grads, cmdstan's is
  sampling-only (saved rows); cmdstan's n_leapfrog_sampling is actually
  "last 500 of 1000 draws". The ~0.06x ESS/grad claim was an artifact.
- Fair recompute (sampling-phase-only both sides, 20 models, median of 3):
  geomean 0.31x. Splits cleanly: 0.25-1.33x on the 13 well-mixed models
  (kronecker 1.33x, pilots 1.05x, esc 1.00x = walnut WINS); collapse only
  where mixing fails (hier_2pl 0.025x, bym2 0.062x, diamonds 0.075x).
- aggregate.py fixed to prefer n_leapfrog_sampling for ess_per_grad.
- accel_gp robustness asymmetry documented: walnutpie aborts on non-finite
  logp mid-trajectory where Stan rejects; all samplers give ESS 1.0 anyway.
- Package: external/ess_per_grad_evidence.md (for the Flatiron team).
- W-17 sweep running (rec/fold/auto x 21 models x 3 reps, freeze-fix binary);
  accel_gp aborts expected under all configs (known).


## 2026-08-23 ~00:30 — W-17/W-18 verdicts; reproducibility bug found+fixed (ours)

- W-17 (21 models x rec/fold/auto x 3 reps, pre-fix binary): arms
  statistically indistinguishable (fail counts 14/16/14 @rhat>1.01;
  geomeans within 13%). No fold catastrophes; no robust fold win either.
- W-18 (6 marginal models, 1000 draws, 2 reps): ESS ~doubles, R-hat stays
  1.02-1.06 => marginal misses are slow mixing, not short runs. Answer to
  'are 500 too short?': longer helps ESS, does not flip the R-hat verdict.
- REPRODUCIBILITY BUG (ours, found via W-16 vs W-17 contradiction 16 vs 247):
  find_reasonable_step drew probe momentum from Eigen::VectorXd::Random()
  (std::rand, clock-seeded by main) => --step-init-heuristic made fixed-seed
  runs irreproducible. Fixed (869dbe7): seeded detail::Random<RNG> threaded
  through; 3-run bit-identity verified. warmup_heuristics.hpp never existed
  upstream => NOT an upstream bug. W-16 hier_2pl numbers retracted; clean
  rerun (w16clean) queued after W-18. Earlier 'init-file-only nondeterminism'
  was a harness false positive (duplicate flag; cmp on missing files).
- Aurora research (hermes glm-5.3): arXiv:2606.27715, tall-2-D only,
  degenerate below 2-D like Muon; full 2025-26 successor table incl. MuonEq
  (diagonal equilibration before NS) and scalar closed-loop line
  (NAMO/OptMuon/AdaGO). Saved external/research_optimizer_aurora.md.
- Score-as-second-dimension: confirmed live in the low-rank estimator
  (st = [Ys|Ss] stacked, SVD) — the sampler-appropriate '2-D' structure;
  hermes: no published sampler-side NS orthogonalization exists; our score
  variance diagonal = Fisher-adaptive Langevin (2305.14442) restricted to
  diagonal.


## 2026-08-23 ~02:00 — w16clean verdict + W-19 pre-registration (2-D optimizer comparison)

- w16clean IS bit-reproducible (initial cmp mismatch = analyzer header rewrite
  in place + trailing newline; no second bug; CLI warmup = fixed direct loop).
- Clean verdict: fold 35/1.084 ~= rec 33/1.089 medians (tracks rep-for-rep);
  full 21/1.139 worse. 11.75x retraction confirmed (clock-luck). Rep-variance
  dominates: init draw quality >> arm choice on hier_2pl. PR #4 follow-up 15.
- W-17 + w16clean agree: fold ~= rec core-set-wide with pf inits; rank stays
  opt-in behind auto-screen.

## W-19 (pre-registered BEFORE running): basis-extraction rules for the
low-rank Fisher metric — the sampler-side 2-D optimizer comparison

Rationale: the 2-D object is the window matrices Y,S (D x K) or the
score-momentum matrix they induce; the "optimizer" is the rule that extracts
the rank-r basis U (+ weights c). All variants feed the SAME frozen
LowRankMass operator; only MassEstimator's low_rank_update changes.

Variants (flag --metric-basis):
  svd    : current — thin SVD of normalized [Ys|Ss] per window (chop)
  power  : streaming — accumulate M = beta*M + (1-beta)*S_norm per obs,
           rank-r via orthogonal iteration every window (no full SVD)
  muon   : Newton-Schulz polar(M) of the score-momentum matrix (5 NS its,
           standard Muon coefficients), basis = polar columns, per window
  muoneq : MuonEq-style diagonal equilibration BEFORE NS (row RMS of M),
           then de-equilibrate the basis
  (aurora-style row-oblique projection: only if muon shows pathology —
   its leverage fix is one more alternating projection on top)

Protocol: rank-relevant models only (kronecker_gp, bym2_offset_only,
hier_2pl, eight_schools_centered, diamonds, pilots, arma11, blr as control),
3 reps, 4 chains, 1000+500, pf inits, fold-mode config, fixed binary.
Metrics: min-ESS/R-hat medians (as everywhere), + basis-orthonormality and
operator SPD property tests before any sampling.
Expected (honest): bounded upside — fold~=rec says the basis is not the
bottleneck on the core set; the test is whether ANY extraction rule unlocks
the funnel class or beats svd on the rank-positive models. Negative result
also valuable: closes the "Muon-in-a-sampler" question empirically.


## 2026-08-23 ~04:00 — W-19 basis rules landed; stale-.o debugging tale; post-fix e/grad

- --metric-basis {0,1,2,3} (svd/power/muon/muoneq) committed (2f97cd6),
  property-tested BEFORE sampling: orthonormality 1e-15, c>=0, top-direction
  recovery, replay determinism. Test caught OOB (V(best,j), 2K-index into
  D x r) pre-sampling.
- Debugging tale: after the fix, cmake binary STILL crashed (malloc unaligned
  tcache) while manual/ASAN builds (same compiler, same flags, same vendored
  paths) ran clean. ROOT CAUSE: stale object file — incremental build
  silently skipped the header change (.o mtime 00:34 < header mtime 00:35).
  RUNBOOK: after scripted header edits, delete .o or --clean-first. (gdb
  backtrace + mtime comparison pinned it; no compiler/ABI/allocator issue.)
- w17g (7 models x 3 reps, log capture) processed: post-fix e/grad
  hier_2pl 2.6x better than pre-fix (1.05e-3), esc 1.3x, pilots 2.8x.
  Evidence package + PR #4 follow-up 16 updated.
- W-19 sweep launched: 8 models x 4 bases x 3 reps (fold config).


## 2026-08-23 ~05:00 — W-19 VERDICT: basis rule is second-order (clean negative)

8 models x {svd,power,muon,muoneq} x 3 reps, fold, reproducible binary:
geoESS(all) 32/30/38/35 — all within rep noise; no rule rescues funnels
(diamonds best 1.534 via muon, pilots 2.31; both still fail). Muon's NS
performs like windowed SVD here: the 2K-column data matrix is
well-conditioned; NS's LLM-regime advantage (ill-conditioned momentum)
doesn't exist at sampler scale/cadence. Closes the 2-D-optimizer question
empirically: basis is NOT the bottleneck; init + single-chain mixing are.
W-19 numbers are the citable ones (reproducible binary; W-17 absolutes
shifted by clock-eps). PR #4 follow-up 17. results/w19_summary.json.

NIGHT-SHIFT LEDGER (all threads closed):
- reproducibility: found (Eigen::Random clock-seed), fixed, verified
  bit-identical; retraction posted; clean rerun confirmed fold~=rec
- stale-.o trap: diagnosed (mtime), documented, runbook updated
- W-17/W-18: fold~=rec core-set; 500->1000 draws don't flip R-hat verdicts
- e/grad: post-fix 2.6x on hier_2pl (direct capture), package updated
- Aurora: researched (tall-2-D only), notes filed
- 2-D comparison: implemented (--metric-basis), property-tested, swept,
  NEGATIVE with mechanism explanation


## W-20 (pre-registered): position-reuse rate inside a run — the memoization question

From the e/grad evidence package (candidate 2): 'if the dyadic search revisits
the same (position, step) pair, logp_grad is called again; a position-keyed
cache within a run could cut evals with zero algorithmic change.'
Cheap decisive measurement BEFORE implementing anything: wrap logp_grad in a
counting driver, hash each unconstrained position (64-bit, full precision
bytes), count duplicate hashes across the whole run (upper bound: includes
different-eps visits which a cache keyed on position alone would wrongly
serve; position-only duplicates are still the necessary condition).
Models: blr, hier_2pl, kronecker_gp (the well-mixed class where the 0.3-0.8x
e/grad gap lives). Expectation: near 0 (each macro step moves the chain; the
dyadic ladder evaluates the SAME position at MULTIPLE eps - those are not
reusable). If <1%: hypothesis closed (negative); if >5%: prototype the cache.


## 2026-08-23 ~06:30 — W-20 VERDICT: no ladder revisits; exactly 1 redundant grad per iteration (boundary re-eval)

Instrumented driver (position-hash counting, no library changes), 3 models,
400 warmup + 200 draws, single chain, recommended config:
- blr 5.55% / hier_2pl 3.91% / kronecker 3.56% duplicate positions.
- Phase split: dups == warmup_iters + draws + 1 EXACTLY (400+200+1=601) on
  every model => exactly ONE duplicate per macro step, uniformly across
  warmup AND sampling: each transition re-evaluates its START position,
  whose gradient the previous transition already computed as its END point.
  The dyadic step ladder revisits nothing (0 accidental dups).
- Implication: a hash cache is unnecessary; the fix is threading the
  endpoint (theta, grad, logp) through WalnutsSampler/AdaptiveWalnuts state
  (start-position eval becomes a reuse). Expected saving 4-6% of all
  gradient calls, mechanically lifting e/grad by the same factor, with a
  perfect verification gate (reusing an identical double is bit-neutral =>
  draws must stay bit-identical).
- NOT implemented this session: hot-path surgery on walnuts.hpp (the
  template-surgery-mishap lesson); pre-registered as the fresh-session item,
  one change, bit-identity gate, 3-model verification.


## Phase 2a recon (read-only, this session): base_nuts.hpp copy/alloc inventory

Submodule re-initialized at the pinned SHA (v2.38.0-rc1-3, d13c50c0f).
Complete inventory of per-transition allocations in transition() + build_tree:

CONSTANT (transition scope, 4 ps_points = 12 VectorXd):
  z_fwd, z_bck, z_sample, z_propose  (+ VectorXd p_fwd_fwd, p_fwd_bck, p_bck_fwd,
  p_bck_bck, 4x p_sharp_*, rho, and per-outer-iteration 2x rho_zero)
PER-SUBTREE (build_tree recursion, EVERY internal node):
  ps_point z_propose_final        -> 3 VectorXd allocs (q,p,g) + V copy
  p_init_end, p_sharp_init_end    -> 2
  rho_init (Zero)                 -> 1
  p_final_beg, p_sharp_final_beg  -> 2
  rho_final (Zero)                -> 1
  rho_subtree = rho_init+rho_final-> 1 temp + 2 more for extended checks
  => ~10 VectorXd allocations per internal build_tree node, ~2-3 temps.
  At depth d there are 2^d - 1 internal nodes + 2^d leaves; for a typical
  depth-6 trajectory that's 63 nodes x ~10 = ~630 heap allocs/transition,
  on top of 63 leaf-level ps_point assignments (z_propose = this->z_:
  3 assign each, no alloc after first).

Attack order (highest leverage, lowest risk):
  1. hoist z_propose_final + the 4 per-node VectorXd scratch into a
     per-transition scratch stack (std::vector member, sized once per
     model, indexed by depth) — kills ~630 allocs to ~0.
  2. rho_init/rho_final: Zero() -> setZero() on hoisted buffers.
  3. rho_subtree chain: reuse one buffer (3 sequential uses).
  4. LEAVE ALONE: leaf z_propose = this->z_ (semantic, cheap assign),
     transition-scope 12 vectors (once per transition, negligible),
     compute_criterion (no alloc), integrator/hamiltonian internals
     (diag_e: dtau_dp = inv_mass.cwiseProduct(p) — one temp, could be
     noalias'd but tiny).
Verification gates (the rho-hoist negative result showed bit-identity is
NOT automatic): (a) draws bit-identical vs stock for 3 models x 3 seeds —
REQUIRED for scratch reuse since arithmetic order unchanged; (b) if any
gate fails, stop and bisect the specific hoist; (c) callgrind memcpy/alloc
share on pilots must drop materially from 21%; (d) wall-clock paired t on
the small-model class.
Plan: implement as ONE coherent patch on a dev branch of the stan
submodule, never mixed with other changes; fresh session per the lesson.


## W-21 (pre-registered): single-chain warmup early-exit (temporal stabilization)

Motivation (measured tonight): logp_grad = 68-99.7% of walnutpie sampling
wall (w17g logs) => kernel/SIMD polish would target <=2% on most models —
CLOSED as a direction, data on file. But warmup = 65-76% of total wall and
the CLI burns a FIXED num_warmup loop, bypassing the library's convergence
controller (which is multi-chain only). If the metric stabilizes at ~200 of
1000 iterations, early exit saves ~40-50% of total wall.

Prototype (CLI-side, no library changes, zero risk):
- flag --early-exit-warmup [tol] (0=off default)
- criterion: after min_iter=200, every 50 iters (aligned with metric-window
  chopping = successive INDEPENDENT window estimates), snapshot inv_mass();
  exit when successive-window l2 rel-diff < tol (default 0.25; library's
  own cross-chain tol is 1.0 — ours tighter because temporal comparison on
  the same chain) AND step rel-diff < 0.3.
- Gates: (1) freeze-class models must not early-exit into failure — check
  frozen params non-degenerate + failure count not worse across 21 models;
  (2) ESS_min within noise of fixed-1000 on well-mixed class; (3) wall
  drops materially; (4) reproducible (same seed + same early-exit decision
  => bit-identical draws given identical iteration count).
Sweep: both arms fresh on current binary, 12 models (wall-heavy + fast
controls) x 3 reps.


## 2026-08-23 ~12:00 — W-21 SHIPPED: --early-exit-warmup (knob, default off)

- Direction triage (measured): logp_grad = 68-99.7% of sampling wall (w17g)
  => SIMD/kernel polish targets <=2% on most models — direction CLOSED with
  data on file. Real levers: fewer grads (W-20: 1/transition redundant,
  threading fix queued fresh-session) and fewer wasted warmup iters (W-21).
- W-21 final: tol flag (mass) + step tol 0.1 (library semantics; 0.3 draft
  regressed lsat, 0.1 recovered 301->501 @exit 500). 12+6+2 models x 3 reps,
  both arms. Wall 1.3-2.4x where it exits (geomean ~1.5x mixed); quality
  neutral-to-positive on easy (blr +27% ESS), NEGATIVE on marginal class
  (arma11 -33%, lsat -40%, hier_2pl -58%). Criterion self-protects (esc
  exit@650, lsat/hier@500); funnel class no new failures; bit-reproducible.
- Recommendation: default off; for wall-bound easy models. Library-level
  quality-preserving version = adapt() multi-chain path (controller already
  has the machinery) — natural upstream follow-up.
- Commits 024d458, 3eddfc4; PR #4 follow-up 19.


## 2026-08-23 ~12:45 — W-22 diagnosis: WHY W-21 hurts the marginal class (step, not mass)

Per-iter traces (chain 0, fixed warmup): the late warmup signal is the STEP
SIZE, not the metric:
- hier_2pl: step 0.0141->0.0378 (+169%) between windows 200-400 and 800-1000
  while invm moves only +13%
- lsat: step +172%, invm +1.8%
- arma11: step +12%, invm -2.3% (and arma11 regressed only -33%)
=> W-21's failure mode is precisely characterized: mass stabilizes early,
  step keeps growing (Adam still marching toward its equilibrium for
  hundreds of iters). A future quality-preserving early exit must gate on
  STEP stabilization specifically (e.g., relative step drift over the last
  2 windows < 5%), not mass. Recorded for the library-level follow-up.

## 2026-08-23 ~13:15 — W-22 close-out; apin made portable; handoff skill

- Portable remote live: git@github.com:sims1253/apin.git (snapshot @ 9fcabfe:
  harness/results/models/data/patches/docs; externals as PINNED SUBMODULES —
  walnutpie@3eddfc4 fork dev/init-robustness, cmdstan@6380837 fork
  nindan/mixed-build-guard, posteriordb@28f8d3d6, tinystan@db27f82; runs/ and
  bs_models/ excluded, regenerable per BOOTSTRAP.md). Verified by fresh
  clone + submodule init. Local export mirror: ../.export-apin (for future
  snapshot pushes).
- Handoff skill: ~/.agents/skills/handoff/SKILL.md — routes to canonical
  records, lists the 3 queued fresh-session items with gates (endpoint-grad
  threading; stan-2a2; library early-exit w/ W-22 step-gate), protocol,
  gotchas.

## 2026-08-23 ~14:00 — handoff packaging (docs only, per user)

- NEXT_IDEAS.md: 4 documented open items (A: logp_grad via model flags —
  bs_models_o3 prepared locally, per-call comparison pending, mixed-build
  caution + statistical-not-bitwise comparison rule; B: mixing-difficulty
  diagnostic — W-21 runs ARE labeled data, threshold-rule fit costs zero
  sampling compute, pilot-burst design as fallback; C: slimming done,
  export ~57MB; D: entrypoints clarified).
- HANDOFF.md added to repo (self-contained copy of the skill; skills dir
  does not travel between machines).
- apin remote updated (slim + docs).


## 2026-08-23 ~14:30 — history purge of apin remote (user caught it)

- The .so/chain.csv deletions were tree-only; blobs remained in pack via
  history (and, after local rewrite, via refs/remotes/origin/main until the
  force-push). Fixed: orphan-squash to single commit e9d5a1c (snapshot repo;
  ledger = WORKLOG), force-push, reflog expire + gc.
- Verified SERVER-side by fresh clone: 0 large blobs in history, .git now
  11MiB (was ~40MiB pack), all entrypoint docs + submodule pins intact.
- Local .export-apin mirrors the purged single-commit state.

- LOCAL repo hygiene issue found (not fixed, documented): runs/ (26,692
  files, raw chains) is TRACKED and entered history via my `git add -A` in
  recent commits (0486440, 2162ffa, 62fb5bd, ...); .git = 44GB all loose
  objects (never gc'd). NOT pushed anywhere; stays on this machine. Remedy
  when wanted: git rm -r --cached runs/ + add runs/ to .gitignore + commit;
  then git reflog expire --expire=now --all && git gc --prune=now
  (expect hours, 44GB loose); or filter-repo if full purge of history.
  The apin REMOTE is unaffected and verified clean.

## 2026-08-23 ~15:00 — LOCAL cleanup EXECUTED (the deferred piece)

- Untracked + ignored: runs/, bs_models/, bs_models_o3/, models/*_model.so
  (.gitignore updated; files remain on disk: 26,692 runs files, 21 .so).
- History purged with git-filter-repo (--invert-paths runs bs_models
  'models/*_model.so'), 50s runtime. Result: .git 44G -> 86M (512x),
  19 commits preserved (hashes rewritten; earlier SHAs cited in WORKLOG
  are now historical narrative), 0 junk blobs reachable, submodule pins
  intact, status clean.
- Standing rule (also added to HANDOFF.md): NEVER `git add -A` in this
  repo — stage explicitly; runs/, bs_models/, *_model.so stay untracked.

## 2026-08-26 ~10:42 — fortk lane opened (pre-registered BEFORE running): per-model fused codegen on stanli

User forked seantalts/stanli → git@github.com:sims1253/stanli.git ("fortk").
Cloned to external/stanli @ 85a8f11 (== upstream main tip, zero fork delta yet;
untracked, same treatment as other external/ checkouts).

Thesis: stanli is an op-graph INTERPRETER over precompiled kernels (no JIT,
no codegen, by stated design; ~2.9x median grad win, ~100x source-to-CSV).
The unclaimed delta is per-model FUSED codegen (primal + adjoint) over its
lowered op sequence. This attacks the term ATLAS says dominates (logp_grad
= 68–99.7% of sampling wall) after the cheap levers closed (flags: closed;
stanc3 --Oexperimental: rejected Phase 0).

Design input recorded (user, re. a comment about autodiff "not mattering in
the age of agents" — hand-writing low-level model details with agents):
division of labor = deterministic codegen for structure (ms-scale compile),
agent-authored kernels for the finite op algebra (write-once, verify-once),
agent-authored whole-model fused kernels as cached AOT artifacts for hot
models; the differential parity harness is the gatekeeper in ALL tiers —
agents draft, the harness decides. Verification stays deterministic.

Pre-registered sequence + gates (all CPU, ≤4 cores, 3 reps medians,
gradient parity vs bridgestan .so at ≥50 random points: max |Δlogp|/|logp|
≈ 0 tolerance only if summation order preserved — else statistical):

- F-1 (baseline): stanli vs bridgestan logp_grad on 5 models spanning
  classes (eight_schools_nc, blr, radon_pp, hier_2pl, kronecker_gp — the
  bs_models/ .so set is ready). GATE: reproduce stanli's ~2–3x locally
  before building anything on top; if it does not hold, root-cause first.
- F-2 (ceiling probe): whole-graph fused C for 2 models (eight_schools_nc,
  blr), clang -O2 -march=native, vs both baselines. GATE: ≥1.5x over
  stanli interpreter to open the codegen lane; a miss is a written
  negative result, not a disaster.
- F-3 (only on F-2 pass): codegen tier design + prototype hooked into the
  op sequence; tiers = deterministic emitter / agent kernel library /
  Enzyme long-tail / interpreter fallback; cache keyed (model, shapes,
  flags).

In flight at time of writing: background agents mapping the stanli
architecture (lower/reroll/partition/executor/tape/kernel tiers) and
building+testing it (log: logs/stanli-build.md). F-1 runs when the build
lands; F-2 can proceed in parallel (independent of stanli internals).

### F-2 VERDICT (2026-08-26, executed by agent; full log logs/fortk-f2.md, artifacts bench/fortk_fused/)

Verification gate PASSED both models (never loosened; one agent mistake
caught by the gate — blr constant off by exactly 53·log√(2π), fixed):

| model | dim_unc | logp max rel | grad rel-L2 | bridgestan µs/call | fused µs/call | speedup |
|---|---|---|---|---|---|---|
| eight_schools_nc | 10 | 4.1e-16 | 9.2e-17 | 1.915 | 0.675 | 2.88x |
| blr (N=100,D=5) | 6 | 1.1e-15 | 2.6e-16 | 2.496 | 0.803 | 3.09x |

Protocol: C ABI vs C ABI (ctypes), taskset-pinned, 3 reps medians, A/B/A/B,
1.3–1.6M calls/rep. Findings:
- ctypes call overhead measured at 0.516 µs/call (no-op control) and
  DOMINATES the fused side at these sizes; kernel-only estimates ~8.9x
  (8schools) / ~7.0x (blr). Recorded numbers are protocol-faithful lower
  bounds.
- propto trap confirmed empirically: `~` statements drop constants in the
  reference (bridgestan propto semantics), `target += normal_lpdf` keeps
  them (propto flag bit-identical True/False). The activity-mask/propto
  doctrine in FORTK_DESIGN §7 is load-bearing, not theoretical.
- Agent-written adjoints reached 1e-16 correctness with exactly one
  harness-caught fix — a datapoint for the "agents draft, harness decides"
  division of labor.
- VERDICT DEFERRED to F-1 per the logged decision rule: F-2's ≥1.5x-over-
  stanli gate passes iff stanli < 1.9x vs bridgestan on these models; if
  stanli delivers its claimed ~2.9x here, the interpreter is at the fused
  ceiling FOR THIS SIZE CLASS and the gate fails as pre-registered.

### F-2b pre-registered BEFORE running (size-class extension)

Motivation: F-2's models are tiny (dim 10/6) where per-call overhead, not
bandwidth, dominates; the fused-codegen hypothesis lives or dies on bigger
graphs. Pre-registered:

- Models: diamonds (largest N in the bs_models corpus) + hier_2pl (medium,
  many params). Same verification gate (1e-12 / 1e-9, 64 seeded points,
  seed 20260826). Constants/propto derived from each .stan source and
  confirmed empirically vs npz (F-2 methodology).
- Protocol addition: C-loop driver — time the call loops INSIDE C for both
  the fused fn and the bridgestan C ABI, removing the 0.516 µs ctypes tax;
  report ctypes and C-loop numbers side by side. F-2's recorded numbers are
  NOT retroactively changed.
- Hypothesis (falsifiable): fused-vs-bridgestan grows with model size; under
  the C-loop protocol diamonds ≥4x. hier_2pl moderate (2–4x). If diamonds
  <2x under C-loop, the bandwidth-fusion thesis is in doubt and F-3's scope
  narrows accordingly.
- Feeds the same F-2 gate evaluation together with F-1 (is there headroom
  between interpreter and hand-fused ceiling on realistic graphs?).

### F-2b VERDICT (2026-08-26, executed by agent; full log logs/fortk-f2b.md; artifacts bench/fortk_fused/)

Verification PASS both models (gates never loosened): diamonds logp 1.1e-14 /
grad 5.6e-15; hier_2pl logp 6.1e-15 / grad 7.7e-16.

| model | protocol | bridgestan µs/call | hand-fused µs/call | speedup |
|---|---|---|---|---|
| diamonds | C-loop | 32.50 | 32.05 | **1.01x (parity)** |
| hier_2pl | C-loop | 621.4 | 430.4 | **1.44x** |

**Both pre-registered hypotheses FALSIFIED** (diamonds >=4x predicted;
hier_2pl 2–4x predicted). The <2x trigger fired: the naive
bandwidth-fusion thesis is dead. Mechanisms:
- diamonds: 960 KB/call X streams pin BOTH arms at ~30 GB/s single-core;
  Stan's AD overhead hides entirely under the stream. Single-core fusion
  cannot beat DRAM.
- hier_2pl: transcendental-bound — 99.4% of 19,200 obs take exp + log1p at
  ~22 ns/obs => 430 µs floor even perfectly fused; hand-fused hit exactly
  the floor. (Vs the stanli interpreter: 521/430 = 1.21x.)
- Combined with F-2 (tiny models, 2.9–3.1x vs CmdStan; 14.6x/4.3x vs
  interpreter): the fused advantage does NOT grow with size. It is largest
  where per-call overhead dominates and vanishes at bandwidth- or libm-
  bound sizes. REFINED THESIS: T1 pays on small/medium graphs (dispatch-
  bound: 4–15x) and mixed mid-size; at scale the wins must come from
  vectorized-ulp libm (exp/log1p ~2x more, 1e-9 gate headroom exists — T2
  item), cross-pass fusion (open problem), or multi-core.

Cross-lane flag (WALNUTPIE): in a bare C host, glibc mmap-threshold
pathology inflates bridgestan hier_2pl by 300+ µs/call (929 vs 621 µs with
mallopt-fixed thresholds) — allocator-sensitive, cheapest Stan-side win
measured. If walnutpie's host does not set M_MMAP_THRESHOLD, this is a
free win on alloc-heavy models. Also: ratios measured under foreign load
are biased UP (bridgestan arm is allocator-sensitive, fused kernel
allocation-free) — never benchmark this comparison on a loaded box.

Upstream-issue candidates (evidence pinned in logs/fortk-f2b.md):
1. Stan 2.39.0 bernoulli_logit_lpmf adjoint in the ntheta>20 saturated
   tail returns -exp(-ntheta) for y=1 — OPPOSITE SIGN of the true
   derivative (<=2.1e-9/term, replicated to 7.6e-16, source line pinned).
2. diamonds (posteriordb reference model) appears to omit the student_t
   -log(sigma) term on the unconstrained scale (measured exactly +1
   gradient offset; source suggests it should be present).

CORRECTION (2026-08-26, later same day; verification agent, memo
orwell-pdb-diamonds-jacobian.md): candidate 2 RETRACTED — the jacobian IS
present and correct. sigma IS real<lower=0>; grad(jacobian=True) minus
grad(jacobian=False) = exactly +1.0 in the sigma_unc coordinate at 8
seeded points and lp diff = sigma_unc to 1e-17 — the transform is fine.
The "+1 offset" was the F-2b prototype's OWN omitted jacobian (student_t
sigma_val misread: it is the scale constant 10, not the response); F-2b's
FINAL formula (with jacobian, verified 5.4e-15) and all F-2b timing
numbers stand. Nothing to file. Candidate 1 STRENGTHENED and drafted
(orwell-bs-logit-adjoint.md): saturated branch must read (2y-1)·e^-ntheta,
code returns bare -e^-ntheta — sign-flipped for y=1; present in
prim/prob/bernoulli_logit_lpmf.hpp:85 AND the OpenCL copy; unfixed on
math develop as of 2026-08-26; reproduced empirically at theta=25
(AD -1.3888e-11 vs analytic +1.3888e-11, exact match to -exp(-theta));
bug present since ~2015 (inherited from bernoulli_logit_log.hpp).
File-worthy; USER DECISION (2026-08-26): NO upstream interaction for now —
drafts stay local, nothing filed, no comments on #3374. Standing rule
until the user says otherwise.
IDENTITY NOTE (2026-08-26): this is the SAME bug as stan-dev/math issue
#3374 (filed 2026-08-24 by WardBrian, attributed to @sims1253) and the
user's own PR #3370 (opened+closed 2026-08-23, branch
bernoulli-logit-partials-sign; fix `signs * exp_m_ntheta` in the
ntheta>cutoff partials branch — identical formula and analysis to our
draft). F-2b's discovery was INDEPENDENT (hand-fused hier_2pl likelihood
vs CmdStan gradients, no prior knowledge) — corroboration, not novelty.
Delta our side can still add on #3374: the OpenCL copy of the bug
(opencl/prim/bernoulli_logit_lpmf.hpp:65-68) appears uncovered by
#3370/#3369; last-digit empirical repro (theta=25: AD -1.3887943864964021e-11
= -exp(-theta) exactly); since-2015 archaeology. Issue remains OPEN
(labeled good-first-issue, no linked fix).

Accounting note: our bridgestan absolutes are ~6x the Phase-0 WORKLOG
µs/grad figures (likely 4-chain parallel accounting there); within-protocol
ratios unaffected.

### F-1 VERDICT (2026-08-26, executed by agent; full log logs/fortk-f1.md, artifacts bench/f1/)

Protocol: C-ABI-vs-C-ABI ctypes both arms (noop control 0.479 µs, matches
F-2's 0.516), taskset core 2, A/B/A/B, 3 reps medians, >=2s/arm/rep.
Correctness anchor: stanli-vs-bridgestan gradient at 8 seeded points.

| model | anchor (grad rel-L2) | bridgestan µs/call | stanli µs/call | stanli speed |
|---|---|---|---|---|
| eight_schools_nc | 0.0 | 1.758 | 1.097 | 1.60x |
| blr | 2.2e-16 | 2.371 | 1.446 | 1.61x |
| radon_pp | 1.8e-14 | 333.674 | 63.241 | 5.30x |
| hier_2pl | 0.0 | 651.489 | 521.234 | 1.25x (1.25–1.31) |
| kronecker_gp | N/A (see below) | 307.472 | 323.458 | 0.96x |

**F-2 GATE: PASS.** stanli 1.60x and 1.61x on the gate models, both < 1.9x.
Direct view: F-2's hand-fused C (0.675/0.803 µs) is 1.62x/1.80x faster than
the stanli interpreter on the same models. The codegen lane opens.

Findings:
- stanli's corpus-claimed ~2.9x does NOT reproduce on 4/5 local models
  (only radon_pp 5.3x — where reroll/vectorization pays on a bigger graph).
  Not a refutation of their corpus median (different models, protocol,
  hardware), but locally the interpreter is far from the fused ceiling on
  small graphs: ctypes floor is ~44% of the stanli arm on 8schools; kernel-
  only estimates put fused/stanli at ~1.8x (8schools) / ~2.1x (blr) even
  before bandwidth effects. bench_grad in-C cross-check: 0.283 µs (8schools),
  0.597 (blr), 62.5 (radon_pp, 0.7% from our number), 494.5 (hier_2pl).
- kronecker_gp anchor structurally unattainable: Sigma1's 1e-5 jitter makes
  16–18/30 eigenvalue gaps machine-degenerate; eigenvector adjoints are
  basis-dependent; FD referee disagrees with BOTH sides by ~1%. Matches
  stanli's own corpus exception note for this model. Timing a wash (0.96x)
  — both arms dominated by the same eigendecompositions.
- hier_2pl only 1.25x despite 669 params: kernel time dominates dispatch;
  the op dump shows the surface (32× SLICE+MULTI_NORMAL_CHOL pairs; a
  6-op 19200-element elementwise chain into BERNOULLI_LOGIT). F-2b's
  hand-fused hier_2pl number quantifies the headroom.
- Op-dump recipe recorded: `stanc --O1 --debug-optimized-mir m.stan >
  m.tmir.sexp; build-rel/dump_ops m.tmir.sexp data.json`. 8schools=7 ops,
  blr=5, hier_2pl=97 (incl. 1 ISLAND).

### F-3 pre-registered BEFORE building (T1 deterministic-emitter prototype)

Scope: v1 emitter OUTSIDE the stanli runtime (additive tool on fork branch
fortk/t1-emitter): link the stanli core, run compile_model() exactly as
capi.cpp does, consume the post-pass Graph, emit ONE C file
(fortk_logp_grad(params, grad)) implementing the whole graph fused:
forward sweep + reverse sweep, per-op variant byte honored (activity
masks, propto, elementwise bits are load-time constants — specialize per
op instance), fills/data as initializers, ADD_N tree order preserved.

- Opcode subset v1: what 8schools/blr/diamonds need (CONSTRAIN_LOWER, FMA/
  MUL/ADD/SUB, ADD_N, NORMAL/CAUCHY/EXPONENTIAL_LPDF, BERNOULLI_LOGIT_LPMF,
  GATHER/SLICE/INDEX + whatever diamonds' dump shows). Unsupported opcode
  => loud rejection naming the op (hier_2pl's ISLAND is v2; GEMM if present
  = v2 or hand-rolled loop).
- Compile clang -O2 -march=native -ffp-contract=off (parity-friendly v1;
  FMA-contraction variant measured but not gated).
- GATES: (a) correctness — gradient rel-L2 < 1e-9 vs the stanli EXECUTOR
  (T0 oracle) at 64 seeded points (seed 20260826) on every emitted model,
  logp rel < 1e-9 modulo documented propto/constant differences; (b) perf —
  kernel-only (in-C loop, bench_grad-matched eval point) emitted >= 1.3x
  vs executor on >=2 of the target models; (c) record clang compile wall
  time of emitted C (informational target <2s, not gated).
- Deliverables: fork branch with tool + CMake target + test; logs/fortk-f3.md
  (incremental); emitted .c archived under bench/fortk_emitted/.

### F-3 VERDICT (2026-08-26, executed by agent; full log logs/fortk-f3.md; branch fortk/t1-emitter, commits 3687e52/f23a9ab/a2e8615, NOT pushed)

Correctness gate PASS all 3 models; perf gate PASS (2 of 3, diamonds honest
negative). Verification vs Executor oracle, 64 pts; kernel-only timing,
taskset core 2, 3 reps medians; clang -O2 -march=native -ffp-contract=off.

| model | grad rel-L2 | logp rel | exec µs/call | emitted µs/call | ratio | clang compile |
|---|---|---|---|---|---|---|
| eight_schools_nc | 0.0 (BITWISE) | 2.5e-16 | 0.2829 | 0.0194 | **14.58x** | 0.134 s |
| blr | 3.2e-16 | 2.4e-16 | 0.5715 | 0.1342 | **4.26x** | 0.167 s |
| diamonds | 3.9e-16 | 2.5e-16 | 34.96 | 40.13 | 0.871x | 0.404 s |

The JIT thesis is demonstrated end-to-end: .stan → MIR → Graph → one fused
C file → clang in 0.13–0.4 s → bitwise-or-1e-16-correct gradient at
4.3–14.6x over the interpreter on small/medium graphs. eight_schools at
19.4 ns/call sits ABOVE the F-2 hand-fused ceiling estimate — dispatch +
recorder tax is ~14x the arithmetic on tiny graphs.

Findings:
- The gate caught a real transcription bug (normal_id_glm residual
  inv_sigma weighting lost to a comment filter dropping continuation lines;
  cauchy dsigma likewise). Standing rule: transcribe stan-math semantics
  from RAW source only, no filtered reads.
- nid_glm kernel binds alpha/beta/sigma as var UNCONDITIONALLY, so
  -N·log(sigma) stays in its value even under propto — differs from
  recorder densities. The emitter must mirror EXECUTOR semantics (kernel
  behavior), not assumed language semantics; the oracle enforces this.
- diamonds (0.87x, negative): memory-bound — two 960 KB X streams both
  sides pay (fwd X·beta, rev Xᵀ·adj; ~55 GB/s single-core ≈ DRAM limit).
  Loop-order fix (col-major axpy, bitwise) + 4-lane unrolled reductions
  took emitted 118→40 µs; the executor's Eigen redux already reassociates
  (no order band existed; 1e-9 gate arbitrates, drift 3.9e-16). Winning
  this class needs cross-pass (fwd/rev) fusion or cache-resident blocking —
  declared open problem, not a blocker.
- ffp-contract=fast drift <= 6e-16 on all 3 (no contraction opportunity
  in emitted code as-is).

### F-4 pre-registered BEFORE building (T1 integration: region emission + runtime install)

Goal: turn the whole-graph emitter demo into a system inside stanli:
carve MAXIMAL regions of supported ops from the post-pass Graph (splits
around ISLAND/unsupported ops, which stay interpreted), rewrite each region
into a single op whose kernel (registered at tool load via the existing
register_kernel mechanism — the removed density-pack is precedent for
runtime kernel registration) dlopens the region's emitted artifact; build
the Executor from the rewritten Graph so ALL existing machinery (gradient,
sampling, cross-path tests, corpus oracle) runs on the fused model
unchanged. Plus: emit-cache keyed (graph region hash, flags, emitter
version).

- Opcode additions for hier_2pl coverage: GEMM (small const dims),
  MULTI_NORMAL_CHOL_LPDF, LKJ_CORR_CHOL_LPDF, CONSTRAIN_CHOL_CORR,
  DIAG_MATRIX. ISLAND stays interpreted via region splitting (no island
  bridging in F-4).
- GATES: (a) full-graph gradient parity vs UNMODIFIED executor at 64 pts
  (grad rel-L2 < 1e-9) on esnc/blr/diamonds AND hier_2pl; existing ctest
  suite stays green (62/62) with new tool tests; (b) perf kernel-only:
  no regression on the F-3 wins (esnc/blr within noise of F-3 numbers);
  hier_2pl target >= 1.3x, PRE-DECLARED as informative-if-miss (island +
  MVN kernel shares may dominate; a miss ranks, not kills); (c) sampling
  smoke: NUTS on a fused model vs unfused, same seed: identical or
  statistically-equivalent draws (bitwise expected where graph rewrite
  preserves order; else 3-seed statistical check) — first end-to-end
  sampler validation of emitted code; (d) record end-to-end compile budget
  (stanc + lower + emit + clang + dlopen) per model — the JIT-feel number.
- Work continues on the fork branch (fortk/t1-emitter or a child branch);
  no push; no modification of existing runtime behavior with the tool
  absent (opt-in path only).

### F-5 pre-registered BEFORE building (T2: vectorized ulp-accurate exp/log1p for the transcendental-bound class)

Motivation (from F-2b refined thesis): hier_2pl-class models are libm-bound
(99.4% of 19200 obs take exp+log1p, ~22 ns/obs, 430 µs floor hit by
hand-fusion). The identified next lever: AVX2 (Zen 3, 4-lane double)
vectorized exp and log1p with accuracy well inside the 1e-9 gradient gate.
This is the first T2 "agent-authored kernel library" item — the tier the
age-of-agents division of labor predicts pays.

- Deliverables (all in apin workspace, bench/fortk_t2/ — NOT the fork
  yet, to avoid file overlap with in-flight F-4): standalone C99 kernels
  (no external deps, no fast-math, -ffp-contract=off), reference-grid
  accuracy harness (vs mpmath), perf harness vs glibc scalar libm AND vs
  direct libmvec calls (_ZGVbN2v_* — callable without fast-math, fair
  baseline), and an end-use probe: COPY bench/fortk_fused/hier_2pl.c,
  swap the observation loop's scalar exp/log1p for the vector kernels,
  measure model-level effect (baseline: 430.4 µs/call hand-fused).
- GATES: (a) accuracy — max rel error <= 2 ulp vs mpmath over grids
  covering the model's operating ranges (exp args ±[0,40]; log1p args
  (0, ~1e-12] union [1e-12, 1e3]; document behavior at extremes), never
  loosened; (b) perf — >= 1.5x vs scalar libm per function on those
  ranges, in-cache, taskset-pinned, 3 reps medians; (c) end-use — fused
  hier_2pl copy with vector kernels must still PASS the F-2b verification
  gate (64 pts, grad rel-L2 < 1e-9) and report the model-level µs change
  (informational: PASS at >= 430*0.85 µs i.e. any real win; a miss ranks).
- Standing rules apply: no upstream interaction (user decision 2026-08-26),
  <=4 cores, quiet-box timing, incremental logging (logs/fortk-f5.md).

### F-4 VERDICT (2026-08-26; full log logs/fortk-f4.md; branch fortk/t1-regions, commits e55ea85+d1f234d, NOT pushed; suite 63/63)

The T1 tier now EXISTS as a system: .stan → stanc3 → MIR → passes → region
carve → per-region C emission → clang → runtime kernel install via
register_kernel → full executor/sampler machinery on fused regions.
Runtime diff: ONE inert opcode line (OP_FORTK_REGION appended; no traits,
no lowering, no kernel unless tool registers). Cache content-keyed
(structure-only; dataset-independent), cached path re-verifies 64 pts.

Gate (a) correctness PASS all four (+ radon_pp non-gate): esnc grad
BITWISE; blr 3.2e-16; diamonds 3.9e-16; hier_2pl 1.0e-15 (97 ops, island
splitting, MVN/LKJ/CHOL_CORR transcriptions); radon_pp 2.0e-14.

Gate (b) perf (unfused→fused executor, µs/call):
esnc 0.275→0.033 = 8.3x; blr 0.583→0.139-0.162 = 3.6-4.2x (within noise of
F-3); diamonds 33.8→39.6 = 0.85x (known bandwidth negative); hier_2pl
486.8→492.8 = 0.99x (pre-declared informative miss: transcendental-bound,
region fwd 360µs beats unfused bernoulli fwd alone but gather/adjoint
traffic balances); radon_pp 62.9→41.3 = 1.52x (the interpreter's
strongest class — total vs CmdStan now 333.7/41.3 = 8.1x). PARTIAL MISS:
esnc region fns 22.7-25.3 ns vs F-3 single-fn 19.4 ns (+17-30%, outside
noise) — mechanism: executor's two-call fwd/bwd Kernel ABI forces a
round-trip F-3's single-function scope didn't pay; only visible on
overhead-bound regions.

Gate (c) sampling: NOT bitwise anywhere (last-bit lp drift ~1e-16
amplifies chaotically in NUTS — expected, now MEASURED); 3-seed
statistical equivalence all four (worst z 2.26-3.05, consistent with
noise over 30-2000 comparisons); divergences 0/0 every model both arms.
Doctrine: fused-tier draws are statistical-equivalence class, not
bitwise class.

Gate (d) compile budget cold→cached: esnc 0.15→0.002 s; blr 0.17→0.002;
diamonds 0.43→0.035; hier_2pl 2.02→0.011 (clang on one 290KB region file
dominates; per-region file splitting = future item). JIT-feel achieved.

Bugs caught by the 1e-9 gate during build-out (never loosened; the
harness-as-compiler pattern now 5-for-5 today): scratch persisting across
gradient calls (pt0 bitwise, pt1 wrong — insidious); MVN half/scaled_diff
transposition; shared lp0 leaking across 32 MVN instances; log1m not in
C99 (= log1p(-x)). Plus design-time raw-source catches:
CONSTRAIN_CHOL_CORR jacobian is log(1-tanh^2(y)) not log(1-y^2).

### F-4b pre-registered BEFORE building (single-region fast path + sampler-overhead census)

Two small items, one agent:
- (i) DIRECT PATH for single-region graphs: tool-side
  fortk_grad_direct(params, grad) calling ONE emitted fn (fwd + adjoint
  memset + bwd in a single call, no per-op dispatch tables, no ctx
  refresh) — recovers F-3's 19.4 ns on esnc-class models. GATE: esnc
  direct-path within noise of 19.4 ns; correctness 1e-9 vs executor
  (64 pts, same seed); blr/diamonds sanity.
- (ii) Sampler-overhead census (informational, no gate): with fused
  gradients, where does NUTS wall-time go on esnc (33 ns/grad →
  bookkeeping dominates)? Time stanli_run nuts vs walnuts per iteration
  on fused + unfused esnc/blr; decompose grad-time vs tree bookkeeping;
  report ns/iteration overhead of each sampler loop.

### F-6 pre-registered BEFORE running (corpus census: the coverage number)

Run the fortk_t1r tool over ALL 21 bs_models .stan sources (models/):
per model — dump_ops stats, carve accept/reject + blocking opcodes,
verification (64 pts < 1e-9 or documented failure), fused vs unfused
executor µs/call. Output: coverage table (fraction of corpus T1 helps,
median speedup, opcode blocker histogram). No perf gate — census. ODE
models (lotka_volterra, sir) expected to reject via ode ops; linalg-heavy
(gp_regr, accel_gp, kronecker_gp) expected slow/parity. Honest table,
including the rejects.

### F-6 VERDICT (2026-08-26; full log logs/fortk-f6.md; raw bench/fortk_f6/; zero fork changes)

Census of the T1 region tier over ALL 21 bs_models (taskset -c 2, 3-rep
medians, in-C loop; verify 64 pts seed 20260826 vs unfused executor):

- Carve coverage 19/21 (90.5%); full-pipeline accept 18/21 (85.7%);
  verification 18/18 PASS among completed (worst 2.0e-14 — five decades
  inside the gate; bym2/low_dim/kronecker BITWISE).
- Speedup among verified (n=18): median 1.25x, geomean 1.81x, range
  0.92x–8.04x. Bimodal exactly as the refined thesis predicts: 7–8x on
  small dispatch-bound graphs; 1.0–1.3x parity cluster on bandwidth/libm-
  bound (hier_2pl 1.00, lsat 1.06, low_dim 1.01, kronecker 0.99, arma11
  0.97, diamonds 0.92); wins in between (pilots 2.87x, kidscore 2.78x,
  radon_var_slope 1.88x, radon_pp 1.58x, bym2 1.28x).
- Rejects: dogs_hierarchical (BERNOULLI_LPMF splits the only carveable
  pair), wells (entire graph = one BERNOULLI_LOGIT_GLM_LPMF op).
- lotka_volterra: carve OK, verify CRASH (rc 134) — nan ODE solutions at
  seeded N(0,1) points hit the interpreted LOGNORMAL domain check.
  Model-level robustness issue, not emitter; documented not retried.
- Blocker histogram (top): CONSTRAIN_LU 5 models, SET_INDEX/SET_SLICE_
  INPLACE family (228 ops in arma11 alone!), ISLAND 3, SUM_VEC 3,
  CHECK_LOWER 2, POW 2, EXPV 2, DIV 2, BETA 2, LOGNORMAL 2; 1-model tail
  incl. ODE, GP_EXP_QUAD_COV, CHOLESKY, EIGEN*_SYM (kronecker), GLM ops.
- Cold clang scales with region count: arma11 201 regions → 26.6 s cold
  (cached ≈0) — per-region file split + parallel clang is the fix.

Data-driven attack order (for F-7): (1) SET_*_INPLACE + CONSTRAIN_LU
(coverage; converts rejects, lifts time-series), (2) T2 vectorized libm
(F-5, in flight — the parity cluster holds the largest µs mass),
(3) BERNOULLI_LPMF + BERNOULLI_LOGIT_GLM_LPMF (unblocks dogs/wells;
kidscore/pilots-class wins suggest 2–4x available there). Also needed
before ODE models can be graded: nan-robust verification points (verify
at warmup-region thetas, not raw N(0,1)) — pre-register any protocol
change, do not quietly alter the seed-point methodology.

### F-7 queued (behind F-4b — same file), F-8 queued (capstone)

- F-7 (LAUNCHED 2026-08-26, branch fortk/t2-coverage off b7a3fd5, after
  F-4b's direct-path commit freed regions.cpp; F-4b's census still running
  read-only — timing hygiene applies):
  (1) T2 integration — vendor bench/fortk_t2/vecmath into the fork tool;
  emitter's transcendental paths (bernoulli_logit vector first) emit
  vectorized calls preserving cutoff/branch semantics. GATE: hier_2pl
  fused-exec >= 1.8x vs unfused (F-5 hand shows 192 µs possible; emitter
  target <= 263 µs vs 474), verify 64 pts 1e-9 unchanged + F-4 sampling
  smoke re-passed (3 seeds, 0 divergences).
  (2) Coverage opcodes: SET_INDEX/SET_SLICE(_INPLACE) (aliasing semantics
  from inplace.cpp + island snapshot doctrine), CONSTRAIN_LU, BETA? no —
  BERNOULLI_LPMF + BERNOULLI_LOGIT_GLM_LPMF. GATE: dogs + wells convert
  (carve + verify PASS); arma11 >= 1.1x (census 0.97x) + cold compile
  < 8 s via per-region .c + parallel clang (<=4 jobs).
  (3) Re-run affected census rows; table updated honestly.
- F-8 (capstone, after F-5/F-4b/F-7): end-to-end north-star table per
  PITCH methodology — wall-clock to reliable posterior + ESS_bulk/sec on
  the CORE_SET × {cmdstan, stanli unfused, stanli fused} × 4 chains ×
  1000+1000, 3 reps, medians. The lane's headline number.

### F-5 VERDICT (2026-08-26; full log logs/fortk-f5.md; artifacts bench/fortk_t2/)

ALL THREE PRE-REGISTERED GATES PASS. T2 tier validated: agent-authored
AVX2 transcendental kernels, <2 ulp, beating/competing with glibc's own
vectorized libm.

| kernel | max err vs mpmath | ns/elem scalar/F-5/libmvec | vs scalar |
|---|---|---|---|
| vexp_pd | 0.82 ulp (94.7% bit-equal to CR) | 4.09 / 1.45 / 1.70 | **2.82x** — BEATS glibc _ZGVcN4v_exp |
| vlog1p_pd | 1.87 ulp (tiny-arg <=1e-18: 0.0 ulp) | 5.65 / 3.21 / 2.99 | 1.76x (7-12% behind libmvec: price of exact-residual reduction) |

hier_2pl_vec (F-2b's hand-fused C, obs loop vectorized; cutoff-20 branch
blend replicating Stan's saturated-tail semantics): verification logp rel
6.10e-15, grad rel-L2 7.67e-16 — passes F-5's 1e-9 floor AND the original
F-2b 1e-12 gate. Timing (C-loop, fair malloc env, 3 reps, spread 0.5%):
**191.9 µs/call = 2.243x vs 430.4 baseline** (same-session re-measure of
original 442.9, baseline reproduces; bridgestan 649.5 → 3.38x). Win bar
(<=366 µs) cleared 1.9x over. Attribution: obs loop 21.4 → 8.3 ns/obs
(vector pass ~1.6; residual 6.7 = scalar gather/accumulate passes —
gather fusion est. ~120-140 µs/call, logged follow-up).

Debug notes for the record (all caught by gates/reference signatures):
exp overflow boundary ulp-bracketing (strict > at 709.78...); atanh |s|
bound asymmetric on negative x; u=1+x exact-residual reduction below
|x|>0.01 cut 2 divs/vector (log1p 1.34x FAIL → 1.76x PASS — the gate
forcing the better algorithm); exponent-surgery off-by-1023 and
off-by-ln2 bookkeeping bugs; nth<20 written for the low-tail mask
(should be <-20) — verify gate caught on first build.

IMPLICATION: hier_2pl's F-4 0.99x parity is now understood as SCALAR-libm
parity; with T2 kernels in the emitter's transcendental paths the target
becomes >=2x vs unfused executor. Integration queued as F-7 scope.

### F-8 pre-registered BEFORE running (pulled forward at user request: "Can we get ESS/s numbers?")

North-star campaign per PITCH methodology. Arms: (A) CmdStan default NUTS
(cmdstanpy; external/cmdstan), (B) stanli UNFUSED (build-rel/stanli_run +
libstanli.so @ 13:58 vintage = pre-inert-opcode = behaviorally pristine),
(C) stanli FUSED via fortk_t1r pinned at b7a3fd5 (clean worktree build at
/tmp/stanli-b7a3fd5, deps symlinked — the live build-rel/fortk_t1r is F-7
work-in-progress and MUST NOT be measured).

- PHASE 1 (now, small/dispatch-bound class): eight_schools_noncentered,
  eight_schools_centered, blr, pilots, kidscore_momiq,
  logmesquite_logvash. PHASE 2 (after F-7 lands, with T2): radon_pp,
  radon_var_slope, bym2, hier_2pl, lsat, diamonds, arma11.
- Protocol: 4 chains x 1000 warmup + 1000 draws, default NUTS; seeds
  20260826+1000*rep+c; 3 reps, MEDIAN per metric; ARMS INTERLEAVED within
  each rep (shared load conditions); load + concurrent-agent state
  recorded per rep (F-7 builds may run concurrently on this 24-core box —
  per-process caps stay <=4 jobs; note in each rep's header; reps with
  load spikes flagged, medians robust).
- Metrics per model x arm: total wall-clock to finish sampling, ESS_bulk/s
  (rank-normalized, their ESS tooling — posterior R or harness/compute_
  ess.py adapted to stanli CSV), divergences, max-treedepth hit rate.
  Aggregate: geomean ESS_bulk/s across models, per arm. Sanity: cross-arm
  ESS_bulk/chain comparability check (a sampler-speed win that silently
  loses ESS is NOT a win — report ESS/draw alongside).
- No gate on phase 1 (measurement); the deliverable is the table + honest
  read. Expected from priors: fused wins big on wall and ESS/s for
  dispatch-bound class; sampler bookkeeping share visible on esnc-class
  (F-4b census context).

### F-4b VERDICT (2026-08-26; log logs/fortk-f4b.md; commits b7a3fd5 + 0243aad on fortk/t1-regions; suite 63/63)

Item (i) direct path — BOTH GATES PASS: esnc direct 20.1 ns vs F-3 ref
20.5 ns SAME-LOOP (ratio 0.977; all sets 0.98-1.04) — ABI overhead
recovered; verification identical to fused-executor gate (esnc bitwise).
Ladder on esnc: direct 20.1 < region fns 25.5 (+5.4 two-call ABI) <
fused exec 34.8 < unfused 279.1 ns. INSTRUMENT NOTE: F-3's absolute
19.4 ns does not reproduce today for F-3's own binary (20.1-21.4 across
4 sets; a 17 GB python ingest job ran all session) — same-loop
interleaved ratios are the honest instrument from now on.

Item (ii) census (200+200, 3 reps, exact grad counters):
- FUSED gradients make esnc-class SAMPLER-BOUND: grad = 6.7% (nuts) /
  14% (walnuts) of wall via installed path, 3.9-8.9% at direct floor —
  85-95% is tree bookkeeping/adaptation/service. Even UNFUSED esnc nuts
  was ~70% bookkeeping — fusion sharpened the overhead, didn't create it.
- FUSION FLIPS THE SAMPLER RANKING: walnuts slower than nuts unfused on
  blr (19.9 vs 15.4 ms) but parity-or-better fused (7.7 vs 7.8); on esnc
  fused walnuts = 236k draws/s = 2.8x fused nuts (84k). Grad-shares
  through direct path: 9-89% depending on model/sampler.
- Consequence for the lane: kernel polish on small models is DEAD;
  sampler-loop work is the lever (that is the walnutpie lane's home
  turf — convergence point). F-8 amended below accordingly.

### F-8 AMENDMENT (pre-run, legitimate): add 4th arm

Arms now: (A) CmdStan nuts, (B) stanli unfused nuts, (C) stanli fused
nuts, (D) stanli fused WALNUTS (census says D is the esnc-class winner;
ESS/s + ESS/draw sanity will judge whether its different trajectory
structure pays statistically). Unfused walnuts arm omitted (census
already measured it slower; keeps the grid affordable).

### F-8 PHASE 1 VERDICT (2026-08-26; full log logs/fortk-f8.md; raw bench/fortk_f8/; pinned worktree @ d4801b5 = b7a3fd5 + measurement plumbing only, detached, never merge)

ESS_bulk/s (geomean per-param, pooled 4 chains, harness/ess.R), medians
of 3 reps; wall = max-chain sampler wall; ratio vs CmdStan:

| model | A cmdstan | B unfused | C fused nuts | D fused walnuts |
|---|---|---|---|---|
| esnc | 141,603 | 135,032 (0.95x) | 329,847 (2.33x) | **696,974 (4.92x)** |
| esc | 3,709 | 17,436 (4.70x) | 19,213 (5.18x) | 24,269 (6.54x) |
| blr | 21,983 | 33,006 (1.50x) | 60,787 (2.77x) | 176 NON-CONV |
| pilots | 32 | 69 (2.2x) | 96 (3.0x) | 565* stuck (*noise) |
| kidscore | 3,490 | 5,226 (1.50x) | 13,177 (3.78x) | 46 NON-CONV |
| logmesq | 9,133 | 11,751 (1.29x) | 23,634 (2.59x) | 24,879 (2.72x) |
| GEOMEAN | 1.0x | **1.74x** | **3.15x** | 0.74x |

ESS_bulk/draw sanity: A 0.169, B 0.258, C 0.238, D 0.022. Divergences:
esc A 43/1k vs B/C 14 (CmdStan mixes centered 8-schools WORSE —
adaptation-internals difference, real); pilots hard for everyone
(139-180/1k, 310-653 td-hits/4k); D reports no divergence diagnostics.

READ: (1) C (fused nuts) is the phase-1 winner EVERYWHERE: 2.3-3.8x
CmdStan ESS/s on all well-behaved models at ESS/draw PARITY-OR-BETTER —
speed without statistical loss. (2) B alone already beats CmdStan
1.5-1.7x — the sampler loop matters as much as kernels. (3) F-6's 4-8x
kernel ratios dilute to ~1.8x incremental at sampling level — F-4b's
85-95% bookkeeping share confirmed quantitatively. (4) D (fused
walnuts) does NOT hold its census promise as a default: where it
converges it is spectacular (esnc 4.92x, esc 6.54x) but it silently
sticks on 3/6 models (blr chains parked at sigma 4.8/2.2/1.7/0.7, rhat
4.3, no diagnostics) — exactly what the ESS/draw gate exists to catch.
Walnuts' Adam warmup is the suspect → walnutpie-lane work, not fortk.
(5) walnuts wasn't CLI-reachable at pinned b7a3fd5; agent added
--sampler walnuts to the pinned tool driving the census's runtime API
(plumbing commit, documented).

Self-corrections during campaign (recorded): tau-stale-slot bug in the
plumbing caught by row-identity vs stanli_run BEFORE campaign; agent's
own chain-file collision caught by duplicate-chain check, ESS recomputed
from raw (walls/div/td unaffected).

### F-9 pre-registered BEFORE running (walnutpie's pf-init idea vs the WALNUTS stuck-chains — user request 2026-08-26)

Hypothesis: D-arm (fused walnuts) non-convergence on blr/kidscore is an
INIT problem (chains parked at sigma 4.8/2.2/1.7/0.7 = stuck near bad
inits with Adam-adapted steps), fixable by the walnutpie lane's standard
Pathfinder-init protocol (harness/run_pathfinder.py): 1 pathfinder run
(num_paths=4) over the model, PSIS draws, chain c init = rep/chain-
seeded random draw; WALL INCLUDES PATHFINDER TIME (their convention).

Arms (phase 1b, same 6 models, 3 reps, F-8 protocol otherwise):
- C_pf: fused NUTS + pf init (matched-init control — pf helps any
  sampler; the walnuts-vs-nuts comparison is D_pf vs C_pf, NOT D_pf vs C)
- D_pf: fused WALNUTS + pf init
- A_pf: CmdStan NUTS + pf init (does pf-init alone fix blr-class on the
  reference arm? completes attribution) — crib cmdstan wiring from
  harness/run_pathfinder.py
- Existing A/B/C/D rows are the reference; no re-runs of those.

Implementation: pinned worktree only (detached; commits never merged —
port to the real branch only if it works): tool gains --init pf using
stanli's own pathfinder (runtime/src/pathfinder.cpp) over the FUSED
executor, PSIS draws per stan::services::pathfinder, per-chain init
seeded per protocol.

GATES: (a) stuck recovery — D_pf on blr + kidscore: all-chain R-hat <
1.01 AND ESS_bulk/draw >= 0.1 (D's failures were 0.01-0.02); (b) no
regression — D_pf on esnc/esc/logmesq within noise of D or better; C_pf
no worse than C; (c) headline (no gate, measurement): D_pf vs C_pf
geomean ESS/s; also D_pf vs C (the practical "best default" question:
is pf-init walnuts the new best arm?). Failure of (a) = the stuck issue
is adaptation-not-init → recorded as walnutpie-lane evidence either way.

### F-7 VERDICT (2026-08-26; full log logs/fortk-f7.md; branch fortk/t2-coverage in worktree external/stanli-f7, commits 0af980c/a6e537d/f8a1f12, NOT pushed; ctest 63/63)

ALL GATES PASS.

(1) T2 integration: kernels vendored to tools/fortk/vecmath.{h,c}, ulp
re-verified from the fork (vexp 0.8165, vlog1p 1.8721 — bit-identical to
F-5's numbers). hier_2pl fused-exec: 474.0 → **215.1 µs = 2.203x**
(target <=263 cleared by 48 µs; hand reference 191.9; the F-5 gather-
fusion follow-up landed as obs-chain fusion: 313→225 µs stage). Verify
1.042e-15/1.221e-14 unchanged; sampling smoke 0 divergences both arms.
Vectorized: bernoulli_logit vector path (cutoff-20 blends with Stan's
value/partial boundary asymmetry), obs-chain fusion, GLM, CONSTRAIN_LOWER
exp. Deliberately NOT vectorized (recorded): cauchy/student_t log1p
loops (overhead/lgamma-bound), bernoulli_lpmf (no log kernel), gathers.

(2) Coverage: SET_INDEX/SET_SLICE(_INPLACE), CONSTRAIN_LU, BERNouLLI_LPMF,
BERNOULLI_LOGIT_GLM_LPMF. Carve 19/21 → **21/21**; accept 18/21 →
**20/21** (lotka nan-ODE unchanged). dogs REJECT→PASS (bitwise!),
wells REJECT→PASS (1 region, 100% ops, direct path too). arma11: 201→1
region over ALL 806 ops incl. the 228-op SET_INDEX chain = **5.47x**
(6.66→1.22 µs; was 0.97x), cold compile 26.6→4.37 s (parallel clang).
esnc/blr/diamonds no regression (8.15x/3.85x/0.85x).

(3) Updated census (changed rows): hier_2pl 1.00→**2.20**, arma11
0.97→**5.47**, lsat 1.06→**1.84**, pilots 2.87→**3.63**, wells→1.46,
dogs→0.97; bym2/accel/garch/kronecker/low_dim ~unchanged. Recomputed
corpus aggregate (20 accepted models): geomean ≈ **2.25x** over the
unfused executor (F-6: 1.81x over 18), median ≈ 1.4x. The bimodality is
softening: the parity cluster is being eaten by T2 (hier_2pl) and
coverage fusion (arma11); what remains is bandwidth-bound (diamonds) and
linalg-bound (kronecker).

Engineering lessons (emitter rules): (i) the inplace-aliasing trap lived
in the CARVER not the kernel — repokes on chain bases legal, pokes on
snapshotted live_ins refused, a poke must never classify its base
internal; (ii) C-precedence leakage — composite accessors like
"adj[x] + 0.0" inlined into multiplications silently degrade jacobian
terms (dogs grads 1.2e-2 off with logp EXACT) — parenthesize at
construction; (iii) saturated-tail boundary asymmetry (strict < -20 vs
>= -20 between value and partial paths) re-checked at every emitter.

QUEUE: F-8 phase 2 (mid/parity class on the F-7 branch) launches when
F-9's campaign finishes (core/timing contention); F-10 sampler-loop
package (2a scratch-hoist + W-20 + mallopt) waits for F-9 because
deps/stan is symlinked into its pinned worktree.

### F-11 DESIGN STUDY (2026-08-26; doc logs/fortk-f11-design.md, 569 lines, read-only)

Inventory + three designs + sequencing + don't-do register, all with
file:line anchors and pre-registration-ready gates:
- Inventory: NUTS delta/max_depth/warmup runtime-configurable end-to-end;
  DA gamma/kappa/t0 + window constants (nuts.cpp:62) + Stan's variance
  regularization (vendored var_adaptation.hpp:27-28) are code-change.
  Vendored walnutpie is upstream-shaped (no batching/chopping/shrink/
  pf-init; Adam lr .05 / β .8/.9, discount 1-1/(4+t) at
  adaptive_walnuts.hpp:76); `mass_additive_smoothing` is DEAD config
  (never consumed) — noted for the walnutpie lane.
- Design 1: LW-style shrinkage of late-window NUTS variance toward
  trace-preserving scaled identity (vendored var_adaptation.hpp).
  Motivation nutpie ~2x (flagged unproven locally); realistic prior =
  Fisher-HMC's 1.3x diag median. Gates: lw_off arm BITWISE; active arms
  no divergence increase (funnel sentinel), geo ESS/s >= 1.0x and
  >= 1.10x on the draw-poor subclass (kronecker/radon).
- Design 2: walnutpie MassEstimator upgrade — window chopping (W-6: blr
  201->401 ESS), robust/Winsorized floored Var_score (W-4 early-drift
  degeneracy), optional batch50 (W-1: 17->9 rhat-bad) + kappa=5 shrink.
  CONDITIONED ON F-9: if pf-init fixes stuck chains, this polishes
  ESS/grad; else it inherits the stuck-recovery gate. Honest bound: W-2
  showed mass patches alone moved nothing — bundle only pieces with
  positive isolated records.
- Design 3: zero-code delta {0.5,.7,.8,.9,.95} x depth {8,10,12} sweep
  on fused NUTS + CmdStan delta-grid interaction control. Hypothesis:
  cheap fused gradients shift the optimum toward higher accept targets
  (F-4b cost flip); kronecker's 99.5% td-hits motivate the depth leg.
  Adoption rule pre-stated: >=3% geo ESS/s, no model >10% regression,
  divergences not worse, td-hits <=5%.
- Sequencing: Design 3 first (no code, baseline), Design 2 parallel with
  F-10 (no deps/stan conflict), Design 1 last behind F-10. Final
  combined capstone arm with multiplicative-attribution check.
- Don't-do register: Aurora/Muon (settled inapplicable to scalar/diag),
  basis extraction (W-19), low-rank default, dense metric at d~7000,
  warmup-budget for stuck chains, funnel=mode-lock, bit-identity for
  estimator changes.

### F-9 VERDICT (2026-08-26; full log logs/fortk-f9.md; raw bench/fortk_f9/; pinned worktree commits d4801b5 + 833d8de, detached)

Hypothesis HALF-RIGHT — clean three-way split of the D-arm failures:
- blr: GATE (a) PASS — pure init failure. Parked sigma 4.8/2.2/1.7/0.7
  -> all 4 chains one basin sigma 1.0339±0.0743 (A_pf: 1.0350±0.0734);
  rhat 4.32 -> 1.006; ESS/draw 0.003 -> 0.149.
- kidscore: GATE (a) FAIL (marginal) — basin FIXED (per-chain beta.1
  25.2-26.2, sigma 18.25-18.35 = correct basin) but within-basin mixing
  still slow (rhat 1.014, ESS/draw 0.093; ~40x rescue from 0.002).
  Residual = Adam warmup/step adaptation -> WALNUTPIE-LANE EVIDENCE.
- pilots: multimodality (4 chains in 4 real basins, rhat 2.59) — init
  cannot fix between-basin mixing; correctly NOT claimed as a win.

Gate (b) partial FAIL: D_pf esnc 0.48x D's median (pf wall + typical-set
start; ESS/draw parity 0.762 vs 0.812); esc/logmesq within noise. C_pf
WORSE than C on 4/6 (0.71-0.78x) — pf-init buys fused NUTS NOTHING end-
to-end (wall cost only; ESS/draw parity-or-better everywhere).

Headline: D_pf vs C_pf = 1.16x; D_pf vs C = 1.00x; D_pf lifts D from
0.74x -> 3.16x CmdStan (2.94x vs A_pf). BEST DEFAULT UNCHANGED: arm C
(fused nuts). The remaining walnuts lever is warmup/adaptation
(F-11 Design 2's territory), with F-9's numbers as its evidence base.

Bonus findings: pf-init alone helps CmdSTAN (A_pf 1.07x, pilots rhat
1.315->1.049, esc div 43->20.5); pf wall 3-40ms (negligible except
pilots); pf cross-validated vs CmdStan (same 2/4 paths fail on blr,
PSIS sigma marginal matches to 3rd decimal). Implementation:
stanli::run_pathfinder_multi (4 single paths over the fused executor,
pooled PSIS, 1000 resampled draws) + --init pf/--pf-seed; default path
BYTE-IDENTICAL without the flag (verified vs F-8 snapshot; one
self-caught regression fixed pre-campaign).

### F-12 (consolidation, pre-registered): cherry-pick the pinned worktree's load-bearing commits onto fortk/t2-coverage

d4801b5 (seeds/chain-id/CSV output/--sampler/SAMPLE_WALL) + 833d8de
(pf-init plumbing + run_pathfinder_multi) were declared never-merge when
they were measurement pins; they are now load-bearing tooling. Cherry-
pick onto fortk/t2-coverage (worktree external/stanli-f7), resolve
(regions.cpp heavily evolved on both sides), GATE: ctest 63/63, esnc
verify PASS, arma11 + hier_2pl quick re-verify PASS, one --sample smoke
byte-comparable to the pinned binary on default path. The pinned
worktree /tmp/stanli-b7a3fd5 stays untouched as the F-8/F-9 measurement
pin. THEN: F-10 (sampler-loop package: 2a scratch-hoist + W-20 endpoint
threading + mallopt, as an in-fork carried patch on the vendored
deps/stan base_nuts.hpp, bit-identity gated per the 2a PLAN) lands on
the consolidated branch; campaigns (F-8 phase 2 + F-11.3 delta sweep)
run AFTER F-10 so they measure the near-final stack in one build round.

### F-12 VERDICT (2026-08-26; log logs/fortk-f12.md; branch fortk/t2-coverage @ 9b2bf80)

ALL 5 GATES PASS, nothing dropped. Picks of d4801b5 + 833d8de auto-
merged CLEAN (pre-flight showed file-region disjointness: F-7's hunks
live in regions.cpp base 198-2140, pinned side in includes/CLI/sample
driver 2479+ and runtime/); coexistence verified semantically, not
assumed: F-7 verify numbers reproduce bit-for-bit (esnc bitwise + DIRECT
bitwise; arma11 7.8e-16; hier_2pl 1.042e-15; wells 1.6e-15), esnc
--sample CSV BYTE-IDENTICAL vs the frozen pin, --init pf smoke
reproduces F-9's blr result (4 chains one basin, PF signature identical,
pf_draws bit-identical). ctest 63/63. The consolidated branch is the
single trunk for F-10 onward. Pinned worktree untouched.

### F-10 pre-registered BEFORE building (sampler-loop package) + F-11.2 (walnuts adaptation) — parallel, file-disjoint

F-10 (worktree external/stanli-f7 @ 9b2bf80):
- (i) 2a scratch-hoist on the VENDORED deps/stan base_nuts.hpp per
  patches/stan-2a2-scratch-hoist-PLAN.md (hunks written for d13c50c0f;
  vendored is c96d0411 — adapt, do not assume). Carried in-fork as a
  patch file + deps/fetch.sh apply hook (deps/fetch.sh is tracked).
- (ii) W-20 endpoint-gradient reuse via a 1-ENTRY CACHE at the
  ExecutorModel adapter seam (key: theta bytes; hit => return the
  identical cached logp/grad doubles) — less invasive than threading
  through base_nuts recursion; bit-identity by construction.
- (iii) mallopt(M_MMAP_THRESHOLD/M_TRIM_THRESHOLD) in the tool's
  sampling driver (F-2b finding).
- GATES: (a) draws BYTE-IDENTICAL stock vs patched on esnc/blr/hier_2pl
  --sample; (b) grad-counter drop consistent with 1/transition removal
  (exact counter); (c) perf: nuts-loop walls on esnc/blr (census-style)
  >= 1.1x target, informative-if-miss with breakdown; (d) ctest 63/63.
  Apply the deps/stan patch ATOMICALLY at session start, then build —
  other lanes' worktrees symlink deps.

F-11.2 (fresh worktree off 9b2bf80; vendored walnutpie is TRACKED in
runtime/third_party/ — no deps conflict): MassEstimator + warmup upgrade
per F-11 Design 2 — window chopping (W-6: blr 201->401 ESS), robust/
Winsorized floored Var_score (W-4 early-drift degeneracy), batch50
optional (W-1), kappa=5 shrink; step-loop options per
research_optimizer_sota; wire or remove the DEAD mass_additive_smoothing
config. GATES (inherited stuck-recovery + no-regression, statistical):
kidscore walnuts+pf: all-chain R-hat < 1.01 AND ESS/draw >= 0.1 (F-9's
residual); blr/esnc/esc/logmesq walnuts arms no regression (3 reps);
builds coordinated with F-10's atomic deps window (code first, build
after F-10's log shows the patch landed).

### F-13 VERDICT (2026-08-26; log logs/fortk-f13.md)

Toolchain BUILT in 13/45 min (opam 2.5.2, ocaml 5.5.0 switch f13, dune
6.1s build; stanc3 checkout untouched, binary in _build). Fusion FIRES:
kronecker tmir 4 eigen FunApps -> 2 eigendecompose_sym + 4 projections =
4 solver-runs/grad -> 2. BUT the fused arm cannot run through stanli:
mir_reader lacks STuple/TupleProjection grammar, lower.cpp lacks
eigendecompose_sym, optable lacks the opcode (CompileError on any
fusable model). Stock arm: 64-pt gate bitwise PASS (0.0/0.0, matches
F-6), fused-exec 287.2 vs unfused 284.5 µs = 0.991 (parity, consistent).
Profile: eigh 51.3% of op time; EIGENVALUES fwd 21.2% of grad is PURE
DUPLICATION the fused op deletes; projected fused arm ~224-227 µs =
~1.27x (PROJECTION, labeled). Verdict vs >1.15x bar: projected-pass,
pending interpreter support. Adoption path (not implemented): mir_reader
tuple parsing + OP_EIGENDECOMPOSE_SYM kernel (one solver, vectors to
scratch, combined pullback V(ḡ_w + f∘(VᵀḡV))Vᵀ — the PR's bit-identity
argument carries structurally).

### F-13.2 pre-registered (eigh kernel adoption) + F-14 pre-registered (batch-throughput) — both branch off 9b2bf80, file-disjoint from F-10/F-11.2

F-13.2: add STuple/TupleProjection parsing to mir_reader.cpp +
eigendecompose_sym lowering + OP_EIGENDECOMPOSE_SYM native kernel
(follow arch map §8a recipe + the user's stanc3 PR math; bit-identity
argument: same solver, combined pullback accumulates into the same
zero-initialized operand adjoint). GATES: kronecker 64-pt verification
BITWISE vs the two-call stock arm; µs/call <= 240 (projected 224-227);
ctest green; fusable-model corpus spot-checks (the two-call idiom in
non-adjacent form must still lower to stock — no behavior change where
the pass does not fire). Uses the F-13-built stanc (external/stanc3/
_build/.../stanc.exe) via staging cwd.

F-14 (the simulation-study workload metric — fits/hour including
compile): arms = (a) cmdstanpy per-fit subprocess loop, (b) stanli
python binding in-process loop (unfused), (c) fortk_t1r CLI per-fit
(fused, process spawn per fit), (d) fused in-process multi-seed (small
tool addition: --seeds N mode looping sample() in-process, reusing the
loaded executor + cache). Models: blr + esnc-class; 200 fits/arm
(3 reps of smaller batches if time demands); metrics: fits/hour, median
fit wall, compile-share of fit wall. GATE: none (measurement) — but the
expected-order prior (b > a, d > c, d >> a) is pre-stated; a miss of the
ORDER is a finding. Worktree off 9b2bf80 (stanli-f14), build its own.

### F-10 VERDICT (2026-08-26; log logs/fortk-f10.md; trunk commits e750504 + 1bfcbb5 on fortk/t2-coverage)

deps/stan patch applied ATOMICALLY at session start (20:22; exactly
M base_nuts.hpp, +63/-13, reverse-check clean) + idempotent fetch.sh
hook (patch file patches/deps-stan/0001-base_nuts-scratch-hoist.patch;
one hook bug caught: deps/stan is a symlink — anchor at script $PWD).
Vendored c96d0411 structurally identical to the plan's d13c50c0f text.

GATES: (a) PASS — draws BYTE-IDENTICAL stock vs patched on esnc/blr/
hier_2pl; cache-on == cache-off; pf smoke reproduces F-9 exactly.
(b) HONEST FAIL of the W-20 expectation — arithmetic exact (drop ==
hits everywhere; cache-off = 4164 evals = F-4b census exactly) but hits
= 61/400, not 400: stan NUTS's last eval per transition is the FAR-END
LEAF, not the carried state, so a 1-entry cache only catches adjacent
duplicates (depth-1 transitions). The redundancy is real (~400 start
re-evals/run = 9.7% of evals) but full capture needs endpoint threading
INSIDE base_nuts (never-touch register) — pre-registered follow-up, not
done. walnutpie's dups==iters+1 pattern does NOT transfer (its
transitions evaluate endpoints last) — cross-lane lesson recorded.
(c) TARGET >= 1.1x MET — esnc 1.167x (2.415->2.070 ms), blr 1.270x
(8.079->6.362 ms), hier_2pl 0.985x parity (92% grad share, as
predicted). Attribution: scratch-hoist is effectively the WHOLE win
(~0.35 ms off 2.27 ms bookkeeping on esnc = ~15%; ~1.4 ns per removed
alloc/free pair, ~252k pairs); mallopt NEUTRAL (stanli's arenas don't
hit F-2b's glibc pathology — another cross-lane non-transfer); cache
~0 by arithmetic.
(d) ctest 63/63. NOTE: one concurrent-lane OOM kill during the session
(4 agents building) — agent dropped to -j2; watch memory for the grand
campaign window.

### F-11.2 VERDICT (2026-08-26; log logs/fortk-f112.md; branch fortk/f112-walnuts, commits 316afe2/7d7c9da/58ec219, ctest 64/64)

GATE (a) STUCK RECOVERY — PASS: kidscore walnuts+pf rhat 1.014 -> 1.008,
ESS/draw 0.093 -> 0.108 with --w-batch 10 (also b25 and chop+b25 pass;
D0 arm reproduces F-9 exactly = bridge validated).
GATE (b) NO REGRESSION — PARTIAL (wall-only on 2/4): statistical quality
better-or-equal on ALL 4 (ESS/draw: esnc +, logmesq 0.106->0.133, blr
0.149->0.210, esc in band; rhat better-or-equal; no new divergences);
ESS/s: esnc 1.253x BETTER, esc 0.775x (in F-9 noise band), logmesq
0.834x (below band), blr 0.403x (FAIL). The wall shortfall is pure
step-scale: batched Adam CONVERGES to the true E[alpha]=0.8 root
(frozen step 0.057 vs stock 0.22) => ~3.5x more micro-steps/iter.

THE TRANSFERABLE FINDING (walnutpie lane): walnutpie's 0.8 accept
target + noisy t^-0.5 Adam are a COUPLED CALIBRATION — the noise was
load-bearing. The stock loop never converges (lr ~1e-3 at freeze); its
accidentally-large frozen step (0.22) was GOOD (cheap trajectories);
denoising lands 4x lower steps: ESS/draw +7..41% at 1.5-3.5x wall. Any
walnutpie adapter change needs a JOINT (target, step-scale) re-tune.
Which pieces mattered: step-loop mean-batching W=10..25 NECESSARY (fixed
both gate metrics); ALL mass-side Design-2 pieces moved nothing or hurt
(chop50 regressed blr ESS/draw to 0.062; robust clip/floor hurt
kidscore; kappa=5 shrink hurt badly 0.058/rhat 1.035; W-6's chop-win
does NOT transfer to this stack). Rejected empirically: accept 0.6/0.7
rescue, decay 0.75 (freezes at step 0.001-0.002). Gates (a)/(b) pull
against each other through one shared quantity (frozen step scale); no
licensed-knob config dominates both — REPORTED, not tuned past.

Status: kidscore fixed; walnuts-as-default still trades wall for
quality — best default remains fused-NUTS+F-10; --w-batch 10 is the
carried config (ESS-limited workflows may prefer it). Joint re-tune
(target,step) with a step-scale Prior is the walnutpie-lane follow-up.

### F-13.2 VERDICT (2026-08-26; log logs/fortk-f132.md; branch fortk/f132-eigh, commits 53db89a/844ad46/08db4b6; ctest 63/63)

ALL 5 GATES PASS. kronecker 64-pt BITWISE (exactly 0.0/0.0) vs the stock
two-call arm, proven two ways: cross-stanc AND same-stanc tmir surgery
(one md5 across all five dump variants). µs/call 232.3 (region arm
229.2) vs stock 287.7 = **1.239x** (F-13 projected 1.27; realized under
residual sibling load). Non-fusion neutrality verified (reversed-order/
different-args/non-adjacent/GQ-nested variants lower to stock ops,
verify 2.1e-15). dump_ops: 2 EIGENDECOMPOSE_SYM, 0 stock eigh ops.
Implementation: reader tuple grammar (TupleProjection 1-based, STuple
sized types, TupleAD decls; everything else tuple-shaped stays a LOUD
error), lowering to one op (out=vectors, out2=values, projections alias
with no copy op), kernel = one solver + combined pullback transcribed
in stock order (values pullback first); executor gained out2_adj_vec.
The user's stanc3 eigh-fusion PR is now realized end-to-end in the fork.
FINDING (outside gates, documented not fixed): CSE subsumption gap —
same-argument fused-pair + stray unfused eigvecs reassociates the
operand adjoint at last-ulp (<=1e-14 rel, lp identical, gates pass);
kronecker-class unaffected (byte-identical). Fix = two cse subsumption
rules; declined as gold-plating. earlyoom SIGTERM'd a -j4 build again
(density shards, 4 sibling agents) — -j2 fallback; grand campaign will
serialize heavy builds.

### F-15 pre-registered (consolidation #2): merge f112 + f132 into trunk; grand campaign follows F-14

Merge fortk/f112-walnuts + fortk/f132-eigh into fortk/t2-coverage
(trunk, now carries F-10) in external/stanli-f7. GATES: (a) ctest 64/64
(63 + test_walnuts_adapt + test_eigen — suite count grows); (b) verify
spot-checks all-green: esnc bitwise, hier_2pl, arma11, wells, kronecker
BITWISE-fused arm; (c) --sample 200 200 esnc + blr byte-identical vs
the pre-merge trunk binary; (d) walnuts D0 (all knobs off) arm bitwise
vs 9b2bf80 (F-11.2 proved this pre-merge; must survive the merge); (e)
--w-batch 10 kidscore quick-check reproduces rhat < 1.01. Then the
GRAND CAMPAIGN (F-16) launches only after F-14 lands + this merge:
F-8-phase-2 models on the merged stack, delta {0.5,.7,.8,.9,.95} x
depth {8,10,12} sweep on fused NUTS, arms A/B/C(trunk)/D(stock walnuts)
/D_b10, 3 reps medians, interleaved, heavy builds SERIALIZED (earlyoom
lesson). Multiplicative-attribution capstone last.

### F-14 VERDICT (2026-08-26; log logs/fortk-f14.md; branch fortk/f14-batch @ c37b623 = 9b2bf80 + flag-gated --fits N; ctest 63/63; raw bench/fortk_f14/)

Fits/hour INCLUDING compile strategy (200 fits/batch, 4 chains × 200+200,
4-way parallel/fit, medians of 3 quiet reps; loaded-box bias 30-45%
measured, quiet numbers used):

| arm | blr | esnc |
|---|---|---|
| a1 cmdstanpy compile-once (steady) | 117,386 | 166,707 |
| a2 cmdstanpy recompile/fit (sim-study reality) | 458 | 445 |
| b stanli binding in-process (unfused) | 200,594 | 392,882 |
| c-cold fortk CLI/fit | 16,701 | 20,383 |
| c-warm fortk CLI/fit | 118,119 | 135,199 |
| d fortk --fits 200 in-process (fused) | **508,260** | **1,156,832** |

HEADLINE: d vs a2 = **1109x (blr) / 2598x (esnc)** — three orders of
magnitude over the recompile-per-fit reality simulation studies live in.
d vs a1 (their best case) = 4.3x / 6.9x. Order verdicts all HOLD.
Decompositions: a2 compile share 99.6+%; c-cold clang 86% (149-187 ms =
36-46x cheaper than a cmdstan recompile); c-warm stanc SUBPROCESS 20 ms
= the CLI bottleneck; d amortizes compile to 0.14-0.19 ms/fit.
Findings: (1) process shape > fusion at this fit size for the unfused
arms (b beats a1 1.7-2.4x unfused; fusion adds 2.5-2.9x on top) — the
"100x compile" pitch matters exactly as much as the gradient speed;
(2) a1 ~= c-warm (per-fit fortk spawn re-runs stanc+lower ~23 ms) — the
CLI win needs in-process (d) or an amortized pipeline; embedding stanc
(stanc_embed.o path) would kill the subprocess cost — noted future item;
(3) self-caught a2 aggregation bug fixed + re-measured; two OOM build
rounds (foreign builds) before -j1 — the earlyoom lesson stands.

### F-15 VERDICT (2026-08-26; log logs/fortk-f15.md; trunk fortk/t2-coverage @ f47f001)

ALL GATES PASS, nothing dropped, ZERO conflicts (regions.cpp zones
region-disjoint again). ctest 64/64; esnc bitwise+DIRECT; hier_2pl/
arma11/wells match recorded history exactly; kronecker via F-13 stanc
fully BITWISE with 2 EIGENDECOMPOSE_SYM (ops 221->94, regions->33);
esnc+blr --sample byte-identical vs premerge binary (GRAD_COUNTER =
F-10's exact 4079/61, 11418/62); walnuts D0 byte-identical (u and pf);
kidscore --w-batch 10 fix survives (rhat 1.0084, ESS/draw 0.133).
Trunk now carries: T1 regions + T2 kernels + coverage + direct path +
F-8/F-9 plumbing + pf-init + F-10 loop package + F-11.2 walnuts knobs
+ F-13.2 eigh. THE STACK IS WHOLE.

### F-16 pre-registered (GRAND CAMPAIGN — the day's capstone measurement)

Setup: merge fortk/f14-batch (--fits; default-off byte-identity already
proven) into trunk first, gate = ctest + esnc --sample byte-identical.
Then, all on the merged trunk binary, arms INTERLEAVED within reps,
3 reps medians, quiet-box rules, NO heavy concurrent builds:

- PHASE 2 models (8): radon_pp, radon_var_slope, bym2, hier_2pl, lsat,
  diamonds, arma11, kronecker_gp (kronecker via the F-13 fused-stanc
  staging; state its arm provenance).
- ARMS (5): A cmdstan nuts; B stanli unfused; C trunk fused nuts (the
  default champion); D trunk fused walnuts (default knobs); D_b10
  walnuts --w-batch 10 (the carried config). pf-init per F-9 protocol
  for D/D_b10 (their intended pairing).
- DELTA x DEPTH sweep (fused nuts, arm C base): delta {0.5,0.7,0.8,
  0.9,0.95} x depth {8,10,12} on the 6 phase-1 models + hier_2pl;
  adoption rule pre-stated (>=3% geo ESS/s, no model >10% regression,
  div not worse, td-hits <=5%); CmdStan delta-grid interaction control
  at delta {0.7,0.9} on 3 models.
- CAPSTONE ATTRIBUTION: per model, measured stacked gain (C vs A) vs
  the product of individually-measured layer gains (interpreter,
  fusion, T2, loop package); report synergy/cannibalization ratios.
  Deliverable: the final table + geomeans per arm + the attribution
  table + honest read. No gates — this is the measurement everything
  else was built for.

### LANE REDIRECT (user, 2026-08-26 evening): sampler-loop optimization now the priority

"Most time is now spent sampling — optimize that rather than squeezing
more ms out of the graph." Consistent with F-4b census (fused esnc-class
= 85-95% bookkeeping; F-10 bought only ~15% of it; ~1.9 ms/run
UNATTRIBUTED) and inverts for hier_2pl-class (92% gradient — emitter
work still pays there). Plan:
- F-17a (RUNNING, read-only while F-16 owns the box): static
  decomposition of one fused NUTS transition — allocation/copy/call-
  layer walk + hypothesis table for the unattributed ~4.75 µs/transition
  + four design mappings (endpoint threading; early-exit warmup with
  step-drift gate; post-hoist base_nuts surgery; lean walnutpie-style
  driver over ExecutorModel with explicit bit-identity accounting).
- F-17 (after F-16 frees the box): perf/callgrind decomposition per the
  F-17a measurement plan; gates from its pre-registration draft.
- F-18+: whichever levers F-17 confirms, in evidence order. Emitter-side
  work pauses except where hier_2pl-class gradients still dominate.

### F-17a VERDICT (2026-08-26; report logs/fortk-f17a.md; read-only)

KEY INSIGHT: the unattributed ~4.75 µs/transition (esnc, post-F-10) is
NOT tree bookkeeping — F-10 took that. It is the VAR-TAPE PRETENSE
around each gradient eval (H1, est. 2.3-4.5 µs of 4.75): between
base_hamiltonian::update_potential_gradient and ex_->gradient stan
builds a std::stringstream PER CALL (model/gradient.hpp:25, logger
overload, unconditional), constructs a var tape (10 arena varis + var
stack pushes + ops heap vector + precomputed_gradients vari + 11
virtual chain() calls + nested recover) = 250-450 ns wrapper around a
35 ns executor gradient, x10.2 evals/transition. The census's "6.7%
grad share" measured the executor floor; the wrapper was booked as
bookkeeping. Runner-up hypotheses: H2 Eigen dynamic momentum temps +
return-by-value dphi_dq/dtau_dp copies (0.6-1.5 µs); H3 residual
ps_point copies (0.3-0.6); H4 RNG 10 zigurat+13-23 mixmax (0.2-0.35);
H5 log_sum_exp chain (0.2-0.4).

MOST PROMISING LEVER (C.5, direct-double gradient seam):
update_potential_gradient/init are NON-VIRTUAL, statically dispatched
through the Hamiltonian template param — a stanli-side
diag_e_metric_direct shadowing them (raw-double ex_->gradient, same
negation/catch semantics) + a stanli-side copy of adapt_diag_e_nuts
deletes the entire wrapper with ZERO deps/stan logic change, ZERO RNG
change, byte-identity by F-10's own argument. Composes with endpoint
threading (C.1, +0.3-0.5 µs, no build_tree changes needed — carried
state only dies at the stan::mcmc::sample boundary). F-17 measurement
plan pre-designed: rdtsc 3-probe build (G1 >= 80% attribution),
callgrind 100 transitions, perf stat, then A/B lever builds with gates
G2 (byte-identical draws, esnc >= 1.3x), G3 (GRAD_COUNTER drop ==
transitions exactly, 4079 -> ~3679), G4 hoists, G5 statistical-only for
early-exit; hier_2pl = regression tripwire. Launches when F-16 frees
the box.

### F-16 VERDICT — THE CAPSTONE (2026-08-26/27 overnight; log logs/fortk-f16.md; raw bench/fortk_f16/; trunk @ 4690a00 = f47f001 + f14 merge 921a6fc + --delta/--max-depth flags 4690a00)

Phase-2 (8 models x 5 arms, 3 reps medians; ESS/s geomean vs CmdStan):
**A cmdstan 1.00x | B unfused 1.65x | C fused nuts 2.84x | D walnuts+pf
2.23x | D_b10 2.06x.** C best on 7/8 models, ESS/draw parity-or-better
on 7/8 (diamonds 0.80 vs 0.85 the exception). Headline cells: radon_pp
8.51x, hier_2pl 4.67x, arma11 4.05x (100k ESS/s). kronecker B==C draws
BIT-IDENTICAL through NUTS — the eigh fusion's bit-identity realized
end-to-end at the sampler level. f14 --fits merged (921a6fc, gates:
ctest 64/64, esnc byte-identical, GRAD_COUNTER 4079/61 = F-10/F-15).

ATTRIBUTION (multiplicative capstone): measured C/A 2.84x vs product
of individually-measured layers 2.88x = **0.99x — the stack composes,
no aggregate synergy or cannibalization**. Per-model 0.99-1.08x except
bym2 1.41x (stale F-6-vintage kernel baseline; F-7 ops postdate it),
arma11 0.58x / radon_vs 0.83x (dispatch-bound kernel census amortizes
at sampling level). Gaps honestly noted: loop gains only measured on
hier_2pl among the 8; sampling-level fusion (C/B) substituted from
kernel census where unmeasured — the 0.99x aggregate validates the
substitution.

DELTA SWEEP (depth-10 only; >5h fallback engaged — campaign alone 4.4h):
**NO ADOPTION — delta stays 0.8.** "Cheap gradients shift the optimum
toward higher accept targets" REFUTED (d0.9 = 0.85x, d0.95 = 0.52x;
d0.5 explodes divergences: esnc 205/1k). d0.7 clears the geo bar but
fails 3 of 4 adoption criteria (logmesq 0.73x, div worse, pilots td
9.8%). CmdStan control shows the same shape — no fusion x delta
interaction. Depth-12 leg UNMEASURED (the one cell this session owes;
kronecker's 3981/4000 td-hits the standing signal).

Honest cells: diamonds 0.77x (bandwidth-bound; fusion taxes; all arms
~parity — cross-pass fusion the only lever). Walnuts NOT default: wins
radon_pp (7.90x) / arma11 (5.21x) / kronecker wall (60x) but fails
bym2+diamonds+kronecker R-hat silently even with pf-init; b10 recovers
bym2 borderline, loses kronecker — residual = F-11.2's coupled
target/step calibration (walnutpie lane). NEW SIGNAL: arma11 rep0
seed-specific stuck chain in BOTH stanli arms where CmdStan recovers —
far-init recovery difference, queued as lever.

Session backlog (evidence-ranked): (1) F-17 direct-double seam +
endpoint threading (H1 var-tape wrapper, est. 2.3-4.5 of 4.75
µs/transition); (2) walnuts joint (target, step) re-tune; (3) depth-12
leg for td-saturated models; (4) diamonds cross-pass fusion; (5) far-
init recovery; (6) embed-stanc (20 ms/fit subprocess cost).

### F-17 VERDICT (2026-08-27; log logs/fortk-f17.md; trunk @ 2bc451a = 4690a00 + feaa4a1/7a6aeee/2bc451a; deps/stan = patches 0001+0002+0003; ctest 64/64 throughout)

PHASE-1 ATTRIBUTION (esnc fused transition, anchor A = 4935 ns; probe
reproduced census baseline within 0.5%; buckets = 100% of A):
executor 371 ns (7.5%) | **H1 var-tape wrapper 2008 ns (40.7%)** | H2
Eigen momentum temps/alloc 1369 (27.7%) | H6 tree glue 507 (10.3%) | H3
ps_point copies 339 (6.9%) | H4 RNG 229 (4.6%) | H5 log_sum_exp 112
(2.3% — DIED vs estimate) | H11 icache ~0 (DEAD). G1 PASS. H1 verdict:
dominance CONFIRMED, magnitude ~half the static estimate (~195 ns/eval).

LEVERS (each: draws byte-identical 3/3 models, ctest 64/64, hier_2pl
tripwire held, kill-switches byte-identical):
- C.5 direct-double seam (feaa4a1): esnc 1.36x, blr 1.48x, hier 1.08x.
- C.1 endpoint threading (7a6aeee + patch 0002): log_prob eval drop =
  transitions - 1 EXACTLY on all 3 (esnc 4140->3741; cache hits -> 0);
  walls small post-seam as predicted.
- H2/H3 hoists (2bc451a + patch 0003): esnc 1.20x, blr 1.13x; ~517
  ns/trans real saving (construction/loop-setup, not just alloc pairs).

OVERHEAD LADDER (esnc ns/transition): 4875 pre -> 3500 (+seam) -> 2958
(+threading) -> **2585 (+hoists) = 1.886x total** (quiet 2480-2750);
grad share 7.5% -> 13.0%. Combined 1.886x vs product-of-levers 1.74x —
composes within noise (second independent attribution validation).
blr 1.533x; hier_2pl ~parity (correct: gradient-bound). Walnuts path
untouched (D0 byte-identical).

### F-18 pre-registered (closing confirmation): post-F-17 ESS/s

Reduced campaign: the 6 phase-1 models, arms A (cmdstan) + C (trunk
@ 2bc451a fused nuts) only, 4 chains x 1000+1000, 3 reps medians,
F-8 conventions. Purpose: convert F-17's ns/transition into the lane's
headline metric; expected small-class ESS/s ratio vs F-8's C arm
~1.3-1.7x (bookkeeping-dominated models gain the loop ratio; measured
not assumed). No adoption gate — final-state measurement. GOAL: the
day-one closing table for the lane report.

### F-18 VERDICT — CLOSING (2026-08-27 morning; log logs/fortk-f18.md; raw bench/fortk_f18/; measurement only, no code changes)

CLOSING TABLE (ESS_bulk/s, 3-rep medians, F-8 conventions; F-8 rows for
context): C/A today per model — esnc 5.28x, esc 11.52x, blr 5.30x,
pilots 6.37x, kidscore 4.73x, logmesq 6.10x; **GEOMEAN 6.24x** (paired
today; 5.0x normalized to F-8's A-day environment — A's walls ran
1.15-1.41x F-8's day with IDENTICAL draws, environment not code).
History: 3.15x at F-8 -> 6.24x after the F-17 loop package = 1.59x
geomean gain (registered expectation 1.3-1.7x; purely wall — C's ESS
identical to F-8's C at FULL PRECISION, draws bit-identical).

STRONGEST VALIDATION IN THE LANE: A today reuses F-8's exes+seeds ->
per-rep ESS rel diff 0.0000 on all 6; C identical to F-8's C to full
precision; GRAD_COUNTER arithmetic exact (esnc 4079/61 pre -> 3741/0
campaign = 399-61). Per-model loop gains scale with bookkeeping share
exactly as the F-17 attribution predicted: esnc 1.43x (diluted by
untouched warmup/adaptation + 8ms timer noise), blr/esc/logmesq/pilots
1.6-2.0x, kidscore 1.05x (most gradient-bound: 31.9 grads/iter at
~1.7 µs vs esnc 8.74 at ~0.6 µs — the removed ~2.3 µs/trans is <5% of
its budget).

LANE MILESTONE CERTIFIED. Day-one summary (all gated, all in this
ledger): fused tiers + T2 kernels + coverage = 2.25x corpus geomean
over the interpreter (F-6/F-7); sampler stack = 6.24x CmdStan ESS/s
geomean on the small class + 2.84x on the phase-2 mid/large class
(F-16/F-18); batch throughput 508k-1.16M fits/hour in-process =
2.5-2.9x stanli's own binding (F-14); two independent multiplicative
attribution validations (0.99x, 1.886x-vs-1.74x); one upstream bug
independently rediscovered + one own-claim retracted; three walnutpie
transferable findings; bit-identity preserved through 6 consolidations.

BACKLOG (evidence-ranked, unmoved): (1) walnuts joint (target, step)
re-tune — makes D-arm a default candidate; (2) depth-12 leg (td-
saturated models); (3) diamonds cross-pass fusion (the one losing
cell); (4) far-init recovery (arma11 seed event); (5) embed-stanc;
(6) LEAN-LOOP REWRITE — remaining 2585 ns/trans (13% grad, H6 tree
glue 10%, momentum math, RNG); the big-swing option now that every
smaller lever is taken; needs the C.5-style bit-identity accounting
for RNG/adaptation order. Standing rules unchanged: no upstream, no
push, trunk @ 2bc451a.

### fortk PR lane COMPLETE (2026-08-28; log logs/fortk-prs.md; agent died at usage limit, parent finished)

Four [fused jit] DRAFT PRs on sims1253/stanli (fork only, never
upstream), hub-and-spoke, all branches rebased onto the synced main
33f79dea and re-gated there (hub ctest 69/69, esnc cross-base CSV
byte-identical; walnuts 70/70 within-rebase byte-identity; eigh 69/69
after the Expr-ordinal fix 9f38119 — portable-MIR v2 tags are enum
ordinals, new kinds must sit after Unsupported; loop 69/69, draws
byte-identical + counter arithmetic exact at both bases):
- #1 fused-JIT tier (jit-tier -> main): the whole tool — verification
  20/21 corpus models, census 2.25x, compile budget, 6.24x ESS/s with
  #2 stacked, 508k-1.16M fits/hour.
- #2 base_nuts sampler-loop package (-> jit-tier): 1.886x esnc loop,
  attribution table, patches carried as patches/deps-stan/000{1,2,3}.
- #3 eigendecompose_sym (-> jit-tier): bitwise kronecker, 1.24x,
  cross-project dep on sims1253/stanc3 eigh pass noted in-body.
- #4 walnuts knobs (-> jit-tier): kidscore gate, coupled-calibration
  finding, default-off byte-identity.
Bodies at orwell-pr-*.md (<=23 lines, orwell style). User reviews
drafts before any further upstreaming consideration. Standing rules
hold: no upstream interaction.

### F-19 pre-registered (post-rebase re-benchmark at 33f79dea; user request)

The PR-lane rebase re-GATED (correctness) but did not re-BENCHMARK.
Upstream's 77 commits include stanc-side MIR loop vectorization — graph
shapes the census measured may change, moving both the unfused baseline
and fused ratios. Scope, mapped to the PR stack:
- (a) Census re-run on the REBASED HUB branch (fortk-pr/jit-tier @
  68c0495): all 21 models, fused-vs-unfused executor µs/call + 64-pt
  verify, same protocol as F-6/F-7. Compare per-model ratios to the
  85a8f11 census; any row moving >10% gets a dump_ops old-vs-new graph
  diff to attribute (stanc graph change vs runtime vs noise).
- (b) kronecker row re-run on the REBASED EIGH branch (9f38119), staged
  F-13 stanc.
- (c) ESS/s headline re-run on the REBASED LOOP branch (91046eb =
  hub+loop, the full sampling stack): phase-1 6 models, arms A (cmdstan)
  + C (fused nuts), F-8/F-18 conventions; the new headline geomean.
- (d) Loop ladder spot-check (esnc ns/transition) at the rebased base.
- No pass/fail gate (measurement); EXPECTATION pre-stated: deltas small
  unless the stanc pin/vectorization changed graphs (then attribute via
  dumps). PR bodies (#1..#4) get a one-line addendum with the rebased
  numbers if any headline moves materially; WORKLOG gets the full table.

### F-19 VERDICT — post-rebase re-benchmark (2026-08-28; log logs/fortk-f19.md; raw bench/fortk_f19/)

HEADLINE: the rebase changed NOTHING structural. Stanc pin identical
(4d440ee), tmir byte-identical (prog_path line only), dump_ops BYTE-
IDENTICAL all 20 models, region counts = F-7 everywhere — upstream's
MIR loop vectorization did not alter any corpus graph at this pin. All
ratio movement is kernel-time/day drift.

- Census (hub @ 68c0495): geomean 2.09x (old-base table 2.03x) = +3.1%;
  movers >10% (esnc +10.6, diamonds +17.6, dogs +23.3) are pure
  interpreter-arm drift (unfused µs/call moved >10% on 14/20 models,
  both directions — this box's absolute walls drift; ratios remain the
  instrument). Verify 20/20 PASS identical to 85a8f11 records.
- Kronecker (eigh @ 9f38119, F-13 stanc staged): 226.6/299.7 = 1.323x
  (was 1.239x); bitwise 0.0/0.0, same dump md5 as the 85a8f11 gate.
- ESS/s (loop @ 91046eb, full stack): geomean 5.98x vs F-18's 6.24x
  (-4.2%) — C's 24/24 chain CSVs BYTE-IDENTICAL to F-18's C, ESS rel
  0.00000; walls moved both directions => environment, not stack.
- Ladder: esnc 2372 ns/trans (band overlap with 2585); GRAD_COUNTER
  3741/0 exact (patches 0001-0003 confirmed live).
- CORRECTION (loud, per protocol): the F-7 verdict's quoted "2.25x
  corpus aggregate" was WRONG — it recomputes to 2.03x from F-7's own
  table (parent's hand-aggregation error at write-up time). Corrected
  here and in PR #1's body (2.03x @85a8f11, 2.09x re-measured @33f79dea).
  No other PR body cites a moved number.

## 2026-08-28 — upstream SE-debt audit: 9 Stan-ecosystem repos (9 parallel review agents)

Full report: logs/upstream-cleanup-review-2026-08-28.md. Method: one
read-only review agent per distinct upstream project we touch; each
fetched the canonical mainline (no remotes added, local feature-branch
checkouts untouched) and reviewed a detached worktree under /tmp/review/*
(all left in place; cleanup loop at end of report). No builds/tests run.

- Projects covered: stan, math, stanc3, cmdstan (stan-dev, at develop/
  develop/master/develop); stanli (canonical parent = seantalts/stanli@main,
  not the sims1253 fork); bridgestan (MOVED: now roualdes/bridgestan —
  stan-dev/bridgestan 404s); walnutpie; tinystan; posteriordb.
  Excluded as untouched: cmdstanpy/cmdstanr/docs.
- Headline: the SE-debt hypothesis is confirmed but concentrated. The
  dominant pattern repo-wide is "deprecated means never removed" — math's
  _cdf_log family alone is ~215 deletable files incl. its full test rig;
  cmdstan's bin/print; bridgestan's 2023 py/jl shims. Second: CI/build
  layers frozen 2018-2021 (clang-6.0 pins, 6x-copied Windows PATH blocks,
  stanc3's dual Jenkins+GHA binary pipelines, OCaml version in 6 places).
- Real BUGS found incidentally (report-upstream candidates, see report
  digest): walnutpie handlers.hpp warmup buffers swapped; bridgestan R
  downloads tarball 5x/install + swapped handle_error args; identical
  unlatched WINDOWS_PATH_SET bug in bridgestan AND tinystan python;
  tinystan R binding 3 latent bugs; same $(STANC#) make typo in stan AND
  cmdstan; math 'doygen/**' CI-ignore typo.
- stanli specifically: an 8-area simplification review was run AND
  executed 2026-08-09; remaining debt is velocity (lower.cpp 2.4k -> 5.8k
  lines in 19 days), plus no CI gate regenerating the 165 MIR fixtures.
- Follow-up same day: 12 upstream-relevant bugs filed as [upstream
  candidate] issues on my forks (orwell-writing style, each verified
  against the /tmp/review worktrees first): stan#3, cmdstan#2, math#7,
  bridgestan#2-4, tinystan#1-4 (new fork created for this; all forks
  had issues disabled -> enabled has_issues on the 6 target forks),
  walnutpie#26-27. stanc3 and stanli: no clear bugs, nothing filed.
- Second round same day: original 12 retitled [upstream candidate] ->
  [upstream bug candidate]; 42 [upstream cleanup candidate] issues
  filed from the audit's non-bug findings: stan#4-8, math#8-13,
  stanc3#2-6, cmdstan#3-7, stanli#5-9, bridgestan#5-9, walnutpie#28-32,
  tinystan#5-7, posteriordb#1-3 (fork already existed; issues enabled,
  as on stanc3/stanli this round). Same orwell style; minor one-liners
  folded into per-repo batches.


### F-20 pre-registered (load-stable PR instruments: callgrind/cachegrind; user direction)

The box is chronically busy; wall ratios drift (F-19: unfused µs/call
moved >10% on 14/20 models, both directions). Convert PR headline claims
to instruction-count / cache-model instruments (deterministic under
load) and update the four draft bodies:
- #1 census: callgrind Ir per gradient eval, fused vs unfused, per model
  + geomean (all 20 if budget allows, else the 12 most-cited; state it).
  Cachegrind D-miss counts for diamonds (explains bandwidth parity).
- #2 loop: Ir per transition, hub-binary vs loop-binary (esnc/blr/
  hier_2pl); seam toggle via STANLI_DIRECT_SEAM where cheap.
- #3 eigh: Ir per gradient, kronecker fused vs stock (the instrument the
  stanc3 eigh PR itself used: 5.254M -> 4.238M).
- #4: statistical claims are draw-based already; no Ir line needed.
Bodies keep the wall numbers as context, clearly labeled busy-box wall;
Ir ratios become the headline ratios. Cap ~24 lines; gh pr edit each.

### F-21 pre-registered (WALNUTS joint (target, step-scale) re-tune — the most promising open direction)

Mechanism (F-11.2): batched/denoised Adam converges to the true
E[alpha]=0.8 root at frozen step ~0.057 vs stock's accidentally-large
0.22 — quality up, wall up 1.5-3.5x. The joint re-tune seeks a config
landing at a GOOD step scale: grid over batch {10,25} x target {0.7,0.8,
0.9} x a new explicit frozen-step multiplier knob (default 1.0 = off) on
a dev set {esnc, blr, kidscore, logmesq}; ESS/draw + rhat = stable
quality gates (draw-based, load-immune), wall recorded (noisy, labeled).
WINNER validation on the full phase-1 6 + the F-16 silent-failure set
{bym2, diamonds, kronecker}: GATE = phase-1 geomean ESS/s (wall,
interleaved within rep as the only fair use of wall) > arm C's 5.98x
rebased, AND all-chain rhat < 1.01 on every validation model (no silent
failures), AND kidscore gate retained. Branch off fortk-pr/walnuts;
default-off discipline for any new knob; never loosen. A miss = ranked
evidence for the walnutpie lane (mechanism write-up either way).

### F-21 VERDICT (2026-08-28; log logs/fortk-f21.md; branch fortk/f21-retune @ 7f4f241, NOT pushed; ctest 70/70)

GATES: (a) FAIL — D_b10_m8 phase-1 geomean ESS/s 2.927x vs C-today
6.565x (arms interleaved same-day; C/A per-rep 3.2-7.0 = wall noise,
best D rep 4.53x still loses). (b) FAIL 5/9 — esc 1.078, pilots 2.434
(multimodal, all arms bad), bym2 1.017, diamonds 1.015, kronecker 1.047;
passes esnc/blr/kidscore/logmesq. (c) PASS — kidscore R-hat 1.006,
ESS/draw 0.457 (best-in-class; ESS/s 12,021 = 1.09x C; logmesq wins
1.30x C). (d) PASS — default path byte-identical (md5 b1bb391c).

MECHANISM (dev set, frozen step / ESS/draw, stock -> b10 -> b10x8):
esnc 0.706/0.763 -> 0.658/0.777 -> 5.33/0.195 (peaks x4: 1.545 —
collapses at x8, trajectory U-turns immediately); blr 0.222/0.149 ->
0.075/0.218 -> 0.60/0.421; kidscore 0.504/0.083 -> 0.310/0.133 ->
2.48/0.457; logmesq 0.336/0.106 -> 0.311/0.090 -> 2.49/0.478.
Findings: the F-11.2 "4x smaller step" was blr-specific (3.0x; others
1.1-1.6x); b25 < b10 at every K (over-denoising past 10); all three F-16
silent-failure models IMPROVED (bym2 1.055/1.027->1.017, diamonds
1.108/1.030->1.015, kronecker 1.05-1.34->1.047) — the too-small denoised
step was part of their problem — but none crossed 1.01. CORE MISS =
heterogeneity: esnc wants K<=4, logmesq needs K=8; no global (target,K)
works; target-side probe declined per pre-registration (gate-bait).
Knob ships default-off: step_freeze_multiplier (warmup draws bit-
identical under any K — property-tested). Open (ranked): per-model
step scale from warmup diagnostics (adaptive K); failure-set mass/step
coupling. Walnutpie-lane evidence complete either way.

### F-20 VERDICT (2026-08-28; log logs/fortk-f20.md; raw bench/fortk_f20/; no git changes)

Load-stable instruments delivered; all four PR bodies live == local.
Instrument: --cg N --cg-arm A noinline loop + callgrind --toggle-collect
(repeats byte-identical under load 3.9-7.8 with F-21 concurrent).
- PR #1: census Ir/eval fused/unfused geomean **2.546x** over the 20
  accepted (all 21 measured; esnc 8.98x, esc 8.52x, arma11 5.97x,
  hier_2pl 2.74x, kronecker 1.01x) — Ir ABOVE busy-box wall (2.09x), as
  expected: instruction cuts exceed wall gains on memory-bound models.
  Diamonds cachegrind: D-read refs 1.007x, LLd ~7 vs 8 misses/eval =
  same DRAM stream — bandwidth parity now mechanistic, not just
  observed. Wall numbers kept as labeled context; correction history
  intact.
- PR #2: sampler Ir/transition hub->loop: esnc 80,412->36,914 =
  **2.178x**, blr 240,911->119,427 = 2.017x, hier_2pl 1.039x (geomean
  1.659x); seam toggle alone 1.542x at identical grads; hier_2pl residue
  attributed EXACTLY (399 = transitions-1 endpoint carry; per-eval Ir
  6,258 vs 6,185). Wall 1.886x labeled context.
- PR #3: kronecker 4,839,871 -> 3,810,092 Ir/grad = **1.270x**
  (interpreter arm; region arm 1.272x); mirrors the stanc3 eigh PR's
  instrument class.
- PR #4: one line — quality gates draw-based, load-immune, no Ir needed.
Pitfall recorded: bare '*run_nuts*' toggle undercounts 45x (nested
lambda names cancel the XOR).

LANE STATE: all four [fused jit] drafts carry load-stable headline
numbers (Ir ratios; cachegrind for the bandwidth story), gated at the
rebased tip, benchmarked at both bases, correction history preserved.
Standing: no upstream, drafts only. Backlog unchanged (F-21's open
directions ranked first on the walnutpie side).

### F-22 pre-registered (lean sampler loop + depth-12 leg; user direction "most promising")

F-21's ranked-first walnutpie direction (adaptive per-model K) stays
parked pending its own lane; the most promising DEFAULT-arm direction
is the F-17a C.4 endgame: remaining esnc transition = 2372 ns wall /
36,914 Ir, gradient ~13%, the rest diffuse (tree glue ~10%, momentum
Eigen math, RNG, adaptation). Charter, evidence-first:
- (i) ATTRIBUTE first: callgrind function-level breakdown of the
  remaining 36,914 Ir/transition (esnc, loop binary); name the top
  functions. DECISION RULE (pre-stated): if >=60% of remaining Ir sits
  in <=3 eliminable components => targeted eliminations (F-17-style
  levers, byte-identity gates); else => the lean driver.
- (ii) LEAN DRIVER (if taken): a stanli-side minimal NUTS over the
  ExecutorModel raw-double seam (the C.5 seam already exists), dropping
  stan::mcmc/services machinery: fixed diag metric (adaptation via the
  existing loop during warmup, then frozen — reuse the adapted metric),
  own tree recursion, arena-resident state (no ps_point). GATES:
  statistical equivalence (3 seeds x phase-1 models: ESS_bulk/draw
  parity within noise of arm C, divergences not worse, R-hat < 1.01),
  ESS/s >= 1.3x arm C on the esnc-class geomean (interleaved same-day),
  hier_2pl no-regression, ctest green. NOT bitwise (own RNG ordering) —
  labeled a separate sampler arm (stanli_run --sampler lean-nuts
  equivalent in the tool: --lean flag), default-off.
- (iii) DEPTH-12 LEG (cheap, owed from F-16): kronecker + lsat at
  --max-depth 12, arm C, 3 reps: fill the td-saturation cell (kronecker
  3981/4000 td-hits context). Informational + adoption rule from the
  F-11.3 design (>=3% geo ESS/s, no >10% regression).
Branch off fortk-pr/sampler-loop (fortk/f22-lean). Instruments: Ir
(load-stable) primary, wall interleaved secondary.

### F-22 VERDICT (2026-08-28; log logs/fortk-f22.md — two-session lane, all numbers cross-verified; branch fortk/f22-lean @ 79ec226, default-off, NOT pushed; ctest 69/69)

(i) ATTRIBUTION + DECISION: remaining esnc Ir = Eigen Dense2Dense assign
23.3% / base_nuts self 13.1% / inner_product 8.9% — structure, not
patchable waste (strict-eliminable ~7% << 60%; top-3 = 59.17% < 60%,
rewrite-only) => LEAN DRIVER on both readings of the pre-stated rule.

(ii) LEAN DRIVER (--lean, default-off; warmup through stock loop +
frozen-state handoff):
- (d) PASS (twice, independently): default path byte-identical.
- (a) PASS with the SURPRISE: lean draws BITWISE-EQUAL to arm C on all
  18 cells (ESS/rhat/div/td + grad counters identical to the digit) —
  observed, not guaranteed across models/dims.
- (b) FAIL at the 1.3x bar: full-run Ir esnc 1.127x / blr 1.097x /
  hier_2pl 0.995x = 1.071x geomean; sampling-PHASE ratio 1.36x (esnc) /
  1.19x (blr); stock warmup = 55-65% of run Ir and caps the ceiling
  (lean-warmup ceiling ~1.2-1.35x). Wall cannot resolve ~1.1x on this
  box (1.123x median-of-ratios vs 1.003x ratio-of-medians); Ir decides.
- (c) PASS clean: hier_2pl 0.997 (the 0.969 was callgrind-load
  conservative). Ships default-off; next levers named: lean warmup,
  pass-fusion, dot-batching (statistical-gated).
- Lane incident recorded: the "failed" session survived the network
  drop; two agents ran ~30 min concurrently before deconflicting via
  the shared log; everything cross-verified or re-run clean.

(iii) DEPTH-12 LEG (the F-16 owed cell): NO ADOPTION. kronecker ESS/draw
1.414x but wall 3.718x => ESS/s 0.380x; td-hits 99.4% -> 49.6% (rep2
still 99.2% — saturates even 12); div worse. lsat vacuous (td 0% at
d10, draws bitwise-identical). Geo ESS/s 0.627x. The td<=5% criterion
is unsatisfiable by construction for td-saturated models — reported
straight; efficiency loses outright anyway.

BACKLOG after F-22 (evidence-ranked): lean warmup + pass-fusion/
dot-batching inside the lean loop; adaptive per-model K (walnutpie);
diamonds cross-pass fusion; far-init recovery; embed-stanc.

### F-23 pre-registered (lean WARMUP; user direction "apply it to warmup too")

F-22 decomposition: lean sampling phase = 1.36x (esnc) Ir but stock
warmup = 55-65% of run Ir => full-run 1.071x vs the 1.3x bar. Ceiling
arithmetic for a lean warmup: ~1.2-1.35x full-run — BORDERLINE at the
bar; build to find out. The design bet: the lean sampling phase came
out BITWISE-equal to arm C; if the lean warmup drives the SAME
adaptation objects (vendored stan dual-averaging + Welford windows) at
the same decision points, with the lean tree/leapfrog underneath, the
whole run may be bitwise too — collapsing the fidelity risk. Charter:
- Extend --lean to run warmup (init + windows + freezes) with the lean
  traversal; reuse, do not reimplement, the adaptation algorithms;
  window schedule identical to stock.
- GATES (never loosen): (a) FIDELITY — full-run draws (warmup-inclusive,
  i.e. --lean from iteration 0) BYTE-IDENTICAL to arm C on esnc/blr/
  hier_2pl (gold; if unachievable, the pre-declared fallback: adapted
  frozen state (eps, inv_metric) compared exactly + 3-seed statistical
  equivalence + divergence parity, and the deviation POINT localized in
  the log); (b) SPEED — full-run Ir geomean over the esnc-class 5 >=
  1.3x (the F-22 bar, kept; a 1.2-1.3x landing = honest near-miss
  verdict naming pass-fusion/dot-batching as the remaining levers);
  (c) default path byte-identity retained + ctest green; (d) ESS/s
  end-to-end (interleaved same-day vs arm C, 3 reps) reported — the
  user's metric, informational.
- Branch fortk/f23-leanwarm off fortk/f22-lean. Ir primary instrument.

### F-23 VERDICT (2026-08-28; log logs/fortk-f23.md; branch fortk/f23-leanwarm @ 2eb3785 off f22-lean, NOT pushed; ctest 69/69)

GATE (a) FIDELITY: GOLD — full-run --lean (warmup from iter 0) draws
BYTE-IDENTICAL to arm C on esnc/blr/hier_2pl (md5s recorded; grad
parity exact — esnc's +-1 = arm C's own endpoint-cache hit; frozen
adapted state identical to 17 digits + FNV). Beyond gate: 15/15
campaign cells md5-EQ; window-rescale edge shapes (w=100, w=20) EQUAL.
The bet held: same adaptation objects at same decision points + lean
traversal = bitwise warmup.
REAL BUG found+fixed en route: F-22's hand-loop dots differed from
Eigen 5.0.1's packet-reduction summation order in the last ulp —
invisible when only 6-digit accept_stat__ consumed it, FATAL once dual
averaging ate it every warmup iteration (drift by iter 4; localized via
STANLI_DEBUG_LEAN_TRACE). Fix = Eigen Map dots (alignment changes load
modes, never order). Also: the tool's in-process "bitwise=" line is an
INVALID instrument (compares unfused-vs-fused executors — explains
F-22's 3765/3741 asymmetry); same-executor md5 is the valid gate.

GATE (b) SPEED: NEAR-MISS — full-run Ir geomean 1.228x vs the 1.3x bar
(one binary, iso-grad by construction; phase split via 200+1 runs):
esnc 1.334x (warmup-ph 1.322 / sampling-ph 1.353) | esc 1.297 | blr
1.185 | logmesq 1.273 | kidscore 1.071 (kernel-bound floor: 13.5k
Ir/grad). HYPOTHESIS CONFIRMED: warmup phases now gain what sampling
gained (F-22: warmup 1.0x stock; now 1.32x); esnc CROSSED the bar
(1.127 -> 1.334). The geomean is floored by kidscore/blr — models where
the GRADIENT dominates and loop work cannot pay by construction. The
loop-side program is near its structural end; remaining named levers:
pass-fusion + dot-batching inside the lean loop (FP-order, statistical-
gated).

GATE (c) PASS (default byte-identity retained). GATE (d): ESS/s 1.220x
end-to-end, 15/15 md5-EQ — ESS identical by construction, pure wall;
ms-scale walls now bracket Ir (unlike F-22 where they resolved nothing).
--lean = lean-from-iter-0 (new default behavior); --lean-stock-warmup =
F-22 two-phase fallback (also md5-verified). No PR edit (bar not
crossed; default-off tool).

### F-24 pre-registered (pass-fusion + dot-batching in the lean loop — the last named loop levers)

F-23: lean loop full-run Ir 1.228x geomean (esnc 1.334x crossed the
bar; kidscore/blr gradient-bound). F-22 attribution of the LEAN loop's
own remaining Ir: loop self (recursion + hand passes + dots) 51.8%.
The two pre-named levers, both FP-ORDER-CHANGING (statistical-gated,
NOT bitwise — the F-23 gold gate becomes statistical for this change):
- PASS-FUSION: the lean leapfrog performs separate passes over q/p/g
  (momentum half-step, gradient read, position step, criterion/H terms);
  fuse into fewer passes (single sweep computing H increments and
  criterion terms together, keep per-element arithmetic identical where
  possible — fusion of LOADS, not reassociation of SUMS where avoidable).
- DOT-BATCHING: the criterion/rho inner products — batch/accumulate to
  cut per-call Eigen dispatch and loop overhead.
Charter, branch fortk/f24-loopfusion off f23-leanwarm:
- GATES: (a) STATISTICAL equivalence vs arm C (draws will differ):
  3 seeds x phase-1 6 models — ESS_bulk/draw within noise, R-hat < 1.01,
  divergences not worse, adapted eps/inv_metric close (report max rel
  diffs); (b) full-run Ir geomean (esnc-class 5) >= 1.30x — the
  original F-22 bar, now the finish line for the loop program; a 1.23-
  1.30x landing = the loop program's structural end verdict; (c)
  default path byte-identity + ctest green; (d) ESS/s interleaved
  informational. Attribution table of the lean loop's Ir after (i) to
  verify the levers actually consumed the 51.8% pool.

### F-24 VERDICT — LOOP PROGRAM FINISHED (2026-08-28; log logs/fortk-f24.md; branch fortk/f24-loopfusion @ 4dbbbdd off f23-leanwarm, NOT pushed; ctest 69/69; only tools/fortk/regions.cpp touched +164/-97)

ALL GATES PASS; the 1.30x bar CROSSED: full-run Ir geomean **1.360x**
(esnc 1.558x, esc 1.495x, logmesq 1.373x, blr 1.324x, kidscore 1.098x;
F-23 was 1.228x; iso-grad caveat: fused did MORE grads on 3 models —
wins understated; per-grad geomean 1.371x).
- Levers shipped: leaf 10-passes+5-memcpy -> 2 sweeps + 1 memcpy (sweep
  A per-element identical; sweep B the deliberate reassociation);
  merges -> 1 sweep, 6 scalar accumulators (rho_sub/rho_ext
  dematerialized); Eigen dot dispatches 7.35% -> 0; pool+dots+memcpy
  -21.5% absolute. Residual = recursion structure + state model = a
  rewrite, not a lever. LOOP PROGRAM: FINISHED (not structurally ended).
- (a) STATISTICAL PASS: ESSd ratios 0.944-1.383, |t|<=1.84, R-hat gate
  held (blr's two 1.011 reps one-per-arm symmetric), div not worse
  (2628 L vs 3022 C). kidscore draws BITWISE C==L for free (n=3: Eigen
  dot sequential = T_seq exactly). Adapted-state deltas reported;
  logmesq's initial -11% ESSd resolved to -3.2% n.s. with 8 reps (extra
  reps run rather than accept ambiguity).
- (c) default byte-identity retained; (d) ESS/s 1.232x L/C wall
  (brackets Ir); kidscore pure-wall ~1.087 vs Ir 1.098 — instrument
  agreement.
- PR #2 updated (materiality rule): "Beyond byte-identity" section,
  1.360x labeled research-tool/default-off/statistical-gated.
- Trace proof: iteration-0 accept differs in the LAST ULP; qhash
  identical 7 iters, tree shapes identical all 200 — decorrelation
  enters via a proposal-draw branch, not physics.

### F-25 pre-registered (kernel-side: the gradient-bound floor — kidscore/blr)

F-24's residue = "gradient-kernel floor": kidscore 1.098x and blr
1.324x are bounded by per-grad Ir (kidscore 13.5k Ir/grad — the highest
in the class). The loop program is done; the binding constraint moved
back to the kernels. Charter: dump_ops kidscore + blr at the current
base, identify unvectorized likelihood paths in their regions, extend
the emitter's T2 vectorization to them (the bernoulli_logit/hier_2pl
pattern: block-of-4 vecmath in the observation loop, variant-honored).
GATES: verify 64 pts < 1e-9 (unchanged oracle); Ir/grad improvement
reported per model (callgrind, primary); ESS/s informational. Branch
off fortk-pr/jit-tier (the emitter home). Loop side closed — this is
the full-circle return to the graph side the evidence now demands.

### F-25 VERDICT (2026-08-28; log logs/fortk-f25.md; branch fortk/f25-kernelfloor @ db60cf0 off fortk-pr/jit-tier, NOT pushed; ctest 69/69; only tools/fortk/regions.cpp touched)

KERNEL-SIDE FULL CIRCLE PAID: kidscore 11,203 -> 5,172 Ir/grad
(**-53.8%**), sampling-run Ir 1.796x; census ratio 3.60 -> **7.80**;
census geomean 2.546 -> **2.737 (+7.5%)**. blr confirmed AT THE F-7
FLOOR (1,788 Ir/eval; residue = priors/logs/memcpy — nothing
vectorizable; honest). Attribution surprises: (1) kidscore's #1 fused
cost was a 3.5 KB bwd local-adjoint MEMSET (31.6% of Ir — ERMS-inflated
but real), eliminated via first-write conversion (converted classes
only; exact in both memset outcomes); (2) a plain block-of-4 loop does
NOT vectorize 4-wide here (12 live values -> 2-wide SLP + spills) — the
MULTI-PASS split (elementwise pass A into block-local array + pure
4-lane reduction pass B) is what buys 4-wide — transferable emitter
lesson; (3) region-cache keys don't hash emitted bodies — version bump
required on every emitter-output change; (4) --cg binaries need
FORTK_VECMATH_DIR.
GATES: (a) verify kidscore 1.4e-15, blr byte-identical to F-19 record,
esnc bitwise, hier_2pl/wells identical to history, census 20/20 PASS;
(b) Ir above; (c) ctest 69/69 + default-path byte-identity 9/20 with
all 11 differences confirmed >=32-lane reassociating (statistical
class); (d) ESS/s kidscore ~1.42x mean (brackets Ir 1.796 from below).
PR #1 addendum shipped (kidscore row +117%, materiality rule).
F-24's kidscore loop-ratio 1.098x was floored by exactly this kernel;
with v6 it re-rates ~2.1x (noted; other lane).

### F-26 pre-registered (INTEGRATION CAPSTONE — the session's closing number)

Merge the two arcs — f25-kernelfloor (jit side) + f24-loopfusion (loop
side; descends f23-f22-sampler-loop PR stack) — into one integration
branch; gate (build, ctest, verify spots); then the CLOSING CAMPAIGN:
phase-1 6 models, arms A (cmdstan) + C (PR-stack fused nuts, stock
loop) + L (integration, --lean) — 4 chains x 1000+1000, 3 reps
interleaved, F-8/F-18 conventions; report per-model + geomean ESS/s vs
CmdStan (wall, labeled) + full-run Ir ratios (primary). EXPECTATION
(pre-stated): F-18 was 6.24x / F-19 5.98x; with the loop stack (1.36x
Ir) + kidscore kernel (1.8x) the best config plausibly lands 8-10x on
the small class. Also the batch-throughput spot (--fits on the
integration branch) to close the loop with F-14. No adoption gates —
the final measurement + honest read of what composed and what didn't.

### F-26 VERDICT — INTEGRATION CAPSTONE, SESSION CLOSING NUMBER (2026-08-28; log logs/fortk-f26.md; branch fortk/f26-capstone @ 70fd71a = merge f24-loopfusion + f25-kernelfloor, auto-merged + semantic hunk audit, NOT pushed; ctest 69/69; all oracle gates digit-for-digit)

CLOSING TABLE (ESS_bulk/s geomean vs CmdStan, 3 reps interleaved, A
reproduces F-18's A ESS at 0.0000 rel — campaign lineage certified):
**C (PR stack, stock loop) 5.92x | L (integration, --lean) 7.53x**;
5-model geomean excl. the pilots realization-chaos cell: **8.20x**;
kidscore end-to-end 9.31x (was 4.70x at F-8). SESSION ARC: F-8's 3.15x
-> 7.53x = 2.39x stacked from individually-gated layers; all
bit-identity gates still green.
- Composition check (third of the session): kidscore wall 2.16x =
  kernel 1.796x x loop 1.19x (2.14 predicted) — the arcs are
  resource-disjoint and multiply.
- Full-run Ir (one binary): geomean 1.422x (F-24 1.360x — the kernel
  arc raised it by shrinking kernel share on logmesq/kidscore).
- Batch: --fits 956k (blr) / 2.6M (esnc) fits/h = 1.88-2.26x over
  F-14's d arm; per-fit 3.63/1.23 ms. NEXT ITEM (recorded): --fits
  drives stock run_nuts_chains — batch lane does not yet ride the lean
  loop.
- Honest negatives: pilots 0.79 L/C = realization chaos (each arm takes
  the catastrophic rep in turn; min ESS 7/4000); blr at its attributed
  kernel floor; A ran an atypically fast day (C/A 5.92 vs F-18's 6.24
  on identical draws — cross-day wall caution again); registered
  8-10x landed 7.53x (8.20x excl. chaos cell).
- Incident handled: fetch.sh hook discarded the shared stanc binary;
  pinned 5b824ee rebuilt from source, MIR byte-identical to 5 recorded
  artifacts, campaign md5s confirm end-to-end.

LANE CLOSED at the capstone. Backlog (parked, user's call): --fits-on-
lean, adaptive-K walnutpie, diamonds cross-pass fusion, far-init
recovery, embed-stanc, the state-model rewrite beyond the loop floor.

### F-27 pre-registered (warmup early-exit: the W-21/22 port — the biggest remaining ESS/s lever)

Evidence base: W-21/W-22 (walnutpie lane): --early-exit-warmup won
1.3-2.4x wall where it exits; hurt the marginal class (arma11 -33%,
lsat -40%, hier_2pl -58% ESS) BECAUSE the step still grows +170% late
in warmup while mass is stable — W-22's gate: step-drift <5% over the
last 2 windows; NEXT_IDEAS B's pilot burst (50 draws post-candidate-
exit, cross-chain R-hat proxy + lag-1 autocorr) as the second gate —
near-free with fused gradients. Warmup = half the campaign wall.
Charter, branch fortk/f27-earlyexit off f26-capstone:
- Implement --wexit (default OFF) in the tool's sampling driver at
  adaptation-window boundaries past a minimum (e.g. iter >= 150): gate 1
  = |dlog(eps)| < 5% across the last 2 windows AND mass stable; gate 2 =
  50-draw pilot burst, cross-chain R-hat proxy < 1.01 + lag-1 autocorr
  of lp below threshold; both pass => freeze adaptation, exit warmup,
  start sampling. Gate fails at any window => continue (full warmup
  path unchanged).
- GATES (never loosen): (a) QUALITY — on every phase-1 model where exit
  fires: post-warmup ESS_bulk/draw within noise of the full-warmup arm
  (3 seeds), all-chain R-hat < 1.01, divergences not worse; where the
  gate holds warmup (no exit): draws byte-identical to arm L; (b) SPEED
  — ESS/s geomean >= 1.2x vs arm L, same-day interleaved, 3 reps;
  report per-model exit iteration (the "how much warmup does each model
  actually need" table — walnutpie-lane gold); (c) default-off +
  default path byte-identity + ctest; (d) the marginal-class tripwires
  (arma11, hier_2pl, lsat — the W-21 victims) run as no-regression
  sentinels even though they are outside phase-1.
- Expected: esnc-class exits at 200-400 of 1000 => 1.3-1.7x ESS/s =>
  geomean toward 8.5-10x. Instruments: ESS (draw-based, primary for
  quality), wall interleaved (speed), exit-iteration table.

### F-27 VERDICT (2026-08-29; log logs/fortk-f27.md; branch fortk/f27-earlyexit @ 91fe4ce, default-off, NOT pushed; ctest 69/69)

HONEST NEGATIVE — the W-22 gate, ported exactly, CLOSES the lever on
this corpus: ZERO exits fired (72/72 campaign chains + 27/27 quality
cells held full warmup; 108/108 CSVs md5-identical to arm L). Gate (b)
FAIL at 0.920x geomean (the 0.08 deficit = rendezvous sync for g1-
passing chains at ms cell scale; all-fail reps measure 0.998).
MECHANISM (why W-21's 1.3-2.4x does not transfer): stan's windowing
(init 75 / base 25 / term 50 — big window starts at 450) means the
last checkable site (450/1000) has eps 15-110% off converged (blr
0.53x, pilots 2.08x). The nearest miss (logmesq@450: step PASS, mass
0.2585 vs 0.25) PROVEN PROTECTIVE: forcing it costs -10..-20% ESS_min.
Sentinels protected (arma11's single corpus-wide g1 pass was REJECTED
by the pilot at rhat 1.0513 — the W-21 victim defense works). Third
cross-lane non-transfer of the session (endpoint-eval, mallopt,
early-exit-as-gated) — walnutpie's schedule differs; models here
genuinely need their 1000.
ASSET SHIPPED: the exit machinery is complete + validated end-to-end
(3-chain all-pass test: unanimous exit at 450, saves 550/1000 warmup;
RNG-discipline structural) — it opens the moment a corpus converges
by 450, and the exit-diagnostics instrument is calibrated (B*=250,
LAG1_TOL=0.35 with the honest caveat that pilot lag1 does not separate
classes at 50 draws; protection came from gate 1 + knife-edge rhat).
No PR edit (materiality not met).

### F-28 pre-registered (F-11 Design 1 at last: LW late-window mass shrinkage — the remaining designed ESS/grad lever)

The draws/s program is at its floors (loop 1.42x Ir done, kernels at
floor); the ESS/s headroom now lives in ESS/DRAW = adaptation quality.
F-11 Design 1 (569-line design doc, never run): Ledoit-Wolf-style
shrinkage of the late-window NUTS variance estimate toward a trace-
preserving scaled identity, in the vendored var_adaptation. Motivation:
nutpie's ~2x attribution (unproven locally); realistic prior Fisher-HMC
1.3x diag. GATES (from the design): (a) lw_off arm BITWISE-identical;
(b) active arms: no divergence increase (funnel sentinel pilots), geo
ESS/s >= 1.0 AND >= 1.10x on the draw-poor subclass (kronecker/radon/
lsat); (c) lambda->1 mechanism check (the shrinkage actually engages);
(d) ctest + default-off. Branch off f26-capstone; patch 0004 in the
deps/stan series. Statistical-class change (adaptation affects draws).

### F-28 VERDICT (2026-08-29; log logs/fortk-f28.md; branch fortk/f28-lwshrink @ a2656b2, --lw-shrink default 0, NOT pushed; patch 0004 in the deps/stan series; ctest 69/69)

HONEST NEGATIVE at every L in {0.1, 0.3, 0.5}: geo ESS/s 0.708/0.438/
0.446x vs L0; draw-poor subclass 0.812/0.461/0.474x; rhat gate FAILS
too (blr 1.0126-1.0237 at the active arms). MECHANISM FULLY
CHARACTERIZED — the design WORKED, the trade did not:
- Metric de-noising is real: ESS/DRAW rises on the draw-poor class
  (radon 1.57-1.78x, lsat 1.92-1.95x); the 4.3-order metric spread IS
  partly noise and the shrinkage tames it (radon max/min 17,095 -> 35/
  10.6/5.4).
- But the anisotropy was worth more than the noise: the flattened
  metric collapses the dual-averaging step (eps median radon 0.240 ->
  0.019, kidscore 0.113 -> 0.0035 = 6-32x smaller) => grads/iter
  3.5-6.7x => wall explodes. Kronecker (td-capped in every arm) only
  loses. The Fisher-HMC ~1.3x prior does not transfer.
GATES: (a) L=0 bitwise 3/3 md5; (d) ctest + default byteid exact.
Pilots div within cell chaos (no attributable regression). Flag ships
default-off, no recommended L, no PR edit.
FOURTH cross-lane non-transfer (endpoint-eval, mallopt, early-exit,
LW-shrinkage) — each with the mechanism identified. NOTE for the
walnutpie lane: ESS/draw gains at matched grads = the shrinkage WOULD
pay on a sampler whose step size does not collapse under isotropy
(walnuts' within-orbit adaptation is exactly that) — recorded as the
one live follow-up from this negative.

LANE STATUS after F-28: every standard adaptation/knob lever is now
either SHIPPED (loop 1.42x Ir, kernels, lean) or REFUTED-WITH-
MECHANISM (delta sweep, early-exit, LW shrinkage). The ESS/s search
has a well-mapped boundary. Remaining swings (user's call): walnuts
adaptive-K + shrinkage interaction (walnutpie lane), state-model
rewrite, --fits-on-lean (batch metric), diamonds, far-init, embed-stanc.

### PUBLISHING ROUND (2026-08-29, parent-executed; user audit request)

- apin record COMMITTED + pushed as NEW branch fortk-lane-record on
  sims1253/apin (local master has no common ancestry with the purged
  remote main — additive branch, no force; merge at user's leisure).
  Bench raw dirs (40-96M) stay local per runs/ convention; the .md
  lane logs are the evidence of record.
- stanli research branches PUSHED (backup, no PRs): fortk/t2-coverage
  (trunk @ 2bc451a) + f21-retune/f22-lean/f23-leanwarm/f24-loopfusion/
  f25-kernelfloor/f26-capstone/f27-earlyexit/f28-lwshrink.
- Three warranted stacked DRAFT PRs opened (making PR #1/#2's addenda
  reproducible — their bodies cited numbers whose code had no PR):
  #10 [fused jit] lean NUTS loop (f24-loopfusion -> fortk-pr/sampler-loop)
  — F-22..F-24, 1.360x Ir, default-off; #11 [fused jit] kernel floor
  (f25-kernelfloor -> fortk-pr/jit-tier) — F-25, kidscore -53.8% Ir/grad,
  census 2.737x; #12 [fused jit] walnuts step multiplier (f21-retune ->
  fortk-pr/walnuts) — F-21 instrument, honest-miss labeled.
  Bodies orwell-pr-{lean,kernel,stepmult}.md. f27/f28 branches pushed,
  NO PRs (documented negatives, default-off, materiality rule).
- walnutpie fork: no PR/issue opened — the F-11.2/F-21 findings are
  recorded in the apin ledger for that lane; an issue there is the
  user's call. stanc3 fork: nothing new (eigh PR #1 pre-existing).

### F-29 pre-registered (BIG SWING 1: walnuts adaptive-K + mass shrinkage — make walnuts the default)

Evidence: F-21 — step-multiplier K works per-model (kidscore ESS/draw
0.457 best-in-class at K=8, esnc peaks K=4/collapses K=8, logmesq needs
K=8) but no GLOBAL K passes; F-28 — shrinkage raises ESS/draw at matched
grads but collapses NUTS steps 6-32x (walnuts' within-orbit steps do
NOT derive from the metric that way — the recorded live follow-up).
Charter, branch fortk/f29-adaptiveK off f21-retune (worktree
stanli-pr-waln): (i) implement per-model ADAPTIVE K chosen from warmup
diagnostics (candidate signals: observed U-turn depth distribution,
accept-stat level, frozen-step vs trajectory-length ratio — pick ONE,
state the rule before the campaign); (ii) walnuts-side mass shrinkage
knob (in the VENDORED MassEstimator, NOT deps patch 0004 — that is
NUTS-side), default off, to test the F-28 hypothesis that shrinkage
pays when steps don't collapse. GATES: (a) phase-1 + failure-set
{bym2, diamonds, kronecker}: geomean ESS/s > arm C measured SAME-DAY
interleaved, all-chain R-hat < 1.01 on every model (no silent
failures), kidscore gate retained; (b) default-off byte-identity;
ctest. Statistical class throughout. A miss = the mechanism table
(where K landed per model, shrinkage x step interaction) — walnutpie
lane gold either way.

### F-30 pre-registered (BIG SWING 2: state-model rewrite — the loop's structural floor)

Evidence: F-24 residue = "recursion structure + state model = a
rewrite, not a lever". The lean loop still allocates/indexes per-depth
state via vectors; the swing: FLAT arena-resident tree state (one
preallocated block, tree nodes as indices, explicit stack instead of
recursion, zero per-transition allocation, no per-depth indirection).
Charter, branch fortk/f30-statearena off f24-loopfusion (new worktree).
FP order changes => statistical class. GATES: (a) statistical
equivalence vs f24 (3 seeds, ESS/draw parity, R-hat < 1.01, div not
worse); (b) full-run Ir geomean (esnc-class 5) >= 1.45x vs STOCK loop
(f24 is 1.360x; the state arena targets the remaining loop-self
share) — plus attribution proving the loop-self pool shrank; (c)
default-off (--lean-arena or fold into --lean behind a second flag,
state which) + ctest; (d) ESS/s informational. Honest floor: if the
gradient-bound models cap the geomean below 1.45x regardless, the
verdict names the true ceiling arithmetic (as F-22 did).

### F-31 pre-registered (BIG SWING 3: batch endgame — --fits on lean + embedded stanc)

Evidence: F-26 — --fits drives stock run_nuts_chains (recorded next
item); F-14 — warm-CLI bottleneck = stanc SUBPROCESS 20 ms/fit; the
stanc_embed.o path exists (arch map; F-13's opam switch f13 survives
on this box). Charter, branch fortk/f31-batchend off f26-capstone:
(i) --fits drives the LEAN loop; (ii) build stanc_embed.o (opam f13
switch; tools/stanc_embed/build.sh) and wire the tool to the embedded
compiler (kill the subprocess); (iii) per-fit telemetry. GATES: (a)
--fits draws (lean) statistically equivalent to --fits stock-loop per-
fit arms (3 seeds, ESS/draw parity — the lean loop is F-24 statistical
class anyway); (b) fits/hour: esnc >= 3.5M and blr >= 1.3M (F-26: 2.6M/
956k; the subprocess kill + lean should compound ~1.3-1.5x) — busy-box
wall labeled, per-fit compile+sample decomposition reported; (c)
default paths byte-identical (no --fits / no embed env => unchanged);
ctest. If embed proves fragile, ship (i) alone with honest numbers.

### INCIDENT + RECOVERY (2026-08-29 ~23:00, parent-recorded)

external/ PARTIALLY WIPED (cause unknown — NOT parent or lane agents;
hit the user's own other-lane assets too: cmdstan, walnutpie,
posteriordb checkouts + tracked research .md files) and ALL
bench/fortk_* raw dirs deleted. SURVIVED: logs/ (complete evidence of
record), WORKLOG, models/ + data/, harness/, external/stanli's GIT
STORE with every branch, stanli-pr-waln @ 7f4f241, /tmp pinned
worktree + review checkout, ~/.cmdstan (A-arm), ~/.opam (f13 switch).
Every code artifact is recoverable from the pushed branches + local
store (the publishing round is why this is an incident, not a
catastrophe). Permanently lost: raw bench campaign dirs (logged
numbers stand on the .md evidence; regenerable by re-running),
in-flight uncommitted edits (F-29's survived in pr-waln pending check;
F-30/F-31 redone from their surviving logs). Recovery: F-29 owns base
(fetch.sh deps re-fetch, pristine stan), siblings re-add worktrees
serialized; F-31 additionally re-clones the stanc3 fork for the embed.
Tracked apin .md files restored via git restore.

CORRECTION (2026-08-29 ~23:40, F-31 direct observation): the earlier
incident entry's claim "external/stanli's GIT STORE survived with every
branch" was WRONG — the store was fully deleted at ~22:56. The
external/stanli present afterward is a sibling agent's 22:59 re-clone
(main @ 33f79de, all ORIGIN branches; origin/fortk/f26-capstone =
70fd71a verified). Consequences: (1) recovery rests on the PUSHED
branches, not a local store — the publishing round is the single point
that made the lane survivable; (2) in-flight UNPUSHED branch objects
died with the store (f29-adaptiveK, f30-statearena, f31-batchend
originals) — f29's edits survive as plain files in the orphaned
pr-waln directory (salvage by diff vs a fresh f21-retune checkout);
f30/f31 redo from their surviving logs; (3) the old worktree
directories' .git linkages are dead — no git operations inside them.
Recovery topology updated: F-29 owns shared deps (serving F-29+F-30);
F-31 PRIVATE deps inside its own worktree (zero shared-state
contention); stanc3 5b824ee rebuilds from F-31's surviving
/tmp/f31-stage/stanc3-src (no network needed).

### PAUSE (2026-08-30 ~05:40): all lanes on the shared 5h usage limit

F-29/F-30/F-31 (and F-30's resume) died simultaneously at the limit;
reset 07:16:43. Recovery state at death: F-29 REBUILT (pr-waln binary
up, branch fortk/f29-adaptiveK, md5 gate pending); F-30 mid-build (85
objects; parent continues the build in the idle window — patches
0001-0003 applied to the shared deps/stan, safe: F-29's build complete
and patch-independent, F-31 private-deps); F-31 in setup (scripts
rewritten, stanc3 staging verified at 5b824ee, /tmp/f31-stage marker;
private deps + build pending). Relaunch scheduled post-reset via the
07:25 automation; all resume charters point at the surviving logs.

### F-30 VERDICT (2026-08-30; log logs/fortk-f30.md; branch fortk/f30-statearena @ e5e4fce, --lean-arena default-off, NOT pushed; insurance bundle /tmp/f30-stage/; ctest 69/69; post-incident execution)

GATES: (a) PASS BY IDENTITY — 36/36 cells md5-identical lean-arena ==
lean (the declared statistical class never engaged: RNG sites + FP
arithmetic verbatim, only two structural deltas, each with a proven
invariant: dead-seed copy_pt dropped; rho zero passes deleted via
single-write-on-valid-return). (b) NOT MET: full-run Ir geomean 1.427x
vs the 1.45x bar (f24 1.360x; arena = +4.9%). (c) default + --lean-
alone byte-identical to the saved f24 binary; ctest 69/69. (d) ESS/s
brackets Ir 1.050 (noisy, sibling-concurrent).

ATTRIBUTION: loop-self pool shrank only 3.7-8.4% per model — the wins
landed as designed (kidscore memset -616k Ir, memcpy -75..-536k,
build_tree clones -4%) but the pool was SMALLER than the F-24 residue
hypothesis claimed. HYPOTHESIS REFUTED (the valuable outcome): post-f24
loop-self is ~90% verbatim sweep arithmetic + per-grad executor
packing — NOT layout/recursion overhead. STRUCTURAL CEILING (zero
loop-self): geomean 2.145x (esnc 3.29, esc 3.26, blr 1.89, logmesq
1.91, kidscore 1.17) — the class is NOT capped; only kidscore is
kernel-bound; the remaining 1.5x lives in sweep arithmetic and the
gradient-call boundary, which no layout rewrite can reach.

Lane incidents fixed in place: predecessor script bugs (Ir-extraction
sed truncation, region-cache prewarm race, two parser bugs). Shared
deps/stan left pristine for F-29.

### F-31 VERDICT (2026-08-30; log logs/fortk-f31.md; branch fortk/f31-batchend @ 58b8915 (8505a82+fix), NOT pushed; bundle /tmp/f31-stage/; ctest 69/69; post-incident execution)

GATES: (a) PASS — --fits --lean per-fit draws statistically equivalent
to stock (3 seeds; ESS geomean lean/stock 1.05-1.12x; R-hat lean <=
stock in 5/6; the R-hat<1.01 form is unattainable in EITHER arm at the
batch's 200+200 shape — stock itself 1.016-1.144 on blr; equivalence-
vs-stock is the operative reading, caveat recorded). (b) MISS AS
WRITTEN — esnc 2.93M < 3.5M (84%), blr 1.05M < 1.3M (81%). MECHANISM
(pre-registration arithmetic error, corrected by measurement): in batch
mode stanc runs ONCE per 200 fits (0.5-1% of wall) so the subprocess
kill buys ~1.0x in batch (stock_emb/stock_sub = 0.98-1.02x) — the 20
ms/fit cost was the PER-FIT CLI class, not --fits; and the lean batch
gain (1.222x/1.312x) reproduces the F-26 campaign L/C ratio exactly
(third composition validation). The 3.5M bar assumed both effects
compound ~1.34-1.36x; they don't. (c) PASS fully — default-arm md5s =
recorded F-26 values; embed-arm md5s IDENTICAL through the embedded
compiler; fallback chain byte-identical.

EMBED SHIPPED FIRST TRY (~35 min vs the 90-min guard): stanc_embed.o
@ 5b824ee on opam f13 from the pinned staging clone; stanc_mode=
embedded; hits the subprocess-compiled region cache MIR-identically;
value = the 1-fit CLI stanc stage 19-25 -> 14 ms + no external binary
dependency (the browser/embed vision of the arch map).

Batch numbers (loaded box 1.5-2.0, labeled; trainer-SMT contamination
caught + superseded): lean_emb 1,046,578 (blr) / 2,929,641 (esnc)
fits/h; stock_sub 0.90x/0.85x F-26's quiet day = the labeled load tax.
Measurement lessons: taskset 2-5 = 2 physical cores (SMT pairs) — a
wandering 1-core job lands directly on it; pin PSR per cell.

### F-32 pre-registered (the gradient-call boundary — F-30's pointer made concrete)

F-30 refuted the layout hypothesis and named the remaining loop-self:
~90% sweep arithmetic + PER-GRAD EXECUTOR PACKING. The packing is
measurable and partially removable: the lean loop calls
Executor::gradient() per eval (adjoint memset + dispatch vectors +
result harvest + grad memcpy); single-region graphs have the F-4b
DIRECT path (fortk_grad_direct: 20.1 vs 34.8 ns class on esnc, PROVEN
bitwise vs the executor — identical doubles). Charter, branch
fortk/f32-directseam off f30-statearena:
- ATTRIBUTE first: the executor-packing share of lean-loop per-eval Ir
  on esnc (single-region) vs hier_2pl (multi-region) — name it.
- INTEGRATE: the lean loop's seam calls fortk_grad_direct when the
  graph is single-region (the --fits path inherits automatically);
  multi-region graphs unchanged. Gate (a) draws BITWISE vs f30's
  --lean-arena on esnc/blr (the direct path returns identical doubles
  — F-4b's proof) + ctest.
- Gate (b): full-run Ir geomean (esnc-class 5) >= 1.50x vs stock loop
  (f30 sits 1.427x; if attribution shows the packing share cannot
  carry +5%, the honest attribution verdict is the outcome — never
  fudge).
- (c) default paths byte-identity; (d) ESS/s informational.

### F-33 pre-registered (FINAL INTEGRATION + closing tables for collection)

At the cutoff (F-29/F-32 resolved or hour-6, whichever first): merge
all SHIPPED layers (f29-if-landed, f30-arena, f31-batch, f32-direct)
into one branch off the f-line; gates: build + ctest + verify spots +
default-path byte-identity; then the closing campaign — phase-1 6 +
phase-2 8 models, arms A (cmdstan) + C (PR-stack) + L (integration,
--lean --lean-arena + direct seam + walnuts-if-landed), 3 reps
interleaved, F-8/F-18 conventions; report per-model + geomean ESS/s
(the session-final number), full-run Ir ratios, and the batch spot.
Push all branches + refresh PR bodies if materiality met. The
collection-day deliverable: one branch, one table, everything pushed.

### F-32 VERDICT (2026-08-30; log logs/fortk-f32.md; branch fortk/f32-directseam @ 291e4ef, NOT pushed beyond backup, bundle /tmp/f32-stage/; ctest 69/69 twice)

GATE (b) MET: full-run Ir geomean stock/direct = **1.557x** >= 1.50
(esnc 1.834x, esc 1.789x, blr 1.542x, logmesq 1.552x, kidscore 1.164x;
f30 was 1.427x; arena->direct adds 1.095x — MORE than the packing-only
1.071x because single-scope direct codegen also drops the region-ABI
spill/round-trip, exactly as F-4b's ns ladder ordered). GATE (a) PASS:
bitwise vs --lean-arena on every model (hier_2pl correctly REFUSED the
seam — 2 regions, path unchanged, 48,508 exec evals; packing residual
there 0.63%). Attribution FIRST: packing shares 1.5-10.2% on the five
direct-eligible models; ceiling predicted 1.528 — built and beaten.
(c) default byte-identity all forms; GRAD_COUNTER 3785 -> 1 (drop ==
direct evals — counter arithmetic exact). (d) ESS/s wall 1.084x
(bitwise draws, pure wall, F-29-concurrent, labeled).

TOOLING LESSON (F-33 must heed): linker ICF folds identical cg-wrapper
bodies to one address (correct runs, EMPTY profiles) — anti-ICF volatile
markers required on any identical --cg wrapper pair. POINTER (next win):
hier_2pl's dominant per-run cost is its REGION BWD's own la-memset =
31.2% of the whole run — the F-25 first-write-conversion pattern applied
to hier_2pl's region emission is the remaining big single-model lever.

### F-34 pre-registered (hier_2pl region-emitter: la-memset elimination + multi-pass on its region bodies)

F-32 attribution: hier_2pl region bwd's la-memset 31.2% of run; vecmath
33.1%; executor packing 0.63% (call seam done). Charter, branch
fortk/f34-hiermemset off fortk/f25-kernelfloor (the emitter home):
apply the F-25 patterns to hier_2pl's region emission — first-write
conversion for the bwd la arrays (converted classes only, uninstrumented
opcodes pre-marked keep-zeros — the exact F-25 discipline), plus
multi-pass where its fwd/bwd loops are scalar-blocked. GATES: (a)
hier_2pl verify 64 pts < 1e-9 vs unfused executor (unchanged oracle) +
no-regression spots (kidscore 1.4e-15-class, blr byte-identical, esnc
bitwise); (b) hier_2pl Ir/grad improvement reported (primary) + census
ratio row; (c) ctest + default-path byte-identity for untouched models;
(d) ESS/s informational. Region-cache version bump REQUIRED (emitter
output changes). Anti-ICF markers on any new --cg wrappers.

### F-29 VERDICT (2026-08-30; log logs/fortk-f29.md; branch fortk/f29-adaptiveK @ 94ae8d0, no new code needed; apin a43fb9a; ctest 70/70; post-incident execution)

MISS on gate (a) — walnuts does NOT become default. The kill: the
pre-stated rule (late-warmup median trajectory depth -> K) UNDER-READS
heavy-tailed depth distributions — kidscore M_med 4 vs M_mean 11.8-23.6
landed K=2 where F-21's optimum was K=8 (same tail signature esc/
diamonds); K also flips 2x at grid boundaries between chains. Where
the bet hit, adaptive-K == best fixed-K (esnc K4: ESS/draw 1.488,
2.92x C ESS/s; blr K8 == F-21; logmesq 1.38x C). R-hat leg FAIL 7/9;
kidscore FAIL (ESS/draw 0.080 vs C 0.348). Phase-1 ESS/s D/C 1.010x
(noise band 0.744-1.576; the >1 all-9 figure driven by C's td-saturated
cells, not D quality — not claimed).
SHRINKAGE INTERACTION (the F-28 hypothesis): CONFIRMED ON MECHANISM,
REFUTED AS A WIN — walnuts frozen steps stay FLAT under shrinkage
(DL/D geomean 0.787x, some ROSE 2.1x; vs NUTS' 6-32x collapse) but
mixing degrades instead (ESS/draw down 8/9; DL/C ESS/s 0.414x).
Gate (b) PASS: default md5 b1bb391c exact; ctest 70/70.
F-33 charter correctly folds walnuts in only on a pass — the NUTS line
integrates alone. RECORDED NEXT SIGNALS (walnutpie lane, unpursued per
binding grid rule): tail statistic (mean not median) or per-model
pooled depth for K; the shrinkage-flat-steps mechanism stands validated
for any sampler whose step does not derive from the metric.
Incidents: runner externally killed 03:59 — resume-safe markers
recovered all 51 cells; F-30's parent build correctly skipped absent
patches (shared deps verified pristine).

### F-34 VERDICT (2026-08-30; log logs/fortk-f34.md; branch fortk/f34-hiermemset @ ed6362c off f25-kernelfloor, NOT pushed, bundle /tmp/f34-stage/; ctest 69/69)

THE 31.2% MEMSET WAS 99.74% DEAD CELLS — a layout bug in the F-7 obs-
chain fusion's own plumbing: the iadj assignment gave fused-away
producers' outputs (GATHER/SUB/MUL intermediates, 5 x 19200 cells) full
adjoint ranges, but the fused bernoulli bwd writes only the 3 source
slots + head out (single-consumer guarantee => nothing else ever
materializes them). hier_2pl is the ONLY census model with an obs chain
=> why only it showed the symptom. FIX (new pattern, sibling to F-25's
first-write): iadj DEAD-CELL COMPACTION — skip fused-away intermediates
in the iadj assignment; la 96,251 -> 251 cells; memset 770 KB -> 2 KB
per eval. Emitted body identical after la-offset normalization (pure
layout); version v6 -> v7.
NUMBERS: hier_2pl Ir/grad 2,393,522 -> 1,623,696 = **-32.2%**; census
row 2.74 -> **4.04**; full-run 40.18G -> 27.81G = 1.445x Ir; memset
share 31.5% -> 1.0%; bwd self Ir BIT-IDENTICAL (4,418,539,882 both) =
the arithmetic-identity proof in vivo. GATES: hier_2pl verify = the
exact F-25 record; byte-identity 20/20 incl. hier_2pl (esnc/esc/wells/
blr = records); ctest 69/69. ESS/s wall 1.047x (draws 12/12 bitwise).
HONESTY (ERMS caveat quantified): 31.5% of Ir was only ~5% of wall —
ERMS memsets are cheap on hardware vs callgrind's per-byte counting;
the Ir/census wins are real, the ESS/s move is modest by design.
DELIBERATELY NOT: full memset elimination (MVN_CHOL genuinely
accumulates across 33 ops — keep-zeros correct); multi-pass (fwd
already 4-lane/F-25-multi-pass, bwd is a scatter, MVN/LKJ/GEMM len-2/4
— the memset WAS the whole lever).
Incidents handled: SIGBUS from cp-replacing instrument binaries under
the campaign (quarantined, rerun byte-identical); rc=3 CSV-reject after
sampling (outdir) — profiles intact, twin-checked to 2e-7.

### F-33 VERDICT — THE CLOSING TABLE (2026-08-30; log logs/fortk-f33.md; branch fortk/f33-final @ 95d9780 (merge 030eb79 + wiring), NOT pushed beyond backup, bundle /tmp/f33-stage/; ctest 69/69; all oracles digit-identical)

Merge reunited the split arcs (f31's base carried the F-25 v6 kernel
line the f30/f32 lineage lacked — post-incident fork healed); zero
textual conflicts; semantic audit clean; seam needed ZERO wiring (the
file-scope pointer — F-32's design). Default byte-identity through the
EMBEDDED compiler; lean ladder bitwise (lean==arena==direct); anti-ICF
markers verified.

CLOSING NUMBERS (3 reps, interleaved, load labeled):
- Phase-1 geomean ESS/s vs CmdStan: **L/A 9.21x** (ex-pilots 9.92x;
  C/A 7.05x; F-26 was 7.53/5.92). Per-model L/A: esc 22.45x, pilots
  6.35x(mirage cell), kidscore 10.76x, esnc 9.32x, blr 6.14x, logmesq
  6.94x. All-14: L/A 5.05x, C/A 4.64x (multi-region heavies 1.08-1.13
  L/C — seam correctly refused; kronecker gives wall back at 7000 dims
  0.91x; diamonds 0.89x).
- Full-run Ir stock/direct geomean **1.647x** (F-32 1.557x; the gain =
  v6 kernel reunion on logmesq/kidscore).
- Batch: esnc **3,542,570 fits/h CLEARS the 3.5M gate F-31 missed**
  (pure composition: arena+seam on the lean-fits path); blr 1,299,226
  = 99.9% of its bar.
- Honest read: 7.53 -> 9.21 tracks Ir 1.422 -> 1.647 at every level;
  every oracle digit-identical; the remaining ~1.30x to F-30's 2.145x
  ceiling is region-body cost — F-34 shipped -32% hier_2pl Ir the same
  day and is the natural next merge.
- Note: F-30/F-32 measured on the v4 emitter (arc split) — their
  absolutes UNDERSTATE the reunited stack.

### F-35 VERDICT — FINAL COMPOSITION (2026-08-30; log logs/fortk-f35.md; fortk/f33-final @ 33bdc8b = 95d9780 + merge of f34, PUSHED; ctest 69/69)

Auto-merged zero conflicts (f34's zones disjoint); emitter v7 verified;
all f33 markers present. GATES: verify spots digit-identical (hier_2pl
= the exact F-34 record; kronecker 0.0/0.0); default-path byte-identity
through the EMBEDDED compiler incl. hier_2pl's new v7 ref 26a46aff;
lean ladder bitwise (arena==lean==direct; 3785->1). CLOSING SPOTS:
draws 96/96 md5-identical to F-33's records (v7 bit-invisible through
the full 4-chain pipeline; v6-twin attribution airtight — twin
reproduced F-33's binary to wrapper addresses). hier_2pl Ir stock
1.453x / lean 1.455x (25.38G lean = lowest on any line); wall 1.036/
1.057x (the ERMS caveat, quantified on the composed stack); composed
L/C 1.09x (F-33: 1.08). esnc control exact (Ir +0.018-0.17%, s/d
1.831). Surprise: composed stack runs hier_2pl ~4% cheaper in Ir than
f34's own line (deps-patch interaction, this pairing only).

=== SESSION CLOSED (pending user collection) ===
ONE BRANCH carries everything: fortk/f33-final @ 33bdc8b — fused-JIT
tiers + vectorized kernels (v7) + base_nuts loop package + lean driver
(arena + direct seam, warmup-inclusive) + batch --fits + embedded stanc
+ the default-off research knobs (walnuts batch/mult/adaptive-K,
lw-shrink, wexit, delta/depth). FINAL NUMBERS: phase-1 ESS/s geomean
L/A 9.21x (ex-pilots 9.92x; session arc 3.15 -> 9.21); all-14 5.05x;
full-run Ir stock/direct 1.647x (esnc-class), hier_2pl 1.453x; batch
3.54M/1.30M fits/h; corpus census Ir 2.74x (pre-v7) -> ~2.9x-class
with hier_2pl 4.04. Every layer gated; bit-identity preserved through
nine merges; four honest refusals/non-transfers documented with
mechanisms; three composition validations; one upstream bug
independently confirmed; one own claim retracted loudly.

### FINAL AUDIT (2026-08-30, pre-contraction; user request)

- ALL fortk work is on the fork: 19 branches verified on origin (the
  last gap, f29-adaptiveK @ 94ae8d0, pushed in this audit); 7 draft
  PRs current; apin ledger pushed through 0199e82. Zero dirty trees.
- The pre-incident worktrees died with the old store (their branches
  were already on origin — nothing lost); live worktrees: f30/f31/f33/
  f34/pr-waln, all clean and re-anchored to the re-cloned store.
- DELIBERATELY LOCAL (user decisions, not loose ends): apin's
  external/{cmdstan,posteriordb,walnutpie} gitlink deletions from the
  incident (restore = their walnutpie lane's assets); bench/fortk_f*
  raw dirs (logs are the pushed evidence of record); /tmp bundles
  (redundant now that all branches are on origin); the bernoulli_logit
  issue draft (no-upstream rule stands).
