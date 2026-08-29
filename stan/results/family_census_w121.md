# W-121 — the COMMON-FAMILY INTERIOR CENSUS (research + measurement, no production changes)

Executed 2026-08-29 per the WORKLOG "W-121 PRE-REGISTRATION". Method = W-117
verbatim (code read + callgrind client-request probe, fwd/full regions, rev =
full − fwd) + the W-119/W-120 fix-class taxonomy. Stock math stack =
bs_prim_stock bundle (all 16 family headers pristine; normal_id_glm md5
90389d08 = the standing reference). Artifacts under `scratch/w121/`
(probe_family.cpp, two postures, 85 callgrind runs, extract.py). No math
worktree touched; no wall claims; sibling trees read-only.

**Headline.** Across the families everyday users actually call, the interior
cost is set by TRANSCENDENTALS + emission, not by the Eigen/autodiff frame:
every discrete family pays 25-45% of its per-element budget in libm lgamma/
log1p/exp, and the brms `target +=` emission (propto=false) pays 109-350
Ir/elem recomputing lgamma of CONSTANT DATA on every gradient eval. The GLM
analytic-gradient advantage generalizes (rev ≈ 0.01 Ir/elem for ALL seven glm
families vs 7.0-14.0 for every plain vector form), but the glm forward math
is NOT uniform: normal_id_glm is 17.7 Ir/elem and transcendental-free while
binomial_logit_glm is 776 (44x) — 45% of it lgamma of data. The biggest
single lever in the census is emission-class (propto), the biggest
bit-identical in-function lever is source-level recompute fusion in
poisson_log_glm (measured −33 Ir/elem exp recompute) with family-frame fusion
on top (−25..−30% band, W-119's proven pattern).

## 1. The family × measurement matrix (Ir/elem; N=12573, K=2, x double, scalar var alpha, beta var(2); plain arms get N-vector var params prebuilt outside the region — the caller-side predictor cost is NOT included for plain arms, disclosed)

| family | fwd stock | fwd avx2 | rev avx2 | full avx2 | full n1000 | top interior shares (avx2, per elem) |
|---|---|---|---|---|---|---|
| normal_id_glm (ref) | 33.4 | 17.7 | 0.01 | 17.7 | 20.5 | memset 8.0 (GEMV evalTo, load-bearing) + GEMV 3.6 + frame 6.0 |
| bernoulli_logit_glm | 179.4 | 132.6 | 0.01 | 132.6 | 136.8 | log1p 67.5 (51%) + frame 53.4 + memset 8.0 + GEMV 2.1 |
| poisson_log_glm | 260.6 | 249.4 | 0.01 | 249.4 | 253.4 | lgamma 109.4 (44%, CONSTANT y) + exp 66.0 (2 sites!) + frame 54.2 |
| neg_bin_2_log_glm | 571.8 | 506.9 | 0.01 | 506.9 | 511.7 | lgamma 228.9 (45%) + log1p 61.7 + exp 33.0 + frame 153.7 |
| categorical_logit_glm | 442.6 | 320.5 | 0.01 | 320.5 | 326.7 | exp 84.0 + GEMM kernels ~90 + memset 24.0 (3 N×C) + frame 147.8 |
| ordered_logistic_glm | 536.6 | 373.0 | 0.01 | 373.0 | 381.8 | log1p 122.0 + exp 74.8 (~5 sites, 2 recomputed) + frame 159.4 |
| binomial_logit_glm | 797.6 | 776.0 | 0.01 | 776.0 | 787.0 | lgamma 349.5 (45%, lchoose of CONSTANT n,N) + log1p 124.5 + exp 99.0 + frame 141.2 |
| bernoulli (plain) | 116.6 | 110.2 | 7.0 | 117.2 | 118.1 | log 25.2 + log1p 30.4 (SCALAR loop) + frame 38.7 + edge 7+8 |
| bernoulli_logit (plain) | 195.9 | 161.1 | 7.0 | 168.1 | 170.3 | log1p 69.1 + frame 73.9 + memset 8.0 + to_arena 5.0 |
| poisson (plain) | 241.8 | 243.2 | 7.0 | 250.2 | 253.0 | lgamma 99.4 (CONST y) + log 45.6 (multiply_log) + frame 72.0 |
| poisson_log (plain) | 233.4 | 184.2 | 7.0 | 191.2 | 194.6 | lgamma 109.4 (CONST y) + frame 59.6 (exp materialized ONCE — the plain form fuses better than its glm sibling) |
| neg_binomial_2 (plain) | 933.2 | 883.1 | 7.0 | 890.1 | 892.1 | lgamma 360.9 + log 93.9 + log1p 70.4 + frame 288.6 (VectorBuilder scalar-loop era) + memset 40.0 |
| exponential | 12.6 | 9.6 | 0.00 | 9.6 | 10.3 | the floor family |
| gamma (scalar params) | 167.1 | 63.7 | 0.00 | 63.7 | 64.6 | ISA lift 2.6x (Eigen plog vectorizes) |
| gamma (vector params) | 498.4 | 375.6 | 14.0 | 389.6 | 391.9 | lgamma 122.5 + log/plog 87.2 + frame 127.0 |
| weibull | 211.4 | 160.3 | 0.00 | 160.3 | 162.3 | generic_pow 102.8 (64%) + plog 20.8 |
| beta (scalar params) | 178.9 | 122.6 | 0.00 | 122.6 | 125.0 | log1p 67.7 (log1m y) + plog 20.8 (log y) |
| beta (vector params) | 878.9 | 771.3 | 14.0 | 785.3 | 788.2 | lgamma 397.9 (52%) + log1p 62.7 + frame 262.2 |

N=1000 reproduces every ordering within 1-5% (per-call overhead amortizes
worse), as in W-117. ISA posture: the lift anti-correlates with the
transcendental share — pois/binom/nb2 ≈ flat (libm scalar calls do not
vectorize; the W-105 flag lane buys little there), norm_glm +88%, gamma +162%,
cat/ord +38-44% (Eigen frame vectorizes).

## 2. Reach (which forms reach which function)

Verified in stanc3 source (`external/stanc3/src/analysis_and_optimization/
Partial_evaluator.ml` + Optimize.ml): glm rewrites exist ONLY for
bernoulli_logit (6 source forms incl. `bernoulli(y|inv_logit(alpha+x*beta))`),
neg_binomial_2_log (6), normal_id (3), poisson_log (6) — ALL gated on
`type_of x = UMatrix` AND on `partial_evaluation`, which is OFF at the default
level (ON at O1; Optimize.ml:1481). NO rewrite exists for categorical_logit,
ordered_logistic, or binomial_logit at ANY level. brms emits glm DIRECTLY in
generated Stan code (diamonds.stan on this box: `target += normal_id_glm_lpdf`
— verified; bernoulli/poisson/nb2/categorical glm same emission class,
knowledge-based, disclosed). brms binomial/ordinal emission NOT verifiable on
this box (no model on disk) — inferred plain-path, low confidence, disclosed.
Suite on disk: 11 normal_lpdf + 2 gamma_lpdf + 1 normal_id_glm (brms) + 1
bernoulli_logit_glm (hand). propto: brms `target +=` = propto=false (pays all
constant terms); hand `~` = propto=true. wells.stan uses `~`.

## 3. Throw / check-order (Ir per throwing eval, avx2, N=12573, one-frame-up catch)

| case | Ir/throw | verdict |
|---|---|---|
| normal_id_glm sigma=0 | 41,631 | O(1) prefix — W-119's 41.6k cross-anchored exactly |
| bernoulli_logit_glm y bad (upfront check_bounded fires 1st) | 114,655 | scan-to-N/2 before throw — 2.8x the normal_id class but no full compute |
| bernoulli_logit_glm beta NaN (deferred) | 926,518 | FULL forward compute before diagnosis (the expensive class) |
| poisson_log_glm beta NaN (deferred) | 740,716 | same deferred class |
| neg_bin_2_log_glm phi=0 | 155,825 | fires after beta/alpha-finite + y scans — mid-order |
| bernoulli plain theta bad | 462,671 | y-scan (full N) runs BEFORE theta scan — order cost |
| bernoulli_logit plain theta NaN | 506,333 | upfront scans, 4.4x the glm y-bad cost |
| gamma vec alpha NaN | 955,894 | check_positive_finite(y) full scan first (2-predicate scan) |
| exponential rate=0 | 136,366 | check_nonnegative(y) full N-scan runs BEFORE the O(1) rate check — the reorder candidate |

Order verdicts: normal_id_glm's design (O(1) param checks first, deferred
elementwise) remains the family gold standard; the discrete glm's
check_bounded/check_nonnegative y-scans run UPFRONT on every happy eval
(~7-14 Ir/elem) and cost scan-to-throw-site on y-failures; NaN-param failures
pay full compute everywhere (deferred class). Reorders are
error-precedence-observable (W-117 C4 caveat stands).

## 4. Fix-class decomposition per family (headroom columns)

- **Emission/propto class (statistical, but draws-preserving): drop
  constant-data lgamma.** propto=false pays lgamma(y+1) [poisson family, plain
  and glm] and lchoose(n,N) [binomial] of DATA on every eval: pois_glm
  −109.4/elem (−44%), binom_glm −349.5 (−45%), nb2_glm ≈ −114 (lgamma(y+1)
  half of its lgamma), pois/pois_log plain −99..−109. Gradients are
  bitwise-unaffected (constants differentiate to 0); HMC draws are
  bitwise-identical (constant lp shift cancels in ΔH; leapfrog uses gradients
  only); only the lp__ reporting column shifts (by the same constant every
  eval). Gate: draw columns md5 + lp-column-exact-shift + gradient memcmp.
- **In-function recompute fusion (bit-identical).** pois_glm exp(theta)
  evaluated twice (source lines 111/125): −33.0/elem measured. ord_glm
  exp(-|cut|) recomputed in the derivative block: ≈ −30/elem (2 of ~5 exp
  sites). Plain poisson_log already materializes exp ONCE — the plain form
  fuses better than its glm sibling here.
- **Eigen frame fusion (bit-identical with op-order discipline, W-119
  pattern).** Frame shares 30-46% in the glm set (bern 53.4, pois 54.2,
  nb2 153.7, ord 159.4, cat 147.8). Applying W-119's expression-fusion ratio
  (5.04→2.76 ≈ −45% of expression cost) to the frame: bern_glm ≈ −24, pois_glm
  ≈ −25, ord/cat/nb2 ≈ −65-70/elem bands.
- **Edge bookkeeping (W-120 class).** Measured stock components: partials-Zero
  memset 8.0 + to_arena ~5.0 per N-vector edge (bern/bern_logit/pois/pois_log
  1 edge; nb2 2; gamma_vec/beta_vec 2 = 14.0 rev + 13 fwd). The glm arms here
  use SCALAR alpha (the brms shape) → O(1) edges; the vec-alpha glm forms
  carry the 8+5 (W-119/W-120 already measured; the seeded edge is PR-ready
  and bern/pois/nb2/binom glm share the pattern — W-120 §7). The GEMV/GEMM
  evalTo setZero (8/elem glm, 24/elem cat at C=3) is LOAD-BEARING (W-120) —
  do not re-chase.
- **Structural (nb2 plain): VectorBuilder scalar-loop era code** — 6
  sequential materialization loops + per-element partials RMW + serial-term
  loop (frame 288.6, memset 40.0). A data-flow restructure preserving the
  serial accumulation order and per-element expressions is bit-identical;
  ceiling ≈ −150..−190/elem (−17..−21%).

## 5. Ranked pre-registrable follow-ups

1. **The propto-emission lane for constant-data lgamma** (pois/pois_log/
   nb2/binom, glm + plain). Ceilings: −44% pois_glm, −45% binom_glm, −22%
   nb2_glm family interiors; model-scale = likelihood share × that.
   Mechanism: emission of the propto=true form (brms-side, or a stanc3
   `target +=`→`~` rewrite for eligible calls, or hand-edit of generated
   code — works TODAY with zero math changes). Gate class: statistical with
   draws-bitwise-identical (gradient memcmp exact; lp column exact constant
   shift; W-34 bands as backstop). Disclose loo/waic pointwise-lp shifts.
2. **W-122 source-level fusion: the poisson_log_glm interior** (bit-identical).
   Measured exp-recompute −33.0 + frame-fusion band ≈ −25 + (composable)
   seeded-edge vec-alpha −8: ceiling ≈ −66..−75/elem ≈ −25..−30% of the
   family at model flags. Highest-reach family (brms direct + stanc3
   rewrite + plain-form parity). Gates: W-112/W-120 verbatim (bitwise unit
   both flag levels, draws md5 digit-for-digit, parity exact-zero, TU +
   sibling controls incl. bern/nb2 glm).
3. **The nb2-plain interior rebuild** (bit-identical data-flow restructure).
   Ceiling −150..−190/elem (−17..−21%) on the 890/elem scalar-loop interior;
   reach = legacy R emission only (modern brms emits the glm), so ranked 3.
   Same gate class as (2). Runner-up considered: categorical_logit_glm's
   3-GEMM/7-materialization structure (higher reach, but the GEMMs are real
   math — headroom band −40..−60, riskier bit-identity).

## 6. Disclosures

- Plain-family arms receive N-vector params PRE-BUILT outside the instrumented
  region; the model-lane comparison plain-vs-glm must add the caller's
  predictor construction (W-117: vec_gather 61 vs glm 44.3 anchors the
  composition class for normal; the same ~+30-40/elem applies here).
- glm arms use the brms shape (scalar alpha, K=2). vec-alpha glm edges were
  measured by W-119/W-120, not re-run. Categorical measured at C=3 classes;
  its N×C arrays scale with C.
- binom_glm's lgamma = lchoose(n,N) fires because T_n/T_N ints with
  propto=false include the constant term; with propto=true it vanishes
  (include_summand<propto>::value false). Same mechanism everywhere in §4.
- Throw runs catch one frame up (W-117 protocol); model-level cycles are
  W-104's ~139.5k on top of unwind structure.
- Machine discipline: one callgrind at a time (real-binary pgrep check; the
  `ps grep callgrind` counts of 3 were W-118's idle watcher loops whose
  command strings contain the word "callgrind" — verified by reading the ps
  lines; their own machine-free gate kept them waiting throughout), nice 19,
  env -u LD_LIBRARY_PATH, ≤2 build cores, gxx_fixed, valgrind 3.23 (~/vginstall).
- brms categorical/binomial/ordinal emission claims are knowledge-based (no
  brms models of those families on this box); the stanc3 rewrite table and
  the diamonds/wells emissions are file-verified.
- check mode: every arm's lp + probed adjoints verified against central
  finite differences (rel ≤ 1.4e-9; norm_glm's near-zero gradients are the
  y=mean degenerate fixture — that family's real-data gate is W-119's d24).
- Sibling trees only read. No production file changed.

## 7. Artifacts

`scratch/w121/`: probe_family.cpp + build.sh + run_one.sh + run_matrix.sh +
extract.py + probe_family_{stock,avx2} + logs/ (85 callgrind.out + ann.txt +
run.log sets + matrix_driver.log).
