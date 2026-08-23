# W-35 — `-march=native` gradient divergence on kronecker_gp: minimized, classified — NOT a compiler bug

Date: 2026-08-22/23. Pre-registration: WORKLOG.md W-35. Mission: minimize and
classify the W-27 finding (bridgestan-built kronecker_gp `.so` with
`-O3 -march=native -mtune=native` gives gradients wrong at 0.006–1.7 rel with
sign flips on 99/99 points while logp matches to 1e-16), producing a reportable
reproducer for the upstream pack (external/upstream_candidates.md candidate 6).

**VERDICT (one line): the divergence is real and reproducible, but it is NOT a
gcc miscompile and NOT stan-math UB. It is Eigen's explicitly-vectorized AVX
(256-bit) GEMM kernel changing FP summation order — a permitted, rounding-level
(1e-15) difference — which flips `SelfAdjointEigenSolver` to a different but
equally valid eigenbasis inside the model's intrinsically near-degenerate
eigenvalue clusters; stan-math's reverse-mode eigenvector adjoint
(F_ij = 1/(w_j−w_i)) then amplifies the basis difference to O(1)–O(1e3) in the
gradient. The DEFAULT build's own gradients are equally finite-difference
inconsistent at those points — the model's gradient through
`eigenvectors_sym` of a rounding-degenerate spectrum is numerically
ill-conditioned in ANY build. W-27's "miscompile" wording is corrected; the
operational conclusion (never build Stan models with `-march=native`) stands.**

Environment: gcc 16.2.1 (Arch, 2026-08-10 build), clang 22.1.8, AMD Ryzen 5
PRO 5650U (Zen 3), bridgestan 2.9.0 (stan-math 5.3.0-era tree, Eigen 3.4.0),
`env -u LD_LIBRARY_PATH`, `/usr/bin/make -j2`. Env note: this machine's gcc
driver (AppImage-provided) required symlinking cc1plus/cc1/collect2 into
`~/lib/gcc/x86_64-pc-linux-gnu/16/` before it could compile anything.

## 1. Reproduction (gate i PASS)

Fresh builds via `bridgestan.compile_model` on a copied `.stan` per variant
(`scratch/w35/<variant>_build/`; the W-27 cache gotcha), gradient parity on 20
random N(0,1) unconstrained points, seed 20260822 (harness:
`scratch/w35/parity.py`):

- default vs `-O3`: **bit-identical** (logp and grad, 0.0 diff) — control.
- default vs `-O3 -march=native -mtune=native`: **20/20 points wrong**,
  max rel grad 6e-3 … 2.36, 55–221 of 438 components > 1e-6 rel, sign flips on
  5/20 points (9 components), logp ≤ 4.5e-16. Worst components are in the L block AND
  var1/bw1 (the Sigma1 block) — e.g. pt7 var1 +2.90 → +7.55, pt18 var1
  −2.50 → +0.063 (sign flip). W-27's signature confirmed.

## 2. Flag matrix — the trigger is the ISA, nothing else (gate ii PASS)

Model-level (full `.so` rebuild per row, same 20 points) and repro-level
(`§5` snippet, phi + eigenvector column identity):

| flags (all on top of gcc -O2/-O3) | diverges? | note |
|---|---|---|
| `-O3` (≡ bridgestan default) | NO (bit-identical) | |
| `-O2 -march=native -mtune=native` | YES, identical signature to -O3 native | -O level irrelevant |
| `-march=native -ffp-contract=off` | YES | **FMA contraction is NOT the trigger** |
| `-mfma` | YES | |
| `-mfma -ffp-contract=off` | YES | |
| `-mavx` / `-mavx2` | YES (identical to each other) | no FMA involved |
| `-march=znver3` | YES (identical to `-mfma`/native) | |
| `-march=native -fno-tree-vectorize -fno-tree-slp-vectorize` | YES | **GCC auto-vectorizer is NOT the trigger** |
| `-ffp-contract=fast` on default march | NO (bit-identical) | contraction alone does nothing on SSE2 |

GCC's contraction is on by default (verified: `-mfma` emits `vfmadd` with no
fast-math flags — standard-permitted). Reading of the matrix: the divergence
appears exactly when Eigen's explicitly-vectorized kernels switch from
128-bit (SSE2, 2 doubles/packet — the x86-64 baseline Eigen uses) to 256-bit
(AVX, 4 doubles/packet) code paths. `-fno-tree-vectorize` cannot touch those
(Eigen packetizes with its own intrinsics); `-ffp-contract=off` cannot undo
the different accumulation order of a 4-wide packet GEMM.

## 3. Isolation path (standalone drivers, `scratch/w35/`)

Drivers link the bridgestan stan-math tree directly (include set from W-32),
read exact hexfloat inputs (`inputs.txt` — identical bits in every binary),
print at %.17g. `d1`–`d6` cover: value-level eigendecomposition (`d1`), rev
gradient of the eigen complex with FD self-checks (`d2`), `lkj_corr_cholesky`
+ `multiply_lower_tri_self_transpose` (`d3`), the full extracted model logp
without the constrain transform (`d4`), value-level GEMM (`d5`), and
`cholesky_decompose` (`d6`).

### 3a. The seed: GEMM rounding (`d5`)

30x30 `A*B`, identical inputs: default vs native `C` differ by max
**2.1e-14 abs / 9.8e-15 rel**; the `sum(C)` reduction differs at 4.5e-13.
This is the entire input-side difference between the two builds — plain
permitted FP summation-order change.

### 3b. The amplifier, value level (`d1`)

`Eigen::SelfAdjointEigenSolver` (what stan-math `eigenvectors_sym` /
`eigenvalues_sym` call) on the model's actual matrices at failing points:

| matrix (30x30) | eigenvalue spectrum | max \|dw\| default-vs-native | max \|dV\| | V entries > 1e-8 | sign flips | residual (validity) |
|---|---|---|---|---|---|---|
| A_wellcond (control) | [17.6, 44.3], gaps O(1) | 7.1e-14 | 3.4e-14 | 0/900 | 0 | ~1e-14 both |
| Sigma1 (pt7) | bottom eigenvalues pinned at exactly 1e-5 (jitter floor) | 1.1e-14 | **9.6e-1** | **489/900** | **162** | 1.0e-14 / 1.5e-14 |
| Lambda = L Lᵀ (pt7) | smallest eigenvalues 2e-16…1e-12 | 7.1e-15 | 8.5e-2 | 150/900 | 14 | ~1e-14 both |

**The two binaries return different eigenbases for the same matrix** — both
satisfy `A·V = V·diag(w)` to ~1e-14, i.e. both are mathematically valid
decompositions. Within a cluster whose eigenvalue gaps are at rounding level
(gaps ~1e-16 across the pinned 1e-5 eigenvalues), the individual eigenvectors
are not uniquely determined — any orthogonal basis of the cluster subspace is
correct. This is the mechanism, and it is not a defect of any one build.

### 3c. The gradient consequence + FD self-checks (`d2`, `d4`)

`d2`: phi(A) = sum(W .* eigenvectors_sym(A)) + c' eigenvalues_sym(A) via
stan-math rev, Richardson central-FD self-check inside each binary:

| input | binary | AD-vs-own-FD | cross-binary grad diff |
|---|---|---|---|
| A_wellcond | default | 5.7e-8 (correct) | — |
| A_wellcond | native | 5.4e-8 (**native computes correct eigen gradients**) | 2.6e-13 |
| Sigma1 (pt7) | default | reldiff 1.0 (AD ~1e12–1e15 vs FD ~1e5) | — |
| Sigma1 (pt7) | native | reldiff 1.0 | **2.1e3 rel** |
| Lambda (pt7) | default/native | reldiff 1.0 | 3.7e3 rel |

`d4` (the full model logp in plain stan-math calls, constrained params from
failing points; FD = Richardson central, both binaries' FD agree to ~1e-6
because phi is smooth and stable to 1e-13):

| point | component | FD (stable) | default AD | native AD |
|---|---|---|---|---|
| pt7 | var1 | 1.049 | 0.604 (**44% off**) | 1.992 (**47% off**) |
| pt1 | var1 | 33.41 | 47.53 (**30% off**) | 36.46 (**8% off**) |
| pt7 | bw1 | −20.13 | −20.73 (2.9% off) | −20.43 (1.5% off) |
| all | sigma1 | — | 2e-9 | 2e-9 |
| all | spot-checked L entries | — | 1e-6…1e-7 | 1e-6…1e-7 |
| — | L block (435 comps) cross-binary | — | max rel up to 3.96, abs up to 11 | |

Three decisive observations: (1) **both** builds' var1/bw1 gradients are
FD-inconsistent at the same points (the reference itself is ill-conditioned —
W-32 saw the same); (2) at pt1 the NATIVE build is *closer* to FD than the
default build — incompatible with "native miscompiles, default correct";
(3) sigma1 (no eigenvector-adjoint coupling) is FD-consistent to 2e-9 in both.

`d3`/`d6`: `lkj_corr_cholesky_lpdf`, `multiply_lower_tri_self_transpose`, and
`cholesky_decompose` rev gradients are FD-consistent (1e-9) and
cross-binary-stable — the L-block functions themselves are fine; the wrong L
partials in W-27 are adjoint flow through `eigenvectors_sym(Lambda)`.

### 3d. Eigendecomposition on the other block: yes, also affected

Sigma1 (var1/bw1 block) and Lambda (L block) both have rounding-degenerate
clusters and both flip bases (§3b). The eigendecomposition complex is the
sole locus; no other stan-math function investigated shows flag sensitivity
beyond 1e-13 on well-conditioned inputs.

## 4. Sanitizers and cross-compiler (gates iv–v)

- `-fsanitize=address,undefined -fno-sanitize-recover=all` on `d2`, `d4`, and
  the minimized reproducer, under baseline and `-march=native`: **rc=0, zero
  reports, all six builds** (leak detection off). No UB, no OOB, no
  misaligned access. → not stan-math UB, no memory corruption.
- clang 22.1.8: `clang++ -O2` (SSE2 baseline) is **bit-identical to gcc
  baseline** on every matrix including cluster ones (eigenvectors equal to
  all printed digits, phi equal to 17 significant digits) — the solver is
  deterministic given identical arithmetic, across compilers.
  `clang++ -O2 -march=native` **reproduces the divergence** (different valid
  basis again, own FD reldiff 1.0). → compiler-independent, ISA-triggered.

## 5. Minimized reproducer (gate iii PASS)

`scratch/w35/repro/march_native_repro.cpp` — self-contained (no model, no
data file, no input file; the 30-point grid and the objective's weight matrix
are generated in-code from integer arithmetic so every binary shares exact
bits), ~65 code lines, stan-math rev + Eigen only. It builds the model's
Sigma1 at a posterior point (`var1*exp(-((x_i-x_j)^2)*bw1) + 1e-5*I`,
n=30), prints the eigenvalues/eigenvectors, then the rev-mode gradient of
phi = sum(W.*V) + c'w with an in-binary Richardson FD self-check. Source is
reproduced in full in §8.

Expected output (gcc 16.2.1 / clang 22.1.8, Zen 3):

| binary | A bits | w[0..4] (pinned cluster) | V col 0 | phi | own-FD check |
|---|---|---|---|---|---|
| gcc -O2 | identical | …1e-5, gaps ~1e-16 | (−0.0025, 0.0249, −0.110, 0.284, −0.450, 0.402) | −1.1122 | reldiff 1.0 |
| gcc -O2 -march=native | identical | …1e-5 (differ at 16th digit) | (0.0005, −0.0048, 0.019, −0.043, 0.046, 0.018) | −0.5028 | reldiff 1.0 |
| clang -O2 | identical | = gcc -O2 exactly | = gcc -O2 exactly | −1.1122236138732831 (17 digits equal) | reldiff 1.0 |
| clang -O2 -march=native | identical | differ again (3rd distinct basis) | (−0.0001, 0.0014, −0.008, 0.029, −0.070, 0.123) | −0.0407 | reldiff 1.0 |
| gcc -O1 -march=native (sanitizer build) | identical | differ again (4th basis) | — | −2.5629 | reldiff 1.0 |

Every build returns a valid decomposition (residual ~2e-14) and every build
fails its own FD check: the gradient does not exist numerically at machine
precision for this input, in any compilation.

Repro-level flag matrix (same pattern as §2): identical for
`-ffp-contract=off` alone / `-ffp-contract=fast` alone; diverges for
`-mavx`, `-mavx2`, `-mfma`, `-march=znver3`, `-march=native`,
`-march=native -ffp-contract=off`, `-march=native -fno-tree-vectorize
-fno-tree-slp-vectorize` (`-mfma`/`znver3`/`native` outputs identical to each
other; `-mavx`/`-mavx2` identical to each other).

## 6. Classification (gate v)

**Not a gcc bug.** Required evidence, all present: (a) the "correct" build is
itself FD-inconsistent at the failing points, and the "wrong" build is
sometimes MORE accurate (pt1 var1); (b) well-conditioned gradients are
computed correctly under `-march=native` (5e-8 FD agreement) and are
bit-identical across gcc/clang/ISA for the baseline; (c) sanitizers clean;
(d) clang reproduces the phenomenon with `-march=native` and clang-baseline
is bit-identical to gcc-baseline; (e) the only input-side difference between
builds is a 1e-15-rel GEMM rounding difference — permitted FP behavior, not
a codegen defect. There is no wrong instruction sequence: each binary
faithfully evaluates its own (differently-rounded, differently-ordered)
floating-point program.

**Not stan-math UB.** Sanitizers clean; the divergence is fully explained by
arithmetic, with no memory or aliasing involvement.

**It IS a real, reportable stan-math/Stan-ecosystem numerics+docs issue:**
`eigenvectors_sym`/`eigenvalues_sym`/`eigendecompose_sym` reverse-mode
adjoints implicitly assume separated eigenvalues; on near-degenerate spectra
(gaps at rounding level — easily produced by a GP kernel + jitter floor, or
any nearly-singular correlation matrix) the adjoint is catastrophically
ill-conditioned and silently returns FD-inconsistent gradients in every
build, and any permitted FP variation (compiler, -O level details, ISA
packet width) moves those gradient components by O(1) or more. `W-32`'s
bit-identical `eigendecompose_sym` rewrite does NOT change this (same
adjoint); only the model's conditioning does.

Corrected record: W-27's phrase "`-march=native` MISCOMPILES kronecker_gp
gradients" (WORKLOG W-27 close-out, W-29 §3 note, upstream_candidates #6)
is retracted in favor of: "`-march=native` (any AVX-or-wider ISA) changes
kronecker_gp gradients by O(1) through rounding-level GEMM reordering
amplified by near-degenerate eigendecompositions; both builds are
FD-inconsistent at these points." The operational guidance is unchanged and
now on solid grounds: do not build Stan models with `-march=native`;
`-O3` is provably safe (bit-identical); the per-call speedup was ≤ ~10%
anyway (W-27).

## 7. READY-TO-FILE drafts

Classification is unambiguous (stan-math/docs issue; no gcc report). Both
drafts included anyway: the one to file, and the gcc-bugzilla rationale for
the record (why we are NOT filing).

### 7a. stan-math issue (file to github.com/stan-dev/math/issues)

> **Title: Rev-mode eigenvector adjoints silently produce FD-inconsistent
> gradients on near-degenerate spectra; any FP reordering (e.g.
> -march=native) moves them by O(1)**
>
> **Summary.** The reverse-mode gradients of `eigenvectors_sym` /
> `eigenvalues_sym` (and `eigendecompose_sym`) use the standard distinct-
> eigenvalue adjoint `dA = V (F ∘ (Vᵀ G_V)) Vᵀ + V diag(g_w) Vᵀ` with
> `F_ij = 1/(w_j − w_i)`. For spectra with eigenvalue gaps near machine
> precision this adjoint is catastrophically ill-conditioned, but no warning
> or documentation exists. Consequences we measured (stan-math bundled with
> cmdstan 2.39 / bridgestan 2.9, Eigen 3.4.0, gcc 16.2.1, Zen 3; minimal
> self-contained reproducer below):
>
> 1. For a 30x30 jittered RBF kernel matrix `A = var1*exp(-(d_ij)^2 * bw) +
>    1e-5*I` (the `kronecker_gp` example model's `Sigma1`; the jitter floor
>    pins a cluster of bottom eigenvalues at exactly 1e-5, gaps ~1e-16),
>    the rev gradient of `phi(A) = sum(W .* eigenvectors_sym(A)) +
>    c' * eigenvalues_sym(A)` disagrees with Richardson central finite
>    differences by ~6 orders of magnitude (reldiff = 1.0) — i.e. the
>    returned gradient is not the derivative of the function being
>    differentiated, at any achievable step size.
> 2. Compiling the same source with any AVX-or-wider ISA (`-march=native`,
>    `-mavx`, `-mfma`, …) makes Eigen's GEMM accumulate in a different
>    order (max 1e-15 rel on a 30x30 product). The SelfAdjointEigenSolver
>    then returns a different but equally valid eigenbasis within the
>    cluster (up to 489/900 entries of V changed by O(1), 162 sign flips;
>    residual A·V − V·diag(w) ~ 1e-14 in both), and the AD gradient changes
>    by O(1)–O(1e3) relative — on the full `kronecker_gp` model, 55–221 of
>    438 gradient components move beyond 1e-6 rel, with sign flips, while
>    logp agrees to 1e-16. Note `-ffp-contract=off` and
>    `-fno-tree-vectorize` do NOT prevent this (Eigen packetizes with its
>    own intrinsics), and clang reproduces it, so this is not a compiler
>    bug — it is the adjoint's ill-conditioning making the gradient a
>    function of rounding noise.
>
> **Ask.** (a) Document in the function references that reverse-mode
> eigenvector/eigendecomposition adjoints assume separated eigenvalues and
> degrade without warning as min gap / ||A|| → eps; (b) consider a
> `check`/warning when the relative eigenvalue gap falls below a tolerance
> (analogous to existing PD checks), or a note pointing users with
> degenerate-spectrum models (jittered GPs, near-singular correlations) at
> the conditioning issue. Happy to provide the reproducer and full flag
> matrix.
>
> **Reproducer** (self-contained; expected output table in the attached
> report): see §8.

### 7b. gcc bugzilla — deliberately NOT filed (rationale for the record)

> Not filing because every criterion for "miscompile" fails: (1) the
> baseline build itself fails finite-difference validation at the failing
> inputs while the `-march=native` build sometimes passes more accurately —
> there is no "correct" reference the native build deviates from; (2) the
> native build computes correct results (FD-consistent to 5e-8, cross-ISA
> bit-stable) wherever the mathematical function is well-conditioned;
> (3) UBSan/ASan are clean under all flag sets; (4) the phenomenon
> reproduces identically with clang 22 `-march=native` while clang baseline
> is bit-identical to gcc baseline, i.e. it tracks Eigen's compile-time
> packet-width selection, not a GCC codegen defect; (5) the only
> binary-level input difference is a 1e-15-rel GEMM accumulation-order
> change, which is permitted by C++ (no fast-math involved) and is exactly
> the class of difference `-ffp-contract`, `-fno-tree-vectorize` etc. are
> documented not to control when the library does its own explicit
> vectorization.

### 7c. cmdstan/bridgestan docs PR (one paragraph, optional but recommended)

> The docs mention `-march=native` as a build-flag speedup. Caveat worth
> adding: any AVX-or-wider `-march` makes model gradients non-reproducible
> across builds on models whose log density routes through matrix
> eigendecompositions of near-degenerate matrices (e.g. jittered GP
> kernels): identical sources and inputs can yield gradients differing by
> O(1) with sign flips (log density still agrees to ~1e-16) because Eigen's
> wider-vector GEMM changes FP summation order and eigenvector bases within
> rounding-degenerate clusters are not unique. `-O3` is bit-identical to the
> default build and safe; measured upside of `-march=native` was ≤ ~10%
> per gradient call. (Evidence and minimal reproducer: stan-math issue
> linked here.)

## 8. Minimized reproducer source

```cpp
// march_native_repro.cpp — self-contained stan-math + Eigen reproducer.
// A = var1 * exp(-((xi-xj)^2) * bw1) + 1e-5 * I  (n = 30; the kronecker_gp
// model's Sigma1 at a posterior point; the jitter floor pins a cluster of
// bottom eigenvalues at exactly 1e-5 -> gaps at rounding level).
// Compile twice with identical inputs (see §5 table):
//   g++ -std=c++17 -O2  <stan-math includes> this.cpp -o repro_base
//   g++ -std=c++17 -O2 -march=native <includes> this.cpp -o repro_native
#include <cmath>
#include <cstdio>
#include <stan/math/rev.hpp>

int main() {
  const int n = 30;
  const double var1 = 2.2259362831331342, bw1 = 0.62234081376409707;
  double x[30];
  for (int i = 0; i < n; ++i) x[i] = -2.0 + 4.0 * i / 29.0;   // data grid
  Eigen::MatrixXd W(n, n);                 // integer LCG -> identical bits
  Eigen::VectorXd c(n);                    // in every binary
  unsigned long long s = 88172645463325252ULL;
  auto rnd = [&]() { s ^= s << 13; s ^= s >> 7; s ^= s << 17; return (int)(s >> 33); };
  for (int j = 0; j < n; ++j)
    for (int i = 0; i < n; ++i) W(i, j) = rnd() / 1073741824.0 - 1.0;
  for (int i = 0; i < n; ++i) c[i] = rnd() / 1073741824.0 - 1.0;

  Eigen::MatrixXd A(n, n);                 // elementwise: bit-identical
  for (int i = 0; i < n; ++i)              // across builds (printed check)
    for (int j = 0; j < n; ++j)
      A(i, j) = var1 * std::exp(-(x[i] - x[j]) * (x[i] - x[j]) * bw1);
  for (int i = 0; i < n; ++i) A(i, i) += 1e-5;
  printf("A(0,1) %.17g  A(15,15) %.17g\n", A(0, 1), A(15, 15));

  Eigen::SelfAdjointEigenSolver<Eigen::MatrixXd> es(A);  // what eigenvectors_sym runs
  printf("w[0..4]:");
  for (int i = 0; i < 5; ++i) printf(" %.17g", es.eigenvalues()[i]);
  printf("\nV col0 [0..5]:");
  for (int i = 0; i < 6; ++i) printf(" %.10g", es.eigenvectors()(i, 0));
  printf("\nresid %.3e\n",
         (A * es.eigenvectors() - es.eigenvectors() * es.eigenvalues().asDiagonal())
             .cwiseAbs().maxCoeff());

  auto phi = [&](const auto& Am) {           // model-like use of V and w
    auto V = stan::math::eigenvectors_sym(Am);
    auto w = stan::math::eigenvalues_sym(Am);
    return (W.array() * V.array()).sum() + c.dot(w);
  };
  std::vector<stan::math::var> av(A.data(), A.data() + n * n);
  Eigen::Matrix<stan::math::var, -1, -1> Am =
      Eigen::Map<Eigen::Matrix<stan::math::var, -1, -1>>(av.data(), n, n);
  stan::math::var f = phi(Am);
  f.grad();
  printf("phi %.17g  gA(0,1) %.17g  gA(5,5) %.17g  gA(29,28) %.17g\n", f.val(),
         av[0 * n + 1].adj(), av[5 * n + 5].adj(), av[29 * n + 28].adj());
  auto phid = [&](const Eigen::MatrixXd& M) { return phi(M); };
  for (auto [i, j] : std::vector<std::pair<int, int>>{{0, 1}, {5, 5}, {29, 28}}) {
    auto ev = [&](double h) {                  // Richardson central FD
      Eigen::MatrixXd P = A, Q = A;
      P(i, j) += h; if (i != j) P(j, i) += h;
      Q(i, j) -= h; if (i != j) Q(j, i) -= h;
      return (phid(P) - phid(Q)) / (2 * h);
    };
    double d1 = ev(1e-5), d2 = ev(5e-6), rich = (4 * d2 - d1) / 3;
    double ad = av[i * n + j].adj() + (i != j ? av[j * n + i].adj() : 0.0);
    printf("fd(%d,%d) rich %.10g  ad %.10g  reldiff %.2e\n", i, j, rich, ad,
           std::abs(rich - ad) / std::max(1.0, std::abs(ad)));
  }
  return 0;
}
```

Build command (from `stan/`):

```
M=~/.bridgestan/bridgestan-2.9.0/stan/lib/stan_math
g++ -std=c++17 -O2 [-march=native] -pthread -D_REENTRANT \
  -I $M -I $M/lib/eigen_3.4.0 -I $M/lib/boost_1.87.0 \
  -I $M/lib/sundials_6.1.1/include -I $M/lib/sundials_6.1.1/src/sundials \
  -I $M/lib/tbb_2020.3/include -x c++ scratch/w35/repro/march_native_repro.cpp -o /tmp/repro \
  -L $M/lib/tbb -Wl,-rpath,$M/lib/tbb -ltbb
```

## 9. What was and was not established

Established: exact trigger class (any ISA that widens Eigen packets beyond
SSE2 — `-mavx` is sufficient, `-mavx2`/`-mfma`/`-znver3`/`-march=native`
equivalent up to their own rounding); contraction and GCC auto-vectorization
ruled out; the mechanism isolated to Eigen SelfAdjointEigenSolver basis
selection within rounding-degenerate clusters + the 1/(w_j−w_i) adjoint;
both builds FD-inconsistent at failing points (the reference is not
"correct"); sanitizers clean; compiler-independent; minimized to a
self-contained 65-line stan-math+Eigen snippet with no model dependency.

Not established (and likely not true): attribution to a single Eigen kernel
(tridiagonalization GEMM vs the QL iteration) — the basis flip is a
data-dependent iterate; a per-kernel bisection was not attempted (not needed
for classification). Model-level confirmation beyond kronecker_gp (e.g.
whether other example models have the same latent exposure) is future work;
the mechanism requires a near-degenerate eigendecomposition on the gradient
path, which the W-29/W-32 atlas says is kronecker_gp-specific among our
models.

## 10. File index

- `scratch/w35/repro/march_native_repro.cpp` — minimized reproducer (committed)
- `scratch/w35/parity.py` — model-level gradient parity harness (committed)
- `scratch/w35/build_variant.sh` — per-variant bridgestan build helper (committed)
- `scratch/w35/gen_inputs.py`, `inputs.txt`, `common.hpp` — driver input
  generation (exact hexfloats) and reader (local)
- `scratch/w35/d1_eigh_values.cpp` … `d6_cholesky.cpp` — isolation drivers
  (values / eigen-grad FD / lkj+mltstp / extracted model / GEMM / cholesky),
  their binaries and `.out` files (local)
- `scratch/w35/*_build/kronecker_gp_model.so` — flag-matrix builds (local)
- Sanitizer binaries: `scratch/w35/*_san`, `scratch/w35/repro/repro_*_san` (local)
