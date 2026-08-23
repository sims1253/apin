# Proposal pack — fewer gradient evaluations per effective draw in WALNUTS

Status: **PROPOSAL-ONLY** (W-37p). Read-only survey of walnutpie @
`exp/safe-adapt-defaults` (submodule worktree untouched), existing artifacts
only — no builds, no runs, no benchmarks (in flight). Every runtime question
below is written up as a designed experiment for a later agent. Source anchors
are `external/walnutpie/include/walnutpie/...` unless noted.

## 0. Problem statement and existing evidence

Per-call gradient cost is a stan-math problem (logp_grad = 81.6–99.4% of
program Ir; walnutpie-internal loop overhead 0.2–5.5% — W-29,
`results/hotspot_atlas_w29.md`). The other half of the lever: the sampler
could **evaluate logp_grad fewer times per effective draw**. On well-mixed
models walnutpie delivers 0.25–1.33x (median ~0.35x) cmdstan's ESS/grad
(`external/ess_per_grad_evidence.md`), and the evidence package attributes
the residual to "the within-orbit dyadic step-size search — design overhead,
not a defect", with two named candidate mitigations: **per-macro-step grad
accounting** and **position-keyed memoization**. The second is now closed
(W-20: zero accidental within-run position revisits; the only duplicate was
one per transition, eliminated by W-23 endpoint threading). This pack takes
the first seriously and enumerates what else the source admits.

Sampling-phase grads/draw from the w17g direct capture
(`results/w17g_grads.json`, median rep, 500 draws, recommended config):

| model | grads/draw | model | grads/draw |
|---|---|---|---|
| arma11 | 28.8 | hier_2pl | 469.0 |
| blr | 177.7 | kronecker_gp | 330.3 |
| diamonds | 313.3 | pilots | 98.1 |
| eight_schools_centered | 88.0 | | |

## 1. Where gradient evals actually go (source anatomy)

A transition (`walnuts.hpp transition_w`, L537–605) = momentum draw + start
grad (W-23-cached, L549–558) + depth loop of doublings, each doubling built
by `build_span` → `build_leaf` → **`macro_step`**. Every logp_grad call in
the kernel lives in exactly three places:

1. **Forward attempts** (`macro_step`, walnuts.hpp L324–356). The dyadic
   ladder starts at `num_steps = min_micro_steps (m)` micro steps of size
   `step` (= adapted eps) and on tolerance failure (`|ΔH| > max_error`,
   default 0.5) restarts from the same span endpoint with `2m` steps of
   `eps/2`, etc., up to `max_step_halvings` (default 5). One eval per micro
   step (L333). **All failed attempts are discarded** — attempt j costs
   `m·2^j` evals and produces nothing but the failed `|ΔH|` test.
2. **Backward reversibility ladder** (`reversible` → `within_tolerance`,
   walnuts.hpp L256–281, L220–237). After a refined accept (h ≥ 1), the
   endpoint is integrated BACKWARD on every coarser lattice `n/2, n/4, …, m`
   (one eval per micro step, L232; endpoint-only test, L236). The ladder
   stops at the first lattice that is *within* tolerance — and that outcome
   **rejects the whole macro step** (returns false → leaf fails). All-fail
   (full ladder, `n − m` evals) is the *accept* path.
3. **Boundary** (1 per transition pre-W-23; 0 with the cache; 2 per chain
   residual, §E5).

Per accepted macro step refined to level h: forward `m(2^(h+1)−1)` +
backward ladder `m(2^h−1)` = `3m·2^h − 2m` evals for `m·2^h` trajectory
micro steps — overhead ratio **2.0x at h=1, 2.5x at h=2, →3x** asymptotically.
At h=0 (first attempt accepted): `m` evals, no ladder (loop guard
`num_steps ≥ 2·min` fails; `num_steps == 1` shortcut), overhead 1.0x.
A leaf failure (reversibility rejection or halving exhaustion) discards the
entire forward spend of that macro step AND terminates trajectory expansion
(`build_span` nullopt propagates; `transition_w` breaks) — there is **no
retry path**; the "retry/rejection waste" class is exactly this
failed-subtree discard.

Terms with no evals (checked, closed): `uturn` uses endpoint momentum/
positions only (L194–203); `combine` (Barker/Metropolis) uses stored logp
(L379–398); momentum half-steps add no evals. Spans already chain
endpoint-to-endpoint carrying `grad_theta_fw_/bk_` — consecutive macro steps
share endpoints by construction (W-20: 0 accidental dups). During the drift
phase the error cap is suspended (`max_err = inf`,
adaptive_walnuts.hpp L683–685) so h=0 always accepts: **drift iterations
already pay zero dyadic overhead**.

Chunking identity: evals/transition = base micro steps (≈ T_uturn/eps, set
by step size and target geometry) + refinement waste + ladder evals + failed
-subtree discards. Re-chunking via `--max-macro-steps-target` /
`--min-micro-steps` moves overhead *between* the last three terms but cannot
touch the base term — the naive "raise the macro-steps target to shrink m"
idea is not a gradient-count lever by itself.

## 2. Designed experiments / proposals

### E1. Per-macro-step gradient accounting (the gateway measurement — run FIRST)

**Mechanism.** Env-gated counters in `macro_step`/`reversible`/
`within_tolerance` (the `WALNUTPIE_DEBUG_ALPHA/SPAN` precedent already in
walnuts.hpp L339, L562), compiled zero-cost when unset, printing per
transition: accepted-halving histogram P(h=0), P(h=1), …; reversibility
-rejection count and the succeeding ladder level; halving-exhaustion count;
eval counters {forward-accepted-attempt, forward-wasted-attempts,
backward-ladder, discarded-on-leaf-failure}; plus m, eps, final depth.
**Saving class:** none directly; it bounds every other proposal's ceiling
(the three overhead terms above, warmup vs sampling split).
**Risk:** none — no behavior change, bit-identity trivially preserved.
**Measurement design (for a later agent, after benchmarks finish):** 3
well-mixed models where the gap lives (blr, hier_2pl, kronecker_gp) +
pilots, 1 chain, fixed seed, recommended config, 100+100 iters; report the
four counters as fractions of total logp_grad calls. Decisions it feeds:
E2's expected saving = (refinement+ladder+discard fraction) × warmup share;
E3 lives iff deep-ladder events are non-rare; E4 lives iff P(h≥1) is
persistent rather than bursty.

### E2. Error-discipline ablation, warmup-weighted (config-only core)

**Mechanism.** The dyadic overhead is *gated by tolerance failures*: loosen
`max_hamiltonian_error` (default 0.5) and/or cap `max_step_halvings` (5)
→ fewer refinements, fewer/smaller backward ladders. Zero-code version
already CLI-exposed: `--max-hamiltonian-error`, `--max-step-halvings`, and
the warmup-only loose-early-cap schedule `--max-error-start` /
`--max-error-iters` (config.hpp L803–804, default off). A warmup-ONLY
halving cap (sampling keeps the full ladder) needs a tiny WarmupConfig knob
— same pattern as the existing max_error schedule. Warmup is 50% of a
1000+1000 run, and warmup draws carry no inference value; the drift phase
already suspends the cap entirely, so the design precedent exists.
**Saving class:** up to the full (refinement+ladder+discard) fraction of
warmup-phase evals (E1 quantifies; ceiling ~2x grads/draw overall if the
"~2x cmdstan grads/draw" attribution is right, realistic quality-preserving
subset 10–30% of total evals).
**Risk:** NOT bit-identical (warmup trajectories change → frozen params
change → sampling draws change). W-21/W-25/W-28 closed *shorter* warmup
(iteration-count cuts hurt the marginal class; late warmup gains live in
trajectory-geometry adaptation). E2 is a different axis — *cheaper* warmup
iterations, same count — but must reuse exactly that gate apparatus
(ESS-min bulk/tail on the marginal class: arma11, lsat_model, hier_2pl) plus
failure counts across the core set. Note the step adapter only consumes the
h=0 alpha statistic (walnuts.hpp L337–348), which a looser cap does not
change — the interaction is purely through trajectory composition.
**Measurement design:** ablation grid {0.5, 1.0, 2.0} × {halvings 5, 3,
warmup-only 3} on 6 models × 3 reps, grads/draw and ESS/grad as co-primary
metrics; pre-registered expectations: ESS/draw falls, grads/draw falls
faster on models with high E1 overhead fraction; kill if ESS/grad does not
rise on the well-mixed class.

### E3. Truncated backward reversibility ladder

**Mechanism.** `reversible`'s accept path walks the FULL coarser ladder
(`n/2 + n/4 + … + m` evals) to confirm no coarser backward lattice is
tolerant. Checking only the first level (`n/2`, the one whose success
rejects) and accepting when it fails skips `n/2 − m` evals per refined
macro step; an incremental |ΔH| early-abort inside `within_tolerance`
(currently endpoint-only, L236) is a stronger variant with the same
character.
**Saving class:** ≤ half of ladder evals on refined steps (E1's ladder
counter bounds it).
**Risk:** HIGH for a small prize — it changes the kernel's accept set
(macro steps the current rule rejects would be accepted whenever a deep
lattice level is the first to succeed), and the reversibility rule is
WALNUTS' correctness core (this is Flatiron-paper territory, not a fork
knob). NOT bit-identical. If E1 shows deep-ladder successes are rare, the
truncation is both near-no-op and near-zero-payoff; if they are common, the
behavioral change is large. **Likely dead end unless E1 surprises** —
pre-register only as a follow-up to an E1 result showing ladder evals
>15% of total with deep-level events non-rare.

### E4. Refinement-aware ladder base (adapt `min_micro_steps` toward h≈0)

**Mechanism.** The ladder always restarts at `m` (l=base). When accepted
levels are persistently h≥1, every macro step pays the doomed coarse
attempts. `MinMicroStepsAdaptHandler` (adaptive_walnuts.hpp L362–407)
already adapts m online (currently to hit `max_macro_steps_target`=15 macro
steps/trajectory, m frozen at sampler()). Add the complementary objective:
grow m when the observed halving level is persistently >0, so the typical
macro step accepts at h=0 — which kills BOTH the forward-refinement waste
AND the backward ladder (h=0 ⇒ no ladder by construction).
**Saving class:** the entire refinement+ladder overhead on models where
P(h≥1) is persistent (E1's histogram is the estimator input); affects
warmup AND sampling (m is frozen into the sampling kernel, so this is a
legitimate per-effective-draw lever, not just a warmup one).
**Risk:** kernel change (different macro granularity ⇒ different draws; the
dyadic rule itself stays state-determined, and m is *already* an adapted
quantity, so this is inside the library's existing design latitude, unlike
E3). Coupling risk: growing m lengthens macro time, the 15-step target
pushes back, and the base term (T_uturn/eps) is untouched — net grads/draw
is an empirical question, which is exactly what the ablation measures.
**Measurement design:** new estimator rule behind a flag
(`--refine-aware-min-steps`), ablate on the E1 model set; co-primary
grads/draw and ESS/grad; same marginal-class quality gates; report the
joint (m, h) trajectories to show the mechanism does what it claims.

### E5. Close the residual 2 dups/chain (W-23 completeness, hygiene)

**Mechanism.** The two remaining duplicate-position evals per chain:
(a) `InitConfigBuilder::masses()` evaluates grad at the init position
(config.hpp ~L365); (b) the first `AdaptiveWalnuts` transition re-evaluates
it (cache empty at construction); with `--step-init-heuristic`,
`find_reasonable_step` also evaluates the same theta (warmup_heuristics.hpp
L32). Fix: have `masses()` return (mass, grad, logp), thread it into
`find_reasonable_step` (skip its L32 eval) and seed `AdaptiveWalnuts`'
`cached_grad_/cached_logp_` (mirror the existing
`WalnutsSampler::seed_endpoint_cache`, walnuts.hpp L960).
**Saving class:** exactly 2–3 evals/chain (~0.01% — negligible wall impact;
the value is closing W-23's accounting to zero known dups and removing the
documented caveat).
**Risk:** none — reuse of bit-identical doubles; draws must be bit-identical
(same gate as W-23). Do it whenever the file is next open; not worth a
solo session.

### Flagged for the Flatiron discussion (not engineering)

**Micro-state selection candidates.** Within an accepted macro step, the
`m·2^h − 1` intermediate micro positions are evaluated and then discarded —
only the endpoint becomes a selection candidate (SpanW keeps one state per
leaf). Making them candidates would raise ESS/grad with zero extra evals,
but it breaks the macro-boundary selection structure that the reversibility
rule exists to protect — an algorithm re-definition, upstream-paper
territory. Recorded so the "every eval should buy a candidate" argument is
at least on the table with the e/grad evidence package.

## 3. Explicit dead ends (do not re-open)

| idea | why dead | evidence |
|---|---|---|
| Position-keyed memoization within transition/run | zero accidental revisits; the only dup was 1/transition, already threaded | W-20 hash instrumentation; W-23 shipped |
| Reuse across dyadic levels / between attempts | fine lattices from the same start diverge immediately (different first half-step); empirically zero revisits | leapfrog structure (walnuts.hpp L330–334); W-20 |
| Subtree/endpoint sharing between consecutive macro steps | already the design (spans chain endpoint-to-endpoint carrying grads) | walnuts.hpp SpanW; W-20 zero dups |
| Cheaper U-turn tests to avoid endpoint grads | uturn uses no gradients | walnuts.hpp L194–203 |
| Momentum-half-step sharing | one eval per position visit; no sharing site exists | same; W-20 |
| Subsampled-data gradients in the kernel | breaks the Hamiltonian invariant the tolerance test needs; estimation-side batching (stride 50) is the shipped, correct cut | PR #4 saga; ess_per_grad_evidence candidate space |
| Warmup early-exit (fewer iterations) | quality-destroying on the marginal class; direction closed | W-21/W-25/W-28 |
| Basis/metric extraction rules as an e/grad lever | statistically indistinguishable; basis is not the bottleneck | W-19 clean negative |

## 4. Ranking (expected grad-call reduction × implementability ÷ risk)

| rank | item | reduction ceiling | implementability | risk | verdict |
|---|---|---|---|---|---|
| 1 | E1 accounting instrumentation | gates all bounds | trivial, env-gated | none | **run first** |
| 2 | E2 error-discipline ablation (warmup-weighted) | up to ~(refinement+ladder+discard share) × warmup share; plausibly 10–30% of total evals | high (config-only core) | medium (quality-gated, not bit-identical) | **best expected value** |
| 3 | E4 refinement-aware ladder base | same terms as E2, sampling-phase too | medium | medium (kernel change within existing latitude) | pre-register after E1 |
| 4 | E3 truncated backward ladder | ≤ half of ladder evals | trivial code | high (correctness core) | hold for E1 evidence |
| 5 | E5 boundary dup hygiene | 2–3 evals/chain | trivial | none (bit-identical) | opportunistic |

Honest overall ceiling: the evidence package's "~2x cmdstan grads/draw via
the within-orbit dyadic search" bounds the entire pack at ~2x e/grad *if all
overhead vanished with no ESS cost* — which no quality-preserving variant
achieves. A realistic outcome is a 10–30% eval reduction on the well-mixed
class (E2+E4), worth roughly 0.35x → 0.45x e/grad parity movement, plus a
definitive decomposition (E1) that either confirms the design-overhead
attribution or redirects it.

## 5. Protocol constraints carried forward

All runtime work deferred (benchmarks in flight). Any implementing session:
pre-register in WORKLOG before running; E2/E4 use the W-25/W-28 gate set
(ESS-min bulk/tail marginal-class non-inferiority + core-set failure counts);
E5 uses the W-23 bit-identity gate; canary discipline per the session-3
branch model; never mix kernel changes with other patches in one commit.
