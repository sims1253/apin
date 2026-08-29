# W-119 — the normal_id_glm lane audit + the Eigen-core kernel probe (research, no production changes)

Executed 2026-08-29 per the WORKLOG "W-119 PRE-REGISTRATION" (increment 1:
audit + measured case). Evidence base: W-117 (results/normal_interiors_w117.md).
New artifacts under `scratch/w119/` (probe_glm, probe_kernel, 25 callgrind
runs + annotates, stanc_out/); archives reused read-only: scratch/w105/profile
(diamonds/blr stock+avx2), results/profile/w29 + diamonds, scratch/w109 stock
.so's. No math worktree touched; no wall claims.

**Headline answers.** (1) Yes, normal_id_glm itself can be improved — but not
where the user's framing placed the weight: the everyday dense-X models
mostly do NOT call glm at all (only brms-emitted diamonds does; blr gets it
only at `--O1`; kidscore/logmesquite NEVER — the stanc3 matcher requires a
UMatrix predictor and runs only at O1+). Inside glm, the removable machinery
is the W-117 C3 class, now measured per shape: 21.0 Ir/elem on the N-vector-
alpha form (−47%), 8.0 Ir/elem on the diamonds scalar-alpha form (−21% of
the AVX2-lifted posture's gradient, −6.7% of stock). The diamonds shape's
reverse mode is FREE per element (0.06 Ir/elem) — the glm's structural
advantage is real and large. glm's check ORDER is already right for sigma
(41.6k Ir/throwing eval vs the plain vectorized path's 333k — 8× better),
and its deferred checks trade that for full-compute-plus-scans on NaN
operands (256–304k). (2) The Eigen arithmetic core CANNOT be beaten by a
hand SIMD kernel at bit-identity: the stop-clause FIRES (+0.1% vs the
compiler's own codegen of the same single-pass source at matched ISA). The
apparent core win is 100% decomposable into ISA flags (free, W-105 class)
plus source-level fusion of Eigen's intermediate materializations —
neither needs a hand kernel.

## 1. (a) What the everyday models actually call

Generated-code reading (stanc 2.39.0, the project's default build level:
no `-O` flag, `g++ -O3`, x86-64 SSE2 baseline; verified live by
re-generating all ten hpps into `scratch/w119/stanc_out/`):

| model | N | exact generated call (default level) | at `--O1` | path class | per-element cost (measured) |
|---|---|---|---|---|---|
| diamonds (brms) | 5000, Kc=24 | `normal_id_glm_lpdf<false>(Y, Xc, Intercept, b, sigma)` — Y `Map<double vec>`, Xc `Map<double mat>`, Intercept SCALAR var, b `Map<const Matrix<var>>` 24, sigma var | same | glm scalar-alpha, real GEMV | stock whole-grad **119.9** Ir/elem (w105b archive, G=1.86e9/3102 grads); avx2 posture 38.9; this probe: fwd 37.8, rev **0.06** |
| blr | 100, D=5 | `normal_lpdf<false>(y, multiply(X, beta), sigma)` — mu is a GEMV result materialized as `Matrix<var>` | **`normal_id_glm_lpdf<false>(y, X, 0, beta, sigma)`** — the rewrite FIRES with literal-0 alpha | vec_aos (plain vectorized) | w105b stock whole-grad 106.8k Ir/grad (N=100: per-call overheads + unwinder dominate; ~55% of program Ir is exception machinery — the failing-eval complex); likelihood alone ~50.7/elem (W-117) |
| kidscore_momiq | 434 | `normal_lpdf<propto__>(kid_score, fma(beta[2], mom_iq, beta[1]), sigma)` | same — NO glm | vec_aos | ~50.7/elem + worse per-call amortization (W-117: 52.5 at N=1000) |
| logmesquite_logvash | 46 | `normal_lpdf<propto__>(log_weight, fma-chain×5, sigma)` | same — NO glm | vec_aos | same class; N=46 is pure per-call overhead |
| wells_dist100 | 3020 | `bernoulli_logit_glm_lpmf<propto__>(switched, x, alpha, beta)` — x 3020×1 double, alpha scalar var, beta 1-elem | same | glm sibling family | this run (stock, 40+40 iters, 374.0M Ir total): likelihood complex ≈ **218/elem** — log1p 92 + glm frame 89 + eta-select 29 + GEMV 7 (grad count ≈448 est., see disclosures) |

WHY the rewrite misses (stanc3 source, `external/stanc3/src/analysis_and_
optimization/Partial_evaluator.ml` lines 536–578): the normal→glm rewrite
matches only `mu = (±)(alpha +) x * beta` with `type_of x = UMatrix`, and
the carrying pass (`partial_evaluation`) is OFF at the default level (ON at
O1/Oexperimental — `Optimize.ml` lines 1470–1487). `beta[1] + beta[2] *
mom_iq` has a UVECTOR predictor, so it can never match at ANY level — and
at O1 the fma-ization rewrites it into `fma(...)` before the glm clause
could see it anyway. Consequences, per model:
- The most common hand-written Stan idiom (intercept + slope·vector) uses
  the plain vectorized path IN EVERY STANC VERSION — it pays vec_aos's
  45% materialization/check overhead and its 26% edge overhead that glm
  does not have, and it forgoes glm's free reverse mode.
- `X * beta` (blr) gets glm only if the user knows to pass `--O1`; at
  default it materializes an N-vector `Matrix<var>` mu and runs the full
  autodiff chain on it.
- diamonds (brms-generated explicit glm) is the only one of the five on
  the glm path — and it is the CHEAPEST per element of the large-N models
  despite Kc=24, entirely because of the free reverse and the deferred
  checks.

Instantiation counts: each model compiles ONE glm/lpdf instantiation per
argument-type tuple (the diamonds binary shows a single `normal_id_glm_lpdf`
symbol); there is no scalar-loop glm instantiation anywhere in this class
(the 272 Ir/elem loop-form pathology belongs to the radon-class models,
not this lane).

## 2. (b) glm_vec's 44.3, root-caused per phase

Source: `stan/math/prim/prob/normal_id_glm_lpdf.hpp` (md5 90389d08 =
pristine, verified against the bs_eprime and bs_prim_stock bundles).

Structure of the forward pass (autodiff case, `T_x_rows != 1`):
1. `check_consistent_size` ×4 (O(1) each) then `check_positive_finite`
   on sigma — **BEFORE any N-scaled work** (line 93 vs the materialization
   at lines 123–134). This is the correct check order the plain vectorized
   path lacks.
2. `Array y_scaled(N_instances);` — default-constructed, i.e. ZEROED
   (8.0 Ir/elem of memset) — then **entirely overwritten** two statements
   later by `y_scaled = x_val * beta_val_vec` (GEMV) and
   `y_scaled = (y - y_scaled - alpha) * inv_sigma`. Pure waste in every
   glm shape.
3. `mu_derivative = inv_sigma * y_scaled` — a second N-array (one
   traversal).
4. Edge partials: beta = a second GEMV (`mu_derivative^T * x`, in the
   FORWARD pass); scalar alpha = `sum(mu_derivative)` (a reduction);
   N-vector alpha = whole-array copy into the edge partials (which was
   Zero-initialized at edge construction — 8.0/elem of waste) plus a
   `to_arena` copy of the alpha operand (~5.0/elem).
5. `y_scaled_sq_sum = sum(y_scaled * y_scaled)` (lazy, no materialized
   z² array; scalar sigma partial `(sum − N)·inv_sigma`).
6. Deferred validity: `if (!isfinite(y_scaled_sq_sum)) { 4 × check_finite
   scans }` — ZERO per-element check cost on the happy path (glm has no
   y/mu scans at all; the W-104 batched-check pattern already exists
   inside glm).

Phase attribution, glm_vec (alpha N-vector `Matrix<var>`, x N×1, sigma
var; N=5000 re-anchor this work — 37.81 fwd / 44.83 full, cross-anchored
with W-117's 37.3/44.3 at N=12573, agreement 1.4%; splitting differences
below are inlining-boundary artifacts between the two binaries):

| phase | Ir/elem | class |
|---|---|---|
| `y_scaled` ctor memset (Zero-then-overwrite) | 8.0 | removable, trivially bit-identical |
| alpha-edge partials Zero (Zero-then-overwrite) | 8.0 | removable, trivially bit-identical |
| alpha operand `to_arena` copy | ~5.0 (0.9 own symbol + ~4 in the edge ctor) | removable bit-identically (lvalue/arena-resident specialization) |
| eltwise body (z expr + mu_derivative + z² redux) | ~13.7 | C2/W-118 fusion lane (bit-identical with op-order discipline) |
| GEMV (1-col) | 1.6 | real math |
| `call_assignment` of the product into y_scaled | 1.3 | folds away with the memset fix |
| reverse: alpha-edge scatter (`update_adjoints`) | 7.0 | SoA operand → 1.5 (W-117 measured; model-side) |

The 28 Ir/elem gap vs glm1 (16.7) decomposes as: vec-alpha edge Zero 8.0 +
arena copy 5.0 + reverse scatter 7.0 (glm1's operands are O(1), so it pays
none of these) + the eltwise alpha subtraction and array-copy differences
inside the body (~8). The diamonds shape (d24: scalar alpha, Kc=24, real
data) measured in the same binary: fwd 37.79 = GEMVs 23.1 (12.08 rev-side
beta-GEMV + 11.02 fwd mu-GEMV; both run forward) + memset 8.02 + body 5.13
+ call_assign 1.31; **full 37.85 (rev 0.06)** — with double y and double X
there are no per-element varis to sweep and the edges are O(Kc+2). The
GEMV share is 61% of the diamonds glm forward at AVX2, and 80.5% of the
whole stock diamonds gradient (w105 archive) — the diamonds class is a
GEMV problem first, an edge-machinery problem second.

Throw paths (the pre-registered unmeasured cell; per throwing eval,
one-frame-up catch, N=5000):

| case | Ir/throwing eval | structure |
|---|---|---|
| glm, sigma=0 (vec or d24 shape) | 40,077 / 41,573 | O(1) prefix + message + throw + unwind — `check_positive_finite` fires BEFORE any N-work. **glm does NOT have the 333k problem** (8× cheaper than the plain vectorized path's throw) |
| glm, y[N/2]=NaN (d24) | 256,340 | FULL happy-path forward (189k at this N) + deferred `isfinite` fails + `check_finite(y)` scan to N/2 + throw complex |
| glm, alpha[N/2]=NaN (vec) | 304,085 | full forward + operand-side scan + throw |

So glm's check design is the good one for the cheaply-checkable class and
the expensive one for the NaN class (it pays full compute before
diagnosis) — the exact mirror of the plain path, which is cheap on neither.

## 3. (c) The Eigen-core kernel probe — STOP-CLAUSE FIRES

Design (scratch/w119/probe_kernel.cpp): doubles y/mu (N=12573 and N=1e5),
scalar inv_sigma; per-element term work = z=(y−mu)·invσ, term=−0.5·z²+c
(c folding the σ constant), dmu=invσ·z — the W-117 ~15 Ir/elem arithmetic
floor class. Arms: (i) the stock-style Eigen expression exactly as the
bundle writes it (materialized z, terms assign, materialized scaled_diff),
(ii) a hand SIMD island with runtime AVX2 dispatch (W-103 pattern), (iii) a
plain scalar loop, plus a shared scalar-sequential accumulation loop
(bit-identity constraint: no SIMD/pairwise reduction). Two builds of the
same source: `sse` (−O3 only: the bundle's baseline SSE2 codegen, island
uses per-lane mul+add) and `avx` (−O3 −mavx2 −mfma: island matches gcc's
contraction points with `vfmadd`; disassembly confirms the reference
expression itself compiles to vfmadd132pd in this build and to mulpd/addpd
in the sse build).

Ir/elem (callgrind, 400 iters at N=12573 / 100 at N=1e5; the two N agree
within 1% — N=12573 shown):

| arm | sse build (stock codegen) | avx build (model-flag codegen) |
|---|---|---|
| Eigen expression (stock-style) | 11.03 | 5.04 |
| hand AVX2 island | 3.01 | 2.76 |
| plain scalar loop | 7.01 | **2.76** |
| shared sequential accumulation | 2.50 | 1.75 |

Bit-identity: term arrays and dmu arrays memcmp-clean (0 mismatches, as
uint64 bit patterns) and totals bit-identical across expr / kernel /
scalar within each build, at both N.

**Verdict.** The hand island (2.759) vs the compiler's own codegen of the
plain scalar loop at the same ISA (2.756): **+0.1% — far below the 5%
stop-clause. STOP: the negative IS the result.** The auto-vectorizer
already ate the core; a hand kernel has nothing left to win at bit-identity
(there is no log1p-class transcendental here, per the pre-registered
prior). What the numbers DO show, decomposed honestly:
- stock posture (SSE2 expression, 11.03) → fused AVX2 (2.76) is −75%, but
  −54 points of that is the ISA flag (free, the W-105 lift class) and the
  rest is SOURCE fusion;
- the Eigen expression at matched ISA (5.04) costs 83% more than the fused
  loop (2.76) because it makes THREE traversals with a materialized z
  intermediate — the win is data-flow fusion (write the loop, keep z in
  registers), not SIMD authorship; gcc emits exactly the right fused
  AVX2+FMA code from a plain scalar loop at −O3.
- one incidental: on this dataset the FMA-vs-mul+add difference never
  changed a bit (cross-build totals coincide); the verified claim is
  within-build bit-identity, and the disassembly is the evidence the
  codegens differ.

## 4. The increment-2 shape (recommendation)

Two live lanes; the kernel lane is closed by its stop-clause.

**Lane A (bit-identical, math-side): the glm edge cleanup — W-117's C3
restricted to glm.** Kill the `Array y_scaled(N)` Zero-then-overwrite
(8.0/elem, every glm shape), the vec-alpha edge partials Zero (8.0/elem),
and the alpha-operand `to_arena` copy (~5.0/elem, lvalue specialization).
Memset/copy only — no floating-point operation changes. Expected on a
diamonds-class G: **−21%** on the AVX2-lifted posture (8.1 of 38.9), −6.7%
on stock; on glm_vec-class models **−47%** (21.0 of 44.3–44.8). Gates
reusable from W-117/W-112: bitwise unit gate, draws md5 digit-for-digit,
parity exact-zero, callgrind band, TU + negative controls; upstream-
candidate class (touches shared edge machinery — own pre-reg, wide
controls). Composes with the W-118 fused-interior lane (which supplies the
fused single-pass body the kernel probe just validated at the arithmetic
level).

**Lane B (statistical, codegen-side, bigger): get the everyday models ONTO
the glm path.** The audit's most user-facing finding: the intercept +
slope·vector idiom never compiles to glm in any stanc version, and `X*beta`
only at `--O1`. Two independent fixes, both stanc3-local: (1) extend the
matcher to vector predictors (synthesize the 1-column matrix or add a
UVector clause) and to already-fma-ized chains; (2) enable
`partial_evaluation`'s glm rewrite at the default level (or document
`--O1` for regression models). Payoff on kidscore/logmesquite-class
models: vec_aos 50.7 → glm scalar-alpha ~18–20/elem fwd with ~0 reverse
(−60%+ on the likelihood complex), plus the check-order throw fix for
free (41k vs 333k per failing eval — blr's profile is ~55% unwinder).
Gate class: statistical (different mu summation order — GEMV vs
expression — and different lp tree), needs W-34-class rel-L2/ESS/s bands
and either model-source edits (`y ~ normal_id_glm(x, alpha, beta, sigma)`
works TODAY with zero code changes) or the stanc3 emission.

**Lane C (closed): hand kernel.** Stop-clause fired; record the negative.
Any future core work on this lane should be expressed as source-level
fusion (Lane A / W-118) and ISA flags (shipped W-105), both of which gcc
then compiles to the same code a hand island would produce.

## 5. Disclosures

- All new callgrind runs (glm matrix ×8, kernel matrix ×16, wells ×1) were
  strictly sequential, nice 19, `env -u LD_LIBRARY_PATH`, valgrind/callgrind
  3.23 (`~/vginstall`); pre-run `ps` checks returned a spurious count of 2
  twice — root-caused to my own wrapper's command string containing
  "callgrind_annotate" (the `[c]allgrind` grep matches it); no actual
  sibling collision (verified by reading the matched ps lines; W-108.1 ran
  none, as pre-registered).
- The first wells invocation died before sampling (bad output path, 0 Ir)
  and one with `--instr-atstart=no` collected nothing (the model has no
  client-request macros); the recorded run is the third, rc=0, 80/80
  iterations. Its grad count (~448) assumes warmup treedepths resemble the
  sampling ones (CSV records sampling only, treedepth 1–3, Σ2^td=224 over
  40 iters) — per-elem wells numbers carry that assumption.
- glm_vec re-anchor ran at N=5000 with synthetic operand values (the real
  diamonds y has only 5000 elements; W-117's N=12573 anchor used radon
  data) — values do not affect Ir; the 1.4% total agreement bounds any
  residual shape effect.
- d24 check mode verifies lp + all adjoints against an analytic double
  reference (rel ≤ 1.4e-15; dbeta inf-err 6.8e-12 from accumulation-order
  differences in the reference itself).
- The kernel probe's expression arm materializes three arrays (z, terms,
  dmu), mirroring the stock normal/glm data flow (z `to_ref`, terms
  assign, scaled_diff materialize); the island keeps z in registers —
  that IS the fusion effect being measured.
- Archives reused read-only: scratch/w105/profile/{diamonds,blr}_{stock,
  avx2}, results/profile/{w29,diamonds}, scratch/w109 build logs +
  quiet_stock recipe. Sibling trees (w116, w117, w1081, external/*)
  touched read-only only. No production file changed; `git status` shows
  only pre-existing PI-owned modifications.
- stanc re-generations live in scratch/w119/stanc_out/ (10 hpps; the five
  models × default/O1).

## 6. Artifacts

`scratch/w119/`: `probe_glm.cpp` + `build_glm.sh` + `run_glm.sh` +
`inc/diamonds_data.inc` (real diamonds y + column-centered Xc); `logs/`
(glm matrix ×8, kernel matrix ×16, wells ×1 callgrind.out + ann.txt +
run.log sets, matrix_driver.log, kernel_driver.log); `probe_kernel.cpp` +
`build_kernel.sh` + binaries `probe_kernel_{sse,avx}`; `stanc_out/`;
`logs/wells_chain.csv`.
