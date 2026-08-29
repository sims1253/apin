# W-120 — the bit-identical normal_id_glm edge cleanup (Lane A): one of the three pre-registered removals lands bit-identically (the vec-alpha edge Zero, −8.03 Ir/elem, memset symbol → 0); the to_arena copy is a disclosed SURVIVOR (lifetime semantics); the diamonds-band item dies as a W-119 MECHANISM MISATTRIBUTION — the "y_scaled ctor memset" never existed (Eigen sized-ctors do not zero), the real diamonds-class memset is Eigen's product-assignment `evalTo → dst.setZero()` and it is LOAD-BEARING (the col-major GEMV kernel read-modify-writes its destination), so the −15..−25%-of-diamonds-G band is UNACHIEVABLE in the memset/copy-elimination class

Executed 2026-08-29 per the WORKLOG "W-120 PRE-REGISTRATION". Worktree
`external/math_dev_w120` (branch `glm-edge-cleanup`, off fork/develop
344d7167a0, the campaign standard base; verified: base normal_id_glm_lpdf
md5 90389d08 = the pristine reference). Commits 635223b627 + 97d9a8a339
(NOT pushed). Artifacts under `scratch/w120/`. PI-owned files untouched;
the sibling bundles/model trees verified untouched afterwards (md5s below).

## 0. Scope decision (pre-registration's first instruction)

**SHARED-ADDITIVE, not glm-local.** The vec-alpha edge is built by
`internal::ops_partials_edge<double, Op, require_eigen_st<is_var, Op>>`
whose constructor ALWAYS does `partials_(partials_t::Zero(rows, cols))` +
`operands_(to_arena(ops))` — there is no glm-local way to reach the edge's
members before construction, and every specialization zeroes. The change is
therefore an OPT-IN addition to the shared templates (no existing code path
modified — every non-glm distribution instantiates byte-identical code):

1. `prim/functor/operands_and_partials.hpp` (+38 lines): a POD
   `internal::operand_with_partials<Op, Partials>` (holds two references,
   consumed synchronously by the edge constructor) + a make-helper.
2. `rev/functor/operands_and_partials.hpp` (+36 lines): a new
   `ops_partials_edge<double, operand_with_partials<...>>` specialization —
   identical to the stock eigen-var edge except `partials_` is CONSTRUCTED
   FROM the given partials expression (arena alloc + copy, no Zero pass).
   Operand storage (`to_arena`), partials type, `partials_vec_`, edge
   position in the tuple, `build()`/`update_adjoints` behavior: unchanged.
3. `prim/prob/normal_id_glm_lpdf.hpp` (net −3 lines): for a reverse-mode
   VECTOR alpha (compile-time `alpha_seeded` = var-return ∧ Eigen-with-var-
   scalar ∧ vector), `mu_derivative` is computed before the propagator and
   seeded into the alpha edge at construction (glm constructs
   `internal::partials_propagator` explicitly because
   `make_partials_propagator`'s `return_type_t` deduction cannot see
   through the wrapper — same class template, same `require_var_t`
   specialization selection, documented in-code). The stock
   `partials<2>(ops_partials) = mu_derivative;` assignment disappears (it
   IS the seed now); scalar-alpha and fwd/mix paths untouched. mu_derivative
   is evaluated exactly once either way (hoisted, not recomputed).

Controls widened accordingly (scope guard): bernoulli_logit_glm +
poisson_log_glm suites + all four operands_and_partials suites (§4).

The value path and all arithmetic are untouched: the only floating-point
delta anywhere is that the alpha-edge partials array receives its final
bits via construction-from-expression instead of Zero-then-assignment
(same expression, same bits, one fewer pass over the array).

## 1. The three pre-registered removals, one by one

**(1) The vec-alpha edge partials Zero (8 Ir/elem measured by W-119):
REMOVED, bit-identically.** All gates pass; the memset symbol attributed to
the edge is gone (§4); the measured win is exactly the predicted magnitude:
−8.03 Ir/elem (fwd 37.56→29.53, full 44.59→36.56 at N=5000, the W-119
glm_vec anchor shape; W-119's stock anchor 44.83 agrees within 0.5%; the
reverse pass is Ir-identical by construction — full−fwd = 10.544M both arms).

**(2) The to_arena alpha-operand copy (~5 Ir/elem): SURVIVOR, with the
mechanism.** glm binds alpha through `const T_alpha&`, so a caller's
temporary (e.g. `normal_id_glm(y, x, alpha_vec + beta, ...)`) is
indistinguishable from an lvalue; a non-owning edge view would dangle the
moment the temporary dies (before the reverse sweep), and the AoS
`Matrix<var>` heap array cannot be pointer-stolen into the arena
(different allocator domains — arena residency requires the copy). The
rvalue case is exercised in the unit probe (gate a `rvalue_alpha`) and in
the new gtest (temporary `alpha2 + alpha2`). Removing this copy is a
semantic change (UB class), not a memset/copy elimination — it stays.

**(3) The "y_scaled ctor memset" (8 Ir/elem, "every glm shape", the basis of
the −15..−25%-of-diamonds-G band): the item DIES as a W-119 mechanism
misattribution, recorded here with the full mechanism.**
- Eigen sized constructors DO NOT zero-initialize
  (`Array<double,-1,1> y_scaled(N)` leaves storage uninitialized — proven
  empirically: forms with the sized ctor and no downstream use show zero
  memset; W-119's phase table attributed Eigen product-evaluation cost to
  the constructor line).
- The real N-sized memset in every glm shape (diamonds d24: 12,005,700 Ir
  per 300 calls = 8.00/elem, EXACTLY the magnitude W-119 measured) is
  Eigen's product assignment: `Assignment<Dst, Product>::run →
  generic_product_impl_base::evalTo → dst.setZero() → std::fill_n →
  memset` (disassembled + addr2line'd inline chain into ProductEvaluators.h
  :148→:348-349). It fires whenever `y_scaled = x_val * beta_val_vec` is
  evaluated (both statements' forms: sized/default ctor, Matrix temp,
  noalias — all identical).
- It is LOAD-BEARING: the col-major GEMV kernel
  (`general_matrix_vector_product<ColMajor>::run`,
  GeneralMatrixVector.h) accumulates with
  `pstoreu(res+i, pmadd(c0, palpha, ploadu<ResPacket>(res+i)))` — it
  READ-MODIFY-WRITES the destination, so the zero pass is semantically
  required for this kernel. Eliminating it requires swapping the kernel
  or the accumulation scheme = an arithmetic-route change (statistical
  class), OR an Eigen-level change (an overwrite-mode gemv for the
  evalTo/first-touch case — which itself has a −0.0 sign-of-zero edge:
  `fma(c,1,0)` maps c=−0.0 to +0.0, a direct store would not). Both are
  OUTSIDE W-120's memset/copy-elimination class. Honest negative recorded;
  this closes the diamonds-band half of Lane A as pre-registered ("if
  ... cannot be removed without semantic change ... disclose the survivor").
- An intermediate y_scaled unsized-ctor edit (the literal pre-registration
  wording) was implemented, verified a NO-OP (identical memset counts,
  identical model md5), and REVERTED so the diff contains only the
  load-bearing change.

## 2. Gate (a) — bitwise unit at model flags: PASS

Same probe source built against the pristine base worktree
(scratch/w120/math_stock_base @ 344d7167a0) and the branch, at BOTH
`-O3 -mavx2 -mfma` and `-O2` (bundle deps eigen 3.4.0 for both arms).
Cases: the real diamonds shape (N=5000/Kc=24, real y+Xc) with scalar/vec
alpha × var/double, y autodiff, x autodiff, scalar/vec sigma × var/double,
propto true/false; randomized N=1..8 shapes; N=64; rvalue (temporary) alpha
expressions; T_x_rows==1 broadcast-x; two chained glm calls on shared
operands; prim-only. Output: hex bit patterns of lp + EVERY gradient
component (alpha, beta, sigma, y, x as instantiated).

- 173,664 value lines per posture, byte-identical between arms:
  avx md5 5a6895a9c6407193ff58901004e8ff5a (stock = patched),
  -O2 md5 537e1766200363fa78881c3b1e99358b (stock = patched).
  (Cross-posture md5s differ — the FMA-contraction dimension, standing
  W-108.1 protocol: identity is required within posture only.)
- Artifacts: scratch/w120/{probe_w120.cpp, build_gate_a.sh,
  probe_{stock,patched}_{avx,o2}, logs/gate_a_*.txt}.

## 3. Gate (b) — model gate (diamonds, W-29 protocol): PASS

- STOCK reference recorded FIRST: frozen read-only
  scratch/w106/model_diamonds_alllayers/diamonds_model.so (md5
  95282364d16b6c90c54af6a15af85e09), sampler read-only
  external/walnutpie/build_w36exp/examples/stan_cli, data stan/data/
  diamonds.json, `--seed 20260819 --warmup 100 --samples 50
  --metric-window 50 --init-file stan/inits_w36/diamonds/rep0/chain_0.txt`
  → draws CSV md5 **7dad75d3325b9a5e2a85ddc46645387d** (rc=0).
- PATCHED arm: `cp -al` of the all-layers bundle → scratch/w120/bs_w120
  (private inodes for every dropped header — verified distinct inodes; the
  sibling's files never written), the three headers applied as PATCHES onto
  the BUNDLE's own versions (the bundle's math is an older release line —
  dropping worktree files wholesale would have imported unrelated drift;
  the glm file was byte-identical to base so it drops in directly),
  src/bridgestan.o rebuilt in-copy (deterministic: md5-identical to the
  original e4b6077b), model rebuilt (gxx_fixed, TBB_CXX_TYPE=gcc,
  /usr/bin/make -j2, nice 19, env -u LD_LIBRARY_PATH, CXXFLAGS
  -mavx2 -mfma kept), same protocol → draws md5
  **7dad75d3325b9a5e2a85ddc46645387d DIGIT-FOR-DIGIT** (rc=0). Rebuilt and
  re-run after the y_scaled revert — still identical.
- Parity: 100 deterministic points (default_rng(20260822),
  standard_normal(26)*0.5), direct ctypes C ABI (the bridgestan python
  module's dllist dependency no longer resolves in this environment —
  ported to raw bs_* calls, same ABI): lp mismatches 0/100, full-gradient
  mismatches 0/100, exact-zero class. PASS.
- Sibling integrity post-run: bs_alllayers' three headers still
  90389d08/f4959651/659c7f6a, its .so 95282364, its bridgestan.o e4b6077b.

## 4. Gate (c) — callgrind: band FAIL (honest negative), attribution clean

W-29 protocol (valgrind 3.23 ~/vginstall, Ir-only), one run at a time
(`ps` checked before each; no sibling collision), w50 s50 protocol on both
arms; draws under callgrind md5-identical to the reference in BOTH arms
(the trajectory is frozen evidence of equal computation).

- **diamonds G (the pre-registered band):** stock 1,065,409,492 Ir →
  patched 1,065,278,463 = **−0.012%** — far outside −15..−25%. Mechanism:
  diamonds has SCALAR alpha (no vec-alpha edge; the O(1) edges are the only
  glm-local machinery), and the one N-sized memset in its glm is the
  Eigen product evalTo setZero of §1(3) — identical in both arms (program
  memsets: stock 125,492,134 / patched 125,520,052; the 125M is dominated
  by rapidjson data parsing 96.99M + sampler infra). The glm self cost
  −0.13% is code-layout noise. **The band was computed from the
  misattributed mechanism; it is unachievable in-class. The negative +
  mechanism is the deliverable for this item.**
- **vec-alpha class (the seeded edge's own band, attribution):**
  W-119's probe rebuilt on both roots, N=5000 ×300:
  fwd 56,340,824 → 44,296,781 (−21.4%; 37.56→29.53 Ir/elem = **−8.03/elem,
  exactly the pre-registered 8.0**), full 66,884,024 → 54,839,981 (−18.0%;
  44.59→36.56/elem); reverse identical (10.544M both). Attribution:
  stock fwd carries TWO N-memsets per call (24,012,900 total = the Eigen
  product setZero + the alpha-edge Zero); patched carries ONE (12,013,500
  = the Eigen product setZero survivor; edge Zero → **0 occurrences**;
  remaining small memsets are K-sized beta-edge Zeros, 3,900×2). lp sinks
  identical across arms.
- Artifacts: scratch/w120/profile/{stock,patched}/ (callgrind.out + ann +
  draws), logs/{vec,d24fwd}_*.out/.ann.txt, micro experiments
  eigen_memset.cpp (7 assignment forms) + micro_memset.cpp, and the
  addr2line chain evidence for the ProductEvaluators mechanism.

## 5. Gate (d) — TU + controls: PASS

- NEW tests (on-branch, test/unit/math/rev/prob/normal_id_glm_lpdf_test.cpp):
  `ProbDistributionsNormalIdGLM_vec_alpha_seeded_edge` (lvalue + rvalue/
  temporary alpha vs the composed-primitives reference: lp, sigma, alpha,
  beta adjoints) and `..._vec_alpha_seeded_edge_rowvec_x` (T_x_rows==1 vs
  analytic gradients). Two test-arithmetic bugs found on first run (wrong
  sign; a chain-rule reference evaluated at the wrong point) were fixed —
  the PRODUCTION code was never at fault.
- **TOTALS: 190 testcases, 0 failures.** rev normal_id_glm 56 (incl. the
  two new seeded-edge tests + the VarMatrixTypedTests suite), mix
  normal_id_glm 2, rev bernoulli_logit_glm 44, rev poisson_log_glm 44,
  operands_and_partials prim 2 + rev 18 + mix 16 + fwd 8. runTests.py,
  gxx_fixed, TBB_CXX_TYPE=gcc, -j2, nice 19; full log + XMLs in the
  worktree, summary in scratch/w120/logs/gate_d.log.
- Note: this math version keeps the glm test suites under rev/mix only —
  the prim bernoulli/poisson paths do not exist (rc=255 = "no matching
  tests found", not failures).
- Note: the math develop tree runs its tests against eigen 5.0.1 (its own
  deps); the model/bundle gates above used eigen 3.4.0 — the change is
  Eigen-version-agnostic (no Eigen API beyond Map/product assignment).

## 6. Deviations & disclosures

- The pre-registration's design item (1) wording ("replace the
  Zero-init-then-overwrite of the alpha edge partials with
  construct-into-arena") was implemented via an opt-in wrapper + edge
  specialization rather than by modifying the existing edge constructor —
  the pre-registration's own scope guard anticipated this ("if the fix
  lands in SHARED edge machinery ... determine first, disclose which"):
  disclosed as SHARED-ADDITIVE, controls widened.
- The pre-registration's band (c) (−15..−25% of diamonds G) was derived
  from W-119's Lane A "y_scaled ctor memset" item, which this work proves
  was a misattribution (§1(3)). The band therefore fails not because the
  implementation fell short but because the targeted waste does not exist
  in removable form; the honest negative + full mechanism is recorded.
- glm constructs `internal::partials_propagator` explicitly for the seeded
  case (make_partials_propagator cannot deduce through the wrapper) —
  same class, same specialization, upstream would likely add a
  make_partials_propagator overload instead (noted in the upstream
  assessment).
- The diamonds stock reference run shows a frozen trajectory (50 near-
  identical draws — short-warmup behavior of this posterior); the md5
  gate is insensitive to this (both arms identical), and parity (100
  randomized points) covers the non-degenerate gradient space.
- Machine discipline: ≤2 build cores, one callgrind at a time (ps checked;
  one spurious grep match root-caused to the wrapper pattern per W-119's
  known issue), nice 19, env -u LD_LIBRARY_PATH, artifacts under
  scratch/w120/. /tmp used only for the parity ref npz.
- Worktree math_stock_base (pristine 344d7167a0, detached) lives under
  scratch/w120/ as the stock probe arm — private, does not touch any
  sibling worktree.

## 7. Upstream-candidate assessment

YES for the seeded-edge opt-in, with small API polish: the two shared-
header additions are additive and gated to distributions that fully
overwrite an Eigen-var operand's partials (the wrapper documents the
contract); bernoulli_logit_glm / poisson_log_glm / neg_binomial_2_log_glm
have the identical full-overwrite pattern and could adopt it (their vec
edges carry the same 8 Ir/elem); a `make_partials_propagator` overload
would remove the explicit-construction wart. NO for the Eigen product
setZero (separate project, Eigen-level: an overwrite-mode first-touch gemv
variant, with a sign-of-zero caveat) and NO for the to_arena copy (API
semantics). stan-math PR sized: ~80 added lines, one distribution touched.

## 8. Artifacts

`scratch/w120/`: probe_w120.cpp + build_gate_a.sh + probe binaries +
logs/gate_a_*.txt (bitwise gate); gate_parity_w120.py (ctypes parity);
bs_w120/ (private patched bundle), model_diamonds_w120/, runs/ (md5
evidence), profile/{stock,patched}/ (model callgrind), run_gate_d.sh +
logs/gate_d.log (test suites); probe_glm_{stock,patched} + logs/{vec,
d24fwd}_* (W-119 probe re-anchor + attribution); eigen_memset.cpp (the
Eigen mechanism isolation); micro_memset.cpp (superceded — region-capture
artifact, kept for the record); math_stock_base/ (pristine stock arm).
