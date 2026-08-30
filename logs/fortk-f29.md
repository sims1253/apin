# F-29 incremental log — BIG SWING 1: walnuts adaptive-K + mass shrinkage

Binding charter: WORKLOG "F-29 pre-registered" (2026-08-29). Read order
honored: F-29 charter, F-21 VERDICT + logs/fortk-f21.md (multiplier
mechanism, heterogeneity miss, per-model K table), F-28 VERDICT +
logs/fortk-f28.md (shrinkage-fails-on-NUTS mechanism + recorded walnuts
hypothesis), F-9 VERDICT (pf-init protocol), F-16 VERDICT (failure set +
arm-C baselines), F-18/F-19 (interleaved-wall discipline).

Setup:
- Worktree external/stanli-pr-waln, branch fortk/f29-adaptiveK off
  fortk/f21-retune @ 7f4f241. Binary build-pr/fortk_t1r @ 7f4f241
  (md5 a21dbe01934d51e0416d18fd72179edc, Aug 28 14:15) = the gate-(b)
  byte-identity reference; snapshotted to bench/fortk_f29/ref_f21_t1r
  BEFORE any rebuild.
- This branch's ancestry is the jit-tier line: deps/stan must be
  PRISTINE for the build (arm C = fused nuts STOCK loop). Found the
  shared tree external/stanli/deps/stan carrying sibling patches
  (+250/-35: 0001-0003 loop series + 0004 lw-shrink, from F-28+ lanes).
  Plan: restore pristine for MY build + ctest window only, re-apply the
  patch series immediately after (serialized-build courtesy; noted here
  per charter).
- Raw bench/fortk_f29/. Sibling agents F-30/F-31 concurrent: builds -j2
  serialized, campaigns note the shared box (ESS metrics immune; wall
  only interleaved same-day same-binary comparisons).

## ADAPTIVE-K RULE — PRE-STATED BEFORE ANY CAMPAIGN (binding)

Signal choice: the observed trajectory-depth distribution during late
warmup (the charter's first candidate; the F-21 esnc evidence directly
names it: "collapsed at K=8 because trajectories U-turn immediately —
shallow average depth at K=8 vs deep at K=4 is the discriminator").

Mechanics (from the vendored walnuts.hpp): each transition produces a
trajectory of 2^depth MACRO steps of duration `step` (Adam's step during
warmup, K*step at sampling); the generalized U-turn check first fires
after 2 macro steps, so 2 is the minimum non-degenerate trajectory. The
physical U-turn timescale T (mass-scaled) is a property of the target;
scaling the frozen macro time by K divides the sampling-phase trajectory
length (in macro steps) by ~K relative to late-warmup behavior.

RULE (deterministic, per-chain, warmup-phase-only):
- Window: the final floor(max_iter/4) warmup iterations (1000 warmup ->
  iterations 750..999, 250 observations). Record m_i = 2^{depth_i}.
- Discriminator: M = median(m_i) (even N: mean of the two central order
  statistics). Empty window -> M undefined -> K = 1 (most conservative).
- K = largest element of the grid {1, 2, 4, 8} with M/K >= 2, i.e.
  K = min(8, max(1, 2^floor(log2(M/2)))). M < 4 -> K = 1.
- Rationale: the projected sampling-phase trajectory M/K must stay >= 2
  macro steps (one full doubling); projecting below 2 is exactly the
  F-21 esnc-at-K=8 immediate-U-turn regime. Grid capped at 8 (the F-21
  grid top; no tuning past it).
- Consistency with F-21's per-model optima (the bet): esnc peaked K=4
  (projects to the floor exactly) and collapsed K=8; logmesq/kidscore
  took K=8 without collapsing => their M must be >= 16 where esnc's is
  ~8. The campaign's mechanism table records M per model and where K
  landed — no adjustment if the bet misses (grid rule binding).

Interaction with shrinkage: under --w-shrink L the warmup runs on the
shrunk metric, so depths reflect the shrunk dynamics and the rule stays
self-consistent. Both knobs compose independently.

## SHRINKAGE KNOB — PRE-STATED

Vendored MassEstimator::inv_mass_estimate(): after the existing kappa /
floor / smoothing transforms, with L > 0 shrink BOTH variance estimates
toward their own means (trace-preserving per vector, F-28 patch-0004's
formula applied to the walnutpie estimator):
  draw_var  <- (1-L) draw_var  + L mean(draw_var)
  score_var <- (1-L) score_var + L mean(score_var)
L = 0 (default) skips the block entirely -> stock arithmetic untouched.
Applied at every estimate (warmup iterations included — the F-28 regime:
the step adapter sees the metric it will sample under). F-28's recorded
hypothesis under test: walnuts' within-orbit step adaptation does NOT
derive its frozen step from metric curvature the way NUTS' dual
averaging does, so the step should NOT collapse 6-32x under isotropy;
the campaign's stepsize__ medians L=0 vs L=0.3 are the direct read.

Plumbing: WarmupConfig.mass_mean_shrink (0 = off) + adaptive_step_mult
(bool, off) in the vendored config; WalnutsConfig.step_mult_auto +
.mass_mean_shrink in stanli; tool --w-step-mult auto (default stays
numeric 1.0) + --w-shrink L (default 0, validated [0,1]); echo lines
extended; CSV tags appended ONLY on non-default values (default path
byte-identical); run_walnuts prints a W_STEP_AUTO diagnostics line (K,
M median/mean, n, frozen step) ONLY when auto mode is on.

## GATES (never loosen)

(a) THE DEFAULT-MAKER: phase-1 6 {esnc, esc, blr, pilots, kidscore,
    logmesq} + failure set {bym2, diamonds, kronecker}, 4 chains x
    1000+1000, 3 reps medians, arms C (fused nuts stock loop, MY
    binary) and D (--w-batch 10 --w-step-mult auto, pf-init) and DL
    (D + --w-shrink 0.3) interleaved same-day model-major; geomean
    ESS/s D > C (harder reading: geomean over all 9 models; the
    phase-1-only geomean ALSO reported for F-21 comparability); AND
    all-chain R-hat < 1.01 on EVERY model for the gate arm; AND
    kidscore retained (R-hat < 1.01, ESS/draw >= 0.1).
(b) Default-off byte-identity: --w-step-mult 1 --w-shrink 0 (i.e. no
    flags) => md5-identical CSVs to the 7f4f241 binary on esnc
    walnuts+pf smoke; ctest green (70/70-era count on this line).
Failure of (a): the mechanism table IS the deliverable (K landing +
discriminator values per model; the shrink x step interaction). Never
tune past the pre-stated rule.

(work in progress — appended incrementally below)

## INCIDENT 2026-08-29 ~22:56 — WORKSPACE WIPE + BASE RECOVERY (owned by F-29)

- external/ was deleted ENTIRELY mid-session (~22:56; F-31's build died
  on it; observed directly: all worktrees + deps + binaries gone), and
  bench/ was deleted (tracked files recovered via git restore; ALL raw
  campaign dirs fortk_f* are gone permanently — the .md lane logs are
  the evidence of record, as designed). Cause unknown, not
  parent-initiated, user informed (coordinator). A later coordinator
  note that the stanli git store + my uncommitted edits survived was
  FACT-CHECKED FALSE: the current external/stanli is a FRESH RE-CLONE
  (main @ 33f79de, origin branches only); my fortk/f29-adaptiveK branch
  and uncommitted F-29 edits died with the original worktree. The edits
  were re-applied verbatim from the session (they were complete +
  standalone-property-tested before the wipe).
- BASE RECOVERY (this session, complete):
  - external/stanli re-cloned from git@github.com:sims1253/stanli.git
    (all fortk/* research branches live on the remote per the
    publishing round — f21-retune @ 7f4f241 verified identical).
  - deps re-fetched via deps/fetch.sh: math@8f326d1459d, stan@c96d04115
    PRISTINE (git diff EMPTY — this line needs no patches; the F-29
    charter's precondition satisfied by construction).
  - stanc REBUILT from source at 4d440ee (stan-dev/stanc3 clone; opam
    f13 switch survived in $HOME) into deps/stanc3/stanc with
    stanc.src=4d440ee provenance. WARNING to siblings: the F-21/F-29
    byte-identity chain (recorded md5 b1bb391c...) depends on this
    4d440ee stanc; fetch.sh's newer 5b824ee provenance check would
    discard it — DO NOT re-run fetch.sh's stanc block on the shared
    tree without coordinating (F-31 has gone private-deps, which
    removes the hazard on its side).
  - Worktree external/stanli-pr-waln re-created at the SAME PATH
    (FORTK_VECMATH_DIR path macros match the original build), branch
    fortk/f29-adaptiveK off origin/fortk/f21-retune @ 7f4f241; deps
    symlinks math/stan/stanc3 -> ../../stanli/deps/*.
  - BASE-RECOVERY SIGNAL (siblings waiting on this): shared
    external/stanli deps are READY (math+stan fetched, stan PRISTINE,
    stanc 4d440ee installed). F-30 may re-add its worktree and apply
    patches 0001-0004 AFTER my -j2 build window (serialized; announce
    in your own log per convention).
- f21 reference binary: the original build-pr/fortk_t1r (md5 a21dbe...)
  was wiped; the gate-(b) reference is the RECORDED CSV md5
  b1bb391c809c7ee686ca6d690da38fc9 (F-21 gate (d), esnc walnuts+pf
  1000+1000 seed 20260826). Restoration validation = rebuild 7f4f241
  clean and reproduce that md5 BEFORE applying F-29 edits... amended:
  practical order = build WITH F-29 edits (default-off) and reproduce
  the md5 on the default path (the knobs are provably default-off by
  construction + property tests; the original two-step binary dance
  died with the wipe). A mismatch triggers the full investigation
  (stanc vintage, compiler flags, source pin) before any campaign.

## Implementation log (pre-wipe; re-applied verbatim post-wipe)

- Branch fortk/f29-adaptiveK created off 7f4f241; binary reference
  snapshotted (bench/fortk_f29/ref_f21_t1r, md5 a21dbe01934d51e0416d18f-
  d72179edc); sibling deps/stan patch state saved to
  bench/fortk_f29/deps_stan_sibling_state_20260829.patch (+250/-35:
  0001-0004) before any pristine restore.
- Implemented exactly as pre-stated: vendored config.hpp (mass_mean_shrink
  [0,1] inclusive + adaptive_step_multiplier flag, builder setters, config
  dump), MassEstimator mean-shrink block (after smoothing, before the
  sqrt ratio; L=0 skips), AdaptiveWalnuts late-window depth recorder
  (pure observation; recording flag off => zero overhead + bit-identical),
  adaptive rule in sampler() (K = min(8, 2^floor(log2(M/2))) for M >= 4
  else 1; M = late-window median; explicit multiplier ignored in auto
  mode), getters (chosen K, late median/mean/count), stanli WalnutsConfig
  (step_mult_auto, mass_mean_shrink) + builder wiring + W_STEP_AUTO echo
  line (auto mode only), tool --w-step-mult K|auto + --w-shrink L (CLI
  validated), SAMPLE_W_ADAPT echo extended (step_mult=%s auto|g +
  mean_shrink), CSV f29 tags appended only on non-default values.
- Property tests 11 (mean shrink: L=0 bitwise stock; anisotropy
  compresses monotonically; finite) + 12 (adaptive: warmup draws
  bit-identical under auto; K equals the pre-stated rule on the recorded
  median; late window exactly the final quarter; frozen macro time
  exactly K x; off-mode inert) added inside test_walnuts_adapt; suite
  run STANDALONE against the vendored headers: ALL PASSED (incl. the
  pre-existing 1-10).
- Coordination: sibling F-31 started a full build (build-f31, external/
  stanli-f31) against the shared deps/stan at 22:32 — deps/stan pristine
  restore DEFERRED until their build completes (a mid-build header swap
  would corrupt their objects). [SUPERSEDED by the incident above: the
  wipe killed that build; F-31 has since gone private-deps. The re-fetched
  shared deps/stan is PRISTINE by construction — no restore needed.]

## Post-wipe re-application (commit 94ae8d0 on fortk/f29-adaptiveK)

- All six files re-applied verbatim from the session (the edits were
  complete and standalone-property-tested pre-wipe): vendored config.hpp +
  adaptive_walnuts.hpp, stanli walnuts.{hpp,cpp}, tools/fortk/regions.cpp,
  tests/test_walnuts_adapt.cpp (tests 11 + 12 + test-9 extension).
- Re-validated standalone: test_walnuts_adapt ALL PASSED (incl. 11/12:
  L=0 bitwise stock + monotone anisotropy compression; auto warmup draws
  bit-identical + K == pre-stated rule on the recorded median + window ==
  final quarter + frozen macro time == K x stock + off-mode inert);
  regions.cpp + walnuts.cpp fsyntax-clean under the real build flags.
- bench/fortk_f29/run_f29.py + analyze_f29.py recreated (campaign
  runner: C/D/DL arms interleaved model-major, prewarm, done-markers,
  W_STEP_AUTO parsing; analyzer: gate tables + K-landing + shrink-x-step).
- build-pr configured -DCMAKE_BUILD_TYPE=Release (the fortk convention
  from logs/fortk-f112.md; RelWithDebInfo is the CMake default — the md5
  gate will adjudicate the choice). BUILD WINDOW NOW (announce:
  siblings, my -j2 runs in external/stanli-pr-waln/build-pr against the
  shared PRISTINE deps/stan; do not patch/re-fetch the shared tree until
  this log records the build complete).

## RESUME 2026-08-30 02:46 (post-pause; usage-limit reset)

- Resumed per charter. Read log + WORKLOG F-29/F-21/F-28 first. State
  found: worktree CLEAN on fortk/f29-adaptiveK @ 94ae8d0 (salvage/
  re-application already done — diff vs origin/fortk/f21-retune = the
  six files, +396/-6; no orphaned-dir diff needed); binary
  build-pr/fortk_t1r @ Aug 29 23:29 (built during my pristine window).
- SHARED DEPS NOTE (siblings): external/stanli/deps/stan is PRISTINE
  (git diff empty, 02:46). The parent's F-30 build-continue command at
  02:33 attempted to apply 0001-0003 to the shared tree but SKIPPED
  (patch files absent in its worktree); F-30's actual build uses its
  PRIVATE deps copy (verified -I flags point at stanli-f30/deps). My
  build is complete; nothing of mine touches shared deps anymore.
- BUILD WINDOW CLOSED (build complete at 23:29 pause).
- GATE (b) BOTH GREEN, measured this session:
  - Default-path byte-identity: esnc walnuts+pf 1000+1000 seed 20260826
    with the f29 binary -> sample CSV md5 b1bb391c809c7ee686ca6d690da38fc9
    == the F-21 record EXACTLY (Release build-type adjudicated). Raw:
    bench/fortk_f29/gateb/.
  - ctest 70/70 (1.41 s, all binaries from the pristine window).
- KNOB SMOKE (esnc, --w-batch 10 --w-step-mult auto --w-shrink 0.3):
  W_STEP_AUTO K=4 late_macro_med=8.0 mean=7.0 n=250 frozen=2.501 — the
  rule fires exactly as pre-stated (M=8 -> K=4; M/K=2 = the floor), and
  K=4 is F-21's measured per-model optimum for esnc. Raw:
  bench/fortk_f29/knob/.
- CAMPAIGN LAUNCHED 02:52 (run_f29.py, background): 9 models x 3 reps x
  arms C/D/DL model-major interleaved, 4 chains x 1000+1000, <=4 procs;
  F-30's parent-continued build (-j2, private deps) concurrent on the
  box — wall arms interleaved same-model-adjacent as designed.
- INCIDENT 03:59: the background runner was KILLED at 51/81 cells (rep1
  kronecker C in flight; no error in campaign.out — external kill, same
  class as the usage-limit pauses). Resume-safe design worked: relaunched
  --from-rep=1 04:02; done-markers skipped the 51 completed cells; the
  interrupted kronecker cell re-ran clean.

K-LANDING + STEP TABLE — SUPERSEDED by the final tables under VERDICT
below (kept only for the kill-incident timeline; interim numbers were
reps 0-1 partials).

## CAMPAIGN COMPLETE 2026-08-30 04:53 — VERDICT

81/81 cells (9 models x 3 reps x C/D/DL x 4 chains x 1000+1000, one
binary, model-major interleaved, same-day). Full tables: analyzer
stdout saved at bench/fortk_f29/analysis.txt (3.9 GB raw local per
runs/ convention).

### GATES

- (b) Default-off byte-identity + ctest: **PASS** (measured 02:46-02:51:
  esnc walnuts+pf 1000+1000 seed 20260826 default path -> CSV md5
  b1bb391c809c7ee686ca6d690da38fc9 == F-21 record EXACT; ctest 70/70).
- (a) ESS/s leg: 3-rep MEDIANS D/C phase1 **1.010x**, all-9 **1.227x**
  (per-rep phase1 1.010/1.502/0.744; all9 1.227/1.576/0.972 = wall-noise
  band; all9 >1 is driven by C's td-saturated kronecker/diamonds cells
  where C's frozen steps are 0.003-0.004, not by D quality). DL/C
  0.414x / 0.564x = shrinkage loses outright.
- (a) R-hat leg: **FAIL 7/9** for D (3-rep median rhat_max): esnc
  1.0113, esc 1.0421, pilots 2.2772, kidscore 1.0165, bym2 1.0172,
  diamonds 1.0148, kronecker 1.0377; pass only blr 1.0030, logmesq
  1.0034. (C itself: esc 1.029, pilots 1.069, bym2 1.008, kronecker
  1.008 — known; the gate binds the GATE arm.)
- kidscore gate: **FAIL** — D rhat 1.0165, ESS/draw 0.080 (vs C 0.348,
  vs F-21's fixed-K=8 0.457).

**VERDICT: MISS (gate a) — walnuts does NOT become the default. The
mechanism table below is the deliverable per pre-registration. No
tuning past the pre-stated rule was done.**

### MECHANISM TABLE (3-rep medians; fz = median frozen stepsize; K/M
from W_STEP_AUTO chain-0 per rep)

  model      C: wall/fz/ESSdr/rhat     D: K(3reps) M_med | wall/fz/ESSdr/rhat
  esnc       0.015s/0.449/0.999/1.003  4 4 4    8   | 0.009s/2.67/1.488/1.011
  esc        0.035s/0.238/0.171/1.029  4 4 8    8   | 0.019s/2.09/0.136/1.042
  blr        0.024s/0.109/0.349/1.004  8 8 8   16   | 0.048s/0.59/0.421/1.003
  pilots     0.670s/0.005/0.018/1.069  8 8 4   16   | 0.083s/1.84/0.003/2.277
  kidscore   0.111s/0.121/0.348/1.003  2 4 2    4   | 0.065s/0.69/0.080/1.017
  logmesq    0.093s/0.077/0.484/1.002  8 8 8   16   | 0.049s/2.33/0.317/1.003
  bym2      22.6 s/0.077/0.994/1.008   8 8 8   16   | 24.8 s/1.00/0.874/1.017
  diamonds  72.9 s/0.004/0.802/1.004   8 8 8   16   | 39.2 s/0.61/0.397/1.015
  kronecker 598 s/0.003/0.398/1.008    4 8 8  8-16  | 32.4 s/1.02/0.140/1.038

### FINDINGS (ranked)

1. THE RULE FIRED EXACTLY AS PRE-STATED — deterministic, zero manual
   adjustment, self-consistent under shrinkage (bym2 DL M_med=32 -> K=8;
   kronecker DL M dropped 16 -> 8-12 -> K=4: the discriminator tracks
   the shrunk dynamics it actually sampled, as designed).
2. THE KILL = the MEDIAN under-reads heavy-tailed depth distributions.
   kidscore M_med 4 vs M_mean 11.8-23.6 -> K=2 where F-21's optimum is
   K=8: kidscore ESS/draw collapsed 0.348 (C) / 0.457 (F-21 m8) ->
   0.080. Same signature esc (med 8 / mean 11-14) and diamonds (med 16
   / mean 31-41). The pre-stated bet ("kidscore's M must be >= 16")
   MISSED for exactly this reason; honored without adjustment.
3. WHERE THE BET HIT, D == THE BEST FIXED-K arm: esnc K=4 ESS/draw
   1.488 (F-21 m4 peak region), ESS/s 2.92x C; blr K=8 ESS/draw 0.421
   (== F-21 m8); logmesq K=8 ESS/s 1.38x C (F-21: 1.30x). Adaptive-K
   from warmup IS sound where the depth distribution is unimodal.
4. SHRINK x STEP — the F-28 recorded hypothesis is CONFIRMED on the
   mechanism, REFUTED as a win: frozen-step DL/D geomean **0.787x**
   (range 0.246-2.124; blr and esc steps ROSE 2.12x/1.37x) — nothing
   like NUTS' 6-32x collapse. But DL loses ESS/draw nearly everywhere
   (only logmesq up 0.317 -> 0.403) => DL/C 0.414x. At L=0.3 the cost
   of shrinkage on walnuts is MIXING, not step. Walnutpie-side
   shrinkage: dead, with a DIFFERENT mechanism than F-28's NUTS death.
5. Failure set: wall wins are real but not bankable — kronecker D 32.4s
   vs C 598s (18x wall) yet ESS/draw 0.140 vs 0.398 and rhat 1.038;
   diamonds 39 vs 73s, rhat 1.015; bym2 rhat 1.017 vs C 1.008. None
   crossed 1.01 — agrees with F-21: the too-small frozen step was part
   of their problem, not all of it.
6. Boundary instability: M sits exactly at grid thresholds on esc /
   kidscore / pilots / kronecker — K flips 2x between chains and reps
   of the SAME model (esc D 4/4/8; kidscore 2/4/2). Per-chain K
   divergence adds rhat variance; a working adaptive rule would need a
   stable landing (tail statistic or per-model pooling) — recorded as
   the walnutpie-lane next signal, NOT pursued here (grid rule
   binding).

### SHIP STATE

Knobs default-off in fortk/f29-adaptiveK @ 94ae8d0 (six files, +396/-6
vs f21-retune): --w-step-mult auto + --w-shrink L (validated [0,1]),
W_STEP_AUTO diagnostic line (auto mode only), CSV tags only on
non-default, property tests 11-12 green, standalone suite green,
default path byte-identical, ctest 70/70. Branch NOT pushed (rule).

Raw: bench/fortk_f29/{gateb,knob,campaign/,campaign_raw.json,
analysis.txt}. Lane incident: the 03:59 external runner kill (above).
