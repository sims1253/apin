# F-11.2 log — vendored walnutpie adaptation upgrade (walnuts arm under-mixing)

Started: 2026-08-26. Binding charter: WORKLOG "F-11.2 (walnuts adaptation)" +
logs/fortk-f11-design.md Design 2 (the spec) + section A inventory.
Worktree: external/stanli-f112 @ 9b2bf80, branch fortk/f112-walnuts.
Depends on F-9 tooling (--init pf, --sampler walnuts) which is IN 9b2bf80 (F-12
consolidation). No deps/stan edits => no F-10 conflict; build waits for F-10's
atomic deps apply anyway (shared symlinked deps).

## Plan of record (from charter + design)

- MassEstimator (vendored runtime/third_party/walnutpie/adaptive_walnuts.hpp):
  window chopping (W-6: blr 201->401 ESS), robust/Winsorized floored Var_score
  (W-4 early-drift degeneracy), kappa=5 shrink toward the re-seed value;
  wire OR remove dead mass_additive_smoothing (record decision).
- Step/warmup loop: cheap defensible upgrades per research_optimizer_sota
  (mean-batching stride W-1 17->9 rhat-bad; beta/decay adjustments; no
  optimizer swap — settled wash). Flag-gated, defaults preserve current
  behavior BITWISE (design gate (ii)).
- Implementation order: smallest change that can pass kidscore gate first;
  add pieces only as gates demand (W-2 honest bound: bundling blindly moved
  nothing).
- Gates (inherited, F-9 protocol): (a) kidscore walnuts+pf rhat<1.01 AND
  ESS/draw>=0.1 (F-9 residual 1.014/0.093); (b) blr/esnc/esc/logmesq walnuts+pf
  ESS/s within noise-or-better of F-9 D_pf (esnc 335,922; esc 20,923; blr
  39,280; logmesq 19,628); (c) ctest green.

## Log

- (boot) reading done: WORKLOG F-9/F-11/F-11.2, f11-design Design 2 + inventory
  (adaptive_walnuts.hpp:76 discount, DEAD mass_additive_smoothing at
  config.hpp:631), research_sota + pass2, fortk-f9.md (D_pf numbers = gate b
  baseline). Fork external/walnutpie @ dev/init-robustness consulted for port
  patterns (chop/shrink/floor live there); per design caution, porting IDEAS
  with fresh minimal diffs, vendored structure preserved, all default-off.
- (setup) worktree + branch created; deps symlinks relative per charter; this
  log created first.
- (impl) ALL default-off, vendored structure preserved, fork consulted for
  port patterns only (fresh minimal diffs per the design caution):
  1. config.hpp: new WarmupConfig fields mass_window(0), mass_score_clip_k(0),
     mass_var_floor(0), mass_shrink_kappa(0), step_batch_stride(1) + builder
     setters (validate_nonnegative added to validate.hpp; 0 = off for the new
     double knobs, 1 = off for the stride). mass_additive_smoothing DECISION:
     WIRED, not removed (design: "free floor-ish knob adjacent to change 3");
     consumption var <- (1-s)var + s in inv_mass_estimate, guarded s>0; its
     setter relaxed finite-positive -> nonnegative so 0 (=off) is passable;
     vendored DEFAULT flipped 1e-5 -> 0.0 (upstream's 1e-5 was never consumed
     anywhere = dead value, so no upstream behavior is being changed; wired
     knob is inert by default at every level).
  2. online_moments.hpp: weight() accessor only (n_eff proxy for shrinkage).
  3. adam.hpp: 8th ctor arg batch_stride (default 1); operator() accumulates
     the mean of `stride` alphas per update. Stride 1 calls the ORIGINAL
     update body verbatim (bitwise); t_ counts UPDATES (lr decay follows
     update count -- the W-1 "Adam was implicitly calibrated for that
     frequency" point). W-1 evidence: rhat-bad 17/21 -> 9/21, single biggest
     adaptation fix in the walnutpie lane. Optimizer swap (DA etc.) NOT
     ported: W-1 verdict "optimizer choice SECONDARY", DA-without-batching
     collapses (10 aborts); research_sota rejected-list agrees. Two-phase
     decay NOT implemented (W-22's step-drift finding is about early-exit
     quality, not this gate; add only if gates demand).
  4. adaptive_walnuts.hpp MassEstimator: (a) ctor stores re-seed variances;
     (b) observe(): caller-side Winsorization of the score stream at the
     PRE-update running mean +/- k*sd (bounded influence; design's "cheaper:
     keep OnlineMoments pristine"); (c) chop: at (iteration+1)%window==0 and
     not the final iteration, restart_windows() RE-SEEDS both estimators at
     their CURRENT estimate with weight mass_init_count (design's warm
     re-seed, NOT the fork's reset-to-original-seeds) and moves the shrink
     targets to the current variances; (d) inv_mass_estimate(): kappa shrink
     toward re-seed variances (w/(w+kappa), w = estimator weight) -> var
     floor on BOTH variances -> additive smoothing -> sqrt ratio. All-off
     path: arithmetic identical to stock (guards skip; same expression).
     Fisher-HMC Thm 2.2 citation added (design change 1, zero code).
  5. stanli wiring: WalnutsConfig + 6 fields (defaults = stock), builder
     chain in walnuts.cpp; regions.cpp flags --w-chop/--w-clip-k/
     --w-var-floor/--w-shrink-kappa/--w-smooth/--w-batch (walnuts arm only),
     SAMPLE_W_ADAPT provenance line + CSV header f112(...) tag.
  6. tests/test_walnuts_adapt.cpp (property tests, W-8 discipline, BEFORE
     sampling): gaussian convergence stock/each-knob/all-on; degenerate
     constant stream finite; giant-outlier scores bounded WITH clip vs
     collapse WITHOUT (control); chop steady-state + regime-shift tracking;
     stride-1 Adam bitwise stock; off-config == stock-config field check.
     Registered in CMakeLists with the walnuts.cpp C++20/third_party
     treatment.
- (syntax) test TU (pulls all edited vendored headers) g++ -std=c++20
  -fsyntax-only vs deps/math Eigen 5.0.1: clean. Full build deferred to F-10's
  atomic apply.
- (coordination) F-10 apply CONFIRMED complete before first build:
  logs/fortk-f10.md documents the patch landed + cmp-verified; deps/stan
  shows only base_nuts.hpp 63+/13- (their scope, draw-neutral per their
  gates; not linked into the walnuts path beyond pf, which is untouched).
  F-10's preserved stock binary (bench/fortk_f10/fortk_t1r.stock, built at
  9b2bf80 pre-patch) = my bitwise-gate control.
- (build) cmake -B build-f112 -DCMAKE_BUILD_TYPE=Release; targets fortk_t1r
  + test_walnuts_adapt, -j4 (one OOM-killed cc1plus under concurrent F-10
  build at load 9.6; resumed -j2 clean). Property tests ALL PASS.
- (gate ii) all-off BITWISE check vs F-10's preserved stock binary
  (bench/fortk_f10/fortk_t1r.stock @ 9b2bf80, pre-patch deps): 18/18
  IDENTICAL (3 models x 3 seeds x {u,pf}), non-vacuous (202 lines each).
  First attempt was VACUOUS (tool needs worktree CWD for deps/stanc3);
  fixed + verified CSV sizes. Gate (ii) PASS.
- (campaign) kidscore ladder, F-9 protocol, 3 reps x 4 chains (runner
  bench/fortk_f112/run_f112.py, analyzer analyze_f112.py; raw under
  bench/fortk_f112/). D0 spot-check BRIDGES F-9 exactly: rhat med 1.0137
  (F-9: 1.014), ESS/draw 0.093 (F-9: 0.093) -- protocol valid.

KIDSCORE LADDER (rhat med / ESS-per-draw med, 3 reps):
  D0            1.014 / 0.093   (F-9 reproduction)
  D_chop        1.008 / 0.090   rhat FIXED, ESS short (rep1 rhat 1.032)
  D_chop_robust 1.017 / 0.082   robust pieces HURT
  D_chop_k5     1.035 / 0.058   kappa5 HURT badly
  D_chop_w25/100 1.016 / 0.088/0.085  window size irrelevant
  D_chop_b50    1.013 / 0.115   ESS fixed, rhat short
  D_chop_b25    1.010 / 0.108   FIRST FULL PASS of gate (a)
  D_b50         1.015 / 0.112
  D_b25         1.008 / 0.106   PASS -- single knob!
  D_b10         1.008 / 0.108   PASS -- best gate-b profile
  D_b10_d75     1.008 / 0.095   decay 0.75 kills ESS (tiny frozen steps)
  D_cb25_a70/60 1.013/1.015 ... accept-target probe fails (see below)

GATE (a) VERDICT: PASS. Minimal passing config = --w-batch 10 (mean-batch
stride 10, single knob): kidscore walnuts+pf rhat 1.008 < 1.01 AND
ESS/draw 0.108 >= 0.1 (F-9 residual was 1.014 / 0.093).

GATE (b) VERDICT (D_b10, vs F-9 D_pf medians; F-9's own rep noise band =
min/max 0.63-0.92):
  esnc    ESS/s 420,983 = 1.253x (BETTER); ESS/draw 0.813 vs 0.762 parity+
  esc     ESS/s 16,207 = 0.775x (inside F-9 band 0.76); ESS/draw 0.074 in
          F-9 band 0.068-0.104; rhat 1.076 ~= F-9 1.074
  logmesq ESS/s 16,369 = 0.834x (below F-9 band 0.946); ESS/draw 0.133 vs
          0.106 BETTER; rhat 1.014 vs 1.026 better
  blr     ESS/s 15,842 = 0.403x (FAIL); ESS/draw 0.210 vs 0.149 = 1.41x
          BETTER; rhat 1.005 vs 1.006 better
  => PARTIAL: statistical quality (the ESS/draw sanity + rhat) better-or-
  equal on ALL FOUR; the ESS/s shortfall on blr (and marginally logmesq)
  is pure WALL (frozen step 0.057 vs stock 0.22 -> ~3.5x more micro steps
  per iteration), not mixing. No new divergences (rhat better-or-equal
  everywhere; walnuts reports no divergence diagnostics by design).

MECHANISM (the campaign's real finding -- walnutpie-lane evidence):
- Batched Adam CONVERGES to the true E[alpha]=0.8 root; noisy per-obs
  Adam freezes early (lr ~0.05/sqrt(2000+) ~ 1e-3) at a step 4x larger.
  walnutpie's 0.8 target and its t^-0.5-decayed noisy Adam are a COUPLED
  calibration: denoising the statistic without re-tuning the target buys
  ESS/draw (+7..+41%) at 1.5-3.5x wall (work ~ 1/step).
  Frozen-step ladder measured (blr): stock 0.214-0.225, b10 0.057,
  b25 0.019-0.025, b10+d75 0.0017, b25+d75 0.0012. kidscore: stock
  0.40-0.51 (chains disagree), chop 0.475-0.525 (ALIGNED -- chop's real
  effect), b25 0.068-0.101.
- Accept-target rescue REJECTED empirically: cb25+a70/a60 keeps blr
  broken (rhat 1.06) and breaks kidscore rhat (1.013/1.015) -- the
  target is not a free dial under batching.
- Decay 0.75 REJECTED: freezes at 0.001-0.002 steps, walls 0.5-0.7s.
- MASS-SIDE DESIGN PIECES ARE NET NEGATIVES here (clean negative result,
  consistent with W-2's honest bound): chop (warm re-seed) regresses blr
  ESS/draw 0.149 -> 0.062 (freeze metric rests on a 50-draw window vs
  the discounted ~1000-draw estimate -- noise, not staleness, binds on
  well-behaved low-dim models); robust clip/floor hurt kidscore (0.082,
  rhat 1.017); kappa5 hurt kidscore badly (0.058, rhat 1.035); window
  size 25/100 irrelevant. The fork's W-6 chop-win (blr 201->401 ESS on
  the CLI) does NOT transfer to this vendored codebase at these settings
  (the fork's stack differed: batch50 + clamp + cold-reset chop).
- The kidscore gate was fixed by the STEP loop (W-1's batching evidence,
  at stride 10-25), not by the mass estimator: lever ordering within
  adaptation is step-noise > mass-staleness on this class.

## Commits (fortk/f112-walnuts, not pushed)

- 316afe2 vendored walnutpie adaptation knobs (all default-off)
- 7d7c9da stanli walnuts wiring + fortk_t1r adaptation flags
- 58ec219 estimator property tests (test_walnuts_adapt)

## GATE (c): ctest 64/64 PASS (63 prior + test_walnuts_adapt), on the
F-10-patched shared deps.

## FINAL VERDICT

(a) PASS -- kidscore walnuts+pf rhat 1.014 -> 1.008, ESS/draw 0.093 ->
0.108 with --w-batch 10 (mean-batched step Adam, single knob).
(b) PARTIAL -- esnc 1.253x better; esc in F-9's noise band; logmesq/blr
ESS/s below band on WALL ONLY (frozen step 4x smaller under honest 0.8-
target convergence; ESS/draw 1.26x/1.41x BETTER, rhat better-or-equal
everywhere, no new divergences). The ESS/s-vs-ESS/draw tradeoff is
intrinsic to repairing the step loop's noise calibration without
re-tuning walnutpie's accept target (probed: stride 5-100, decay 0.75,
accept 0.6/0.7 -- no config dominates; evidence above).
(c) PASS 64/64.
Design-2 mass-side pieces (chop/robust/floor/kappa/smooth): implemented,
property-tested, and empirically NET NEGATIVE or inert on the gate set --
the pre-registered honest negative, now with the mechanism (50-draw
window noise vs discounted 1000-draw estimate; W-6's CLI chop-win does
not transfer to this codebase/stack). Step-loop batching (W-1) is the
lever that moved both gate metrics; stride 10-25 is the sweet spot.
