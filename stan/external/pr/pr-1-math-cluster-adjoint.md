# Guard reverse-mode eigenvector adjoints against numerically degenerate eigenvalue clusters (minimal-norm gauge)

## Problem

### The adjoint being computed

For a real symmetric matrix with eigendecomposition `A = V diag(w) Vᵀ`
(distinct eigenvalues), the first-order perturbation response to a
symmetric perturbation `E`, with `M = VᵀEV`, is

```
ẇ_i  = M_ii
V̇    = V (F ∘ M),   F_ij = 1/(w_j − w_i)  (i ≠ j, F antisymmetric)
```

Pairing these with downstream adjoints `Ḡ_V` (of the eigenvector output)
and `ḡ_w` (of the eigenvalue output) gives the reverse-mode contribution
to the operand adjoint (standard result; see Giles 2008 for the general
matrix version):

```
Ā = V (F ∘ (Vᵀ Ḡ_V)) Vᵀ  +  V diag(ḡ_w) Vᵀ
```

stan-math splits this across three primitives: `eigenvectors_sym`
implements the first term, `eigenvalues_sym` the second, and
`eigendecompose_sym` both. The eigenvalue term has no gap division and is
unaffected by this PR. The problem is the `1/(w_j − w_i)` factor in the
eigenvector term: it is computed with no guard, and it is only the
derivative of anything when the eigenvalues are separated.

### Failure mode 1: exactly repeated eigenvalues → NaN

If two eigenvalues are exactly equal (easy to produce: a jittered GP kernel
whose floor pins bottom eigenvalues at exactly the jitter value; `L·Lᵀ` at
`L = 0`), then `F` contains `1/0 = ±inf`, and `inf · 0` appears as `NaN`
wherever the symmetric part of `VᵀḠ_V` vanishes. Concretely, the
`kronecker_gp`-class model (Kronecker-GP with `2×2 ⊗ 30×30` kernels)
initialized at zero parameters returns NaN in 435 of 438 gradient
components (log density finite). A user initializing such a model at zero
gets NaN gradients today.

### Failure mode 2: rounding-degenerate clusters → silently wrong gradients in every build

When the gap `δ = |w_i − w_j|` falls to rounding level (`1e-16 … 1e-13`),
the individual eigenvectors within the cluster are mathematically
determined but carry condition `1/δ ~ 1e16`: any two runs that differ by a
permitted floating-point reordering (e.g. compiling the identical model
with any AVX-or-wider SIMD ISA, which changes GEMM accumulation order by
~1e-15) get different but equally valid eigenbases (residual ~1e-14 in
both), and the `1/(w_j−w_i)` factor amplifies that basis difference to
O(1)–O(1e3) relative gradient changes, with sign flips. Decisively, the
default build's own gradients are Richardson-finite-difference
inconsistent by 30–52% at those points. There is no "correct"
reference that the reordered build deviates from, the adjoint is a function
of rounding noise. (This was initially suspected to be a gcc miscompile and
refuted: not `-O` level, not FMA contraction, not the vectorizer, ASan+UBSan
clean, clang reproduces it.)

### Why no local (caller-side) workaround exists

The mathematically bounded limit exists: for a symmetric direction `E`, the
contribution of a pair `(i, j)` involves `F_ij (G'_ij − G'_ji)` with
`G' = VᵀḠ_V`, only the antisymmetric combination of `G'` pairs with
the antisymmetric `F`, and `(G'_ij − G'_ji)/δ` stays finite as `δ → 0`
when the downstream functional is smooth. But that difference is `O(δ)`
mathematically while being computed with absolute error `~ε‖Ḡ_V‖` by the
upstream tape: SNR ≈ δ/(ε‖Ḡ_V‖) ≪ 1 at rounding degeneracy. The bounded
within-cluster contribution is not computable from double-precision tape
data, a library-level choice is required. (This is the classical
repeated-eigenvalue situation: Friswell; Nelson; Fox–Kapoor; van der Aa et
al. ELA 2007 solve supplemental systems that need downstream-specific
information a primitive does not have; He et al. 2023 derive the adjoint
equations including the repeated-eigenvalue pathology; the 2025
shift-and-invert adjoint paper handles exactly this regime by modifying the
adjoint solve.)

## Solution (derivation; the diff is one concrete instantiation)

### The gauge argument

Within a cluster the eigenbasis is undetermined up to an orthogonal
rotation `R`. The derivative of any *smooth* functional of `A` does not
depend on `R`, only the *representation* does. The classical theory
(Fox–Kapoor, Nelson) resolves the indeterminacy with the minimal-norm
gauge: the within-cluster block of the eigenvector sensitivity is set to
zero. In the adjoint this means: zero the coupling terms whose gap is
below the resolution at which eigenvalue pairs are identifiable, keep the
standard formula everywhere else:

```
F̃_ij = 1/(w_j − w_i)   if |w_i − w_j| ≥ τ
     = 0                otherwise
τ = κ · max(1, ‖w‖_∞) · ε_machine,  κ = 1e3 (default)
```

Properties, each verifiable by direct argument or test:

1. **Bounded:** `F̃ ≤ 1/τ`; the NaN and the O(1/ε) amplification disappear
   by construction, and the masked adjoint is invariant (up to retained-gap
   terms) under within-cluster basis rotation — which is what collapses the
   cross-build divergence.
2. **Exact where exactness is recoverable:** for exactly repeated
   eigenvalues and cluster-symmetric/diagonal/cross directions the masked
   adjoint is the exact derivative of the well-defined composite (verified
   FD-consistent to ~1e-11 on a synthetic 4-fold degeneracy). The dropped
   within-cluster mixing term is the provably-uncomputable term above; on
   the measured model it is ≤1e-6 relative along parameter directions.
3. **Zero behavior change outside clusters:** compute the minimum
   *adjacent* gap (Eigen returns `w` ascending, so min adjacent = min over
   all pairs); if it is ≥ τ, run the original code path verbatim,
   bit-identical results on well-separated spectra (verified on 200/200
   random matrices).

### Step-by-step implementation recipe (independent of our diff)

1. In the `reverse_pass_callback` of `eigenvectors_sym` (rev) and of
   `eigendecompose_sym` (rev), before building `F`:
   compute `tau = kappa * std::max(1.0, w.cwiseAbs().maxCoeff()) *
   std::numeric_limits<double>::epsilon()` with `kappa` from an
   overridable macro (`STAN_MATH_EIGEN_GAP_KAPPA`, default `1e3`).
2. `has_degenerate_gap = p > 1 && (w.tail(p-1) - w.head(p-1)).minCoeff() < tau`.
3. If false: the existing `F` construction and the existing adjoint
   expression, unchanged (this preserves bit-identity).
4. If true: build `F` as `(gaps.array().abs() >= tau).select(gaps.array().inverse(), Zero)`
   instead of `1/gaps` — i.e. pairwise masking (each pair vs τ
   independently, not transitive cluster closure; the measured model spectra
   show a gap continuum, and pairwise is the minimal, most defensible rule).
   Everything else in the callback is unchanged.
5. Do **not** touch `eigenvalues_sym`'s callback: `V diag(ḡ_w) Vᵀ` has no
   gap division and is effectively basis-invariant for cluster-constant
   `ḡ_w` (measured FD-consistent to 2e-11 in both builds).
6. Tests: (a) exact 4-fold repeated eigenvalue → all gradient components
   finite (stock: NaN), FD-consistent on cluster-symmetric/diagonal/cross
   directions, two-call vs `eigendecompose_sym` bit-identical; (b) the zero
   matrix; (c) a jitter-floor exp-quad kernel spectrum (guard fires, output
   finite and self-consistent); (d) well-separated matrices reproduce the
   textbook adjoint `V(F∘(VᵀG_V))Vᵀ + V diag(g_w) Vᵀ` to ≤1e-12 — this
   guards against the fix overreaching.

Deliberately left as discussion points:
the κ default (1e3 conservative vs 1e4–1e5 for cross-build gradient
reproducibility), and whether masking on large clusters should emit a
`warning()` analogous to the existing positive-definiteness checks.

## Evidence

Model-level numbers: `kronecker_gp`-class model (2 symmetric eigendecoms of
30×30 + 2×2 per gradient), gcc 16.2.1, Zen 3, stan-math as bundled with
cmdstan 2.39 / bridgestan 2.9 (Eigen 3.4.0) — the numbers marked (develop)
are unit tests on current develop (Eigen 5.0.1) at 46a3133.

**Cross-ISA gradient divergence** (20 random N(0,1) unconstrained points;
same source compiled default vs `-mavx`; grel = |Δg|/max(1,|g|)):

| arm | max grel | sign flips | components > 1e-6 |
|---|---|---|---|
| stock | **1.156** | yes | 55–221 / 438 |
| patched, κ = 1e3 | **6.96e-5** | 0 | 26 / 438 |
| patched, κ = 1e4 | 1.58e-5 | 0 | 19 / 438 |
| patched, κ = 1e5 | **3.1e-8** | 0 | 7 / 438 |

**AD vs Richardson finite differences** (model level, failing points,
h = 1e-4 / 5e-5; representative components):

| point/component | stock | patched (κ = 1e3) |
|---|---|---|
| pt1 var1 | 2.76e-1 | **8.5e-7** |
| pt1 bw1 | 1.26e-1 | 8.7e-7 |
| pt7 var1 | 2.29e-1 | 1.4e-6 |
| pt14 var1 | 5.17e-1 | 9.2e-7 |
| all sigma1 (control, not routed through the eigenvector adjoint) | 2.4e-11 | 2.4e-11 (identical) |

**Exact degeneracy:** stock NaN → patched finite (435/438 → 0 NaN);
synthetic 4-fold degeneracy: patched FD-consistent to 1.1e-11…2.2e-11 on
cluster-symmetric/diagonal/cross directions; within-cluster *mixing*
directions return the gauge value 0 while FD gives the bounded true value —
the provably-dropped term, documented.

**Well-separated spectra:** 200 random symmetric 30×30 (LCG-generated,
min adjacent gap ≥ 1e-6·scale): stock vs patched gradient dumps
**byte-identical (200/200)**.

**Sampler-level effect** (kronecker_gp, 3 reps × 4 chains, warmup 1000,
draws 1000, fixed deterministic inits, only the .so differs):

| arm | healthy-rep median bulk-ESS-min | R-hat max (healthy reps) |
|---|---|---|
| stock | 48.1 (29.1 / 67.2) | 1.13 |
| patched (κ = 1e3) | **367.7 (411.4 / 324.0)** | **1.02** |

Mechanism: stock warmup/sampling adapted to a 30–50%-wrong gradient (table
2); the patched arm's extra wall time (~35% more gradient calls) is deeper
trajectories from correct gradients — ESS/second is far ahead. Per-call
kernel cost of the guard: ~1% (393–399 µs/gradient both arms).

**(develop) Test status at 46a3133 (Eigen 5.0.1):** all existing tests of
the touched functions pass with the patch (`rev/fun/eigenvectors_sym_test`,
`rev/fun/eigenvalues_sym_test`, `prim/fun/eigendecompose_sym_test`, and the
three mix counterparts — the mix tests are the FD-reference ones). The new
test file: 4/4 PASS with the patch, 2/4 FAIL on stock with exactly the
NaN the first failure mode predicts.

## Validation protocol (to reproduce the evidence)

- Divergence: build the same model .so twice (default flags vs `-mavx`),
  evaluate logp+gradient at ≥20 seeded random N(0,1) unconstrained points,
  compare per-component `|Δg|/max(1,|g|)`. Stock exhibits modes 1–2; with
  the patch the same comparison collapses per the table. (Any FP-reordering
  build difference, not just `-mavx`, triggers mode 2 on clustered models.)
- FD consistency: central Richardson differences of logp in unconstrained
  coordinates at the same points, h = 1e-4 and 5e-5, compare to the AD
  gradient. The FD reference itself floors at ~1e-6 on coordinates routed
  through the 1e-5-floor curvature (visible on control components).
- Bit-identity: hash gradient dumps of the three rev primitives on ≥200
  seeded well-separated random symmetric matrices, stock vs patched.
- Unit reproducer for mode 1: `eigenvectors_sym(A)` with A built to have an
  exact 4-fold repeated eigenvalue (e.g. `I₄ ⊕ diag(rest)` rotated by a
  seeded orthogonal map) — the added test file does exactly this with
  integer-only LCG data so it is platform-deterministic.
- Cost: matched per-gradient call timing and callgrind instruction counts
  (medians of 3 interleaved reps).

## References

- M. Giles, "Collected matrix derivative results for matrix adjoint
  computations" (2008) — the general-matrix adjoint framework.
- He, Scarbourough, Amsallem et al., "Eigenvalue problem derivatives
  computation for a complex matrix using the adjoint method" (AIAA J.
  2022 / J. Sound & Vibration 2023) — adjoint eigen-derivatives including
  the repeated-eigenvalue pathology.
- "Adjoint methods for computing derivatives of functions of eigenvectors
  using shift-and-invert preconditioning" (2025) — closest published
  analogue of the degenerate-regime treatment.
- J. de Leeuw, "Differentiating Generalized Eigenvalues and Eigenvectors",
  arXiv:2508.09355 (2025).
- M. I. Friswell, "The derivatives of repeated eigenvalues and their
  associated eigenvectors"; R. L. Fox and M. P. Kapoor, "Rate of change of
  eigenvalues and eigenvectors" (1968); H. D. Nelson (1976) — the
  minimal-norm gauge for repeated eigenvalues.
- N. van der Aa, H. ter Morsche, R. Mattheij, "Computation of eigenvalue
  and eigenvector derivatives for a general complex matrix" (ELA 2007).
- Adjacent-AD common knowledge: Julia discourse #11563; TF/PyTorch `eigh`
  backward (SO 58856160) — same `1/(w_j−w_i)` structure, no degeneracy
  guard there either.
- **Major-framework precedent for the gauge choice**: JAX PR #36832
  (merged 2026-04) added an opt-in gauge-fixed eigenvector JVP for exactly
  this reason (degenerate eigenbases make the raw JVP arbitrary within the
  invariant subspace); see also arXiv:2411.14141 (minimal-norm SVD
  backward). To our knowledge no framework applies the fix in the reverse
  mode adjoint by default — stan-math's `var` path currently has no guard
  at all, which is the NaN/FD-inconsistency demonstrated above.
- stan-math #1803 (adjoint convention wart, open since 2020) is the closest
  prior in this repo; the 2017 discourse thread 7616 (bbbales2: "I dunno if
  the derivatives fall apart there or what") never became an issue.

Full evidence trail (four pre-registered gates, κ sweep, honest residual
analysis) is available on request or via the public benchmark repo
(https://github.com/sims1253/apin — `stan/results/` and `stan/WORKLOG.md`)
— happy to attach or paste any section.
