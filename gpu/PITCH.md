# absin — desynchronized, trustworthy NUTS on accelerators

absin3 = Sumerian "seed furrow." Parallel furrows across a field = parallel
Markov chains across a GPU. This lane builds on the FSM-MCMC result (ICML
2025), closes its correctness gap, extends its performance frontier, and —
as a stretch — adds a Lean 4 verified-rewrite layer so agents can mutate
sampler structure without silently breaking invariance.

You are an autonomous agent picking up this brief. You know nothing from any
prior conversation. Work phase by phase; append everything to `WORKLOG.md`
in this directory.

---

## Context

The paper: Dance, Glaser, Orbanz, Adams, "Efficiently Vectorized MCMC on
Modern Accelerators," ICML 2025 (arXiv:2503.17405). Code:
github.com/hwdance/jax-fsm-mcmc (JAX; our substrate).

Problem it solves: `vmap` over a sampler whose `sample` contains a while
loop (NUTS, slice, delayed rejection) forces all chains into lockstep —
every chain waits for the deepest tree. Cost ∝ Σ_i max_j N_ij instead of
max_j Σ_i N_ij. Their fix: decompose `sample` into code blocks at while-loop
boundaries; a per-chain finite state machine (NUTS becomes 5 states: init,
double, integrate, check, done) advanced by a single `vmap`ed `step`
dispatched via `lax.switch`; loops only synchronize after all n samples.

Their measured NUTS results (ESS/sec, 128 chains, 1000 samples): 3.15x vs
BlackJAX on Real-Estate GPR, 2.43x on posteriorDB "Soil", **0.91x (a slight
loss) on posteriorDB "Pilots"** — the cheap-log-density regime where the
FSM's all-branches-per-step overhead (vmap executes every switch branch,
masked) outweighs desynchronization.

The two gaps this project owns:

1. **Correctness gap.** Equivalence to reference NUTS is argued "by
   construction" (same blocks, same order, RNG state carried in z) and
   validated only by side-by-side ESS comparisons on 3 problems. No draw-
   level verification, no property-based testing, no check that the
   construction survived implementation and JAX version drift.
2. **Performance gap.** The 0.91x regime; state-granularity design; logp
   amortization; scaling in number of chains.

North-star metrics: (a) ESS/sec vs BlackJAX vectorized and numpyro at equal
chain counts on a frozen target suite; (b) an equivalence report classifying
every claim by evidence class: bitwise / statistical / property / none.

Environment: WSL2, RTX 5090 32GB (Blackwell), `uv`, Python. **FP64 on the
5090 runs at ~1/64 rate: correctness-critical equivalence runs go in FP64 on
CPU; GPU perf work runs FP32 with explicitly recalibrated divergence
thresholds; measure both, label which is which.** Pin and record JAX + CUDA
versions on day one; JAX version drift vs the paper's code is expected —
your first job is archaeology, not innovation.

---

## Phase 0 — Reproduce

- Clone jax-fsm-mcmc; make their NUTS experiments run: Real-Estate GPR,
  posteriorDB Soil, posteriorDB Pilots (Table 2 of the paper).
- Reproduce direction and rough magnitude (3.15x / 2.43x / 0.91x). Exact
  numbers will differ (different GPU); document deltas and any code changes
  needed for modern JAX.
- Freeze a target suite in `gpu/CORE_SET.md` (their 3 + Neal's funnel +
  Stock–Watson stochastic volatility + a hierarchical model + one
  intentionally multiscale/funnel-ish target). Never edit after Phase 1
  starts.

DoD: reproduction table in WORKLOG; one-command rerun of the suite.

## Phase 1 — Equivalence harness (the contribution the authors would want)

1. **Bitwise draw alignment.** Same seed, same model, FSM-NUTS vs BlackJAX
   NUTS, per-chain RNG streams aligned: do the draws match bit-for-bit? If
   yes: strongest possible equivalence evidence for the construction. If
   no: bisect where the RNG consumption order diverges; classify each
   divergence as benign (different but valid stream usage) or real
   (different transition kernel). Expect this to be the subtlest part of
   the whole project — the FSM reorders *when* randomness is drawn relative
   to loop scheduling.
2. **Statistical battery** (where bitwise fails or is impossible): 100 seed
   pairs; KS on marginals, ESS ratio distributions, divergence rates,
   rank-normalized R-hat behavior on the target suite.
3. **Property tests** (sampler-level, substrate-independent):
   - Reversibility round-trip of the integrator map (forward L, flip
     momentum, back L; recovery within tolerance — FP32 AND FP64 policies).
   - Volume preservation: numerical Jacobian det of the L-step map, small d.
   - π-invariance on analytic targets: isotropic/affine Gaussians, funnel;
     moment coverage, divergence profiles.
   - Negative control: deliberately break one branch (e.g. skip a U-turn
     check); prove the battery detects it. A harness that can't fail is
     decoration.

DoD: `gpu/EQUIVALENCE_REPORT.md` — every claim labeled with evidence class,
including honest "none" rows. This document is valuable even if everything
downstream fails.

## Phase 2 — Performance frontier

Attack the measured gaps, in this order:

1. **Cheap-logp regime (the 0.91x).** Per-step cost is the sum of all
   branches because vmap runs everything masked. Candidate: homogeneous-batch
   fast path — detect when all chains are in the same state (cheap max/min
   reduce over state ids) and dispatch the single relevant block via
   `lax.cond`, falling back to the switch otherwise. During trajectory
   integration (where NUTS spends most steps) chains are frequently
   homogeneous; this recovers most of the all-branches tax exactly where it
   hurts. (This is a scheduling optimization: kernel semantics unchanged —
   verify with the Phase 1 battery.)
2. **State granularity.** Paper's own theory says per-step cost scales with
   number of states and imbalance of block costs. Try merged states (e.g.
   init+double), split CHECK, per-subtree integrate states; measure against
   their E(m) vs R(m) model.
3. **Amortized logp.** They cache expensive g = logp across states; extend
   (keyed by state-value hashing? per-chain valid flags?) and measure at
   m ∈ {64, 256, 1024, 4096} chains on the 5090 (32GB — watch memory at 4096
   chains × tree bookkeeping; report the ceiling).
4. **FP32/FP64 study.** Divergence-threshold recalibration under FP32
   energy-error inflation; does FP32 + recalibrated threshold shift ESS/grad
   or divergence rates materially on funnel-ish targets? Document a sane
   default.

DoD: ESS/sec vs chains curves for FSM, FSM+fast-path, BlackJAX, numpyro on
the frozen suite; Pilots-regime no longer a regression.

## Phase 3 (stretch, timeboxed) — Lean 4 verified integrator rewrites

The formal-verification layer from the original idea. Scope honestly: this
is research-grade work; timebox it; the Phase 1 property harness is the
pragmatic fallback gate and stays authoritative regardless.

- Tool-choice note (decided, don't relitigate per session): Lean 4 over
  Isabelle/HOL and Coq/Rocq for this lane because (a) proof-carrying
  rule structures want dependent types, (b) Mathlib has the needed real
  analysis (Jacobians, change of variables, `MeasurePreserving`) plus a
  fast-moving probability layer (s-finite kernels, disintegration,
  Ionescu-Tulcea as of 2025), (c) strongest LLM proof-automation tooling,
  which matters when agents write proofs. If the scope ever shifts to
  kernel-level detailed-balance theorems ("this kernel preserves π"),
  Isabelle/HOL has the deeper measure-theoretic library (Hölzl, Eberl's
  verified density compiler, PPV quasi-Borel) — flag it in WORKLOG and
  ask before switching provers. Known Mathlib gap to budget for: no
  developed theory of invariant/reversible Markov kernels — reversibility
  must be defined from kernel symmetry primitives yourself.
- Small integrator DSL in Lean 4 over Mathlib. Rewrite rules as structures
  carrying proofs — architecture modeled on lambdaclass/supertensor_lean
  (`SoundTensorRule` has `sound : ∀ env, lhs.eval env = rhs.eval env`;
  ours: `reversible : IsReversal R R⁻¹` and `volume_preserving :
  MeasurePreserving R` as fields — an unsound rewrite cannot be constructed).
- Target rules (in order): plain leapfrog; leapfrog with diagonal metric
  (shear-map argument, unit-determinant triangular Jacobians); implicit
  midpoint; WALNUTS-style dyadic micro-step schedule on a fixed macro grid
  (arXiv:2506.18746 — their paper's whole math section is exactly this
  proof done by hand; mechanizing even a simplified version is novel).
- Codegen the verified schedule to JAX, plug into the FSM integrator state,
  benchmark ESS/grad on funnel + stochvol vs plain leapfrog.
- Rules: zero `sorry` in anything labeled verified; anything unproven ships
  as property-harness-gated instead, explicitly labeled.

Kill criterion: if after the timebox fewer than 2 rules are fully proven,
archive under `gpu/lean/ATTIC.md` with a honest friction log (which Mathlib
gaps hurt — expect change-of-variables and matrix-det ergonomics) and
continue without it.

## Phase 4 — Open discovery lane

With Phases 1–2 in place, run a mutation loop: agents propose structural
sampler variants (momentum persistence/partial refresh, generalized HMC,
alternative tree-sampling weights within valid progressive-sampling
schemes, multinomial-vs-slice variants), each must pass the property battery
before benchmarking, then rank by ESS/grad and ESS/sec on the frozen suite.

Anti-gaming rules (this is benchmark work; expect metric gaming):
- A variant only counts if it also passes moment-coverage tests on analytic
  targets at multiple dimensions and ≥5 seeds.
- Record the nearest known prior for every "novel" variant; a rediscovery is
  a validation, not a discovery — label it as such.
- Any variant whose win disappears under a different divergence threshold or
  FP mode is flagged fragile in the results table.

DoD: `gpu/DISCOVERY.md` — ranked variants with evidence classes and failure
galleries. Even an all-fail gallery is a publishable artifact.

## Guardrails

- Perf claims: median of ≥5 runs, pinned seeds, pinned versions, hardware
  recorded. No bar charts without the table behind them.
- Correctness claims: always labeled with evidence class; never say
  "equivalent" when you mean "statistically indistinguishable so far."
- JAX/CUDA version pinned and recorded; any version bump re-runs Phase 0.
- Don't fork-and-drift: performance improvements with clean semantics go
  upstream to hwdance/jax-fsm-mcmc as PRs (check their LICENSE and norms
  first).

## References

- Dance, Glaser, Orbanz, Adams 2025, ICML — arXiv:2503.17405; code
  github.com/hwdance/jax-fsm-mcmc (read Appendix B: automated FSM
  construction; Appendix B.4: their implementation details, incl. the
  scan-of-100-steps runtime and amortization caveats)
- BlackJAX (github.com/blackjax-devs/blackjax) — reference NUTS
- NumPyro (github.com/pyro-ppl/numpyro) — chain_method='vectorized' baseline
- Hoffman & Gelman 2014 (arXiv:1111.4246); Betancourt 2017
  (arXiv:1701.02434) — NUTS semantics, multinomial progressive sampling
- WALNUTS: arXiv:2506.18746, code github.com/bob-carpenter/walnuts —
  within-orbit adaptive step size; reversibility proof to mechanize
- supertensor_lean (github.com/lambdaclass/supertensor_lean) — Lean 4
  verified-rewrite architecture to copy; SciLean (github.com/lecopivo/SciLean)
- Gimlet Labs, "Formally Verifying AI-Generated GPU Kernels" (Z3 equivalence
  checking, bounded translation validation) — the translation-validation
  pattern Phase 1 mirrors
- posteriorDB: github.com/stan-dev/posteriordb (Soil, Pilots models)
