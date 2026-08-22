# W-29 — stan-math model-gradient hotspot atlas (upstream candidature evidence pack)

Date: 2026-08-22. Pre-registration: WORKLOG.md W-29. Mission: name exactly which
stan-math functions dominate `logp_grad` cost on our expensive models, so
upstream proposals (walnutpie or stan-math) can target them. Measurement only —
no sampler or math code was changed.

## 1. Method (reproducible)

- Binary: `external/walnutpie/build_e27/examples/stan_cli`, built at walnutpie
  commit `0cb5b7b` during W-27 (stable shared build; NOT rebuilt for W-29).
- Models: default BridgeStan 2.9.0 builds in `bs_models/` (default flags —
  W-27 showed they are already -O3-equivalent; -march=native miscompiles).
- Tool: valgrind 3.23.0 from `~/vginstall`, `--tool=callgrind`, Ir only
  (no cache simulation), one model at a time (single core, shared machine).
- Runs (fixed seed 20260819, fixed inits, `--metric-window 50`, 1 chain):

| model | warmup+samples | init | logp_grad calls | exception-truncated calls |
|---|---|---|---|---|
| hier_2pl | 100+50 | inits_w25/hier_2pl/rep0/chain_0.txt (pathfinder) | 4,493 | 69 (1.5%) |
| kronecker_gp | 100+50 | inits_w27/kronecker_gp/rep0/chain_0.txt | 5,094 | 138 (2.7%) |
| gp_regr | 50+50 | inits_w27/gp_regr/rep0/chain_0.txt (det. N(0,1)) | 577 | 0 |
| accel_gp | 50+50 | inits_w27/accel_gp/rep0/chain_0.txt (det. N(0,1)) | 3,102 | 0 |
| diamonds | 50+50 | inits_w27/diamonds/rep0/chain_0.txt | 3,102 | 0 |

  (gp_regr/accel_gp inits generated with the W-27 scheme:
  `random.Random('20260819-0').gauss(0,1)` per unconstrained dim.)

- Exact commands (what `harness/w29_callgrind.py` executes, per model):

```bash
env -u LD_LIBRARY_PATH OMP_NUM_THREADS=1 ~/vginstall/bin/valgrind --tool=callgrind \
  --callgrind-out-file=results/profile/w29/<m>/callgrind.out \
  external/walnutpie/build_e27/examples/stan_cli \
  bs_models/model_<m>.so data/<m>.json --seed 20260819 \
  --init-file <init file from table> --warmup <W> --samples 50 \
  --metric-window 50 --output results/profile/w29/<m>/draws.csv
env -u LD_LIBRARY_PATH ~/vginstall/bin/callgrind_annotate \
  results/profile/w29/<m>/callgrind.out                       # exclusive
env -u LD_LIBRARY_PATH ~/vginstall/bin/callgrind_annotate --inclusive=yes ...
env -u LD_LIBRARY_PATH ~/vginstall/bin/callgrind_annotate --tree=both ...
uv run python harness/analyze_w29.py    # -> results/profile/w29/w29_analysis.json
```

- Attribution rule: **logp_grad subtree G = inclusive Ir of
  `bs_log_density_gradient`** (the BridgeStan C entry the sampler calls once per
  gradient; contains forward pass + `grad()` reverse pass + arena recovery).
  Shared callees (libm, malloc) are attributed into G via `--tree=both`
  caller-edge costs from callers in the model `.so` excluding IO/bridge glue
  (rapidjson data read etc.). Raw dumps: `results/profile/w29/<m>/`.

## 2. Headline: where the program goes

| model | total Ir T | logp_grad G | G/T | fwd (log_prob_impl) | rev+glue (grad()) | Ir/grad | native us/call |
|---|---|---|---|---|---|---|---|
| hier_2pl | 35.02e9 | 34.80e9 | **99.4%** | 91.0%G | 9.0%G | 7,745,279 | 950/968 |
| kronecker_gp | 27.63e9 | 26.77e9 | **96.9%** | 71.0%G | 29.0%G | 5,254,654 | 366/369 |
| gp_regr | 47.4e6 | 38.7e6 | **81.6%** | 76.0%G | 24.0%G | 66,990 | 5.4/5.3 |
| accel_gp | 573.6e6 | 531.0e6 | **92.6%** | 78.6%G | 21.4%G | 171,186 | 14.0/13.7 |
| diamonds | 2.17e9 | 1.86e9 | **85.7%** | 99.6%G | 0.4%G | 599,583 | 36.3/34.7 |

(native us/call = warmup/sampling stanza of the identical native run,
`results/profile/w29/<m>/cli.log`.)

**Walnutpie-internal (non-logp_grad) overhead** — two honest cuts:

| model | inside sampler loop (S−G)/S | one-time + IO outside loop (T−S)/T |
|---|---|---|
| hier_2pl | **0.2%** | 0.4% |
| kronecker_gp | **0.5%** | 2.6% |
| gp_regr | **5.5%** | 13.7% (ld.so + data read + csv write dominate) |
| accel_gp | **1.0%** | 6.5% |
| diamonds | **0.2%** | 14.2% (rapidjson data read ~6.6%T + ld.so + csv) |

S = inclusive Ir of `run_walnuts` (the sampler loop in stan_cli). The
sampler-side ceiling is **0.2–5.5% of loop instructions** — confirms W-17g's
"logp_grad = 68–99.7% of sampling wall" at instruction level and re-confirms
the closure of the kernel/SIMD-polish direction. Drift vs ATLAS.md §1/§2:
old cmdstan-binary shares (eigen 69% diamonds etc.) are same-regime; the
bigger T−S numbers here are short-run one-time costs that amortize (ATLAS
already noted diamonds data-read 38% at 40 iters → ~1% at 1000).

Cross-check with ATLAS.md §4 (BridgeStan Ir/grad, 100+100): diamonds
652,455 → 599,583 here (−8%, different warmup fraction); same ballpark,
method consistent.

## 3. Per-model logp_grad-internal top functions (% of G)

### hier_2pl (IRT 2PL; the model line: `y ~ bernoulli_logit(alpha[ii] .* (theta[jj] - beta[ii]))`)

| %G | function (stan-math) | call path from logp_grad |
|---|---|---|
| 18.5 | `bernoulli_logit_lpmf<true, vector<int>, Matrix<var>>` (exclusive) | log_prob_impl → bernoulli_logit_lpmf |
| 14.4 | libm `log1p` | bernoulli_logit_lpmf → apply_scalar_unary rev lambda (stable log1p(exp(−|x|))) |
| 12.4 | `subtract<Holder<IndexedView<var>>>` | log_prob_impl → `theta[jj] − beta[ii]` elementwise on multi-indexed views |
| 11.5 | `elt_multiply<Holder<IndexedView<var>>>` | log_prob_impl → `alpha[ii] .* (...)` |
| 6.5 | `stack_alloc::alloc` | every eltwise op's arena_matrix |
| 6.3 | `apply_scalar_unary`(inv_logit) reverse lambda | reverse pass (grad) |
| 5.4 | `stan::model::rvalue<..., index_multi>` | log_prob_impl → alpha[ii]/theta[jj]/beta[ii] gathers |
| 4.5 | chainstack `vector<vari_base*>::emplace_back` | every vari constructed |
| 3.4+3.2 | `elt_multiply`/`subtract` reverse callbacks | grad() |
| 2.7 | second `rvalue<index_multi>` instantiation | log_prob_impl |
| 2.0 | `update_adjoints<arena_matrix<var>>` | grad() adjoint application |

Buckets: eltwise var-ops 23.9%, lpdf 18.7%, reverse sweep 15.0%, libm(log1p)
14.4%, tape build 12.6%, index glue (rvalue) 8.1%. Reading: **≈32% of the
gradient is expression plumbing** (forward eltwise var-ops 23.9% + rvalue
gathers 8.1%) and **≈39% is likelihood math** (bernoulli_logit 18.5% +
log1p 14.4% + inv_logit reverse lambda 6.3%); both are per-element var-mode
costs — ATLAS suspect #1 now at function level. (I=32 items, J=600 persons,
N=19,200 observations.)

### kronecker_gp (Kronecker GP, n1=n2=30; tp block computes `eigenvectors_sym`+`eigenvalues_sym` of Sigma1 AND Lambda per gradient)

| %G | function | call path |
|---|---|---|
| 20.6 | `Eigen::internal::computeFromTridiagonal_impl` | SelfAdjointEigenSolver::compute ← stan::math `eigenvectors_sym<var>`/`eigenvalues_sym<var>` |
| 19.0 | `Eigen::internal::gebp_kernel` (GEMM core) | gemm ← SelfAdjointEigenSolver Q-apply, eigenvectors_sym reverse callback, kron_mvprod |
| 4.3 | `Eigen::internal::tridiagonalization_inplace` | SelfAdjointEigenSolver::compute |
| 4.2 | `Eigen::internal::outer_product_selector_run` | gemm path |
| 4.1 | `stack_alloc::alloc` | var matrices per gradient |
| 3.4 | `Eigen::internal::selfadjoint_matrix_vector_product` | selfadjoint products |
| 3.2 | chainstack `emplace_back` | tape |
| 2.2 | `Eigen::internal::lhs_process_one_packet` | gebp |
| 1.8 | `Eigen::internal::general_matrix_vector_product` | gemv |

Inclusive anchors (% of T=27.63e9): `eigenvectors_sym<var>` **20.4%T**,
`eigenvalues_sym<var>` **18.9%T**, `Eigen::SelfAdjointEigenSolver::compute`
**36.6%T**, eigenvectors_sym reverse callback **9.1%T**. The model calls
values AND vectors on each of two matrices → **4 full double-mode
eigendecompositions per gradient where 2 would do** (eigenvalues_sym internally
runs the complete solver). Buckets: eigen_linalg 35.1%, eigen_sym 25.9%,
tape 8.2%. This is ATLAS's "transformed params 71%" wall block, now resolved
to named stan-math functions. NOTE: this eigendecomposition complex sits
immediately downstream of the `lkj_corr_cholesky` → `Lambda` block whose
gradient -march=native miscompiled (W-27) — same tape region, different cause.

### gp_regr (GP regression, N=11 observations)

| %G | function | call path |
|---|---|---|
| 17.0 | `cholesky_decompose<var>` reverse lambda (`unblocked_cholesky_lambda`) | grad() ← rev callback |
| 9.8 | `cholesky_decompose<var>` forward | log_prob_impl → multi_normal_cholesky_lpdf → cholesky_decompose |
| 8.9 | libm `pow` | `gp_exp_quad_cov` kernel distances |
| 7.1 | var/arena ctor + var_value glue | tape |
| 5.9 | `multi_normal_cholesky_lpdf<var>` | log_prob_impl |
| 5.3 | `add<var>` (K + jitter) | log_prob_impl |
| 4.5 | `Eigen::internal::triangular_solve_matrix` | multi_normal_cholesky_lpdf solves |
| 3.8 | chainstack `emplace_back` | tape |
| 3.1+3.0 | libm `exp`, `general_matrix_vector_product` | kernel / solves |

Buckets: cholesky complex 24.4%, reverse sweep 23.3%, libm 12.9%, eigen
12.1%. **The reverse pass of cholesky costs 1.7× its forward pass.**

### accel_gp (small GP with Student-t priors)

| %G | function | call path |
|---|---|---|
| 9.9+8.9 | two `Eigen::internal::general_matrix_vector_product` instantiations | `multiply<var>` (X·z) in latent-GP mean |
| 8.0 | `stack_alloc::alloc` | tape |
| 7.2 | chainstack `emplace_back` | tape |
| 5.3 | `Eigen::internal::plog_impl_double` | `normal_lpdf`/lgamma path (Student-t priors) |
| 5.2 | `normal_lpdf<var>` | log_prob_impl |
| 4.6+4.6+3.5 | `add<var>`, `multiply<var>`, second `add<var>` | latent-GP line |
| 4.2 | libm `exp` | kernel |

Buckets: eigen 19.1%, tape 16.9%, eltwise 14.3%, lpdf 12.8%, rev 6.4%,
alloc 2.5% — the "small model" regime: fixed tape/alloc overhead looms large
per-call (consistent with ATLAS accel 12.2% memcpy+alloc).

### diamonds (GLM, N=5000, K=25)

| %G | function | call path |
|---|---|---|
| 40.4 | `Eigen::internal::general_matrix_vector_product` #1 | log_prob_impl → `normal_id_glm_lpdf<var>` forward |
| 40.1 | `Eigen::internal::general_matrix_vector_product` #2 | normal_id_glm_lpdf partials (gradient GEMV) |
| 9.5 | `normal_id_glm_lpdf<var>` (other exclusive work) | log_prob_impl |
| 6.7 | libc helper (0x1b2800) via normal_id_glm_lpdf | memcpy-ish |

Buckets: eigen_linalg **82.4%**, lpdf 9.7%. Exactly two GEMVs carry the whole
model; reverse pass is 0.4%G (GLM partials are computed in the forward call —
the efficient pattern other distributions could copy). ATLAS micro: double
mode already ≈50% AVX2 FMA peak.

## 4. Ranked upstream candidates (stan-math), with WHY and fix shape

1. **Reverse-mode symmetric eigendecomposition (`eigenvectors_sym` /
   `eigenvalues_sym<var>)`** — kronecker_gp: 39.3% of whole-program Ir
   (eigenvectors_sym 20.4%T + eigenvalues_sym 18.9%T inclusive), reverse
   callback 9.1%T, on 30×30 matrices.
   WHY: (a) API — the model needs values AND vectors; each function runs a
   complete `SelfAdjointEigenSolver`, so 2× the work is redundant (4 solver
   runs/gradient where 2 suffice); (b) reverse pass is GEMM-heavy adjoint
   propagation through the full eigenvector matrix; (c) Eigen's
   `computeFromTridiagonal_impl` (20.6%G exclusive) is an unblocked scalar QL
   loop. FIX: algorithmic first (combined `eigh`-style primitive returning
   both, or reuse of the factorization across the two calls — an
   upstream-visible API gap), then vectorization of the tridiagonal solver,
   then level-3 formulation of the eigenvector adjoint.

2. **Elementwise var-mode tax on indexed likelihood expressions** — hier_2pl:
   ≈32%G plumbing (`subtract`/`elt_multiply` forward ops 23.9%,
   `rvalue<index_multi>` gathers 8.1%) + ≈39%G likelihood math
   (`bernoulli_logit_lpmf` 18.5%, libm `log1p` 14.4%, inv_logit reverse
   lambda 6.3%) + ≈13%G tape machinery. One Stan program line ≈ 71% of a
   7.7M-Ir gradient.
   WHY: every elementwise op materializes an arena_matrix + vari + reverse
   callback per element (ATLAS micro: 4.3× tax, 8.2 ns/var-elem-op; now
   localized). FIX: algorithmic — fused/batched partials for eltwise chains,
   fewer var nodes per element (expression fusion), SoA adjoint application
   (`update_adjoints` pointer chase). The rvalue/index_multi share is pure
   stanc3 codegen (gather cost) — fixable in the generated C++ too.

3. **`cholesky_decompose<var>` reverse pass + `gp_exp_quad_cov` kernel** —
   gp_regr: reverse lambda 17.0%G vs forward 9.8%G; kernel `pow` 8.9%G.
   WHY: the adjoint sweep is a column-wise unblocked lambda (O(n³) but
   level-2); kernel distances call libm `pow` where a multiply would do.
   FIX: algorithmic — blocked/level-3 reverse cholesky (upstream math PR);
   trivial — replace `pow(d,2)` with `d*d` in the kernel inner loop.

4. **Tape/arena construction fixed cost (all var-mode models)** — 12.6%G
   (hier_2pl), 16.9%G (accel_gp), 8.2%G (kronecker), 4.9%G (gp_regr):
   `stack_alloc` + chainstack `emplace_back` + arena var ctors.
   WHY: per-node cost of reverse-mode autodiff itself, invisible per function
   but the second-largest bucket overall. FIX: allocation/representation —
   this is the SoA-arena / vari-pool redesign lever from ATLAS #1; not a
   single-function patch.

5. **`normal_id_glm_lpdf<var>` GEMV pair (GLM class)** — diamonds: 80.5%G in
   two GEMV instantiations. WHY: forward + partial GEMV on X (5000×25) —
   already near the vectorization ceiling (double mode ≈50% FMA peak).
   FIX: lowest priority — possible fusion of the two GEMVs / layout tuning;
   the pattern to REPLICATE elsewhere (partials inside the lpdf call keep the
   reverse pass at 0.4%G).

Rejected/non-issues re-confirmed at function level: validity checks
(`bounded<...>::check` 1.9%G on hier_2pl, ~0 elsewhere); DRAM (Ir-based here;
ATLAS already showed LL misses ≈0).

## 5. Walnutpie-internal overhead summary

Inside the sampler loop, non-gradient instructions are **0.2% (hier_2pl,
diamonds), 0.5% (kronecker_gp), 1.0% (accel_gp), 5.5% (gp_regr — the
smallest per-gradient model, 67 kIr/grad)**. The sampler-side optimization
ceiling on this model class is therefore ≈0–5%: any material wall-time win
must come from the model gradient (stan-math / stanc3), consistent with
W-17g/W-21/W-27. Outside the loop, one-time costs (dynamic linking, rapidjson
data read, csv write) are 0.4–14.2% of short-run totals and amortize at
production iteration counts.

## 6. File index

- `results/profile/w29/<model>/callgrind.out` — raw callgrind dumps
- `results/profile/w29/<model>/ann_{exclusive,inclusive,tree}.txt` — annotate text
- `results/profile/w29/<model>/cli.log` — native run (call counts, per-call µs, exception counts)
- `results/profile/w29/w29_analysis.json` — parsed tables (this document's source)
- `harness/w29_callgrind.py` — runner; `harness/analyze_w29.py` — parser/analyzer
- Known caveats: 1.5%/2.7% exception-truncated gradient calls (hier_2pl/
  kronecker_gp) slightly undercount reverse-pass shares; `--tree=both` blocks
  exist only above callgrind's auto threshold (top functions verified by hand
  from ann_inclusive/ann_tree greps where needed).
