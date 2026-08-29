# F-11 — mass-matrix / step-size adaptation upgrades for the fortk fork (stanli + fused tier)

**Status:** READ-ONLY design study. No code, no builds, no file modified except this document.
**Date:** 2026-08-26. **Inputs:** WORKLOG.md (fortk lane F-1..F-9 + walnutpie/nindan W-series and
Phase 0-3), PITCH.md, external/research_optimizer_{sota,pass2,aurora}.md, and read-only inspection
of `external/stanli` (main worktree @ `fortk/t1-regions`, 0243aad) incl. vendored
`deps/stan` (2.39, c96d04115) and `runtime/third_party/walnutpie` (upstream-shaped vendored copy).

---

## 0. Why adaptation is the next lever in the fused tier

The fused tier has inverted the cost structure that Stan's adaptation defaults were tuned under:

- **F-4b census:** with fused gradients, the esnc-class model is SAMPLER-BOUND — grad = 6.7% (nuts)
  / 14% (walnuts) of wall through the installed path; **85-95% of wall is tree bookkeeping /
  adaptation / service**. Even unfused esnc nuts was ~70% bookkeeping.
- **F-8 phase 1:** fused NUTS (arm C) = 2.33-3.78x CmdStan ESS/s on the well-behaved models
  (5.18x on esc; geomean 3.15x) at ESS/draw parity-or-better; fused WALNUTS (arm D) is
  spectacular where it
  converges (esnc 4.92x, esc 6.54x) but silently sticks on 3/6 models (blr chains parked at
  sigma 4.8/2.2/1.7/0.7, rhat 4.3) — the walnutpie-lane stuck-chain class, now reproduced inside
  stanli's vendored walnutpie.
- **Adaptation share of the remaining wall:** Phase-0 atlas had warmup = 52.7% of sampler time
  (median, >1s models; radon 77%), kronecker_gp 99.5% iterations at maxdepth=10. With gradients
  now 2-8x cheaper (F-7 census: corpus geomean ≈ 2.25x, hier_2pl 2.20x, arma11 5.47x), the
  adaptation loop's *quality per warmup iteration* — not kernel speed — sets both wall (how much
  warmup is wasted) and ESS/grad (how good the frozen (step, mass) pair is).
- **External attribution to beat/test:** PITCH.md's motivating fact — nutpie's claimed ~2x over
  default Stan "without changing the algorithm" — and the Columbia-blog-note attribution of that
  ~2x *entirely to better mass-matrix adaptation*. Our Phase-0 decomposition found nutpie's
  quality-adjusted ESS/s was a wash locally (0.98x geomean; wall 1.21x; per-gradient 2.6x cheaper),
  so the mass-matrix attribution is **a hypothesis to test in our stack, not a fact to import**.
  The strongest published number on our side: Fisher-HMC (arXiv 2603.18845, the walnutpie-adjacent
  team) — a better *diagonal* estimate beats Stan/PyMC variance diagonals by a median **1.3x** on
  114 posteriordb models (their low-rank+diag variant: median 4x, out of scope here — see §D).

F-11 therefore targets three surfaces: (1) the NUTS diag metric estimator in the vendored Stan,
(2) the WALNUTS MassEstimator in the vendored walnutpie, (3) the step-size target / treedepth
knobs of the fused NUTS arm — the last one requiring zero code.

---

## A. Inventory of adaptation knobs reachable in the fork

Two sampler arms exist in the stanli runtime, each with its own adaptation stack:

- **NUTS arm:** `stanli::run_nuts` (runtime/src/nuts.cpp:20) drives
  `stan::mcmc::adapt_diag_e_nuts<ExecutorModel, rng_t>` (nuts.cpp:34) from the **vendored Stan
  2.39** at `external/stanli/deps/stan` (submodule pin c96d04115). Model surface =
  `ExecutorModel` (runtime/include/stanli/model_adapter.hpp:41) which satisfies the Stan model
  concept over the (optionally fused) Executor.
- **WALNUTS arm:** `stanli::run_walnuts` (runtime/src/walnuts.cpp:103) drives the **vendored
  walnutpie headers** at `runtime/third_party/walnutpie/` — an upstream-shaped copy (single-chain
  `AdaptiveWalnuts`, plain per-observation Adam, discounted `MassEstimator`). It does NOT contain
  the walnutpie-lane fork stack (batching, chopping, low-rank, clamp, pf-init live in
  `external/walnutpie` @ dev/init-robustness, a separate repo).

### A.1 NUTS arm (vendored stan 2.39 via stanli)

| Knob | Default | Where it lives (file:line) | Runtime-configurable? |
|---|---|---|---|
| Target acceptance `delta` | 0.8 | `NutsConfig::delta` runtime/include/stanli/nuts.hpp:27 → `set_delta` nuts.cpp:60 → `stepsize_adaptation::set_delta` deps/stan/.../stepsize_adaptation.hpp:20 | **Yes** — C API `stanli_sample` (capi.h:87-88), `stanli_sample_opts.delta` (capi.h:108), CLI `--delta` (tools/stanli_run.cpp:128-129) |
| DA restart anchor `mu` | `log(10·eps_0)` | nuts.cpp:58-59 (matches adapt_diag_e_nuts.hpp:38 re-anchor at each window end) | Value fixed by construction; code-change to alter |
| DA `gamma` (adaptation scaling) | 0.05 | stepsize_adaptation.hpp:14 (ctor default); setter :25-28 **never called by stanli** | Code-change (setter exists; add NutsConfig field + nuts.cpp call) |
| DA `kappa` (iterate-averaging decay) | 0.75 | stepsize_adaptation.hpp:14; setter :30-33 never called | Code-change (same) |
| DA `t0` (effective start iter) | 10 | stepsize_adaptation.hpp:14; setter :34-37 never called | Code-change (same) |
| Step-size jitter | 0.0 | nuts.cpp:57 `set_stepsize_jitter(0.0)` | Hard-coded 0; code-change |
| Welford window schedule (init_buffer / term_buffer / base_window) | 75 / 50 / 25 | nuts.cpp:62 `set_window_params(warmup, 75, 50, 25)` → windowed_adaptation.hpp:29-78; window doubling + end-stretch logic windowed_adaptation.hpp:91-110; <20-iter and too-small-warmup fallback = 15%/75%/10% (:39-71) | `warmup` yes (nuts.hpp:21, CLI); the 75/50/25 constants hard-coded in nuts.cpp:62 — code-change (trivial) |
| Window variance regularization (Stan's shrink rule) | `var ← (n/(n+5))·var + 1e-3·(5/(n+5))·1` | **deps/stan/.../var_adaptation.hpp:27-28** (inside `learn_variance`, after Welford `sample_variance` at :24); estimator restart :38 | Hard-coded; **code-change in vendored stan** (this is Design 1's target). Object is reachable (`stepsize_var_adapter::get_var_adaptation()`, stepsize_var_adapter.hpp:20) but has no setters for these constants |
| Welford accumulator | — | deps/math/stan/math/prim/fun/welford_var_estimator.hpp:10-40 (add_sample :23, sample_variance :35) | Not a knob |
| Metric type | diagonal | nuts.cpp:34 `adapt_diag_e_nuts` | Code-change (dense-E exists upstream but O(d²)-O(d³); d~7000 infeasible — see §D) |
| `max_depth` | 10 | nuts.hpp:31 → nuts.cpp:61 | **Yes** — CLI `--max-depth` (stanli_run.cpp:130-131), C API opts (capi.h:109) |
| Init (radius / fixed point) | 2.0 / random | nuts.hpp:41-46, initialize.hpp; CmdStan-matched stream nuts.cpp:31-33 | **Yes** — `--init-radius` (stanli_run.cpp:139-140), `inits` array (capi.h:113); pf-init (`--init pf`) exists only on F-9's pinned worktree so far |
| warmup / samples / thin / save_warmup | 1000/1000/1/no | nuts.hpp:21-35, loop nuts.cpp:98-101 | **Yes** |

### A.2 WALNUTS arm (vendored walnutpie via stanli)

Warmup = `walnutpie::AdaptiveWalnuts` (adaptive_walnuts.hpp:183), constructed in walnuts.cpp:187-192
with a `WarmupConfigBuilder` that sets **only** `min_max_iter` — everything else is the vendored
default. All knobs below therefore exist as builder setters
(runtime/third_party/walnutpie/config.hpp:646-850) but are **not reachable from stanli without a
code change** (add builder calls + WalnutsConfig fields in runtime/include/stanli/walnuts.hpp:17).

| Knob | Default | Where it lives (file:line) | Runtime-configurable from stanli? |
|---|---|---|---|
| Step adapter (algorithm) | scalar Adam on log-step, one observation **per micro-step** | adam.hpp:35-109; `grad = target − alpha` :75; bias-corrected update :77-85 | No — hard-wired in AdaptiveWalnuts ctor (adaptive_walnuts.hpp:216-220) |
| Accept target (`step_accept_rate_target`) | 0.8 | config.hpp:633; setter :740-744 | Code-change (builder call) |
| Adam lr | 0.05 | config.hpp:634; setter :754-758 | Code-change |
| Adam betas (gradient / sq-gradient decay) | 0.8 / 0.9 | config.hpp:635-636; setters :767-784 | Code-change |
| Adam stabilization eps | 1e-4 | config.hpp:637; setter :794-798 | Code-change |
| lr decay exponent | 0.5 (`t^-0.5`) | config.hpp:638; setter :807-811 | Code-change |
| **Observation batching (stride)** | none (1 obs/micro-step) | does NOT exist in this vendored copy (the walnutpie-lane fork's `BatchedAdapter` is not vendored) | Code-change (port) |
| Mass discount offset (`mass_init_count`) | 4.0 | config.hpp:630; setter :701-705; consumed as discount `1 − 1/(offset+t)` at adaptive_walnuts.hpp:76-77 | Code-change |
| Mass additive smoothing | 1e-5 | config.hpp:631; setter :714-718 — **DEAD CONFIG: never consumed anywhere** (grep-verified; the doc comment in MassEstimator describes it but the ctor at adaptive_walnuts.hpp:54-62 ignores it) | — |
| Mass estimator rule | `inv_mass = sqrt(Var_draw / Var_score)`, discounted Welford on draws AND scores | adaptive_walnuts.hpp:25-105 (`observe` :74-80, `inv_mass_estimate` :89-94); OnlineMoments online_moments.hpp:125-247 | Code-change (Design 2's target) |
| Initial mass | **identity** (`Eigen::VectorXd::Ones`) | walnuts.cpp:186 (`InitChainConfig(step0, q, Ones)`); the gradient-seeded `InitConfigBuilder::masses(...)` (config.hpp:360-382, the "nutpie outer product strategy") is NOT used by stanli | Code-change |
| Initial step + probe | `init_step_size`=1.0 then a local find-reasonable-epsilon probe (60 iters, double/halve on |ΔH| vs log 2) | walnuts.hpp:30 + walnuts.cpp:145-173 | `init_step_size` is in WalnutsConfig but no CLI/C-API flag; probe always on |
| `max_macro_steps_target` (orbit-length target feeding MinMicroStepsAdaptHandler) | 15.0 | config.hpp:632; setter :727-731; handler adaptive_walnuts.hpp:119-164 | Code-change |
| Convergence tols (`step_size_converge_tol` 0.1, `mass_converge_tol` 1.0), `publish_stride` 5, `yield_period` 32 | see defaults | config.hpp:628-640 | Dead for the single-chain loop stanli runs (multi-chain controller params; stanli never runs it) |
| `max_error` (Hamiltonian drift cap per macro step — "the sampler's tunable in place of delta") | 0.5 | walnuts.hpp:28 → walnuts.cpp:180 → SamplingConfig (config.hpp:951) | **Yes** — C API `stanli_sample_walnuts_stream` (capi.h:270-273); no CLI flag on main worktree |
| `max_step_halvings` | 5 | walnuts.hpp:27 → walnuts.cpp:179 | In WalnutsConfig; not CLI/C-API exposed |
| `max_depth` (trajectory doublings) | 10 | walnuts.hpp:23 → walnuts.cpp:178 | Same |
| NaN/-inf policy | logp/grad non-finite → logp=-inf, grad=0 | walnuts.cpp:44-57 (ExecLogpGrad) | Not a knob (semantics) |

### A.3 Shared / service layer

- **Pathfinder** (runtime/src/pathfinder.cpp): `run_pathfinder` wraps
  `stan::services::pathfinder::pathfinder_lbfgs_single` (pathfinder.cpp:201-206) with
  `PathfinderConfig` (history_size, init_alpha, tolerances, num_iterations, num_elbo_draws,
  num_draws). Single-path only on main; F-9's pinned worktree adds `stanli::run_pathfinder_multi`
  (num_paths=4, PSIS pooling) + tool `--init pf` / `--pf-seed`. This is F-9's surface; F-11
  composes with its outcome but does not modify it.
- **CLI (`tools/stanli_run.cpp`)**: exposes warmup/samples/delta/max-depth/init-radius/thin/
  save-warmup/sampler-stats for NUTS. `--sampler walnuts` and `--init pf` exist only on F-9's
  pinned worktree (plumbing commits, never merged — confirmed by grep of the main worktree).
- **C API (`runtime/src/capi.cpp`, header capi.h)**: full NUTS opts struct; walnuts only via the
  streaming entry with `max_error`.

### A.4 Inventory read-out (what this enables)

1. The **step-size target and treedepth of the fused NUTS arm are already fully
   runtime-configurable** end-to-end (CLI + C API) → Design 3 needs zero code.
2. The **only mass-matrix knob with any existing runtime exposure is none** — Stan's
   regularization constants (var_adaptation.hpp:27-28) and walnutpie's discount/smoothing/target
   are all compile-time; both designs 1 and 2 are code changes in *vendored* trees
   (deps/stan and runtime/third_party/walnutpie respectively).
3. The vendored walnutpie is materially BEHIND the walnutpie-lane fork (no batching, no chopping,
   no shrink/floor, no clamp, no pf-init) — Design 2 is substantially a **port of
   already-evidenced changes** into the vendored copy, not new research.
4. deps/stan is shared: F-10 (sampler-loop package: 2a scratch-hoist in base_nuts.hpp + W-20
   endpoint-grad threading + mallopt) and Design 1 both modify the vendored stan submodule →
   hard sequencing constraint (§C).

---

## B.1 Design 1 — Shrunk / regularized late-window covariance for the NUTS diag metric

**Surface:** vendored Stan's `var_adaptation::learn_variance`
(external/stanli/deps/stan/src/stan/mcmc/var_adaptation.hpp:17-46), wired through
`adapt_diag_e_nuts::transition` (adapt_diag_e_nuts.hpp:25-43) and reachable from stanli at
nuts.cpp:34/62.

### Mechanism

Stan already shrinks — the rule at var_adaptation.hpp:27-28 is
`var ← (n/(n+5))·var + 1e-3·(5/(n+5))·1`: a fixed prior weight `5/(n+5)` toward a *tiny*
(1e-3-scaled) identity, applied at every window end regardless of how noisy the window estimate
is. Two things are missing, both classical (research_sota TL;DR #4):

1. **A data-dependent intensity.** Ledoit-Wolf (2004)/OAS give closed-form shrinkage intensities
   for Gaussian-ish data: mix the sample estimate with a structured target using a weight
   estimated from the estimator's own sampling variance, not a constant. In the diagonal/windowed
   setting the honest adaptation (no published online LW for windowed Welford exists — the
   research register flags this as untested) is:
   - target: scaled identity `m·1` with `m = mean(var_window)` (trace-preserving, unlike 1e-3);
   - intensity: per-coordinate or scalar `λ ∈ [0,1]` from window sample size `n`, dimension `d`,
     and the window's own dispersion. The full LW oracle needs 4th moments; an O(d) surrogate
     keeps a second Welford stream on `q_i²` (same window discipline) to estimate per-coordinate
     kurtosis, giving `λ_i ≈ clip( (1+2κ_i/n)-ish · scale term , 0, 1 )`; the simplest defensible
     v1 is a **scalar** λ from the mean dispersion (`λ = n/(n + c·d̄)`-shaped, `d̄ = d/n_eff`
     effective draw-poor-ness), i.e. "shrink harder exactly when the window has few draws per
     dimension" — the regime kronecker_gp (d≈7000, ~hundreds of window draws) lives in.
2. **A meaningful target scale.** 1e-3 is arbitrary (Stan picked κ=5 and 1e-3 "by convention,
   not theory" — research_sota risk note). Trace-preserving shrinkage never moves the *average*
   scale, only de-noises per-coordinate ratios — safer for the DA equilibrium (step size is
   re-found after every window anyway: adapt_diag_e_nuts.hpp:35-40 re-runs `init_stepsize` +
   re-anchors DA at each update).

### Expected effect (evidence, with honest calibration)

- **Motivation (external):** the nutpie ~2x "due entirely to better mass-matrix adaptation"
  attribution (PITCH fact 1 + the Columbia blog note). Caveat recorded up front: our Phase-0
  decomposition found nutpie's *quality-adjusted* win locally was a wash (ESS/s 0.98x geomean;
  the 2.6x was per-gradient wall), so the attribution bounds what a metric change can deliver in
  our stack. The directly relevant published number is Fisher-HMC's **median 1.3x** for a better
  diagonal on 114 posteriordb models (2603.18845) — that estimator also uses scores (out of scope
  here; see §D), and 1.3x median is the realistic ceiling family for diag-metric work.
- **Where it should pay in CORE_SET:** high-d / draw-poor late windows — kronecker_gp (d~7000;
  Phase-0: 99.5% td-hits, ESS 944/4000; pf+w200 could NOT adapt its mass matrix, ESS 0.25x —
  direct evidence that window quality is the binding constraint there), radon_all (warmup 77% of
  wall), hier_2pl, bym2. Also the shorter-warmup regime PITCH Phase-3 pre-registered (H2: 200-iter
  warmup) — a better per-window estimator is exactly what makes short warmup viable.
- **Local precedent (mixed, must be cited):** W-2 tested shrink κ=5 + floor 1e-3 on walnutpie's
  *discounted* estimator and it did NOT move rhat-bad (9→9) — but that was the init-stuck regime
  (W-4/W-7 showed those chains never reach the typical set, so no estimator sees informative
  draws), and the estimator differed (discounted, no windows). In windowed NUTS with sane inits
  the failure mode is absent. Stan's own rule proves the mechanism is load-bearing at least
  weakly (it exists to keep windows finite).

### Implementation sketch

All in the vendored stan on a dedicated fork branch (same discipline as F-10's 2a patch; never
mixed with other changes):

1. `var_adaptation.hpp`: parameterize the rule — add `set_metric_regularization(double kappa,
   double shrink_scale, double lw_c)` with defaults exactly (5.0, 1e-3, 0.0) where `lw_c=0`
   reproduces stock arithmetic **bit-identically** (same expression order). Non-zero `lw_c`
   activates: target `m = var.mean()`, intensity `λ = n/(n + lw_c·d)` (v1 scalar; per-coordinate
   kurtosis variant v2 behind the same flag), output `λ·var + (1-λ)·m·1`. ~20 lines.
2. Plumb one int/double through stanli (NutsConfig field, nuts.cpp call after line 62 via
   `sampler.get_var_adaptation().set_...` — getter confirmed to exist,
   stepsize_var_adapter.hpp:20). CLI flag on the runner tool.
3. Optional v2 (separate arm only): second Welford stream on squared draws for per-coordinate
   intensity; strictly additive.

**Conflict note:** var_adaptation.hpp does not collide textually with F-10's base_nuts.hpp /
ps_point work, but both are commits to the same `deps/stan` submodule pin — the lane's QUEUE rule
(F-10 waits for F-9 because deps/stan is symlinked into F-9's pinned worktree) extends to F-11.1:
it queues behind F-10, or shares F-10's branch-mechanics with its own commit.

### Risk / failure modes

- **Over-shrinkage slows adaptation** on badly-scaled models (research_sota #4 risk; λ→0 means
  unit metric where the model needs scales) — mitigated by trace-preserving target and λ→1 as
  n/d grows.
- **Funnel flip-flop:** metric changes move divergences nonlinearly on funnels; W-8's rank metric
  regressed eight_schools_centered to 0.19x — any metric change must be judged per-family, with
  the funnel class explicitly watched (divergence-rate gate below).
- **No bit-identity possible** for the active arms (variance values change → trajectories
  diverge chaotically per F-4 gate-(c) doctrine) — statistical-equivalence class only.
- **Diminishing returns on well-conditioned models** — λ should →1 there; the gate explicitly
  checks the rule is inert where it should be.

### Pre-registration-ready gate proposal

Protocol: 3 reps × 4 chains × 1000+1000, seeds/interleaving per F-8; arms = {stock,
lw_off (wired knob at identity — **bit-identity check**), lw_c ∈ {2, 10, 50}}; models = the F-8
phase-2 seven (radon_pp, radon_var_slope, bym2, hier_2pl, lsat, diamonds, arma11) + kronecker_gp
+ eight_schools_centered as funnel sentinel.

- **Correctness invariants:**
  (i) `lw_off` arm BITWISE-IDENTICAL to stock (3 models × 3 seeds, cmp on draws) — proves the
  refactor changed nothing;
  (ii) active arms statistically equivalent where stock is healthy: rank-normalized ESS_bulk
  within noise, rhat<1.01, **divergence rate not increased** on any model (this is the funnel
  sentinel; an increase >2x on eight_schools_centered/pilots = arm rejected);
  (iii) finite/inverse-able metric at freeze (no `Numerical overflow` throws) on all arms.
- **Perf/ESS gates (3-rep medians):** geo ESS/s ≥ 1.00x (no aggregate regression) AND ≥ 1.10x on
  the draw-poor subclass {kronecker_gp, radon_pp, radon_var_slope}; secondary: warmup-trimmed
  variant (500 warmup) does not lose more than 5% ESS vs stock-at-1000 on the same subclass
  (the short-warmup payoff hypothesis).
- **Mechanism check (diagnostic, no gate):** log per-window λ; require λ > 0.9 on esnc-class
  (well-estimated windows) for the arm to be considered "behaving" rather than lucky.

---

## B.2 Design 2 — Upgrade the vendored walnutpie MassEstimator (walnuts arm)

**Surface:** `runtime/third_party/walnutpie/adaptive_walnuts.hpp:25-105` (MassEstimator),
`online_moments.hpp:125-247` (OnlineMoments), `config.hpp` (WarmupConfig), plus wiring in
`runtime/src/walnuts.cpp:175-199` and `runtime/include/stanli/walnuts.hpp:17-36`.
Notably this does NOT touch deps/stan → no F-10 conflict.

### Mechanism — four changes, each individually evidenced

1. **Cite and keep the rule (no code):** `inv_mass = sqrt(Var_draw/Var_score)` is Fisher-HMC
   Theorem 2.2 (arXiv 2603.18845) — the Fisher-divergence-optimal diagonal — not a heuristic
   blend. Fork-facing comment + WORKLOG correction only.
2. **Window chopping instead of (or blended with) discounting:** at window boundaries of width W
   (~50, matching the walnutpie lane's chop50), RESET the two OnlineMoments instead of carrying
   `1 − 1/(offset+t)` forever (adaptive_walnuts.hpp:76-77). The one published head-to-head
   (2603.18845 §discount) comes down for chopping: stale early draws are bias, not signal.
   Concretely: add a `mass_window` field to WarmupConfig + a `restart()` call on
   `draw_var_estimator_`/`score_var_estimator_` when `iteration % W == 0` (OnlineMoments already
   has the constructor for re-seeding from the current estimate — re-seed with weight
   `mass_init_count` at the post-reset inv_mass to avoid a cold start).
3. **Robustify + floor Var_score (the early-drift failure mode):** pass2 idea 5 — clip each score
   coordinate at a running robust scale (±k·MAD or k-σ Winsor, k≈3-5) before its second moments,
   and floor Var_score at `max(var, ε_floor)` before the ratio. Mechanism (W-4 diagnosis): during
   distant-init drift a handful of giant scores blow up Var_score → inv_mass collapses → chain
   throttled ~1e6x → Var_draw≈0 self-locking loop. Bounded-influence second moments break the
   loop; the heavy-tail-clipping theory (2406.04443 / 2410.16561) says un-clipped adaptive
   scaling is *provably* the bad case under such noise.
4. **n_eff-aware shrinkage toward the re-seed value** (Kish `n_eff = (Σw)²/Σw²` for the
   discounted weights — computable in O(1) alongside OnlineMoments since weights follow the
   deterministic `1−1/(offset+t)` schedule): the Stan-rule analogue
   `var ← (n_eff/(n_eff+κ))·var + seed·(κ/(n_eff+κ))`, κ≈5 (research_sota TL;DR #4; W-2's
   single-chain probe: arma11 rhat 9.48→~1.02 with exactly this shape of fix — though see the
   honest negative below).

Also ported as *optional* arms (not core): **observation batching** for the step Adam
(mean-α per stride ~50) — the walnutpie lane's single biggest adaptation fix (W-1: rhat-bad
17/21→9/21, aborts eliminated) — since the vendored copy feeds Adam one observation per
micro-step (adam.hpp:70; the W-1 finding: Adam was implicitly calibrated for that frequency,
classic DA was not). And **`mass_additive_smoothing` is dead config** — either wire it (it is
documented at config.hpp:631 but consumed nowhere) or delete it; wiring it is a free floor-ish
knob adjacent to change 3.

### Expected effect (evidence)

- **The chain that motivates everything:** W-5/W-6 on the walnutpie CLI — pf-inits alone took
  geo ESS 25.8→295.8 (11x) but left rhat-bad ~9-11; **+chop50 was a clear win on top**
  (blr 201→401 ESS rhat 1.007, kronecker 1.046, diamonds 1.465) → recommended config included
  chop. The stanli walnuts arm has NONE of {pf-init (F-9 in flight), chop, shrink, robust scores,
  batching}.
- **F-8's D-arm read:** stuck chains (blr sigma parked at 4.8/2.2/1.7/0.7) are attributed to
  init + Adam-adapted steps → F-9 tests the init half. Design 2 is the *other* half plus the
  estimator-quality polish; W-7's no-crossover result says you cannot warmup your way out of a
  collapsed metric, so the estimator must be fixed for short warmups to ever work.
- **Honest negatives that bound expectations:** W-2 found shrink+floor did NOT move rhat-bad
  beyond batching alone (9→9) on the stuck class; W-3 found longer orbits buy nothing there;
  the mass patches were 0/5 *in isolation* — the lever ordering was init distance first. So
  Design 2's expected value is explicitly conditional on F-9: if pf-init unfreezes the D-arm,
  Design 2 converts "converges" into "converges efficiently" (ESS/grad, wall); if pf-init does
  NOT fix it, Design 2 (chop + robust scores + batching, the W-6 stack minus what F-9 owns) is
  the next-evidenced lever, and its stuck-recovery gate is the pre-registered arbiter.
- **W-22 guardrail:** the late-warmup drifting signal in walnutpie is the STEP, not the mass
  (hier_2pl step +169% late while invm +13%). Mass-side changes alone should not be sold as
  fixing late-warmup behavior; if a warmup-length interaction appears, the step-stabilization
  gate is the follow-up, out of F-11 scope.

### Implementation sketch (file:line)

- `online_moments.hpp`: add `kish_neff()` (O(1), closed form under the known discount schedule)
  and a `winsorized_observe(clamp_scale)` variant, or do the clipping caller-side (cheaper:
  keep OnlineMoments pristine).
- `adaptive_walnuts.hpp`: in `MassEstimator::observe` (:74-80) — apply score clipping + Var_score
  floor inside `inv_mass_estimate` (:89-94); add window reset logic keyed on `iteration`; re-seed
  per change 2. In `AdaptiveWalnuts::operator()` (:234-251) nothing changes structurally.
- `config.hpp`: add `mass_window` (0=off default), `mass_score_clip_k`, `mass_var_floor`,
  `mass_shrink_kappa`; builder setters alongside the existing ones (:646-850). Either wire or
  remove `mass_additive_smoothing` (:631).
- `runtime/src/walnuts.cpp`: extend the `WarmupConfigBuilder` chain (:187-190) and add fields to
  `WalnutsConfig` (walnuts.hpp:17-36); expose `step_accept_rate_target` + the mass knobs through
  capi alongside `max_error` (capi.h:270-273 pattern).
- **Porting shortcut with a caution:** the walnutpie-lane fork (external/walnutpie
  @ dev/init-robustness) already contains battle-tested versions of chop/shrink/batch/clamp —
  porting selected commits into the vendored copy is faster and lower-risk than re-deriving, BUT
  the vendored copy is single-chain and header-shaped differently in places; port the *ideas*
  with fresh minimal diffs, keep the vendored tree's structure (the lane's PROVENANCE rule: every
  change default-off and inert).

### Risk / failure modes

- Over-shrinkage / over-clipping biases the metric for genuinely heavy-tailed posteriors
  (pass2 idea-5 risk): keep k generous (≥3), funnel models in the gate set.
- Chopping loses information in slow-drift regimes where discounting tracks (pass2 idea-1 risk)
  — mitigated by re-seeding windows from the previous estimate rather than cold identity.
- Interaction with WALNUTS' within-orbit dyadic adaptation: the step loop's effective acceptance
  statistic is unusually noisy (research_sota §3), which is why batching is bundled — but the
  bundling must be ablatable (separate arms) or attribution is lost.
- Draw-level changes only, no bit-identity (estimator change); statistical gates only.
- Reproducibility discipline: any new RNG use must thread the existing seeded `detail::Random`
  (W-18's clock-seeded `Eigen::Random` bug class).

### Pre-registration-ready gate proposal

Protocol: F-8/F-9 shape — 6 phase-1 models + blr/kidscore as the stuck sentinels; 4 chains ×
1000+1000, 3 reps, medians; arms = {vendored-stock, +chop50, +chop50+robust(floor/clip),
+chop50+robust+batch50, (optional) +shrink κ=5}. Factorial enough to attribute.

- **Correctness invariants:**
  (i) estimator-level property tests BEFORE sampling (the W-8 discipline): feed synthetic
  Gaussian draw/score streams with known σ → inv_mass converges to σ within 5%; degenerate
  Var_score=0 input → floored, finite output; giant-outlier score stream → inv_mass bounded
  (no collapse); window reset → estimate unchanged at steady state within noise;
  (ii) all-off arm BITWISE-IDENTICAL to current vendored behavior (3 models × 3 seeds);
  (iii) sampler-level statistical equivalence on healthy models (esnc/esc/logmesq): ESS/draw
  within noise, no new divergences, frozen (step, inv_mass) non-degenerate at freeze.
- **Perf/ESS gates (3-rep medians):**
  - If F-9 PASSED its stuck-recovery gate: primary = geo ESS/s and ESS/grad of D_pf+design2 vs
    D_pf, target ≥ 1.10x on the previously-stuck subclass at equal or better rhat profile;
  - If F-9 FAILED (adaptation-not-init verdict recorded): primary = stuck recovery itself, same
    gate shape as F-9(a): blr+kidscore all-chain R-hat < 1.01 AND ESS_bulk/draw ≥ 0.1;
  - universal: no model regresses >10% ESS/s; wall not worse than +5% (chopping is O(1) per
    window, batching reduces per-micro-step work — wall should be flat-to-better).
- **Mechanism check (diagnostic):** per-window inv_mass dispersion across chains
  (AdaptResult.log_mass_dispersion analogue — the hook the walnutpie lane added) trending down
  over warmup; Var_score floor firing rate < 5% of coordinates by mid-warmup (a higher rate
  means the clip is fighting a real tail, flag for review).

---

## B.3 Design 3 — Step-size target (delta) re-tuning sweep for the FUSED regime

**Surface:** existing knobs only — `NutsConfig.delta` (nuts.hpp:27) → DA target
(nuts.cpp:60, stepsize_adaptation.hpp:63), `max_depth` (nuts.hpp:31, nuts.cpp:61). CLI:
`--delta` / `--max-depth` (tools/stanli_run.cpp:128-131); C API: capi.h:87-88/108-109.
**Zero code change. Pure campaign.**

### Mechanism and interaction hypothesis

`delta` sets the DA equilibrium: higher target → smaller step → longer (deeper) trajectories →
more leapfrogs per transition. In stock Stan the cost of extra leapfrogs is linear in the
dominant per-gradient cost. The fused tier changes that arithmetic:

- per-gradient cost is 2.2-8x cheaper (F-7 census; esnc 8.15x, arma11 5.47x, hier_2pl 2.20x) and
  on esnc-class models gradients are only 6.7-14% of wall (F-4b) — i.e. **extra leapfrogs are
  nearly free relative to the fixed per-transition bookkeeping**;
- therefore the ESS/s optimum should shift toward *higher* accept targets (0.85-0.95) and/or the
  surface should flatten (a wider plateau of acceptable deltas), because the usual penalty for
  pushing delta up (paying more gradients for robustness) has shrunk;
- symmetric caveat: on bandwidth/libm-bound models (diamonds 0.85x, kronecker linalg-bound) the
  gradient cost did NOT drop much, so the shift should be weak there — a per-family read is the
  point, not just the geomean;
- treedepth cap ablation pairs with this: kronecker_gp sat at 99.5% td-hits at maxdepth=10 in
  Phase 0 (its ESS 944/4000 was treedepth-capped); higher delta lowers step size and raises
  treedepth demand, making the cap bind earlier — the two knobs must be swept together on the
  deep-tree models. (NUTS folklore "0.8 is not universally optimal" is the PITCH Phase-3
  pre-registration this executes, now in the fused regime it was never tuned for.)

### Campaign specification (pre-registration-shaped)

- **Arms:** delta ∈ {0.5, 0.7, 0.8 (reference), 0.9, 0.95} × max_depth = 10 (full grid), plus
  depth arms {8, 12} at delta ∈ {0.8, best-delta} — the depth ablation is a nested sub-grid so
  the campaign stays affordable: 5 + 4 = 9 NUTS arms.
- **Interaction control arm:** CmdStan default NUTS at the same delta grid (5 arms) — separates
  "the optimum moved because of fusion" (interaction) from "0.8 was never optimal on these
  models" (main effect). This is the difference between a tuning note and a result.
- **Models:** phase-1 six (esnc, esc, blr, pilots, kidscore, logmesq) immediately; phase-2 seven
  (radon_pp, radon_var_slope, bym2, hier_2pl, lsat, diamonds, arma11) on the F-7 fused build
  (fortk/t2-coverage @ external/stanli-f7) once F-8 phase 2 unblocks; kronecker_gp added to the
  depth sub-grid only (its cost makes the full grid wasteful).
- **Protocol:** 4 chains × 1000 warmup + 1000 draws, seeds 20260826+1000·rep+c, 3 reps, MEDIAN
  per metric, arms interleaved within rep (F-8 amendment convention), load recorded per rep,
  ≤4 concurrent processes (lane resource policy).
- **Metrics per model × arm:** ESS_bulk/s (primary), ESS_bulk/grad (the mechanism metric —
  higher-delta arms must show it rising if the hypothesis is right), ESS_bulk/draw (sanity: a
  speed win that silently loses ESS is NOT a win — F-8's rule), divergence rate, max-treedepth
  hit rate, wall.
- **Binary/feeding:** runs on whichever fused tool build F-8 phase 2 uses (same binary across
  arms — deltas are CLI flags, so one build serves all arms; that is the beauty of this design).

### Expected effect (evidence)

- F-8 phase 1: fused C-arm won everywhere at default delta — the sweep asks how much was left
  on the table. F-4b's cost flip is the mechanistic prior for "optimum shifts up".
- esc divergence note: CmdStan 43/1k divergences vs 14 for stanli arms at matched delta —
  adaptation-internals already differ between stacks; the CmdStan control arm also doubles as a
  divergence-rate comparison across delta.
- Prior expectation (falsifiable, state before running): fused tier's ESS/s-optimal delta ≥
  CmdStan's on the dispatch-bound class (esnc/blr/logmesq), roughly equal on bandwidth-bound
  (diamonds); ESS/grad monotonically improving in delta up to 0.9-0.95 on the cheap-gradient
  class; pilots (the pathology) improves in delta the way CmdStan users already know
  (delta 0.95-0.99 is the standard manual fix) — quantifying that cost curve in the fused regime
  is itself a deliverable.

### Risk / failure modes

- None to code. Measurement risks: load contention (interleave + record; medians), stale-binary
  traps (F-19-style mtime lesson — one build, verified once), rep variance on marginal models
  (W-16 lesson: single-rep comparisons are noise; 3-rep medians only, and hier_2pl-class
  conclusions need rep-for-rep tracking).
- Interpretation risks: delta and divergence-rate trade against ESS in ways the geomean hides —
  the per-model table with divergence columns is the artifact, not just the aggregate; treedepth
  saturation masquerading as convergence (report td-hit rate everywhere).

### Pre-registration-ready gate proposal

- **Recommendation rule (decide before looking):** adopt a new default delta* for the fused tier
  iff (i) geo ESS/s improves ≥ 3% over delta=0.8 AND (ii) no model loses > 10% ESS/s AND
  (iii) divergence count does not increase on any model AND (iv) td-hit rate at delta* ≤ 5% on
  all non-kronecker models. Depth default changes only if td-hit > 5% at baseline and the depth
  arm recovers it without violating (i)-(iii).
- **Correctness invariants:** trivially satisfied (no code change) but include the standard
  sanity: ESS/draw within ±20% of the delta=0.8 reference on healthy models (a delta that
  inflates ESS/s by crashing ESS/draw is flagged, not adopted — F-8's cross-arm comparability
  check).
- **Perf gates:** the recommendation rule above IS the gate; plus the interaction finding
  (fused-vs-CmdStan optimal-delta difference) reported with per-family breakdown regardless of
  adoption (negative result still writes the "0.8 fine everywhere in fused tier" note and closes
  the question).

---

## C. Recommended sequencing

Constraints in force (WORKLOG, 2026-08-26): F-9's campaign is running (its pinned worktree
symlinks `deps/stan`); F-8 phase 2 is queued behind F-9 (core/timing contention); **F-10
(sampler-loop package) waits for F-9 because deps/stan is shared**; 4-core discipline caps
concurrent measurement work; agents are active in `external/stanli` and `external/stanli-f7`.

**Order: Design 3 → Design 2 → Design 1.**

1. **Design 3 first (can start as soon as measurement slots open).** Zero code, zero tree
   conflicts, one binary serves all arms. It can run phase-1 (esnc-class) even while F-9
   finishes, interleaved under the load-recording protocol, or immediately after — its phase-2
   legs naturally ride F-8 phase 2's unblocked slot and build. It also produces the *baseline
   curves* (ESS/grad vs delta) that Designs 1-2's campaigns will be judged against — running it
   first removes a confound from every later comparison (mass-matrix changes shift the optimal
   step size; you want the delta-response surface measured before and after, not discovered
   after).
2. **Design 2 second, gated on F-9's verdict, in parallel with F-10.** It touches only
   `runtime/third_party/walnutpie` + `runtime/src/walnuts.cpp` + capi — **no deps/stan conflict
   with F-10**, so it can be implemented while F-10 lands. Its arm set and primary gate are
   *chosen by* F-9's outcome (stuck-recovery vs ESS/grad polish — see B.2), so design work now,
   campaign after F-9 reports. Porting from the walnutpie-lane fork keeps implementation cost low.
3. **Design 1 last, behind F-10.** Same vendored submodule (deps/stan) as F-10's base_nuts.hpp
   scratch-hoist; the lane's one-coherent-patch-per-branch discipline and the symlink sharing
   mean F-11.1 queues after F-10 lands (or shares F-10's branch mechanics as a separate commit,
   never mixed). It is also the change with the weakest local evidence and the only one that
   cannot default to bit-identity, so it benefits from the matured campaign harness anyway.

**Composition with F-10 + F-9 — the "stupidly good" stack, each layer independently evidenced:**

| Layer | Item | Evidence already on file |
|---|---|---|
| Init | F-9 pf-init (fused, `--init pf`) | walnutpie W-5 (ESS 25.8→295.8), W-7 no-crossover; stanli-arm verdict pending |
| Sampler loop | F-10 alloc-free loop (2a scratch-hoist + W-20 endpoint-grad threading + mallopt) | Phase-2a recon (~630 allocs/transition), W-20 (exactly 1 redundant grad/iteration), F-2b mallopt (300+ µs on alloc-heavy) |
| Mass matrix | F-11.1 (NUTS LW-shrink) / F-11.2 (walnuts chop+robust scores) | Fisher-HMC 1.3x diag median; W-6 chop wins; W-4 degeneracy diagnosis |
| Knobs | F-11.3 delta*/depth* re-tune for the fused regime | F-4b cost-flip mechanism; this campaign |

Composition rule (the lane's established doctrine): each layer ships default-off or
default-preserving and is gated independently; the stack is then measured as ONE combined arm
(the natural F-8-phase-3/capstone table: {A cmdstan, C fused, C+stack, D_pf+stack}) with
multiplicative-attribution checks (if the combined arm underperforms the sum of parts, the
interaction is the finding). Expectation set by arithmetic: C-arm 3.15x (F-8) × F-10's loop win
× F-11's metric/knob wins — each expected in the 1.05-1.3x family locally, none assumed, all
measured — against a D_pf arm that, if F-9 passes, competes for the default on the
dispatch-bound class where its census draw-rate was 2.8x fused nuts (F-4b).

---

## D. What NOT to do (recorded negative results that constrain these designs)

1. **Matrix-geometry optimizers (Aurora, Muon, NS variants, Shampoo/SOAP/K-FAC) for either
   adaptation loop — SETTLED, do not revisit.** Aurora is tall-2-D-only and degenerate below 2-D
   like Muon (research_aurora.md; WORKLOG 2026-08-21: "Aurora/OKLS/CM are matrix-geometry-bound,
   structurally MORE inapplicable to scalar/diagonal than Muon"). The polar factor of a scalar is
   its sign; of a diagonal vector, per-coordinate normalization — which destroys the scale
   information the metric exists to capture.
2. **Basis-extraction rules for richer metrics (W-19).** svd/power/muon/muoneq all within rep
   noise; basis is not the bottleneck. Closes "Muon-in-a-sampler" empirically.
3. **Low-rank / full-operator metrics as a DEFAULT (W-8/W-9/W-10).** Fold≈rec under good inits;
   rank hurts funnels (eight_schools_centered 0.19x); screening (metric-auto 0.5) is the only
   defensible shape, and it stays opt-in. F-11 deliberately stays diagonal.
4. **Dense metric at d~7000.** O(d²)-O(d³) refresh; infeasible (research_sota §4 rejected list).
5. **Fixing stuck chains with adaptation budget or trajectory length (W-3, W-7).** Longer orbits
   and 4-6x warmup do not unlock scale-locked chains (absorbing states; stock@4000 ≪ full@1000).
   The lever ordering is init distance → estimator robustness → everything else.
6. **Funnel class = mode-lock, not adaptation (W-14, W-11).** No warmup-config stack rescues
   single-chain scale/mode lock; needs draw screening at reinit or in-sampler multimodality
   handling. F-11 must not promise funnel fixes; it can only avoid making funnels worse
   (divergence gates in B.1/B.2 exist for this).
7. **Mass-estimator patches ALONE as the walnutpie fix (W-2).** Shrink/floor did not move
   rhat-bad beyond batching (9→9); metric drift guard, mass combine power, and stall/reset were
   all NEGATIVE (W-4 steps 1-3). Design 2 bundles only the pieces with a positive isolated record
   (chop: W-6; batching: W-1) plus the robust-score fix aimed at the diagnosed degeneracy.
8. **Optimizer-swap fantasies for the step loop:** AdEMAMix (slow EMA mismatches nonstationary
   target), AMSGrad (ratchet anti-tracking), Lion (fixed-magnitude oscillation), Sophia, CAME,
   schedule-free wholesale, hypergradient/SPSA/BOCPD/Kalman variants — all rejected with reasons
   in research_sota/pass2 rejected-idea lists. Dual-averaging-vs-Adam is a settled wash once
   clipped/averaged/batched (W-1's actual finding: batching was the fix, optimizer choice
   second-order).
9. **Mass-gated early exit (W-21/W-22).** The late-warmup drift signal is the STEP (hier_2pl
   step +169% vs invm +13%), not the mass — any warmup-length work gates on step stabilization.
10. **SIMD/kernel polish on small models (F-4b), --Oexperimental (Phase 0), march flags
    (Phase 2c).** Closed with data; the sampler loop and adaptation are what's left.
11. **Bit-identity expectations for fused-tier sampling or any estimator change (F-4 gate-(c)
    doctrine).** Last-bit drift amplifies chaotically in NUTS; statistical-equivalence class
    only. Bit-identity gates are reserved for order-preserving refactors (the lw_off arm in
    B.1, the all-off arm in B.2).
12. **Do not treat nutpie's "2x from mass matrix" as settled.** Our Phase-0 quality-adjusted
    decomposition (ESS/s 0.98x geomean) contradicts the headline locally; Fisher-HMC's 1.3x
    diagonal median is the defensible external prior. Design 1's gate is sized accordingly.

---

## Summary

F-11 = three adaptation upgrades for the fortk fork: (1) data-dependent LW-style shrinkage of
the NUTS window variance in vendored `deps/stan` var_adaptation.hpp:27-28 (queued behind F-10;
bit-identity-gated refactor, statistical gates for active arms); (2) a walnutpie-MassEstimator
upgrade in `runtime/third_party/walnutpie` (chop windows + robust/floored Var_score + optional
batching/shrink, ported from the evidenced walnutpie-lane fork; no deps/stan conflict; gated on
F-9's verdict); (3) a zero-code delta × treedepth sweep for the fused NUTS regime with a
CmdStan interaction control (runs first). Sequencing: 3 → 2 ∥ F-10 → 1, composing with F-9
(pf-init) and F-10 (alloc-free loop) into the independently-gated "stupidly good" stack.
