# W-34 — elementwise var-mode plumbing ceiling on hier_2pl: measured numbers for the upstream proposal

Date: 2026-08-22. Pre-registration: WORKLOG.md W-34. Mission: W-29 atlas
candidate #2 — ONE program line of hier_2pl,
`y ~ bernoulli_logit(alpha[ii] .* (theta[jj] - beta[ii]))`, costs ~71% of a
7.75M-Ir gradient (~32%G plumbing + ~39%G likelihood math). Put a number on
what better codegen / an available language-level primitive could buy, as
evidence for the stanc3 / stan-math upstream push. Measurement only; models
in `harness/w34/`, builds in `scratch/w34/` (untracked), nothing pushed.

**Headline: the complete-grid data lets the whole likelihood line collapse
into ONE var-mode GEMM (the diamonds/`normal_id_glm` pattern). The rewrite
removes 28.2% of per-gradient instructions (7.745M → 5.561M Ir/grad) and
23–25% of per-call wall, with last-ulp gradient agreement (rel-L2 ≤ 2.3e-15)
and statistically identical sampling. The language-level GLM primitive
(`bernoulli_logit_glm_lpmf`) CANNOT express this model — the 2PL predictor
is bilinear in two parameter vectors, not a dense design times weights; the
upstream gap is expression fusion (stanc3) or a gathered/indexed-GLM
primitive (stan-math). The likelihood math itself (42→58% of the surviving
gradient, dominated by libm `log1p`) is already the efficient
partials-in-forward pattern and is the next ceiling.**

## 1. Codegen findings (from source, before any measurement)

Gradient-path instantiation of the stock generated hpp
(`scratch/w34/hier_2pl_stock.hpp`, stanc3 v2.39.0; identical text in the
double and write_array instantiations):

```cpp
lp_accum__.add(stan::math::bernoulli_logit_lpmf<propto__>(y,
                 stan::math::elt_multiply(
                   stan::model::rvalue(alpha, "alpha", stan::model::index_multi(ii)),
                   stan::math::subtract(
                     stan::model::rvalue(theta, "theta", stan::model::index_multi(jj)),
                     stan::model::rvalue(beta,  "beta",  stan::model::index_multi(ii))))));
```

- **Trigger shape**: any elementwise operator applied to *indexed var
  containers*. `rvalue(vector<var>, index_multi)` (stan/src/stan/model/
  indexing/rvalue.hpp:157) returns a lazy `make_holder(...)` =
  `Holder<IndexedView<var, int-map, SingleRange>>` — cheap by itself; the
  cost materializes when `subtract`/`elt_multiply` consume it: each eltwise
  op eagerly builds one vari + arena matrix entry + chainstack push + reverse
  callback PER ELEMENT (N = 19,200 per op, 2 ops, plus 3 gathers).
- **The lpmf is NOT the problem**: `bernoulli_logit_lpmf<var>` (stan-math
  5.3.0, prim/prob/bernoulli_logit_lpmf.hpp) already computes partials in
  the forward call via `partials_propagator` (one edge for the whole
  vector — the diamonds pattern). The plumbing is in the ARGUMENT
  EXPRESSION the compiler emits, not the distribution.
- **The anti-pattern done right** (atlas, diamonds): `normal_id_glm_lpdf`
  takes the linear predictor structurally (`x*beta + alpha`) and runs two
  GEMVs with partials-in-forward, reverse pass 0.4%G. The plain lpdfs take
  an already-assembled var vector and pay per-element assembly costs.
- **KEY data fact** (verified from `data/hier_2pl.json`): the response data
  is the COMPLETE J×I grid (I=32 items, J=600 persons, N=19,200=J·I),
  item-major (ii = 1..I each ×J, jj = 1..J tiled). The N-vector eta is
  exactly the column-major flatten of eta_mat[j,i] = alpha_i(theta_j −
  beta_i).

## 2. Arm A — language-level GLM: NO clean mapping exists (documented, not implemented)

`bernoulli_logit_glm_lpmf(y | x, alpha, beta)` computes
`bernoulli_logit_lpmf(y, alpha + x*beta)` with analytically simplified
gradients (prim/prob/bernoulli_logit_glm_lpmf.hpp, `require_matrix_t<T_x>`:
x is a DENSE matrix; alpha scalar or per-observation vector). The 2PL
predictor is

```
eta_n = alpha_{ii[n]} * theta_{jj[n]} − alpha_{ii[n]} * beta_{ii[n]}
```

— a PRODUCT of two per-observation-gathered parameter vectors
(alpha_i · theta_j): bilinear in (alpha, theta), not linear in any dense
coefficient vector. The only encodings are sparse designs materialized
dense: x_n = theta_{jj[n]}·e_{ii[n]} with beta = item params (N×I =
614,400 var matrix entries, 32× the current per-element work) or the
transpose role (N×J = 600×) — and x must itself be `var` (theta is a
parameter), so the GLM would additionally differentiate through the design
matrix it was supposed to exploit. **Verdict: bernoulli_logit_glm_lpmf is
structurally inapplicable to the 2PL/IRT class.** This inapplicability IS
an upstream finding: the GLM family covers only dense-linear-predictor
models; the most expensive elementwise-plumbing models (gathered/indexed
likelihoods: IRT, rating, sparse interactions) fall outside it.

## 3. Arm B — the GEMM formulation (codegen-ceiling arm)

`harness/w34/hier_2pl_gemm.stan` — everything identical to stock except the
likelihood line, computed as a model-block LOCAL matrix (not transformed
parameters — a tp would add 19,200 output columns to every draw):

```stan
matrix[J, I] eta = append_col(theta, rep_vector(-1.0, J))
                   * append_row(to_row_vector(alpha),
                                to_row_vector(alpha .* beta));
target += bernoulli_logit_lpmf(y | to_vector(eta));
```

`[theta, −1](J×2) · [alpha; alpha.*beta](2×I)` = theta·alpha′ − 1·(alpha.*beta)′
= alpha_i(theta_j − beta_i) per cell. stanc3 emits ONE
`stan::math::multiply(...)` (rev/fun/multiply.hpp: forward GEMM on `.val()`
doubles, single `reverse_pass_callback`, adjoints via two GEMMs), ZERO
`rvalue<index_multi>` gathers, ZERO N-level eltwise var ops (only the
600-element append_col and 32-element alpha.*beta remain); `to_vector` on a
var matrix is a zero-copy view. `target +=`-form generates propto=false vs
the sampling statement's propto=true — mathematically identical for
bernoulli_logit (no constant terms; `include_summand` only gates on T_prob),
verified numerically below. Note arm B exploits this dataset's complete
grid; designs with missing cells need the stock form (or eta as tp + gather).

Arm C (indexing/layout reorder) was pre-registered as optional and SKIPPED:
arm B removes the gathers entirely, mooting the gather-layout question.

Builds: `scratch/w34/{stock,armB}_build/` (copied .stan per variant — W-27
gotcha), default CXXFLAGS, `env -u LD_LIBRARY_PATH`, make -j2, bridgestan
2.9.0 (stan-math 5.3.0, stanc3 2.39). Instruments: read-only
`external/walnutpie/build_e27/examples/stan_cli` @0cb5b7b (gates a/b,
W-29 protocol) and `external/walnutpie/build/examples/stan_cli` @43b6435
(gate c; NOT rebuilt).

## 4. Gate (a) — correctness: PASS at last-ulp level (not bit-identical, as pre-registered)

100 random N(0,1) + 100 posterior-cloud (pf init + 0.25σ) unconstrained
points, deterministic rng (W-32 scheme):

| metric | random pts | posterior cloud |
|---|---|---|
| max rel logp | 3.19e-16 | 3.75e-16 |
| max ABS logp (|lp|≈2.3e4) | 7.28e-12 | — |
| worst grad rel-L2 | 1.77e-15 | 2.26e-15 |
| worst cosine | 1.0 (12 dp) | 1.0 (12 dp) |

The differences are exactly the pre-registered FP-reorder of eta
(theta·alpha − alpha·beta vs alpha·(theta−beta)) amplified through the
lpmf — vastly better than the W-32 precedent (kronecker_gp's
near-degenerate eigensystem amplified reordering to 1e-2; hier_2pl's
gradient is well-conditioned, so reordering stays at last-ulp). Richardson
FD spot-checks (3 points × 8 components spanning all parameter blocks):
stock and armB agree with FD identically — |AD−FD| equal to FD truncation
level (1e-10..8e-8) for both arms on every component.

## 5. Gate (b) — cost: −28.2% Ir/grad, −23..−25% wall

Per-call wall (Python/bridgestan driver, 100 identical posterior-cloud
points, 3 interleaved reps, medians): **stock 793.5 → armB 595.3 µs/call
(0.750x, −25.0%)** (reps: stock 970.3/793.5/791.4, armB 598.3/595.3/590.6).

Callgrind (W-29 protocol: valgrind 3.23, warmup 100 + samples 50, seed
20260819, pf init rep0/chain_0, one job at a time; raw:
`results/profile/w34/{stock,armB}/`):

| metric | stock | armB | delta |
|---|---|---|---|
| total program Ir T | 35.023e9 | 25.204e9 | **−28.04%** |
| logp_grad subtree G | 34.799e9 (99.36%T) | 24.980e9 (99.11%T) | −28.16% |
| gradient calls | 4,493 | 4,493 (identical) | — |
| **Ir / gradient** | **7,745,272** | **5,560,689** | **−28.17%** |
| native µs/call (warm/samp stanza) | 935.9 / 951.3 | 715.7 / 729.2 | −23.5% / −23.4% |

Stock reproduces W-29 digit-for-digit on every overlapping number (T
35.02e9; Ir/grad 7.745M; calls 4,493; every named symbol share to 0.1pp).
The identical 4,493 gradient calls means the last-ulp gradient differences
did not change the HMC trajectory length at these settings; the draws
differ only at rounding scale (md5 differs; 81.6% of CSV entries
bit-identical, max abs 2.0e-11, max rel 3.5e-9).

### Attribution — where the instructions went (exclusive Ir, % of T)

| complex | stock | armB |
|---|---|---|
| eltwise plumbing fwd (`subtract` 12.37% + `elt_multiply` 11.40%) | 8.325e9 (23.8%T) | **0** (only 32-elem alpha.*beta ≈ 0.05e9) |
| gathers (`rvalue<index_multi>` ×2) | 2.804e9 (8.0%T) | 0 |
| eltwise reverse callbacks + `update_adjoints` | 3.007e9 (8.6%T) | 0.714e9 (2.8%T)¹ |
| GEMM complex (`multiply` fwd 8.70% + callback 2.18% + append 0.24%) | — | 2.803e9 (11.1%T) |
| likelihood (`bernoulli_logit_lpmf` incl.) | 14.878e9 (42.5%T) | 14.709e9 (58.4%T)² |
| — libm `log1p` (inside lpmf) | 5.020e9 (14.3%T) | 5.020e9 (19.9%T)² |
| tape (`stack_alloc` + chainstack `emplace_back`) | 3.811e9 (10.9%T) | 2.033e9 (8.1%T) |

¹ the surviving update_adjoints/edge application is the lpmf partials edge
  and tp-block. ² likelihood share RISES because the denominator shrank;
  absolute Ir is unchanged (−1.1%).

Reading: the **entire eltwise+gather complex (40.4%G stock) was removed and
replaced by an 11.1%T GEMM complex** — net −9.8e9 Ir ≈ exactly the measured
T delta. The GEMM's own kernel children (Eigen gebp 1.61e9, three
general_matrix_matrix_product instantiations ≈2.15e9, packs ≈0.50e9;
inclusive, overlapping) are the new floor of the predictor assembly. The
likelihood math is untouched: `bernoulli_logit_lpmf` inclusive is
14.88e9 → 14.71e9 — already partials-in-forward; its interior (libm log1p
14.3%T, the Select/log1p-lambda sum redux 6.3%T stock, exp) is now the
single dominant block of the surviving gradient (58.4%T) and the next
ceiling, a libm/kernel question, not a plumbing one.

## 6. Gate (c) — sampler-level sanity

3 reps × 4 chains, warmup 1000 draws 1000, seeds 20260819+1000·rep+c, pf
inits `inits_w25/hier_2pl/`, `--metric-window 50`, 4 parallel single-chain
procs (W-30 par4 protocol), binary
`external/walnutpie/build/examples/stan_cli` @43b6435 read-only. Bit-identity
NOT expected (ulp-different gradients); the arms are independent
realizations of the same seed/init, so hier_2pl's documented single-realization
min-ESS instability (W-16: 20–420 swing on bit-identical code) applies.

| metric (median of 3 reps) | stock | armB |
|---|---|---|
| wall, 4 parallel chains (s) | 50.64 (49.79/50.64/50.84) | **37.40 (37.13/37.40/37.85) = 0.739x** |
| per-call logp_grad, sampling stanza (µs) | 1,207 (1199–1219) | 884 (878–887) = 0.732x |
| gradient calls, sampling phase | 75.6–76.3k | 75.6–75.9k (identical workload) |
| bulk-ESS min / tail-ESS min | 519.5 / 733.0 | 447.2 / 567.3 |
| rhat max | 1.0099 | 1.0118 |
| bulk ESS MEDIAN over all 804 params | 3,213 (3205/3213/3374) | 3,241 (3241/3221/3348) |
| bulk ESS p10 over all params | 1,016/970/1029 | 971/1008/1020 |

The stock arm reproduces the W-25/W-28 base arm exactly (per-rep bulk-min
548/502/520), validating protocol continuity. Reading:

- **Wall: −26.1% (0.739x) at IDENTICAL trajectory workload** (same gradient
  call counts; the sampler does the same math per draw, 27% cheaper per
  call). ESS-per-wall improves: bulk-min/s 10.26 → 11.96 (1.17x), tail-min/s
  14.5 → 15.2 (1.05x).
- **ESS distribution: indistinguishable** — median (≈3,200–3,400) and p10
  (≈1,000) bulk ESS over all 804 parameters agree within rep noise; rhat
  ≤1.016 both arms. The **ESS-min statistic alone is lower in armB
  (447 vs 520, 0.86x) — a MARGINAL MISS of the literal pre-registered
  'min within noise' gate, recorded as such**: the argmin parameter is a
  DIFFERENT marginal item param every rep (stock: xi2.32/xi2.21/xi2.17;
  armB: xi2.21/xi1.32/xi2.9), the count of sub-600 params wobbles
  (24/9/12 vs 9/6/18) — the min of 804 params with a marginal tail is
  exactly the statistic W-16 flagged as realization-unstable on this model.
  With gradients agreeing at 2.3e-15 rel-L2 and the whole-distribution
  statistics identical, this is characterized as realization noise of the
  min statistic, not evidence of degradation — but the honest statement is
  'min-ESS gate marginal (0.86x median), distribution gates clean'.

## 7. Upstream proposal sketch (the story the numbers support)

1. **Model-level, available today (complete-design IRT/rating models —
   hier_2pl, lsat_model class)**: assemble the linear predictor as ONE
   matrix product (append_col/append_row trick above), keep the same
   vectorized lpmf. 6-line diff, −28.2% Ir/grad, −23..25% per-call wall,
   last-ulp gradients, statistically identical draws. Candidate for Stan
   example-models / the performance-tips docs (same slot as W-32's
   `eigendecompose_sym` recommendation).
2. **stanc3 codegen — expression fusion (the general fix)**: the measured
   tax is per-element vari materialization for eltwise chains over indexed
   var containers (`elt_multiply(subtract(gather, gather), gather)` → 2
   varis + 2 callbacks + 2 arena matrices per element). A peephole that
   (a) CSEs repeated gathers (`alpha[ii]` was gathered once but the
   eltwise chain re-reads it) and (b) emits ONE fused vari for a pure
   eltwise chain — values computed in double space in a single pass, one
   callback applying the batched chain rule — has a measured ceiling of
   ~28% of total gradient Ir on this model class. Unlike W-32's
   eigendecompose peephole it CANNOT promise bit-identity in general
   (per-element arithmetic is reordered); here the drift is last-ulp
   (rel-L2 2.3e-15), and the sampler gates (6) show it is behaviorally
   inert.
3. **stan-math — close the GLM gap for gathered/bilinear predictors**: the
   GLM family (`*_glm_lpdf`, partials-in-forward, the pattern to copy)
   requires a DENSE design matrix and a linear predictor linear in beta.
   The expensive plumbing models (2PL IRT: eta = a[ii].*(t[jj]−b[ii]))
   are bilinear in (a,t) with index-gathered structure. Two primitive
   shapes: (i) a *gathered GLM* taking index vectors instead of a
   materialized design (`bernoulli_logit_glm_lpmf(y | theta, jj, alpha,
   beta, ii)`-style) computing eta + both partials in one forward pass —
   generalizes to Rasch/2PL/ordinal/rating models; (ii) general eltwise
   var-expression fusion at the stan-math level (compound vari for
   eltwise chains), which helps every model, not just likelihood lines.
4. **What this does NOT fix**: the likelihood interior (lpmf inclusive
   58.4%T after the fix; `log1p` alone 19.9%T) — vectorized libm /
   polynomial-rational approximations of the stable log1p(exp(−|x|)) branch
   are the next lever, and the tape/arena fixed cost (8.1%T) remains the
   SoA-arena item from W-29 candidate #4.

## 8. Reproduction

```
# builds (per-variant dirs — compile_model caches .so next to .stan):
env -u LD_LIBRARY_PATH BRIDGESTAN=$HOME/.bridgestan/bridgestan-2.9.0 MAKEFLAGS=-j2 \
  uv run python -c "import bridgestan; \
  bridgestan.compile_model('scratch/w34/<arm>_build/hier_2pl.stan')"
# gate (a)+(b) wall:
env -u LD_LIBRARY_PATH uv run python harness/w34/w34_gatea.py
env -u LD_LIBRARY_PATH taskset -c 0-3 uv run python harness/w34/w34_gateb_timing.py
# gate (b) callgrind (one job at a time) + parse:
env -u LD_LIBRARY_PATH uv run python harness/w34/w34_callgrind.py run stock armB
env -u LD_LIBRARY_PATH uv run python harness/w34/w34_callgrind.py parse
# gate (c):
env -u LD_LIBRARY_PATH uv run python harness/w34/w34_gatec.py run analyze
```

Raw: `results/profile/w34/{stock,armB}/` (callgrind.out, ann_*,
cli.log, draws.csv), `results/w34_{ess,wall}.json`, `runs/w34/`.
Scripts: `harness/w34/`. Builds kept local in `scratch/w34/` (untracked).
