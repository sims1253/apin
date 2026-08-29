# W-124 — stanc3 CONST-HOIST emission (compute-once/re-add for constant-data lgamma): ALL FIVE GATES GREEN; the interior saving measures −48.4%, ABOVE the pre-registered −30..−45% band (census attribution was libm-line-only; the dropped lgamma term carries its expression overhead too)

Executed 2026-08-29 per the WORKLOG "W-124 PRE-REGISTRATION" (W-34-ArmB
gate class — draws NOT expected md5-equal; measured: they mostly are).
Deliverable: stanc3 branch **`const-hoist` @ 33ef9e1** (parent `master`
90c6532 — the W-108/W-115 lineage; single commit, DCO + AI note; NOT
pushed) in the dedicated worktree `external/stanc3_w124` (siblings
`stanc3`/`stanc3_w108`/`stanc3_w115` verified clean before and after).
Artifacts `scratch/w124/`.

**Headline: `Optimize.hoist_const_lgamma` recognizes
`target += poisson_log_lpmf(y | ...)` / `poisson_log_glm_lpmf(y | ...)`
with y a data integer array in the reverse-mode log prob, rewrites the
call to the `<propto__>` overload, re-adds the constant from a new
transformed-data double `y_lgamma_y1__ = -sum(lgamma(to_vector(y) + 1))`
computed once at data init — and on a brms-style N=12,573 poisson model
the gradient path stops calling lgamma entirely (lgamma Ir 25.5% -> 0.02%
of the run; poisson_log_glm subtree 259.9 -> 134.7 Ir/elem, −48.2% (subtree −48.4%)), while
lp__ keeps the full-constant value to exactly 1 ulp and parameter
gradients are bitwise-identical 100/100. No math-side changes needed:
the pass is self-contained with upstream stan math.**

---

## 1. What was built

- **`src/analysis_and_optimization/Optimize.ml`**: `hoist_const_lgamma`
  matches, in `reverse_mode_log_prob` ONLY, `TargetPE (FunApp (StanLib
  (name, FnLpmf false, mem), rv :: args))` for `poisson_log_lpmf`
  (arity 2) and `poisson_log_glm_lpmf` (arity 4), where `rv`
  is a bare `Var` with meta `{UArray UInt; DataOnly}` whose name is in
  `input_vars` (the data block). The statement (with its own location, so
  the numbering/location tables are untouched) becomes
  `SList [TargetPE <same call, suffix FnLpmf true>; TargetPE (Var
  "<y>_lgamma_y1__")]`; one new `Decl {DataOnly; Sized SReal;
  initialize = Assign (-sum(lgamma(Plus__(to_vector(y), Promotion(1)))))
  }` is APPENDED to `prepare_data` per distinct y (empty location =
  invisible to `locations_array__`; ordering safe — after all data
  reads). All synthesized nodes are the exact StanLib shapes the stock
  lowering produces for the equivalent Stan source (`to_vector`,
  `Plus__`, `lgamma`, `sum`, `PMinus__`, `Promotion`), so the backend
  needs NO changes and NO new includes (everything is in model_header).
  The suffix flip `FnLpmf false -> true` is the only change to the call;
  arg order, `mem`, and metadata preserved. The double-mode
  instantiation (`log_prob`) is untouched (constants belong there).
- **Suite position**: LAST (after `block_fixing`), own settings field
  `hoist_const_lgamma`, ON at `--O1` + `--Oexperimental`, OFF at `--O0`
  (W-108 convention). **Upstream note (in the commit message): unlike
  the W-108/W-115 paired-primitive passes, this one needs NO stan-math
  landing — it emits only stock `poisson_log_*_lpmf<propto__>` calls
  plus standard library functions, so it is self-contained as-is.**
- **Emitted C++** (validation model, rev-mode instantiation):
  `lp_accum__.add(stan::math::poisson_log_glm_lpmf<propto__>(y, Xc,
  Intercept, b)); current_statement__ = 5; lp_accum__.add(y_lgamma_y1__);`
  with member `double y_lgamma_y1__;` initialized once in the
  constructor after the data reads. The stock-vs-emit .hpp diff is
  EXACTLY: +1 member, +1 constructor init, the one suffix flip, +2
  statement lines.
- **Semantics pinned in the math source before writing the pass**: the
  constant is `-sum(lgamma(y+1))` under `include_summand<propto>::value`
  in poisson_lpmf.hpp:76-77 (with a `* N / size(n)` broadcast that is
  exactly ×1 for full-vector y) and poisson_log_glm_lpmf.hpp:120-121
  (clean sum); the y `check_nonnegative` scan runs UNCONDITIONALLY, so
  the propto instantiation keeps the throw-set; the hoisted computation
  itself cannot throw (lgamma of a double returns inf at poles), so
  invalid data still throws from the same call site as stock.
- **Tests**: integration model `const-hoist.stan` (3 firing statements:
  plain head / glm head / glm head re-using the same y's hoist; 4
  non-firing: `poisson_lpmf` rate head, `poisson_log_lupmf`, `~`
  sampling statement — which --O1 glm-rewrites into a
  `poisson_log_glm_lpmf<propto__>` call, propping the suffix guard —
  and a transformed-data y). `cpp/cppO1/cppO0.expected` regenerated:
  the diff vs the old expectations is a SINGLE PURE INSERTION of the new
  model's section at every level (690/636/621 diff lines, all `>`).

## 2. Gate (a) — negative controls never fire: PASS

Standalone controls in `scratch/w124/negctl/` compiled `--O1 --print-cpp`
(counting `_lgamma_y1__` occurrences and poisson `<propto__>` calls):

| control | fires? |
|---|---|
| neg_rate (`target += poisson_lpmf(y \| lambda)`) | no |
| neg_tilde (`y ~ poisson_log(a + b*x)`) | no (stock `<propto__>` emission unchanged) |
| neg_lupmf (`target += poisson_log_lupmf`) | no (already propto) |
| neg_tilde_glm (`y ~ poisson_log(a + x*b)`, glm-rewritten at O1) | no (glm head + propto suffix) |
| neg_tdata_y (y a transformed-data array) | no (the input_vars guard) |
| neg_local_y (y a model-block local array) | no |
| neg_scalar_y (`for (n..) target += poisson_log_lpmf(y[n] \| ..)`) | no (scalar broadcast form) |
| neg_otherhead (`target += normal_lpdf`) | no |
| neg_userfun (density inside a user function, called via target +=) | no (functions block untouched) |
| positives pos_plain / pos_branch | 1 and 2 rewrites; the branch case re-uses ONE hoist in both arms |
| everything above at --O0 | 0 fires (positives included) |

In-repo: the 9 real poisson-bearing models under test/ compiled --O1:
`optimize_glm.stan` fires on exactly its 4 data-y `target +=
poisson_log_glm_lpmf(y_vi_d | ...)` statements (4 suffix flips, 1 hoist;
its scalar-y, tdata-y and `~` forms correctly untouched) — its committed
expectations are default-level (=O0) so `dune runtest` is unaffected
(disclosed: real in-repo code does change at --O1, as intended). All
other 8 models: byte-identical to the parent compiler.

## 3. Gate (b) — parity, 100 points: PASS (full-constant lp to 1 ulp; gradients bitwise-exact)

Validation model `v12k2.stan` (brms emission class:
`target += poisson_log_glm_lpmf(y | Xc, Intercept, b)`, N=12,573 = the
census N, K=2 standardized covariates, deterministic generator seed
20260829, y_mean 2.87): stock arm = pristine 90c6532 stanc --O1, emit arm
= branch stanc --O1, same bundle (`scratch/w124/bs_stock`, stock math —
the pristine header md5 asserted), same flags (`-O3 -mavx2 -mfma`,
gxx_fixed, make -j2, nice 19, `env -u LD_LIBRARY_PATH`). A third
scratch-only DIAGNOSTIC arm (emit .hpp minus the single re-add line —
one-line hand edit, attribution only) isolates the constant. One-process
harness (W-115 method), 100 points W-103 scheme, propto/no-jacobian;
verdict re-checked with swapped load order (identical numbers):

| comparison | lp | gradients |
|---|---|---|
| **emit vs stock** (the full-constant claim) | 28/100 bitwise-unequal, **max |Δ| = 1.455e-11 = exactly 1.0 ulp of |lp| ~ 1.2e5; rel-L2 9.65e-17** | **0/100 bitwise mismatches** |
| propto vs stock (constant-attribution) | Δ = +Σ exactly: max |Δ − Σ| = 3.27e-10 (~22 ulps of Σ = 3.3e4), rel-L2 9.4e-15 | 0/100 bitwise |

Interpretation note (the pre-reg formula): the pre-registration's
`lp_new − lp_stock == −lgamma_y1__` holds with `lgamma_y1__` read as the
HOISTED variable's value (= −Σ = −33264.74243969206): the propto-only arm
differs from stock by exactly +Σ, and the re-add cancels it to ≤1 ulp
(the residual is the `[Σterms]+C` accumulator association vs stock's
per-element fold, as pre-registered). Both decompositions reported above;
gradients are exact under both because the constant differentiates to 0.

## 4. Gate (c) — sampler, 3 reps x 4 chains both arms: PASS (distribution-level; draws differ as expected, 2/12 chains coincidentally identical)

W-29 protocol (walnutpie `build_w36exp` CLI READ-ONLY, warmup 100,
samples 50, `--metric-window 50`, OMP_NUM_THREADS=1, near-truth
deterministic per-chain inits, per-chain seeds 20260819+100r+c).
Bulk-ESS/rhat = rank-normalized split estimators (Vehtari et al. 2021,
the Stan/arviz algorithm, implemented in-repo — no arviz on the box);
all 24 runs healthy (no stuck chains — see disclosure).

| rep | stock ESS-median (Intercept/b.1/b.2) | emit ESS-median | ratio | rhat max (stock/emit) |
|---|---|---|---|---|
| 0 | 181.6 (206/182/137) | 189.8 (190/198/130) | 1.045 | 1.011/1.035 |
| 1 | 152.6 (153/158/147) | 152.6 (identical) | 1.000 | 1.032/1.032 |
| 2 | 179.3 (189/171/179) | 179.3 (identical) | 1.000 | 1.052/1.053 |

- Stock's own rep-to-rep ESS spread: 16.9% — the emit deltas (0–4.5%)
  are WITHIN rep noise; rhat ranges comparable arm-to-arm.
- **Gradient calls**: stock 18,736 vs emit 18,738 (+0.01%); reps 1 and 2
  EXACTLY equal, rep 0 differs by 2 calls on one chain (the 1-ulp lp
  noise flipping one trajectory doubling — the expected mechanism).
- **Draws**: not md5-equal as pre-registered (different lp arithmetic):
  10/12 chains differ; 2/12 (r0c3, r1c1) are md5-IDENTICAL — consistent
  with the W-121 census's "draws bitwise-identical" mechanism class
  (leapfrog uses gradients only, which are bitwise-exact; the ulp-level
  lp association noise flips an accept/reject only with probability
  ~1e-7 per decision). Strictly better than the pre-registered
  expectation, reported as measured.

## 5. Gate (d) — callgrind cost: PASS, band met and exceeded (−48.4% vs the −30..−45% band top)

`scratch/w124/run_callgrind.sh` (valgrind 3.23, one run at a time,
ps-checked; matched sampler runs, seed 20260819):

| metric | stock | emit | delta |
|---|---|---|---|
| PROGRAM TOTALS | 6,719.9M Ir | 3,568.1M Ir | **−46.9% (whole run)** |
| poisson_log_glm_lpmf subtree (INCLUSIVE) | 6,514.9M | 3,361.7M | **−48.4%** |
| … per element (per-arm grad-call counts) | 259.9 Ir/elem | 134.7 Ir/elem | −48.2% |
| poisson self | 1,445.8M | 654.6M | −54.7% |
| lgamma complex (libm `__lgamma_r_finite` + ddcore + compat + as_logd) | 2,754.6M (41.0%) | ~2.1M (0.06%) | **→ ~0 exactly as pre-registered** |
| exp engine (shared) | 1,649.3M | 1,641.0M | unchanged (−0.5%) |
| memset / GEMV frame | 200.5M / 180.2M | 199.5M / 179.3M | unchanged |
| gradient calls (warmup+sampling) | 1598+396 | 1600+384 | within noise |

Census cross-check (W-121 posture, N=12573): stock interior 259.9 vs
census 260.6 Ir/elem; lgamma 109.9 vs census 109.4 — the arms are the
census posture. **Band disclosure (owned): the measured interior
reduction −48.4% EXCEEDS the pre-registered −45% top.** Mechanism: the
census's −44% counted only the libm lgamma LINES; the dropped term also
carries its expression overhead (the y->VectorXd conversion, the +1
Eigen pass, the lgamma-expression loop — all inside the stock poisson
self cost), which the emission rewrite removes as well. The band was
derived conservatively from the line attribution; the pass delivers
more, not less. The emit arm's one-time hoist cost is the residual lgamma
Ir: ~0.86M Ir once at construction ≈ 0.03% of a single run.

## 6. Gate (e) — no-op elsewhere: PASS

- `blr` / `diamonds` / `eight_schools_centered` / `bym2_offset_only`
  (the box's one poisson model, `~` form) at `--O1 --debug-optimized-mir`
  vs a PRISTINE 90c6532 build (`scratch/w124/base`): **byte-identical**
  (21,687 / 28,652 / 21,520 / 37,653 bytes, cmp clean).
- The five committed `models/*.hpp` references (accel_gp, arma11,
  gp_regr, kronecker_gp, lotka_volterra) regenerate **byte-identical**
  (mine = pristine base = committed).
- `dune runtest -j2` (opam switch w39) on the full tree: **exit 0**.

## 7. Deviations and disclosures (all owned)

1. **Pre-reg parity formula reading** (§3): both decompositions
   reported; the implemented remedy keeps full-constant lp per the
   mission headline / issue-#20 primary remedy / ledger note, and the
   pre-reg's algebraic identity holds exactly once `lgamma_y1__` is read
   as the hoisted (negated-sum) variable.
2. **Band overshoot** (§5): −48.4% vs −45% top; mechanism above;
   strictly more saving than pre-registered.
3. **Sampler seeds**: the first grid used one seed per rep across
   chains; walnutpie's 100-iter warmup proved fragile (chains with inits
   >~5 posterior-sd out froze identically in BOTH arms — an arm-symmetric
   walnutpie warmup quirk, upstream of this pass). Protocol adjusted to
   per-chain seeds + near-truth inits (W-122's scheme); the frozen grid
   is preserved in `scratch/w124/draws/` history note and the final grid
   is fully healthy. The arm comparison was symmetric in both grids.
4. **propto-only diagnostic arm**: one-line hand edit of the emitted
   .hpp (re-add line removed), scratch-only, used solely to measure the
   constant-attribution identity in §3; not part of the deliverable.
5. **optimize_glm.stan** fires at --O1 in-repo (4 statements, correct
   pattern discipline on every form in the model); no committed
   expectation covers it at --O1 (it is tested at default level = O0),
   so `dune runtest` is green without regeneration.
6. The pristine base compiler lives at `scratch/w124/base` (detached
   worktree of the stanc3 repo at 90c6532, own _build) — kept for
   reproducibility; `external/stanc3*` siblings never touched.

## 8. Artifacts

- Branch `const-hoist` @ 33ef9e1 (6 files: Optimize.{ml,mli},
  const-hoist.stan, 3 regenerated .expected). NOT pushed.
- `scratch/w124/`: `bs_stock/` (private hardlink bundle, pristine
  header asserted), `model_v12k2_{stock,emit,propto}/` (.stan/.hpp/.so/
  build.log), `data_w124/` (+ scipy constant), `inits_w124/`,
  `gate_parity.py` (one-process, order-swapped), `run_sampler.sh` +
  `analyze_sampler.py` + `draws/` (24 runs + logs), `run_callgrind.sh` +
  `cg/` (out + annotate + incl), `negctl/` (9 negatives + 2 positives),
  `gate_e/` + `refs/` (byte-identity artifacts), `base/` (pristine
   90c6532 build), `probe/` (MIR-shape probes).
- Reused read-only: `scratch/w108/bs_prim_stock`, `scratch/w46/gxx_fixed`,
  `external/walnutpie/build_w36exp/examples/stan_cli`.
- Machine: ≤2 cores, nice 19, `env -u LD_LIBRARY_PATH` everywhere; one
  callgrind at a time (ps-checked, none running); OCaml build ~5 min
  (shared dune cache); `dune runtest -j2` exit 0.

## 9. Follow-ups (not this W)

- Family rows for the census's other constant-lgamma carriers:
  `poisson_lpmf` (rate form, −99/elem), `neg_binomial_2_log_glm` (−114),
  `binomial_logit_glm` (lchoose, −350): each is one (name, arity,
  constant-expression) entry in `const_hoist_heads` + the hoisted init
  expression per family (the binomial constant is
  `lchoose(n, N) = lgamma(n+1)+lgamma(N-n+1)-lgamma(N+1)` — same
  machinery, two hoists).
- Upstream-readiness: **self-contained, no stan-math dependency** — the
  pass emits only stock propto overloads of existing densities plus
  standard library calls; it can land in stanc3 as-is (no
  paired-branch gating, unlike W-108/W-115).
