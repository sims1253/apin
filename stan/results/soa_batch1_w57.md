# W-57 — SoA arena batch rollout, BATCH 1: both-autodiff branches of subtract/add/divide/multiply batched; bit-exact everywhere; hier_2pl −15.95% total / −17.06% gradient Ir; in-sampler wall −5.6..−6.3%

Date: 2026-08-24. Pre-registration: WORKLOG.md W-57 (scope, gates,
expectations) + same-session addenda (GEMM probe verdict; cachegrind
measurement added). Inputs: W-53 slice (results/soa_var_w53.md) and
its migration plan §2 (verdict GO). Trees: bundle math 5.3.0
(scratch/w53/bs_w53, batch-0 edits + batch-1) for model builds;
develop @344d7167 (external/math_soa, uncommitted) for unit tests +
patch artifact scratch/w57/w57_soa_batch01_develop.patch (14 files,
13 modified + 1 new header, batch 0+1 combined).

**Headline.** Batch 1 extends the W-53 slice pattern (ONE arena
allocation + ONE nochain span per op output) from elt_multiply to
the both-autodiff branches of subtract (rev-rev), add (rev-rev),
divide (m/c, c/m, m1/m2), and multiply (GEMM rev-rev via an explicit
arena temp, scalar×matrix rev-rev). ALL gates PASS on the first
build: 4-model exact-zero parity (0/400 values, 0/400 gradients),
sampler draws md5 = stock = W-53's fe7c57… digit-for-digit, 81/81
touched-target unit tests on develop/Eigen-5, callgrind Ir strictly
below BOTH stock and batch-0 references, wall gates green. MEASURED:
hier_2pl **total −15.95% Ir / gradient subtree −17.06%** at identical
trajectories (4,493 gradient calls); **in-sampler wall −6.3% warmup /
−5.6% sampling** (5 interleaved rounds, non-overlapping bands) —
3× the batch-0 in-sampler effect. Two pre-registered EXPECTATIONS
(not gates) missed and flagged: model-level LLd misses flat (+1.16%
vs hoped ≥−20%) and repeated-eval −10.3..−10.7% (vs −18..−28% band
derived from W-53's loaded-machine session) — see §4.

## 1. Scope decision: the GEMM probe (closed both ways)

scratch/w57/gemm_probe.cpp (bundle math 5.3.0, Eigen 3.4.0, -O2):
1. coeff(i) walks over a double Product expression are IMPOSSIBLE —
   Eigen 3.4 ProductImpl::coeff asserts (Option==LazyProduct || 1x1).
   make_nochain_vari_array can never take A*B directly.
2. Stock arena_t<Matrix<var>> construction from A*B is BITWISE
   IDENTICAL to (A*B).eval() AND to an arena_t<double> temp across 11
   shapes / 82,039 elements (0 mismatches) — stock implicitly
   evaluates through the same GEMM-kernel temp.
=> GEMM included via `arena_t<plain_type_t<decltype(A*B)>> res_val =
A*B;` then batched from the temp (identical kernel, identical bits).

## 2. Implementation (5 functions, 4 files, both trees)

subtract/add rev-rev and divide's three both-autodiff branches wrap
the output construction in `if constexpr (is_eigen_v<ret_type>)`
(divide m/c and c/m: `is_eigen_v<promote_scalar_t<var, Mat>>`) with
the stock body verbatim in the else arm; the batched arm mirrors the
W-53 elt_multiply exemplar. multiply GEMM + scalar×matrix rev-rev
same pattern (guard on return_t). Instantiation probe
(scratch/w57/instantiate_probe.cpp) compiled all 8 op calls × {Matrix<var>,
var-matrix, mixed} on BOTH toolchains. The 4 op files are
byte-identical between trees except multiply.hpp's pre-existing
val_op() rename (untouched lines). Batch-2 remainder (one-autodiff /
broadcast branches, ~21 sites incl. elt_multiply's mixed pair)
intentionally NOT touched.

## 3. Gates (all pre-registered)

| gate | result |
|---|---|
| (a) exact-zero parity, hier_2pl/kronecker_gp/gp_regr/accel_gp × 100 pts, values AND every gradient component | **PASS 4/4** — 0/100 mismatch in all cells (fresh refs from current stock .so; stock .so md5-verified unchanged before/after) |
| (b) full sampler draws md5 (stan_cli, W-29 protocol) | **PASS** — stock = patched = fe7c57c99a7a6530ce2dcc408d6e9c65 (W-53 cross-session continuity) |
| (c) unit tests touched targets (develop/Eigen 5, runTests.py -j2) | **PASS 81/81** — mix add 9, subtract 9, divide 1, elt_multiply 3, multiply_complex 1 (agent pass) + multiply1 1, multiply2 1, operator_multiplication 54, diag_pre 1, diag_post 1 (my addition: the first discovery grep missed the multiply-family names — direct rev coverage of both touched multiply branches) |
| (d) callgrind Ir (valgrind 3.25.1 ~/vginstall, both arms fresh) | **PASS all 4 criteria** — see §4; stock reproduced W-53's 37,128,497,671 to +0.000059% (tool continuity) |
| (e) wall gates | **PASS** — in-sampler patched ≤ stock×1.01 both stanzas (measured −6.3%/−5.6%); repeated-eval patched < stock |

## 4. Measurements

Callgrind (same protocol as gates; draws md5 under valgrind identical
in all 4 runs incl. cachegrind's):

| metric | stock | patched (b0+b1) | delta |
|---|---|---|---|
| total program Ir | 37,128,519,406 | 31,207,289,278 | **−15.95%** |
| logp_grad subtree (inclusive) | 34,701,743,887 | 28,780,442,093 | **−17.06%** |
| gradient calls | 4,493 (3,737+756) | 4,493 — identical | — |
| Ir / gradient | 7,723,133 | 6,386,109 | −17.3% |
| vs W-53 batch-0 patched (34,272,961,754) | — | −8.94% further | — |

Per-op attribution (self, callgrind_annotate):

| symbol | stock | patched | delta |
|---|---|---|---|
| subtract fwd | 4,332,644,400 | 3,228,524,605 | **−25.5%** (predicted window 3.0–3.3e9: the elt_multiply −27.7% ratio transferred) |
| elt_multiply fwd | 3,992,863,504 | 2,888,756,981 | −27.7% (stable vs W-53 patched −0.0006%) |
| subtract reverse callback | 1,104,287,912 | 1,104,287,912 | **0.0% — instruction-identical** |
| elt_multiply reverse callback | 1,189,224,288 | 1,189,224,288 | **0.0%** |
| stack_alloc::alloc | 2,246,152,545 | 37,691,745 | −98.3% |
| chainstack emplace_back | 1,564,528,830 | 35,594,040 | −97.7% |

add/divide/multiply forwards: below annotate threshold in both arms
(hier_2pl does not exercise them materially — their coverage is gate
(c) unit tests + the probe). Allocation/registration machinery is now
essentially absent from the tape complex (−98%), i.e. batches 0–1
have captured (nearly) the whole per-record alloc+emplace tax the
level-(a) arithmetic bound priced at −8.1..−12%G for full rollout —
the measured −17.06%G EXCEEDS that bound because the replaced Eigen
assignment-loop ctor stores are also gone (the bound's "ctor share
(optimistic end)" column was the right one).

Wall (idle desktop, AMD 5650U, interleaved):

| regime | stock | patched | delta |
|---|---|---|---|
| in-sampler warmup µs/call (median of 5 rounds) | 998.9 [991..1008] | 936.4 [931..947] | **−6.3%** |
| in-sampler sampling µs/call | 1023.1 [1016..1040] | 965.7 [939..973] | **−5.6%** |
| repeated-eval (50 pts, 3×3, both orders) | 1060..1092 | 947..980 | −10.3..−10.7% (orders agree 0.4pp) |

Cachegrind MODEL-LEVEL (added measurement; both arms' draws md5
identical): I refs −15.97% (matches callgrind), D refs −20.6%, D1
misses −2.8%, **LLd misses 479,150 → 484,693 = +1.16% (FLAT;
106.6 → 107.9 per gradient)**.

## 5. The two flagged expectation misses (mechanisms)

1. **Model-level LLd flat** (+1.16% vs hoped ≥−20%): the W-53
   microbench bound (−96.7% of record-complex LLd misses) does NOT
   transfer to the sampler regime. Mechanism: total model-level LLd
   misses are only ~0.48M over the run (~107/gradient) — the arena
   memory is reused every gradient call (recover/realloc bump), so
   the record complex is already last-level-resident; the scatter
   the microbench punished does not exist here. Corollary for the
   roadmap: the Increment-B record-shrink upside (locality
   component) is even less relevant at model level than W-53
   argued — the batch API (Increment A) is the whole story for the
   sampler regime.
2. **Repeated-eval −10.3..−10.7% vs the −18..−28% band**: the band
   was derived from W-53's session, which ran under concurrent
   compile load (shared machine; W-53 §5.3 caveats). Tonight's idle
   desktop also shows stock itself +7..9% vs W-53's stock. Reading:
   the serving-regime win is LOAD-SENSITIVE — under memory pressure
   the per-record scatter sits on the critical path (and the
   locality upside exists), on an idle machine it does not (flat
   LLd corroborates). NOT adjudicated as a batch-1 regression:
   in-sampler improved 3× vs batch-0 and all deterministic gates
   are green; a same-session batch-0-arm A/B is the queued
   discriminator if the bridgestan-serving regime ever becomes the
   priority. (Hypothesis, not measured tonight.)

## 6. Verdict + roadmap state

**BATCH 1: GO — shipped and gated.** Batches 0–1 together: hier_2pl
−15.95%T / −17.06%G deterministic Ir, −5.6..−6.3% in-sampler wall,
bit-exact at every level probed (values, gradients, draws, unit
tests, callbacks instruction-identical). Migration-plan state:
batch 0 DONE (W-53), batch 1 DONE (W-57); batch 2 (one-autodiff/
broadcast branches, ~21 sites) is the next one-decision increment
with the SAME gate battery; batch 3/4 are audit-only; batch 5
(old-style scalar varis) untouched. For the upstream PR: the record
loop restructure (raw vptr-store + memcpy'd val block instead of
per-record placement-new) remains the recommended pre-PR step (W-53
§5.3 toolchain lesson; the +9 Ir/record new-cost term).

Artifacts: scratch/w57/ (gemm_probe.cpp, instantiate_probe.cpp,
w57_soa_batch01_develop.patch [batch 0+1 combined, applies to
develop@344d7167], w57_batch1_bundle.patch + w57_batch1_develop.diff
[batch-1 only], gate_draws.sh, wall_sampler.sh [note: agent-patched
sed extraction + bc shim — see WORKLOG], run_callgrind_w57.sh,
run_cachegrind_w57.sh, profile/, cachegrind/, wall/, draws/,
stock_so_md5.txt). Models: scratch/w53/model_*_patched now carry
batch 0+1 (stock arms pristine, md5-verified).
