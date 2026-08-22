# nindan — final consolidated report (Phase 0 → W-10)

Metric: wall-clock to reliable posterior on CORE_SET (21 posteriordb models,
4 chains, 1000+1000, median of 3 reps, ESS = rank-normalized ESS_bulk).
Machine: Ryzen 9 5900X (AVX2 only), ≤4 cores throughout.

## 1. Baseline atlas (where Stan wall-clock goes)

| finding | evidence |
|---|---|
| cmdstan services carry 2.1–5.0× more instructions per gradient than a minimal bridgestan driver on identical math | callgrind, 4 models, parity-checked gradients |
| model-gradient = 76–97% of steady wall on data-heavy models; small/stiff models are kernel-bound (pilots: memcpy 21%) | profile() + callgrind |
| validity checks ≤ 2.2% (folklore rejected); LL misses ≈ 0 (no DRAM wall; L1/L2 latency only) | callgrind cache sim |
| -march=native: NO geomean win (1.13× slower, diamonds-only gain) — and the widely-reported crashes are cmdstan's mixed-build ABI bug, not compilers | validated fix in sims1253/cmdstan PR #1 |
| --Oexperimental: 3/21 uncompilable + 1 silent miscompile; no QA win | Phase 0 |
| nutpie "2×": real per-gradient win (2.6×) but quality-adjusted wash (0.98× ESS/s) | Phase 0 |

## 2. walnutpie adaptation engineering (the main arc)

Failure inventory at session start: 17/21 models R-hat>1.01 (chains frozen at init).

Mechanism chain (each step measured, PR #4 = the full saga):
1. **Freeze-from-init**: gradient-seeded mass ≈ 1e6 → inv_mass 1e-6 throttles all
   motion; no step-size search → every span divergent → transitions return the
   init point unchanged (sd ~1e-14). 6× warmup does not help (absorbing state).
2. **Fix layer 1 (init robustness)**: mass clamp + Stan-style step heuristic +
   typical-set (Pathfinder) inits via --init-file → freeze class resolved
   (blr 4→406 ESS, arma11 3→1381, lsat 7→736).
3. **Fix layer 2 (estimation discipline)**: observation batching (stride 50)
   halves failures 17→9; Fisher-HMC window chopping (memoryless) adds blr
   201→401, kronecker rhat 1.15→1.05. Mass shrinkage, clipping, drift-guard,
   power-mean combination, stall resets: all negative, all documented.
4. **Budget sweep**: no crossover — stock@4000 (15 bad, ESS 93) < full@1000
   (8 bad, 317). The fixes change the asymptote (~4× budget equivalence).
5. **Low-rank Fisher metric**: estimator + exact O(Dr) operator (property-tested:
   reversibility 3e-17, volume 9e-16, exact-Cholesky momentum sampling) + two
   integration bugs found by analytic-target testing (rejection under wrong
   Hamiltonian; metric dropped at freeze) + concentration-based auto-screening.
   W-9/W-10: full>fold 1.21×; screening protects funnels (8schools 1.11×) and
   activates wins (bym2 3.46×); aggregate within noise of diag — optional flag.
6. **Cross-chain mode diagnostic** (log-mass dispersion) shipped as the hook for
   mode-aware reinit; reinit-draw screening evidence recorded.

**Final config: batch-50 + Pathfinder inits + mass clamp + step heuristic + chop-50.**
R-hat failures 17/21 → 8/21 (cmdstan: 4), geo ESS_min 26 → 294 (11×).

## 3. Optimizer research (passes 1+2, with hermes/GLM-5.3)

Muon/Aurora/OKLS structurally inapplicable (scalar + diagonal state; every
production stack routes 1-D to AdamW; flower's own Aurora screen: "do not
deploy"). Transferable: zero-staleness (shaped chopping), closed-loop lr
(AdaGrad-Norm adapter), anti-windup (control-theoretic, rescues collapse),
PI-controller framing. walnutpie's mass rule is Fisher-divergence-optimal
(arXiv 2603.18845 Thm 2.2) — now cited, and its window discipline adopted.
Reports: external/research_optimizer_{sota,pass2}.md + docs/notes in fork.

## 4. Stan-source patches

- sims1253/cmdstan #1: mixed-build corruption guard (validated 3/3 on 2.39.0).
- patches/stan-2a1-rho-hoist.patch: bit-identical, no measurable win (negative
  result; the real 2a needs coordinated z_propose/p_sharp surgery).
- sims1253/walnutpie #1–#5 (+ 8 evidence comments): pluggable optimizers,
  hardening (clip = negative), shrinkage (negative), init robustness (the saga),
  research notes.

## 5. What remains open

- cmdstan per-gradient gap (2.1–5×): kernel-loop copy/alloc surgery (2a, full set).
- walnutpie funnel class (8 vs cmdstan 4 failures): mode-aware warmup via the
  dispersion hook + multi-path init screening.
- ESS/grad 0.06× vs cmdstan even when mixed: sampler-level question (WALNUTS'
  error-cap discipline trades trajectory reuse) — flagged for the Flatiron team.


---

# Session 2 addendum (W-11 → W-19): correctness, honesty, and closed questions

## 2a. The freeze-consistency family (three instances, all found by testing our own work)

Same defect shape each time: warmup tuned under one metric/operator, the frozen
sampler ran another, silently, exactly at the warmup→sampling boundary.

| # | instance | finder | fix |
|---|---|---|---|
| 1 | sampler() dropped the low-rank part at freeze (full mode) | analytic-Gaussian integration tests | 5e56ff2 set_low_rank |
| 2 | fold mode: warmup used rank_folded_estimate(), freeze used unfolded | independent audit child (glm-5.3) | 6fd6664 |
| 3 | full mode: warmup integrated UNFOLDED lrm.D, freeze rebuilt it folded | validation of the audit fixes (myself) | ef3c582 freeze memo |

Fix 3 introduced the freeze memo: frozen samplers carry the exact mass their
last warmup transition used (also kills a one-draw-staleness window in the
auto-screen decision). Also fixed en route: inert `--anti-windup` (CLI
template dispatch bypassed the config rate), restored a lost `CLI::Range`
check, rank-aware combined-span uturn.

## 2b. Reproducibility bug (ours; found the hard way)

`find_reasonable_step` drew probe momentum from `Eigen::VectorXd::Random()` →
`std::rand()` → clock-seeded by main. `--step-init-heuristic` therefore made
fixed-seed runs irreproducible (eps 0.0005–0.008 observed on hier_2pl).
Fixed 869dbe7 (seeded `detail::Random<RNG>` threaded through); 3-run
bit-identity verified. Consequences handled: W-16's "fold 11.75× vs rec"
RETRACTED (clean rerun: fold 35/1.084 ≈ rec 33/1.089, tracking rep-for-rep);
all post-W-16 numbers come from the reproducible binary. Two false alarms
debunked en route (init-file pair = harness bug; sweep-vs-rerun "mismatch" =
analyzer rewriting files in place). Upstream is clean (file never existed
there; their srand only picks the default seed).

## 2c. Where the rank metric actually stands (W-17 + w16clean + W-19)

- Full core set (21 × rec/fold/auto × 3 reps): arms statistically
  indistinguishable (fail counts 14/16/14 @ R-hat>1.01 — mostly marginal
  1.01–1.09 — geomeans within 13%).
- 500→1000 draws on the marginal class: ESS ~doubles, R-hat does NOT cross
  1.01 → slow mixing, not short runs.
- Rep-level variance dominates arm choice on hier_2pl (rep1 ~10× rep0/2 in
  every arm): init draw quality >> metric choice.
- W-19 basis ablation (svd/power/muon-NS/muonEq-equilibrated, all feeding the
  same frozen operator, property-tested pre-sampling): geoESS 32/30/38/35 —
  inside rep noise; no rule rescues funnels. The 2-D-optimizer question is
  closed empirically: basis is not the bottleneck. (--metric-basis stays as a
  one-flag ablation seam.)
- Honest recommendation unchanged but now evidence-complete: rank stays
  opt-in behind `--metric-auto`; funnels are a mode-lock/sampling problem
  (documented frontier), not a metric problem.

## 3a. ESS-per-gradient: the 0.06× claim corrected to 0.31×

Two metric-definition asymmetries found in our own harness (walnut denominator
included warmup; cmdstan's `n_leapfrog_sampling` meant "last 500 of 1000").
Fair sampling-phase-only recompute, 20 models, median of 3:
- geomean **0.31×**; splits into 0.25–1.33× on the 13 well-mixed models
  (walnutpie WINS kronecker 1.33×, pilots 1.05×, esc 1.00×) vs collapse only
  where mixing fails (hier_2pl 0.025× → 2.6× better post-fixes).
- Package for the Flatiron team: external/ess_per_grad_evidence.md
  (definitions, per-model table, four candidate explanations with cheap
  experiments). Robustness asymmetry noted: walnutpie aborts on non-finite
  logp mid-trajectory where Stan rejects (accel_gp).
- aggregate.py fixed to prefer sampling-phase grads.

## 4a. Patches/PRs as of session close

- sims1253/walnutpie PR #4: 17 evidence comments (the saga + retraction +
  clean rerun + W-19); dev/init-robustness @ 2f97cd6.
- sims1253/walnutpie **PR #6** (new): upstream-forwardable minimal slice —
  `adapt_with_stats()` + `AdaptResult::log_mass_dispersion` (1 file, +56,
  zero behavior change, validated against pristine main).
- Upstream provenance audit (external/upstream_audit_walnutpie.md): 51 hunks
  classified; zero genuine upstream bug fixes; our three session bugs all
  ours. The audit found 2 live bugs at HEAD (fixed same day) + corrected my
  own B2 "double-wrap" story (was single-wrap rate-8 semantics).
- Aurora research (hermes): arXiv 2606.27715, tall-2-D only —
  external/research_optimizer_aurora.md (with the 2025–26 successor table).

## 5a. What remains open (updated)

- cmdstan per-gradient gap (2.1–5×): Phase 2a coordinated surgery — untouched;
  enter fresh (the earlier template-surgery mishap lesson applies).
- Funnel class: unchanged (mode-lock; the reinit/re-targeted policies W-11/14/15
  are all neutral on it — consistent, so it's sampling, not adaptation).
- WALNUTS e/grad ceiling on well-mixed models (0.3–0.8×): design overhead of
  the within-orbit dyadic search; candidate mitigations in the evidence
  package (per-macro-step grad accounting, position-keyed memoization).

## 6. Session-3 addendum (W-23 … W-34)

Branch model: walnutpie feature branches kept as per-idea history; integration
on `exp/endpoint-grad-threading+chains` (0cb5b7b) → `exp/pilot-burst-gate`
(b80f4a8) → `exp/parallel-chains` (da71e5b) → `exp/safe-adapt-defaults`
(43b6435). `dev/init-robustness` verified pristine (3eddfc4 = origin).
cmdstan-fork history: `sims1253/stan` PR #1 (scratch-hoist, all 5 gates pass,
geomean wall 0.931).

**Shipped sampler wins** (all canary-gated bit-identical on unchanged paths):
- Endpoint-gradient threading (W-23): one redundant logp_grad/transition
  eliminated; drop = warmup+draws−1 per chain; 24/24 bit-identical.
- Parallel multi-chain (W-30): event-driven controller (busy-poll ~100%→1%
  CPU), thread/serial bit-equivalence 15/15 (+ mc chain == sequential
  single-chain run 15/15); wall geomean **3.2× vs sequential** 4-chain runs,
  1.03× vs 4 separate processes (hier_2pl 14% faster than procs).
- Safe adapt defaults (W-31): cross-chain early exit OFF by default
  (`allow_early_exit`); default `--chains 4` bit-identical to full-warmup base
  24/24; `--early-exit` still reproduces the destructive exit (519→24 ESS).

**Closed directions (measured, recorded):**
- Compile flags (W-27): default build already -O3-equivalent; -march=native
  silently MISCOMPILES kronecker_gp gradient (lkj_corr_cholesky block, sign
  flips) in a self-contained build — hard ban; bridgestan compile_model
  silently reuses cached .so regardless of make_args.
- Warmup early-exit: W-21 (fast, quality-destroying), W-25 (static step/mass
  gate refuted — 519→126), W-28 (pilot-burst gate preserves quality only by
  never exiting; lp lag-1 autocorr cannot separate classes: hier 0.71–0.91 vs
  blr 0.62–0.74). Direction closed: warmup's late gains live in
  trajectory-geometry adaptation invisible to step/mass/lp-window statistics.
- cholesky rev pass (W-33): at n≤35 the Giles sweep is at its ~2×-forward
  algorithmic floor; not worth patching at this size.

**Gradient-cost levers (stan-math/stanc3 upstream pack — see
external/upstream_candidates.md for details):**
- kronecker_gp (W-32): rewrite with `eigendecompose_sym` (ALREADY upstream in
  stan-math 5.3.0 / stanc3 2.39): −19.4% Ir/grad, −14.3% µs/call,
  bit-identical. Upstream ask: stanc3 peephole fusing the
  eigenvectors_sym+eigenvalues_sym pair (4 full decompositions per gradient
  today where 2 suffice). results/eigh_reuse_w32.md.
- hier_2pl (W-34): eltwise var-mode plumbing = 40.4% of gradient; complete
  -design GEMM reformulation (6-line model diff): −28.2% Ir/grad, −25%
  µs/call, 0.739× wall, ESS distribution clean (ESS-min marginal: unstable
  statistic). Upstream asks: stanc3 expression fusion for eltwise chains over
  indexed var containers; a gathered/indexed GLM primitive (dense GLMs
  structurally exclude IRT/rating/sparse-interaction likelihoods — measured).
  results/hier2pl_plumbing_w34.md.
- gp_regr (W-33): stan-math `square()` calls std::pow(x,2) (contradicting its
  own doc); x*x patch = −9.1% Ir/grad, −13–15% µs/call, bit-identical (glibc).
  One-line upstream PR; patch at scratch/w33/pow_to_mul.patch.
- Hotspot atlas (W-29): results/hotspot_atlas_w29.md — logp_grad = 81.6–99.4%
  of program Ir across the 5 profiled models; walnutpie-internal sampling-loop
  overhead 0.2–5.5% (sampler-side ceiling confirmed at instruction level);
  tape/arena fixed tax 8–17%G (SoA-arena lever, not a single patch).

**Safety findings for upstream:** -march=native gradient miscompile
(reproducer: harness/run_w27.py parity); bridgestan default .so silently
unsafe under threaded evaluation (double-free/SEGV; STAN_THREADS=1 build
clean — repro + provenance in upstream_audit_walnutpie.md §4).
