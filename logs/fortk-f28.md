# F-28 incremental log — F-11 Design 1 at last: LW late-window mass shrinkage

Binding charter: WORKLOG "F-28 pre-registered" (2026-08-29) + F-11 Design 1
(logs/fortk-f11-design.md §B.1, read in full). Read order honored: design
doc (mechanism, anchors, gates, risks), WORKLOG F-28 charter, F-27 VERDICT
(ESS headroom now on ESS/draw side; warmup cannot be cut — window quality
is the lever), F-16 VERDICT (draw-poor subclass context, phase-2 corpus),
F-18/F-19 VERDICTs (ESS conventions, interleaved same-day wall discipline).

Setup:
- Worktree external/stanli-f26, branch fortk/f28-lwshrink off fortk/
  f26-capstone @ 70fd71a (NOT off f27-earlyexit — charter says f26 base).
- Surface: vendored deps/stan (shared symlink, stan @ c96d0411 with
  patches 0001-0003 +222/-35) var_adaptation.hpp learn_variance — the
  design's anchors were written against this shape and still match
  (regularization at the `var = (n/(n+5.0))*var + 1e-3*(5.0/(n+5.0))*Ones`
  line).
- Mechanism (design B.1 + charter): at every variance window end, after
  stock regularization, optionally shrink the diagonal toward a
  trace-preserving scaled identity:
    shrunk = (1-lambda)*sample_post_reg + lambda*mean(sample_post_reg)*I
  with fixed lambda L from --lw-shrink (default 0.0 = stock arithmetic
  bit-identical, same expression order). LW analytic lambda deferred
  unless trivially clean (fixed-flag-first per charter).
- Plumb: var_adaptation.hpp setter -> stepsize_var_adapter getter (exists,
  stepsize_var_adapter.hpp:20) -> stanli nuts.cpp -> NutsConfig -> tool
  --lw-shrink. Tool echoes final inv_metric (already? check; if not, add
  under an existing diagnostics flag) for gate (c).
- Carry: patches/deps-stan/0004-lw-shrink.patch + fetch.sh hook already
  globs *.patch in sorted order — 0004 rides free; the file is the change.
  Atomic patch application at session start (established discipline; deps
  shared via symlink).
- GATES (never loosen):
  (a) L=0 BITWISE: draws md5-identical to f26 binary on esnc/blr/hier_2pl
      (--lean arm, 1000+1000, seed 20260826).
  (b) ACTIVE: draw-poor {kronecker_gp, radon_pp, lsat_model} + phase-1
      {esnc, blr, kidscore, logmesq}; 3 reps, arms interleaved same-day,
      --lean, L in {0.1, 0.3, 0.5} fixed grid; geo ESS/s >= 1.0x vs L=0
      AND >= 1.10x on the draw-poor subclass; ESS_bulk/draw per-model
      reported; R-hat < 1.01; divergences not worse (pilots the funnel
      sentinel: div/1k L vs L=0).
  (c) MECHANISM: final inv_metric echo; trace(shrunk)/trace(stock) ~ 1;
      eigen-spread visibly moved on >=1 draw-poor model.
  (d) ctest 69/69 + default-off byte-identity (same as (a)).
- Grid outcome rules: pass at any L ships --lw-shrink (default 0); all-fail
  = honest negative with mechanism table; never tune past the grid.
- Rules: <=4 concurrent sampling procs, CPU only, -j2 builds, no upstream,
  no push, explicit staging, raw bench/fortk_f28/, do not touch
  /tmp/review/stanli, other worktrees' sources, WORKLOG.md, other logs.

(work in progress — appended incrementally below)

## Implementation + staging (commit a2656b2 on fortk/f28-lwshrink, off 70fd71a)

- Vendored var_adaptation.hpp (deps/stan shared tree, applied in place at
  session start = the atomic-patch discipline; carried as
  patches/deps-stan/0004-lw-shrink.patch, +28 lines, reverse-check
  verified, fetch.sh hook picks it up via the sorted *.patch glob — no
  ordering dependency on 0001-0003; fetch.sh comment extended for 0004):
  `set_lw_shrink(L)` + guarded post-regularization shrink at each
  variance-window end, `var <- (1-L)*var + L*mean(var)*I`. L=0 skips the
  block entirely -> stock expression order untouched.
- Plumbing: NutsConfig.lw_shrink (default 0.0); run_nuts sets it via
  sampler.get_var_adaptation() (both instantiations); the tool's BOTH lean
  drivers wired (lean-from-0 `va` instance + stock-warmup fallback), the
  --fits config, and `--lw-shrink L` CLI (validated [0,1], reject at
  parse). SAMPLE_ADAPT + LEAN_WARM echo the value; LEAN_METRIC (final
  inv_metric, exact doubles) already existed — that is gate (c)'s
  instrument.
- Build -j2 clean; ctest 69/69.

## Gate (a) — PASS (raw gate_a/)

--lean 1000+1000 seed 20260826 chain 1, f28 binary (default, no flag) vs
fortk_t1r.f26ref (the F-27-preserved binary rebuilt from 70fd71a, which
reproduced the recorded F-22..F-26 md5s):
- esnc  7b6c3c976582d16285eb58e030f50851 BOTH (the F-27-recorded value)
- blr   acbbeed55ac7f2cd6bb4faaa97dd9d83 BOTH
- hier_2pl 89ea07436325ee7f48a0e4f18f4d087f BOTH
3/3 md5-IDENTICAL.

## Gate (d) — PASS

- Default path (no flag, no lean) 200+200: esnc md5 5253067ddd95 +
  grads exec1=3741, blr b6e8df4bde54 + 11081 — exactly the recorded
  F-26 values (raw gate_a/byteid_*).
- ctest 69/69 (above).

## Gate (c) pre-check — MECHANISM CONFIRMED (raw mech/)

Frozen final inv_metric (LEAN_METRIC, 1000 warmup, seed 20260826):

| model | L | d | trace ratio vs L=0 | metric max/min | metric CV |
|---|---|---|---|---|---|
| radon_pp | 0 | 389 | 1.000 | 17,554 | 0.824 |
| radon_pp | 0.3 | 389 | 1.017 | 9.94 | 0.569 |
| radon_pp | 0.5 | 389 | 1.004 | 4.86 | 0.401 |
| lsat | 0 | 1006 | 1.000 | 175.9 | 0.138 |
| lsat | 0.3 | 1006 | 0.988 | 4.19 | 0.098 |
| lsat | 0.5 | 1006 | 0.991 | 2.43 | 0.069 |

- The stock late-window metric on radon_pp spans 4.3 orders of magnitude
  (max/min 17,554) — the draw-poor noise the design targets, made vivid.
  L=0.3 collapses it to ~10x, L=0.5 to ~5x. lsat: 176x -> 4.2x/2.4x.
- Trace ratio 0.988-1.017: the per-window arithmetic preserves trace
  EXACTLY; the end-to-end deviation is the shrinkage changing warmup
  trajectories -> different final-window data. Within the "~1" gate.
- Lambda engagement: the flag moves the metric exactly as the formula
  predicts (visible eigen-spread compression at every L on both models).

## Campaign (gate (b)) — RUNNING (bench/fortk_f28/campaign/)

run_f28_campaign.py: 8 models x 4 arms (L0/L01/L03/L05) x 3 reps x 4
chains, one binary, --lean --sample-arm 1, seeds 20260826+1000*rep+c,
arms interleaved model-major within rep, 4 concurrent chain procs,
sampler_wall = max SAMPLE_WALL exec1_s (F-26 convention), ESS via
harness/ess.R. kronecker_gp from /tmp/f16-stage (the eigh staging).
Models: radon_pp, lsat, esnc, blr, kidscore, logmesq, pilots (funnel
sentinel), kronecker_gp (last; ~17 min/cell x 12 cells).

## Gate (c) final — MECHANISM FULLY ENGAGED (campaign LEAN_METRIC, rep2 chain0)

| model | L | trace ratio | metric max/min | metric CV |
|---|---|---|---|---|
| radon_pp | 0 | 1.000 | 17,095 | 0.820 |
| radon_pp | 0.1 | 0.999 | 34.9 | 0.726 |
| radon_pp | 0.3 | 1.010 | 10.6 | 0.578 |
| radon_pp | 0.5 | 1.006 | 5.4 | 0.408 |
| kronecker | 0 | 1.000 | 98.7 | 0.677 |
| kronecker | 0.1 | 0.990 | 37.0 | 0.592 |
| kronecker | 0.3 | 0.980 | 14.1 | 0.434 |
| kronecker | 0.5 | 0.988 | 8.7 | 0.350 |

(lsat in the pre-check table above; same shape.) Trace preserved end-to-end
within 0.98-1.01; eigen-spread compressed 3-500x at every L; the knob does
exactly what the formula says on every draw-poor model. THE MECHANISM IS
NOT THE PROBLEM — see below.

## Gate (b) — FAIL AT EVERY L (raw campaign/, analysis.out)

ESS/s 3-rep medians, ratios vs L0 (F-26 conventions; geo over 8 models,
DP = draw-poor {radon_pp, lsat, kronecker}):

| arm | geo/L0 | DP/L0 | blr rhat | kidscore rhat |
|---|---|---|---|---|
| L=0.1 | 0.708 | 0.812 | 1.0126 | 1.0087 |
| L=0.3 | 0.438 | 0.461 | 1.0128 | 1.0097 |
| L=0.5 | 0.446 | 0.474 | 1.0237 | 1.0117 |

Both gates (>=1.0x all-model AND >=1.10x draw-poor) FAIL at all three L;
the rhat<1.01 quality gate ALSO fails on blr/kidscore at every L>0
(kronecker's baseline rhat 1.0146 > 1.01 at L0 already — marginal model;
L05 1.0226 is worse, L01 1.0128 no worse). Divergence sentinel (pilots,
the funnel): div/1k medians L0 259, L01 268, L03 250, L05 180 — inside
the cell's documented realization chaos; no attributable regression, no
signal (the cell is pathological at every arm, rhat 1.46-2.33).

## THE MECHANISM TABLE (why it fails — the honest negative's core)

ESS/draw (3-rep medians, ratio vs L0) vs the wall mechanism (grads/iter
median over 12 chains; eps_frozen median):

| model | ESS/d L0.1 | ESS/d L0.5 | gpi L0 -> L0.1 -> L0.5 | eps L0 -> L0.1 -> L0.5 |
|---|---|---|---|---|
| radon_pp | 1.57x | 1.78x | 36 -> 126 -> 244 | 0.240 -> 0.042 -> 0.019 |
| lsat | 1.92x | 1.95x | 21 -> 33 -> 62 | 0.247 -> 0.154 -> 0.075 |
| kronecker | 1.00x | 0.66x | 1000 -> 1002 -> 1006 (td-capped) | 0.0022 -> 0.0027 -> 0.0020 |
| kidscore | 0.54x | 0.44x | 32 -> 88 -> 182 | 0.113 -> 0.0080 -> 0.0035 |
| blr | 1.10x | 1.08x | 16 -> 22 -> 38 | 0.109 -> 0.040 -> 0.019 |

- The designed effect IS REAL on the draw-poor subclass: ESS/draw +57-95%
  on radon/lsat (metric de-noising works — the noisy small entries of the
  stock window variance were throttling mixing).
- But the shrunk metric deliberately FLATTENS real anisotropy, and NUTS
  pays for isotropy in step size: the DA equilibrium eps collapses 6-32x
  (kidscore 0.113 -> 0.0035), leapfrogs/iteration rise 3.5-6.7x, and
  under wall ~ leapfrogs the ESS/s loses everywhere. On kronecker (already
  treedepth-saturated at 2^10 in every arm) the flattened metric only
  loses ESS (0.65x at L0.5).
- On well-conditioned models (kidscore) the stock window variance is
  well-estimated: shrinking toward the identity throws away real scale
  information — ESS/d 0.54x and rhat above gate at the mildest L.
- The one >1.10x ESS/s cell (lsat L01 1.249x) does not rescue the
  registered geomean gates — not cherry-picked past them (grid rule).

VERDICT: HONEST NEGATIVE at the registered gates. The Fisher-HMC-style
prior ("a better diagonal is worth ~1.3x") does not transfer to this
stack at fixed trace-preserving lambda: metric NOISE was not the binding
constraint — metric ANISOTROPY INFORMATION is worth more than the noise
in it. Same session pattern as F-27's cross-lane non-transfers.

## Shipping decision (grid outcome rules)

All-fail => no recommended L; --lw-shrink stays ON THE BRANCH default 0
(bit-identical, gate (a)/(d)). NO PR edit: the materiality clause is for
headline wins to label; an all-fail grid ships nothing to the PR notes.
Branch fortk/f28-lwshrink @ a2656b2 (implementation + patch 0004 +
fetch.sh comment), NOT pushed. deps/stan tree carries 0001-0004
(+250/-35), reverse-checks clean, fetch.sh idempotent.

## Incidents / notes

- Region-cache write race on cold 4-chain cells (truncated .so, dlopen
  fail) — fixed the F-26 way: sequential per-model prewarm before the
  campaign (run_f28_campaign.py prewarm()).
- /tmp/f16-stage's stanc is the F-13 FUSION stanc; its STuple-typed fused
  MIR is only readable by eigh-branch stanli (PR #3 is NOT in f26's
  ancestry). Kronecker ran under the STOCK pinned stanc from the worktree
  cwd (unfused graph, ops=223->96 regions=33, the F-19 stock-arm shape;
  F-16 proved fused-vs-unfused kronecker draws bit-identical) — all four
  arms share it, internally exact.
- The campaign runner was killed externally twice mid-kronecker (harness
  side); done-markers made every resume clean, no cells lost.
- Background load: load avg 1.5-4.0 across the campaign; arms interleaved
  model-major within rep (same-day discipline held); wall metric is the
  in-process SAMPLE_WALL exec1_s (contention-soft), ratios are the read.
