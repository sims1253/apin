# W-32 — eigh-reuse ceiling on kronecker_gp: measured numbers for the upstream proposal

Date: 2026-08-22. Pre-registration: WORKLOG.md W-32. Mission: W-29 atlas
candidate #1 claimed kronecker_gp's gradient spends 39.3% of whole-program Ir
in reverse-mode `eigenvectors_sym`/`eigenvalues_sym<var>` because the model
calls BOTH primitives on the SAME two matrices — measure the ceiling an
"one decomposition instead of two" fix would buy, so the upstream proposal has
numbers. Measurement only; prototype lives in `scratch/w32/` and `harness/w32/`.

**Headline: the fix already exists upstream — `eigendecompose_sym` (stan-math
5.3.0 + stanc3 2.39 language support). Rewriting the model to use it is
BIT-IDENTICAL in gradients and draws, and saves 19.4% of gradient
instructions, 18.4% of total program Ir, and ~14% of gradient wall time on
this model. The gap is discoverability/codegen: stanc3 does not fuse the
natural `eigenvectors_sym(A)` + `eigenvalues_sym(A)` pair.**

## 1. Codegen findings (the 4-runs claim, from source)

Model (`models/kronecker_gp.stan`, tp block):

```stan
Q1 = eigenvectors_sym(Sigma1);   // n1 x n1 = 30 x 30
R1 = eigenvalues_sym(Sigma1);
Q2 = eigenvectors_sym(Lambda);   // n2 x n2 = 30 x 30
R2 = eigenvalues_sym(Lambda);
```

- stanc3 v2.39.0 emits these 4 calls verbatim in THREE instantiations of the
  generated hpp (double `log_prob_impl`, var `log_prob_impl` — the gradient
  path —, and `write_array_impl`): lines 427-437 / 548-558 / 696-706 of the
  generated `kronecker_gp.hpp` (see `scratch/w32/kronecker_gp_stock.hpp`).
- Each stan-math rev overload constructs its OWN full decomposition:
  `stan/math/rev/fun/eigenvectors_sym.hpp` line 34 and
  `stan/math/rev/fun/eigenvalues_sym.hpp` line 32 both run
  `Eigen::SelfAdjointEigenSolver<Eigen::MatrixXd> solver(arena_m.val())` in
  default (ComputeEigenvectors) mode. The rev eigenvalues overload cannot use
  the prim path's cheaper `EigenvaluesOnly` mode because its adjoint needs the
  eigenvectors. Net: **4 full decompositions per gradient where 2 suffice** —
  the atlas claim, now confirmed from source.
- Callgrind (below) reproduces W-29 exactly: `SelfAdjointEigenSolver::compute`
  inclusive 36.56%T (W-29: 36.6%), `eigenvectors_sym<var>` 20.41%T +
  `eigenvalues_sym<var>` 18.85%T = **39.26%T** (W-29: 39.3%).
- **The combined primitive already exists**: `stan/math/rev/fun/
  eigendecompose_sym.hpp` (stan-math 5.3.0, identical in cmdstan-2.39 and
  bridgestan-2.9 trees) runs ONE solver, ONE reverse callback computing both
  adjoints, returns `tuple(V, w)`. stanc3 v2.39 exposes it in the language
  (`tuple(matrix, vector) ed = eigendecompose_sym(A);` — verified by
  compiling a test model). Nothing fuses the two-call pattern into it.

## 2. The adjoint math (what a combined callback must compute)

For A = V diag(w) V^T (V orthogonal, distinct eigenvalues) with downstream
adjoints G_V (eigenvector matrix) and g_w (eigenvalue vector), first-order
perturbation theory gives dw_i = v_i^T dA v_i and
dv_i = sum_{j!=i} v_j (v_j^T dA v_i)/(w_i - w_j), hence

```
dA = V ( F . (V^T G_V) + diag(g_w) ) V^T,   F_ij = 1/(w_j - w_i), F_ii = 0
```

( . = elementwise; the two summands are exactly stan-math's separate
`eigenvectors_sym` and `eigenvalues_sym` callbacks). This matches
`eigendecompose_sym.hpp`'s implementation, which computes the two terms
separately and adds (`arena_m.adj() += value_adj + vector_adj`).

### Validation (route a, unit level)

`harness/w32/w32_unit.cpp`: phi(V,w) = sum(R . V) + c^T w on 5 random
well-conditioned 30x30 symmetric matrices (eigenvalue gaps >= ~0.5), comparing
dphi/dA from (1) stock two-call composition, (2) the W-32 hand helper
`w32_eigh` (fused inner F.(V^T G_V) + diag(g_w)), (3) central finite
differences along symmetric directions E_ij + E_ji:

```
trial 0: |g|max=1.716e+00  stock-vs-comb 6.661e-16 (rel 3.883e-16)
         sym(stock)-vs-fd 1.171e-07 (rel 6.828e-08)  sym(comb)-vs-fd 1.171e-07
(all 5 trials: fused == stock at 4-6e-16 rel; both == FD at 6-8e-8 rel)
```

Two documented subtleties: (a) stan's eigenvector adjoint V(F.(V^T G))V^T is
NOT symmetric (F is antisymmetric); its antisymmetric part is inert for the
admissible symmetric perturbations, so FD can only validate the symmetrized
adjoint (which it does, to FD truncation level). (b) FD along E_ij + E_ji
measures g_ij + g_ji.

## 3. Arms

| arm | what | where |
|---|---|---|
| stock | models/kronecker_gp.stan, fresh default-flag bridgestan build | scratch/w32/stock_build/ |
| lang | same model rewritten to call `eigendecompose_sym` (2 lines changed per matrix; pure Stan, compiles on stock cmdstan 2.39 / bridgestan 2.9 toolchain) | scratch/w32/lang_build/kronecker_gp.stan |
| hand | stanc hpp hand-patched to `stan::math::w32_eigh` (one solver + ONE callback with the FUSED inner matrix `F.(V^T G_V) + diag(g_w)`) | scratch/w32/patched_build/ (hpp patch: harness/w32/patch_hpp.py + harness/w32/w32_eigh.hpp) |

Build gotchas hit and worked around: bridgestan's Makefile deletes the .hpp
and .o as intermediates after a successful build — build the .hpp as an
EXPLICIT make target first, patch it, then request `.hpp + _model.so` together
(the .hpp is then not intermediate and survives; make does not re-run stanc
because the .stan is older). Build env: `env -u LD_LIBRARY_PATH`, -j2, default
CXXFLAGS only (W-27: -march=native miscompiles this model). Stock sanity: the
fresh stock build's (logp, grad) is BIT-IDENTICAL to bs_models/
model_kronecker_gp.so on all 100 random points (max rel 0.0).

## 4. Gate (a) — correctness

**lang vs stock: BIT-IDENTICAL.** logp AND full gradients identical to the
last bit on 100 random N(0,1) unconstrained points (worst rel-L2 exactly
0.0, cos exactly 1.0), and the entire 150-iteration callgrind sampler
trajectory is identical: draws.csv md5 `6b61df9f...` for BOTH arms, same
5094 gradient calls. Structural reason (why this is not luck): adjoints start
at zero and 0 + x is exact, so stock's two fired callbacks
`adj = (0 + T_val) + T_vec` and the combined callback
`adj = 0 + (T_val + T_vec)` produce the same bits when T_val, T_vec are
computed from the same doubles — which they are (same deterministic solver on
the same input, same expressions). **An upstream peephole can therefore
promise ZERO numerical change.**

**hand vs stock: same adjoint operator, last-ulp arithmetic differences.**
The fused inner computes V (F.(V^T G_V) + diag(g_w)) V^T instead of
V(F.(V^T G_V))V^T + V diag(g_w) V^T — mathematically equal (unit test:
4-6e-16), bitwise not. Observed on this model: logp bit-identical everywhere;
gradients differ by amplified rounding on a handful of components (below).

**The pre-registered <1e-9 max-rel bar is unattainable on this model for ANY
independent reimplementation — including one that only reassociates the
callback arithmetic.** Controls (matched points/components):

| sigma (cloud around posterior init) | stock-vs-hand | FD-vs-stock | FD-vs-hand |
|---|---|---|---|
| 0.0 (the init itself) | 1.26e-02 | 4.49e-02 | 4.49e-02 |
| 0.01 | 2.20e-01 | 3.85e-01 | 3.85e-01 |
| 0.1 | 1.68e-01 | 4.62e-01 | 4.62e-01 |
| 0.25 | 3.92e-01 | 3.67e-01 | 3.67e-01 |

FD-vs-stock == FD-vs-hand at every sigma to all digits: the two
implementations are indistinguishable to finite differences, and the REFERENCE
itself is only FD-verifiable to ~4e-2 at best (Richardson-stable). At random
N(0,1) points the stock AD deviates from Richardson FD by O(1). Root cause:
Sigma1 = var1*exp(xd*bw1) + 1e-5 jitter on n1=30 is an intrinsically
near-degenerate spectrum (the jitter floor creates a bottom eigenvalue
cluster); the eigenvector adjoint F_ij = 1/(w_j - w_i) is huge within the
cluster, so last-ulp input differences move individual gradient components by
O(1e-3..1e-1) ABSOLUTE. Vector-level, the hand arm stays equivalent to stock:
worst rel-L2 3.8e-3, worst cos-sim 0.9999929 over posterior-cloud points; at
the posterior init, per-component abs diffs: median 5.2e-8, p99 1.0e-2, max
8.9e-2 against |g| median 11.5 / max 392 (sigma1's component: EXACTLY equal).
This is recorded as a gate re-interpretation: correctness of the ADJOINT MATH
is proven at unit level (2 above); bit-level identity is delivered by the lang
arm. NOTE for W-27's record: this same intrinsic sensitivity explains how
-march=native's reassociation produced O(1) L-block "miscompile" signatures
here while passing elsewhere — on this model, ANY arithmetic reordering of
the eigen adjoint moves the L-block gradient at rounding scale (the native
failure remains a miscompile verdict for FMA contraction, but the model's
amplification is part of that story).

## 5. Gate (b) — per-call wall (matched serial driver, 100 identical posterior-cloud points, 3 interleaved repeats, medians; Python/bridgestan, taskset 0-3)

| arm | us/call (reps) | median | saving |
|---|---|---|---|
| stock | 393.2 / 393.0 / 392.5 | 393.0 | — |
| lang (official `eigendecompose_sym`) | 337.0 / 335.7 / 339.9 | 337.0 | **14.3%** |
| hand (fused-inner `w32_eigh`) | 324.1 / 324.5 / 324.1 | 324.1 | **17.5%** |

(An earlier 2-arm run reproduced the same ratio: 375.1 vs 309.6, -17.5%.)
Stock 393 us/call is consistent with W-29's native 366-369 us/call (different
driver). Wall tracks Ir imperfectly: the removed work (scalar QL tridiagonal
loop) is instruction-dense, the remaining GEMMs are latency-bound.

## 6. Gate (c) — callgrind Ir (W-29 protocol: seed 20260819, init
inits_w27/kronecker_gp/rep0/chain_0.txt, warmup 100 + samples 50,
--metric-window 50, valgrind 3.23 ~/vginstall, one job at a time, build_e27
stan_cli @ 0cb5b7b, NOT rebuilt)

| metric | stock | lang | hand |
|---|---|---|---|
| total program Ir T | 27.633e9 | **22.430e9 (-18.4%)** | 23.677e9 (-14.3%)* |
| logp_grad subtree G (bs_log_density_gradient incl.) | 26.771e9 (96.88%T) | 21.589e9 (96.25%T) | 22.829e9 (96.42%T) |
| gradient calls | 5094 | 5094 (identical) | 5615 (+10.2%)* |
| Ir / gradient | 5.254e6 | **4.238e6 (-19.4%)** | 4.066e6 (-22.6%)* |
| eigen fwd complex incl. (eigenvectors_sym+eigenvalues_sym / eigendecompose_sym / w32_eigh) | 10.850e9 (39.26%T) | 5.651e9 (25.19%T) | 6.102e9 (25.77%T) |
| Eigen computeFromTridiagonal_impl incl. | 5.537e9 (20.04%T) | **2.778e9 (12.38%T, -49.8%)** | 3.083e9 (13.02%T) |
| eigh reverse callbacks incl. | 3.359e9 (2.525 vec + 0.834 val) | 3.290e9 | 2.798e9 |
| draws.csv md5 | 6b61df9f... | 6b61df9f... (IDENTICAL) | 60ceb678... |

*the hand arm's rounding-different gradients changed the HMC trajectory
(more gradient calls), contaminating its TOTAL Ir; its per-gradient Ir is the
honest unit. The lang arm is the clean, shippable measurement.

The absolute saving (lang) = 5.199e9 Ir ~= exactly the eigenvalues_sym
inclusive share (5.209e9): the rewrite deletes one of the two redundant full
eigen complexes per gradient, halving the solver's dominant phase
(computeFromTridiagonal: -49.8%) while keeping both adjoints. The callbacks
cost roughly what they did (they must — the same adjoint GEMMs are required);
the hand arm shows a further ~15% callback saving is available by fusing the
inner matrix (one GEMM pair less) at the cost of bit-identity.

Sanity cross-checks: stock run reproduces W-29 to three digits on every
overlapping number (T 27.633 vs 27.63e9; G/T 96.88 vs 96.9; Ir/grad 5.254e6
vs 5,254,654; calls 5094; solver incl. 36.56 vs 36.6%T).

## 7. Upstream proposal sketch

1. **Zero-code, available today (model-level)**: models that need values AND
   vectors should use the existing language function
   `tuple(V, w) = eigendecompose_sym(A)` (stan-math 5.3.0 / stanc3 2.39 /
   CmdStan 2.39+). On kronecker_gp this is a 6-line diff, gives BIT-IDENTICAL
   draws, and cuts gradient Ir by 19.4% and wall by ~14%. Candidate for the
   Stan example-models repo and the docs ("performance tips" page currently
   does not mention it).
2. **stanc3 codegen peephole (the real fix)**: when the same matrix expression
   feeds both `eigenvectors_sym` and `eigenvalues_sym` (same-value CSE in the
   transformed-parameters block), emit one `eigendecompose_sym` call instead.
   The bit-identity argument (4 above) means this can be shipped with a
   "numerically identical" guarantee — a rare property for an optimization
   pass. Implementation shape: in stanc3's codegen, after the existing
   common-subexpression elimination, pattern-match the call pair; fall back to
   the two calls when the expressions are not provably identical.
3. **stan-math micro-polish (optional, +3% wall here)**:
   `eigendecompose_sym`'s callback could fuse the inner matrix
   (`F . (V^T G_V) + diag(g_w)` before the outer GEMMs, saving one GEMM pair
   and one adjoint accumulation) — measured 324.1 vs 337.0 us/call — but this
   LOSES bit-identity with the two-call form (rounding-level gradient
   changes); probably not worth it upstream given (2)'s guarantee.
4. **What this does NOT fix**: the eigenvector adjoint GEMM complex (~12-15%T
   here) and Eigen's unblocked scalar QL loop (computeFromTridiagonal,
   ~12.4%T after the fix) — W-29's deeper items (level-3 adjoint formulation,
   vectorized tridiagonal solver) remain the next candidates, now with a
   smaller base.

## 8. Reproduction

```
# builds (scratch/w32/{stock,patched,lang}_build/, per-variant dirs because
# compile_model silently reuses a cached .so next to the .stan):
env -u LD_LIBRARY_PATH BRIDGESTAN=~/.bridgestan/bridgestan-2.9.0 MAKEFLAGS=-j2 \
  uv run python -c "import bridgestan; \
  bridgestan.compile_model('scratch/w32/<arm>_build/kronecker_gp.stan')"
# patched arm: make the .hpp an explicit target first, then
#   python3 harness/w32/patch_hpp.py <hpp>; rm *.o *.so; make <hpp> <so>
# gates:
uv run python harness/w32/w32_gates.py      # parity + FD + timing (2-arm)
uv run python harness/w32/w32_lang_check.py # 3-arm parity + timing
# adjoint unit test (compile with the bridgestan stan-math include set, -O3,
# no -march=native; then run):
g++ -std=c++17 -O3 -pthread -D_REENTRANT \
  -I ~/.bridgestan/bridgestan-2.9.0/stan/src \
  -I ~/.bridgestan/bridgestan-2.9.0/stan/lib/rapidjson_1.1.0 \
  -I ~/.bridgestan/bridgestan-2.9.0/stan/lib/stan_math \
  -I ~/.bridgestan/bridgestan-2.9.0/stan/lib/stan_math/lib/eigen_3.4.0 \
  -I ~/.bridgestan/bridgestan-2.9.0/stan/lib/stan_math/lib/boost_1.87.0 \
  -I ~/.bridgestan/bridgestan-2.9.0/stan/lib/stan_math/lib/sundials_6.1.1/include \
  -I ~/.bridgestan/bridgestan-2.9.0/stan/lib/stan_math/lib/sundials_6.1.1/src/sundials \
  -I ~/.bridgestan/bridgestan-2.9.0/stan/lib/stan_math/lib/tbb_2020.3/include \
  -x c++ harness/w32/w32_unit.cpp -o /tmp/w32_unit \
  -L ~/.bridgestan/bridgestan-2.9.0/stan/lib/stan_math/lib/tbb \
  -Wl,-rpath,$HOME/.bridgestan/bridgestan-2.9.0/stan/lib/stan_math/lib/tbb -ltbb
# (w32_eigh.hpp must sit next to w32_unit.cpp or be -I'd)
env -u LD_LIBRARY_PATH OMP_NUM_THREADS=1 ~/vginstall/bin/valgrind --tool=callgrind \
  --callgrind-out-file=results/profile/w32/<arm>/callgrind.out \
  external/walnutpie/build_e27/examples/stan_cli scratch/w32/<arm>_build/kronecker_gp_model.so \
  data/kronecker_gp.json --seed 20260819 --init-file inits_w27/kronecker_gp/rep0/chain_0.txt \
  --warmup 100 --samples 50 --metric-window 50 --output results/profile/w32/<arm>/draws.csv
```

Raw: `results/profile/w32/{stock,patched,lang}/` (callgrind.out, cli.log,
ann_{exclusive,inclusive}.txt; draws.csv md5s in draws_md5.txt — draws
regenerable). Scripts: `harness/w32/`. Prototype builds kept local in
`scratch/w32/` (not in repo).
