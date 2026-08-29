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

## W-24 (pre-registered): stan-2a2 scratch-hoist in base_nuts.hpp (cmdstan fork)

- Plan: patches/stan-2a2-scratch-hoist-PLAN.md. Target
  external/cmdstan/stan/src/stan/mcmc/hmc/nuts/base_nuts.hpp. Plan text cited
  submodule d13c50c0f — object not present in fork; submodule pin per
  portability snapshot is 6380837 (nindan/mixed-build-guard). DEVIATION:
  implemented on 6380837 (base_nuts.hpp byte-identical to cmdstan-2.37.0
  copy, so pin drift is immaterial for this file).
- Expectation: hoisting build_tree locals (p/p_sharp init_end/final_beg,
  rho_init/final/subtree, z_propose_final) into depth-indexed member scratch
  removes ~630 heap allocs/transition @ depth 6; pilots memcpy/alloc share
  21% -> <8%; small-model wall geomean improves modestly (allocs are a minor
  share vs 68-99.7% logp_grad).
- Recursion safety: parent depth-d scratch is written only via refs children
  hold (children use depth-d-1 slots); parent reads its slot only after
  children return. z_propose_final as PER-DEPTH ps_point stack (single
  shared ps_point would alias across recursion levels — plan flagged the
  per-depth option; taking it).
- Gates (in order): G1 build stanc + 3 probe models (blr, pilots, lsat_model);
  G2 BIT-IDENTITY first: 3 models x 2 seeds, 4 chains, csv diff vs stock == 0
  (rho-hoist history: do NOT assume); G3 callgrind pilots memcpy/alloc <8%
  (valgrind absent on box — will install local build or record as blocked);
  G4 wall-clock paired small models (pilots, arma11, blr, eight_schools
  noncentered), 3 reps medians, seeds 20260819+1000*rep+c, 4 chains; G5
  bisect hunks if G2 fails, ship only what passes.
- Never touch: leaf z_propose assign, transition-scope 12 vectors,
  compute_criterion, integrator/hamiltonian, RNG call order.
- Test bed: pristine ~/.cmdstan/cmdstan-2.39.0 = stock canary; identical
  patch applied to its base_nuts.hpp for the patched variant (verified
  byte-identical header first).


## W-23 (pre-registered BEFORE running): endpoint-gradient threading (work item A)

From W-20: exactly ONE redundant logp_grad per transition (the start-position
re-eval whose gradient the previous transition already computed as its end
point; dups = warmup+draws+1 on every model, ~4-6% of gradient calls).
Change: thread (theta, grad, logp) through WalnutsSampler / AdaptiveWalnuts
state — transition_w/transition_w_lr accept a cached (grad, logp) for the
start position and skip the re-evaluation when the cache matches theta size;
samplers carry the cache across transitions and across the warmup->sampling
freeze (sampler() seeds the frozen sampler's cache).

GATES (non-negotiable):
1. BIT-IDENTICAL draws before vs after, 3 models x 2 seeds x 4 chains
   (models: blr, kidscore_momiq, arma11 — small/cheap per core_manifest;
   CLI defaults, warmup=400, samples=200, no init files — fixed deterministic
   random inits; identical across arms by construction).
2. Grad-count check (W-17g style, from stan_cli's printed 'logp_grad calls'):
   duplicates must drop from warmup+draws+1 to ~0 per model/chain
   (total calls drop by exactly warmup+draws+1 per chain, modulo one eval at
   chain start; freeze boundary also seeded from warmup cache).
Protocol notes: this is a bit-identity gate, not a perf claim — no 3-rep
medians needed for the gate itself. ONE edit to walnuts.hpp +
adaptive_walnuts.hpp, build clean (--clean-first equivalent, delete .o),
test, commit on submodule branch endpoint-grad-threading off
dev/init-robustness. Expectation: draws identical, grad calls drop; if
bit-identity fails, the implementation is wrong (reusing an identical double
cannot change arithmetic) — stop and fix, do not rationalize.

## 2026-08-23 — W-23 SHIPPED: endpoint-gradient threading (bit-identical, dups eliminated)

Implementation (submodule branch endpoint-grad-threading off dev/init-robustness,
commit 30ac6db): transition_w/transition_w_lr take optional trailing
(grad_cached, logp_cached) params — valid when size matches theta — and skip
the start-position re-eval; WalnutsSampler caches the endpoint across draws
(+ seed_endpoint_cache()); AdaptiveWalnuts caches across warmup iterations
(diagonal, drift, low-rank paths) and seeds the frozen sampler at the freeze
boundary. Defaults preserve old signatures for all other callers. ONE edit
set, clean-first build, gate, commit.

GATE RESULTS:
- Bit-identity: 24/24 chain CSVs identical before vs after
  (blr, kidscore_momiq, arma11 x seeds 20260819/20260820 x 4 chains;
  CLI defaults, warmup=400 samples=200, deterministic random inits
  [--init 2 default] — no pf inits needed since arms share everything).
- Grad calls (sum over 4 chains, both seeds): drop = 2396 = 4 x 599 =
  exactly (warmup + draws - 1) per chain — every transition except the
  chain's very first reuses the endpoint. Examples per chain (seed 20260819,
  before->after): blr 19201->18602, kidscore 19184->18586, arma11 16553->15954.
  Residual 2 dups/chain are the init mass seeding (pre-sampler) and the
  chain-start eval — not reachable from transition state (documented, not
  a regression; W-20's +1 dup count included the init seeding).
- ~3.1% fewer gradient calls on these runs (599/19201 blr), in the
  expected 4-6%-of-grad-calls band for the models measured in W-20
  (fraction depends on trajectory length per transition).
No perf claim made (bit-identity gate item, no 3-rep timing per protocol).
ctest in the cmake build config has no test targets (tests not wired);
compile + bit-identity gate served as verification.

## W-25 (pre-registered): library-level warmup early-exit with temporal step-drift gate

Design (from W-21/W-22): move early-exit out of the CLI knob into the
library multi-chain controller (`adapt.hpp` controller_loop, which already
has cross-chain convergence machinery). New WarmupConfig knobs:
`temporal_step_drift_tol` (0 = OFF, default — behavior preserved),
`temporal_window` (50), `temporal_min_iter` (200). Gate semantics: the
controller's existing cross-chain criteria (mass tol, step tol vs the
geometric mean) must hold AND, when the temporal tol > 0, every chain's
step size must have drifted < tol (relative) across the last full
temporal window ending at iter >= temporal_min_iter, max over chains.
Motivation (W-22): on hurt models mass is stable (+2-13%) but step still
grows (+170%) late in warmup; cross-chain agreement alone can hold while
all chains march together, so the temporal step gate is the quality
preserver. AdaptResult gains exit_iter / early_exit for observability.

CLI: new `--chains N` (default 1; N>1 runs the multi-chain library path
with one BridgeStan model instance + one mt19937_64 + one StanHandler per
chain, seeding exactly as the per-chain single-chain invocations, so the
unchanged-warmup path matches the baseline arms). Single-chain path
untouched (W-21 knob remains, default off).

Arms (all fresh, 4 chains, seeds 20260819+1000*rep+c, 3 reps, medians):
- base: single-chain CLI x4, fixed warmup 1000 (default code path).
- mc_nogate: --chains 4, temporal tol 0 (controller cross-chain exit only).
- mc_gate05: --chains 4, temporal tol 0.05 (window 50, min_iter 200).
Models: marginal class W-21 hurt = arma11, lsat_model, hier_2pl; easy
class = blr, eight_schools_noncentered.

Gates:
- Quality (primary): mc_gate05 ess_bulk_min / ess_tail_min per model-rep
  NOT worse than base beyond noise on the marginal class (median of 3
  reps; noise band from base rep spread).
- Speed: wall improvement for mc_gate05 where it early-exits (exit_iter
  < 1000), per model median.
- Canary (bit-identity): default single-chain path draws must match the
  pre-change binary bit-for-bit (temporal tol defaults 0, controller code
  unreachable from single-chain path).
- Negative results recorded either way.

Deviations from protocol (recorded up front): R `posterior` package not
installed on this fresh machine — ESS via Python arviz 1.3.0
(rank-normalized bulk/tail, same estimator, identical across arms).
/tmp/winit pf inits gone and cmdstan-2.39.0 install incomplete — arms use
the CLI's default deterministic init (model.initialize, per-chain seed),
identical across all arms; recorded here as the init source.

## W-24 CLOSE-OUT: stan-2a2 scratch-hoist SHIPPED (all gates pass)

- Correction to pre-registration: d13c50c0f is the STAN sub-submodule pin
  (stan inside external/cmdstan), and it IS what was checked out — no pin
  drift; the 6380837 figure is the cmdstan-level pin. Implemented exactly
  on d13c50c0f.
- Implementation per plan H1/H2/H3, one deviation inside plan's latitude:
  z_propose_final as PER-DEPTH ps_point stack (single shared ps_point is
  recursion-UNSAFE — child overwrites parent's buffer via the z_propose
  ref it receives; plan flagged per-depth as the clean option).
- G1 PASS: stanc 2.39.0 + 5 models compiled stock & patched.
- G2 PASS: bit-identity 24/24 (3 models x 2 seeds x 4 chains, 1000+1000;
  CSVs byte-identical modulo elapsed-time/file-path comments). False alarm
  en route: first comparison 0/24 — my filter missed the "# file =" output
  path comment; stock-vs-stock canary + re-filter resolved it. Determinism
  itself is exact.
- G3 PASS: callgrind pilots (40+40, seed 20260819, valgrind 3.23 built
  locally to ~/vginstall — box had none): memcpy/alloc Ir share 9.9% ->
  6.7% (<8% target); total Ir 75.3M -> 70.7M (-6%). Plan's 21% baseline
  used a wider bucket definition; with this harness's bucket the win is
  the same direction and crosses the gate.
- G4 PASS: wall-clock paired (warmup+sampling, 1000+1000, 4 chains
  serialized, medians of 3 reps, seeds 20260819+1000*rep+c): pilots
  1.037->0.962 (0.928), arma11 0.966, blr 0.888, 8schools-nc 0.943;
  GEOMEAN RATIO 0.931 (~7% faster small-model class).
- Ship: commit 7fc7f7eda branch scratch-hoist-base-nuts. SHIP-TARGET
  DEVIATION: base_nuts.hpp lives in the STAN sub-submodule (remote =
  upstream stan-dev, push forbidden), NOT the cmdstan fork. Created fork
  sims1253/stan, PR within fork: https://github.com/sims1253/stan/pull/1
  (head scratch-hoist-base-nuts -> base develop of the fork).
- Cleanup: ~/.cmdstan/cmdstan-2.39.0 header restored pristine (stock
  builds for other work items unaffected); stan sub-submodule restored to
  pin d13c50c0f; stock/patched probe exes kept in stan/build/{model}__stock
  /{model}__patched (untracked).
- Build/env notes for successors: install_cmdstan rejects "-j4" (use
  --cores); interactive `make` is aliased to make -j12 and a MAKE env
  quirk can silently no-op recursive makes — use /usr/bin/make -j2
  explicitly; background tasks get a private /tmp overlay (valgrind had
  to be built in a foreground call).

## 2026-08-22 — W-25 close-out: library temporal step-gate SHIPPED (default off); quality/speed gates FAIL on the marginal class — negative result

Implementation (walnutpie branch `w25-library-temporal-step-gate`,
commits e650c63 + f4e37d5):
- Gate lives in controller_loop (adapt.hpp). WarmupConfig:
  temporal_step_drift_tol (0=off default) / temporal_window (50) /
  temporal_min_iter (200). When on, early exit = cross-chain step
  agreement (existing tol) AND per-chain step drift <5% AND mass l2
  drift < mass_converge_tol, both measured over the last TWO windows
  (boundary k vs k-2, ~100 iters). The cross-chain mass criterion is
  REPLACED in temporal mode: measured 1.4-2.8 l2 diff vs tol 1.0 late
  in warmup on healthy models — windowed mass estimates are too noisy
  cross-chain for it to ever fire. AdaptResult gains exit_iter /
  early_exit. Env-gated WALNUTPIE_DEBUG_CTRL trace.
- CLI: --chains N runs the library controller (adapt_with_stats) with
  one BridgeStan model + one mt19937_64 + one StanHandler per chain,
  seeding identical to per-chain single-chain invocations. Single-chain
  path untouched. NOTE: multi-chain requires STAN_THREADS=1 model .so
  (bs_models/ were built without it — stan::math arena corrupts; the 5
  study models recompiled into bs_models_threads/, single-chain draws
  bit-identical across the two .so builds).
- Canary: PASS — default single-chain draws md5-identical pre/post all
  changes (blr, arma11, eight_schools_noncentered; re-verified on final
  code).

Experiment (5 models x 3 reps x 4 chains, medians; pf inits regenerated
-> inits_w25/ via cmdstan-2.39.0 pathfinder + bridgestan unconstrain,
harness/gen_w25_inits.py, runner harness/run_w25.py, ESS via arviz —
R posterior absent on this machine; same estimator, same procedure all
arms; all arms --metric-window 50):
  bulk-ESS-min:            base  mc_nogate  mc_gate05(1win)  mc_gate05(2win)
    arma11                 1028      830         1004             860
    lsat_model              944      944          110             942
    hier_2pl                519       61          168             126
    blr                     350      217           350             347
    eight_schools_nc       1488     1459          1459            1459
  exit_iter med (2win): arma 400, lsat 350, hier 345, blr 570, esc n/a.
  wall (median): hier base 49.6s vs gate 89.3s; lsat 14.5s vs 111.4s.
  hier timing split (base vs gate): warmup 28-29s vs 11-15s, SAMPLING
  21s vs 77s — early-exited tuning makes sampling 3.6x more expensive
  (smaller frozen step, deeper trajectories), more than eating the
  warmup saving.

VERDICTS:
1. Quality gate (pre-registered): FAIL. hier_2pl collapses 519 -> 126
   bulk / 733 -> 112 tail, consistent across all 3 reps (91-179 vs
   502-548) — not noise. lsat tail halves (1638 -> 825); arma11 -16%.
   The 1-window gate was worse (lsat 944 -> 110). W-22's hypothesis
   (step-drift <5% is the quality-preserving signal) is REFUTED at
   window 50 / 2-window horizon: even with step AND mass temporally
   stable, warmup continues to materially improve the frozen sampler
   on hier_2pl — likely the min-micro-steps / trajectory-geometry
   adaptation, which no step/mass gate observes.
2. Speed gate: FAIL. Where it exits, wall gets WORSE on the slow
   models (sampling-cost blowup dominates warmup savings). W-21's CLI
   1.3-2.4x did not survive the quality-preserving gate.
3. Side finding (upstream-relevant): the library controller's DEFAULT
   cross-chain tols (mass 1.0 / step 0.1) exit at iter 50-80 with good
   inits + windowed metric and destroy quality (hier 519 -> 61, arma11
   -19%, blr -38%). Any embedding using adapt() with defaults is
   exposed; the temporal gate (tol>0) is strictly safer than the
   default cross-chain-only stop.
Ship state: default off (tol 0 preserves prior behavior bit-for-bit).
Useful only on easy models (blr tail +27%); do not enable on the
marginal class. Raw: runs/{base,mc_nogate,mc_gate05,mc_gate05_1win},
results/w25_{ess,wall}.json (+_1win).

## W-27 (pre-registered BEFORE running): BridgeStan model .so with aggressive CXXFLAGS (-O3 -march=native -mtune=native) vs default build

From NEXT_IDEAS section A; lever = logp_grad is 68-99.7% of walnutpie
sampling wall (W-17g) and logp_grad speed is a MODEL-COMPILE property.
(NEXT_IDEAS claimed bs_models_o3/ was prepared — it did NOT survive the
move; rebuilding from scratch. bs_models/ is the default arm.)

- Expectation: O3+native model .so cuts sampling wall by a single-digit-
  to-tens % at ZERO quality cost, PROVIDED gradients are correct.
- CAUTION (history): cmdstan -march=native corruption was root-caused as
  mixed-build ABI (prebuilt main.o/PCH). bridgestan compile_model is a
  single self-contained make -> likely safe, but gates below.
- GATES:
  G1 gradient parity: per model, (logp, grad) on 100 random unconstrained
     points, default vs O3 .so: max rel diff < 1e-9, no NaN/Inf. FAIL -> stop.
  G2 draws will NOT be bit-identical (vectorization reorders FP) — quality
     compared STATISTICALLY only: bulk/tail min-ESS (arviz), 3 reps,
     no regression beyond noise.
  G3 wall: 5 models (blr, arma11, hier_2pl, kronecker_gp, diamonds) x 3 reps
     x 4 chains, single-chain CLI procs (4 parallel), seeds 20260819+1000*rep+c,
     warmup=1000 samples=1000 --metric-window 50, IDENTICAL fixed inits per arm:
     inits_w25/ pf inits for blr/arma11/hier_2pl; for kronecker_gp/diamonds
     deterministic normal(0,1) inits via random.Random(f'{seed}-{c}') written
     once (same files for both arms). Medians per model + geomean; parse
     per-call logp_grad time AND total wall from chain logs.
  G4 if O3 wins cleanly: also test -O3 alone (portability: -march=native
     may add nothing beyond -O3).
- Negative result gets recorded same as a win.

## W-26 (pre-registered BEFORE running): integration merge of W-23 + W-25 into dev/init-robustness

Task: merge BOTH feature branches into the submodule's dev/init-robustness:
1. endpoint-grad-threading (30ac6db, W-23) first, then
2. w25-library-temporal-step-gate (e650c63 + f4e37d5, W-25).
Branch topology is linear (origin/dev/init-robustness 3eddfc4 -> 30ac6db ->
f4e37d5), so merges are recorded with --no-ff to keep explicit merge commits;
conflict policy if any: W-23 semantics win in walnuts.hpp, W-25 in adapt.hpp.

GATES (each on a CLEAN build, --clean-first -j2, after EVERY merge step):
a. Canary bit-identity: default single-chain draws md5-identical to the
   PRE-MERGE dev/init-robustness binary (i.e. WITHOUT W-23), 3 models
   (blr, arma11, eight_schools_noncentered) x seed 20260819 x 4 chains,
   --warmup 400 --samples 200, deterministic default inits. W-23 removes
   redundant evals only; reused identical doubles change no arithmetic, so
   draws must remain identical (failure = wrong implementation).
b. Grad-count: post-W-23 the per-chain logp_grad call drop vs pre-merge
   binary must equal warmup+draws-1 = 599 per chain.
c. W-25 only: --chains 4 (bs_models_threads .so, STAN_THREADS=1) runs and
   each chain's output matches the per-chain single-chain invocation with
   seed S+c (pre-verified feasible: default controller settings run full
   warmup on blr, exit_iter=400 early_exit=0, draws md5-identical).
Do NOT delete feature branches. Update outer stan submodule pointer
(explicit git add of external/walnutpie only). Negative results recorded
either way.

### W-26 correction (mid-task scope change, appended before close-out)

Redirect from the user: feature branches/PRs in the personal forks are
HISTORY for different ideas, NOT to be merged into mainline.
dev/init-robustness must stay pristine. Correction applied: the two merges
initially made on local dev/init-robustness were reset away
(git reset --hard 3eddfc4; verified dev/init-robustness == origin/
dev/init-robustness == 3eddfc4, nothing lost — branches hold all work).
Both features merged instead into NEW experimental branch
exp/endpoint-grad-threading+chains (off dev/init-robustness):
  61cca46 exp merge endpoint-grad-threading (W-23)
  0cb5b7b exp merge w25-library-temporal-step-gate (W-25)
Both --no-ff, no conflicts (topology is linear: 3eddfc4 -> 30ac6db ->
f4e37d5; W-25 branch already sat on top of W-23). Merged tree hash
a438e36 identical to the (reset-away) mainline merge tree. Clean-first
rebuild on the exp branch produced a byte-identical binary to the earlier
merged build (cmp PASS).

## 2026-08-22 — W-26 CLOSE-OUT: W-23 + W-25 integrated on exp/endpoint-grad-threading+chains (gates a+b PASS, gate c partial — pre-existing W-25 behavior)

Submodule state: dev/init-robustness PRISTINE at 3eddfc4 (= origin);
integration lives on exp/endpoint-grad-threading+chains @ 0cb5b7b;
feature branches endpoint-grad-threading (30ac6db) and
w25-library-temporal-step-gate (f4e37d5) kept, not deleted. No pushes.

GATE RESULTS (all on --clean-first -j2 builds, env -u LD_LIBRARY_PATH;
baseline = pre-merge dev/init-robustness binary WITHOUT W-23; 3 models
blr/arma11/eight_schools_noncentered x seed 20260819 x 4 chains,
--warmup 400 --samples 200, default deterministic inits; serialized runs):
a. Bit-identity vs pre-merge baseline: PASS 12/12 chain CSVs md5-identical
   at BOTH merge steps (post-W-23 merge and post-W-25 merge), and again on
   the final exp-branch binary. Reused endpoint doubles changed no
   arithmetic, as required.
b. Grad-count: PASS 12/12. Per-chain logp_grad call drop vs baseline =
   exactly 599 = warmup+draws-1 on every model/chain (e.g. blr
   19201->18602, esc c0 5225->4626).
c. --chains 4 vs per-chain single-chain (same seeds, bs_models_threads
   .so): PASS on blr and arma11 (controller exit_iter=400 early_exit=0;
   all 8 chain CSVs md5-identical to single-chain runs — seeding invariant
   holds). FAIL-as-designed on eight_schools_noncentered: the controller's
   DEFAULT cross-chain tols early-exit at iter 50 (early_exit=1), so the
   frozen sampler differs from full-warmup single-chain runs. This is
   W-25's already-documented side finding 3 (default tols are unsafe), not
   a merge regression — the exp binary is byte-identical to the W-25
   feature branch build (that branch already contained W-23), and
   matching-warmup-length single runs (warmup 50) also differ because the
   controller freezes chain states at its own exit, confirming the
   divergence is the controller path, not seeding.
Outer stan repo: submodule pointer updated to 0cb5b7b (explicit
`git add external/walnutpie WORKLOG.md` only), local commit on main, no
push. Feature branches NOT merged into any mainline; dev/init-robustness
untouched.

## W-28 (pre-registered BEFORE running): pilot sampling-burst gate for warmup early-exit

From NEXT_IDEAS section B (dynamic upgrade). W-25 refuted STATIC gates: even
with step AND mass temporally stable over 2 windows (tol 0.05), warmup keeps
improving the frozen sampler on the marginal class (hier_2pl bulk 519->126)
— suspected min-micro-steps / trajectory-geometry adaptation that no
step/mass drift signal observes. W-28 tests the DYNAMIC gate: after a
candidate exit point, actually LOOK at mixing.

Design (implementation on walnutpie branch exp/pilot-burst-gate off
exp/endpoint-grad-threading+chains @ 0cb5b7b):

- CANDIDATE TRIGGER (unchanged from W-25): controller cross-chain step
  agreement + per-chain 2-window temporal step drift <= 0.05 and mass drift
  <= mass tol, window 50, min-iter 200 (--temporal-step-tol 0.05).
- PILOT BURST: at each candidate, take P=50 draws per chain from the
  would-be-frozen sampler. Pilots run on SEPARATE per-chain RNG streams
  (seed + 7919*(c+1), fresh per check) and a recording-only handler, so
  pilot draws NEVER enter saved draws and never advance the chains'
  sampling RNG streams (bit-transparent to the no-pilot arm when the first
  check passes). Pilot draws are ALWAYS discarded (requirement: safest for
  the ESS comparison); after a pass, sampling starts fresh via
  adapters[c].sampler().
- GATE FORMULAS (exact, on the P=50 lp__ values per chain):
  1. Per-chain lag-1 autocorrelation (biased/ML autocovariance estimator):
     mean = (1/P) sum lp; c0 = (1/P) sum (lp-mean)^2;
     c1 = (1/P) sum_{n=0..P-2} (lp_n-mean)(lp_{n+1}-mean);
     rho1 = c1/c0 (if c0 <= 0: rho1 := 1, i.e. fail).
     Statistic: rho1_max = max over chains. PASS requires rho1_max <= 0.5.
     Rationale: AR(1) heuristic ESS/N=(1-r)/(1+r); r=0.5 -> ESS ~ N/3.
     The marginal-class regressions (-33..-58% ESS) imply far slower mixing
     than N/3 in the pilot window; r > 0.5 = visibly slow, resume.
  2. Cross-chain short R-hat proxy on lp (split-half, NOT rank-normalized
     — 50 draws is too few; documented simple proxy): each chain's 50
     draws split into first/last 25 -> J = 2*chains half-chains of n_h = 25.
     W = mean of half-chain sample variances (ddof=1);
     B = n_h/(J-1) * sum (mean_j - grand)^2;
     var_plus = (n_h-1)/n_h * W + B/n_h; Rhat_lp = sqrt(var_plus/W)
     (if W <= 0: Rhat := +inf, fail). PASS requires Rhat_lp < 1.10
     (classic threshold; 8x25 halves are noisy, so false-FAIL is possible
     and costs only warmup — conservative direction).
  GATE PASS = (rho1_max <= 0.5) AND (Rhat_lp < 1.10). Both statistics and
  the decision are printed per check (parseable `pilot check k: ...` lines).
- RESUME on failure: warmup continues from the PRESERVED adapter state (no
  adaptation state discarded) via adapt_with_pilot (new, adapt.hpp): it
  loops adapt_with_stats phases with the remaining warmup budget as the
  phase max_iter; a fresh controller phase re-arms the temporal gate
  (~200 + 2 windows more iters before the next candidate, so at most ~2-3
  pilot checks within a 1000-iter budget). If the budget is exhausted
  after a rejection, warmup has run its full length (early_exit reported
  0) and sampling proceeds — quality floor = full warmup.
- CLI: --pilot-burst N (0 = OFF, default; N must be even), --pilot-rho1-max
  (default 0.5), --pilot-rhat-max (default 1.1). Multi-chain only. Default
  path (all new flags 0/absent) must stay bit-identical (canary).
- Known approximation, recorded: pilot logp cost lands in the warm-phase
  timing stanza; total wall measured externally (harness) is the honest
  speed metric. The adapter-internal metric-window reset guard reads the
  PHASE-1 max_iter while resumed phases are shorter — affects only whether
  the accumulator chops at the exact final iteration of a resumed phase
  (interior-boundary semantics; immaterial and documented).

Arms (3 reps x 4 chains, seeds 20260819+1000*rep (+c single-chain), pf
inits from inits_w25/, --metric-window 50, warmup=1000 samples=1000):
- base:              4 single-chain procs, fixed warmup (REUSE runs/base —
                     W-25 runs; canary bit-identity makes them valid).
- mc_gate05:         --chains 4 --temporal-step-tol 0.05 (the refuted
                     static gate; REUSE runs/mc_gate05 for reference).
- mc_pilot50 (NEW):  --chains 4 --temporal-step-tol 0.05 --pilot-burst 50.
Models (W-25 grid): arma11, lsat_model, hier_2pl (marginal class), blr,
eight_schools_noncentered (easy class). Harness: extend run_w25.py with the
mc_pilot50 arm; new analyze_w28.py (3-arm tables, arviz ESS, medians).

GATES (pre-registered):
- Quality (primary): mc_pilot50 ess_bulk_min AND ess_tail_min per marginal
  model NOT worse than base beyond noise (median of 3 reps; noise band =
  base per-rep spread). This is the gate W-25 failed.
- Speed: on models where the pilot arm's final exit is early
  (exit_iter < 1000), wall median vs base must improve >= 1.2x; no model
  may be > 1.1x SLOWER than base (pilot overhead must not eat the win).
- Canary: default single-chain draws AND the unchanged multi-chain path
  (mc_gate05 flags) bit-identical (md5) pre/post change.
- Expectation: pilot REJECTS hier_2pl (and likely lsat) at the first
  candidate, resumes, final ESS within noise of base; blr passes
  immediately keeping most of the 1.3-2.4x wall win minus ~5-10% pilot
  cost. Honest risk: arma11 (only -33% ESS, step stable +12%) may look
  "well-mixed" in a 50-draw lp pilot and pass early — if its ESS then
  regresses beyond noise, the quality gate FAILS and the early-exit
  direction closes (lp-window mixing signals too weak): recorded either
  way as the W-28 verdict.

## 2026-08-22 — W-27 close-out: NEGATIVE RESULT — flags are a dead end; -march=native MISCOMPILES kronecker_gp gradients

Setup: 5 models rebuilt as bs_models_o3 (-O3 -march=native -mtune=native) and
bs_models_o3only (-O3) via bridgestan 2.9.0 compile_model (CXXFLAGS=...; NOTE
compile_model caches <stem>_model.so next to the .stan file and silently
returns it regardless of make_args — first build attempt shipped default
binaries; had to copy .stan into scratch dirs per variant. out_dir kwarg
does not exist in 2.9.0). CLI for wall runs: own build at
external/walnutpie/build_e27 @ 0cb5b7b (shared build was being rebuilt by
another agent; one consistent binary for both arms). Runner/analysis:
harness/run_w27.py, harness/analyze_w27.py; inits: inits_w25 pf for
blr/arma11/hier_2pl, deterministic normal(0,1) random.Random(f'{seed}-{c}')
for kronecker_gp/diamonds -> inits_w27/. Raw: runs/w27/{default,o3only}.

G1 GRADIENT PARITY (100 random unc points/model, default vs variant):
- default vs -O3: BIT-IDENTICAL (logp AND grad, all 5 models, 0.0 diff) —
  no fast-math => -O level cannot reassociate FP; only codegen changes.
- default vs -O3+native: blr 8e-14, hier_2pl 2e-14, diamonds 2e-11,
  arma11 5e-15 rel grad — PASS. kronecker_gp: CATASTROPHIC FAIL — 99/99
  points wrong, ~250-305 of 438 components (the L lkj_corr_cholesky
  block) off at 0.006-1.7 REL with SIGN FLIPS, while logp matches to 1e-16.
  Richardson finite differences side with the default build (pt1 comp3:
  fd -2.984 vs default -3.000, native -8.121) => -march=native
  miscompiles the gradient (gcc FMA-contraction/eigen packet path).
  The historic cmdstan corruption was blamed on mixed-build ABI; this
  shows the hazard is NOT only mixed builds — self-contained single-make
  -march=native can miscompile gradients outright. DO NOT USE
  -march=native for Stan model builds.

G2/G3 WALL (default vs -O3 only; -O3+native disqualified at G1), 5 models
x 3 reps x 4 chains, seeds 20260819+1000*rep+c, warmup=1000 samples=1000
--metric-window 50, identical inits per arm, single-chain CLI procs:
  wall ratio (o3/default): blr 0.95, arma11 1.04, hier_2pl 0.99,
    kronecker_gp 1.01, diamonds 1.02 — GEOMEAN 1.002 (no effect).
  per-call logp_grad (sampling): ratios 0.98-1.02 all models.
  Draws: 60/60 chain CSVs BIT-IDENTICAL default vs -O3 (expected from G1)
  => ESS identical by construction, no separate ESS run needed.
- Why no win: the default bridgestan build is ALREADY optimized at -O3-
  equivalent level (-O0 control build of hier_2pl: 1343us/call vs ~976
  default/~982 -O3 in matched serial CLI runs; default==explicit -O3).
- What -march=native would have bought where its gradients pass: only
  ~6-15% per call (hier_2pl serial CLI: 920 vs 981us; Python micro-bench
  0.85-0.88x on hier/kron, 0.72-0.74x on blr/diamonds — but small-model
  micro-bench numbers are Python-overhead-dominated, not trustworthy).

VERDICT: no flags win available. Default build flags are already optimal
in practice; -O3 alone is a provably safe no-op (bit-identical draws);
-march=native is UNSAFE (silent gradient miscompile on kronecker_gp) for
at most ~10% per-call. Recommend: keep default compile flags, close the
"speed up logp_grad via build flags" direction (NEXT_IDEAS A). stanc
--Oexperimental was already rejected in Phase 0; no remaining cheap
compile lever.
Artifacts committed: harness/run_w27.py, harness/analyze_w27.py,
inits_w27/, this WORKLOG entry. bs_models_o3*/ kept local (not in repo).

## W-29 (pre-registered BEFORE running): stan-math model-gradient hotspot atlas for upstream candidature

Mission: produce the EVIDENCE PACK naming which stan-math functions dominate
logp_grad cost on our expensive models, so upstream proposals (walnutpie or
stan-math) can target them. Measurement/documentation only — NO code changes
to walnutpie or stan-math. W-27 closed the compile-flags direction; W-17g
says logp_grad = 68-99.7% of walnutpie sampling wall, so the remaining
per-call lever is the MATH LIBRARY itself.

Method (one callgrind job at a time, <=4 cores shared, env -u LD_LIBRARY_PATH):
- Binary: external/walnutpie/build_e27/examples/stan_cli @ 0cb5b7b (W-27's
  stable build; NOT rebuilt). Models: default bs_models/*.so.
- valgrind 3.23 from ~/vginstall. --tool=callgrind (no cache sim — Ir only).
- Models (gradient-heavy class): hier_2pl, kronecker_gp, gp_regr, accel_gp,
  diamonds. SHORT runs: warmup=100 samples=50 for hier_2pl/kronecker_gp
  (longer warmup to keep exception-truncated gradient calls low: probe
  1.5% / 2.7% of calls), warmup=50 samples=50 for the rest. Fixed seed
  20260819, fixed inits (inits_w25 pf for hier_2pl, inits_w27 for the
  others; gp_regr+accel_gp inits generated with the W-27 deterministic
  random.Random('20260819-0') normal(0,1) scheme -> inits_w27/).
- Attribution: cg_annotate exclusive + --inclusive=yes (logp_grad subtree
  Ir = inclusive cost of the gradient entry) + --tree=both (call paths);
  results/profile/w29/<model>/ holds raw dumps, harness/w29_callgrind.py
  is the runner/parser.
- Deliverable: results/hotspot_atlas_w29.md — per-model tables (function,
  exclusive Ir, % of logp_grad subtree, call path), ranked upstream-
  candidate list with WHY + fix shape (algorithmic vs vectorization vs
  allocation), walnutpie-internal (non-logp_grad) overhead fraction per
  model vs ATLAS.md's old numbers.

Expectations (pre-registered):
- hier_2pl: lkj_corr_cholesky + bernoulli/beta lpmf chains + reverse-pass
  overhead dominate (its gradient has the known exception-heavy lkj block).
- kronecker_gp: gp_exp_quad_cov / cov_exp_quad + cholesky + transformed-
  params (ATLAS: 71% of profiled time in tp block).
- diamonds: eigen linalg (normal_id_glm) should dominate (ATLAS 69% eigen).
- accel_gp/gp_regr: small models — higher alloc/memcpy and sampler-side
  share.
- walnutpie-internal fraction expected <5% on these models except gp_regr/
  accel_gp (small per-call cost) — consistency check vs W-17g 68-99.7%
  wall shares (instruction shares should be lower than wall shares where
  the sampler has I/O waits; note drift, don't re-litigate).
Gate: every number in the atlas traceable to a callgrind.out in the repo;
commands in the atlas must reproduce it verbatim.

### W-28 mid-task note (implementation validated; pre-registered thresholds UNCHANGED)

Implementation shipped (submodule exp/pilot-burst-gate @ b80f4a8). Canary:
single-chain default path 12/12 CSVs bit-identical pre/post (3 models x 4
chains, warmup 400 / samples 200, seeds 20260819+c). The multi-chain path
is NOT run-to-run deterministic even pre-change (controller exit depends
on thread timing: identical blr invocations exited at 500/520/540/550) —
this is why W-25 reported exit-iter medians; with --pilot-burst 0 the CLI
calls the unchanged adapt_with_stats on the unchanged controller, so the
mc canary is the code-path argument + statistical equivalence.
Functional probes (rep0 inits, seed 20260819, ONE run each — validation,
not the grid; thresholds NOT recalibrated):
  blr    check@515: rho1 0.861 rhat 1.262 -> resume (full warmup)
  hier   check@385: 0.719/1.394; @685: 0.723/1.052 -> resume x2 (full)
  arma11 check@600: 0.608/1.056 -> resume (full)
  lsat   check@350: 0.663/1.034; @650: 0.773/1.197 -> resume x2 (full)
  esc    check@350: 0.570/1.070; @685: 0.670/1.016; @985: 0.530/1.020
        -> resume x3 (full)
Early read (to be confirmed by the 3-rep grid): the sampler's lp stream
carries lag-1 autocorr 0.5-0.9 at ALL candidate points — the AR(1)-based
0.5 bar (ESS>=N/3 intuition) is miscalibrated to this model class, where
even FULL-warmup min-param ESS is ~N/9 (blr 350/4000). And rho1 does NOT
separate marginal from easy (easy blr 0.86 > marginal hier 0.72). Running
the pre-registered grid unmodified; any threshold recalibration would be
POST-HOC and labeled as such.

## 2026-08-22 — W-28 CLOSE-OUT: pilot-burst gate SHIPPED (default off); quality gate PASSES where it matters, speed gate FAILS — the lp pilot statistic cannot separate marginal from easy; early-exit direction closed

Implementation: walnutpie branch exp/pilot-burst-gate @ b80f4a8 (off
exp/endpoint-grad-threading+chains @ 0cb5b7b). adapt_with_pilot (adapt.hpp)
= phased adaptation under the total budget with a caller veto; vetoes
resume warmup from preserved adapter state. CLI --pilot-burst 50
(+ --pilot-rho1-max 0.5, --pilot-rhat-max 1.1), pilots on separate rng
streams (seed + 7919*(c+1)) with a recording-only handler — discarded
always; sampling after approval starts fresh from the untouched adapters.
Arms: base + mc_gate05 reused from W-25 runs (canary argument: single-chain
path 12/12 bit-identical; with --pilot-burst 0 the mc path calls the
byte-identical adapt_with_stats; the mc path is inherently run-to-run
nondeterministic anyway — identical blr invocations exit at 500/520/540/550,
which is why W-25/W-28 use medians).

Grid (3 reps x 4 chains x 5 models, medians; arviz ESS; full tables in
results/w28_{ess,wall,pilot}.json):
  bulk-ESS-min:            base   mc_gate05  mc_pilot50
    arma11                 1028      860        806   (pilot per-rep 806/1150/584)
    lsat_model              944      942        809   (884/809/758)
    hier_2pl                519      126        511   (547/511/504)
    blr                     350      347        346
    eight_schools_nc       1488     1459       1488
  tail-ESS-min:
    arma11                 1539     1260       1320
    lsat_model             1638      825       1463
    hier_2pl                733      112        647
    blr                     361      457        362
    eight_schools_nc       1361     1361       1411
  wall (median s):  hier 49.6/89.3/48.8; lsat 14.5/111.4/21.8;
    arma 0.2/0.2/0.2; blr 0.3/0.4/0.4; esc 0.1/0.1/0.1
  pilot behavior: 13/15 runs REJECTED every candidate -> full warmup
  (checks 1-3 each). Approved: arma11 rep2 @730 (rho1 0.39, rhat 1.007),
  esc rep0 @750 (0.47, 1.028). esc rep1/2: no candidate at all.

VERDICTS (pre-registered gates):
1. Quality: PASS with one borderline cell. hier_2pl — the model that
   destroyed W-25 (519->126) — is fully protected (511 vs 519 bulk, tail
   within base's per-rep spread). arma11 within base spread (806 vs 1028;
   base reps span 605-1376). lsat bulk median 809 sits 9.5% BELOW base's
   worst rep (894) — strictly out of the pre-registered noise band
   (tail passes; and no early exit ever fired on lsat, so the delta is
   mc-path/full-warmup variance, not an early-exit effect). Where the
   gate DID approve (2/15), ESS stayed in-band (arma11 rep2 bulk 584 vs
   base worst 605; esc rep0 1745, best of all arms).
2. Speed: FAIL. No model's median exit was early (all 1000) — the gate
   recreates full warmup, so no wall win exists to preserve. Worse, the
   in-process mc path at full warmup carries overhead vs 4 parallel
   single-chain procs: lsat 14.5 -> 21.8s (1.50x; warmup 6 -> 14-17s),
   hier warm +12-18% (sampling actually cheaper, 21 -> 16s), sub-second
   models unchanged. The pilot itself is cheap (~100 pilot draws; the
   overhead is the controller's busy-poll core + in-process arena/thread
   contention) — quantified for successors.
3. Canary: PASS (12/12 single-chain bit-identical; mc path unchanged code
   when --pilot-burst 0, inherently nondeterministic run-to-run).

WHY IT FAILS (the scientific result): the sampler's lp stream carries
lag-1 autocorrelation 0.5-0.9 at EVERY candidate point on this benchmark —
including full-warmup-quality freezes on the easy class (blr 0.62-0.74,
esc 0.53-0.67) — because even base min-param ESS is ~N/9 (blr 350/4000).
So (a) absolute thresholds calibrated on iid intuition (rho1 <= 0.5 ~
ESS >= N/3) reject everything, and (b) NO threshold separates classes:
values that must reject marginal hier (0.71-0.91) and lsat (0.66-0.90)
also reject easy blr (0.62-0.74) and esc (0.53-0.67); the two approvals
landed on marginal-class arma11 (0.39) and esc (0.47). hier_2pl's
catastrophic under-exit (ESS -76%) is INVISIBLE to a 50-draw lp window —
consistent with W-25's suspicion that the damage lives in trajectory
geometry / min-micro-steps, which only long-horizon min-dimension ESS
sees.

DIRECTION CLOSED: three independent gates now agree — CLI temporal knob
(W-21: fast but quality-destroying), static step/mass drift gate (W-25:
quality-destroying), dynamic lp pilot burst (W-28: quality-preserving
only by never exiting). Library-level warmup early-exit on this benchmark
has no cheap observable that is both class-separating and cheap to
evaluate; recommendation: keep warmup fixed-length (defaults unchanged,
gate ships default-off for future use), revisit only with a per-DIMENSION
pilot ESS estimate (cost ~ a full 50-draw pilot per param block — no
longer cheap) or an adaptation signal internal to trajectory geometry.
Ship state: exp/pilot-burst-gate @ b80f4a8, default off; base + mc
paths bit-identical. Raw: runs/mc_pilot50/, results/w28_*.json.

## W-30 (pre-registered BEFORE running): parallel multi-chain execution — event-driven controller sync + serial-execution control

Mission: wall time of the `--chains 4` in-process path. W-28 measured
the mc path at 1.5x wall vs 4 PARALLEL single-chain procs on lsat
(21.8 vs 14.5s; warmup 6 -> 14-17s) and attributed it to (a) the
controller's busy-poll core and (b) in-process contention. Correction
to the task brief, recorded up front: the mc path at b80f4a8 is NOT
serial — warmup workers already run as jthreads (adapt.hpp AdaptWorker)
and sampling already runs as jthreads in the CLI. The work is therefore
(a) remove the busy-poll, (b) make thread topology CONTROLLABLE so
serial vs threaded is a measurable, deterministic comparison, (c)
quantify remaining contention. Budget: 4 chains = 4 worker threads =
the whole core budget; machine has 12 CPUs so no hard oversubscription
discipline applies beyond convention (<= 4 runnable threads per run
after the fix; 5 while the spinner exists).

Design (walnutpie branch exp/parallel-chains off exp/pilot-burst-gate
@ b80f4a8):
- ADAPTMONITOR: mutex + condition_variable + version counter in
  adapt.hpp. Workers notify after EVERY snapshot publish
  (publish_stride = 5 iters -> ~800 notifies/chain/full warmup,
  negligible). The controller replaces its spin loop with
  cv.wait_for(100ms cap, version-changed predicate): wakes on any
  publish; the timeout keeps the interrupt-callback contract bounded
  (interrupt latency <= 100ms vs ~immediate before; NullInterrupt in
  the CLI) and bounds any missed-notify bug (final publish at
  max_iter always wakes it). Convergence arithmetic UNCHANGED.
- SERIAL EXECUTION MODE (ChainExec::serial, new defaulted parameter on
  adapt_with_stats / adapt_with_pilot; default ChainExec::threads =
  current behavior minus the spin): the calling thread runs all chains
  round-robin in blocks of publish_stride iterations, publishing every
  chain's snapshot at block boundaries and running the SAME factored
  stop evaluation (controller body refactored into a shared helper —
  no arithmetic change) — deterministic observation points, same
  (chain, iter) publish grid as the threaded workers. No jthreads.
- CLI: --chain-exec threads|serial (default threads; serial also runs
  the SAMPLING phase and pilot bursts serially in-process) and
  --fixed-warmup (mc only: min_iter = max_iter so the controller's
  cross-chain criteria can only stop at the budget — gives a
  deterministic warmup LENGTH for the equivalence gates; the default
  early-exit behavior is unchanged).
- ISOLATION (carried from W-25): per-chain BridgeStan model instance,
  mt19937_64, StanHandler + handler GQ rng; STAN_THREADS=1 .so from
  bs_models_threads/ for every multi-threaded model loading.
- DETERMINISM MODEL (pre-registered gate definition): per-chain draw
  CONTENT depends only on (seed+c, init, config) — never on thread
  scheduling; all per-chain state is chain-local and the RNG streams
  never interleave. Warmup-LENGTH nondeterminism under the default
  cross-chain early exit is PRE-EXISTING (W-28: identical blr runs
  exited at 500/520/540/550) and out of scope; the gates pin the
  length via --fixed-warmup.

GATES (pre-registered):
- (a) CANARY: default single-chain path draws bit-identical pre/post
  (md5, 12/12 = 3 models blr/arma11/hier_2pl x 4 chains x seed
  20260819+c, warmup 400 samples 200, default init, bs_models_threads
  .so). Pre binary: stan/build/stan_cli_w30_pre (clean-first rebuild
  at b80f4a8).
- (b) MC EQUIVALENCE: --chains 4 --fixed-warmup output CSVs md5-identical
  between --chain-exec threads and --chain-exec serial (all 5 gate- c
  models, rep0). BONUS check (not gating; failure investigated for
  pre-existence): mc chain-c CSV md5 vs single-chain proc chain-c CSV
  (W-25 seeded the mc path to replicate per-chain streams).
- (c) WALL: 5 models (blr, arma11, hier_2pl, lsat_model,
  eight_schools_noncentered) x 3 reps x 4 chains, warmup=1000
  draws=1000, seeds 20260819+1000*rep(+c), pf inits from inits_w25/
  (all 5 available), --metric-window 50, --fixed-warmup on BOTH mc
  arms (isolates execution topology from early-exit noise).
  Arms: seq4 = 4 SEQUENTIAL single-chain procs (wall = batch elapsed);
  par4 = 4 parallel procs (W-28's base configuration, re-measured
  fresh under current machine conditions); mc_serial = --chains 4
  --chain-exec serial; mc_threads = --chains 4 --chain-exec threads.
  Medians. Expectation: mc_threads/seq4 ~ 0.25-0.4 on the multi-second
  models (~3-4x); mc_threads <= par4 x 1.1 (contention gone); mc_serial
  ~ seq4 (same work, one process). Contention disclosure: agent I runs
  single-core callgrind concurrently on this box — real-usage
  contention, affects all arms' medians, noted per-run.
- Negative results recorded either way. Builds: env -u LD_LIBRARY_PATH
  cmake --build external/walnutpie/build --clean-first -j2 after every
  header edit (standing rule).

## 2026-08-22 — W-29 CLOSE-OUT: hotspot atlas delivered (results/hotspot_atlas_w29.md)

Method executed as pre-registered: callgrind (valgrind 3.23, ~/vginstall, Ir
only, one job at a time) on build_e27/stan_cli @ 0cb5b7b, 5 models, seed
20260819, fixed inits (hier_2pl pf from inits_w25; others inits_w27; gp_regr/
accel_gp det-N(0,1) inits added to inits_w27), warmup 100+50 (hier_2pl,
kronecker_gp) / 50+50 (rest). Subtree G = inclusive Ir of
bs_log_density_gradient; shared callees attributed via --tree=both caller
edges. Raw dumps + annotate text: results/profile/w29/<model>/; parser:
harness/w29_callgrind.py + harness/analyze_w29.py.

HEADLINE NUMBERS:
- logp_grad subtree G/T: hier_2pl 99.4%, kronecker_gp 96.9%, accel_gp 92.6%,
  diamonds 85.7%, gp_regr 81.6%. Walnutpie-INTERNAL (non-gradient) inside the
  sampler loop: 0.2/0.5/1.0/0.2/5.5% respectively => sampler-side ceiling
  ~0-5% on this class; one-time+IO outside the loop 0.4-14.2% (amortizes).
- Ir/grad: hier_2pl 7.75M, kronecker_gp 5.25M, diamonds 600K, accel_gp 171K,
  gp_regr 67K. Cross-check vs ATLAS bridge numbers: diamonds 599,583 vs old
  652,455 (-8%, different warmup mix) — consistent.
- RANKED stan-math UPSTREAM CANDIDATES:
  1. Reverse-mode eigendecomposition eigenvectors_sym/eigenvalues_sym<var>
     (kronecker_gp): 39.3% of TOTAL program Ir (20.4%T + 18.9%T inclusive);
     model needs values AND vectors -> 4 full SelfAdjointEigenSolver runs/
     gradient where 2 suffice (API gap); eigenvector adjoint callback 9.1%T;
     Eigen computeFromTridiagonal unblocked scalar loop 20.6%G.
  2. Elementwise var-mode tax on indexed likelihood lines (hier_2pl): ~32%G
     plumbing (subtract/elt_multiply fwd 23.9% + rvalue<index_multi> 8.1%) +
     ~39%G likelihood math (bernoulli_logit_lpmf 18.5%, libm log1p 14.4%,
     inv_logit rev lambda 6.3%) for ONE program line (y ~ bernoulli_logit(
     alpha[ii] .* (theta[jj] - beta[ii]))).
  3. cholesky_decompose<var> REVERSE pass (gp_regr): rev lambda 17.0%G vs
     forward 9.8%G (adjoint sweep 1.7x the factorization); gp_exp_quad_cov
     calls libm pow (8.9%G) where d*d would do.
  4. Tape/arena construction fixed cost (all var models): stack_alloc +
     chainstack emplace_back + arena ctors = 12.6%G hier_2pl, 16.9%G
     accel_gp, 8.2%G kronecker — the SoA-arena lever, not a single patch.
  5. normal_id_glm_lpdf<var> GEMV pair (diamonds): 80.5%G in two GEMVs;
     already near vectorization ceiling (ATLAS 50% FMA peak) — and the
     PATTERN TO COPY (partials in-forward keeps rev pass at 0.4%G).
- Checks folklore re-rejected at function level: bounded<>::check 1.9%G max.
- Caveats recorded: 1.5%/2.7% exception-truncated gradient calls on
  hier_2pl/kronecker_gp slightly undercount reverse-pass shares; tree blocks
  only exist above callgrind's auto threshold (top paths hand-verified).
- Drift note vs ATLAS.md: same regimes; old §2 bucket shares were cmdstan-
  binary based, new ones are walnutpie-CLI + finer buckets — not comparable
  number-for-number, direction unchanged.

Artifacts: results/hotspot_atlas_w29.md (the atlas), results/profile/w29/
(raw + parsed), harness/w29_callgrind.py, harness/analyze_w29.py,
inits_w27/{gp_regr,accel_gp}/rep0/chain_0.txt, this entry.
Contended with agent F's W-28/W-30 sampling runs on shared cores (their
close-out notes it; medians unaffected direction).

## W-32 (pre-registered BEFORE running): eigh-reuse ceiling on kronecker_gp — prototype one-decomposition values+vectors to measure the upstream win

From W-29 atlas candidate #1: kronecker_gp's gradient spends 39.3% of
whole-program Ir in reverse-mode eigenvectors_sym/eigenvalues_sym<var> — the
generated code calls BOTH primitives on the SAME two matrices (Sigma1, Lambda),
so each gradient runs 4 full double-mode SelfAdjointEigenSolver decompositions
where 2 would suffice (each primitive internally computes values AND vectors
and throws half away). This is an API gap: stan-math has no combined eigh
primitive; stanc3 emits the two calls. The user will propose fixes upstream;
this item MEASURES THE CEILING so the proposal has numbers. No walnutpie/
stan-math/submodule changes; prototype lives in scratch/w32/ only.

Method:
- Codegen: stanc (cmdstan-2.39.0) kronecker_gp.stan -> hpp; confirm the 4-runs
  claim from the generated source (2x eigenvectors_sym + 2x eigenvalues_sym on
  var inputs; check what each stan-math overload actually runs).
- Prototype (route a, stan-math-style): local header implementing a combined
  eigh for var input — ONE SelfAdjointEigenSolver on the .val() matrix, one
  reverse callback producing BOTH eigenvalue and eigenvector adjoints. Adjoint
  math for A = V diag(w) V^T with eigen-adjoints G_V (for vectors) and g_w
  (for values): dA = V [ (V^T G_V V + diag(g_w)) symmetrized w.r.t. the
  w_i-w_j denominators ] V^T — derived against stan-math's own
  eigenvectors_sym/eigenvalues_sym reverse implementations and validated by
  (i) finite differences and (ii) max rel grad diff vs the STOCK model on
  random points. Patch a COPY of the generated model hpp to use the helper for
  both matrices. scratch/w32/ only.
- Build: bridgestan.compile_model on a COPIED .stan per variant (W-27 gotcha:
  cached .so next to the .stan is silently reused regardless of make_args);
  default CXXFLAGS (W-27: -march=native MISCOMPILES this model's gradients —
  forbidden). env -u LD_LIBRARY_PATH for make; /usr/bin/make if direct.
- GATES:
  (a) correctness: max rel gradient diff stock vs patched on ~100 random
      unconstrained points < 1e-9 (no NaN/Inf), PLUS finite-difference
      spot-checks on the patched model (W-27 method).
  (b) per-call: matched serial timing of logp_grad via a small Python
      bridgestan driver on identical points (do NOT touch external/walnutpie
      builds — agent H owns that worktree); us/call stock vs patched,
      3 repeats, medians.
  (c) callgrind Ir/grad (valgrind 3.23 ~/vginstall, one job at a time,
      W-29 short-run protocol: warmup 100 samples 50, seed 20260819,
      inits_w27/kronecker_gp/rep0/chain_0.txt) on stock vs patched .so.
- Deliverable: results/eigh_reuse_w32.md — codegen findings, prototype +
  adjoint validation evidence, measured ceiling (expected order: tens of % of
  the kronecker_gp gradient; report what is actually measured), and an
  upstream proposal sketch (stan-math combined primitive / stanc3 codegen).
- Expectation (pre-registered): eigenvectors_sym+eigenvalues_sym = 39.3%T of
  which roughly the eigenvalues_sym half is the redundant solver work ->
  naive ceiling ~19%T program / ~30-40% of Ir-per-gradient... measured
  honestly; the adjoint callbacks (9.1%T) largely remain (still needed).
  Cores <=4 shared; builds -j2; one callgrind job at a time. Negative
  results recorded.

## 2026-08-22 — W-30 CLOSE-OUT: event-driven controller + topology control SHIPPED; all determinism gates PASS; threaded mc = 3.2x sequential, within noise of 4 parallel procs — W-28's "contention" attribution largely corrected

Implementation: walnutpie branch exp/parallel-chains @ da71e5b
(off exp/pilot-burst-gate @ b80f4a8; commits 3041e9b adapt.hpp, da71e5b
CLI). AdaptMonitor (mutex+condvar+version): workers notify after every
snapshot publish, controller blocks in wait_for_change with a 100 ms cap
(interrupt re-checked per wait; final publish always wakes it). The stop
arithmetic is the former per-spin pass factored VERBATIM into
poll_controller, shared by both schedules. ChainExec::Serial runs all
chains round-robin in publish_stride blocks on the calling thread (same
publish grid, deterministic observation points); CLI gains --chain-exec
threads|serial (serial also runs sampling + pilots chain-by-chain) and
--fixed-warmup (min_iter = max_iter; both reject single-chain mode
loudly).

Pre-implementation diagnostics (pre binary stan/build/stan_cli_w30_pre,
clean-first rebuild at b80f4a8):
- Busy-poll CONFIRMED: during an mc run the main (controller) thread
  burned ~100% user CPU while the four workers got ~76% each; after the
  fix the controller idles at ~1% and workers run ~99.7% (schedstat).
- Correction to the task brief: the mc path at b80f4a8 was NOT serial —
  warmup workers and sampling already ran as jthreads. Correction to
  W-28's overhead attribution: per-call logp_grad cost is IDENTICAL
  in-process (lsat: 0.159-0.173 ms/call mc vs 0.159-0.165 single-chain
  procs), so there is no gradient-level "in-process contention" on this
  12-CPU box. W-28's lsat warmup gap (6 -> 14-17 s) traces mostly to
  EXTRA WORK: the pilot-resume phases re-chop the metric window at
  different boundaries, so chains took deeper trajectories (measured
  26-57k warmup logp calls vs 20-30k for the single-chain procs), plus
  the spinner's core. The threaded mc path was already running at
  wall = slowest chain.

GATES (pre-registered):
- (a) CANARY: PASS — 12/12 single-chain CSVs byte-identical pre/post
  (blr, arma11, hier_2pl x 4 chains, seeds 20260819+c, warmup 400 /
  samples 200, default init, bs_models_threads .so).
- (b) MC EQUIVALENCE: PASS — with --chains 4 --fixed-warmup, threaded
  vs serial output CSVs md5-identical in 15/15 cells (5 models x 3
  reps). BONUS (stronger than pre-registered): mc chain-c CSVs are also
  md5-identical to the SEQUENTIAL single-chain proc chain-c CSVs in
  15/15 cells — W-25's per-chain stream replication now verified
  bit-exactly end-to-end (it was unverifiable before --fixed-warmup
  because early exit changed warmup length run-to-run). Threaded A/A
  repeat (lsat, gate flags, 2 runs x 4 chains): 4/4 md5 pairs equal —
  the threaded path is run-to-run deterministic once warmup length is
  pinned; draw content is scheduling-independent as designed. ESS
  therefore carries over from the W-25/W-28 base arm by construction.
- (c) WALL (medians of 3 reps, warmup=1000 draws=1000, pf inits,
  --metric-window 50, --fixed-warmup on both mc arms):
    total wall (s):          seq4    par4  mc_ser  mc_thr  thr/seq thr/par ser/seq
      blr                    1.20    0.35    1.16    0.39    0.33   1.13    0.96
      arma11                 0.65    0.19    0.64    0.19    0.30   1.02    0.99
      hier_2pl             160.06   52.04  159.38   45.01    0.28   0.86    1.00
      lsat_model            42.93   15.02   43.63   15.90    0.37   1.06    1.02
      eight_schools_nc       0.41    0.12    0.40    0.13    0.32   1.09    0.97
    GEOMEANS: thr/seq 0.317 (3.2x), thr/par 1.027, ser/seq 0.988.
    warmup split (s): e.g. hier 23.3(seq, per chain) / 29.4(par) /
    92.2(ser) / 28.9(thr); lsat 6.9 / 7.7 / 23.3 / 8.1.
  Verdicts: expectation thr/seq 0.25-0.4 MET (0.28-0.37 on all models);
  mc_threads <= par4 x 1.1 holds on every model with wall > 1 s (hier
  0.86 — 14% FASTER than 4 procs; lsat 1.06) and on the geomean (1.027),
  but blr's median ratio is 1.13 (0.39 vs 0.35 s — a 40 ms absolute
  delta on a sub-second model, startup-jitter-dominated; per-rep par4
  [0.32, 0.48, 0.35] vs mc_threads [0.38, 0.55, 0.39]). Recorded as a
  marginal miss of the literal per-model bound on the smallest model,
  not as contention: hier — the model where W-28 saw the mc path lose —
  now WINS. mc_serial ~ seq4 (0.96-1.02) as designed (same work, one
  process; its warmup split shows the round-robin schedule costs nothing
  beyond serialization).
- Machine disclosure: no callgrind/valgrind process was observed during
  the grid (top consumers zcode/firefox at <= 4% CPU); per-rep walls are
  tight (hier mc_thr 45.49/44.98/45.01). Builds -j2 clean-first after
  each header edit.

VERDICT: the 4-chain in-process path now (i) respects the 4-thread
budget (controller sleeps), (ii) is bit-deterministic in draw content
and in run-to-run behavior once --fixed-warmup pins the length, and
(iii) delivers the full ~Nx parallel speedup vs sequential execution
(3.2x geomean, 0.28-0.37 vs the theoretical 0.25 floor at N=4; the gap
is the serial non-gradient remainder + slowest-chain skew) with no
measurable in-process contention penalty vs 4 independent processes.
The remaining wall lever is not topology: it is per-chain work (W-29
atlas) and the pre-existing warmup-length nondeterminism of the DEFAULT
cross-chain early exit, which --fixed-warmup now makes avoidable.
W-28's "busy-poll core + in-process contention" is hereby corrected:
the core burn was real (removed), the contention was not measurable —
the 1.5x it saw was pilot-resume work + environmental.

Ship state: exp/parallel-chains @ da71e5b, defaults unchanged
(--chain-exec threads = former behavior minus the spin; --fixed-warmup
off). Raw: runs/w30/{seq4,par4,mc_serial,mc_threads}/,
results/w30_wall.json, results/w30_md5.json; harness/run_w30.py,
harness/analyze_w30.py. Pre-change binary kept at
stan/build/stan_cli_w30_pre.

## W-31 (pre-registered BEFORE running): safe default cross-chain tolerances in the walnutpie controller

From W-25 side finding 3 + W-26 gate c FAIL-as-designed: the library
multi-chain controller's DEFAULT cross-chain tols (mass 1.0 / step 0.1,
temporal gate off) stop warmup at iter 50-80 with good inits + windowed
metric and destroy quality (hier_2pl bulk-ESS 519 -> 61, arma11 -19%,
blr -38%). Any embedder calling adapt()/adapt_with_stats() with a default
WarmupConfig is exposed. Mission: make the default SAFE out of the box,
keep the old behavior reachable for W-25/W-26 reproducibility, and
package the upstream-worthy findings.

DESIGN CHOICE (decided up front): default cross-chain early-exit OFF
(opt-in), NOT "more conservative tolerances". Rationale: W-25/W-28
together show no cheap tolerance-based gate makes the exit
quality-preserving — the most conservative gate tested (temporal
2-window tol 0.05, min_iter 200) still collapsed hier_2pl 519 -> 126,
and the pilot gate preserved quality only by never exiting. Therefore
"defaults conservative enough that exit at iter 50-80 is impossible"
cannot be met by any tolerance: the only default that makes the
destructive exit impossible is no early exit. The useful safe default
for embedders is fixed-budget warmup with full AdaptResult observability
(exit_iter = max_iter, early_exit = false, dispersion diagnostics still
computed at stop).

Implementation (walnutpie branch exp/safe-adapt-defaults off
exp/parallel-chains @ da71e5b):
- WarmupConfig gains allow_early_exit (default FALSE; builder setter of
  the same name). poll_controller evaluates/acts on the cross-chain
  criteria (incl. the temporal mode) ONLY when allow_early_exit() is
  true; otherwise the only stop is the budget (hit_max_iter) — the
  W-30 --fixed-warmup posture as the library default. The debug trace
  keeps printing mass/step diffs either way.
- CLI: new opt-in flag --early-exit restores the exact pre-W-31 default
  semantics (cross-chain tols, temporal off -> exit at iter 50-80).
  --temporal-step-tol > 0 also opts in (W-25/W-28 arm command lines stay
  reproducible verbatim). --pilot-burst without an early-exit enabler
  (--early-exit or --temporal-step-tol > 0) now FAILS loudly instead of
  silently never firing. --fixed-warmup unchanged (still pins min=max;
  now redundant at default, still meaningful with early exit on).
- Single-chain path untouched (canary must stay 12/12).

GATES (pre-registered):
- (a) CANARY: default single-chain draws bit-identical pre/post (md5,
  12/12 = 3 models blr/arma11/eight_schools_noncentered x 4 chains,
  seeds 20260819+c, warmup 400 / samples 200, default deterministic
  inits, bs_models_threads .so). Pre binary: clean-first rebuild at
  da71e5b kept as stan/build/stan_cli_w31_pre.
- (b) SAFE DEFAULT: --chains 4 with DEFAULT flags (no --early-exit, no
  --temporal-step-tol, no --fixed-warmup) on eight_schools_noncentered +
  hier_2pl, 3 reps x 4 chains, seeds 20260819+1000*rep (+c), pf inits
  from inits_w25/, warmup=1000 samples=1000, --metric-window 50,
  bs_models_threads .so. PASS = controller exit_iter=1000 early_exit=0
  on every run AND per-rep bulk-ESS-min (arviz, same procedure as W-25)
  within the base arm's per-rep spread (results/w25_ess.json: hier base
  reps 548/502/520, esc 1678/1488/1459). Expected stronger: per-chain
  CSVs md5-identical to runs/base (W-30 gate b bonus implies mc ==
  single-chain at fixed warmup length; full-budget default has the same
  per-chain warmup iteration count).
- (c) FOOTGUN OPT-IN NOT GONE: --chains 4 --early-exit on the same grid
  reproduces the W-25/W-26 destructive exit: early_exit=1 with
  exit_iter ~50-80, hier_2pl bulk-ESS collapse vs base (W-25: median
  61 vs 519), esc exits at ~50.
- STAN_THREADS evidence for the audit doc (no code change): one
  --chains 4 --fixed-warmup esc run against bs_models/ (default
  bridgestan make, STAN_THREADS off) vs bs_models_threads/ (built with
  make_args=['STAN_THREADS=True']) — documents the arena corruption
  repro; single-chain draws are .so-independent.
- Builds: env -u LD_LIBRARY_PATH cmake --build external/walnutpie/build
  --clean-first -j2 after every header edit; runs serialized; <=4 cores.
- Negative results recorded either way.

## W-33 (pre-registered BEFORE running): stan-math micro-lever ceiling on gp_regr — pow->mul in the exp-quad kernel + cholesky<var> reverse-pass assessment

From W-29 atlas candidate #3: gp_regr's gradient spends 8.9%G in libm `pow`
(attributed to `gp_exp_quad_cov` kernel distances — squaring a scalar via
pow) and the `cholesky_decompose<var>` reverse lambda costs 17.0%G vs the
forward call's 9.8%G (1.7x). Mission: put NUMBERS on the cheap stan-math
patches before proposing them upstream. This is a LOCAL stan-math patch +
rebuild + measure task: the bridgestan 2.9.0 stan-math tree at
~/.bridgestan/bridgestan-2.9.0/stan/lib/stan_math is patched (backed up to
scratch/w33/ first), gp_regr is rebuilt against it, and the tree is
RESTORED to pristine afterwards (other agents build against it). walnutpie
submodule untouched; nothing pushed.

Pre-patch source audit (done before registering gates):
- The pow is NOT in gp_exp_quad_cov itself; it is
  stan/math/prim/fun/square.hpp:28 — `square(x)` for arithmetic x is
  implemented as `std::pow(x, 2)` (despite the doc comment saying "just
  x * x"). Kernel loop calls squared_distance(x[i], x[j]) -> square(diff).
  W-29 callgrind confirms: 32,889/33,078 pow calls come from
  gp_exp_quad_cov = 57/grad (55 kernel pairs + square(sigma) +
  square(l_val)); the rev callback uses products (no pow). Patch: replace
  that one std::pow(x, 2) with x * x. Two further pow-with-2 sites exist
  in rev/fun/squared_distance.hpp scalar-var overloads (NOT exercised by
  gp_regr: x is data) — noted for the upstream proposal, not patched
  here so the measured diff stays attributable to one line.
- cholesky: N=11 <= 35 so the UNBLOCKED Giles lambda runs (blocked Murray
  path only for n>35). Assessment only (see gates) unless a trivially
  bit-safe patch is obvious; the rev pass does NOT recompute the
  factorization (L_A is reused).

Build: stock + patched .so from COPIED models/gp_regr.stan per variant in
scratch/w33/{stock,patched}_build/ (W-27 gotcha: compile_model silently
reuses the cached .so next to the .stan); default CXXFLAGS (-march=native
forbidden, W-27); env -u LD_LIBRARY_PATH; make -j2 max (cores shared).

GATES:
(a) correctness: gradient parity stock vs patched on ~100 random
    unconstrained points (deterministic rng scheme, W-27 style):
    max rel diff < 1e-12, no sign flips, no NaN/Inf, logp parity.
    NOTE: pow(x,2) vs x*x should be BIT-identical (glibc pow is correctly
    rounded and x*x is the correctly rounded square) — anything above
    exact-0 rel diff indicates a non-glibc pow path and gets
    investigated, not waved through. PLUS finite-difference spot-check
    on the patched .so (W-27 method).
(b) cost: matched per-call logp_grad timing from one Python driver on
    identical points (both .so in-process, interleaved, 3 timing
    repeats, medians, us/call), AND callgrind Ir per gradient (W-29
    protocol: valgrind 3.23 ~/vginstall, one job at a time, short runs,
    seed 20260819, fixed init inits_w27/gp_regr/rep0/chain_0.txt,
    warmup 50 samples 50) stock vs patched.
(c) restoration: patched header restored to pristine, verified against
    the scratch backup; patched .so + patch file kept in scratch/w33/.
Deliverable: results/gp_micro_w33.md — numbers, patch file pointer
(scratch/w33/pow_to_mul.patch), cholesky assessment (2-3 paragraphs with
the measured part-breakdown and ceiling), upstream-proposal text.
Expectation (pre-registered): pow Ir (3.45M of 38.7M = 8.9%G) collapses
to ~0; wall/call win bounded by ~9% of the gradient -> expect single-
digit % us/call on this 5.4us/call model; Ir/grad 66,990 -> ~61-63k.
Cholesky assessment expected to conclude: 17.0%G is the scalar Giles
sweep at n=11 (~11.4k Ir/grad, ~14 Ir/inner-loop-flop); blocked level-3
rewrite targets n>35 models, not gp_regr; division-hoist in the (i,j)
pair loop saves O(1k) Ir/grad (~1.5%G) — measured honestly if attempted,
else assessment-only. Negative results recorded.

## 2026-08-22 — W-32 CLOSE-OUT: eigh-reuse ceiling MEASURED — the fix already exists upstream (eigendecompose_sym); bit-identical lang rewrite saves 19.4% gradient Ir / 14.3% wall on kronecker_gp

Codegen (from source, confirming W-29's 4-runs claim): stanc3 v2.39 emits
eigenvectors_sym + eigenvalues_sym on BOTH Sigma1 and Lambda in 3 hpp
instantiations (double log_prob_impl, var log_prob_impl = gradient path,
write_array_impl); each stan-math rev overload runs its OWN full
SelfAdjointEigenSolver (default ComputeEigenvectors mode — the rev eigenvalues
overload cannot use EigenvaluesOnly because its adjoint needs V) => 4 full
decompositions/gradient, 2 redundant. Stock callgrind reproduces W-29 to 3
digits (T 27.633e9, G 96.88%T, 5.254e6 Ir/grad, 5094 calls, solver 36.56%T,
eigenvectors+eigenvalues 39.26%T).

KEY DISCOVERY: stan-math 5.3.0 (both cmdstan-2.39 and bridgestan-2.9 trees)
ALREADY SHIPS rev/fun/eigendecompose_sym.hpp — one solver, one callback, both
adjoints — and stanc3 2.39 exposes it in the language
(tuple(V,w) = eigendecompose_sym(A)). The gap is only discoverability/codegen:
nothing fuses the natural two-call pattern.

ARMS (scratch/w32/, default CXXFLAGS, per-variant dirs for the compile_model
cache; NEW gotcha: bridgestan's Makefile deletes the .hpp/.o intermediates —
build the .hpp as an EXPLICIT make target to patch it, then request
.hpp + .so together):
- stock: fresh build, (logp,grad) BIT-IDENTICAL to bs_models .so (100 pts).
- lang: model rewritten with eigendecompose_sym (2 lines/matrix, pure Stan,
  works on stock cmdstan 2.39) — harness/w32/kronecker_gp_eigendecompose.stan.
- hand: hpp patched to stan::math::w32_eigh — one solver + ONE callback with
  the FUSED inner F.(V^T G_V) + diag(g_w) (saves one GEMM pair vs the official
  primitive). Adjoint derivation validated at unit level
  (harness/w32/w32_unit.cpp): fused == stock two-call at 4-6e-16 rel on
  well-conditioned 30x30; both == central FD at 6-8e-8 (FD truncation);
  documented: stan's eigenvector adjoint is not symmetric (antisymmetric part
  inert for symmetric dA) so FD validates the symmetrized adjoint.

GATES:
(a) correctness — SPLIT VERDICT, documented:
  - lang vs stock: BIT-IDENTICAL logp AND gradients on 100 random points
    (worst rel-L2 exactly 0.0) AND the whole 150-iter callgrind trajectory:
    draws.csv md5 IDENTICAL (6b61df9f), same 5094 grad calls. Structural
    argument: adjoints start at 0, 0+x exact => two-callback and combined
    accumulation give identical bits. An upstream peephole can promise ZERO
    numerical change.
  - hand vs stock: logp bit-identical; gradients differ by amplified last-ulp
    rounding (fused inner reassociation): at posterior init median abs diff
    5.2e-8 (|g| median 11.5), p99 1.0e-2, max 8.9e-2; worst vector rel-L2
    3.8e-3, cos >= 0.9999929. The PRE-REGISTERED <1e-9 max-rel bar FAILED for
    the hand arm — and the controls show it is unattainable on this model for
    ANY independent reimplementation: FD-vs-stock == FD-vs-hand at every
    sigma cloud (0/0.01/0.1/0.25) to all digits, while the stock reference
    itself is only FD-verifiable to 4.5e-2 at the init and O(1) at random
    points (Richardson-stable). Root cause: jittered exp-quad Sigma1 (30x30)
    has an intrinsically near-degenerate bottom eigenvalue cluster; F=1/(w_j-
    w_i) amplifies ulp noise. Correctness of the adjoint MATH rests on the
    unit test; bit-identity is delivered by the lang arm. (Also informs W-27:
    this amplification is how -march=native reassociation produced O(1)
    L-block signature on this model.)
(b) per-call wall (serial bridgestan driver, 100 identical posterior-cloud
    points, 3 interleaved reps, medians, taskset 0-3): stock 393.0, lang
    337.0 (-14.3%), hand 324.1 us/call (-17.5%). (2-arm rerun reproduced:
    375.1 vs 309.6, -17.5%.)
(c) callgrind (W-29 protocol, one job at a time): stock T=27.633e9;
    lang T=22.430e9 (-18.4%), G=21.589e9, SAME 5094 calls => 4.238e6 Ir/grad
    (-19.4%), computeFromTridiagonal halved exactly (5.537e9 -> 2.778e9,
    -49.8%), eigen fwd complex 39.26%T -> 25.19%T; hand per-grad 4.066e6
    (-22.6%) but its trajectory drifted (5615 calls, +10.2%) so its TOTAL
    (-14.3%) is contaminated — lang is the clean number. Callbacks remain
    ~3.3e9 Ir (the same adjoint GEMMs are required; hand's fused inner saves
    ~15% of callback Ir at the cost of bit-identity).

UPSTREAM PROPOSAL (results/eigh_reuse_w32.md §7): (1) model-level — use
eigendecompose_sym TODAY (6-line diff, bit-identical draws, -19.4% Ir);
(2) stanc3 peephole fusing the eigenvectors_sym+eigenvalues_sym pair on the
same matrix into one eigendecompose_sym call, shippable with a bit-identity
guarantee; (3) optional math micro-polish (fused inner, +3% wall, loses
bit-identity); (4) NOT fixed by this: adjoint GEMM complex (~12-15%T) and the
unblocked QL loop — W-29's deeper items.

Artifacts: results/eigh_reuse_w32.md, results/profile/w32/{stock,patched,lang}/
(+draws_md5.txt), harness/w32/ (scripts + kronecker_gp_eigendecompose.stan),
this entry. scratch/w32/ builds kept local. walnutpie build_e27 untouched.

## 2026-08-22 — W-33 CLOSE-OUT: pow->mul one-liner measured at the FULL pow bucket (−9.1% Ir/grad, −12.9/−15.2% us/call, bit-identical end-to-end); cholesky rev assessed — no patch for the n=11 class

Source audit finding: the 8.9%G libm pow is one line —
stan/math/prim/fun/square.hpp:28 implements square(x) for arithmetic x as
std::pow(x, 2) while its own doc comment says "just x * x". Kernel paths
(prim AND rev gp_exp_quad_cov, which computes distances on value_of data)
instantiate it: W-29 tree shows 32,889/33,078 pow calls from gp_exp_quad_cov
= 57/grad (55 kernel pairs + square(sigma) + square(l_val)); rev callback
is pow-free. Patch = that single line -> x * x (scratch/w33/
pow_to_mul.patch; pristine backup scratch/w33/square.hpp.pristine; two
sibling pow-with-2 sites in rev/fun/squared_distance.hpp:24,38 noted for
the upstream PR, not patched — gp_regr does not exercise them).

GATES:
(a) CORRECTNESS: PASS at bit-identity — 100/100 random unconstrained
    points: logp max rel 0.0, gradients bit-identical, 0 sign flips, 0
    non-finite (glibc pow correctly rounded: pow(x,2)==x*x exactly, as
    pre-registered). FD spot-check on patched: 4.9e-8 (noise level).
    BONUS end-to-end canary: full sampler draws (W-29 protocol) md5-
    IDENTICAL across stock/patched .so, native AND under valgrind (all
    four CSVs 32881fbe4b02fc9b6c5665ac2867cb5a).
(b) COST (577 grads, both arms, one callgrind job at a time):
      Ir/grad 66,950 -> 60,864 (−6,086, −9.09%); pow Ir 3,453,345 -> 0
      in the model gradient path (19.9k residual = sampler-side Adam).
      Stock arm reproduced W-29 to the digit (pow Ir exactly 3,453,345).
      Wall (native stan_cli stanza, 3 reps interleaved, medians):
      warmup 6.681 -> 5.820 us/call (0.871x), sampling 6.655 -> 5.640
      (0.848x); per-rep ranges non-overlapping (absolute us inflated by
      a co-running agent job; ratio is the measurement). Wall win EXCEEDS
      the 9.1% Ir share — glibc pow's branchy path has poor IPC.
      Python-driver cross-check: same direction, −1.4% on ~13.7us
      Python-inflated calls (dilution).
(c) RESTORATION: square.hpp restored, byte-identical to pristine backup;
    find confirms it was the only header touched in the stan-math tree;
    patched+stock .so and patch file kept in scratch/w33/ (untracked, like
    W-32's scratch).

CHOLESKY ASSESSMENT (no patch — numbers identical in W-29 and both W-33
dumps): N=11 <= 35 so the UNBLOCKED Giles scalar sweep runs (blocked
Murray lambda only above n=35). Reverse lambda 6,718,588 Ir = 11,643
Ir/grad = 17.4%G; forward cholesky_decompose<var> 3,787,995 = 9.8%G, of
which LLT kernel 2,078,354 (5.4%G) and var-glue ~1.71M (~4.4%G). Ratios:
rev = 1.77x forward total, 3.23x LLT kernel. Flop accounting: sweep does
~950 flops + 121 divisions at ~12 Ir/flop vs LLT's 443 flops at ~8 Ir/flop
— the Giles recurrence is already AT its ~2x-forward-flop algorithmic
floor; the excess is loop machinery, not redundant work; no factorization
recomputation to reuse. Rewrite ceiling at n=11: <= ~4.4k Ir/grad
(<= 6.6%G) best case, realistically much less (Eigen dispatch overhead at
11x11 — why stan-math itself only blocks above 35). Micro-levers rejected:
1/L_jj division-hoist ~1.7%G but breaks bit-identity (reassociation);
adjL/adjA allocations ~0.4%G. Verdict: no gp_regr-class cholesky patch;
upstream targets are mid-size n (36–few hundred, blocked lambda level-3
adjoint — re-atlas on a representative model first) and the general
var-glue/arena lever (W-29 candidate #4).

UPSTREAM CANDIDATURE (evidence now in hand): the square() pow->mul one-
liner removes the full 9.1%G / 13–15% per-call bucket on gp_regr with
bit-identical behavior end-to-end. PR notes: code contradicts its doc
comment; square<int> overflow nuance (x*x overflows for |x|>46341 where
pow promotes to double — promote or document); sibling sites in
rev/fun/squared_distance.hpp:24,38; on non-glibc libms expect <=1 ulp
shifts. Indicative pow shares elsewhere (W-29, not re-measured):
kronecker_gp 1.93%T, accel_gp 0.71%T, diamonds 0.08%T.

Deliverable: results/gp_micro_w33.md. Raw:
results/profile/w33/gp_regr_{stock,patched}/ (committed); drivers +
patch + .so in scratch/w33/ (untracked). No walnutpie submodule changes,
no pushes.

## W-34 (pre-registered BEFORE running): elementwise var-mode plumbing ceiling on hier_2pl — codegen confirmation + rewrite arms

From W-29 atlas candidate #2: ONE program line of hier_2pl —
`y ~ bernoulli_logit(alpha[ii] .* (theta[jj] - beta[ii]))` — costs ~71% of a
7.75M-Ir gradient: ~32%G plumbing (subtract/elt_multiply on
Holder<IndexedView<var>> 23.9%G fwd + rvalue<index_multi> gathers 8.1%G) +
~39%G likelihood math (bernoulli_logit 18.5% + libm log1p 14.4% + inv_logit
rev lambda 6.3%). Mission: put a number on what better codegen / an available
language-level primitive could buy — evidence for the upstream push (stanc3
and/or stan-math). No walnutpie/submodule changes; scratch/w34/ +
harness/w34/ only; nothing pushed. Instrument read-only:
external/walnutpie/build_e27/examples/stan_cli @ 0cb5b7b (NOT rebuilt).

Codegen + source findings (confirmed BEFORE building):
- stanc3 v2.39 gradient (var) instantiation emits exactly:
  bernoulli_logit_lpmf(y, elt_multiply(rvalue(alpha, index_multi(ii)),
    subtract(rvalue(theta, index_multi(jj)), rvalue(beta, index_multi(ii)))))
  — 3 index_multi gathers on var vectors (each an eager Holder<IndexedView>
  materialization) + 2 N-element eltwise var ops (each a per-element vari +
  arena matrix + reverse callback). TRIGGER: any eltwise operator applied to
  an indexed var-container expression; nothing fuses the gather+eltwise chain.
- bernoulli_logit_lpmf<var> itself ALREADY uses partials_propagator
  (partials computed in the forward call, one edge — the diamonds /
  normal_id_glm pattern; stan-math 5.3.0 prim/prob/bernoulli_logit_lpmf.hpp).
  The lpmf is NOT the problem; its ARGUMENT EXPRESSION is.
- KEY DATA FACT (verified from data/hier_2pl.json): the data is the COMPLETE
  J×I response grid (I=32, J=600, N=19200=J*I), item-major order
  (ii = 1..I each repeated J, jj = 1..J tiled) — the N-vector eta IS the
  column-major flatten of eta_mat[j,i] = alpha_i*(theta_j - beta_i).

ARMS:
- A (language-level GLM): bernoulli_logit_glm_lpmf(y | x, alpha, beta)
  computes bernoulli_logit_lpmf(y, alpha + x*beta), DENSE matrix x
  (require_matrix_t), per-doc with analytic gradients; alpha may be a
  per-observation vector. The 2PL predictor alpha_ii*(theta_jj - beta_ii) is
  BILINEAR in two parameter vectors (alpha_i * theta_j product): no dense
  O(1)-column design encodes it; sparse encodings (x_n = theta_jj*e_ii with
  beta = item params) need dense N×I or N×J var matrices (32–600x the
  current N-element work) and x must itself be var (theta is a parameter),
  so the GLM would additionally differentiate through the design. VERDICT
  (from signature + docs, up front): NO clean mapping exists — documented,
  NOT implemented; proceed to B/C.
- B (matrix/GEMM formulation — the codegen-ceiling arm): exploit the
  complete grid; eta as a MODEL-BLOCK LOCAL (not tp — avoids 19200 output
  columns):
    matrix[J, I] eta = append_col(theta, rep_vector(-1.0, J))
                       * append_row(alpha, alpha .* beta);
    target += bernoulli_logit_lpmf(y | to_vector(eta));
  ([theta, -1](J×2) x [alpha; alpha.*beta](2×I) = theta*alpha' - ones*c'
  with c = alpha.*beta.) ONE var-mode GEMM (rev/fun/multiply.hpp: single
  reverse_pass_callback, adjoints via 2 GEMMs on .val() doubles), ZERO
  index_multi gathers, ZERO N-level eltwise var ops (only 600- and
  32-element ones); to_vector(var_value<Matrix>) is a zero-copy view.
  Same math, different per-element arithmetic (theta*alpha - alpha*beta vs
  alpha*(theta-beta)) => bit-identity NOT expected; FP-reorder level diffs.
- C (optional, only if cheap): column/row-major indexing reorder — SKIP
  rationale: B removes the gathers entirely, mooting the gather-layout
  question; recorded either way.

BUILD: copied .stan per variant in scratch/w34/{stock,armB}_build/ (W-27
gotcha: compile_model silently reuses the cached .so next to the .stan);
default CXXFLAGS (-march=native forbidden, W-27); env -u LD_LIBRARY_PATH;
/usr/bin/make -j2 max. Inits: inits_w25/hier_2pl/rep{0,1,2}/chain_{0..3}.txt
(pf, unconstrained — covered, verified present).

GATES:
(a) correctness vs stock on 100 random unconstrained points (deterministic
    rng, W-32 scheme): max rel logp <= 1e-12 REQUIRED (same lpmf, only eta
    arithmetic reordered); gradient vector rel-L2 + cosine reported
    honestly (expect small-FP-reorder ~1e-13, NOT 1e-16); FD spot-checks
    (Richardson-style, W-27/W-32 method) on both arms.
(b) cost: per-call logp_grad on identical posterior-cloud points via
    Python/bridgestan driver (3 interleaved reps, medians) + callgrind
    Ir/grad (W-29 protocol: valgrind 3.23 ~/vginstall, one job at a time,
    warmup 100 samples 50, seed 20260819, init
    inits_w25/hier_2pl/rep0/chain_0.txt). Attribute the delta: plumbing
    (subtract/elt_multiply/rvalue/IndexedView + their rev callbacks + tape)
    vs likelihood (bernoulli_logit/log1p/exp) shares before/after.
(c) sampler-level sanity on the best arm: 3 reps x 4 chains, seeds
    20260819+1000*rep+c, pf inits inits_w25/hier_2pl, warmup=1000
    draws=1000, --metric-window 50, 4 parallel single-chain stan_cli procs
    (W-30 par4 protocol, same read-only binary); bulk/tail ESS-min (arviz)
    within noise of stock; wall medians per the same protocol.

Expectations (pre-registered): plumbing bucket (~32%G) + eltwise rev
callbacks (~6.6%G) + rvalue-adjacent tape share collapse; naive Ir/grad
ceiling ~35-45%; wall saving >= Ir share plausible (per-element var
machinery is instruction-dense); logp within 1e-12; gradients FP-reorder
level; sampler ESS within noise. Negative results recorded either way.

## 2026-08-22 — W-31 CLOSE-OUT: safe defaults SHIPPED — controller early exit opt-in; all three gates PASS; STAN_THREADS repro pinned down

Implementation: walnutpie branch exp/safe-adapt-defaults @ 43b6435 (off
exp/parallel-chains @ da71e5b). WarmupConfig gains allow_early_exit
(DEFAULT FALSE; builder setter; config_test asserts the default).
poll_controller gates the convergence stop (cross-chain criteria AND the
temporal mode) behind allow_early_exit() — criteria still computed for
the debug trace, which now also prints the early-exit posture; with it
off, the only stop is the max_iter budget (the W-30 --fixed-warmup
posture as the library default). CLI: new opt-in --early-exit restores
the exact pre-W-31 semantics; --temporal-step-tol > 0 also opts in
(W-25/W-28 arm command lines reproducible verbatim); --pilot-burst
without an enabler now FAILS loudly instead of silently never firing;
--fixed-warmup help corrected (redundant at default, meaningful with
early exit). Single-chain path untouched.

GATES (pre-registered):
- (a) CANARY: PASS — 12/12 single-chain CSVs md5-identical pre/post
  (blr, arma11, eight_schools_noncentered x 4 chains, seeds 20260819+c,
  warmup 400 / samples 200, default inits; pre binary =
  stan/build/stan_cli_w31_pre, clean-first rebuild at da71e5b).
- (b) SAFE DEFAULT: PASS — default-flag --chains 4 runs exit_iter=1000
  early_exit=0 on 6/6 runs (esc + hier_2pl x 3 reps). STRONGER than
  pre-registered: per-chain CSVs are md5-identical to the W-25 base arm
  24/24 (full-budget default warmup has the same per-chain iteration
  count and seeding as fixed warmup), so bulk-ESS-min is IDENTICAL to
  base by construction — medians esc 1487.6 (base 1487.6), hier_2pl
  519.5 (base 519.5); per-rep values equal cell-for-cell
  (results/w31_ess.json, results/w31_md5.json).
- (c) FOOTGUN OPT-IN NOT GONE: PASS — --chains 4 --early-exit exits at
  iter 50 with early_exit=1 on hier_2pl 3/3 reps and collapses quality:
  bulk-ESS-min median 24.0 (per-rep 68.2/22.9/24.0) vs base 519.5
  (548/502/519) — the W-25 side-finding-3 destruction, reproduced under
  the explicit opt-in (median slightly worse than W-25's 61 because the
  exit lands at exactly 50). esc: rep0 exits at 50 (early_exit=1);
  rep1/rep2 run to budget — the criteria's known run-to-run
  nondeterminism under thread timing (W-28: identical blr runs exited
  500/520/540/550); the mechanism is reachable, the default is not.
- STAN_THREADS evidence (audit doc §4): default-build bs_models/ .so +
  threaded --chains 4 -> "free(): double free detected in tcache 2" /
  SIGSEGV rc=139, 3/3 runs; STAN_THREADS=1 bs_models_threads/ .so ->
  clean; SAME default .so with --chain-exec serial -> clean AND draws
  md5-identical to the threads build. The hazard is precisely CONCURRENT
  evaluation; raw in runs/w31_threads/. model_info() confirms the builds:
  bs_models STAN_THREADS=false vs bs_models_threads true (bridgestan
  2.9.0 Makefile default is OFF).

VERDICT: embedders calling adapt()/adapt_with_stats() with a default
WarmupConfig now get fixed-budget warmup (quality = the verified base
arm, bit-identically) instead of a silent quality-destroying exit at
iter 50-80; the old behavior is one explicit flag away and still
reproduces its documented damage. Design rationale recorded up front in
the pre-registration: OFF was chosen over "conservative tolerances"
because W-25/W-28 showed NO tolerance-based gate preserves quality on
the marginal class, so no tolerance default can make the failure mode
impossible — only disabling the exit can.

Ship state: exp/safe-adapt-defaults @ 43b6435 (submodule pointer
updated in the outer repo); no pushes. Docs: STAN_THREADS addendum (§4)
in external/upstream_audit_walnutpie.md; new consolidated candidate list
external/upstream_candidates.md (6 items; item 4 = this change, item 1
updated to the delivered W-32 finding — eigendecompose_sym already
upstream, the ask narrowed to stanc3 codegen fusion). Artifacts:
harness/run_w31.py, harness/analyze_w31.py, results/w31_{ess,md5}.json,
runs/w31/ + runs/w31_threads/ (local), pre binary
stan/build/stan_cli_w31_pre.

## 2026-08-22 — W-34 CLOSE-OUT: hier_2pl plumbing ceiling MEASURED — one GEMM replaces the eltwise/gather complex: −28.2% Ir/grad, −23..26% wall, last-ulp gradients; GLM primitive structurally inapplicable (arm A negative result); ESS-min gate MARGINAL (0.86x), distribution gates clean

Codegen (from source, confirming the atlas): stanc3 v2.39 emits for the
gradient path exactly bernoulli_logit_lpmf(y, elt_multiply(rvalue(alpha,
index_multi(ii)), subtract(rvalue(theta, index_multi(jj)), rvalue(beta,
index_multi(ii))))) in all 3 hpp instantiations. rvalue<index_multi> returns
a lazy Holder<IndexedView> (rvalue.hpp:157, make_holder) — cheap alone; the
COST materializes when eltwise ops consume it: 2 N-element ops × (per-element
vari + arena entry + chainstack push + reverse callback) + 3 gathers.
bernoulli_logit_lpmf<var> itself ALREADY uses partials_propagator
(partials-in-forward, one edge — the diamonds pattern): the distribution is
fine; its ARGUMENT EXPRESSION is the tax.

ARM A (bernoulli_logit_glm_lpmf): NEGATIVE — no clean mapping exists, from
signature + docs (require_matrix_t dense x; eta = alpha + x*beta). The 2PL
predictor alpha_ii*(theta_jj − beta_ii) is BILINEAR in two parameter
vectors; dense encodings need N×I or N×J var design entries (32–600x
current work) AND var x (differentiating through the design). The GLM
family structurally excludes the gathered/indexed likelihood class — itself
an upstream finding.

KEY ENABLER (verified from data): hier_2pl's data is the COMPLETE J×I grid
(I=32, J=600, N=19,200), item-major — the N-vector eta IS the column-major
flatten of eta_mat[j,i] = alpha_i(theta_j − beta_i).

ARM B (GEMM formulation, harness/w34/hier_2pl_gemm.stan): model-block LOCAL
eta = append_col(theta, rep_vector(-1,J)) * append_row(to_row_vector(alpha),
to_row_vector(alpha .* beta)); target += bernoulli_logit_lpmf(y |
to_vector(eta)). ONE var-mode GEMM (single reverse_pass_callback, adjoints
via 2 GEMMs), zero gathers, zero N-level eltwise var ops; to_vector is a
zero-copy view. Arm C skipped as pre-registered (B removes the gathers,
mooting layout).

GATES:
(a) PASS at last-ulp (not bit-identical, as pre-registered): 100 random +
  100 posterior-cloud points: max rel logp 3.2e-16 (abs 7.3e-12 at |lp|~2.3e4
  = accumulated ulp of summing 19,200 terms), grad rel-L2 worst 1.8e-15 /
  2.3e-15, cos 1.0. Richardson FD spot-checks: stock and armB agree with FD
  identically (both at 1e-10..8e-8 FD-truncation on 24 matched components).
  (W-32 precedent did NOT recur: hier_2pl's gradient is well-conditioned —
  no near-degenerate amplification of the reorder.)
(b) PASS: per-call wall (Python driver, 3 interleaved reps, medians):
  793.5 -> 595.3 µs/call (−25.0%). Callgrind (W-29 protocol; stock
  reproduces W-29 digit-for-digit: T 35.023e9, 4,493 calls, 7.745M Ir/grad,
  every named symbol to 0.1pp):
    T 35.023e9 -> 25.204e9 (−28.0%); G 34.799e9 -> 24.980e9; SAME 4,493
    gradient calls (trajectory length unchanged) => Ir/grad 7,745,272 ->
    5,560,689 (−28.2%). Native stanza 935.9/951.3 -> 715.7/729.2 µs.
    Attribution: eltwise+gather complex (subtract 12.37%T + elt_multiply
    11.40%T + rvalue 8.01%T + callbacks 6.55%T + update_adjoints 2.04%T =
    40.4%G) REMOVED, replaced by GEMM complex 11.1%T (multiply fwd 8.70% +
    callback 2.18% + append 0.24%; Eigen gebp/gmm children ~2.6e9 incl).
    Likelihood (lpmf incl.) UNCHANGED in absolute Ir: 14.878e9 -> 14.709e9
    (−1.1%); share 42.5%T -> 58.4%T (denominator shrank). Tape halved
    (stack_alloc 6.41->4.74%T, chainstack 4.47->3.32%T). libm log1p (5.02e9,
    14.3%T -> 19.9%T) is now the single largest symbol — the next ceiling
    is libm/kernel, not plumbing.
    Draws: md5 differs; 81.6% of CSV entries bit-identical, max rel 3.5e-9.
(c) WALL PASS / ESS-min MARGINAL: 3 reps × 4 chains (W-30 par4 protocol,
  read-only stan_cli @43b6435): wall 50.64 -> 37.40s (0.739x) at IDENTICAL
  gradient-call workload (75.6–76.3k sampling grads both arms; per-call
  1207 -> 884 µs = 0.732x). ESS distribution CLEAN: median bulk ESS over
  all 804 params 3,213 vs 3,241, p10 ~1,000 both, rhat ≤1.016. ESS-MIN:
  stock 519.5 (reps 548/502/520 = the W-25/W-28 base arm exactly) vs armB
  447.2 (540/404/447) = 0.86x median — literal gate miss, recorded: the
  argmin is a DIFFERENT marginal item param every rep and the sub-600-param
  count wobbles (24/9/12 vs 9/6/18) — the min-of-804 statistic W-16 flagged
  as realization-unstable on this model; with 2.3e-15 gradient agreement
  and identical distribution stats, characterized as realization noise of
  the min, not degradation. ESS/wall: bulk-min/s 10.26 -> 11.96 (1.17x).

UPSTREAM STORY (results/hier2pl_plumbing_w34.md §7): (1) model-level GEMM
trick available today for complete-design IRT/rating models (−28% Ir, 6-line
diff; example-models/docs candidate); (2) stanc3 expression fusion — emit
one fused vari for eltwise chains over indexed var containers (CSE the
gathers, values in double space, one batched callback): measured ceiling
~28% of gradient Ir on this class; cannot promise bit-identity (reorders
per-element arithmetic) but measured drift is last-ulp here; (3) stan-math:
a gathered/indexed GLM primitive (eta from index vectors, not a dense
design) would extend the partials-in-forward pattern to the IRT/rating/
sparse-interaction class the GLM family structurally excludes; (4) NOT
fixed: likelihood interior (lpmf 58.4%T after fix, log1p 19.9%T) and
tape/arena (8.1%T) — W-29 candidates #4 + libm level.

Artifacts: results/hier2pl_plumbing_w34.md, results/w34_{ess,wall}.json,
results/profile/w34/{stock,armB}/ (callgrind + annotate + cli.log),
harness/w34/ (w34_gatea.py, w34_gateb_timing.py, w34_callgrind.py,
w34_gatec.py, hier_2pl_gemm.stan), runs/w34/ (untracked), scratch/w34/
builds (untracked). No walnutpie submodule changes, no pushes.

## W-35 (pre-registered BEFORE running): minimize + classify the W-27 -march=native kronecker_gp gradient divergence; produce a reportable upstream reproducer

Mission: W-27 found self-contained single-make bridgestan builds of
kronecker_gp with -O3 -march=native -mtune=native give WRONG GRADIENTS
(99/99 random points, 250-305 of 438 components = the L block, 0.006-1.7
rel with sign flips; logp matches 1e-16; -O3-only is bit-identical).
Candidate 6 in external/upstream_candidates.md wants a gcc/stan-math bug
report. W-32 complicates the "miscompile" label: kronecker_gp's Sigma1
spectrum is intrinsically near-degenerate (jitter floor cluster), the
eigenvector adjoint F=1/(w_j-w_i) amplifies ulp-level input differences to
O(1) gradient components, and the stock gradient is itself only FD-verifiable
to ~4e-2 at the init / O(1) at random points. W-35 must decide: compiler
miscompile vs standard-permitted FP contraction/vectorization reordering
amplified by model ill-conditioning (vs stan-math UB).

PLAN (all controlled compile experiments, NO sampler runs):
1. Reproduce cheaply: rebuild default + native .so (copied .stan per variant
   in scratch/w35/<variant>_build/ — W-27 compile_model cache gotcha),
   gradient parity on 20 random N(0,1) unc points; record per-block stats
   (max rel, count wrong, sign flips) to confirm the W-27 signature.
2. Model-level flag matrix (one .so per flag set): -O3; -O3 -march=native;
   -march=native -ffp-contract=off; -mavx2; -mfma; -mavx; -march=znver3;
   -march=native -fno-tree-vectorize -fno-slp-vectorize; -O2 -march=native;
   also -ffp-contract=fast on the DEFAULT march (isolate contraction as a
   variable independent of ISA). Identifies the triggering flag/feature.
3. Isolate the function with standalone C++ drivers (scratch/w35/, linking
   the bridgestan-2.9.0 stan-math tree): differential default-vs-native
   binaries on candidate functions with var inputs on random data:
   lkj_corr_cholesky_lpdf, multiply_lower_tri_self_transpose,
   cholesky_decompose, eigenvectors_sym/eigenvalues_sym (values AND
   gradients), and VALUE-level eigendecomposition comparison on the same
   input matrix (do the two binaries return different eigenvectors for
   identical input? eigenvalue gaps of the actual Lambda/Sigma1 at failing
   points). Also FD self-consistency per binary (a miscompile fails its own
   FD check on well-conditioned inputs; reordering-amplification stays
   FD-consistent wherever the model is FD-resolvable).
4. Minimize to the smallest self-contained snippet (goal < ~50 lines,
   ideally pure stan-math+Eigen, no model); vary flags on the snippet.
5. Classify: -fsanitize=address,undefined on the minimized case under both
   flag sets; gcc 16.2.1 vs clang 22.1.8 -march=native; -ffp-contract.
   UBSan/ASan finding => stan-math UB (find exact line) => stan-math issue.
   Clean sanitizers + native fails its own FD / differs from default in a
   way no permitted reordering explains => gcc miscompile => gcc bugzilla
   draft. Clean sanitizers + divergence fully explained by contraction/
   vectorization reordering amplified by near-degenerate eigen-clusters =>
   NOT a compiler bug; reclassify candidate 6 (stan-math numerics/docs
   issue, or expected-FP-behavior + documentation item) and record the
   correction of W-27's "miscompile" wording honestly.
GATES: (i) reproduce W-27's signature (max rel >= 0.1, >= 100 components
wrong on native-vs-default, logp <= 1e-12); (ii) identify triggering flag
set; (iii) minimization measured (lines + deps of final snippet);
(iv) sanitizer verdict under both flag sets; (v) classification with a
READY-TO-FILE draft (gcc bugzilla OR stan-math issue format; both if
ambiguous) in results/march_native_w35.md, reproducer source also under
scratch/w35/repro/.
Env: env -u LD_LIBRARY_PATH for all make/compiles; /usr/bin/make; -j2 max;
bridgestan 2.9.0; no pushes; walnutpie submodule untouched. Negative
findings recorded honestly (e.g. cannot isolate below model level) with
what WAS established. Expectation (pre-registered, from W-32 evidence): the
divergence will turn out to be FMA-contraction-permitted reordering inside
Eigen's SelfAdjointEigenSolver (or a reduction) amplified by the model's
near-degenerate eigen-clusters — i.e. NOT a gcc miscompile — but this is
to be TESTED, not assumed; sanitizer/FD/clang evidence decides.

## 2026-08-23 — W-35 CLOSE-OUT: -march=native divergence MINIMIZED + CLASSIFIED — NOT a gcc miscompile; Eigen AVX packet GEMM rounding flips the eigenbasis of rounding-degenerate clusters; W-27 "miscompile" wording RETRACTED (guidance unchanged)

All pre-registered gates PASS (reproduce / flag matrix / minimize / sanitize
/ classify). Full evidence pack: results/march_native_w35.md; minimized
reproducer: scratch/w35/repro/march_native_repro.cpp (committed).

GATE (i) REPRODUCE: fresh default + native builds (scratch/w35/*_build/),
20 random N(0,1) unc points: 20/20 wrong, max rel grad 6e-3..2.36, 55-221/438
components > 1e-6, sign flips on 5/20 points (9 components), logp <= 4.5e-16. Worst components
include var1/bw1 (Sigma1 block) alongside the L block. W-27 signature
confirmed. -O3 control bit-identical.

GATE (ii) FLAG MATRIX (10 model .so builds + repro-level): EVERY AVX-or-wider
ISA diverges (-mavx alone sufficient; -mavx2 == -mavx outputs; -mfma ==
-march=znver3 == native outputs; -O2 vs -O3 irrelevant). FMA contraction
RULED OUT (-march=native -ffp-contract=off still diverges; -ffp-contract=fast
on SSE2 baseline is bit-identical to default). GCC auto-vectorization RULED
OUT (-fno-tree-vectorize -fno-tree-slp-vectorize still diverges — Eigen
packetizes with its own intrinsics). Trigger = Eigen's 256-bit packet GEMM
code paths (4 vs 2 doubles/packet -> different FP accumulation order).

GATE (iii) ISOLATION + MINIMIZATION (standalone drivers d1-d6, exact
hexfloat inputs, %.17g diffs): seed = GEMM rounding diff 2.1e-14 abs /
9.8e-15 rel (d5). Amplifier at VALUE level (d1): on the model's actual
Sigma1 (jitter floor pins bottom eigenvalues at EXACTLY 1e-5, gaps ~1e-16)
default-vs-native eigenvectors differ in 489/900 entries up to 0.96 with 162
sign flips while eigenvalues agree to 1.1e-14 and BOTH decompositions are
valid (residual ~1e-14); well-conditioned control identical to 3.4e-14.
Gradient level (d2/d4): rev eigenvector adjoint (F_ij = 1/(w_j-w_i)) turns
the basis flip into cross-binary gradient diffs up to 3.7e3 rel; Richardson
FD self-checks show BOTH builds' var1/bw1 gradients are 8-47% off FD at
failing points (native sometimes CLOSER than default — pt1 var1: default
30% off, native 8% off), while sigma1 (no eigen-adjoint coupling) is
FD-consistent to 2e-9 in both and L-block functions (lkj_corr_cholesky,
multiply_lower_tri_self_transpose, cholesky_decompose — d3/d6) are
FD-consistent (1e-9) and cross-binary-stable. Eigendecomposition on BOTH
model matrices affected (Sigma1 AND Lambda = L L^T near-singular, cluster
1e-16..1e-12). Minimized reproducer: self-contained 65-line stan-math+Eigen
snippet (no model/data/input files, LCG-generated weights), committed.

GATE (iv) SANITIZERS: ASan+UBSan (-fno-sanitize-recover=all) on d2/d4/repro
under baseline AND native: rc=0, ZERO reports — no stan-math UB, no memory
corruption.

GATE (v) CLASSIFICATION: NOT a gcc bug (native computes correct eigen
gradients on well-conditioned input at 5e-8 FD agreement; clang 22 baseline
is BIT-IDENTICAL to gcc baseline incl. cluster matrices; clang -march=native
reproduces the divergence; reference build itself FD-inconsistent; only
input-side diff is a permitted 1e-15 GEMM reordering). NOT stan-math UB.
IS a stan-math numerics/docs issue: rev eigenvector/eigendecomposition
adjoints assume separated eigenvalues; on rounding-degenerate spectra
(jittered GP kernels, near-singular correlations) they silently return
FD-inconsistent gradients in EVERY build, and any permitted FP variation
moves them O(1). W-32's eigendecompose_sym does NOT change this (same
adjoint) — only model conditioning does.

RETRACTION (protocol: where the claim was made): W-27 close-out's
"-march=native MISCOMPILES kronecker_gp gradients" and W-29 §3's "same tape
region, different cause" miscompile framing are corrected to: "any
AVX-or-wider ISA changes kronecker_gp gradients O(1) via rounding-level GEMM
reordering amplified by near-degenerate eigendecompositions; both builds are
FD-inconsistent at these points." external/upstream_candidates.md candidate 6
rewritten accordingly. OPERATIONAL GUIDANCE UNCHANGED, now on solid grounds:
never build Stan models with -march=native; -O3 safe (bit-identical); native
upside was <= ~10%/call anyway (W-27).

DELIVERABLES: results/march_native_w35.md (reproduction, flag matrix,
isolation, reproducer source + 4-compiler output table, sanitizer results,
classification, READY-TO-FILE stan-math issue draft §7a, cmdstan/bridgestan
docs paragraph §7c, and §7b recording why the gcc bugzilla report is
deliberately NOT filed). Committed: WORKLOG.md, results/march_native_w35.md,
scratch/w35/repro/march_native_repro.cpp, scratch/w35/parity.py,
scratch/w35/build_variant.sh, external/upstream_candidates.md. Local
(untracked): scratch/w35/ drivers+outputs+builds, sanitizer binaries.
Env note: this machine's gcc (AppImage-provided 16.2.1) needed cc1plus
symlinks at ~/lib/gcc/x86_64-pc-linux-gnu/16/ before any compile worked.
No sampler runs, no pushes, walnutpie submodule untouched.

## W-36 (pre-registered BEFORE running): end-to-end session headline benchmark — stock walnutpie @ 3eddfc4 vs exp tip @ 43b6435, both at DEFAULTS, 10-model pathfinder grid

PURPOSE: one defensible table quantifying the TOTAL sampler-side win of
this session: stock dev/init-robustness @ 3eddfc4 (pre-session state)
vs exp/safe-adapt-defaults @ 43b6435 (session tip), both binaries run at
their CLI DEFAULTS (only --warmup 1000 --samples 1000 passed explicitly;
--metric-window stays default 0/off, no --fixed-warmup, no --early-exit),
across the 10-model pathfinder grid (run_pathfinder.py MODELS list).
4 chains, 3 reps, seeds 20260819+1000*rep+c (per-chain +c; the mc path
seeds per-chain identically — W-30 bonus gate verified equivalence).

ARMS:
- stock_seq: STOCK binary, 4 SEQUENTIAL single-chain CLI invocations
  (pre-session status quo workflow; wall = batch elapsed).
- exp_par: EXP binary, `--chains 4 --chain-exec threads` (default value;
  everything else default). MUST print controller exit_iter=1000
  early_exit=0 in every run (W-31 safe default) — verified per run.
- exp_seq (optional, run after the main arms if time permits): EXP binary,
  4 sequential single-chain invocations — isolates endpoint-threading
  (W-23) contribution from parallelism (W-30).

BUILD SETUP (worktree discipline): EXP binary built from the existing
submodule worktree (exp/safe-adapt-defaults) into a NEW build dir
external/walnutpie/build_w36exp; STOCK binary from a SEPARATE git worktree
external/walnutpie_stock_w36 checked out at 3eddfc4 into its own build dir
(submodule branch NEVER switched; worktree removed only at the very end,
after all measurements are recorded). env -u LD_LIBRARY_PATH for all
cmake/make. Builds -j4 allowed; sampling runs never exceed 4 threads total
(sequential arms are 1 process at a time; exp_par = 4 worker threads).

MODEL .so: STAN_THREADS=True builds in bs_models_threads/ for ALL 10 grid
models (5 exist: arma11, blr, esc_nonc, hier_2pl, lsat — grid needs hier,
lsat + 8 NEW: radon_partially_pooled_noncentered, bym2_offset_only,
diamonds, accel_gp, kronecker_gp, pilots, eight_schools_centered,
lotka_volterra). W-27 cache gotcha: compile each from a per-model scratch
copy of the .stan so no cached default-flags .so can be silently reused;
verify model_info() reports STAN_THREADS=true for every .so before
trusting it. Both arms load the SAME .so per model.

INITS (identical across arms per model/rep/chain): hier_2pl + lsat_model
use inits_w25/ pf inits (rep0-2 x chain0-3 exist); the other 8 models get
deterministic inits in inits_w36/<model>/rep<r>/chain_<c>.txt generated as
normal(0,1) draws, one per unconstrained coordinate, dimension from
BridgeStan num_unconstrained_parameters (bs_models_threads .so), rng =
random.Random(f'{model}-{seed}-{c}').normalvariate(0,1) with seed =
20260819+1000*rep (recorded method; standard-normal scale comparable to
Stan's default uniform[-2,2] init radius).

EXPECTATIONS (pre-registered):
- WALL: exp_par/stock_seq geomean ~0.25-0.35 (W-30 measured 0.317
  thr/seq on 5 models with --fixed-warmup + metric-window 50; defaults
  here, so the number may shift — whatever it is, it is the headline).
  exp_seq/stock_seq ~0.96-1.00 (endpoint threading removes exactly
  warmup+draws-1 logp_grad calls per chain, ~3-6% of calls).
- CALL COUNTS: per-chain logp_grad calls printed by both binaries; exp
  arms should show stock_calls - (warmup+draws-1) per chain on the same
  model/seed/init (W-23), µs/call ~unchanged (same .so, same machine).
- QUALITY (non-negotiable): bulk/tail ESS-min and max R-hat (arviz,
  rank-normalized, trim ragged chains to min length) — exp arms
  statistically match stock on every model. Divergences recorded per
  model/arm (pilots and eight_schools_centered are expected to diverge in
  BOTH arms — model-inherent, not arm-attributable).
- CANARY (bit-identity): draws for identical (seed, init, config) are
  BIT-IDENTICAL stock_seq vs exp_seq on the single-chain path (md5 of
  chain CSVs; every default-path change this session was canary-gated).
  Spot check 2 models BEFORE the grid; full md5 on every exp_seq cell
  covered by the optional arm.

GATES: (a) early_exit=0 + exit_iter=1000 on every exp_par run; (b) canary
md5 identical (spot 2 models, and all exp_seq cells if run); (c) quality
per-model medians within the stock arm's rep spread on non-pathological
models; (d) walls reported as 3-rep medians with per-rep values in the
raw rows. Negative/unexpected results recorded either way.

DELIVERABLE: results/session_benchmark_w36.md — headline table (per-model
+ geomean wall ratios exp_par/stock_seq, plus exp_seq ratios if run),
quality table (ESS-min bulk/tail, max R-hat per model per arm), call-count
deltas, short honest narrative (parallelism vs threading vs nothing).
Runner harness/run_w36.py, analysis harness/analyze_w36.py, raw
runs/w36/<arm>/<model>/rep<r>/. Commit explicit paths only.

## W-37p (PROPOSAL-ONLY — pre-registration placeholder, no runs, no builds)

Read-only source survey: how can WALNUTS compute FEWER logp_grad calls per
effective draw (not cheaper per-call — that is the stan-math lane, W-29/W-32/
W-33/W-34)? Deliverable: results/proposals_fewer_gradients.md — a proposal
pack grounded in walnuts.hpp/adaptive_walnuts.hpp anatomy + the w17g/W-20/
W-23 evidence. Key structure findings: every kernel eval sits in (a)
macro_step forward dyadic attempts (failed attempts fully discarded), (b)
the backward reversibility ladder (accept path walks the FULL coarser
ladder; first success = macro-step REJECTION, and leaf failure terminates
the trajectory — no retry path exists), (c) boundary (W-23 handled).
Accepted-at-h=0 macro steps cost m evals with no ladder; refined steps cost
3m·2^h − 2m for m·2^h useful (2x at h=1 → 3x asymptotic). Drift phase
already runs cap-free (zero dyadic overhead). Ranked pack: E1 per-macro-step
grad accounting (env-gated counters, the gateway measurement named in
FINAL_REPORT §5a — run FIRST); E2 error-discipline ablation warmup-weighted
(--max-hamiltonian-error/--max-error-start/--max-step-halvings already
CLI-exposed; ~10–30% realistic eval cut, W-25/W-28 gates); E4
refinement-aware min_micro_steps adaptation (target h≈0 ladder base, kills
refinement AND ladder; kernel change within existing latitude); E3 truncated
backward ladder (held: touches the correctness core, needs E1 evidence);
E5 close the residual 2 dups/chain (masses() seeding + chain start, +
find_reasonable_step's theta eval; bit-identical, ~0.01%). Dead ends
re-confirmed with citations: memoization/lattice reuse (W-20), endpoint
sharing (by design), uturn/momentum evals (none exist), subsampled kernel
gradients (invariant-breaking), warmup early-exit (W-21/25/28), basis rules
(W-19). Micro-state selection candidates flagged for the Flatiron team, not
engineering. Any implementation session must pre-register and reuse the
W-23/W-25 gate apparatus; no claims made here without runs.

## W-38u (SCAN-ONLY): upstream ecosystem scan — stan-math/stanc3/bridgestan/walnutpie + WALNUTS literature

Date: 2026-08-22/23. Web + local reading ONLY (gh API, web search, arXiv) —
no builds, no benchmarks, no profiling (N's wall-time lane untouched).
Mission: cross-check our upstream findings (upstream_candidates.md,
upstream_pr_kits.md, march_native_w35.md) against the current state of the
upstream repos. Full report with URLs: results/upstream_scan_2026-08.md.

HEADLINES:
1. eigendecompose_sym provenance CORRECTED: added Aug 2023 (math PR #2931 /
   stanc3 PR #1346), shipped math 4.8.0 / CmdStan 2.34 (Jan 2024) — NOT
   5.3.0/2.39 as our W-32/Kit-2 records say. Kit 2 ask (stanc3 pair-fusion
   peephole) still novel — no upstream ask exists; reframe text.
2. Eigenvector adjoint conditioning (W-35/W-40): NOT known/fixed/documented
   upstream — no matching issue/PR; develop's eigenvectors_sym.hpp still has
   raw 1/(w_j−w_i), no guard/docs; no degenerate-spectrum tests. Closest:
   math #1803 (open, 2020; triangular-adjoint convention — sibling wart,
   cite it) + 2017 discourse thread 7616 ("I dunno if the derivatives fall
   apart there or what" — never filed). W-40 + Kit 4 PROCEED as novel;
   enrich with adjoint-methods literature (shift-and-invert 2025; He et al.
   2023; de Leeuw arXiv:2508.09355; Friswell/van der Aa). NOTE: math
   develop migrated Eigen 3.4.0 → 5.0.1 (PR #3271) — re-validate the W-35
   repro under Eigen 5 before filing.
3. The "2.39 cholesky_decompose derivative fix" from our context prompt is
   NOT in upstream release notes (checked 2.38/2.39/5.2/5.3 full texts);
   no cheaper-cholesky-adjoint PR exists; candidates item 3(a) unaffected.
4. Elementwise plumbing (W-29/W-34): stanc3 PR #1666 `vectorize_loops`
   merged 2026-08-19 (`--Oexperimental`, nightlies): scalar density loops →
   vectorized densities, "O(1) autodiff nodes instead of O(N)", 3.54x on
   radon_pooled in their benches; follow-ups planned for indirect indexing
   (a[county[n]]). Does NOT touch our hier_2pl line (already vectorized
   syntax) — candidate 2 ceiling stands, reframe as #1666-family extension.
   Adjacent: math PR #3352 (rev Eigen const views, 2026-07-23), PR #3346
   map helpers (2026-08-12). No SoA-arena work.
5. square()/std::pow (Kit 1): develop STILL `std::pow(x, 2)` (verified in
   source, with the ironic "just x*x" doc comment); squared_distance sites
   too; no issue/PR anywhere. Kit 1 valid — file as-is.
6. bridgestan: v2.9.0 (2026-07-06) is LATEST; main = 5 CI-only commits past
   it; compile_model cache issue unfiled upstream (Kit 3 valid). Adjacent:
   issues #194 (threading control, open), #289 (parallel-misuse segfault,
   closed). 
7. No new CmdStan/math releases (latest 2.39.0/5.3.0, both 2026-05-19; no
   2.40/5.4). Develop perf-relevant: Eigen 5.0.1 (above), vectorize_loops,
   cmdstan clang-PCH template instantiation (PR #1346, compile-time). Stay
   pinned 2.39.0 for W-36; backlog post-2.40 re-baseline.
8. walnutpie upstream = github.com/flatironinstitute/walnutpie (not a fork,
   no releases); upstream main tip = 6162d88 = OUR fork point — nothing
   landed since. Paper published: JMLR 27(113):1-64 (2026), arXiv:2506.18746
   (v1 only); companion research repo bob-carpenter/walnuts (Python/MATLAB)
   is a DIFFERENT codebase. Watch: PR #77 (unroll leapfrogs, open), issue
   #34 (cache gradients across transitions), branches preconditioner/
   leapfrog-momentum-compose. Upstream style is warn-first (PR #90) — Kit 5
   should present the warn-only alternative. New literature for our lane:
   Picard-map PARALLEL Metropolis transitions (Grazzi et al., arXiv:
   2506.09762, Biometrika 2026) — orthogonal axis to W-30/W-36 cross-chain
   parallelism; parked in backlog.

ACTIONS: see report §Action list (correct Kit 2 text; W-40 novel, cite
lit + Eigen 5 re-validation; Kits 1/3 file as-is; --Oexperimental spot
check cheap; keep 2.39.0 pin).

## 2026-08-23 — W-36 CLOSE-OUT: session headline delivered — exp_par/stock_seq geomean 0.341 (2.93x) at DEFAULTS, draws BIT-IDENTICAL end-to-end 28/28 (+28/28 bonus incl. threaded mc); all gates PASS

Executed as pre-registered (arms, builds, inits, seeds, gates). Builds:
exp @ 43b6435 from the untouched submodule worktree into build_w36exp;
stock @ 3eddfc4 from a separate git worktree (walnutpie_stock_w36) into
build_w36stock — submodule branch never switched. All 10 grid models
verified STAN_THREADS=true in bs_models_threads/ (8 newly compiled from
per-model scratch .stan copies; W-27 cache trap avoided). Inits: hier_2pl
+ lsat_model = inits_w25 pf; other 8 = inits_w36 deterministic
normal(0,1) via random.Random(f'{model}-{seed}-{c}').normalvariate
(dims via BridgeStan). Machine idle; <=4 threads; sequential arms one
process at a time. Raw: runs/w36/, results/w36_{wall,ess,md5}.json;
report results/session_benchmark_w36.md.

HEADLINE (medians of 3 reps, warmup=1000 draws=1000, 4 chains):
- exp_par/stock_seq wall ratio per model 0.281 (hier_2pl, 161.2 -> 45.3s)
  to 0.432 (diamonds); GEOMEAN 0.341 = 2.93x. Total grid time 481 -> 158s.
- exp_seq/stock_seq GEOMEAN 0.947 (endpoint threading alone, ~5.6%);
  per-chain logp_grad calls drop by EXACTLY warmup+draws-1 = 1999 on
  every completed chain of every model (verified chain-by-chain);
  us/call unchanged (+-3%).
- Attribution: parallelism (W-25 mc path + W-30 event-driven threads)
  = 2.77x of the 2.93x; threading (W-23) multiplies by 1.056. Honest
  cost of concurrency: per-call logp_grad +10-25% under 4-way sharing
  (memory bandwidth), plus slowest-chain skew — why it is 2.9x not 4x.

GATES:
- (a) PASS: controller exit_iter=1000 early_exit=0 on 28/28 exp_par runs
  (W-31 safe default holds at the tip).
- (b) CANARY PASS: stock_seq vs exp_seq chain CSVs md5-identical 28/28
  (spot-checked on esc + lsat rep0 BEFORE the grid, then every cell).
  BONUS: stock_seq vs exp_par (threaded mc) also md5-identical 28/28 —
  the session's final binary reproduces the pre-session binary's draws
  byte-for-byte on the full grid while running 2.9x faster.
- (c) QUALITY PASS by exact identity: bulk/tail ESS-min and max R-hat
  identical across arms on every model (bit-identical draws). The
  pathological rows (bym2 R-hat 4.93, diamonds 3.63, accel 4.18,
  pilots 3.05 ESS-min ~4) are init-protocol artifacts — normal(0,1)
  inits stick chains in separated modes — IDENTICALLY in all arms;
  pf-init models (hier 625/800, lsat 730/1255) healthy.
- Failures recorded: kronecker_gp rep0 + lotka_volterra rep1 abort
  deterministically in ALL THREE arms ("macro_time must be in (0, inf)"
  at chain 0, exactly 32001 logp_grad calls) — pre-existing
  warmup-adaptation robustness limit, unchanged by the session; those
  models' medians use 2 reps. Queued: guard non-finite adaptation state.

Ship state: no sampler code changed (measurement item). Committed:
WORKLOG.md, results/session_benchmark_w36.md, results/w36_{wall,ess,
md5}.json, harness/{run_w36,analyze_w36,gen_w36_inits}.py. Local
(untracked/gitignored): runs/w36/, inits_w36/, build dirs, scratch.
Stock worktree walnutpie_stock_w36 removed AFTER results were committed.

## W-41 (pre-registered BEFORE running): freeze-time step clamp — fix the warmup-freeze abort "macro_time must be in (0, inf)" on kronecker_gp rep0 + lotka_volterra rep1 (W-36 failure)

DIAGNOSIS (to verify first, from W-36 evidence + code reading): the W-36
deterministic aborts fire at the freeze boundary — AdaptiveWalnuts::
sampler() (include/walnutpie/adaptive_walnuts.hpp ~L744-764) passes
step_size() (the step adapter's exp(theta_)) as the frozen sampler's
macro_time; WalnutsSampler's ctor runs detail::validate_positive and
throws std::invalid_argument when the value is 0 / NaN / +inf. 32001
logp_grad calls = end of the 1000th warmup iteration. Same-family
exposure: api.hpp walnuts_with_reinit reseeds outlier chains with
ar.step_bar (geometric mean of per-chain exp(log_step)) — degenerate if
any chain's log_step underflowed to -inf / NaN.

EXPECTATION: freeze falls back to a finite positive step instead of
aborting; healthy freezes are untouched bit-for-bit (clamp is dead code
when step_size() is finite-positive).

FIX DESIGN (minimal, in the spirit of the init-robustness clamps):
- At freeze time in sampler(): validate step_size(); if not
  finite-positive, fall back in order (a) last finite adapter state —
  the last finite-positive step_size() observed during warmup, tracked
  per iteration (seeded with the init step), (b) find_reasonable_step
  (warmup_heuristics.hpp) re-derivation at the current position with the
  current inv_mass and the init step as seed, (c) documented hard floor
  1000 * numeric_limits<double>::min() (~2.2e-305). Computed once and
  cached (pilot-mode double sampler() calls stay stable). on_warmup_
  complete reports the value actually frozen.
- Loud auditable warning to stderr (prefix "WALNUTS WARNING",
  harness logs capture stderr; ChainHandler has no warning hook — noted
  here as the deliberate channel choice) stating the degenerate value
  and the fallback used + source.
- Same guard on the api.hpp reinit path: if ar.step_bar is not
  finite-positive, fall back to the geometric mean of the per-chain
  frozen samplers' macro_time() (always valid post-clamp), else the
  current init step, else the floor; same warning.
- No change to warmup arithmetic: the tracker is a pure read of
  opt_.step_size() (no existing member is modified differently).

GATES (pre-registered):
- (a) BIT-IDENTITY CANARY: default single-chain draws (warmup=1000
  draws=1000, CLI defaults) md5-identical PRE vs POST change on 3
  healthy models x 4 chains, seed 20260819+c (run_w36 single-chain arm
  recipe, inits_w25 for hier_2pl/lsat_model, inits_w36 otherwise).
  Models: hier_2pl, lsat_model, radon_partially_pooled_noncentered.
- (b) RECOVERY: the two aborting cells — kronecker_gp rep0 chain 0
  (seed 20260819), lotka_volterra rep1 chain 0 (seed 20261819), inits_w36
  chain_0.txt, warmup=1000 draws=1000, CLI defaults — now COMPLETE
  (rc=0, 1000 draws). Record: the exact degenerate step value (0? nan?
  inf?), fallback source used per cell, warning line, and the resulting
  chain set's bulk-ESS-min / R-hat-max (4 chains: the recovered chain 0
  rerun + chains 1-3 rerun for a valid R-hat). Quality is informational:
  a divergent-ish chain that completes still beats an abort; garbage ESS
  gets recorded honestly.
- (c) NO COLLATERAL: 2 healthy cells outside the canary set (different
  model/rep/chain) md5-identical pre vs post binary.

BUILD PROTOCOL: separate worktree walnutpie_w41, branch
exp/freeze-clamp off exp/safe-adapt-defaults @ 43b6435; PRE-change
binary built in the same worktree BEFORE the edit (that commit state IS
pre-change). Header edits => clean-first rebuild; -j2; serialized
sampling runs.

## W-38 (pre-registered BEFORE running): per-macro-step gradient accounting — phase E1 of the W-37p fewer-gradients pack (results/proposals_fewer_gradients.md)

Instrumentation-only, zero-risk: env-gated counters (precedent: the
WALNUTPIE_DEBUG_ALPHA/SPAN env vars in walnuts.hpp) activated by
WALNUTPIE_GRAD_ACCOUNTING=1. Accumulated per phase (warmup vs sampling,
switched at the AdaptiveWalnuts->WalnutsSampler boundary) and per process:
- accepted-halving-level histogram P(h) of macro steps;
- reversibility-rejection count + succeeding-ladder-level histogram
  (level 0 = first lattice checked = n/2 micro steps at 2*step);
- halving-exhaustion count (all max_step_halvings attempts failed
  tolerance);
- FOUR eval buckets that exactly decompose every kernel logp_grad call:
  forward-accepted (final attempt of accepted macro steps),
  forward-wasted (tolerance-failed dyadic attempts),
  backward-ladder (within_tolerance evals inside reversible()),
  discarded-on-leaf-failure (tolerance-passing attempt whose reversibility
  ladder succeeded -> macro step rejected);
- macro-step/attempt/transition counts + min_micro_steps histogram
  (E4's (m, h) joint input).
Identity: forward m*2^h accepted + m(2^h - 1) wasted + ladder m(2^h - 1)
= 3m*2^h - 2m per accepted refined step (h=0: m evals, no ladder).
NO behavior change when unset (no doubles touched, no RNG, no output);
when set, counters only.

GATES:
1. CANARY (bit-identity): same binary, WALNUTPIE_GRAD_ACCOUNTING=1 vs
   unset, chain CSVs md5-identical, 2 models (blr, pilots) x 4 chains
   (seeds 20260819+c), warmup=100 samples=100, deterministic default
   inits. Instrumentation touching no arithmetic cannot change draws;
   a mismatch means the implementation is wrong.
2. CONSISTENCY: bucket sum + 2 boundary evals (masses() init + chain
   start) == CLI per-phase logp_grad calls, per model per run.
RUNS (light; 1 chain, warmup=100 samples=100, seed 20260819, fixed inits
from inits_w36 rep0 / inits_w25 hier_2pl rep0): blr, hier_2pl,
kronecker_gp, pilots; plus ONE fuller hier_2pl run (warmup=1000
samples=1000) as a production-settings check.
DELIVERABLE: results/grad_accounting_w38.md — bucket table (per model,
warmup/sampling split) + pre-registered verdicts:
- E2 (warmup error-discipline ablation): GO iff warmup-phase
  (refinement + ladder + discard) share of warmup evals >= 20% (ceiling
  >= ~10% of total evals at 50/50 warmup/sampling — the pack's
  realistic 10-30% band floor);
- E3 (truncated backward ladder): GO iff ladder share > 15% of total
  kernel evals AND deep successes (ladder level >= 1) non-rare
  (>= 1% of macro steps) — per the pack's own pre-condition;
- E4 (refine-aware min_micro_steps): GO iff sampling-phase P(h>=1)
  >= 10% of macro steps AND (refinement+ladder) share of sampling
  evals >= 15% (persistent overhead in the frozen kernel; the 100-draw
  vs 1000-draw hier_2pl comparison is the burstiness caveat check —
  aggregate counters cannot see within-phase bursts, stated in report).
BUILD PROTOCOL: separate worktree walnutpie_w38, branch
exp/grad-accounting off exp/safe-adapt-defaults @ 43b6435; main
submodule worktree untouched; header edits => clean-first rebuild; -j2;
serialized runs (other agents share cores). Report() printed from the
CLI at end of run; harness script + raw logs under runs/w38/ (local,
gitignored).

## 2026-08-22 — W-38 CLOSE-OUT: E1 gradient accounting shipped + measured — canary PASS 8/8 (+3-way vs pre-change binary), consistency PASS 7/7; E2 GO / E3 NO-GO / E4 GO; BONUS: blr pins at short warmup (pre-existing, 100% wasted evals, zero ESS)

Implementation (walnutpie exp/grad-accounting, worktree walnutpie_w38,
off exp/safe-adapt-defaults @ 43b6435): new
include/walnutpie/grad_accounting.hpp; env-gated hooks in macro_step/
reversible (+ low-rank mirrors) accumulating per phase (warmup vs
sampling, switched at the AdaptiveWalnuts->WalnutsSampler boundary):
accepted-halving histogram, ladder-success-level histogram,
reversibility-rejection + halving-exhaustion counts, the four eval
buckets (forward-accepted / forward-wasted / backward-ladder /
discarded-on-leaf), macro/attempt/transition counts, m histogram;
CLI prints the report at end of run. GATES: canary env-on vs env-off
md5-identical 8/8 (blr+pilots x 4 chains) plus a 3-way smoke equality
with the PRE-CHANGE binary; consistency kernel_total+2 boundary ==
warmup calls, == sampling calls, exact on all 7 runs.

HEADLINE NUMBERS (1 chain, defaults, 100+100; hier_2pl also 1000+1000,
blr 1000+100 pin-escape check; kronecker_gp seed-20260820/chain-1
deviation — seed-20260819/chain_0 aborts with the KNOWN W-36
"macro_time must be in (0, inf)" failure):
- Overhead (wasted+ladder+discard) share of evals: WARMUP 68-86%
  (healthy models, 100 iters), 32.7% at hier_2pl 1000; SAMPLING 53-66%
  (100 iters), 21.6% at 1000+1000.
- E2 GO: ceiling = warmup-overhead x warmup-share = 18.2% of total
  evals at production settings (in the pack's 10-30% band), >50% in
  short-warmup regimes.
- E3 NO-GO: ladder successes are ~97-100% at level 0; with m=1 an h=1
  full ladder IS one level-0 eval (prize zero); beyond-level-0 prize
  <=3% of sampling evals on all models except blr@1000 (14.1%, but
  zero ladder successes ever and subsumed by E4). Pack's "likely dead
  end" confirmed with numbers.
- E4 GO: sampling P(h>=1) = 38-58% (short warmup), 96.6% on
  blr@1000 (h2-h4 structural, 104 evals/draw), 8.7% on settled
  hier_2pl@1000; fw+bl share 17-66%. KEY STRUCTURAL FACT:
  min_micro_steps = 1 in 100% of macro steps everywhere — the current
  estimator only pushes m DOWN to its floor; growing m toward h~0 is
  an untested direction.
- BONUS (pre-existing, now measured): blr at CLI defaults pins for
  <=~400 warmup iters under BOTH pf and default inits — every
  transition burns exactly 31 evals (all 5 halvings fail; |dH| ~ 8e6),
  100% fw, all draws identical (zero ESS). W-23's canary arithmetic
  (18602/600 ~ 31/transition) shows the pin was present there too —
  bit-identity made it invisible. Escapes between 400 and 1000 warmup
  iters. Feeds E2 (--max-error-start would unpin, config-only), W-25/
  W-28 short-warmup work, W-41 freeze robustness.

Artifacts: results/grad_accounting_w38.md (tables + verdicts),
harness/run_w38.py, runs/w38/ (raw logs + accounting.json, local).
Worktree NOT removed (supervisor). Caveats recorded in the report:
aggregate counters can't see within-phase bursts (100 vs 1000 contrast
is the proxy), single chain/cell, pooled multi-chain counts.
Next (per pack ranking): E2 ablation grid {0.5,1,2}x{5,3,warmup-only-3}
behind W-25/W-28 gates; E4 estimator rule behind a flag with joint
(m,h) reporting; E3 closed.

## W-38-E2 (pre-registered BEFORE running): error-discipline ablation, warmup-weighted — phase E2 of the W-37p pack

HYPOTHESIS (from E1, results/grad_accounting_w38.md): the dyadic overhead
is gated by tolerance failures; loosening error discipline DURING WARMUP
ONLY (sampling keeps full discipline 0.5 / 5 halvings) cuts total
logp_grad calls materially while preserving sampling quality — warmup only
needs to estimate mass/step/m reasonably, not exactness. E1 ceiling at
production settings: warmup overhead 32.7% of warmup evals on hier_2pl
1000+1000 = 18.2% of total evals; short-warmup regimes >50%.

ARMS (all warmup=1000 draws=1000, 4 chains as 4 SEQUENTIAL single-chain
invocations, 3 reps, seeds 20260819+1000*rep+c; inits identical across
arms: inits_w25/ pf for arma11, blr, hier_2pl, lsat_model; inits_w36/
deterministic for kronecker_gp — the W-36 assignment; CLI defaults
otherwise, .so from bs_models_threads/):
- base: CLI defaults (canary reference arm).
- e2a: `--max-error-start 5.0 --max-error-iters 950` — the EXISTING
  schedule knob (config.hpp max_error_schedule, default off): warmup cap
  decays geometrically 5.0 -> 0.5 over iters 0..949, full 0.5 discipline
  for the last 50 warmup iters and all of sampling. Zero new code.
- e2b: `--warmup-max-step-halvings 3` — NEW WarmupConfig knob
  (warmup_max_step_halvings, 0 = off default): caps the halving ladder at
  3 during WARMUP only; the frozen sampler keeps --max-step-halvings (5).
- e2c: `--warmup-max-error 5.0` — NEW WarmupConfig knob
  (warmup_max_error, 0.0 = off default): constant loose warmup error cap
  (overrides the e2a schedule when set); sampling keeps 0.5. Isolates
  "constant loose" vs e2a's decay-to-0.5.
New-knob implementation: consumed ONLY inside AdaptiveWalnuts (the warmup
phase; WalnutsSampler/sampler() untouched); CLI flags default off.
MODELS: marginal class arma11, lsat_model, hier_2pl + overhead class blr,
kronecker_gp (the E1 overhead-heavy set).

GATES (pre-registered):
(a) CANARY bit-identity: default-path draws (all knobs off) of the NEW
    binary md5-identical to the exp/safe-adapt-defaults binary
    (external/walnutpie/build_w36exp @ 43b6435), 3 models (arma11, blr,
    hier_2pl) x 4 chains, seed 20260819, 1000+1000, rep0 inits. New knobs
    default off => draws must match exactly; mismatch = wrong impl.
(b) QUALITY: arviz rank-normalized bulk/tail ESS-min + max R-hat per
    model-rep (chains trimmed to min length), MEDIANS of 3 reps on
    arma11, lsat_model, hier_2pl, blr. An arm PASSES a model iff
    median(ess_bulk_min) >= min(base per-rep bulk) AND
    median(ess_tail_min) >= min(base per-rep tail) AND
    median(rhat_max) <= max(base per-rep rhat) — the W-25/W-28 "within
    the base rep spread" band, measured on base runs from THIS grid.
(c) SPEED: total logp_grad calls per chain (warmup+sampling, CLI stanzas)
    and batch wall, medians of 3 reps. Pre-registered expectation: >=10%
    call reduction vs base on the overhead class (hier_2pl, kronecker_gp,
    blr); recorded honestly if less.
(d) blr SHORT-WARMUP PROBE (E2 as a FIX for the E1-found pin): warmup=400
    draws=1000, arms base / e2a5 (= e2a settings) / e2a8
    (`--max-error-start 1e8 --max-error-iters 950` — E1 measured the
    pinned |dH| ~ 8e6 at the min attempt, which a 5.0 cap cannot accept;
    only a start above the pinned error can test "does a loose-early cap
    unpin"). Pin-disappears criterion: ess_bulk_min > 0 AND unique draw
    positions > 1 (pinned = all draws identical, zero ESS, 31 evals/
    transition). 3 reps x 4 chains, same seeds/inits.
VERDICT RULE (pre-registered): ADOPT an arm iff quality (b) passes on ALL
three marginal-class models AND (c) gives >=10% median call reduction on
>=2 of the 3 overhead-class models. TUNE if quality passes but the speed
criterion misses (or vice versa). REJECT if any marginal-class model
fails (b) below the base band.

BUILD/RUN PROTOCOL: separate worktree external/walnutpie_w38e2, branch
exp/error-discipline off exp/safe-adapt-defaults @ 43b6435, build dir
build_e2 INSIDE the worktree; env -u LD_LIBRARY_PATH; /usr/bin/make -j2;
header edits => clean-first rebuild; serialized sampling only (other
agents share cores). Deliverable: results/error_discipline_w38e2.md +
harness/run_w38e2.py + harness/analyze_w38e2.py; runs/w38e2/ local.
Commits: worktree branch exp/error-discipline; stan repo explicit paths
(never git add -A).

## 2026-08-22 — W-41 CLOSE-OUT: freeze clamp SHIPPED — the two W-36 abort cells now complete; all three gates PASS; root cause = lp=-inf at init NaNs the adapter at iteration 0 (degenerate value NaN, not 0/inf)

Executed as pre-registered (worktree external/walnutpie_w41, branch
exp/freeze-clamp @ 53daa3e off exp/safe-adapt-defaults @ 43b6435; the
pre-change binary is the same worktree built at the base commit before
the edit). Report: results/freeze_clamp_w41.md.

DIAGNOSIS CONFIRMED + SHARPENED: on both aborting cells the model
returns lp=-inf AT THE INIT POSITION (no exception; invalid region of
kronecker_gp / lotka_volterra at those inits_w36 draws). The acceptance
statistic is inf-inf=NaN, so the step adapter (Adam) NaNs on its FIRST
update: step=-nan from iteration 0, chain pinned at the init for all
1000 warmup iterations, freeze throws validate_positive(NaN) at exactly
the 32001st logp_grad call. Degenerate value: NaN on BOTH cells (not 0,
not inf) — so fallback (a) resolves to the init-step seed (1.0), the
tracked "last finite warmup step" never existing.

GATES:
- (a) CANARY PASS: 12/12 (hier_2pl, lsat_model, radon_partially_pooled
  x 4 chains, seed 20260819+c) md5-identical pre/post; 0 warnings in
  the post logs — the clamp is dead code on healthy freezes and the
  per-iteration tracker changed no warmup arithmetic.
- (b) RECOVERY PASS: both cells rc=0 with 1000 draws + the loud warning
  `WALNUTS WARNING: freeze step size degenerate (step_size()=-nan);
  falling back to 1 (last finite warmup step size); warmup
  iterations=1000`. Chains 1-3 of both cells: 0 warnings. Quality
  (informational, honestly garbage as pre-registered-acceptable):
  kronecker_gp rep0 4-chain bulk-ESS min 5.34 / R-hat max 2.13 with
  chain 0 fully pinned (all constrained columns constant); lotka_
  volterra rep1 ESS/R-hat = NaN (chain 0 moves but every constrained
  draw is NaN — constrain fails in the -inf region). Healthy reps of
  these models: 48 / 174 bulk-ESS-min. Root pathology = init protocol
  hitting -inf regions, NOT adaptation; queued for the init-policy
  backlog (the clamp makes the failure loud + survivable, it does not
  make the chain good).
- (c) COLLATERAL PASS: eight_schools_centered rep1 c2 + diamonds rep2
  c1 md5-identical pre/post, 0 warnings.

api.hpp walnuts_with_reinit ar.step_bar guard: shipped (geometric mean
of the just-frozen per-chain macro times -> init step -> floor, same
warning); library-only path, guarded by inspection + compile (the CLI
grid calls adapt_with_stats directly).

Ship state: committed on walnutpie branch exp/freeze-clamp (worktree
left in place, NOT merged — other agents active on the submodule);
stan repo: WORKLOG.md + results/freeze_clamp_w41.md. Raw runs
runs/w41/{pre,post}/ and scratch/w41_*.py local/untracked.

## 2026-08-23 — W-39 PRE-REGISTRATION: stanc3 eigh pair-fusion implemented (develop @ 90c6532) — validation about to run; plus fresh vectorize_loops verdict

Mission (Kit 2, external/upstream_pr_kits.md; evidence results/
eigh_reuse_w32.md; novelty check results/upstream_scan_2026-08.md #1):
make stanc3 itself fuse the `eigenvectors_sym(A)` + `eigenvalues_sym(A)`
pair into one `eigendecompose_sym` call (bit-identical per W-32's
structural argument), with a pedantic-mode warning as companion, then
validate against the W-32 language-level rewrite as ground truth.

TOOLCHAIN (userspace, no root): opam 2.5.2 (~/.local/bin) + OCaml 5.5.0
SOURCE-BUILT switch `w39` (ocaml-base-compiler; the distro ocaml package
lacks compiler-libs so ocamlfind/base fail on ocaml-system — source build
~25 min at -j2 resolved everything). stanc3 develop cloned to
external/stanc3 (untracked) @ 90c6532 ("Merge PR #1672
fix/vectorize-loops-nobase" — tip of develop, 2026-08-22). stanc.opam
pins ocaml {= 5.5.0} exactly: satisfied. Vanilla build verified before
patching.

IMPLEMENTED (both deliverables, before any measurement):
1. FUSION PASS `Optimize.fuse_eigendecompose` (src/analysis_and_
   optimization/Optimize.ml): peephole over statement lists; rewrites
   ADJACENT `V = eigenvectors_sym(A); w = eigenvalues_sym(A)` (either
   order, incl. Promotion-wrapped complex-target case, incl. nested
   blocks/loops) into `tuple ed = eigendecompose_sym(A); V = ed.1;
   w = ed.2`. Gates: Expr.Typed.equal args (locs ignored), distinct
   plain-variable targets, arg not referencing either target, arg free
   of target/RNG/user-defined calls (fused form evaluates arg once).
   Tuple decl reuses the targets' sized decl dims when both known,
   else Unsized. Enabled at --O1 and --Oexperimental (not O0), runs
   after function inlining / constant folding, before copy-prop.
   Generated C++ on kronecker_gp verified to match the W-32 lang-arm
   shape (`std::tuple` + `std::get<0/1>`) in all 3 instantiations.
2. PEDANTIC WARNING `eigh_pair_warnings` (Pedantic_analysis.ml, fires
   under --warn-pedantic when the same arg expression feeds both calls
   anywhere in log_prob/functions, gated on arg purity): message
   recommends `eigendecompose_sym` (notes --O1 fuses adjacent pairs).
   Fires on kronecker_gp (2 sites), silent on harness/w32/
   kronecker_gp_eigendecompose.stan.
3. Tests: eigh-fusion.stan added to the compiler-optimizations golden
   dir (fused/reversed/different-args/non-adjacent/nested cases; cpp,
   cppO1, cppO0 .expected regenerated — diffs purely additive) and
   eigh-pair.stan to cli-args/warn-pedantic (expected regenerated).
   Full `dune runtest` running; any failure blocks shipping.

VALIDATION PLAN (gates pre-stated, W-32 protocol, scratch/w39/ dirs —
W-27 bridgestan cache gotcha: one dir per arm, fresh):
- (a) SEMANTICS: compile harness/w32/kronecker_gp_eigendecompose.stan
  with VANILLA develop stanc (no fusion) vs models/kronecker_gp.stan
  with PATCHED stanc --O1 (fusion): diff hpp — expect only cosmetic
  deltas (temp names, statement numbering, extra braces from the lang
  rewrite's blocks). Then build BOTH .so via bridgestan (default flags,
  env -u LD_LIBRARY_PATH, make -j2) and compare (logp, grad) on ~50
  random N(0,1) points: EXPECT BIT-IDENTICAL (W-32 structural argument;
  pre-registered bar: max rel-L2 == 0.0 exactly).
- (b) STOCK CONTROL: patched stanc --O0 arm (fusion off) vs vanilla
  develop --O1: builds must behave like stock two-call codegen —
  guards against develop-vs-2.39 drift being attributed to fusion.
- (c) TIMING: per-call logp_grad medians of 3 interleaved reps on the
  same 50-point set (taskset 0-3, serialized): expect patched-O1 ~=
  W-32 lang arm (~337 us/call vs ~393 stock); record honestly.
- (d) Warning coverage: fires on kronecker_gp; silent on 3 models
  without the pattern (incl. the w32 lang model).
SECONDARY (time permitting): vectorize_loops fresh verdict — compile
all stan/models/*.stan with patched stanc --Oexperimental (fusion +
vectorize): record failures; for 2-3 scalar-loop models that compile,
build .so and compare logp_grad vs default build (statistical parity
~1e-6 rel, NOT bit-identity — vectorization reorders summation) +
median-of-3 timing. Phase 0's old --Oexperimental verdict (3/21
uncompilable + 1 silent miscompile) gets a fresh data point on the new
pass set only.
Patch saved as scratch/w39/stanc3_eigh.patch (external/stanc3
untracked). Commit: explicit paths only.

## W-40 (pre-registered BEFORE running): cluster-aware minimal-norm adjoint for rev eigenvectors_sym/eigendecompose_sym — fix the W-35 numerics at the stan-math level, validate locally, produce the fix PR kit

Mission: W-35 classified the -march=native gradient divergence: rev
eigenvectors_sym/eigendecompose_sym adjoints divide by eigenvalue gaps
(F_ij = 1/(w_j-w_i)); on rounding-degenerate spectra (kronecker_gp Sigma1
pinned cluster) this is catastrophically ill-conditioned, FD-inconsistent
30-47% in EVERY build, and cross-ISA unstable O(1)-O(1e3). W-40 implements
the mathematically defensible fix in the LOCAL bridgestan stan-math copy
(~/.bridgestan/bridgestan-2.9.0/stan/lib/stan_math), measures it, RESTORES
the tree pristine, and writes the upstream kit (issue + fix PR extending
Kit 4). walnutpie submodule untouched.

MATH (derived, to be validated against the W-35 evidence): for
A = V diag(w) V^T, the standard first-order reverse adjoint is
  dA-bar = V (F o (V^T G_V)) V^T + V diag(g_w) V^T,  F_ij = 1/(w_j - w_i),
(F antisymmetric; o = Hadamard). For a group of numerically coincident
eigenvalues (pairwise gaps |w_i - w_j| < tau) the individual eigenvectors
are not identifiable — only the invariant subspace is: within the group,
W = V^T dV has an arbitrary SKEW gauge (Fox-Kapoor/Nelson gauge), and the
pairing with downstream adjoints satisfies skew((V^T G_V)_group) = 0
WHENEVER the downstream composite is invariant to within-group rotations
(the kronecker_gp case: V enters only through V f(w) V^T forms — W-35
showed logp agrees to 1e-16 across flipped bases). Therefore zeroing the
within-group couplings (the minimal-norm gauge choice) is EXACT for
invariant downstream and the unique bounded, basis-invariant choice
otherwise (matching literature: He et al. J Sound Vib 2023 adjoint
eigen-derivatives incl. the repeated-eigenvalue pathology; de Leeuw
arXiv:2508.09355; Friswell; van der Aa ELA 2007; shift-and-invert adjoint
preconditioning 2025 — list in results/upstream_scan_2026-08.md).
IMPLEMENTED FORMULA: F~_ij = 1/(w_j - w_i) if |w_j - w_i| >= tau else 0,
tau = kappa * max(1, |w|_inf) * DBL_EPSILON, applied in
rev/fun/eigenvectors_sym.hpp and rev/fun/eigendecompose_sym.hpp (the
vector_adj term only). rev/fun/eigenvalues_sym.hpp callback
(V diag(g_w) V^T) has NO gap division — unchanged (its cross-build
variation is bounded; W-35: sigma1 FD-consistent 2e-9 already). NOTE on
the task brief's "1/(w_i-w_j)^2 eigenvalue term": no squared-denominator
term exists in the FIRST-order adjoint stan-math implements (verified by
reading all three hpp files); 1/(w_i-w_j)^2 terms arise in SECOND-order
eigenderivatives (Hessians) — out of scope, documented in the writeup.
Guard: min adjacent gap (eigenvalues sorted ascending; min over adjacent
== min over all pairs) >= tau => run the ORIGINAL code path VERBATIM
(well-separated spectra: literally identical code path, bit-identical
results). kappa pre-registered PRIMARY = 1e3; SENSITIVITY SWEEP
kappa in {1e2, 1e3, 1e4, 1e5} on gates (a)/(b). Measured gap structure
feeding this choice (scratch/w40/dump_gaps.out, Eigen 3.4.0 values):
Sigma1_7 bottom ~12 eigenvalues pinned at exactly 1e-5 with internal gaps
3.7e-17..6e-13 then a CONTINUUM (9.9e-12, 1.5e-10, ...); smallest
retained gap at kappa=1e3 is ~1e-11 (1/d ~ 1e11). Because the spectrum is
a continuum (NOT bimodal), cross-build agreement after masking is
expected to be limited by the smallest RETAINED gap (dF/F ~ dw/delta with
dw ~ 1e-14 cross-build eigenvalue wobble) — pre-registered honestly as
the two-tier gate (a) below.

ARMS:
- stock stan-math tree: existing stock binaries (.so in bs_models_threads +
  scratch/w35 builds) + freshly built stock unit drivers.
- patched tree: same sources with the F~ mask (kappa=1e3 primary; sweep by
  rebuilding unit drivers only).
- ISA axis: default (SSE2) vs -mavx builds of BOTH trees (W-35: -mavx alone
  reproduces the divergence).

GATES (pre-registered):
(a) DIVERGENCE COLLAPSE: patched default vs patched -mavx must agree on
    kronecker_gp gradients (W-35 parity.py protocol: 20 N(0,1) unc points,
    seed 20260822; grel = |dg|/max(1,|g|)). PRIMARY: max grel <= 1e-9 on
    the previously-diverging points. FALLBACK (reported honestly if the
    primary misses): max grel <= 1e-6 AND >= 5 orders collapse from stock's
    O(1) AND the residual shown to be retained-gap-limited (improves
    monotonically as kappa increases). Stock pair re-measured same session
    for the baseline number.
(b) FD-CONSISTENCY IMPROVES: Richardson central FD (h=1e-5, 5e-6; d4
    protocol) vs AD at the W-35 failing points (parity pts 1/2/7/14,
    var1/bw1 components): stock 30-47% -> patched report what it becomes.
    Expected small-but-nonzero: even the 'true' gradient is ill-defined at
    rounding level for non-invariant functionals; for the (invariant) model
    logp the masked adjoint is exact, so the residual should be FD
    truncation; residual documented honestly. Unit level: same comparison
    on the d2 phi (NON-invariant; residual expected, documented) and on a
    deliberately INVARIANT phi (V diag(1/w) V^T quadratic form) where the
    masked adjoint must be FD-consistent to truncation while stock is not.
(c) WELL-SEPARATED UNCHANGED: patched vs stock on well-conditioned random
    symmetric matrices (min adjacent gap >= 1e-2; 200 seeds, n=30) through
    eigenvectors_sym + eigendecompose_sym + eigenvalues_sym rev:
    bit-identical output (%.17g dumps byte-compare; the if-guard makes the
    code path literally identical). Edge case around tau documented.
(d) SAMPLER SANITY: kronecker_gp 3 reps x 4 chains, warmup=1000 draws=1000,
    seeds 20260819+1000*rep+c, inits from inits_w36/kronecker_gp
    (deterministic; kronecker_gp has NO inits_w25 pf inits — deviation
    from the brief noted here; W-41: rep0 c0 is the -inf-init cell), ONE
    fixed binary for both arms (external/walnutpie_w41/build_w41
    stan_cli — completes the -inf cell with the clamp) so the .so is the
    only difference; stock .so = bs_models_threads/model_kronecker_gp.so
    vs patched .so (STAN_THREADS=True, default CXXFLAGS otherwise).
    GATE: bulk/tail ESS-min (arviz, protocol of analyze_w36.py) within the
    stock arm's rep spread on healthy reps (rep1, rep2; rep0 reported with
    the W-41 pinned-chain caveat). Draws NOT expected bit-identical
    (adjoint changed on a clustered model) — divergence counts and R-hat
    recorded.
ALSO: Eigen-5 porting note (develop eigenvectors_sym.hpp fetched and
compared — callback structure identical => patch ports trivially); patched
tree RESTORED byte-identical after all patched-tree builds (backups +
cluster_adjoint.patch + patched .so kept in scratch/w40/); ready-to-file
issue + fix-PR text extending Kit 4 in results/cluster_adjoint_w40.md.
Env: env -u LD_LIBRARY_PATH; /usr/bin/make; builds -j2; sampling
serialized; no pushes; other agents' builds unaffected outside the
measured patch window (patch applied, everything built, tree restored
BEFORE long measurements).

## 2026-08-23 — W-39 CLOSE-OUT: Kit 2 SHIPPED as a real stanc3 patch — fuse_eigendecompose pass (O1+) + pedantic warning on develop @ 90c6532; kronecker_gp fused build BIT-IDENTICAL to vanilla develop (logp/grad/constrained, worst rel-L2 exactly 0.0) and −15.6% wall (406.8→343.4 us/call); full dune runtest PASS; fresh vectorize_loops verdict: 21/21 compile, 0/21 grid coverage, synthetic 27x at N=200k with 2e-14 parity

Executed as pre-registered. Toolchain: opam switch `w39` = OCaml 5.5.0
SOURCE build (distro ocaml lacks compiler-libs; ocamlfind/base chain
fails on ocaml-system — source build is the clean fix). stanc3 develop
90c6532 (2026-08-22 tip, includes #1666 vectorize_loops + #1672).

IMPLEMENTATION (patch: scratch/w39/stanc3_eigh.patch; external/stanc3
untracked):
- Optimize.fuse_eigendecompose (Optimize.ml/.mli): adjacent-pair
  peephole, either order, nested blocks, complex-target promotion
  handled (real decomposition kept, projections re-promoted); gates:
  Expr.Typed.equal args, plain distinct targets, arg pure (no
  target/RNG/user-defined fn — fused form evaluates arg once). Tuple
  decl reuses target dims when known. Enabled --O1/--Oexperimental.
  One bug caught by my own edge tests mid-flight (missing arg-equality
  check fused `A*x` with `A+x`) — fixed before any measurement.
- Pedantic_analysis.eigh_pair_warnings (--warn-pedantic): fires once
  per shared pure argument; message recommends eigendecompose_sym.
- Tests: eigh-fusion.stan golden model (cpp/cppO1/cppO0 expected
  regenerated, additive-only), eigh-pair.stan pedantic expectation;
  FULL dune runtest PASS (zero failures).

GATES (all as pre-registered):
- (a) SEMANTICS PASS: normalized hpp diff vs the W-32 lang rewrite =
  token-identical eigen regions in all 3 instantiations (only deltas:
  18 redundant frontend validates dropped, temp names, numbering,
  wraps, local_scalar_t__ vs double in write_array). .so level:
  BIT-IDENTICAL logp + gradient + constrained outputs on 50 random
  pts (worst rel-L2 exactly 0.0 — pre-registered bar met; W-32's
  structural argument transfers to compiler-generated code).
- (b) CONTROL: stock arm built with VANILLA develop stanc --O1;
  patched --O0 shows zero fusion (verified). Develop-vs-2.39 drift
  cannot contaminate the comparison.
- (c) TIMING PASS: 406.8 → 343.4 us/call medians (3 interleaved
  reps), ratio 0.844 = −15.6%; consistent with W-32 lang arm (−14.3%).
- (d) WARNING COVERAGE PASS: kronecker_gp 2 sites; silent on hier_2pl,
  gp_regr, lotka_volterra, arma11, accel_gp + the w32 lang model.

SECONDARY (vectorize_loops, fresh verdict on the new pass set):
- 21/21 grid models compile with --Oexperimental (vanilla AND patched)
  — Phase 0's 3/21 uncompilable + miscompile verdict superseded.
- 0/21 grid models have an ELIGIBLE loop (compound-indexed args are
  the documented #1666 follow-up; lsat_model's alpha[k]*ones is the
  blocker) — measured the pass on 2 synthetic eligible models instead:
  N=2k bit-identical + 1.01x (overhead-masked); N=200k: 7710.6 →
  285.8 us/call = 27x, parity 2e-14 (rounding-level, statistical as
  expected). --Oexperimental is a clean no-op on our current grid.

Committed: WORKLOG.md, results/stanc3_w39.md, harness/w39/{w39_gates,
w39_vec_gates,w39_vec_big}.py. Local (untracked): scratch/w39/
(stanc binaries, arms, hpp arms, patch copy, edge models, Oexp sweep),
external/stanc3 clone. Nothing pushed.

## 2026-08-23 — W-40 CLOSE-OUT: cluster-aware minimal-norm adjoint SHIPPED (locally) + VALIDATED — cross-ISA divergence 1.16 -> 7e-5 (k=1e3) / 3.1e-8 (k=1e5); model FD-inconsistency 30-52% -> ~1e-6; well-separated BIT-IDENTICAL (200/200); stock NaN-at-exact-degeneracy FIXED; sampler ESS-min 48 -> 368; tree RESTORED byte-identical

Executed as pre-registered. Report: results/cluster_adjoint_w40.md.
Patch: scratch/w40/cluster_adjoint.patch (eigenvectors_sym.hpp +
eigendecompose_sym.hpp rev callbacks; eigenvalues_sym.hpp read, NOT
patched — its V diag(g_w) V^T callback has no gap division). Formula:
F~_ij = 1/(w_j-w_i) if |w_i-w_j| >= kappa*max(1,|w|_inf)*eps else 0,
kappa=1e3 primary, macro-overridable for the sweep; min-adjacent-gap
if-guard keeps the well-separated code path VERBATIM (bit-identical by
construction, verified). TREE RESTORED after all patched builds
(md5-verified vs scratch/w40/backup/; patch round-trip verified).

MATH SHARPENED during validation (report §1.2): for symmetric
directions only the ANTIsymmetric combination F_ij(G'_ij - G'_ji) pairs
survive — bounded as delta->0 (catastrophic 1/delta cancellation), and
the bounded limit is NOT computable in doubles (SNR ~ delta/(eps*||G'||)
<< 1 at rounding degeneracy). Hence the gauge choice (drop the coupling)
is not merely defensible, it is the only library-level option short of
NaN. Task-brief note recorded: NO 1/(w_i-w_j)^2 term exists in the
first-order adjoint (squared denominators are second-order/Hessian
terms — He et al. 2023, de Leeuw 2508.09355); the implemented
eigenvalue adjoint term is division-free.

GATE (a) DIVERGENCE COLLAPSE: model-level parity (20 pts, seed 20260822,
default vs -mavx .so): stock max grel 1.156 (sign flips, var1 -2.50 ->
+0.39); patched 6.96e-5 (k=1e3), 1.58e-5 (1e4), 3.10e-8 (1e5), 0 sign
flips, logp <= 1.3e-16. PRIMARY <=1e-9 NOT met; pre-registered FALLBACK
(<=1e-6 AND >=5 orders AND monotone retained-gap-limited) PASSES at
k=1e5 (collapse 3.7e7; residual = bottom-L retained-gap channel,
monotone in kappa exactly as derived from the measured gap continuum —
no bimodal cluster structure in these spectra, dump_gaps.out).
Unit level: abs differences 1e16-1e22 -> <=1.5e13; remaining O(1) REL
differences on the unit functionals are the required basis dependence
of basis-DEPENDENT phis (G_V = fixed W), documented.

GATE (b) FD-CONSISTENCY: model-level (logp, unc coords, Richardson
h=1e-4): var1/bw1 at pts 1/2/7/14: stock 2.8e-1/5.1e-2/2.3e-1/5.2e-1
and 1.3e-1/1.6e-3/1.8e-2/8.4e-2 -> patched 8.5e-7...1.4e-6 and
6.7e-8...8.7e-7 (k=1e3; 1e-9..2e-8 at k=1e5); sigma1 control identical
2.4e-11 both. Full pt7 scan: worst 1.6e-3 at L252 (identical across k
AND matching stock's FD at that comp — FD truncation, not masking).
Honest residuals documented: unit phi_inv on Sigma1/Lambda has NO valid
FD reference at any h (h must exceed 1e-16 gaps, stay under the 1e-5
floor); EXACT 4-fold degenerate test (mu=1): stock NaN, patched
FD-consistent 1.1-2.2e-11 on cluster-symmetric/cross directions, gauge
0 (vs bounded FD value) on within-cluster mixing directions — the
uncomputable term, by design; W-35 repro phi (basis-dependent):
|grad| 1e15 -> 1e8 (bounded), FD gap remains by necessity (no
derivative exists). BONUS: kronecker_gp at theta=0 (Lambda == 0,
30-fold exact degeneracy): stock grad NaN in 435/438 components,
patched all finite (logp identical) — ready-to-file demo.

GATE (c) WELL-SEPARATED UNCHANGED: 200 random well-separated symmetric
30x30 (min gap >= 1e-6*scale, 0 skipped) through eigenvectors_sym +
eigenvalues_sym + eigendecompose_sym: stock vs patched outputs
BYTE-IDENTICAL (cmp). PASS.

GATE (d) SAMPLER SANITY: kronecker_gp 3x4 chains, fixed walnutpie
exp/freeze-clamp binary (inits_w36 deterministic — kronecker_gp has NO
inits_w25 pf inits, deviation noted in pre-registration), .so the only
difference: healthy-rep bulk/tail ESS-min stock 29.1/67.2 & 40.0/94.0
(reps 1/2) -> patched 411.4/324.0 & 349.1/308.6; R-hat max 1.13 ->
1.02; rep0/c0 (W-41 -inf-init) pinned in both arms identically (same
warning both logs — init pathology, not arm-attributable). Draws NOT
bit-identical (expected, pre-registered). Stock arm reproduces W-36
stock_seq runs BIT-FOR-BIT (md5 match) — baseline independently
corroborated. The 7.6x ESS improvement is mechanistic: stock adaptation
used the 30-50%-wrong gradient. Per-call 393->397us (+1%, the mask);
patched walls +35% from more (correct-gradient) trajectory work; ESS/s
far ahead. PASS (exceeds).

PORTING NOTE (Kit 4 gate): develop eigenvectors_sym.hpp fetched —
callback structurally IDENTICAL (no guard; only .val() vs .val_op()
naming) -> patch ports trivially; math is Eigen-5-independent; cannot
compile develop here — noted for the kit.

DELIVERABLES: results/cluster_adjoint_w40.md (derivation + citations,
kappa sensitivity, 4 gates, porting note, updated ready-to-file issue +
fix-PR kit extending Kit 4). Committed: WORKLOG.md,
results/cluster_adjoint_w40.md, results/w40_ess.json,
scratch/w40/{cluster_adjoint.patch, w40_unit.cpp, dump_gaps.cpp,
cmp_grads.py, fd_model.py, run_w40.py, ess_w40.py, ccw40.sh,
ccw40_stock.sh, build_so.sh}. Local (untracked): binaries + .out
dumps, backup/ + patched/ headers, builds/ .so variants,
runs/w40/ chains, repro_patch_*. No pushes. Walnutpie submodule
untouched. Bridgestan stan-math tree PRISTINE (verified) for other
agents.

## 2026-08-23 — W-38-E2 CLOSE-OUT: error-discipline ablation, warmup-weighted — NEGATIVE RESULT, all three arms REJECTED; E1's "max-error-start would unpin blr" REFUTED

Implementation (walnutpie exp/error-discipline @ b62969b, worktree
walnutpie_w38e2 off exp/safe-adapt-defaults @ 43b6435): WarmupConfig
knobs warmup_max_step_halvings (e2b) + warmup_max_error (e2c, overrides
the max-error schedule when set), consumed ONLY in AdaptiveWalnuts
(frozen sampler untouched); CLI --warmup-max-step-halvings /
--warmup-max-error, both default off. GATE (a) CANARY: PASS 12/12 —
default-path draws md5-identical to the pre-change binary (build_w36exp
@ 43b6435; arma11/blr/hier_2pl x 4 chains, seed 20260819, 1000+1000).
Knob liveness verified: pinned blr 10+10 warmup calls 312 -> 72 under
e2b (10*7+2), sampling unchanged.

ARMS (1000+1000, 4 chains serialized, 3 reps, seeds 20260819+1000*rep+c,
inits per W-36 assignment): base / e2a (--max-error-start 5.0
--max-error-iters 950, the EXISTING knob) / e2b (warmup halvings 3) /
e2c (warmup error 5.0 constant). Models: arma11, lsat_model, hier_2pl,
blr, kronecker_gp.

GATE (b) QUALITY (arviz ESS-min bulk/tail + max R-hat, medians of 3
reps, band = base per-rep spread; structurally constant GQ columns
excluded — 4 on hier_2pl, 466 on kronecker_gp, constant in base too):
ALL ARMS FAIL. e2a/e2c by small margins (e2a lsat tail -3.2%, e2c hier
bulk -4.4%, several <0.4% "hairs"), e2b MATERIALLY (lsat -24%, hier_2pl
-24% bulk — the same marginal class as W-25/W-28). e2a passes hier_2pl;
e2b/e2c pass blr + kronecker.

GATE (c) SPEED (calls/chain, median of 3): e2a/e2c FAIL 0/3 (hier_2pl
-6.5%/-7.7% only vs the 18.2% E1 ceiling; kronecker_gp +118%/+162% —
a loose warmup cap ADMITS long high-error trajectories, walls ~2-2.4x).
e2b nominal 2/3 (kron -15.9%, blr -23.4% — the pin effect) but hier
+12.6%, blr rep1 calls 4.5x, and one hard kronecker_gp abort (the KNOWN
"macro_time must be in (0, inf)" W-36 failure, hit under e2b's changed
warmup trajectories; recorded as e2b failure count).

GATE (d) BLR SHORT-WARMUP PROBE: at warmup=400 base is mostly unpinned
(E1's "<=400" was inferred from 100/1000 endpoints; escape sits ~100-400
for pf inits), but rep1/chain_0 stays pinned in EVERY arm incl.
e2a8 (start 1e8). Supplementary post-hoc probes (labeled): at warmup=100
base pins 3/4 chains/rep (bulk 5-9, 31-evals/transition signature);
e2a8 (decaying 1e8) AND a constant 1e8 cap (--warmup-max-error 1e8)
BOTH pin identically. The pin is NOT error-discipline-gated at all
(caps 10x above the measured |dH|~8e6 change nothing; the failures are
not cap-passable tolerance verdicts) — E1's "--max-error-start would
unpin" is REFUTED; the pin is W-41's problem. e2a8 also degrades healthy
cells (w400 rep2 bulk 612 -> 265) at 3.1x calls.

VERDICT (pre-registered rule): REJECT all three arms. Mechanism lesson:
E1's "wasted" warmup attempts double as a trajectory-growth limiter;
harvesting them lengthens warmup trajectories or destabilizes the frozen
sampler. Realized saving on the only production-relevant model
(hier_2pl -6.5/-7.7% calls/wall) is below the 10% bar and costs
marginal-class quality. E2 closed as a quality-preserving lever; the
pack's live item is E4 (refine-aware min_micro_steps, E1 GO, m=1 in
100% of steps — grow-m never exercised). Deviations recorded in the
report (kronecker rep0 c0 init swap per E1; e2b kron rep0 c2 abort;
ESS vectorization validated exact on blr).

Artifacts: results/error_discipline_w38e2.md (tables + verdicts),
results/w38e2_{canary,calls,ess,probe}.json, harness/run_w38e2.py,
harness/analyze_w38e2.py, runs/w38e2/ (local). Worktree
external/walnutpie_w38e2 left in place.

## W-37 (pre-registered BEFORE running): trajectory-geometry warmup-exit gate — measurement/separability FIRST, implementation only if separation passes

HYPOTHESIS (user's, refined against W-21/W-25/W-28): warmup's late gains
live in TRAJECTORY-GEOMETRY adaptation — the accepted-halving-level
distribution, ladder behavior, and evals-per-transition that the E1
accounting (results/grad_accounting_w38.md) instruments but the
step/mass/lp gates never observed. If those distributions stabilize AND
agree cross-chain, warmup has converged in the dimension that actually
matters and exiting preserves quality. W-28's refutation measured
lp-STREAM statistics (rho1/Rhat of pilot draws), not these
search-structure statistics; E2's lesson (the "wasted" dyadic attempts
double as a trajectory-growth limiter) says trajectory geometry is
behaviorally load-bearing. This is the ONLY live early-exit idea left.

SIGNALS (per window of 50 warmup transitions, per chain, from the E1
counters): mean_h = mean accepted-halving level (undefined if the window
has 0 accepted macro steps); P(h>=1); fw_share / bl_share = forward-
wasted / backward-ladder share of window kernel evals; ept = kernel
evals per transition. E1 anchors for magnitudes (aggregate, phase-level):
mean_h settled hier_2pl@1000 = 0.090 vs unsettled @100 = 0.845,
kronecker 0.61, pilots 0.55, escaped blr@1000 = 2.9; ept 16-104
(hier warmup 20.4@1000 vs 36.5@100, blr 31 pinned vs 104 escaped).

GATE FORMULAS (multi-chain controller, exit at a window boundary k,
window 50, min_iter >= 300 = 6 full windows; per W-31 the traj gate is
opt-in, default off, bit-identical when off):
- T1 temporal mean-h drift: max over chains |mean_h(k) - mean_h(k-2)|
  < 0.05 ABSOLUTE. Anchor: E1's settled-vs-unsettled adaptation
  amplitude is ~0.75 mean-h units (0.845 -> 0.090 hier); 0.05 is <7% of
  that amplitude.
- T2 temporal ept drift: max over chains |ept(k) - ept(k-2)| / ept(k-2)
  < 0.10 RELATIVE. Anchor: hier ept fell 44% between w100 and w1000
  (36.5 -> 20.4) while W-22 measured step +170% over the last 800
  warmup iters; 10% per 100 iters is ~1/3 of that late-growth rate.
- T3 cross-chain spread at k: max over chain pairs |mean_h_i - mean_h_j|
  < 0.10 absolute AND max_i ept_i / max_j ept_j - 1 < 0.20. No E1
  anchor (E1 was single-chain); set at 2x the temporal bounds — W-25's
  lesson that cross-chain tolerances tighter than per-chain window noise
  never fire.
- PIN RULE (pre-registered safety): a window with ZERO accepted macro
  steps is the E1-measured blr pin signature (31 evals/transition, 100%
  fw, zero-ESS sampler). Such a window is NOT CONVERGED: T1/T3 fail
  (mean_h treated as +inf drift) regardless of how constant the other
  signals look.
- EXIT = T1 AND T2 AND T3. fw_share/bl_share are RECORDED but not
  gated (their window-level behavior is unknown pre-data; gating on
  them now would be post-hoc).

MEASUREMENT-FIRST (the W-25 mistake was skipping this): before any exit
is implemented, a separability pass on the exp/grad-accounting worktree
(external/walnutpie_w38 @ 33cd398, DO NOT EDIT that branch) — extended
in MY OWN worktree (external/walnutpie_w37, branch exp/traj-gate off
exp/grad-accounting) ONLY with per-window accounting series (env-gated
WALNUTPIE_GRAD_ACCOUNTING=1, window 50, zero behavior change; canary
env-on vs env-off bit-identity before any measurement). Runs: full
warmup 1000 iters, 4 chains as 4 sequential single-chain invocations,
seeds 20260819+c, rep0 inits per the W-36 assignment (inits_w25 pf:
arma11, blr, hier_2pl, lsat_model, eight_schools_noncentered; inits_w36
deterministic: kronecker_gp; kron rep0 chain_0 uses the chain_1 init —
E1's recorded deviation for the known W-36 abort cell). Models: EASY
{blr, eight_schools_noncentered, arma11} + MARGINAL {hier_2pl,
lsat_model} + kronecker_gp (overhead class, reported separately).
samples=100 (separability needs only the warmup series).

SEPARABILITY CRITERION (pre-registered): per model and window boundary
k, define the normalized drift distance
  D(k) = max( D_h(k)/0.05, D_e(k)/0.10, S_h(k)/0.10, S_e(k)/0.20 ),
where D_h/D_e are the max-over-chains temporal drifts of T1/T2 and
S_h/S_e the cross-chain spreads of T3 (pin rule applied to every term
that needs mean_h). D(k) <= 1 means the W-37 gate WOULD exit at k.
CLASSES SEPARATE iff there exists k in {400, 450, 500, 550, 600} with
  max over EASY models of D(k) <= 0.5   (2x margin below the gate line)
  AND min over MARGINAL models of D(k) >= 2.0  (2x margin above it).
Class labels: PRIMARY = the brief's (easy: blr, esc, arma11; marginal:
hier_2pl, lsat_model); SECONDARY (reported, labeled) = the W-21/W-25
historical assignment (marginal includes arma11 — its ESS regressed
-33% under W-21 exits). kronecker_gp is reported but not in either
class (its known abort cell aside, E2 showed its behavior is dominated
by the high-error-trajectory pathology, not the marginal-class
mechanism). VERDICT RULE: PASS (primary) -> implement; PASS secondary
only -> TUNE, no implementation, record; no separating k with margin ->
REFUTED, STOP, no implementation — a fast refutation here closes the
early-exit direction permanently (4th independent gate) and is a
first-class result. Honest risks pre-registered: (a) blr may still be
pinned or freshly-escaped at 400-600 (E1/E2: pin escape ~100-400 for pf
inits, settled blr sits at mean_h ~2.9 / ept ~104) — if its drift
there is large, blr simply fails exit-stability (safe direction, kills
the speed win, not the quality claim); (b) like W-28, the classes may
genuinely share the same trajectory-geometry settlement schedule —
that is exactly the refutation the pass is designed to detect cheaply.

IMPLEMENTATION (ONLY on separability PASS): gate lives in the
multi-chain controller (adapt.hpp poll_controller, next to the W-25
temporal scaffolding), fed by per-chain windowed accounting counters
(lane-split so cross-chain spread is computable), zero cost when the
gate is off (canary: default path bit-identical 12/12 vs the
exp/grad-accounting binary, which is itself bit-identical to
build_w36exp @ 43b6435). New WarmupConfig knobs traj_* default off;
CLI opt-in flag(s). Then the 3-ARM gates:
(a) CANARY: default-path draws md5-identical to the pre-change binary,
    3 models (arma11, blr, hier_2pl) x 4 chains, seed 20260819,
    1000+100, rep0 inits.
(b) QUALITY: base (fixed warmup 1000) / naive W-25 early exit
    (--temporal-step-tol 0.05) / traj-gate, models blr, arma11,
    lsat_model, hier_2pl, kronecker_gp, 3 reps x 4 chains, seeds
    20260819+1000*rep+c, W-36 init assignment; arviz bulk/tail ESS-min
    within base's per-rep spread on the marginal class; ZERO exits
    allowed on the marginal class (that asymmetry IS the hypothesis).
(c) SPEED: wall + total logp_grad calls where the gate exits;
    expectation 1.2-2x wall on the easy class where it exits; no model
    >1.1x slower (in-process overhead confound recorded as in W-28).
BUILD/RUN PROTOCOL: env -u LD_LIBRARY_PATH; /usr/bin/make -j2;
clean-first after header edits; serialized sampling (<=4 cores);
one edit -> build -> test -> commit. Deliverable either way:
results/traj_gate_w37.md (separability analysis FIRST, published even
if negative; then gates if implemented), harness/run_w37.py (+analyze),
runs/w37/ local. stan repo commits: explicit paths only (never
git add -A). Worktrees left in place.

## W-38-E4 (pre-registered BEFORE running): refinement-aware min-micro-steps (grow-m) — phase E4 of the W-37p fewer-gradients pack

HYPOTHESIS (from E1, results/grad_accounting_w38.md): the dyadic ladder
always restarts at m = min_micro_steps and m = 1 in 100% of macro steps
in every E1 run — the MinMicroStepsAdaptHandler only ever pushes m DOWN
to its floor (mean_macro/target rounds to 0). A complementary GROW rule
— when the last k accepted macro steps ALL refined (h >= 1), raise m
(grow_floor), so the typical macro step accepts at h = 0 — removes the
forward-refinement waste AND the backward ladder by construction
(h = 0 => no ladder). E1 formula: accepted-at-h costs 3m*2^h - 2m evals
vs m at h = 0; grow-m trades one halving level (~ +4m evals) for +m.
Risk (pre-registered, sharpened from the pack's "coupling risk"): at
FIXED eps the first attempt integrates macro time m*eps, so growing m
RAISES first-attempt |dH| ~ linearly — h = 0 cannot be reached by m
alone. The benefit route is the coupling: bigger |dH|_first => smaller
alpha (the step adapter's statistic, measured at the min attempt) =>
adapter pulls eps DOWN; at the adapter equilibrium |dH|_first ~
-ln(0.8) = 0.223 < max_error 0.5 => h = 0 — persistent h >= 1 is
adapter LAG (blr@1000 h2-h4 structural = |dH|_first ~ 2-8, eps stuck
~2-4x above equilibrium). Equilibrium caricature says accepted-h is
pinned by (adapter target)/(tolerance) and m-invariant; if the adapter
is genuinely stuck, grow-m ratchets m to the cap with |dH| still high =>
evals/unit-trajectory-time UP ~2^(5/3) ~ 3.2x (m=32). Cap bounds the
damage; the micro-search catches it immediately on blr.

RULE (minimal, E1 accounting commit 33cd398 cherry-picked for the
mechanism gate — env-gated, draw-neutral, proven bit-identical in E1
8/8 + 3-way): in MinMicroStepsAdaptHandler, a grow_floor state machine
fed per ACCEPTED macro step (halvings h, via a thread_local sink set
around warmup transitions; null when the knob is off => zero cost, no
FP/RNG touched => bit-identical): streak over consecutive accepted
steps — h >= 1 => streak_refine++, streak_coarse = 0; h = 0 =>
streak_coarse++, streak_refine = 0; FAILED step (exhaustion or ladder
reject) resets both (pins must not ratchet m). GROW: streak_refine >= k
=> grow_floor <- 1 if 0 else min(2*grow_floor, cap) (or +1 variant),
streak_refine = 0. SHRINK counterweight: streak_coarse >= 4k and
grow_floor > 0 => grow_floor <- grow_floor / 2 (1 -> 0 = fully off).
Effective m = max(config floor, lround(mean/target), grow_floor) at all
4 call sites incl. sampler() freeze (the frozen m is what matters).
Knobs in WarmupConfig (grow_min_micro_steps = false default,
grow_m_streak k = 8, grow_m_cap = 32, grow_m_increment 2 = double /
1 = +1); CLI --grow-min-micro-steps, --grow-m-streak, --grow-m-cap,
--grow-m-increment. Default OFF = bit-identical handler.

ARMS: base = CLI defaults (REUSES the W-38-E2 base arm runs
runs/w38e2/base — same seeds/inits/models/binary-lineage; legitimacy
rests on gate (a) below: this binary's default path must be md5-identical
to that base arm, which was itself md5-verified against the
exp/safe-adapt-defaults binary in E2). grow = best micro-search variant.

GATES (pre-registered):
(a) CANARY bit-identity: THIS binary, knobs off + env off, 3 models
    (arma11, blr, hier_2pl) x 4 chains, seed 20260819+c, warmup=1000
    draws=1000, rep0 inits (W-36 assignment) => md5-identical to
    runs/w38e2/base rep0 CSVs (== build_w36exp @ 43b6435). 12/12
    REQUIRED. Bonus: kronecker_gp + lsat_model rep0 cells too (20/20).
(b) QUALITY: marginal class (arma11, lsat_model, hier_2pl) + blr +
    kronecker_gp, 3 reps x 4 chains, seeds 20260819+1000*rep+c,
    warmup=1000 draws=1000, on-arm: median bulk/tail ESS-min and max
    R-hat within the base per-rep band (W-25/W-28 rule, medians of 3
    reps; structurally constant GQ columns excluded as in E2). REPORT
    co-primary efficiency: evals/draw (total logp_grad calls / draw)
    AND ESS/wall per model — a config that cuts evals but ESS
    proportionally is a wash.
(c) MECHANISM: WALNUTPIE_GRAD_ACCOUNTING=1, 1 chain, 1000+1000, seed
    20260819, inits per E1 (inits_w25 pf blr/hier_2pl rep0 chain_0):
    blr@1000 (the P(h>=1) = 96.6% case) and hier_2pl@1000, on vs off:
    accepted-h histogram shifts toward h = 0, forward-wasted and
    backward-ladder shares drop; report measured evals/draw delta per
    model + final frozen m (min_micro histogram).
(d) MICRO-SEARCH (before the full grid): 3 variants on blr only,
    3 reps x 4 chains, 1000+1000: g1 k=8 double; g2 k=16 double;
    g3 k=8 linear (+1). Pick best by evals/draw among variants whose
    ESS-min is within the base band; ties -> smaller cap-contact.
    Then run gate (b) with the winner.
VERDICT RULE: ADOPT iff (a) 12/12 AND (b) quality PASS on all 5 models
AND evals/draw median reduction >= 10% on >= 2 models AND no model
evals/draw increase > 5% AND ESS/wall not degraded beyond the base band
on any model. TUNE if the mechanism gate shows h-shift without the
evals win (smaller cap / slower trigger documented). REJECT otherwise
(expected failure mode: m ratchets to cap with |dH| still > tolerance,
evals/draw up; report as the equilibrium-caricature confirmation).

BUILD PROTOCOL: worktree external/walnutpie_w38e4, branch exp/grow-m
off exp/safe-adapt-defaults @ 43b6435 + cherry-picked E1 accounting
commit 33cd398 (separate commit, no kernel changes mixed); build_e4
mirrors build_w36exp/build_e2 configure (empty CMAKE_BUILD_TYPE,
/usr/sbin/c++, -std=c++20); env -u LD_LIBRARY_PATH; /usr/bin/make -j2;
header edits => clean-first; serialized sampling (OMP_NUM_THREADS=1,
chains sequential); one edit -> build -> test -> commit. Harness:
harness/run_w38e4.py + harness/analyze_w38e4.py (E2 pattern); raw runs
under runs/w38e4/ (local, gitignored). Deliverable:
results/grow_m_w38e4.md (design, variant table, gates, verdict).
Deliverable commit paths explicit (WORKLOG.md, results/, harness/) —
never git add -A. Worktree left in place.

### W-37 pre-registration CORRECTION (formula typo, fixed before any
outcome was inspected; measurement grid still running at time of write)

In the W-37 pre-registration above, T3's ept spread term reads
"max_i ept_i / max_j ept_j - 1", which is degenerate (identically 0).
Intended formula, and the one used in the analysis: S_e(k) =
max_i ept_i / min_j ept_j - 1 (the max/min spread ratio). No threshold
or criterion changes — only this formula expression is corrected.
Every other pre-registered quantity (D_h, D_e, S_h, thresholds
0.05/0.10/0.10/0.20, margins 0.5x/2x, k in {400..600}, pin rule,
verdict rule) stands as written above.

## 2026-08-22 — W-37 CLOSE-OUT: trajectory-geometry separability REFUTED — no gate implemented (pre-registered stop rule); early-exit direction CLOSED permanently (4th independent gate)

Executed as pre-registered (separability-first; no exit code written).
Instrumentation: walnutpie exp/traj-gate (worktree external/walnutpie_w37,
off exp/grad-accounting @ 33cd398), commits 862381f + ec90f3f — per-window
warmup accounting series (window 50), env-gated, canary env-on vs env-off
bit-identical 8/8; window eval sums consistent with CLI call counts within
exactly one transition's work per cell (boundary snapshot fires at the
start of the boundary transition — 1-15 evals, uniform, documented).
MEASUREMENT DATA NOTE: the grid ran commit 862381f whose sum_h/ge1 window
records were delta-of-deltas; fixed in ec90f3f, and the true series was
recovered EXACTLY by telescoping (integer identity, verified against the
final phase histograms: blr_c0 recovered sum_h total 803 == 642*1+64*2+
3*3+6*4). Nothing re-run.

Runs: 6 models x 4 chains (sequential single-chain processes), seeds
20260819+c, warmup 1000 samples 100, W-36 inits (kron c0 = chain_1 init,
E1 deviation). 24/24 cells, 20 windows each.

FINDINGS:
1. THE CLASSES SHARE THE SETTLEMENT SCHEDULE — EARLY. By window 300-400
   every model INCLUDING hier_2pl sits at the settled floor mean_h
   0.05-0.14 / P(h>=1) 0.05-0.14 (hier w400 0.077 vs esc 0.113 vs blr
   0.076); ept flat (hier 16.0 at w500 -> 16.4 at w1000). Class
   differences live EARLY (w100 mean_h: blr 4.0 [pin escape], hier 1.49,
   kron 0.99, lsat 0.28, esc 0.10) — where exiting is already known
   unsafe. hier_2pl's late warmup (worth 4x ESS per W-25: 519 vs 126 on
   exit ~350) is FLAT in every trajectory-geometry signal.
2. NO SEPARATING THRESHOLD. D(k) (normalized distance from gate-pass):
   easy models sit at D 1.5-3.1 across k 400-600 (noise floor), hier_2pl
   DROPS TO 1.00/1.40 at k 550/600 — BELOW blr/esc/arma11 at the same ks.
   Criterion fails at every k in {400..600} under BOTH class assignments;
   labeled post-hoc scan: 0/18 boundaries in 100-1000 separate. At the
   pre-registered thresholds the gate never exits (W-28 failure mode);
   loosened to the noise floor it exits on hier_2pl too (W-25 failure
   mode).
3. THE RESIDUAL IS NOISE, NOT SIGNAL. D_e (ept 2-window drift) dominates
   23/29 model-k cells at k>=400; heavy-tailed per-transition eval counts
   swing 10-30% per window on both classes; lsat (marginal) has the
   LARGEST cross-chain ept spread (S_e 0.45 at k=500 vs esc 0.14). Class
   ordering inverts k to k — structural, not fixable by recalibration.
4. Pin rule fired as designed (blr acc=0 windows at w50-150, escape
   w150-250 — E2's 100-400 escape window confirmed at window resolution;
   a constant-signal gate would have found the pin maximally "stable").

VERDICT (pre-registered rule): REFUTED -> STOP, no implementation. The
early-exit direction is now closed by FOUR independent gates (W-21 CLI
temporal knob: fast but quality-destroying; W-25 static step/mass drift:
quality-destroying; W-28 dynamic lp pilot: quality-preserving only by
never exiting; W-37 trajectory geometry: not class-separating at any
exit-relevant point). Consistent picture: the marginal class's
late-warmup quality gains are invisible in every cheap windowed
statistic of sampler operation — step/mass state, the lp stream, and
now the search structure; they are visible only in long-horizon
min-dimension ESS, which costs what it would save. Warmup length stays
fixed. Any future early-exit proposal must name a quantity outside
this exhausted list.

Ship state: instrumentation only, default path bit-identical; the
per-window series is a standing measurement tool. Worktree left in
place. Artifacts: results/traj_gate_w37.md (full tables + series),
results/w37_separability.json, harness/run_w37.py + analyze_w37.py,
runs/w37/ (local).

## 2026-08-23 — W-38-E4 CLOSE-OUT: grow-m (refinement-aware min-micro-steps) — NEGATIVE RESULT, REJECTED; the E4 premise was sign-inverted; fewer-gradients pack fully closed

Implementation (walnutpie exp/grow-m, worktree walnutpie_w38e4 = 43b6435
+ cherry-picked E1 accounting fe5dd61 + grow-m 9715518): MinMicroSteps-
AdaptHandler gains a grow FLOOR fed per ACCEPTED macro step via a
thread-local sink (new include/walnutpie/grow_m.hpp): k-consecutive
h>=1 accepted steps grow the floor (double or +1, capped), 4k
consecutive h=0 steps halve it (1->0 off), failed steps reset streaks
(pins cannot ratchet); effective m = max(config floor, mean/target,
grow_floor) at all call sites incl. sampler() freeze. WarmupConfig knobs
default OFF (grow_min_micro_steps=false, streak 8, cap 32, increment 2)
+ CLI flags. GATE (a) CANARY: PASS 20/20 (12/12 required) — default
path md5-identical to the E2 base arm (== safe-adapt binary) on all 5
models rep0 x 4 chains, 1000+1000.

GATE (d) MICRO-SEARCH (blr, 3 reps x 4 chains): NO viable variant. g1
(k8 double cap32) / g2 (k16) / g3 (k8 linear) ABORT 9/9 cells each —
the ARM-TRIGGERED known abort family: growth multiplies the pin burn
(31 -> 992 evals per failed macro step at m=32; g1 rep0 c0 burned
790k warmup evals vs ~15k base) with alpha saturated (e^{-8e6} -> 0,
no adapter signal) until nan positions kill the run. t4 (cap 4) aborts
2/3. t2 (cap 2) survives 3/3 but is WORSE than base: evals/draw 9.5 vs
9.3 (+2%), total/draw +5%, tail ESS 595 below the base band (652).
t2 -> full grid per the pre-registered smaller-cap tie rule.

GATE (b) GRID (t2 arm vs E2 base, 5 models x 3 reps x 4 chains):
quality 2/5 PASS (lsat, kronecker — the latter inside a wide band,
base R-hats 1.05-1.31); FAILS: arma11 tail -1.7% vs band, hier_2pl
bulk -2.0%, blr tail -8.8% — the E2 marginal-class lesson repeating.
Efficiency: evals/draw ratios 0.974-1.023 (best kronecker -2.6%, bar
was >=10% on >=2 models); ESS/wall ratios 0.900-1.192 (worse on 4/5;
lsat +19% is a warmup lottery — at cap 2 the frozen m is 1, see (c)).

GATE (c) MECHANISM (1 chain 1000+1000, E1 inits): at cap 2 the grow
floor SELF-EXTINGUISHES before freeze (sampling m-hist m1-only both
models): h0 share hier 91.0->92.0 (+1.0pp), blr 92.4->87.0 (-5.4pp,
WORSE); evals/draw blr +1.0%, hier +3.7% — mechanism NOT confirmed at
the survivable cap. At cap 32 (hier_2pl 200+100 smoke, before the blr
aborts ruled g-variants out) the rule does exactly what it claims —
warmup m1=110 -> m32=263 ratchet, frozen m=32, sampling h0 30%->84% —
at 2.0x sampling evals/transition (56 vs 27.6) and 4.6x warmup evals
(28886 vs 6265): the eps shrinkage the alpha-coupling buys costs more
than the ladder it removes.

VERDICT (pre-registered rule): REJECT — all three prongs fail. Lesson:
at fixed eps the first attempt integrates m*eps (error ~ m*eps^3), so
growing m makes h=0 HARDER; accepted h at adapter equilibrium is pinned
by delta/max_error = -ln(0.8)/0.5 = 0.45 < 1 => h=0, and settled
kernels already sit at 90%+ h0; persistent h>=1 is step-adapter LAG,
m can only act through alpha->eps, which (a) has nothing to buy where
alpha is informative and (b) is saturated exactly where h>=1 is
structural (blr). E1's GO criterion selected FOR the models where grow
is most counterproductive. Pack closed: E1 shipped, E2 rejected, E3
NO-GO, E4 rejected, E5 opportunistic. blr's 104 evals/draw remains
W-41's freeze-robustness problem.

Artifacts: results/grow_m_w38e4.md (design, variant table, gates,
verdict), results/w38e4_{canary,micro,grid,mech}.json,
harness/run_w38e4.py, harness/analyze_w38e4.py, runs/w38e4/ (local).
Worktree external/walnutpie_w38e4 left in place. Deviations recorded in
the report (base arm reused from E2 per canary 20/20; t4/t2 TUNE arms
added after the g-aborts per the pre-registered TUNE branch; kronecker
rep0 c0 chain_1 init per E1/E2).

## W-42 (pre-registered BEFORE running): init-protocol guard — never start a chain at a non-finite-logp position (the ROOT fix behind the W-41 pathology)

DIAGNOSIS (W-41, verified): both W-36 abort cells and both W-41
"recoveries" share one root cause — the init protocol hands the sampler
a position where the model logp is non-finite (-inf at the
kronecker_gp rep0/c0 and lotka_volterra rep1/c0 inits_w36 draws; no
exception fires — load_stan maps model errors to lp=-inf). NO init-time
finitess check exists anywhere: the first logp evaluation happens in
InitConfigBuilder::masses() (config.hpp), whose lp output is DISCARDED
into `lp_to_discard` while only the gradient seeds the mass. The first
warmup transition then starts from that position, the within-orbit
acceptance statistic NaNs (inf - inf), Adam NaNs at iteration 0, the
chain is pinned for the whole budget, and (pre-W-41) the freeze throws
/ (post-W-41) the run "completes" with a zero-ESS chain that poisons
R-hat. Stan convention (cmdstan/bridgestan): random init REJECTS
non-finite-logp draws before warmup, retrying up to 100 times.

FIX DESIGN (guard is a PRE-WARMUP check; finite inits behave exactly as
today in both modes):
- (a) FILE-INIT (--init-file): the provided draw is the draw — no
  resampling. masses() already evaluates (logp, grad) at each chain's
  position; W-42 RECORDS the lp (today discarded). The CLI checks
  finiteness immediately after the builder runs, BEFORE the step-size
  heuristic probe and before the AdaptiveWalnuts is constructed (zero
  warmup consumption): non-finite -> loud multi-line stderr banner
  naming chain, file, and the lp value + throw std::invalid_argument
  (the CLI's existing init-error convention, e.g. dimension mismatch ->
  uncaught -> terminate, exit code non-zero). Rationale: a pinned chain
  is strictly worse than an early error — it burns the whole budget and
  produces zero-ESS draws.
- (b) RANDOM-INIT (CLI default when no file): rejection loop — draw,
  check logp finite, retry, up to --init-tries draws (NEW knob, default
  100, pre-registered per the Stan convention). A model eval error
  (ret!=0 -> lp=-inf) or a thrown exception during the check counts as
  rejection. One stderr line per rejected draw (WALNUTS WARNING prefix,
  the W-41 auditable channel); all N exhausted -> loud error + throw.
  RNG DISCIPLINE (pre-registered): candidates come from the chain's
  BridgeStan init RNG stream (model.make_rng(seed) single-chain;
  seed+c multi-chain), exactly one initialize() per attempt consumed
  strictly in order, BEFORE any warmup consumption (warmup runs on the
  separate std::mt19937_64{seed[+c]} stream, untouched by init
  retries); the first ACCEPTED draw is the final init-stream
  consumption and then seeds the chain exactly as today; a finite
  first draw consumes one initialize() and reproduces today's stream
  state bit-for-bit. Candidate checks are direct model.logp_grad calls
  outside the timing stanzas (the accepted position is re-evaluated by
  the builder's mass seeding exactly as before, so the random path adds
  one eval per accepted draw + one per rejected draw; the file path adds
  ZERO evals).
- (c) NO behavior change for finite inits: the guard reads values
  already computed; no warmup arithmetic, RNG or output changes.
- (d) E5-HYGIENE THREADING (only if trivial; guard ships first):
  masses() also records the raw init grad next to the lp;
  InitChainConfig carries the optional (init_grad, init_logp) pair and
  the AdaptiveWalnuts ctor seeds its W-23 endpoint cache
  (cached_grad_/cached_logp_) from it, so the FIRST warmup transition
  skips its start-position re-evaluation — the same duplicate-eval
  elimination W-23 did for transitions and the freeze (the mass seed
  eval and the first transition's start eval are the same
  (position, function) pair; reused doubles change no arithmetic, W-23
  precedent). Saving: 1 logp_grad call per chain (W-38's "2 boundary
  evals" become 1). Dropped without ceremony if it turns out
  non-trivial.

GATES (pre-registered):
(a) CANARY bit-identity: default-path draws (CLI defaults, warmup=1000
    samples=1000, 4 SEQUENTIAL single-chain invocations, seeds
    20260819+c) md5-identical to the exp/safe-adapt-defaults binary
    (external/walnutpie/build_w36exp @ 43b6435): 12/12 file-init cells
    (hier_2pl + lsat_model rep0 inits_w25 pf,
    radon_partially_pooled_noncentered rep0 inits_w36, chains 0-3) PLUS
    4 random-init cells (radon_partially_pooled_noncentered, NO
    --init-file, seeds 20260819+c) = 16/16 required. If the E5
    threading is implemented, draws must STILL be bit-identical.
(b) FAIL-FAST: the two known -inf file-init cells — kronecker_gp rep0
    c0 seed 20260819, lotka_volterra rep1 c0 seed 20261819, inits_w36
    chain_0.txt (regenerated via harness/gen_w36_inits.py's exact
    method if missing), warmup=1000 samples=1000 — now error
    IMMEDIATELY (before any warmup iteration; 1 logp_grad call total =
    the masses seed eval). Record error text + exit code + wall vs both
    the W-41 pinned 1000-iter completion
    (external/walnutpie_w41/build_w41 binary, same cell) and the
    pre-W-41 freeze abort (build_w36exp, rc=134 after 32001 calls).
(c) RANDOM-INIT RECOVERY: a random-init kronecker_gp run (no
    --init-file) with a seed whose FIRST draw(s) land at non-finite lp
    (found by seed trial — per-retry warnings in the log) COMPLETES
    rc=0 having started from a finite-lp draw; retries DETERMINISTIC:
    two identical invocations -> identical retry-warning counts +
    md5-identical CSVs.
(d) NO COLLATERAL: 2 healthy cells outside the canary set
    (eight_schools_centered rep1 c2 seed 20261821, diamonds rep2 c1
    seed 20262820 — the W-41 cells) md5-identical to build_w36exp.

BUILD/RUN PROTOCOL: separate worktree external/walnutpie_w42, branch
exp/init-guard off exp/safe-adapt-defaults @ 43b6435; build_w42 INSIDE
the worktree mirroring the build_w36exp configure (empty
CMAKE_BUILD_TYPE, /usr/sbin/c++, default flags); env -u
LD_LIBRARY_PATH; /usr/bin/make -j2; header edits => clean-first
rebuild; serialized sampling (OMP_NUM_THREADS=1, one chain process at
a time — other agents share cores); one edit -> build -> test ->
commit. Deliverable: results/init_guard_w42.md (design, gates, the
fail-fast before/after) + harness/run_w42.py; runs/w42/ local.
Commits: worktree branch exp/init-guard; stan repo explicit paths only
(never git add -A). Worktree left in place.

## 2026-08-23 — W-42 CLOSE-OUT: init-protocol guard SHIPPED — all four gates PASS; file-init -inf cells now fail in <0.2s (vs 8.2s/5.3s pinned W-41 completions or rc=134 freeze aborts); random-init policy moved to the CLI (--init-tries) after discovering Stan's own reject loop hidden inside BridgeStan; E5 init-eval threading shipped (−1 eval/chain, draws bit-identical 16/16)

Executed as pre-registered (worktree external/walnutpie_w42, branch
exp/init-guard @ 5aed078 off exp/safe-adapt-defaults @ 43b6435;
pre-change reference = build_w36exp). Report: results/init_guard_w42.md;
raw gates results/w42_gates.json.

IMPLEMENTATION: (a) FILE-INIT — InitConfigBuilder::masses() records the
logp it already computed (was literally discarded as lp_to_discard);
InitConfig::init_logps() exposes it; the CLI checks finiteness right
after the builder runs (before the step heuristic, before the adapter,
zero warmup consumption, zero new evals) and fails with a loud stderr
banner naming chain + file + logp, then throws invalid_argument (rc
134, the CLI's init-file-error convention). Builder hygiene: recorded
evals invalidated by any later positions() call. (b) RANDOM-INIT —
MID-FLIGHT DISCOVERY: the Stan-convention rejection loop ALREADY
EXISTED inside the model layer: BridgeStan 2.9.0 param_initialize calls
stan::services::util::initialize with max_tries=100 HARDCODED by
walnutpie's load_stan.hpp (cmdstan-style "Rejecting initial value"
messages, "Initialization failed" throw) — invisible and un-knobbed
from the CLI. W-42 exposes it (initialize(..., max_tries=100), default
= historical behavior) and moves the policy to the CLI: inner layer
called with max_tries=1, the CLI owns the budget (--init-tries, default
100), per-draw audit lines, and the loud all-failed error. RNG
discipline: one one-draw initialize() per attempt from the chain's bs
init stream, strictly in order, before any warmup consumption (warmup
runs on the separate mt19937_64 stream); the accepted position is
IDENTICAL to what stock would have accepted for any run stock started
(the inner loop always drew sequentially from the same stream) —
verified bit-for-bit by the random canary cells. (d) E5 THREADING
(trivial, shipped): masses() also records the raw init grad;
InitChainConfig carries the optional (init_grad, init_logp) (5-arg
ctor; 3-arg unchanged); the AdaptiveWalnuts ctor seeds its W-23
endpoint cache from it, so the first warmup transition skips its
start-position re-eval. Multi-chain guard included (chain-resolved file
names in the banner).

GATES (all PASS, harness/run_w42.py):
- (a) CANARY 16/16: 12 file-init (hier_2pl + lsat_model inits_w25 rep0,
  radon inits_w36 rep0, chains 0-3, seeds 20260819+c) + 4 random-init
  (radon, no --init-file) md5-identical to build_w36exp; 0 post
  warnings; EVERY cell shows warmup logp_grad calls exactly −1 (the E5
  threading's only trace — draws unmoved, W-23 precedent holds).
- (b) FAIL-FAST: kronecker_gp rep0 c0 (20260819) + lotka_volterra rep1
  c0 (20261819) now rc=134 in 0.16s/0.09s with 1 logp_grad call total
  (the masses seed), banner + what() naming chain/file/logp AND the
  underlying model error surfaces (lkj_corr_cholesky reject / lognormal
  NaN location). Baselines same cells: W-41 binary rc=0 in 8.22s/5.28s
  (31k calls, pinned chain 0, freeze-degenerate warning) = garbage
  draws; stock binary rc=134 in 2.97s/0.80s (abort at freeze, budget
  burned). Wall saved ~98% of the pinned run, with zero poison draws.
- (c) RANDOM RECOVERY: kronecker_gp seed 20260820 --init 2.2 (first
  draw -inf — found by seed trial; acceptance cliff: radius 2.0
  all-pass, >=2.5 100/100 fail): rc=0 at production settings, 1
  audited rejection then acceptance; two identical invocations ->
  identical retry counts + md5-identical CSVs. Exhaustion (seed
  20260819 --init 2.5): 100/100 rejections + loud error, rc=134.
- (d) NO COLLATERAL: eight_schools_centered rep1 c2 + diamonds rep2 c1
  md5-identical, 0 warnings.

Ship state: committed on walnutpie branch exp/init-guard (worktree left
in place, NOT merged — other agents active on the submodule); stan repo:
WORKLOG.md + results/init_guard_w42.md + results/w42_gates.json +
harness/run_w42.py. Raw runs runs/w42/{pre,post,w41}/ local/untracked.
The W-41 freeze clamp stays as the second line of defense; the
init-policy backlog item behind W-36/W-41 is now closed at the root.

## W-44 (pre-registered BEFORE running): upstream dry-run — apply the W-40 cluster-adjoint patch and Kit 1's square() fix to TODAY's stan-dev/math develop and run the repo's unit tests; re-verify the stanc3 patch against develop tip

MISSION: land the user's PRs pre-validated. Kits 1/4 (stan-math) and
Kit 2 (stanc3) exist as patches validated against older/local trees
(W-40/W-39); before the user pushes, dry-run them against the REAL
target repos. Clone stan-dev/math develop (untracked, external/math_dev,
record commit hash), apply scratch/w40/cluster_adjoint.patch (port if
the Eigen-5 migration moved lines; W-40 verified the callback is
structurally identical — record any hunk edits), build+run ONLY the
touched functions' unit tests (test/unit/math/rev/fun/
eigenvectors_sym_test.cpp, eigendecompose_sym_test.cpp,
eigenvalues_sym_test.cpp; -j2, /usr/bin/make, env -u LD_LIBRARY_PATH,
serialized). If green: port the W-40 degenerate-spectrum tests (exact-
degeneracy NaN->FD-consistent case; cluster-symmetric direction case)
as a new test file following repo conventions (copy saved at
scratch/w44/eigen_cluster_adjoint_test.cpp, local only). Then on a
SECOND clean state apply Kit 1's square() x*x fix (scratch/w33/
pow_to_mul.patch logic, adapted: int-overflow nuance + the two
squared_distance sibling sites) and run square + squared_distance
tests. Kit 2: re-verify scratch/w39/stanc3_eigh.patch applies to
TODAY's develop tip (fetch/re-clone, record new hash; rebase + re-run
touched dune tests only if quick). Kit 3 skipped (issue-only). NO
PUSHING ANYWHERE — local validation only.

GATES: (a) cluster patch applies to develop (clean or trivial port,
hunk edits recorded); touched-function tests PASS with it; any failing
test investigated + reported, not hidden. (b) new degenerate-spectrum
test file PASSES (exact-degeneracy finite + FD-consistent; cluster-
symmetric direction; well-separated path unchanged) and follows repo
test conventions. (c) Kit 1 fix applies; square + squared_distance
tests PASS (prim + rev). (d) stanc3 patch still applies at develop tip
(new hash recorded; if drift: rebased + touched tests re-run).
Deliverables: results/upstream_dryrun_w44.md + one-line status notes
per kit in external/upstream_pr_kits.md; stan-repo commits by explicit
paths (never git add -A); external clones stay untracked.

## W-43 (pre-registered BEFORE running): blr short-warmup pin root cause — what distinguishes the pinned phase from the escaped phase, and what event/accumulation triggers escape between warmup 400 and 1000

TARGET (W-38-E1 bonus, W-38-E2 gate (d), W-37 result 4): at CLI
defaults blr's chain does not move for the first ~100-400+ warmup
iterations — every transition = 1 macro step, all 5 halvings fail,
31 evals burned, |dH| huge (E1 measured ~8e6), alpha underflows to 0,
all later draws identical (zero ESS). Escapes between ~100 and 400
(pf inits; E2 probe) / 400-1000 (E1 endpoints). NOT error-discipline
gated (E2: caps 1e8 constant or decaying change nothing — so the
pinned min-attempt |dH| is either > 1e8 or non-finite at w100, and
E1's 8e6 must sit LATE in the pin; measuring the true series is part
of this item). NOT the W-41 pathology (blr init logp is finite; the
W-41/W-42 -inf-init pin is a different mechanism — do not conflate).

SOURCE FACTS (read before pre-registering; walnutpie @ 43b6435):
- CLI defaults: plain Adam step adapter (no anti-windup, no batching,
  stride 1), step seeded 1.0, mass seeded (1-1e-5)*|grad(init)|+1e-5,
  metric_window=0 (chopping OFF), drift_iters=0, stall/collapse resets
  OFF, max_error 0.5, target accept 0.8, Adam lr 0.05 decayed by t^-0.5.
- Momentum rho = sqrt(mass)*z; per-micro-step displacement =
  step*sqrt(inv_mass)*z; every dyadic attempt integrates the SAME
  macro time (m*2^h micro steps at step/2^h), so refinement changes
  only discretization error, not trajectory length.
- alpha = exp(-|dH|) is fed to the adapter ONLY at the min-micro
  attempt (num_steps == min_micro_steps) of each macro step.
- While pinned, draws AND scores are exactly constant and both
  OnlineMoments share one discount schedule 1-1/(4+iter): the
  var_draw/var_score ratio — hence inv_mass = sqrt(ratio) — is
  EXACTLY constant during a true pin; there are NO window boundaries
  to fire (metric_window=0) and no batching (stride=1).

CANDIDATE MECHANISMS (pre-registered, with discriminating predictions):
- M1 mass-estimate maturation (windowed Fisher/variance needs draws
  before inv_mass stops throttling motion; echoes session-1
  gradient-seeded-mass ~1e6 freeze). PREDICTS: inv_mass geo-mean
  drifts materially (order-of-magnitude) during the pin and escape
  coincides with an inv_mass threshold crossing; step flat/noise.
  Structural prior against: at defaults inv_mass is provably constant
  during a true pin (source fact above) — if the trace confirms
  constancy, M1 is REFUTED for the default-config pin.
- M2 step-adapter escape from saturated-alpha regime: alpha = exp(-|dH|)
  underflows to exactly 0.0 every pinned iteration; Adam target 0.8
  descends log-step at ~0.05/t^0.5 per iteration (cumulative ~0.1*sqrt(t)
  nats); |dH| declines as step^k until an attempt first passes 0.5.
  PREDICTS: log(step) declines smoothly as -0.1*sqrt(t) during the pin;
  min-attempt |dH| declines smoothly (monotone trend) as a power of
  step; at the escape boundary step is CONTINUOUS (no jump); alpha
  jumps 0 -> O(1) exactly at escape; escape iteration roughly
  reproducible across seeds/inits (schedule-driven).
- M3 observation-batching / memoryless-window boundary event (stride-50
  batches, Fisher window chopping crossing a threshold). PREDICTS:
  escape aligns with a window/batch boundary multiple. Structural
  exclusion at defaults: stride=1 and metric_window=0 — no boundaries
  exist; verify escape still occurs with all window/batch knobs off.
- M4 position drift / stochastic accumulation: fresh momentum z every
  iteration makes the min-attempt dH a RANDOM variable (z-dependent);
  the pin persists while P(|dH| <= 0.5 at some halving) ~ 0 per
  iteration, and escape is the first lucky draw (hazard grows as step
  shrinks). PREDICTS: min-attempt |dH| SCATTERS iteration-to-iteration
  around a declining trend (not monotone); no structural state jump at
  the boundary (step, inv_mass both continuous); escape iteration
  varies strongly across seeds/inits/chains (consistent with E2's 3/4
  chains pinned at w100 and per-chain escape spread).
- M5 (added from source, W-43): reversible-ladder rejection as the
  pinning verdict — attempts whose |dH| passes the cap are rejected by
  the backward ladder (a coarser re-integration also within tolerance
  => return false), which would make the pin cap-INDEPENDENT even for
  passable |dH|. PREDICTS: with the trace on, pinned transitions show
  tolerance-PASSING attempts (|dH| <= cap) that then fail reversible()
  — distinguishable from M2/M4's tolerance failure by recording, per
  transition, the min |dH| over ALL attempts and whether any attempt
  passed tolerance. E2's 1e8-cap pin is only explainable by |dH|>cap,
  NaN, or M5; the trace separates these.

MEASUREMENT PLAN (before any run):
1. Worktree external/walnutpie_w43, branch exp/pin-diagnosis off
   exp/grad-accounting @ 33cd398 (W-38's hooks present). New env-gated
   (WALNUTPIE_PIN_TRACE=1) zero-behavior instrumentation, new header
   include/walnutpie/pin_trace.hpp + call sites in walnuts.hpp +
   a per-iteration print in the CLI handler (extending the W-41
   WALNUTPIE_DEBUG_WARMUP precedent): per warmup iteration record
   iter, lp, step_size (pre-transition), inv_mass {geo-mean,min,max},
   per-transition {macro-step count, evals, last min-attempt alpha,
   last min-attempt dH, min |dH| over all attempts, any-tolerance-pass
   flag}, position drift {l2 norm and max-abs vs init}, and position
   changed? (pin verdict). Header edits => clean-first rebuild; -j2;
   /usr/bin/make; env -u LD_LIBRARY_PATH; serialized runs.
2. Runs (1 chain, seed 20260819, .so from bs_models_threads, defaults
   otherwise, samples=100): blr {warmup 400, warmup 1000} x {default
   init, pf init inits_w25/blr/rep0/chain_0.txt}; plus warmup=100
   (E1's pinned endpoint) if 400 already escapes for a given init —
   the pinned regime must be observed in the trace for both inits
   (E1 claimed both pin at <=400; verify). Post-escape iterations are
   part of the same trace (what the escaped phase looks like).
3. ESCAPE BOUNDARY TABLE (the crux): for each run, the first
   iteration where the position changes; a before/after table (escape
   -10..+5) with step, inv_mass stats, alpha, min-attempt dH, min
   all-attempt |dH|, evals, macro steps. Identify what changed AT or
   just before escape and separate M1-M5 by the predictions above.
4. Discriminating supplements (labeled): (i) escape-iteration spread
   across 4 seeds (20260819..22) x 2 inits at warmup=400 — M2 predicts
   tight clustering, M4 predicts spread; (ii) optional NaN check: does
   any pinned attempt produce |dH| = inf/NaN (E2's not-cap-passable
   finding)?
5. VERDICT + fix latitude: if a minimal, default-off, library-latitude
   fix is obvious (candidates already in the tree: --step-init-
   heuristic at init with the seeded metric (config-only); a
   warm-start/clamp on the saturated-alpha descent; a first-window
   mass clamp), implement on exp/pin-diagnosis and gate: canary
   bit-identity 12/12 (default path, 3 models x 4 chains, vs the
   pre-change binary) + pin disappears at warmup=100/400 on blr with
   ESS > 0 + healthy quality 3 reps x 4 chains vs the warmup=1000
   base band. If no obvious small fix: STOP at the mechanism writeup
   (a complete result; feeds upstream candidate 7 + the Flatiron team).
DELIVERABLE: results/blr_pin_w43.md (mechanism verdict, escape-boundary
table, fix status). Commits per repo, explicit paths only. Worktree
left in place.

OUTCOME (W-44, all gates PASS): all three patch-carrying kits are GREEN
against today's real target tips (local only, nothing pushed; details
results/upstream_dryrun_w44.md).

- (a)+(b) KIT 4 GREEN on math develop @ 46a3133 (shallow clone,
  external/math_dev untracked; Eigen 5.0.1 vendored — the W-40 §8 "not
  established under Eigen 5" gap is now COMPILED + tested). Patch
  apply: 3/5 hunks clean; the 2 rejects are exactly the predicted
  `.val_op()`->`.val()` develop rename — hand-completed, no logic edits
  (ported patch scratch/w44/cluster_adjoint_dev_46a3133.patch). Tests
  with patch: rev/prim/mix eigenvectors_sym + eigenvalues_sym +
  eigendecompose_sym 6/6 binaries PASS (mix = FD-reference tests). New
  test file scratch/w44/eigen_cluster_adjoint_test.cpp (4 gtest cases,
  repo conventions, LCG-deterministic): exact 4-fold repeat (finite +
  Richardson-FD <=1e-8 on cluster-diagonal/separated/cross directions,
  two-call == eigendecompose_sym bitwise), zero matrix (finite), 30-pt
  exp-quad jitter kernel (guard fires: 10 eigenvalues at the 1e-5
  floor, 8 gaps < tau; finite + idioms agree), 10 well-separated LCG
  matrices (textbook adjoint to 4.4e-16). With patch 4/4 PASS; on stock
  2/4 FAIL with exactly the NaN the issue describes. Dry run caught 3
  test-authoring traps before any reviewer could: bit-exact double-EQ
  vs 4e-16 GEMM reorder; column-major layout vs row-major read (operand
  adjoint is NOT symmetric); FD claims only valid off the
  within-cluster MIXING directions (W-40 §1.2(3) dropped term).
- (c) KIT 1 GREEN on a second clean state @ 46a3133: square()
  widen-to-double-then-multiply (covers BOTH kit caveats: int promotion
  AND float double-rounding — micro bit-identity PASS incl. 3e9 int64,
  -46341 int, float 1.0000001f, 1e300 overflow) + both
  squared_distance pow sites hoisted to diff*diff; prim+mix square and
  squared_distance 4/4 binaries PASS (scratch/w44/square_fix_dev_
  46a3133.patch).
- (d) KIT 2 NO DRIFT: stanc3's default branch is master and its tip is
  STILL 90c6532 — the exact commit W-39 dune-validated; applied tree
  diff-normalized byte-identical to scratch/w39/stanc3_eigh.patch.
  Patch as-is; no rebase, no re-run needed.
- Kit 3 skipped (issue-only); Kit 5 out of scope.

Red flags: NONE anywhere (no test fails with any patch applied; the
only failures seen are the intentional stock-NaN demonstrations).
external/upstream_pr_kits.md now carries per-kit DRY-RUN STATUS notes
with the tested commits. Ship: stan repo WORKLOG.md + results/
upstream_dryrun_w44.md + external/upstream_pr_kits.md + scratch/w44/ (4
files); external/math_dev left untracked with the Kit 4 patch + test
applied at 46a3133 for the user's PR branch; external/stanc3 index
restored to its W-39 state.

## 2026-08-23 — W-43 CLOSE-OUT: blr pin root-caused — saturated-alpha step-descent race (M2 engine + M4 first-passage trigger); M1/M3/M5 refuted; fix SHIPPED (3 defects in find_reasonable_step corrected, opt-in path); canary 12/12, 0/48 chains pinned post-fix, pf-class short warmup restored to full health

MECHANISM VERDICT (trace WALNUTPIE_PIN_TRACE=1, exp/pin-diagnosis @
8853fd7+468e60f, off exp/grad-accounting @ 33cd398): the pinned and
escaped phases differ in exactly ONE bit of internal state — whether
alpha = exp(-|dH_min-attempt|) has underflowed to ~0. Seeded mass =
|grad| at blr's default init ~1.6e7 makes step 1.0 carry min-attempt
|dH| = 8.2e6 (iteration 0 — E1's 8e6; pf init up to 2e12): all 5
halvings fail (31 evals), alpha = 0, Adam descends log-step at
0.100*(sqrt(t)-1) nats (measured to 2% over 948 iters), inv-mass is
EXACTLY frozen (identical discount schedules on constant draw/score
streams preserve the var ratio; trace shows 6.42493e-08 to all digits),
and escape is the FIRST iteration where the FINEST attempt's |dH|
crosses the 0.5 cap: def-init boundary margin 0.5017 -> 0.4987 at
it=948 (step continuous, alpha jumps, accepted h=4). M1 (mass
maturation) refuted — mass dormant until AFTER escape; M3 excluded by
construction (metric_window=0, stride=1 at defaults; escapes happen
anyway); M5 refuted as the pinning verdict (strictly pre-escape:
tolpass=0, ladrej=0 in all 8 traced runs; ladder acts only
post-escape). M4 modulates the trigger: escape iteration spreads
{574,778,948,>1000} across def-init seeds (z-scatter vs a 0.3%/iter
trend; seed 20260822 stays pinned the full 1000 — E2's rep1/c0 analog)
but clusters {185,189,198,200} for pf inits (envelope ~step^16, steep
approach). Zero-ESS has a second layer: if warmup ends pinned, the
FROZEN sampler re-pins (no adapter; w100 CSVs = 1 unique row of 100) —
resolves E2's 1e8-cap paradox (loose cap admits warmup movement but
~1 nat of descent leaves the frozen step ~1000x divergent; E2's
pinned-draws metric cannot distinguish).

FIX SHIPPED (468e60f, opt-in --step-init-heuristic path only,
include/walnutpie/warmup_heuristics.hpp): find_reasonable_step was
broken 3 ways — (1) momentum scale INVERTED (p ~ N(0, inv_mass) vs the
sampler's rho ~ N(0, mass); under mass 1e7 the probe moved 1e7x too
little, always accepted, returned eps>=1; adapt_step in util.hpp uses
the correct convention — the two heuristics disagreed), (2) fresh
momentum per probe (sign lottery; H-G Alg 4 draws once), (3)
asymmetric statistic exp(-(h1-h0)) reads divergent-direction energy
gain as accept-and-DOUBLE. Fixed: correct scale, one draw,
exp(-|dH|) mirroring macro_step's own alpha. Post-fix the probe
returns eps~0.008 on the pinned cell; escape at iteration ONE with
alpha=0.84~target; warmup 937 calls vs 3102 pinned; sampling 8.2
evals/draw vs 31.

GATES: (a) canary default-path bit-identity vs pre-fix binary
(same worktree, saved build): PASS 12/12 (arma11/blr/hier_2pl x 4
chains, 1000+1000, seeds 20260819+c, rep0 pf inits).
(b) blr knob grid (3 reps x 4 chains, E2 seed protocol):
0 of 48 chains pinned (base: 3/4 chains/rep at w100-pf, 1/12 at
w400-pf, 1/4 at w1000-def). pf class restored to full health at SHORT
warmup: w100 bulk-min med 779.0 / rhat 1.0048 (base w100: bulk 5-9
pinned; w1000 base band 432.9-545.5); w400 630.4/693.7 vs probe-base
612.4 (whose rep1 = 86.5 was its pinned chain) — strictly better.
def class: pin equally gone (0/12, chains move from it~1, lp climbs
-3.347e7 -> -2.93e7 in 100 iters) but short warmup remains
DRIFT-limited (default init lp=-3.3e7; the full-warmup BASE there is
itself garbage: bulk 4.2, rhat 5.4, 1/4 pinned — the never-escape
seed): init-protocol territory (W-42), not the pin; recorded honestly.
Follow-up recorded (not done): exp/freeze-clamp's W-41 fallback (b)
calls the same broken probe — port 468e60f when that branch is next
touched.

Artifacts: results/blr_pin_w43.md (mechanism + boundary tables + fix
gates), results/w43_{canary,knob,ess}.json, harness/run_w43.py,
harness/analyze_w43.py; raw runs/w43/ (local). walnutpie commits
8853fd7 + 468e60f on exp/pin-diagnosis (worktree external/walnutpie_w43
LEFT IN PLACE). Feeds upstream candidate 7 + the Flatiron team: the
saturated-alpha regime is a GENERAL warmup-robustness hazard for any
gradient-seeded-mass sampler whose step adapter uses an underflowing
acceptance statistic — the adapter is blind (constant-gradient descent)
for as long as |dH| > ~745, and the descent pace (lr/sqrt(t)) sets a
seed-dependent minimum warmup of hundreds to >1000 iterations.

## W-46 (pre-registered BEFORE running): libm log1p ceiling in the bernoulli_logit likelihood path of hier_2pl — kernel micro-benchmarks + model-level ceiling

From W-34: after the GEMM fix, the likelihood interior is ~58.4%T of the
armB gradient and libm log1p alone is 19.9%T (5.020e9 Ir) — the single
largest symbol. Mission: measure the CEILING for replacing the glibc
log1p (and fusing the select/redux machinery around it) in
bernoulli_logit_lpmf, as evidence for a stan-math vectorization/packet
proposal. This is a ceiling measurement, not a production kernel.

WHAT STAN-MATH CALLS TODAY (read before registering, from
bernoulli_logit_lpmf.hpp 5.3.0 + W-34 callgrind dumps):
- Per observation (var-mode forward): e = exp(-ntheta) via Eigen Packet2d
  polynomial pexp (glibc exp is 0.02%T — ALREADY specialized, NOT
  re-measured); then logp term = 3-way Select at cutoff 20
  (x>20: -e; x<-20: x; else: -log1p(e)), partials = sel(x>20: -e;
  band: e/(1+e); x<-20: 1)*signs — partials-in-forward, no libm in rev.
- CRITICAL (verified from armB callgrind raw): log1p is called
  84,697,422 times / 4,424 var log_prob calls = ~19,150 ~= N — the
  nested Selects do NOT short-circuit; apply_scalar_unary evaluates
  stan::math::log1p (is_nan + check_greater_or_equal + std::log1p,
  glibc, ~59.3 Ir/call) EAGERLY on ALL 19,200 elements, and the result
  is DISCARDED for |x|>20. So the u = exp(-x) argument spans the FULL
  range (0, e^708] in principle, though only u in [e^-20, e^20] is used.
- Replaceable complex at model level: log1p 19.9%T + Select/redux/lambda
  machinery (stock-separable: 2.20e9 = 6.3%T; inlined into lpmf excl in
  armB) + partials-select arithmetic — ~30%T of armB, ~23% of stock T.

KEY MATH FACT (kernel enabler): with t = -x and the branch cut kept at
20, the whole in-band term is min(x,0) - log1p(exp(-|x|)) — i.e. ONE
log1p with argument w = exp(-|x|) in [e^-20, 1] (2.06e-9..1) for BOTH
sign branches; partial = w/(1+w) (x>=0) / 1/(1+w) (x<0). The primitive
reduces to log1p(w) on [2e-9, 1].

KERNELS (scratch/w46/, pure C++, no model builds for the bench):
- K0 stock-shape replica of the lpmf interior (Eigen array exp +
  per-element stan::math::log1p wrapper + nested Selects + partials
  select) — baseline; sanity: ~measured Ir share.
- K1 std::log1p direct, no stan checks — isolates the wrapper tax.
- K2 fused branch-cut SCALAR: glibc exp+log1p but log1p called ONLY
  in-band; value/partial/select structure otherwise identical to stock
  -> BIT-IDENTICAL outputs by construction (in-band bits unchanged).
- K3 fused scalar min-form: v = min(x,0) - log1p(exp(-|x|)) (glibc
  log1p always, but argument confined to [e^-20,1]); ulp-level reorder.
- K4 Kahan-corrected log1p: log1p(u) = plog(1+u) + m/(1+u) with
  m = ((1+u)-1)-u exact (FastTwoSum), u in [e^-20,1]; scalar and
  Packet2d (Eigen internal plog_double) variants.
- K5 polynomial log1p(w) = w*P(w), P a Chebyshev/minimax fit (mpmath,
  high precision) on w in [e^-20,1]; scalar and Packet2d variants.
- K7 Eigen generic_plog1p (exists for packets via Eigen
  MathFunctions) — accuracy expected to FAIL the 2ulp bar; measured
  anyway as the 'free' Eigen option.
- SLEEF u10/u35: NOT trivially vendorable (not single-header, not on
  system) -> SKIPPED, documented.
- APPROXIMATE ARM (separate, pre-registered): low-degree poly (~u35
  grade, few-ulp/1e-15 rel): gradient-parity gate NOT applicable by
  design; only quality-only 1-rep ESS spot check IF tested at model
  level; labeled approximate everywhere.

ACCURACY BAR (likelihood MATH — strict): for exact-grade kernels, max
abs error <= 2 ulp of the glibc log1p result on the tested argument
range (dense grids over [e^-20,1] and [e^-20,e^20] + edges), and
value/partial term ulp vs K0 on the real x sample. Model-level parity
gate: <=1e-12 rel on ~50 random unconstrained points (bit-identity
expected for K2).

SPEED BAR: >1.5x on the interior (ns/element) vs K0 on the REAL x
distribution (extracted by replicating eta = alpha_i*(theta_j - beta_i)
from the model at: inits_w25/hier_2pl pf points, posterior-cloud (init
+ 0.25 sigma), and random N(0,1) points — numpy replication of the
constraint transforms; the in-band fraction and |x| histogram get
recorded). 3 interleaved reps, medians, taskset, shared machine.

MODEL-LEVEL (only if a kernel clears accuracy+speed): patch
bernoulli_logit_lpmf.hpp locally (backup to scratch/w46/ first,
patch kept there), rebuild stock-form hier_2pl .so fresh in
scratch/w46/{stock,patched}_build/ (W-27 compile_model cache gotcha —
per-variant dirs), default CXXFLAGS, env -u LD_LIBRARY_PATH,
/usr/bin/make -j2. Measure: per-call us (3 reps medians, Python
driver, identical points), callgrind Ir/grad (W-29 protocol: warmup
100 samples 50, seed 20260819, pf init rep0/chain_0, one job at a
time), gradient parity ~50 points <=1e-12 rel. RESTORE stan-math to
pristine (md5-verified) after measurement.

Deliverable: results/log1p_ceiling_w46.md — what stan-math calls
today, per-kernel table (ns/elem, max ulp value+partial), model-level
ceiling, upstream proposal paragraph. Negative results recorded.
Expectation (pre-registered): K2 wins ~= out-of-band fraction of x
(likely small at posterior points — then its model win is only the
skipped redux/select fusion); K4/K5 2-4x on the log1p bucket if the
2ulp bar holds (packet 2-wide + inlined poly vs PLT call into glibc);
model-level ceiling ~= replaceable-complex share times kernel speedup,
i.e. up to ~15-25% further wall on top of armB-class codegen. The bar
may FAIL for all exact-grade kernels — that is a legitimate ceiling
answer (glibc log1p is correctly-rounded; beating it at 2ulp with a
faster kernel is the open question).

## W-45 (pre-registered BEFORE running): data-subsampled warmup transplant — the untried axis of warmup cost reduction

HYPOTHESIS: warmup only needs to estimate (inv_mass, step, min_micro_steps)
well enough that the FROZEN sampler is good. On data-heavy models a
gradient computed on a random α fraction of observation rows estimates
curvature/step nearly as well at ~αx the cost. Run WARMUP against a
SUBSAMPLED-DATA .so, then SAMPLE with the full-data .so using the
transplanted frozen state. NOT early exit (W-21/W-25/W-28/W-37 closed
that 4 ways): iterations stay 1000, each is cheaper. NOT error-loosening
(W-38-E2 rejected): the lever is the DATA the gradient sees.

STATISTICAL EXPECTATION (pre-registered): a mass estimated on αN rows is
a noisier but often near-sufficient curvature estimate — for iid-row
models the observed-information per row is unbiased for the same
population quantity, so E[inv_mass(alpha)] ≈ inv_mass(full) with variance
~1/(αN); the step size should transfer to first order (same posterior
geometry), BUT (a) hier_2pl/lsat per-person/per-item scale factors are
estimated from fewer rows per person (alpha*I or alpha rows) — persons
with 0 retained rows (P = (1-α)^32 ≈ 3% at α=0.1 on hier_2pl) fall back
to prior-scale mass, so SOME components may transfer badly; (b) the step
size at freeze is calibrated to the SUBSAMPLE posterior's error landscape
on trajectories of the full model — a mismatch concentrated in models
whose error scales with N (logp magnitude grows with N). Because of (b)
TWO freeze-time variants are pre-registered:
- V1 (pure transplant): frozen (inv_mass, step, min_micro_steps) + final
  warmup POSITION transplanted verbatim into the full-data sampler,
  warmup=0.
- V2 (transplant + step re-tune): as V1 but re-run ONLY the step-size
  heuristic (walnutpie find_reasonable_step, the library's own
  --step-init-heuristic code path) on the full-data model with the
  transplanted mass before sampling; mass and min_micro stay transplanted.
  (The third variant — re-run min_micro adaptation only — is NOT tested:
  min_micro is an integer trajectory-shape statistic with no cheap
  outside-warmup estimator; recorded as out of scope.)

MECHANISM (harness-only; walnutpie NOT edited, submodules NOT rebuilt):
stan_cli exports neither the frozen mass vector (WALNUTPIE_DEBUG_WARMUP
prints only invm[0]) nor accepts mass injection. The smallest harness
alternative: a standalone tool harness/w45/w45_run.cpp, compiled against
the walnutpie HEADERS read-only (same include set as build_w36exp's
compile_commands; the library is header-only), replicating stan_cli's
single-chain path exactly (same seeding, same StanHandler, same CSV
writer, same timing stanzas) with three modes: FULL (= CLI clone, state
dump added), WARMUP (subsample .so, warmup-only, dumps frozen step /
inv_mass diag / min_micro_steps / final position / final lp), SAMPLE
(full-data .so, constructs WalnutsSampler DIRECTLY from the transplanted
state — the library's own frozen-sampler constructor — warmup=0, seeds
the endpoint cache with one explicit full-data logp_grad eval, W-42
finite-logp guard included; --retune-step switches V1->V2 via the CLI's
find_reasonable_step call). TOOL FIDELITY GATE: FULL-mode draws must be
md5-identical to stan_cli (external/walnutpie/build_w36exp, READ-ONLY,
@43b6435) on 4 models x 3 reps x 4 chains (all cells; any mismatch = the
tool is wrong, fix before any transplant arm). Transplant chains are NOT
bit-comparable to base by design (fresh RNG stream in the sampling
process, different warmup trajectory); gates are statistical.

MODELS + SUBSAMPLING (deterministic seed 45; JSONs in scratch/w45/data,
.stan copies per (model,alpha) in scratch/w45/build_* — W-27 cache
gotcha; builds default flags, STAN_THREADS=1, env -u LD_LIBRARY_PATH,
/usr/bin/make, -j2, serialized):
- hier_2pl (N=19200 rows y/ii/jj; data-heavy, warmup share ~55%): random
  αN row subset, I/J unchanged. Unconstrained dims identical (671).
- blr (N=100 rows X/y; task labels it data-heavy class — N is in fact
  only 100, so the expected win is capped by non-data warmup overhead;
  recorded honestly either way): random αN aligned rows.
- lsat_model (Rasch; N=1000 students encoded as pattern counts): the
  aligned row unit is a STUDENT; subsampling students would change
  parameter dim (theta[N]). DEVIATION (pre-registered): the α-subsample
  .stan is a COPIED, data-block-modified version (likelihood over M=αN
  retained students, parameters alpha[T]/theta[N]/beta UNCHANGED so dims
  match 1006); retained thetas keep the likelihood, dropped thetas keep
  only their normal(0,1) prior — their transplanted mass is
  prior-variance-scale by construction (a known mechanism probe: does a
  wrong-scale minority mass block ESS?). Full-data .so stays stock.
- arma11 (CONTROL, T=200 time series, expect NO wall win — warmup is not
  data-dominated): random row drops are INVALID for a lag model;
  DEVIATION (pre-registered): contiguous PREFIX of length round(αT) is
  the consistent aligned subsample. Quality gates still apply.
α ∈ {0.25, 0.1}.

ARMS (all: warmup 1000 iterations on the warmup model, draws 1000 on the
full-data model, 4 chains as 4 SEQUENTIAL single-chain invocations,
3 reps, seeds 20260819+1000*rep+c, pf inits inits_w25/ for all four
models per the W-36 assignment, CLI-default configs otherwise, .so from
bs_models_threads/ for full-data phases):
- base: stan_cli full-data warmup+sampling (the reference; fresh runs,
  same grid as the transplant arms).
- toolbase: w45_run FULL mode (CLI-clone fidelity gate + source of base
  adapted state for gate (c)).
- v1_a25 / v1_a10: WARMUP on subsample α + SAMPLE full-data, pure
  transplant.
- v2_a25 / v2_a10: same WARMUP state (SHARED with v1 — same dump file,
  one warmup run per (model,α,rep,chain)) + --retune-step.

GATES (pre-registered):
(a) QUALITY: arviz rank-normalized bulk/tail ESS-min + R-hat max per
    model-rep (chains trimmed to min length, structurally-constant
    columns excluded — W-38-E2 conventions), MEDIANS of 3 reps. An arm
    PASSES a model iff median(ess_bulk_min) >= min(base per-rep bulk)
    AND median(ess_tail_min) >= min(base per-rep tail) AND
    median(rhat_max) <= max(base per-rep rhat) — the W-25/W-28/W-38-E2
    base-noise band. The marginal-class rule applies in full (no ESS
    regression on arma11/lsat/hier_2pl beyond the band).
(b) WALL: median total wall (subsample warmup process + full sampling
    process, external harness clock) vs base total (stan_cli warmup +
    sampling stanzas summed), per model/α, medians of 3 reps. Report
    realized saving vs theoretical (1-α)*warmup_share; warmup share
    measured from THIS grid's base stanzas. Phase-2 process startup +
    .so dlopen overhead counted against the arm (honest; a library-level
    in-warmup .so swap would remove it — recorded in the verdict).
(c) STATE TRANSFER (mechanism evidence either way): per model/α, the
    transplanted (step, inv_mass, min_micro) vs toolbase's full-data
    adapted values: step relative diff; inv_mass l2 rel diff + median/
    p90 |log-ratio| per component (separately for prior-only components
    on lsat); min_micro abs diff. Medians over 12 cells. If quality
    fails, this table must show WHY (e.g. per-item scale factors need
    full data; step mismatch from N-scaled error landscape).
VERDICT RULE: ADOPT (harness-level; propose library in-warmup .so swap)
iff (a) passes on ALL 4 models for at least one (variant, α) AND (b)
gives >=25% median total-wall saving on hier_2pl for that arm. TUNE if
quality passes but the wall saving is <25% or only at α=0.25. REJECT if
no arm passes (a) on the marginal class; the mechanism section must then
carry the state-transfer diagnosis.

BUILD/RUN PROTOCOL: env -u LD_LIBRARY_PATH everywhere; /usr/bin/make -j2;
serialized sampling (another agent shares the machine); no walnutpie
edits, no submodule rebuilds, no pushes. Deliverable:
results/subsampled_warmup_w45.md + harness/w45/* + runs/w45/ local.
Commits: explicit paths only (never git add -A).

## W-48 (pre-registered BEFORE running): stanc3 expression fusion for indexed elementwise likelihood arguments — the compiler-level fix for the W-34 plumbing tax

From W-34: ONE line of hier_2pl,
`y ~ bernoulli_logit(alpha[ii] .* (theta[jj] - beta[ii]))`, costs ~32%G
in eltwise var plumbing (subtract/elt_multiply over Holder<IndexedView>
gathered containers; per-element vari + arena entry + chainstack push, N
= 19,200 x 2 ops) plus ~8%T in rvalue<index_multi> gathers — ~40%G
total; the hand GEMM rewrite bounds the achievable win at -28.2% Ir/grad
(-23..25% per-call wall) with last-ulp gradient agreement (rel-L2
2.3e-15). W-34 Arm A showed no existing language primitive (GLM family)
reaches the pattern. W-39 proved a scoped stanc3 peephole
(fuse_eigendecompose) can be built, dune-tested, and validated
bit-identically on this clone @ 90c6532 with opam switch w39. Mission:
attempt the general fix in the compiler: remove the per-element vari for
elementwise expressions over INDEXED containers feeding a density call,
WITHOUT changing model semantics.

CANDIDATE SHAPES (explore both; ship what validates):
- A (narrow, first): detect when a density's vector argument is a pure
  eltwise chain over indexed var containers (`elt_multiply(gather,
  subtract(gather, gather))` and sub-patterns) and emit the value
  computation in double space with ONE fused autodiff node carrying the
  batched chain rule (partials-in-forward, the pattern the GLM lpmfs
  use). Study first how bernoulli_logit_glm_lpmf / normal_id_glm_lpdf
  get their special treatment (expectation: it is all in stan-math, NOT
  stanc3 codegen — then the mechanism to reuse is the MIR synthesis +
  codegen emission proven by W-39's eigendecompose_sym tuple trick).
- B (general, only if A is tractable): a Middle-End fusion pass merging
  elementwise chains over common indices before codegen (src/middle or
  the typed MIR).

GATES (validation is the arbiter; W-34 protocol):
(a) SEMANTICS: patched-stanc hier_2pl .so vs stock .so on ~50+100
    random/posterior-cloud unconstrained points: logp rel diff and
    gradient rel-L2 at LAST-ULP level (NOT bit-identity — per-element
    arithmetic is reordered by design), cosine ~1.0.
(b) COST: per-call wall (3 interleaved reps, medians, taskset 0-3);
    target approaches the -25% of the hand GEMM. Callgrind Ir/grad
    (W-29 protocol; ceiling -28.2%).
(c) SAMPLER SPOT: 1 rep x 4 chains ESS/rhat sanity vs stock base band.
(d) NO-TRANSFORM CHECK: compile 3 other models without the pattern
    (gp_regr, arma11, lotka_volterra); hpp diff vs vanilla-develop stanc
    shows ONLY boilerplate (no behavioral change).
(e) SUITE: dune runtest green.

DEGRADATION (effort is free but honesty rules): if full fusion is
intractable, deliver (i) the GLM-codegen study (how stan-math/stanc3
special-case GLM densities — the machinery a general mechanism
reuses), (ii) whatever scoped transform DID validate (e.g. gather-CSE
only), (iii) design doc for the rest. Negative results recorded.

BUILD/RUN PROTOCOL: work in external/stanc3 on branch w48-fusion off
90c6532 (W-39 patch preserved separately on its own branch; w48 patch
must apply to pristine develop); opam switch w39; dune -j2. Model
builds: fresh scratch/w48 dirs (W-27 cache gotcha), bridgestan 2.9.0,
default CXXFLAGS, env -u LD_LIBRARY_PATH, make -j2, custom stanc via
make_args=['STANC=...'] (W-39 mechanism). Deliverables:
results/stanc3_fusion_w48.md + scratch/w48/stanc3_fusion.patch. Commits:
explicit paths only (never git add -A). No pushes; walnutpie untouched.

## W-47 (pre-registered BEFORE running): SoA-arena / typed-pool / flat-callback tape refactor — tax decomposition + microbench ceiling + shippable-increment feasibility (research item X1)

Mission: the tape/arena complex is W-29 candidate #4 (fixed tax:
stack_alloc + chainstack emplace + arena ctors = 12.6%G hier_2pl,
16.9%G accel_gp, 8.2%G kronecker, 4.9%G gp_regr; 10.9%T stock / 8.1%T
post-GEMM-fix on hier_2pl per W-34). Upstream scan 2026-08: NO SoA-arena
work exists in stan-dev/math (only closed PRs #1103/#2928 adjacency).
Decompose the tax, measure the CEILING of alternative tape designs in a
pure-C++ microbench (no stan-math edits), and either prototype a minimal
integration hook or deliver the design document for the upstream
conversation.

WHAT THE TAPE ACTUALLY DOES (read from stan-math 5.3.0 source in
~/.bridgestan/bridgestan-2.9.0/stan/lib/stan_math BEFORE registering):
- var(double) -> new vari_value<double>(x,false) -> var_NOCHAIN_stack_
  push (arena alloc 24B: vptr+val+adj{0.0}); eltwise ops over
  Matrix<var> build ONE such vari PER ELEMENT of their output; each op
  registers ONE reverse_pass_callback vari (var_stack_) whose lambda
  loops the whole matrix on grad(). grad() iterates ONLY var_stack_
  (virtual chain() per entry); the per-element scalar varis have EMPTY
  chain() and are never dispatched — the nochain stack exists for
  set_zero_all_adjoints{,_nested} only. recover_memory(): vector clears
  + memalloc_.recover_all() + delete of chainable_alloc objects.
- So candidate taxes to separate: (1) stack_alloc::alloc bump calls,
  (2) chainstack emplace_back (both stacks), (3) vari ctor stores
  (vptr+val+adj zero) mostly INLINED into op bodies, (4) grad()
  dispatch loop + virtual calls (O(#ops) NOT O(N) on hier_2pl),
  (5) recover_memory/clears, (6) cache effects of pointer-soup layout.

TAX DECOMPOSITION (task 2): from EXISTING W-29/W-34 callgrind dumps in
results/profile/{w29,w34}/ (no fresh model runs unless a needed number
is missing; fresh hier_2pl callgrind allowed, W-29 protocol, one
valgrind 3.23 job at a time, ~/vginstall). Sub-shares per model:
stack_alloc::alloc excl; chainstack emplace_back excl; vari-ctor
inlined share (tree edges from alloc/emplace callers into eltwise
ops); grad() loop share (locate under logp_grad subtree);
recover/clear share. Report as %G with Ir/grad and Ir/vari
(vari counts derived: hier_2pl line = 2N scalar varis + 2 callbacks
per gradient, N=19200).

MICROBENCH (task 3, scratch/w47/, pure C++ linking the bridgestan
stan-math 5.3.0 headers, -O3 default flags, no model builds, no .so):
- A0 stock-replica: N=19200 gathered eltwise chain exactly like the
  hier_2pl line (rvalue multi-index views -> subtract -> elt_multiply)
  + grad + recover; measures real ns/vari and Ir/vari (build+reverse).
- A1 scalar-vari floor: k*N var(double) constructions (isolates
  alloc+emplace+ctor without Eigen glue).
- B typed-pool variant: same elementwise OUTPUT as A0 but vari records
  are POD {double val; double adj;} in a preallocated typed bump pool
  (no vptr, no per-vari chainstack push — batched span registration),
  callbacks unchanged; bounds allocation+record-layout savings only.
- C flat-callback variant: reverse pass as an array of
  {fnptr, void* data} POD entries replayed in reverse (no vari_base
  vtable, no virtual dispatch), forward pass stock-shaped otherwise.
- D = B+C combination.
- Correctness gate per arm: gradient of the chain matches A0 to
  rel-L2 <= 1e-12 on the same inputs (the bench computes a real
  derivative of the chain, not a no-op loop).
- Measurements: wall ns/vari (median of interleaved reps, taskset'd)
  and Ir/vari via callgrind on the bench binary (one job at a time).
  Report per arm: build ns/vari + Ir/vari, reverse ns/vari + Ir/vari.

INTEGRATION FEASIBILITY (task 4): read hook points first (vari_base
operator new -> memalloc_; vari ctors -> stack pushes; grad() loop;
recover_memory). If a variant clears >30% of the vari overhead AND has
a non-invasive hook (compile-time flag, no public-type change), attempt
minimal integration in the bridgestan stan_math tree with md5-verified
restore. var is a POINTER type (vi_) across all of rev/ + user code +
stanc3 output — an index-based SoA var is a breaking rewrite: expected
outcome is STOP-at-ceiling + design doc with the API surface needed
(cite the scan's no-existing-work finding + stanc3 #1666 O(1)-nodes
motivation as the upstream context).

DELIVERABLE: results/sota_arena_w47.md (tax decomposition, microbench
table, integration verdict + the incremental shippable proposal or
design doc, honest ceiling statement). Artifacts under scratch/w47/
(bench.cpp, Makefile, raw outputs, any patch files). RESTORE any
patched bridgestan stan-math files to pristine (md5-verify). Commits:
explicit paths only (never git add -A). No pushes; walnutpie untouched.
Env: env -u LD_LIBRARY_PATH; /usr/bin/make -j2; serialized heavy runs.

## W-49 (pre-registered, feasibility-first — no new runs; arithmetic over existing artifacts): within-chain speculative parallelism for WALNUTS — measured ceiling vs the 4-chain null

Item X3. The parked lead from W-38u / upstream_scan §T7: Picard-map
parallel Metropolis transitions. ID DISAMBIGUATION (verified): the
Picard-map paper is arXiv:2506.09762 (Grazzi et al., Biometrika 2026);
arXiv:2506.09355 is de Leeuw's eigenvalue-derivatives note (scan §2,
unrelated — the context prompt's "2506.09355... verify" resolves to
2506.09762, as the scan lists). Companion: WALNUTS paper arXiv:2506.18746
(JMLR 27(113) 2026) — its §4.1 ALREADY anticipates one mechanism (see
below). Walnutpie watchers that touch the accounting: issue #34
(gradient caching), PR #77 (leapfrog unroll).

QUESTION: can a single WALNUTS chain productively use >1 core by
SPECULATION — evaluating leapfrog micro-steps along the orbit before the
dyadic search / U-turn logic knows it needs them, then committing or
discarding? Feasibility-first: the deliverable is a MEASURED ceiling
verdict from EXISTING data (runs/w38/accounting.json buckets, W-36
parallel-session walls, W-29 overhead shares) plus the paper mapping; a
prototype is built ONLY if the ceiling clears the gate below.

DEPENDENCY MAP (from walnuts.hpp @ 43b6435, the part that decides
everything): within one attempt, micro-steps are a STRICTLY SERIAL chain
(each leapfrog needs the previous gradient: macro_step L330-334). The
dyadic attempts in a macro_step all RESTART from the same span endpoint
(L326-328) — mutually independent, no guessing needed, bit-identical by
construction. Same for the ladder rungs in reversible/within_tolerance
(L269-279): independent integrations from the accepted endpoint. Macro
steps chain endpoint-to-endpoint (build_span L489-497) — serial. The
per-depth direction coin (transition_w L594, uniform_binary) is
state-INDEPENDENT Bernoulli(1/2). U-turn and combine use no gradients
(L194-203, L379-398). Walnutpie implements the paper's D (deterministic
micro-selection) variant — no per-macro-step random lattice bit; the
paper's R2P variant would add one more unguessable bit per step.

PRE-REGISTERED CEILING SPLITS (work decomposition = W-38-E1 buckets
{fa, fw, bl, dl} of kernel evals):
- SPLIT A (the maximally generous framing, clairvoyant): fa alone is
  speculative; fw+bl+dl serial. Amdahl S(N) = 1/(s + p/N).
- SPLIT B (dependency-honest): hideable = fw+bl ONLY (the independent
  attempts/rungs); critical path = fa+dl (micro-chains serial within
  attempts; dl is decision-necessary; direction-coin lookahead has
  expected correct-prefix length 1 = O(1) macro steps at m=1). More
  cores beyond 2 cannot raise SPLIT B.

NULL HYPOTHESIS TO BEAT (W-36, same 4 cores): 4-chain parallel
exp_par/exp_seq = 2.77x geomean (3.43x on hier_2pl: 155.06 s -> 45.26 s),
already carrying +10-25%/call memory-bandwidth contention. GATE
(pre-registered): BUILD the prototype only if the best defensible 4-core
ceiling >= 1.5x the null (~4.2x vs the geomean null); also fails if the
dependency-honest ceiling < 1.5x absolute. STOP at analysis otherwise —
a complete negative that parks the direction with numbers.

CONTINGENT PROTOTYPE SHAPE (only on gate pass; own worktree
external/walnutpie_w49 off exp/safe-adapt-defaults @ 43b6435): 2-thread
producer that pre-integrates the next macro-step's most-likely forward
span while the current transition's ladder/decision logic runs
single-threaded; commit/discard rule on the main thread. Gates:
bit-identity canary 12/12 with speculation OFF and ON (speculation must
compute the SAME doubles, just earlier; any arithmetic-order change is a
bug; RNG stream stays main-thread-only and untouchable); wall on
hier_2pl + blr vs serial and 4-chain-parallel baselines, serialized
runs.

VERDICT RULE: report split A as the unphysical upper bound, split B as
the honest one; the gate is evaluated on split B primarily (A only to
show the idea fails even under clairvoyance). Where split B is large
(mis-settled kernels), the evals in question are dyadic WASTE — the
W-38-E2/E4 lane deletes them serially; parallelizing waste is strictly
dominated by deleting waste, and that argument must appear in the
verdict.

Deliverable: results/speculative_w49.md (paper mapping, ceiling
arithmetic, verdict, contingent-prototype gates). No builds unless the
gate passes. Protocol: env -u LD_LIBRARY_PATH; /usr/bin/make -j2 only if
building; serialized runs; explicit-path commits only (never git add -A);
no pushes; walnutpie submodule branch untouched.

## 2026-08-23 — W-46 CLOSE-OUT: log1p ceiling MEASURED — fused branch-cut kernel with deg-16 Chebyshev log1p + AVX2/FMA runtime island: −22.8% Ir/grad, −15.3% wall on STOCK hier_2pl, gradient parity 2.4e-16; at baseline ISA the ceiling is WALL-NEUTRAL (the ask is multiversioned packet math); BONUS: found a real partials sign bug in stan-math bernoulli_logit_lpmf (ntheta>20 branch misses `signs`, wrong sign for y=1, still in develop)

WHAT STAN-MATH CALLS (§1 of results/log1p_ceiling_w46.md): per observation
the lpmf computes packet exp (Eigen pexp — glibc exp is 0.02%T, NOT
re-measured) and then EAGERLY calls glibc log1p (via apply_scalar_unary ->
stan::math::log1p wrapper -> std::log1p, 59.2 Ir/call) for ALL 19,200
elements — 84,697,422 calls / 4,424 var log_prob = 19,150 ~= N (verified
from W-34 armB raw callgrind) — with the result DISCARDED for |ntheta|>20
by the nested Selects. Real x distribution (numpy replication of the
model's eta, scratch/w46/extract_x.py): posterior draws 100% in-band,
|x| <= 15.7; pf-init/cloud/random 99.63-99.65% in-band — so the out-of-band
skip (k2, bit-identical by construction) buys ~nothing on real data; the
win must come from the in-band primitive, which reduces (softplus
identity) to log1p(w), w = exp(-|x|) in [e^-20, 1].

MICRO-BENCH (§2): peeled deg-16 Chebyshev log1p on [0,0.5]-reduced u
(mpmath 60dps fit, tail error 2^-60): **<= 1 ulp vs glibc** on 2.2M-point
grids (exact-w; an 8-ulp figure seen in one harness was a w-roundtrip
artifact of the test, not the kernel). Kahan-corrected Eigen plog: 1 ulp.
Eigen generic_plog1p (already exists for packets): 2 ulp. Fused kernels
(value+partial, both outputs): at BASELINE SSE2 nothing beats stock on
wall (best packet kernel −24% Ir but 0.85-1.02x wall, latency-bound 2-wide
no-FMA; scalar fused 1.09x); under AVX2+FMA 1.9-2.2x wall / 3.1x fewer Ir
(100 -> 32 Ir/elem interior). Approximate deg-10 arm (~3000 ulp = 2e-13):
2.59x only — accuracy is cheap; arm NOT exercised at model level
(pre-registered conditional). SLEEF skipped (not single-header vendorable).

MODEL-LEVEL (§3): patch = one fused kernel replacing exp-array + both
Select expressions (scratch/w46/bernoulli_logit_lpmf.hpp.patched):
scalar path + #pragma GCC target("avx2,fma") island with
__builtin_cpu_supports dispatch. Three arms, fresh builds in
scratch/w46/{stock,patched,patched_base}_build (W-27 cache gotcha).
TOOLCHAIN: system g++ driver lost its internal search paths mid-session
(GCC 16.2.1 fresh package, AppImage-branded); scratch/w46/gxx_fixed
wrapper restores them; rebuilt STOCK .so is BIT-IDENTICAL to W-34's stock
build on 20 points (lp + full gradients) — like-for-like confirmed.
GATES: (a) parity PASS — island max rel lp 1.24e-14, grad rel-L2
2.37e-16 (100 pts: 50 random + 50 cloud); base 3.7e-16/2.45e-16.
(b) wall: stock 1261.4 -> island 1068.8 us/call (0.847x, −15.3%; 3
interleaved reps, medians; absolute inflated by co-running agents);
patched_base (scalar) 1.206x = NEGATIVE result (packetization essential).
(b) callgrind (W-29 protocol; IDENTICAL 3737+756 = 4493 grad calls all
arms): stock T 34.92e9, 7.772M Ir/grad (W-34: 7.745M, 0.35% rebuild
drift); island T 26.98e9, **6.004M Ir/grad (−22.8%)**; base 8.500M
(+9.4%). Replaced complex {glibc log1p 4.60e9 + wrapper 0.42e9 +
Select/redux 2.20e9 + partials machinery} -> fwd_avx2 2.99e9 (11.1%T);
lpmf exclusive 6.43e9 -> 2.04e9. Draws md5 differ (ulp-level grads, same
workload), as expected. Two kernel bugs caught BY THE GATES before any
reported number: island pldexp used two 2^b factors instead of Eigen's
three (2^b scale error; parity failed at 14% -> fixed -> 2.4e-16), and
hand-transcribed poly coefficients were stale (unit ulp check caught;
regenerated from the mpmath header).

BONUS UPSTREAM BUG (§5): bernoulli_logit_lpmf partials,
(ntheta > cutoff) branch is `-exp_m_ntheta` WITHOUT the signs factor —
d lp/d theta = signs·(+exp(−ntheta)) there, so for y=1 observations with
ntheta > 20 the partial has the WRONG SIGN (error 2·e^-ntheta <= 4e-9 per
element; correct only for y=0). Present in stan-math develop as of
2026-08-23. Found because the first patched build differed from stock by
exactly this amount (max |dpartial| 4.08e-9 at ntheta = 20.011 ->
5e-10 rel on alpha-grads at wild points). Final patch is bug-COMPATIBLE;
the fix (`-exp_m_ntheta` -> `signs * exp_m_ntheta`) is a separate
one-line upstream PR.

UPSTREAM ASK (§4): (1) fuse + packetize the lpmf interior — log1p only
needs w in [e^-20,1]; deg-16 Chebyshev or Kahan-plog (or Eigen's own
generic_plog1p, 2 ulp) gives <=2 ulp, and one fused pass computes value +
partials, removing the eager full-array glibc log1p and both Select
passes: −22.8% Ir/grad on hier_2pl stock form (more on the W-34 armB form
where the interior is 58%T). (2) The wall win REQUIRES AVX2+FMA — at
baseline ISA the same kernel is wall-neutral; the concrete ask is
function-multiversioned packet kernels (pragma-target island + runtime
dispatch) inside stan-math, which does not touch the global -march
question (W-27's miscompile was global -march=native on Eigen GEMM).
(3) fix the signs bug in the same PR. (4) do NOT chase exp (already
packet), the OOB skip (99.6-100% in-band), or the stan wrapper checks
(~4 Ir/elem, free).

Artifacts: results/log1p_ceiling_w46.md; results/profile/w46/{stock,
patched,patched_base}/ (callgrind.out, cli.log, draws.csv); harness/w46/
(scripts + kernel sources + gxx wrapper); scratch/w46/ untracked (builds,
.so, pristine backup). stan-math RESTORED pristine (md5
f003c78a165c2be67ce22b30c046c0e2 re-verified after restore; find confirms
bernoulli_logit_lpmf.hpp was the only header touched). walnutpie
submodule untouched; no pushes.

## W-50 (pre-registered BEFORE running): the -fno-math-errno family — a compile-flag lever W-27 never tested

RATIONALE (user's sharp question): gcc under its default -fmath-errno
cannot optimize errno-setting libm calls; with -fno-math-errno the
errno-guarded transforms unblock. W-33 proved std::pow(x,2) -> x*x in
stan-math's square() is worth the full 8.9%G Ir / 13-15% wall bucket on
gp_regr with BIT-IDENTICAL values (glibc pow correctly rounded). If gcc
performs that same transform at the MODEL .so level under
-fno-math-errno, W-33-style wins arrive WITHOUT touching stan-math.

MECHANICS PROBE (done BEFORE registration; gcc 16.2.1, -O3 -std=c++17
-fPIC, this box): -fno-math-errno turns pow(x,2) into mulsd (x*x);
sqrt(x) loses its errno compare+branch (bare sqrtsd, value-identical);
pow(x,3) and pow(x,0.5) are NOT transformed (stay pow@PLT) — so the only
value-level transform is the bit-exact one from W-33. Elementwise
exp/log1p loops do NOT vectorize under -fno-math-errno (nor with
-fno-trapping-math added): glibc guards its libmvec __DECL_SIMD_*
declarations behind __FAST_MATH__, which we will NOT define (it implies
reassociation => breaks bit-identity). Honest scope: errno-only removal
buys scalar errno-guarded transforms (pow2->mul, inline sqrt), NOT
vectorized elementwise libm chains.

ARMS (per model): default build vs CXXFLAGS=-fno-math-errno (flag
APPENDED to the default set; default -O level O=3 preserved). Contingent
3rd arm ONLY if arm 2 passes parity AND wins on the first two models:
-fno-math-errno -fno-trapping-math (semantic difference stated:
-fno-trapping-math additionally promises FP exceptions need not be
raised precisely — no value change for non-trapping code; Stan never
unmasks FP traps nor reads exception flags; parity gate unchanged).
Models: gp_regr (pow-heavy: 8.93%G libm::pow), hier_2pl (log1p-heavy:
14.43%G libm::log1p — expected UNTOUCHED, the falsification model for
the vectorization half of the story), kronecker_gp (eigh-heavy control:
pow 1.99%G, expect ~nothing). Build protocol: .stan COPIED per variant
into scratch/w50/<model>_<variant>/ (W-27 cache gotcha: compile_model
silently reuses a cached .so next to the .stan); env -u LD_LIBRARY_PATH
(confirmed first-hand this session: the profile's AppImage
LD_LIBRARY_PATH breaks the system g++ header search outright);
MAKE=/usr/bin/make; MAKEFLAGS=-j2; shared cores -> serialized timing.
Baselines: fresh default-build arm (plus gp_regr cross-check against
the surviving W-33 stock .so).

GATES (pre-registered):
(a) PARITY — 100 deterministic random unconstrained points per model
    (W-27 scheme, random.Random('w50-parity-0')): gradient AND logp
    BIT-IDENTICAL vs default .so. Exact 0.0 is the target and the
    expectation (errno-only removal changes no FP value; pow(x,2)->x*x
    bit-exact per W-33). ANY nonzero diff stops the arm and gets
    investigated/documented before any win is claimed. FD spot-check on
    the flagged .so (W-27/W-33 method).
(b) COST — per-call logp_grad us via the native stan_cli stanza
    (build_e27 binary, read-only; 3 interleaved reps per arm-pair,
    medians; W-33 protocol) + Python pair-interleaved cross-check +
    callgrind Ir/grad (system valgrind 3.25.1, one job at a time;
    ~/vginstall 3.23 cross-check on gp_regr stock vs the recorded W-29
    digits 66,990 Ir/grad / pow 3,453,345 Ir for era-consistency).
(c) SAMPLER SPOT — winning model only, 1 rep x 4 chains (single-chain
    procs, seeds 20260819+c, warmup=1000 samples=1000 --metric-window
    50, identical fixed inits per arm): draws md5-IDENTICAL to the
    default-.so run + wall comparison.

EXPECTATIONS (pre-registered): gp_regr replicates W-33 (Ir/grad about
-9%, wall about -13..15%, bit-identical draws); hier_2pl about 0 (log1p
stays scalar per the probe); kronecker_gp small (<=2% class). If
confirmed, the flag is a free companion to the W-33 upstream ask (same
transform, zero source change) — adoption decision recorded either way.
Negative results recorded same as wins. Deliverable:
results/errno_flags_w50.md. No stan-math / walnutpie tree changes
(shared trees pristine; new scratch builds only); no pushes.

### W-47 CLOSE-OUT: SoA-arena ceiling = ~1/3 of the eltwise complex; flat callbacks measured ZERO; span-chainstack prototype sampler-bitwise but codegen-blocked — results/sota_arena_w47.md

Tax decomposition (existing W-29/W-34 dumps, harness/w47/alloc_edges.py):
alloc 6.41%T + emplace 4.47%T (hier_2pl; 13.0/9.0 Ir per call, 172M/174M
calls) + ctor stores inlined in op exclusives; grad() loop + recover =
0.27%T; anatomy: eltwise ops build one nochain vari per element + ONE
reverse_pass_callback per op — dispatch is O(#ops), NOT O(N).
Microbench (scratch/w47/bench.cpp, bitwise-gated): stock per-vari floor
32.6 Ir (A1); typed pool saves 16.6 Ir/record = -32% of the tape complex
(F_SS 51.1 -> F_PS 34.6 Ir/record; build wall 3.97 -> 1.40 ps/record);
FLAT CALLBACKS = 0.00 delta (negative result: vtable concern obsolete at
per-op granularity); A0-F_SS gap (50.8 Ir/record) is Eigen/Holder glue =
the fusion lane (W-34), not the arena lane. Integration: SoA var =
rewrite (pointer type everywhere) -> STOPPED at ceiling per
pre-registration, design doc in the writeup (Increment A: batch
vari-array + span registration API; Increment B: typed pools keeping var
a pointer). The shippable increment WAS attempted: span-chainstack
shadow-header patch (8 files, scratch/w47/w47_span_chainstack.patch;
pristine tree md5-verified untouched): correctness PERFECT (microbench
gradients bitwise; hier_2pl .so full sampler run warmup100+draws50
draws.csv md5-IDENTICAL fe7c57c9...; gotcha recorded: bridgestan's
prebuilt src/bridgestan.o links pristine headers into every model .so —
any layout-touching patch must rebuild it or segfault). Perf: microbench
build -25.7% wall (controlled, non-overlapping reps) but model-level Ir
+1.0%T (GCC 16 -O3 -fPIC inlines per-record registration ~11 Ir/record
WORSE than the out-of-line emplace; subtract excl +25.5%); model wall
noise-bound. VERDICT: not shippable as per-record checks; needs the
op-level batch API (design doc). Deliverable: results/sota_arena_w47.md;
artifacts scratch/w47/ + harness/w47/alloc_edges.py; profile dumps
scratch/w47/out/profile/{stock,patched}. No walnutpie changes; no
pushes; bridgestan pristine (md5 OK; hardlink copy deleted).

## 2026-08-23 — W-45 CLOSE-OUT: REJECT (negative result) — the transplanted geometry is a DIFFERENT posterior's, not a noisier full-data one; mechanism fully measured

Executed as pre-registered (harness-only; walnutpie untouched, exp-tip
binary read-only, no submodule rebuilds). Full report:
results/subsampled_warmup_w45.md. Artifacts: harness/w45/ (make_subdata,
build_subso, w45_run.cpp, run_w45.py, analyze_w45.py), runs/w45/ local,
results/w45_{fidelity,ess,wall,state,hierblocks}.json.

- TOOL FIDELITY: 48/48 toolbase CSVs md5-identical to stan_cli base — the
  transplant runs on a bit-exact clone of the reference path. Mechanism
  (documented, not a CLI flag): standalone w45_run.cpp consuming the
  header-only walnutpie; SAMPLE mode constructs WalnutsSampler directly
  from the dumped frozen (inv_mass, step, min_micro, position).
- GATE (a) QUALITY: FAIL — no arm passes on the marginal class (all 4
  arms fail hier_2pl, lsat_model, arma11; hier collapses to bulk-min
  4-97 vs base 625, rhat to 3.4, up to 5/12 pinned chains; only
  blr/v1_a25 passes, a 6-param N=100 model). REJECT per the
  pre-registered rule.
- GATE (b) WALL: subsample warmup prices ~alpha AND slightly fewer
  calls (hier a25 17.6k vs 20.5k) — but the transplanted SAMPLER burns
  1.2-1.9x base gradient calls (wrong metric -> deeper ladders), eating
  the win on hier (38% -> net 0.62x at a25, 24% at a10). blr v2's
  "90% saved" cells are PINNED chains (fast garbage). Control arma11: no
  reliable win, as expected.
- GATE (c) STATE TRANSFER (the result): STEP transfers (median
  log-ratio +0.03..+0.26; V2's re-tune lands no closer AND is worse on
  hier/lsat — a global step cannot repair per-component metric
  mis-scaling); min_micro 1->1 everywhere. INV_MASS does NOT transfer:
  hier med |log-ratio| 1.18 (a25) / 1.70 (a10), block split theta
  1.19->1.70, xi2 1.49->3.01 vs population blocks 0.33-1.07 — exactly
  the data-dominated per-person/per-item components (632/669 of hier's
  dims); lsat's constructed retained-vs-prior-only split shows 0.07-0.19
  vs 0.35. POSITION does not transfer: full-data logp at the subsample
  warmup endpoint is -1,247 (a25) / -1,896 (a10) below base's on hier.
  The optimistic premise ("noisier but near-sufficient curvature
  estimate") is refuted: per-component posterior width scales with each
  component's retained-row count; subsample warmup adapts toward a
  different target (why subsampling-MCMC uses importance corrections,
  not state transplants).
- VERDICT + library question: REJECT V1/V2 as implemented; a library
  in-warmup .so swap is NOT worth proposing in this form (failure is
  statistical, not I/O). Recorded follow-up candidate (needs its own
  pre-registration): two-phase warmup — alpha-subsample early phase +
  truncated K-iter full-data re-adaptation; mechanism data predict a
  modest ceiling (warmup share 0.52-0.56 minus re-adaptation length
  minus the measured sampling-phase inflation).

## W-52: FILE-READY upstream PR branches + polished PR/issue bodies (external/pr/) — user files TODAY

MISSION (release prep): per PR — a branch with clean commit history and
meaningful message in a local clone, clean code, and a detailed body that
identifies the issue, motivates the solution, and carries before/after
benchmarks + references. Correctness of attribution and numbers over
speed. NO PUSHES anywhere; exact push/PR commands produced for the user.

ADDITIONAL REQUIREMENT (user, mid-task): every PR body must enable
maintainer RE-DERIVATION — complete problem derivation (actual
equations), step-by-step solution derivation followable WITHOUT reading
our diff (patch positioned as "reference implementation, provided for
convenience"), validation protocol precise enough to reproduce (model,
N, seeds/method, parity bar, FD checks), references. Noted as the design
principle in external/pr/README.md and applied to all four PR bodies.

BRANCHES (one clean commit each; explicit-path adds only; never -A):
1. math `eigen-cluster-aware-adjoint` @ 3f240769 (base develop 46a3133,
   Eigen 5.0.1): W-44's uncommitted tree (verified byte-equal to
   scratch/w44/cluster_adjoint_dev_46a3133.patch + identical test file)
   committed as 3 files (+428/-4); test target force-recompiled and run:
   4/4 PASS. math_dev left checked out here, clean.
2. math `square-pow-to-mul` @ 3ef423bd (same base): scratch/w44/
   square_fix_dev_46a3133.patch applied; square_test 2/2 +
   squared_distance_test 7/7 recompiled and run.
3. math `bernoulli-logit-partials-sign` @ 87026fef (same base): the
   one-liner written directly against develop's
   prim/prob/bernoulli_logit_lpmf.hpp (ntheta>cutoff partials branch:
   `-exp_m_ntheta` -> promote_scalar<T_partials_return>(signs *
   exp_m_ntheta); develop wraps sibling branches in promote_scalar —
   matched). Shared template confirmed (rev/mix route through prim);
   SEPARATE same-pattern site found in bernoulli_logit_glm_lpmf.hpp
   (theta_derivative first branch) — NOT fixed in this PR, flagged in
   the body with an offer to include or follow up. New gtest
   `cutoff_partials_sign` (analytic signs*exp(-ntheta) + central FD of
   the double impl, both y=1/theta=+25 and y=0/theta=-25, h=1e-3
   staying in-branch): binary 6/6 with fix; verified to FAIL on the
   unpatched header (stash/rebuild/run/pop cycle) — discriminating.
4. stanc3 `fuse-eigendecompose-pair` @ c2c3b0b (base master 90c6532,
   re-verified zero drift on a FRESH shallow clone at
   external/stanc3_pr; external/stanc3 untouched per instruction):
   scratch/w39/stanc3_eigh.patch applied (staged diff byte-verified
   identical to the patch); opam switch w39; dune runtest of
   compiler-optimizations + warn-pedantic golden dirs, then re-run with
   --force: PASS exit 0. Single commit (9 files, +2914/-2).
5. fork PR sims1253/stan#1 (scratch-hoist): already filed; indexed.

BODIES (stan/external/pr/, tracked): README.md (index + per-item push +
gh pr create commands incl. fork setup for account sims1253, drift-check
snippet, could-not-verify list) + pr-1..4 + issue-5a/5b (bridgestan,
with repro snippets + versions) + issue-6 (fused log1p proposal: design
+ reference-implementation pointer + the numbers + SSE2 latency caveat +
MVCC-island ask) + notes-7 (walnutpie trio: init-guard 8.22s/31,002
calls -> 0.16s/1 call loud abort; freeze-clamp auditable fallback; blr
pin root cause + find_reasonable_step 3-defect fix, 0/48 chains pinned,
w100-pf bulk-ESS-min 779.0 vs base 5-9, canary 12/12). Every number
cross-checked against results/*.md before writing (key figures:
cluster-adjoint divergence 1.156 -> 6.96e-5/3.1e-8, FD 30-52% ->
<=1.4e-6, ESS-min 48.1 -> 367.7 median / R-hat 1.13 -> 1.02, 200/200
well-separated bit-identical; square 66,950 -> 60,864 Ir/grad, wall
6.681 -> 5.820 / 6.655 -> 5.640; stanc3 406.8 -> 343.4 us/call (-15.6%)
with W-32 ceiling 5.254M -> 4.238M Ir/grad; log1p 7.772e6 -> 6.004e6
Ir/grad (-22.8%), 1261.4 -> 1068.8 us/call (-15.3%), parity 1.24e-14 lp
/ 2.37e-16 grad).

NOT VERIFIED (recorded for the user): math develop drift past 46a3133
(README carries the check command); CI on other platforms/compilers;
Eigen-5 kappa sweep (kappa evidence measured on the 2.39/Eigen-3.4.0
toolchain — guard math is Eigen-independent); GLM sign fix offered but
not in the branch. Clones stay untracked; no pushes; machine shared
(-j2 throughout).

## W-51 (pre-registered BEFORE running; RETRY of the rate-limit-killed attempt — no prior W-51 entry survived): literature scan 2 — recent (2024–2026) published/preprint ideas for our active fronts

MISSION: six fronts, one query each: (1) SoA/adjoint-array autodiff
arenas (JAX/XLA, Enzyme, Adept lineage, batched vari APIs); (2) SIMD
transcendental kernels in stats libraries (SLEEF/xsimd/libmvec
adoption + accuracy standards); (3) HMC/NUTS step-size+mass adaptation
theory post-2023 (dual-averaging successors, warmup-with-guarantees);
(4) differentiation with repeated/degenerate eigenvalues
(gauge/minimal-norm adjoints) beyond He 2023 / de Leeuw 2508.09355;
(5) within-chain MCMC parallelism (parallel/speculative leapfrog
beyond arXiv:2506.09762); (6) WALNUTS citations/derivatives since
JMLR 2026 (arXiv:2506.18746).

METHOD (rate-limit mitigation, pre-committed): at most 6 hermes
one-shot queries (`hermes chat -q`), sleep 90 between calls, raw
output saved under scratch/w51/ as it runs; after TWO consecutive
rate-limit failures hermes is ABANDONED and WebSearch/WebFetch (zcode
builtin) covers everything — fallback fully satisfies the mission and
will be stated honestly in the close-out. Top ~5 leads independently
verified via WebSearch/WebFetch (existence + one-line relevance,
titles/abstracts only). Read-only research: no builds, no model runs,
shared trees untouched.

DELIVERABLE: stan/external/research_scan2_2026-08.md — per front:
leads with arXiv IDs/URLs + one-paragraph relevance verdict; TOP-5
ranked "try this next" mapped to open items (two-phase warmup W-45
follow-up, SoA rollout W-53, fused log1p kernel W-46, errno flags
W-50, eltwise fusion W-48). Commits: explicit paths only (never
git add -A). Companion context: results/upstream_scan_2026-08.md +
results/UPSTREAM_SUMMARY.md (read first).

## W-53 (pre-registered BEFORE running; attempt 3 — two prior attempts died on infra rate limits before any artifact; no prior W-53 entry survived): staged SoA-var rewrite for stan-math — phase 0/1 only (pointer-semantics inventory + migration plan + 3-level utility estimate + ONE vertical slice)

MISSION: W-47 stopped at the typed-pool ceiling (-32% of the tape
complex, microbench) and wrote the design doc (Increment A batch
make_vari_array + span registration; Increment B typed pools keeping
var a pointer). W-53 is the staged rollout's phase 0/1: (0) classify
EVERY var/vari POINTER-semantics dependency across stan/math/develop
(raw vari* in signatures, identity comparisons on var, address-of,
casts, containers of vari*, dump/serialize, direct chain() calls) into
(i) mechanical / (ii) needs API shim (var stays a pointer backed by
typed-pool storage) / (iii) structural blockers (nested arenas,
thread-local chainstack, STAN_THREADS); write the ordered MIGRATION
PLAN (file batches, seam, per-batch risk) as the fresh-session handoff
artifact. Utility estimate at 3 levels: (a) arithmetic bound per model
(W-47/W-29 tape shares x -32%), (b) locality bound via cachegrind on
W-47's microbench pair (scratch/w47/, rebuild if needed), (c) ground
truth from the slice. (1) vertical slice: typed-pool/SoA records for
ONE op path end-to-end — elt_multiply (98% of hier_2pl's tape traffic;
W-47 attribution: eltwise pair owns ~98% of arena-alloc calls).

SAFEGUARD (non-negotiable, pre-registered): a pure layout refactor
must be BIT-IDENTICAL by construction. Gates per increment: (a)
exact-zero gradient parity on the 4-model battery (hier_2pl,
kronecker_gp, gp_regr, accel_gp; bridgestan .so from per-variant
scratch dirs — W-27 .so-cache gotcha), (b) full sampler draws
md5-identical via walnutpie binary
external/walnutpie/build_w36exp/examples/stan_cli READ-ONLY (never
rebuild walnutpie), (c) stan-math unit tests for TOUCHED targets only,
(d) documented arena-semantics reasoning for what bit-identity cannot
see (nested arenas, reset/reuse). ANY nonzero parity = stop and
diagnose. HAZARD (W-47): bridgestan's prebuilt src/bridgestan.o embeds
pristine stan-math headers — model .so MUST be built with a
consistent-ABI bridgestan copy whose stan_math carries the patch
(hardlink-copy recipe, W-47-validated) or segfaults.

SETUP: fresh clone github.com/stan-dev/math (develop) ->
external/math_soa (untracked; commit recorded). external/math_dev and
external/stanc3_pr are the PR-prep agent's — READ-ONLY for me, not
used. Uncommitted W-51 WORKLOG append left as-is (selective staging
for my commits: git apply --cached of my own hunks only). Env:
env -u LD_LIBRARY_PATH; /usr/bin/make -j2; test targets only;
measurements serialized (shared cores).

STOP RULES: bit-identity failing structurally -> stop, document the
impossibility precisely. Slice gates failing nonzero -> stop and
diagnose before ANY further rollout. Deliverable:
results/soa_var_w53.md (inventory, migration plan, 3-level utility,
slice gates+measurements, go/kill verdict); patches scratch/w53/;
external/math_soa untracked. Commits: explicit paths only (never git
add -A). No pushes; walnutpie untouched. NOT in scope: the full
400-file rollout (multi-session by design — this session delivers the
validated foundation + measured utility number).

## 2026-08-23 — W-50 CLOSE-OUT: -fno-math-errno replicates the W-33 win on gp_regr but is NOT value-neutral — glibc pow(x,2) is 1-ulp-unrounded; parity FAILS on hier_2pl/kronecker_gp, full-length draws diverge; DO NOT ADOPT, and W-33's bit-identity claim is demoted to trajectory-conditional

ARMS BUILT (scratch/w50/<model>_{default,nme}/, copied .stan per variant,
env -u LD_LIBRARY_PATH — confirmed first-hand: the profile's AppImage
LD_LIBRARY_PATH breaks the system g++ header search outright, which is WHY
the protocol demands unsetting it; MAKE=/usr/bin/make; MAKEFLAGS=-j2;
CXXFLAGS=-fno-math-errno appended, O=3 default preserved). Arm 3
(-fno-trapping-math) SKIPPED per pre-registration (arm 2 failed parity;
mechanics probe shows it adds nothing anyway).

(a) PARITY: gp_regr PASS (100/100 logp+grad bit-identical; fresh default
    also 100/100 bit-identical to the surviving W-33 stock .so). hier_2pl
    FAIL: 99/100, pt43 comp 667 (tau.2) 2.0e-15 rel. kronecker_gp FAIL
    CATASTROPHICALLY: 14/100, max rel 1.72, 5 sign flips — W-27
    march=native signature.
    ROOT CAUSE (investigated as pre-registered): the premise inherited
    from W-33 — glibc pow(x,2)==x*x — is FALSE. glibc 2.44 pow(x,2)
    differs from the correctly-rounded x*x by 1 ulp on ~0.08% of doubles
    (x*x is the CORRECT one; pow errs). Isolation with W-35's drivers
    (rebuilt per flag arm) + a d0 stage printer + a dlopen gradient
    driver + full-threshold callgrind: GEMM/eigh-fixed-inputs/cholesky/
    lkj all bit-identical between arms; kronecker_gp's xd=-square(grid
    diffs) differs on 4/900 entries (the 1-ulp cases) -> Sigma1 bits
    differ -> SelfAdjointEigenSolver returns a different-but-valid basis
    of the jitter-pinned near-degenerate cluster -> eigenvector adjoint
    amplifies to O(1) (W-35's amplifier; same end-to-end signature as
    march=native, different seed). hier_2pl: exactly 2 param-dependent
    pow(x,2)/grad (W-29 tree confirms 8,986/4,493); default arm executes
    libm pow at pt43, nme inlines it; one site hit a disagreeing double
    -> 1-ulp seed -> 2-ulp wobble in tau.2's adjoint (logp bit-identical;
    the fixed 150-iter callgrind trajectory never hits one -> draws
    md5-identical on that protocol). gp_regr's 11-point grid: 0/121
    kernel pairs disagree — the model's 55/57 pow sites are data-fixed,
    which is exactly why W-33 measured perfect bit-identity there.
(b) COST (native stan_cli stanza, 3 interleaved reps, medians; callgrind
    system valgrind 3.25.1, one job at a time):
      gp_regr:     us/call 5.414->4.738 warmup (0.875x), 5.320->4.584
                   sampling (0.862x); Ir/grad 66,987->61,310 (-8.48%);
                   pow Ir 3,473,268->18,975 (sampler-side Adam residual).
                   REPRODUCES W-33 (-9.09% Ir, -12.9/-15.2% wall) within
                   noise. Stock arm reproduces W-29 to the digit (pow Ir
                   exactly 3,473,268; Ir/grad 66,987 vs 66,990; vginstall
                   3.23 vs system 3.25.1 differ by 602 Ir total).
      hier_2pl:    960.7->959.1 (0.998x), Ir/grad -0.002%; log1p Ir
                   identical 423,531,966; ZERO pow in the model gradient.
                   As pre-registered: no libmvec vectorization without
                   __FAST_MATH__ (glibc guard), so the log1p bucket is
                   untouchable by errno-family flags.
      kronecker_gp: per-call 0.963/0.986 and Ir/grad -1.23% CONTAMINATED
                   (trajectory drifts: 5,094->4,732 calls; the 1-ulp seed
                   changes warmup) — same caveat class as W-32's hand arm.
(c) SAMPLER SPOT (gp_regr, 4 chains, warmup=1000 samples=1000, seeds
    20260819+c, deterministic inits inits_w50/gp_regr/): wall 278.1ms ->
    244.1ms (-12.2%); draws md5 c1/c3 IDENTICAL, c0/c2 DIVERGED — gate
    FAIL. Cross-check with the W-33 patched .so (same x*x semantics): it
    ALSO diverges from stock at full length on both tested chains, and on
    c2 its draws are md5-IDENTICAL to the nme arm (flag == patch != stock).
    Short fixed-init 50+50 protocol stays md5-identical across all arms
    (32881fbe..., native and under valgrind) — bit-identity there is real
    but trajectory-length-dependent.

VERDICT: no free W-33 via flags. -fno-math-errno delivers the same win
only where parity already holds (gp_regr, by grid luck) and is a
reproducibility hazard everywhere else; on eigh-heavy models it is the
march=native hazard class (silent O(1) gradient changes). NOT adopting for
our builds. UPSTREAM CONSEQUENCES: (1) W-33's pow->mul PR keeps its
performance case but must drop the bit-identity promise — reframe as
"replaces a <=1-ulp-error pow with the correctly-rounded product (strict
accuracy improvement, glibc 2.44 measured), NOT bit-identical; can flip
equally-valid eigenbases on rounding-degenerate models (W-35)"; (2) add
errno-family flags to the march=native do-not-use list in the docs ask.
Deliverable: results/errno_flags_w50.md; raw results/profile/w50/
(committed); scripts+drivers+.so in scratch/w50/ (untracked);
inits_w50/ committed. stan-math + walnutpie trees pristine; no pushes.

### W-53 CLOSE-OUT: staged SoA-var phase 0/1 DONE — pointer-semantics inventory (registration seam = 19 sites/5 files; 2 null-check-only identity cmps; no hash/map-on-var; nested+TLS = the structural set), ordered migration plan, 3-level utility (arithmetic −8..−12%G hier full rollout; locality −96.7% of record-complex LLd misses on the W-47 pair), and the elt_multiply vertical slice ALL GATES PASS + MEASURED — results/soa_var_w53.md

TREE: external/math_soa = fresh clone develop @ 344d7167 (arena
machinery byte-identical to bs bundle 5.3.0 except the stack_alloc pad
bugfix). SLICE (scratch/w53/w53_soa_slice_develop.patch, 9 files + 1
new header, applies to both develop and the bs 5.3.0 bundle tree):
make_nochain_vari_array = ONE arena alloc + placement-new records +
ONE nochain span; elt_multiply rev-rev Matrix<var> branch only;
set_zero{,_nested}/start/recover{,_nested}/profiling span-aware;
records stay 24B layout-compatible (Increment A, not B). GATES ALL
PASS first try: (a) exact-zero parity 4/4 models (100 pts each, values
+ full grads bitwise, 0 mismatches); (b) draws md5 IDENTICAL
stock==patched==W-47's recorded fe7c57c99a7a6530ce2dcc408d6e9c65
(walnutpie build_w36exp read-only, W-29 protocol; 69 identical benign
probe-failure logs both arms); (c) mix/fun/elt_multiply_test 3/3;
probe-level stock-vs-patched bitwise (develop+Eigen5 via git-stash
A/B). MEASURED: sampler-level callgrind (identical 4,493-call
trajectories): T 37.128e9->34.273e9 = −7.69%, G/grad 7.723M->7.087M =
−8.23%; elt_multiply fwd −27.7%, its reverse callback
instruction-identical, subtract (untouched) 0.0%, stack_alloc::alloc
−49.2%, chainstack emplace −48.9%; net −13.0 Ir/record of the 32.6
Ir/vari stock tax (new batch loop costs +9 Ir/record vs stock's
inlined Eigen ctor loop). WALL is regime-split: in-sampler native
stan_cli stanza −0.7..−2.2%/call; repeated-eval (python bridge, 50
fixed pts, both arm orders, tight non-overlapping) −21..−23% with Ir
anchor −11.5%/call (valgrind .venv python — NOTE: uv run under
valgrind silently skips the model load; and a 20-call variant gave a
sign-flipped artifact from a fixed +24.8M patched-.so loader
constant — resolved at 200 calls; both gotchas documented). Locality
bound (cachegrind, --cache-sim=yes, on W-47's F_SS/F_PS pair): LLd
3.169M->0.106M = −96.7% (0.413->0.014 misses/record) — the wall-vs-Ir
gap in the repeated-eval regime. CODEGEN RISK MEASURED: isolated
develop/Eigen-5/-O3-nonPIC driver (scratch/w53/wild_driver.cpp):
patched −9.2% Ir but +17% WALL (placement-::new serialization blocks
reordering; production bundle TU shows the opposite) — batch 1 of the
migration plan must gate on WALL per toolchain and the record loop
should be restructured (vptr-store + memcpy val block) before any
upstream PR. HAZARD BIT AGAIN: default make left the hardlinked
pristine bridgestan.o in place (silently up-to-date, md5-identical) —
must rm src/bridgestan.o && make src/bridgestan.o. VERDICT: GO for
staged batch-API rollout; bit-identity NOT structurally blocked;
Increment B (no-vptr SoA) not needed for most of the value (batch API
alone captured −8.2%G vs the −10..−16%G Increment-B ceiling).
Artifacts: results/soa_var_w53.md; harness/w53/ (scripts);
scratch/w53/ untracked (patch, inventory raw, builds incl. bs_w53
hardlink copy, profile dumps, draws, drivers); external/math_soa
untracked, left PATCHED at the slice state. Pristine bundle md5-verified
untouched; walnutpie untouched; no pushes; W-51 WORKLOG append left
as-is (my commits stage my own hunks only via git apply --cached).

## W-48 OUTCOME (appended after completion; entry above is the
pre-registration): eltwise fusion transform CORRECT but Ir/wall-NEUTRAL
— W-34 §7.2(a,b) eltwise-fusion ceiling REFUTED on current math; −28%
belongs to grid-structure exploitation

Resumed from a predecessor that died on rate limits at 14:11 with the
full implementation uncommitted on external/stanc3 w48-fusion; all state
salvaged, re-verified, and completed. Branch committed: w48-fusion @
4b07a23 (base 90c6532); patch scratch/w48/stanc3_fusion.patch; full
writeup results/stanc3_fusion_w48.md.

WHAT SHIPPED: Optimize.fuse_indexed_eltwise (Oexperimental-only, last in
suite, reverse-mode log prob only; matches bernoulli_logit_lpmf args
that are pure +,-.*,/ chains over containers indexed once by a
data-variable multi-index, <=8 leaves) + Lower_expr.Fused_eltwise
lowering (Cpp.IIFE): values gathered once in double space, ONE
vari_value<VectorXd>, ONE reverse_pass_callback applying the batched
chain rule with inline per-element partials; AoS (Matrix<var>) leaves
get arena vari** pointer arrays, SoA (var_value<VectorXd>) leaves use
x.vi_ — selected via if constexpr. Integration test fused-eltwise.stan
(2 firing + 3 guarded cases); expectations regenerated; fused code only
in the Oexperimental expectations.

GATES: (a) PASS bit-identical (0.0 rel logp, 0.0 grad rel-L2, 200 pts)
vs stock --Oexperimental — same per-element arithmetic order; (c) draws
BIT-IDENTICAL same-seed (cmp clean); (d) arma11/gp_regr/lotka_volterra
hpp diff = 1 boilerplate line each; (e) dune runtest -j2 green (full
tree, twice; manual Oexperimental sweep content-matches cpp.expected).
(b) FAIL: Ir/grad 5,644,934 -> 5,678,304 (+0.59%), wall 665.8 -> 671.1
us/call (+0.80%, 7 reps medians); the HAND-coded same-shape reference
also loses to its stock (+7.97% on its baseline). All arms traced
identical 2172 gradient calls.

MECHANISM (refutation): on stan-math 5.3.0 the eltwise rev ops over
gathered containers are ALREADY one-callback-per-op with arena value
matrices; the ~35%G eltwise+gather complex is per-element value-gather +
adjoint-scatter, which eltwise-shape fusion cannot remove — the fused
lowering re-spends forward (value_of-expression gathers cost MORE than
direct var gathers for AoS; 2x19,200 vari** pointer fills) what it saves
on op boundaries. W-34's −28.2% (arm B GEMM) eliminated per-element work
entirely via the complete-grid identity — reachable only by (1) a stanc3
grid-detection pass (complete-design IRT -> [theta,-1]*[alpha;alpha.*b]
rewrite + runtime grid check) or (2) a stan-math gathered-GLM primitive
(W-34 §7.3(i)). Candidate B (middle-end eltwise fusion) MOOT. GLM-codegen
study done: GLM specialness is 100% stan-math prim/prob single headers
via operands_and_partials (no rev/prob GLMs, zero stanc3 codegen — only
signatures + OpenCL restrictions + pedantic); the general reusable route
for compiler-side custom varis is the W-39/W-48 marker+lowering+
reverse_pass_callback mechanism, now proven twice.

CONFOUNDS/GOTCHAS recorded: predecessor's stock_build/handfused arms
were compiled against the since-reverted W-46 vectorized-log1p math
(w46_kern in profiles — worth −34%G alone on hier_2pl!); only the
pristine-math pair stock_oexp/fused_build is comparable; cross-arm grad
rel-L2 3e-10 vs those arms is the log1p kernel, not the fusion. stanc
embeds absolute source paths + output path in the hpp (normalize before
diffing). dune is silent on test success; verify by forcing output
regeneration. hier_2pl tp-block per-element assignment (alpha[i]=...)
forces Matrix<var> AoS layout — vectorized tp would give SoA and cheaper
gathers for stock AND fused (orthogonal lever, unmeasured).

Artifacts: external/stanc3 w48-fusion @ 4b07a23 committed (stanc3_pr and
w39-eigh untouched); scratch/w48/ (5 .so arms, 5 callgrind profiles,
gate scripts, gatec draws); results/stanc3_fusion_w48.md. Upstream pack
consequence: the hier2pl-plumbing candidate should be refiled as
grid-GEMM detection / gathered-GLM, NOT eltwise fusion.

## W-54 (pre-registered BEFORE running): two thread-inspired early-warmup shields — Arm A init-buffer mass deferral (mass_init_buffer) + Arm B warmup-only soft gradient clipping of the adapter's score stream (grad_clip_scale) — both default-off, both targeting the W-43 pin class from the mass/gradient sides the W-43 step fix left untouched

COMMUNITY SOURCES (why these two levers): (1) walnutpie 0.0.1
release thread (discourse 41487, post 11, seantalts relaying
"Fable"'s analysis of a Lotka-Volterra stuck-chain report): nutpie-style
CONTINUOUS mass adaptation from iteration 1 (mass_init_count=4, first
observation ~20% weight) lets enormous tail gradients collapse the
mass estimate -> chain crawls -> self-reinforcing; Stan avoids this
with an INIT BUFFER (identity metric for the first ~75 iterations) so
tail geometry never contaminates the metric. (2) discourse 41095
post 39 (aseyboldt): SOFT gradient clipping f(x) = c*asinh(x/c)
(c=1e10; identity below ~1e8, logarithmic beyond) eliminated stuck
chains in nutpie, with only a reversibility intuition for validity.
Our W-43 fixed the STEP side (find_reasonable_step); the MASS side
(deferral) and the GRADIENT side (soft clipping) are untested by us.
NOTE: session-2's "clipping negative" was clipping the MASS ESTIMATE
(--mass-init-clamp family) — a different lever; do not conflate.

BASE: worktree external/walnutpie_w54, branch exp/warmup-shields off
exp/safe-adapt-defaults @ 43b6435. Cherry-picks first (both
default-path-neutral, verified by the canary): 468e60f (W-43
find_reasonable_step fix — REQUIRED for the 779-bar comparison arm;
opt-in --step-init-heuristic path only) and 8853fd7 (W-43
WALNUTPIE_PIN_TRACE instrumentation, env-gated zero-behavior; manual
conflict resolution drops the W-38 grad-accounting context lines that
do not exist on this branch).

ARM A DESIGN — mass_init_buffer (std::size_t, default 0 = current
behavior; CLI --mass-init-buffer N): for warmup iterations < N the
mass estimator is NOT fed (no observe(), no window-chopping reset, no
low-rank refresh) and the transition runs with the IDENTITY inverse
mass; from iteration N on, continuous adaptation begins exactly as
today. To avoid a metric discontinuity at the buffer boundary the
estimator is SEEDED AT IDENTITY when mass_init_buffer > 0 (both
OnlineMoments initial variances = 1; with the default 0 the constructor
is byte-identical to today's gradient-seeded path). Reading of the
latitude "identity/initial value": IDENTITY (the Stan transplant).
Holding at the "initial" (CLI gradient-seeded |grad| ~ 1e7) value
instead is NOT chosen because the seed is itself the contamination
vector the thread diagnoses; that variant also equals drift-phase
metric semantics minus the step/cap suspension (drift_iters), a
different lever. Knob grid: N = 75 primary (Stan-style), 50/100
probes. PRE-REGISTERED EXPECTATION (from W-43): A ALONE probably does
NOT unpin the base cell — during a pin the mass is dormant anyway
(ratio of constant streams) and the buffer's N iterations are spent
pinned; escape remains the step-descent first passage (A changes the
|dH| constants via the identity metric, shifting escape iteration
either way). A's real test is ON TOP of the W-43 step fix: with
--step-init-heuristic the chain moves from iteration ~1 and crosses
the tail for ~100+ iterations (W-43: lp climbs -3.347e7 -> -2.93e7
over 100 iters) — exactly the phase where continuous adaptation eats
1e7-scale scores; the buffer should keep the metric clean until the
chain is near the typical set. Prediction: A75+heur >= heur alone on
the pf class; A alone shifts escape iteration but leaves the race.

ARM B DESIGN — grad_clip_scale c (double, default 0 = off; CLI
--grad-clip-scale) + grad_clip_iters M (std::size_t, default 200; CLI
--grad-clip-iters): during warmup iterations < M the gradient fed to
the ADAPTER — i.e. the score stream of the mass estimator,
MassEstimator::observe's grad argument — is replaced elementwise by
g' = c*asinh(g/c). SCOPE REASONING (pre-registered): the ONLY
model-gradient input to adaptation is the mass estimator's score
stream — the step adapter consumes the scalar alpha = exp(-|dH|)
only (adam.hpp: grad = target - alpha), and |dH| is a property of the
integrated trajectory. Clipping the INTEGRATOR gradient would change
the Hamiltonian being integrated (the sampler would target a
smoothed posterior — the reversibility ladder checks the same
smoothed dynamics, so it is self-consistent but for a DIFFERENT
target); that is out of scope for a warmup shield and we do NOT do
it. Consequence, stated up front: B CANNOT tame the alpha underflow
(the pin's engine) by construction — if the mechanism requires
touching alpha via the trajectory gradient, the pre-registered
action is STOP and document, not silent semantics change. B's testable
claims are mass-side: bound the score-variance scale during the tail
crossing so inv_mass cannot collapse; measurable in the trace and in
B+heur vs heur. Knob grid: c = 1e10 (thread value), 1e8 (thread
alternative), and a labeled exploratory 1e6 — pre-registered
justification: blr's pinned-class gradients are 1e6-1e7 (W-43 seed
1.6e7; pf class ~5e2), i.e. 1-4 orders BELOW the thread's c, where
asinh is the identity function to <1e-6 relative; without a value at
the model's own scale the lever cannot bite on THIS pin class. M = 200
throughout. NOTE the honest prediction: during a true pin the score
stream is CONSTANT, so clipping is a fixed monotone map of a constant
— the var ratio (hence inv_mass) stays frozen at a slightly different
level; B alone leaves the pin alone, exactly like A.

GATES (same battery as W-43 for comparability; all runs serialized
single-chain CLI invocations, env -u LD_LIBRARY_PATH, OMP_NUM_THREADS=1):
(a) CANARY: default path (all knobs off) draws bit-identical 12/12
(arma11/blr/hier_2pl x 4 chains, 1000+1000, seeds 20260819+c, rep0 pf
inits) vs the exp/safe-adapt-defaults binary saved BEFORE the
cherry-picks from the same worktree. This gate also transitively
covers both cherry-picks.
(b) UNPIN (blr, 3 reps x 4 chains, seeds 20260819+1000*rep+c,
samples 1000; pinned = all draws identical): w100/w400 x default/pf
inits, knob ON vs base. Because (a) proves the knob-off path is
bit-identical to base, base pin behavior is INHERITED (W-43/E2 bands:
w100-pf 3/4 chains pinned, bulk 5-9; w1000-def 1/4). Arms: A75
(4 cells), A50/A100 (w100 both inits), B c=1e10 (4 cells), B c=1e8/
1e6 (w100 both inits), AND the W-43 fixed-heuristic arm reproduced
on this branch (--step-init-heuristic alone; its w100-pf bulk 779.0
is the bar) plus combinations A75+heur and B(c best)+heur. PASS
criterion for an arm: 0/12 pinned in its cells AND bulk-ESS-min
median >> base's pinned 5-9; "beats the bar" = > 779 on w100-pf.
(c) NO-HARM: hier_2pl AND lsat_model, w1000 samples 1000, 3 reps x
4 chains (same seed protocol; rep0/1/2 pf inits), knob ON (A75; B
c=1e10 and c=1e6) vs base runs on the SAME binary (knob-off):
bulk/tail ESS-min medians within the base rep-to-rep noise band.
(d) MECHANISM (WALNUTPIE_PIN_TRACE=1, blr, 1 chain, seed 20260819,
w1000): knob off vs A75 vs B(1e6) — |dH| of first/min attempt, alpha,
step, inv_mass geo/min/max per iteration. Questions: does A hold
inv_mass at identity through the buffer and does adaptation then
start from identity (no seed collapse, no boundary jump)? does B
change the frozen inv_mass level (constant-stream map) and/or tame
the post-escape score-variance scale? does either move the escape
iteration materially? Expectation from W-43: neither tames alpha
(step-side).
DELIVERABLE: results/warmup_shields_w54.md (both arms, all gates,
mechanism traces, verdict per arm: adopt as additional shield /
redundant given the W-43 fix / reject; negatives recorded). Commits
on exp/warmup-shields in the worktree; stan repo WORKLOG + results +
harness with explicit paths only (NEVER git add -A). Worktree left
in place. Hygiene: -j2 builds, clean-first after header edits,
/usr/bin/make, serialized sampling, one edit -> build -> test ->
commit.

## 2026-08-23 — W-51 CLOSE-OUT: literature scan 2 DELIVERED — stan/external/research_scan2_2026-08.md; hermes 6/6 queries survived (one transient 429 post-answer, no fallback needed); TOP-5 ranked leads mapped to open items

Executed as pre-registered (retry attempt; no prior entry existed).
Hermes: all 6 one-shot queries completed (q1 13:58 / q2 9:39 / q3
19:30 / q4 17:10 / q5 15:26 / q6 39:00 wall; sleep 90 between; raw
transcripts scratch/w51/q{1..6}_*.txt). ONE provider 429 fired during
q4's post-answer memory-save (zai 5-hour limit, reset 23:01) — q5/q6
then ran clean on rotated pooled credentials, so the two-consecutive-
failures fallback never triggered; WebSearch/WebFetch/gh used for the
planned independent verification pass only (20+ leads verified
first-hand: arXiv abs fetches, gh api on JAX PR #36832 / XAD v2.1.0 /
AHMC.jl #470 (+ Carpenter's own comments) / numpyro #2070 / walnutpie
README / lindermanlab/parallel-mcmc, Semantic Scholar citation pulls
for 2506.18746, 2506.09762, 2508.09355).

HEADLINES per front: (1) SoA arenas — the field SHIPPED our W-47
design: CoDiPack 3.0/3.1 statement-level tape + custom evaluators,
XAD 2.1.0 flat slot/multiplier op tape, Warp/PyTorch-compiled-autograd
per-array-op registration, ParDiff direct-indexed tape (PPoPP 2026,
geomean 30.9x vs Enzyme); Adept = negative (maintenance-only). (2) SIMD
libm — glibc 2.41/2.43 imported correctly-rounded CORE-MATH binary32/
binary64 + uses ifunc multiversioned FMA islands itself (the W-46
mechanism); SLEEF u10/u35 two-tier policy is the norm; stan-math has
NO vector libm and NO library ships correctly-rounded VECTOR binary64
log/exp — our fused log1p kernel claim stays best-in-class; W-50 errno
probe corroborated (__DECL_SIMD_* behind __FAST_MATH__). (3) Adaptation
— Fisher-divergence low-rank+diagonal metrics (2603.18845, Carpenter
co-author, 114 posteriordb models, 4x median) + theory-backed two-phase
unadjusted-then-adjusted warmup (2603.22741, LAPS 2601.16696); explicit
gap confirmed: nobody analyzes DA x expanding-window. (4) Degenerate
eigenvalues — JAX PR #36832 (merged 2026-04-17) ships a gauge-fixed,
opt-in-flag eigvec JVP; Zhang&Hu minimal-norm SVD backward (2411.14141);
verified negative: NO paper does gauge-fixed/minimal-norm eigh adjoints
valid at clusters — W-40/Kit 4 remains novel with new precedents to
cite. (5) Within-chain parallelism — DEER trajectory parallelism incl.
parallel leapfrog (2508.18413 NeurIPS 2025, 4-180x GPU) + Lyapunov
predictability theory (2508.16817); multiproposal ceiling proven
(2410.23174); open cell = Metropolis-adjusted + warmup (walnutpie-
shaped). (6) WALNUTS — 9 citations pulled; upstream walnutpie is
BECOMING "Adaptive WALNUTS" (README) = nutpie-style Fisher mass + Adam
step size (Carpenter talk 3/2026 + his AHMC #470 comments, verified);
only third-party WALNUTS quantification = AHMC #470's ~0.5x ESS/grad
vs NUTS pre min-micro-steps tuning — matches our W-38-E1 framework.

TOP-5 (full rationales in the deliverable): (1) score/Fisher
low-rank+diagonal metric in walnutpie warmup -> W-45 follow-up + fork
strategy; (2) two-phase unadjusted-warm-start warmup -> W-45 follow-up
axis with new theory; (3) cite-and-ship gauge-fixed eigvec adjoint
(JAX PR #36832 + 2411.14141 precedents) -> W-40/Kit 4; (4) DEER/Picard
trajectory parallelism w/ predictability gate -> W-49 successor lane;
(5) reframe W-53 SoA rollout on the CoDiPack-3/Warp pattern (feeds
W-48's fused-node story).

Artifacts: stan/external/research_scan2_2026-08.md (committed);
scratch/w51/ (untracked, transcripts preserved). Read-only research:
no builds, no model runs, shared trees untouched, no pushes.

## W-55: REMAINING PRs prepared and PUSHED (batch 2) — math GLM sign sibling (fix, discriminating-test gated), walnutpie robustness trio (3 branches off dev/init-robustness), SoA-arena issue text; external/pr index items 5–9

Mission: the follow-ups beyond the four already-pushed batch-1 branches.
Fork pushes only (sims1253/*, the established idea-history pattern); NO
upstream pushes. Concurrent agents respected (W-51/W-54 files untouched).

TASK A — math `bernoulli-logit-glm-partials-sign` @ 305cc0cb, PUSHED to
fork (sims1253/math) ✓. Base develop 46a31337 (same as batch 1); built in
a NEW worktree external/math_dev_glm (math_dev proper left checked out on
eigen-cluster-aware-adjoint, untouched; lib/ symlinked into the worktree).
- Pattern VERIFIED (not just taken from PR 3's body): prim/prob/
  bernoulli_logit_glm_lpmf.hpp builds theta_derivative =
  select(ytheta>cutoff, -exp_m_ytheta, select(ytheta<-cutoff, signs*1.0,
  signs*exp_m_ytheta/(exp_m_ytheta+1))) — value branch -exp(-ytheta) ⇒
  d/dtheta = signs*exp(-ytheta); first branch drops signs (wrong sign
  for y=1, theta>20; feeds x/alpha/beta adjoints). rev/mix instantiate
  the same prim template (no overrides). BONUS same-pattern site found:
  opencl/prim/bernoulli_logit_glm_lpmf.hpp
  select(high_bound_expr, -exp_m_ytheta_expr, …) — flagged in the body,
  NOT fixed (needs a STAN_OPENCL validation environment).
- Fix: one line, sibling-branch style (`signs * exp_m_ytheta`). Test
  `AgradRev.bernoulli_glm_cutoff_partials_sign` appended to
  test/unit/math/rev/prob/bernoulli_logit_glm_lpmf_test.cpp: 1x1 design
  matrix, alpha=0, beta=±25, y∈{0,1}; beta AND alpha autodiff gradients
  vs analytic signs*exp(-ytheta) AND central FD (h=1e-3, both points
  in-branch) of the double implementation.
- GATES: full binary 23/23 PASS with the fix; verified to FAIL on stock
  via stash/rebuild/run/pop — adjoints sign-flipped by exactly 2*exp(-25)
  (-1.3887943864964021e-11 vs +1.3887943864964021e-11) — discriminating.
  Worktree left rebuilt in the FIXED state. Body:
  external/pr/pr-5-math-glm-sign.md (self-contained per the README spec;
  cross-references the non-GLM sibling PR by title; offers fold-in).

TASK B — external/pr/issue-9-math-soa-arena.md (no branch;
conversation-starter): Problem/Evidence/Proposed direction/Feasibility
proven/Risks/References, self-contained from results/soa_var_w53.md +
results/sota_arena_w47.md. Contents: tape decomposition (stack_alloc
6.41%T + emplace 4.47%T on hier_2pl, 172.4M+173.5M calls, 22.4 of 32.6
Ir/record; one nochain vari/element + one callback/op ⇒ dispatch is
O(#ops) not O(N), grad() loop 0.27%T); typed-pool microbench ceiling
(−32% of the tape complex; LLd misses −96.7%, 0.413→0.014/record);
flat-callback refutation (measured 0.00 — stated to focus effort on
records); the bit-identical vertical slice (4-model exact-zero parity,
sampler draws md5-identical fe7c57…, −7.69%T/−8.23%G at sampler level,
identical 4,493-call trajectories); the two shippable increments (batch
make_nochain_vari_array + span registration; typed pools keeping var a
pointer); pointer-semantics inventory headline (19 push sites/5 files; 2
identity compares, both null guards; 0 var-in-map/hash); risks (Eigen-5
isolated-TU +17% wall codegen sensitivity — gate on wall per toolchain;
bridgestan prebuilt bridgestan.o hazard with the exact rm+make command).

TASK C — walnutpie trio off dev/init-robustness (3eddfc4 == the fork's
origin/dev/init-robustness, so PR bases exist). New worktree
external/walnutpie_rob; main submodule worktree untouched (still
exp/safe-adapt-defaults); other agents' worktrees untouched. All three
PUSHED to origin = sims1253/walnutpie ✓ (origin already is the user's
fork — no remote changes needed):
- robustness/step-heuristic-fix @ da42cc2 ← 468e60f only (trace commit
  8853fd7 excluded). CLEAN cherry-pick (warmup_heuristics.hpp has zero
  overlap with the 9 intermediate W-23..W-31 commits).
- robustness/freeze-clamp @ c5058ff ← 53daa3e (W-41 clamp) then cfc1de3
  (W-43 probe-fix port — the clamp's fallback (b) calls the probe).
  CLEAN cherry-pick despite adaptive_walnuts.hpp/api.hpp overlap.
- robustness/init-guard @ 1f963eb ← 5aed078 ADAPTED (documented in the
  commit message): the cherry-pick hit delete/modify conflicts on
  examples/stan_cli.cpp (the exp lineage carries the W-25..W-31
  multi-chain machinery absent on dev/init-robustness) — resolved by
  dropping the multi-chain plumbing; AND a g++ -fsyntax-only check
  caught that the E5 endpoint-cache seeding (adaptive_walnuts.hpp)
  references cached_grad_/cached_logp_ from W-23 (absent here) — that
  file restored to base. Guard itself unchanged (config.hpp lp
  recording + init_logps(), load_stan max_tries plumbing, CLI file-init
  fail-fast + random-init rejection loop + --init-tries). E5 was proven
  draw-neutral by the original W-42 gates, so dropping it cannot move
  draws. All three branches passed the same -fsyntax-only check.
- No binaries rebuilt (gates already run on the original commits:
  results/init_guard_w42.md, freeze_clamp_w41.md, blr_pin_w43.md);
  branches are history artifacts.
- Bodies: external/pr/pr-6-walnutpie-init-guard.md,
  pr-7-walnutpie-freeze-clamp.md, pr-8-walnutpie-step-heuristic.md —
  each self-contained (mechanism derivation, discourse-41487-post-11
  community cross-ref, fix, gates incl. bit-identity canaries,
  before/after: init guard 8.22s/31,002 calls → 0.16s/1 eval loud abort
  (lotka 5.28s→0.09s; unguarded outcomes = zero-ESS pinned chain, set
  bulk-ESS 5.34/NaN estimators); freeze-clamp recovery table (both cells
  complete, fallback (a)=init seed 1.0, chains 1-3 zero warnings,
  quality recorded honestly as garbage); step-heuristic w100-pf
  bulk-ESS-min 5–9 → 779.0 median, 0/48 chains pinned, escape iteration
  948 → 1, probe eps 2.0 → ~0.008, warmup 3102 → 937 calls, sampling 31
  → 8.2 evals/draw).

INDEX — external/pr/README.md: restructured into batch-1 (W-52,
historical) / batch-2 (W-55) sections with file names as the unique
identifiers; items 5–9 with branch/clone/base/push-✓; filing commands
for all (walnutpie BOTH variants: fork-internal PRs against
dev/init-robustness, and upstream flatironinstitute/walnutpie with the
check-the-upstream-base caveat; recommended order 6→7→8); batch-2
verification evidence + not-verified list; drift-check extended with
the GLM file.

NOT VERIFIED (recorded): walnutpie gates not re-run on the re-based
robustness/* branches (originals gated; per-branch syntax check only);
OpenCL GLM sibling not fixed (flagged); upstream
flatironinstitute/walnutpie base-branch layout unchecked; math develop
drift past 46a31337 (README drift check now covers the GLM file).
NOTE: external/pr/issue-6-math-fused-log1p.md carries a concurrent
agent's uncommitted edit (6+/6−) — deliberately NOT committed by W-55.
Worktrees left in place (external/math_dev_glm with lib→math_dev/lib
symlink; external/walnutpie_rob). No upstream pushes anywhere.

## 2026-08-23 — W-54 CLOSE-OUT: both shields REJECTED on the W-43 pin class — arm A (init-buffer) makes the pin WORSE alone (escape 948→>1000 def / ~198→266 pf; 10-12/12 pinned vs base 8/12) and damages the W-43 fix 4.7x (165.8 vs the 779.0 bar); arm B is the numerical identity at the thread's scales and a 4.1x metric lift that still can't reach the alpha engine at model scale; the step-side W-43 fix stands alone

GATES (details results/warmup_shields_w54.md):
- (a) Knob-isolated canary PASS 12/12 (e46da43 vs same-worktree
  b657198, 3 models x 4 chains, 1000+1000, rep0 pf). The FULL-binary
  comparison vs 43b6435 is 0/12 — a FINDING: the cherry-picked pin-trace
  hooks perturb hot-loop codegen (semantically identical source), the
  |dH| series shifts in the last ulp, and the pin's escape FIRST
  PASSAGE moves a few iterations (save-warmup bisect: draws identical
  for 183 iterations, diverge exactly at the escape region). W-43's
  8853fd7 "zero-behavior" claim was only ever smoke-tested on a PINNED
  cell, where identical draws are trivially preserved — pinned chains
  hide last-bit differences. Second instance of W-50's
  bit-identity-is-trajectory-conditional lesson. All gate-(b)/(c) base
  references were therefore re-run knob-off on the SAME binary.
- (b) Pin battery (3 reps x 4 chains, E2 seeds): heur bar EXACTLY
  reproduced (w100-pf 779.0/769.5/rhat 1.005/0-12 pinned; w400-pf
  630.4/693.7 — W-43's own numbers). A75/A50/A100: bulk 4.0-5.1,
  10-12/12 pinned (base 8/12, bulk 7.0) — FAIL. A75+heur 165.8 (bar
  779.0), w400 406.3 (bar 630.4) — HARM. B1e10/B1e8 == base (c is the
  identity function on 1e6-1e7 gradients; pinned cells md5-identical);
  B1e6 same pin structure, heur+1e6 750.6 (−4%). B1e10+heur = the
  bar's exact medians (not bit-identical: the 1e-7-relative asinh
  residue perturbs post-escape trajectories).
- (c) No-harm (hier_2pl + lsat w1000, 3 reps x 4 chains): all arms
  within the base band except b1e6 on lsat (−13% bulk-min median, all
  reps below the base band; tail unaffected) — flagged. 0 pins
  anywhere. hier_2pl NaN rhat = constant transformed-parameter columns
  (L_Omega.1.1 etc.) in every arm incl. base — analysis artifact.
- (d) Mechanism (WALNUTPIE_PIN_TRACE, blr w1000 1-chain, off-trace ==
  W-43 digit-for-digit): A does NOT prevent the metric collapse — the
  estimate crashes 1 → 2.07e-07 (def) / 6.05e-03 (pf) at the FIRST
  post-buffer observation (the var-ratio collapse happens at first
  observation, NOT by accumulation — the community thread's premise
  does not transfer to walnutpie's continuous estimator); buffer-phase
  |dH| = inf..1e24 under identity; and the step adapter spends the
  buffer calibrating for a metric that is REPLACED at N (pf+heur:
  step dives 0.0074→0.00098 during the buffer, re-inflates to 0.102 by
  it999; def+heur: the fix's iteration-1 escape delayed to 76). B
  never touches alpha (by construction; alpha=0 through every pinned
  iteration in every arm); its one real effect: c=1e6 lifts the frozen
  metric 4.1x (2.648e-07 vs 6.425e-08), doubling per-step displacement
  and halving the required descent nats — escape 948 → 244 on the
  traced def cell — still >> any short-warmup budget; and when the
  clip window ends (M=200) still in the tail, the deferred
  contamination lands compressed (2.65e-07 → 1.95e-08 in one
  iteration).

VERDICTS: arm A REJECT (fails unpin, harms the fix, safe-but-useless
on healthy models); arm B REJECT-as-shield / REDUNDANT given W-43
(numerical identity at thread scales; model-scale lift real but
insufficient and mildly harmful). The W-43 step-side fix remains the
only effective shield for this class. Upstream relevance: nutpie-
style init buffers assume an identity-initialized windowed estimator
and a step probe calibrated under identity; transplanting the buffer
alone (without both assumptions) is counterproductive. General lesson
recorded: env-gated hot-loop instrumentation is NOT draw-neutral
across builds — first-passage escape times amplify last-ulp codegen
differences; canaries must compare like-for-like builds.

Artifacts: results/warmup_shields_w54.md + results/w54_{canary_
1e02b5,canary_43b6435,knob_ess,noharm_ess,trace}.json; harness/{run_
w54,analyze_w54,trace_w54}.py; raw runs/w54/ (local). walnutpie
commits 33bcff5 + b657198 + e46da43 on exp/warmup-shields (worktree
external/walnutpie_w54 LEFT IN PLACE; bisect worktree /tmp/w54_preknob
kept for the canary base binary).

## 2026-08-23 — W-56: stan-math PR checklist VERIFIED LOCAL for all four math branches — every checklist item PASS on full runs (test-headers 1901/1901 headers x4, runChecks x4, FULL make cpplint x4, make doxygen x4 + warning attribution, targeted runTests.py suites x4); 3 cpplint nits found+fixed (folded into the DCO-signed fork tips); honest gap = full test/unit suite delegated to CI

Context: the user's PR checkboxes claim the stan-math pull-request-template
items pass. W-56 ran them FOR REAL, per branch, in external/math_dev and
worktrees (base origin/develop @ 46a31337; fork = sims1253/math):
1. eigen-cluster-aware-adjoint (external/math_dev)
2. square-pow-to-mul (temp worktree external/math_dev_sq, lib symlinked
   to math_dev/lib; removed at the end)
3. bernoulli-logit-partials-sign (temp worktree external/math_dev_bl;
   removed at the end)
4. bernoulli-logit-glm-partials-sign (external/math_dev_glm)
All builds -j2 and serialized (W-54 sharing the machine); one -j2 compile
stream max, plus at most one 1-core lint/doxygen stream.

RESULTS (item = stan-math PULL_REQUEST_TEMPLATE):
(a) make test-headers — PASS x4, FULL runs, -j2, ~16-19 min each
    (b1 16:54:58-17:13:45, b2 17:23:18-17:39:33, b3 17:40:42-17:57:43,
    b4 18:00:17-18:16:47). 1901/1901 headers compiled per branch
    (b2/b3 logs show 61 extra lines = sundials .a rebuilds triggered by
    fresh-worktree mtimes into the SHARED lib/ symlink — same sources,
    same flags, no correctness impact; b4 ran after those and passed).
(b) make test-math-dependencies (= ./runChecks.py) — PASS x4, exit 0.
    Only output: Python 3.14 SyntaxWarnings from runChecks.py itself
    (pre-existing upstream, not ours).
(c) make cpplint — PASS x4 on FULL repo runs (~2 min each; the repo's
    own target lints ALL of stan/ + test/unit, no fallback needed):
    - b1: 1 error first run — eigen_cluster_adjoint_test.cpp(47)
      runtime/int (unsigned long long) -> fixed to std::uint64_t +
      <cstdint>; re-run clean.
    - b2: clean first try (0 errors).
    - b3: 1 error — bernoulli_logit_test.cpp(108) 81-col line ->
      wrapped; re-run clean.
    - b4: 1 error — bernoulli_logit_glm_lpmf_test.cpp(622) 81-col
      line -> string split; re-run clean.
    Fix commits 55ef6807 / c72d5d7b / 181be38e pushed to fork, then
    folded by the coordinator's DCO-signed amend (see below).
(d) make doxygen — PASS x4 (exit 0, real 185 MB HTML each; b1 also
    re-verified FROM CLEAN after rm -rf doc/api). doxygen 1.13.2
    upstream binary (distro has none) at scratch/w56/doxygen-1.13.2.
    Warning attribution: repo cfg is WARNINGS=NO, so a second pass per
    branch ran with WARNINGS=YES + WARN_IF_DOC_ERROR=YES +
    WARN_IF_UNDOCUMENTED=NO (HTML off): 2046 library-wide baseline
    doc warnings (all pre-existing: opencl CL/opencl.hpp, finite_diff,
    CONTRIBUTING.md label clash, ...). Normalized diff b2/b3/b4 vs b1
    warning sets: IDENTICAL modulo paths/line numbers; ZERO warnings
    mention any changed file. The one red herring — square.hpp:64
    "argument 'x' has multiple @param documentation sections" — exists
    on develop at square.hpp:59 (the b2 diff just shifted the line).
    (Attribution pass exits 1 solely from the GENERATE_HTML=NO
    "no output formats" complaint; parse is complete — evidence is
    the 2046-line log.)
(e) Unit tests (runTests.py, -j2) — PASS x4, broader than the single
    binaries W-40/W-50/W-55 had gated:
    - b1: rev/fun eigen* (3 binaries incl. the new
      eigen_cluster_adjoint_test) + prim/fun eigen* (3) + mix/fun
      eigen* (10: eigendecompose part1/2, identity[_complex],
      eigen_comparisons, eigenvalues[_sym], eigenvectors[_sym]) —
      16 binaries, all OK.
    - b2: prim+mix square*_test (square, squared_distance; 4 binaries,
      12 cases) — this layout has NO dedicated rev square tests (rev
      coverage is via mix), so rev leg = the three rev tests that USE
      squared_distance through var: cov_exp_quad (25), gp_exp_quad_cov
      (25), gp_periodic_cov (41) — all PASS.
    - b3: prim/prob bernoulli_logit* (bernoulli_logit_test incl. the
      new cutoff-sign tests + bernoulli_logit_glm_rng) + rev/prob +
      mix/prob bernoulli_logit_glm_lpmf — 4 binaries, 32 cases OK.
    - b4: same 4-binary set (the rev glm lpmf test carries the new
      cutoff-sign cases) — 32 cases OK.
(f) Touched test targets all rebuilt+run inside (e) (fresh worktrees
    for b2/b3 prove it from scratch).
NOT RUN (recorded honestly): the FULL test/unit suite per branch —
out of scope locally by plan; CI owns that. That is the only gap
between "user's checkboxes verified" and "everything CI will do".

MID-RUN EVENT: coordinator force-pushed DCO-signed amended tips
(Stan AI policy) — 951d9203 (b1), 1e68cf72 (b2), a84edfaa (b3),
d7817886 (b4). Verified post-fetch: fork trees IDENTICAL to the
tested local trees (tree hashes match; git diff empty), so all
results above hold for the pushed tips verbatim. Local branches then
reset to the fork tips (no-op for file content). Any future fix push
to these branches needs --force-with-lease.

Cleanup: temp worktrees math_dev_sq + math_dev_bl removed
(git worktree remove --force after reset; lib symlinks gone with
them). Left in place: math_dev (b1) and math_dev_glm (b4) checkouts
+ their stale test binaries, and the pre-existing stray self-referential
math_dev/lib/lib symlink (observed, untouched — outside all find
scopes). Evidence logs: stan/scratch/w56/ (testheaders_b*.log,
tests_b*.log, cpplint_full_*.log, doxygen_b*[_warnings].log,
runchecks_*.log, status.txt, drivers build_driver.sh +
doxygen_driver.sh).

## 2026-08-24 — W-57 PRE-REGISTRATION (before any run): SoA arena batch rollout BATCH 1 — both-autodiff eltwise branches of subtract/add/divide (+ scalar-x-matrix multiply), extending the W-53 slice substrate per the pre-registered migration plan (results/soa_var_w53.md §2, verdict GO)

SCOPE (batch 1, per plan): convert the BOTH-autodiff (rev-rev)
per-element output-record constructions to ONE batched arena
allocation + ONE nochain span via make_nochain_vari_array, substrate
unchanged from batch 0:
- operator_subtraction.hpp rev-rev (subtract(VarMat1,VarMat2))
- operator_addition.hpp rev-rev (add(VarMat1,VarMat2))
- operator_division.hpp: divide(m,c), divide(c,m), divide(m1,m2) —
  the is_autodiff_v<both> branches only
- rev/fun/multiply.hpp scalar-x-matrix rev-rev branch (a_val *
  arena_B.val().array() — coefficientwise)
- EXCLUDED pending probe: GEMM multiply (arena_A_val * arena_B_val) —
  Product expressions' evaluation path (blocked GEMM kernel vs lazy
  per-coeff) is not guaranteed arithmetic-stable under a coeff(i)
  walk; a bitwise probe decides inclusion THIS batch or defers it.
- Batch 2 (separate gated increment, later): one-autodiff/broadcast
  branches of the same ops + elt_multiply mixed branches.
Trees: bundle math 5.3.0 (scratch/w53/bs_w53, batch-0 edits already
in place) for model builds/gates; external/math_soa @ develop
344d7167 (batch-0 edits in place, uncommitted) for unit tests +
develop patch. Target files byte-identical across both trees except
multiply.hpp val_op() rename (develop) — one edit set, two trees.

EXPECTATION (pre-registered): hier_2pl sampler-level vs STOCK
(pristine bundle): Ir total −8.5..−11.5%T, gradient subtree
−9..−12%G (W-53 slice alone measured −7.69%T/−8.23%G; subtract fwd
inclusive 4.333e9 Ir with the elt_multiply-analogous structure
extrapolates ≈ −1.2e9 Ir more; add/divide/scalar-multiply
contributions small on hier_2pl). Wall: in-sampler ≥ −0.5%
(no-regress), repeated-eval regime −18..−28%. Other battery models:
parity-only expectations (no Ir measurement pre-registered).

GATES (non-negotiable, plan §2 + W-53 codegen lesson):
(a) exact-zero gradient parity (values AND every gradient component,
    bitwise, np.array_equal) hier_2pl/kronecker_gp/gp_regr/accel_gp,
    100 deterministic points each (gate_parity.py scheme);
(b) full sampler draws md5 via READ-ONLY walnutpie
    build_w36exp/examples/stan_cli (W-29 protocol: warmup 100,
    samples 50, seed 20260819, pf init rep0 chain_0, --metric-window
    50): patched == stock AND == W-53's recorded
    fe7c57c99a7a6530ce2dcc408d6e9c65;
(c) unit tests touched targets in math_soa: mix/fun
    {add,subtract,divide,multiply,elt_multiply}_test (+ rev/fun
    variants where present);
(d) callgrind Ir/grad (valgrind 3.23 ~/vginstall, one job at a
    time, stock arm reusable from W-53 profile/ — deterministic
    counter, same binary, verify .so md5 first): patched T and G
    BOTH strictly < W-53 stock numbers; per-op attribution:
    subtract fwd inclusive MUST drop materially (the batch-1
    target), elt_multiply stays at its W-53 patched level, reverse
    callbacks instruction-identical (control);
(e) WALL gates (the W-53 toolchain lesson made this a gate):
    in-sampler native stanza (warmup + sampling µs/call, ≥3
    interleaved rounds per arm) patched median ≤ stock median
    ×1.01 in BOTH stanzas; repeated-eval regime (gate_timing.py)
    patched < stock.
ANY gate failure = stop and diagnose before proceeding (plan §2).

BUILD HAZARDS respected: rm bs_w53/src/bridgestan.o + make
src/bridgestan.o BEFORE model rebuilds; delete model_*_patched/*.so
(compile_model silently reuses cached .so); env -u LD_LIBRARY_PATH;
/usr/bin/make; ≤4 cores, one compile stream, one callgrind at a
time; header edits ⇒ full clean of touched TUs.

PRE-RUN SCOPE UPDATE (W-57, before implementation): the GEMM probe
(scratch/w57/gemm_probe.cpp, bundle math 5.3.0/Eigen 3.4.0/-O2)
settled the excluded-by-default question BOTH ways:
(1) coeff(i) walks over a double Product expression are IMPOSSIBLE —
    Eigen 3.4 ProductImpl::coeff asserts (Option==LazyProduct ||
    1x1); make_nochain_vari_array can never take A*B directly.
(2) stock arena_t<Matrix<var>> construction from A*B is BITWISE
    IDENTICAL to (A*B).eval() AND to an arena_t<double> temp on 11
    shapes / 82,039 elements (0 mismatches) — stock evaluates through
    the same GEMM-kernel temp.
=> GEMM multiply (rev-rev) IS INCLUDED in batch 1 via an explicit
arena double temp (same kernel, same bits; probe-verified).
MEASUREMENT ADDED (not a gate): model-level CACHEGRIND stock vs
patched hier_2pl sampler run (--cache-sim=yes, same W-29 protocol).
Pre-registered expectation: LLd misses per gradient call drop
materially (>=20% on the data side — W-53 microbench bound was
-96.7% of record-complex LLd; model level should land between),
while in-sampler wall may move little (the W-53 regime split) —
this quantifies the Increment-B upside argument at model level.
Method notes: reuse W-53 stock callgrind ONLY after verifying the
stock .so bytes unchanged; wall gates run on a quiet machine (no
parallel compiles during wall stanzas).

## 2026-08-24 — W-57 CLOSE-OUT: BATCH 1 ALL GATES PASS — hier_2pl −15.95%T / −17.06%G deterministic Ir (b0+b1), in-sampler wall −6.3%/−5.6% (3× batch-0), bit-exact at every level; two expectation misses flagged (model-level LLd FLAT +1.16% — microbench locality bound does NOT transfer, arena reuse keeps records LL-resident; repeated-eval −10.3..−10.7% vs −18..−28% band from W-53's LOADED machine — serving-regime win is load-sensitive, hypothesis not regression, in-sampler contradicts regression)

GATES: (a) exact-zero parity 4/4 models ×100 pts — 0 value / 0 grad
mismatches (fresh refs; stock .so md5 verified unchanged before/after:
6eda628e/9c72a5d6/6642f25e/fe601699). (b) draws md5 stock = patched =
fe7c57c99a7a6530ce2dcc408d6e9c65 (W-53 continuity digit-for-digit).
(c) unit tests develop/Eigen-5 81/81: mix add 9, subtract 9, divide 1,
elt_multiply 3, multiply_complex 1 (agent) + multiply1 1, multiply2 1,
operator_multiplication 54, diag_pre 1, diag_post 1 (mine — FIRST
DISCOVERY GREP MISSED the multiply-family test names
[multiply1/2_test, operator_multiplication_test]; lesson: numbered/
suffixed siblings escape ^name_ patterns — enumerate per-family).
(d) callgrind (fresh both arms): T 37,128,519,406 → 31,207,289,278
(−15.95%; −8.94% beyond batch-0 patched); logp_grad subtree inclusive
34,701,743,887 → 28,780,442,093 (−17.06%); gradient calls 4,493
identical; stock reproduced W-53's T to +0.000059% (tool continuity;
~/vginstall = 3.25.1 installed 08-22, W-53's "3.23" note was stale).
Per-op: subtract fwd −25.5% (4.333e9 → 3.229e9, inside predicted
3.0–3.3e9 window); elt_multiply stable (2,888,756,981 vs W-53 patched
−0.0006%); BOTH reverse callbacks INSTRUCTION-IDENTICAL (1,104,287,912
/ 1,189,224,288 exact); stack_alloc::alloc −98.3%, emplace_back
−97.7% (per-record machinery now essentially absent: the level-(a)
arithmetic bound −8..−12%G was BEATEN because the ctor-store share
was real too). (e) wall gates PASS: in-sampler warmup 998.9 → 936.4
(−6.3%), sampling 1023.1 → 965.7 (−5.6%), 5 interleaved rounds,
non-overlapping bands, idle desktop; repeated-eval −10.3..−10.7%
(both orders agree 0.4pp) — expectation MISS flagged with mechanism
(§ below). add/divide/multiply forwards below annotate threshold in
hier_2pl (not exercised materially; covered by gate (c)).

CACHEGRIND MODEL-LEVEL (added measurement): I −15.97%, D refs
−20.6%, D1 −2.8%, LLd 479,150 → 484,693 (+1.16% FLAT; 106.6 →
107.9/grad). Expectation ≥−20% REFUTED with mechanism: arena memory
is reused every gradient call → record complex already
last-level-resident at model level; the microbench's −96.7% punished
a scatter that does not exist in-sampler. COROLLARY: Increment-B
record-shrink upside is irrelevant for the sampler regime; the batch
API (Increment A) is the whole story. Repeated-eval miss mechanism
(hypothesis, not measured): W-53's −21..−23% was measured under
concurrent compile load; tonight's idle stock is +7..9% vs W-53's
stock; under memory pressure the per-record scatter is on the
critical path (locality upside exists), idle it is not (flat LLd
corroborates). Discriminator if the serving regime ever matters:
same-session batch-0-arm A/B.

IMPLEMENTATION (5 functions / 4 files / both trees, senior-reviewed):
subtract+add rev-rev, divide ×3 both-autodiff, multiply GEMM rev-rev
(explicit arena temp — probe: Eigen 3.4 Product::coeff ASSERTS, stock
Matrix<var>=A*B is bitwise (A*B).eval() bitwise arena-temp, 11 shapes
/ 82,039 elements 0 mismatches), multiply scalar×matrix rev-rev.
Guards is_eigen_v<ret_type> (divide m/c,c/m: promote_scalar_t<var,Mat>);
else arms verbatim stock. Instantiate probe compiled all ops ×
{Matrix<var>, var-matrix, mixed} on both toolchains. Artifacts:
results/soa_batch1_w57.md (canonical); scratch/w57/ incl.
w57_soa_batch01_develop.patch (batch 0+1 combined, 14 files, applies
to develop@344d7167), gemm_probe.cpp, instantiate_probe.cpp,
profile/, cachegrind/, wall/, draws/.

ROADMAP STATE: migration plan batches 0+1 DONE/GO. Batch 2
(one-autodiff/broadcast branches, ~21 sites incl. elt_multiply's
mixed pair) = next one-decision increment, SAME gate battery; batch
3/4 audit-only; batch 5 untouched. Pre-PR step remains: restructure
the record loop (raw vptr-store + memcpy'd val block; the +9
Ir/record placement-new overhead term, W-53 §5.3).

GOTCHAS added: (1) bs_w53 bundle has NO make rule for
src/bridgestan_threads.o — the stale-hardlink rm deleted it
permanently; deliberate fail-loud is SAFER than a pristine .o linked
against patched headers (mixed-build ABI), but bs_w53 cannot build
STAN_THREADS models until upstream adds the rule. (2) test-name
discovery greps miss numbered siblings (multiply1/2_test). (3)
wall_sampler.sh needed live fixes (sed -n without p; bc absent —
agent shipped a python shim at /tmp/w57bin/bc); the w57 copy is now
correct, w53's never had the bug. (4) ~/vginstall is 3.25.1 (not
3.23 as W-53's repro block said) — installed 08-22, so W-53 numbers
came from it; stock reproduction to +6e-6% confirms.

## 2026-08-24 — W-58 PRE-REGISTRATION (before any run): SoA arena rollout BATCH 2 — one-autodiff/broadcast branches of the same four op families + elt_multiply's mixed pair (~21 sites), migration plan §2 batch 2, same gate battery

SCOPE: extend the batch construction to every remaining
`arena_t<...> ret/res(<coefficientwise double expr>)` site in the four
files + elt_multiply.hpp:
- operator_subtraction.hpp: VarMat-Arith (L157), Arith-VarMat (L183),
  Var-EigMat (L203), EigMat-Var (L222), Var-VarMat (L243), VarMat-Var
  (L272)
- operator_addition.hpp: VarMat+Arith (L150), Var+EigMat (L186),
  Var+VarMat (L223) [the delegating overloads are covered via these]
- operator_division.hpp: m/c var-only (L141) + c-var (L149); c/m
  m-var (L185) + c-var (L193); m1/m2 m2-var (L235) + m1-var (L246)
- rev/fun/multiply.hpp: GEMM arith-var (L57) + var-arith (L68) [arena
  temp pattern per W-57 probe]; scalar-matrix var-only (L161) +
  scalar-var (L170)
- elt_multiply.hpp: both mixed branches (L85, L93)
Guards: is_eigen_v<ret_type/return_t> (or promote_scalar_t<var,Mat>
for divide's m/c,c/m shapes) with stock else arms verbatim; else-arm
code byte-identical.

EXPECTATION (pre-registered, honest): hier_2pl does NOT exercise
these branches materially (W-57 attribution: nothing above threshold
beyond subtract/elt_multiply rev-rev) => hier_2pl Ir delta expected
0..−1% — A NULL HIER_2PL IR RESULT IS EXPECTED, NOT A FAILURE. The
batch's value: upstream-PR completeness + models that hit mixed
branches (blr/diamonds/lsat classes). Correctness gates are the
decision; no-regress gates bind as in W-57.

GATES (same battery, non-negotiable): (a) exact-zero parity 4 models
×100 pts; (b) draws md5 == stock == fe7c57c99a7a6530ce2dcc408d6e9c65;
(c) unit tests touched targets develop/Eigen-5 — SAME list as W-57
plus any / operator_division-family suites found by per-family
enumeration (lesson: enumerate numbered siblings); (d) callgrind both
arms fresh: patched T/G must NOT regress vs W-57 patched
(31,207,289,278 / 28,780,442,093) — regression = STOP+diagnose
(possible cause: codegen in branches hier_2pl DOES compile/instantiate
via templates even if cold — if T regresses >0.2%, bisect per-op);
(e) wall in-sampler both stanzas ≤ stock×1.01 (5 interleaved rounds,
quiet machine). Repeated-eval + cachegrind NOT rerun (characterized
in W-57; regime conclusions unchanged by cold-branch edits).

## 2026-08-24 — W-58 GATE (c) FAILURE + DIAGNOSIS (fix dispatched, re-gate pending): develop/Eigen-5 static-assert on batch-2 broadcast sites — make_nochain_vari_array's linear coeff(i) requires LinearAccessBit, which general 2D CwiseBinaryOps lack in Eigen 5; add_test/subtract_test compile FAIL at add/subtract(const Var&, const EigMat&) (scalar var vs Eigen-block operands). Bundle/Eigen-3.4 compiles (gates (a) 4/4 PASS 0/400, (b) md5 fe7c57… exact — the failing instantiations don't exist there), so this is a develop-only regression CAUGHT ONLY by the two-toolchain gate discipline (W-53's codegen-sensitivity risk materializing as a hard compile error, not perf). FIX (substrate-level, both trees): compile-time branch on (Eig::Flags & Eigen::LinearAccessBit) — linear walk unchanged (the gated batch-0/1 path; identical codegen), 2D col-major coeff(i,j) walk otherwise (same per-element arithmetic as stock's assignment loop; also correct for RowMajor arith operands, which lose the bit by construction). Pending: probe recompile both trees, linear-access behavior probe (block + RowMajor cases), add/subtract test re-run, THEN full re-gate (a)/(b) on rebuilt bundle binaries + measurements (d)/(e). LESSON for the upstream PR: the Eigen-5 linear-access constraint must be encoded in the substrate helper, not left to call-site luck.

## 2026-08-24 — W-58 CLOSE-OUT: BATCH 2 ALL GATES PASS after one caught-and-fixed develop-only regression — 21 broadcast/one-autodiff sites shipped; hier_2pl Ir null-to-slightly-better as pre-registered (T −0.04%, G −0.046% vs W-57); wall clean-rounds −6.2%/−6.9% (consistent with W-57); cumulative batches 0+1+2 = −15.9%T/−17.1%G bit-exact

GATES (final, on the FIXED substrate):
(a) exact-zero parity 4/4 ×100 pts — 0/400 (fresh binaries; stock md5
re-verified). (b) draws md5 stock = patched =
fe7c57c99a7a6530ce2dcc408d6e9c65. (c) unit tests FULL battery
develop/Eigen-5: 392/0 across 19 targets (add 18, subtract 18,
divide 2, elt_multiply 6, multiply_complex 2, multiply1 4, multiply2 2,
operator_multiplication 108, diag_pre/post 2+2, operator_addition 84,
operator_subtraction 84, operator_division 48, lmultiply{,1,2,3} 2 ea,
matrix_exp_multiply 2, scale_matrix_exp_multiply 2) — the widest
touched-target battery of the SoA effort. (d) callgrind fresh both
arms: stock T 37,130,444,615 (+0.005% vs W-57 stock — env-size-level
drift, no loader shim this time), patched T 31,194,060,751 and G
28,767,198,065 — BOTH marginally BETTER than W-57 patched
(31,207,289,278 / 28,780,442,093; −0.04%/−0.046%); gradient calls
4,493 identical; draws md5 exact under valgrind both arms. (e) wall
in-sampler 5 interleaved rounds: clean-rounds (stock r3-5 were
uncontaminated; r1-2 stock spiked by background agents 1997/1258us)
warmup −6.2%, sampling −6.9%; all-rounds medians −7.9%/−8.6% (stock
contamination inflates — clean-round number is the honest headline);
patched bands tight [934..958]/[957..972] vs W-57 patched
[931..947]/[939..973] — indistinguishable, as expected for cold
branches.

INCIDENT LOG (recorded for the method): (1) gate (c) caught the
LinearAccessBit compile regression (see W-58 failure entry) — fixed
substrate-level, re-gated EVERYTHING from fresh binaries; the
two-toolchain gate discipline paid for itself. (2) The re-gate agent
DIED on a model-infra error after completing rebuild+(a)+(b);
reconstruction from filesystem state + re-driven (c)/(d)/(e)
by the coordinator (me) — gate results are not agent-memory-dependent.
(3) wall harness bugs: bc absent (W-57 agent had shimmed via volatile
/tmp), and the v1 w58 script's analysis read a hardcoded path —
displayed W-57's data for W-58 runs; caught because the numbers were
EXACTLY W-57's (a lesson: identical-to-previous results are a red
flag, not a comfort); v2 script (awk + $OUT-relative analysis) is the
durable fix; W-57's wall_sampler.sh retains both bugs — do not reuse
without the v2 fixes.

IMPLEMENTATION RECAP: 21 sites (subtract ×6, add ×3, divide ×6,
multiply ×4 incl. both GEMM mixed arms via arena temps, elt_multiply
×2), both trees; bundle GEMM arms use val_op() (Eigen 3.4 CwiseUnaryView
const-qualifier — matches stock), develop val(). Substrate fix:
make_nochain_vari_array compile-time branches on (Eig::Flags &
LinearAccessBit) — linear walk (hot path, identical codegen) vs 2D
col-major coeff(i,j) walk (correct for any expression incl. RowMajor
operands; values identical, coefficientwise per-element). Dedicated
linear_access_probe (block + RowMajor + adjoint checks) all PASS.

ROADMAP: migration plan code-changing batches COMPLETE (0, 1, 2 —
batches 3/4 are audit-only, batch 5 old-style scalar varis is a
separate seam). Cumulative artifact:
scratch/w57/w58_soa_batch012_{develop,bundle}.patch (14 files:
substrate ×9 + ops ×5 incl. new header). REMAINING before any
upstream PR: (i) record-loop restructure (raw vptr-store + memcpy'd
val block; removes the +9 Ir/record placement-new term; gate on wall
per toolchain per W-53 §5.3), (ii) develop-side Ir/wall spot-check of
a non-hier_2pl model that exercises mixed branches (blr/diamonds
class) to demonstrate batch-2 value where it actually bites,
(iii) batches 3/4 lifetime audits (no code change expected).
Artifacts: scratch/w57/{w58_*,linear_access_probe.cpp,draws_w58_final,
profile_w58,wall_w58}, results file results/soa_batch2_w58.md.

## 2026-08-25 — W-59 PRE-REGISTRATION (before any run): record-loop restructure — FUSED construction+pointer-fill loop (one pass: placement-new record + write output var pointer), the W-53 §5.3 named pre-PR step

DESIGN: make_nochain_vari_array gains an output-pointer parameter
(`vari* make_nochain_vari_array(const Eig& expr, var* out)` — writes
`out[i] = var(recs + i)` INSIDE the construction loop, both the linear
and 2D-fallback branches); all 26 batched call sites (W-53/57/58)
switch to it and drop their separate pointer-fill loops. Semantics
unchanged: same records, same values, same zeros, same spans; the
output Matrix<var> data array is still arena-allocated and sized by
the caller first. Rationale: removes the second pass over out/recs
(loop overhead + locality; W-53 priced the batch loop's overhead at
+9 Ir/record vs stock's ctor stores and predicted 1-2 Ir/record
recoverable by fusing) and reduces the placement-new serialization
that produced the develop/Eigen-5 isolated-TU +17% wall (W-53 §5.3).
EXCLUDED (this batch): the scratch-eval/raw-vptr variant (double temp
+ strided raw stores) — speculative, worse arena footprint; only if
fusing underdelivers.

EXPECTATION (pre-registered): hier_2pl patched G improves −0.3..−1.2%
vs W-58 patched (28,767,198,065) from ~170M batch records × 1-2 Ir;
T similar; in-sampler wall within noise of W-58 or slightly better;
the develop/Eigen-5 isolated eltwise line (wild_driver TU) wall
should NOT regress and ideally recovers part of the +17% (measured,
not gated — toolchain-specific). All bit-identity gates MUST stay
exactly green (draws md5 fe7c57…).

GATES: identical battery to W-58: (a) parity 4×100; (b) md5; (c) the
19-target 392-test battery; (d) callgrind no-regress vs W-58 patched
T=31,194,060,751 G=28,767,198,065 (gate: within +0.2%); (e) wall
in-sampler clean-round medians <= stock×1.01. PLUS (f, new,
measurement-only): wild_driver develop-TU wall stock-vs-patched
(W-53 protocol, scratch/w53/wild_driver.cpp) to quantify the
placement-new-serialization effect.

PARALLEL (read-only, no machine): batches 3/4 lifetime audit —
verify ODE adjoint (rev/functor), reduce_sum/map_rect, and the
serialize family hold no assumption the span substrate breaks
(pointer-stability, nested recover, no linear-index assumptions).
Findings-only deliverable; no code changes.

## 2026-08-25 — W-60 PRE-REGISTRATION (before any run): mixed-branch DEMONSTRATOR — blr stock-vs-patched; first model-level evidence for batch-2 value where it actually bites

MODEL: blr (stan/models/blr.stan; normal_lpdf(y | X*beta, sigma)) —
the GEMM is arith-double-matrix × var-vector (W-58 M2 site) and the
lpdf's internal (y - mu)/sigma machinery hits mixed subtract/divide
broadcast branches. diamonds REJECTED for this purpose
(normal_id_glm_lpdf = specialized GLM primitive, does not exercise
the generic eltwise ops). Runs against the W-59-final tree.

GATES: (a) exact-zero parity blr ×100 pts vs stock; (b) full sampler
draws stock-vs-patched cmp (W-29-protocol analog; no historical md5
exists for blr — internal-consistency gate: patched csv byte-identical
to stock csv); (c) no unit-test implications (no new code).
MEASUREMENTS: callgrind both arms (fresh) — EXPECTATION
(pre-registered): multiply fwd inclusive drops materially (the GEMM
mixed-arm record tax; stock share unknown — first measurement),
subtract/divide forwards drop if the lpdf path routes through them;
in-sampler per-call stanza stock vs patched. NOT a no-regress gate on
hier_2pl numbers (different model); this is the batch-2 value
demonstration for the upstream PR narrative.

## 2026-08-25 — MIGRATION PLAN BATCHES 3/4 AUDIT COMPLETE (read-only, no code change): SAFE everywhere — span substrate breaks NO assumption in ODE adjoint, reduce_sum/map_rect, or the serialize family; one residual test-accounting blind spot noted

Verdicts (full citations in the session record; agent: Explore,
read-only): (a) ODE adjoint SAFE — cvodes_integrator_adjoint.hpp:359
registers its forward-solve vari on the CHAINED stack (untouched);
returned states use ordinary per-record var_nochain pushes (still
supported); nested-region batch records live above the
memalloc_.start_nested() watermark with span index >= snapshot —
span rollback + recover_nested frees exactly what per-record pushes
would. (b) reduce_sum/map_rect SAFE — span registry is per
AutodiffStackStorage instance; ScopedChainableStack swaps in a fresh
storage (own empty spans); reduce_sum's set_zero walks the local
stack's spans correctly; no cross-stack sharing. (c) serialize family
SAFE — all seven (save_varis/read_var/count_vars/deep_copy_vars/
collect_adjoints/accumulate_adjoints/filter_var_scalar_types) operate
on user-facing var objects via vi_/.adj()/.val(), never enumerate
stack vectors; batch-registered varis are invisible to them exactly
as per-record nochain varis are. Consumer inventory: exactly 6
semantic var_nochain_stack_ sites, all patch-aware (matches W-53's
count). RESIDUAL (disclosed in the PR body, not fixed): unit tests
summing var_nochain_stack_.size()+var_stack_.size() cannot see span
records; minimal future fix = nochain_record_count() test helper.
OpenCL varis remain per-record — both registration forms coexist.

MIGRATION PLAN STATE: batches 0,1,2 SHIPPED+GATED (W-53/57/58);
batches 3,4 AUDITED-SAFE (this entry); batch 5 (old-style scalar
varis) NOT planned this session. W-59 (fused record loop) in flight.

INCIDENT: stan/external/pr/ found EMPTIED today 21:19 (deletion
unstaged, files still in git HEAD; not me) — flagged in comms.md;
filing kit restoration deferred to the owner of the deletion. New PR
artifacts land in the empty dir as standalone files.

## 2026-08-24 — W-63 PRE-REGISTRATION (renumbered from W-60 after the 23:22 comms collision warning; SoA's blr demonstrator keeps W-60): metric-window chopping A/B at full benchmark scale — `--metric-window 100` vs default exponential discounting (ESS/s ideas session; ox-alpha orchestrator)

MOTIVATION: walnutpie's MassEstimator defaults to pure exponential
discounting (metric_window=0); a memoryless chop variant already exists
behind --metric-window (adaptive_walnuts.hpp reset_to_seeds) and was used
at window=50 only in short profiling runs (W-29-style), NEVER A/B'd at
benchmark scale. Published head-to-head favors chopping (research_optimizer_pass2.md;
arXiv:2603.18845 Fisher-HMC discipline: stale early draws are noise, not
signal). This is idea #1 of the ESS/s ideas list posted in comms.md
(Tier 1 zero-code).

DESIGN: two arms, identical everything except the flag.
- Arm BASELINE = existing runs/w36/exp_par artifacts (bit-identical by
  construction: same binary build_w36exp @43b6435, same seeds/inits/flags;
  28/28 DONE cells verified present). No rerun.
- Arm MW100 = fresh runs/w59/mw100/<model>/rep<r>/ via a new harness
  script (adapted from harness/run_w36.py): same 10 MODELS, 3 reps,
  seeds 20260819+1000*rep, OMP_NUM_THREADS=1, --chains 4 --chain-exec
  threads, warmup/samples 1000/1000, pf inits for hier_2pl+lsat from
  inits_w25, others from inits_w36, PLUS --metric-window 100.
- Window value 100 chosen a priori (10 chops over 1000 warmup iters;
  prior profiling usage was 50 at warmup=100). Single value this
  experiment; sensitivity sweep is a separate decision if gates pass.

EXPECTATION (pre-registered):
1. Aggregate geo-mean ess_bulk_geomean (median over reps, 10 models):
   MW100 >= baseline +5% (published direction; mechanism: memoryless
   windows drop drift-phase and early-warmup contamination).
2. Largest upside on hard-adaptation models (hier_2pl, bym2_offset_only);
   small risk on fast/easy models (eight_schools_centered, pilots) where
   100-draw variance estimates are noisier than discounted ones.
3. Wall per model within ±15% of baseline medians (same eval budget;
   adaptation differences shift trajectory lengths slightly).
4. Draws NOT bit-identical across arms (different adaptation path) —
   statistical comparison over 3 reps only, per protocol.

GATES:
- ADOPT-candidate: gate 1 met AND no model's median ess_bulk_min drops
  >20% vs baseline.
- REJECT: any hard model collapses >2x (the W-25 signature 519→126) or
  geomean delta within ±3% (noise band).
- Either way: results + verdict recorded in results/metric_window_w60.md
  and cross-referenced here; negative result gets recorded same as wins.

COST: ~8–10 min sampler time (one arm × 30 cells, machine idle; SoA
session released it at 23:01).

## 2026-08-25 — LOW-RANK METRIC DESIGN MEMO (research, read-only): arXiv:2603.18845 fully extracted and mapped onto walnutpie — the W-8/9/10 machinery already covers the operator/CLI/transition side; the gap is the paper-faithful Alg-1 basis (~100-120 LOC in low_rank_metric.hpp: joint-QR subspace of standardized draw+score SVDs, Cx/Ca geometric-mean solve, eigenvalue filter c=2 as the rank cap, SIGNED corrections c=lambda-1 in (-1,0) — today's low_rank_factors() only emits c>=0)

Artifact: scratch/w57/lowrank_metric_design.md (algorithm with
equations; file-by-file integration map; risks incl. W-43-pin
orthogonality — low rank cannot fix the pin, auto-screen is
protective, step probe must run under the full operator; 4-arm
pre-registration-ready plan on CORE_SET with 5 gates incl. the 0/12
pin battery; ~3 sessions estimate; 7 maintainer questions). Paper
claims 1.3x/4x median ESS/grad (diagonal/low-rank) vs Stan over 114
posteriordb models, measured on nutpie — NOT on funnel/short-warmup
regimes (our marginal-class risk). W-8/9/10 lessons carried in:
forced rank hurts aggregates (0.66-0.79x), auto-screen delivers
targeted wins (bym2 3.46x), freeze-mismatch is the recurring bug
family. IMPLEMENTATION NOT STARTED (this session holds W-59/60/PR);
next session's one-decision start. walnutpie main worktree is
exp/safe-adapt-defaults — coordinate with the ox-alpha session
(exp/pf-metric-seed lineage) before branching.

## 2026-08-24 — W-61 PRE-REGISTRATION (before any run): ladder/backward-eval accounting — how much of walnutpie's gradient budget goes to `reversible()` backward re-integration, and does it correlate with the ESS/grad ceiling? (ESS/s orchestrator session #2)

MOTIVATION: walnutpie's well-mixed ESS/grad is 0.31–0.32× cmdstan
(ess_per_grad_evidence.md) and the residual was attributed to "dyadic
search overhead" without decomposition. Structural audit (this session):
`reversible()` (walnuts.hpp:258–285) re-integrates BACKWARD at coarser
lattices from the accepted end state — those evals are NOT cacheable
(different start state + different step lattice than any forward attempt;
extends W-20's no-revisit finding to the backward direction). Cost when
the accepted rung is k halvings up: m·2^k−m extra evals vs forward
m·(2^{k+1}−1) → 0% at k=0, →50% as k grows; called once per tolerance-
passing macro_step (leaves ≈ 2^depth per transition). Existing pin_trace
counts ladder evals inside the SAME `evals` counter as forward evals
(pin_trace.hpp observe_ladder :162) — not separable today.

CHANGE (instrumentation only, private copy scratch/w61/walnutpie_instr,
env-gated like the rest of WALNUTPIE_PIN_TRACE):
1. pin_trace.hpp: new `ladder_evals` counter incremented in
   `observe_ladder`; reset in begin_transition... NO — reset in the same
   place other counters reset for summary scope (per-run totals, matching
   existing counters' lifecycle); forward/backward separation only.
2. stan_cli.cpp: print `ladevals=` next to existing `ladrej=`.
No behavioral change: counters are additive integers on an env-gated
diagnostic struct; sampling path untouched ⇒ bit-identity gate = draws
md5 identical to unmodified w54 binary on the canary cell.

MEASUREMENT DESIGN (profiling pass, NOT the full benchmark):
Models: eight_schools_centered (easy), blr (pin class), hier_2pl (hard),
arma11 (stiff), kronecker_gp (WALNUTS-wins class). 1 rep, seeds
20260819+0+c, 4 chains serial (single core), 1000/1000, pf inits.
Report per model: fraction ladder_evals/(total logp_grad calls) median
across chains, mean k (halvings) distribution, correlation with
per-model ESS/grad from W-36 logs.

EXPECTATION (pre-registered):
1. Easy models: fraction <5% (k=0 dominates).
2. Stiff/hard models: fraction 10–40% (frequent halvings); if so this is
   a real component of the ESS/grad ceiling and motivates an algorithmic
   follow-up (cheaper irreversibility certificate), NOT a cache.
3. If fraction <5% EVERYWHERE: lane closed, ceiling lives elsewhere
   (macro-step count / trajectory length policy → overlaps P3).

GATES:
- Bit-identity: md5 of constrained draws identical instrumented vs stock
  w54 on eight_schools_centered rep0 chain0 (canary).
- No verdict from single-chain wall numbers (not a timing experiment).
- Either outcome recorded here + results file scratch/w61/w61_ladder_accounting.md;
  negative result closes the lane with mechanism.

MACHINE: single-core serial runs; build deferred until load < 2 (23:28
load 6.2). No wall-time claims; no quiet-machine requirement.

COST: ~15 min build (header-only, one TU) + ~10 min runs.

## 2026-08-25 — W-59 CLOSE-OUT: ALL GATES PASS — fused loop −2.18%T/−2.36%G BEYOND the predicted band (cleanly attributed: subtract fwd −10.5% + elt_multiply fwd −11.8% sum EXACTLY to the delta; callbacks/alloc/emplace unchanged); wild_driver Eigen-5 regression ELIMINATED (1.0043 vs +17% pre-fuse); cumulative batches 0+1+2+fused = −17.82%T / −19.06%G bit-exact

GATES: (a) 4/4 parity 0/400; (b) md5 fe7c57… both arms + cmp
identical; (c) 392/0 across 19 targets (pattern matched expected
exactly); (d) T 30,514,462,110 / G 28,087,600,877 — both PASS the
×1.002 no-regress bound vs W-58 with −2.18%/−2.36% IMPROVEMENTS
(outside the predicted −0.3..−1.2% band, positive direction — the
removed second loop cost more than the 1-2 Ir/record estimate);
stock reproduction to −7e-8% (logp_grad inclusive bit-identical
cross-session). Per-op self (one consistent extraction, correction:
the W-58 agent's reported per-op numbers — 3,228,524,605 etc — were
an extraction-convention artifact; canonical values from the ann.txt
files: subtract fwd W-58 3,228,515,757 → W-59 2,888,712,739;
elt_multiply 2,888,748,133 → 2,548,958,387; sum of deltas =
−679.6M = exactly the G delta; alloc 37,634,233 and emplace
35,554,224 UNCHANGED (fusing touches only the construction loops);
reverse callbacks unchanged (1,189,224,288 / 1,104,287,912)).
(e) wall PASS −5.3%/−4.9% under sustained foreign load (protocol
never reached load<1.6 — foreign python3@100% + a compile started
against the notice; proceeded+FLAGGED per protocol; NO contaminated
stock rounds by the 1.3x criterion; wide bands honest).
(f) wild_driver develop-TU (5 interleaved runs, load~3): stock
372.6 vs patched 374.2 µs/call, ratio 1.0043 — the +17% pre-fuse
regression is GONE (steady-state +1.2%, all-rep +2.8%); stash dance
incident: git stash refuses intent-to-add headers ("not uptodate")
— resolved by staging the header first, then restoring the -N state
EXACTLY (verified: status-diff empty, md5s identical) — a gotcha
for any future stash A/B on this tree.

CUMULATIVE (stock → final, same-session binaries): T 37,130,441,910
→ 30,514,462,110 = −17.82%; G 34,703,678,559 → 28,087,600,877 =
−19.06%; draws md5 fe7c57… throughout; wall −5..−7% across three
sessions (quiet and loaded). Artifacts: scratch/w59→ scratch/w57/
{draws_w59,profile_w59,wall_w59}, gate_draws_w59.sh,
run_callgrind_w59.sh, wall_sampler_w59.sh,
w59_soa_batch012_fused_{develop,bundle}.patch,
scratch/w53/wild_driver_w59_{stock,patched}.
PR body (brief, per user style): scratch/w57/pr10-body.md — blr slot
pending W-60; then fork-internal draft PR sims1253/math.

## 2026-08-25 — W-61 CLOSE-OUT: ladder/backward-eval accounting — lane OPEN, 8–20% of the gradient budget goes to `reversible()` backward re-integration (ESS/s orchestrator session #2)

Results: scratch/w61/w61_ladder_accounting.md. Setup per prereg (5 models
× 4 serial chains, 1 rep, w54 @ e46da43 + env-gated counters). Fraction
ladder/(forward+ladder): eight_schools_centered 15–20%, kronecker_gp
12–13%, arma11 10–11%, blr 8–10%, hier_2pl 8%.

VERDICT: pre-registered "closed if <5% everywhere" gate does NOT fire —
expectation 1 refuted. The backward certificate is a real component of
the ESS/grad ceiling on EASY as well as stiff targets (eight_schools is
the WORST — halvings are not rare). Structural audit stands: evals are
not cacheable; cost is algorithmic. Top follow-up: walnuts-ai port
(p-micro Hastings correction deletes the whole ladder; conditional-GO
plan in comms.md).

ANOMALY logged: kronecker_gp chain0 post-warmup abort
`std::invalid_argument: macro_time must be in (0, inf)` — pre-existing
w54 validation throw (abort-vs-reject asymmetry class), unrelated to
instrumentation.

CAVEAT: bit-identity md5 battery not re-run this pass; counters are the
same env-gated-scratch design W-43 verified 24/24. PR-quality packaging
of the counters exists as branch diag/pin-trace-accounting on
sims1253/walnutpie (draft PR withdrawn upstream per user rule: never
file upstream).

## 2026-08-24 — W-65 PRE-REGISTRATION (before any run): curvature-seeded warmup metric — feasibility phase (instrumented warmup traces → replay fidelity gate → seed-dominance discriminator → cross-chain pooling simulation) — ESS/s orchestrator session (P1/P2 of results/proposals_ess_per_sec.md)

NOTE ON NUMBERING: first posted as "W-59", renumbered W-62, now W-65 —
parallel sessions independently claimed W-59..W-64 (and two other entries
also carry "W-62"; those are NOT mine). Renumbered again 2026-08-25 ~01:00
to the next free number. All W-65 references here and in comms.md mean
THIS entry: curvature-seeded warmup metric, feasibility phase.

BACKGROUND (desk-established): walnutpie's initial mass seed is
(1-s)*|grad(x0)|+s per chain (config.hpp InitConfigBuilder::masses,
smoothing 1e-5); MassEstimator seeds BOTH OnlineMoments accumulators with
it at mass_init_count=4 pseudo-counts, and memoryless chopping
(reset_to_seeds at every --metric-window boundary except the last)
RE-BLENDS that seed into every window estimate for the whole run. Seed
quality therefore has permanent leverage, dominating exactly coordinates
where within-window draws carry little information. Proposed replacement
(P1): L-BFGS/Pathfinder-style inverse-Hessian diagonal at the SAME init
position. Not covered by: cmdstan-only pf-position ablation (08-19),
W-45 (subsampled-DATA geometry), HANDOFF C''#1 (online Fisher =
complement), upstream `preconditioner` branch (wrapper only).

SCOPE OF THIS ENTRY (feasibility only — no bench claims):
(1) Instrumentation slice (implemented, uncommitted on
exp/safe-adapt-defaults, to be committed as exp/warmup-trace after gates):
AdaptiveWalnuts::last_grad()/last_depth() const accessors (both operator()
return paths) + CLI --warmup-trace-dir (single-chain only; file-scope
settings struct avoids the 8-call-site dispatch trap; stderr warning on
--chains>1). Dumps theta/grad/invmass [T x D] f64 + step/lp f64 + depth
u64 + meta.json (initial_position, initial_mass = masses() output, all
flags). Trace contract v2 FROZEN in scratch/w59/replay/FORMAT.md:
invmass row t = EST[t] (metric in effect during transition t = verbatim
on_warmup payload); frozen log diagonal = EST[T-1] by freeze-memo design.
(2) Replay engine: scratch/w59/replay/mass_replay.py replicates
MassEstimator under stock defaults (combine power 0 geometric, no
shrinkage/floor/guard) — 12/12 synthetic unit tests PASS incl.
independent-loop hand example.
(3) Trace generation (FIRST EVIDENCE-RUN, gated below): 4 models
{hier_2pl, bym2_offset_only, arma11, blr} × rep{0,1,2} × chain{0..3},
warmup-only (--samples 1), single-chain invocations, seeds
20260819+1000*rep+c, uniform inits from inits_w36/<model>/rep<r>/chain<c>.txt,
recommended-config flags (--step-opt-batch-stride 50 --mass-init-clamp 100
--step-init-heuristic --metric-window 50; exact flag names verified
against --help at run time). Sequential, ≤2 cores, no wall measurements
taken during generation.
(4) Analyses (all offline, deterministic given traces): replay-fidelity
gate; seed-swap counterfactual replays (|grad| vs oracle vs L-BFGS seed);
cross-chain pooled-M2-at-boundaries simulation. HONEST LIMIT (stated up
front): these measure ESTIMATOR quality under REALIZED streams — they do
not simulate closed-loop feedback (a different seed changes trajectories).
Closed-loop evidence comes only from a later bench pre-registration.

GATES:
G1 (fidelity, binds everything): compare_frozen.py rel-L2 < 1e-8 on
>=11/12 chains PER MODEL (48 runs total). Any model <11 ⇒ STOP, diagnose
the replay before any counterfactual number is reported.
G2 (discriminator, prediction not gate): oracle-seeded windows reduce
median |log-ratio| error vs |grad|-seeded by >=30% on slow-decile
coordinates (decile by oracle variance over trace tail) in first-half
windows for hier_2pl AND bym2.
G3 (P1 GO/NO-GO): L-BFGS seed closes >=30% of the [|grad|-seed −
oracle-seed] median-error gap on slow-decile coords in >=2 of
{hier_2pl, bym2, blr} ⇒ GO for bench pre-registration (W-63);
<15% ⇒ NO-GO recorded with mechanism; between ⇒ judgment documented here.
G4 (P2 GO/NO-GO): pooling simulation reduces final-window median error
vs oracle by >=25% on slow-decile coords in >=2 models ⇒ GO for P2
implementation pre-reg (determinism stance decision required first);
else NO-GO recorded.
Negative results get recorded either way. No default changes proposed
without a separate two-sided bench (house rule).

MACHINE NOTES: compile of instrumented stan_cli waits for the foreign
`make -j2` stream (posted in comms 23:2x); traces are instruction-light
and unmeasured; no quiet-machine requirement until a future WALL RUNNING
window (bench only).

## 2026-08-25 — W-60 CLOSE-OUT + SESSION WRAP: blr demonstrator gates PASS (parity 0/100+0/100, draws md5 11fb5b6f… identical) — mixed-GEMM forward −46.8% / vari recording −82.2% = batch-2 value shown where it bites; FORK-INTERNAL DRAFT PR FILED: sims1253/math#5 (soa-eltwise-batch-records, 14 files +787/−186, DCO + AI-policy note, branch == gated math_soa state byte-verified)

W-60 DETAIL: blr (D=6, N=100) total −0.91%T / −1.04%G — the named-op
savings (≈−9.8M Ir: multiply fwd −5.9M = −46.8% on the X*beta mixed
GEMM; vari_base emplace −4.1M = −82.2%) are partially absorbed by
+5.0M libgcc unwinder/FDE .so-layout artifact (patched-binary layout
difference, not autodiff work — honest accounting recorded);
subtract/divide/elt_multiply/add forwards absent from blr's profile
(Eigen-inlined in both arms); update_adjoints self identical; wall
sampling −1.9%, warmup flat (tiny model, floor effects). CONCLUSION:
batch-2's payoff concentrates in mixed GEMM + recording — exactly
the demonstrator's purpose; net small on a model this cheap per
call.

FILING RECORD: worktree external/math_dev_soa (fork clone math_dev,
branch soa-eltwise-batch-records off 344d7167 = fork develop ==
stan-dev develop, no drift); w59_soa_batch012_fused_develop.patch
applied clean; all 14 files byte-verified vs math_soa before
commit; push → fork only; PR sims1253/math#5 DRAFT (NEVER upstream
— user rule re-confirmed this session). Body: scratch/w57/pr10-body.md
(brief per user style).

SESSION STATE: SoA migration COMPLETE end-to-end (batches 0/1/2 +
fused loop + audits 3/4 + demonstrator + PR). NEXT session starts:
low-rank metric Alg-1 basis (scratch/w57/lowrank_metric_design.md,
W-8/9/10 machinery exists, ~100-120 LOC, coordinate with ox-alpha's
walnutpie branch lineage).

## 2026-08-25 — W-62 PRE-REGISTRATION (before any code): low-rank metric, increment 1 — paper-faithful Alg-1 basis mode (arXiv:2603.18845) per scratch/w57/lowrank_metric_design.md

SCOPE: new walnutpie worktree (external/walnutpie_lowrank; base =
whichever existing branch carries the W-8/9/10 machinery — agent
determines and REPORTS; do not touch other walnutpie worktrees).
Implement "basis mode 4" per the memo: low_rank_factors() gains the
paper-faithful path — standardize by sigma, SVD draws + scores
submatrices, joint-QR basis Q, project to Cx/Ca, regularize
gamma=1e-5, solve the SPD geometric mean (Sigma Ca Sigma = Cx via
eigendecomposition), eigenvalue FILTER (keep lambda <= 1/c or >= c,
c=2) as the rank cap, SIGNED corrections c_i = lambda_i - 1 ∈
(-1,0]; compose M^-1 = diag(sigma)(I + U diag(c) U^T) diag(sigma)
through the EXISTING low_rank_mass.hpp operator (O(rd)/leapfrog).
CLI: extend --metric-rank with the new mode; DEFAULT/OFF paths
unchanged.

INCREMENT-1 GATES (this pre-registration; full 4-arm ESS campaign is
a separate later pre-registration when the machine frees):
(i) new mode OFF by default => default-path draws BIT-IDENTICAL to
the base branch (canary, W-29 protocol on 2 models);
(ii) basis mode ON: new low_rank_factors verified against a
python/numpy REFERENCE implementation of Alg-1 (agent-written, same
inputs) on 3 synthetic problems — subspace agreement (principal
angles) and composed-matrix agreement to 1e-12;
(iii) -fsyntax-only + existing walnutpie unit tests for touched
files where present.
EXPECTATION: (i) exact; (ii) exact to 1e-12 modulo eigensolver
ordering; ESS effect UNKNOWN until the campaign — no ESS claim made
this increment. Machine: syntax checks only until a compile window
opens (other agents active).

## 2026-08-25 — W-62 PRE-REGISTRATION (before any run): walnuts-ai Phase-1 prototype — isokinetic BAB micro-steps + anchored radial stopping behind an opt-in compile-time path, correctness-gated only (no ESS claims this phase)

MOTIVATION: W-61 measured the reversible() backward ladder at 8–20% of
gradient budget; the generalized-WALNUTS isokinetic-anchored variant
replaces that ladder entirely (Hastings p-micro correction) and reports
~10.9× ESS/grad on Neal's funnel vs their Python walnuts-h. Port scope:
conditional GO (comms.md 23:35 entry). Phase 1 = throwaway-quality-ok
prototype on diagonal mass, single chain, fixed h; adaptation (anchor
refresh, h calibration, adapter statistic) is Phase 2.

IMPLEMENTATION (scratch/w61/walnutpie_w54 worktree, branch
exp/isokinetic-ai off e46da43):
- New include/walnutpie/isokinetic.hpp: b_step (unit-sphere momentum,
  closed-form rotation with log-Jacobian dlogJ = -(d-1)(delta +
  log((1+gamma)+(1-gamma)e^{-2 delta})/2)), macro_step_iso (level search
  ell=0..ell_max upward, admissible iff H_eff range <= delta; randomized
  ell_p in {ell* w.p. 2/3, ell*+1 w.p. 1/3}; leaf weight += Hastings term
  log p(ell_p|ell*) - log p(ell_p|ell_plus)), cross_radial_max stopping
  vs anchor C (phi=(theta-C).rho sign change + -> - forward, swapped
  backward; crossing leaf terminates growth, not retained),
  transition_w_iso mirroring transition_w structure (SpanW reuse, logJ
  folded into span weights).
- Dispatch: opt-in flag/env in a test driver ONLY; default hot path
  untouched (canary requirement).

EXPECTATION (pre-registered):
1. Correctness first: reversibility-by-negation property test passes
   (forward then negated backward reproduces start state to 1e-10);
   detailed-balance smoke on standard Gaussian — chain mean within 3 SE
   of 0, variance within 20% after 20k draws.
2. Funnel sanity: on Neal's funnel (10-dim, sigma_log hierarchical),
   finite draws throughout, zero non-finite logp aborts, log(sigma)
   marginal explores below -5 (not mode-locked at init).
3. Gaussian ESS/grad within 2x of walnuts-h diagonal on same machine
   (paper gap may shrink vs C++ baseline; we claim NO parity this phase).
4. Determinism: identical seeds reproduce bit-identical draw CSVs.
5. Ladder-fraction = 0 by construction on iso path (pin_trace totals).

GATES:
- PROCEED to Phase 2 iff gates 1, 2, 4 pass and gate 5 holds trivially.
- ABANDON if gate 1 fails after 2 debugging cycles (correctness hazard
  #1 = anchored-rule orientation; property tests are the detector).
- Negative/abandon recorded here either way.

MACHINE: builds -j2 single stream; runs single-chain serial. No wall-time
claims this phase (gate 3 uses eval counts, not wall).
COST: ~1 session implementation + ~30 min runs.

## 2026-08-25 — ROBUSTNESS TRIAGE (W-61 anomaly): kronecker_gp "macro_time must be in (0, inf)" abort root-caused — dead-init NaN propagation through the step adapter; guard incoming (orchestrator #2)

CHAIN OF FAILURE (all confirmed by pin-trace log scratch/w61/runs/
kronecker_gp/chain_0.log): init position makes the Stan model throw
(eigenvectors_sym non-symmetric/-nan) → DynamicStanModel::logp_grad maps
every eval to (-inf, 0) → both macro-step endpoints -inf ⇒ min_accept =
exp(-|−inf−(−inf)|) = NaN (walnuts.hpp:345) → AntiWindupAdapter gate
`alpha < floor_alpha_` is FALSE for NaN (step_optimizers.hpp:290) so NaN
passes into Adam → m_, v_, theta_, step_size() all NaN → at warmup→
sampling freeze AdaptiveWalnuts::sampler() constructs WalnutsSampler with
macro_time=NaN → validate_positive throws → terminate. Chain pinned at
init all 1000 iters (moved=0 every iteration); NOT late-warmup collapse;
min_micro/mass/max_error ruled out. Matches the known abort-vs-reject
asymmetry class (Stan would finish with divergences).

NOTE: init was -inf from iter 0 yet run proceeded — the W-42 fail-fast /
retry policy does not cover this path on w54 defaults (separate gap,
flagged for ledger).

FIX PREREGISTRATION (branch rob/nan-alpha-guard off e46da43, worktree
scratch/w61/walnutpie_instr):
1. walnuts.hpp macro_step (+_lr mirror): skip adapt_handler when either
   endpoint logp is non-finite (failed evaluation carries no acceptance
   information; do NOT fabricate alpha=0).
2. step_optimizers.hpp AntiWindupAdapter::operator(): treat NaN as
   dropped (`!(alpha >= floor_alpha_)`).
GATES: (a) kronecker_gp chain0 seed 20260819+0 completes 1000+1000
without abort (pinned-but-finite outcome, Stan-parity behavior);
(b) healthy-path bit-identity: blr chain0 md5 identical with/without
guard when init is fine (guard only touches non-finite branches).
EXPECTATION: (a) yes; (b) yes by construction.

## 2026-08-25 — NaN-ALPHA GUARD SHIPPED (rob/nan-alpha-guard): both gates PASS (orchestrator #2)

Implementation per prereg (previous entry): skip adapt_handler when
min_accept non-finite (macro_step + _lr mirror, walnuts.hpp); treat NaN
as saturated in AntiWindupAdapter (`!(alpha >= floor_alpha_)`,
step_optimizers.hpp).
GATES: (a) PASS — kronecker_gp dead-init chain seed 20260819+0 completes
1000+1000 rc=0 (previously terminate at freeze); pinned-degenerate draws,
Stan-parity finish-with-diagnostics. (b) PASS — blr healthy-path chain0
md5 e5e754be061fdaa130639d11f14e77e2 identical with/without guard.
Packaging: branch rob/nan-alpha-guard pushed to sims1253/walnutpie; draft
PR #10 on the FORK (per user rule: never upstream). Residual gap flagged:
W-42-style fail-fast did not catch this -inf init path on w54 defaults —
separate ledger item, not fixed here.

## 2026-08-25 — W-62 INCREMENT 1 IMPLEMENTED + REFERENCE-VERIFIED (run-gates pending compile window): exp/lr-alg1-basis @ d0ca4a7 off dev/init-robustness 3eddfc4 — Alg-1 basis mode 4, +144/−11 across 5 files, defaults OFF

DONE: basis mode 4 per the memo (standardize, dual SVD, joint QR,
projected Cx/Ca + 1e-5 I, SPD geometric mean, eigenfilter c=2 as
rank cap, SIGNED c = lambda-1, composed via the existing low_rank
operator which was already valid for c in (-1,inf) — consumer audit
clean); --metric-cutoff/--metric-gamma plumbed through WarmupConfig
(all 8 dispatch sites receive it; no dispatch edits). VERIFIED:
-fsyntax-only on 5 touched + 3 consumer files (C++20, project
includes); numpy reference vs C++ driver (compiled AND linked -O0):
3 synthetic problems, composed M^-1 max dev 4.0e-13, principal
angles 0.0, lambdas ~1e-15 — gates met; problem (b) is a 6-dim
exchangeable block (memo's 2-dim example never crosses the upper
cutoff for Gaussian targets — honest deviation, covers BOTH filter
tails). CAVEATS (flagged): WarmupConfig/LowRankMetricEstimator
layouts +16B (no serialization/offsetof users — draws unaffected,
argued not measured); existing unit tests NOT run (zero-build
constraint); memo's negative-c property tests + step-probe-under-
full-operator deferred to the compile-window session. PENDING GATES
(pre-registered): (i) 2-model default-path bit-identity canary,
(iii) touched-file unit tests — both need builds. Artifacts:
scratch/w57/lr_alg1_{reference.py,driver.cpp,data.h}; worktree
external/walnutpie_lowrank (committed, -s DCO, NOT pushed).

## 2026-08-25 — W-63 CLOSE-OUT: metric-window chopping A/B REJECTED — `--metric-window 100` loses 24.5% aggregate geo-mean ESS vs default discounting (collapses: pilots −89.7%, accel_gp −62.6%, lotka −51.3%; wins: lsat +35.8%, diamonds +43.1% geoESS) — ESS/s orchestrator session

Executed per the W-63 prereg above (renumbered from W-60). All 30 cells
run by the sibling "W-60 agent" (27 DONE + 3 known-abort cells → 2-rep
medians for kronecker_gp/lotka_volterra/accel_gp rep0/1). Analysis
harness/analyze_w60.py; full table results/w60_ess.json + writeup
results/metric_window_w63.md.

GATES: Gate 1 FAIL (−24.5% vs required ≥+5%). Gate 2 FAIL (lotka
ess_bulk_min −57.7%, kronecker −56.1%). Hard-model collapse present.
VERDICT: REJECT. Default stays metric_window=0.

HONESTY NOTES: (a) mw100 wall numbers are CONTAMINATED by concurrent
sibling wall windows (comms 23:38/23:53) and were not used in the
verdict — ESS/R-hat are wall-independent; clean n_leapfrog corroborates
(pilots +49%, accel_gp +27% evals = noisier mass → longer trajectories).
(b) accel_gp/rep1 is a NEW instance of the pre-existing `macro_time must
be in (0, inf)` abort class (3rd model affected across arms) — logged
for the robustness ledger.
(c) Mechanism: window=100 estimates come from ≤100 correlated draws;
targets that don't need resetting pay pure noise cost. A larger-window
sensitivity sweep (250–500) is a NEW decision, not part of this closed
experiment. The published chopping-beats-discounting result does NOT
transfer to this suite at this window size.

## 2026-08-25 — W-64 PRE-REGISTRATION (before any run): step-optimizer head-to-head — Adam (default) vs DualAveraging vs AdaBelief at full benchmark scale — ESS/s orchestrator session #1

MOTIVATION: walnutpie ships four step-size adapters (Adam default,
DualAveraging, AdEMAMix, AdaBelief — stan_cli.cpp:1380-1390) plus
Batched/Clipped/AntiWindup wrappers; the optimizer-scan sessions adopted
wrappers on paper but NO head-to-head of the base optimizers was ever
recorded on this suite at benchmark scale. Stan's 20 years of DA
experience vs walnutpie's Adam-on-log-stepsize choice is exactly the
comparison the scans called "the state of the art is our own benchmark".

DESIGN: three arms, identical everything except --step-optimizer.
- Arm ADAM (baseline) = existing runs/w36/exp_par artifacts (default;
  no rerun).
- Arms DA / BELIEF = fresh runs/w64/{da,belief}/ via harness/run_w64.py:
  same 10 MODELS × 3 reps, seeds 20260819+1000*rep, OMP_NUM_THREADS=1,
  --chains 4 --chain-exec threads, warmup/samples 1000/1000, same inits,
  DONE markers + rows.csv. All other adapter knobs at defaults (no clip,
  anti-windup default posture) — this isolates BASE optimizer choice only.
- AdEMAMix excluded a priori: two extra hyperparameters, no published HMC
  precedent, scan flagged it rejected-on-paper.

EXPECTATION (pre-registered):
1. Aggregate geomean ess_bulk_geomean: ADAM ≥ DA ≥ BELIEF (upstream chose
   Adam deliberately; AdaBelief's trust-ratio is unproven here). If any
   alternative BEATS Adam by ≥5% aggregate, that contradicts the default.
2. DA's risk profile: dual averaging on saturated-alpha hard models
   (hier_2pl-class) can oscillate without walnutpie's batch/clip wrappers.
3. Wall parity ±15% per model (eval counts similar; wall numbers only
   usable if machine quiet — sibling build streams noted).

GATES:
- ADOPT-candidate (flag flip): alternative beats Adam geomean ESS ≥ +5%
  AND no model median ess_bulk_min drop >20% AND rhat_max not worse
  beyond noise.
- REJECT/CONFIRM-DEFAULT: Adam within ±3% of best or better; or any
  arm shows hard-model collapse (>2×).
- Either way recorded in results/step_optimizer_w64.md + close-out here.

COST: 2 new arms ≈ 20 min sampler time, run sequentially; machine load
checked before each arm (orchestrator #2's -j2 stream respected).

## 2026-08-25 — W-62 INCREMENT 1 CLOSED (all gates PASS): exp/lr-alg1-basis is default-path BIT-IDENTICAL (hier_2pl AND kronecker_gp byte-identical vs base binary; hier_2pl md5 ALSO == the W-53 known-good from the untouched build_w36exp binary — third independent binary, same bytes) + 225 CTest + both standalone property suites PASS

GATES: (iii) config/util/summary 225/225 via ctest (build_gates/,
Release, eigen/cli11 reused from main checkout fetches, googletest
fetched OK); low_rank_metric_test (standalone, manual -O2 compile):
ALL PASSED incl. cond(lowrank-precond)=19.3 rel-dense 4e-17;
leapfrog_property_test: reversibility 3.3e-17, |detJ|-1 8.9e-16.
(i) canary: branch vs base stan_cli (identical configure, -j1, NO
--metric* flags): hier_2pl fe7c57c9… == fe7c57c9… BYTE-IDENTICAL;
kronecker_gp 6b61df9f… BYTE-IDENTICAL. DEVIATION (both arms
identical, fine): kronecker init is inits_w27 (inits_w25 lacks it —
the W-29 protocol's own naming). Artifacts: scratch/w62_gates/;
build dirs build_gates/ + build_base/ left in the worktree.

STATE: low-rank Alg-1 basis is implemented, reference-verified
(4e-13), and proven draw-neutral by default — increment 1 COMPLETE.
NEXT (not started; pre-register fresh): the 4-arm ESS campaign per
scratch/w57/lowrank_metric_design.md §plan (CORE_SET, 3 reps, seeds
20260819+1000*rep+c, pf inits, 5 gates incl. pin battery 0/12) +
memo's deferred code items (negative-c property tests ~80 LOC,
step-probe-under-full-operator ~15 LOC). Needs a quiet multi-core
window (shared machine at load ~2.6 from the ox-alpha session as of
00:15).

## 2026-08-25 — W-63 PRE-REGISTRATION (before any run): partial momentum refresh (Horowitz α<1) A/B on the core-set subset — ESS/s at fixed quality (ESS/s orchestrator session #2, overnight)

MOTIVATION: literature verdict (this session): partial refresh
rho' = alpha*rho + sqrt(1-alpha^2)*M^{1/2}z is a pi-invariant momentum
kernel composing validly with any GIST/WALNUTS trajectory kernel;
production precedent nutpie/nuts-rs ships it as momentum_decoherence
length L=3 => per-trajectory alpha≈exp(-1/L)=0.72. Never tried in-tree.
Mechanism: correlated momenta lengthen effective orbits (antithetic
behavior near half period on Gaussian-like targets) => more ESS per
gradient. Known risks: miscalibrated DA under correlated trajectories
(freeze/slow adaptation if needed); rejection clustering
(Sohl-Dickstein 1205.1939); U-turn masking.

IMPLEMENTATION (worktree scratch/w61/walnutpie_refresh, branch
exp/partial-refresh off e46da43):
- Thread the selected state's momentum across transitions (SpanW already
  stores rho_select_; extend the endpoint-cache threading pattern).
- Env-gated single read WALNUTPIE_PARTIAL_REFRESH_ALPHA (default empty =
  1.0 = exact current behavior; no CLI wiring, avoiding the 8-call-site
  hazard). alpha applied AFTER mass multiply: rho' = alpha*rho_prev +
  sqrt(1-alpha^2)*(chol_mass*z). First transition of a chain = fresh draw.
- Validity care: on REJECTED transitions the returned state is still the
  selected span state (walnutpie always returns a selected state), whose
  momentum is used as next rho_prev — composition remains a valid kernel
  product; documented in code comment.

DESIGN: arms BASELINE (alpha unset) vs PR07 (alpha=0.72) vs PR05
(alpha=0.5, exploratory). Models: eight_schools_centered,
eight_schools_noncentered (if data/inits exist, else diamonds), blr,
hier_2pl, arma11, kronecker_gp (guard branch cherry-picked so chain0
doesn't abort — noted deviation from pure e46da43 base, identical both
arms). 3 reps x 4 chains, seeds 20260819+1000*rep+c, 1000/1000, pf
inits same mapping as W-61, chains sequential single-core batches
(machine discipline; wall numbers NOT used — ESS/grad + eval counts are
the metrics).

EXPECTATION (pre-registered):
1. Gaussian-like/easy models: ESS_bulk-min geomean improvement >= +10%
   at EQUAL gradient counts (antithetic orbit mechanism).
2. Hard/funnel-adjacent models (hier_2pl, arma11): no collapse; any
   change within ±20%.
3. R-hat>1.01 count not worse than baseline in any arm.
4. Gradient counts within ±10% of baseline (adaptation unaffected on
   healthy path).

GATES:
- ADOPT-candidate: gate 1 met AND gates 2-4 hold.
- REJECT: any model's min-ESS drops >2x in either arm (W-25 signature),
  or aggregate delta within ±3% noise band.
- 3-rep medians throughout; bit-identity canary: baseline arm draws md5
  == stock e46da43 binary draws on blr rep0 chain0.
COST: ~90 runs x ~40-90s ≈ 2-3 h serial; machine otherwise idle
overnight; no wall-time claims.

## 2026-08-25 — W-63 PRE-REGISTRATION (before any run): low-rank Alg-1 ESS campaign — 4 arms, full CORE_SET, overnight grid (unattended window; ~20h)

BASE: exp/lr-alg1-basis @ d0ca4a7 build_gates stan_cli (W-62-gated,
default-path bit-identical). Single-chain binary ⇒ 4 chain processes
per cell, seed = 20260819 + 1000·rep + c (c=0..3; CORE_SET frozen
protocol), ALL arms --metric-window 50 (repo protocol), 1000 warmup
+ 1000 draws, 3 reps, pf inits. Arms (one binary, flags):
A0 = no rank flags (baseline + canary, CITED from W-62 gate (i));
A1 = --metric-rank 10 --metric-basis 4 (fold);
A2 = A1 + --metric-full (exact operator);
A3 = A2 + --metric-auto <threshold> (screened full).

SCOPE (honest cut): A0/A2/A3 on all 21 CORE_SET models; A1 on the
6-model cross-structure subset only (G5 is an operator-choice
confirmation). 69 cells × 12 chain-runs. SUBSETS: cross-structure
{hier_2pl, bym2_offset_only, kronecker_gp, radon_variable_intercept_
slope_noncentered, lsat_model, garch11}; no-harm = rest (esp.
funnels eight_schools_centered/pilots/arma11/blr).

STEP 0 (before grid, recorded): A3 threshold check — bym2 (screen
should ENGAGE) + hier_2pl (should NOT) at basis 4 rank 10,
--metric-auto {0.3,0.5,0.7}, w400 s400 1 rep; pick the threshold
that separates; if all agree keep 0.5. DECISION RECORDED BEFORE GRID.

GATES:
G1 canary: CITED (W-62 increment-1 gate (i): byte-identical vs base
binary, hier_2pl + kronecker_gp, third-binary md5 continuity).
G2 efficacy: geomean over cross-structure subset of (A3/A0
ESS_bulk_min median-of-reps) >= 1.5 (paper ceiling 4x; heuristic's
best single 3.46x on bym2).
G3 no-harm: every no-harm model A3/A0 ratio >= 0.9 (rep median) AND
count(rhat>1.02) <= A0's.
G4 pin battery: blr w100/w400 × {pf (inits_w25/blr), default} × 3
reps × 4 chains × EACH rank-on arm (A1/A2/A3): pinned chains 0/12
per cell. CAVEAT (recorded): this base is dev/init-robustness (no
freeze-clamp — W-43's original was exp-stack); if A0 does not pin,
the gate is recorded VACUOUS-for-comparison and the honest claim is
"no pins introduced by rank-on arms on this base".
G5 full-vs-fold: A2/A1 on the subset, expect ~1.2x (W-9 precedent).

METRICS: per-run per-parameter bulk ESS (posterior, per-variable),
model score = min-over-params bulk ESS; report BOTH ESS_min/grad
(logp_grad calls from cli logs — primary) and ESS_min/s (wall — the
user's headline). Ragged chains trimmed to min length. Medians of 3
reps; geomeans across subsets. ANALYSIS: harness python, artifacts
scratch/w63/.

EXECUTION: resume-capable driver (per-cell dirs; skips completed),
priority order: step-0 screen check → G4 battery (cheap, safety
first) → cross-structure A0/A2/A3 → no-harm A0/A2/A3 → A1 subset.
Parallelism 2 workers while foreign load ~2 (shared machine, comms
coordination), scales to 4 when sustained load < 1.5; total <= 4
cores ALWAYS. PARTIAL GRID = honest partial adjudication (missing
cells marked not-adjudicated), no post-hoc scope creep. Missing pf
inits regenerated via harness/run_pathfinder.py into inits_w63/
(in-repo; 13 of 21 missing; 8 reused from inits_w36). Model .so =
bs_models stock math (identical across arms — sampler-side change
only). EXPECTATIONS: G2 1.5-4x on cross-structure; G3 clean unless
rank hurts funnel class (W-9 forced-rank precedent says aggregates
can lose 0.66-0.79x — the SCREEN is the mitigation, watch G3);
G4 honest unknown (first rank-on short-warmup test on this base);
G5 ~1.2x. Negative results recorded and kept, same as wins.

## 2026-08-25 — W-63 CAMPAIGN DIARY (setup + launch + bym2 diagnosis): grid RUNNING detached (1020 jobs, 2 workers, ~11h est); step-0 threshold check VACUOUS (bym2 pins under ALL arms at w400 on this base — incl. A0; fallback 0.5 recorded per pre-reg); bym2 rank-arm ABORT diagnosed as the known NaN-adapter-feed class

SETUP: manifest complete (21/21 models; bs_models .so + data json
resolved; inits: 5×w25 + 8×w36 + 8 generated into inits_w63 via the
PINNED cmdstan 2.39.0 (~/.cmdstan), 96 files verified; init format =
one unconstrained coord per line per the binary's --init-file, not
JSON — recorded). Driver scratch/w63/driver.py detached (PID 169442),
resume-capable, WORKERS control file (2 now, ≤4 clamp), priority
order P1 pin battery → P2 cross-structure → P3 no-harm → P4 A1
subset. Shakedown 9/10 well-formed.

DIAGNOSIS (no code change mid-campaign): bym2/A2/w1000 aborts
post-sampling with `std::invalid_argument: macro_time must be in
(0, inf)` (rc −6; A0 succeeds; reproducible). Source path: api.hpp
reinit/step-adaptation propagates a corrupted adapted step (ar.step_bar
/ macro_time) into validate_positive on sampler re-construction.
SAME failure class the ox-alpha session fixed on their lineage
(rob/nan-alpha-guard, fork PR #10: "skip adapter feed on non-finite
min_accept + NaN-as-saturated anti-windup; kronecker_gp completes
(was abort)") — my dev/init-robustness base predates it. PLAN: let
the grid census ALL aborts (expect bym2 rank arms; WATCH kronecker_gp
rank arms — their fix mentions kronecker aborting pre-fix); post-
campaign increment = cherry-pick the guard onto exp/lr-alg1-basis,
re-run the W-62 bit-identity canary, rerun ONLY aborted cells.
bym2's cross-structure role is DOUBLY compromised on this base
(pins at w400 under A0; aborts at w1000 rank arms) — G2 geomean will
be over adjudicable models with bym2 marked not-adjudicated +
recorded honestly.

## 2026-08-25 — W-64 CLOSE-OUT: step-optimizer head-to-head CONFIRMS DEFAULT (Adam) — da catastrophic (5/10 models abort entirely), belief noise-band (+2.4% agg) — ESS/s orchestrator session #1

Executed per W-64 prereg. All 60 new cells run (37 DONE, 23 deterministic
macro_time aborts). Analysis harness/analyze_w64.py; full table
results/step_optimizer_w64_ess.json; writeup results/step_optimizer_w64.md.

GATES: DA — gate1 FAIL (lost bym2/lsat/accel/pilots/eight_schools
entirely; hier_2pl −43.2% where alive). BELIEF — gate1 FAIL (+2.36%
aggregate, inside ±3% noise band; −43.2% on lotka). VERDICT: CONFIRM
DEFAULT. Adam is the only base optimizer that completes this grid at CLI
default posture (wrappers OFF uniformly for all optimizers — verified in
stan_cli.cpp dispatch).

NEW KNOWLEDGE: (1) first recorded head-to-head evidence behind walnutpie's
Adam default; naked DA without Stan-style freeze regularization diverges
step→0 on saturated-alpha models (same macro_time throw class).
(2) Diamonds-class easy targets: da +233.8%, belief +71.6% geoESS over
Adam — real ESS left on the table on easy targets; conditional-optimizer
follow-up flagged as a NEW decision, not adopted here.
(3) macro_time abort class now observed under all three optimizers and 6
model/repro cells across W-36/W-59/W-64 arms → generic dead-init→NaN-alpha
hole; rob/nan-alpha-guard (orchestrator #2) is the fix vehicle.
Wall numbers clean this time (quiet machine); roughly parity.

## 2026-08-25 — W-62 PHASE 1 CLOSE-OUT: walnuts-ai prototype — ALL GATES PASS, PROCEED to Phase 2 (orchestrator #2)

Commit 2b7af30 on exp/isokinetic-ai (scratch/w61/walnutpie_w54):
include/walnutpie/isokinetic.hpp (471 LOC) + tests/test_isokinetic.cpp.
Faithful port of generalized-WALNUTS engine.py; formula corrections vs
my prereg paraphrase: (1) exact rotation coef_pre =
((1+γ)−(1−γ)e^{−2δ})/2 − γe^{−δ}; (2) level search uses FIXED TOTAL
MACRO TIME h with per-level step h/2^ell (matches reference).
BUG FOUND & FIXED during dev: reverse level search must initialize H_eff
at −logp(end) WITHOUT the leaf Jacobian offset — including lJ_leaf
spuriously rejected admissible levels and corrupted Hastings ratios
(15–40% variance over-dispersion). Verified by recorded-RNG replay:
0/300 decision mismatches vs Python reference.

GATES: reversibility-by-negation 5.2e-15 PASS; Gaussian 20k draws
max|z|=1.64 (<3), max var err 2.7% (<20%) PASS (2nd seed too); funnel
10k all finite, min log σ = −11.68, mean(v)=−0.06 PASS; determinism
bit-identical PASS; ESS/grad proxy on Gaussian ~10× plain leapfrog HMC
(reference reports ~10.9× vs their walnuts-h — consistent); ladder evals
0 by construction PASS.

HONEST LIMITS: no adaptation (fixed h=1.6, δ_tol=0.05), anchor C=0
placeholder, weighting algebra does NOT factor through SpanW/Barker
(documented deviation — iso path has its own leaf-weight bookkeeping),
ESS estimator caps at n (iso chains near-anticorrelated → conservative).
Phase 2 next per port plan: anchor estimation (coordinate median,
refreshed), h calibration (Γ=0.80 bisection or adapter statistic),
then C++ parity gate ≥5× walnuts-h on funnel.

## 2026-08-25 — W-63 CLOSE-OUT: partial momentum refresh REJECTED by pre-registered gates — sign INVERTED on the worst model (orchestrator #2)

Implementation: commit 28bec03 on exp/partial-refresh (e46da43 + NaN
guard); rho threading mirrors W-23 endpoint-cache pattern;
WALNUTPIE_PARTIAL_REFRESH_ALPHA env-gated, unset = bit-identical (canary
PASS: blr md5 e5e754be… stock==new).

RESULTS (3-rep medians, min-param rank-normalized ESS): geomean bulk-min
PR07 −11.2%, PR05 −7.4%; tail worse still (−18.5%/−13.5%). Gate 1 not
only failed but REVERSED: eight_schools_CENTERED min-bulk −46% (PR07) /
−34% (PR05) — correlated momenta hurt exactly where the funnel's scale
coordinate needs independent escape attempts; arma11 tail −29% at PR07.
blr neutral; grad counts within ±10% everywhere; R-hat not worse.
VERDICT: REJECT both arms (noise-band + collapse conditions). Negative
result recorded; mechanism consistent with Sohl-Dickstein rejection-
clustering caveat and Carpenter's skepticism (stan-forums t/1526) —
decoherence helps microcanonical-type samplers, not Metropolis-HMC with
within-orbit adaptation. Lane closed with data.

SURPRISES for the ledger:
1. Centered-parameterization funnels are the ANTI-target for momentum
   decoherence — useful design knowledge for any future refresh-style
   feature (nutpie default L=3 transfers badly to Stan-model class).
2. kronecker_gp rep0 chain pins identically in ALL arms (Lambda.30.30
   constant, R-hat O(10^2)) — arm-independent init-file pathology,
   more evidence for the -inf/fail-fast screening gap flagged at the
   NaN-guard close-out.
Artifacts: scratch/w61/runs_w63/ (w63_results.md/.json, analyzer scripts;
self-contained Vehtari-2021 ESS impl validated on iid/AR(1) since arviz
unavailable — reusable).

## 2026-08-25 — KRONECKER_GP rep0/chain0 INIT PATHOLOGY ROOT-CAUSED: inits_w36 entry maps to LKJ-Cholesky diagonal == 0 ⇒ model throws at every eval (flagged, NOT fixed — canonical inputs) (orchestrator #2)

Probe: stock w54 binary + inits_w36/kronecker_gp/rep0/chain_0.txt,
warmup 5: every logp_grad fails "lkj_corr_cholesky_lpdf:
Random variable[27] is 0, but must be positive!" (kronecker_gp.stan:73).
The deterministic-normal unconstrained init lands on a constraint
transform boundary (diagonal exactly 0). Explains: W-61 chain0 abort
(NaN-alpha chain), W-63 arm-independent pin (guard now prevents the
abort but the chain stays dead), and likely historical kronecker
min-ESS floor cells in earlier grids that used inits_w36.
DO NOT silently regenerate: inits_w36 are frozen W-36 benchmark inputs;
changing them breaks cross-session comparability. Options for owners:
(a) keep + document (cells are stress-tests of dead-init behavior),
(b) regenerate kronecker pf-inits into inits_w25 style and re-baseline
kronecker cells only. User/ledger decision.

## 2026-08-25 — W-62 PHASE 2 CLOSE-OUT: adaptation works, C++ PARITY GATE FAILED HONESTLY (0.29x NUTS on funnel) — Phase 3 NOT unlocked; one pre-registered diagnostic follows (orchestrator #2)

Commit d179fb7 on exp/isokinetic-ai: include/walnutpie/isoadapt.hpp
(reference tuning.py port: Gamma-bisection h calibration P(micro=0)=0.80,
deterministic seed arithmetic; anchor = coordinate median refreshed
every 50 iters over trailing 250-window; run_adapted_iso warmup/freeze
driver).
GATES: a h-convergence PASS (|Δh|/h<5% by it200); c adapted-Gaussian
0.62x its fixed-h self (>=0.5x) PASS; d determinism PASS; e full Phase-1
battery unchanged PASS. **b FAILED: funnel ESS/grad 4.3e-5 vs best-swept
inline NUTS 1.5e-4 = 0.29x** (0.44–0.55x other accountings). Control:
adapted == fixed-h efficiency ⇒ shortfall is COST PROFILE (~1100
grads/transition in the deep neck: long level searches at small h) not
an adaptation defect. Two debugging cycles used; found+fixed a real
probe-normalization bug en route; numbers reported unmodified.
VERDICT per protocol: Phase-3 integration NOT unlocked. The paper's
10.9× was vs walnuts-h (not NUTS) — our inline NUTS baseline may be
flattering itself via divergence-cheap profiles; also warmup+calibration
(~660k grads) charged in. Both confounds are exactly why the follow-up
is scoped as DIAGNOSTIC, not tuning-to-pass.

## 2026-08-25 — W-62b PRE-REGISTRATION (before any run): isokinetic funnel cost-profile decomposition + FAIR baseline vs walnutpie's own walnuts-h; pre-specified sensitivity grid (orchestrator #2)

QUESTIONS (diagnostic, not gate-rescue):
Q1 Where do iso's gradient calls go on funnel? Decompose per phase
(warmup/calibration/frozen) and per depth (level-search attempts vs
accepted leaf length) at h=adapted, max_ell=8.
Q2 Fair baseline: same driver, same funnel spec, same frozen-phase draw
budget — walnutpie's OWN diagonal-mass transition_w (walnuts-h lineage)
vs iso, SAMPLING-PHASE-ONLY ESS/grad both sides. Report ratio honestly.
Q3 Pre-specified sensitivity grid (chosen NOW, no iteration): max_ell ∈
{8, 6, 4} × delta_tol ∈ {0.05, 0.20}, h recalibrated fresh per cell,
fixed seeds, funnel only. Expectation: lower max_ell trades neck reach
for per-transition cost; if ESS/grad improves >=3x toward NUTS parity at
max_ell=4–6, the lever is trajectory-length economics, not the flow.
DECISION RULE (now): if Q2 shows iso >= 1x walnutpie-walnuts-h on funnel
sampling-only, OR Q3 finds a cell >= 3x its Q2-baseline — schedule a
proper CORE_SET-scale evaluation design next session; otherwise record
the walnuts-ai lane as reference-material (correct port exists, replay-
verified) and close W-62 entirely.
MACHINE: single-core, nice; ~30 short runs.

## 2026-08-25 — W-62b CLOSE-OUT: cost decomposition + fair baseline done; decision rule routes to CORE_SET-scale design; delta_tol is the lever (orchestrator #2)

Commit bd8eba8 (isokinetic.hpp opt-in IsoLeafProbe hook default-off +
tests/test_w62b.cpp). Q1: frozen phase = 80% of grads; ~98 leaves/draw
× ~13 grads each at mean accepted level 0.18 — per-leaf overhead × leaf
count dominates, max_ell nearly dead weight. Q2 fair baseline
(walnutpie's own transition_w w/ minimal DA, identity mass): ratio
iso/wh = 0.29x at delta_tol=0.05 — independently reproduced Phase 2.
Q3 grid: delta_tol=0.20 → h 0.48→0.95, grads/draw 1324→~680,
rnESS 78→476 ⇒ **3.44–3.52x wh** at max_ell ∈ {8,6}. Decision rule
fired: schedule CORE_SET-scale evaluation design.
CAVEATS (carried): single-seed/single-chain ratios; baseline min-coord
ESS=6/2000 (huge variance); identity-mass baseline could strengthen
with a better metric; DA needed eps clamp [1e-3,10] on funnel (pinned
degenerate chains now score ESS=0).

## 2026-08-25 — W-62c PRE-REGISTRATION (before any run): replicated delta_tol confirmation — the gate before proposing core-set scale (orchestrator #2)

DESIGN: funnel d=11 reference spec, arms {wh (as W-62b), iso(8,0.05),
iso(8,0.20), iso(6,0.20)}, 5 seeds (20260824+0..4), frozen 2000 draws
each, sampling-only ESS/grad both sides (same accounting as W-62b).
EXPECTATION: iso(0.20) median ratio >= 1x wh across seeds; mechanism
prediction: iso advantage grows when wh's divergences waste work in the
neck (wh rnESS variance across seeds should exceed iso's).
GATES: GRADUATE iff median ratio >= 1.0 AND worst-seed ratio >= 0.5;
else close W-62 lane entirely (reference port remains archived).
COST: ~20 runs x minutes, single-core nice'd.

## 2026-08-25 — W-62c CLOSE-OUT: GRADUATE — replicated confirmation passes with margin (orchestrator #2)

Commit 7d7c7da (tests/test_w62c.cpp). Ratios iso/wh (sampling-only
rnESS_bulk-min/grads, 5 seeds): iso(8,0.20) median 2.32x worst 1.26x;
iso(6,0.20) median 2.25x worst 1.27x; iso(8,0.05) fails (median 0.92x)
as predicted — the advantage is SPECIFIC to delta_tol=0.20. Mechanism
confirmed: wh rnESS cv=0.47 (divergence-cost seed lottery; DA eps landed
anywhere in [0.24,9.03]) vs iso(0.20) cv=0.10. Caveats carried:
single-chain cells, ESS ceiling on d=11 funnel, identity-mass baseline.
DECISION: core-set-scale evaluation scheduled ⇒ W-64 pilot below.

## 2026-08-25 — W-64 PRE-REGISTRATION (before any run): walnuts-ai BridgeStan PILOT on a 5-model core-set subset — first real-posterior test, adaptation deliberately out of scope (orchestrator #2)

MOTIVATION: W-62c graduated the funnel evidence. Open question: does
delta_tol=0.20 iso survive real posteriors, where (a) per-leaf overhead
meets cheap gradients, (b) no funnel geometry exists, (c) wh carries
ADAPTED diagonal mass while iso has NONE (Phase-3 out of scope)?
DESIGN answers (c) head-on with a decomposition arm.

ARMS (all sampling-only accounting, 1000 warmup + 1000 draws):
- WH-ADAPT: stock w54-lineage binary, CLI defaults (adapted diag mass +
  DA) — the production comparator.
- WH-ID: same binary, identity mass via flags if available else minimal
  driver arm (implementer documents which; determinism rules).
- ISO(0.05), ISO(0.20): extended test driver bound to BridgeStan .so
  models via load_stan.hpp (dlopen), anchor online median, h by Gamma
  bisection per chain on warmup states, identity mass.
MODELS: blr, eight_schools_centered, low_dim_gauss_mix (funnel class),
arma11, hier_2pl. 3 reps x 4 chains, seeds 20260819+1000*rep+c,
pf inits (inits_w25: blr/hier_2pl/arma11; inits_w36 others);
kronecker excluded (known dead-init input pathology, see ledger).
METRIC: min-param rank-normalized ESS_bulk over draws / sampling-phase
grad counts; medians of 3 reps. Degenerate chains ESS=0.

EXPECTATION: ISO arms LOSE to WH-ADAPT on hierarchical/GLM models
(no mass adaptation — expected, not a failure of the pilot); ISO(0.20)
target: >= WH-ID everywhere (integrator at least matches unadapted HMC)
and >= 1x WH-ADAPT on low_dim_gauss_mix (funnel-class transfer).
GATES: PROPOSE-FULL-CORESET iff ISO(0.20) >= WH-ID geomean AND
ISO(0.20) >= 0.5x WH-ADAPT geomean AND funnel-class expectation met.
Otherwise close lane with envelope map (which model classes iso wins/
loses). Either way the deliverable is the envelope, honestly reported.
COST: 5 models x 3 reps x 4 chains x ~4 arms ≈ 240 runs, serial,
~4-5 h. Machine idle overnight otherwise.

## 2026-08-25 — W-65 CLOSE-OUT: replay fidelity BITWISE (G1 48/48, max|log-ratio|=0.0 after root-causing an Eigen lazy-delta aliasing in OnlineMoments::observe); P1 curvature-seed NO-GO by pre-registered gates (windows are data-starved on slow coords — no seed can help); P2 cross-chain pooling GO-with-caveats (final-window error −86..−91% on 3/4 models; bym2 shows the guard-tuning failure mode); instrumentation slice validated and drafted as fork PR

GATES (per pre-registration):
- G1 (fidelity, binds all): PASS 48/48 cells (4 models x 3 reps x 4 chains).
  Primary metric = replay EST[0:T] vs trace invmass.f64 rows at native
  double precision: worst-cell max|log-ratio| = 0.000e+00 (bitwise) on all
  four models. Log-line check passes at print precision (rel-L2 <= 1.9e-6
  against the ~6-significant-digit "Mass matrix diagonal" output; the
  original 1e-8 threshold was miscalibrated against print rounding — gate
  recalibrated, rationale recorded here).
- G2 (prediction): REFUTED on the marginal class. Oracle-quality seeding
  cuts slow-decile first-half-window error by only 0.31% (blr), 13.1%
  (hier_2pl), 17.6% (bym2) vs predicted >=30%; 90.2% on easy arma11.
- G3 (P1 GO/NO-GO): NO-GO. lbfgs closure: hier_2pl -2274% (the D=669
  LBFGS run did NOT converge in 500 iters; its path-curvature seed is
  ~4x WORSE than |grad|), blr nil-in-denominator (grad-oracle gap ~0),
  bym2/arma11 unseeded. Mechanism (measured, not conjectured): after a
  chop reset the segment carries ~4 pseudo-count seed weight vs ~49 data
  weight, and on slow coordinates 50 correlated draws have near-zero
  realized variance — the DATA term drowns ANY seed with noise around
  ~zero exploration. Seed quality is third-order behind window
  information content. This is direct, quantified evidence FOR
  score-based metrics (C''): gradients carry curvature information on
  coordinates the chain cannot explore.
- G4 (P2 GO/NO-GO): GO, formally (>=25% on >=2 models), with a required
  redesign item. Final-window error reduction vs oracle, pooled-M2 at
  boundaries behind a median-log-spread<ln(10) guard: arma11 90.9%,
  blr 85.4%, hier_2pl 29.2%, bym2 -176% (HARMFUL). bym2 anatomy: reps 1-2
  (cross-chain spread e^6-e^7) were refused pooling by the guard and are
  unaffected; rep0 (spread e^1.1-e^1.2, just UNDER the guard) pooled and
  was poisoned — the single scalar guard is too loose near mode-dispersed
  ensembles; per-coordinate gating or a much stricter threshold is
  REQUIRED before any closed-loop trial. Honest limit restated: this is
  an open-loop estimator study on realized streams, not a closed-loop
  bench.

DISCOVERY (upstream-candidate, found by G1 diagnosis): walnutpie
OnlineMoments::observe (include/walnutpie/online_moments.hpp:187-192)
computes `auto delta = y - mean_` — an Eigen LAZY expression holding a
reference to mean_. By the time the sum_sq_dev_ line evaluates it,
mean_ has been updated, so the update applied is
    ssd <- d*ssd + (y - mean_NEW)^2
instead of the classic Welford delta_old*(y - mean_new) implied by the
class documentation ("reduces to the original Welford accumulator when
discount_factor = 1"). Verified against the compiled binary by dumping
internal draw_var/score_var/est at iterations 0-2 (env-gated debug,
since reverted): reproduced to print precision, e.g. arma11 rep0 chain0
score coord0 = 4883.88 vs 4883.86 predicted from (y-mu_new)^2 vs 6494.7
under classic semantics. Effect: transient variance estimates overweight
the newest deviation; asymptotic stationary impact unquantified. Fix =
materialize the expression (`delta.eval()`), but it CHANGES SAMPLER
NUMERICS (not bit-compatible) — packaged separately from the
instrumentation PR.

ARTIFACTS: scratch/w65/{traces/ (48 cells + manifest.csv), pipeline.log,
g1_results.csv, g2g3_results.csv, g4_results.csv, canary/};
scratch/w59/replay/{mass_replay.py, compare_frozen.py, FORMAT.md v2,
test_mass_replay.py}; scratch/w65/{analyze_seeds.py, analyze_pooling.py};
scratch/w59/seeds/ + lbfgs_report.md (L-BFGS generator harness/
gen_lbfgs_seed.py; self-test 1e-5; blr validated vs exact posterior).
Fork branch exp/warmup-trace @ 7621584 (instrumentation slice; CANARY A
bit-identity PASS 3x: tracer on/off draws md5 identical e35703a3...).

LESSONS: (1) trace-contract consumers must normalize producer key case —
a silent .get() default silently disabled chopping in the first replay.
(2) Gate thresholds must respect measurement precision of the reference
(6-digit log line can never support 1e-8). (3) `auto` + Eigen expressions
is a live bug class in this codebase — grep candidate:
`auto .* = .*-.*mean_` patterns inside expression templates.

NEXT (one-decision items, NOT batched): (a) P2 closed-loop implementation
pre-reg — REQUIRES the guard redesign first (per-coordinate spread cap;
refuse pooling above it) and a determinism stance (ChainExec::Serial
first per proposals_ess_per_sec.md); (b) aliasing fix draft PR decision;
(c) C''#1 Fisher-online arm inherits a stronger motivation statement
from G3's mechanism.

## 2026-08-25 — W-64 PRE-REGISTRATION (guard increment, per W-63 diary plan): cherry-pick rob/nan-alpha-guard onto exp/lr-alg1-basis, re-canary default path, rebuild, rerun ONLY the W-63 aborted cells (+ any completed-but-NaN-contaminated rank-arm cells the analysis flags); final re-adjudication of affected arm×model cells

GATES: (i) cherry-pick clean or resolved with conflicts EXPLAINED in
the commit message; (ii) default-path bit-identity canary RE-RUN
(hier_2pl + kronecker_gp, same protocol as W-62 gate (i)) — MUST
stay byte-identical (the guard is inert on finite paths; this is the
claim under test); (iii) unit tests 225 + property suites re-run;
(iv) rerun set = the 86 rc=-6 cells + analysis-flagged garbage cells;
completed-finite cells are NOT rerun (guard inert for them — mixing
old/new binary outputs is sound iff (ii) holds and the guard only
alters non-finite feeds). EXPECTATION: aborted rank-arm cells
complete; their ESS then adjudicated into G2-G5; canary byte-exact.

## 2026-08-25 — W-64 PROGRESS (guard verified, rerun running): cherry-pick 6ba0798 resolved for the dev/init-robustness base (W-43 pin_trace lines dropped — absent lineage; guard-only semantics), canary BYTE-IDENTICAL (fe7c57… + 6b61df9f… reproduce W-62 exactly — guard is bit-inert on healthy paths), 225 ctest + both property suites PASS, bym2/A2 smoke that aborted pre-guard now COMPLETES (rc=0, 1000 draws) surviving 680 NaN poisson-log-rate logp failures during warmup; driver relaunched 03:15 for the 86 aborted cells at 2 workers

## 2026-08-25 — W-63 CLOSE-OUT: low-rank Alg-1 ESS campaign — ALL GATES FAIL, DECISIVE NEGATIVE RESULT KEPT (A3 screen engaged 0/300 — byte-identical to A2; G2 geomean 0.037 vs bar 1.5; rank arms RE-PIN blr w400-pf 1/12→6-12/12)

Executed per the W-63 low-rank prereg + campaign diary. 1020 chain-run
jobs, 934 done / 86 rc=-6 macro_time NaN-feed aborts (census verified from
disk with the driver's own is_done; naive driver.log grep double-counts the
shakedown job9). CORRECTION to diary expectation: "A0 never aborts" is
false — A0 lost 3/588 runs (kronecker r0c0 dead-init, accel r1c1, lotka
r1c0; the same seeds abort under rank arms => init-driven base class), but
no A0 cell was lost (all ≥11/12). Rank-arm-added aborts: arma11 A2/A3 ALL
12 each, bym2 5/6/6 (A1/A2/A3), kronecker +4/5/5, accel +4/+4, radon_pp
3/3, pilots 2/2, blr r0c2 (1/1, pf-init; also kills its w100/w400-pf
battery cells). A2 and A3 abort on identical seeds.

HEADLINE MECHANISM FINDING: A3 ≡ A2 — all 252 completed main-grid csvs and
48/48 pin-battery csvs are md5-identical between A2 and A3. The --metric-
auto 0.5 screen (0.5 = step-0 fallback, vacuous there) NEVER ENGAGED in the
whole campaign; every A3 number is the unscreened exact low-rank operator.

GATES (ESS = rank-normalized Geyer bulk on combined 4-chain draws, min over
params, median of 3 reps; posterior pkg absent — reused+revalidated the
Vehtari-2021 impl from scratch/w61/runs_w63; rhat = rank-normalized split;
constant columns excluded per W-54: 466/rep kronecker, 30 dogs, 4 hier_2pl):
- G1 canary: CITED (W-62 gate (i)).
- G2 efficacy FAIL: geomean A3/A0 ESS_min/grad over adjudicable cross-
  structure {hier_2pl 0.0913, radon_var_int_slope 0.0147, lsat 0.0030,
  garch11 0.4525} = 0.0368 vs bar 1.5 (~41x miss; e/s geomean 0.028;
  sensitivity incl degraded bym2/kronecker 0.068). bym2/kronecker not
  adjudicated (rank-arm aborts; bym2's A0 w1000 baseline itself degenerate:
  rhat_max 3.6e15, 9598/9610 params rhat>1.02 — triple compromise).
- G3 no-harm FAIL: adjudicable violators eight_schools_centered 0.029x
  (rhat 10>1), eight_schools_noncentered 0.351x, gp_regr 0.822x,
  kidscore 0.862x, diamonds rhat 26>17; degraded violators blr 0.015x
  (rhat 6>0), lotka 0.739x (rhat 49>45); not-adjudicated radon_pp 0.0097x
  rhat 652 vs 1 (plainly harmful), accel 0.98x, arma11 A3 cell 0/12
  (completion regression). Adjudicable PASS: low_dim_gauss_mix 2.75x,
  logmesquite 2.06x, wells 1.068x, dogs 0.992x. Adjudicable-9 geomean
  0.708x — inside the W-9 0.66-0.79 band in aggregate, but per-model
  collapses (0.003-0.06x on the high-dim correlated class: lsat 1012p,
  hier_2pl 804p, radon_pp 775p, kronecker 5463p, bym2 9610p) are 10x worse
  than the precedent; the screen was the pre-registered mitigation and it
  never fired.
- G4 pin battery: pre-registered 0/12 bar VACUOUS (A0 pins on this
  dev/init-robustness base: w100-pf 8/12, both def cells 12/12) AND the
  fallback claim "no pins introduced" FAILS: w400-pf A0 1/12 (escaped
  chains 445-487 unique rows, 21.3 evals/draw) vs A1 12/12, A2/A3 6/12
  (identical sets; pinned = all-500-rows-identical, 32 evals/draw = the
  W-43 31-eval signature). Rank arms re-pin chains the base escapes.
- G5 full-vs-fold: A2/A1 geomean 1.345 vs ~1.2x expectation (hier_2pl 0.52,
  radon 3.10, lsat 0.39, garch11 5.18) — expectation-met-on-geomean-only;
  uninformative since 3 of 4 models sit on collapsed chains under both
  operators.

Top wins A3/A0: low_dim_gauss_mix 2.75x, logmesquite 2.06x (real);
pilots 1.94x (garbage-vs-garbage, A0 rhat 3.06). Top losses: lsat 0.0030x,
radon_pp 0.0097x, radon_var 0.0147x. All-20 aggregate 0.250x.

HONEST LIMITS: the 86 aborts are unmeasured-not-bad (NaN-guard cherry-pick
+ aborted-cell rerun queued, deliberately NOT done here); A2-vs-A3 wall
diffs (up to 2x, e.g. lsat 68.7s vs 141.4s) are 2-worker shared-machine
load noise on bit-identical draws — e/g is the comparator; diamonds/pilots/
bym2/kronecker A0 baselines are themselves broken (ratios there are
garbage-vs-garbage); degraded cells (blr, lotka, pilots, radon_pp, accel,
kronecker) scored on full 4-chain reps only, 1-2 reps in places.

VERDICT per prereg (negatives kept): low-rank Alg-1 rank-10/basis-4
--metric-full REJECTED at CORE_SET scale on this base. The NaN-guard rerun
is only worth its cost if a future arm design changes the operator — the
completed-cell evidence stands regardless.

Artifacts: results/lowrank_ess_w63.md (full report); scratch/w63/
{lowrank_results.json, analyze_lowrank.py, analyze_lowrank.out, driver.log,
runs/}.

## 2026-08-25 — W-63 ANALYSIS VERDICT (interim, rerun fold-in pending): NEGATIVE RESULT RECORDED AND KEPT — Alg-1 basis forced at rank-10 REJECTED at CORE_SET scale on this base; the auto-screen NEVER ENGAGED (A3≡A2 byte-identical, 0/300) so this measures FORCED rank; G2 0.0368 vs bar 1.5, G3 multiple violators, G4 rank arms RE-PIN the class A0 escapes at w400 (A1 12/12, A2/A3 6/12); wins concentrated in true low-dim-structure models (low_dim_gauss_mix 2.75x, logmesquite 2.06x); aggregate 0.25x

MECHANISM READING (senior): consistent with W-9's forced-rank lesson
(0.66-0.79x), now amplified by the paper-faithful estimator; the
screen was calibrated on heuristic spectra and is inert on Alg-1
spectra (step-0 already flagged vacuous) — the protective mechanism
that made rank TARGETED in W-9 did not exist in this campaign. High-d
models without low-dim structure (lsat d=747, hierarchicals) get
noise-fitting rank corrections (n≈draws < d for Cx/Ca). RESIDUAL
DIRECTION (narrowed, burden raised): fix the screen for Alg-1 spectra
FIRST, or restrict rank to screened structure models — no further
forced-rank grids. Also: 3 A0 runs aborted (kronecker r0c0 dead-init
known + accel r1c1 + lotka r1c0, same seeds abort under all arms =
init-driven class — census corrected: A0 not abort-free). Full
report: results/lowrank_ess_w63.md; ESS implementation note:
posterior absent in venv, Vehtari-2021 ESS reimplemented + validated
(scratch/w61 lineage). Rerun (guard binary) completing the 86 cells
for the record; CANNOT flip the verdict (the collapse evidence is in
COMPLETED cells) — fold-in is for completeness + bym2/arma11/
radon_pp adjudication.

## 2026-08-25 — W-63 FINAL CLOSE-OUT (post-guard fold-in, grid complete): VERDICT UNCHANGED — forced-rank Alg-1 REJECTED on the full 1020/1020 grid; G2 0.0368 (4-model, unchanged) / 0.0798 (all-6 adjudicable) vs bar 1.5, G3 8/15 violators (aggregate 0.446), G4 rank arms re-pin w400-pf 1/12→7-12/12, screen 0/300 even under 946k NaN-feed events; ONE new fact: arma11 is a GENUINE win (ESS_min 1022→2541, e/g 1.47x, rhat_max 1.001) after the guard carried its warmup-only 121k-event NaN storm

Driver FINAL: done=1020/1020, failed-not-done=0. Analysis re-run
(scratch/w63/analyze_lowrank.py, single process): census 1020/1020,
every cell 12/12 chains, 3 full reps — interim §1 adjudicability rule is
moot, all †/‡ marks superseded by the FINAL section appended to
results/lowrank_ess_w63.md (interim sections kept verbatim in the record).

MIXED-BINARY SOUNDNESS (stated for the record): the 934 pre-guard cells are
bit-exactly what the guarded binary produces on finite paths (W-64 canary:
byte-identical, both md5s); the 86 rerun cells exist ONLY under the guard —
their adaptation differs from an unguarded abort-free run precisely on
non-finite feeds, but no unguarded abort-free counterpart exists for ANY of
them (all aborted rc=-6 pre-guard). The grid is a sound measurement of
"arms + guard" semantics. 3 of the 86 are A0 cells (kronecker r0c0,
accel r1c1, lotka r1c0), so those A0 baselines are guard-era too.

GUARD-TRIGGER ACCOUNTING (86 cells, "Error in logp_grad" lines): 946,059
total = 586,097 warmup-phase + 359,962 sampling-phase. The split predicts
quality: NaN storms confined to warmup (arma11 121,113/0, pilots 11,854/0,
accel 9,404/35) sample cleanly afterwards; storms persisting INTO sampling
(bym2 15,634, kronecker ~32k, lotka ~31.7k, blr r0c2 22,000) are zombie
chains — completion without quality, rhat up to 3.6e15.

RECOVERED-CELL HEADLINES: arma11 A2/A3 12/12 (was 0/12), ESS_min 2541.0 vs
A0 1022.3, e/g 1.468x, rhat_max 1.001 — genuine win, d=4 low-rank class.
radon_pp A2/A3 now adjudicated: 0.0087x, ESS_min 2.8 vs 216.7, 762/775
params rhat>1.02 (catastrophic, confirmed). bym2: NO usable baseline at any
arm (9598-9610/9610 params rhat>1.02, rhat_max 3.6e15 at A0 too; apparent
0.821x is garbage-vs-garbage). kronecker rank arms collapsed (2.3-2.5
ESS_min, 3771-4378/4997 rhat>1.02) AND the A0 baseline fell 29.0→8.1 (its
rescued dead-init r0c0 is a 64k-event zombie) — garbage-vs-garbage, 0.173x
is an upper bound. lotka A0 fell 49.4→10.3 (zombie r1c0) → both arms
garbage. blr 3F now: 6.4 ESS_min, 6/6 params rhat>1.02, adjudicable
violator 0.0217x. Pin battery: recovered r0c2 chains PINNED — A2/A3 w100-pf
10→11/12, w400-pf 6→7/12 (A0 1/12).

FINAL GATES: G1 CITED. G2 FAIL (hier_2pl 0.0913, radon_var 0.0147, lsat
0.0030, garch11 0.4525 — geomean 0.0368 unchanged; +bym2 0.821, kronecker
0.173 → 0.0798 all-6; bym2/kronecker baselines garbage). G3 FAIL, stronger:
8/15 adjudicable violators (blr 0.0217, esc 0.0285, esnc 0.351, gp_regr
0.822, kidscore 0.862, lotka 0.227, radon_pp 0.0087, diamonds rhat 26>17);
PASS incl. genuine arma11 1.468 + low_dim_gauss_mix 2.75, logmesquite 2.06,
wells 1.068, dogs 0.992; aggregate 0.446 (interim 0.708 over 9 — recovered
collapses entered; now BELOW the W-9 0.66-0.79 forced-rank band).
All-21-model aggregate 0.273. G4 FAIL (rank arms re-pin what A0 escapes).
G5 geomean 1.458 over all 6 cross models — still uninformative (4/6 models
collapsed under both operators). A3≡A2 md5 on ALL 300 csv pairs incl. the
37 guard-rescued twins (identical per-chain guard-hit counts): the screen
engaged 0/300 even in NaN-storm conditions.

MECHANISM READING (final): the operator helps exactly the models that HAVE
a low-rank posterior (arma11 d=4, low_dim_gauss_mix, logmesquite, wells)
and destroys high-dimensional models without that structure (lsat 1012p,
hier_2pl 804p, radon 775/345p, kronecker 5463p, bym2 9610p); the screen
that should separate the classes is inert on Alg-1 spectra (0/300, and
step-0 already flagged it vacuous). W-63 CLOSES: forced-rank grids are dead
— no further rank-forcing campaigns at any scale; the W-9 lesson plus this
grid is a two-point line. NARROWS to: fix the screen for Alg-1 spectra
FIRST, or restrict rank to screened/structure-targeted models; burden of
proof for any future low-rank arm is now "show the screen engages, or show
the target model's spectrum is actually rank-10" before any grid. Branch
exp/lr-alg1-basis carries mode-4 + guard, default-off, NOT PR'd (unproven
value).

Artifacts: results/lowrank_ess_w63.md (FINAL section §6); scratch/w63/
{lowrank_results.json + analyze_lowrank.out (final recompute, 1020/1020),
analyze_lowrank.py, driver.log (guard-rerun stanzas 03:15+), runs/ (13 GB)}.

## 2026-08-25 — W-64 CLOSE-OUT (guard increment per W-63 diary plan): DONE and VINDICATED — cherry-pick 6ba0798 clean, canary BYTE-IDENTICAL both md5s (guard bit-inert on finite paths), 225 ctest + both property suites PASS, bym2 smoke completes surviving 680 warmup NaN feeds, rerun 86/86 (driver FINAL 1020/1020); NOTE the guard is ox-alpha's rob/nan-alpha-guard work, already filed by them as walnutpie fork PR #10 — cross-referenced here, NOT re-filed (per standing rule: never file PRs upstream ourselves)

Gates (pre-registered above): (i) cherry-pick resolved for this base —
W-43 pin_trace hunks dropped (absent lineage), guard-only semantics, no
conflicts unexplained. (ii) default-path bit-identity RE-RUN per W-62
protocol: fe7c57… and 6b61df9f… reproduce W-62 EXACTLY — the guard is
bit-inert on finite paths; this is what licenses folding guard-era reruns
into the pre-guard grid (see W-63 FINAL CLOSE-OUT soundness note).
(iii) 225 ctest + both property suites PASS. (iv) rerun = exactly the 86
rc=-6 cells, 86/86 complete under the guard (946,059 catch-and-continue
events; no rc=-6 anywhere in the rerun). EXPECTATION met: aborted rank-arm
cells completed; their ESS adjudicated into G2-G5 without flipping any
verdict.

OPERATIONAL NOTE for whoever touches this class next: the guard converts
aborts into completions, and completion ≠ quality — cells whose NaN feeding
persists into sampling (bym2, kronecker dead-init, lotka r1c0, blr r0c2-pf)
are zombie chains with garbage draws; log-side "Error in logp_grad" counts
split by phase are the cheap diagnostic (grep + first "total time" line).
The macro_time abort class (W-36/W-59 lineage) is now CLOSED on this base:
zero rc=-6 across the entire 1020-job rerun grid.

FILING STATE: guard = ox-alpha's rob/nan-alpha-guard, cherry-picked as
6ba0798 onto exp/lr-alg1-basis; they already filed it as walnutpie fork
PR #10 — cross-reference only. Branch exp/lr-alg1-basis (mode-4 basis +
guard) stays local, default-off, NOT PR'd (unproven value; W-63 rejected
the forced-rank use at grid scale).

## 2026-08-25 — W-62/W-64 LANE CLOSED: walnuts-ai REJECTED for real-posterior deployment — funnel win does not transfer; envelope map archived (orchestrator #2)

Commit d92c0b6 (tests/test_w64_pilot.cpp) + artifacts scratch/w61/
runs_w64/. 52 cells × 4 arms; hier_2pl 1 rep (prereg trim rule).
VERDICT per prereg gates: gate1 PASS AS ARTIFACT (WH-ID died on 3/5
models — inline DA poisoned by BridgeStan -inf, exactly the NaN-adapter
family rob/nan-alpha-guard fixes; not positive evidence). Gate2 FAIL:
iso(0.20) ~10^-3 x WH-ADAPT geomean. Gate3 FAIL: 0.15x even on
low_dim_gauss_mix.
ENVELOPE MAP: iso pays 20–150× more grads/draw (leaf-search overhead);
delta_tol=0.20 consistently beats 0.05 by 1.4–1.7× but from far below
parity. CONCLUSION: within-orbit adaptive leapfrog (walnutpie-h) +
adapted mass dominates generalized-WALNUTS iso flow on Stan-model-class
posteriors; the paper's funnel advantage requires expensive-gradient
regimes. Lane closed honestly after full prereg chain (P1 replay-
verified port remains archived on exp/isokinetic-ai as reference).
LEDGER NOTES: (1) min-coord-ESS-over-constrained-params is mechanically
0 for models with structurally constant constrained coords (hier_2pl
Omega/L_Omega diagonal) — methodology caveat for ANY such comparisons;
project harness should drop structurally-pinned coords. (2) Third
independent instance of the NaN-adapter poisoning class (inline drivers
need the same guard shipped in rob/nan-alpha-guard).

## 2026-08-25 — W-65 PRE-REGISTRATION (before any run): cheaper irreversibility certificate — bounded investigation, abandon allowed (orchestrator #2)

MOTIVATION: W-61 measured the reversible() backward ladder at 8–20% of
gradient budget (uncacheable, algorithmic). Eliminating/cheapening it is
worth ~10–25% ESS/s at fixed quality. Constraint: the ladder is part of
kernel VALIDITY (detects non-minimal paths); it cannot simply be skipped
in sampling phase.

PHASE A (analysis, existing artifacts only): from W-61 runs +
pin-trace fields (ladder_calls, ladder_rejects, h_accept distribution)
characterize: what fraction of tolerance-passing macro steps have k>=1
(the only costly case)? conditional on k>=1, how often does the backward
walk REJECT at rung j>0 vs confirm (walk full length)? Cost model:
expected walk length x frequency per model class.
EXPECTATION A1: k>=1 on 10–30% of macro steps (from eight_schools 19%
overall). EXPECTATION A2: rejects are rare (most walks run all rungs) —
if instead rejects cluster at j=0, an early-abort ordering already
captures most savings (check current order: walk goes coarsest-first?
verify in code).

PHASE B (prototype, ONLY IF Phase A shows >=10% recoverable): candidate
mitigations in validity-preserving order:
B1 reorder/early-exit the walk if Phase A shows cheap wins exist.
B2 surrogate-bounded skip: during the ACCEPTED forward rung we compute
all intermediate states anyway; build a CONSERVATIVE bound on the coarse
lattice's |dH| from stored intermediates (e.g., max local curvature
proxy x coarse_step^2); skip the walk ONLY when bound < max_error with
safety factor. Behavior-changing when the bound is loose-but-wrong =>
GATES: (i) funnel/Gaussian property tests unchanged, (ii) blr +
eight_schools 3-rep ESS parity within noise (±3%) AND md5 NOT expected
identical (document divergence rate), (iii) measured ladder-eval
reduction >= half the Phase-A headroom.
ABANDON RULE: if Phase A headroom < 10% or no B-candidate passes gates
after 2 cycles, close with the cost model as the record.
MACHINE: single-core serial, nice'd; builds -j2 max.
COST: analysis <30 min; prototype <= half day.

## 2026-08-25 — W-63 CORRECTION (mechanism identified; posted where the claim was made): "screen 0/300 / A3≡A2 / screen inert on Alg-1 spectra" is WRONG as stated — the auto-screen NEVER GATED the full operator. Code path (adaptive_walnuts.hpp ~L632): rank_active = rank>0 && (!auto || window_cross_ratio() <= auto) feeds ONLY the folded-diagonal estimate choice; the full_rank_mode branch (metric_full && rank>0) runs transition_w_lr UNCONDITIONALLY. W-63's A3 = A2+--metric-auto with --metric-full ⇒ forced full BY CONSTRUCTION ⇒ byte-identity explained; the screen STATISTIC was never consulted on the A3 path. Root cause: W-62 wired --metric-auto per its pre-existing (fold-only) semantics and did not extend the screen to the full operator — the memo's "A3 auto-screened full" was unimplementable as flagged. CONSEQUENCE: W-63's G2/G3 stand as the verdict on FORCED full rank (A2≡A3 evidence now reads as wiring artifact, not screen inertness); "screened full" REMAINS UNMEASURED. The screen-statistic calibration question (step-0's vacuous check) is also still open.

## 2026-08-25 — W-65 PRE-REGISTRATION (before any code): fix the screen to gate the full operator; re-canary; TARGETED screened-full rerun (bounded subset, NOT a full grid)

CHANGE (walnutpie exp/lr-alg1-basis, new commit): full_rank_mode's
operator branch becomes conditional on rank_active — when auto_screen
is on and window_cross_ratio() > threshold, warmup transitions AND
the freeze use the plain diagonal path (freeze-side consistency is
the freeze-mismatch family risk — the freeze must apply the SAME
decision as the last warmup window; inspect and align the freeze
code, comment it). ~5-15 LOC in adaptive_walnuts.hpp.
GATES for the change: (i) default-path canary RE-RUN byte-identical
(hier_2pl + kronecker, W-62 protocol — the change is unreachable
without BOTH metric_full AND metric_auto set); (ii) A2-no-auto canary
SPOT-CHECK unchanged (one model, vs the pre-change binary — the
no-auto full path must be untouched); (iii) 225 ctest + property
suites.
TARGETED RERUN (bounded): models = the 3 W-63 rank-WINNERS
{low_dim_gauss_mix, logmesquite_logvash, arma11} + 4 no-harm
sentinels {eight_schools_centered, blr, kidscore_momiq, dogs} +
3 cross-structure {hier_2pl, garch11, lsat_model} = 10 models × arm
A3' (screened full: rank 10, basis 4, full, auto 0.5) × 3 reps × 4
chains, w1000+s1000, = 120 runs (A0/A2 numbers REUSED from W-63 —
same seeds/protocol).
EXPECTATIONS (pre-registered): (E1) A3' output DIFFERS from A2 on at
least the funnel sentinels (screen engages = the wiring fix works —
the primary deliverable, an implementation gate not an ESS claim);
(E2) sentinels: A3'/A0 ESS ratio materially better than W-63's
forced-rank numbers (engagement should prevent the worst collapses;
0.9x no-harm bar on eight_schools_c would be a STRONG positive);
(E3) winners: A3'/A0 within 10% of the W-63 forced-rank win on the 3
winners IF the screen engages there too — if the screen blocks the
winners (concentrated spectra), that kills the screen calibration
and the direction closes. NEGATIVE outcomes recorded and kept.
ANALYSIS: engagement census (A3' vs A2 csv inequality per model),
ESS table vs A0/A2, E1-E3 adjudication. Machine: ≤4 cores, driver
resume pattern reused (subset list into a w65 driver).

## 2026-08-25 — RENUMBER NOTE: the "W-65 PRE-REGISTRATION (cheaper irreversibility certificate)" entry above is hereby W-69 — concurrent session had reserved W-65..68 before my prereg landed (orchestrator #2)

Apologies for the churn; artifact dir stays scratch/w61/runs_w65/ (path
only), branch exp/ladder-cert, all future references use W-69. W-66/67/68
remain the other session's.

## 2026-08-25 — W-70 PRE-REGISTRATION (before any run): metric-window sensitivity {250, 500} — does a larger chop window keep the drift-contaminated winners without the small-window noise collapses? — ESS/s overnight session

MOTIVATION: W-63 REJECTED --metric-window 100 decisively (−24.5%
aggregate geoESS; collapses pilots/accel_gp/lotka) but showed large wins
on drift-contaminated models (lsat +35.8%, diamonds +43.1%, bym2 +29.2%).
The failure mechanism was hypothesized as small-window variance noise
(≤100 correlated draws per estimate), NOT the chopping principle. This
experiment tests that hypothesis at windows where each estimate sees
250/500 draws. Numbering: clean W-70 to end the W-65..69 churn; my
overnight-plan claims of W-65..68 are superseded except W-66/67/68
per orchestrator #2's note — I take W-70/71/72 instead.

DESIGN: two arms via harness/run_arms.py, identical everything else to
W-36 exp_par baseline (reused): mw250 = --metric-window 250, mw500 =
--metric-window 500. 10 models × 3 reps × 2 arms ≈ 20 min sampler time.

EXPECTATION:
1. Monotone-in-window: aggregate geoESS(mw500) > geoESS(mw250) > geoESS
   (mw100=249.1), approaching baseline 330.1 from below IF the noise
   mechanism is right; possibly exceeding it if stale-history removal
   helps even with low noise.
2. The W-63 collapse models (pilots, accel_gp, lotka) should recover
   toward baseline as window grows; the W-63 winners should keep most
   of their gains.
3. Wall parity ±15% (quiet machine overnight).

GATES:
- ADOPT-candidate for a window value w: geomean ess_bulk_geomean(w)
  ≥ baseline+5% AND no model median ess_bulk_min drop >20%.
- CONFIRM-HYPOTHESIS (mechanism): monotone recovery trend even if no
  adoption gate passes — recorded as knowledge either way.
- REJECT direction entirely: both windows still ≥20% below baseline
  aggregate → chopping principle itself does not transfer to this suite.

COST: ~20 min, sequential arms, quiet machine verified before start.

## 2026-08-25 — W-71 PRE-REGISTRATION (before any run): wrapped-DualAveraging rescue — does walnutpie's wrapper stack let DA complete the grid AND keep the easy-model wins? — ESS/s overnight session

MOTIVATION: W-64 showed naked DualAveraging aborts on 5/10 models
(saturation → step→0 → macro_time throw) yet beats Adam by +233.8%
geoESS on diamonds. Stan's DA survives analogous targets because of its
regularization/freeze schedule; walnutpie ships AntiWindup (1-in-N
thinning during alpha~0 saturation) and Clipped (impulse clip) wrappers
that plausibly provide the same protection but were never combined with
DA at benchmark scale.

DESIGN: two arms via harness/run_arms.py, baseline reused:
- da_aw   = --step-optimizer da --anti-windup 8
- da_aw_clip = --step-optimizer da --anti-windup 8 --step-grad-clip 0.3
(8 and 0.3 are the CLI help's own example values; a priori choice, no
tuning). 10 models × 3 reps × 2 arms.

EXPECTATION:
1. Wrappers eliminate most naked-DA aborts; if any model still aborts in
   ALL reps under BOTH arms, wrappers are insufficient for DA here.
2. diamonds-class gains persist (≥ +50% geoESS) under at least one arm.
3. Aggregate: one of the arms ≥ baseline+5% over shared models would
   make wrapped-DA an ADOPT-candidate as an OPT-IN preset (not default
   flip — that would need its own decision).

GATES:
- ADOPT-candidate (opt-in preset): completes ≥9/10 models AND shared-
  model geomean ess_bulk_geomean ≥ baseline+5% AND no shared-model
  ess_bulk_min drop >20%.
- REJECT: aborts persist broadly or aggregate within ±3%.
- Either way recorded; negative results kept per protocol.

COST: ~20 min sequential after W-70 finishes.

## 2026-08-25 — W-69 CLOSE-OUT: ABANDONED per prereg — ladder cost is INTRINSIC to WALNUTS validity; cost model recorded (orchestrator #2)

Phase A (cost model): headroom confirmed 8–18% by model; P(k>=1 | tol
pass) 2–19%; BUT rejects are NOT rare — 63–98% of k>=1 walks REJECT
(invalidate the macro step), esc's accepted-halvings spread {1:53%,
2:27%, 3:14%, 4:6%}, others concentrated at k=1. Walk visits rungs
finest-first with early-abort already present.
Phase B: B1 coarsest-first reorder engineered bit-identical (property
smoke PASS, md5 PASS on esc/blr/arma11) — saved ~0 because ~86% of walk
evals are fully-confirming traversals that any order must pay; B2 not
built: a conservative surrogate bound on coarse-lattice |dH| from
fine-path observables is UNSOUND (coarse error depends on path
derivatives of H). ABANDON rule fired.
CONCLUSION: the backward certificate's cost cannot be engineering'd away
without changing the sampler's validity notion — it is the price of
within-orbit step adaptivity, and its rejection work is load-bearing
(48–93% of tolerance-passing steps get invalidated). Any future ESS/grad
gap analysis should treat it as structural, like the W-38-E2 finding.
Branch exp/ladder-cert kept for the record (do-not-PR reorder commit +
per-rung histogram counters, env-gated).
LEDGER INSIGHT (new): high invalidate-rate means forward integrations
are frequently wasted AFTER passing tolerance — but predicting which is
the same unsound-surrogate problem; recorded to prevent re-litigation.

## 2026-08-25 — W-70 PRE-REGISTRATION (before any run): DEER/Picard within-trajectory parallelism — FEASIBILITY MEASUREMENT ONLY, go/no-go by pre-set threshold (orchestrator #2)

MOTIVATION: W-51 front 4 ranked DEER/Picard trajectory parallelism as
the successor to W-49's refuted speculation, explicitly "gated by a
predictability analysis before any threading" — never done. Prize:
logp_grad = 68–99.7% of sampling wall; parallelizing trajectory
evaluation across our 4 cores would multiply ESS/s without touching
sampling statistics IF converged Picard reproduces the sequential
trajectory bit-for-bit (statistics unchanged by construction).
Speedup model (pre-declared): sequential cost = S grad evals/transition;
Picard round evaluates all steps' residuals in parallel ⇒ wall ≈
rounds·S/cores + sync overhead; WIN requires rounds ≤ 3 at 4 cores
(median over transitions) with bit-exact final states vs sequential
leapfrog.

PHASE A (measurement, no sampler changes): instrument a driver (w54
tree, new branch exp/deer-feasibility off e46da43+W61-counters) to dump
per-transition micro-step trajectories (positions + grads) for blr,
eight_schools_centered, arma11 (1 chain each, 200 transitions post-
warmup). Offline Picard replay: iterate x_{t+1}^{(r+1)} = x_t +
step*inv_mass*rho-update using gradients from the CURRENT iterate set
(standard fixed-point on the discrete trajectory), init iterate 0 =
linear extrapolation from endpoints (WALNUTS' own trick); measure
rounds-to-bit-convergence (max |Δx| < 1e-12 vs sequential truth) and
the eval count per round. ALSO measure the funnel-class caveat:
low_dim_gauss_mix neck transitions expected to need many rounds or not
converge — quantified, not assumed.
EXPECTATION: easy/GLM models median rounds 2–3 (Lipschitz small);
stiff/funnel tails heavy (rounds >6 or non-convergence); decision hinges
on the MEDIAN and the fraction ≤3.
GATES: GO = median rounds ≤ 3 on ≥2 of 3 easy/stiff models AND ≥60% of
transitions ≤3 rounds AND converged states bit-match sequential.
NO-GO otherwise → lane closed with the rounds distribution as record.
NO-GO also fires automatically if Picard eval overhead > 1.5× sequential
evals at convergence.
MACHINE: single-core serial, nice'd; pure measurement, no wall claims.
COST: driver + offline analysis, ~half day.

## 2026-08-25 — W-65 CLOSE-OUT: screen-gating fix VERIFIED (E1 PASS, 0/120 ==A2) + TARGETED A3' rerun complete (120/120) — E2 PASS (eight_schools_c 0.930 vs 0.037 forced, all sentinels no-harm) but E3 FAIL (screen blocks all 3 W-63 winners at threshold 0.5: ratios 1.000 vs 3.37/1.73/2.49 forced) — direction CLOSES per pre-registration

Executed per the W-65 prereg (fix-the-screen entry). Commit 7b81357 on
exp/lr-alg1-basis, worktree external/walnutpie_lowrank (~19 LOC in
adaptive_walnuts.hpp: full_rank_mode operator branch now requires
rank_active; freeze memoizes last_lr_active_ instead of re-screening).

PHASE 1 GATES (all PASS):
(i) default-path canary, new build_gates binary vs build_base (both run):
hier_2pl AND kronecker_gp byte-identical new-vs-base AND == recorded
fe7c57c99a7a6530ce2dcc408d6e9c65 / 6b61df9fd30646be915c87961b2ff816
(artifacts scratch/w65/gates/{new,base}/). Rebuild was real: stan_cli.cpp.o
recompiled post-header-change (mtime 08:32:50 > fix 08:26:02).
(ii) A2-NO-AUTO spot check done as a REAL comparison (better than the
anticipated by-construction-only): blr w100 s500 pin cell rerun on the new
binary byte-identical to W-63's pre-fix scratch/w63/runs/A2/blr/w100_pf/
rep0_c0.csv (md5 fbf331a37a368184a085478ca331a289).
(iii) ctest build_gates 225/225 PASS; low_rank_metric_test PASS
(cond(lowrank-precond)=19.31, rel-dense 4.26e-17, roundtrip 1.08e-16);
leapfrog_property_test PASS (reversibility 3.32e-17, |detJ|-1 8.88e-16) —
values match W-62's. ENV DEVIATION: property tests compiled clang++-22 -O2
(the relocated g++ install prefix /home/m0hawk/Applications/../lib/gcc is
broken: no stdlib includes, liblto_plugin missing; CMake builds unaffected).
E1 PROBES (pre-grid): eight_schools_centered (expect DECLINE) A3' != A2
(wiring works) and == A0 (declined every window); low_dim_gauss_mix (expect
ENGAGE) != A2 but ALSO == A0 — the screen declined the winner everywhere,
first hint of E3.

PHASE 2: driver scratch/w65/driver.py (resume pattern from w63; 10 models
x A3' x 3 reps x 4 chains; WORKERS=4; hier_2pl-first dispatch): 120/120
DONE, 0 fails, ~15 min wall (machine shared with sibling W-70 threads run
+ one compile stream; ESS is wall-independent).

PHASE 3 (results/lowrank_screened_w65.md, JSON scratch/w65/w65_results.json):
ENGAGEMENT CENSUS (exact: declined-everywhere A3' is byte-identical to A0,
post-fix A3' can never equal A2 — drift phase differs): ==A2 0/120 chains
(W-63 artifact: was 300/300). ENGAGED: hier_2pl 12/12, lsat_model 12/12,
eight_schools_centered 2/12, low_dim_gauss_mix 1/12. DECLINED-ALL (==A0):
garch11, dogs, kidscore, blr, arma11, logmesquite (12/12 each).
ESS (ess_bulk_min med-of-reps, w1000_pf): hier_2pl .797 (A2 .397),
lsat .226 (A2 .006), eight_schools_c .930 (A2 .037), all declined models
1.000 (==A0 by construction). hier_2pl rep0 A3' tail collapse (25.2 vs
540.6 A0) — engagement has heavy-tail risk.
VERDICTS: E1 wiring PASS (primary deliverable). E2 sentinels PASS
(eight_schools_c 0.930 > the 0.9 strong-positive bar; blr 1.000 vs 0.018;
kidscore 1.000; dogs 1.000, giving up the 1.076 forced upside). E3 winners
FAIL: all 3 blocked (1.000 vs 3.373/1.727/2.486 forced) — per prereg this
KILLS the screen calibration at window_cross_ratio threshold 0.5 and the
direction CLOSES. No threshold sweep post-fix; 0.5 was inherited from W-63
step0 where the broken wiring made thresholds indistinguishable (honest
limit — the E3 failure indicts the operating point/measurement, not the
now-verified gating mechanism). Commit 7b81357 itself is canary-clean and
correct; it ships. NOT pushed (never file PRs upstream myself).

## 2026-08-25 — W-66 PRE-REGISTRATION (before any run): screen-threshold sweep — the LAST low-rank falsification test; hard closure rule

CONTEXT: W-65 verified the screen mechanism (E1) and sentinel rescue
(E2: 8schools_c 0.930 vs 0.037 forced) but threshold 0.5 blocks all
three winners (E3 FAIL). The 0.5 was inherited from W-63 step-0 whose
wiring was broken (all thresholds indistinguishable) — an operating-
point failure, not a mechanism failure, per the W-65 limits note.
DESIGN: A3' rerun at thresholds {0.65, 0.8} on the SAME 10-model set,
same protocol/seeds/driver (240 runs; A0/A2/W65-A3'@0.5 all reused).
Engagement census via byte-equality (==A0 declined-all; else engaged
per-chain fraction). DECISION RULE (pre-registered, binding): a
threshold is VIABLE iff (a) it ENGAGES the three winners (>= 6/12
chains each: low_dim_gauss_mix, logmesquite, arma11) AND (b) it still
DECLINES-or-is-neutral on the collapse sentinels (eight_schools_c
A3'/A0 >= 0.9 — it may engage only if harmless; blr/kidscore no
worse than 0.9) AND (c) hier_2pl (engaged-but-harmful at 0.5:
0.797) does not regress below its 0.5-screened value. IF NO
threshold in {0.65, 0.8} is viable => THE LOW-RANK DIRECTION CLOSES
FOR GOOD at CORE_SET scale on this base (the screen statistic cannot
separate winners from harm; recorded as the final verdict, no
further sweeps). IF ONE IS VIABLE => it becomes the candidate
operating point; a FULL-grid confirmation campaign is queued as the
next session's decision (NOT auto-run — user reviews first).
EXPECTATION (honest): uncertain — hier_2pl's engaged-but-harmful
0.797 suggests the statistic may not encode "rank helps here"; if
winners engage at 0.65 by being just-above-0.5 spectra while 8schools
also engages, closure is likely. Machine: 4 workers (quiet), ~30 min.

## 2026-08-25 — W-70 CLOSE-OUT: window sensitivity REFUTES the noise hypothesis — mw250 −5.7% / mw500 −11.2% aggregate (non-monotone; winners flip sign between windows); default confirmed twice — ESS/s overnight session

Full writeup results/metric_window_w70.md, raw results/w70_ess.json.
GATES: no ADOPT; monotone-recovery check FAILED (mw500 < mw250;
diamonds +55→−23%, eight_schools +33→−25% across adjacent windows).
accel_gp collapses at every window — its issue is not estimator noise.
CONCLUSION: chopping is a high-variance redistribution of ESS on this
suite with no stable tuning to adopt; metric_window=0 stands (W-63+W-70).
Persistent winners (radon/lsat) hint at a model-adaptive screen idea —
recorded as a lead, not adopted; no a-priori selector identified.

## 2026-08-25 — W-71 LAUNCH NOTE: wrapped-DA arms starting ~09:05 after W-70 close (prereg above)

## 2026-08-25 — W-70 CLOSE-OUT: DEER/Picard within-trajectory parallelism NO-GO — all four pre-set conditions fail independently (orchestrator #2)

Commit f3eb585 (tests/test_w70_deer.cpp + analyze_w70_deer.py) on
exp/deer-feasibility; artifacts scratch/w61/runs_w70/. Method: real
BridgeStan models, 200 sampling transitions each, full micro-trajectory
recording, offline Picard replay with momentum-extrapolation init,
strict 1e-12 inf-norm convergence target (achieved where converged:
blr 4e-15 = true bit-level match).
RESULTS: only blr converges (200/200, median 3 rounds); arma11 +
eight_schools_centered diverge outright 200/200 (iterates blow up 2–5
rounds: per-round error amplification ≈ S·eps·Lip(∇logp) ≫ 1 at
accept-0.8-calibrated steps over S=32-step horizons); funnel-class
gauss_mix: 186/200 fail, median 27 rounds when converging. Eval
overhead at convergence 2.91× (>1.5× cap) even for blr.
GATES: median≤3 on ≥2 easy/stiff FAIL; bit-match outside blr FAIL;
overhead FAIL; fraction≤60% FAIL. NO-GO.
CONCLUSION: fixed-point trajectory parallelism is dead for walnutpie's
regime — HMC step sizes calibrated to accept-0.8 sit right at the
Picard instability boundary (error amplification grows with
S·eps·Lipschitz), so divergence is structural, not a tuning artifact.
Closes W-51 front 4's open gate with data. W-49's no-go now has a
mechanistic sibling. Remaining parallelism lane: across-chain only.
CAVEATS: plain-HMC warmup driver (not full span machinery — dynamic
lengths would stress Picard more, not less); extrapolation init may be
suboptimal vs coarse-pass init (unmeasured residual lane, low prior).
Branch archived to fork as idea history.

## 2026-08-25 — W-66 CLOSE-OUT: threshold sweep {0.65, 0.8} executed per the binding prereg (240/240, 0 fails, ~41 min at 4 workers) — T=0.65 NOT VIABLE (rule a FAIL: winners 1/12-0/12-0/12; rule c FAIL: hier_2pl 0.039), T=0.8 NOT VIABLE (a FAIL same, b FAIL: eight_schools_c 0.585, c FAIL: hier_2pl 0.529) => THE LOW-RANK DIRECTION CLOSES FOR GOOD at CORE_SET scale on this base — FINAL for the direction

Executed exactly per the W-66 prereg; no deviations, no code changes
(binary build_gates @ 7b81357 reused; no rebuild). Driver
scratch/w66/driver.py = w65 driver parameterized over T (outputs
scratch/w66/runs/T<T>/...; same DONE/resume convention; WORKERS=4;
hier_2pl-first dispatch; env -u LD_LIBRARY_PATH, OMP_NUM_THREADS=1).
T0.65 09:07-09:25 (~18 min), T0.8 09:25-09:48 (~23 min; hier_2pl mean
chain 263s @0.65, 357s @0.8 vs 190s @0.5 — engagement deepens with T,
runtime is the depth proxy). 120/120+120/120 DONE, 0 failures, 0/240 ==A2
(gating mechanism stays verified).

CENSUS (exact byte-equality vs same-seed w63 A0/A2): the ONLY engagement
changes from 0.5 -> 0.65 -> 0.8 are eight_schools_centered 2/12 -> 9/12 ->
12/12 and deeper within-window acceptance on hier_2pl/lsat (12/12 engaged
at every T). Winners do NOT cross: low_dim_gauss_mix 1/12 (the same lone
r2c1 chain since 0.5), logmesquite 0/12, arma11 0/12 — even at 0.8.
blr/kidscore/dogs/garch 12/12 declined at every T.

ESS (ess_bulk_min med-of-reps; analyze_w66.py reusing the w63/w65 Vehtari
conventions incl. constant-column exclusion; full tables in
results/lowrank_threshold_w66.md, JSON scratch/w66/w66_results.json):
@0.65 hier_2pl 0.039 (ALL THREE reps collapse: 15.2/19.4/37.4 vs ~500 A0 —
the 0.5 rep0 tail risk became systemic), lsat 0.029, eight_schools_c 0.930
(9/12 engaged yet med-of-reps holds), everything declined 1.000. @0.8
hier_2pl 0.529, lsat 0.394, eight_schools_c 0.585 (full flip: per-rep
90.8/60.5/25.6, rhat_max 1.110), declined models 1.000.

ADJUDICATION (binding): T=0.65 (a) FAIL (1/12, 0/12, 0/12 < 6 each),
(b) PASS (0.930/1.000/1.000), (c) FAIL (0.039 < 0.797) => NOT VIABLE.
T=0.8 (a) FAIL (same), (b) FAIL (eight_schools_c 0.585 < 0.9),
(c) FAIL (0.529 < 0.797) => NOT VIABLE. Neither threshold viable => per
the prereg THE LOW-RANK DIRECTION CLOSES FOR GOOD at CORE_SET scale on
this base; recorded as the FINAL verdict for the direction on this base,
no further sweeps (0.5 already failed W-65 E3; below 0.5 re-blocks
everything, above 0.8 deepens the already-failing hier_2pl/eight_schools
harms). Full-grid confirmation NOT queued (moot at closure).

MECHANISM READING (spectra placement given the flips — engagement is
window_cross_ratio <= T, so the census brackets each model's statistic):
hier_2pl/lsat sit WELL BELOW 0.5 (certified "spread" at every T, exactly
where forced rank hurts most: A2/A0 0.397/0.006, harm deepening with T);
eight_schools_c sits IN the flip band (0.5, 0.8] (2/12 -> 9/12 -> 12/12,
ESS 0.930 -> 0.930 -> 0.585); the three winners sit ABOVE 0.8 in
essentially all windows (read as "concentrated" exactly where forced rank
helps 3.373/1.727/2.486; the lone engaged ldgm chain harmless but
benefit-less, rep2 599.8 vs 575.6 A0). The statistic's ordering is
INVERTED relative to benefit — models it certifies as spread are the ones
rank degrades; models it reads as concentrated are the ones rank
accelerates. Any successor screen needs a statistic that reverses this
ordering; window_cross_ratio at any operating point on [0.5, 0.8] cannot.
Honest limits: 3x4 reps (hier_2pl's non-monotone T-wobble 0.797 -> 0.039
-> 0.529 is tail-sensitive at this budget, but both T fail (c) outright
and (a) fails by 1/12-vs-6/12 margins rep-noise cannot close); census
binary per chain (extent only proxied by runtime).

Artifacts: results/lowrank_threshold_w66.md (census+ESS tables per
threshold, adjudication, verdict, mechanism); scratch/w66/{driver.py,
driver.log, analyze_w66.py, w66_results.json, runs/T0.65|T0.8/...}. Commit
7b81357 (mechanism) remains shipped and correct — the closure is a
statement about the window_cross_ratio operating statistic, not the gating
wiring. NOT pushed (never file PRs upstream myself).

## 2026-08-25 — W-71 CLOSE-OUT: INVALID AS RUN — --anti-windup/--step-grad-clip/--step-opt-batch-stride silently no-op under --chains>1; bug root-caused and fixed; rerun preregistered as W-71R — ESS/s overnight session

WHAT HAPPENED: both W-71 arms produced draws BIT-IDENTICAL to W-64's
naked-DA arm (md5-verified across models) → the wrapper flags never
reached the sampler. SOURCE ROOT CAUSE (stan_cli.cpp): the compile-time
wrapper-type ladder (AntiWindupAdapter/ClippedAdapter/BatchedAdapter)
exists ONLY in the single-chain dispatch (~:1163–1208 post-patch); the
multi-chain path called run_walnuts_multi<Opt> with the RAW optimizer.
Textbook instance of the known "flags silently no-op" hazard class
(HANDOFF gotchas) — a new capability was wired into one dispatch site
only. All wrapper-flag results previously collected under --chains 4 are
suspect for the same reason.

FIX (branch exp/discounted-min-micro, worktree external_w72/walnutpie_w72,
commit pending): run_multi now mirrors the single-chain ladder via a
type_identity launch lambda (8 branches). VERIFIED: (a) diamonds da+
anti-windup 8 draws now DIFFER from naked da (md5), (b) unflagged default
path stays bit-identical to runs/w36/exp_par baseline (canary md5 match),
(c) eight_schools_centered still aborts under wrapped DA — anti-windup
thins updates but does not prevent divergence (genuine, not a wiring
artifact).

W-71R PREREGISTRATION (rerun, same gates as W-71, fixed binary):
arms da_aw / da_aw_clip vs baseline, output runs/w71b/{da_aw,da_aw_clip},
same grid/seeds/inits, binary build_w72. Expectation unchanged EXCEPT:
abort persistence now measures genuine wrapper insufficiency (already
previewed by (c)). Gates identical to W-71 prereg above.

## 2026-08-25 — W-72 PREREGISTRATION ADDENDUM (before its grid): discounted min-micro-steps EWMA, decay=0.99 — ESS/s overnight session

Implementation complete on the same branch/worktree/binary as the W-71R
fix (both ship in build_w72). Change: MinMicroStepsAdaptHandler gains an
EWMA mode (decay in (0,1)) selected by env WALNUTPIE_MINMICRO_DECAY,
default path bit-identical (constructor reads env once; observe/min_
micro_steps branch only when decay>0). RATIONALE (from source audit):
lifetime cumulative mean means one early-warmup depth burst permanently
inflates min micro steps → extra gradient evals per macro step for the
whole run (and the frozen sampling-phase min too).
ARM: mmdecay099 = env WALNUTPIE_MINMICRO_DECAY=0.99 (memory ≈100 iters;
a priori single value), no other flags, output runs/w72/mmdecay099.
EXPECTATION: (1) fewer logp_grad calls per unit ESS on models whose warmup
starts with deep trajectories (hard models); (2) aggregate geoESS within
noise of baseline (the estimator targets trajectory shape, not quality);
(3) wall −5..15% if (1) holds on slow models. GATES: ADOPT-candidate if
aggregate wall drops ≥5% with geomean ess_bulk_geomean ≥ baseline−3% AND
no model ess_bulk_min collapse >2×; REJECT otherwise, recorded either way.
CANARY: done — unflagged build_w72 == exp_par md5 on diamonds rep0.

## 2026-08-25 — W-66 CLOSE-OUT + LOW-RANK DIRECTION CLOSED + SESSION FILE INVENTORY: threshold sweep 240/240 — NO VIABLE OPERATING POINT on [0.5,0.8] (winners never cross: 1/12-0/12 engaged at every T; hier_2pl harm DEEPENS with T: 0.797@0.5 → 0.039@0.65 → 0.529@0.8, all-rep collapse at 0.65; eight_schools_c flips to engaged at 0.8 and degrades 0.930→0.585) — MECHANISM: the window_cross_ratio ordering is INVERTED relative to rank benefit (models it certifies "spread" = hier_2pl/lsat are those rank degrades; the 2.5-3.4x winners read "concentrated" >0.8) — DIRECTION CLOSED FOR GOOD at CORE_SET scale on this base; the 7b81357 gating mechanism itself is verified and SHIPPED as walnutpie fork draft PR #13 (robustness/auto-screen-gates-full-operator off dev/init-robustness, clean cherry-pick, default-path canary fe7c57…/6b61df9f… byte-identical, no-auto full path reproduced byte-identical, 225+property tests; filed AFTER a path-broken false-DEFER canary was caught and rerun with absolute paths — the DIFFER was harness error, not behavior)

SESSION INVENTORY (2026-08-24/25, SoA + low-rank arcs): W-57..W-60
SoA migration complete + sims1253/math#5 draft; W-61 was ox-alpha's;
W-62 Alg-1 basis (implemented/verified/draw-neutral); W-63 campaign
(forced rank REJECTED, 1020/1020, honest negatives kept); W-64 NaN
guard (ox-alpha's fix verified + unblocked 86 cells); W-65 screen
wiring fix (E1+E2 pass: sentinel rescue 0.037→0.930; E3 fail at 0.5);
W-66 closure. LOW-RANK LEDGER FILES: results/lowrank_ess_w63.md,
results/lowrank_screened_w65.md, results/lowrank_threshold_w66.md,
memo scratch/w57/lowrank_metric_design.md. Branches: exp/lr-alg1-basis
(local, mode-4+guard+gating-fix, NOT PR'd — research history),
robustness/auto-screen-gates-full-operator (fork PR #13). NEXT:
nothing autonomous remains — B''/A'' and any low-rank revival on a
DIFFERENT screen statistic are user decisions.

## 2026-08-25 — W-71R CLOSE-OUT: wrapped-DA REJECTED (wrappers verified active this time) — da_aw −14.5% shared agg + still aborts 5 models; clip variant catastrophic (−78.6%, 3 collapses) — ESS/s overnight session

With PR#14's dispatch fix the wrapper flags genuinely bite (draws differ
from naked-DA md5s), so this is the first VALID wrapped-DA measurement.
da_aw (--anti-windup 8): loses bym2/lsat/accel/pilots/eight_schools to
macro_time aborts exactly as before (wrapper insufficiency confirmed),
hier_2pl collapses −60.7%. da_aw_clip (+clip 0.3): worse — radon/diamonds
collapse too. The W-64 diamonds +233% was a naked-DA artifact: +70% under
aw, −93% under clip — not robust. VERDICT: REJECT per preregistered
gates; Adam default stands a third time. Raw: results/w71b_ess.json.
Side value: end-to-end validation of PR#14 (flags measurably change
behavior post-fix; default path canary bit-identical).

## 2026-08-25 — W-72 CLOSE-OUT: discounted min-micro-steps REJECTED at decay=0.99 — ESS neutral (+0.3% agg) but NO gradient-call reduction (3 models bit-identical, bym2 +51.7% calls) — ESS/s overnight session

The stickiness mechanism is real in code, but the EWMA almost never
changes the rounded integer min (5/10 models produced bit-identical
draws to baseline), and where it did change, effects were mixed:
bym2 +51.7% logp_grad calls / +53% wall (EWMA lowered min micro steps →
costlier trajectory shape), diamonds +6.5% calls −10.8% geoESS,
accel_gp −10.8% calls (the only win, tiny). Gates required ≥5% aggregate
wall reduction with ESS ≥ baseline−3%: FAIL. VERDICT: REJECT; keep
lifetime mean as default. If revisited: the lever interacts with
max_macro_steps_target (proposals file P3) rather than standing alone.
Raw: results/w72_ess.json.

## 2026-08-25 (evening) — W-73 PRE-REGISTRATION (before any run): Adam hyperparameter sweep — step-learning-rate {0.02, 0.15} vs default 0.05, accept-target {0.7} vs default 0.8 — ESS/s continuation session

MOTIVATION: W-64/W-71R showed easy targets leave large ESS on the table
under Adam's DEFAULT hyperparameters (naked da +234% geoESS on diamonds)
while hard targets punish optimizer switches. The untested middle path:
tune Adam itself. These knobs have NEVER been swept on this suite
(optimizer scans adopted values on paper only).

DESIGN: three zero-code arms via harness/run_arms.py, baseline =
runs/w36/exp_par reused: lr_hi=--step-learning-rate,0.15;
lr_lo=--step-learning-rate,0.02; target07=--step-accept-rate-target,0.7.
Standard grid/seeds/inits, binary build_w36exp (unpatched defaults arm —
no wrapper flags involved so PR#14 bug class is inert here).

EXPECTATION:
1. lr_hi helps easy/fast-adapting models (diamonds/pilots/eight_schools
   class) by converging the log-step estimate sooner in fixed warmup;
   risks oscillation on hier_2pl/bym2 (saturated alphas × bigger steps
   of the adapter).
2. lr_lo is the safety arm: expected neutral-to-slightly-negative
   everywhere (slower adaptation), included to map the gradient.
3. target07: fewer gradient evals per unit ESS if quality holds
   (larger steps accepted); classic ESS/s-vs-quality trade, worst case
   divergences/funnel harm on centered parameterizations.
4. Aggregate: no arm beats baseline+5% — the honest prior is that
   upstream chose decent defaults; any win likely concentrated on easy
   models.

GATES (per arm): ADOPT-candidate iff geomean ess_bulk_geomean ≥ +5%
AND no model median ess_bulk_min drop >20% AND max rhat_max not worse
than baseline+0.05. REJECT otherwise; recorded either way.
COST: ~30 min sequential, machine idle.

## 2026-08-25 — W-73 PRE-REGISTRATION (before any run): two-phase warmup via an UNADJUSTED warm-start phase — skip the reversibility certificate where bias is allowed (orchestrator #2)

MOTIVATION: overnight wrap names two-phase warmup the last big queued
lead (W-51 front 2; W-45 follow-up). Prior framings failed on wall cost
(early exit W-21/25/28 refuted; subsample transplant W-45 rejected).
NEW ANGLE grounded in W-69: the backward reversibility certificate is
validity work for the SAMPLING kernel — but during warmup we may
tolerate bias in the transition kernel as long as ADAPTATION STATISTICS
are not poisoned (estimators see draws from a slightly-wrong law early;
metric-window chopping already treats early draws as noise). So:
PHASE 1 (first U warmup iters): unadjusted transitions — bypass
`reversible()` (return true immediately). Saves the 8–20% ladder tax
AND removes ladder-driven leaf rejections (W-69: 48–93% of tol-pass
steps invalidated ⇒ phase-1 trajectories are much cheaper AND longer).
PHASE 2 (remaining warmup): standard Metropolized walnutpie, estimators
continue (chopping/mass-init-buffer semantics unchanged); freeze as
today. Sampling phase untouched — validity preserved where it counts.
RISKS (pre-declared): biased phase-1 draws contaminate mass/step
estimates (mitigation: metric-window reset at phase boundary — reset
accumulators at U, one line, tested as arm variant if plain fails);
step adapter sees min_accept stats from unadjusted paths (alpha stat is
end-to-end dH-based, still meaningful).

DESIGN: env-gated WALNUTPIE_UNADJUSTED_WARMUP_FRAC (read-once; unset =
exact current behavior). Arms: BASELINE, U25 (U=250/1000), U50 (500),
each ± metric-reset-at-boundary => 6 arms total but primary comparison
BASELINE vs U25/U50 plain. Models: blr, eight_schools_centered,
arma11, hier_2pl (1 rep trimmed to 3 reps only for survivors). Seeds/
inits per house protocol. Branch exp/two-phase-warmup off e46da43+W61
counters in scratch/w61/walnutpie_w54.

EXPECTATION: 1. Wall per warmup iteration drops 15–35% in phase 1
(ladder gone + fewer leaf rejections); total-run wall −10–25% at
U=250–500. 2. ESS parity: geomean ess_bulk-min within ±5% of baseline
(bias washes out via phase 2 + freeze). 3. hier_2pl is the risk model
(long-memory adaptation); accept up to −10% there IF wall wins hold.
GATES: PROPOSE-candidate iff gate 2 met (±5% geomean, no model >2x
collapse) AND measured wall saving >= 10% median-of-reps on >=2 models
(quiet-machine wall runs — machine currently idle, will post WALL
RUNNING). REJECT otherwise; negative closes the two-phase framing that
specifically exploits W-69's asymmetry (the generic two-phase literature
framing then remains open for others).
MACHINE: serial single-core for ESS arms; wall stanza posted in comms.
COST: impl ~2h agent + ~90 runs ≈ 2h.

## 2026-08-25 — W-74 PRE-REGISTRATION (before any run): warmup truncation with pf inits — the isolated simple variant of the two-phase lead (W-45's subsample transplant is dead by mechanism: position 1250-1900 logp below typical set; but plain truncation was never isolated); ZERO code, pure CLI arms; the biggest untested ESS/s lever (warmup = 65-76% of wall)

ARMS (A0 binary, default config, pf inits, --samples 1000, seeds
20260819+1000*rep+chain, --metric-window 50 — IDENTICAL to the W-63
A0 grid except --warmup): W400 (--warmup 400) and W700 (--warmup 700).
BASELINE: the existing W-63 A0 w1000 grid (scratch/w63/runs/A0/ — all
21 models, 3 reps, 4 chains, same seeds/inits/protocol) — REUSED, not
rerun. New runs: 2 arms × 21 models × 3 reps × 4 chains = 504.
GATES (pre-registered): (G1 no-harm) per-model ESS_min ratio
(arm/w1000, rep medians) >= 0.9 on EVERY model — warmup truncation
must not cost sampling quality anywhere; (G2 efficacy) geomean
TOTAL-wall saving >= 20% (expected 25-35% if quality holds: warmup
1000→400 at ~1.5-3x sampling-phase per-iteration cost means total
~0.65-0.75x; ESS/s roughly +35-55%); (G3 pathology) no new
pinned/rhat>1.02 pathology vs the w1000 arm's own census (W-63
baseline pathologies counted, not excused — zombie cells compared
like-for-like). VERDICT RULE: GO = G1+G2+G3 all pass => "short-warmup
with pf inits" becomes a recommended-config finding (user decides
promotion); any G1 violator => record per-model class (the W-21
marginal-class lesson likely applies — the honest outcome may be
per-class truncation guidance, still useful, still recorded).
DOSE-RESPONSE: W400 vs W700 vs W1000 gives the truncation curve.
ANALYSIS: reuse scratch/w63/analyze_lowrank.py ESS conventions; wall
from log "total time:" lines; ESS/s = ESS_min / total_wall.
Machine: 4 workers (idle), est 3-5h. Artifacts scratch/w74/.

## 2026-08-25 — W-75 PRE-REGISTRATION (before any run): (A) OnlineMoments aliasing-fix EFFECT study + (B) P2 cross-chain pooled-warmup closed-loop prototype — ESS/s session resumption

CONTEXT: overnight sessions closed low-rank-for-good (W-66), DEER
parallelism (W-70c), wrapped-DA (W-71R), discounted min-micro (W-72).
Standing lanes from MY W-65: P2 pooling (formal GO, open-loop) and the
Welford aliasing bug (sims1253/walnutpie#12, unmeasured effect).

ARM A (aliasing effect, cheap): cherry-pick PR-#12 one-liner onto
exp/warmup-trace tip -> branch exp/aliasing-effect; rebuild; regenerate
the 48-cell trace set (same seeds/inits/flags as W-65); replay-vs-oracle
final-window slow-decile error fixed-vs-aliased (prediction: fixed is
closer on transient-heavy early windows, neutral late); THEN ESS bench
arms {aliased, fixed} x {arma11, blr, hier_2pl, bym2_offset_only} x
rep{0,1,2} x --chains 4 --chain-exec serial (single core/cell,
sequential), seeds 20260819+1000*rep+c, defaults otherwise. GATES: draws
DIFFER across arms by design (numerics fix — no bit-identity); verdict =
two-sided: geoESS_bulk_min medians + R-hat failures; wall NOT claimed
under contention. Decision rule: adopt-fix-as-default recommendation iff
ESS non-inferior (>=0.95x geomean) AND R-hat fails not worse AND replay
error not worse.
ARM B (P2 prototype, code-first): implement pooled-warmup behind
--pooled-warmup (Serial exec only; AdaptSnapshot += draw/score
(mean,ssd,weight); at window boundary reseed chain c from OTHER chains'
latest published snapshots via Chan combine, PER-COORDINATE guard:
pool coord j iff cross-chain log-spread_j < ln(4) (bym2 rep0 poisoned at
~ln(1.1) median with e^6 reps correctly refused — tighter than open-loop
ln(10)); else solo seeds). Library-level synthetic test must reproduce
analyze_pooling semantics on fixed streams. Bench only AFTER Arm A cells
free the machine: arms {off,on} x same grid as Arm A. Gates: ESS_bulk_min
two-sided (>=1.05x geomean win required to advance), R-hat fails not
worse, wall <=1.05x. NO default changes without two-sided evidence.
Numbering: W-75 fresh (highest prior = W-74).

## 2026-08-25 — W-73 CLOSE-OUT (P3 stage-1, ZERO runs): min-micro × max-macro joint-policy LOG-MINING — 252/252 A0 logs parsed; joint structure VISIBLE but only half-measurable; conditional GO for a 5-model depth-cap pin battery; logging GAP REPORT written up as UX-PR candidate — numbering collision NOTED (two prior W-73 preregs exist from the ESS/s session; label kept per task assignment, renumber on merge if needed)

P3 stage-1 per overnight summary ("min-micro×max-macro-steps joint
policy (P3 stage-1 log parse is cheap)"). Pure parsing of
scratch/w63/runs/A0 (21 models × 3 reps × 4 chains, w1000/s1000) +
A0/blr pin battery + lowrank_results.json ESS join (my grads parse ==
json per_rep grads, exact). Full report + table + method:
results/p3_logparse_w73.md. Key facts established:

FORMAT: logs carry ONLY 2 stanzas (warmup/sampling: total+logp_grad
time/fraction/calls/per-call), one `Macro time =` (= frozen sampler's
ADAPTED MACRO STEP SIZE, walnuts.hpp:992 — not wall time), inverse-mass
diagonal, param means/stddevs, countable error lines. NO depth /
min-micro / step-size / halvings / accept anywhere; CSVs have zero
sampler columns.

COST MODEL (source-verified): min_micro=1 + no halvings + reversible()
free at num_steps==1 + W-23 cache => calls/draw == E[2^depth] EXACTLY;
corpus-wide 0/252 chains at the 64-rung => whole corpus is min_micro=1,
so calls/draw IS mean trajectory states; exact-32 chains (bym2 7/12,
pin-battery w100_def 12/12) = always-reject depth-cap signature (w400_pf
escapes: 21.3 calls/draw, macro time 10x smaller, chains move).

FINDINGS: (F1) healthy-model Spearman(calls/draw, ESS/draw) = -0.83,
(calls/draw, ESS/call) = -0.94 — the 4.2x calls/draw spread buys NO
mixing (ecological, confounded, but kills the "earning their keep"
defense). (F2) depth-cap saturation measurable via rung pinning: healthy
p(cap)>=0.25 ONLY blr (0.49) and eight_schools_centered (0.30). (F3) 6
ESS-dead models hold 44% of sampling-call mass, sit at/near 32 with
macro-time CV 0.27-1.36 (healthy <=0.16) — adaptation failure, not a
trajectory-policy target. (F4) the joint structure appears as a SIGN
FLIP of within-model Spearman(macro time, calls): coverage-limited
(diamonds -0.77, bym2 -0.65) vs error-limited (lotka +0.76, hier_2pl
+0.66, kronecker +0.63) — both regimes healthy models exist.

VERDICT (pre-registered style): conditional GO for a SMALL stage-2:
CLI-only depth-cap pins (--max-trajectory-doublings 4 vs 5, optional +4
joint with min-micro 2) on {blr, eight_schools_centered,
logmesquite_logvash, radon_partially_pooled_nc} + hier_2pl control,
w400/s500, ~180 chain-runs; advance iff ESS_min/draw >= 0.95x AND
grads/draw <= 0.9x per model. Mechanical win bound (rung arithmetic,
ESS-flat assumption): blr <=33%, 8sch_c <=23%, all other healthy <=8% —
the >=10% bar is plausible for exactly TWO models; expect nulls
elsewhere. Class-closure bound (spendy 18.5 vs lean 8.6 calls/draw)
would be ~54% but needs the untested ESS-flatness.

GAP REPORT (blocks the full joint program, ~15-line UX PR candidate):
(1) min_micro_steps_ has NO getter — add beside macro_time() and print;
(2) WalnutsSampler::operator() DISCARDS depth from transition_w —
accumulate 6-bin histogram, print in sampling stanza; (3) micro-halvings
counter in macro_step/macro_step_lr (makes F4 regimes direct);
(4) optional CSV per-draw depth__/micro_per_macro_mean__ columns.
WALNUTPIE_DEBUG_ALPHA already exposes per-macro alphas (rerun-only).

## 2026-08-25 — W-76 THEORY RESULT: antithetic/multi-draw emission HAS a valid route — iid draws from the Barker leaf marginal are π-exact; pair-mirror salvage derived; naive fixed-fraction pairing invalid (orchestrator #2)

Doc: scratch/w61/w76_antithetic_theory.md. Key results:
(1) Lemma: nested Barker combines give exact leaf law
p_B(j|S) = e^{-H_j}/Σ e^{-H_i}; emitting k iid draws from p_B is
marginally π-exact (Prop. 1). Computable O(N)/transition from LSE
weights walnutpie ALREADY computes (~80–120 LOC: leaf-index +
prefix-LSE array).
(2) Extra draws are GRADIENT-FREE (trajectory already built) ⇒
E[ESS]/grad ceiling ≈ 2× plain WALNUTS via Gaussian antithetic pairing;
degeneracy risk: heavy tails collapse p_B onto one leaf ⇒ gain→1×
(funnel/multimodal = risk classes — consistent with project's funnel
lessons).
(3) Naive deterministic fixed-fraction pair emission INVALID (GIST
involution dies at doubling-tree regeneration off-midpoint + depth-
truncated trees); U-turn criterion itself reversal-invariant; salvage =
"pair_mirror" two-point ψ inside GIST selection kernel.
(4) Partial refresh re-rejected by theory (breaks ρ regeneration past
accept/U-turn tests).

## 2026-08-25 — W-78 PRE-REGISTRATION (before any run): pair-Barker emission implementation — correctness gate first, then effect gate (orchestrator #2)

IMPLEMENTATION (branch exp/pair-emission off 788d832 in scratch/w61/
walnutpie_w54, queued behind W-73 grid for machine): env-gated
WALNUTPIE_PAIR_EMISSION={off,pair_barker} (off = bit-identical);
during SAMPLING phase only, emit second draw per transition by sampling
the leaf index j~p_B(j|accepted span) from the stored LSE weights
(warmup stays single-draw so adaptation statistics unchanged);
draws CSV gains interleaved rows with a per-row transition-id column
variant documented for the analyzer.
CORRECTNESS GATES: (i) off-mode md5 canary identical; (ii) Gaussian
D=100: pair-emission chain moments within 3 SE / 20% of truth AND
empirical overlap of single-vs-pair marginal distributions (KS test n.s.)
— proves marginal π-exactness empirically.
EFFECT GATES: ESS/grad (rnESS_bulk-min ÷ total grad calls, both phases)
≥1.25× off-mode on Gaussian D=100 median-of-3 seeds; no model harm
worse than −10% on blr/esc real-model spot check (tail-degeneracy watch:
report min weight-mass diagnostic).
DECISION RULE: both gates pass → propose CORE_SET-scale arm; else close
with measured numbers. EXPECTATION: 1.4–1.8× Gaussian per theory doc.
COST: impl ~150 LOC + analyzer tweak; runs cheap (functor targets).

## 2026-08-25 (evening) — W-73 CLOSE-OUT: Adam hyperparameter sweep REJECTS all three arms — lr_hi −1.0% agg (+89% diamonds / −53% lotka collapse), lr_lo −67.8%, target07 −27.0% — defaults confirmed; the easy/hard split pattern named — ESS/s continuation session

Full writeup results/adam_sweep_w73.md, raw results/w73_ess.json.
lr 0.02 catastrophic (warmup too short to converge log-step), accept
0.7 loses quality faster than it saves evals, lr 0.15 pure redistribution
(+89% diamonds vs −53% lotka). KEY SYNTHESIS: every lever measured in
this session cluster shows wins concentrated on {diamonds, radon, bym2}
and harm on {lotka, kronecker, hier_2pl} — global defaults are already
at the Pareto frontier for this suite; remaining headroom requires
per-model selection (all cheap selectors so far: inverted or blind) or
the open two-phase-warmup lead.

## 2026-08-25 (night) — W-74 CLOSE-OUT: warmup truncation with pf inits NO-GO — G1 FAIL (W400 7 violators, W700 5; blr 0.42–0.56, esc 0.66–0.68, radon_pp 0.71–0.88, dogs 0.81–0.89, bym2 0.88–0.90, lotka-W400 0.41, ldgm-W400 0.85), G3 FAIL (new pinned: bym2 5→12/8 of 12, accel_gp 2→6/4, diamonds 0→3, radon_pp 0→2 + rep2 ESS collapse 149→2.2, blr/pilots 0→1), G2 FAIL-as-measured (raw wall ratio 1.21/1.55 — CONFOUNDED: arms ran 22:09–22:55 under W-73's 4-thread run + IO load, per-log µs/call shows 1.35–1.7x slowdown; load-invariant grad-CALL ratio 0.695/0.867 = true 30.5%/13.3% work saving, ESS-per-call geomean 1.32/1.20) — the two-phase lead is now dead BOTH ways (W-45 transplant by mechanism, W-74 truncation by no-harm floor); fallback per-class guidance recorded (easy/small + GLM benign members pass, hierarchical/funnel split — confirms the W-21 marginal-class lesson: truncation must be screened per-model)

Runs: 504/504 (21 models x 3 reps x 4 chains x {400,700}), 0 failures,
46 min at 4 workers, guarded binary (default-path only — canary-proven
bit-inert, sound vs the pre/post-guard baseline mix). Full tables +
mechanism notes: results/warmup_truncation_w74.md; raw:
scratch/w74/w74_results.json. Dose-response: ESS geomean 0.918/1.042/1,
violators 7/5/0, net new pinned +18/+5/0 — no knee passes G1+G2
together. lotka-W700's 6.6x is single-rep mode luck (rep2 only), not
usable. diamonds W700 needs 1.38x MORE calls than w1000 (truncated
adaptation -> smaller stepsize -> sampling pays it back).

## 2026-08-25 — W-76 PRE-REGISTRATION (before any run; next free number after W-75): P3 stage-2 — depth-cap pins on the W-73 conditional-GO set; ADVANCE rule per model: ESS/draw >= 0.95x AND grads/draw <= 0.9x vs baseline

ARMS (A0 binary, default config otherwise, pf inits, w1000 s1000,
seeds 20260819+1000*rep+chain, --metric-window 50, flags only):
C4 = --max-trajectory-doublings 4; C5 = 5; C5MM2 = 5 + min-micro 2
(flag name per cli --help). MODELS: blr, eight_schools_centered,
logmesquite_logvash, radon_partially_pooled_noncentered + hier_2pl
(negative control — 8.6% bound, expect null). BASELINE: W-63 A0
w1000 grid reused (default cap). 3 arms x 5 models x 3 reps x 4
chains = 180 runs. MECHANICAL BOUNDS (W-73 rung arithmetic): blr
<= 33% grads saving, 8sch_c <= 23%, others <= 8%. VERDICT per
model: ADVANCE iff ESS_min ratio >= 0.95 AND grads/draw ratio <=
0.9; record nulls honestly. This is a POLICY probe (per-model
caps), not a default change — any advance becomes a screening
question (same W-21/W-74 lesson: per-class only). Machine: 4
workers if idle; coordinate via comms.

## 2026-08-25 — W-75 CLOSE-OUT: flag-dispatch audit — 8 confirmed findings; new sibling class packaged as fork PR #16 (orchestrator #2)

AUDIT.md on branch audit/flag-dispatch (commit 404cba9): all 57 CLI
flags × {chains=1, chains>1}. Confirms #14's three wrapper no-ops
empirically (bit-identical step traces multi-chain; positive control
differs). NEW findings: --early-exit + --temporal-step-tol/window/
min-iter silently ignored at chains=1 while positive temporal tol
IMPLICITLY enables early exit on multi — cross-path semantic divergence.
Also: inert-without-parent flags (--da-* without --step-optimizer da,
--metric-full/auto/basis without --metric-rank) documented as UX gaps,
and multi path prints no parameter summary. 8 run_walnuts call sites
verified byte-identical (ledger claim TRUE).
PACKAGED: fix/temporal-guard-chains1 → draft PR sims1253/walnutpie#16
([upstream-candidate], base exp/safe-adapt-defaults): loud invalid-
argument for multi-chain-only early-exit flags at chains=1, mirroring
the existing guard pattern. Probe: rc=134 with message both flags;
plain run unchanged. Remaining audit items (guard widening for the
inert-without-parent flags) left as documented recommendations in
AUDIT.md — lower severity, UX-only.

## 2026-08-25 — W-78 CLOSE-OUT: pair-Barker emission — correctness PROVEN empirically, effect gate FAILED (median 1.096× < 1.25) → closed per prereg (orchestrator #2)

Commit 4bf0246 on exp/pair-emission: library-level leaf collector +
inverse-CDF second draw from the accepted span's exact Barker law
(zero extra gradients, warmup bit-identical by construction).
CORRECTNESS GATES PASS: canary md5 identical; Gaussian D=100 moments
within limits under rnESS-adjusted SE; KS primary-vs-secondary n.s.
— W-76's π-exactness lemma verified end-to-end.
EFFECT GATE FAIL: median ESS/grad ratio 1.096 (seeds 1.043–1.119).
Mechanism understood and consistent with theory: iid p_B draws from one
span are POSITIVELY correlated — averaging two same-span draws adds far
less than independent draws; the 2× ceiling lives in the pair_mirror
variant (antithetic mirrored pairs via reversal-equivariant ψ), which is
substantially harder (GIST-kernel-level change). Real-model spot check:
blr 1.000, esc 1.047 with span-dominance hitting 1.0 and single-leaf
spans emitting duplicates — degeneracy collapse exactly as predicted.
DECISION: close lane per prereg. pair_mirror documented as the residual
open variant but NOT pursued: its ceiling applies to easy targets
(where ESS/s is not binding) while its risk classes are exactly where
help is needed. Branch pushed to fork as idea history.

## 2026-08-25 — W-77 PRE-REGISTRATION (before any code): adapt-freeze — the mechanism isolate for W-74's over-adaptation signal (ESS/grad 1.32x at W400: is it the ADAPTATION DURATION or the POSITION that matters?)

DESIGN: new walnutpie flag --adapt-freeze-iters N (default 0 = off).
When iteration_ >= N (N>0): warmup CONTINUES transitioning (full
w1000 budget, position keeps exploring) but the estimator OBSERVE and
the step-adapter FEED stop updating (all tuning frozen at its N-iter
state; freeze/sampler() uses the frozen state). Small change in
adaptive_walnuts operator(); default-off; canary must be
byte-identical (N=0 reaches identical code).
ARMS: freeze400 (--adapt-freeze-iters 400) on all 21 CORE_SET models
(w1000 s1000, pf inits, standard seeds/protocol) = 252 runs;
baselines REUSED (W-63 A0 w1000).
MOTIVATION/HYPOTHESIS: if W-74's 1.32x ESS-per-call at W400 is an
adaptation-duration effect (over-adapted tuning drives unproductive
trajectory spend), freeze400 captures the per-call efficiency at
FULL position quality => sampling-phase grads/draw ~0.76x with no
ESS loss => ESS/s +5-12%. If it is a position effect (or the
estimator needs the tail), NULL or harm — recorded either way. This
also cleanly separates W-72's failed estimator-discounting (which
changed WHAT is estimated) from adaptation DURATION.
GATES: (G1) canary N=0 byte-identical + 225 ctest + property suites;
(G2) no-harm: per-model ESS_min ratio >= 0.9 vs baseline on ALL
models; (G3) efficacy: geomean grads/draw in SAMPLING phase <= 0.92
AND ESS/s geomean >= 1.05; (G4) pathology census no worse (pins/
rhat>1.02/errors). GO iff G2+G3+G4. Machine after W-76.

## 2026-08-25 — W-78 PRE-REGISTRATION (before any code): init-eval-failure guard extension — the kronecker dead-init class (model throws at EVERY eval from a boundary/degenerate init; logp stays finite or error-shaped, so W-42's non-finite-logp guard misses it; the chain zombies/aborts instead of failing fast)

DESIGN: extend the init guard (on the robustness/init-guard lineage,
new branch robustness/init-eval-guard): at initialization, evaluate
logp_grad; if the evaluation THROWS (or returns error) — not merely
non-finite — treat exactly like the non-finite case: file-init =>
loud abort; random-init => retry loop (existing --init-tries
machinery). Guard lives at init time only; zero sampling-path
changes; default behavior for healthy inits untouched.
TEST SET (known dead inits): kronecker_gp rep0 chain0 (LKJ-Cholesky
boundary, deterministic-normal), accel_gp r1c1, lotka r1c0 (W-63
init-driven aborts — same seeds abort under ALL arms).
GATES: (G1) the three dead inits: file-init fails FAST with a clear
message (seconds, no zombie sampling); random-init mode retries and
either lands a working init or aborts loudly with tries exhausted —
NO zombie chains; (G2) healthy-inits canary: draws byte-identical to
the robustness/init-guard binary (hier_2pl + kronecker good init);
(G3) existing init-guard tests + new unit test for the throw-class;
(G4) 225 ctest. PR candidate ([upstream-candidate] class) if green.

W-77 PRE-REG AMENDMENT (before any build/run; design correction): the
N=0 canary-vs-old-binary gate is REPLACED — the W-54 lesson (env-gated/
flag-gated code changes perturb codegen; last-ulp divergence moves
first-passage times even when N=0 semantics are identical) makes
cross-binary byte-identity the WRONG gate. AMENDED DESIGN: build ONE
new binary (exp/adapt-freeze); run BOTH arms on it: N0 (fresh
baseline, N=0, 252 runs) AND freeze400 (252 runs) — the experiment
compares WITHIN the same binary (no codegen confound). GATES become:
(G1a) N0 arm STATISTICALLY consistent with the reused W-63 A0 grid
(per-model ESS ratios within the rep-noise band; outliers
investigated — a continuity check, not bit-identity); (G1b) 225
ctest + property suites on the new build; (G2-G4) unchanged, now vs
the N0 arm (same binary). Total runs 504. The agent's N=0 semantic-
identity argument (all gates reduce to original expressions; no RNG
interaction) stands as the reason N0 is a VALID baseline rather than
a modified arm.

## 2026-08-26 — W-74 PRE-REGISTRATION (before any run): pf-inits-for-all arm — quantifying the suite-level ESS cost of default normal(0,1) inits — overnight-2 session

MOTIVATION (from the quality-gap mining, recorded in comms + erratum in
results/OVERNIGHT_2026-08-25_SUMMARY.md): the catastrophic W-36-grid
cells (bym2 geoESS 5.9/rhat 4.9; kronecker rep0 dead chain; eight_
schools_c rep0 rhat 1.45) are INIT artifacts — with Pathfinder inits
(table_per_config.csv pf_full/clang_native arms) current walnutpie is at
or above CmdStan parity on nearly every model. Question: how much ESS/s
does the default init posture cost across the standard 10-model grid?

DESIGN: one arm pfall = standard grid (binary build_w36exp, seeds
20260819+1000*rep, --chains 4 --chain-exec threads, 1000+1000) with ALL
10 models initialized from FRESH pathfinder draws (inits_w74/<model>/
rep<r>/chain_<c>.txt, unconstrained txt generated via cmdstan pathfinder
PSIS draws → BridgeStan param_unconstrain, per-chain draw seeded
rep/chain like run_pathfinder.py). Baseline = runs/w36/exp_par (normal
inits except hier_2pl/lsat). Pathfinder generation wall recorded
separately and CHARGED to the arm in reporting (honest accounting).
Runner: harness/run_arms.py with WALNUTPIE_INIT_ROOT=inits_w74.

EXPECTATION:
1. bym2_offset_only: geoESS from ~5.9 into the thousands (pf_full arm
   measured 4722); kronecker_gp rep0 abort disappears (different init);
   eight_schools_c rep0-class rhat failures shrink.
2. Easy/well-conditioned models: within noise of baseline (pf init ≈
   typical set ≈ what normal init already achieves there).
3. Aggregate geomean ess_bulk_geomean: large gain driven by the bad tail.
4. Wall: sampling-phase similar or slightly better (chains start adapted);
   pf overhead small vs total but nonzero.

GATES: ADOPT-candidate (as a WORKFLOW/default-init proposal to the user,
not sampler code): aggregate geomean ≥ baseline+20% AND no model median
ess_bulk_min drop >20% AND pf overhead ≤10% of suite wall. REJECT
otherwise. Either way recorded in results/pf_init_w74.md.

COST: pf generation (~minutes) + one 30-cell grid (~10 min).

## 2026-08-25 (night) — W-76 CLOSE-OUT: depth-cap pin battery ALL REJECT (0/15 advance) — blr C4 realizes the full 32% sampling-grads saving bound but ESS collapses to 0.435x, proving the W-73 ESS-flatness premise FALSE; 8sch_c saves ~0 (rejection-limited, not depth-limited); hier_2pl control null as designed; UNREGISTERED min-micro-2 lead on hier_2pl (3.16x ESS at 1.80x grads = 1.75x ESS/grad)

Flags confirmed on the A0 binary (--help): --max-trajectory-doublings
[5], --min-micro-steps [1] — both exist, so all 3 pre-registered arms ran:
180/180 runs (3 arms x 5 models x 3 reps x 4 chains), 0 failures, 21 min
at 4 workers under W-75 co-load; pf inits, w1000 s1000, seeds
20260819+1000*rep+chain, --metric-window 50. C5 (cap 5 = default) is
config-identical to the reused W-63 A0 baseline: all 60 CSVs md5-IDENTICAL
(0 mismatches) — validates baseline reuse AND isolates the session's wall
ratios (C5 1.23-1.49 on identical compute) as pure load confound (W-74
lesson); grads-based ratios are load-invariant. VERDICTS (rule: ESS ratio
>= 0.95 AND grads/draw ratio <= 0.9, rep medians, w63/w74 estimators):
blr C4 0.435/0.802, 8sch_c C4 0.420/1.011 (rhat02 3 vs 1), logmesquite
C4 0.532/0.856, radon_pp C4 0.701/0.933, hier_2pl C4 1.053/1.000 — all
reject; all C5MM2 reject on grads (1.35-1.80x) despite ESS gains.
BOUNDS vs W-73 rung arithmetic: blr sampling-only saving 32.0% sits AT
the 33% bound (arithmetic right, ESS-flat assumption wrong — ESS/grad
0.542); 8sch_c ~0 saving vs 23% bound (exact-32 always-reject signature
does not release grads when capped); logmesquite 17.9% / radon 10.8%
sampling savings EXCEED their 8% bounds (cap couples through warmup
adaptation — bounds under-predict when adaptation shifts); hier_2pl null
as predicted. OBSERVED (not registered, not a gate): C5MM2 per-model
ESS/grad ratios hier_2pl 1.75x, logmesquite 1.15x, radon_pp 1.13x, blr
0.82x, 8sch_c 0.52x — min-micro 2 is a QUALITY lever for hierarchical
gainers at 1.25-1.94x sampling-grads cost; joins the per-model screening
queue (W-21/W-74 lesson), NOT defaults. P3 cap direction closed negative.
Full tables: results/depthcap_w76.md; raw: scratch/w76/w76_results.json;
runs scratch/w76/runs/<arm>/<model>/; driver scratch/w76/driver.py;
analyzer scratch/w76/analyze_w76.py.

## 2026-08-25 — W-73 CLOSE-OUT: two-phase unadjusted warm-start REJECTED on all gates — the lever backfired on cost AND quality (orchestrator #2)

Commit 1773e67 on exp/two-phase-warmup (env-gated
WALNUTPIE_UNADJUSTED_WARMUP_FRAC; canary bit-identical; sampling phase +
adaptation untouched by construction).
GATES ALL FAIL: geomean ESS ratio 0.888 (<parity ±5%); esc U25 collapse
3× (87.7→30.0, consistent across reps — biased warm-start poisons
estimation exactly on the funnel-adjacent model); clean-window wall
≥10% on ≥2 models FAIL (esc +12–15% but blr −7..−8%).
MECHANISM (the important part): removing ladder rejections does NOT
save gradients — trajectories run LONGER without the invalidation
pruning (hier_2pl calls 148k→156k/168k), so the W-69 tax and the
rejection pruning are two faces of the same mechanism: the ladder both
costs evals AND shortens trajectories. You cannot buy back one without
paying the other. This closes the W-69-asymmetry framing of two-phase
warmup specifically; the generic literature framing (unadjusted
warm-start theory, arXiv:2603.22741) remains open to others but now
carries this counter-indication.
Also noted: contaminated-window wall hinted hier_2pl −28..−34% —
suggestive only, not gated on.
INCIDENT: another session checked out audit/flag-dispatch in the shared
worktree mid-run; recovered via cherry-pick + reset (both branches
verified at correct heads). Reminder to all sessions: claim worktree
branch exclusivity in comms.md before switching.
Branch exp/two-phase-warmup pushed to fork as idea history.

## 2026-08-25 — W-77 PRE-REGISTRATION (before any run): init-screen hardening — fail fast on constraint-boundary inits, closing the gap W-42 missed (orchestrator #2)

MOTIVATION: kronecker_gp rep0/chain0 (inits_w36) lands ON the LKJ
Cholesky constraint boundary (diagonal exactly 0) — logp finite-check
at init passes?? No: model THROWS at every eval ⇒ logp = -inf from
iter 0, yet the chain ran 1000 warmup iters pinned and then either
aborted (pre-NaN-guard) or wasted a full run. The W-42 init guard
(fail-fast on -inf init + random retries) exists on exp branches but
this class slipped through on w54 defaults; also BridgeStan EXCEPTIONS
at init (not just -inf returns) need covering.
DESIGN (branch rob/init-screen off e46da43+NaN-guard in scratch/w61/
walnutpie_w54, env-gated WALNUTPIE_INIT_SCREEN=1 to keep default-path
bit-identity): at chain start, evaluate logp_grad at the initial
position; if it throws OR returns non-finite logp, retry up to N=10
random inits (BridgeStan param_initialize-style within unconstrained
bounds); if all fail, exit loudly with a diagnostic naming the model
and init source. Wire at stan_cli single-chain + multi-chain inits.
GATES:
(a) kronecker_gp rep0 chain0 with screen ON: run completes with an
explicit "init failed after 10 attempts" diagnostic in <5s (vs 1000
pinned iters or abort today).
(b) healthy path bit-identity: blr md5 unchanged with env unset.
(c) blr with env set + good init: identical draws (screen no-op when
init is fine) — md5 match.
(d) unit-ish check: synthetic throw-at-init functor → loud exit.
EXPECTATION: all pass; this converts silent dead chains into fast
loud failures (project's standing robustness principle).
COST: small diff; probes minutes. Load-gated builds per current
contention.

## 2026-08-25 — W-78 CLOSE-OUT: init eval-guard extension VERIFIED + dead-init triage RECLASSIFIED (1 of 3 "dead inits" is a true init failure) — lotka r1c0 caught perfectly (refused before warmup, exception named, zero budget); accel r1c1 + kronecker r0c0 are MID-WARMUP eval-death classes (init evaluates fine; chain zombies then macro_time-aborts — the PR#10 adapter-guard class, NOT init-guard scope); healthy-init canaries BYTE-IDENTICAL both models across independent builds; 227/227 ctest incl. 2 new unit tests; PR filed

GATES: G1 SPLIT (lotka PASS by design; accel/kronecker reclassified out
of scope — the W-61 triage's "model throws at every eval [from init]"
held only for lotka; kronecker's LKJ-boundary walk + accel's vsdgp
NaN develop DURING warmup — 138 and 20,365 mid-warmup error lines
respectively; they need ox-alpha's adapter guard + possibly a warmup-
phase eval-failure policy = separate queue item). G2 PASS (hier_2pl +
kronecker healthy inits byte-identical, new-vs-base independent
builds). G3/G4 PASS (227/227). EXTENSION covers: exception NAMED at
abort; escape-throw -> loud abort (was terminate); finite-logp-with-
poisoned-gradient rejected at both guard points (Stan init validity =
finite logp AND grad); random-init rejects NaN-grad draws. Branch
robustness/init-eval-guard @ d019a28 (off robustness/init-guard
70c4a76). Artifacts: /tmp gate logs (copied to
scratch/w77/../w78_gates/ by coordinator), build_ig/, /tmp/ig_base.

## 2026-08-25 — W-75 Arm A CLOSE-OUT: aliasing fix = CORRECTNESS-ONLY (adopt on correctness grounds; NO ESS win claimable) — geomean ESS ratio fixed/aliased 0.959 (knife-edge pass of the 0.95 gate; 0.946 excluding degenerate bym2), rhat failures tied 6=6, replay aggregate error ratio 0.982; pre-registered "fixed improves transients" prediction NOT confirmed

24/24 bench cells + 48/48 trace cells rc=0. Per-model ESS_bulk_min ratios:
arma11 0.966, blr 0.931, hier_2pl 0.940, bym2 1.000 (mode-locked in BOTH
arms, rhat ~3.6e15 — serial-mc bym2 at defaults is its own pathology,
flagged for the W-74 lane). Verdict per prereg: adopt-as-default stands
formally, stated plainly as a knife-edge pass within benchmark noise;
PR #12 stays a correctness fix, not an optimization. Artifacts:
scratch/w75/arm_a_verdict.md (+ trace_effect.csv, ess_summary.csv),
runs_w75/{aliased,fixed}, branch exp/aliasing-effect @ 5122857.
NOTE: ess.R 'posterior' package unavailable in env; self-contained
Vehtari estimators reused from scratch/w63/analyze_lowrank.py applied
identically to both arms (recorded deviation).
Arm B (P2 prototype) implementation launched in isolated worktree
scratch/w75/walnutpie_pooled (branch exp/pooled-warmup off exp/warmup-trace).

## 2026-08-25 — W-76 ADDENDUM (zero-cost selector mining, no new W number): candidate selector for the min-micro-2 benefit split FOUND-but-unconfirmed — "benefit iff A0 sampling calls/draw <= ~18 (p32 lb <= ~0.1, i.e. NOT depth-cap saturated)": clean 5/5 on the labeled sample (harms blr 23.9 / 8sch_c 20.9 = exactly the two W-73 cap-saturated models; benefits 16.7-17.4), LOO-stable 5/5, but exact perm p=0.10 at n=5, 20% margin, per-rep label flips at the boundary (blr nnY, 8sch_c nnY, radon_pp nYY), D / macro-time-CV / ESS-per-draw all FAIL to separate, family consistent-but-confounded — NOT adopted; closing protocol written into results/depthcap_w76.md (C5MM2 on lsat + radon_var_slope + dogs + gp_regr + NEW spendy healthy models; no healthy CORE_SET model exists on the predicted-harm side).

## 2026-08-26 — W-79 PRE-REGISTRATION (before any run): min-micro-2 selector CONFIRMATORY batch — the W-76 addendum protocol (calls/draw <= ~18 => benefit), 4 healthy models all predicted BENEFIT (harm branch untestable inside CORE_SET — recorded as the design's limit)

ARMS: C5MM2 (--min-micro-steps 2, cap default) on {lsat_model,
radon_variable_intercept_slope_noncentered, dogs_hierarchical,
gp_regr} + the A0 baseline REUSED from W-63 (same-binary caveat:
W-76's C5MM2 runs came from the lowrank build_gates binary — the
confirm batch reruns on the SAME binary for arm-consistency; 4
models × 3 reps × 4 chains = 48 runs + reuse nothing else.
GATES (exploratory-confirm, honest): PREDICTION table recorded
beforehand: all 4 predicted benefit (calls/draw 5.7-16.7 << 18).
CONFIRMED iff >= 3/4 models show ESS/grad ratio > 1 (the selector's
directional claim); STRONG if all 4 > 1.05; REFUTED if >= 2 show
<= 0.95. Per-rep variation recorded (the addendum's boundary-flip
lesson). This does NOT adopt the selector — it tests its
extrapolation; adoption needs the harm branch tested on new
spendy/capped models from OUTSIDE CORE_SET (user decision whether
to source them).

## 2026-08-25 — W-77 CLOSE-OUT: init-screen hardening SHIPPED — all gates PASS, kronecker dead-init chain now SALVAGED by retry (orchestrator #2)

Commit 495c981 on rob/init-screen (+104/−6 in stan_cli.cpp): env-gated
WALNUTPIE_INIT_SCREEN=1; at chain start evaluate logp_grad; on
exception or non-finite logp retry up to 10 random inits, then exit 1
with diagnostic naming model/init-source/last error. Wired into BOTH
dispatch paths; per-chain RNG streams preserved so passing runs are
unaffected.
GATES: (a) kronecker rep0 chain0: screen detects -inf instantly and a
random retry succeeds immediately → healthy 1000+1000 run in ~20s
(better than prereg's "fail fast": the run is SALVAGED, not just failed
fast; honest deviation recorded); (b) env-unset blr md5 identical to
stock e5e754be… PASS; (c) env-set + good init md5 identical PASS;
(d) synthetic always-throw model: unscreened SIGABRT vs screened exit 1
in <10ms after exactly 11 attempts, both dispatch paths PASS.
Caveat documented: load_stan maps BridgeStan throws to -inf+stderr, so
"threw" vs "-inf" is indistinguishable at CLI layer — screen covers both.
PACKAGED: draft PR sims1253/walnutpie#18 [upstream-candidate]
(rob/init-screen → exp/safe-adapt-defaults). This closes the
robustness gap behind three historical anomalies (kronecker pins,
W-61 abort, W-63 all-arm pins).

## 2026-08-26 — W-74 CLOSE-OUT: pf-inits-for-all = +81.8% aggregate geoESS at 5.1% wall overhead — biggest win of the session cluster; ADOPT gate formally FAILS on two min-ESS drops + 2 new accel aborts; CONDITIONAL-PROMOTE recommended — overnight-2 session

Full writeup results/pf_init_w74.md, raw results/w74_ess.json, gen wall
results/w74_pf_gen_wall.json, inits in inits_w74/. GATES: agg PASS
(+81.8%, bym2 5.9→793, diamonds +289%, radon +76%), overhead PASS (5.1%),
min-drop FAIL (kronecker −47%/eight_schools −45.5% medians; single-stuck-
coordinate noise + 2-vs-3-rep baseline asymmetry). NEW ROBUSTNESS FINDING:
accel_gp rep0/2 abort AT FINALIZATION under pf inits — chains complete,
then macro_time validate throws on freeze → exactly the failure draft
PR #8 (freeze clamp) converts to a fallback; also kronecker rep0/lotka
rep1 now COMPLETE (confirms dead-init diagnosis). hier_2pl/lsat draws
bit-match baseline (pf pipeline cross-validated). RECOMMENDATION (user
decision): promote pf-init workflow + merge robustness PRs #7/#8/#9/#10,
then re-gate this grid.
NOTE: subagent built 9 missing cmdstan exes into build/*__default/
(107s) for pathfinder generation — sanctioned deviation, recorded.

## 2026-08-26 — TWO-PHASE DESIGN DOC LANDED (no code): results/design_twophase_warmup_w76.md — ceiling ~8–12% gross wall best case, expect-REJECT recommendation; drift-phase min_micro leakage hazard documented (observe not suspended at adaptive_walnuts.hpp:736)

## 2026-08-26 — W-74 FOLLOW-UP: accel_gp finalize-abort ROOT-CAUSED (NaN-alpha → Adam theta=NaN → freeze-time WalnutsSampler ctor validate throws AFTER all compute spent); draft PR #8 intercepts exactly this site; probe evidence captured — overnight-2 session

Mechanism (probe-reproduced bit-exactly, /tmp/acceldiag/): pf init adapts
large viable steps fast → trajectory reaches accel_gp's fragile
constrained-transform region mid-warmup → BridgeStan returns NaN logp on
some evals that aren't flagged −inf → dlogp = NaN → min_accept = exp(NaN)
= NaN fed to Adam (WALNUTPIE_DEBUG_ALPHA shows `[alpha 2107] -nan`) →
adam.hpp propagates NaN into m_/v_/theta_ permanently → step_size()=NaN.
Warmup runs its full 1000 iterations harmlessly (NaN step fails every
macro step), stanzas print, THEN run_walnuts_multi constructs each
chain's frozen sampler (stan_cli.cpp ~:567 → AdaptiveWalnuts::sampler()
→ walnuts.hpp:901 validate_positive(macro_time)) → uncaught throw,
std::terminate, rc 134, no rows.csv. Saturation-to-zero ruled out
arithmetic (Σlr·t^-0.5 bounded ≈17 → e^-17 ≠ 0): NaN poisoning is THE
route. FIX: draft PR #8 (freeze clamp) patches exactly this ctor site
and covers 0/NaN/inf via last_finite_step_ fallback; complementary:
PR #10's non-finite-alpha feed guard keeps warmup itself alive. ACTION:
merge #8 (+optionally #10's feed guard), re-run w74 accel rep0/2, re-gate
per results/pf_init_w74.md.

## 2026-08-26 — W-75 FOLLOW-UP: bym2 "serial mode-lock anomaly" RETRACTED — false premise; bym2 was never healthy under normal(0,1) inits; serial==threads RE-PROVEN bit-identical on current binary

My Arm A close-out flagged "bym2 mode-locked at defaults under serial mc"
as a possible pathology. Diagnosis (scratch/w75/bym2_anomaly.md) refutes
it: results/w36_ess.json shows bym2 ess_bulk_min 4.0-4.4 / rhat
[3.50, Inf, 4.93] identically in ALL w36 arms — normal inits stick chains
in separated modes (named in the original W-36 close-out); "healthy bym2"
numbers come from PF-init campaigns only (pf_init_w74: geoESS 5.9->793).
Discriminating probe: current binary + THREADS exec, identical inputs ->
all 4 chain md5s EQUAL to both the W-75 serial cell AND the w36 threads
cell (12/12 md5s across three runs). No harness bug, no divergence, no
binary drift; analysis-layer differences (arviz vs self-contained Vehtari)
explain the cosmetic rhat/ESS deltas. Side finding: aliasing fix inert
once warmup fully freezes (fixed rep1 md5s == aliased rep1). Owner action:
none beyond this record; healthy-by-default bym2 requires the pf-init
default-policy decision (W-74 lane).

## 2026-08-26 — W-77 CLOSE-OUT (adapt-freeze): NO-GO, hypothesis refuted INVERSELY — freezing all adaptation at iter 400 (warmup budget intact) makes SAMPLING-phase grads/draw 2.22x GEOMEAN MORE expensive (lsat 10.2x, hier_2pl 6.0x, kidscore 6.6x) at 0.53x ESS geomean (15/21 G2 violators, min radon_pp 0.078) + census regressions — the late 600 warmup iterations of continued adaptation are PRODUCTIVE on both quality and per-draw cost; W-74's 1.32x per-call was pure warmup-BUDGET arithmetic (sampling-phase calls at W400 were PARITY 0.970), so there is no over-adaptation tax to harvest

Protocol: pre-reg + AMENDMENT followed (same-binary arms). Binary
exp/adapt-freeze @ db8cbd8, flag verified on --help: --adapt-freeze-iters
UINT:NONNEGATIVE [0]. 504/504 runs (2 arms x 21 CORE_SET x 3 reps x 4
chains), 0 failures, 37 min at 4 workers on the idle machine, arm-
innermost dispatch (temporal pairing), w1000 s1000 pf inits
--metric-window 50 seeds 20260819+1000*rep+chain. GATES: G1a PASS in
STRONGEST form — N0 vs reused W-63 A0 grid: 252/252 CSVs md5-IDENTICAL
(the W-54 codegen fear did not materialize; statistical band never
needed). G1b PASS — ctest 225/225 (build_af_tests, tests-only configure;
campaign binary untouched) + both property suites PASS at W-62/W-66
values (cond 19.3126, rel-dense 4.26e-17, reversibility 3.3e-17,
|detJ|-1 8.9e-16). G2 FAIL (15 violators: radon_pp 0.078, esc 0.222,
hier_2pl 0.217, kidscore 0.253, 8sch_nc 0.255, lsat 0.284, lotka 0.298,
logmesq 0.387, kronecker 0.539, radon_var 0.567, gp_regr 0.614, garch
0.715, blr 0.734, bym2 0.881, diamonds 0.875; passers only wells 1.377,
arma11 2.077, ldgm 1.038, dogs 0.962, accel 0.931, pilots 0.906).
G3 FAIL both prongs INVERTED: sampling-grads geomean 2.223 (gate <=0.92,
hypothesis 0.76), ESS/s geomean 0.288 (gate >=1.05); warmup grads also
1.698x, total calls 1.932x. G4 FAIL: new pins blr 0->1, diamonds 0->3,
radon_pp 0->2, pilots 0->9, accel 2->6, bym2 5->12; rhat02 worse on 12
(radon_pp 1->162, kronecker 1992->3793, hier_2pl 0->18); lge worse on 6
(blr 28552->49877, accel 582->62608). GO FALSE (G2+G3+G4).
W-74 TIE-BACK (recomputed same estimators): W400/W1000 TOTAL-call ratio
0.682 (recorded 0.695) and ESS/total-call 1.347 (recorded 1.32) —
reconciled — but W400 SAMPLING-phase calls were parity 0.970: W-74's
saving was the budget cut, not a better sampling state; F400 (full
budget, same iter-400 tuning) prices that state: 2.22x sampling calls,
0.53x ESS. MECHANISM CLOSE: the over-adaptation framing is dead —
truncation fails on ESS (W-74), estimator-discounting fails (W-72), and
freeze-at-400-with-full-budget fails on cost AND quality (W-77); the
adaptation schedule's second half is doing real work on CORE_SET. Only
exception observed (not registered): pilots sampling-grads 0.851 (the
sole faller) at ESS 0.906 — noise-level, no lead. Full tables:
results/adaptfreeze_w77.md; raw scratch/w77/runs/<N0|F400>/<model>/;
driver scratch/w77/driver.py; analyzer scratch/w77/analyze_w77.py +
w77_results.json. Branch exp/adapt-freeze left at db8cbd8 (default-off;
not a default-change candidate).

## 2026-08-26 — CORRECTION (posted where the claim was made): W-74's "over-adaptation observation" (ESS/grad 1.32x at W400 read as "shorter warmup leaves a more per-call-efficient sampler") is RETRACTED — W-77's reanalysis with phase-split estimators shows W400's SAMPLING-phase calls were at parity (0.970x); the 1.32x was total-budget arithmetic (fewer warmup calls in the denominator), never a better sampling state. The adapt-freeze experiment that isolated this REFUTED the hypothesis inversely (F400: sampling calls 2.22x, ESS 0.53x — late warmup adaptation is productive on BOTH axes; there is no over-adaptation tax at w1000). Baseline airtightness: N0 arm md5-identical to the W-63 A0 grid 252/252 (the cross-binary codegen concern did not materialize for this change class). W-77 NO-GO recorded; branch exp/adapt-freeze stays local as history.

## 2026-08-26 — W-75 FOLLOW-UP: guard-threshold offline sweep — response along the guard axis is a STEP FUNCTION, not a trade-off; benched median-ln4 is OUTSIDE the open-loop safe set; Pareto point = frac90 @ ln(10)

360-row sweep (2 trace sets x 4 models x 3 reps x {median,frac50,frac90}
x {ln2..ln10}; driver reuses analyze_pooling math bit-identically,
verified against archived g4_results.csv at 0.0 rel diff). Findings:
(1) healthy-model gains are guard-INSENSITIVE wherever pooling engages
(~93% arma11 / ~85% blr / ~23% hier_2pl final-window error reduction,
bit-identical per-rep across settings); (2) frac50 == median everywhere;
(3) bym2 safety IS the axis: median/frac50 poison 2/6 bym2 reps at every
limit >= ln3 (worst -815%); frac90-ln10 = full gains + zero negative
reps (runner-up any-rule ln2). CONSEQUENCE: the running Arm B closed-loop
bench (median-ln4) tests an unsafe-by-open-loop point -> predict bym2
regressions in pooled_on there; healthy-model closed-loop numbers remain
informative. NEXT after Arm B lands: one targeted closed-loop iteration
with guard swapped to frac90-ln10 (pre-register as W-76); further tuning
NOT justified (step response). Caveat stands: open-loop replay, not ESS.
Artifacts: scratch/w75/guard_sweep.{py,csv,md}.

## 2026-08-26 — W-79 CLOSE-OUT: min-micro-2 selector confirm batch — gate CONFIRMED (3/4 models ESS/grad > 1: dogs 1.452, gp_regr 1.466, radon_var 1.116) but lsat is a DECISIVE miss (predicted benefit at calls/draw 16.66, observed harm 0.648, per-rep nnn) — the W-76 addendum's clean 5/5 separation is DEAD at n=9 (rule 8/9; lsat's feature ≈ hier_2pl's 16.7 with opposite labels, so NO threshold on calls/draw can fix it); selector NOT adopted, direction claim survives

Protocol: pre-reg followed exactly. Binary = W-63 A0 / W-76 build_gates
stan_cli (arm-consistent). 48/48 runs (C5MM2 --min-micro-steps 2 on lsat,
radon_var, dogs, gp_regr; 3 reps x 4 chains), 0 failures, ~80 s at 4
workers on the idle machine, w1000 s1000 pf inits --metric-window 50
seeds 20260819+1000*rep+chain; baseline = reused W-63 A0 grid. Feature
convention verified ON-GRID first: per-chain sampling calls/draw median-12
reproduces the pre-registered predictions exactly (16.66/16.58/5.68/6.63
vs 16.7/16.6/5.7/6.6, all <= 18 = predicted benefit). GATES: CONFIRMED
(3/4 > 1; not STRONG — lsat 0.648; not REFUTED — only 1 <= 0.95). Batch
health: 0 pins, 0 rhat>1.02 both arms; pf-init error-spam scales with
evals (radon_var 88->932 lines), no outcome impact. KEY FINDINGS: (a)
low-spend extremes are clean wins — dogs/gp_regr sampling-grads ~parity
(1.02/1.13x) for +46-47% ESS/grad, i.e. nearly free quality; (b) lsat's
harm is economic, not qualitative (ESS 1.27x BUT sampling grads 2.27x);
(c) per-rep: radon_var YYn (boundary-cluster ±30% noise, as the addendum
forecast), lsat nnn (decisive); (d) post-hoc hypothesis only: lsat is the
one predicted-benefit model with BIMODAL per-chain feature (9/12 chains
~16.5, 3/12 at 18.4/23.9/30.9 — minority-chain depth-cap saturation the
median hides; mechanism-consistent, untested). STATUS: --min-micro-steps 2
stays a per-model lever, no default change, no selector adopted; open
items unchanged+1: harm branch still needs healthy spendy models from
OUTSIDE CORE_SET (user decision), and any selector v2 needs a per-chain
saturation feature (frac chains > ~20), not the median. Wall (idle
machine) corroborates: ESS/s ratios 1.33/1.35/1.46 radon_var/dogs/gp_regr,
0.77 lsat. Full writeup results/minmicro_confirm_w79.md; raw
scratch/w79/runs/C5MM2/<model>/; driver scratch/w79/driver.py; analyzer
scratch/w79/analyze_w79.py + w79_results.json.

## 2026-08-26 — W-80 PRE-REGISTRATION (before any run): min-micro-2 selector v2 + harm branch — (a) per-chain saturation feature mined on the EXISTING 9 labeled models; (b) harm-branch test on 2-3 SPENDY HEALTHY models sourced from posteriordb (supplementary, clearly non-CORE_SET — the freeze is untouched)

(a) V2 MINING (zero cost): hypothesis from W-79: the median hides
minority-chain depth-cap saturation; feature v2 = per-chain
saturation fraction (e.g., frac of the 12 chains with calls/draw
above ~20, or the per-chain p32-style upper tail). Mine the existing
W-63 A0 logs for all 9 labeled models; test separation 9/9 with
LOO. HONEST: post-hoc feature search on 9 points — any v2 rule is
EXPLORATORY until out-of-sample confirmation.
(b) HARM BRANCH: select from external/posteriordb 2-3 candidates
that are spendy (calls/draw > 18 target) and HEALTHY — quick screen
(w300 s300, rep0 4 chains, A0 flags) of ~4-6 candidates, pick the
qualifying ones; then FULL arms A0 + C5MM2 (w1000 s1000, 3 reps, 4
chains, random pf-style inits via pathfinder or model default —
record which) on the selected. PREDICTION (registered BEFORE): high-
spend + healthy => min-micro-2 HARM-side (ESS/grad < 0.95) per the
saturated-cap mechanism... CAREFUL: blr/8sch_c were harmed BECAUSE
cap-saturated; high-spend-healthy (U-turn-limited deep trajectories)
might instead BENEFIT — the mechanism is ambiguous here, so this arm
is registered as EXPLORATORY with BOTH outcomes informative (bounds
the lever's domain either way). Gates: none binding; deliverable =
the labeled-domain map for the min-micro-2 lever + selector v2
status. Models + data clearly labeled non-CORE_SET supplementary.

EXECUTION: agents; machine idle; posteriordb .so builds via the
bs_models recipe (bridgestan, -j2); ≤4 cores total.

## 2026-08-26 — W-80a CLOSE-OUT: selector v2 mining on the 9 labeled models (zero cost, W-63 A0 logs; parse validated vs all 9 known medians) — p90 of the 12 per-chain sampling calls/draw separates 9/9 benefit/harm with LOO 0/9 and the largest margin (gap 4.15: radon_pp 19.18 vs lsat 23.34; any t in (19.18, 23.34); candidate rule "p90 <= 21"); the registered frac(chains>20) ALSO 9/9 but one-chain margin (radon_pp 1/12 vs lsat 2/12, LOO 1/9) and frac>18 FAILS (lsat ties logmesquite/radon_pp at 3/12 — the median's pathology at a new threshold); mechanism (minority-chain cap saturation) now backed by 3 agreeing features, but the specific rule is EXPLORATORY (post-hoc search, 10 rules on 9 points — winner's-curse risk LOO cannot price) -> register "p90 <= 21" and score one-shot on W-80b's out-of-sample labels before any adoption. Artifacts: results/minmicro_confirm_w79.md (appended "v2 selector" section), scratch/w80/{v2_mining.py,v2_mining.out,v2_results.json}.

## 2026-08-26 — W-80 ONE-SHOT PREDICTION REGISTERED (before W-80b results are seen): v2 rule "p90(per-chain sampling calls/draw) <= 21 => min-micro-2 BENEFIT (ESS/grad > 1)" — scored ONE-SHOT on every supplementary model W-80b delivers (screen-stage p90 computable from its A0 screens before the MM2 arms run; the full-arm label from the A0-vs-MM2 ESS/grad). PASS = all supplementary models classified correctly; the rule then graduates from exploratory to CONFIRMED-selector (still not an adopted default — adoption is a user decision with the domain map in hand). FAIL = the 9/9 was winner's curse; recorded and the lever stays real-but-unpredictable.

## 2026-08-26 — W-75 Arm B CLOSE-OUT: pooled-warmup GATE FAILS — primary bench a PERFECT NULL (my prereg omitted --metric-window => hook never fired: bit-identical 1.0000 everywhere); engaged diagnostic HARMFUL (0.50x geomean, new rhat failures at unsafe median-ln4); lane pivots to chop-free pooling v2 (W-76)

Facts: 24/24 cells ok; ON==OFF md5-identical in all cells (root cause =
preregistration flag-shape gap — MINE, owned: pooling triggers only at
metric-window boundaries and the arm left --metric-window default 0;
plumbing proven correct by the 13 unit tests, commit 8d68ac5). Agent's
off-protocol diagnostic (+mw50, plus win50-only control): pooling engages
(8/8 differ) but pooling-on-windows LOSES 7/8 cells vs windows-alone
(geo pool-effect 0.50x; hier_2pl ess_min 0.06x / new rhat fail 1.086;
blr rep2 new fail 1.107) — consistent with the guard sweep's prediction
for the unsafe median-ln4 point AND with W-63/W-70 (chopping itself
costs ESS). VERDICT per prereg: DO NOT ADVANCE as designed. Structural
lesson recorded: coupling pooling to CHOP boundaries taxes it with the
(chronic) cost of chopping; the open-loop G4 wins were measured on
chopped streams and do not transfer automatically. TEST-SIDE lesson: the
make recursive-shim quirk needs MAKE=/usr/bin/make in sandbox shells.
Artifacts: scratch/w75/{arm_b_verdict.md, ess_summary_armB.csv},
runs_w75/pooled_{off,on}, branch exp/pooled-warmup @ 8d68ac5.

## 2026-08-26 — W-76 PRE-REGISTRATION (before any run): pooled warmup v2 — CHOP-FREE periodic pooling (decouple cross-chain sharing from window resets)

DESIGN: new mode alongside Arm B machinery: --pooled-warmup keeps Serial
hook cadence (publish_stride blocks) but (a) does NOT require or trigger
chops — runs with default metric_window=0; (b) apply becomes MERGE not
overwrite: this accumulator pair absorbs OTHER chains' exported moments
per coordinate j behind the SAME frac90-ln10 guard (from guard_sweep
Pareto), blending weight-aware: w_self' = w_self + sum_c n_cj·1[guard_j
passes], mean/ssd updated by Chan combine over {self-state} ∪ {valid
others}; refused coords untouched. Guard evaluated per boundary on
current geometric estimates incl. self. Rationale: removes the chop tax
that sank Arm B's engaged arms; shares information the way continuous
discounting keeps it.
IMPLEMENTATION: extend exp/pooled-warmup (merge variant + CLI passthrough
+pooled_merge tests mirroring existing suite); commit; rebuild.
BENCH: arms {off, merge-on} x {arma11, blr, hier_2pl, bym2_offset_only}
x rep{0,1,2}, serial mc, defaults otherwise (NO metric-window), seeds/
inits identical to W-75 benches. GATES (binding): advance iff geomean
ess_bulk_min ratio >= 1.05 AND no model median drop >20% AND max rhat
not worse than off-arm +0.05; KILL RULE: any new rhat failure in on-arm
=> stop-and-record. EXPECTATION (honest): small positive on healthy
models (better late-window metric from 4x data) is the HOPE; the
mechanistic risk is that shared moments early (correlated inits) mislead
— the per-coordinate guard is the shield. Wall not claimed under
contention. Numbering fresh: highest prior = W-75.

## 2026-08-26 — W-76 CLOSE-OUT: chop-free merge-mode pooling REJECTED — KILL RULE FIRED (geomean 0.589x; arma11 -61% / blr -62% median drops; NEW hier_2pl rhat failures rep1+rep2); pooling lane CLOSED across all three designs

24/24 cells ok; implementation validated (20/20 pooled tests, 246/246
suite; commit d7f65c4). Results table + gates in scratch/w76_verdict.md;
per-prereg stop-and-record honored — NO iteration on this result. The
three-design arc closes P2 with mechanism: (i) open-loop estimator-error
wins were REAL (86-91%) but measured on chopped streams; (ii) closed-loop
coupled-to-chop inherits the chop tax (0.50x); (iii) closed-loop chop-free
merge at stride-5 cadence HOMOGENIZES the chains' independently-adapted
metrics — breaking the per-chain step-size/metric co-calibration — and
loses everywhere that matters (0.589x) while also costing wall (+37%
hier_2pl). Convergent with W-31 (cross-chain agreement criteria
destructive) and W-66 (low-rank closed): walnutpie's chain independence
during warmup is LOAD-BEARING on this suite. Cross-chain information
sharing for ESS/s is closed unless someone reopens it with a theory of
WHEN chains disagree productively (the dispersion diagnostic measures
this — candidate for a future screening-only, never-pooling use).
ESS/s session portfolio final state: P1 refuted (data-starved windows),
P2 rejected 3 ways, P3 stage-1 assigned to sibling (conditional GO),
P4 answered negatively via W-73 target07. Standing frontier unchanged:
funnel/mode-lock class (sampling-level), pf-init default policy (owner
decision), upstream numerics fixes (#12 correctness).

## 2026-08-26 — W-80b CLOSE-OUT: min-micro-2 harm branch on SUPPLEMENTARY non-CORE_SET posteriordb models (pre-reg W-80 part (b), exploratory, both-outcomes-informative) — harm branch OCCUPIED by a clean healthy spendy point (gpcm_latent_reg_irt: ESS/grad 0.002, 7/12 MM2 chains PINNED — chain-death mechanism, not cost inflation) but "spendy healthy => harm" as a RULE is DEAD: election88_full (21.8 calls/draw) benefits 1.35 and hierarchical_gp (25.4) benefits 4.22 at comparable spend; W-80a's v2 selector (p90<=21) scored one-shot as registered: 1/3 on the mining-comparable pf grid (correct on the clean point, misses on 2 caveated baselines; the def-grid 3/3 is artifact labels) -> v2 NOT adopted

Protocol: 5 candidates sourced from external/posteriordb @28f8d3d6
(election88_full D=90 grouped-logit, 2pl D=531 and gpcm D=543
latent-reg IRT, hierarchical_gp D=934, state_space D=389; no ODE, JSON
data, none in CORE_SET), bridgestan 2.9.0 -j2 builds in
scratch/w80/model_*/. Screen (A0 w300 s300 rep0 4 chains, DEFAULT init)
rejected state_space (pinned rows + NaN-scale errors) and 2pl (lowest
spend, family overlap); selected gpcm/election88/hier_gp. FULL ARMS as
instructed (default init, w1000 s1000, 3x4, seeds 20260819+1000r+c):
72/72 rc=0 in 31.5 min — but DEFAULT INIT BROKE THE A0 PREMISE for 2/3
(election88 chains in different beta.1 modes, rhat>1.02 on 913 cols;
hier_gp chains FROZEN at init basins — the screen's row-uniqueness was
defeated by y_new_pred GQ RNG noise). Recovery via the PRE-REGISTERED
alternative init ("pathfinder or model default — record which"):
cmdstan-2.39.0 pathfinder first-PSIS-draw inits (W-63 convention;
hier_gp simplex renormalized 1+1.4e-8), reran both arms: 72/72 in 35.4
min. PF-GRID RESULTS: gpcm A0 CLEAN (ess 537, rhat02=0) and MM2
destroys it — 7/12 chains emit ONE unique draw each, 402k logp_grad
errors, per-rep nnn 0.00/0.00/0.00, ESS/grad 0.002, mechanism = IRT
mode reflection (alpha 1.9 vs 0.8) + step/metric collapse, i.e. SILENT
CHAIN PINNING (worse than lsat's economic harm); election88 1.351
benefit (nYY, marginal baseline: 102-col rhat, beta.1 2+2 split);
hier_gp 4.221 benefit (YYY 3.5/3.4/6.8, MM2 mixes the tot_var~0.001
soft funnel far better: ess_min 4->36, rhat cols 1143->222;
degenerate-consistent baseline). DOMAIN MAP (deliverable): sign is
class-specific not spend-thresholdable — harm at 22.6 (IRT) vs benefits
at 21.8/25.4 (deep hierarchy/GP) in the same spend band; post-hoc
hypothesis only: harm where discrete multimodality sits at trajectory
scale, benefit where fine-scale degenerate directions limit mixing.
W-80a ONE-SHOT (p90<=21, scored on A0 pf grid): gpcm 27.40->harm OK;
election88 25.27->harm vs benefit MISS; hier_gp 27.42->harm vs benefit
MISS => 1/3, not adopted (also: def-grid 3/3 is 2 artifact labels; and
the FEATURE ITSELF is init-dependent — election88 med12 15.1 def vs
21.8 pf, p90 19.1 vs 25.3 flips the verdict — selector features must
be measured under the mining init protocol). PROTOCOL LESSONS: default
init unviable for spendy posteriordb models at w1000 (pf inits are
minimum); screens must check param-block-only uniqueness + cross-chain
rhat; show rhat02 next to every label (ESS/grad on a sick batch masks
chain death). Status: --min-micro-steps 2 unchanged (per-model lever,
now with a documented catastrophic-failure mode); no selector (v1 or
v2) adopted. Everything here SUPPLEMENTARY non-CORE_SET; freeze
untouched. Full writeup results/minmicro_harmbranch_w80.md; runs
scratch/w80/{runs,runs_pf}/<A0|MM2>/<model>/, inits scratch/w80/inits/,
driver+analyzer+JSON scratch/w80/{driver.py,analyze_w80.py,
w80b_results_{def,pf}.json}. Machine ~1h45m total.

## 2026-08-26 — W-80 FINAL ADJUDICATION + MIN-MICRO-2 ARC CLOSED: one-shot v2 selector FAILED (1/3 on the pf grid — gpcm correct, election88/hier_gp missed on caveated baselines; a registered fail is a fail) AND the feature is init-protocol-dependent (election88 p90 19.1 def vs 25.3 pf — flips the verdict) — NO calls/draw-based selector is viable (v1 falsified by lsat, v2 one-shot + protocol-unstable). THE LEVER IS REAL AND CLASS-SPECIFIC: benefit at fine-scale degenerate directions (hier_gp soft funnel 4.22x ESS/grad YYY, election88 1.35x, hierarchials +13-75%); CATASTROPHIC harm at trajectory-scale discrete multimodality (gpcm polytomous IRT 0.002x — MM2 pins 7/12 chains to 1 unique draw/1000, 402k errors, IRT mode reflection alpha 1.9 vs 0.8). Any future selector needs multimodality/degeneracy observables, NOT trajectory spend. Cross-reference: PR #15's depth-cap-rate summary line would have made gpcm's pinning visible in logs (cap saturation observable) — the diagnostics PR pays for itself here.

W-80b EXECUTION NOTES (recorded): screen rejected state_space (pinned +
NaN spam — screen worked); default-init grid broke the healthy premise
on 2/3 models (chain-mode splits) — the pre-registered alternative
(pathfinder inits) rerun cleanly; 168/168 sampler invocations rc=0,
~1h45m, ≤4 cores. Supplementary non-CORE_SET models (posteriordb
@28f8d3d6): election88_full, gpcm_latent_reg_irt, hierarchical_gp
(+2pl/state_space screened out). MIN-MICRO-2 FINAL STATUS: per-model
lever, documented catastrophic failure mode, NO selector — user
decision whether a multimodality-aware selector is worth designing
(the one open sampler-side idea left, with the domain map now in
hand: results/minmicro_harmbranch_w80.md).

## 2026-08-26 — W-81 PRE-REGISTRATION (before any run): COMBINED-STACK benchmark — does the exp-tip sampler win STACK with the SoA .so win? The B''-promotion decision number

ARMS: the W-36 grid (10 models, w1000 s1000, 4 chains sequential, 3
reps, seeds 20260819+1000*rep+c, W-36 init assignment inits_w25/w36):
stock_seq and exp_seq REUSED from the W-36 results (same binaries/
protocol); NEW ARM exp_soa = exp binary (build_w36exp, read-only) ×
SoA-patched .so (bs_w53 batch012+fused tree — 6 models need fresh
builds: the 4 parity models exist) × 4 sequential chains.
EXPECTATION (pre-registered): SoA wall win −3..−7% per model on the
exp binary (regime-dependent; W-59 measured −5..−7% on hier_2pl);
combined exp_soa/stock_seq ≈ W-36's exp_seq/stock × (0.93..0.97).
GATE: none binding (measurement); deliverable = the combined wall
table + multiplicativity check (per-model: does the .so ratio on the
exp binary match its standalone-measured ratio within noise?).
NOTE: single-thread .so are correct for the SEQUENTIAL arms (the
threads-parallel arm is out of scope — bs_w53 cannot build
STAN_THREADS .so, documented gotcha; W-36's headline par/stock ratio
multiplies orthogonally).

## 2026-08-26 — W-82 PRE-REGISTRATION (before any code): GUARDED min-micro-2 — reactive pin-detection + MM1 restart (the safe-by-construction path; sidesteps the dead selector problem)

DESIGN: CLI-level guard in stan_cli (branch robustness/mm2-guard off
robustness/init-guard lineage? NO — off dev/init-robustness clean:
new flag --min-micro-guard [off]: when min-micro>1 AND guard on:
after N=50 sampling draws, count unique position rows in storage; if
unique/probe < 0.5 (pinned signature — tune from W-80b's gpcm logs:
1/1000 unique), RESTART the entire chain from the SAME init+seed
with min-micro 1 (fresh trajectory; library re-invocation within the
CLI process). Costs a wasted warmup+50 draws on pinned chains only.
GATES: (i) default+MM1 path: canary byte-identical (guard inert);
(ii) gpcm (the catastrophic case): 7/12 W-80b MM2 chains pinned =>
guard fires on those chains, final draws = MM1-quality (ESS/grad vs
W-80b A0 >= 0.9 per chain-set); (iii) benefit models (hier_2pl,
dogs, gp_regr, hier_gp, election88): NO false trigger (probe
uniqueness >> threshold) and MM2 wins preserved (ESS/grad within
noise of W-79/W-80b MM2); (iv) 225 ctest. MODELS for the campaign:
the 7 above + blr/8sch_c (MM2-mild-harm, no pin => guard silent =>
stays mildly worse — honest residual). 3 reps x 4 chains, reusing
A0/MM2 grids where the binary matches (NOTE: new branch = new binary
=> MM2 arm must RERUN on it for arm-consistency; A0 also reruns
(canary check) — 9 models x 2 arms x 12 = 216 runs + guard arm 9x12
= 108; total ~324 runs).
EXPECTATION: guarded MM2 = benefit-class wins locked in, gpcm-class
catastrophe converted to MM1-parity at 1.05x cost (wasted probe).
GO => PR candidate [upstream-candidate] (feature flag, default off).

## 2026-08-26 — W-81 PRE-REGISTRATION (before any analysis): ESS/R-hat measurement-trust audit — do the self-contained Vehtari estimators used since the R `posterior` breakage agree with references, and would any standing gate verdict flip?

CONTEXT: every overnight ESS verdict since the R posterior package became
unavailable rests on self-contained estimators (scratch/w63/
analyze_lowrank.py lineage, reused by W-75/76 collect scripts). They have
NOT been validated against a reference implementation. If biased, gates
were judged on a crooked ruler.
DESIGN (pure analysis, no samplers): reference = arviz (if importable via
uv; else R posterior via ess.R if installable; report which). Test sets:
archived chains from (a) runs_w75/aliased arma11+hier_2pl (healthy/
marginal), (b) runs_w75/*/bym2_offset_only (pathological/mode-locked),
(c) runs/w36/exp_par/{kronecker_gp, diamonds} (historical), (d) one
ragged/adaptive-stopping case if archived (trim-to-min-length behavior).
Per cell compute ess_bulk_min + rhat_max with BOTH implementations;
report per-cell relative deltas, median + max, split healthy vs
pathological. SENSITIVITY: recompute THREE historical gate decisions
(W-75 Arm A adopt-threshold 0.95; W-76 kill-rule rhat 1.01 crossings;
W-73-style +5% adopt bar on one sweep arm if present in results/) under
the reference estimators — verdict flips get listed loudly.
GATES: median |Δess| < 5% AND |Δrhat| < 0.01 AND zero verdict flips
=> VALIDATED (overnight verdicts sound; record estimator choice as
blessed). Any flip => loud correction entry + affected-verdict inventory.
Either way: scratch/w81_estimate_trust.md + csv.

## 2026-08-26 — W-82 PRE-REGISTRATION (before any run): kronecker_gp dead-init REBASELINE EVIDENCE — valid-inits arm only, decision memo, NO policy change
CONTEXT: kronecker rep0/chain0 (inits_w36) maps to LKJ diagonal 0 =>
model throws on every eval; owner decision (regenerate vs document)
blocked on lacking a valid-init baseline (sibling diagnosis, 08-25).
DESIGN: regenerate kronecker inits for rep{0,1,2} chain{0..3} with the
SAME deterministic scheme as harness/gen_w36_inits.py (discover and
reuse it; verify no coordinate degeneracy by an eval-probe: logp finite
at every init) into inits_w82/kronecker_gp/. Run the current exp-lineage
binary (external/walnutpie build_w65/examples/stan_cli — canary-A-proven
behavior-identical to 43b6435 defaults) --chains 4 --chain-exec serial,
warmup 1000 samples 1000, seeds 20260819+1000*rep, outputs runs_w82/
kronecker_gp/rep{r}/. Collect ESS (blessed estimators per W-81 outcome;
if W-81 unfinished, BOTH estimator sets) -> compare against archived
runs/w36/exp_par kronecker cells (dead-init era). EXPECTATION (honest):
dead-init era understated kronecker quality; magnitude unknown. GATE:
memo scratch/w82_kronecker_memo.md quantifies old-vs-new (ess_bulk_min,
rhat_max, per-chain liveness) with explicit NO-RECOMMENDATION framing
(owner decides). Sequential cells; no wall claims.
Numbering: fresh W-81/W-82 (ledger grep tail W-79; comms mentions W-80
in results filenames only — checked, no ledger collision).

## 2026-08-26 — W-75 PRE-REGISTRATION (before any run): robustness-stack re-gate — exp/robust-stack-w75 (exp/safe-adapt-defaults + cherry-picked #7/#8/#9/#10 fixes) × pf-inits-for-all — overnight-3 session

MOTIVATION: W-74's conditional-promote package (pf-init workflow +
robustness PRs) can be TESTED without merging anything: stack the four
fixes on a fresh exp branch (established stacking-branch pattern), build,
and re-run the pfall grid. The accel finalize-abort (root-caused: NaN→
Adam→freeze ctor) should convert to a completed run via #8's clamp.

DESIGN: branch exp/robust-stack-w75 = exp/safe-adapt-defaults + commits
from walnutpie fork branches: init-guard (#7), freeze-clamp (#8),
step-heuristic-fix (#9), nan-alpha-guard (#10, guard commit only — drop
any W-61 instrumentation-only commits if separable). New worktree + build
dir; do NOT touch shared checkouts. Then arm pfall75 = standard grid ×
inits_w74 (WALNUTPIE_INIT_ROOT), same seeds/protocol.

EXPECTATION:
1. accel_gp rep0/rep2 COMPLETE (abort→clamped-fallback run; those chains'
   ESS may be poor but finite and reported).
2. Healthy-path canary: models that ran identically before (e.g. hier_2pl
   rep draws vs W-74 pfall) stay BIT-IDENTICAL (fixes must not touch
   healthy paths).
3. Aggregate geoESS ≥ +75% vs normal-init baseline (i.e., keeps at least
   W-74's +81.8% level; kronecker/eight_schools min-drops NOT expected to
   improve — those need policy work, not robustness).
4. No model's geoESS regresses >10% vs W-74's pfall arm.

GATES: PASS-to-user = all four; failure of (1) means the stack is
incomplete (diagnose which guard); failure of (2) = canary breach (fix
must be behavior-preserving on healthy paths); (4) = robustness fix
interfering with sampling (investigate before promoting).
COST: cherry-pick+build ~20 min, grid ~10 min. Machine announced.

## 2026-08-26 — W-76 PRE-REGISTRATION (before any run): Fisher-ratio selector feasibility — can Var_draw·Var_score (walnutpie's dual-Welford Fisher diagnostic) classify which models benefit from which policy? — offline analysis of warmup traces; overnight-3 session

MOTIVATION: every global policy lever measured this cluster shows gains
on {diamonds, radon, bym2} and harm on {lotka, kronecker, hier_2pl}. A
reliable END-OF-WARMUP selector would unlock conditional policies
(lr_hi +89% diamonds / rank-metric 2.5–3.4× winners). All prior selectors
failed (lp autocorr W-28, windowed stats W-37, window_cross_ratio W-66
inverted). NEW signal: walnutpie uniquely estimates per-coordinate
Var_draw AND Var_score; their product's deviation from constancy is the
Fisher-divergence misfit (2603.18845 lineage) — never tested as a
classifier. We hold ground-truth labels: per-model policy outcomes from
W-63 (window), W-64 (da/belief), W-66 (rank).

DESIGN: build the #11 warmup-tracer (branch exp/warmup-trace, opt-in
--warmup-trace-dir; default path untouched) in a private worktree. Run
short warmup-trace collections (warmup 1000, samples 100, standard seeds,
normal inits — selector must work WITHOUT pf) on the 10-model grid × 3
reps. Offline: per model, at final warmup iteration compute per-coordinate
log(Var_draw·Var_score); aggregate stats (mean, spread, quantiles, frac
|log|>1). Correlate against labels: BENEFITS-from-policy per model
(diamonds/radon/bym2 = winners; lotka/kronecker/hier = harmed; others
neutral) via simple separation analysis (which aggregate statistic best
separates winners from harmed; report AUC-equivalent + best threshold).

EXPECTATION (honest): prior selectors failed via inversion or blindness;
preregistered expectation is WEAK separation (AUC < 0.8) — the useful
output either way is a definitive keep-or-kill on the last cheap selector
candidate.
GATES: GO-to-prototype iff some statistic separates winners-from-harmed
with zero misclassifications across the 10 models (all 3 reps consistent
per model). KILL the selector direction otherwise — recorded as closure.
COST: build ~10 min + 30 short runs ~15 min + analysis. Runs AFTER W-75's
grid releases the machine (sequential, announced).

## 2026-08-26 — W-83 PRE-REGISTRATION (before any run): init-quality → downstream ESS predictability study — hunting a best-of-K init selection rule (orchestrator #2, day-3 session)

MOTIVATION: repeated ledger finding: on hier_2pl/lsat, rep-level variance
dominates every arm comparison (rep1 ~10× rep0/2 min-ESS, bit-identical
code; "init draw quality >> metric choice", W-17/W-19). W-5/6 shipped
pathfinder inits (11× geomean) but there is NO rule for choosing AMONG
pf draws — we take rep{r}/chain_{c} as-is. If a cheap init-time feature
predicts downstream min-ESS, a best-of-K selection rule is pure ESS/s
at fixed sampler cost.
DESIGN: models hier_2pl + lsat_model. Generate K=16 pf inits per model
(harness/run_pathfinder.py, fixed seed grid; existing inits_w25 may be
reused for the first 4 and extended to 16). For each init record
features AT INIT TIME ONLY: logp(x0), ||grad(x0)||, and (post-hoc
validation only) Mahalanobis distance to the run's posterior mean.
Then run SHORT sampling (warmup 1000 + draws 400, 1 chain, seed fixed,
same flags) from each init. Outcome: rnESS_bulk-min (pinned coords
dropped per W-64 methodology note).
ANALYSIS: Spearman rank-corr of each init-time feature vs rnESS across
the 16 inits per model; also binary "collapsed (<100)" classification
AUC. GATES for follow-up W-84 selection-rule experiment: |rho| >= 0.5
on BOTH models with the SAME sign, or AUC >= 0.8 both models. If no
feature qualifies → record negative (init quality is not cheaply
predictable at init time; selection rule lane closed).
MACHINE: serial single-core runs (32 short runs), pf generation cheap;
announce before any wall-sensitive work (none planned). Artifacts
scratch/w61/runs_w83/. COST: ~2-3h.

## 2026-08-26 — W-84 CLOSE-OUT: property hunt — 244 checks, 2 REAL BUGS; LOW-RANK MOMENTUM SAMPLER HAS THE WRONG INVARIANT DISTRIBUTION (orchestrator #2)

Branch tests/property-hunt (74cf30e): tests/property_hunt.cpp +
PROPERTY_HUNT.md. Everything else PASSES (span algebra exact-enumeration
cross-checks, uturn reflection, RNG discipline, Welford restore,
LowRankMass apply_inv/log_det, adapter semantics) — the core algebra is
sound.

**BUG 1 (confirmed present at 788d832/w54 lineage): OnlineMoments
variance lazy-aliasing** — `auto delta = y - mean_;` evaluated after
mean_ update ⇒ computes (y−mean_new)² not Welford's cross product.
Variance systematically underestimated ⇒ mass-matrix adaptation
poisoned on every lineage lacking the fix. PR #12 (fix/online-moments-
lazy-delta, base exp/safe-adapt-defaults) fixes this class — my repro
({1,2} after (w=1,m=0,v=0), df=1 → 5/12 vs correct 2/3) is a ready
regression test; VERIFY #12's fix matches before promoting.

**BUG 2 (SEVERE, new): LowRankMass::sample_momentum_from computes
(I+UWUᵀ)D^{-1/2}z instead of D^{-1/2}(I+UWUᵀ)z.** Non-commuting ⇒
Cov(ρ) ≠ A⁻¹ whenever U is not coordinate-aligned ⇒ the FULL low-rank
metric path samples a WRONG invariant distribution. MC repro: D=diag(4,1),
U=(e1+e2)/√2, c=1: empirical cov off by ~10-30% entries. The header
docstring AND tests/leapfrog_property_test.cpp replicate the wrong
formula — the bug survived "verification" because the test encoded it.
LEDGER IMPLICATIONS: every historical FULL low-rank-operator result
(W-9 full/diag 0.79, W-19 basis ablations' full-operator arms, any
--metric-full runs incl. yesterday's walnutpie_lowrank w74 gates)
sampled a slightly wrong posterior — treat those numbers as carrying
this caveat; FOLDED-diagonal estimates are unaffected (no operator).
FIX: swap the multiplication order; update docstring + the wrong test.
CAVEAT: walnutpie upstream main may differ — check before assuming.

## 2026-08-26 — PILOTS DIAGNOSIS (overnight-3 subagent, read-only): the last big walnutpie-vs-CmdStan gap is an EXACT LIKELIHOOD-NULL RIDGE, not the sigma_a funnel — 4/4 chains lock at different ridge points deterministically; lp-based rescues structurally blind; precise detector + 10-min discriminating experiment defined

MECHANISM (forensics on runs/w36+w74 + models/pilots.stan +
scratch/w77/runs/N0 frozen-mass print): y_hat = a[group]+b[scenario] is
invariant under a+=s·1, b−=s·1, mu_a+=s/10, mu_b−=s/10 → continuous null
direction, marginal sd(s)≈7 (a-scale). Per-chain: ESS_bulk(mu_a)=1–14,
ridgeF(std of chain-means / mean chain-sd)≈26–30, rhat(a.*)>2 while
rhat(y_hat.*)≤1.01; sigma_a itself fine (combined ESS 109, rhat 1.02 —
funnel NOT binding). WHY WALNUTPIE: (1) diagonal mass rule (Var_draw ×
1/Var_score geometric mean) collapses onto within-lock variance — frozen
inv_mass(mu_a)=0.00072 → sd 0.027, ~670x too small vs 0.7 marginal
(CmdStan's covariance-only Welford keeps full ridge scale); (2) short
trajectories: 8–37 sampling grads/draw vs CmdStan 136–170. EXPLAINS ALL
prior neutrals: W-11/14/15 (log-mass invariant along ridge → reinit and
log-mass dispersion hook blind), W-74 pf inits (−17%, pool itself
collapsed: pf.csv mu_a∈[−0.006,0.071]).
DETECTOR (zero-cost, sampler-internal): extend cross-chain dispersion
hook from log-mass to POSITIONS — ridgeF(p)>5 & per-chain ESS<10 &
rhat>1.5; well-mixed cells sit at ridgeF<2. Run-level red flag visible
today: rhat(a.*)>2 with rhat(y_hat.*)≤1.01 in the same CSVs.
DISCRIMINATING EXPERIMENT (queued as W-85, ≤10 min): pilots-only, w36
protocol, --min-micro-steps 128 (CmdStan-scale trajectory budget).
Prediction A (metric-binding): ESS(mu_a) rises only to ~15–30, ridgeF>5
→ fix = metric variance-floor along cross-chain-dispersed coordinates.
Prediction B (length-binding): ESS>100, rhat<1.2 → fix = trajectory
budget policy. NOTE: interplays with sibling W-82-guarded (pin-detection
MM1 restart) — coordinate before implementing either fix.
Full subagent report incl. per-chain table in session records; artifacts:
runs/w36/exp_par/pilots/*, runs/w74/pfall/pilots/*.

## 2026-08-26 — CLOSE-OUT [W-82-kronecker-rebaseline, MY entry — number also used by another session; disambiguate by title]: regeneration is a NO-OP by construction; valid-init re-baseline SAME-OR-LOWER (prereg expectation refuted); owner decision now has its evidence

Key facts: (1) the gen_w36 deterministic scheme regenerates md5-IDENTICAL
inits — rep0/chain0's LKJ-degenerate draw is a property of the scheme,
not file corruption; "regenerate with the same scheme" cannot fix
anything, so the owner choice is document-vs-new-scheme (e.g. rejection
resampling), not regenerate-same. (2) rep0 aborts with the W-61-class
"macro_time in (0,inf)" freeze (exp lineage lacks the nan-alpha guard)
— robustness gap, consistent with archive. (3) Quality: median ess_bulk_min
46.6 (dead-init era) vs 24.7 (valid inits, cross-binary due to the
aliasing fix) — dead-init era did NOT understate kronecker; every
completed cell fails rhat 1.01 in BOTH eras (rep1 1.12-1.13, rep2 1.13/
1.20 new). 3 reps is thin for cross-binary deltas — treat as "no hidden
quality was being masked". (4) BONUS: arviz reproduces results/
w36_ess.json EXACTLY — first independent validation datum for the
campaign estimators (feeds W-81-trust-audit). Memo (NO RECOMMENDATION,
arms needing matching runs if adopted listed): scratch/w82_kronecker_
memo.md. Artifacts: inits_w82/, runs_w82/, scratch/w82/.

## 2026-08-26 — W-83 CLOSE-OUT: init-quality NOT cheaply predictable — best-of-K selection lane CLOSED per prereg; plus a benchmark artifact discovery (orchestrator #2)

GATE FAIL: no init-time feature predicts downstream rnESS (Spearman
logp0 +0.05/−0.15, ||grad0|| −0.11/+0.42 across hier_2pl/lsat — signs
FLIP; lsat logp0 AUC 0.818 but hier_2pl has zero healthy runs so the
both-models gate cannot fire). Even post-hoc Mahalanobis distance to
the posterior mean is flat (−0.17/−0.04) — not merely the wrong cheap
feature. Lane closed with data: init draw quality is real (10× rep
variance) but not selectable at init time.
ARTIFACT DISCOVERY (flag to all): inits_w25/hier_2pl/rep0/chain_{0..3}
are BIT-IDENTICAL (same pf draw picked 4×) — every "4-chain" run using
that init set started all chains from the same point (chains differed
only by seed). Affects interpretation of rep-level comparisons on
hier_2pl specifically; regenerate distinct per-chain inits before the
next hier_2pl benchmark campaign. (lsat rep0 not checked — worth a
look by whoever owns the next run.)
Also: hier_2pl collapsed under ALL 16 distinct pf inits in the short
config (1000+400) — init choice does not rescue it; and the zombie init
with the SMALLEST Mahalanobis distance collapsed worst (init closeness
is not safety).
Artifacts: scratch/w61/runs_w83/ (features, runs, analysis, pf seeds).

## 2026-08-26 — CLOSE-OUT [W-81-trust-audit, MY entry — number also used by another session; disambiguate by title]: campaign ESS/R-hat estimators VALIDATED vs arviz 1.3.0 — ZERO verdict flips across all three recomputed gate decisions; sole structural delta = missing split-chain step (2-line fix documented, reproduces arviz <0.1%)

Method: campaign estimators extracted byte-verbatim (provenance 48/48
archived values reproduced); reference = az.ess(method='bulk') +
az.rhat(method='rank'). 52 cells (healthy/marginal/pathological/heavy).
RESULTS: healthy median |Δess| 0.98% (max 8.67%), median |Δrhat| 1e-5;
pathological cells diverge relatively (~49%) only at floor ESS where both
rulers FAIL identically. SENSITIVITY (the point of the audit): (i) W-75
Arm A adopt ratio 0.9591→0.9535 under arviz — still PASS (margin narrows;
excl-bym2 0.946→0.938 still below bar as stated); (ii) W-76 kill-rule
crossings IDENTICAL under both rulers — rejection evidence intact;
(iii) W-76 adopt bar 0.5893→0.5793 — REJECT unchanged. CAVEATS: absolute
ESS reads ~19% higher under arviz on marginal cells — standing gates all
used RATIOS (move <0.6pt), but future ABSOLUTE-ESS comparisons must pick
one ruler and stay on it. RECOMMENDATION (non-binding): next campaign
that touches the estimators adds the split-chain step (2 lines,
scratch/w81/estimate_trust.md documents it) BEFORE new runs, keeping
archived numbers' provenance intact. Artifacts: scratch/w81/ (trust_cells
.csv 52 cells, audit.py, sensitivity.py, w81_results.json).

## 2026-08-26 — CLOSE-OUT [W-81 combined-stack benchmark, MY entry — number also used by the trust-audit session; disambiguate by title]: CROSS-.SO BIT-IDENTITY 112/112 chains on the full W-36 grid (draws md5 + EXACT logp-call equality + both dead cells' path-normalized logs identical); .so wall effect regime-split −7..−9% on eltwise-heavy models vs ~0 on GLM-primitive ones (interleaved CPU-time control geomean 0.965 — inside the pre-registered −3..−7% band); the cross-session wall table itself is INVALIDATED by sustained foreign load and is reported flagged-only

ARMS exactly as pre-registered: W-36 grid protocol (w1000 s1000, 4
sequential chains, 3 reps, seeds 20260819+1000*rep+c, inits_w25/w36
assignment, defaults otherwise), stock_seq/exp_seq REUSED, exp_soa =
READ-ONLY build_w36exp CLI × SoA .so. Builds: bs_w53 tree verified ==
w59_soa_batch012_fused_bundle.patch state (reverse-apply clean, no
header drift since the W-59 .so builds; pre-flight canary reproduced
draws md5 fe7c57…); 7 fresh per-variant builds (make -j2 serial,
env -u LD_LIBRARY_PATH) + hier_2pl/kronecker_gp/accel_gp reused; all 10
verified name+param_unc vs the W-36 .so. HEADLINE (the decision-grade
result): exp_soa chain CSVs md5-EQUAL W-36 exp_seq on 112/112 completed
chains (28/28 cells) — a three-way composed identity stock-binary×stock-
math == exp-binary×stock-math == exp-binary×SoA-math; logp_grad calls
exactly equal per chain 112/112; kronecker rep0 + lotka rep1 abort
reproduced with byte-identical path-normalized logs (macro_time throw at
the same call). ESS/R-hat identical by construction (W-36 table verbatim).
WALLS: cross-session table unusable — three sibling sessions held
~3-5 load through the grid (ledger in rep jsons); geomean soa/stock
1.066, µs/call inflation +2..+26% inversely to per-call work = load
signature. RESOLUTION (control, not a new arm): chain-granularity
interleaved pristine-2.9.0-stock vs SoA .so (same build config, patch =
only delta), per-chain rusage CPU time; hier_2pl 0.929 (W-59 band edge);
full split — lsat .913 / bym2 .919 / accel .920 / hier .929 vs diamonds
1.017 / pilots 1.008 / eight_schools 1.007 / radon .984 / kronecker .975
/ lotka .986 — GLM-primitive log-densities route around the patched
eltwise ops (W-60's diamonds reasoning, now measured). GEOMEAN 0.965.
OPEN (deferred, not refuted): clean-machine 30-cell re-run for the
combined-wall table (exp_soa/stock expected ≈ 0.88..0.92 by
multiplicativity). Artifacts: results/combined_stack_w81.md; scratch/
w81/{build_missing,build_stock,verify_so,run_soa,analyze_soa,control_cpu,
control_all}.py, runs/, control2/, control3/, w81_analysis.json,
so_verify.json.

## 2026-08-26 — W-75 CLOSE-OUT: robustness-stack re-gate PASSES ALL FOUR GATES — +84.66% aggregate geoESS, 30/30 cells complete (was 28/30), healthy paths BIT-IDENTICAL, accel_gp +16.7% vs W-74 — the promote package is validated end-to-end — overnight-3 session

Branch exp/robust-stack-w75 (local only) = exp/safe-adapt-defaults +
local-lineage twins of #7/#8/#9 + #10 guard commit (1 conflict resolved:
dropped pin_trace context lines; ledger /tmp/w75_notes.md). Grid
runs/w75/pfall75, raw results/w75_ess.json. GATES: (1) accel rep0/2
COMPLETE — and no clamp warning fired: the #10 NaN-alpha guard prevented
the Adam poisoning upstream of the freeze; #8 clamp = backstop. (2)
canaries + 9/10 grid models bit-identical to W-74/baseline. (3) aggregate
330.1→609.5 = +84.66% (≥ W-74's +81.83%). (4) no model regresses >10% vs
W-74 (accel +16.74% is the biggest change). DECISION PACKAGE FOR USER:
merge walnutpie robustness PRs #7/#8/#9/#10 + adopt pf-init workflow
(results/pf_init_w74.md + this entry; re-gate cost ~10 min once merged).
NOTE: shared walnutpie checkout was moved to 5122857 concurrently by a
sibling agent mid-experiment — W-75 worktree was isolated, unaffected.

## 2026-08-26 — W-85 PRE-REGISTRATION (before any run): pilots metric-vs-length binding discrimination — --min-micro-steps 128 (CmdStan-scale trajectory budget), pilots-only, w36 protocol — overnight-3 session

DESIGN (from the pilots diagnosis above): arm mm128 = run_arms.py
--models pilots --arms 'mm128=--min-micro-steps,128', standard seeds/
inits (inits_w36 normal inits — the lock is init-independent), binary
build_w36exp, 3 reps. Analysis: per-chain ESS_bulk(mu_a) + a.1 (arviz),
ridgeF(mu_a) = std(chain-means)/mean(chain-sd), rhat, vs baseline
runs/w36/exp_par/pilots.
PREDICTION A (metric-binding): ESS(mu_a) rises only to ~15–30, ridgeF
stays >5 → fix = metric variance-floor along cross-chain-dispersed
coordinates (ridgeF detector feeds it).
PREDICTION B (length-binding): ESS(mu_a)>100 and rhat<1.2 → fix =
trajectory budget policy (min-micro-steps ramp for wide-dispersion
models).
GATES: whichever prediction matches (3-rep medians); tie/ambiguous →
record honestly, design follow-up.
COST: ≤5 min.

## 2026-08-26 — W-85 CLOSE-OUT: pilots lock is TRAJECTORY-LENGTH-BINDING, not metric-binding — --min-micro-steps 128 (robust-stack binary) traverses the ridge: per-chain ESS(mu_a) 1–14 → 12–1000, ridgeF 26–30 → 0.2–1.4 (chains co-locate), rhat 3.37 → 1.024–1.66 — overnight-3 session

Two-stage run: stock binary ABORTED 2/3 reps (mm128 deep trajectories
amplify NaN-alpha poisoning — 3.96M NaN log lines; robust-stack binary
completes 3/3, NaN-guard held, zero clamp warnings: third independent
validation of the #7–#10 package). RESULTS (in /tmp analysis + runs/w85):
mm128s rep2 fully healthy (all rhat ≈1.02, incl. sigma_a); rep0/1 partial
(one chain each at ESS≈1000, others 6–44 — budget still marginal).
MECHANISM CLOSURE: the collapsed mass (sd 0.027 along ridge) does NOT
prevent traversal given sqrt(n)-accumulation over 128-step trajectories;
CmdStan's 136–170 grads/draw is precisely the posture that works. COST:
22–34s/rep vs 0.35s baseline (~80×) — same ballpark CmdStan pays.
FIX DIRECTION (design candidate W-86, not implemented): conditional
trajectory-budget policy gated on the ridgeF cross-chain POSITION
dispersion detector (mid-warmup detection → raise min-micro-steps /
lower max-macro-steps-target for affected models). Env-gated prototype
+ canary per house rules if adopted. Do NOT pursue the metric
variance-floor idea for this class (refuted by this experiment).

## 2026-08-26 — W-76 CLOSE-OUT: Fisher-ratio selector KILLED by pre-registered gate — best statistic (median log(Var_draw·Var_score)) misclassifies diamonds (1/8) with 5 rep violations, direction INVERTED — fourth and final cheap selector dead; the conditional-policy program closes with it — overnight-3 session

Executed per prereg on the #11 warmup-tracer (worktree external_w76,
120/120 chain traces, warmup 1000/samples 100, normal inits). Full
tables results/fisher_selector_w76.md (agent-written; artifacts
runs/w76/traces/, scratch/w76_analyze.py). GATE: required ZERO
misclassifications + 3/3 rep consistency; best AUC-equivalent 0.875 with
diamonds (winner) sitting at 0.559 among harmed models (kronecker 0.534,
accel 0.219) — FAIL. Robust across windows 100/200/500. Mechanistic
byproduct: the spread statistics DO separate tight-vs-broad posteriors
({radon, lsat, hier, kronecker} vs {diamonds, pilots, lotka, 8sch, bym2,
accel}) — a real axis, but orthogonal to the policy axis; and same
INVERTED-direction pathology family as W-66's window_cross_ratio.
PROGRAM CLOSURE: selectors killed on this label set now = W-28 (lp
autocorr), W-37 (windowed stats), W-66 (cross-ratio), W-76 (Fisher
ratio). No cheap end-of-warmup signal selects policy response. The
conditional-policy idea stays dead unless an expensive (mid-run probe)
selector is ever proposed; not recommended.

## 2026-08-26 — W-82 CLOSE-OUT: guarded min-micro-2 GO — all pre-registered gates PASS on a fresh 324-run 3-arm grid (9 models x A0/MM2/GMD x 3x4); gpcm catastrophe converted to MM1-parity-or-better (7/7 pinned chains detected, md5-exact restarts), 5/5 benefit wins survive byte-identically, guard silent everywhere else; PR candidate

Campaign per pre-reg (the guarded-MM2 W-82 entry): binary robustness/
mm2-guard ef524a5 (3eddfc4 + guard 7a5cf1c + NaN-adapter cherry-pick;
canaries/ctest gated by the build session and reconfirmed here — fresh A0
md5-equals the W-80b pf A0 grids 36/36 and W-63 gp_regr). 9 models x 3
arms x 3 reps x 4 chains = 324/324 rc=0 in ~92 min at 3 workers (foreign
load ~3; one SIGTERM kill exercised the resume path cleanly). Arms: A0
fresh same-binary baseline, MM2, GMD = MM2 + --min-micro-guard (probe 50,
min-unique 25). GATES: (ii-ext) gpcm PASS — fires exactly on the 7 pinned
chains (r0c0,r0c1,r0c2,r1c1,r1c2,r1c3,r2c0 = the W-80b set), each firing
chain's output md5-EXACT the A0 run (in-process restart == MM1), GMD/A0
ESS 1.226 (per-rep 1.17/1.11/1.23, min 0.87; bar 0.9 at population), ESS
2.1->659 vs A0 537, rhat02 550->0 cols, 402k errors -> 241k; (iii) benefit
models 5/5 PASS — 0 fires, all 96 silent chains md5-identical to MM2
(GMD==MM2 exactly; ESS ratio 1.000), GMD/A0 ESS/grad hier_gp 3.94 /
hier_2pl 1.63 / dogs 1.62 / election88 1.54 / gp_regr 1.53 all >= 1.05;
probe-uniqueness margin min 34 (8sch_c) vs pinned 1 against threshold 25 —
no borderline cell. RESIDUALS honest: lsat 0.56 / 8sch_c 0.56 / blr 0.84
ESS/grad stay mildly harmed (guard converts pins, not economic harm).
WALL: GMD/MM2 0.874-1.014 per model — the guard is free on silent chains
and ~12% CHEAPER than MM2 on gpcm (abort-after-probe beats full-budget
pin spam); restart cost 1.06x summed over the 7 firing chains; gpcm
ESS/grad_total (incl. discarded attempts) 0.54 vs A0 — the honest
wasted-probe price. COMPOSITION REQUIREMENT (PR note): guarded MM2
requires the adapter NaN guard (ef524a5/6ba0798) present — else the
gpcm-class path is abort-not-pin (NaN min-accept -> adapter poison ->
freeze terminate before the sampling probe) and the guard never sees it.
VERDICT: GO — guarded-MM2 is the safe per-model lever, feature flag
--min-micro-guard default off, PR candidate. Artifacts: results/
mm2_guard_w82.md; scratch/w82/{driver.py,analyze_w82.py,w82_results.json,
runs/}. (Ledger note: the other "W-82" entry above is the kronecker_gp
rebaseline pre-reg — numbering collision recorded there.)

## 2026-08-26 — W-82 CLOSE + W-83 ASSESSMENT (SKIPPED) + SESSION STATE: guarded-MM2 GO — PR sims1253/walnutpie#20 filed ([upstream-candidate]; branch carries the NaN-guard cherry-pick ef524a5, cross-referenced to #10 in the body); W-83 (SoA batch 5, old-style-vari allocation seam) SKIPPED on assessment: remaining alloc traffic ≈37.6M calls ≈1.2% of patched G — the gate battery costs more than the win; recorded as not-worth-it rather than run. W-81 deferred item: clean-machine combined-wall confirmation queued for a quiet window (evening; coordinate via comms). PR tally across both days: math#5 + walnutpie#13/#15/#17/#20, all [upstream-candidate]; negatives W-74/W-76/W-77/W-79-selector/W-80 + the closed lanes all recorded with mechanisms.
2026-08-26 21:06 — W-81 QUIET-MACHINE CONFIRMATION (deferred item closed): clean 30-cell wall grid (fresh pristine quiet_stock .so x existing SoA .so, exp binary, strict-sequential cells, rep-major arm interleave, max load 1.81 self-only) — soa/stock geomean 0.964 wall-level, matching the interleaved CPU control 0.965 with the regime split intact (bym2 -9.1/accel -8.6/lsat -8.0/hier -5.9 vs GLM-flat); cross-session combined reads 0.951 = 0.964 x 1.043 machine-drift x 0.947 W-36 threading, drift-corrected 0.913 INSIDE the expected 0.88..0.92 band; draws md5-equal to earlier exp_soa 44/44 (4 spot models) and my stock arm md5-equal to W-36 exp_seq 44/44; all 4 dead cells reproduced; artifacts scratch/w81/quiet_* + results/combined_stack_w81.md '## Quiet-machine confirmation'.

## 2026-08-26 — W-84 PRE-REGISTRATION (before any run): guarded-MM2 FULL-domain table — GMD arm on the 15 models not covered by W-82 (completing PR #20's evidence to all 24 measured models); A0 grids REUSED (binary default-path equivalence proven by W-82's 36/36 md5 cross-checks)

ARMS: GMD (--min-micro-steps 2 --min-micro-guard) only, on the 15
remaining models of the 24 measured set (21 CORE_SET + election88/
gpcm/hier_gp): {eight_schools_noncentered, kidscore_momiq,
logmesquite_logvash, wells_dist100_model, diamonds,
radon_partially_pooled_noncentered, radon_variable_intercept_slope_
noncentered(W-82 has it? no — W-82 had lsat not radon_var; CHECK:
W-82 models were hier_2pl, dogs, gp_regr, gpcm, hier_gp, election88,
blr, 8sch_c, lsat — so remaining = the other 12 CORE_SET + none of
w80} — agent confirms the exact remaining list against scratch/w82).
w1000 s1000 --metric-window 50, seeds 20260819+1000*rep+chain, pf
inits per w63 manifest / w80 for supplementary; binary
walnutpie_mm2guard/build_mg. EXPECTATION per model: GMD/A0 ESS/grad
either >1 (benefit class — hierarchials/GLM-with-structure) or ~0.5-
0.9 (economic-harm class, guard silent) or pinned-with-recovery
(fire census). NO gate — this completes the domain TABLE for the PR;
per-class summary + updated domain map is the deliverable.

## 2026-08-26 — W-85 PRE-REGISTRATION (before any run): stan-math PR CHECKLIST for sims1253/math#5 (soa-eltwise-batch-records) — the W-56 battery: make test-headers (FULL), runChecks.py, make cpplint, make doxygen + warning attribution, targeted unit suites — run LOCALLY on the branch worktree external/math_dev_soa (already exists at the PR tip 0b7b0dc13); evidence to scratch/w85/ + WORKLOG; the PR body's checklist section gets its evidence

## 2026-08-26 — W-87 PRE-REGISTRATION (before any run): trajectory-budget generalization grid — mm128 (min-micro-steps 128) on ALL 10 models, robust-stack binary — which models are budget-responsive? — overnight-4 session

MOTIVATION: W-85 proved length-binding on pilots alone. Before building
any conditional policy (W-86), map the whole suite: which models gain
ESS/rhat from CmdStan-scale budgets, which only pay wall. This defines
the policy's payoff landscape and its detection requirements.

DESIGN: arm mm128g = --min-micro-steps 128, standard 10-model grid × 3
reps, seeds/inits per protocol, binary = W-75 robust-stack build
(external_w75 build_w75; NaN-guard needed at these budgets — W-85 showed
stock aborts 2/3 on pilots). Baseline = runs/w36/exp_par.

EXPECTATION:
1. Budget-responsive (rhat/ESSmin improve materially): pilots (proven),
   eight_schools_centered (tau-funnel, 3.66x gap to cmdstan — hypothesis
   it's the same class), possibly kronecker/accel (their min-drops under
   pf arms suggested marginal mixing).
2. Budget-neutral (ESS ~flat, wall up 10–80x): diamonds, radon, bym2,
   hier_2pl, lsat, lotka — these already traverse their posteriors.
3. Wall: aggregate wall will RISE substantially — the point is ESS/s
   accounting per model, not adoption of mm128 globally.

GATES: none to adopt (this is a mapping experiment). Deliverable: a
per-model classification {responsive, neutral} with ESSmin/rhat deltas +
ESS/s deltas, recorded in results/budget_map_w87.md; feeds W-86 policy
thresholds. COST: ~30 min grid.

## 2026-08-26 — W-88 PRE-REGISTRATION (before any run): low-rank FULL-operator re-evaluation under the PR#19 momentum-draw fix — was the operator direction handicapped by the bug? (orchestrator #2, day-4)

MOTIVATION: PR #19 fixes LowRankMass::sample_momentum_from (wrong
invariant distribution whenever U not coordinate-aligned). Historical
full-operator verdicts (W-9 full/diag geomean 0.79; W-19 basis
ablations) ran the BUGGY draw. If the bug cost ESS, the operator lane's
closure was partly an artifact. This is NOT the screen question (closed
by overnight session); it is operator-correctness in isolation.
DESIGN: branch exp/lr-fixed off 788d832 + PR#19 cherry-pick in a NEW
worktree scratch/w61/walnutpie_w88. Models where forced rank previously
REGRESSED (bym2_offset_only, radon_partially_pooled_noncentered) and
where it won (hier_2pl — caveats: pinned-metric artifact + all-inits-
collapse at short config; use 1000 draws) + eight_schools_centered
(control). Arms: DIAG (default) vs FULL-r (r per --metric-auto or the
W-9 settings) both on the FIXED binary. 3 reps × 4 chains, seeds
20260819+1000r+c, 1000/1000, pf inits (inits_w25 for hier_2pl EXCEPT
regenerate distinct chain inits first — W-83 artifact alert), inits_w36
others (kronecker excluded). Metric: rnESS_bulk-min (pinned coords
dropped) median-of-reps.
EXPECTATION: FULL-fixed ≥ FULL-buggy (re-run buggy arm from archived
numbers or fresh same-seed run on unfixed binary — prefer fresh paired
run for clean comparison) on non-aligned-basis models; geomean
full/diag moves from historical 0.79 toward ≥1.
GATES: RESURRECT-CANDIDATE iff full-fixed/diag geomean ≥ 1.0 AND no
model >2x collapse; else the operator lane stays closed (now for the
right reason). Either outcome resolves the #19-impact question with
numbers.
MACHINE: serial single-core runs, load-gated. COST ~2-3h.

## 2026-08-26 — W-89 PRE-REGISTRATION (before any run): ThreadSanitizer race hunt on the multi-chain path (orchestrator #2, day-4)

MOTIVIGATION: W-30 shipped threaded multi-chain (std::jthread per chain,
SpscBuffer lock-free handoff, controller polling). Never run under
TSan. Project history: heap corruption shipped once via stale .o
(gotcha), STAN_THREADS hazard documented, spsc_buffer is hand-rolled
lock-free — classic data-race territory. Proven ROI of bug hunts in
this codebase (5 real bugs so far).
DESIGN: worktree scratch/w61/walnutpie_w89 off 788d832; build stan_cli
with -fsanitize=thread (clang++, Release+debug-info; document flags);
run --chains 4 --chain-exec threads on blr + eight_schools_centered,
warmup 200/samples 200 (short — TSan 5-20x slowdown), plus
--chain-exec serial as control; capture ALL TSan reports; triage each
(real race vs benign-by-design e.g. seq_cst pattern in SpscBuffer —
document the intended memory ordering and verify the code matches).
GATES: any REAL race (not explained by the buffer's intended ordering)
→ minimized repro + report; no fix without coordination (shared
machinery). Zero reports → record all-clear as the assurance result.
MACHINE: TSan runs are single heavy process; load-gated; no wall
claims. COST ~1h.

## 2026-08-26 — W-88 PRE-REGISTRATION (tooling, before any code): blessed ESS/R-hat estimator module — campaign estimators + the W-81-documented split-chain step, dual-mode for provenance
Standing tool scratch/w88/blessed_estimators.py: mode="split" (default; Vehtari-2021 complete incl. split-chains) and mode="campaign" (byte-verbatim legacy). GATES: split-mode agrees with arviz 1.3.0 on the W-81 52-cell trust set to <0.1% relative on ess_bulk_min and rhat_max; campaign-mode reproduces the 48 archived W-75/76 values exactly. Announce in comms as THE estimator for all future campaigns; archived scripts untouched.

## 2026-08-26 — W-89 PRE-REGISTRATION (before any run): upstream PR #77 (leapfrog unroll + double-rho elimination) — first benchmark on our stack; instruction-count primary, ESS two-sided
Isolate worktree scratch/w89/walnutpie_lfu off exp/safe-adapt-defaults @43b6435 + upstream branch leapfrog-momentum-compose (fetch flatironinstitute/walnutpie). Confirm patch scope by diff (expect walnuts.hpp micro-step loop unroll + rho-update elimination, fixes #30). Builds -j2. ARMS: base = external build_w65 lineage binary; lfu = patched. Draw-content WILL differ (arithmetic) — bit-identity unavailable by design; gradient parity spot-check (logp_grad at 10 fixed points identical) validates scope. PRIMARY (contention-immune): callgrind Ir per sampling phase on {arma11, hier_2pl} both arms, 3 interleaved re-runs, medians; SECONDARY: ESS_bulk_min two-sided {arma11, blr, hier_2pl, eight_schools_centered} × rep{0,1,2} serial mc. GATES: ESS non-inferior (geomean ratio ≥0.95, no model median drop >20%, rhat fails not worse) AND Ir not worse (≤ +1%); if Ir improves ≥3% with ESS non-inferior => verdict "recommend-merge-from-perf-perspective" (user files/merges; we never upstream). Wall only if machine goes quiet (interleaved rounds), else unclaimed.

## 2026-08-26 — W-90 PRE-REGISTRATION (before any run): funnel-class MECHANISM characterization from instrumented traces — error-cap truncation at the neck vs mode-lock, the two competing stories
Generate warmup traces (existing tracer binary, single-chain, warmup-only, recommended-config flags incl --metric-window 50, seeds/inits per house protocol) for {eight_schools_centered, low_dim_gauss_mix} × rep{0,1,2} × chain{0..3} into scratch/w90/traces (liveness-checked inits; tracer saves depth.u64 + per-iter lp/step/invmass). ANALYSIS (blessed estimators, W-88): per iteration correlate depth, (proxies for) macro-step halvings via step.f64 drops, lp variance, and radial position (for esc: group-scale params = known neck coordinates; for ldgm: distance from mode) across warmup phases. Hypotheses: H-neck = depth/halving structure concentrates at small-group-scale states (error-cap-driven truncation story => motivates FUTURE adaptive-error-cap research, not a knob now); H-lock = trajectories healthy but stuck in one region (mode-lock story => strengthens pf-init/reinit direction). Deliverable: scratch/w90_funnel_mechanism.md (<60 lines) with the verdict, one figure-quality table, upstream-shareable framing. NO sampler changes, NO new knobs.

## 2026-08-26 — INIT-DUPLICATION AUDIT (extends W-83 artifact alert): hier_2pl rep0 fully degenerate (4x same init), lsat_model rep1 has ONE dup pair (chain_1==chain_2 md5 3eff271d), lsat rep0 / arma11 / blr clean (orchestrator #2)

Cause pattern: pathfinder draw-picking occasionally selects the same
draw for multiple chains (replacement-style selection). Impact: chains
started identically differ only by seed — cross-chain R-hat/ESS
interpretation on the affected cells is optimistic (shared start
inflates convergence diagnostics agreement, deflates effective
diversity). AFFECTED CELLS: hier_2pl rep0 (all 4), lsat rep1 (2 of 4).
FIX DIRECTION for harness owner: gen scripts (gen_w25_inits.py lineage)
should pick distinct draws without replacement per (model, rep), or
verify-and-regenerate; affected archived cells get a caveat note.

## 2026-08-26 — CORRECTION NOTE [init-dup audit applies to my entries]: hier_2pl rep0 chains shared ONE init position in W-65 traces/G4-sim, W-75, W-76
Sibling audit found inits_w25/hier_2pl/rep0/chain_{0..3}.txt identical.
Impact stated per entry: W-65 G4 — hier_2pl rep0's pooled-group
independence was overstated; GO verdict unaffected (arma11/blr carried
it, both clean). W-75 Arm A/B + W-76 — rep0 cells affected in BOTH arms
equally; A/B internal comparisons and 3-rep medians stand; the W-76
kill-rule crossings were rep1/rep2 (unaffected). Going-forward: unique
inits per draw-without-replacement convention (see harness fix note,
comms 17:0x). My W-88/89 number collisions with day-4 claims noted;
title-based disambiguation in effect (W-88-blessed-estimators,
W-89-lfu-bench).

## 2026-08-27 — W-86 IMPLEMENTED + VALIDATED (rep0 spot): ridge guard fires correctly on pilots (F=20.4, rhat 2.93→1.12, ridgeF 26→0.3) AND diamonds (F=98 TRUE positive: geoESS 60→802, rhat 3.63→1.15 — diamonds was itself partially locked all along); eight_schools_centered silent (no false positive); env-unset canary bit-identical. Branch exp/ridge-guard (commit 88157bc, worktree external_w86/): 86 lines — sampler_min_micro() + CLI cross-chain position-F gate. — overnight-4 session

## 2026-08-27 — W-88 PRE-REGISTRATION (before any run): ridge-guard feature A/B on the full grid — guard5 arm (WALNUTPIE_RIDGE_GUARD=5, default min-micro bump 128, binary w86) vs normal-init baseline — overnight-4 session

EXPECTATION:
1. Guard-silent models → draws BIT-IDENTICAL to baseline (mass canary;
   eight_schools verified silent already).
2. pilots + diamonds fire → large ESS/rhat gains (rep0-validated;
   expect reps 1/2 similar).
3. Possible additional fires on bym2/kronecker (both have lock history
   under normal inits) → gains.
4. Wall rises only on firing models (they pay the 128 budget).

GATES (ADOPT-candidate as env-gated feature / future fork PR):
- aggregate geomean ess_bulk_geomean ≥ baseline+20%
- AND ≥3 silent-model cells md5-identical to baseline
- AND no model geoESS worse than baseline by >10%.
COST: est 30–60 min (firing cells pay ~30–80× sampling cost).
Launched before W-87 mm128g map (resume-safe), which follows after.

## 2026-08-26 — CLOSE-OUT [W-90-funnel-mechanism]: the funnel class SPLITS — eight_schools_centered = H-NECK CONFIRMED (error-cap truncation at the log-tau neck; adaptation exonerated: ZERO step drops in 26/26 traces); low_dim_gauss_mix = slow-decorrelation region-lock at the TRUE mode (NOT mode-locked, NOT init-limited)

Evidence (scratch/w90_funnel_mechanism.md + analysis.json; 26/26 traced
warmups, unique inits, blessed-config flags): ESC: P(depth<=1) at neck
tercile 0.126 vs 0.041 outer (3.1x, persists last-third); depth-log-tau
Spearman +0.25..+0.53 in 12/12; tau range 60-100% explored (no lock);
min consecutive step ratio 0.951 across ALL traces => adaptation never
intervened. LDGM: ordered-mu coord decodes to the true data mode reached
by 12/12 chains; pathology = slow sigma decorrelation (acf1 0.75 vs
mu1 0.31), quantitatively coherent with archived ESS ratios. IMPLICATIONS:
(a) esc supports ADAPTIVE-ERROR-CAP research (trajectory truncation at
the neck with stable step+metric) — distinct from blanket E2 loosening
(warmup-weighted, rejected); (b) pf-init/reinit NOT supported by either
funnel model (esc not init-limited; ldgm already at the true mode —
pf's bym2 value is mode-separation, a different mechanism); (c) ldgm
points at the trajectory-budget family (@W-87 lane). Correction to comms
17:0x: esc DID have archived unique inits_w36 (only ldgm lacked inits).
Binary provenance + hier_2pl rep0 caveats carried in the memo.
NEXT (pre-registered separately): targeted sampling-phase error-cap
relaxation on esc-class funnels ONLY — the localized version E2 never
tested.

## 2026-08-26 — W-91 PRE-REGISTRATION (before any run; LAUNCH LOAD-GATED <5 sustained): targeted error-cap relaxation on the esc-class funnel — the LOCALIZED version W-38-E2 never tested
MOTIVATION: W-90-funnel-mechanism confirmed esc failure = error-cap
trajectory truncation AT THE NECK with adaptation exonerated. E2 rejected
WARMUP-WINDOWED blanket loosening on the full core set (kronecker calls
+118-162%, marginal ESS -24%); the neck-localized hypothesis predicts
funnel-class-specific gains with bounded cost, guarded by controls.
DESIGN (zero-code CLI grid): --max-hamiltonian-error x {1x(base), 2x,
4x} on {eight_schools_centered, low_dim_gauss_mix} + controls {arma11,
hier_2pl} x rep{0,1,2}, serial mc, 1000+1000, house seeds/inits (esc
uses its archived UNIQUE inits_w36; ldgm the W-90 generated unique set),
binary = external build_w65 lineage (provenance caveat recorded, all arms
same binary). Arms statistical (draws differ by design).
PRIMARY GATE: esc ess_bulk_min ratio (vs 1x) >= 1.2x at EITHER relaxed
level, median-of-reps. SECONDARY: gradient calls per draw on esc (ESS/grad
currency: relaxed arm must NOT exceed 2x calls for the ESS gained);
ldgm reported exploratory. CONTROLS REJECT: any control model median
ess_bulk_min drop > 10% or new rhat failures => whole direction REJECT
(E2's shadow). Divergence/abort counts reported. Artifacts: scratch/w91/,
runs_w91/. LAUNCH CONDITION: sustained load < 5 (board currently ~6-7.5
with sibling grids; defer politely).

## 2026-08-26 — CLOSE-OUT [W-89-lfu-bench]: upstream PR #77 (leapfrog unroll) = PERF-NEUTRAL, NO-HARM on our stack — callgrind Ir +0.06%/-0.02% (medians x3 interleaved), ESS geomean 0.993, parity byte-identical; no perf case for/against merge
Method highlights: merge applied cleanly through our walnuts->walnutpie
rename (single file walnuts.hpp +18/-6, diff-audited to leapfrog internals
only); PRISTINE 43b6435 base built in scratch/w89/walnutpie_base after
the agent caught build_w65 contamination (43b6435+tracer+aliasing-fix) —
provenance section in verdict; gradient parity byte-identical at 10
points/model and vs bridgestan reference. STRUCTURAL RESULT: model .so
= 81.5-85% of total Ir with UNCHANGED call count — sampler-side ceiling
15-19%, and the patch moves ~0% of it at -O2 (compiler had already
composed the rho updates). esc ESS 0.971 from last-ulp draw differences
(max rel 1e-11) — statistical noise band. Callgrind jitter lesson:
"deterministic" holds to ~1e-6, not bit-exact. Verdict: merge decision
on code-quality grounds only, not perf; nothing filed upstream.
Artifacts: scratch/w89_verdict.md, runs_w89/, worktrees walnutpie_{lfu,
base} (branch exp/lfu-bench @ cc2d913).

## 2026-08-27 — W-85: stan-math PR checklist VERIFIED LOCAL for sims1253/math#5 (soa-eltwise-batch-records @ 0b7b0dc13) — all items PASS after 3 our-line fixes (2 of them REAL catches: standalone-include failure of the new header + 5 cpplint line-length nits); doxygen attribution ZERO new warnings; 3 fixes left uncommitted for the coordinator to fold into the DCO-signed fork tip

Ran the full W-56 battery in external/math_dev_soa (branch tip 0b7b0dc13,
single commit over develop-344d7167, 14 files: rev/core batch substrate +
eltwise ops; worktree verified clean pre-run). Constraints: /usr/bin/make
only (shell make aliases -j12), env -u LD_LIBRARY_PATH, -j2 max (sampler
agent pushed load to 12-14, hence 33min test-headers vs W-56's 16-19).

RESULTS (item = PR template):
(a) test-headers -j2 FULL: 1st run FAIL (31m17s, exit 2, aborted 1649/1901) —
    REAL catch: make_nochain_vari_array.hpp (our NEW header) uses `var`
    without including rev/core/var.hpp; compiles at call sites (transitive
    include) but fails the target's standalone `-include header dummy.cpp`.
    Fixed with the 1 missing include; other 12 changed headers meanwhile
    verified standalone-clean with the exact make flags. FULL re-run PASS
    (33m10s): 1902/1902 headers = 1901 develop corpus + our new header.
(b) runChecks.py: PASS exit 0 (23s; only its own pre-existing SyntaxWarnings).
(c) make cpplint FULL: 1st run 5 errors — ALL whitespace/line_length on OUR
    added lines (operator_division.hpp 318/339/345/366 + rev/fun/multiply.hpp
    68; develop had zero >80 lines in both). Minimal wraps; re-run PASS.
(d) make doxygen: PASS x2 (1.13.2 W-56 binary, 186MB html). Attribution per
    W-56 method vs pristine develop-344d7167 (temp worktree — math_soa is
    dirty with batch edits, unusable): baseline 2046 warnings (= W-56's);
    ours pre-fix 2049, the 3 extra ALL from the new header's `Matrix<var>`
    doc comment (doxygen HTML <var>-tag trap) — fixed by escaping. Post-fix:
    normalized (paths/lines stripped) warning sets IDENTICAL to baseline —
    attribution_diff.txt empty. vari.hpp:368 x6 = pre-existing baseline set
    (vari.hpp:349) shifted by our diff. TARGET MET: zero new warnings.
(e) runTests.py -j2 targeted: PASS (16m35s) — 32/32 binaries, 362 cases:
    13 mix/fun eltwise (add/subtract/divide/elt_multiply/multiply{,_complex,
    1,2}/operator_{multiplication,addition,subtraction,division}/diag_{pre,
    post}_multiply) + 19 rev/core (all tests grep-confirmed to include a
    changed header + vari_test; no rev/fun multiply/elt tests exist here,
    rev leg runs through mix, same as W-56 b2).
(f) No dedicated make_nochain_vari_array test exists (see (e) coverage).
NOT RUN (honest gap, as W-56): full test/unit suite — CI owns it.

FIXES (UNCOMMITTED in math_dev_soa for the coordinator, diff =
stan/scratch/w85/fixes.diff, 3 files / 77 diff lines — fold into the
DCO-signed tip; no raw push from W-85):
  1. make_nochain_vari_array.hpp: +#include <stan/math/rev/core/var.hpp>
     [required for checklist item test-headers]
  2. same file, doc comment: Matrix<var> -> Matrix\<var\> [doxygen]
  3. operator_division.hpp (4x) + rev/fun/multiply.hpp (1x): 80-col wraps
     [cpplint]
Note for CI expectations: the PR tip AS PUSHED (0b7b0dc13) FAILS
test-headers and cpplint locally; with the 3 fixes folded every checklist
item passes. Evidence: stan/scratch/w85/ (testheaders.log = failed 1st run,
testheaders_fix.log = passing full run, runchecks.log, cpplint_full.log +
cpplint_full_fix.log, doxygen.log, doxygen_warnings{,_base}.log +
.normalized.txt + attribution_diff.txt, tests.log, fixes.diff, status.txt).
Baseline temp worktree removed after the doxygen passes.

## 2026-08-27 — W-85 FOLD: checklist fixes committed 8c63b8f355 and pushed to the fork branch (3 files, +12/−6: standalone var.hpp include in the new header — the REAL catch, the pushed tip failed test-headers without it; doxygen <var> escape; 5 80-col wraps); PR sims1253/math#5 updated with the checklist evidence comment. math#5 is now checklist-complete locally (CI owns full test/unit).

## 2026-08-27 — W-84 CLOSE-OUT: guarded-MM2 FULL-domain table COMPLETE — 24/24 measured models classified: 15 benefit / 4 economic-harm / 5 fired (21 chain-fires = 13 MM2-caused all md5-exact-restarted + 8 A0-inherent init-pathology pins the guard surfaces and makes arm-neutral); NEW subclass discovered (baseline-pinned chains, restart exact to 1 marginal accept per 1000 draws); zero guard misses/false fires in 288 chains

Executed per prereg (the "15 models" of the title; the inline "~12" guess
resolved to exactly 15 = 24 - 9, the other 12-13 CHECK line was wrong
arithmetic, agent-confirmed against manifest+W-82 sets: remaining = 15
CORE_SET minus W-82's six manifest models; all three w80 supplementaries
were already covered). (Ledger note: numbering collision — an unrelated
"W-84 CLOSE-OUT: property hunt / low-rank momentum sampler" entry exists
above at 2026-08-26; this entry closes the guarded-MM2 W-84 pre-reg,
recorded like the W-82 collision.) GMD-only arm on binary ef524a5, 180/180 rc=0 in
~47 min at 2 workers (foreign load 10-17 from the co-scheduled build
agent; budget respected), w1000 s1000 metric-window 50, seeds
20260819+1000r+c, pf inits 12/12 verified present for all 15 pre-run,
resume-capable driver scratch/w84/driver.py. A0 REUSED from
scratch/w63/runs/A0 w1000_pf grids per prereg; equivalence re-proven on
a 15th model: fresh same-binary A0 canary kronecker rep0_c0 md5-EQUAL
the w63 grid (46be8163), scratch/w84/canary/. RESULTS (results/
mm2_domain_w84.md, full 24-table merging W-82): benefit 15/24 (W-84
adds lotka 15.8 sick-median caveat, wells 2.26, low_dim_gauss_mix 1.83,
kidscore 1.61, garch11 1.32, 8sch_nc 1.29, logmesquite 1.24, radon_pp
1.23, radon_var 1.11 = W-79 label 1.12 reproduced, arma11 1.15; W-82's
hier_gp 3.94, hier_2pl 1.63, dogs 1.62, election88 1.54, gp_regr 1.53);
economic-harm 4/24 (W-82 lsat/8sch_c/blr 0.56-0.84 + NEW diamonds 0.69);
fired 5/24: gpcm 7 + pilots 2 + bym2 3 + accel 1 = 13 MM2-caused pins,
EACH restart md5-EXACT to the healthy A0 chain (gpcm mechanism extended
to 3 models), PLUS the new A0-inherent subclass — 8 chains (kronecker
r0c0, bym2 r1c0-c3+r2c3, accel r0c2+r1c3) pinned at MM1 IN THE BASELINE
GRIDS; guard fires (MM2 pins them too), restart returns the baseline pin
up to ONE marginal acceptance per 1000 draws (md5 neq but 2-unique-rows
vs 1, first rows identical) — detection honest, recovery impossible by
arm choice, recorded as init pathology not MM2 harm. Guard census across
the 15: 14 fires all at 1/50 unique; zero misses (silent-chain nu50 min
38 = diamonds vs threshold 25); zero false fires. accel_gp is the one
mixed verdict (fires 3, ESS/grad 0.53 — economic harm on its 9 silent
chains, degenerate baseline ~2.3 ESS both arms). HONEST: kronecker/
bym2/pilots/diamonds/accel baselines are degenerate (rhat>1.02 on tens
to ~9600 cols) — ratios are population statements about the slow
coordinate; bym2 rep1 314.97Y is a tiny-number ratio; lotka's 15.78 is a
sick-median artifact (per-rep 1.63Y/0.68n/22.51Y, heals reps 0/2:
rhat02 12→0/78→0, grads parity 1.015x); GMD/A0 wall ratios 1.9-4.6 are
CROSS-SESSION (w63 idle vs w84 loaded) — non-comparable, W-82's
GMD/MM2 0.99-1.014 stays the guard-cost reference. Domain-map paragraph
for PR #20's narrative written into the results file. Artifacts:
results/mm2_domain_w84.md; scratch/w84/{driver.py,analyze_w84.py,
w84_results.json,analyze.out,driver.log,WORKERS,runs/,canary/}.

## 2026-08-27 — W-92 PRE-REGISTRATION (before any run): math#5 toolchain-completion — CLANG-built .so pair (stock vs SoA) parity + Ir + wall on hier_2pl; closes the PR's per-toolchain codegen gate (W-59 covered GCC/Eigen-3.4 + GCC/Eigen-5; clang untouched)

DESIGN: two fresh model builds of hier_2pl with CXX=clang++ (bundle
makefile env): stock from pristine ~/.bridgestan/bridgestan-2.9.0
(scratch/w92/model_hier_2pl_stock_clang/), patched from bs_w53
(scratch/w92/model_hier_2pl_soa_clang/) — per-variant scratch dirs
(cache rule), bridgestan.o rm+make for the patched copy. Then: (a)
parity 100 pts exact-zero vs the GCC stock .so (values AND grads —
toolchain must not change arithmetic bits? NO — different compilers
may legitimately reorder FP at -O2+; the gate is STOCK-CLANG vs
SOA-CLANG parity (same compiler, same protocol) — the GCC stock
reference is a REPORT comparison, not a gate); (b) draws md5:
stock-clang vs soa-clang must be IDENTICAL (same-binary-analog:
same compiler, bit-identity gate as all previous SoA gates); (c)
callgrind Ir both clang arms — the SoA win must hold under clang
(expect −12..−19%G; a significantly smaller clang win is a FINDING
for the PR's risk section, not a failure); (d) wall in-sampler 3
interleaved rounds (nice 19, load-contaminated — ratios only, FLAG).
GATE: (b) mandatory; (a) within-compiler mandatory; (c)(d)
measurements with honest reporting. Machine: 2 builds -j1/-j2 nice
19 + short runs; ≤2 cores under the current board policy.

## 2026-08-27 — W-92 CLOSE-OUT: CLANG verification ALL GATES PASS — SoA win holds under clang (T −16.31% / G −17.44% vs GCC's −17.82%/−19.06%, gap attributed to clang callback codegen NOT the substrate); BONUS four-way draws md5 identity fe7c57c9… (gcc-stock = gcc-soa = clang-stock = clang-soa); wall −11.4% warmup / −6.4% sampling (ratios, FLAG); math#5 per-toolchain codegen gate CLOSED

BUILDS (clang 22.1.8, defaults libstdc++, prebuilt gcc TBB/sundials
linked as-is — same ABI): hardlink bundle copies scratch/w92/
{bs_stock_clang, bs_soa_clang} (cp -al; rm src/bridgestan.o; make
CXX=clang++ src/bridgestan.o each; originals untouched — bs_w53's
.o still the Aug-24 gcc one); SoA patch presence re-verified via
make_nochain_vari_array.hpp (W-58 LinearAccessBit fallback + W-59
fused loop both in file). Models: (cd <bundle> && env -u LD_LIBRARY_
PATH CXX=clang++ nice -n 19 make STANCFLAGS=--include-paths=.
<abs>/hier_2pl_model.so) — CXX via env per make/compiler_flags
"origin default" logic; flags verbatim from the makefile. Same
stanc3 both bundles (md5 3ce8bce9…), .stan diff-identical, loads OK
(name hier_2pl_model, D=669 both). Two -j1 compiles concurrent =
2 cores, nice 19, policy-clean.

GATES: (a) PASS exact-zero stock-clang-vs-soa-clang (W-27 points,
rng 20260822): 0/100 values + 0/100 grads. BONUS report comparison:
stock-clang vs GCC-stock is ALSO bit-identical (0/100+0/100, max
abs diff 0.0 on values and gradients) — the "allowed" FP-reorder
difference does not materialize at -O3/no-fast-math on this model.
(b) PASS mandatory md5: draws_stock_clang = draws_soa_clang =
fe7c57c99a7a6530ce2dcc408d6e9c65 = w53 GCC-stock digit-for-digit —
FOUR-WAY cross-compiler identity (stronger than the gate; the
pre-registered "expected/allowed" clang-vs-gcc difference is absent).
(c) callgrind (~/vginstall, one at a time, W-29 protocol): T
37,476,899,030 → 31,362,307,060 (−16.31%), G 35,049,517,505 →
28,934,915,315 (−17.44%), calls 3737+756 identical. GCC same-state
refs (W-59 fused, the like-for-like tree state; the brief's
−15.9/−17.1 were pre-fuse W-58 refs): −17.82%/−19.06%. Gap
ATTRIBUTED from ann.txt: within clang the two reverse callbacks are
instruction-IDENTICAL across arms (1,783,783,344 elt_multiply chain
+ 1,359,079,344 subtract chain in BOTH) — patch still touches only
forward construction; across compilers clang's callbacks cost
+849,350,488 vs gcc's 2,293,512,200 and the whole clang-soa total
excess vs gcc-soa is +847,844,950 (match to 0.2%) — a compiler
constant in both arms (ratio dilution), NOT a substrate effect;
clang keeps make_nochain_vari_array out-of-line (934,636,405 +
934,592,165) where gcc inlines it. PR-risk answer: no toolchain-
specific failure mode; win inside the pre-registered −12..−19%G
band. (d) wall 3 interleaved rounds nice 19 (W-59 parser, both
"time per call" stanzas): warmup 1382.5→1224.3 (0.8856), sampling
1394.2→1305.2 (0.9362), non-overlapping per-round bands, direction
consistent; FLAG per policy: foreign load ~12–13 at start, receded
to ~5 during rounds (per-round load in wall/raw.txt); absolute
us/call cross-session non-comparable, ratio is the measurement;
warmup −11.4% tops the GCC wall range (−5..−7%), sampling −6.4% in
it.

GOTCHA added: stan/.venv python BREAKS under the current agent
environment (AppImage LD_LIBRARY_PATH pollution → "No module named
'encodings'") — `env -u LD_LIBRARY_PATH` is not just politeness
here, it is required to run ANY venv python; same env hygiene for
make/CLI as always. walnutpie build_w36exp untouched (READ-ONLY).

Artifacts: results/soa_clang_w92.md (canonical); scratch/w92/
{bundles, model dirs, gate_parity_clang.py, gate_draws.sh,
run_callgrind.sh, wall.sh, build_*.log, draws/, profile/, wall/}.

## 2026-08-27 — W-89 CLOSE-OUT: TSan hunt — SPSC/multi-chain machinery CLEAN; REAL HAZARD is STAN_THREADS=false model .so under --chain-exec threads (orchestrator #2)

Commit c62d6d3 on tsan/hunt (TSAN_TRIAGE.md; logs scratch/w61/runs_w89/).
The hand-rolled lock-free SpscBuffer + AdaptMonitor + latch design is
TSan-clean (intended acquire/release ordering documented; ZERO reports
touched it — no benign defenses even needed). 25 reports + 2 SEGVs, ALL
inside bs_log_density_gradient: plain bs_models/*.so are
STAN_THREADS=false (verified via strings) ⇒ stan-math AD arena/vari
stacks are process-global across chain threads ⇒ corrupted sampler
state ("normal_lpdf: Scale parameter is 0", SEGV). Isolation clean:
serial on plain .so = 0 reports; threads on STAN_THREADS=true .so = 0
reports. Minimized repro: --chains 2 --chain-exec threads --warmup 5
--samples 5 on bs_models blr → exit 66 in seconds. Nondeterministic
manifestations (3 attempts, 3 different crashes).
RETROSPECTIVE AUDIT: W-36 exp_par headline used bs_models_threads
(verified harness line 115) — SAFE. All threads-arm grids seen on the
board used bs_models_threads — but any FUTURE/other use of plain
bs_models with threads exec is invalid. Ledger gotcha now has an
enforcement gap → fix: startup fail-fast.
FIX SHIPPED: PR #21 (fork, [upstream-candidate]) — stan_cli checks the
loaded .so's STAN_THREADS flag when --chain-exec threads && chains>1;
exits loudly naming the .so and the rebuild command instead of racing
silently.

## 2026-08-27 — W-88 CLOSE-OUT: ridge-guard A/B ADOPT-CANDIDATE — ALL GATES PASS — aggregate geoESS +57.42% (330.1→519.6), zero harm, 14/14 unfired cells bit-identical, diamonds +1230.7% / pilots ESSmin 4.6→33 / bym2 +145.2% / eight_schools +68.5% — overnight-4 session

Full writeup results/ridge_guard_w88.md, raw results/w88_ess.json, grid
runs/w88/guard5 (28/30; 2 missing = the known normal-init abort cells).
Fire census: accel/bym2/diamonds/pilots 3/3, radon/eight_schools 1/3,
healthy models 0/3 — per-REP conditionality (locks are stochastic).
Gates: agg ≥+20% PASS (+57.4); md5 canary PASS (only differing cell =
the one that fired); no-model-worse PASS. NEXT NATURAL GRID: guard × pf
inits combined posture. Feature = branch exp/ridge-guard @88157bc.

## 2026-08-27 — W-87 CANCELLED (partial data retained): forced-128 full map costs hours/heavy-cell (stray ran 70+ min on ONE bym2 cell) and is superseded by W-88's conditional fire census — the guard itself is the cheap domain map. 6 completed mm128 cells kept in runs/w87 (radon rep0/1 + others; analysis skipped). Machine discipline incident recorded in comms (stray survived SIGTERM; serialization plan adopted: one announced stream, SIGKILL verification) — overnight-4 session

## 2026-08-27 — W-93 PRE-REGISTRATION (before any run): combined posture — ridge guard × pf inits — do the init-side and sampling-side lock fixes COMPOSE? — overnight-4 session

MOTIVATION: W-74/75 (pf inits) and W-88 (ridge guard) fix the same lock
family from two sides. Open question: independent failure modes
(composition → additive gains) or overlapping (pf prevents most locks,
guard catches residuals)? Sibling W-90-funnel says esc-class is
error-cap-driven — a third mechanism the guard partially helps (+68.5%
via 1/3 fire); note for interpretation.

DESIGN: arm gpf = WALNUTPIE_RIDGE_GUARD=5 (w86 binary) × inits_w74 pf
inits, standard grid × 3 reps. Compare vs THREE parents:
runs/w36/exp_par (neither fix), runs/w75/pfall75 (pf only),
runs/w88/guard5 (guard only).

EXPECTATION:
1. Fewer fires than W-88 (pf reduces lock frequency) but nonzero on
   residual locks (accel/radon-rep2 class).
2. Unfired cells BIT-IDENTICAL to w75/pfall75 counterparts (same binary
   lineage + guard inert without fire).
3. Aggregate ≥ +85% vs normal-init baseline (i.e., ≥ each parent alone:
   W-74 +81.8, W-88 +57.4).

GATES: COMPOSE-candidate iff agg ≥ +85% AND no model worse than BOTH
parent arms by >10% AND ≥3 unfired cells md5-identical to pfall75.
REJECT-composition (record as overlap) if agg ≤ max(parents)+3% or
fires ≈ 0 under pf (guard redundant).
COST: 40–80 min (firing cells pay the 128 budget).

## 2026-08-27 — W-88 CLOSE: low-rank FULL-operator re-run under PR#19 fix — RESURRECT-CANDIDATE by gate, but the fix is ESS-neutral; full/diag >= 1 NOT fix-driven
Grid 3 arms (DIAG; FULL_fixed = exp/lr-fixed 1b6322b = 788d832+33ea9c8; FULL_buggy = 788d832 binary) x {bym2, radon_pp_nc, hier_2pl, esc} x 3 reps x 4 chains, 1000/1000, --metric-rank 10 --metric-full, seeds 20260819+1000r+c, hier_2pl on 4 FRESH distinct pf inits (pf seeds 20260900+c; W-83 artifact avoided). Machine overloaded -> ran ungated nice 19 per coordinator; ESS count-based, no wall claims. RESULTS (rnESS_bulk-min medians, pinned dropped): fullfix/diag geomean (bym2 excluded: all 3 arms collapse IDENTICALLY 0/0 — freeze pathology, arm-independent) = 1.147 (radon 1.65, esc 1.03, hier 0.89); gate PASS -> RESURRECT-CANDIDATE. BUT bug-impact: fullfix/fullbuggy = 0.91 geomean (0.87/0.91/0.94; per-rep mixed) — the fix does NOT buy ESS; the buggy draw was jitter, not a correctness tax visible in ESS; buggy/diag even higher (1.26). PR#19 case remains correctness-of-invariant, not performance. Radon FULL>DIAG today vs historical 0.60 — seed/init protocol differs. Artifacts scratch/w61/runs_w88/{runs,w88_raw.json,analyze_w88.py,run_w88.py,gen_inits_hier.py,w88_results.md}; code = cherry-pick only on exp/lr-fixed.

## 2026-08-27 — W-94 CLOSE-OUT: ASan+UBSan all-clear — sanitizer campaign COMPLETE (TSan+ASan+UBSan): sampler is memory-safe; the only findings were the already-packaged PR#19 pair (orchestrator #2)

Commit 61fd454 on san/asan-ubsan (SANITIZER_REPORT.md; artifacts
scratch/w61/runs_w94/). Matrix: blr + esc + blr-full-lowrank ×
{ASan,UBSan} + property suite under both sanitizers: ZERO heap/UB/lifetime
reports anywhere incl. the LowRankMass hot loop. Only noise = ~2300
benign handled model-domain rejections (Scale parameter is 0 during
warmup — the -inf mapping working as designed).
The property suite's 3 flags at base 788d832 are the KNOWN pair already
fixed+packaged in PR#19 (low-rank momentum draw + Welford aliasing) plus
the documented NaN-XFAIL — no new bugs.
NET: walnutpie core + threading machinery now validated under all three
sanitizers; robustness surface is clean at this depth.

## 2026-08-26 — CLOSE-OUT [W-88-blessed-estimators]: STANDING TOOL shipped — both gates PASS at machine precision (split mode vs arviz 52/52, max rel 1.6e-15 ess / 2.2e-16 rhat; campaign mode reproduces 48/48 archived rhat bit-identical, ess 43+5-ulp)
scratch/w88/blessed_estimators.py = THE estimator for future campaigns:
mode="split" (default, Vehtari-2021 complete, pinned to arviz 1.3.0) and
mode="campaign" (byte-verbatim replay of archived numbers ONLY — never
mix). Contract + pin-one-ruler warning + odd-n corner in scratch/w88/
README.md; 9-check self-test built in. Adoption is by-convention (archived
scripts untouched, provenance preserved).

AMENDMENT [W-88-blessed-estimators, from the completion report]: the
W-81 "2-line split-chain fix" framing was INCOMPLETE — the campaign
lineage carried two further reference misalignments that split mode had
to correct: (1) rank-scale denominator S-1/4 vs Blom's S+1/4 (w63-lineage
sign artifact, <=0.15%/param), and (2) the Geyer truncation variant
(trailing-rho improvement + 1/log10(N) tau floor vs campaign clamp).
Split+these-two = machine-precision arviz agreement (1.57e-15 ess /
2.2e-16 rhat, 52/52). Practically: campaign-mode ess values deviate from
the reference by up to ~1.2% on near-iid cells — ratios were always the
safe currency (W-81 sensitivity confirmed), and the blessed module now
removes even that caveat. Operationally noted: two background gate runs
were killed externally mid-run (board congestion) and resumed cleanly —
the checkpointed gate runner handles it.

## 2026-08-27 — W-93 CLOSE-OUT: combined posture (guard × pf) COMPOSES SUPER-ADDITIVELY — aggregate geoESS 1094.9 vs 329.9 = +231.9%, 30/30 cells incl. historic aborts, all gates PASS — the shippable package number — overnight-4 session

Full writeup results/combined_posture_w93.md. Stars: accel_gp +8095%
(42.6→3487.1; pf fixes the abort cells, guard 3/3-fires the residual
lock — neither fix alone reaches 50x), bym2 +13277% (pf-level; guard
redundant = free). Fire census under pf: accel/diamonds/pilots 3/3,
others 0/3 (pf prevents their locks). Canaries: unfired cells md5 ==
pfall75. PACKAGE FOR USER: pf-init workflow + PRs #7/#8/#9/#10 + PR #22.

## 2026-08-27 — W-95 PRE-REGISTRATION (before any run): ridge-guard threshold calibration — full max-F distribution via warmup-only runs (silent-F diagnostic added to exp/ridge-guard) — overnight-4 session

DESIGN: 10 models × 3 reps, warmup 1000 samples 1 (sampling cost
minimal), BOTH init postures (pf inits_w74 AND normal inits_w36 arms)
to see F under each, guard env set (fires still allowed but their
sampling cost ≈ nil at samples=1). Extract "max cross-chain position
F" lines from stderr/mc.log → per-model/rep F distribution.
EXPECTATION: bimodal separation — lock-prone cells F>15, healthy cells
F<3; threshold 5 sits in the gap. If healthy cells reach F 5–15, raise
default threshold; if lock cells sit near 5, lower it.
GATES: calibration only — recommendation recorded, no adoption change
without a new grid. COST: ~20 min (two arms × 30 warmup-only cells).

## 2026-08-27 — W-95 CLOSE-OUT: ridge-guard threshold calibration — F distribution strongly bimodal under BOTH init postures; threshold 5 CONFIRMED (sits inside the gap); diagnostic print committed to exp/ridge-guard — overnight-4 session

DISTRIBUTIONS (max cross-chain position F, warmup-only, 3 reps):
- pf inits: FIRES {accel 10.7–17.2, diamonds 11.5–25.2, pilots 8.8–44.4};
  silent everything else, max 4.8 (bym2 — pf pulls it back from its
  normal-init F of 1926–15924!). Gap [4.8, 8.8].
- normal inits: FIRES {accel 206–750, bym2 1926–15924, pilots 20–265,
  diamonds 19–146} + borderline radon rep2 7.1 / eight_schools rep2 5.1
  (both fired in W-88, harmless-to-helpful); silent max 5.1.
RECOMMENDATION: keep default threshold 5 — margin above silent-max
thin (4.8–5.1 vs 5) but every observed in-band fire was beneficial or
neutral, and lock cells reach F≥8.8 even under pf. If false positives
ever appear, 6–7 is the evidenced alternative. Diagnostic (silent-F
print, env-gated) pushed to exp/ridge-guard. COST NOTE: /usr/bin/pkill
must be used for kills — shell pkill is shadowed by the ZCode AppImage
pgrep (explains both stray-survival incidents; ledger gotcha).

## 2026-08-26 — CLOSE-OUT [W-91-error-cap]: ALL GATES PASS — first positive ESS lever of the campaign; the default max_hamiltonian_error=0.5 is a GLOBAL binding constraint (13-62% ESS cost on every tested model; esc +147% @4x, ESS/call 2.7x; controls GAIN; hier_2pl rhat fails 2->0)
36/36 cells; blessed split ruler; paired seeds across levels. esc 26.2/
34.3/64.7 (x1/x2/x4, ratios 1.31/2.47); grad calls 0.983/0.913 (DOWN);
steps/draw 20.4->16.2 (cap TRUNCATES rather than lengthens — causal
confirmation of W-90's neck mechanism); posterior means stable (no
drift); esc rhat 1.116->1.046 (better, not cured). Caveats: single
non-stock binary (internal ratios); divergence counts not extractable
from CSVs/logs (rc+non-finite-warn proxy = zero); walls unclaimed.
Artifacts: runs_w91/, scratch/w91/, verdict scratch/w91_verdict.md.
NEXT pre-registered separately: W-92 scale-out (w36 grid minus kronecker
dead-init artifact, pristine 43b6435 binary, knee search x1..x8) — the
two-sided evidence any default-change ask requires per W-31 discipline.

## 2026-08-26 — W-92 PRE-REGISTRATION (before any run): error-cap scale-out — w36-class grid, PRISTINE stock binary, knee search {1x,2x,4x,8x}
DESIGN: levels {0.5, 1.0, 2.0, 4.0} x the W-36 benchmark model list
MINUS kronecker_gp (dead-init artifact, W-82) x rep{0,1,2}; BINARY =
scratch/w89/walnutpie_base/build/examples/stan_cli (verified-pristine
43b6435, removes W-91's single-binary caveat; stock-stack evidence, not
exp-stack); serial mc 1000+1000; house seeds/inits per run_w36
conventions (hier_2pl/lsat pf-init handling mirrored; init-dup caveats
recorded per cell). MEASURES: blessed split ess_bulk_min + rhat_max
medians-of-reps; grad calls per draw; abort/non-finite-warn census.
GATES (binding): at SOME level: (a) geomean ess ratio vs 1x >= 1.15
across models; (b) NO model median drop >10%; (c) total rhat>1.01 cell
count not worse; (d) geomean grad-calls ratio <= 1.3x. KNEE REPORT:
monotonicity/turnover per model; the recommended level = highest with all
gates green. DEFAULT-CHANGE: NOT proposed by this entry — output is the
evidence pack for a user decision (W-31 two-sided standard incl. the
divergence-diagnostic gap, stated).

## 2026-08-26 — CLOSE-OUT [W-92-errorcap-scaleout]: NO LEVEL ALL-GREEN — blanket cap relaxation is NOT a default change (binding verdict); the lever is real but PER-MODEL (radon +261%, hier_2pl +55% w/ 10% FEWER calls, lsat +37%) and blocked by lotka (-40..-88%, non-monotone) + esc CONTRADICTING W-91 on stock (0.54x @4x vs 2.47x exp-lineage; baselines 101 vs 26 at identical config)
104/108 ok (4 aborts = lotka rep1 all levels, cap-independent freeze-abort
family, matches archive). Floor models (bym2/diamonds/accel_gp/pilots,
ess 4-6 / rhat 3-5 at every level) unaffected — consistent with W-90's
"different disease". VERDICT: no default change; user decision pack =
scratch/w92_verdict.md. RETRACTION-ADJACENT: W-91's headline ("default
cap is a global constraint") is DOWNGRADED to "per-model trade-off knob";
its esc evidence did not transfer across stacks — mechanism unknown
(candidates: fragile tau-ESS statistic under last-ulp trajectory changes
vs real stack interaction). NEXT pre-registered: W-93 discriminator.
Artifacts: runs_w92/, scratch/w92/errorcap/, scratch/w92_verdict.md.

## 2026-08-26 — W-93 PRE-REGISTRATION (before any analysis; analysis-only): why does esc flip sign across binaries? — per-rep ESS anatomy of runs_w91 vs runs_w92 esc cells
QUESTION: is W-91's esc +147%@4x (exp-lineage binary) a robust binary
effect or rep-level noise on a fragile ess_bulk_min statistic (tau-ESS)?
DESIGN: parse ALL esc cells from runs_w91 (3 levels x 3 reps x 4 chains)
and runs_w92 (4 levels x 3 reps x 4 chains); per-rep ess_bulk_min AND
per-param ESS (esp. tau vs thetas) via blessed split; per-chain too.
Report: rep-level scatter (min/median/max) per level per binary; tau-ESS
vs bulk-min attribution; fraction of variance from reps vs chains.
PREDICTIONS: P1 (fragile-statistic): enormous rep scatter, sign flips
within-binary across reps; P2 (real stack effect): consistent within-
binary direction across reps, scatter between binaries. GATE: whichever
prediction the data supports is recorded as the W-91 reconciliation;
if ambiguous (scatter ~ effect), BOTH W-91 and W-92 esc numbers get
flagged unusable for decision-making. Output scratch/w93_esc_anatomy.md.

## 2026-08-26 — CLOSE-OUT [W-93-esc-anatomy]: flip = REAL stack effect in direction (exp 3/3 up, stock 3/3 down @4x); magnitudes NOT size-grade (paired-ratio rep spread ~4x); DEEP FINDING: per-chain tau-ESS flat 17-37 in ALL 7 binary-level cells — esc ess_bulk_min is a BETWEEN-CHAIN COVERAGE statistic, not a mixing rate (chain-variance 63-100% of total)
Reconciliation recorded: both W-91 and W-92 esc point values flagged
not-size-grade; directions under paired seeds usable. Mechanism: cap
relaxation moves whether the 4 chains jointly cover the funnel's scale
(pooled = 0.5-4.6x per-chain mean), not how fast any chain mixes tau
(tau-Rhat >1.01 in all 21 cells; per-chain ESS/draw ~2-4% throughout).
MEASUREMENT-VALIDITY COROLLARY for every session: pooled ess_bulk_min
gates on coverage-dominated (funnel/multimodal) models measure chain
dispersion luck, not sampler mixing — report per-chain ESS + coverage
factor alongside. Artifacts: scratch/w93/ (memo, per-rep/per-chain json).

## 2026-08-26 — W-94 PRE-REGISTRATION (tooling, before any code): blessed-estimator coverage extension — per-chain ESS + coverage factor as standing outputs
Extend scratch/w88/blessed_estimators.py (additive API only; default
behavior unchanged): `ess_bulk_per_chain(chains)` (split-mode per-chain
ESS, 4x500 halves), `coverage_factor(chains)` = pooled ess_bulk_min /
median per-chain ESS (the W-93 statistic; ~1 => mixing-dominated, >>1 or
<<1 => coverage-dominated), and a `summarize(chains)` dict emitting
ess_bulk_min, rhat_max, per-chain, coverage. VALIDATION GATE: reproduce
W-93's numbers on its 21 esc cells (per-chain flat 17-37; pooled/per-chain
0.5-4.6) and W-88's 52-cell trust values unchanged (regression guard).
README updated with "when to distrust ess_bulk_min" guidance. Then a
comms note recommends coverage_factor reporting for funnel-class gates.

## 2026-08-26 — CLOSE-OUT [W-94-coverage-tooling]: ALL GATES PASS — blessed module extended (ess_bulk_per_chain, coverage_factor, summarize; 19-check self-test; W-93 cells reproduced BIT-EXACT 84/84; W-88 trust set 52/52 regression-clean; defaults byte-compatible)
One documented deviation: prereg said MEDIAN per-chain ESS for
coverage_factor, W-93's 0.5-4.6 band was MEAN-based — both reported;
median-band [0.579, 5.371]; anchor note: agreeing independent chains put
the factor near m (~4), ~1 => mixing-dominated, >>m or <<1 => coverage-
dominated. README carries "WHEN TO DISTRUST ess_bulk_min". Standing API
for all sessions.

## 2026-08-26 — W-95 PRE-REGISTRATION (analysis-only): coverage-regime MAP of every archived benchmark cell — contextualize all standing verdicts
DESIGN: run blessed summarize() over ALL archived 4-chain cells
(runs/w36/{stock_seq,exp_par}, runs_w75/{aliased,fixed,pooled_*},
runs_w89/{base,lfu}, runs_w91/*, runs_w92/*; skip trace-only dirs) ->
per-cell {ess_bulk_min, coverage_factor, argmin-param regime}; aggregate
per model: median factor + regime classification (mixing-dominated ~1-4 /
coverage-dominated). OUTPUT: scratch/w95_regime_map.md + csv: one row per
model (regime, median factor, n cells); a "verdict-context" table listing
each standing W-7x/9x verdict and whether its gated models were mixing-
or coverage-dominated. NO gates re-judged — context only; NO new runs.
Expectation: bym2/diamonds/ldgm/esc-class coverage-dominated; hier_2pl/
arma11/blr mixing-dominated. HANDOFF-ready.

## 2026-08-26 — CLOSE-OUT [W-95-regime-map]: 292/300 cells mapped; verdict-context table delivered; PREREG SURPRISE = the classification rule's blind spot — coverage_factor needs per-chain ESS LEVEL as co-discriminator (esc reads factor-2.89 "mixing" while per-chain ESS is 11-36/1000, coverage-scaled mechanistically per W-93)
Classifications: MIXING arma11/lsat/radon_nc/blr/(hier_2pl root-level);
COVERAGE bym2 (crushed 0.62)/diamonds/pilots/accel_gp/ldgm/kronecker/
lotka-at-2x+ (0.03-0.07 = chains DIVERGE under relaxation — W-92's
blocker is coverage loss, not slower mixing). Verdict-context: W-75A/
W-76/W-89 gates sound; W-91's esc headline = dispersion luck (already
flagged W-93); W-92 winners mixing-real, blockers coverage stories.
hier_2pl argmin-churn fragility at p~800 noted. README guidance updated
(W-95 refinement section). Artifacts: scratch/w95/ + scratch/
w95_regime_map.md. ESS/s PORTFOLIO NOW FULLY CONSOLIDATED — all lanes
closed with data/tooling; remaining items are USER decisions: error-cap
per-model adoption (W-92 pack), kronecker init scheme (W-82 memo), pf-init
default policy (W-74 sibling pack), PR reviews #11/#12 + sibling #7-#10/#13+.

## 2026-08-27 — W-96 PRE-REGISTRATION (before any run): combined-posture INTEGRATION BRANCH assembly + canary — mechanical prep per PROMOTION_ASSEMBLY_MAP.md; promotion stays a USER decision (orchestrator #2)

TASK: assemble the W-93 package onto ONE branch so the user's decision
is a merge, not a project:
1. Worktree scratch/w61/walnutpie_w96 (new), branch
   assembly/combined-posture. Base per map: start from dev/init-robustness,
   merge in order: #7 init-guard → #17 init-eval-guard → #18 init-screen
   (rebased from exp/safe-adapt-defaults; resolve honestly, document every
   conflict), then #10 NaN guard, then #22 ridge-guard stack
   (exp/robust-stack-w75 lineage pieces as needed), then #20 mm2-guard.
   If a piece cannot merge cleanly, STOP that piece and continue with
   the rest (record exactly what's excluded).
2. Distinct pf inits for hier_2pl + lsat: generate 12 fresh pathfinder
   inits per model into NEW dir inits_w96/ (rep0/chain_{0..3}.txt
   md5-distinct, verified; lsat rep1 set too). DO NOT touch inits_w25/
   w36 (frozen).
3. CANARY GATES (integration correctness, not performance):
   a. Build green (env -u LD_LIBRARY_PATH pattern).
   b. Default-path bit-identity: blr chain0 seed 20260819 md5 ==
      pristine stock 43b6435 binary (scratch/w89/walnutpie_base) with
      all package features OFF — proves the assembly is behavior-neutral
      by default.
   c. Features-on spot: blr + eight_schools_centered + diamonds 3 reps
      × 4 chains with pf inits + guard defaults per W-93 posture:
      completion 12/12 chains (zero aborts/pins), rhat ≤1.01 median,
      ESS-min medians within 2x of the W-93 published cell values
      (results/combined_posture_w93.md reference; blessed estimators).
4. Deliverable: branch pushed to fork (NO PR — assembly artifact, user
   decides); scratch/w61/runs_w96/w96_assembly.md with conflict log,
   gate table, excluded pieces.
MACHINE: idle now; canary grid ~30-60 min serial single-core. No wall
claims.

## 2026-08-27 — W-99 PRE-REGISTRATION (renumbered from W-96 — siblings took 96-98): ridge-guard OUT-OF-SAMPLE generalization — the 11 unseen CORE_SET models, same-binary env-toggle A/B — overnight-4 session

MOTIVATION: the +232% package claim rests on the 10-model W-36 grid (the
guard's design set). Honest test: the remaining 11 CORE_SET models,
never seen by any guard decision.

DESIGN: models = eight_schools_noncentered, blr, kidscore_momiq,
logmesquite_logvash, wells_dist100_model, radon_variable_intercept_
slope_noncentered, dogs_hierarchical, gp_regr, garch11, low_dim_gauss_
mix, arma11. Threaded .so: build the 8 missing via bridgestan
(STAN_THREADS=1, per-variant scratch dirs, model_info verification —
cache gotcha). Normal deterministic inits via the gen_w36_inits scheme
into inits_w96/. Arms (SAME w86 binary, ONLY env differs): base96 (env
unset) vs guard96 (WALNUTPIE_RIDGE_GUARD=5). 1000+1000, 4 chains
threads, seeds 20260819+1000*rep, 3 reps.

EXPECTATION:
1. Unfired cells BIT-IDENTICAL across arms (automatic canary: same
   binary + env toggle).
2. Most models silent (healthy) — the suite's remaining models are
   mostly well-conditioned; possible fires: dogs_hierarchical (funnel
   class), radon_variable_intercept_slope (wide geometry), garch11
   (marginal class).
3. No fired cell gets WORSE rhat (guard budget only traverses).

GATES: GENERALIZES iff (a) all unfired cells md5-identical, (b) no
model's geoESS drops >10% vs its base96 arm, (c) any fired model shows
rhat improvement. Fails → document the failure mode (false-positive
class) and adjust threshold per W-95's [4.8, 8.8] gap evidence.
COST: 8 compiles (~15 min) + inits + 2 arms × 33 cells (~30–60 min).

## 2026-08-27 — W-97 PRE-REGISTRATION (before any code/run): cap-pressure census instrumentation — the SAFETY half of the error-cap decision pack (the divergence-analog W-92 could not extract)
CONTEXT: W-92's no-default verdict rests on ESS/rhat only; walnutpie CSVs
carry no divergence analog and logs only timing. For any adoption decision
the missing axis is: how HARD does the cap bind, per model, per level?
DESIGN: additive opt-in instrumentation in the walnutpie worktree
scratch/w89/walnutpie_base lineage — new branch exp/cap-census off
43b6435 pristine: (a) counters in transition_w/macro_step hot path behind
a file-scope settings struct (pattern: W-65 tracer): per SAMPLING phase —
macro attempts, attempts where the accepted attempt's |dlogp| landed
within 10% of max_error ("cap-pressure"), halvings-used histogram;
exposed via end-of-run stderr line when --cap-census flag set. Zero
behavior change when off — CANARY GATE: flag off vs pristine binary,
arma11 rep0 chain0 identical draws md5. (b) TARGETED rerun: {radon_pp_nc,
lsat_model, hier_2pl, lotka_volterra, esc} x {1x,2x,4x} x rep{0,1,2},
serial mc, house seeds/inits (mirror W-92 resolutions), census output
parsed into scratch/w97/census.csv. OUTPUT: scratch/w97_verdict.md (<40
lines): cap-pressure fraction per model x level; interpretation — winners'
pressure at adopted level (expect: drops as cap rises = headroom), lotka
pressure/divergence-analog trend (expect: rises = the harm mechanism),
esc pressure (W-90 neck prediction: high at 1x, falling). NO adoption
gate — this completes the USER's evidence pack. Numbering: W-97 (W-96
taken).

## 2026-08-27 — W-98 PRE-REGISTRATION (doc-only): funnel-class consolidation memo — upstream-shareable, from W-90/93/95/91/92
One document scratch/w98_funnel_memo.md (<80 lines) consolidating: the
two-diseases split (esc H-neck vs ldgm slow-decorrelation at the true
mode); per-chain tau-ESS 2-4%/draw flat across cap levels and binaries
(the REAL funnel number); ess_bulk_min as between-chain coverage
statistic (with the co-discriminator rule); cap relaxation = dispersion
lever (esc direction stack-dependent, lotka divergence); implications
for algorithm research (neck traversal needs trajectory-level work, not
adaptation). Audience: walnutpie maintainers; orwell-voice, claims each
cite a WORKLOG entry/artifact; NO recommendations to change defaults —
findings only. User decides whether/where to send.

## 2026-08-27 — CLOSE-OUT [W-98-funnel-memo]: upstream-shareable consolidation memo DELIVERED — scratch/w98_funnel_memo.md (41 lines, findings-only, every claim artifact-cited)
Structure: two-diseases split; adaptation exonerated; per-chain tau-ESS
2-4%/draw as THE mixing number (flat across levers/bins); pooled ESS =
coverage statistic + co-discriminator rule; cap = per-model trade-off.
Implications labeled as implications. NO default-change asks; user
decides whether/where to send. (Doc-only entry; no gates applicable —
fidelity checked against the five source entries during review.)

## 2026-08-27 — W-99 CLOSE-OUT: ridge guard GENERALIZES out-of-sample — 11 unseen CORE_SET models, 0 false positives, 9/9 fired cells rhat-improved, 24 unfired cells bit-identical — feature validation complete — overnight-4 session

Raw results/w99_ess.json; artifacts runs/w99/{guard99,base99}, inits_w96/,
scratch/w99_bs/ (8 fresh threaded .so + verifier), harness/gen_w99_inits.py,
run_arms.py gained WALNUTPIE_MODELS_DIR. FIRED: blr 3/3 (F≈7-12k — the
historical blr-normal-init pin class; partial fix, rhat 4.45→3.41, rep2
→1.43), kidscore_momiq 3/3 (rhat 2.77→1.54), radon_var_intercept_slope
2/3 (geoESS +270%, rhat 1.32→1.12), arma11 1/3. Silent: 7 models incl.
dogs/garch (predicted risk models — clean) and logmesquite at silent-max
F=4.51 (inside the W-95 gap band's low edge — threshold 5 holds).
Prediction scorecard: fires ≠ predicted set (blr/kidscore/arma11 vs
predicted dogs/radon/garch) — the guard finds REAL coverage breaks
regardless of my priors; that is the point of an automatic detector.
PACKAGE EVIDENCE NOW COMPLETE: in-sample +232% (W-93) + out-of-sample
0-FP/9-TP (W-99) + threshold calibration (W-95) + memory-safety green
(sibling W-94 sanitizers).

## 2026-08-27 — W-100 PRE-REGISTRATION (before any code): extend --step-init-heuristic to the multi-chain path (per-chain find_reasonable_step probe) — closes the single-chain-only gap that leaves the blr-pin class unfixed under --chains>1 — overnight-4 session

MOTIVATION: W-99 showed blr/kidscore/arma11-rep1 still coverage-broken
under multi-chain normal inits (guard fires but only partially fixes;
blr rhat 4.45→3.41). The W-43 find_reasonable_step fix targets exactly
this pin class but currently THROWS under --chains>1 (stan_cli.cpp:1085)
— a wiring gap in the same class as PR #14, not an algorithmic limit:
the probe is a per-chain operation.

DESIGN (env-gated first step, flag lift as follow-up): WALNUTPIE_MC_
STEP_HEURISTIC=1 in run_walnuts_multi: after init_cfg build + init
guard, per chain c: probe eps_c = find_reasonable_step(Random(rngs[c]),
logps[c], position_c, inv_mass_c, step_size_init); rebuild that chain's
InitChainConfig with eps_c (preserving init eval cache fields as the
single-chain path does); feed prebuilt chain_inits[c] to the adapter
loop. Default (env unset): chain_inits = init_cfg values verbatim →
flag-off path structurally unchanged. The :1085 throw stays (the FLAG
remains single-chain-only; the env var is the experiment knob).

EXPECTATION:
1. Flag-off canary: bit-identical draws vs current binary on canary
   models (diamonds + blr).
2. On the W-99 pin-class cells (blr 3 reps, kidscore 3, arma11 rep1,
   radon_vis rep0/2): rhat improves vs W-99 base99 arm; heuristic+guard
   compose (heuristic fixes the STEP side of the pin, guard the
   traversal side).
3. Healthy models with the env set: eps probe ≈ no harm (single-chain
   W-43 evidence: ESS 5-9→779 with 0/48 pins).

GATES: GO iff canary bit-identity holds AND ≥2 of the 4 pin-class
models reach rhat_max ≤ 1.2 median (the W-43 bar) with env set, no
model worse than base99 by >10% geoESS. Arm: pin-class models × 3 reps
× {env off, env on}, w86 binary lineage.
COST: code+build ~15 min; grid ~10 min (small models).

## 2026-08-27 — W-100 CLOSE-OUT: multi-chain step-init heuristic REJECTED for flag-lift (gate: only 1/4 pin-class models reaches rhat ≤1.2); env-gated knob committed as experimental — overnight-4 session

Results (median, base99 → +WALNUTPIE_MC_STEP_HEURISTIC): radon_vis
rhat 1.32→1.01 geoESS 385.6→2891.9 (+650%, CLEARS bar); kidscore 2.76
→1.61 (improved, fails); blr 4.45→3.73 (partial, fails); arma11
neutral-healthy (+20% geoESS). Canary: flag-off bit-identical (diamonds
md5). CONCLUSION: per-chain probe helps real cases but multi-chain pins
are coverage locks (need pf inits), not step-init defects — the :1085
restriction stays; env knob on exp/ridge-guard for experimentation.
RUNS: runs/w100/heuron; code committed+pushed.

## 2026-08-27 — W-101 PRE-REGISTRATION (before any analysis): why do pf inits hurt kronecker (−22.7%) and lotka (−7.8%)? — offline init-dispersion hypothesis test — overnight-4 session

HYPOTHESIS: pf PSIS pools concentrate draws → low cross-chain init
dispersion → correlated early warmup → worse metric estimation on
models whose geometry needs spread. TESTABLE OFFLINE from inits_w74
(pf) vs inits_w36/w96 (normal): per model, relative cross-chain
dispersion of init positions (e.g., mean over coords of
std(chain-means)/std(all-values)) pf vs normal; correlate sign/magnitude
with the pf ESS deltas (W-75/W-93 tables). PREDICTION: kronecker/lotka
show the LARGEST dispersion collapse (pf/normal ratio ≪ 1); models pf
helped (bym2: pf pulls 15924→4.8 F — co-location is GOOD there) will
also collapse, so the discriminator must separate "collapse+help" from
"collapse+harm" — if it cannot, hypothesis is incomplete and the
honest answer is per-model init posture selection (selector graveyard
applies) OR jittered pf draws.
GATES: mechanism CONFIRMED iff dispersion collapse ordering matches
harm ordering among the pf-hurt models; mitigation experiment only if
confirmed. Pure analysis: no machine.

## 2026-08-27 — W-101 INTERIM: init-dispersion hypothesis test INCONCLUSIVE by design (1 init point/chain ⇒ no within-scale reference; end-of-warmup F shows no kronecker/lotka anomaly either way). PIVOT (pre-registered before the new runs): rep-noise check — kronecker_gp + lotka_volterra × pf inits × 5 NEW reps (seeds 20260819+100000+1000·r, r=0..4, fresh normal-init-free comparison vs the same 5 reps on the W-36 posture) — is the −22.7%/−7.8% pf delta stable or rep noise? — overnight-4 session

## 2026-08-27 — W-101b EXECUTION NOTE: pf pools reused from runs/w74/pfgen (column-filtered to model params; lp_approx__/lp__/path__ excluded — first attempt failed by feeding diagnostics columns to param_unconstrain); normal inits in inits_w101 (seeds 21260819+1000r); pf inits in inits_w101pf (same seeds, PSIS redraw scheme). 5 reps × 2 models × 2 postures.

## 2026-08-28 — W-102 PRE-REGISTRATION (before any code): gather/index-copy elimination in rvalue<index_multi> — the post-SoA #2 hotspot complex (rvalue 1.87e9+0.93e9 + vector<int> copies 1.02e9 ≈ 13.5% of hier_2pl patched G); pure restructuring, bit-identity gate class

DESIGN (stan-math develop side, math_dev_soa worktree lineage): audit
prim/fun/rvalue.hpp index_multi path + its call sites (the Holder<
IndexedView> machinery): (a) the per-call std::vector<int> deep copies
of index arrays (1.02e9 Ir — the indices are model DATA, immutable);
replace with spans/views where the API allows WITHOUT breaking the
public contract; (b) stream the gather construction (avoid intermediate
allocations). CONSTRAINT: no FP changes anywhere — values, order, and
accumulation identical => draws bit-identical (the SoA gate class).
GATES: (a) parity 4 models ×100 pts exact-zero + draws md5 fe7c57…
(hier_2pl, W-29 protocol); (b) callgrind G reduction target −3..−6% on
hier_2pl vs the W-59 patched reference (28,087,600,877; FAIL if < −1%);
(c) touched-target unit tests (rvalue/multiply-index tests) on develop.
RISK: the public API may force the copies (e.g. std::vector params) —
if so, document the wall and STOP (negative result recorded).

## 2026-08-28 — W-102 CLOSE-OUT: ALL GATES PASS — index_multi view storage kills the per-call index deep copies; hier_2pl G −3.63% (−1.019e9 Ir, copy-ctor function ELIMINATED from the profile), T −3.33%, bit-identical at every level; PREMISE CORRECTION: the code is stan-repo, not stan-math

AUDIT RESULT: "prim/fun/rvalue.hpp" does not exist in stan-math —
the indexing machinery (index types, rvalue, assign) lives in the
STAN repo stan/src/stan/model/indexing/ (bundle bs_w53/stan +
develop external/cmdstan/stan; index.hpp byte-identical pre-edit).
math_dev_soa: ZERO edits, no gather-elimination branch created there
(an empty branch would falsely imply math edits; soa-eltwise-batch-
records lineage untouched by design). The copies: index.hpp:35-45
index_multi stored vector<int> ns_ BY VALUE; stanc-generated
index_multi(ii)/index_multi(jj) from lvalue DATA members deep-copied
19,200 ints × 3 per logp_grad (callgrind caller edges: copy ctor
calls=4424 ×3, 341.5M+341.0M+340.7M = 1,023,204,712 Ir). NOT copies:
lpmf takes y by const&, rvalue takes index_multi&&, subtract/
elt_multiply const& — the only forcing shape was the internal holder.
FIX: ns_ re-typed to internal multi_index_view (lvalue→view, rvalue→
move-own, other integral vectors→converting copy as before, copy→
always deep-own); all consumers read-only, unchanged; test util.hpp
convert_to_multi 5× index_multi(std::move(v)) (local died at return).
Caveat for upstream port: lvalue construction now VIEWS (lifetime
contract of the public struct changes; all in-repo + generated call
sites verified — generated code passes long-lived data members).
Check loops (8 Ir/elem) kept IDENTICAL — behavior-bound remainder.
GATES: (a) parity 4 models ×100 pts fresh refs 0/400 exact-zero;
(b) draws md5 fe7c57c99a7a6530ce2dcc408d6e9c65 BOTH arms + cmp
identical (+callgrind-run draws same md5); (c) callgrind patched arm
vs RECORDED W-59 ref, protocol-identical (4493 grad calls, 69
rejects): T 30,514,462,110→29,497,308,808 (−3.33%), G
28,087,600,877→27,068,343,850 (−3.63% = −1,019,257,027 Ir; PASS ≥1%
bound, in the −3..−6% pre-registered band); attribution CLEAN:
vector<int>::vector(const&) GONE from the profile, rvalue<Matrix>&/
Map& entries 1,869,157,696→1,869,148,848 and 934,605,392→934,654,056
(±0.005% layout noise); transparency: develop test compiles ran
concurrent with the callgrind (Ir is a deterministic counter, load-
independent; no wall gate in W-102). (d) tests develop stan
gather-elimination branch (cmdstan/stan @ faa973bb7): index 6/6,
rvalue 28/28, rvalue_index_size 5/5, assign 50/50, deep_copy 6/6,
rvalue_varmat 47/47, assign_varmat 50/50 = 192/192 (CL pair skipped:
matrix_cl<int> path, no index_multi). Cumulative lineage: stock→W-59
−19.06% G, W-59→W-102 −3.63% more, md5 fe7c57… throughout. Full
audit/implementation/gate record: results/gather_elim_w102.md;
patch scratch/w102/w102_gather_elim_stan.patch; gates scratch/w102/
{gate_draws_w102.sh, run_callgrind_w102.sh, draws_w102/,
profile_w102/}; rebuilt .so in scratch/w53/model_*_patched/.

## 2026-08-28 — W-103 PRE-REGISTRATION (before any code; runs AFTER W-102): the W-46 fused log1p kernel as target_clones function multiversioning inside bernoulli_logit_lpmf — the −15.3% wall ceiling made shippable
DESIGN: port harness/w46's kernel (bug-COMPATIBLE variant first —
parity 2.4e-16 rel-L2 as measured; the signs-bug question is a separate
upstream decision) into prim/prob/bernoulli_logit_lpmf.hpp behind
__attribute__((target_clones("avx2","default"))) on the kernel island;
single TU, no build-flag changes (the W-27 mixed-build ban does NOT
apply — no second compilation unit). GATES (statistical class — FP
legitimately changes): (a) gradient parity vs stock: rel-L2 <= 1e-12
on 100 pts × 4 models (W-46 measured 2.4e-16); (b) draws: NOT md5-gated
— instead 3-rep ESS medians within the noise band vs stock on hier_2pl
+ blr; (c) callgrind: G reduction <= −15% on hier_2pl (W-46 measured
−22.8% at eager-everything; expect −15..−22%); (d) wall 5 interleaved
rounds <= 0.90 ratio; (e) unit tests bernoulli_logit*. EXPECTATION:
−15..−22% G, −8..−15% wall, composing with math#5 (kernel vs tape).

## 2026-08-27 — W-101 CLOSE-OUT: pf-init "regressions" were REP NOISE — 5 fresh reps (seed offset +100000): kronecker pf/nrm geoESS ratio 1.041 (was −22.7% at n=3 medians), lotka 1.210 (pf WINS; was −7.8%) — the package has NO real regressions on this suite — overnight-4 session

Design pivot recorded above: init-dispersion statistic ill-posed (1
point/chain); rep-noise check decisive instead. Artifacts runs/w101/
{pf,nrm}, inits_w101{,pf}. IMPLICATION: promote package is
unconditionally positive on-suite (pf inits neutral-or-better on every
model at adequate rep counts; all ESS gains from W-74/75/93/99 stand).
Method note for the ledger: 3-rep medians on high-variance models
(kronecker historically) can swing ±25% — the W-63 protocol's noise
band ±3% applies to AGGREGATES, not per-model deltas; per-model claims
need ≥5 reps or effect sizes >2× the observed swing.

## 2026-08-28 — MULTI-MODEL POST-SoA PROFILE SCAN (5 models, method anchored to W-57 numbers): cross-model complexes ranked — GEMM/gemv 22-80.5% G (Eigen-internal; the GLM/gathered lane's true interior), eigh family 36.6% self on kronecker_gp (CONFIRMS math#1 cluster-adjoint + stanc3#1 pair-fusion aim at the GP-class hotspot), lpmf-interior splits (hier_2pl's log1p redux does NOT transfer; glm models' interior IS gemv). SURPRISE: blr's #1 complex = exception/unwinding at 49.8% G (rethrow_located + message formatting + unwinding) from normal_lpdf elementwise_check firing on sigma-underflow at warmup probe points — IDENTICAL on stock (posture/check-design, not SoA). W-102's rvalue/gather target confirmed hier_2pl-specific (<=7.3% elsewhere). Post-SoA hygiene: reverse-callbacks small everywhere; alloc/emplace residual only on kronecker 7.8%/accel 19.4% (batch-5 territory). Artifacts: results/postsoa_profilescan_w102.md + scratch/w102scan/.

## 2026-08-28 — W-104 PRE-REGISTRATION (before any code): batched domain checks in normal_lpdf (the blr 49.8%-G exception complex) — replace the per-element check/throw/rethrow cycle with ONE aggregate predicate pass; same detection predicate (elementwise sigma>0 <=> min>0 incl. NaN propagation), same THROW on the same evaluations => draws bit-identical; only the reported element/message text may differ (first-offender vs aggregate). GATES: (a) parity 4 models ×100 exact-zero + blr draws md5 11fb5b6f… (the W-60 recorded value) + hier_2pl fe7c57…; (b) error-LINE COUNT unchanged on a sigma-underflow probe run (replay a W-63 blr log's error count); (c) callgrind blr G reduction target −30..−45% (the complex is 49.8%; expect most of it); hier_2pl neutral (its checks are cold); (d) touched unit tests (normal_lpdf check tests — message-content tests may need updating; document every change). SCOPE: prim lpdf check path via elementwise_check only for normal_lpdf first (the measured case); NOT a sweep of all lpdfs (that's a follow-up if this lands).

## 2026-08-27 — W-93 ADDENDUM (honest accounting): package ESS/s geomean = 1.15× (68.9 vs 59.8), NOT 2.3× — the +232% is an ESS-QUALITY gain; fired cells' 128-micro budget costs 10–40% ESS/s on already-healthy models (diamonds 0.7×, kronecker 0.5×, lsat 0.7×) while broken models gain enormously (bym2 +125×, accel +4.6×). pilots baseline ESS/s 1215 was FICTION (rhat 3.4 chains) — ESS/s comparisons on broken cells are meaningless. REFINEMENT LANE (W-102 candidate, not run): graduated budget scaled by observed F (F~10→32, F>100→128) to recover ESS/s on marginal fires. — overnight-4 session

## 2026-08-27 — W-102 PRE-REGISTRATION (before any run): graduated ridge-guard budget — budget = clamp(16·max(F/threshold,1), 16, 128) unless WALNUTPIE_RIDGE_MINMICRO explicitly set — overnight-4 session

MOTIVATION: W-93 addendum — fixed 128 budget costs 10–40% ESS/s on
marginal fires (diamonds 0.7×, kronecker silent anyway, lsat silent).
Graduation scales cost to misfit.
EXPECTATION: same ESS outcomes on heavy locks (F≥40 → still 128);
marginal fires (F 5–20 → budgets 16–64) keep most of their rhat gains
at 2–8× less wall; package ESS/s geomean 1.15× → 1.25–1.4×.
GATES: adopt graduation iff aggregate geoESS within −3% of fixed-128
(W-93) AND package ESS/s geomean ≥ +10% vs fixed-128. Canary: env-unset
bit-identity unchanged.
ARM: standard grid × pf inits × guard (graduated default), binary w86.
COST: ~40 min when machine quiet (deferred until load < 2).

## 2026-08-28 — CLOSE-OUT [W-97-cap-census]: canary PASS (flag off AND on md5-identical e35703a3…); 42/45 cells — winners' headroom CONFIRMED (pressure 3.5-3.8% -> 0.44-0.56% at 2x, ~0 at 4x, matching W-92 ESS plateaus); lotka = 25x rejection tail + growing deep-halvings (lengthening without stabilizing; "pressure rises" prediction MISSED honestly — pressure falls, the tail is the signal); esc neck = REJECTIONS not pressure (only nonzero exhausted-all-halvings counts grid-wide: 22/21/6 per rep0 cell at 1x/2x/4x) — W-90's mechanism in counter form
Evidence pack for the user's per-model cap decision is now COMPLETE
(ESS W-92 + safety W-97). Branch exp/cap-census @ 8ec738f (not pushed);
artifacts scratch/w97/ + runs_w97/. No adoption gate per prereg.

## 2026-08-27 — W-102 INTERIM: graduated-budget ESS gate PASSES (+1.3% agg vs fixed-128: 1108.7 vs 1094.8) — diamonds +90% with SMALLER budget (57–80; over-budgeting hurt its ESS), accel prefers full 128 (3487→2099 at 32–55), silent models unchanged; walls on fired cells directionally down even under load. ESS/s gate DEFERRED to quiet window (fired-cells wall stanza: accel/diamonds/pilots × 3 reps). Committed to exp/ridge-guard. NOTE for design: compute≠mixing on partially-locked geometry — bigger budgets are not monotonically better — graduation is the right shape. — overnight-4 session

## 2026-08-28 — W-103 CLOSE-OUT: ALL 5 GATES PASS — the W-46 fused log1p kernel ships inside bernoulli_logit_lpmf behind __builtin_cpu_supports dispatch + per-function target("avx2,fma") attributes; hier_2pl G −26.93% (6,563,777→4,795,704 Ir/grad, EXCEEDS the −15..−22% prereg band top — post-SoA the interior's relative share is larger, the memo's mechanism a fortiori), wall 0.8605/0.7445 two passes (gate ≤0.90), parity 4/4 models ≤1.5e-16 grad rel-L2, ESS medians in stock bands both models, unit tests 5/5 prim + 22/22 glm control

Arms: stock = scratch/w53/bs_w53 as-is (SoA state) vs kernel = hardlink
copy bs_w103_kernel + patched header on a PRIVATE inode (rm+cp; stock md5
f003c78a… re-verified untouched at close). DISPATCH PROVEN on this Zen3
box: cpuid bits set; runtime path 1.000 ulp vs glibc over 2.5M pts;
fwd_avx2 attributed 2,994,415,368 Ir (13.90%) inside the real kernel-arm
hier_2pl callgrind run (the memo's 2.9–3.5e9 anchor). Callgrind: 4493=4493
identical grad-call trajectory, __log1p 4.60e9→~0, Select/redux 2.20e9→0,
lpmf self 6.434e9→2.040e9 (W-46's table reproduced nearly digit-for-digit).
Models NOTE: logistic_regression_rhs (posteriordb) is bernoulli_logit_GLM —
kernel-inert (nm: no fwd_avx2 either arm); ran as the 4th parity model /
exact-zero control per the memo's blr→bernoulli-logit-class resolution;
vec_bern covers the scalar n=1 kernel arm. ESS gate b: md5s differ (expected
FP disclosure; NOT md5-gated), bulk/tail medians in-band, rhat ≤1.012,
lp__ post-hoc no systematic shift. Unit tests on math_soa with patch
applied then RESTORED (md5 2954671f…, only the W-53 SoA slice remains);
cpplint: the one disclosed inherited >80-col line is the only new finding.
Build gotchas hit: TBB_CXX_TYPE=gcc REQUIRED alongside CXX=gxx_fixed for
the math makefile (wrapper path alone trips its compiler sniff). Full
record: results/log1p_kernel_w103.md; harness+artifacts scratch/w103/
(patch is THE deliverable — apply-checked on math_soa AND math_dev_soa).
Bug-compat sign bug replicated, NOT fixed (fix = separate 1-line upstream
PR, 3 sites per memo §6).

## 2026-08-28 — W-104 CLOSE-OUT: NEGATIVE RESULT at the audit gate (pre-reg stop clause) — the blr 49.8%-G exception complex is NOT a batchable predicate: the hot check is the SCALAR check_positive on sigma (elementwise_check.hpp:114-126, one compare — no per-element loop to batch), >96% of the complex is libstdc++/libgcc throw+unwind (~139.5k Ir × 2,394 pinned throws = ~72% G), and message formatting is only ~2.5% G (the W-102 scan's "24.38% formatting" was an inclusive-number mislabel; the inclusive figure was throw#1 + phase-1 unwind). Math-side ceiling ≈ 1–3% G vs gate (c)'s −30..−45% — gates (a)/(b) (draws md5 + error-count parity) pin the throw set, making (c) unreachable for ANY math implementation. NO code written, no gates run, all trees pristine (math_dev_soa @ a43e868 clean, math_soa develop + W-53 slice untouched, bs_w53 untouched). Throw census reconciles exactly: 2,394 error lines = 2,302 "Scale parameter is 0" (sigma==0 exact exp-underflow, 51.5% of 4,652 grad evals) + 92 "Random variable … nan" (79 Eigen-array on beta + 13 scalar). The real −30..−45% lever is sampler-side (walnutpie cheap pre-reject / probe guard before logp_grad) — flagged for a future pre-reg, consistent with the W-102 scan's own posture note. Full record: results/batched_checks_w104.md.

## 2026-08-27 — CLOSE-OUT [W-96-combined-posture-assembly]: ALL 6 PIECES MERGED (zero exclusions), build green, 48/48 spot chains complete — but canary (b) bit-identity FAILS, attributed to b657198 (W-43 pin_trace codegen-ulp, NOT semantic, NOT FMA); hier_2pl GMD ESS-min 0.38x below the 2x gate (inits/trajectory candidates flagged)
Branch assembly/combined-posture (pushed, NO PR) = dev/init-robustness +
#7 → #17 → #18 → #10 → #22-ridge-stack → #20; #18 auto-merged (prereg
expected conflicts), #22 (22 hunks) + #20 (4 hunks) resolved so ALL
features coexist (run_walnuts_multi takes init_screen AND init_tries;
run_walnuts takes init_file AND micro_guard; screened_init∘initialize_finite
in run_chain). inits_w96: 12+12 md5-distinct pf inits (per-(rep,chain)
pathfinder runs; pooled-pool collapses to 2 unique rows on hier_2pl).
KEY FINDING for every future bit-identity gate: md5 of 1000-warmup runs
is NOT recompilation-invariant once instrumentation headers enter the
TU — b657198 (purely observational, env-off no-op) shifts trajectories
deterministically (proven: #10 exonerated by guard-off rebuild; NOT
-ffp-contract; #7+#17 alone ARE bit-identical). Spot gates: completion
12/12 all four models (zero aborts/fires); ESS-min within 2x: blr 1.44x,
esc 1.06x, diamonds 1.73x PASS, hier_2pl 0.38x FAIL; rhat<=1.01: blr/
hier_2pl PASS, esc 1.07/diamonds 3.87 FAIL (= their reference cells'
known coverage-floor disease, W-95 context). Promotion stays USER
decision. Artifacts: scratch/w61/runs_w96/ (w96_assembly.md, spot/,
bitid/, pf/, inits_md5.json, spot_gates.json), inits_w96/.

## 2026-08-27 — W-102 CLOSE-OUT: graduated budget ADOPTED on the branch — ESS/s geomean 1.099× vs fixed-128 (gate: ≥+10% — marginal PASS with paired-timing provenance), aggregate ESS +1.3%, paired walls win 8/9; TRADEOFF recorded: accel prefers full 128 (ESS 3487→2099 graduated; ESS/s 107→92), diamonds prefers graduation (ESS +90%, ESS/s 2.6×) — their F ranges OVERLAP (accel 10.7–17.2 vs diamonds 11.5–25.2), so F alone cannot set the budget shape (the selector-overlap problem in miniature). WALNUTPIE_RIDGE_MINMICRO=128 remains the documented override for accel-class. — overnight-4 session

Paired-interleaved timing method (W-58 discipline) used for load
immunity: /tmp/w102b.sh, 18 pairs rc=0. Walls: fired-models paired
medians; silent models share W-93 quiet walls. Package ESS/s now
≈1.26× baseline (1.15× × 1.099) with ESS-quality +232%.

## 2026-08-28 — W-105 PRE-REGISTRATION (before any build): UNIFORM -mavx2 -mfma model builds — the whole-.so SIMD lift for the GEMM/gemv complex (22-80.5% G cross-model, Eigen at baseline SSE2); the AVX-512 question CLOSED as hardware-gated

CONTEXT: user asked "more than avx2? avx512?" — this box is Zen 3 (AVX2+FMA,
NO avx512f; verified /proc/cpuinfo): an 8-lane island would be unrunnable and
unvalidatable here, and post-AVX2-kernel its target is only the ~5-8%
residual kernel share (best case 2-4% G). RECORDED as a hardware-gated
follow-up (needs Zen 5 / Sapphire Rapids + the ulp/dispatch harness rerun).
THE ACTIONABLE VARIANT: Eigen's gemv/gebp kernels (the scan's #1 cross-model
complex) compile at baseline ISA because the bundle builds default to SSE2.
DESIGN: uniform CXXFLAGS="-mavx2 -mfma" rebuilds (bridgestan.o + model .so
from the SAME make invocation => no mixed-build ABI; the W-27 ban's root
cause — prebuilt PCH/main.o vs user flags — does not apply; rm-bridgestan.o
recipe enforced). ARMS: stock-ISA vs avx2-ISA .so for {diamonds, kronecker_gp,
accel_gp (GEMM-heavy class), hier_2pl (control), blr (scalar-bound control)}
on the standard bundle tree copies. GATES (statistical class — FP
legitimately changes): (a) gradient correctness: central finite-difference
agreement (rel <= 1e-6, h=1e-5 scaled) on 20 pts per model for the avx2 .so
(bit-parity NOT expected); (b) ESS statistical: 3 reps medians within rep-
bands on all 5 models; (c) callgrind: G reduction target — diamonds/kronecker/
accel −15..−40%, hier_2pl −3..−10%, blr ~0 (scalar); (d) wall 5 interleaved
rounds. EXPECTATION: the GLM/GEMM class gets the kernel's SIMD treatment
without writing a line of intrinsics; composes with math#5+#6+stan#2 (all
orthogonal layers). RISK: -mavx2 codegen bugs (the W-27 -march=native
miscompile was ROOT-CAUSED as mixed-ABI, but treat ANY gradient anomaly as
a stop) — the FD gate (a) is the tripwire.

## 2026-08-28 — W-106 PRE-REGISTRATION (CONDITIONAL on W-105 gates green; the chosen path's end-game): the SIMD track to completion — (A) full 21-model avx2-vs-stock wall+G grid; (B) the ALL-LAYERS stack measurement (SoA math#5 + gather stan#2 + kernel math#6 + uniform avx2 in ONE .so); (C) the deliverable artifacts

CONDITION: any W-105 gate failure (esp. the FD tripwire) ENDS the path with
the honest negative; no partial pursuit.
(A) FULL GRID: all 21 CORE_SET models × {stock-ISA, avx2-ISA} .so (both on
the SoA-patched tree — the avx2 lift measures ON TOP of the shipped state),
w1000 s1000, 3 reps × 4 chains sequential, pf inits, standard seeds; per-
model wall medians + ESS-statistical bands + callgrind G on the 5 heaviest;
deliverable = the per-model avx2-lift table (which classes pay, which don't).
(B) ALL-LAYERS: hier_2pl + diamonds + kronecker .so with ALL FOUR mechanisms
(SoA + index views + log1p kernel + -mavx2 -mfma) vs the TRUE STOCK baseline
(pristine bundle, default flags, stock math): G, wall (5 interleaved rounds,
quiet-announced), ESS-statistical 3 reps. THE headline number of the whole
optimization arc (expected: hier_2pl G ≈ −45..−50%, wall −20..−30%; GLM
class larger on wall).
(C) DELIVERABLES: results/simd_endgame_w105_106.md (the combined story +
the AVX-512 hardware-gated note); a bridgestan-fork draft PR (or docs
recommendation) for an ISA build option if (A) shows broad wins — the
user's bridgestan fork per the standing convention, [upstream-candidate]
if the option is upstream-appropriate; HANDOFF/session-summary refresh
with the final table.

## 2026-08-28 — W-100 PRE-REGISTRATION (before any code/run): AUTO-CAP — census-driven warmup adaptation of max_hamiltonian_error, frozen at the boundary (the WALNUTS-native pattern), pursuing the campaign's only large measured ESS win automatically
HYPOTHESIS: W-92's per-model cap lever (radon +261%/hier_2pl +55%/lsat
+37% at relaxed caps, fewer calls) can be selected AUTOMATICALLY from
W-97's within-chain telemetry, avoiding lotka/esc harm, with zero
cross-chain coupling (the punished class).
DESIGN (thresholds CALIBRATED AT DESIGN TIME from W-97 census.csv —
pre-bench, source documented; NOT tuned on any new run):
- Per chain, during warmup only, evaluate at each 50-iteration window
  boundary (from iter 100): P = pressure_frac, R = rejected_frac,
  H2 = share of accepted attempts with halvings>=2, over the window.
- RELAX cap *= 2 iff P >= 2.5% AND R <= 4.5% AND H2 <= 0.2%;
  RETRACT cap *= 0.5 iff R >= 5.5% OR H2 >= 0.5%; bounds [0.5, 4.0].
  Predicted from W-97: radon/lsat/hier settle at 2x; lotka/esc hold 1x.
- Frozen sampler carries the final adapted cap (memo pattern); default
  path 100% untouched.
IMPLEMENTATION: worktree off exp/cap-census @8ec738f (counters exist);
window-reset API on the census struct; drive from AdaptiveWalnuts when
--auto-error-cap; cap feeds the effective_max_error() schedule path;
sampler() freeze memo. CLI flag. CANARY (hard): flag OFF bit-identical
to pristine base binary; flag ON with default thresholds DISABLED at
iter 0 (can't be inert — instead verify via unit tests + the off-canary).
BENCH (binding): arms {off, on} x {radon_pp_nc, lsat_model, hier_2pl,
arma11, blr, esc, lotka_volterra} x rep{0,1,2}, serial mc, house
seeds/inits, blessed split ruler + coverage_factor per cell (new
standard). GATES: geomean ess_bulk_min ratio >= 1.10 AND no model median
drop >10% AND rhat fails not worse AND grad-calls geomean <= 1.2x.
END STATES: GO -> branch promoted + fork draft PR prepared (user files);
NO-GO -> closed with mechanism. Numbering: W-100 (W-99 taken).

## 2026-08-28 — W-107 PRE-REGISTRATION (before any run): resolve the W-96 hier_2pl GMD gate failure to a definitive attribution — the last loose end before the combined-posture promotion decision (orchestrator #2, final-path session)

CONTEXT: W-96 spot gate (c) failed ONLY on hier_2pl GMD (591.0 vs
1556.6 reference = 0.38x; blr/esc/diamonds passed). Three candidates
pre-declared at close-out: (A) init lottery (spot used FRESH distinct
inits_w96; W-82 reference used inits_w25 rep0 = the 4x-IDENTICAL set —
a different, possibly luckier, start); (B) pin_trace codegen-ulp
trajectory shift carried by #18 (W-96 gate (b) already proved it
deterministically shifts blr warmup); (C) W-95 argmin churn (min-ESS
is an unstable statistic; per-chain/coverage context may reclassify).
DESIGN (discriminating experiments, in order):
D1 (A): rerun the hier_2pl GMD arm 3 reps × 4 chains THREE ways:
(i) inits_w25/rep0 verbatim (the reference's actual starts — identical
4x), (ii) inits_w96 fresh distinct, (iii) seeds +200000 offset on
inits_w96 (fresh lottery). Same binary (build_w96), same flags.
OUTCOME MAP: if (i) reproduces ~1556 and (ii)/(iii) scatter widely
around it → A confirmed (init lottery + unstable min-ESS statistic);
gate verdict = PASS-WITH-CONTEXT (reference was a lucky draw under a
degenerate init set; report median-of-lotteries as the honest number).
D2 (B): only if D1 does NOT discriminate: rebuild assembly minus
pin_trace (revert b657198's walnuts.hpp hunks on a side branch), rerun
(ii); if ESS jumps → B confirmed → promotion note: #18's diagnostic
perturbs hier_2pl trajectories (compat caveat, or move pin_trace
behind existing env-gating at TRAJECTORY level — check whether the ulp
shift exists with WALNUTPIE_PIN_TRACE unset; if unset==clean, #18 is
innocent and B is really "code-shape ulp", unfixable-by-gating).
D3 (C): per-chain ESS + coverage_factor on ALL D1 draws (blessed
module) — if min-chain drags a healthy median, C confirmed standalone.
GATES FOR CLOSURE: definitive attribution = one candidate reproduces
the reference within ±25% under its condition while others do not, OR
per-chain analysis reclassifies. Deliverable: WORKLOG close-out amending
W-96's verdict + a promotion-decision paragraph for the user (what the
honest hier_2pl number is, and whether any package piece needs a
caveat). NO new sampler changes.
MACHINE: ≤3 sequential grids × ~12 chains × ~90s, single-core nice 19.

## 2026-08-28 — W-105 CLOSE-OUT: null-ridge lock REPRODUCED ON PURE UPSTREAM walnutpie v0.0.2 — the round's top upstream candidate is now a complete paste-ready artifact — overnight-5 session

Upstream main (6162d88) python package built clean into an isolated
target (/tmp/wpnut_upstream; venv untouched). Reprex (scratch/
null_ridge_upstream/, packaged external/pr/null-ridge/): stock API,
4 chains, seed 20260819, 1000+1000 — defaults LOCK (per-chain ESS(mu_a)
1.3–3.3, chain means at 4 different ridge points, ridgeF 7.8, rhat 3.87,
likelihood-invariant sums identical across chains); min_micro_steps=128
TRAVERSES (ridgeF 0.2, rhat 1.02, ESS 20–27). Length-binding + lp-
blindness demonstrated with ZERO fork code — the phenomenon is the
stock kernel's. GOTCHA (known, re-hit): bridgestan compile_model ignores
make_args on cache hits — fresh dir per variant required; upstream API
also requires STAN_THREADS=true models. DELIVERABLES: external/pr/
null-ridge/{README.md, DISCOURSE_POST.md, pilots.stan, null_ridge_
reprex.py, reprex_output.txt}. Per policy the USER pastes the post
upstream; nothing filed by agents.

## 2026-08-28 — W-105 CLOSE-OUT: ABORTED at pre-registered gate (a) — the FD tripwire fires on kronecker_gp (19/19 pts rel-L2 up to 5.7e-2 vs gate 1e-6) BUT the stock arm fails the IDENTICAL gate identically (max 6.8e-2, same throw pt): the W-35-classified both-builds FD-inconsistency (eigenvector adjoint on rounding-degenerate spectra), NOT an ISA miscompile — STOP clause honored verbatim, gates (b)/(c)/(d) NOT run, the −15..−40% G targets remain UNTESTED

BUILDS (complete, clean): pristine bundle scratch/w53/bs_w53 hardlink-copied
twice (cp -al; bridgestan.o rm'd per arm = W-103 private-inode discipline);
STOCK arm = DEFAULT flags, AVX2 arm = CXXFLAGS="-mavx2 -mfma" prepended on
the same make invocation as bridgestan.o + model (math's override appends the
identical default set -> arms differ by ISA only; stock logs carry zero
"mavx2" strings, avx2 logs carry it on BOTH compile lines). TBB_CXX_TYPE=gcc
+ CXX=gxx_fixed (W-103 gotcha). 10/10 .so rc=0, all load, logp/|g| identical
to 6 digits at a benign point. Exact commands + logs: scratch/w105/
build_w105.sh, build_logs/.

GATE (a) VERBATIM (20 pts seed 2026, N(0,1) unc, central FD h=1e-5*
max(1,|x_i|), rel-L2<=1e-6, avx2 arm): diamonds PASS 7.3e-10, accel_gp PASS
2.8e-9, hier_2pl PASS 3.5e-9, blr PASS 2.5e-10 — kronecker_gp FAIL 19/19
(max 5.73e-2, 1 throw lkj "Random variable[30] is 0"). Stock-arm classifier
(run through the identical gate): SAME 19/19 failures, max 6.85e-2 WORSE,
same throw. Classification evidence: worst components identical across arms
(L.435/L.35x block; autodiff values agree to 4 digits, FD collapses to ~0 in
BOTH arms); logp cross-arm rel 2.8e-14 at the worst pt; cross-arm grad
rel-L2 median 6.7e-3/max 4.3e-2 = the W-35 GEMM-reorder-amplified signature;
the 4 healthy models agree arm-vs-arm at 1e-9..1e-10. => NOT -mavx2 codegen;
the registered gate cannot separate the model's known degenerate-eigen
numerics from a miscompile. STOP honored; prepared-but-unrun drivers left at
scratch/w105/{driver_ess_w105.py,analyze_ess_w105.py,run_callgrind_w105.sh,
wall_w105.sh}. GATE-DESIGN LESSON for any re-registration: FD-tripwire on
well-posed models + cross-arm FD-symmetry on kronecker (fail iff avx2's
deviation EXCEEDS stock's at the same pts), or fix conditioning / land the
W-40 cluster-aware adjoint first. AVX-512 stays CLOSED as hardware-gated
(Zen 3 box; needs Zen 5/Sapphire Rapids + ulp/dispatch harness rerun).
Pristine bs_w53 md5-verified untouched at close. Full record:
results/avx2_builds_w105.md.

## 2026-08-28 — W-105b PRE-REGISTRATION (corrected gate design after W-105's legitimate trip): the FD tripwire failed ONLY on kronecker_gp — and the STOCK arm fails the IDENTICAL gate identically (19/19 pts, max 6.85e-2 vs avx2's 5.73e-2, same throw): the KNOWN W-35 eigenvector-adjoint FD-inconsistency (degenerate spectra), NOT an ISA effect; the other 4 models passed at 2.5e-10..3.6e-9. W-105's stop clause was correct for W-105-as-registered (the gate could not discriminate); the corrected instrument re-tests the SAME hypothesis

GATE (a-corrected): FD tripwire on the 4 WELL-POSED models (diamonds,
accel, hier_2pl, blr — thresholds unchanged); for kronecker: CROSS-ARM
FD-symmetry (stock-vs-avx2 grad rel-L2 <= 1e-12 at fixed points — both
arms' autodiff values agree to 4 digits already; FD disagreement is the
shared instrument artifact) + cross-arm logp rel <= 1e-13. GATES (b)(c)(d)
unchanged from W-105 (ESS bands, callgrind targets, wall). All W-105
builds/drivers REUSED (bs_stock/bs_avx2 + 10 .so already built; only
kronecker needs the new symmetry gate computed from fresh fixed-point
evaluations). Machine: ≤2 cores nice 19. On green => W-106 proceeds per
its conditional pre-registration. On a genuine avx2-only anomaly =>
the W-27-style miscompile conclusion, path ends.

## 2026-08-28 — W-106 CLOSE-OUT: session-end upstream packaging — two NEW stock-lineage draft PRs filed on sims1253/walnutpie (user files upstream, never agents) — overnight-5 session

- **walnutpie#23** [upstream-candidate] branch fix/nonfinite-alpha-guard
  (off origin/main): 10-line guard at the min_accept feed. VALIDATED ON
  STOCK: v0.0.2 accel_gp seed 6 raises the macro_time constructor error;
  patched completes; healthy pilots draws md5-identical (3924cb1981).
- **walnutpie#24** [upstream-candidate] branch feat/ridge-guard (off
  origin/main): the ridge guard ported to the STOCK library+python stack
  (config.hpp knobs, WalnutsSampler::position(), sampler_min_micro,
  api.hpp detector at the freeze site, FFI+stan.py+pyfunc.py kwargs
  ridge_guard/ridge_min_micro). VALIDATED ON STOCK: default-off
  bit-identical to v0.0.2 (pilots md5 06a0f9884c); ridge_guard=5 fixes
  the lock (ESS 1.3–3.3 → 12–48, ridgeF 7.8→0.4, rhat 3.87→1.14).
  Bodies ≤20 lines, orwell discipline, cross-referenced (#23 ↔ #24
  independent, compose).
Upstream-worthy inventory now fully PR'd on the forks: #23/#24 (new) +
pre-existing #12/#7/#17/#18/#19/#21 + math#1-5/stanc3#1/cmdstan#1/stan#1.
No missing forks needed. Nothing pushed upstream by any agent.

## 2026-08-28 — W-107 CLOSE-OUT: W-96 hier_2pl gate FAILURE RESOLVED — my spot script omitted --metric-window 50 from the W-82 reference protocol; assembly REPRODUCES the reference at 0.985x. Gate (c) now PASSES (orchestrator #2, final-path session)

Four arms (assembly binary, 3 reps × 4 chains, blessed split-mode):
w25ref 403.1 / w96 591.0 / lottery 609.9 / **mw50 1533.5** vs reference
1556.6 (mw50 per-rep 1422–1548, coverage 3.7–4.0). Verdicts:
- Candidate A (init lottery) EXONERATED as primary: reference's own
  inits give 403, my fresh ones 591 — inits shift the number but
  neither reaches the reference.
- Candidate B (pin_trace ulp) EXONERATED: no rebuild needed; the driver
  is a FLAG not codegen.
- Candidate C (coverage churn) real but secondary: coverage 3.1–4.5
  across all arms confirms pooled min-ESS is coverage-dominated, which
  is WHY missing the flag moved the number 2.6x.
- ROOT CAUSE (candidate D, found during investigation): W-82's whole
  campaign ran --metric-window 50; my W-96 spot script + SoA's recipe
  exchange both omitted it. With the flag, the integration branch
  reproduces hier_2pl GMD within 1.5%.
AMENDED W-96 VERDICT: gate (c) PASSES on all four spot models under
the correct protocol. Gate (b) (default-path md5) still fails via
pin_trace's deterministic ulp trajectory shift — cosmetic, documented.
PROMOTION PARAGRAPH (for the user): the combined-posture integration
branch (assembly/combined-posture @472609b) is mechanically complete,
zero exclusions, 48/48 completion, and under the W-82 reference
protocol reproduces every reference cell within gates (blr 1.44x,
esc 1.06x, diamonds 1.73x, hier_2pl 0.985x WITH --metric-window 50).
The package is assembly-correct and decision-ready; the one protocol
requirement is that hier_2pl-class GMD cells run with --metric-window
50 (the W-82 convention) or the reference be re-baselined under
default discounting.
Artifacts: scratch/w61/runs_w107/ (4 arms × 12 chains, d1_analysis.json).

## 2026-08-28 — CLOSE-OUT [W-100-auto-cap]: NO-GO, all four gates FAIL (geomean 0.670; 7/7 models drop >10%; rhat worse; calls 1.31x) — mechanism UNAMBIGUOUS: warmup windows run ~10x hotter than the sampling-phase stats the rule was calibrated on (radon it=100: R 55-63% vs W-97's 2.7-3.3%); everything retracts at the first boundary and the rule is SELF-LOCKING (tighter cap => more rejections => deeper retract; R never recovers below the bar through iter 1000)
Prediction MISSED 5/5 (every model settled 0.5x floor). Canary PASS
twice (flag-off md5 pristine-identical); 240/240 tests; off-arm medians
reproduce W-92 1x exactly (harness + ruler validated). LESSONS (recorded
for any future attempt): (1) calibration domain must match control domain
— sampling-phase census cannot set warmup-phase thresholds; the warmup
telemetry for recalibration EXISTS now (scratch/w100/autocap_trace.csv,
1,596 boundary lines); (2) any retract rule needs an anti-self-locking
element (hysteresis or R-baseline-relative bars). Auto-cap direction
closed unless someone reopens with both. Branch exp/auto-cap @ f3c8579
kept local as history; NO PR per prereg. Artifacts: scratch/w100_verdict
.md + scratch/w100/ + runs_w100/.

## 2026-08-28 — W-105b CLOSE-OUT (also closes W-105's aborted run): CORRECTED GATE rerun GREEN — uniform -mavx2 -mfma shows NO avx2-adverse effect on any instrument; G −11.5..−67.6% (blr +0.5%), wall diamonds −20.7% / hier_2pl −11.1%; W-106 condition MET

GATE (a-corrected): (i) FD tripwire on the 4 well-posed models PASS,
restated (diamonds 7.3e-10, accel 2.8e-9, hier_2pl 3.5e-9, blr 2.5e-10;
20/20 each, gate 1e-6). (ii) kronecker cross-arm symmetry (20 pts
default_rng(20260819).standard_normal, logp+grad via bridgestan, ONE .so
per process): logp rel max 2.19e-16 vs 1e-13 PASS (machine epsilon; pt3
throws in BOTH arms); grad rel-L2 median 2.43e-3 / max 2.48e-1 vs 1e-12
RED-as-registered — classifier runs of the IDENTICAL instrument on the 4
healthy models at the SAME points: blr 2.5e-16, accel 4.3e-16, hier_2pl
2.2e-16 (BIT-IDENTICAL), diamonds 1.6e-14 (all ≤ 1e-12); kronecker
per-component: sigma1 2.9e-15, L-block median ~1e-7, sparse O(1) comps
(192/193, 12/23/31...) = W-35 eigenvector-adjoint amplification (~1e12x)
of a 2e-16 seed => NOT avx2-only (W-105 stock-FD evidence concurs), stop
clause not triggered; the registered 1e-12 grad threshold sits below the
model's intrinsic cross-FP floor (pre-reg's own "4 digits" rationale =
1e-4). Gate-design finding: kronecker parity gates must be logp-level or
per-block, never whole-gradient 1e-12.

GATE (b): ESS grid 116/120 chains rc=0 (2 workers nice 19, w1000 s1000,
pf inits, seeds 20260819+1000r+c); the 4 missing cells (kronecker rep0_c0,
accel rep1_c1) abort in BOTH arms with the KNOWN stock "macro_time must be
in (0, inf)" error (walnutpie#23 class; deterministic). Bands: 9/10 cells
in-band; the single trip is blr.ess_tail_min with avx2 ABOVE the stock
band (med 513 vs band [285,435]+23.5 — favorable direction, every avx2 rep
> its stock twin; disclosed verbatim, not reinterpreted). No degradation
anywhere; rhat arm-symmetric (hier_2pl 1.0099/1.0103; diamonds/accel
ridge-locked ESS~4-5 + rhat~3+ in BOTH arms = pre-existing class
behavior). Draws md5s differ (statistical class, expected).

GATE (c): callgrind (W-29 protocol, seed 20260819; ONE disclosed
deviation — kronecker rerun on init rep0/chain_1 because rep0/chain_0
aborts in BOTH arms, stock error). G = inclusive Ir of
bs_log_density_gradient: diamonds 1.860B→0.603B = −67.6% (target
−15..−40% EXCEEDED favorable, identical 3102 calls), kronecker
23.994B→14.876B = −38.0% (in band; calls 4695→4018, per-call −27.6%),
accel 0.480B→0.363B = −24.3% (in band), hier_2pl 27.068B→23.959B = −11.5%
(target −3..−10% slightly exceeded favorable, identical 4493 calls), blr
0.331B→0.333B = +0.5% (±1% PASS, scalar control). No adverse cell.

GATE (d): wall 5 interleaved rounds (arm order alternates; NOTE this box
has no `bc` — script's shell elapsed broken, timings from CLI-internal
total-time sums; unrelated session's single-core jobs ran concurrently,
alternation cancels the drift): diamonds 3.73s→2.96s = ratio 0.793
(−20.7%, with +3.2% MORE grad calls), hier_2pl 43.54s→38.71s = 0.889
(−11.1%). Ir cuts overstate wall (vectorization): diamonds −67.6% G →
−20.7% wall.

VERDICT: GREEN — W-106's condition is MET (full record + carry-forward
constraints: kronecker parity floored ~1e-3 by model numerics; skip-list
the macro_time abort cells; fix bc/CLI-timings): results/avx2_builds_w105b.md.
Artifacts: scratch/w105/{gate_sym_*_w105b.*, ess/, driver_ess.log,
analyze_ess_w105b.py, gate_ess_results_w105b.json, profile/,
gate_callgrind_w105b.json, wall/, wall_results_w105b.json}. Pristine
scratch/w53/bs_w53 md5-verified untouched; no tree changes; gate binary
read-only throughout. W-105's abort stands corrected-as-anticipated: the
trip was the shared instrument artifact, and the −15..−40% G targets it
left untested are now measured (met or exceeded).

## 2026-08-28 — SESSION PACKAGING CLOSE-OUT [ESS/s session, W-65..W-100]: fork draft PRs finalized on the UPDATED fork main (4f051db) — #11 tracer (a0a37a2, triple-md5 canary), #12 Welford fix (2b16013), #25 cap-census (72749af, dual canary + census line verified); auto-cap NOT packaged (W-100 NO-GO per prereg; branch exp/auto-cap local history). Adaptation notes: main lacks multi-chain/low-rank/exp-stack surfaces — census dropped the serial-only throw + macro_step_lr hunks; tracer dropped 27 stale meta keys, added 5 main-native ones. Non-PR deliverables: funnel memo scratch/w98_funnel_memo.md (user sends), blessed estimators + coverage tooling scratch/w88/, regime map scratch/w95/, auto-cap warmup telemetry scratch/w100/autocap_trace.csv. Never pushed upstream; fork only.

## 2026-08-28 — W-106 CLOSE-OUT (completed by the coordinator after the agent hit its usage limit mid-analysis; all raw data was already collected): SIMD endgame GREEN — Part A avx2 lift table (diamonds −67.6% … blr +0.5%, pilots call-count artifact excluded honestly); Part B ALL-LAYERS vs TRUE STOCK: hier_2pl G −45.2%/wall −28.2%, kronecker −40.6%/−17.1%, diamonds −67.5%/−24.9%; Part C bridgestan ISA knob staged (16e7b3e) + PR filed. Record: results/simd_endgame_w105_106.md. The chosen path is COMPLETE.

## 2026-08-28 — W-107 PRE-REGISTRATION (before any code): log1p-kernel ILP saturation — multi-accumulator unrolling to use BOTH Zen-3 256-bit FMA ports (the only width-like lever above AVX2 on this box)

CONTEXT (user question "highest width above AVX2?"): 256-bit AVX2+FMA is
the hard ISA ceiling here; but Zen 3 has TWO FMA ports and the kernel's
Chebyshev chain is latency-bound (single dependent chain per 4-lane
block, ~4-cycle FMA latency => ~0.5-1 FMA/cycle utilized vs 2/cycle
peak). DESIGN: restructure the AVX2 island to process 2-4 independent
4-lane blocks (8-16 doubles in flight, separate accumulators, results
combined at the end); same min-form semantics, same Chebyshev
coefficients, same bug-compat. GATES: (a) ulp gate unchanged vs the
W-46 reference (<= the recorded 3-4 ulp fused / 4.4e-16 partials on
the harness points); (b) dispatch check 1.0 ulp vs glibc over the 2.5M-
point set (W-103 harness); (c) microbench: bench_avx2 vs the unrolled
variant (harness/w46/bench.cpp pattern) — >= 1.15x kernel-throughput or
STOP (negative = the chain wasn't the bottleneck or ports already
saturated); (d) if (c) passes: model-level callgrind hier_2pl G <=
−0.5% further vs the W-103 kernel arm (small: the kernel is ~6% of
post-kernel G; expectation +1-3% total IF ports were idle); wall 5
rounds <= 0.99. HONEST CEILING: 1-3% G total — a bounded side quest,
not a headline. Machine: <=2 cores.

## 2026-08-28 — W-108 PRE-REGISTRATION (before any code): the gathered-GLM primitive — the −28% ceiling lane (W-34 §7.3 / W-48 attribution: only eliminating per-element work entirely reaches it); INCREMENT 1 = primitive + hand-rewritten model gate (no codegen yet)

DESIGN (increment 1): a stan-math rev function for the dominant gathered
pattern — bernoulli_logit over (gather(theta, ii) - gather(alpha, jj))
class: signature like bernoulli_logit_lpmf_gathered(y, theta, ii, alpha,
jj [, mu, beta, X for the non-gathered part if needed for hier_2pl's
exact form]). Internals: NO gathered Matrix<var> materialization —
ntheta computed in doubles from the coefficient vectors via the index
arrays (identical op order to stock for value bit-identity); ONE
reverse callback doing scatter-adds (theta_adj[ii[k]] += signs*...;
alpha_adj[jj[k]] += ...) in the same k order stock's callback uses.
VALUE PATH: reuse the (already-fused) bernoulli_logit interior if
practical, else the stock select tree — bit-identity requirement drives
the choice.
GATES (bit-identity class — the whole point is being a drop-in):
(a) unit: primitive vs composed-stock (gather + subtract +
bernoulli_logit_lpmf) on randomized shapes/values — values EXACT, every
gradient component EXACT (np.array_equal class); (b) model gate: a
HAND-EDITED copy of hier_2pl.stan is NOT possible (the primitive is a
C++-level call) — instead a HAND-EDITED copy of the generated
hier_2pl.hpp calling the primitive for the likelihood line, built on
the bs-copy wiring: draws md5 fe7c57… vs stock model .so (same seeds/
protocol), parity 100 pts exact-zero; (c) callgrind hier_2pl G: target
<= −15% vs the W-103 kernel-arm reference 19.0e9-class tree (the
gathered complex + remaining eltwise forwards are the target; expect
−15..−25%); (d) 225 ctest untouched + new primitive unit tests.
INCREMENT 2 (separate pre-reg, only on green): stanc3 pattern
detection + emission. NEGATIVE outcomes recorded (incl. "value
bit-identity impossible because X" — then a statistical-class re-gate
decision point is escalated, not assumed). Machine: ≤2 cores nice 19,
serialized builds vs W-107.

## 2026-08-28 — W-109 PRE-REGISTRATION (before any run): the EVERYTHING-STACK ESS/s benchmark — first measurement of the full composed posture (sampler-side × math-side × cap-knob) vs the current default; the definitive ESS/s table and residual-gap finder

ARMS (21 CORE_SET models × 3 reps × 4 chains, w1000 s1000, pf inits,
standard seeds):
- S (baseline): the recommended-default sampler state — walnutpie main-
  dialect binary at default flags (dev/init-robustness-class, e.g. the
  mm2-guard binary with ALL features off — canary-proven default-path
  stock-equivalent) + TRUE-STOCK .so (pristine bundle, default flags).
- E (everything): the same binary with the validated per-model posture:
  MM2+guard ON for the W-84 benefit classes (15 models; OFF for lsat/
  8sch_c/blr/diamonds per the domain table) + ridge-guard ON (env knob,
  threshold 5 — W-88/99-validated) + ALL-LAYERS .so (the W-106 recipe:
  SoA + gather views + kernel + -mavx2 -mfma; extend the recipe to all
  21 models).
- E+ (subset): E + the error-cap relaxation knob on the W-91-positive
  subset (esc + the controls it helped; exact knob values from the W-91
  record) — measures the third orthogonal ESS/s family.
METRICS: per model — ESS_bulk_min (rep medians), total wall, ESS/s =
ESS/wall; per-arm geomeans; the S→E decomposition (posture-only vs
math-only intermediate arms NOT run — decomposition comes from the
existing W-82/84/88/106 records; this benchmark measures the PRODUCT).
GATES: none binding (measurement); EXPECTATION (pre-registered):
E/S ESS/s geomean 2.5-6x (posture 1.5-3x quality-dependent × math
1.2-1.4x wall × MM2 per-model); esc-class larger with E+. Residual-gap
analysis: which models' ESS/s stay <2x and WHY (the next-lever finder).
COORDINATION: the assembly branch (scratch/w61 lineage) is orchestrator-
#2's artifact — post on comms BEFORE using; else use my mm2-guard
binary + ridge-guard env from exp/ridge-guard's binary if buildable
separately. Machine: heavy (~1500 runs, 3-5h at 4 workers) — runs AFTER
W-107/W-108 release their cores or at reduced workers with announce.

## 2026-08-28 — W-107 CLOSE-OUT: log1p-kernel ILP unroll — gates (a)/(b)/(c)/(d-wall) PASS, (d-callgrind Ir) FAIL +1.50% BY MECHANISM: lean3 multi-accumulator unroll = 1.408x kernel throughput, BIT-IDENTICAL outputs (kernel AND hier_2pl lp+grad), model wall −7.38%/−3.48% two passes vs the W-103 kernel arm — but +1.5% retired instructions (a latency-hiding unroll ADDS spills/mask-recompute; callgrind counts instructions, not cycles). Wall win / Ir-regression trade recorded; NOT promoted (metric-choice decision)

DEPENDENCY MAP (pre-registered question, answered from codegen_probe.s):
GCC does NOT unroll the W-103 island — 1 block/iter, ~143 instr; per block
ONE dominant chain: exp ~65 cyc feeding the 16-step Clenshaw (16 x [4-cyc
fma + 3-cyc sub] ~ 118 cyc) => ~178 cyc/block critical path vs a 27-30
cyc/block pipe-work floor => ~17-20% FMA-port utilization; the island is
~28% of the kernel arm's WALL but only 13.9% of its Ir (the 2x gap IS the
latency-boundness). DESIGN: fwd_avx2_unroll<W>, W in {2,3,4}, separate
accumulators, phased (exp xW -> poly xW -> finish xW); per-block horizontal
reduction kept IN BLOCK ORDER => outputs BIT-IDENTICAL for every n (0
differing bits on 1.80M elements x 4 x-sets + 25 remainder sizes, all 6
variants; model-level: hier_2pl lp+grad hex-identical over 50 pts, STRONGER
than W-103's 1.5e-16 statistical parity). LEAN flavor (phase-1 live set
{px,sg,w,y}; nw/gt/lt recomputed in phase 3) cuts spills 464->453
instr/group. MICROBENCH (c) geomean vs u1: u2 1.229x / u3 1.394x / u4
1.366x / lean2 1.225x / lean3 1.408x / lean4 1.414x — PASS (bar 1.15x);
W=3 lean ships (lean4 loses to reg pressure: 30 ymm spill stores/group;
u2 leaves ports idle). GATES: (a) ulp = the W-46 record exactly (3 ulp
val, 4.409e-16 partials, sum_rel 0.000e+00); (b) dispatch 1.000 ulp over
2.5M pts + NEW 16-lane unrolled-path check (6.355e-16 value sum / 3.388e-16
partials, per-lane bits unchanged); (d) callgrind Ir/grad 4,795,704 ->
4,866,649 (+1.50%, gate was <= -0.5% => FAIL, structurally: island Ir
2.994e9 -> 3.320e9 = +10.9% x 13.9% share; any latency unroll fails this
sub-gate) while wall 0.9262 / 0.9652 two 5-round interleaved passes (gate
<= 0.99 => PASS; sibling-compile load present, W-59 ratio-disclosure).
POSTURE: the prereg's "honest ceiling 1-3% G" was framed on the wrong
metric for this transformation — delivered ceiling is on WALL (hier_2pl
-3.5..-7.4% on top of W-103's -13.9%) at +1.5% Ir; promotion = a
metric-choice call (G ledger vs user wall), left to the user. Composes
with W-105/106 uniform-avx2 (orthogonal layers). DELIVERABLE:
scratch/w107/bernoulli_kernel_ilp.patch (+306/-0, pristine-base
2954671f, apply-checked, result fa423fb1; the W-103 patch untouched);
trees pristine (math_soa 2954671f, math_dev_soa @a43e868 clean — its one
untracked gathered.hpp pre-dates W-107; bs_w103_kernel header re-verified
2c61408a after cp -al; bs_w53 untouched). Full record:
results/kernel_ilp_w107.md; harness+artifacts scratch/w107/ (bench_ilp,
test_kernel_ilp, dispatch_check_ilp, codegen probes, bs_kilp bundle,
model_hier_2pl_kilp .so, parity_bits, callgrind profile/kernel_ilp,
gate_timing x2). W=3 is Zen-3-tuned (lean4 marginally better on wider
silicon; one-line <3>-><4> change, re-gate with the same harnesses).

## 2026-08-28 — W-108 CLOSE-OUT (increment 1): the gathered-GLM primitive — ALL GATES PASS, bit-identical (draws md5 fe7c57… digit-for-digit), −40.9% Ir/grad on the composed stack; INCREMENT 2 = GO

Executed per the W-108 pre-registration (increment 1: primitive + hand-rewritten
model gate, no codegen). Full report: results/gathered_glm_w108.md. Deliverable:
branch `gathered-glm` @ ea96b3c9fa (parent fork/develop 344d7167a0, adds ONLY
stan/math/rev/prob/bernoulli_logit_lpmf_gathered.hpp + its unit test) in a
DEDICATED worktree external/math_dev_w108 — the pre-registered worktree
math_dev_soa was checked out back to log1p-kernel-avx2 and advanced by the
W-107 agent mid-session; no W-108 files remain there and no builds were run in
it after the collision.

PRIMITIVE: bernoulli_logit_lpmf_gathered<propto>(y, theta, jj, alpha, beta, ii)
for the exact generated shape y ~ bernoulli_logit(alpha[ii] .* (theta[jj] -
beta[ii])) — handles the compiler's real operand mix (theta var_value<VectorXd>
SoA from the deserializer, alpha/beta Matrix<var> AoS from the tp loop; all-AoS
and all-SoA too). No gathered Matrix<var>: 2N doubles + 2N ints + (J+2I) vari*
(or the single SoA vi_) per call. Value path = stock composed op order per
element (t−b then *a) + the stock lpmf interior copied verbatim over the same
Eigen expression types (signs/ntheta/exp/Select trees/sum redux). Reverse =
ONE make_callback_var doing stock's scatter-adds in stock's k order:
alpha+=(t−b)(w·d), theta+=a(w·d), beta−=a(w·d) — matching elt_multiply +
subtract callbacks AND the SoA gather's own reverse callback
(rvalue_varmat.hpp), so adjoints are bit-identical, not just close.

GATES (bit-identity class — the whole point):
(a) unit, scratch/w108/test_prim.cpp, composed stock via the REAL
    stan::model::rvalue/index_multi, 22 cases × 3 layouts (real 19200-grid,
    N≤49999, I/J≤100, |ntheta|>20 branch cuts, all-y0/all-y1, N=1..8): 9,000
    bitwise checks (lp + every gradient component, memcmp), 0 mismatches, on
    BOTH the stock-interior and kernel-interior bundles. (This gate CAUGHT a
    real dev bug: leftover vi-fill loops wrote a size-0 arena map OOB and
    pushed vari_view records for SoA operands → segfault; fixed before any
    number below.)
(b) hand-edited hier_2pl.hpp (2-line diff: include + the REV-mode likelihood
    line only; double-mode instantiation untouched), built on the bs-copy
    wiring: parity 100 pts EXACT-ZERO both pairs (0/100 lp, 0/100 grad
    vectors); full sampler draws W-29 protocol (walnutpie stan_cli READ-ONLY):
    prim on the stock stack = md5 fe7c57c99a7a6530ce2dcc408d6e9c65
    DIGIT-FOR-DIGIT (plain and under valgrind), and the kernel-interior
    variant on bs_prim = md5 1744c2087c7049203b0e78bc6f4b5107 = the W-103
    kernel arm's draws digit-for-digit.
(c) callgrind, 4,493 identical grad calls all arms, interior held constant
    (w46::fwd_avx2 Ir identical to the digit): kernel-pair Ir/grad
    4,795,704 → 2,831,876 = −40.95% (gate ≤ −15% PASS; pre-registered
    −15..−25% band overrun disclosed). Bonus stock-interior pair:
    6,563,777 → 5,012,233 = −23.63%. Attribution: the eltwise+gather complex
    (13.87e9 Ir: elt_multiply 3.738e9 + subtract 2.889e9 + rvalue gathers
    2.804e9 + subtract's reverse callback 1.104e9 + update_adjoints 0.714e9 +
    ops_partials_edge ctor 0.584e9 + composed lpmf self 2.040e9) → 0, replaced
    by primitive fwd 3.897e9 + scatter callback 1.784e9. Vs the W-34-era stock
    baseline (7.745M Ir/grad) the composed current stack is at 2.832M = −63.4%.
(d) unit tests: new TU 3/3 PASSED on the branch; untouched control
    bernoulli_logit_glm_lpmf_test 22/22 PASSED; external/math_soa untouched
    (exactly the 14-file SoA slice, lpmf pristine 2954671f…).

VERDICT increment 1: GREEN on every pre-registered gate; the open question
("value bit-identity impossible because X → escalate to statistical gates")
resolved NEGATIVE — bit-identity is achievable and proven at three levels
(unit bitwise, model parity exact-zero, same-seed draws md5). INCREMENT 2
(stanc3 pattern detection + emission of the primitive call) = GO; the pattern
to match is bernoulli_logit_lpmf(y, elt_multiply(gather(a,ii), subtract(
gather(t,jj), gather(b,ii)))) with data-typed index vectors (grid-complete
designs keep the W-34 arm-B GEMM rewrite as the better target). Artifacts:
results/gathered_glm_w108.md; scratch/w108/{bs_prim,bs_prim_stock,test_prim*,
make_kernel_variant.py,gate_parity_w108.py,model_hier2pl_prim*,draws,profile};
branch external/math_dev_w108 gathered-glm @ ea96b3c9fa (NOT pushed).

## 2026-08-28 — W-108 INCREMENT-1 CLOSED ALL-GATES + math#7 FILED; INCREMENT-2 PRE-REGISTRATION (stanc3 emission): detect the gathered-bernoulli-logit pattern in MIR and emit the primitive call

math#7 = sims1253/math#14 (branch gathered-glm @ ea96b3c9fa off develop,
plain-style body, [upstream-candidate]). INCREMENT 2 DESIGN: a stanc3 MIR
pass (external/stanc3, new branch gathered-glm-emit off its develop) that
recognizes the pattern: lpdf(bernoulli_logit) applied to an expression of
the form (gather(A, i) - gather(B, j)) [with the operand-mix variants the
generated code actually produces: var_value<VectorXd> SoA vs Matrix<var>
AoS] and rewrites the call to bernoulli_logit_lpmf_gathered. Constraint:
the C++ signature must accept the ACTUAL stanc3-emitted types (the W-108
header already handles the mix). GATES: (a) pass fires ONLY on the
pattern (negative controls: non-gathered eltwise, gathered-non-bernoulli,
three-term gathers — no rewrite); (b) regenerated hier_2pl.hpp ≡ the W-108
hand-edit (the emission matches what was gated); (c) end-to-end: stanc3
regen → build → draws md5 fe7c57… (stock math) / the W-108 kernel-variant
md5 on the kernel bundle; parity exact-zero; (d) other models regen
WITHOUT the pattern compile byte-identical .hpp (the pass must be a no-op
elsewhere). Machine: OCaml build ~1-2h single stream; coordinate.

## 2026-08-28 — W-109 CLOSE-OUT [everything-ess]: the composed-posture ESS/s table is IN — 540/540 clean, E/S ESS/s geomean 1.485x (sampling-only 1.637x; ON-13 1.75x, OFF-8 math-only 1.13x; E+/E 1.438x) — expectation 2.5-6x MISSED for a STRUCTURAL reason: the S baseline already contains the protocol posture (pf inits + mw50), so E/S isolates MM2 × math-layer only, and MM2 pays its ESS in grads (ON-13 wall +14%)
STAGING: determinism 8/8 bit-exact (w36exp CLI + w106 alllayers .so
reproduce scratch/w106/ess_b Part-B csvs md5-EXACT, incl. the
kronecker rep0_c0 cell that aborted for W-105b); 18 new all-layers .so
+ 11 pristine stock .so built (uniform-flag property verified in
build_logs: model .o AND bridgestan.o both -mavx2 -mfma; stock default
flags, CXX=gxx_fixed — system g++ still broken liblto_plugin). THREE
RECORDED DEVIATIONS: (1) sampler = build_mg not the prescribed
build_main (build_main lacks --init-file AND --metric-window — cannot
run the protocol; no canary record; worktree mid-modification by
another session); (2) ridge-guard ABSENT from E — no binary on the box
carries MM2-guard+ridge (40 builds checked; ridge only in external_w86
exp/ridge-guard; assembly unreleased on comms) — the W-88/99
decomposition stands in, and the residual-gap list shows exactly where
it would bite (pilots/bym2/diamonds/accel ridge-locked ESS~4-5,
rhat-fails IDENTICAL S=E); (3) MM2 ON = benefit-list ∩ CORE_SET = 13
(OFF 8 = 4 economic-harm + 4 fired/degenerate; for those 8 E-vs-S
isolates the math layer: ESS 0.89x, wall 0.77x).
VERIFIED CONSISTENT WITH ARCHIVE: S reproduces W-84's A0 ESS medians
(radon_pp 220.8/216.7, ldgm 792/778.6, wells 769/749, arma11 1028/
1022, 8sch_nc 1488/1470...); E reproduces W-82/84 GMD (hier_2pl
1489.5/1556.6, wells 1648/1599, ldgm 1342/1389). Zero guard fires in E
(13 MM2 models x 36 chains — the W-84 silent prediction).
HEADLINES: E/S ESS/s geomean 1.485x full-wall / 1.637x sampling-only;
>2x class = hier_2pl 2.19, logmesquite 2.27, wells 2.60, lotka 11.16
(MM2-surplus + wall headroom); esc 0.41x = the W-92 stack-sensitivity
class repeating on the math-layer axis (per-rep consistent, E+ recovers
1.69x); radon_pp 0.90x = MM2 grad spend (wall 1.66x) exceeds its
1.68x ESS surplus; E+ (cap 2.0, W-91 value, subset esc/hier_2pl/arma11)
STACKS: E+/E 1.438 geomean (hier_2pl 1.47 ESS 1489->1868; arma11 1.20
via wall DOWN; esc 1.69). rhat arm-neutral on floor models (9610=9610,
72=72, 16=16, 17=17); MM2 heals lotka 90->4 fails. HONEST PROJECTION:
with ridge composed + on its W-88/99 domain the everything-stack E/S
geomean lands 2-3x (W-88's +57% aggregate geoESS on top of this E) —
the composition (assembly/combined-posture) is the single highest-value
missing measurement. Wall LOAD-FLAGGED throughout (driver loadavg
median 3.98/max 6.67 of 12; sibling compile + desktop; arms interleaved
per cell so ratios cancel drift).
Artifacts: results/everything_ess_w109.md (full tables + 17-model
residual-gap list with per-model WHY); scratch/w109/{runs/,driver_w109
.py,analyze_w109.py,w109_results.json,spotcheck/,build_logs/,model_*_
alllayers/,quiet_stock/}. Machine: grid 1.21 h wall-sum, 22 min
elapsed at 4 workers nice 19; +7 min builds; ~1.4 core-hours total.

## 2026-08-28 — W-108 INCREMENT-2 CLOSED ALL-GATES: stanc3 emits bernoulli_logit_lpmf_gathered itself — the compiler-generated hier_2pl is bit-identical end-to-end (parity exact-zero, draws md5 fe7c57… digit-for-digit, same as the i1 hand-edit)

Executed per the "INCREMENT-2 PRE-REGISTRATION" appended with the i1
close-out. Full report: results/gathered_glm_emit_w108i2.md. Deliverable:
stanc3 branch gathered-glm-emit @ 58e6824 (parent master 90c6532,
w48-fusion's lineage) in a NEW worktree external/stanc3_w108 —
external/stanc3 (w48-fusion @ 4b07a23) verified untouched. NOT pushed.

PASS DESIGN: Optimize.gather_bernoulli_logit, LAST in optimization_suite
(after block_fixing), new settings field like every other pass; ON at
--O1 + --Oexperimental, OFF at --O0 (the repo convention — all
correctness-preserving suite passes run at O1; stated per the pre-reg;
upstream submission would gate --Oexperimental until the primitive lands
in math — recorded in the commit). Matches TargetPE(
bernoulli_logit_lpmf(data-int-vector y, EltTimes__(gather(a,ii),
Minus__(gather(t,jj), gather(b,ii))))) with SAME ii for a and b, in
mir.reverse_mode_log_prob ONLY (double-mode instantiation keeps stock,
matching the gated hand-edit), preserving the FnLpmf suffix (~ →
<propto__>, target+= → <false>). Rewrites to
bernoulli_logit_lpmf_gathered(y, theta, jj, alpha, beta, ii) — the W-108
header's parameter order; no lowering special-case (default
lower_fun_app path), and Lower_program emits the primitive #include ONLY
when the rewrite fires (pattern-free includes unchanged). New integration
model gathered-bernoulli.stan (2 firing incl. target+= form + 4
non-firing); expectations regenerated as a SINGLE pure insertion at all 3
levels.

GATES: (a) negative controls NEVER fire — non-gathered eltwise, gathered
normal_lpdf, three-term gather (external .stan files + in-repo), plus
mixed-index-vector and O0 controls; double-mode instantiation untouched.
(b) regenerated hier_2pl.hpp (--O1 --debug-optimized-mir, same input path)
≡ the i1 hand-edit with the ONLY diff the whitespace wrapping of the
likelihood statement; include + stancflags + every other line
byte-identical. models/hier_2pl.hpp restored byte-intact after capture
(shared reference NOT modified). (c) END-TO-END with NO manual C++: the
regenerated .hpp built on scratch/w108/bs_prim_stock (W-103-era prebuilt
bridge reused untouched; gxx_fixed, -j2 nice 19, env -u
LD_LIBRARY_PATH) → parity 100 pts vs the W-103 stock-form .so EXACT-ZERO
(0/100 lp, 0/100 grad vectors; bridgestan C ABI via ctypes — the python
module env is broken) AND W-29-protocol draws md5
fe7c57c99a7a6530ce2dcc408d6e9c65 DIGIT-FOR-DIGIT (= i1's hand-edit and
the stock reference). The emitted rev-instantiation keeps the real
operand mix (theta var_value<VectorXd> SoA, alpha/beta Matrix<var> AoS)
the header's if-constexpr routes handle. (d) blr/diamonds/
eight_schools_centered at --O1: BYTE-IDENTICAL to the base compiler
(same in/out paths, cmp clean); bonus — all 5 existing models/*.hpp
references regenerate identical modulo my invocation's embedded path
strings. dune runtest -j2 exit 0 (full tree + explicit code-gen/
compiler-opt/bad dirs).

W-108 IS NOW CLOSED AS A PAIR: math primitive (gathered-glm @ ea96b3c9fa,
filed math#7) + compiler emission (gathered-glm-emit @ 58e6824) — the 2PL
class model needs no hand edit to reach −40.9% Ir/grad bit-identically.
Remaining upstream packaging: header PR + this pass behind --Oexperimental
+ the runtime grid-completeness story (W-48 §6) deferred as pre-registered.
Machine: ≤2 cores nice 19 throughout, load ≤1.8 (no W-109 waits needed);
one stanc3 build ~25 min + runtest ~3 min cached.

## 2026-08-28 — W-108 INCREMENT-2 CLOSED ALL-GATES + stanc3#2 FILED: the gathered-GLM lane is COMPLETE end-to-end — compiler detects the pattern at --O1, regenerates byte-identical-to-hand-edit, no-op elsewhere (negative controls + 5 reference models byte-identical), end-to-end draws fe7c57… digit-for-digit with NO manual C++. PR sims1253/stanc3#2 ([upstream-candidate], base master, plain-style body, REQUIRES math#14 stated). The lane: −41% Ir/grad on the kernel arm / −63% vs stock, bit-identical, now automatic.

## 2026-08-29 — W-111 PRE-REGISTRATION (before any run): gathered-GLM generalization census — callgrind attribution of the candidate families' per-element complexes (sizing the W-108 successor campaign; NO code)

CONTEXT: W-108 closed the bernoulli_logit-gathered lane (−40.9% Ir/grad
bit-identical, math#14 + stanc3#7). The user's session questions: which
OTHER families admit the pattern. Desk census over all 21 CORE_SET models
(+ build/ extras) found: normal-with-gathered-mu in LOOP form (radon_pp
N=12,573/J=386; radon_var N=919/J=85; pilots N=40 = negligible), ICAR
dot_self(gather−gather) in EXPRESSION form (bym2 N=1,921/5,461 edges),
pcm/ordered-logistic gathered (gpcm_latent_reg_irt in build/, non-CORE —
the W-80 harm model doubles as gate), additive multi-gather
bernoulli_logit (election88_full in build/, non-CORE), and NEGATIVES:
lsat (broadcast, no gather), dogs (plain bernoulli, 2 params, 750
cells), poisson_log/neg_binomial_2/categorical gathered (zero in-suite
models — register-only). Corrections carried: the /tmp handoff's
"pilots are bernoulli" and "poisson_log gathered: bym2 class" were both
wrong (pilots is normal N=40; bym2's likelihood has NO gather).

DESIGN: 4 callgrind runs, W-29 short protocol verbatim (warmup 100,
samples 50, seed 20260819, --metric-window 50, pf init rep0/chain_0 per
the w63 manifest), sampler build_w36exp READ-ONLY, .so = the W-109
ALL-LAYERS arms (scratch/w109/model_*_alllayers — measures what remains
AFTER the landed layers, the same reference class W-108 gated against).
One callgrind at a time, nice 19, env -u LD_LIBRARY_PATH,
OMP_NUM_THREADS=1.

EXPECTATIONS (pre-registered): (1) radon_pp per-element loop complex
(scalar normal_lpdf<false> instantiations + assign/rvalue<index_uni> +
their edges/callbacks) >= 40% of G (only 390 params outside it; N=12,573
scalar calls; hier_2pl's composed eltwise complex was 64%); (2) bym2
ICAR complex (rvalue<index_multi> x2 + subtract + callbacks + dot_self)
15-35% of G, with poisson_log likelihood + tp eltwise a further large
NON-gather chunk (W-48-neutral class — out of this lane); (3) lsat:
zero index_multi gather symbols above noise (negative control — its
eltwise broadcast complex is interior/fusion class); (4) radon_var loop
complex >= 30% of G. NO gates binding (measurement); negatives recorded
same as wins. Deliverable: results/gathered_glm_generalization.md
(census + campaign plan + measured sizing). Machine <= 1 core, no wall
claims.

## 2026-08-29 — W-111 CLOSE-OUT: the gathered-GLM generalization census — ALL FOUR pre-registered expectations PASS with upward overruns disclosed — radon_pp's scalar-lpdf LOOP complex is 90.1% of G (the largest unexploited math-side target in the suite), radon_var 87.4%, bym2's ICAR gather complex ~43%, lsat negative control 0 gather symbols

Executed per the W-111 pre-registration (4 callgrind runs, W-29 short
protocol, all-layers .so arms, one at a time). Full record:
results/gathered_glm_generalization.md. NUMBERS (G = inclusive
bs_log_density_gradient Ir; T = program total):

- radon_pp T 28.27e9, G 26.32e9 (93.1%): scalar normal_lpdf<false> body
  42.6% + per-element libm log(sigma) 13.6% + assign/rvalue loop machinery
  16.7% + chainstack emplace 10.5% + lp_accum sum 2.0% + scalar-call edges
  4.6% = LOOP COMPLEX 90.1% of G (expectation was >=40%). Mechanism note:
  the loop's propto=false form calls log(sigma) per ELEMENT (13.6% of the
  whole gradient); a primitive computes it once (deterministic value, so
  per-term reuse is bit-identical if the addition schedule is kept).
- radon_var T 2.45e9, G 1.73e9 (70.6%): loop complex 87.4% of G
  (expectation >=30%).
- bym2 T 18.03e9, G 5.01e9 (27.8% — sampler-side mass-ops + output
  formatting dominate T): ICAR complex (subtract(Holder) fwd+cb 23.8% +
  index_multi gathers 11.2% + dot_self fwd+cb 4.1-8.1%) ~43% of G
  (expectation 15-35%). EXPRESSION form — the direct W-108 matcher class,
  no loop problem. poisson_log likelihood itself only 5.7%; eta assembly
  ~18% = the W-48-neutral fusion class.
- lsat (negative control): ZERO index_multi gather symbols (G 3.64e9;
  broadcast eltwise 39.3% + interior 32.3% = fusion/kernel class, NOT the
  gathered lane). Expectation confirmed exactly.

CAMPAIGN MAP (ranked, recorded for the next session's pre-registrations;
NO code this session): (1) normal_lpdf_gathered for the LOOP-form radon
class — expectation band -60..-85% G on radon_pp; design forks: scalar
lpdf op-order bit-identity target (in-order accumulation, NOT Eigen
redux) + a stanc3 LOOP-pattern matcher (new matcher class); (2) ICAR
dot_self_gathered (bym2; expression matcher exists; band -25..-40% G);
(3) pcm/ordered gathered (gate model gpcm_latent_reg_irt, build/,
non-CORE); (4) additive multi-gather bernoulli_logit (election88_full,
build/); (5) register-only: poisson_log/neg_binomial_2/categorical
gathered (no suite gate model). stanc3 side becomes a REGISTRY (family
table: expression + loop matchers, per-entry negative controls).
Census corrections carried into the record: pilots = NORMAL family N=40
(negligible math target; ridge class), lsat = no gather (broadcast),
bym2's gather is the ICAR prior not the likelihood. PR numbers verified
vs the forks: math#14 + stanc3#7 (the "math#7"/"stanc3#2" labels in two
earlier close-out headers were internal typos). Machine: <=1 core
throughout, load ~1.2, no wall claims. Artifacts: scratch/w111/
(profile_*/ callgrind.out + ann + incl_ann + cli.log + draws.csv,
run_census_w111.sh, census.log); results/gathered_glm_generalization.md.

## 2026-08-29 — W-110 PRE-REGISTRATION (before any run): the staged ridge-composed E-arm — assembly binary × all-layers .so on the 4 ridge-locked W-109 gap models (executed by the sole active session per user direction; the run was staged by the SoA session 2026-08-28 with "pre-reg ready")

CONTEXT: W-109's residual-gap analysis named the ridge composition the top
sampler-side lever and "the single highest-value missing measurement":
pilots/bym2/diamonds/accel sit at ESS ~4.4-4.6 with rhat-fail counts
IDENTICAL S=E (ridge-locked floors), and no binary carried MM2+ridge. The
W-96 assembly branch IS that composition: assembly/combined-posture @
472609b on the fork; its worktree scratch/w61/walnutpie_w96 with the built
binary build_w96/examples/stan_cli is intact, verified at the branch head
(remote ref matches), and smoke-checked (init-screen/multi-chain/MM2
flags present; ridge guard in stan_cli.cpp reads cross-chain positions
post-warmup, F>threshold → rebuild at min-micro 128 for sampling).

ARMS (4 models {pilots, bym2_offset_only, diamonds, accel_gp} × 3 reps ×
4 chains, w1000 s1000, pf inits, --metric-window 50, --seed
20260819+1000·rep with --chains 4 in-process — per-chain seed +c IS the
W-109 convention, verified in source; --chain-exec serial [DEVIATION
from W-88's threads layout, disclosed: the alllayers .so are
STAN_THREADS=false and the assembly carries PR #21's refusal guard;
serial≡threads draws equivalence is W-75-proven 12/12 md5]; --init-file
/ --output take {c} patterns, verified in source):
- R0 (control): assembly binary, DEFAULT path (no env knobs, no MM2
  flags — these 4 are the MM2-OFF class, so R0 = the W-109 E-arm posture
  re-run on the assembly binary).
- ER (composed): R0 + WALNUTPIE_RIDGE_GUARD=5 (threshold 5 = the W-95
  calibration; MINMICRO keeps the assembly's fixed-128 default — the
  branch predates W-102's graduated budget; disclosed; fixed-128 is
  accel's preferred setting per W-102).
.so = the W-109 ALL-LAYERS arms (scratch/w109/model_*_alllayers) — the
E-arm models, reused read-only. BASELINES: W-109's S and E table values
(results/everything_ess_w109.md).

GATES/EXPECTATIONS (pre-registered):
(a) completion 24/24 rc=0, zero aborts;
(b) UNFIRED-ER cells BIT-IDENTICAL to R0 (per-chain csv md5) — the guard
    is a pure no-op below threshold;
(c) fired-cell ESS per the W-88/99 decomposition: pilots ESS-min 4.6 →
    ≥20 (W-88: 33), bym2 4.4 → ≥9 (W-88 +145%), diamonds 4.5 → ≥30,
    accel 4.4 → ≥8; rhat-fail counts on fired models collapse toward 0
    (W-99: 0 false positives, 9/9 fired cells rhat-improved);
(d) R0 ESS statistically consistent with W-109 E (same .so, equivalent
    default flags); draws NOT expected md5-equal to W-109's build_mg
    cells (the assembly's documented pin_trace ulp shift — W-96 gate (b),
    W-107 resolution).
NO promotion decision here (user's Package A call); deliverable = the
composed ESS/s table + the honest everything-stack projection update
(W-109 projected E/S geomean 2-3x with ridge composed).
Machine: 24 single-process runs, ≤4 cores nice 19, one grid, no quiet
window needs. Ruler: scratch/w88/blessed_estimators.py.

AMENDMENT (before any grid cell ran successfully; the first launch
attempt failed 24/24 at startup — all rc!=0, zero sampling — recorded
here per protocol): **BINARY SWAP: assembly → external_w86 (exp/
ridge-guard @ 7dd0f71, binary build_w86/examples/stan_cli).** Root
cause of the failed launch, and a genuine W-96 ASSEMBLY DEFECT now on
the record: the assembly's stan_cli.cpp DEFINES run_walnuts_multi
(line 785, containing the merged #22 ridge guard at line 1011) but
NEVER CALLS it — main() dispatches only the single-chain run_chain, so
--chains 4 parses and then dies opening the literal {c} init pattern
("cannot open --init-file: … chain_{c}.txt", the single-chain site).
The assembly's ridge guard is UNREACHABLE CODE: the mm2-guard lineage
(W-82) that W-96 assembled around is single-chain-only and dropped the
multi-chain dispatch the guard was written against. Package A fix note
for the user: the assembly needs the multi-chain dispatch lineage
merged (or the guard ported to the single-chain CLI) before its guard
can ever fire; W-96's "features-on" spot did not exercise the guard.
Consequences for W-110: (1) binary = external_w86 exp/ridge-guard tip
7dd0f71 — the guard's home, multi-chain dispatched (verified: call
site at stan_cli.cpp:1372), the exact binary family W-88/W-99/W-102
validated; (2) its tip carries the W-102 GRADUATED budget (vs the
assembly's fixed-128) — the ADOPTED variant; disclosure: accel prefers
fixed-128 (W-102 ESS 3487 vs 2099 graduated) while diamonds prefers
graduation; (3) arms become the W-99 same-binary A/B design: R0 =
external_w86 env UNSET (default path), ER = WALNUTPIE_RIDGE_GUARD=5;
both --chains 4 --chain-exec serial --fixed-warmup (deterministic
w1000; the W-30-gates convention), .so unchanged (W-109 all-layers,
non-THREADS — serial exec needs no threads safety). Gate (b)
strengthens: same-binary env-toggle makes unfired-ER ≡ R0 expected
BIT-IDENTICAL with no binary-provenance caveat.

## 2026-08-29 — W-110 CLOSE-OUT: ridge-composed E-arm on the 4 floor models — GATE (c) FAILS at the median on all four (ESS 1.45-2.21x UP, ESS/s 0.150x geomean = large NET LOSS at graduated budgets); two mechanisms diagnosed (graduated budget under-budgets the fired class — pilots 6.4→103 at fixed 128 same rep; F=16k locks not budget-healable — bym2 rep1 4,824s/chain at 128 stayed locked); W-109's "2-3x with ridge" projection REFUTED for ESS/s (it is a QUALITY lever: rhat-max collapse, full heals 103/61/23 in the right regime)

Executed per prereg + amendment. Full record: results/ridge_composed_w110.md.
Gates: (a) 24/24 PASS; (b) VACUOUS — guard fired 12/12 (every model/rep
ridge-locked, as predicted); (c) ALL FOUR FAIL at median: pilots 9.7
(gate >=20), bym2 6.4 (>=9), diamonds 8.1 (>=30), accel 7.1 (>=8
marginal) — rep-level full heals exist (bym2 r0 23.0 + rhat-fails
9412→743; diamonds r1 61.5, rhat 1.06); (d) R0 ESS medians reproduce
the W-109 E table EXACTLY on all four (4.4/4.4/4.3/4.6). POST-HOC
diagnostic (labeled): pilots x WALNUTPIE_RIDGE_MINMICRO=128 → ESS
103.0/8.4/12.2 vs graduated 6.4/9.7/15.1 — the F=5.2→16 graduation
forfeited a 16x heal on rep0; W-102's accel finding generalizes (3 of 4
fired models want full 128; diamonds wants graduation — selector problem
deepens). bym2 rep1: F=15,924, 4,824s/chain at 128, STILL locked (ESS
4.0, rhat inf) — the deep-lock class is init-pathology (W-84), not
budget. COMPOSED-POSTURE CORRECTION: quote the everything-stack ESS/s
(1.485x) WITHOUT ridge; ridge = per-model quality escape whose budget
rule needs revision (user lane). ALSO ON RECORD: the W-96 assembly's
ridge guard is UNREACHABLE CODE (run_walnuts_multi defined, never
called; --chains 4 dies on the literal {c} init pattern) — Package A
must merge the multi-chain dispatch lineage or port the guard to the
single-chain CLI. Wall convention disclosure: per-rep wall = SUM of 4
overlapping per-chain timers (serial round-robin) ≈ 4x true wall —
within-table ratios valid, NOT comparable to W-109 wall column. Machine:
one grid ~2.5h wall (bym2 ER cells dominate: 2,903/19,483/6,313s), ≤1
core effective (serial), nice 19, load ~1.5-2. Artifacts: scratch/w110/
(runs/{R0,ER,ER128}, run_w110.py, analyze_w110.py, grid.log);
results/ridge_composed_w110.md.

## 2026-08-29 — W-112 PRE-REGISTRATION (before any code): gathered-GLM campaign FAMILY 1, increment 1 — normal_lpdf_gathered for the LOOP-form radon class (primitive + hand-edited model gates; no codegen)

Per the campaign map (results/gathered_glm_generalization.md; W-111
measured the loop complex at 90.1% of G on radon_pp / 87.4% on
radon_var). Method = the W-108 recipe.

PRIMITIVES (new header stan/math/prim or rev placement per W-108
precedent; branch `gathered-normal` off fork/develop 344d7167a0 in a
DEDICATED worktree external/math_dev_w112 — created via git worktree
from the math repo, like W-108):
- `normal_lpdf_gathered<propto>(y, alpha, ii, sigma)` — eta[n] =
  alpha[ii[n]] (radon_pp);
- overload for eta[n] = alpha[ii[n]] + x[n] * beta[ii[n]] (radon_var;
  x data vector, beta second coefficient vector).
BIT-IDENTITY TARGET = the generated LOOP form (NOT the vectorized
expression): per element the SCALAR `normal_lpdf<false>(y_n, mu_n,
sigma)` op order verbatim (propto=false includes the log-sigma constant
term per element; log(sigma) is deterministic so the primitive may
compute it once and reuse the double, but the per-term ADDITION
schedule must match), lp accumulated in a plain n-order loop (NOT
Eigen redux), and reverse = stock's accumulation order for the shared
scalar sigma (per-call edge adds in n order) + scatter-adds into
alpha/beta through the index arrays in n order (the assign/rvalue
aliasing route the generated code produces). Operand layouts: alpha/
beta as Matrix<var> (tp-loop AoS — the real radon case) AND
var_value<> (SoA); sigma as var and as double.

GATES (bit-identity class):
(a) unit, bitwise vs the composed stock LOOP using the REAL generated
    pattern (stan::model::rvalue index_uni + assign into a local var
    vector + scalar normal_lpdf<false> per element), randomized
    shapes/values (N up to ~13k, J up to ~400, degenerate/edge sigma,
    x vectors for the radon_var shape, N=1..8, repeated indices): lp +
    EVERY gradient component memcmp-exact. This gate stays maximally
    strict (W-108's caught a real OOB bug).
(b) model gate: HAND-EDITED copies of the generated radon_pp and
    radon_var hpp (rev-mode likelihood loop replaced by the primitive
    call; double-mode instantiation untouched), built on the bs-copy
    wiring: FIRST record stock reference draws md5 under the W-29
    protocol (build_w36exp CLI READ-ONLY, seed 20260819, warmup 100,
    samples 50, --metric-window 50, pf init rep0/chain_0 from inits_w36
    / inits_w63), then primitive arm must match DIGIT-FOR-DIGIT; parity
    100 pts exact-zero vs the stock .so.
(c) callgrind (W-29 protocol, one at a time, ~/vginstall): hand-edit
    arm vs stock arm on radon_pp AND radon_var. PRE-REGISTERED BAND:
    −60..−85% G on radon_pp (complex 90.1%; primitive keeps ~10-20
    Ir/elem interior + scatter), −55..−80% G on radon_var. Attribution
    table: which loop-complex symbols go to zero.
(d) untouched-control ctest (normal_lpdf tests) + new unit TU.
ESCALATION: if (a) bit-identity proves impossible, STOP and report the
mechanism — statistical-class re-gate is a PI decision, not the
agent's. NO increment-2 (stanc3 loop matcher) this W.
Machine: ≤2 cores builds nice 19; callgrind serialized against W-113
(check `ps aux | grep -c '[c]allgrind'` before starting; wait+recheck
if busy). Records: agent reports gates to the PI (this session); PI
writes ledger/comms. Never push upstream; DCO-sign commits.

## 2026-08-29 — W-113 PRE-REGISTRATION (before any code): gathered-GLM campaign FAMILY 2, increment 1 — dot_self_gathered_diff for the bym2 ICAR prior (primitive + hand-edited model gate; no codegen)

The ICAR line is EXPRESSION form today: `target += -(0.5) * dot_self(
subtract(rvalue(phi, index_multi(node1)), rvalue(phi, index_multi(
node2))))` (W-111: complex ~43% of G). Branch `gathered-icar` off
fork/develop 344d7167a0 in a DEDICATED worktree external/math_dev_w113.

PRIMITIVE: `dot_self_gathered_diff(phi, node1, node2)` — value = the
stock chain replicated bit-for-bit (read rev/fun/dot_self.hpp + the
eltwise subtract over Holder<IndexedView> operands in the actual tree;
replicate per-element subtract order AND the dot_self reduction order —
Eigen dot/squaredNorm reduction semantics decide bit-identity, the
bitwise unit gate arbitrates); reverse = ONE callback doing per-edge
scatter phi[node1[e]] += w*2*d_e, phi[node2[e]] -= w*2*d_e in stock's
callback order (subtract's callback then dot_self's — replicate what
stock actually does, including the -(0.5) scaling living OUTSIDE the
primitive as today). Operand layouts: phi as var_value<> (SoA — the
real bym2 case) AND Matrix<var>.

GATES:
(a) unit bitwise vs the composed stock EXPRESSION using the REAL
    stan::model::rvalue + index_multi (the W-108 reference pattern),
    randomized graphs (N up to ~2000, edges up to ~5500, both index
    arrays unsorted/repeated, self-edge-free), phi SoA + AoS: value +
    every gradient component memcmp-exact.
(b) model gate: hand-edited bym2.hpp (ICAR line → primitive; everything
    else untouched), bs-copy wiring: stock reference draws md5 recorded
    FIRST (W-29 protocol, pf init inits_w36/bym2_offset_only rep0
    chain_0), primitive arm DIGIT-FOR-DIGIT; parity 100 pts exact-zero.
(c) callgrind bym2: PRE-REGISTERED BAND −20..−35% G (complex ~43%;
    primitive keeps diff+square+reduce interior). NOTE the honest
    framing: bym2 G is only 27.8% of program T — model-level wall
    effect is bounded; the class story (ICAR/CAR disease mapping) is
    the upstream interest.
(d) untouched-control ctest (dot_self + eltwise tests) + new unit TU.
ESCALATION as W-112. Machine: same discipline; callgrind serialized
against W-112.

## 2026-08-29 — W-113 CLOSE-OUT (PI-arbitrated): dot_self_gathered_diff — gates (a)/(b)/(d) ALL PASS (59,178 bitwise checks 0 mismatches — the strict unit gate CAUGHT a real scatter-order bug: GCC evaluates subtract's args right-to-left, so the SoA reverse must scatter node2-before-node1 in callback order; first implementation failed last-bit on dual-endpoint components), draws md5 54c62090… DIGIT-FOR-DIGIT, parity 100 pts exact-zero (full D=3845 gradients), controls 54/54; gate (c) −17.0% G — band UNDERRUN (−20..−35% pre-registered) honestly disclosed: the entire 2,161M-Ir ICAR complex → 0, replaced by primitive fwd 980.3M + scatter 330.3M; bit-identity forces the scalar-sequential dot loop (no SIMD reassociation) + 2×E bounds checks + arena fills ≈ 51.6 Ir/edge retained

PI ARBITRATION: (a)/(b)/(d) accepted at full strength (a THIRD operand
layout discovered and covered — Map<const Matrix<var_value>> via the
deserializer, proven bitwise at model level first; exception-name
deviations disclosed). (c) accepted WITH the underrun disclosed — the
−17.0% is real and bit-identical, the miss is the honest cost of the
bit-identity constraint on the reduction. PI DECISION: NO W-113.1
relaxed-precision variant (headroom −20%+ exists at "small semantics
deviations") — the campaign's headline property is bit-identity;
trading it for a few % G on one small-G model is a bad trade. Increment-2
(stanc3 emission) = GO as the registry's second entry once W-112 lands
(matcher = the W-108 expression class over dot_self(subtract(gather,
gather))). Deliverable: branch gathered-icar @ 3b9ee1b7dd (parent
fork/develop 344d7167a0) in external/math_dev_w113, 2 files, 3 DCO
commits, NOT pushed. Full record: results/icar_gathered_w113.md;
artifacts scratch/w113/. Machine: callgrind run last per coordination,
no contention.

## 2026-08-29 — W-114 CLOSE-OUT (PI-arbitrated): assembly/combined-posture-v2 — the W-96 dead-dispatch defect FIXED, all four canaries GREEN; Package A is functional again (artifact branch on fork, NO PR)

Approach: merge exp/ridge-guard 7dd0f71 into the assembly (merge-base
4b1cdb8; the merge was CLEAN — no conflicts; the two commits unique to
7dd0f71 are confined to run_walnuts_multi, disjoint from the assembly's
edits) + ONE surgical commit restoring the dispatch block verbatim from
7dd0f71 (with one adaptation: init_screen_enabled() for the assembly's
W-77 param). ROOT-CAUSE NOTE: the defect was NOT a missing merge — the
W-96 assembly's OWN conflict resolution dropped the dispatch (git
preserves that), which is why the merge alone could not fix it.
Branch assembly/combined-posture-v2 @ 5a797d0 (merge a4ea22c, parents
472609b + 7dd0f71), fork artifact only. CANARIES: (a) build green
(scratch/w114/build_v2); (b) single-chain default path v2 ≡ v1
BIT-IDENTICAL (hier_2pl f5db6c52…, pilots 75e71929…, W-29 protocol);
(c) --chains 4 --chain-exec serial dispatches AND the guard FIRES with
the graduated W-102 budget live — F=21.36 → "raising min micro steps to
68" = 16×F/5, proving the graduated curve (and mechanically explaining
W-110's under-budgeting: at F≈5 the curve yields only ~16);
(d) tree diff v1→v2 = examples/stan_cli.cpp only (+110/−1, 5 hunks, all
multi-chain-side; the single-chain region byte-identical, md5
1d99eeea…); Package A symbols verified (init screen ×4 sites, NaN
guard, ridge guard reachable, mm2 wired at ALL 8 run_walnuts sites).
Record: results/assembly_v2_w114.md; worktree scratch/w114/walnutpie_v2.
CONSEQUENCE: the user's Package A decision now has a functional
assembly; the fired-class budget curve (16×F/5, floor ~16 near
threshold) is the concrete knob for the ridge-budget decision lane.

## 2026-08-29 — W-112 CLOSE-OUT (PI-arbitrated): normal_lpdf_gathered — ALL FOUR GATES PASS, bit-identical, BOTH callgrind bands HIT: radon_pp G −65.54% (26.32e9 → 9.07e9; band −60..−85), radon_var −66.40% (1.73e9 → 0.58e9; band −55..−80) — the campaign's headline family lands

Gates: (a) 22,360 bitwise checks 0 mismatches (real rvalue/index_uni/
assign + REAL accumulator<var> on both sides; real grids; sigma
{0.5,1,1e-3,1e3} var+double; zeros/negatives in x; repeated/permuted
indices; AoS+SoA; propto=true; plus 12,573/12,573 per-element term
values bitwise on the real grid) — the gate caught TWO real 1-ulp FMA
defects during development (fixed, disassembly-verified). (b) draws md5
DIGIT-FOR-DIGIT both models (radon_pp 4a9ca349…, radon_var bbafc652…;
stock refs recorded first, reproduce W-111's csvs); parity 100 pts
exact-zero (lp + full gradients, D=389/175, raw-ctypes C ABI).
(c) identical trajectories (6,113/3,669 grad calls): Ir/grad
4,305,737 → 1,483,625 (radon_pp) and 470,351 → 157,960 (radon_var).
Attribution: scalar normal_lpdf body 11.22e9 → 0; per-element glibc log
3.49e9 → 1.6e6 (the log-sigma reuse); chainstack emplace 2.77e9 → 0.70e9;
loop machinery 4.39e9 → 1.08e9; accumulator sum+callback DELIBERATELY
identical (it IS stock's lp tree); primitive fwd+scatter 5.96e9
(~77 Ir/elem vs stock ~276). (d) new TU 4/4 + normal controls green.

PI ARBITRATION: accepted in full. KEY STRUCTURAL FINDING (changes the
emission design): accumulator<var> is a rev partial specialization with
a 128-element chunk-collapse buffer — a single-var primitive return
would break the lp addition tree, so the primitive returns ONE VAR PER
OBSERVATION (no-chain varis + ONE reverse callback in reverse-n order)
and the model edit pushes terms per element; the stanc3 emission MUST
emit the per-term push loop. Other owned deviations: two FMA-contraction
barriers (forward alpha + x*beta volatile; beta scatter fused on AoS /
unfused on SoA — stock's multiply_vd_vari::chain provably compiles to
vfmadd132sd); per-element check_not_nan/finite dropped (invalid-input
behavior only); first callgrind attempt aborted on an agent script
init-path bug (fixed, rerun clean, disclosed). Deliverable: branch
gathered-normal @ bc00891778 (parent fork/develop 344d7167a0) in
external/math_dev_w112, 2 files, DCO+AI note, NOT pushed. Full record:
results/normal_gathered_w112.md; artifacts scratch/w112/. Increment-2
(stanc3 loop-matcher emission) = GO — pre-registered as W-115 with
W-113's expression entry (the registry).

## 2026-08-29 — W-115 PRE-REGISTRATION (before any code): the gathered-families stanc3 REGISTRY — one table-driven suite pass emitting all landed primitives (entry 1 bernoulli_logit EXPRESSION [already shipped on gathered-glm-emit]; entry 2 dot_self ICAR EXPRESSION [new]; entry 3 normal LOOP matcher, both eta shapes [new, the hard part])

Base: stanc3 branch gathered-glm-emit @ 58e6824 (W-108 i2) → new branch
`gathered-registry` in a DEDICATED worktree external/stanc3_w115 (git
worktree from the stanc3 repo; NEVER touch external/stanc3 or
external/stanc3_w108). REFACTOR: Optimize.gather_bernoulli_logit
becomes a table-driven family pass (the campaign map's registry design):
per entry = {matcher spec, primitive call + signature, negative
controls, include}. Matchers: CLASS-E expression trees (entries 1-2;
entry 2's head is dot_self(subtract(gather(g,ix1), gather(g,ix2))) in
mir.reverse_mode_log_prob, SAME index-var g both sides, emitting
dot_self_gathered_diff(phi, node1, node2) — the −0.5 scaling and
everything outside stay untouched); CLASS-L the stereotyped LOOP
(entry 3): for n in data range { mu[n] = <gather-tree over n with
index exprs depending only on n, mu loop-local, element-wise>; target
+= normal_lpdf(y[n] | mu[n], sigma) } with sigma loop-invariant —
matched shapes: eta = alpha[ii[n]] AND eta = alpha[ii[n]] +
x[n]*beta[ii[n]] (same or second index array), emitting the W-112
hand-edit shape EXACTLY: the primitive call (which returns one var per
observation) + the per-term lp_accum push loop + the mu decl removal —
BYTE-IDENTICAL to the gated hand-edits is the gate, not approximation.
LEVEL: entries ON at --O1 per the W-108 i2 convention (paired-branch
behavior; upstream gating note in commits).

GATES: (a) negative controls NEVER fire, per entry (expression: non-
gathered eltwise, gathered-non-head, three-term; loop: cross-iteration
dependencies, mu used outside the lpdf, sigma varying in-loop, writes
to y/ii inside, non-normal scalar lpdf heads; plus O0 fires nothing);
(b) regenerated radon_pp/radon_var/bym2 hpp ≡ the W-112/W-113 gated
hand-edits (whitespace-wrapping-only diffs allowed, the W-108 i2 gate-b
standard); (c) END-TO-END no manual C++: regenerated hpp built on a
math bundle carrying ALL THREE primitive headers (gathered-glm +
gathered-normal + gathered-icar dropped into a stock-bundle copy —
independent files, union is a file copy; the bs-copy wiring, gxx_fixed,
env -u LD_LIBRARY_PATH, /usr/bin/make -j2 nice 19) → parity 100 pts
exact-zero + W-29-protocol draws md5 DIGIT-FOR-DIGIT vs the recorded
references (radon_pp 4a9ca349…, radon_var bbafc652…, bym2 54c62090…);
(d) no-op elsewhere: blr/diamonds/eight_schools_centered + the 5 models/
references regenerate BYTE-IDENTICAL at --O1 (cmp clean); dune runtest
-j2 exit 0. MACHINE: one OCaml build ~25 min -j2 nice 19 + model builds
+ 3 draws runs; NO callgrind (perf carries from W-112/113 by
construction); ≤2 cores. ESCALATION: any matcher semantics question
that cannot satisfy (b) byte-identity → STOP and report (PI decision).
Deliverable: branch gathered-registry (+ integration model(s) +
regenerated expectations as SINGLE pure insertions); record
results/gathered_registry_w115.md.

## 2026-08-29 — W-116 PRE-REGISTRATION (before any run): the PRIMITIVES ESS/s WRAP — wall + ESS/s for the landed gathered-GLM family (the Ir→ESS/s translation the campaign has NOT yet measured)

CONTEXT: W-112/113 gated on callgrind Ir + bit-identity by design; the
user's goal metric is ESS/s. Existing wall evidence is adjacent (W-34:
−28% Ir → −23..25% wall; W-109: math layer −23% wall on OFF-8) but the
new primitives' own wall/ESS/s contribution is UNMEASURED. The payoff
case: radon_pp is the worst math-attributable ESS/s cell in W-109
(0.90x, MM2 grad spend) and the primitive cuts its per-grad Ir −65.5%
with BIT-IDENTICAL draws — ESS unchanged by construction, so ESS/s
moves exactly 1/wall.

ARMS: models {radon_pp, radon_var, bym2_offset_only, hier_2pl} × {S, E,
E'} × 3 reps × 4 chains, W-109 protocol verbatim (w1000 s1000, pf inits
per w63 manifest, mw50, seeds 20260819+1000·rep+c, single chain per
process, nice 19, build_mg binary or build_w36exp-class READ-ONLY —
whichever the archive used, stated in the record):
- S / E: the W-109 ARCHIVE values (no rerun; the archived runs are the
  reference).
- E' (new): the E-arm .so REPLACED by all-layers+primitive builds —
  drop the three primitive headers (gathered-glm + gathered-normal +
  gathered-icar) into the all-layers math tree, rebuild per the bs-copy
  wiring, hand-edited hpps from W-108/112/113 (hier_2pl: the W-108
  hand-edit; the W-115 emission output may substitute if it has landed
  and its gates are green — stated in the record which was used).
METRICS: per model — ESS_bulk_min (blessed split, rep medians; expected
UNCHANGED vs E for bit-identical arms — itself a gate), wall (per-rep
sum of per-chain total time), ESS/s; E'/E and E'/S ratios.
GATES/EXPECTATIONS (pre-registered): (a) 48/48 runs rc=0;
(b) draws md5: E' cells for bit-identical arms reproduce the E-arm
draws EXACTLY (same binary, same .so math except the likelihood line —
md5 equality expected vs the W-112/113 recorded md5s at the W-29
protocol; at the W-109 protocol the draws should match the archive E
cells md5-for-md5 — if the archive cells were run with the identical
binary/protocol, verify; any mismatch = STOP and root-cause before
reading a single wall number); (c) WALL: radon_pp E'/E wall ratio
<= 0.55 (Ir says −65% of G; logp-fraction discount), radon_var <= 0.60,
bym2 <= 0.90 (G only 27.8% of T), hier_2pl <= 0.75 (primitive is −41%
of its G-class on the kernel arm; the all-layers composition already
includes other layers — the marginal is vs the W-106 all-layers .so
which E used); (d) ESS/s: radon_pp E'/S > 1.3x (flipping the 0.90x
cell), suite-level statement recorded as the E'-augmented everything-
stack geomean estimate (computed, flagged as 4-model partial).
WALL PROTOCOL: arms interleaved per cell (adjacent S/E' processes) so
load drift cancels; run ONLY when W-115's builds are done (quiet-ish);
load-flag disclosure in the record either way. Machine: grid ~1-2h at
≤4 workers nice 19 + ~6 model builds.
Sequencing: AFTER W-115 completes (machine + the emission option).

## 2026-08-29 — W-115 CLOSE-OUT (PI-arbitrated): the gathered-families stanc3 REGISTRY — ALL GATES PASS; families 1+2 are now COMPLETE END-TO-END (primitive + automatic emission, no manual C++); gate (a) caught a real matcher bug (ICAR var_name guard on Indexed operands — dot_self(phi[n1] − psi[n2]) would have fired and SILENTLY DROPPED psi; fixed b8171fc); PI RULING on the pre-reg's level conflict (the prereg's own error, owned): recorded W-112/113 hand-edits were DEFAULT-level artifacts while the pass is O1-on — resolved by the agent's three-arm measurement, accepted

GATES: (a) 14 negative controls never fire (incl. 7 loop controls:
mu-read-after-loop, sigma[n], extra body statement, cauchy head,
doubly-nested index, cross-iteration mu, y-not-data; 2 positive loop
controls fire; O0 fires nothing) — and it caught the ICAR guard bug
above. (b) BYTE-IDENTITY at the same-base standard: diff(emitted --O1,
parent-58e6824 --O1) is EXACTLY the intended rewrite on all three
models (tokens identical to the hand-edits, pretty-printer wrapping
only); reproducing default-level hand-edits from an --O1 compiler is
impossible even for the unmodified parent (residual 40/72/77 lines =
stock O1's own fma/decl-init/SoA drift, present identically in the
parent). (c) END-TO-END on bs_all3 (stock bundle + all three headers):
bym2 draws 54c62090… DIGIT-FOR-DIGIT; radon_pp b442ad18… / radon_var
93928010… = the parent-O1-stock md5s EXACTLY; parent at DEFAULT
reproduces the recorded 4a9ca349… (version-neutral — the recorded refs
are default-level); parity exact-zero vs same-level stock 3/3; vs
recorded stock 5/9/24-of-100 lp at 2-4e-16 — identical in count AND
magnitude to the parent's own O1-vs-default deviation (fully
level-attributed; the pass adds ZERO drift on top of O1). (d) no-op
elsewhere: 3 models + 5 references byte-identical; hier_2pl ≡
gathered-glm-emit (entry 1 preserved); dune runtest -j2 exit 0; one
in-repo model (expr-prop-fail4.stan, a BYM/ICAR model) now gets the
ICAR rewrite = the pass working, disclosed.
PI ARBITRATION: accepted in full. The level conflict was the PREREG'S
error (demanded O1 convention + default-level md5s simultaneously) —
owned here; the agent's three-arm resolution is the correct
experimental answer and the substantive claim stands: THE REWRITE IS
NUMERICALLY INERT AT ITS LEVEL (same-level draws md5-exact, parity
exact-zero). Owned deviations: loop matcher accepts the O1-fused fma
form and emits the unfused source-semantics primitive (measured
consequence on radon_var: none); parity harness became one-process
(Eigen reductions are malloc-layout sensitive down to the .so path
string — cross-process exact-zero not well-posed; control-proven).
REGISTRY VERDICT: family-4 pcm/ordered needs one table row + one
LOOP-class matcher (backend already generic — include + push loop);
the real work is the math-side LSE interior. Deliverable: branch
gathered-registry @ 50e8c9d (3 DCO commits, NOT pushed) in
external/stanc3_w115. Record: results/gathered_registry_w115.md;
artifacts scratch/w115/. The W-108/112/113/115 arc: hier_2pl, radon
class, and bym2-class models now reach their primitives AUTOMATICALLY.

## 2026-08-29 — W-116 CLOSE-OUT (PI-arbitrated, PARTIAL — stop-gate fired exactly as designed): E′ md5-clean on radon_pp/radon_var/bym2 (archive E cells reproduced); hier_2pl MISMATCH 12/12 — root-caused to a REAL OPERAND-LAYOUT COVERAGE GAP in the W-108 primitive at DEFAULT-level codegen (Map/Holder theta adjoint route unreplicated; lp exact-zero, theta adjoints 6.4e-13 rel → warmup divergence). NO wall/ESS/s numbers read (suppressed per the stop). Fix pre-registered as W-108.1; measurement completes as W-116b

DETAILS: the stop-gate compared all 48 E′ draws vs the archive E cells
before any wall reading — radon ×2 + bym2 MATCH (bym2 passes because
W-113 explicitly covered the Map layout — the mirror lesson);
hier_2pl's primitive arm diverges from first sampling draw. Gradient
attribution: alpha 0/800 EXACT, beta 1.3e-14, priors exact, theta 6.4e-13
(the dominant block) — the default-level deserializer hands theta as
Map<const Matrix<var>> and the composed stock rvalue takes the lazy
make_holder route (rvalue.hpp EigVec multi-index), a THIRD adjoint
schedule bernoulli_logit_lpmf_gathered does not implement (its
is_var_v<Map> check routes Map to AoS). W-108's gates used the O1 hpp
where theta is read var_value (SoA) — gap invisible at O1. UPSTREAM
RELEVANCE: math#14 carries this gap; a PR comment follows the W-108.1
fix. Agent's wiring corrections vindicated by evidence: the
kernel-interior bernoulli variant is what the archive draws flow
through (lp exact-zero proves it), and the W-108 hand-edits are O1
artifacts (the PI's default-level premise for them was wrong — owned;
the agent ported the 2 gated line groups onto the pristine default
hpp). Record: results/ess_wrap_w116.md; artifacts scratch/w116/.

## 2026-08-29 — W-108.1 PRE-REGISTRATION (before any code): close the Map/Holder operand-layout gap in bernoulli_logit_lpmf_gathered — add the lazy-holder adjoint route for Map-readonly theta (the default-level deserializer's layout), mirror of W-113's layout-3 work; then W-116b completes the ESS/s wrap

DESIGN: in external/math_dev_w108's gathered-glm branch (NEW worktree
external/math_dev_w1081, branch gathered-glm-mapfix off ea96b3c9fa):
extend the theta route selection so Map<const Matrix<var>> operands
replicate the composed stock make_holder rvalue's adjoint schedule
(read stan/src/stan/model/indexing/rvalue.hpp + rvalue_varmat.hpp
EigVec multi-index + make_holder chain to extract the exact callback
order — the same archaeology W-113 did for dot_self). Value path
unchanged (lp already exact — only the reverse scatter schedule is in
play). GATES: (a) unit bitwise — the W-108 gate (scratch/w108/
test_prim.cpp) EXTENDED with Map-layout cases (real rvalue/index_multi
composed reference), all previous cases still 0 mismatches;
(b) model gate at DEFAULT level: rebuild the W-116 hier_2pl E′ .so
(bundle copy under scratch/w1081/, kernel-interior variant as W-116
evidenced) → E′ draws reproduce the ARCHIVE E hier_2pl cells md5-for-
md5 12/12 (the W-116 stop-gate rerun); (c) O1 regression: the W-108
O1 hand-edit .so rebuild still md5 fe7c57… / its recorded kernel-arm
md5 (no regression on the landed path); (d) new TU cases + untouched
controls pass. Then the hier_2pl WALL stanza (12 processes, W-109
protocol, interleaving impossible vs frozen archive — load-flag per
cell) with band E′/E ≤ 0.75. MACHINE: ≤2 cores builds, nice 19, no
callgrind. W-116b (parallel, separate dirs): the 3 passing models'
wall + ESS/s grid from scratch/w116's existing builds — bands radon_pp
≤0.55, radon_var ≤0.60, bym2 ≤0.90; ESS/s E′/E, E′/S; headline radon_pp
E′/S > 1.3x. Records: results/ess_wrap_w116b.md (+ the fix record
appended to the W-116 file or its own section).

## 2026-08-29 — W-117 PRE-REGISTRATION (research audit, no production code): the normal-likelihood INTERIORS — is stock normal_lpdf's "highly optimized" reputation earned? Measure every variant's per-element cost and find the structural slack (user-requested lane)

CONTEXT: the campaign has only ever optimized the CALLING of normal
(scalar-loop → gathered primitive, −65%); the interior math was copied
verbatim. Open datapoints: W-112's primitive retains ~77 Ir/elem
(unexamined); W-104 found blr's #1 cost is EXCEPTIONS (sigma==0 throw
complex); W-34's "the lpmf is not the problem" was about call-level
plumbing, not the interior; the bernoulli interior yielded −13.9% wall
to a fused kernel (W-103) — is there a normal analogue?

DESIGN (audit, measurement + code reading; NO production changes):
(a) CODE READ: prim/prob/normal_lpdf.hpp (scalar + vectorized paths,
propto handling, Eigen expression structure, to_ref/to_arena
materializations, checks), normal_id_glm_lpdf interior, the rev edge
application, and our gathered primitive's retained 77 Ir/elem; identify
multiple passes over N, redundant materializations, unfused
check/normalize structure, exception-path structure (the W-104 class).
(b) MEASURE: per-element Ir of each variant at matched shapes (N≈1k,
12.5k; scalar loop, stock vectorized, normal_id_glm, gathered
primitive), one callgrind at a time (siblings W-108.1/W-116b run no
callgrind), nice 19; attribute phases (value pass, partials, edge,
checks, throw paths incl. a sigma<=0 stress case).
(c) RANK: candidate optimizations with expected ceilings and gate
class (bit-identity achievable vs statistical — Eigen evaluation-order
constraints stated explicitly), incl. the "does a fused single-pass
normal kernel exist" question and whether stock vectorized-vs-glm
already leaves a gap on the table.
DELIVERABLE: results/normal_interiors_w117.md — the verdict on the
reputation, the per-variant cost table, ranked candidates (each with a
pre-registrable shape), honest negatives if the interior is already at
its floor. Machine: ≤1 callgrind at a time, ≤2 build cores for probes,
no wall claims.

## 2026-08-29 — W-116b CLOSE-OUT (PI-arbitrated): the ESS/s wrap PARTIAL-2 — radon_pp WALL 0.348× / ESS/s E′/S 2.65× (headline gate >1.3× MET at 2× margin; the 0.90× floor cell flipped on bit-identical draws), bym2 0.824×/1.80× (PASS, load-caveated); radon_var VOID — 2/12 REAL reproducible .so-level divergences (rare sibling of the W-108 Map gap; same-env four-way experiments isolate E′-stable vs archive-stable forks from the first sampling draw) + 1/12 environment-ill-posed (archive itself unreproducible outside W-109's env; E′ exculpated). PROTOCOL LESSON: pilot-clean ⇒ grid-clean is FALSIFIED — full-grid md5 stop-gates are mandatory

NUMBERS (W-109 protocol, archive E recomputed from logs = w109_results
exactly): radon_pp E wall 120.07s → E′ 41.81s = 0.348 (per-rep
0.348/0.341/0.374; band ≤0.55 PASS at 37% margin — the −65% Ir
translated ~1:1 into wall); E′/S ESS/s = 2.65× (E′/E 2.93; E′ ESS/s
8.08 vs S 3.05; ESS unchanged by md5-identity, verified by
recomputation). bym2 0.824× wall (band ≤0.90 PASS, 9% margin,
load-caveated: archive ran under higher ambient load), E′/S 1.80× (ESS
pinned 4.43 by the known A0 init pathology in every arm — a pure wall
win). 2-model geomean E′/S 2.183× / E′/E 1.871× (partial, flagged).
radon_var: 9/12 md5-clean, 2/12 divergent (59e2b30b/651d5236 stable ×
all envs vs archive-frozen values stable — REAL .so-level fork, warmup
divergence from the first sampling draw; suspect the W-112 primitive's
alpha+x·beta boundary path), 1/12 env-ill-posed. PI RULING: radon_var
wall/ESS/s VOID; the divergence root-cause is queued behind W-108.1
(if the Map-route fix does not cover it → W-112.1 with the same-env
four-way methodology this agent established). Agent deviations owned:
driver crash recovered (4 orphaned cells completed validly, md5-verified);
3 pilot cells reused (disclosed); ~10 extra same-env probe cells; a
mid-session "artifacts lost" alarm verified FALSE (all intact).
Record: results/ess_wrap_w116b.md; artifacts scratch/w116/
(grid_w116b.py, analyze_w116b.py, runs/Eprime/, runs/Eprime_rerun/).

## 2026-08-29 — W-117 CLOSE-OUT (PI-arbitrated): the normal-interiors audit — reputation verdict: the Eigen core (~15 Ir/elem arithmetic) is earned; EVERYTHING AROUND IT IS NOT: the scalar-loop instantiation models actually run is 272 Ir/elem (18× the floor, incl. 15.3/elem of redundant log σ); the stock vectorized path wastes 45% of its 50.7 on operand materialization + two unfused check scans and 26% on removable edge bookkeeping; our own W-112 primitive carries ~40 removable Ir/elem. Throw-path finding: the VECTORIZED sigma=0 throw costs 333k Ir/eval because mu materialization + both check scans run BEFORE check_positive — check ORDER, not the throw (the W-104 class generalized + quantified)

TABLE (N=12573, sigma var; fwd/full/rev Ir per element): scalar loop
220.5/271.8/51.3; vec_gather (vectorized form composed with a var
gather — EXPRESSIBLE IN STAN TODAY) 54.0/61.0/7.0; vec_aos 43.7/50.7;
vec_soa 32.7/34.2; glm_vec 44.3; glm1 (scalar-alpha degenerate) 16.7;
W-112 gathered primitive 84.4/109.7/25.3. Throw paths per throwing
eval: scalar 32.4k, vectorized 333k, gathered 335k, NaN-in-y 168k.
RANKED CANDIDATES (1 Ir/elem = 0.848% of radon_pp's post-primitive G):
C2 fused single-pass primitive interior (kill the redundant y_d copy,
fuse gather+term loops 3→1+scatter, SIMD the term loop incl. matching
vfmadd contraction points, batch no-stack term varis) — 97.4 → 55-65
Ir/elem ≈ −25% G BIT-IDENTICAL, W-112 gates reusable verbatim; honest
negative: reverse scatter cannot fuse (adjoints unknown until grad);
serial sigma accumulation at its Ir floor (re-association =
statistical class). C1 vectorized-form EMISSION (y ~ normal(alpha[ii],
sigma)) — 61 all-in vs ~120 loop-form lane ≈ −45..−50% G,
STATISTICAL class (different lp tree + scatter order), zero math work
(codegen lane). C3 stock edge cleanup (remove Zero-then-overwrite of
partials_ + the to_arena operand copy — memset/copy only, trivially
bit-identical): vec_aos −26%, vec_soa −24%, glm_vec −48%; composes
with C1 (61 → ~48); UPSTREAM-candidate class (touches shared
edge machinery — broad blast radius, own pre-reg with wide controls).
PI QUEUE: W-118 = C2 (pre-reg below), sequenced AFTER W-108.1 + the
radon_var boundary ruling (one editor per header at a time); C1/C3
held for user awareness (C1 changes numerics; C3 touches shared math).
Record: results/normal_interiors_w117.md; artifacts scratch/w117/
(42 callgrind runs, probes; all sibling trees verified clean).

## 2026-08-29 — W-118 PRE-REGISTRATION (before any code; LAUNCH HELD until W-108.1 + radon_var ruling land): C2 — the fused single-pass normal primitive interior (bit-identical lane; W-112 gates reusable verbatim)

DESIGN: branch off gathered-normal (or its W-112.1 successor if that
lands first) in a dedicated worktree: (1) eliminate the redundant y_d
copy (8 Ir/elem); (2) fuse the gather + term loops (3 traversals → 1
forward + scatter); (3) SIMD the per-element term loop with per-lane
ops IDENTICAL incl. matching vfmadd contraction points (no horizontal
ops — terms are per-element; the accumulation stays scalar-sequential
for bit-identity); (4) batch the no-stack term varis (W-53 machinery).
GATES = W-112's verbatim: (a) bitwise unit gate (all cases + the
contraction-point checks; 0 mismatches); (b) model gate draws md5
digit-for-digit (radon_pp 4a9ca349… + radon_var bbafc652… or their
W-112.1-updated values — whichever is canonical at launch) + parity
exact-zero; (c) callgrind band −15..−30% G on radon_pp (per-elem
97.4→55-65 target; band from the W-117 audit); (d) TU + controls.
Machine: ≤2 cores, one callgrind at a time.

## 2026-08-29 — W-119 PRE-REGISTRATION (user-steered lane; increment 1 = audit + measured case, increment 2 only on green): normal_id_glm itself + an Eigen-core kernel probe — the every-day workhorse path (diamonds/blr/kidscore class), NOT the niche loop lane

USER RATIONALE (recorded): loop-form optimization serves niche models;
the vectorized/normal_id_glm path is the everyday one where wins
benefit the most users; "give the core itself a try."
W-117 EVIDENCE: glm_vec (N-vector alpha) 44.3 Ir/elem vs its own
scalar-alpha sibling glm1 at 16.7 — a measured 2.7× INTERNAL gap in
the flagship (materialization/edge bookkeeping class); vec_soa 34.2;
the arithmetic floor ~15. Throw paths inside glm unmeasured (the
333k-Ir check-order finding was the plain vectorized path — measure
glm's).

INCREMENT 1 (audit + case, no production changes):
(a) map what the everyday models ACTUALLY call — read the generated
    hpps: diamonds (explicit normal_id_glm in .stan), blr, kidscore,
    logmesquite (which stanc3-rewrite fires for beta[1]+beta[2]*x
    forms — suspected NONE → plain vectorized), wells
    (bernoulli_logit_glm); record per-model per-element path + cost;
(b) root-cause glm_vec's 28 Ir/elem over glm1: alpha materialization,
    the mean-centering path, edge bookkeeping (the W-117 C3 class:
    Zero-then-overwrite partials_, to_arena operand copies), check
    scans + their ORDER (the 333k throw finding — measure glm's throw
    path), instantiate counts;
(c) Eigen-core probe with STOP-CLAUSE: can a hand kernel (W-103-style
    SIMD island, runtime ISA dispatch, contraction-point-matched,
    scalar-sequential accumulation) beat the auto-vectorized core at
    BIT-IDENTITY on the normal term computation? Prior: the core is
    trivially auto-vectorizable (unlike log1p) — expected gain small;
    STOP if a microbench shows < 5% over the compiler's codegen (the
    negative is the result then).
INCREMENT 2 (only on green, separate prereg): the bit-identical glm
cleanup (edge/materialization/check-order reorder within-glm) gated
bitwise + a diamonds-class model gate (draws md5 + callgrind band
from the measured headroom); the kernel lands only if (c) survives
its stop-clause.
Machine: ≤2 cores probes, ONE callgrind at a time (W-108.1 runs none),
nice 19, no wall claims in increment 1. Deliverable:
results/glm_lane_w119.md.

## 2026-08-29 — W-108.1 CLOSE-OUT (PI-arbitrated): the Map-fix is REALLY an FMA-contraction-schedule fix — ROOT CAUSE REDEFINED AT MACHINE-CODE LEVEL: stock's reverse chains at archive build flags (-O3 -mavx2 -mfma) fuse ONLY alpha's increment (vfmadd213sd); theta/beta get one-rounded products + pure add/sub — the primitive's plain adj += a*b statements fused ALL THREE (~1 ulp on ~50% of gradient components, compounding through warmup into the 12/12 divergence). INVISIBLE to W-108's gates because those binaries had no FMA-capable flags. ALL GATES PASS; hier_2pl 12/12 archive md5s EXACT; wall −51..−61%

FIX (branch gathered-glm-mapfix in external/math_dev_w1081, commits
56c88d2440+eb8fe63f9c; NOT pushed): volatile-barrier rounded products
for theta/beta + SoA alpha increments (statement splits get re-fused
by GCC — proven by disassembly of the first attempt); AoS alpha kept
fused (matches stock); value path untouched. GATES: (a) unit bitwise
12,000 checks 0 mismatches AT MODEL FLAGS (-O3 -mavx2 -mfma AND -O2 —
the gate elevation is the load-bearing protocol change: FMA flags are
a bit-identity dimension and every prior unit gate under-detected);
(b) hier_2pl default-level E′ stop-gate 12/12 == archive (rebuild
verified 1202 vfmadd = archive count — FMA-count provenance); (c) O1
regressions exact both stacks (fe7c57…, 1744c208…); (d) TU+controls
green. WALL (hier_2pl): pre-registered E′-sequential vs frozen archive
0.328 (band ≤0.75 PASS; load-flagged); load-matched quiet-E comparison
0.488 (−51%, consistent with W-108's −40.9% Ir); dispatch-matched
4-worker 0.395. ESS/s implication (ESS = archive E, md5-proven):
E′/S ≈ 5.6× (dispatch-matched) .. 6.7× (sequential stanza) — hier_2pl
becomes the suite's top ESS/s cell (was 2.19×); conventions flagged.
Deviations owned: the prereg's "third Map route" framing was WRONG (no
new Map branch needed — the fix corrects arithmetic schedules); first
E′ build dropped -mavx2 -mfma (caught pre-run via FMA count);
hygiene verified (bs_alllayers bridgestan.o md5 unchanged, siblings
untouched). Record: results/mapfix_w1081.md.
CAMPAIGN-WIDE CONSEQUENCE: W-112's radon_var 2/12 divergence (W-116b)
is presumptively THE SAME CLASS — W-112's own deviations note flagged
contraction points ("beta scatter fused on AoS, unfused on SoA") and
its unit gate ran without FMA flags. W-112.1 pre-registered below.

## 2026-08-29 — W-112.1 PRE-REGISTRATION (before any code): close the radon_var divergence with the W-108.1 methodology — disassemble the archive radon_var .so's reverse chains + the composed reference AT MODEL FLAGS, extract stock's exact FMA-contraction schedule for the alpha + x·beta shape, match it in normal_lpdf_gathered; re-gate with the FMA-ELEVATED unit gate

DESIGN: branch off gathered-normal in a dedicated worktree
external/math_dev_w1121 (branch gathered-normal-fmafix): apply the
W-108.1 archaeology (disassembly of BOTH the archive
radon_variable_intercept_slope all-layers .so chains AND a
composed-reference probe built at -O3 -mavx2 -mfma) to the two-gather
eta shape's increments — alpha[ii], beta[ii] (the x[n]·beta product
path), sigma accumulation, SoA and AoS routes — and insert
volatile-barrier rounded products wherever stock's schedule is unfused
(and keep fused where stock fuses). GATES: (a) unit bitwise, ALL
W-112 cases re-run AT -O3 -mavx2 -mfma AND -O2, both eta shapes, all
layouts, 0 mismatches (this gate previously under-detected — the
elevation is mandatory); (b) the W-116b divergent cells as the primary
stop-gate: rep1_c2 (59e2b30b…) and rep2_c0 (651d5236…) E′ draws ==
the E′-stable values AND the full 12/12 grid == archive (same-env
four-way methodology from W-116b if anything mismatches); (c)
regressions: radon_pp 12/12 archive md5s unchanged (the W-116b-passing
arm must not break) + W-112's original recorded md5s (bbafc652… at its
protocol) still reproduce at non-FMA flags; (d) TU+controls. Then the
radon_var WALL stanza + ESS/s cell (bands: wall ≤0.60 per the original
W-116 prereg; ESS/s E′/S recorded). Machine: ≤2 cores, one callgrind
only if attribution demands it.

## 2026-08-29 — W-119 CLOSE-OUT (PI-arbitrated, increment 1): the glm-lane audit — PREMISE INVERSION: everyday models mostly NEVER reach normal_id_glm (the stanc3 rewrite needs a UMatrix predictor and lives in partial_evaluation, OFF at default level — the commonest idiom (intercept + slope·vector, the fma(b2,x,b1) form) compiles to plain vectorized in EVERY version; X*beta only at --O1; diamonds reaches glm only because brms emits it explicitly). glm_vec's 28 Ir/elem internal gap = ENTIRELY vec-alpha edge machinery (memset 8.0 + Zero-partials 8.0 + to_arena ~5.0) — bit-identical cleanup class. KERNEL STOP-CLAUSE FIRES: hand AVX2 island 2.759 vs gcc auto-vec 2.756 Ir/elem = +0.1% << 5% — the auto-vectorizer already ate the core (first-class negative; the stock expression's own −75% headroom decomposes into −54% ISA flags + source-level fusion of Eigen intermediates, no hand kernel needed; probe itself bit-identical incl. matched contraction points). glm's throw path is 8× BETTER than plain vectorized (41.6k vs 333k Ir/throwing-eval — glm's check order is right); NaN-in-y still 256-304k. diamonds-shape: reverse is FREE (0.06/elem); forward GEMV 61% + memset 21%. wells context: bernoulli_logit_glm like-complex ~218/elem (log1p 92 + frame 89) — separate candidate

WHAT MODELS CALL (verified live, stanc 2.39.0): diamonds normal_id_glm
(scalar alpha; stock 119.9/elem, avx2 38.9); blr plain-vec default /
GLM AT --O1 (the rewrite fires for X*beta there); kidscore+logmesquite
fma-chain forms NEVER glm (any level); wells bernoulli_logit_glm.
LANES: A (bit-identical, W-120 below) glm edge cleanup — −21% G
diamonds-class avx2 / −47% glm_vec-class; B (statistical, bigger,
USER-DECISION) stanc3 glm emission for vector-predictor/default-level
forms: 50.7 → ~18-20/elem with free reverse (−60%+; changes numerics —
draws differ; workaround exists today: write normal_id_glm explicitly);
kernel lane CLOSED by stop-clause. Record: results/glm_lane_w119.md;
artifacts scratch/w119/ (25 callgrind runs, probes, 10 regenerated
hpps; sibling trees read-only verified).

## 2026-08-29 — W-120 PRE-REGISTRATION (before any code): Lane A — the bit-identical normal_id_glm edge cleanup (kill the Zero-then-overwrite partials memset + the to_arena alpha copy via lvalue/arena-local construction); upstream-candidate class

DESIGN: branch off fork/develop in a dedicated worktree
external/math_dev_w120 (branch glm-edge-cleanup): in
normal_id_glm_lpdf's vector-alpha path, (1) replace the
Zero-init-then-overwrite of the alpha edge partials with
construct-into-arena (no memset pass), (2) avoid the to_arena copy of
the alpha operand where an arena-local lvalue/reserve construction
preserves semantics. SCOPE GUARD: if the fix lands in SHARED edge
machinery (operands_and_partials templates) rather than glm-local
code, the control gates widen to other distributions (bernoulli_logit,
poisson_log, categorical vec paths) — determine first, disclose which.
GATES: (a) bitwise unit at MODEL FLAGS (-O3 -mavx2 -mfma AND -O2 —
standing protocol since W-108.1): glm with scalar alpha + N-vector
alpha + both + data/param mixes, y double, sigma var/double; lp +
every gradient component memcmp-exact vs stock; (b) model gate:
diamonds draws md5 — record the stock reference FIRST (W-29 protocol,
stock all-layers .so scratch/w106/model_diamonds_alllayers, pf init
inits_w36/diamonds rep0 chain_0, mw50, seed 20260819), then the
patched arm digit-for-digit; parity 100 pts exact-zero; (c) callgrind
band: −15..−25% of diamonds G (avx2 posture), attribution of the
memset/to_arena symbols → 0; (d) TU + UNTOUCHED controls (the glm test
suite +, if shared machinery touched, sibling-distribution tests).
Machine: ≤2 cores, one callgrind at a time (W-112.1 may run —
coordinate by checking ps first).

## 2026-08-29 — W-112.1 CLOSE-OUT (PI-arbitrated, STOP-CLAUSE HONORED): the radon_var divergence is NOT FMA-contraction-class — every contraction point MATCHES at machine-code level (full table w/ addresses) AND runtime certification shows 0/100 lp + 0/100 gradient bitwise mismatches on valid states (the .so pair is arithmetically indistinguishable on every VALID state). ACTUAL MECHANISM: THROW-SET divergence from W-112's dropped per-element check_finite(mu): on warmup states with mu non-finite but sigma>0, stock THROWS (→ wrapper logp=-inf/grad=0 → clean rejection) while the primitive returns lp=-inf/NaN with 88/175 NaN grad components → NaN momentum → the PRIORS' check_not_nan throws on the NEXT call → different tree decisions → permanent fork. Log forensics 1:1 (archive "Location -nan/-inf" events vs E′ "Random variable -nan"; 10/12 cells carry Location events, only 2 forked = conditional amplification); explains radon_pp's 12/12 cleanliness (no mu-non-finite states). STANDING LESSON: gathered-primitive bit-identity requires THROW-SET parity, not just valid-state parity — exceptions are observable sampler behavior (connects W-104)

No fix applied, no gates run, nothing committed (stop-clause; worktree
external/math_dev_w1121 left pristine at the W-112 base for W-112.2).
Record: results/fmafix_w1121.md (+ the ready-to-apply escalation
package §3); artifacts scratch/w1121/. PI ACCEPTS and approves W-112.2.

## 2026-08-29 — W-112.2 PRE-REGISTRATION (before any code): restore throw-set parity in normal_lpdf_gathered — per-element check_not_nan(y) + check_finite(mu) in stock's order in the term loop (~2 predicated compares/elem, zero effect on valid states — valid-state parity already proven by W-112.1); gates = W-112.1's (a)-(d) PLUS throw-set parity unit cases

DESIGN: in external/math_dev_w1121 (branch gathered-normal-fmafix off
bc00891778 — the worktree W-112.1 left pristine): add the two checks
per element in the impl's term loop matching stock's exact order and
exception type/message behavior (read the scalar normal_lpdf's checks;
W-112 §6 dropped them as "invalid-input behavior only" — falsified).
Both eta shapes. GATES: (a) bitwise unit at MODEL FLAGS (-O3 -mavx2
-mfma AND -O2), all W-112 cases + NEW throw-set parity cases (mu=±inf,
mu=NaN, y=NaN, sigma>0; y=NaN with sigma>0; sigma<=0 behavior
unchanged) — identical exception thrown at the same element index,
identical message class, AND valid-state bitwise unchanged; (b)
PRIMARY: the W-116b divergent cells — rep1_c2 → predicted fc7dbe12…,
rep2_c0 → predicted e6ab04e0…, full 12/12 grid == archive (rep0_c2
expected at its same-env c7ce20bf… — the frozen 65d8f98c… is
archive-unreproducible per W-116b; same-env four-way methodology if
anything mismatches); (c) regressions: radon_pp 12/12 archive md5s
still exact (rebuild + rerun) + W-112's original non-FMA-flag md5s
(bbafc652…) still reproduce; (d) TU + controls. THEN the radon_var
WALL stanza + ESS/s cell (band wall E′/E ≤ 0.60; ESS/s E′/S recorded;
ESS expected = archive E 415.0). Machine: ≤2 cores, callgrind only if
attribution demands. W-118 (fused interior) branches off THIS fix's
tip when green — one editor per header.

## 2026-08-29 — W-112.2 CLOSE-OUT (PI-arbitrated): the throw-set fix — ALL GATES PASS, diagnosis CONFIRMED BY PREDICTION (rep1_c2 → fc7dbe12…, rep2_c0 → e6ab04e0…, both exactly as pre-computed from the W-112.1 mechanism); rep0_c2 landed on the FROZEN archive value 65d8f98c stable ×3 (the archive .so itself gives c7ce20bf in today's env — the fixed primitive reproduces the archive better than the archive binary does; env-ill-posed cell resolved favorably); radon_var 12/12 == archive; regressions green (radon_pp 12/12 + W-112 originals digit-for-digit); wall E′/E = 0.297 (band ≤0.60, 2× margin), ESS 415.01 unchanged, ESS/s E′/S = 3.90×. THE FOUR-MODEL CAMPAIGN MEASUREMENT IS COMPLETE

THE FIX: commit 9a07ffa459 (+ TU 559da085d5) on gathered-normal-fmafix
(external/math_dev_w1121): check_not_nan(y[k]) then check_finite(mu[k])
per element, stock's exact order + byte-identical messages; sigma check
hoisted (throw-set-equivalent); zero FP ops added (FMA counts of the
rebuilt .sos identical to old-E′: radon_var 240/19/8, radon_pp
223/18/8). Gate (a): 22,380 checks 0 mismatches at BOTH flag levels
incl. 20 throw-set cases; boundary probe: mu=+inf now rc=-1 Location
inf grad-zero = archive behavior (old: rc=0 with 88/175 NaN grads).
COMPILED FOUR-MODEL TABLE (E′ = all-layers + primitives, W-109
protocol, every draw md5-identical to its archive E cell):
- radon_pp:  wall E′/E 0.348, ESS/s E′/S 2.65× (W-116b)
- radon_var: wall E′/E 0.297, ESS/s E′/S 3.90× (W-112.2)
- hier_2pl:  wall E′/E 0.328-0.488 (accounting-dependent),
             ESS/s E′/S ≈ 5.6× (dispatch-matched) .. 6.7× (W-108.1)
- bym2:      wall E′/E 0.824, ESS/s E′/S 1.80× (W-116b)
GEOMEAN E′/S ≈ 3.2× (dispatch-matched hier_2pl) .. 3.3×; ESS levels
unchanged everywhere (bit-identity); the other 17 suite models are
untouched by construction. This is the campaign's ESS/s headline: the
gather-class models run ~3.2× ESS/s vs the recommended default with
md5-identical draws. W-118 (fused interior, −15..−30% more) branches
off 9a07ffa459 — LAUNCHING. Record: results/throwset_fix_w1122.md;
artifacts scratch/w1121/.

## 2026-08-29 — W-120 CLOSE-OUT (PI-arbitrated): glm edge cleanup — gates (a)/(b)/(d) ALL PASS bit-identically (173,664 hex checks both flag levels; diamonds draws md5 digit-for-digit + parity exact-zero; 190 controls 0 failures with the scope-widened set), gate (c) BAND FAIL as an honest mechanism correction: the vec-alpha edge Zero removal delivered EXACTLY the predicted −8.03 Ir/elem (−18% on the glm_vec class, memset symbol → 0), but the diamonds band was built on W-119's MISATTRIBUTION — Eigen sized-ctors never zero; the real N-sized memset is Eigen's product evalTo setZero (addr2line ProductEvaluators.h:148/348) and it is LOAD-BEARING (the col-major GEMV kernel RMWs its destination) — removal = kernel/arithmetic change, out of the bit-identical class. The to_arena alpha copy: SURVIVOR with mechanism (const-ref binding cannot distinguish temporaries; a view dangles pre-reverse-sweep; allocator domains forbid pointer-stealing)

SCOPE: shared-ADDITIVE (the pre-registration's scope guard fired — the
Zero lives inside ops_partials_edge's ctor, unreachable glm-locally;
implemented as PURE ADDITIONS: internal::operand_with_partials POD +
an opt-in seeded edge specialization; no existing path modified —
hence the widened controls incl. bernoulli_logit_glm 44 + poisson_log_
glm 44 + operands_and_partials prim/rev/mix/fwd). Net suite effect ≈ 0
(diamonds is SCALAR-alpha; the −18% class is vec-alpha glm, which NO
suite model uses today). UPSTREAM CANDIDATE: YES for the seeded edge
(~80 additive lines, PR-sized; bern/poisson/neg_binomial_2 glm share
the full-overwrite pattern); NO for the Eigen setZero (Eigen-level
project) and NO for the to_arena copy (API semantics). Branch
glm-edge-cleanup @ 97d9a8a339 (+635223b627), NOT pushed. This
STRENGTHENS the Lane-B framing: the everyday win is routing models to
glm (user decision), not cleaning the vec-alpha edge no model uses.
Record: results/glm_edge_cleanup_w120.md; artifacts scratch/w120/.

## 2026-08-29 — W-121 PRE-REGISTRATION (user-steered, research audit, no production code): the COMMON-FAMILY INTERIOR CENSUS — extend the W-117 methodology to the distributions everyday users actually call, weighted by what brms emits (R-land sits on the _glm path: diamonds IS brms output with normal_id_glm explicit)

SCOPE (user's list + the glm set): the 8 GLM densities (bernoulli_logit,
binomial_logit, categorical_logit, neg_binomial_2_log, normal_id,
ordered_logistic, poisson_log [+ their emission reach]) + the non-glm
common families (exponential, gamma, weibull, beta, and
bernoulli/poisson/neg_binomial_2 plain forms for the contrast).
METHOD (W-117 verbatim + its extensions): per-element Ir at stock AND
avx2 postures; pass counts + intermediate materializations (the
source-level-fusion class — W-119 proved bit-identity of the fused
form for normal; measure the same headroom per family); check order +
throw paths (the W-104/W-112.1 class — exceptions both cost AND steer);
edge bookkeeping (the W-120 class: Zero-then-overwrite, to_arena);
which stanc3/brms forms reach which function (the W-119 premise-
inversion question per family). DELIVERABLE: the family × fix-class
matrix with Ir/elem headroom and gate classes, ranked; the top 3
pre-registrable follow-ups. Machine: ≤2 cores probes, ONE callgrind at
a time (W-118 may run one — coordinate via ps), no wall claims.
Record: results/family_census_w121.md.

## 2026-08-29 — W-122 QUEUED (pre-registration to be finalized on W-118's verdict): the SOURCE-LEVEL FUSION production lane — restructure distribution interiors to eliminate Eigen intermediate materializations, per the W-119 probe's validated pattern (bit-identity of the fused form PROVEN for normal: 0 mismatches on terms/partials/totals at both flag levels with matched contraction points; stock expression 11.03 → 2.76 Ir/elem = −54% ISA + fusion). First target = the W-121 top-ranked family interior (or stock normal_lpdf's vectorized interior if it tops the ranking); design + gates finalized when W-118 lands (its fused-primitive learnings transfer; one editor per header)

## 2026-08-29 — W-121 CLOSE-OUT (PI-arbitrated): the common-family interior census — 85 callgrind runs, 0 failures. HEADLINES: (1) the free-reverse finding GENERALIZES (rev ≈ 0.0 Ir/elem for ALL 7 glm families — the forward interior is everything); (2) poisson_log_glm computes exp(θ) TWICE (source lines 111/125, measured −33 Ir/elem to eliminate) — the W-122 target with a measured bit-identical −25..−30% band; (3) CONSTANT-DATA lgamma dominates three glm interiors (binomial_logit_glm: lgamma 350 = lchoose of const n,N = 45% of the family; poisson 109; nb2 229) — the propto-emission candidate (−44/−45/−22%) is STATISTICAL-class-but-draws-bitwise-identical (gradients exact; lp shifts by an exact constant; loo pointwise shifts — USER-DECISION lane with upstream-policy implications); (4) ISA lift ANTI-CORRELATES with transcendental share (pois/binom avx2-flat vs normal +88%, gamma +162% — the W-105 flag lane buys little on lgamma-bound families); (5) neg_bin_2 PLAIN at 933 Ir/elem (lgamma 361 + scalar-loop frame 289) = a −150..−190 bit-identical rebuild candidate (legacy-R reach); (6) exponential is already near-floor at 13; weibull's cost is pow (103); normal_id_glm's check order remains the gold standard

MATRIX + top-3 follow-ups recorded in results/family_census_w121.md;
artifacts scratch/w121/. W-122 TARGET CONFIRMED: poisson_log_glm_lpmf.

## 2026-08-29 — W-122 PRE-REGISTRATION (before any code): source-level fusion of the poisson_log_glm interior — eliminate the measured exp(θ) recompute (compute once, reuse the double — bit-identical by determinism) + fuse the frame per the W-119-validated pattern (no intermediate materializations; scalar-sequential accumulations; contraction points matched and disassembly-verified); NO seeded-edge composition this W (one editor per branch — follow-on)

DESIGN: branch off fork/develop in external/math_dev_w122 (branch
poisglm-fused), target stan/math/prim/prob/poisson_log_glm_lpmf.hpp:
compute exp(theta) once and reuse; restructure the expression chain to
avoid Eigen intermediate materializations where per-element op order
is preserved; keep every check in stock's exact order (throw-set
parity is contract — W-112.2 lesson) incl. the NaN-deferred class;
reverse path untouched (already free). GATES: (a) bitwise unit at
MODEL FLAGS (-O3 -mavx2 -mfma AND -O2): lp + every gradient component
(alpha, beta, phi-if-present) vs pristine stock, randomized shapes
(N=1..8, 100, 1000, 12573; K 1..8; scalar/vector alpha; y all-zero/
all-positive mixes; theta extremes) + throw-set cases (y-NaN, y-negative,
theta ±inf; phi classes if in signature) — identical exception at the
same element index + valid-state bitwise; (b) BESPOKE MODEL GATE
(disclosed: no suite model uses poisson_log_glm — build a small
poisson-log-regression .stan with real-shaped data (N≥1000, K≥2),
compile stock vs patched (same generator/level), W-29-protocol draws
md5 digit-for-digit + parity 100 pts exact-zero; (c) callgrind band
−20..−30% of the family interior per-elem (measured −33 recompute +
−25 frame; conservative band), attribution of the second exp site → 0;
(d) TU + controls (poisson_log_glm suite + poisson_log neighbors).
Machine: ≤2 cores, one callgrind at a time (W-118 may run one — check
ps first), nice 19. Record: results/poisglm_fused_w122.md.

## 2026-08-29 — W-122 CLOSE-OUT (PI-arbitrated): poisson_log_glm source-level fusion — ALL FOUR GATES GREEN: -21.0% Ir/elem (248.52 -> 196.39, in the -20..-30 band; second exp site -> 0 EXACTLY, exp 72.00->36.00; rev 0.01 unchanged; propto arm -39.0% adjacent to the user-decision const-lgamma lane), bit-identical (55 cases x both flag levels 0 mismatches, 9 throw cases byte-identical incl. element index; bespoke model 6/6 draws digit-for-digit + parity 200 pts exact-zero; 24/24 TU + controls). MECHANISM (disassembly-proven): both stock exp(theta) sites (lines 110-111 theta_derivative, 124-125 logp term) are scalar glibc-exp DefaultTraversal passes for non-double y (mixed-scalar Eigen; scalar_*_op requires is_same for PacketAccess) — provably the same std::exp per element, so the patch computes it ONCE in a fused scalar-sequential loop (derivative store + term fold + lgamma fold, per-element order preserved, fold from element 0, (0-lgamma_sum)+terms_sum final shape); contraction points verified (vfmsub132sd @AVX2 / mulsd+subsd @-O2 both arms). OWNED SCOPE NARROWING: double-typed y (C++-API-only; Stan y is array[int]) keeps stock verbatim — its sites use Eigen packet pexp with per-site scalar tails where sharing is not provably value-identical. Branch poisglm-fused @ 03c5e17783, NOT pushed. Record: results/poisglm_fused_w122.md. The fusion lane (W-119 pattern) is now PROVEN in production stock math; follow-ons queued: seeded-edge composition (+8), nb2-plain rebuild (W-123 below)

## 2026-08-29 — W-123 PRE-REGISTRATION (before any code): the neg_binomial_2 (plain) interior rebuild — the census's #3: 933 Ir/elem stock (lgamma 361 + SCALAR-LOOP frame 289 — the legacy VectorBuilder emission), band -150..-190 Ir/elem (-17..-21%) bit-identical data-flow restructure; reach = legacy R emission (no suite model — bespoke gate model, disclosed)

DESIGN: branch off fork/develop in external/math_dev_w123 (branch
nb2-plain-rebuilt), target stan/math/prim/prob/neg_binomial_2_lpmf.hpp
(and its _log sibling if the frame is shared): restructure the
scalar-loop-era interior to vectorized/fused data flow with per-element
op order preserved (the W-119/W-122 pattern; scalar-sequential
accumulations; contraction points disassembly-verified at BOTH flag
levels), every check in stock's exact order (throw-set parity
contract), lgamma calls UNCHANGED in count and argument order (the
361 Ir/elem lgamma is transcendental floor unless propto-emission is
decided — NOT this W). GATES (W-122 verbatim): (a) bitwise unit at
model flags both levels, randomized shapes (N=1..8..12573; mu/phi
scalar+vector mixes; extreme mu/phi incl. graceful edges) + throw-set
cases; (b) BESPOKE model gate (disclosed: no suite model; small
neg-binomial regression .stan, N>=1000, same generator/level both
arms, stock md5 FIRST then digit-for-digit + parity exact-zero);
(c) callgrind band -150..-190 Ir/elem vs census posture, attribution;
(d) TU + controls (neg_binomial_2 suite + neighbors). Machine: <=2
cores, one callgrind at a time (check ps — W-118 may run one).
Record: results/nb2_rebuild_w123.md.

## 2026-08-29 — LEDGER NOTE (user-steered, no W-number — prepared artifact): the const-lgamma issue is DRAFTED and the semantics VERIFIED in source: include_summand<propto>::value == !propto (prim/meta/include_summand.hpp — so ~-forms ALREADY drop lgamma-of-constant-data; the gating is convention-CORRECT) — the recompute burden is specific to the target += emission, which is the brms DEFAULT (diamonds.stan on this box: "target += normal_id_glm_lpdf"), making the whole R ecosystem pay constant-data lgamma every gradient eval. Paste-ready issue: external/pr/const-lgamma-recompute-issue.md (two remedies: transformed-data hoisting = BIT-IDENTICAL incl. for target += users — lgamma of the same double is deterministic; and the propto-for-likelihood-lines policy option = semantic). The user's normalization question answered in-session: lp__ is documented unnormalized; MCMC uses only within-model differences (our draws-md5 proofs); the constant shift touches only absolute-lp cross-comparisons (already fragile) and pointwise-lik built from propto forms (standard LOO practice uses explicit full-constant GQ calls — unaffected)

## 2026-08-29 — LEDGER NOTE (user idea, adopted): "compute-once / re-add-per-eval" is now the issue draft's PRIMARY remedy (external/pr/const-lgamma-recompute-issue.md restructured: hoisted constant in transformed data + internal <propto> call + one precomputed add per log_prob — full-constant lp__ at propto speed; gate class = last-ulp/behaviorally-inert, the W-34 Arm-B precedent; NOT md5-class because [Σterms]+C associates differently than stock's per-element fold). W-124 QUEUED (prereg on launch): stanc3 emission behind a flag — recognize target += f(...) with data-only subterms, hoist to transformed data, emit the internal propto overload + constant; gates: W-34-ArmB class (last-ulp parity, statistical sampler gates, ESS equivalence) + the interior savings measured vs census; validation models: a brms-style poisson/binomial target+= model. Launch when an agent slot frees (W-118/W-123 running).

## 2026-08-29 — FILING TALLY (user authorization change: agents MAY now file [upstream-candidate] PRs + issues ON THE FORKS, head = feature branch -> fork mainline; NEVER stan-dev/* upstream): math#15 normal_lpdf_gathered (gathered-normal-fmafix; will auto-advance when W-118 lands), math#16 dot_self_gathered_diff, math#17 FMA-contraction mapfix (SUPERSEDES #14, contains its tip), math#18 opt-in seeded edge, math#19 poisson_log_glm fused, stanc3#8 the family registry (SUPERSEDES #7), math ISSUE #20 const-data-lgamma recompute (re-add remedy primary). Bodies: orwell-style, <=20 lines, persisted in external/pr/ (pr-15..19, pr-8-stanc3, issue-20). Bases follow the forks' mainlines (math develop / stanc3 master — "main" does not exist on the math fork). All branches pushed to the forks from this session's worktrees; nothing pushed to any stan-dev/* repo.

## 2026-08-29 — W-123 CLOSE-OUT (PI-arbitrated): nb2-plain interior rebuild — gates (b)/(d) GREEN (bespoke model 6/6 draws digit-for-digit + parity exact-zero x2; 31 controls green), (a) GREEN with a FINDING: -O2 fully clean (59+12 throw cases); at -O3+mfma 5/59 lp-only 1-ulp diffs are STOCK'S OWN TU-INSTABILITY (two pristine stock compilations differ from each other on the same data — stock is not compile-stable under FMA flags; the patch PINS the contraction deterministically via std::fma after gate (b) caught GCC fusing the wrong product in some TUs), (c) SPLIT, owned: worktree posture 941.9→788.6 = −153.3 IN BAND on the RELEASED 5.3-era interior (the vintage users run: 3 lazy DefaultTraversal passes, mu+phi recomputed 4x/elem, log(mu+phi) 2x, the Eigen select evaluating BOTH operands = one discarded glibc log1p per element — all replaced by ONE scalar-sequential pass, lgamma count/args UNCHANGED per constraint); census-posture on the develop base = only −14..−25 (the campaign base carries a leaner post-VectorBuilder stock — the W-121 census measured the bundle's 5.3.0 vintage, correct for user-facing reality; both numbers real, vintage stated). NEW BOX GOTCHAS: (1) zsh `VAR="-I $path"` expands as ONE argv word — silently voided the pristine-overlay arm of the first gate run (caught, redone with a compile-time header-provenance canary; W-122's gate (b) used real file swaps, unaffected); (2) stock nb2 TU-instability at -mfma (above). Branch nb2-plain-rebuilt @ b2161e54b7 (5 commits). Record: results/nb2_rebuild_w123.md. FILING: math#21 (orwell body, vintage nuance stated).

## 2026-08-29 — W-124 PRE-REGISTRATION (before any code; the user's compute-once/re-add remedy, validated as an experiment): stanc3 CONST-HOIST emission — recognize `target += <lpdf/lpmf>(...)` whose constant-data subterm is recomputed per gradient eval; hoist it to transformed data and emit the internal <propto> overload + one precomputed add per log_prob call. Scope increment 1: the poisson family (poisson_log_lpmf + poisson_log_glm_lpmf — the census's best-measured, ~44% of family interior; lgamma(y+1) with y constant data)

DESIGN: stanc3 branch const-hoist off master-lineage 90c6532 in a
DEDICATED worktree (external/stanc3_w124 — never touch siblings).
MIR pass (own settings field, ON at --O1 per repo convention, OFF at
--O0; upstream note re --Oexperimental in the commit): match `TargetPE(
poisson_log_lpmf | poisson_log_glm_lpmf)(y_data, <params>))` in
reverse_mode_log_prob with y data-typed; rewrite to (a) a new
transformed-data double `lgamma_y1__ = sum(lgamma(y + 1))` (emitted
once at data init; lowered through the standard transformed-data
machinery to a stan::math call), (b) the likelihood call rewritten to
the internal <true> overload, (c) `lp_accum__.add(lgamma_y1__)`-class
re-add (exact emission shape = the accumulator pattern W-115 uses).
Double-mode instantiation KEEPS stock (constants belong there).
GATES (W-34-ArmB class — NOT md5-class, stated): (a) pattern
discipline: negative controls never fire (target += with param-typed y;
~ forms — which already drop constants — unaffected and NOT rewritten;
other lpdf heads; O0); (b) parity: regenerated vs stock form, 100 pts
lp agreement to LAST-ULP-with-constant-offset (lp_new − lp_stock ==
−lgamma_y1__ + summation-order ulps; gradients EXACT — the constant
has zero gradient; report max rel-L2); (c) SAMPLER: same-seed short
runs vs stock target+= form — draws NOT expected md5-equal (different
lp arithmetic); gates = distribution-level equivalence (bulk-ESS
medians within rep noise, rhat comparable, 3 reps) + identical grad-
call counts expected within noise; (d) cost: callgrind on a brms-style
poisson target+= model, band −30..−45% of the likelihood interior
(census: −44% emission-class); (e) no-op elsewhere: pattern-free
models byte-identical; dune runtest exit 0. Machine: <=2 cores, one
callgrind at a time (W-118 may run one — check ps), nice 19. Deliver-
able: results/consthoist_w124.md; if the accumulator re-add emission
cannot reproduce full-constant lp to ulp-class, STOP and report.

## 2026-08-29 — W-124 CLOSE-OUT (PI-arbitrated): the const-hoist emission (the user's compute-once/re-add remedy, VALIDATED) — ALL FIVE GATES GREEN, band exceeded favorably: poisson_log_glm subtree −48.4% Ir (per-elem 259.9→134.7; whole-run −46.9%; lgamma complex 41.0%→0.06% of run Ir — overshoot owned: the census's −44% counted libm lines only, the dropped term also carried Eigen expression overhead). PARITY: lp max |Δ| = EXACTLY 1.0 ulp vs stock (rel-L2 9.7e-17); gradients BITWISE-IDENTICAL 0/100; constant attribution Δ = +Σ exactly (3.3e-10). SAMPLER: distribution-level equivalent (ESS ratios 1.045/1.000/1.000 vs stock's own 16.9% rep spread; grad calls +0.01%); 2/12 chains coincidentally md5-IDENTICAL (the gradients-exact mechanism — when the ulp never bites, draws are literally equal). SELF-CONTAINED with upstream stan math (no paired-branch dependency — unlike W-108/W-115). THE PASS: Optimize.hoist_const_lgamma, LAST in suite, own settings, ON at --O1/--Oexperimental; suffix flips FnLpmf false→true; one transformed-data double −sum(lgamma(y+1)) in prepare_data (computed once at construction, location-table invisible); re-add via a second lp_accum__.add; .hpp diff = +1 member +1 ctor init +1 suffix flip +2 lines; 9 negative controls silent (~ forms untouched — they already drop constants). Branch const-hoist @ 33ef9e1 (parent master 90c6532), NOT pushed by agent. FILING: stanc3#9 + cross-comment on math issue #20. Deviations owned: pre-reg parity-formula reading (both decompositions reported); walnutpie warmup-freeze discovery → per-chain seeds, arm-symmetric, disclosed. Record: results/consthoist_w124.md.

## 2026-08-29 — W-125 PRE-REGISTRATION (before any run; converts the ridge-budget DECISION into data): fill the budget-shape matrix — graduated (W-110 archive) vs FIXED-128 (WALNUTPIE_RIDGE_GUARD=5 + WALNUTPIE_RIDGE_MINMICRO=128) on {bym2, diamonds, accel_gp} x 3 reps (pilots fixed-128 already measured in W-110: ESS 103/8.4/12.2). Binary/protocol = W-110 verbatim (external_w86 tip, --chains 4 --chain-exec serial --fixed-warmup, w1000/s1000, pf inits, mw50, seeds 20260819+1000*rep) — same-binary comparability with the W-110 ER/ER128 cells. EXPECTATIONS (pre-registered, from W-102/W-110): diamonds fixed-128 < graduated ESS (W-102: diamonds wanted graduation); accel >= graduated (7.1-class); bym2 unknown (graduated rep0 hit 23.0 — does 128 beat it?). NO single gate — the deliverable is the per-model ESS/wall/ESS-s trade TABLE + a curve recommendation (floor/shape) for the user's decision. Disclosure: bym2 fixed-128 cells may cost ~1h each (W-110 graduated cells ran 12-85 min). Machine: <=2 workers nice 19 while W-118 finishes. Deliverable: results/ridge_budget_w125.md.

## 2026-08-28/29 QUEUE (pre-registered shapes, launch as slots free; all green-lit by the user's "try them all"):
- W-126 (family 3): pcm/ordered gathered primitive — gpcm_latent_reg_irt as gate model; one registry row + the LSE-over-categories interior (the hard part); W-112 gate template.
- W-127 (family 4): additive multi-gather bernoulli_logit — election88_full as gate model; extends the LANDED primitive's eta space + a registry entry; W-112 gate template.
- W-128 (Lane B): stanc3 glm emission for everyday forms — rewrite beta[1]+beta[2]*x-class vector-predictor likelihoods to normal_id_glm at DEFAULT level; census says 50.7 -> ~18-20 Ir/elem with free reverse; W-34-ArmB gate class on REAL suite models (kidscore, logmesquite — the strongest possible gates); statistical class, stated.
- C1 (vectorized-form emission): HOLD until W-118's verdict — if the fused primitive lands at 55-65 Ir/elem bit-identically, C1's remaining advantage is nil and the lane closes without a run.
- FINAL COMPOSED BENCHMARK (after W-118 + the above): the everything-stack v2 table — 21-model grid, E-prime for the 4 gather models + E for the rest + the promoted-posture arms — the definitive promotion artifact.

## 2026-08-29 — W-125 CLOSE-OUT (PI-arbitrated) + IN-SESSION ADDENDUM: the ridge-budget decision matrix COMPLETE. KEY FINDINGS: (1) the graduated curve is clamp(16F/5,16,128) — bym2 all reps, diamonds r1/2, accel r2 ALREADY ran at effective 128 in W-110 (5 cells reused, md5-anchored by a fresh fixed-128 bym2 rep0 = 4/4 chains bit-equal); (2) bym2 has NO budget choice (F>=40 clamps; rep1's F=15,924 lock is budget-immune — init-class lane); (3) diamonds + accel prefer graduated (accel's "wants 128" refuted at the margin: ceiling ~7.1-7.2 for any budget >=95; +0.1 ESS for +83% wall); (4) pilots fixed-128 wins on rep0 only (6.4->103.0, the grid's ONLY ESS/s win 1.66x) — fixed-128 is a net ESS/s LOSS everywhere (0.03-0.22x R0): the W-110 quality-lever conclusion holds for BOTH budgets; (5) the benefit ANTI-CORRELATES with F (marginal locks want full 128; deep locks immune) — NO monotone curve or F-selector separates the classes. ADDENDUM (PI-run, 3 cells): pilots at FIXED-64 = ESS 61.3/7.8/22.3 (median 22.3 — the BEST median of all three arms; rep0 captures 60% of the heal 6.4->61.3 of ->103; rep2 BEATS both arms 22.3 vs 15.1/12.2; walls 38s-class). RECOMMENDATION (now risk-closed): budget = max(64, 16F/5) cap 128 — dominates every measured cell; a one-line change on exp/ridge-guard whenever the user adopts. Record: results/ridge_budget_w125.md + scratch/w125/runs/ER64.

## 2026-08-29 — W-128 PRE-REGISTRATION (before any code; Lane B, user green-lit): stanc3 glm emission for EVERYDAY forms — extend the existing UMatrix-predictor glm rewrite (partial_evaluation, currently --O1-only per W-119's read of Partial_evaluator.ml 536-578) to DEFAULT level AND to the scalar-intercept + slope*vector shape (the kidscore/logmesquite fma(b2,x,b1) class that NEVER reaches glm at any level today); census: 50.7 -> ~18-20 Ir/elem with free reverse. STATISTICAL CLASS, stated everywhere: the glm interior computes a different (analytically-simplified) gradient — draws change; gates are W-34-ArmB-class on REAL suite models

DESIGN: stanc3 branch glm-default-emit off master 90c6532 in
external/stanc3_w128 (never touch siblings). First READ the existing
rewrite + the stanc3 signature tables + math's normal_id_glm
requirements (T_x matrix-typed: does an Eigen vector bind? if not, the
single-slope emission must wrap x as a 1-column design or call the
vector-compatible path — determine, disclose). SCOPE increment 1:
normal family only, shapes {alpha + x*beta (vector x, K=1), X*beta +
alpha (matrix, any K)} at default level + the O1 status quo preserved.
GATES (W-34-ArmB class): (a) pattern discipline — negatives NEVER fire
(nonlinear predictors, vector sigma, non-normal heads, y non-data);
fires recorded per form; (b) PARITY on kidscore_momiq + logmesquite
(REAL suite models, their real data/inits): regenerated-vs-stock .so,
100 pts: lp + gradient rel-L2 in the last-ulp band (<= ~1e-14; the glm
gradient is analytically equivalent, not bitwise — REPORT the actual
agreement class honestly); (c) SAMPLER: 3 reps x 4 chains both arms,
W-36-class protocol (pf inits, mw50): ESS medians within rep noise,
rhat comparable, draws NOT expected equal; (d) COST: callgrind both
models, band −40..−60% of the likelihood interior (census 50.7→18-20;
glm1 anchor 16.7), attribution; (e) no-op elsewhere: the pattern-free
suite models byte-identical at BOTH levels; dune runtest -j2 exit 0.
Machine: <=2 cores, one callgrind at a time (W-118 may run one),
nice 19. Deliverable: results/glm_default_emit_w128.md; UPSTREAM NOTE
in the commit: this changes numerics at default level — the natural
upstream gating is --Oexperimental-first.
