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
