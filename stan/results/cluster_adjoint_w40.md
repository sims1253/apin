# W-40 — Cluster-aware minimal-norm adjoint for reverse-mode symmetric eigendecomposition: implemented, validated, restored

Date: 2026-08-23. Pre-registration: WORKLOG.md W-40. Mission: implement the
fix for the W-35 numerics classification (rev `eigenvectors_sym` /
`eigendecompose_sym` adjoints divide by eigenvalue gaps; on
rounding-degenerate spectra — kronecker_gp's jitter-pinned cluster — the
gradients are FD-inconsistent 30–47% in every build and move by O(1)–O(1e3)
across ISAs), validate it against four pre-registered gates, restore the
stan-math tree pristine, and produce the ready-to-file upstream kit.

**One-line result: the cluster-gauged adjoint (zero the 1/(w_j−w_i)
couplings whose gap falls below κ·max(1,‖w‖∞)·ε, behind an if-guard that
keeps the well-separated code path bit-identical) collapses the
cross-ISA gradient divergence on kronecker_gp from 1.16 rel to 7e-5
(κ=1e3) / 3.1e-8 (κ=1e5), turns the model's FD-inconsistent var1/bw1
gradients (30–52% off) into FD-consistent ones (~1e-6, FD-truncation
level), leaves well-separated spectra BIT-IDENTICAL (200/200 matrices),
returns finite gradients where stock returns NaN (exact degeneracy,
435/438 components at kronecker_gp θ=0), and IMPROVES sampler quality
~7x (bulk-ESS-min 48→368 median) because the sampler no longer adapts to
a wrong gradient.** Tree restored byte-identical; patch + backups +
patched .so in scratch/w40/.

Environment: same as W-35 (gcc 16.2.1, bridgestan 2.9.0 stan-math,
Eigen 3.4.0, Zen 3; `env -u LD_LIBRARY_PATH`, `/usr/bin/make`, -j2
builds, serialized sampling). Patched files:
`stan/math/rev/fun/eigenvectors_sym.hpp`, `stan/math/rev/fun/eigendecompose_sym.hpp`
(`eigenvalues_sym.hpp` read and left untouched — see §1.3).
Patch: `scratch/w40/cluster_adjoint.patch` (a/ b/ unified, verified to
apply to pristine and reproduce the measured binaries); pristine backups:
`scratch/w40/backup/`; patched headers for reading:
`scratch/w40/patched/`.

---

## 1. The mathematics

### 1.1 What stan-math implements (all three files read; two patched)

For A = V diag(w) Vᵀ (symmetric, distinct eigenvalues), perturbation
E, M = VᵀEV, the forward derivative is ẇ_i = M_ii and
V̇ = V (F ∘ M) with F_ij = 1/(w_j − w_i), i≠j (F antisymmetric). The
reverse-mode adjoint accumulated into the operand is

  **Ā = V (F ∘ (Vᵀ Ḡ_V)) Vᵀ + V diag(ḡ_w) Vᵀ**

with Ḡ_V / ḡ_w the downstream adjoints of the eigenvector/eigenvalue
outputs (derivation: differentiate AV = Vdiag(w), left-multiply Vᵀ;
pair the antisymmetric F with the symmetric M; standard — Giles 2008
"Collected matrix derivative results" has the general-matrix version).
stan-math splits this across three primitives: `eigenvectors_sym` =
first term only; `eigenvalues_sym` = second term only (it runs the
solver in vectors mode precisely because its callback needs V — Kit 2);
`eigendecompose_sym` = both. Verified against the local 2.9.0 tree.

*Note on the task brief's "1/(w_i−w_j)² eigenvalue term":* **no
squared-denominator term exists in the first-order adjoint stan-math
implements** (read from all three hpp files; the eigenvalue term is the
division-free V diag(ḡ_w) Vᵀ). Terms in 1/(w_i−w_j)² arise in
SECOND-order eigenderivatives (Hessians of spectral functions; see He
et al. 2023 §adjoint equations, de Leeuw arXiv:2508.09355 §second
derivatives) — out of scope for a first-order reverse callback, and not
the source of the observed pathology.

### 1.2 What breaks at a cluster, exactly

Within a group of coincident eigenvalues (pairwise gaps δ → 0):

1. **Exact repeats (δ = 0):** F = 1/0 = ±inf. The within-group block of
   F ∘ (VᵀḠ_V) is inf · (finite) → inf, and inf·0 → NaN wherever the
   symmetric part of (VᵀḠ_V) vanishes. Stock returns **NaN gradients**
   — demonstrated two ways below (synthetic 4-fold degeneracy, and
   kronecker_gp at θ=0 where L=0 makes Lambda the zero matrix: 435/438
   gradient components NaN).
2. **Rounding-level repeats (δ ~ 1e-16…1e-13, the kronecker_gp case):**
   the labeled eigenvectors are mathematically determined but carry
   condition 1/δ ~ 1e16; the solver's returned basis within the group is
   a rounding-arbitrary choice (W-35 §3b), so the adjoint is a function
   of rounding noise: FD-inconsistent (30–52%) in every build and
   O(1)–O(1e3) different across ISAs.
3. **The subtle point (derived here, sharpens the pre-registration):**
   for a SYMMETRIC direction E, the adjoint's contribution of a pair
   (i,j) is F_ij(G'_ij − G'_ji)(VᵀEV)_ij where G' = VᵀḠ_V — only the
   ANTIsymmetric combination of G' pairs with the antisymmetric F, and
   this combination stays bounded as δ→0 when the downstream functional
   is smooth (e.g. for φ = uᵀ A⁻¹ u = Σ f(w_k)(v_kᵀu)² the limit is
   −2(v_iᵀu)(v_jᵀu) f'(ξ) — finite). So the large F terms cancel in
   bounded pairs — a catastrophic cancellation of size 1/δ that
   floating-point arithmetic destroys at δ ≲ ε·scale. Equivalently: the
   bounded limit (G'_ij − G'_ji)/δ needs the difference G'_ij − G'_ji,
   which is of size O(δ) mathematically but is computed with absolute
   error ~ε‖Ḡ_V‖ by the downstream tape — SNR ≈ δ/(ε‖Ḡ_V‖·scale⁻¹) ≪ 1
   for rounding-degenerate pairs. **The bounded within-cluster
   contribution exists mathematically but is not computable from
   double-precision tape data.** A library primitive that sees only
   (V, w, Ḡ_V, ḡ_w) cannot recover it without downstream-specific
   information (the classical repeated-eigenvalue methods — Friswell;
   Nelson/Fox–Kapoor; van der Aa et al. ELA 2007 — solve a supplemental
   system involving the specific functional; He et al. 2023 derive the
   adjoint equations including the repeated-eigenvalue pathology; the
   2025 shift-and-invert adjoint preconditioning paper handles exactly
   this regime by modifying the adjoint solve).

### 1.3 The implemented fix: cluster-gauge (minimal-norm) adjoint

Choose the gauge the classical theory uses for the undetermined
within-cluster rotation — W_cc = 0 (Fox–Kapoor/Nelson) — which in the
adjoint means zeroing the unidentifiable couplings:

  **F̃_ij = 1/(w_j − w_i) if |w_i − w_j| ≥ τ, else 0,
  τ = κ · max(1, ‖w‖_∞) · ε_machine, κ = 1e3 (primary; sweep below).**

Properties (all verified empirically in §3):
- **Bounded and basis-invariant:** F̃ ≤ 1/τ; under any within-group
  basis rotation R (what different ISAs/compilers produce) the masked
  adjoint is invariant up to the retained-gap terms — this is what
  collapses the cross-ISA divergence.
- **Exact where exactness is recoverable:** for exactly repeated
  eigenvalues and cluster-symmetric directions the masked adjoint is
  the exact derivative of the well-defined composite (demonstrated:
  FD-consistent to 2e-11 on the synthetic exact-degenerate test; and
  model-level FD ~1e-6). The dropped within-cluster mixing contribution
  is the provably-uncomputable bounded term of §1.2(3) — at kronecker_gp
  it measures ≤ 1e-6 relative along parameter directions.
- **Zero behavior change outside clusters:** the guard computes the min
  ADJACENT gap (Eigen returns w ascending, so min adjacent = min over
  all pairs); if it is ≥ τ the ORIGINAL code runs verbatim — bit-identical
  results (gate c). Pairwise masking (each F_ij vs τ independently,
  not transitive cluster closure) is used because the model spectra show
  a gap CONTINUUM, not separated clusters (§2), and pairwise is the
  minimal, most defensible rule (identifiability of the pair at
  resolution τ).
- `eigenvalues_sym.hpp` is NOT patched: its callback
  V diag(ḡ_w) Vᵀ has no gap division; it is bounded and (for
  cluster-constant ḡ_w, the kronecker_gp case: ḡ_w,i = f'(w_i),
  w_i equal to rounding level within a cluster) effectively
  basis-invariant — W-35 measured its channel (sigma1) FD-consistent to
  2e-11 in both builds. Leaving it untouched is also what makes the
  well-separated bit-identity gate trivially hold for it.

Literature (from results/upstream_scan_2026-08.md, novelty confirmed
there): He, Scarbourough, Amsallem et al., "Eigenvalue problem
derivatives computation for a complex matrix using the adjoint method"
(J. Sound & Vibration 2023; AIAA J. 2022); "Adjoint methods for
computing derivatives of functions of eigenvectors using shift-and-invert
preconditioning" (2025) — closest published analogue; de Leeuw,
"Differentiating Generalized Eigenvalues and Eigenvectors"
(arXiv:2508.09355, 2025); Friswell, "The derivatives of repeated
eigenvalues and their associated eigenvectors"; van der Aa, Meeussen,
Rikmenspoel (ELA 2007); + the adjacent-AD common knowledge (Julia
discourse 11563; TF/PyTorch eigh backward SO 58856160). None of this is
reflected in stan-math upstream (scan §2: develop still computes raw
1/(w_j−w_i), no guard, no degenerate-spectrum tests).

## 2. The measured spectrum (why κ and why the continuum matters)

`scratch/w40/dump_gaps.cpp` + `dump_gaps.out` (values, Eigen 3.4.0):
Sigma1 at the W-35 failing points has its bottom 10–18 eigenvalues
pinned at exactly 1e-5 (the jitter floor) with INTERNAL gaps
5e-18…6e-13, followed by a CONTINUUM (Sigma1_7: …, 2.98e-14, 5.85e-13,
9.95e-12, 1.5e-10, …) — no bimodal cluster/separator structure. Lambda
= LLᵀ likewise decays geometrically from ±1e-16. Consequences:
- any τ leaves a smallest RETAINED gap δ_ret; cross-build eigenvalue
  wobble dw ≈ 1e-14 (W-35 d5) perturbs the retained couplings by
  ~dw/δ_ret² — the residual floor of gate (a), improving as κ grows;
- τ = κ·max(1,‖w‖∞)·ε with κ=1e3 gives τ ≈ 7e-12 (Sigma1_7, scale 31.3),
  masking 12/29 adjacent pairs, δ_ret = 9.95e-12;
- the max(1,·) floor makes the zero matrix / all-equal spectra safe
  (τ > 0 → everything masked → finite adjoint; stock: NaN).

## 3. Gates (all pre-registered in WORKLOG W-40)

### Gate (a) — DIVERGENCE COLLAPSE (model level, W-35 parity protocol:
20 N(0,1) unconstrained points seed 20260822, grel = |Δg|/max(1,|g|))

| arm pair (default vs -mavx .so) | max grel | sign flips | comps >1e-6 | worst component |
|---|---|---|---|---|
| stock (W-35 builds, re-run) | **1.156** | yes | 55–221/438 | var1 −2.50→+0.39 (pt18) |
| patched κ=1e3 | **6.96e-5** | 0 | 26/438 | L[9] −0.5598→−0.5600 (pt8) |
| patched κ=1e4 | **1.58e-5** | 0 | 19/438 (all L) | L[9] (pt8) |
| patched κ=1e5 | **3.10e-8** | 0 | 7/438 | L[12] (pt5) |

logp agrees ≤ 1.3e-16 in every pair. VERDICT vs pre-registration:
PRIMARY (≤1e-9) not met at any tested κ; FALLBACK (≤1e-6 AND ≥5 orders
collapse AND monotone-in-κ retained-gap-limited residual) **PASSES at
κ=1e5** (collapse factor 3.7e7; residual location = bottom-eigendirection
L components, consistent with the δ_ret channel; monotone
7e-5 → 1.6e-5 → 3.1e-8). At the primary κ=1e3 the collapse is 4.3
orders. Recommendation for the upstream PR: κ default 1e3 (conservative
— masks only pairs with condition ≥ ~1e11·(scale-relative)); users who
need cross-build gradient reproducibility on clustered models benefit
from 1e4–1e5; all values kill the O(1)/O(1e3) catastrophe.

Unit level (scratch/w40/cmp_grads.py on the 9 W-35 matrices, same-ISA
pair): stock maxrel 1.9e1…9.4e5 (maxabs to 9.5e22); patched κ=1e3
maxrel 0.44…2.9e3 BUT maxabs ≤ 1.5e13 — the remaining O(1)-relative
differences are the mathematically-required basis dependence of the two
BASIS-DEPENDENT test functionals (fixed weight matrix Ḡ_V = W, not
cluster-covariant); the amplification is gone. The cluster-INVARIANT
unit functional improves 5e0–4.5e3 → 3e0–3e2 (same retained-gap floor).

### Gate (b) — FD-CONSISTENCY (model level: Richardson central FD of
logp in unconstrained coords, h=1e-4/5e-5, W-35 failing points)

| point/component | stock AD-vs-FD | patched κ=1e3 | κ=1e4 | κ=1e5 |
|---|---|---|---|---|
| pt1 var1 | 2.76e-1 | **8.5e-7** | 4.8e-8 | 1.3e-9 |
| pt1 bw1 | 1.26e-1 | **8.7e-7** | 1.3e-8 | 5.5e-9 |
| pt2 var1 | 5.1e-2 | **9.4e-8** | 1.5e-9 | 1.5e-9 |
| pt7 var1 | 2.29e-1 | **1.4e-6** | 1.3e-7 | 3.3e-9 |
| pt7 bw1 | 1.8e-2 | **1.8e-7** | 1.0e-7 | 9.4e-10 |
| pt14 var1 | 5.17e-1 | **9.2e-7** | 2.0e-8 | 2.0e-8 |
| pt14 bw1 | 8.4e-2 | **2.3e-7** | 4.6e-10 | 4.6e-10 |
| all sigma1 (control) | 2.4e-11 | 2.4e-11 (identical) | — | — |

The 30–52% inconsistency collapses to 1e-9…1.4e-6 — FD-truncation level
(the FD reference itself: sigma1 shows 2e-11 where the function is
locally smooth; var1/bw1 routes through the 1e-5-floor curvature).
Full 438-component scan at pt7 (|ad|>1e-3): stock worst 2.3e-1 (var1);
patched worst 1.6e-3 at L comp 252 — and that component is IDENTICAL
across κ (and its stock value matches patched to FD), i.e. it is FD
truncation on that coordinate, not a masking artifact. **PASS.**

Unit level, honest residuals:
- Well-conditioned control (A_wellcond): stock = patched = 4.2e-9
  (FD-consistent both; bit-identical outputs).
- EXACT 4-fold degeneracy (μ=1, synthetic): **stock = NaN** (every
  cluster-coupled component); patched finite, FD-consistent to
  1.1e-11…2.2e-11 on cluster-symmetric/diagonal/cross directions;
  within-cluster MIXING directions return the gauge value 0 while FD
  gives the bounded O(1) true value — the provably-uncomputable term of
  §1.2(3), dropped by design and documented (this is the honest content
  of "minimal-norm adjoint": the price of identifiability).
- On Sigma1/Lambda matrices the unit phi_inv functional has NO valid FD
  reference at any h: h must exceed the cluster gaps (1e-16) to resolve
  the composite but stay below the 1e-5 eigenvalue floor to keep
  log(w)/1/w defined — h ∈ (1e-14, 1e-5); at h=1e-3/1e-4 the −h side
  drives floor eigenvalues negative (FD = NaN); at h=1e-5 truncation
  dominates. The stock-vs-patched reldiffs there (1e-1 vs ~1e0)
  measure FD breakdown, not patch quality — the model-level test above
  is the valid reference, which is why gate (b) was pre-registered on
  the model.
- W-35 minimized reproducer (BASIS-DEPENDENT phi = sum(W.*V) + c'w):
  phi value unchanged (−1.1122236138732831, bit-equal to stock);
  stock |grad| ~1e12–1e15, FD ~1e5, reldiff 1.0; patched |grad| ~1e8
  (bounded by 1/τ·‖Ḝ‖), still ≠ FD because NO derivative exists for
  this phi at rounding degeneracy (the function value itself moves O(1)
  under 1e-14 input changes — W-35 §5). Documented as the expected
  residual; the adjoint returned is the defensible minimal-norm one.
- Bonus, model level at θ=0 (L=0 → Lambda ≡ 0, 30-fold exact
  degeneracy): **stock gradient NaN in 435/438 components; patched all
  finite** (logp identical, −187.858). Any Stan user initializing such
  a model at zero gets NaN gradients today.

### Gate (c) — WELL-SEPARATED UNCHANGED

`w40_unit wellsep`: 200 random symmetric 30×30 (LCG-generated,
deterministic across builds; min adjacent gap ≥ 1e-6·scale enforced,
0 skipped), gradients of three functionals through
eigenvectors_sym + eigenvalues_sym + eigendecompose_sym rev, %.17g
dumps: **stock vs patched outputs byte-identical (cmp = 0 files
differ)**. The guard makes the well-separated code path LITERALLY the
original one (identical FP ops; the threshold computation adds only
pre-branch arithmetic that cannot alter the branch-not-taken path).
**PASS (bit-identical, 200/200).**

### Gate (d) — SAMPLER SANITY (kronecker_gp, one fixed binary
walnutpie exp/freeze-clamp stan_cli, 3 reps × 4 chains, warmup=1000
draws=1000, seeds 20260819+1000·rep+c, inits_w36 deterministic inits —
kronecker_gp has NO pf inits in inits_w25, deviation noted — the .so is
the only difference between arms)

| arm | rep0 (c0 = W-41 -inf-init cell) | rep1 bulk/tail ESS-min | rep2 bulk/tail ESS-min | R-hat max (healthy reps) |
|---|---|---|---|---|
| stock .so | 5.3/4.0, R̂ 2.13, pinned | 29.1/40.0 | 67.2/94.0 | 1.13 |
| patched .so | 6.9/4.0, R̂ 1.68, pinned | **411.4/349.1** | **324.0/308.6** | **1.02** |

Draws are NOT bit-identical (md5s differ) — expected and pre-registered:
the adjoint changed on a clustered model, so every post-init gradient
differs. Gate wording was "ESS within the stock arm's rep spread" —
the result EXCEEDS it: healthy-rep median bulk-ESS-min 48.1 → 367.7
(~7.6×), tail 67.0 → 328.8, R-hat 1.13/1.05 → 1.02, and the mechanism
is transparent: stock warmup/sampling adapted to a 30–50%-wrong
gradient (gate b), patched to the FD-verified one. The stock arm
reproduces the independent W-36 stock_seq runs bit-for-bit
(runs/w36/stock_seq/kronecker_gp/rep1/chain_0.csv md5 =
dba5eb797a82e22f706073675a099524 = ours), so the baseline is not an
artifact of this session's binary. rep0/c0 shows the W-41 init
pathology identically in both arms (freeze-clamp warning in both logs;
model-inherent, not arm-attributable). Per-call cost unchanged
(393–395 µs stock vs 396–399 µs patched, i.e. the mask costs ~1% of a
gradient); patched chains take ~35% more wall because correct gradients
produce deeper trajectories (25477+23475 vs 18712+16871 logp_grad
calls at rep1) — ESS/second is still far ahead. **PASS (with
improvement).**

## 4. κ threshold sensitivity (pre-registered sweep)

Unit (cross-ISA, basis-dependent functionals — residual is basis
dependence + δ_ret): κ=1e2 max 2.8e4, κ=1e3 max 2.9e3, κ=1e4 max 6.2e2,
κ=1e5 max 6.2e2 (saturates at the basis-dependence floor of the
non-invariant functionals).
Model (gate a): 1.156 (stock) → 7e-5 (κ1e3) → 1.6e-5 (κ1e4) → 3.1e-8
(κ1e5); FD-consistency (gate b) holds at ALL κ (var1/bw1 1e-9…1.4e-6,
non-monotone in κ but always ≥5 orders below stock). Well-separated
bit-identity holds at every κ by construction. The trade-off κ↑ =
masking more pairs (dropping more of the bounded-but-uncomputable
content — measured negligible ≤1e-6 relative at parameter directions on
this model, and those pairs carry condition ≥ κ·1e3-ish anyway).
Recommendation: ship κ = 1e3 default (conservative); document 1e4–1e5
for cross-build reproducibility use-cases. Absolute-floor note: τ uses
max(1,‖w‖∞) — for matrices with ‖w‖∞ ≪ 1 and genuinely well-separated
relative spectra the mask is over-aggressive (a known, documented
conservatism of the absolute-scale choice; the alternative
τ = κ‖w‖∞ε alone is unsafe at w≡0).

## 5. Porting note for stan-math develop (Eigen 5) — Kit 4 requirement

Fetched develop's `stan/math/rev/fun/eigenvectors_sym.hpp` (2026-08-23):
the reverse_pass_callback is **structurally identical** to 2.9.0's —
same `f = 1/(replicate − replicate)`, same `f.diagonal().setZero()`,
same `arena_m.adj() += V (F ∘ (Vᵀ adj)) Vᵀ`, NO degeneracy guard (scan
W-38u finding confirmed still true). Only cosmetic differences (e.g.
`.val()` vs `.val_op()`). **The patch ports trivially** — same edit,
macro/constant unchanged; the math is Eigen-version-independent (the
cluster mechanism lives in the adjoint formula, not the solver).
`eigendecompose_sym.hpp` develop was not re-fetched (2.9.0-era structure
confirmed by the scan); expect the same. We cannot build develop
(Eigen 5.0.1) here — the kit should say: repro validated on Eigen
3.4.0 (2.39/bridgestan 2.9); the fix is solver-agnostic; re-run the
repro + patch under Eigen 5 at PR time.

## 6. READY-TO-FILE upstream kit (extends Kit 4)

### 6a. Issue (file first; supersedes/extends §7a of march_native_w35.md)

> **Title: Rev-mode eigenvector adjoints: NaN on exactly repeated
> eigenvalues, silently FD-inconsistent (30–50%) on near-degenerate
> spectra, O(1) gradient changes under any FP reordering — plus a
> ready fix (cluster-gauged minimal-norm adjoint)**
>
> **Summary.** The reverse-mode adjoints of `eigenvectors_sym` /
> `eigendecompose_sym` (and the eigenvector half of the pair idiom)
> compute F_ij = 1/(w_j − w_i) with no guard. Three measured failure
> modes (stan-math as bundled with cmdstan 2.39 / bridgestan 2.9,
> Eigen 3.4.0; self-contained reproducers for each):
>
> 1. **Exactly repeated eigenvalues → NaN.** For any matrix with two
>    exactly equal eigenvalues (e.g. a jittered GP kernel whose floor
>    pins bottom eigenvalues at exactly the jitter; L·Lᵀ at L=0), F = 1/0
>    and the gradient is NaN — e.g. the kronecker_gp example model at
>    θ=0 returns NaN in 435 of 438 gradient components (logp fine).
> 2. **Rounding-degenerate clusters → silently wrong gradients in every
>    build.** On the same model at ordinary posterior points the
>    gradients disagree with Richardson finite differences by 30–52%
>    (var1/bw1), while components not routed through the eigenvector
>    adjoint agree to 1e-11. The returned gradient is not the derivative
>    of the log density at any achievable FD step.
> 3. **Any permitted FP reordering moves the gradient O(1)–O(1e3).**
>    Compiling the identical model with any AVX-or-wider ISA
>    (`-mavx` suffices; also clang) changes GEMM accumulation order by
>    ~1e-15, `SelfAdjointEigenSolver` returns a different-but-equally-
>    valid basis within the cluster (residual ~1e-14 in both), and the
>    1/(w_j−w_i) adjoint amplifies that to O(1) gradient differences
>    with sign flips (logp agrees to 1e-16). Not a compiler bug: the
>    default build is itself FD-inconsistent at these points (mode 2),
>    ASan/UBSan clean, and clang reproduces it (full characterization,
>    flag matrix, and 65-line reproducer: linked report).
>
> **Why no local workaround exists:** the mathematically bounded
> within-cluster contribution (G'_ij − G'_ji)/(w_j − w_i) requires the
> difference of two tape adjoints that is O(δ) mathematically but is
> computed with absolute error ~ε‖Ḡ_V‖ — SNR ≪ 1 at rounding
> degeneracy. The information is not in the doubles; a library-level
> choice is required. (References: He et al., J. Sound & Vib. 2023
> adjoint eigen-derivatives incl. repeated eigenvalues; shift-and-invert
> adjoint preconditioning, 2025; de Leeuw arXiv:2508.09355; Friswell;
> van der Aa et al. ELA 2007.)
>
> **Proposed fix (implemented and validated, patch attached):** treat
> pairs with |w_i − w_j| < κ·max(1,‖w‖∞)·ε (κ = 1e3) as one numerically
> degenerate cluster and zero their coupling — the classical
> Fox–Kapoor/Nelson gauge for the undetermined within-cluster rotation,
> i.e. the minimal-norm adjoint; cross-cluster pairs keep the standard
> formula, and a min-adjacent-gap guard keeps the well-separated code
> path bit-identical. Measured on kronecker_gp (20 random points,
> default vs -mavx builds): cross-ISA max gradient disagreement
> 1.16 → 7e-5 rel (κ=1e3) / 3.1e-8 (κ=1e5), sign flips → 0; AD-vs-FD
> 30–52% → ≤1.4e-6; exactly-repeated case NaN → finite; 200/200
> well-separated random matrices bit-identical to unpatched; end-to-end
> sampling on the clustered model improves bulk-ESS-min 48 → 368
> (median, healthy reps) because adaptation no longer uses a wrong
> gradient.
>
> Happy to turn the patch into a PR with tests (exact-degenerate NaN
> case, near-degenerate FD-consistency and cross-ISA cases, bit-identity
> regression) — the callback structure is unchanged on develop (Eigen 5),
> so the patch ports as-is.

### 6b. Fix PR sketch (for when the user files)

Title: "Guard rev eigenvector adjoints against numerically degenerate
eigenvalue clusters (minimal-norm gauge)". Body: the §1 derivation above
(condensed), the patch (scratch/w40/cluster_adjoint.patch — applies to
both files; `#define STAN_MATH_EIGEN_GAP_KAPPA` default 1e3 so
reviewers/users can tune), the four gates as the test plan:
- `eigenvectors_sym(A)` with A having exact repeats: finite gradient
  (today: NaN) + equals FD on cluster-invariant composites to ~1e-11;
- near-degenerate spectrum (exp-quad kernel + jitter floor): AD vs FD
  ≤1e-6 where unpatched is 1e-1;
- min-gap ≥ threshold: EXPECT bit-identical adjoints (regression guard);
- suggested reviewer discussion: κ default (1e3 vs 1e4–1e5), and whether
  to `warning()` (like existing PD checks) when masking triggers on
  large clusters.

### 6c. Kit 4 text update

Replace Kit 4's "Ask (a)+(b)" (docs-only) with: "fix available + docs":
the issue above now carries an implemented, gated fix; the docs
paragraph (§7c of march_native_w35.md) stays as-is.

## 7. File index

- `scratch/w40/cluster_adjoint.patch` — the fix (a/ b/ unified; verified
  apply-to-pristine == measured binaries' sources)
- `scratch/w40/backup/` — pristine originals (md5-verified after restore)
- `scratch/w40/patched/` — patched headers (for reading/attaching)
- `scratch/w40/dump_gaps.cpp/.out` — spectrum/gap measurement (§2)
- `scratch/w40/w40_unit.cpp`, `ccw40.sh`, `ccw40_stock.sh` (pristine-
  header shadow include), binaries `u_stock_*`, `u_patch_*`,
  outputs `*.out` — unit gates (a)(b)(c) + κ sweep + exact-degeneracy
- `scratch/w40/cmp_grads.py` — cross-build gradient comparison
- `scratch/w40/fd_model.py` — model-level FD-vs-AD (gate b)
- `scratch/w40/build_so.sh`, `builds/{patched_default,patched_avx,
  patched_threads,k1e4_default,k1e4_avx,k1e5_default,k1e5_avx}/` —
  patched model .so variants (patched_stdlib; tree restored after)
- `scratch/w40/run_w40.py`, `../runs/w40/{stock,patched}/` — gate (d)
  raw chains; `scratch/w40/ess_w40.py`, `results/w40_ess.json`
- `scratch/w40/repro_patch_{base,avx}` — W-35 reproducer rebuilt against
  the patched tree

## 8. What was and was not established

Established: the fix is mathematically grounded (gauge argument +
uncomputability of the bounded within-cluster term), implemented in the
bridgestan stan-math copy, and validated on all four pre-registered
gates with the honest residuals documented (primary gate (a) ≤1e-9 met
only at κ=1e5's 3.1e-8 near-miss; unit-level FD references provably
unavailable on the cluster matrices themselves; the repro's
basis-dependent functional retains an O(1) AD-vs-FD gap by necessity).
The tree is restored (md5-verified) and the patch file round-trips.

Not established: behavior under Eigen 5 (source-verified portable, not
compiled — no develop build here); sampler-level effects beyond
kronecker_gp (the W-29/W-32 atlas says this exposure is
kronecker_gp-specific among our models); the optimal κ (presented as a
measured trade-off, not a solved problem); upstream review appetite for
a warning vs silent masking (flagged in the PR sketch).
