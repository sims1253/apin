# W-126 scratch notes (pcm/ordered gathered primitive, family 3)

Resilience log. Commit after every meaningful step.

## STEP ZERO — the stock interior, fully read

The gate model does NOT call a stock pcm_lpmf (none exists in any stack — verified:
prim/prob has categorical/ordered_logistic only). It defines its own `pcm` fn; the
generated hpp (/tmp/w126_model.hpp, regenerated from the pristine .stan with the
bundle stanc) compiles for the rev instantiation to:

```cpp
unsummed = append_row(rep_vector(0.0,1), subtract(theta_var, beta_seg));  // [0; t - beta_k]
probs    = softmax(cumulative_sum(unsummed));
return categorical_lpmf<false>(y+1, probs);
```
Loop: `for n: lp_accum__.add(pcm(y[n], theta[jj[n]]*alpha[ii[n]], segment(beta,pos[ii[n]],m[ii[n]])))`
- y[n] in 0..m_i (0-based); K_i = m_i + 1 categories; beta IS a parameter (model tp block).
- priors (lognormal/normal/student_t on alpha/beta/theta/lambda) come BEFORE the likelihood
  → sweep-order-relevant (W-129 lesson #4); gpcm gathers AT the likelihood statement, so a
  likelihood-site single callback sits at stock's stack position (the hier_2pl/radon case,
  W-127 §3b) — but P6-style priors-before unit pattern still required to certify.

### The interior arithmetic (family/base math = alllayers = w127 = w130 = base 344d7167a0
### arithmetic; cmdstan-2.39.0's bundled math differs ONLY in the softmax rev adjoint spelling)

Forward value path per observation (all double space):
1. t = theta_j.val * alpha_i.val (var*var vari; ONE double multiply)
2. u_k = t.val - beta_k.val (k=1..m, elementwise)
3. c_0 = 0; c_k = c_{k-1} + u_k (prim cumulative_sum: STRICTLY SEQUENTIAL loop,
   result[i] = m[i] + result[i-1] — replicable trivially, no Eigen redux)
4. p = prim softmax(c): theta_e = (c.array() - c.maxCoeff()).exp();
   p = (theta_e / theta_e.sum()).matrix()  [family/base] or .exp().eval() then
   theta.array()/theta.sum() [cmdstan] — SAME double values both ways
   (exp recomputed vs materialized is value-identical; the divide is per-element)
5. lp_n = log(p[y+1])  (glibc log)
=> The "LSE" is softmax(cumsum) + log(element). NOTE: stock does NOT spell it as
   c_y - log-sum-exp; it DIVIDES each exp by S first, then logs. The primitive must
   do the SAME (call the same prim softmax on the same c vector, then log the element).

Checks on the path (throw set): categorical_lpmf does
  check_bounded("categorical_lpmf","Number of categories", y+1, 1, K)  → y out of range
  check_simplex("categorical_lpmf","Probabilities parameter", p)       → non-finite eta
(NaN theta/alpha/beta → NaN c → NaN p → check_simplex throws). Primitive keeps both,
per-element order, same function strings → byte-identical messages (W-112.2 discipline).

### The adjoint path per observation (reverse sweep, stock; family/base spelling)
1. log callback: a.adj += vi.adj / a.val  → g = e_n / p_y   (DIVISION, not inv-multiply)
2. softmax callback (family/base): x_adj.array() += p.array() * (res_adj.array() - p.dot(res_adj))
   dot = p.dot(res_adj) — Eigen dot redux (vectorized order inherited by calling same ops)
   [cmdstan-2.39 spelling differs: adj += -p*dot + p⊙res_adj — NOT numerically equal]
3. cumulative_sum callback: reverse i loop: adj(u_i) += adj(c_i); adj(c_{i-1}) += adj(c_i)
   ⇒ adj(u_k) = adj(c_k) exactly (relay only)
4. append_row callback: bottomRows passthrough (adj(u_k) to subtract's ret adjoints)
5. subtract callback (var - Matrix<var> overload): col-major loop ascending i:
   a.adj() += ret_adj_i (sequential SCALAR accumulation into t's adjoint — NOT a redux);
   beta_k.adj() -= ret_adj_i
6. multiply (var*var) chain: theta_j.adj += adj_t * alpha_val ; alpha_i.adj += adj_t * theta_val
   (probe to confirm exact spelling + FMA contraction on the compiled chain)

Cross-observation: all callbacks of obs n are contiguous on the stack (self-contained
body) → sweep visits obs N..1; per-coefficient adjoint accumulation order for repeated
jj/ii/item-shares = REVERSE-n. Primitive's ONE scatter callback (created at the
likelihood site, after prior edges → swept before them = stock's relative position)
must iterate reverse-n and accumulate in that order.

### STEP ZERO VERDICT (pre-registered question: is the category LSE reduction
### replicable bit-identically in a single-pass primitive?)

YES — mechanism: the reduction is NOT something the primitive must re-derive. Stock's
category reduction is (a) a strictly-sequential prim cumulative_sum (trivial), (b) the
prim softmax's exp/max/sum/divide where the ONLY order-sensitive piece is Eigen's
redux sum() over K+1 ∈ 3..9 elements — and the primitive CALLS THE SAME prim softmax
function on the same assembled c vector, so the redux semantics are inherited BY
CONSTRUCTION (same compiled code, same flags). Same for the adjoint's dot redux: the
primitive spells the same Eigen expression on the same-size vectors. The residual
replication burden is op-order discipline in the value/adjoint scalar arithmetic
(t multiply; sequential subtract-adjoint accumulation; division in log's chain; FMA
contraction matching per W-108.1) — the W-112-class discipline, not an Eigen-semantics
risk. NO STOP. (Probe to confirm type resolution + adjoint spelling before coding.)

### Accumulator (W-112 §2): rev accumulator<var> = 128-chunk collapse buffer
→ primitive returns std::vector<var> per-observation no-chain terms; model edit pushes
them per-element (identical chunk schedule = stock lp tree).

## STACK DECISION (gate a+b bundle)
- Family lineage bundle bs_w130 (cp -al → bs_w126): softmax arithmetic = base = what the
  branch (344d7167a0) carries; bs_alllayers/bs_w127/bs_w130 all identical on ALL interior
  files (softmax prim b87ea021, rev 45b31866; categorical_lpmf/cumsum/append_row/log =
  base; operator_subtraction = W-57/58 layers, adjoint arithmetic unchanged).
- cmdstan-2.39.0's bundled math has a DIFFERENT softmax rev adjoint spelling (9d845487) —
  the W-80 .so (661e6853…) and the build-dir ELF binary sit on it; NOT bit-comparable to
  campaign-math arms at gradient level. Disclosed; they stay read-only cross-checks.
- Protocol (W-130 §3 verbatim): both arms rebuilt on bs_w126 at model flags via the
  recorded W-129 command lines (direct gxx, rebuilt bridgestan.o in-copy — W-127 §3c
  mixed-ABI lesson), stock reference recorded FIRST (w36exp CLI read-only, seed 20260819,
  w100 s50 mw50, W-80 pf init rep0/chain_0).
- DATA/INIT: FOUND (not generated): scratch/w80/model_gpcm_latent_reg_irt/data.json
  (N=5500, I=11, J=500, K=5, y∈0..m_i polytomous — from the timssAusTwn_irt W-80 screen,
  generated by W-80's own fixed-seed protocol) + scratch/w80/inits/gpcm_latent_reg_irt/
  rep0/chain_0.txt (cmdstan-2.39 pathfinder, first PSIS draw, unconstrained).
  Disclosed in the record as W-80 assets, read-only.
- m vector (per-item max y) computed from data at gate time; real shape drives gate (a).

## Type-resolution questions for the probe (before writing the header)
1. subtract(var, Matrix<var>) → overload at operator_subtraction.hpp:240 (var_vt arithmetic
   + rev_matrix) → ret_type = ? (probe: expect var_value<VectorXd> or Matrix<var>; the
   family stack may have a W-57/58 batched-span variant)
2. append_row(VectorXd, X) → rev overload (any_var_matrix) or prim Eigen path → ?
3. cumulative_sum(X) → require_rev_vector_t; softmax(X) → require_rev_matrix_t → ?
4. assign into Matrix<var> probs: stan::model::assign path (needs bundle src on include)
5. Compiled chain of var*var (operator_multiplication) — exact FMA form
6. Eigen dot on sparse res_adj: confirm values match my hand-built dense formulation
   (the primitive builds res_adj as a dense zero + one nonzero, same as stock's arena adj)

## STEP ZERO — EMPIRICAL VERIFICATION (probes 1-6, family stack, model flags)

- probe_types/probe_adj: full type chain pinned. subtract(var,Matrix<var>) → Matrix<var>
  (AoS, W-57/58 batched-span layer); append_row → Matrix<var>; cumulative_sum →
  Matrix<var>; softmax → arena_matrix<Matrix<var>> (a Map); probs assign = var-handle
  copies (shared varis). Value path = plain double arithmetic; lp = log(p[y]).
- probe_adj forensics: printed cs adjoints are POST-cumsum-callback (suffix-summed):
  adj(un_k) = A_k + (A_{k+1} + (... + A_m)) RIGHT-NESTED (the cumsum reverse relay).
  adj_t = ((suf_1 + suf_2) + ...) ASCENDING left-assoc (subtract chain). multiply chain:
  avi->adj_ += bvi->val_ * adj_ (single statement → GCC-fused at model flags).
- **probe_softmax/probe_softmax2 — THE decisive finding**: softmax<VectorXd> (dense
  input) DIFFERS from stock's instantiation softmax<val-view> in last ulps (3554/14000
  elements). Mechanism: stock feeds softmax a CwiseUnaryView (val() over Map<Matrix<var>>)
  — non-packet-accessible → Eigen DefaultTraversal EVERYWHERE → glibc std::exp per
  element + SEQUENTIAL SCALAR sum + per-element divide. The dense instantiation
  packetizes → Eigen's polynomial pexp → last-ulp diffs. Manual SCALAR spelling:
  mx = max(c); S = Σ ascending RN(exp(c_k−mx)); p_k = RN(exp(c_k−mx)/S) —
  **bit-identical to stock's view instantiation on 2000 trials x K=3..9 (0 diffs)**
  while dense differs (3554). The stock LSE reduction is the SCALAR path — the MOST
  replicable semantics possible. No Eigen-redux risk.
- **probe_hand (final): 400/400 trials bitwise** (lp + adj_theta + adj_alpha + every
  adj_beta_k; m=2..8 → K=3..9; randomized values; model flags). Complete verified chain:

  FORWARD per obs: t=th*al; c[0]=0; c[k+1]=c[k]+(t−bv[k]) sequential;
  S = Σ ascending exp(c_k−mx); p_k = exp(c_k−mx)/S; lp_n = log(p[y_n]).
  CHECKS per obs (stock order): check_bounded("categorical_lpmf","Number of
  categories", y+1, 1, K); check_simplex("categorical_lpmf","Probabilities
  parameter", p) [check_simplex materializes dense; same instantiation → same sum].
  BACKWARD per obs (e = term adjoint): r=0; r[y]=e/p[y] (DIVISION);
  dot = p·r (single nonzero ⇒ exact); A = p⊙(r−dot);
  suf[K−1]=A[K−1]; suf[k]=A[k]+suf[k+1] (right-nested);
  adj_t = suf[1]; adj_t = adj_t+suf[k] ascending (k=2..K−1);
  theta_j.adj += adj_t*alpha_i.val (fused stmt); alpha_i.adj += adj_t*theta_j.val;
  beta_{pos+k}.adj −= suf[k+1] (pure subtract). Cross-obs: reverse-n (stock sweep).

### STEP ZERO VERDICT: REPLICABLE, bit-identically. GO.
(The pre-registered "Eigen redux semantics" risk dissolved: the model's softmax
instantiation is the scalar path. Verified, not assumed.)

## THE STACK-DEPENDENT SOFTMAX (found via the smoke; the -I mistake that found it)

HARNESS BUG WITH A BIG LESSON: my first smoke put `-I $BRANCH_REPO` FIRST, shadowing
the bundle's ENTIRE math with the branch base's math — and the branch base
(344d7167a0) carries a DIFFERENT prim softmax (make_holder/apply_vector_unulary
materializing form, hash a6aa50c1) than the family bundle (b87ea021, lazy-view
form). Both arms of that smoke compiled against the branch softmax; the "dense ==
stock" reversal was an artifact. Correct discipline (W-112's): ONLY the new header
shadows the bundle (-I inc/ with just the one header subtree).

THE REAL FINDING (probe9, both stacks, correct includes):
- BUNDLE (gate a/b stack): rev-softmax path == softmax(Matrix-val-view) ==
  softmax(arena-val-view) == MANUAL-SCALAR interior; the DENSE call differs (932/3500).
- BRANCH base (TU stack): rev path == both view calls == DENSE; MANUAL differs (932).
=> The softmax interior's arithmetic is STACK-DEPENDENT (the bundle keeps the val
view lazy -> Eigen scalar traversal, glibc exp, sequential sum; the branch's
apply_vector_unary materializes -> packet traversal). THE PORTABLE INTERIOR:
call `softmax(<val() view over an arena AoS var matrix>)` — the EXACT
instantiation the stock rev softmax produces — bit-identical to the composed
stock path on EVERY stack (0 diffs both). The primitive's forward now builds an
arena_matrix<Matrix<var>> of the K cumsum values per obs (K+1 no-chain varis) and
calls softmax(c_var.val()).
- The adjoint dot (p.dot(res_adj)) is stack-immune: res_adj has exactly one
  nonzero (g at y) so every traversal order yields the same double.
- Smoke (bundle, correct includes): 60/60 bitwise (lp + all grads, repeated idx).

## GATE (a): PASS at BOTH flag levels
`test_prim.cpp` on the bs_w130-family bundle math + ONLY our header via inc/
(W-112 discipline), stock arm = the EXACT generated loop (real rvalue/index_uni,
segment, the composed pcm body, the REAL accumulator<var>), prim arm = the
primitive + per-term accumulator adds.
- P1: 6 seeds x N in {1,2,3,5,8,17,100} x randomized I/J/m (K=2..8), repeated +
  permuted indices, 18 layouts (theta/alpha x {AoS, Map, SoA}; beta x {AoS, Map}
  — SoA-beta has NO stock counterpart: the generated model's beta is always a
  local Matrix<var>; segment/subtract/append_row on var_value don't compose to
  the generated spelling — the primitive's SoA-beta route is compile+value
  certified in the TU instead).
- P1b: N in {919, 2000} x 18 layouts, all-y-min / all-y-max boundary responses.
- P2: the REAL gpcm shape (N=5500, I=11, J=500, m from W-80 data; K in {2,3}),
  3 layout combos incl. the model's (Map theta/alpha + AoS beta).
- P3: priors BEFORE the likelihood (lognormal alpha + normal beta/theta — the
  model's statement order), AoS/Map x AoS/Map (this math's lpdf doesn't take
  var_value) — the sweep-order certification (W-127 P6 pattern).
- Throw set (13 cases): y low/high (2 per-item classes), NaN/inf theta, NaN
  alpha, NaN beta, jj 0/high, ii 0/high, N=0, baseline — ALL byte-identical
  messages (incl. the OOB-index names: stock's compiled evaluation order
  matches our jj-then-ii "theta"/"alpha" checks).
RESULT (logs/gate_a_{O3,O2}.out):
  O3 (-O3 -mavx2 -mfma): 802 cases / 20,764 bitwise component checks
     (lp + every theta/alpha/beta adjoint), 0 mismatches + 13/13 throws.
  O2: identical numbers.

## GATE (b): ALL GREEN
- bs_w126 = cp -al of bs_w130 (family bundle; W-57/58 layers etc.), primitive
  header at a PRIVATE inode (11893441) in its math tree; bridgestan.o
  e4b6077b (the canonical rebuilt one, reused); direct gxx compile+link
  (W-129 command lines; the bundle's kinsol lib name is libsundials_kinsol.a).
- STOCK arm built FIRST from the pristine hpp (bundle stanc 2.39, hpp md5
  9151275b; .so md5 32d5b3fe). STOCK REFERENCE recorded BEFORE the prim arm
  existed: draws md5 a342848b18bf6eebe360097c0681a633 (w36exp CLI read-only,
  seed 20260819, w100 s50 mw50, W-80 data + pf init rep0/chain_0; 3,102+1,550
  grad calls; 510 NaN-exception spam — the W-80-documented gpcm pattern, priors
  throw before the likelihood; the trajectory moves at ~1e-15 relative scale —
  gradient-sensitive at ulp level).
- DOUBLE ANCHOR: the W-80 SHIPPED .so (cmdstan-2.39.0 stack, default flags,
  md5 661e6853) reproduces the SAME draws md5 + 510 errors under the same
  protocol — the family stack is output-equivalent to the shipped artifact
  here.
- Hand-edit (make_prim_edit.py, asserts blocks verbatim): the include + the
  REV-mode loop -> pcm_lpdf_gathered<propto__>(y, theta, jj, alpha, ii, beta,
  pos, m) + per-term lp_accum__.add loop. The double-mode instantiation and
  write_array keep the stock loop. hpp md5 8bb3c3ef; .so md5 1a5e98d9.
- PRIM arm draws: md5 a342848b... DIGIT-FOR-DIGIT; same grad calls; same 510
  exception count.
- 100-pt parity (gate_parity_w126.py, ctypes C ABI, W-103 points): lp 0/100,
  gradient-vector 0/100 (D=530), constrained output 0/100 (DC=545) EXACT-ZERO.

## GATE (c) — expectations stated BEFORE measuring (family baseline, first)
Stock per-observation graph (avg K≈2.45 here: m∈{1,2}): ~3m+5 ≈ 8-11 varis +
~6 callbacks/obs (subtract span, append passthrough, cumsum, softmax, log,
multiply) + Eigen arena copies + per-obs softmax instantiation; prim: ~K+2
no-chain varis/obs (c_var + term) + ONE callback + the view softmax call.
The gpcm run also carries priors (lognormal/normal×2/student_t), the 500x5
W_adj*lambda_adj regression, the beta sum tp, GQ — NOT touched.
EXPECTATIONS (family-3 baseline; election88 family-4 was 1,578 Ir/elem stock):
- per-obs likelihood interior symbols (softmax/cumulative_sum/subtract chains,
  categorical_lpmf) -> ~0 (replaced by pcm_lpdf_gathered forward + scatter);
- vari-stack pushes and sweep/zeroing frames shrink ~2-3x (≈8-11 -> ≈5/obs);
- net run-total: -25..-45% class (the likelihood's share is diluted by priors
  + regression + GQ that election88 didn't have... actually election88 had
  tp-loops; here the tp is tiny (beta sum) but the W_adj*lambda product is
  J-sized. I'll take any net, the baseline is the deliverable);
- draws md5 under tracing == a342848b on BOTH arms.

## GATE (d): TU + controls: PASS
- TU (branch worktree, Eigen 5.0.1 + bundle tbb, -O2 -mavx2 -mfma standalone
  gtest build): 5/5 PASSED -- BitIdenticalToComposedStock (6 shape/seed/layout
  cases incl. SoA theta/alpha and N=519), PriorsBeforeLikelihood (2 cases),
  ValueMatchesReference, ThrowSet, SizeZero.
  TWO TEST-SIDE bugs found during development (owned; no header change):
  (i) the stock arm's accumulation was `prior + sum()` instead of the same
  accumulator push schedule; (ii) the prim arm ran the primitive BEFORE the
  prior -- the reversed callback creation order moved the prior edge to the
  wrong sweep position (theta_0 1 ulp) -- the W-129 delivery-position
  mechanism confirmed LIVE in family 3, caught by the TU's own priors test.
- Controls (same build): prim/prob/categorical 6/6, mix/fun/softmax 1/1,
  mix/fun/cumulative_sum 1/1, mix/fun/log_softmax 1/1, rev/fun/log_softmax
  2/2 -- all PASSED.
- Sibling integrity: bs_w130's bernoulli header + bridgestan.o (e4b6077b) +
  w127 stock .so (2cf00ef9) byte-intact; worktrees w112/w127/w130 untouched.

## GATE (c): -88.28% (band -25..-45 EXCEEDED FAVORABLY — owned below)
| metric | stock | prim | delta |
|---|---|---|---|
| PROGRAM TOTALS Ir | 214,271,454,670 | 25,116,551,792 | -88.28% |
| Ir/grad (4,652 both) | 46.05M | 5.40M | -88.3% |
| Ir/obs-eval (25.6M both) | 8,366 | 981 | -88.3% |
| draws md5 under tracing | a342848b... BOTH ARMS | | bit-identity certified under tracing |
| grad calls | 3102+1550 both | same | |
- Attribution (self Ir, complex classes):
  | complex | stock | prim |
  |---|---|---|
  | pcm body (stock user-fn) / pcm_lpdf_gathered fwd (prim) | 8.557e9 | 7.163e9* |
  | softmax instantiation | 10.486e9 | 3.641e9 |
  | cumulative_sum | 5.517e9 | 0 (symbol gone) |
  | subtract | 4.540e9 | 0 (gone) |
  | "string-class" copy complex (see below) | 115.799e9 | 0.005e9 |
  | malloc/free | 18.687e9 | 2.894e9 |
  | stack_alloc (arena) | 7.039e9 | 0.605e9 |
  | vari-stack pushes | 2.407e9 | 0.693e9 |
  | scatter callback (prim only) | -- | 2.611e9 |
  | exp (libm) | 2.785e9 | 2.808e9 (the LSE interior retained) |
  | log (libm) | 1.014e9 | 1.014e9 (identical) |
  | log_prob_impl self | 3.261e9 | 0.277e9 |
  *prim fwd = pcm_lpdf_gathered_impl 6.416e9 + public fn 0.747e9
- THE BIG BLOCK: stock's 115.8e9 "string-class" complex (54% of the run) is
  MEMCPY-CLASS work inside the stock likelihood's per-observation expression
  materialization, MIS-SYMBOLIZED: stan_cli has no debug info and the copy
  helpers resolve into its address range (the caller tree shows the bulk
  reachable from the stock softmax<Matrix<var>> instantiation, 22.8M calls;
  _M_append fired 91.1M times = ~3.5/observation-eval). The primitive's
  equivalent copies are ~0.005e9. I.e., the dominant stock cost is the
  per-obs graph materialization itself -- exactly what the primitive deletes.
- OVERSHOOT mechanism (owned): beyond the registered likelihood-complex
  removal (~35e9 of softmax/cumsum/subtract/pcm-body self), the stock run's
  copy/alloc complexes (~141.5e9) collapse with the per-observation
  expression graph gone -- a compounding the per-complex band never priced
  (the W-130 sweep-collapse overshoot class). The untraced wall times:
  stock 14.56s + 8.03s (two CLI phases) vs prim -- check prim_run.log.

## FINAL (post-record bookkeeping)
- Branch message repair: an --amend/--exec sequence briefly duplicated the
  header commit; repaired via soft reset to base + two clean commits:
  gathered-pcm @ e355b14535 (2a3b5139db header + e355b14535 TU), tree
  IDENTICAL to the gated state (header f3bc10b3 in branch == bundle private
  inode; 659 insertions, 2 files). Record hashes updated.
- Wall times: stock 14.56+8.03s vs prim 1.52+0.82s (9.7x).
- All artifacts committed; nothing pushed; WORKLOG.md/comms.md untouched (PI).
