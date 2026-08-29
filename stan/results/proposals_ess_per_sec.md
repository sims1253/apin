# Proposals: new ESS/s levers for walnutpie (desk study, no runs)

Date: 2026-08-24. Session: ox-alpha (ESS/s ideas). Method: read-only —
walnutpie source (`include/walnutpie/{walnuts,adapt,adaptive_walnuts,
config}.hpp` @ exp/safe-adapt-defaults 43b6435), WORKLOG W-1..W-58,
FINAL_REPORT §1-8, ess_per_grad_evidence.md, upstream_scan_2026-08 §7,
research_scan2 (W-51), pathfinder-ablation entry (08-19 ~15:30), upstream
GitHub state (main 6162d88 = fork point; `preconditioner` branch diffed).
NO experiments were run; every proposal below is pre-registration-ready.

Framing. ESS/s decomposes as (ESS/draw) · (draws/s), and draws/s into
gradient cost × gradients/draw × parallelism. Gradient cost is the SoA
session's territory (W-53/57/58) + filed upstream pack; parallelism is
shipped (W-30/W-36: 3.2×); warmup early-exit is closed by 4 gates;
warmup = 65-76% of total wall; on well-mixed models walnutpie's ESS/grad
is 0.3-0.8× cmdstan (bounded dyadic-search overhead) while collapse
models are adaptation-limited (every freeze fix mechanically lifted
e/grad). The unclaimed territory is therefore: (a) metric/warmup
QUALITY per fixed budget, (b) cross-chain information flow during
adaptation, (c) trajectory-length policy. Queued-but-unstarted HANDOFF
C'' items are marked where a proposal touches them.

---

## P1 (top pick): Curvature-seeded warmup metric — "Pathfinder metric transplant, done right"

**Today.** The initial mass seed is `(1-s)*|grad(x0)| + s` per chain
(config.hpp InitConfigBuilder::masses, the Nutpie outer-product strategy),
optionally clamped. That seed matters PERMANENTLY, not just at iteration
0: MassEstimator seeds both OnlineMoments accumulators with it
(mass_init_count = 4 pseudo-observations), and memoryless chopping calls
`reset_to_seeds()` at EVERY window boundary (adaptive_walnuts.hpp
operator()) — so each window's estimate is a blend of the seed and ≤50
discounted draws. On coordinates where the chain mixes slowly inside a
window, the window carries almost no information and the seed dominates.
The freeze-class saga showed how bad |grad|-seeds can be (≈1e6 mass →
inv_mass 1e-6 throttle → pinned chains).

**Proposal.** Replace the |grad(x0)| seed with an L-BFGS inverse-Hessian
approximation computed at the SAME Pathfinder init point: diag + rank-r
regularized B⁻¹ (exactly Pathfinder's formula; two-loop recursion over
the stored (s,y) pairs, ~100 lines against the existing bridgestan .so
via harness code). Wire through the EXISTING plumbing:
InitConfigBuilder::masses_ → InitChainConfig::mass → MassEstimator seeds
(+ optionally U,c via the existing set_low_rank path for full mode). CLI:
--init-mass-file (+ --init-rank-file). The pf run itself is already part
of the standard harness pipeline and cached — marginal pipeline cost ≈ 0.

**Why this is NOT any of the refuted/queued things.**
- H1/H2 pathfinder ablation (W-ledger 08-19 ~15:30) was CMDSTAN-only,
  position-inits only, Stan windowed adaptation — it predates the
  walnutpie pivot entirely. Its mechanism caveat (typical-set starts make
  early warmup trajectories pricier) applies to the position, which is
  ALREADY sunk in the recommended config; the metric seed adds ~nothing
  to trajectory length.
- W-45 rejected transplanting covariance estimated from SUBSAMPLED DATA
  (a different posterior's geometry). L-BFGS curvature at the pf mode is
  same-posterior, full-data, analytic — the disqualifying mechanism does
  not apply.
- HANDOFF C''#1 (arXiv:2603.18845 Fisher low-rank ONLINE estimation) is
  complementary, not duplicate: that estimates from scores ALONG the
  chain; P1 injects prior curvature AT the chain's start and re-feeds it
  at every chop. Seed + online-refine plausibly beats either alone; if
  C''#1 lands first, P1 becomes its initialization arm.
- Upstream check: flatironinstitute/walnutpie `preconditioner` branch
  ships only a static DiagPreconditionedLogpGrad wrapper (external `a`
  supplied by the caller) — the wrapper exists, the preconditioner
  GENERATOR does not. Our fork-point has neither.

**Expected effect / measurement.** Better final frozen metric on the
ill-conditioned + marginal class (the e/grad-collapse models are
adaptation-limited), faster settlement within each window; warmup wall
unchanged to slightly up (H1 mechanism). Pre-register as: arms =
recommended-config vs recommended+pf-metric-seed, CORE_SET subset =
{hier_2pl, blr, bym2, diamonds, arma11, kronecker_gp, 8schools_centered},
3 reps, gates = ESS_bulk_min distribution + R-hat + wall two-sided.
Watch for funnel degradation (pf collapses chain diversity — pilots
lesson, H2): the log-mass dispersion diagnostic detects it per-run.

**Cost/risk.** ~1 day implementation + one grid. Low risk (opt-in flag;
default path untouched). Honest unknown: how much of the final-window
metric error is seed-dominated vs draw-noise dominated — cheap
discriminator BEFORE implementing: instrument one run to report, per
coordinate, |window estimate − pooled truth| attributed to seed vs data
(reuse w17g logs first).

---

## P2: Cross-chain pooled moment estimation mid-warmup

**Today.** M chains adapt M independent metrics from M independent draw/
score streams; the ONLY cross-chain moment sharing is at freeze
(geometric-mean mass in poll_controller — walnutpie is already unusual
here; cmdstan shares nothing ever). Each chain's window variance estimate
runs on n_eff ≈ window draws of ONE chain.

**Proposal.** Extend AdaptSnapshot with the two accumulators' (mean, M2)
vectors (publish_stride=5 already publishes snapshots; +2·D doubles).
At each chain's OWN window boundary, reset toward the POOLED estimate
(summed M2 across chains ≈ M× effective sample size) instead of bare
seeds, guarded by the existing log-mass dispersion diagnostic: pool only
when cross-chain agreement is below a tolerance, else fall back to solo
estimation (mode-lock safety comes free).

**Payoff.** Variance-estimate noise ∝ 1/n_eff drops ~M×; either better
final metric at fixed warmup budget or same quality at fewer windows
(warmup-wall lever — the biggest bucket). Particularly targets exactly
the slow-mixing coordinates where single-chain windows are blind (same
target as P1, different information source; P1 seeds prior knowledge, P2
shares sampled knowledge — they compose).

**Cons (honest).**
- Determinism: in ChainExec::Threads the pooled value depends on publish
  schedule ⇒ draws become schedule-dependent; breaks the W-30-style
  thread==serial bit-equivalence discipline. Mitigations: land behind
  ChainExec::Serial first (deterministic round-robin observation points,
  already shipped), or document schedule-dependence as parallel-chain
  runs already implicitly accept. Needs a protocol decision BEFORE
  implementation — this is the main gate.
- Correlated chains inflate confidence: chains share the warmup
  trajectory history only through their (independent) inits; post-pf-init
  chains start close together, so early windows' pooled estimate has less
  independent information than M suggests. The dispersion guard plus
  late-window pooling (skip the first window or two) addresses it.
- Literature: MEADS/ChEES/LAPS adapt STEP SIZE cross-chain (theory
  exists); cross-chain MASS pooling is comparatively unexplored → a
  defensible novelty claim, but also means no ready-made tuning constants.

**Cost/risk.** Medium implementation (~AdaptSnapshot fields, a
controller→worker seed channel via a second SpscBuffer, guards). GO/NO-GO
experiment can be SIMULATED offline first: pool the w17g/w36 per-chain
draw logs post-hoc, recompute what each chain's window estimates WOULD
have been under pooling vs solo, and compare against the realized final
metrics — zero new sampling compute for the feasibility verdict.

---

## P3: Trajectory-length policy — measure first, control later

**Today.** MinMicroStepsAdaptHandler pins expected macro steps ≈ target 15
(≈ tree depth 4) via the min_micro_steps floor; the frozen sampler carries
it into sampling unchanged. The AdvancedHMC.jl #470 thread identified this
knob as THE confounder of WALNUTS-vs-NUTS ESS/grad comparisons; our own
evidence package names the bounded dyadic overhead (0.3-0.8×) without
asking whether depth-4-ish trajectories are right per model.

**Proposal (two-stage, stage 1 is analysis-only).**
1. From EXISTING artifacts (w17g grad counts, w36 logs, ESS tables):
   extract per-model realized depth distributions and e/grad; identify
   models whose sampling-phase efficiency sits far from the well-mixed
   band despite clean R-hat. If no headroom signal, STOP here (record
   negative, like W-19).
2. Only then: online controller nudging max_macro_steps_target during
   LATE warmup against a mixing-per-gradient proxy (sliding lag-1 lp
   autocorrelation per unit gradient cost), frozen at the boundary like
   everything else.

**Must-be-framed-against graveyard:** grow-m/E4 was REJECTED with a
sign-inverted premise (refinement-success signal); W-37 permanently
closed EXIT-gating, not length control; W-31 requires two-sided default
changes. Stage 1 costs nothing (log parsing), respects "measure before
build", and cannot contaminate anything.

**Ceiling.** Unknown until stage 1; bounded above by the well-mixed-band
gap (≤ ~2-3× e/grad on specific models, geomean likely ≤ 1.2×). Worth
stage 1 precisely because it reuses data already on disk.

---

## P4: Cheap knob audit — acceptance-target & error-cap interaction

step_accept_rate_target defaults 0.8 (config.hpp:775). Classical HMC
theory (Hoffman-Gelman; Neal) puts the gradient-optimal target nearer
0.6-0.65 at high dimension; WALNUTS' error-cap discipline may shift it,
but nobody has measured it HERE. One pre-registered sweep {0.65, 0.7,
0.8} × {default max_error} on the well-mixed class, 3 reps, existing
harness, two-sided verdict per W-31 discipline. Modest ceiling, nearly
free, and it hardens any future default-change ask with evidence.
(Do NOT touch defaults without the W-31-style gate battery.)

---

## Explicitly NOT proposed (closed/refuted/parked elsewhere)

- Warmup early-exit in any form (W-21/25/28/37 — 4 independent refutations).
- Compile-flag gradient speedups (-march=native ban, -fno-math-errno
  non-value-neutral; W-27/W-50); stanc3 fusion (W-48 mechanism-negative);
  log1p kernel (measured; wall-neutral at baseline ISA — upstream ask).
- Subsampled-data warmup transplants (W-45 mechanism-rejected).
- Error-discipline loosening (E2) and grow-m (E4) — rejected with mechanisms.
- Within-chain speculative parallelism (W-49 ceiling arithmetic loses to
  the 4-chain null); its successor lane (DEER/Picard over
  Metropolis-adjusted trajectories) stays parked per W-51 #4 with the
  analysis-first predictability step.
- Basis-extraction rules (W-19 second-order), position memoization
  (W-20 none exist; W-23 shipped the real win), SIMD-across-chains
  (no gain under the ≤4-core machine budget).
- Fourth-order integrators (upstream issue #35): interesting under an
  error-tolerance-driven sampler, but upstream-owned and arithmetic-
  breaking; watch, don't build.

## Suggested order (one-decision increments, per house protocol)

P1 discriminator (log-based, hours) → P1 implementation+grid →
P2 offline pooling simulation (no sampling compute) → P2 serial-mode
prototype IF simulation shows signal AND determinism stance decided →
P3 stage 1 (log parsing, anytime) → P4 sweep (any quiet-machine gap).
P1 and C''#1 should share one decision point: whichever arm lands first
becomes the other's baseline/complement.

---

## POSTSCRIPT (2026-08-26): every proposal in this file has now been adjudicated

- **P1 curvature-seeded warmup metric — REFUTED** (W-65 G2/G3): chop windows
  on slow coordinates are data-starved (~12:1 data:seed weight, near-zero
  realized variance); even oracle seeds move the estimate ≤18% on the
  marginal class. L-BFGS path-curvature seed actively harmful on hier_2pl.
- **P2 cross-chain pooled moments — REJECTED three ways** (W-75 Arm B,
  W-76; guard map scratch/w75/guard_sweep.md): open-loop estimator wins
  were real but do not survive any closed-loop form — chop-coupled pooling
  inherits the chop tax (0.50×), chop-free merge homogenizes independently
  calibrated chains (0.589×, new R-hat failures). Chain independence is
  load-bearing.
- **P3 trajectory-length policy** — handed to a sibling session; stage-1
  log-mining conditional GO on a depth-cap pin battery (their W-73-P3).
- **P4 acceptance-target sweep — answered negatively** without a new run:
  W-73's target07 arm rejected it (−27% aggregate).

Durable artifacts from this file's program: warmup tracer (fork PR #11),
OnlineMoments Welford-aliasing correctness fix (PR #12), bitwise MassEstimator
replay + frozen trace contract (scratch/w59/replay/), and the negative-
result mechanisms above. Standing frontier unchanged: funnel/mode-lock
class, pf-init default policy (owner decision).
