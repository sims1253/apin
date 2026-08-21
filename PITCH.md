# nindan — make Stan reach target ESS in half the wall-clock

nindan = the Sumerian surveyor's measuring rod (also: the act of measuring).
This lane is about measuring where Stan's wall-clock actually goes, cutting
what's waste, and squeezing more ESS out of every gradient evaluation.
CPU-side, Stan-land, no algorithmic religious wars — evidence only.

You are an autonomous agent picking up this brief. You know nothing from any
prior conversation. Work phase by phase; do not skip Phase 0/1 to get to the
fun part. Append everything to `WORKLOG.md` in this directory.

---

## Context

Stan (mc-stan.org) is the reference implementation of HMC/NUTS for Bayesian
inference: a C++ templated log-density with reverse-mode autodiff
(stan::math), compiled per model by stanc3, driven by the NUTS transition
kernel (`src/stan/mcmc/hmc/nuts/base_nuts.hpp` in stan-dev/stan).

Two facts motivate this project:

1. **nutpie** (pymc-devs/nutpie, Rust) reports ~2x average speedup over
   default Stan sampling on posteriorDB *without changing the algorithm*
   (their claim; verify it). That means a substantial fraction of Stan's
   wall-clock is implementation overhead, not Hamiltonian dynamics.
2. Stan's own adaptation (warmup: step size via dual averaging, mass matrix
   via Welford covariance over sliding windows) is ~15 years old, tuned by
   hand, and directly determines ESS-per-gradient. Almost nobody has run a
   systematic, benchmark-grounded ablation of its knobs.

North-star metric: **wall-clock to reach a reliable posterior** on a frozen
benchmark set. Concretely, per model: 4 chains, 1000 warmup + 1000 draws,
default NUTS; report (a) total wall-clock, (b) ESS_bulk/sec, (c) ESS_bulk per
gradient evaluation, (d) divergence rate, (e) max treedepth-hit rate.
Aggregate across the set as the geometric mean of (b). ESS via rank-normalized
ESS_bulk (posterior R package, Vehtari et al. 2021, arXiv:1903.08008).

Environment: WSL2, Linux, `uv` for Python, R available, RTX 5090 available
but this lane is CPU-only by design (do not GPU-ify Stan). Install CmdStan
via cmdstanr or cmdstanpy. Use posteriordb (github.com/stan-dev/posteriordb,
R package `posteriordb`) as the model corpus.

---

## Phase 0 — Harness (Rtisan-style; treat like a benchmark harness, not a script)

Build a reproducible benchmark runner:

- Select ~20 posteriorDB reference models spanning: small/easy (e.g.
  eight_schools noncentered), GLM-ish, hierarchical (radon-style), GP or
  spatially correlated, and at least one pathologically stiff/funnel-ish.
  Freeze the list in `stan/CORE_SET.md` **before any optimization work
  begins; never edit it afterwards.**
- Runner: fixed CmdStan version (record SHA), fixed seeds, median of 3 runs
  per config, output to CSV/parquet with full metadata (model, config, seed,
  walltimes, sampler diagnostics).
- Baselines to include from day one:
  1. cmdstan default NUTS (the reference)
  2. cmdstan with stanc3 `--Oexperimental` (free upside if it wins; measure)
  3. nutpie sampling the same posteriorDB models (quantify and localize its
     claimed 2x: which models, and is it warmup, kernel loop, or autodiff?)

DoD: one command reruns the whole grid; a results table regenerates from raw
outputs; WORKLOG shows baseline numbers for all 20 models x 3 baselines.

## Phase 1 — Bottleneck atlas

Where does wall-clock actually go? Produce a ranked, per-model-family
breakdown:

- Stan's built-in profiling (introduced 2.26: `profile("block")` statements
  in the Stan program) on representative models — add profile blocks to
  copies of a few CORE_SET models.
- System-level: perf / callgrind on the sampling binary; separate time in
  gradient evaluation vs. kernel bookkeeping vs. RNG vs. I/O.
- Microbenchmarks of suspected overheads (hypotheses to test, not facts —
  historical evidence says several of these have each been worth ~2x on
  model families where they dominate):
  - `ps_point` copies and Eigen dynamic allocations in the NUTS tree loop
    (`base_nuts.hpp` transition/build_tree copy state vectors liberally)
  - var/varvalue allocation and expression-template depth in stan::math
    reverse mode; arena reset policy per gradient
  - validity checks (`check_finite`, `check_not_nan`, `check_positive`)
    inside hot lpdf templates — measured at ~60% of runtime in one GLM
    microbenchmark before specialization (stan-dev discourse, "Potential
    slowness in operands_and_partials")
  - `operands_and_partials` / `make_partials_propagator` construction —
    historically ~half of `normal_id_glm_lpdf` runtime (pass-by-value bug
    + partials `Zero()` allocation); verify current state
  - Eigen codegen on small/medium dynamic matrices (measured ~4x off
    hand-vectorized code on identical CPUs; stan discourse "Stan SIMD &
    Performance")
  - recomputation of log-density constants; gradient calls on states that
    end up discarded by subtree invalidation

Hardware note: this machine's Ryzen 5900 is Zen 3 — AVX2/256-bit lanes
(4 FP64 doubles) only, no AVX-512. SIMD work means tight AVX2+FMA loops,
alignment, unrolling, and allocation removal — not zmm-width games. Record
this in WORKLOG so no session wastes time on AVX-512 paths.

DoD: `stan/ATLAS.md` — per-family stacked breakdown, ranked suspects with
measured (not guessed) shares, including "share of time in user model
gradient with no structural waste" as an explicit number.

## Phase 2 — Implementation wins

Attack the top measured suspects only. "Gradient evaluation is 85% of
wall-clock" is NOT a wall — it means the gradient path is the target.
Historical precedent: operands_and_partials fixes and check specialization
were each worth ~2x on the families where they dominated. Sub-tracks, in
escalating order of invasiveness (each gated on ATLAS.md evidence):

- **2a Kernel loop.** ps_point copy elimination, allocation hoisting in
  base_nuts.hpp — only if ATLAS shows nontrivial share.
- **2b Check policy.** Batch/hoist/specialize validity checks in the hot
  lpdf templates (upstream precedent exists; be careful to preserve Stan's
  error semantics — rejected-parameter behavior is user-visible).
- **2c Build flags.** Measure `-march=native` (+ `-O3`, tuned `-mtune`)
  across CORE_SET — CmdStan defaults to generic x86-64; this may be free
  10-30% on AVX2 machines. Cheap, do it early.
- **2d Allocator/arena.** var allocation policy, partials buffers, Eigen
  temporary elimination in the reverse pass.
- **2e SIMD specialization.** For the lpdf families ATLAS shows dominant
  (GLM/vectorized lpdfs first): replace the Eigen expression template with
  an explicitly vectorized primal+adjoint (AVX2 intrinsics or
  Eigen-fixed-size batches), keeping exact summation-order semantics where
  feasible and reporting ULP drift where not.
- **2f Enzyme research spike (timeboxed ~2 weeks, clearly labeled
  research).** stanc3 emits the model as templated C++; instantiate
  `log_prob` at plain `double` (no var/tape), compile to LLVM IR with
  clang -O3 -emit-llvm, generate the reverse pass with Enzyme
  (enzyme.mit.edu) at the LLVM level, bridge back into Stan as a custom
  gradient via `reverse_pass_callback` / USER_HEADER external function.
  Why it could be big: AD after LLVM optimization on tape-free primal
  code — the vectorizer finally sees pure FP code. Risks: Enzyme chokes on
  Eigen intrinsics (fallback: -fno-vectorize primal, re-vectorize the
  differentiated output), custom-grad bridging subtleties, check-heavy code
  confusing activity analysis. Success criterion: gradient parity with
  stan::math reverse mode (finite differences + direct comparison at
  multiple points) and a measurable CORE_SET win. Failure is a written
  friction log, not a disaster.

Rules:

- Every change ships with before/after on the full CORE_SET (geomean, median
  of 3), not a microbenchmark.
- Numerics-affecting changes (summation reordering, caching, skipping
  discarded work) must additionally report max/quantile absolute difference
  of resulting draws against reference on 2 models — some divergence is
  fine, silent divergence is not.
- Patches kept as a quilt/branch series against the pinned CmdStan version,
  each with a rationale paragraph tying back to ATLAS.md. Anything clean and
  general becomes an upstream PR to stan-dev (their CONTRIBUTING is strict;
  read it before writing the patch).

DoD: geomean wall-clock-to-ESS improvement quantified honestly (including
"no win" outcomes), patch series + upstream PRs filed.

## Phase 3 — ESS-per-gradient lane (adaptation ablations)

Same harness, now varying warmup/adaptation instead of C++:

- Step-size target ablation (delta target 0.5–0.95): ESS/grad and divergence
  curves across CORE_SET. (Known folklore: 0.8 is not universally optimal.)
- Mass matrix richness: diag vs. dense vs. regularized/shrinkage covariance
  estimator (e.g. Ledoit–Wolf-style) for the Welford estimate in late
  adaptation windows; also ablate window counts/lengths and warmup total
  (does 1000 warmup over-adapt some model families?).
- Warmup-length reduction with better initialization (dispersed inits +
  shorter windows) — judged on post-warmup ESS/sec AND adaptation failures.

Every variant pre-registered in WORKLOG before running; failures recorded as
carefully as wins. DoD: ablation tables + a recommendation of default
changes worth proposing to Stan (with evidence, not vibes).

## Phase 4 (stretch) — Property harness for transition correctness

The cheap stand-in for formal verification; makes Phase 2/3 aggression safe:

- Reversibility round-trip: integrate L leapfrog steps, negate momentum,
  integrate L back; assert recovery within FP tolerance. Expose it as a
  test on the compiled model, run for every patched kernel.
- Volume preservation spot-check: numerical Jacobian determinant of the
  L-step integrator map on small-d models; |det| ≈ 1.
- Analytic-target invariance: standard Gaussian targets (isotropic, affine,
  funnel-adjacent) — moment coverage tests on long runs; divergence-rate
  profiles.

DoD: `stan/properties/` runnable in CI against any modified kernel; catches
a deliberately-broken kernel (negative control: flip a sign, prove the
harness sees it).

## Guardrails

- Never modify stanc3 the language or the .stan format.
- No formal methods in this lane (C++ template metaprogramming is not
  verifiable with current tooling — that's the other lane's job). Property
  harness is the ceiling here.
- No benchmark cherry-picking; CORE_SET is frozen.
- Kill criterion for Phase 2: none based on the "85% in gradients" number
  alone — gradient time is itself decomposable (checks, allocs, Eigen
  codegen, AD overhead, actual FLOPs; see Phase 1/2d-2f). The honest
  ceiling test is roofline: when a hand-specialized SIMD primal+adjoint
  for the dominant lpdf family sits near memory/compute roofline AND
  ATLAS shows no remaining structural share, write that up and shift
  effort to Phase 3.

## References

- Hoffman & Gelman 2014, JMLR — the NUTS paper (arXiv:1111.4246)
- Betancourt 2017, "A Conceptual Introduction to HMC" (arXiv:1701.02434)
- Vehtari, Gelman, Simpson, Carpenter, Bürkner 2021 — rank-normalized
  ESS/R-hat (arXiv:1903.08008); `posterior` R package
- posteriorDB: github.com/stan-dev/posteriordb
- Stan reference manual, MCMC + adaptation chapters (mc-stan.org/docs)
- Stan profiling docs (Stan ≥ 2.26); `base_nuts.hpp` in stan-dev/stan
- nutpie: pymc-devs.github.io/nutpie (verify its 2x claim yourself)
- Stan internals: stan-dev/math wiki, reverse-mode autodiff design docs
