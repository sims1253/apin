# The gathered-GLM generalization map: which families admit the W-108 optimization

> **STATUS 2026-08-29 (evening — campaign ESS/s COMPLETE):** families
> 1+2 landed AND measured end-to-end. The four gather-class models run
> **~3.2× ESS/s geomean vs the W-109 recommended default with every
> draw md5-identical**: radon_pp 2.65× (wall 0.348×), radon_var 3.90×
> (wall 0.297×), hier_2pl ≈5.6-6.7× (wall 0.33-0.49×, accounting-
> dependent), bym2 1.80× (wall 0.824×). Primitives: bernoulli_logit
> gathered (math branch incl. the W-108.1 FMA-schedule fix,
> gathered-glm-mapfix), normal gathered (incl. the W-112.2 throw-set
> fix, gathered-normal-fmafix @ 9a07ffa459), ICAR dot_self gathered
> (gathered-icar). Compiler: the stanc3 REGISTRY emits all three
> automatically (gathered-registry @ 50e8c9d; numerically inert at its
> level). Three standing bit-identity lessons banked: (1) unit gates
> compile at MODEL FLAGS (FMA contraction is a bit-identity dimension —
> W-108.1); (2) THROW-SET parity is part of the contract, not
> "invalid-input behavior only" (W-112.1/112.2 — exceptions steer
> trajectories); (3) full-grid md5 stop-gates, not pilots (W-116b).
> In flight: W-118 (fused normal interior, −15..−30% more,
> bit-identical), W-120 (glm edge cleanup). User-decision lanes: glm
> emission for everyday forms (−60%+, statistical class; workaround =
> write normal_id_glm explicitly), vectorized-form emission (C1),
> families 3/4 (pcm, election88).

> **STATUS 2026-08-29 (post-execution):** Families 1 and 2 of the ranked
> campaign below are LANDED, both bit-identical drop-ins, per the W-108
> recipe: **W-112** `normal_lpdf_gathered` (branch gathered-normal @
> bc00891778) — radon_pp G −65.5% / radon_var −66.4%, BOTH pre-registered
> bands hit, 22,360 bitwise checks (caught two real 1-ulp FMA bugs), draws
> md5 digit-for-digit; key structural finding: `accumulator<var>`'s
> 128-element chunk buffer forces a per-observation-var return + per-term
> push loop (shapes the emission). **W-113** `dot_self_gathered_diff`
> (branch gathered-icar @ 3b9ee1b7dd) — bym2 G −17.0% (band underrun
> disclosed: bit-identity forbids SIMD reassociation of the dot
> reduction; entire 2.16e9-Ir ICAR complex → 0), 59,178 bitwise checks
> (caught a real GCC arg-order scatter bug), draws digit-for-digit; PI
> decision: NO relaxed-precision variant. **W-115** (in flight) = the
> stanc3 REGISTRY (bernoulli_logit expression + ICAR expression + the
> normal LOOP matcher, both eta shapes). Families 3 (pcm/gpcm) and 4
> (additive bernoulli_logit/election88) remain queued. Records:
> results/normal_gathered_w112.md, results/icar_gathered_w113.md,
> WORKLOG W-112/113/115.

Session 2026-08-29. Questions (user): (1) why a NEW `bernoulli_logit_lpmf_gathered`
instead of changing the existing one; (2) which OTHER distribution families admit
this kind of extreme optimization. This record = the family census over the whole
benchmark suite, the measured cost attribution (W-111 callgrind census, below),
and the campaign plan with per-family designs and gates. No code was written;
every number here is measured on existing binaries.

Landed state this builds on: math#14 (`bernoulli_logit_lpmf_gathered`, branch
`gathered-glm` @ ea96b3c9fa) + stanc3#7 (emission pass, branch `gathered-glm-emit`
@ 58e6824) — hier_2pl −40.9% Ir/grad on the composed stack (−63.4% vs W-34-era
stock), bit-identical end-to-end, automatic at --O1. (PR numbers verified against
the forks this session: sims1253/math#14 and sims1253/stanc3#7. Two WORKLOG
close-out headers carry the internal typos "math#7"/"stanc3#2"; the entry bodies
are correct.)

## 1. The admission test

A likelihood family admits the extreme optimization when ALL four hold:

1. **Separable lpdf** — the density is a sum of per-observation terms
   f(y_k, eta_k, [shared scalars]). Holds for the one-parameter exponential
   families in log/natural form (bernoulli_logit, poisson_log, neg_binomial_2_log,
   categorical_logit, ordered_logistic/pcm) and normal (with scalar or
   per-observation scale). Fails for multi_normal/GP (dense cross-observation
   covariance), ODE models, and any likelihood with cross-observation reductions.
2. **Gather-GEMV linear predictor** — eta is assembled from INDEX-GATHERED
   coefficient vectors (theta[jj], alpha[ii], …) plus data vectors/scalars via
   eltwise ops. The indices must reach the primitive's ABI so reverse can be ONE
   scatter-add. Dense design matrices do NOT belong here (that is the stock
   `*_glm_lpmf` family, already in math — W-34 Arm A documented that the GLM
   family structurally cannot express gathered/bilinear predictors).
3. **Diagonal d(lp)/d(eta)** — the gradient wrt the linear predictor is
   per-observation, so the reverse pass scatters through the index arrays with
   no cross terms. (categorical_logit is the boundary case: per-observation it
   is a dense K-category block — still scatter-addable but with a softmax/LSE
   interior, the hardest of the set.)
4. **Reproducible interior** — stock's lpdf is partials-in-forward
   (operands_and_partials), so the primitive can copy the interior verbatim and
   claim BIT-IDENTITY instead of statistical equivalence. Verified in the tree:
   bernoulli_logit_lpmf, normal_lpdf, poisson_log_lpmf, ordered_logistic_lpmf
   all qualify.

What does NOT admit it (measured or structural): eltwise fusion without a
primitive (W-48: ~0 ceiling — only eliminating per-element work reaches it);
dense-X GLMs (stock-served); broadcast-no-gather forms (lsat — W-111 confirms
zero gather symbols); GP/multivariate (dense linear algebra class); tiny-N
models (sampler-dominated).

## 2. The census (all 21 CORE_SET models + build/ extras)

| family | suite models | Stan form | generated form | math target |
|---|---|---|---|---|
| bernoulli_logit, 2PL bilinear gather | hier_2pl (N=19,200) | `y ~ bernoulli_logit(alpha[ii] .* (theta[jj] - beta[ii]))` | expression, index_multi | **LANDED** (math#14 + stanc3#7) |
| normal, gathered mu, loop form | radon_pp (N=12,573, J=386); radon_var (N=919, J=85) | `for (n) { mu[n] = alpha[c[n]] (+ x[n]*beta[c[n]]); target += normal_lpdf(y[n] \| mu[n], sigma) }` | C++ loop, index_uni, SCALAR lpdf per element | **90.1% / 87.4% of G** (W-111) |
| ICAR/CAR quadratic gather | bym2 (N=1,921, 5,461 edges) | `target += -0.5 * dot_self(phi[node1] - phi[node2])` | expression, index_multi ×2 | **~43% of G** (W-111) |
| pcm / ordered_logistic gathered | gpcm_latent_reg_irt (build/, non-CORE; the W-80 harm model) | `for (n) target += pcm(y[n], theta[jj[n]] .* alpha[ii[n]], …)` | loop, gathered scalar eta + cutpoints | unmeasured; gate model exists |
| bernoulli_logit, additive multi-gather | election88_full (build/, non-CORE) | `y_hat[i] = … + a[age[i]] + b[edu[i]] + c[age_edu[i]] + d[state[i]] + e[region[i]]; y ~ bernoulli_logit(y_hat)` | tp loop, 5 gathers, 2 index arrays | unmeasured; generalizes the LANDED primitive's eta space |
| bernoulli (non-logit), integer-exponent | dogs (30×25, 2 params) | `y[j,t] ~ bernoulli(a^s * b^v)` | nested loops | negligible (math side ~irrelevant at N=750, 2 params) |
| bernoulli_logit broadcast (NO gather) | lsat (N=1,000×T=5) | `r[k] ~ bernoulli_logit(beta * theta - alpha[k] * ones)` | expression, broadcast | **0 gather symbols (W-111)** — fusion/kernel class, NOT this lane |
| poisson_log / neg_binomial_2_log gathered | none in suite | — | — | register-only (no gate model) |
| categorical_logit gathered | none in suite | — | — | register-only |
| normal dense-X / _glm class | blr, kidscore, logmesquite, diamonds | `X * beta` | stock glm / rewrite | stock-served; blr's residual cost is exceptions (W-104) |
| everything else | GP/kronecker/accel (dense lin alg), ODE (lotka, garch, arma), mixtures | — | — | other lanes (W-34 §7.4 interior/eigensystem classes) |

Corrections carried into the record (vs the 2026-08-28 handoff): **pilots is the
NORMAL family with N=40** (not bernoulli; and negligible as a math target — its
problem is the ridge class, W-88's lever); **lsat has no gather** (broadcast);
**bym2's likelihood has no gather** — its gather complex is the ICAR prior, so
the family that admits the optimization is a gathered quadratic form
(dot_self), not a gathered poisson_log.

## 3. W-111 — measured attribution (callgrind census)

Protocol: W-29 short run (warmup 100, samples 50, seed 20260819,
--metric-window 50, pf init rep0/chain_0 per the w63 manifest), sampler
`build_w36exp` READ-ONLY, models = the W-109 ALL-LAYERS .so arms (SoA math#5 +
W-102 index views + W-103 log1p kernel + avx2 — i.e., what remains AFTER every
landed math layer). One callgrind at a time, nice 19. G = inclusive Ir of
`bs_log_density_gradient`. Artifacts: `scratch/w111/profile_*/`.

| model | T | G (share of T) | per-element complex | share of G |
|---|---|---|---|---|
| radon_pp | 28.27e9 | 26.32e9 (93.1%) | scalar `normal_lpdf<false>` body 42.6% + per-element libm `log(sigma)` 13.6% + assign/rvalue loop machinery 16.7% + chainstack pushes 10.5% + lp_accum sum 2.0% + scalar-call edges 4.6% | **90.1%** |
| radon_var | 2.45e9 | 1.73e9 (70.6%) | scalar lpdf 28.5% + loop machinery 29.6% + chainstack 10.4% + log 9.2% + sum 2.6% + edges 7.1% | **87.4%** |
| bym2 | 18.03e9 | 5.01e9 (27.8%) | ICAR: subtract(Holder) fwd+cb 23.8% + index_multi gathers 11.2% + dot_self fwd+cb 4.1–8.1% (symbol-overlap band) | **~43%** |
| lsat (negative control) | 7.65e9 | 3.64e9 (47.6%) | index_multi gather symbols: **0** (eltwise broadcast 39.3% + interior 32.3% = the fusion/kernel class) | 0% |

Readings:

- **radon_pp is the single largest unexploited math-side target in the suite.**
  Its gradient is essentially nothing BUT the loop complex (90%), because the
  model has 390 parameters and one N=12,573 scalar-lpdf loop. Notable mechanism:
  the loop's `target +=` form (propto=false) calls libm `log(sigma)` once per
  ELEMENT — 13.6% of the whole gradient — which a primitive computes once (the
  value is deterministic, so per-element reuse is bit-identical as long as the
  per-term addition schedule is kept). radon_pp is also the worst
  math-attributable E/S cell in W-109 (0.90x, MM2 grad spend), so this is the
  rare primitive that hits the ESS/s headline table directly.
- **bym2's ICAR line is the direct W-108 template application**: it is
  EXPRESSION form today (`dot_self(subtract(rvalue(phi, index_multi(node1)),
  rvalue(phi, index_multi(node2))))`) — the same matcher class stanc3#7 already
  exercises, no loop problem. Caveat for expectations: bym2's G is only 27.8% of
  program total (sampler-side linear algebra over 1,921 params + output
  formatting dominate), so the model-level wall effect is bounded; the upstream
  story rests on the ICAR/CAR disease-mapping class, not on this instance.
- **lsat confirms the boundary**: the admission test is about GATHERS, not
  eltwise cost — lsat pays 39% broadcast eltwise plumbing that no gathered
  primitive can touch (W-48 measured that class at ~0 win).

## 4. The campaign (ranked, one family per increment pair)

Method per family = the W-108 recipe verbatim: increment 1 = primitive + gates
(a) bitwise unit vs the composed stock reference USING the real
stan::model rvalue/index machinery (this gate caught a real OOB bug in W-108 —
keep it that strict), (b) hand-edited generated-model gate, draws md5 under the
W-29 protocol, (c) callgrind attribution vs the ALL-LAYERS reference with the
interior held constant, (d) untouched-control ctest + new TU; increment 2 =
stanc3 emission with negative controls + byte-identical no-op-elsewhere.
Pre-register each increment in WORKLOG before any code.

1. **normal_lpdf_gathered (radon_pp + radon_var)** — the headline. Two design
   forks, both resolvable at gate (a):
   - The models are LOOP form, so the bit-identity target is the SCALAR
     `normal_lpdf<false>(y_n, mu_n, sigma)` op order per element with
     sequential lp accumulation (0+t and in-order sums make the loop vs
     one-call accumulation provably equivalent IF each term is computed with
     identical operations — the unit gate settles it empirically). Use a plain
     in-order accumulation, not Eigen redux.
   - The stanc3 matcher needs a second matcher CLASS: the stereotyped
     likelihood loop (`for n: mu[n] = <gather tree over n>; target += <lpdf>(
     y[n] | mu[n], sigma>)` with mu loop-local and element-wise). W-108's
     expression matcher does not apply; the loop matcher is the new work.
   Signatures: `normal_lpdf_gathered<propto>(y, alpha, ii, sigma)` (radon_pp)
   and the `alpha[ii] + x .* beta[ii]` eta shape (radon_var) — overload or
   sibling per the math#14 naming decision.
   Pre-registerable expectation band from W-111: **−60..−85% G on radon_pp**
   (90% complex share; primitive keeps ~10–20 Ir/elem interior + scatter).
2. **ICAR dot_self_gathered (bym2)** — `dot_self_gathered(phi, node1, node2)`
   or a quadratic-form primitive; expression matcher (existing class); reverse
   = per-edge ± scatter. Replicate stock subtract/dot_self reduction order.
   Band: **−25..−40% G**. Class story (spatial/CAR models) carries the upstream
   interest.
3. **pcm/ordered_logistic gathered (gate model: gpcm_latent_reg_irt)** — the
   polytomous IRT class; loop form with per-observation cutpoint vector; the
   hardest interior (LSE over categories) but scatter still diagonal per
   observation. Requires bringing gpcm into a gated bench set (non-CORE today).
4. **Additive multi-gather bernoulli_logit (gate model: election88_full)** —
   extends the LANDED primitive's eta space (2PL bilinear → sum of gathered
   vectors + data terms); math#14 follow-up overloads + a generalized matcher.
5. **Register-only (no primitive until a gating model exists):**
   poisson_log_gathered, neg_binomial_2_log_gathered, categorical_logit_gathered,
   bernoulli(non-logit)_gathered. Design the signatures in the registry so the
   pass is ready, but no code without a model to gate it.

**stanc3 registry design** (replacing the single hardcoded pass): one suite
pass, table-driven — each entry = (lpdf name, matcher [expression-tree |
stereotyped-loop], eta-shape spec, primitive call + signature, negative
controls, include). W-108's `gather_bernoulli_logit` becomes entry 1; the
normal family adds the loop matcher class; ICAR adds a non-lpdf head
(dot_self). One pass, N primitives — and the negative-control gates stay
per-entry.

## 5. Answer to question 1 (why a new function, not a mutation)

Recorded with the PRs and summarized here for the ledger:

- **The contract is different, not better.** Stock `bernoulli_logit_lpmf(y, eta)`
  takes an already-assembled var expression; by the time it runs, the gathers
  and eltwise ops have already executed and the index information no longer
  exists. The primitive's whole mechanism — computing eta in double space from
  the coefficient vectors and doing reverse as one scatter-add through the
  index arrays — requires the indices AT the signature. "Changing the existing
  one" means changing its signature, which breaks every existing caller
  (all stanc-generated code for non-gathered etas, hand-written uses, the test
  suite).
- **Precedent.** stan-math's own `_glm` suffix family is exactly this pattern —
  a specialized sibling that takes the linear predictor structurally while the
  plain function stays untouched. Same for `_log` variants
  (bernoulli_logit vs bernoulli). Stan's API stability contract is additive.
- **Reviewability + zero behavior change.** math#14 adds exactly two files;
  existing callers cannot be affected; the control test passes 22/22 untouched;
  the bit-identity gates (draws md5 digit-for-digit) are only statable because
  the old path still exists to reproduce.
- **The emission composes safely** for the same reason: stanc3#7 rewrites only
  the matched pattern and regenerates everything else byte-identically —
  impossible to promise if stock semantics had moved.
- **Open refinement (flagged, not re-litigated):** the gathered form could be
  an OVERLOAD of the same name (argument count disambiguates; the Stan
  signature tables have no conflict). The gates are name-agnostic; this is a
  naming-preference call for the user/maintainers, worth one line in the PR
  drafts if asked.

## 6. Protocol + machine

W-111 pre-registration in WORKLOG precedes every number above (expectations
were registered BEFORE the runs; all four bands were overrun upward —
disclosed here). Machine: 4 sequential callgrind runs, ≤1 core each, nice 19,
load ~1.2 throughout; no wall claims anywhere (Ir is deterministic).
