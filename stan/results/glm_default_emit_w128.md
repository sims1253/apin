# W-128 — stanc3 glm emission for EVERYDAY forms at DEFAULT level: ALL FIVE GATES GREEN; the kidscore class measures 54.3 -> 9.5 Ir/elem at the likelihood subtree (−82.5%, complex −90.0%, whole run −56.3%), far through the pre-registered −40..−60% band (favorable overshoot, owned); the K≥2 wrap measured honestly (append_col 37.4 Ir/elem) and does NOT eat the win (logmesquite complex −66.2%)

Executed 2026-08-29 per the WORKLOG "W-128 PRE-REGISTRATION" (Lane B,
W-34-ArmB gate class — STATISTICAL, stated everywhere: the glm interior
computes analytically-simplified gradients and differently-associated
densities; draws change; lp/gradients agree to the last-ulp class).
Deliverable: stanc3 branch **`glm-default-emit` @ bc71346** (parent
`master` 90c6532; 2 commits, DCO + AI note; NOT pushed) in the dedicated
worktree `external/stanc3_w128` (siblings verified clean; worktree created
with `git worktree add ... -b glm-default-emit 90c6532` from stanc3_w108).
Artifacts `scratch/w128/`.

**Headline: `Optimize.emit_normal_glm` (own settings field, ON at every
level INCLUDING the default, LAST in the suite) rewrites the two everyday
regression shapes to `normal_id_glm_lpdf` in the reverse-mode log prob
only: (1) the scalar-intercept + scalar-slope-scaled DATA-VECTOR chain —
`y ~ normal(beta[1] + beta[2] * x, sigma)`, the kidscore/logmesquite class
that NEVER reached glm at any level in any stanc version — including its
--O1-fused fma spelling and subtracted slopes; (2) the matrix forms
`x*beta (+ alpha)` (the stock --O1 shapes, now also at default). For K = 1
the emission is a PLAIN CALL passing the data vector directly as the
design and the scalar slope directly as the weight — probe-verified
bindings (an Eigen column vector satisfies `require_matrix_t<T_x>`:
`is_matrix` is `is_eigen`-based; `T_x::RowsAtCompileTime = -1 != 1` takes
the general branch with `x.rows()/x.cols()` giving exact K=1 design
semantics; a scalar `T_beta` binds with correct edge gradients). For K ≥ 2
the design is synthesized `append_col(x2, append_col(...))` and the
weights with a vector literal — both stock-library shapes. On
kidscore_momiq (N=434): likelihood subtree 54.3 -> 9.5 Ir/elem, whole
gradient-eval machinery −56.3% of the entire sampler run; on
logmesquite_logvash (K=5, N=46) the append_col wrap costs 37.4 Ir/elem
(measured, disclosed) against the stock chain's ~215/elem of eltwise
machinery — complex −66.2%. SELF-CONTAINED with upstream stan math (the
emission calls only stock `normal_id_glm_lpdf` + standard library
functions; both gate models' emitted .hpp compile against the PRISTINE
stock-math bundle, md5-asserted).**

---

## 1. The design determination (pre-registered question, answered by probe)

`scratch/w128/probe/probe_bind.cpp` + `probe_wrap.cpp` (stock-math bundle
headers, -mavx2 -mfma -O1):

| binding question | answer | evidence |
|---|---|---|
| can an Eigen VECTOR bind T_x? | YES — column vector: `is_matrix` = `is_rev_matrix || is_eigen`; `T_x_rows=-1` -> general branch; `N=x.rows()`, `K=x.cols()=1` — exact K=1 design semantics. A ROW vector would hit the T_x_rows==1 broadcast branch (different semantics) — Stan data vectors are column vectors, never emitted | compiles; lp + dalpha/dbeta/dsigma match the plain `normal_lpdf(y, add(a, multiply(b,x)), s)` reference |
| can a SCALAR bind T_beta? | YES — scalar edges handle it; check_consistent_size is a no-op on scalars; `x_val * beta_val` = vector*scalar | correct dbeta vs reference |
| 1-element vector beta? | YES | same numbers |
| K≥2 design synthesis? | `append_col(x2, append_col(x3, ...))` + weight VECTOR literal (`Expr.Helpers.vector`, lowers to the comma-init column literal the stock backend emits for `to_vector([...])`) | compiles with Map'd data operands; lp/grads match the stock 5-term nested-add reference |

Consequence: **the K=1 form needs NO wrap at all** — the pre-registered
"worry" case applies only to K ≥ 2, where the tables' idiom (append_col)
was used and its cost measured (§5).

## 2. The pass (`src/analysis_and_optimization/Optimize.ml`)

- Matches `TargetPE (FunApp (StanLib ("normal_lpdf", FnLpdf _, _), [y; mu;
  sigma]))` in `reverse_mode_log_prob` ONLY (the double-mode instantiation
  keeps the stock expression). Gates: y a bare `Var` typed UVector with
  adlevel DataOnly (data or transformed data); sigma UReal (scalar — vector
  sigma never fires, per the pre-registered negative list); mu UVector.
- **Shape 1 (matrix, the stock --O1 forms)**: `Plus__(alpha, Times__(X,
  beta_vec))` | `Plus__(Times__(X, beta_vec), alpha)` | `Times__(X,
  beta_vec)` with X UMatrix -> `normal_id_glm_lpdf(y, X, alpha|0, beta_vec,
  sigma)` (`Expr.Helpers.zero` literal-0 alpha, mirroring the stock --O1
  blr emission bit-for-bit).
- **Shape 2 (data-vector chains)**: flatten the mu +-chain (any nesting;
  `Minus` of a scaled term -> negated slope via a synthesized `PMinus__`
  node; Minus of a bare scalar -> negated intercept; the --O1 `fma(b, x,
  z)` spellings flatten identically) into at most one scalar intercept +
  ≥1 terms `scalar * bare-data-Var[UVector, DataOnly]` (either operand
  order). K=1: `normal_id_glm_lpdf(y, x, alpha, slope, sigma)` — direct,
  no wrap. K≥2: design `append_col` fold in source order + weights vector
  literal. Anything else (nonlinear terms, parameter-vector predictors,
  bare-vector Minus, dot_product heads, EltTimes) -> no fire.
- Propto suffix, call metadata, statement locations all preserved
  (statement-level rewrite keeps the statement node; the emitted kidscore
  .hpp location table is IDENTICAL to stock's — only the likelihood
  statement changes). Synthesized nodes are the exact StanLib shapes stock
  lowering produces for equivalent source; NO backend changes, NO new
  includes.
- Suite position LAST; settings field `emit_normal_glm`; ON at O0+O1+
  Oexperimental (O0 = `{no_optimizations with emit_normal_glm=true}`). At
  --O1 the pass is a no-op for the matrix forms (partial_evaluation's own
  glm clauses already fired — blr's --O1 output is BYTE-IDENTICAL to stock)
  and ADDS the vector-chain forms (whose fma spelling partial_evaluation's
  own fma-ization created — the W-119 finding that the stock glm clauses
  could never see them).
- **UPSTREAM NOTE (in the commit message): this changes numerics at the
  default level** (statistical class, last-ulp agreement); the natural
  upstream gating is --Oexperimental-first; the branch enables it at every
  level deliberately as the measured experiment.

## 3. Gates

### (a) Pattern discipline — GREEN

- **In-repo integration model** `normal-glm-emit.stan`: 8 firing statements
  (K=1, K=2 chain, matrix ± intercept, K=1 no-intercept, subtracted slope,
  right-nested chain, transformed-data response), 6 non-firing controls
  (nonlinear predictor, parameter-vector predictor, vector scale,
  parameter response, scalar-broadcast predictor, non-normal head) —
  verified at O0/O1/Oexperimental through the regenerated expectations;
  expectations diff = SINGLE PURE INSERTION at every level (1036/885/899
  added lines, ZERO removed).
- **External controls** (`scratch/w128/negctl/`, 10 negatives + 3
  positives, compiled --print-cpp at default AND --O1): nonlinear
  (square(x)), vector sigma, student_t head, y-parameter, x-parameter,
  x-expression (log(x) — disclosed scope line: predictors must be BARE
  data vars), all-scalar (N=1 class), array real[] y, dot_product head,
  bare-vector Minus — **0 glm calls in every negative at both levels**;
  positives fire 1 (2 sites for matrix at O1 = both instantiations, the
  stock partial_evaluation behavior).
- **Full-tree census** (pristine 90c6532 stanc vs branch over ALL 1233
  .stan under test/integration/good, default AND --O1, byte-compare):
  default — exactly 2 differing: the new integration model +
  `normal_id_glm_old_performance.stan` (an existing model whose likelihood
  is literally `y ~ normal(x * beta_inferred + alpha_inferred, sigma)` —
  the pass working on real in-repo code, rev-mode statement only; the
  W-115 expr-prop-fail4 precedent). --O1 — exactly 2 differing: the new
  integration model + `functions-good-void.stan` (a likelihood inside a
  user function that --O1 inlining lands in the log prob as the fma-
  spelled vector chain `fma(x, alpha, beta)` — the K=1 class firing at
  O1, where stock leaves it as fma+normal_lpdf; the emitted
  `normal_id_glm_lpdf(y, x, beta, alpha, sigma)` maps intercept/slope
  correctly — source `x*alpha + beta`, glm alpha=beta, glm beta=alpha).
  normal_id_glm_old_performance is IDENTICAL at --O1 (stock O1 already
  glms it — the status quo preserved).

### (b) Parity on the REAL models — GREEN (statistical class, last-ulp)

`scratch/w128/setup_gate_b.sh`: ONE pristine-stock-math bundle
(`cpio -pdlm0` hardlink copy of w108/bs_prim_stock; `normal_id_glm_lpdf`
md5 90389d08 asserted); hpps generated by pristine-90c6532 stanc (stock
arm) and branch stanc (emit arm), BOTH at default level; `.so`s built
`CXX=gxx_fixed CXXFLAGS="-mavx2 -mfma" TBB_CXX_TYPE=gcc /usr/bin/make
-j2`, nice 19, `env -u LD_LIBRARY_PATH`. Post-build assertions: stock hpp
has NO glm call, emit hpp HAS one, both compile+link clean (the emission
is stock-math-self-contained). 100 points (W-103 scheme,
default_rng(20260822), standard_normal*0.5, propto/no-jacobian), one-
process harness with swapped-load-order control (`gate_parity.py`):

| model | lp rel-L2 | lp max diff | grad rel-L2 (vec) | grad max comp rel | bitwise lp / grad |
|---|---|---|---|---|---|
| kidscore_momiq (D=3) | **1.016e-16** | 3.7e-9 on |lp|~3e7 = **2.0 ulp** | **1.688e-15** | 2.910e-15 | 48/100 / 99/100 unequal |
| logmesquite_logvash (D=7) | **1.046e-16** | 9.1e-13 on |lp|~7.8e3 = **2.0 ulp** | **6.057e-16** | 6.307e-16 | 38/100 / 100/100 unequal |

Metrics IDENTICAL under swapped load order (order-invariant). Both models
DEEP inside the pre-registered ≤~1e-14 band — the glm analytic-gradient
equivalence is numerically last-ulp-class here, reported as measured (NOT
rounded down to exact-zero: the gradient vectors genuinely differ in
their last bits, 99-100/100).

### (c) Sampler — GREEN (distribution-level; draws differ as stated)

W-29 protocol: walnutpie `build_w36exp` CLI READ-ONLY, 3 reps x 4 chains
x both arms, per-chain seeds 20260819+100·rep+ch, pf per-chain inits
(`inits_w63/kidscore_momiq/rep<R>/chain_<c>.txt`), warmup 100, samples 50,
--metric-window 50, OMP_NUM_THREADS=1. Rank-normalized split bulk-ESS/rhat
(Vehtari et al. 2021, the Stan estimators — W-124's analyzer):

| rep | stock ESS-median (beta.1/beta.2/sigma) | emit ESS-median | ratio | rhat max (stock/emit) |
|---|---|---|---|---|
| 0 | 10.62 (10.6/10.2/196.9) | 10.62 (identical values) | 1.000 | 1.417/1.417 |
| 1 | 36.64 (35.7/36.6/93.3) | 11.55 (11.1/11.6/138.2) | 0.315 | 1.154/1.350 |
| 2 | 33.62 (32.8/33.6/114.9) | 31.63 (30.5/31.6/128.0) | 0.941 | 1.165/1.162 |

kidscore's posterior is a near-ridge in (beta.1, beta.2): at 4x50 draws
the ESS estimator itself is dominated by single-chain noise (stock's OWN
rep spread: 10.6 -> 36.6 = 96.5%). Rep 1's 0.315 ratio was therefore
chased with a LONG-HORIZON CONTROL (same seeds/inits, warmup 1000,
samples 500, both arms): **stock median ESS 136.8 (rhat_max 1.057) vs
emit 244.3 (rhat_max 1.012)** — the emit arm is BETTER-mixed at horizon;
the short-run gap is trajectory noise (mechanism: one branch decision
flipping in a chain with ESS~10). Gradient calls: stock 26,585 vs emit
26,551 (−0.13%; rep 0 chains byte-matched call counts, arms identical).
**Draws: 0/12 chains md5-identical** — differ as pre-registered for the
statistical class (gradients ulp-different, unlike W-124's exact-constant
case where 2/12 coincided).

### (d) Callgrind cost — GREEN, band exceeded favorably (−82.5% vs the −40..−60% band)

`run_callgrind_w128.sh` (valgrind 3.23, real-callgrind pgrep check before
each run — W-118's watchers matched only the naive grep, read and
excluded; matched sampler runs seed 20260819, rep0/chain_0 init, warmup
100 samples 50 mw50; per-arm grad counts EQUAL: kidscore 1816+457=2273
both arms; logmesquite 2139+942=3081 both arms). Per-element denominators:
2273x434 = 986,582 (kidscore), 3081x46 = 141,726 (logmesquite).

| metric | kidscore stock | kidscore emit | delta |
|---|---|---|---|
| PROGRAM TOTALS | 149.82M Ir | 65.42M Ir | **−56.3% (whole run)** |
| density subtree (INCLUSIVE) | normal_lpdf 53.58M = **54.3 Ir/elem** | normal_id_glm_lpdf 9.38M = **9.5 Ir/elem** | **−82.5%** |
| likelihood COMPLEX (subtree + mu-construction + reverse chains + memset) | 93.77M = 95.1/elem | 9.50M = 9.6/elem | **−90.0%** |
| memset | 8.00M (the vec_aos materialization) | 0.074M | -> ~0 |
| eltwise autodiff nodes | add 10.08M + multiply 6.23M + their 2 reverse chains 16.88M + lpdf edge scatter 6.99M | (absent) | -> 0 |
| glm frame | — | self 7.03M + z^2 redux 1.00M | the analytic interior |

| metric | logmesquite stock | logmesquite emit | delta |
|---|---|---|---|
| PROGRAM TOTALS | 123.52M Ir | 98.37M Ir | −20.4% (N=46: per-call overheads dominate the run) |
| density subtree | 9.99M = 70.5/elem | 8.06M = 56.8/elem | −19.4% |
| **likelihood COMPLEX** (adds the K=5 chain's 4 adds + 5 multiplies + 3 chain sweeps, stock; the append_col wrap + edges, emit) | 40.55M = **286.1/elem** | 13.73M = **96.8/elem** | **−66.2%** |
| append_col wrap (4 levels, per eval) | — | 5.30M = **37.4 Ir/elem** | the measured wrap cost |

**Band disclosure (owned): the kidscore interior reduction −82.5% EXCEEDS
the pre-registered −60% band top.** Mechanism: the census's 18-20 Ir/elem
glm target (W-121: 17.7 fwd avx2, N=12573) was probed at K=2 with a
VECTOR var beta (AoS edges) and carries the 8/elem y_scaled-memset class;
the kidscore emission shape — K=1, design = Map<Vector>, ALL-var-scalar
alpha/beta/sigma (O(1) edges), no matrix deref — is cheaper per element
(9.5 incl. its ~0.05/elem reverse), and memset amortizes to ~0 at this
posture. The logmesquite wrap (37.4 Ir/elem, every gradient eval) is the
honest cost of the K≥2 synthesis WITHOUT transformed-data hoisting — it
does NOT eat the win (the stock chain pays ~215/elem of eltwise
machinery), but a follow-up increment could hoist the design to
transformed data (the W-124 prepare_data machinery) and reclaim it; not
done here (scope discipline: increment 1 = emission only). The GEMV:
symbol-level the design products fold INTO the glm frame (inlined; the
z^2 redux is the one separately-visible Eigen symbol); W-119's probe
measured the GEMV inside glm directly — same interior.

### (e) No-op elsewhere — GREEN (with the two intended pattern-bearing fires)

- The 5 committed `models/*.hpp` references (accel_gp, arma11, gp_regr,
  kronecker_gp, lotka_volterra): regenerate with `--O1
  --debug-optimized-mir --o=` — **byte-identical** (mine = pristine
  90c6532 = committed).
- diamonds (brms-emits glm directly — no `normal_lpdf` pattern) and
  eight_schools_centered: **byte-identical at default AND --O1**.
- **blr [default]: DIFFERS by exactly the intended statement** —
  `normal_lpdf<false>(y, multiply(X, beta), sigma)` ->
  `normal_id_glm_lpdf<false>(y, X, 0, beta, sigma)` (2 lines; the same
  emission stock produces at --O1). blr is pattern-bearing — the mission's
  matrix-form-at-default target. **blr [--O1]: byte-identical** (the O1
  status quo preserved exactly).
- `dune runtest -j2` (opam switch w39) on the full tree: **exit 0**.

## 4. Deviations and disclosures (all owned)

1. **The K≥2 form (logmesquite class) is IN the increment** (the
   pre-registration's scope line named the K=1 vector + matrix shapes,
   but its gate (b) names logmesquite for emitted-vs-stock parity, which
   requires the K=5 chain to fire): implemented via append_col
   synthesis, wrap cost measured at 37.4 Ir/elem (§5d), win holds at
   −66.2% complex. The transformed-data hoist of the design (free wrap)
   is the natural increment 2.
2. **Predictors must be BARE data vars**: `b * log(x)` does not fire
   (correct and a win, but out of scope; the per-eval recompute question
   belongs with the hoist increment). Disclosed as the scope line; the
   negative control `neg_x_expr` pins it.
3. **Bare-vector Minus does not fire** (`a - x`); Minus of a SCALED term
   does (`a - b*x` -> negated slope). The negated-intercept spelling
   (`b*x - a`) also fires.
4. **rep-1 short-run ESS ratio 0.315**: chased with the long-horizon
   control (§5c) — emit BETTER at horizon; reported with both numbers,
   no cherry-picking.
5. **--O1 census**: 2/1233 differing (the integration model +
   functions-good-void.stan — an inlined-function likelihood in the fma
   spelling, §3a; the emission is the correct K=1 glm with intercept/
   slope roles verified against the source). No other in-repo model's
   --O1 or default output changes; `dune runtest` green confirms no
   committed expectation is affected.
6. Machine: ≤2 build cores (make -j2, dune -j2, nice 19), one callgrind
   at a time (real-binary pgrep check; W-118's watcher loops matched the
   naive `ps | grep callgrind` — read and excluded, per the W-121
   disclosure), `env -u LD_LIBRARY_PATH` on every build/run; sibling
   trees read-only (stanc3_w108 worktree verified clean before/after;
   w124/base pristine compiler used as the stock arm).

## 5. Artifacts

- Branch `glm-default-emit` @ bc71346 (commits 9ea96dd pass + bc71346
  tests): `src/analysis_and_optimization/Optimize.{ml,mli}`, the new
  `test/integration/good/compiler-optimizations/normal-glm-emit.stan` +
  3 regenerated `.expected`. NOT pushed.
- `scratch/w128/`: `probe/` (probe_bind.cpp, probe_wrap.cpp — the T_x
  determination), `bs_stock/` (pristine-header-asserted bundle),
  `model_{kidscore_momiq,logmesquite_logvash}_{stock,emit}/` (.stan/.hpp/
  .so/build.log), `gate_parity.py`, `run_sampler.sh` +
  `analyze_sampler.py` + `draws/` (24 runs) + `draws_long/` (8 long-
  horizon control runs), `run_callgrind_w128.sh` + `cg/` (4 callgrind.out
  + annotate extraction), `negctl/` (10 negatives + 3 positives),
  `gate_e/` (byte-identity artifacts), `setup_gate_b.sh`.
- Reused read-only: `scratch/w108/bs_prim_stock`, `scratch/w46/gxx_fixed`,
  `scratch/w124/base` (pristine 90c6532 stanc), `external/walnutpie/
  build_w36exp/examples/stan_cli`, `stan/data`, `stan/inits_w63`,
  `stan/models`.

## 6. Upstream-readiness

One-line: the pass is self-contained with upstream stan math (stock
`normal_id_glm_lpdf` only), but it changes numerics at the default level,
so the natural upstream form is the same pass gated --Oexperimental-first
(or --O1) — everything else (pattern discipline, settings field, suite
position, tests) is upstream-shaped as-is.
