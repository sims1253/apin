# W-76 DESIGN — two-phase warmup for walnutpie (design only; no code, no builds)

Date: 2026-08-25. Repo: `external/walnutpie`, branch `exp/safe-adapt-defaults`
(@43b6435). All line numbers verified against this checkout.

Status: DESIGN DOCUMENT. Nothing here has been built or run. This is the last
queued research lead; everything adjacent has been measured and rejected
(W-21/W-25/W-28/W-37 early-exit gates, W-38-E1/E2/E4 fewer-gradients pack,
W-45 subsample transplant). Honest ceiling assessment is the point of this
document, not enthusiasm.

Literature leads on file:

- arXiv:2603.22741 — warm-start via non-Metropolized HMC (unadjusted Phase A,
  corrected Phase B).
- arXiv:2601.16696 (LAPS) — unadjusted warmup phase with a bias-to-step-size
  conversion at the phase boundary.

Prior results this design must survive contact with (all read before writing):

- `results/subsampled_warmup_w45.md` — REJECTED transplant; §6 sketches exactly
  one sanctioned follow-up shape (cheap Phase A + truncated full-data Phase B)
  and predicts a "modest ceiling".
- WORKLOG W-38-E2 close-out (~line 3538): loosening warmup error discipline
  (schedule cap, constant cap, halvings cap) REJECTED on quality AND speed.
- WORKLOG W-37 close-out (~line 3828): four independent early-exit gates
  closed; "warmup length stays fixed".

---

## 1. What exists today

### 1.1 The drift phase, precisely

`AdaptiveWalnuts::operator()` (include/walnutpie/adaptive_walnuts.hpp) opens
with:

```cpp
const bool drifting = iteration_ < warmup_cfg_.get().drift_iters();   // :622
```

`WarmupConfig::drift_iters_` defaults to **0** (config.hpp:798); the CLI
exposes it as `--drift-iters` with default 0 (examples/stan_cli.cpp:823 and
:1090-1095). So on the default path `drifting` is always false and every code
path below is dead.

While `drifting` is true, five suspensions engage simultaneously:

| # | Suspension | Where | Effect |
|---|---|---|---|
| 1 | Identity metric | adaptive_walnuts.hpp:636 (`drifting ? Eigen::VectorXd::Ones(theta_.size()) : ...`) | transition integrates under inv_mass = 1 regardless of the estimator |
| 2 | Infinite error cap | :654-655 (low-rank path), :687-689 (diagonal path): `drifting ? std::numeric_limits<double>::infinity() : effective_max_error()` | the existing max-error schedule (`effective_max_error()`, :608-619; config fields config.hpp:803-804, builder :1048-1052) is bypassed entirely |
| 3 | No-op step adapter | :694-703: a stack-local `detail::NoOpStepSizeAdapter drift_noop` (walnuts.hpp:818-833) replaces `opt_` in the transition call | `opt_.step_size()` stays at its initialization value for the whole window; no acceptance statistic is consumed |
| 4 | Metric estimation suspended | :666-667 (low-rank) / :719-723 (diagonal): `mass_estimator_.observe(...)` skipped when drifting; low-rank refresh also gated on `!drifting` (:624-627); window chopping/reset likewise (:729-733) | draws from the drift window never reach the MassEstimator |
| 5 | (partial) min-micro NOT suspended | :736: `min_micro_estimator_.observe(1 << depth)` runs **unconditionally**, including during drift | see risk in §3.5 |

The in-code rationale (comments at :684-694, :719-722) records the failure
modes these suspensions were built against: a distant initialization cannot
satisfy any tight cap (every macro step rejected → chain pinned), and feeding
the step adapter saturated alphas drives the macro step toward zero and
freezes the chain when drift ends. The MassEstimator additionally carries
defenses that exist *because* poisoned draws were a diagnosed problem: the
stall detector (adaptive_walnuts.hpp:103-121), `reset_to_seeds()` (:127-133),
the logspace drift guard (:267-275), and shrinkage regularization
(mass_shrink_kappa, :276-291).

### 1.2 What a drift iteration actually costs (mechanics, from walnuts.hpp)

With `max_error = inf` and default `min_micro_steps = 1` (config.hpp:1336):

- `macro_step` (walnuts.hpp:310-356) tries `num_steps = min_micro_steps = 1`
  first; the tolerance test at :350 passes trivially; `reversible()`
  (walnuts.hpp:256-281) returns true immediately for `num_steps == 1`
  (:263-265). **The dyadic halving ladder never runs** — each leaf costs
  exactly `min_micro_steps` gradient evaluations.
- Trees therefore grow until U-turn or `max_trajectory_doublings = 5`
  (config.hpp:1333), i.e. up to ~31 evals/iteration — comparable to adapted
  iterations on hier_2pl (~20 evals/iter, W-38-E1 accounting).
- Selection inside the tree is Barker (walnuts.hpp:504), across doublings
  Metropolis (:589), both computed on wildly wrong energies — the selected
  position is transported by raw leapfrog dynamics whose acceptance
  statistics are meaningless by construction.
- The step used during drift is the **initialization** step size
  (`opt_.step_size()`, untouched because of #3).

### 1.3 What limits it

Today's drift is pure transport with zero learning: identity mass, frozen
initial step size, no estimator contact, draws declared invalid ("not drawn
from a Markov chain and ... not valid for inference", adaptive_walnuts.hpp
docstring at :594). It moves the chain toward the typical set under an
identity metric — useful exactly while gradients are huge and nothing else
can work, useless as soon as curvature matters. It buys robustness (W-41/W-43
pin family), not speed: iterations cost the same order as adapted ones, and
whatever the chain learns about geometry during drift is thrown away.

---

## 2. Design proposals, ranked

Env-gating pattern (house style, both precedents verified):

- `WALNUTPIE_MINMICRO_DECAY` (WORKLOG ~7868): single static env read;
  empty/unset = exact current behavior; branch only when the value is active.
- `WALNUTPIE_PARTIAL_REFRESH_ALPHA` (WORKLOG ~6789, 6975): env-only, **no CLI
  wiring**, unset = bit-identical, canary-verified.

Rule adopted here: all knobs below are env-read-once, default off, no CLI
flag, no config-schema change unless explicitly noted. Default-path
bit-identity argument per proposal in §2.5.

### 2.0 First, two ideas that are already closed (do not propose them)

**(i) "Raise the max-error schedule during warmup."** Measured, REJECTED:
W-38-E2 arm e2a used the EXISTING `--max-error-start/--max-error-iters` knob
(5.0 → 0.5 over 950 iters) and arm e2c a constant loose warmup cap — all arms
failed the pre-registered quality band (marginal class, small margins) and
the ≥10% call-reduction bar (hier_2pl −6.5/−7.7% vs the 18.2% E1 ceiling;
kronecker_gp +118/+162% calls, walls ~2–2.4x — a loose cap admits long
high-error trajectories). The measured mechanism lesson: harvested tolerance
failures double as a trajectory-growth limiter.

**(ii) "Skip the dyadic tolerance check during drift."** Vacuous, per §1.2:
under the infinite cap with `min_micro_steps = 1`, the ladder never executes
and `reversible()` short-circuits at num_steps == 1. There is nothing to skip.
This closes the literal "skip dyadic tolerance during drift" variant of
proposal (a).

What remains genuinely untested is the *drift-phase* combination: today's
suspensions (#1–#4 above) mean no experiment has ever run unadjusted dynamics
WITH a growing step size and a boundary handoff, because the current drift
freezes the step at its initialization value and discards everything. That is
the sliver proposals A/B occupy.

### 2.1 Proposal A (rank 1): productive drift — LAPS-style unadjusted Phase A with a bias→step-size handoff

Keep the existing drift machinery exactly as suspended today (identity metric,
no estimator feeding, no live adapter) and add two env-gated behaviors:

**A1 — drift-phase step schedule.** During drift, integrate at
`step_scale × opt_.step_size()` where `step_scale` grows geometrically across
the drift window (or is constant, single knob). Touch points:

- adaptive_walnuts.hpp:697-703 — the drifting branch currently passes
  `opt_.step_size()`; wrap with the scaled value. One expression, inside the
  existing `if (drifting)` branch.
- New private member initialized once from `std::getenv("WALNUTPIE_DRIFT_STEP_SCALE")`
  (empty ⇒ scale ≡ 1.0 ⇒ the multiplied value is bit-identical to today's
  argument).

Rationale (LAPS lead): the unadjusted phase tolerates bias; what it needs is
aggressive transport, which today's frozen init step does not deliver. The
infinite cap already guarantees the step is never the binding constraint
during drift (§1.2), so scaling cannot cause rejections/pins — worst case is
divergent flight, bounded by the depth cap and U-turn checks.

**A2 — bias→step-size conversion at the boundary.** Accumulate the Phase-A
terminal |ΔH| stream (already computed inside macro_step but currently
discarded under NoOp; cheapest correct hook: accumulate `|logp − logp_next|`
per accepted macro attempt via a tiny accumulator member threaded alongside
`drift_noop`, or reuse the observed depth/alpha if a debug hook exists —
implementation must add NO gradient evaluations). At the drift→adapt
boundary (`iteration_ == drift_iters_`, first non-drifting pass through
operator()), feed the real adapter ONE synthetic acceptance statistic
`min_accept = exp(−median |ΔH|_phaseA)` instead of leaving Adam/DualAveraging
to start cold from the untouched init step. Touch points:

- adaptive_walnuts.hpp:705-713 (the else branch calls the transition with
  `opt_`): insert the one-shot boundary update immediately before the first
  non-drift transition.
- Gate: `WALNUTPIE_TWOPHASE_STEP_INIT` (empty = off = adapter starts exactly
  as today).

Rationale: comment :690-694 documents WHY the adapter must not be fed
*saturated* alphas during drift (step → 0 → freeze). The LAPS conversion is
the disciplined inverse: convert the measured bias scale into a *starting*
step, once, at the boundary — not a stream of garbage updates. This directly
addresses the known cliff at the drift→adapt transition.

**Cost model:** drift iterations already cost ≤ full adaptation iterations
(§1.2). Expected saving is NOT from cheaper Phase-A iterations; it is from
(a) faster typical-set approach allowing a shorter subsequent adaptation
ramp to reach the same estimator quality, and (b) eliminating the wasted
early post-drift iterations whose observes poison windows and trigger resets
(the reason chopping resets exist, :729-733).

### 2.2 Proposal B (rank 2): truncated Phase-B budget after a cheap full-data Phase A (the W-45 §6 "V3" shape, minus transplant)

Fix total warmup at 1000 (fixed-warmup guarantee untouched); reallocate
`drift_iters = D` + effectively shorten the *estimation-bearing* portion by
relying on Phase A for transport. Concretely: `D ∈ {100, 200}` with the
existing chopping-reset machinery (:729-733) guaranteeing the metric is
rebuilt from post-drift samples only; optionally pair with the shipped
`WALNUTPIE_MINMICRO_DECAY=0.99` so Phase-A depths (risk §3.5) do not leak
into the frozen min_micro_steps.

This is exactly the follow-up shape W-45 §6 sanctions, applied on FULL data
(no transplant ⇒ none of the measured failure mechanisms apply: no
per-component mass mis-scaling, no −1.2k..−1.9k logp position gap). Its
saving is bounded by W-45's own algebra: win ≤ (warmup_share × replaced
fraction) − (Phase B must be long enough for the OnlineMoments discount
schedule to converge from post-drift seeds) − sampling-phase inflation risk
(W-45 measured 1.2–1.9× sampling grad-call inflation whenever imported state
was even slightly off; here the imported state is only a POSITION reached by
biased-but-full-data dynamics, so the inflation risk is smaller but nonzero).

Ranked below A because alone it changes almost nothing: with `drift_iters >
0` today's drift is still frozen-step transport, so B without A mostly
renames iterations. B is the natural SECOND arm of the same experiment as A.

### 2.3 Proposal C (rank 3, measurement-first, zero behavior change): instrument the boundary before believing either proposal

Before any wall claim, measure what A/B would have to beat, using the
standing W-37 instrumentation pattern (env-gated, canary-clean): per-window
series of (a) Phase-A terminal |ΔH| distribution, (b) post-boundary steps-to-
stabilize of the adapter, (c) mass l2-rel-diff between "adapt-from-init" and
"drift-then-adapt" freeze states. If the adapter stabilizes within <100
iterations of the boundary anyway (plausible given discount memory
~mass_init_count + schedule), there is nothing for A2 to save and the whole
direction dies cheaply. This is the recommended FIRST commit of any W-76
session.

### 2.4 Explicitly out of scope

- Anything touching defaults (`drift_iters_` stays 0; error caps, adapters,
  estimator seeds unchanged when env unset).
- Any cross-chain-controller change (§3.4).
- Any .so/data-side lever (closed by W-45).
- Any early exit from warmup (closed by W-21/W-25/W-28/W-37).

### 2.5 Default-path bit-identity argument, per proposal

- A1/A2: all new computation sits behind `if (drifting)` (existing branch,
  adaptive_walnuts.hpp:622/:696) or behind an env-checked flag read once into
  a member; with env unset the added members are inert and the transition
  arguments are textually identical. The only unconditional additions are
  two/three member initializations. Canary protocol (W-38-E2 gate-a style):
  new-binary default-path CSVs md5-identical to build_w36exp @43b6435 across
  ≥3 models × 4 chains before anything else runs; plus an env-ON liveness
  probe (knob visibly changes drift trajectories; env-OFF re-check identical).
- B: no library change at all beyond A's gates (uses existing `--drift-iters`);
  the only new surface is the pairing with the already-shipped
  WALNUTPIE_MINMICRO_DECAY.
- C: instrumentation only, W-37 precedent (env-gated series, env-on/off
  bit-identical 8/8).

### 2.6 Expected wall saving vs priors — honest arithmetic

Priors on file: warmup share of total wall = 52.7% median over >1s models,
radon 77% (WORKLOG ~106); 65–76% in the W-21 measurement context (WORKLOG
~982); this grid's base stanzas arma11 0.53, lsat 0.52, hier_2pl 0.56, blr
0.69 (subsampled_warmup_w45.md §4).

Ceiling for the WHOLE direction (A+B together, optimistic):
`saving_total ≤ warmup_share × f_replaced × (1 − c_phaseA) − K_forget/N_B − inflation`,
where f_replaced is the fraction of warmup iterations made shorter-or-better,
c_phaseA the Phase-A cost ratio (≈1 per §1.2 — this is the binding pessimist),
K_forget the iterations Phase B needs for the discounted moments to forget
the boundary state, and inflation the W-45-style sampling-phase penalty.
Plugging in the best plausible numbers (share 0.55, f 0.2 effective, K_forget
~150 of 1000): gross ~8–12% of total wall; net after inflation risk, single
digits. W-45's verdict language applies verbatim: "the plausible ceiling is
modest". If Proposal C's measurements show the adapter self-stabilizes in
<100 iterations post-boundary, expected net saving rounds to zero and the
recommendation flips to no-go without running the grid.

---

## 3. Correctness risks

### 3.1 Phase-A draws feeding the MassEstimator

Documented as poisonous in-source (adaptive_walnuts.hpp:719-722: pinned/
throttled-chain draws "poison the variance estimates"; the entire stall-
detector subsystem :103-121 and reset_to_seeds :127-133 exist for the
self-locking failure mode tiny-metric → tiny-moves → tinier-metric).
Design rule: suspension #4 is NON-NEGOTIABLE in every variant. Phase-A
positions may be handed to Phase B; Phase-A statistics may not. Mitigation
for the boundary transient itself: the existing post-drift chopping reset
(:729-733) plus the logspace drift guard (:267-275) plus kappa-shrinkage
(:276-291) are exactly the mechanisms that make a dirty first hundred
post-boundary observes survivable; they stay on.

### 3.2 Feeding Phase-A statistics to the step adapter

The failure is documented at :690-694: saturated alphas drive the macro step
to zero and freeze the chain at drift end. A2's boundary handoff is designed
around this: ONE converted statistic (exp(−median |ΔH|)), not a stream.
Additional guard required by W-41's lesson (adapter NaN from a single inf/NaN
statistic at iteration 0): the accumulator must drop non-finite |ΔH| entries
before taking the median, and the handoff is skipped entirely if fewer than
a quorum (say 16) finite observations exist. Without this, a Phase-A divergent
flight converts to exp(−inf) = 0 → step collapse → the exact pin the drift
phase exists to prevent.

### 3.3 Metropolis correction at the phase boundary — explicitly NOT handled, with the bias argument

No importance weights, no rejection correction, no MH accept against the
target at the A→B switch. Argument: warmup draws are already outside any
asymptotic guarantee (adaptive_walnuts.hpp:594 declares them invalid for
inference); Phase A is an initialization procedure, not a sampler. Correctness
of the ESTIMATES rests entirely on Phase B being a genuine (Metropolis-
corrected, capped at `effective_max_error()`) kernel run long enough to mix
from the Phase-A endpoint before freeze. The residual bias decays as Phase B
mixes — that decay is an empirical quantity (rhat / ess_bulk_min at the
margin), which is precisely what the gates in §4 measure; it is not assumed.
If Phase B is truncated too far (Proposal B), the bias argument weakens
linearly in truncation — this is why B is ranked below A and gated harder.

### 3.4 Cross-chain controller and fixed-warmup interaction

- The controller (`adapt_with_stats`, adapt.hpp) consumes `on_warmup`
  callbacks (issued unconditionally at :677/:737, including during drift
  today) and its convergence criteria compare cross-chain step/mass state.
  During drift the step is CONSTANT (suspension #3), so cross-chain step
  agreement can look artificially converged inside the drift window.
  Protection already shipped: convergence-based exit is opt-in
  (`allow_early_exit_ = false`, config.hpp:810; rationale adapt.hpp:439-450,
  W-31), so with defaults the only stop is the max_iter budget — fixed-warmup
  guarantee intact. Design rule: two-phase work must NOT enable or modify
  `allow_early_exit`; the temporal gate's known marginal-class fragility
  (W-25: hier_2pl bulk 519→126) stays out of scope.
- Multi-chain + drift: verify (measurement item, Proposal C) that chains in
  differing drift progress do not trip the (dormant-by-default) criteria in
  any future controller experiment; record the interaction, change nothing.

### 3.5 min_micro leakage from Phase A (live bug-shaped hazard, exists TODAY with --drift-iters > 0)

:736 observes `1 << depth` unconditionally; drift trees are unadjusted and
reach depth up to 5 (§1.2), so enabling drift today inflates the lifetime
cumulative min_micro estimate — which then feeds BOTH remaining warmup and
the FROZEN sampler (sampler() passes
`min_micro_estimator_.min_micro_steps()`, :757) — permanently paying extra
gradient evals per macro step. This is the exact mechanism W-72's EWMA was
shipped against. Two-phase variants MUST either gate this observe during
drift (env-gated, part of A1's touch points) or pair with
WALNUTPIE_MINMICRO_DECAY=0.99. Unaddressed, it silently taxes the sampling
phase and can erase the entire warmup saving (W-45's inflation lesson,
library-internal edition).

### 3.6 Endpoint cache at the boundary

The cached (grad, logp) at theta_ remains valid across the phase switch
(same position, same target); `seed_endpoint_cache` (:769) semantics
unchanged. Low risk; listed for completeness because W-42 showed a stale/
inf cache is a real crash class — the boundary does not touch the cache.

---

## 4. Pre-registration draft (W-76)

**Expectation.** Phase A (drift with A1 scale + A2 handoff) reaches
typical-set neighborhoods in fewer effective estimation iterations than
adapt-from-init, and the adapter at the boundary starts within a factor ~2
of its eventually-stabilized step (vs arbitrarily far today). Net wall
saving expectation: MODEST — geomean −3..−8% total wall at best; central
expectation is below the adopt bar, consistent with the W-45 ceiling
analysis.

**Arms** (single overnight session, standard protocol: 10-model grid, 3 reps,
seeds 20260819+1000·rep+c, W-36 init assignment, 4 chains serialized,
CLI-default configs otherwise, binary from a fresh worktree off
exp/safe-adapt-defaults @43b6435):

- base (default binary, reference band)
- canary (new binary, env unset — must be md5-identical to base; GATE 0)
- C-instrumentation (env-on diagnostics only; draws must equal base)
- A1 (`WALNUTPIE_DRIFT_STEP_SCALE` schedule, drift 200) 
- A1+A2 (+`WALNUTPIE_TWOPHASE_STEP_INIT`)
- B (= A1+A2 with truncated estimation window / paired MINMICRO_DECAY=0.99)

**Gates (pre-registered, W-25/W-28/W-38-E2 band convention):**

0. CANARY: default-path draws md5-identical, all models/chains rep0; env-on
   liveness probe shows changed drift trajectories; env-off re-check
   identical. Fail ⇒ fix before any grid.
1. QUALITY (verdict-bearing): arviz rank-normalized ess_bulk_min /
   ess_tail_min + max rhat, medians of 3 reps. Arm PASSES iff, on ALL
   marginal-class models (arma11, lsat_model, hier_2pl) AND the aggregate:
   median ess_bulk_min ≥ min(base per-rep bulk), tail likewise, and
   median rhat_max ≤ max(base per-rep rhat). Aggregate health:
   geomean ess_bulk_geomean ≥ base − 3%. ANY pinned chain (identical draws)
   in an arm = automatic fail for that arm (W-43/W-45 signature).
2. SPEED: total wall and logp_grad calls/chain, medians of 3. Adopt-candidate
   requires ≥5% geomean wall reduction WITH gate 1 fully green and no model's
   ess_bulk_min dropping below half its base median (>2× collapse rule).
3. STATE (diagnostic, non-gating): frozen (step, inv_mass, min_micro) of A
   arms vs base at freeze — the W-45 transfer table format, to attribute any
   quality loss to step vs mass vs micro.

**Verdict rule:** ADOPT-candidate only if gates 0–2 all pass; TUNE (one
pre-declared re-run with adjusted scale/split) if quality passes and speed
misses; REJECT (direction closed, recorded) otherwise — same discipline as
W-38-E2/W-45. No second session without a new pre-registration.

**Cost estimate:** one fresh worktree + header-only edits (≤ ~60 lines behind
gates), one clean rebuild (header edit ⇒ clean-first per house protocol),
one serialized overnight grid (~10 models × 6 arms × 3 reps; fast models
dominate count, wall dominated by hier_2pl/kronecker_gp cells), analysis
reusing harness/w45 + harness/run_w37 patterns. Total ~1 session + analysis;
abandon-after-C exit available within ~2 hours of grid start if boundary
instrumentation shows nothing to save.

---

## 5. Recommendation — conditional go, narrowly scoped, expecting rejection

The honest picture:

- Four early-exit gates closed independently (W-21 fast-but-quality-
  destroying; W-25 static gate quality-destroying; W-28 pilot gate preserves
  quality only by never exiting; W-37 trajectory geometry not class-
  separating). WORKLOG's own close-out: "warmup length stays fixed."
- W-38-E2 measured-and-rejected the nearest neighbor to "loosen Phase A":
  error-discipline loosening failed quality on the marginal class AND failed
  to harvest calls (loose caps admit long trajectories). Any two-phase
  variant inherits this as prior evidence AGAINST.
- W-45 refuted state transplantation outright and measured that the only
  sanctioned remainder (its §6 V3 shape) has a modest ceiling with a known
  discount-forgetting floor and a 1.2–1.9× sampling-inflation hazard.

What is actually left untested is thin but real: the CURRENT drift phase has
never been made productive — frozen init step, discarded statistics, no
boundary handoff. Proposals A/C test exactly that sliver with contained blast
radius (Phase B still adapts fully from whatever Phase A hands over; defaults
untouched; fixed warmup untouched; controller untouched).

**Recommendation: GO for Proposal C (measurement-first instrumentation) +
one combined A/B grid under the §4 pre-registration, with the explicit
prior expectation of REJECT. Proceed only if gate 1+2 pass; treat a reject
here as closing the warmup-reduction program entirely** — after W-76 there
is no queued lead left, and the recorded mechanism table (what transferred,
what didn't, why) will be the deliverable either way. Do NOT proceed to
Proposal B standalone, to any default change, or to any second tuning
session on a fail.
