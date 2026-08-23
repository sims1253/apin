# W-54: init-buffer mass deferral (arm A) + warmup-only soft gradient clipping (arm B) — two thread-inspired early-warmup shields, tested against the W-43 pin class

Date: 2026-08-22/23. walnutpie branch `exp/warmup-shields` (worktree
`external/walnutpie_w54`, off `exp/safe-adapt-defaults` @ 43b6435):
33bcff5 (cherry-pick 468e60f, W-43 find_reasonable_step fix — needed for
the 779-bar arm), b657198 (cherry-pick 8853fd7, W-43 pin-trace
instrumentation; conflicts resolved by dropping the W-38 grad-accounting
context that does not exist on this branch), e46da43 (the W-54 knobs).
Pre-registration: WORKLOG.md "W-54" (written before any run). Community
sources: discourse 41487 post 11 (Stan-style init buffer, identity
metric for the first ~75 iterations so tail geometry never contaminates
the metric) and discourse 41095 post 39 (soft clip f(x) = c·asinh(x/c),
c = 1e10, eliminating stuck chains in nutpie). W-43 fixed the STEP side
of the pin; these two levers are the MASS side and the GRADIENT side.
NOT the same lever as session-2's mass-estimate clipping
(`--mass-init-clamp`).

## Implementation (both default-off)

- **Arm A — `mass_init_buffer`** (size_t, 0 = off; CLI
  `--mass-init-buffer N`, tested 50/75/100): for warmup iterations < N
  the mass estimator is not fed at all (no `observe()`, no window
  chopping, no low-rank refresh) and the transition runs with the
  IDENTITY inverse mass; the accumulators are SEEDED AT IDENTITY when
  the knob is on, so the first post-buffer estimate is identity and
  real observations blend it in (no metric discontinuity at N).
  "identity/initial" latitude resolved as IDENTITY (the Stan
  transplant): holding at the *initial* (gradient-seeded) value would
  keep exactly the contamination vector the thread diagnoses and
  duplicates `drift_iters` metric semantics minus its step/cap
  suspension. The error cap and step adapter stay ACTIVE during the
  buffer (unlike `drift_iters`) — the W-43 step-descent race must keep
  racing while the metric is protected.
- **Arm B — `grad_clip_scale` c + `grad_clip_iters` M** (0 = off /
  default 200; CLI `--grad-clip-scale`, `--grad-clip-iters`): during
  warmup iterations < M the gradient fed to the mass estimator's score
  moments is replaced elementwise by g' = c·asinh(g/c). Scope (as
  pre-registered): the score stream is the ONLY model-gradient input to
  adaptation — the step adapter consumes the scalar alpha =
  exp(-|dH|) only (`adam.hpp`: grad = target − alpha), and |dH| is a
  property of the integrated trajectory. Clipping the INTEGRATOR
  gradient would change the Hamiltonian (a self-consistent but
  DIFFERENT, smoothed target); not done. Consequence stated up front:
  B cannot tame the alpha underflow by construction; the pre-registered
  STOP clause (integrator clipping needed) was never triggered — the
  lever simply does not reach the engine.
- Knob sites: `WarmupConfig`/builder (`config.hpp`),
  `MassEstimator` ctor + a private `observe_estimator()` helper that
  applies the clip (`adaptive_walnuts.hpp`), CLI plumbing
  (`stan_cli.cpp`). Library-level knobs (multi-chain legal), exercised
  here via single-chain CLI invocations (the W-43 protocol).

## Gate (a) — canary bit-identity

- **Knob-isolated canary: PASS 12/12** (results/w54_canary_1e02b5.json):
  default-path draws of the final binary (e46da43, all knobs off) vs
  the SAME worktree built at b657198 (both cherry-picks, before the
  knob commit): arma11/blr/hier_2pl × 4 chains, 1000+1000, seeds
  20260819+c, rep0 pf inits — md5-identical on every cell. The knobs
  are exactly draw-neutral when off.
- **Full-binary comparison vs exp/safe-adapt-defaults (43b6435):
  0/12** (results/w54_canary_43b6435.json) — and this is a FINDING, not
  a knob failure: the cherry-picked pin-trace hooks (b657198) perturb
  hot-loop codegen (semantically identical source — two `bool`
  extractions around `within_tolerance` calls under `-O3`), the |dH|
  series shifts in the last ulp, and the pin's escape is a FIRST
  PASSAGE on |dH| crossing 0.5 — so escape shifts by a few iterations
  and all post-escape draws differ. Evidence: with `--save-warmup`
  (blr, pf init, seed 20260819, w1000) the two binaries agree for 183
  warmup draws and diverge exactly in the escape region (W-43: pf
  escape ≈ 185-200). Corollary for W-43's own claim: 8853fd7's
  "zero-behavior" smoke canary was a PINNED cell (identical draws are
  trivially preserved); it was never verified draw-neutral on an
  escaping cell against its parent. A pinned chain hides last-bit
  differences; bit-identity canaries must compare like-for-like builds
  (second instance of W-50's "bit-identity is trajectory-conditional"
  lesson).
- Because the knob-isolated canary passes, every knob-off run of the
  e46da43 binary is a valid "base" run for gates (b)/(c); the base
  cells below were re-run on this binary rather than borrowed.

## Gate (b) — the W-43 pin battery (blr, 3 reps × 4 chains, seeds 20260819+1000·rep+c, 1000 draws; pinned = all draws identical)

| arm (w100 pf unless noted) | bulk-min med | tail-min med | rhat-max med | pinned | note |
|---|---:|---:|---:|---:|---|
| **base** (knobs off) | 7.0 | 10.5 | 2.39 | 8/12 | the pin (W-43/E2: 5-9 bulk, 3/4 chains/rep) |
| **heur** (W-43 fix, THE BAR) | **779.0** | 769.5 | 1.005 | **0/12** | reproduces W-43 exactly |
| a75 | 5.1 | 4.0 | 5.4 | 10/12 | A alone: pin WORSE than base |
| a50 | 4.6 | 4.0 | 9.1 | 10/12 | same |
| a100 | 4.0 | 4.0 | — | 12/12 | fully pinned |
| b1e10 | 7.0 | 10.5 | 2.39 | 8/12 | identical to base |
| b1e8 | 7.0 | 10.5 | 2.39 | 8/12 | identical to base |
| b1e6 | 7.0 | 10.3 | 2.39 | 8/12 | same pin structure |
| **a75 + heur** | **165.8** | 243.6 | 1.025 | 0/12 | A DAMAGES the fix: 4.7× below the bar |
| b1e10 + heur | 779.0 | 769.5 | 1.005 | 0/12 | exactly the bar (no-op) |
| b1e6 + heur | 750.6 | 694.9 | 1.007 | 0/12 | −4% vs the bar |

w400 pf (the cells with a healthy base): base 626.5 (1/12 pinned) /
heur 630.4 / **a75 214.0** (1/12 pinned) / b1e10 626.5 (identical to
base) / a75+heur 406.3. w100/w400 def: all arms 4.0-4.6 bulk with
12/12 pinned except heur-class arms (0/12 pinned but drift-limited at
4.2-4.6 — the W-43 init-protocol class, unchanged by any shield).
Per-rep detail in results/w54_knob_ess.json; all 372 runs rc=0.

Reading: the W-43 bar is live on this branch (779.0/769.5 and
630.4/693.7 reproduce W-43's numbers exactly — same fix, same seeds).
**Arm A fails the unpin gate outright** (bulk 4.0-5.1 vs the required
≫ 5-9; pin counts ≥ base) **and is actively harmful on top of the
fix** (165.8 vs 779 at w100, 406 vs 630 at w400). **Arm B changes
nothing** at the thread's scales — c = 1e10/1e8 is the numerical
identity on blr's 1e6-1e7 gradients (through-warmup-pinned cells give
literally md5-identical CSVs; escaping cells differ only via the
~1e-7-relative asinh residue) — and at model scale (c = 1e6,
exploratory, pre-registered) it leaves the pin structure intact and
shaves 4% off the fixed arm.

## Gate (c) — no-harm (hier_2pl + lsat_model, w1000 + 1000 draws, 3 reps × 4 chains, pf inits)

| model/arm | bulk-min med (per-rep) | tail-min med |
|---|---|---:|
| hier_2pl base | 560.6 (611.6 / 560.6 / 496.2) | 796.1 |
| hier_2pl a75 | 618.4 (618.4 / 645.4 / 549.4) | 700.6 |
| hier_2pl b1e10 | 560.6 (611.6 / 560.6 / 496.2) | 796.1 |
| hier_2pl b1e6 | 610.5 (611.6 / 610.5 / 496.2) | 796.1 |
| lsat base | 718.8 (849.5 / 647.9 / 718.8) | 1058.7 |
| lsat a75 | 732.2 (855.9 / 732.2 / 580.4) | 1130.5 |
| lsat b1e10 | 718.8 (767.0 / 647.9 / 718.8) | 1185.7 |
| lsat b1e6 | 627.0 (627.0 / 568.8 / 643.1) | 1157.0 |

hier_2pl: every arm inside the base band (draws DO differ — md5s
checked; the near-identical ESS values are the statistic's stability,
not identical runs). lsat: a75 and b1e10 inside the band; **b1e6 flags
a mild degradation** (−13% bulk-min median, all three reps below the
base band's low end; tail unaffected) — one more mark against
model-scale clipping. hier_2pl rhat shows NaN on constant
transformed-parameter columns (L_Omega.1.1, Omega diagonals = 1 by
construction) in every arm including base — an analysis artifact of
constant columns, not a knob effect. 0 pinned chains anywhere.

## Gate (d) — mechanism traces (WALNUTPIE_PIN_TRACE=1, blr, 1 chain, seed 20260819, w1000; results/w54_trace.json)

1. **off == W-43 reproduced**: escape at it=948, boundary mindh
   0.5017 → 0.4987, step continuous, invm frozen at 6.42493e-08 for
   the whole pin, alpha jumps 1.5e-56 → 5.7e-165·(moved) at escape —
   the W-43 table digit-for-digit.
2. **A does NOT prevent the metric collapse — it only schedules it.**
   a75, def init: during the buffer the identity metric makes every
   attempt catastrophically divergent (|dH| = inf at step ~0.95,
   vs 8.2e6 under the seeded metric); at the FIRST post-buffer
   observation the estimate crashes 1 → 2.065e-07 in one iteration
   (identity draw-variance seeds meeting 1e7-scale constant scores:
   the var-ratio collapse the community thread describes happens at
   FIRST OBSERVATION, not by accumulation — deferring the feed cannot
   prevent it). The chain then remains pinned past iteration 1000
   (escape: none; base escapes at 948). pf init: same story at
   pf scale (buffer |dH| ~ 1e24, crash 1 → 6.05e-03 at N, escape
   266 vs base ~198).
3. **A's second failure mode — the step is calibrated for a metric
   that gets replaced.** a75 + heur, def init: the fix's iteration-1
   escape is DELAYED to iteration 76 (the buffer phase runs at
   identity where the probe-calibrated step is hopeless again, alpha
   = 0 for 76 iterations); pf init: the chain moves from it=1 but the
   step adapter spends the buffer diving 0.0074 → 0.00098 (alphas
   2e-12 under the identity metric) and then needs the remaining 925
   iterations to re-inflate to 0.102. This — 75 wasted iterations plus
   a post-buffer step ~100× too small — is the mechanism behind the
   165.8-vs-779 damage in gate (b).
4. **B's one genuine (insufficient) mechanism effect.** b1e6, def
   init: the clipped constant stream freezes the metric at
   2.648e-07 instead of 6.425e-08 (4.1× lift — asinh compresses the
   1e7 scores to ~3e6), the per-step displacement doubles, and the
   escape first-passage arrives at it=244 instead of 948 (boundary
   mindh 0.545 → 0.495 at step 0.224 vs 0.502 → 0.499 at 0.049):
   the required log-step descent halves (1.54 vs 3.03 nats). Still
   ≫ the w100/w400 budgets, so no battery cell improves. Secondary
   effect: when the clip window ends at M=200 still deep in the tail,
   the raw scores hit the protected estimator and the estimate
   crashes 2.65e-07 → 1.95e-08 in one iteration (below the base
   level) before recovering — the deferred contamination, compressed.
5. **B never touches the alpha engine** (as pre-registered): alpha
   underflows to exactly 0 through every pinned iteration in every
   arm; the escape remains the step-descent race W-43 described.

## Verdicts

- **Arm A (mass_init_buffer): REJECT.** Fails the unpinned gate (pin
  counts ≥ base, bulk 4.0-5.1), worsens the base cell's escape
  (948 → >1000 def, ~198 → 266 pf), and damages the W-43 fix's class
  4.7× (165.8 vs 779.0 at w100-pf). The Stan-style init buffer
  presupposes (i) an estimator whose initial state is identity and
  whose contamination is ACCUMULATED, and (ii) a step-size heuristic
  calibrated under identity. In walnutpie the collapse happens at
  first observation regardless of schedule, the gradient seed is (on
  this class) a better metric prior than identity, and the step
  adapter spends the buffer calibrating for a metric that is swapped
  at N. Safe on healthy models (hier_2pl/lsat w1000: within band) —
  but safe and useless-with-harm-on-the-target-class is a reject.
- **Arm B (grad_clip_scale): REJECT as a pin shield; REDUNDANT given
  the W-43 fix.** At the thread's scales (1e10, 1e8) it is the
  numerical identity on this model class — exactly reproduces base.
  At the model's own scale (1e6, exploratory) it lifts the frozen
  metric 4.1× and halves the escape time on the traced cell — a real
  mechanism, but insufficient for any short-warmup budget, and it
  costs 4% on the fixed arm and −13% lsat bulk-min. The pin's engine
  (alpha underflow → blind Adam descent) is unreachable from the
  adapter's score stream; the thread's reversibility-intuition lever,
  transplanted strictly to adapter inputs, does not address walnutpie's
  binding constraint.
- **The W-43 step-side fix remains the only effective shield for this
  pin class.** Neither community lever adds robustness on top of it
  (B@1e10 + heur lands on the bar's exact medians 779.0/769.5/1.005 —
  statistically indistinguishable from heur, though not bit-identical:
  the ~1e-7-relative asinh residue perturbs post-escape trajectories;
  A subtracts).

## Repro

```
# knob (arm A): external/walnutpie_w54/build_w54/examples/stan_cli \
  bs_models_threads/model_blr.so data/blr.json --seed 20260819+c \
  --warmup 100 --samples 1000 --init-file inits_w25/blr/repR/chain_C.txt \
  --mass-init-buffer 75
# knob (arm B): ... --grad-clip-scale 1e6 [--grad-clip-iters 200]
# mechanism trace: prepend WALNUTPIE_PIN_TRACE=1, drop --output
# harness: harness/run_w54.py {canary,knob,noharm,trace};
#          harness/analyze_w54.py {knob,noharm}; harness/trace_w54.py
```

Artifacts: results/w54_{canary_1e02b5,canary_43b6435,knob_ess,
noharm_ess,trace}.json; harness/{run_w54,analyze_w54,trace_w54}.py;
raw runs/w54/ (local, gitignored; the knob-isolating canary base
binary is the b657198 build kept at /tmp/w54_preknob). Walnutpie
commits 33bcff5 + b657198 + e46da43 on exp/warmup-shields; worktree
left in place.

## Caveats

- The full-binary canary's 0/12 vs 43b6435 is codegen-induced (escape
  first-passage shifts); the knob-isolated canary (12/12) is the gate
  that matters, and all base references in gates (b)/(c) were re-run
  on the e46da43 binary so no number crosses that build boundary.
- Trace evidence is 1 chain × 1 seed × 2 inits per arm (the W-43
  precedent); the battery (372 runs) is the statistical layer.
- The heur arms are single-chain-only (CLI restriction, inherited from
  W-43); the new knobs are library-level but were exercised only via
  single-chain invocations.
- b1e6 was an exploratory c (pre-registered with justification: the
  thread's c is 1-4 orders above this class's gradients); its mild
  harms quantify the cost of clipping at model scale and are part of
  the reject rationale, not a separate recommendation.
