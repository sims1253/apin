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
