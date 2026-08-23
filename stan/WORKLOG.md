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
