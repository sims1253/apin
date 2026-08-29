# W-117 — the normal-likelihood INTERIORS: audit verdict (research, no production changes)

Executed 2026-08-29 per WORKLOG "W-117 PRE-REGISTRATION" (user-requested
lane: is normal_lpdf's "highly optimized" reputation earned?). Code reading
+ a dedicated probe harness under `scratch/w117/` (callgrind, client-request
instrumentation regions). No math worktree was touched; no wall numbers.

**Headline: the reputation is earned ONLY at the Eigen-math core (~15 Ir/elem
of likelihood arithmetic in the vectorized path) and NOT anywhere else. The
scalar instantiation the loop-codegen models actually call costs 272 Ir/elem;
the stock vectorized path spends 45% of its 51 Ir/elem on operand
materialization + two unfused check scans and another 26% on removable edge
bookkeeping (a Zero-init that is immediately overwritten + an arena copy of
the operand); normal_id_glm's much-touted simplified gradients buy a real
38% interior-math cut that its own edge machinery then half-refunds; and our
W-112 gathered primitive — the campaign's −65% radon win — still carries ~40
Ir/elem of removable machinery (a redundant y copy, two passes where one
would do, per-element chainstack pushes, closure copies) and is itself 1.8x
the cost of the stock vectorized call composed with a var gather (61 Ir/elem)
— a path the Stan language can already express, gated only by codegen and
bit-identity class.**

## 1. What was measured

`scratch/w117/probe_normal.cpp` (+ `probe_vgather.cpp` for the
vectorized-form composition): each variant called at matched shapes with the
REAL radon_pp data pattern (y, county_idx; N=12573 and N=1000; alpha
J=386; sigma 0.77), operands rebuilt per iteration OUTSIDE the instrumented
region after `recover_memory()`. Modes: `fwd` (instrument the likelihood
call only) and `full` (call + `lp.grad()`); **rev = full − fwd** from two
separate runs. Callgrind 3.23 (`~/vginstall`), `--instr-atstart=no`,
`CALLGRIND_START/STOP_INSTRUMENTATION` regions, one job at a time (verified
before each run), nice 19, `env -u LD_LIBRARY_PATH`. Compile: gxx_fixed,
`-mavx2 -mfma -O3 -std=c++17` (model flags), math stack = the bs_prim_stock
bundle (normal_lpdf.hpp md5 `9f5ad345` = pristine, standing W-53 slice),
gathered header from a PRIVATE md5-identical copy of the W-112 branch file.
Check mode verifies every variant against an analytic double gradient
(max rel ~2.8e-15; gathered 3.4e-13 from its summation order; glm1 differs by
construction — different mean — and is a degenerate-shape reference only).

## 2. Per-element Ir table (N=12573, sigma var unless noted; 300 iters, scalar 100)

| variant | fwd/elem | full/elem | rev/elem |
|---|---|---|---|
| scalar loop — N calls `normal_lpdf<false>(double,var,var)` | 220.5 | **271.8** | 51.3 |
| **vec_gather** — var-gather + stock vectorized call (the `y ~ normal(alpha[ii],sigma)` form) | 54.0 | **61.0** | 7.0 |
| vec_aos — stock vectorized, mu `Matrix<var>` | 43.7 | **50.7** | 7.0 |
| vec_soa — stock vectorized, mu `var_value<VectorXd>` | 32.7 | **34.2** | 1.5 |
| vec_aos_sdbl — sigma double | 40.0 | **47.0** | 7.0 |
| glm1 — `normal_id_glm_lpdf`, scalar alpha, 1-elem beta (degenerate) | 16.7 | 16.7 | 0.0 |
| glm_vec — `normal_id_glm_lpdf`, alpha N-vector `Matrix<var>` | 37.3 | **44.3** | 7.0 |
| gathered — W-112 primitive, shape A | 84.4 | **109.7** | 25.3 |
| gathered_sdbl — sigma double | 84.4 | 105.7 | 21.3 |
| gathered_soa — alpha SoA | 83.2 | 107.5 | 24.3 |

N=1000 reproduces every ordering within ~4% (per-call overheads amortize
worse): scalar 271.6, vec_aos 52.5, vec_soa 35.8, glm_vec 46.7, gathered
107.5.

Caveats that keep the table honest: (i) scalar/gathered include their
`sum(terms)` consumption root (fwd 2.1/6.3, rev 2.0/6.0 Ir/elem) because
they return per-element terms; vec/glm return one var. (ii) The rev region
of `full` includes the grad() sweep over operand varis built outside the
region (differs per variant; the symbol split below separates it). (iii)
gathered fwd includes its internal gather (index bounds + mu values) — the
vec arms receive mu pre-built, vec_gather pays its own gather inside.

## 3. Phase attribution (self Ir/elem, from callgrind_annotate)

**vec_aos (50.7):** operand materialization + check scans ~23.0 (measured
directly as the pre-throw prefix of the sigma=0 run: `to_ref(value_of(mu))`
~7 + `check_not_nan(y)` scan ~7 + `check_finite(mu)` scan ~7; both scans are
scalar Eigen loops with a per-element branch — not SIMD) + value/partial
arrays + redux ~7.6 + `partials_` Zero memset 8.0 (**immediately overwritten
by the partials assignment — pure waste**) + `to_arena(ops)` operand copy
5.0 (**pure duplication**) + `update_adjoints` edge apply 7.0 (scattered
vari-adjoint RMW). Likelihood math is ~30% of the total.

**vec_soa (34.2):** scans ~14 + arrays ~7.6 + Zero memset 8.0 (waste) +
edge apply 1.5 (dense adjoint array — 4.7x cheaper than AoS apply).

**glm_vec (44.3):** Zero-inits 16.0 (the `Array y_scaled(N)` ctor memset +
the alpha-edge partials Zero) + alpha operand arena copy 5.0 + lpdf body
13.7 + GEMV 1.6 + beta-partial product 0.9 + edge apply 7.0. Interior math
(body+GEMV+product+apply) = 23.2 vs vec_aos's 37.6 → **the GLM's simplified
gradients are 38% cheaper per element**, but its edge bookkeeping (21.0 vs
13.0) refunds half. glm1 (16.7 total) shows the floor when operands are
O(1): memset 8.0 + body ~6 + GEMV/product ~2.5.

**gathered (109.7):** primitive symbol 67.3 (gather loop ~12 + term loop
~45 incl. per-element `var(double)` ctors + inline closure-capture copies
~5 + fixed) + **redundant `y_d = value_of(y)` copy 8.0** (memcpy symbol; y
is already a dense double vector) + chainstack `emplace_back` 9.0 (one
`var_stack_` push per term vari — an out-of-line call per element, verified
in disassembly) + scatter callback 13.0 (matches W-112's model-context 13.0
exactly) + `sum(terms)` fwd 6.3 + sum chain 6.0.

**scalar (271.8):** call bodies 137.0 + **glibc `log(sigma)` 15.3/elem**
(recomputed per element although sigma is loop-invariant) + chainstack
emplace 12.0 (2 pushes/elem) + grad() sweep 8.0 + per-call edge callbacks
4.7 + sum complex 4.1 + fixed.

**Throw paths (Ir per throwing eval, catch one frame up — shallower than
the model's rethrow cycle; W-104 measured the full model cycle at ~139.5k):**

| case | Ir/throwing eval | structure |
|---|---|---|
| scalar, sigma=0 | 32,354 | O(1) prefix + message + throw#1 + unwind |
| vec_aos, sigma=0 | 333,189 | **mu_val materialization + BOTH check scans run before check_positive fires** (~23/elem × N) + ~30k throw complex |
| gathered, sigma=0 | 334,603 | y_d copy (8/elem) + gather loop (15/elem) before the sigma check + ~30k |
| vec_aos, y[N/2]=NaN | 167,891 | scan to N/2 + materialization + ~25-30k |

The happy path carries the sigma check at O(1) depth (it is the THIRD check);
the N-scaled cost on a failing eval is the checks' ORDER, not the throw.

## 4. Ranked candidates

Ceilings quoted against radon_pp post-primitive G = 9.07e9 total / 6113
grads = 1,483,625 Ir per gradient (W-112), one likelihood call of N=12573
per gradient → **1 Ir/elem = 12,573/1,483,625 = 0.848% of G**.

**C1 — vectorized-form emission (codegen/model lane). STATISTICAL class.**
`y ~ normal(alpha[ii], sigma)` in vectorized form composes a var-gather with
the stock vectorized call at **61.0 Ir/elem all-in** vs the loop-form lane's
~120 (primitive 97.4 + model push-loop 14 + accumulator 19.1/... measured
components: fwd 64.5 + scatter 13 + emplace 9 + sweep ~8 + push-loop 14.1 +
accumulator 19.1). Mechanism: one `Matrix<var>` gather (pointer copies), the
vectorized lpdf, ONE accumulator push. Ceiling ≈ −58 Ir/elem ≈ **−45..−50% G**
on radon-class models. NOT bit-identical to the loop form (Eigen redux lp
tree, edge-apply scatter order) — needs the W-34-class statistical gates
(rel-L2 ≤ 1e-15, ESS/s bands), and either model-source edits or a stanc3
emission change. Effort: trivial in Stan source, moderate in stanc3.

**C2 — fused single-pass primitive interior (bit-identity lane, the
pre-registered question).** The answer to "does a fused single-pass kernel
exist under bit-identity" is **YES for the forward pass**: value terms,
d_mu/d_sigma partials, term varis and the index arena can be produced in ONE
traversal (gather + bounds + z, z², lp_k, d_mu, d_sigma + batch vari
placement), with log σ computed once (already true). The REVERSE scatter
cannot fuse into it — term adjoints are unknown until the graph is graded —
so the structure is one forward pass + one scatter pass (vs today's THREE
forward traversals: y_d copy, gather loop, term loop). Explicit constraints:
per-element op ORDER must match the scalar instantiation including its
compiler contraction points (disassembly shows the term loop's constant adds
compile to `vfmadd213sd`; a SIMD kernel's `vfmadd213pd` is per-lane
identical — no horizontal ops exist in this loop because terms are returned
per element); the scatter stays exactly reverse-n; the accumulator push
schedule is untouched. Components: y_d copy −8.0 (take y by const ref), loop
fusion −8..−10, SIMD arithmetic/data −15..−20, batch no-stack term varis
(the W-53 `vari_no_stack_t`/span machinery, or upstream: one span-registered
batch) −6..−9, dead d_sigma store when sigma is data −3..−4. Ceiling:
primitive-own 97.4 → **~55-65 Ir/elem**; model lane 100.7 → ~70 ⇒ ≈ −31
Ir/elem ≈ **−25% G, bit-identical**, gates identical to W-112's (bitwise
unit gate + draws md5 + parity exact-zero). Effort: one header + W-103-style
kernel discipline; moderate.

**C3 — stock edge bookkeeping cleanup (upstream math lane). TRIVIAL
bit-identity** (memset/copy only — no floating-point operation changes):
kill the Zero-then-overwrite of `partials_` (assign directly / lazy init)
and avoid `to_arena` copying operands that are already arena-resident or
outlive the edge (lvalue specialization). Ceilings: vec_aos 50.7 → ~37.7
(−26%), vec_soa 34.2 → ~26 (−24%), glm_vec 44.3 → ~23 (−48%); composes with
C1 (vectorized-form lane 61 → ~48). Also upstreamable: the GLM's `Array
y_scaled(N)` ctor memset. Effort: small, stan-math PR sized; risk: the
Zero-init is defensive for broadcast (scalar-operand) partial writes — needs
an assigned-full flag; the arena copy is needed for temporaries.

**C4 — check restructuring (stock).** Two sub-candidates: (a) reorder
`check_positive` FIRST — saves the ~23/elem pre-check prefix on FAILING
evals only (333k → ~32k per failed vectorized eval, −90%); on blr (N=100,
51.5% failing evals) that is ~1-2% G (W-104's verdict stands); on large-N
models with warmup-heavy rejection it scales with N. (b) adopt the GLM's
deferred pattern (one `isfinite` on the already-computed sum, cold-path
per-element diagnosis): removes BOTH scan passes (~14/elem) from every happy
vectorized eval ≈ −12% G if the vectorized lane were otherwise clean — but
in composition it is subsumed by C1/C3. Gate class: bit-identical on VALID
inputs; error-message precedence/order changes on invalid inputs (an
observable behavior change — the y→mu→sigma order is current behavior).
Effort: small. Note: the scans are scalar early-exit loops — SIMD-able only
as aggregate-then-report, same semantic caveat.

**C5 — negative results (recorded to close the lanes).** (i) The scatter's
serial sigma-adjoint accumulation (store-to-load chain per element) is at
its Ir floor; re-associating it into a tree/local accumulator changes
adjoint bits → statistical class, not pursued. (ii) The 77 Ir/elem W-112
figure decomposes into ~35 math + ~42 machinery — the primitive's gradient
math was never the problem; the machinery was. (iii) glm's simplified
gradient interior cannot serve the loop form bit-identically (different
operand structure entirely).

## 5. The pre-registered questions, answered

- **Is there a normal analogue of the bernoulli fused-kernel win?** Yes in
  structure (C2: single forward traversal, −25% G bit-identical), but the
  normal interior has no `log1p`-class transcendental to replace — its math
  core is already ~15 Ir/elem — so the win is in fusing DATA FLOW and
  autodiff bookkeeping, not arithmetic. The bigger analogue is C1: the
  "kernel" that matters is the vectorized call the codegen never emits.
- **Is the interior at its floor (the honest-negative check)?** No — but the
  floor is set by bookkeeping, not math: no variant is within 2x of its
  arithmetic floor except glm1's degenerate shape. The pure per-element
  arithmetic (z, z², −0.5z², +const, −logσ-term, d_mu, d_sigma, one gather
  read, one scatter RMW) is ~15-20 Ir/elem; every real path pays 34-110.
- **Is normal_id_glm cheaper per element than plain vectorized?** Interior
  math yes (23.2 vs 37.6, −38%): no y_scaled_sq array (scalar sigma partial
  from the sum), mu_derivative reused as the alpha partial, GEMV-fused
  predictor, deferred checks. All-in only −13% (44.3 vs 50.7) because of its
  double memset + operand copy. With C3's cleanup the gap would widen to
  ~−38% all-in.

## 6. Disclosures

- Probe definitions differ from model-context attributions: my fwd includes
  operand-value preparation inside the call; W-112's table split rvalue
  machinery into `log_prob_impl`. The cross-check anchors: gathered scatter
  13.0 = W-112's 13.0; scalar total 271.8 vs W-112's ~276 loop complex;
  emplace 9.0 vs W-112's 9.1/elem — three independent matches.
- The scalar/gathered arms carry `sum(terms)` (12.3 Ir/elem combined for
  gathered) that the model replaces with the accumulator push loop (14.1
  measured inside log_prob_impl) — same cost class, disclosed.
- Throw numbers are to a one-frame-up catch (throw#1 + unwind only); the
  model-level cycle (rethrow_located, deeper unwinder) is W-104's 139.5k.
- One `ps aux | grep -c '[c]allgrind'` check returned 2 immediately after
  "MATRIX DONE" — the matches were the matrix driver's finishing
  `callgrind_annotate` post-processing (analysis only, no measurement
  collision); my subsequent vec_gather runs started after and ran strictly
  sequentially.
- `probe_normal x 0 0 check` (N=0 sanity invocation) prints zeros —
  meaningless row, ignore. glm1's check-mode row differs by construction.
- Sibling trees only read: bs_prim_stock, external/math_dev_w112 (header
  copied out, md5 `509d374a` both), scratch/w112 data inc (copied out).
  All artifacts under `scratch/w117/`. No wall claims anywhere.

## 7. Verdict

"Highly optimized" is earned by the vectorized Eigen core and by glm's
analytic gradients, and forfeited everywhere the autodiff machinery and the
codegen touch: the scalar instantiation (the one loop models actually call)
is 18x the arithmetic floor; the vectorized path spends 70% of its budget on
checks/materialization/bookkeeping; the GLM half-refunds its own math win;
and our gathered primitive — the campaign's proudest normal-lane result —
still holds ~40 Ir/elem of removable machinery and is 1.8x a stock-composed
alternative that needs no new math at all. The single best pre-registrable
follow-up is **C2** (fused single-pass primitive interior, −25% G
bit-identical on radon_pp, W-112 gates reusable verbatim); the strategic
runner-up is **C1** (vectorized-form emission, −45..−50% G, statistical
class).

## 8. Artifacts

`scratch/w117/`: `probe_normal.cpp` + `build.sh` + `run_one.sh` +
`run_matrix.sh` + `extract.py`; `probe_vgather.cpp` (vectorized-form arm);
`inc/` (private gathered-header copy); `radon_pp_data.inc` (copy);
`logs/` (42 callgrind.out + run.log + ann.txt sets); `NOTES_coderead.md`,
`NOTES_measure.md` (working notes).
