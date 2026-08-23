# square() for arithmetic types: multiply instead of calling std::pow(x, 2)

## Problem

`stan/math/prim/fun/square.hpp` implements `square(x)` for arithmetic `x`
as

```cpp
template <typename T, require_arithmetic_t<T>* = nullptr>
inline double square(const T x) {
  return std::pow(x, 2);
}
```

while the doc comment directly above it says "The implementation of
square(x) is just x * x".

### Why the pow call survives compilation

`std::pow` with default toolchain settings (gcc/clang default to
`-fmath-errno`) is *not* a pure arithmetic operation: it is specified to
set `errno` on domain/range/overflow/pole errors, which makes the call
observable and prevents the optimizer from rewriting it to a multiply in
general (the rewrite would change `errno` behavior on the generic-domain
cases). The result is a real libm call per evaluation, glibc's `pow` is a
branchy, multi-path implementation (~105 instructions
per call measured in the profile below: 3,473,268 Ir over 33,078 calls) —
whereas `x * x` is one (fused) instruction. There is no constant to fold
here: the exponent is a literal `2`, but the base is runtime data.

This line sits in hot paths: covariance kernels (`gp_exp_quad_cov`
computes `square(squared_distance(x_i, x_j))` per kernel pair. The rev
overload computes distances on `value_of` data and instantiates this
template), normal-type lpdfs, and user models. On the measured GP
regression model, `square()` accounts for **57 `pow` calls per gradient
and 8.9% of gradient instructions** (callgrind): of 33,078 executed `pow`
calls, 32,889 come from `gp_exp_quad_cov` (55 kernel pairs for N=11, plus
`square(sigma)` and `square(l)`).

### Why the change is safe: the strictly-more-accurate argument

For IEEE-754 double, `x * x` is by definition the correctly rounded square
(single rounding of an exact product). I measured glibc 2.44's `pow(x, 2)`
against that reference on dense input grids: it agrees on the vast majority
of doubles but differs by 1 ulp on ~0.08% of them (glibc's `pow` is not
correctly rounded for this exponent in every case). The proposed multiply is
therefore the *strictly more accurate* operation, not merely an equal one.

Two consequences stated plainly:

1. This is not a bit-identity claim. Where the two disagree, results
   shift by 1 ulp. In my measurements such shifts stayed at FP-noise level
   (e.g. one gradient component of a hierarchical logit model at 2e-15 rel,
   log-density exactly equal). Full sampling trajectories on models whose
   gradients I compared were bit-identical for the tested short runs, and
   diverged on some chains of longer runs purely through 1-ulp seed drift.
2. On models with *rounding-degenerate eigendecompositions* (e.g. GP kernels
   with jitter-pinned eigenvalue clusters), a 1 ulp input change can select a
   different but equally valid eigenbasis, and reverse-mode eigenvector
   adjoints amplify that to O(1) gradient differences. That amplification is
   a pre-existing conditioning property of the adjoint (I report it
   separately), not something this patch introduces, but reviewers should
   know bit-for-bit reproducibility across this change is not guaranteed on
   that model class.

## Evidence

GP regression model (`gp_exp_quad_cov`, n = 11 → 55 kernel pairs), matched
binaries, identical inputs, gcc 16.2.1, glibc, Zen 3. Medians of 3
interleaved reps. Callgrind on a fixed seeded run (warmup 50 / samples 50,
577 gradient calls in both arms):

| metric | stock | patched | delta |
|---|---|---|---|
| Ir / gradient (callgrind, deterministic) | 66,950 | 60,864 | **−9.1%** |
| pow instructions in run | 3,473,268 | 19,923 | −99.4% (residual is sampler-side Adam) |
| µs / logp_grad call (warmup stanza) | 6.681 | 5.820 | **−12.9%** |
| µs / logp_grad call (sampling stanza) | 6.655 | 5.640 | **−15.2%** |

The wall win exceeds the instruction share because glibc `pow`'s branchy
double path runs at much worse IPC than the surrounding Eigen/arithmetic
code. Per-rep ranges do not overlap (stock 6.52–6.99, patched 5.61–5.89
across all six stanzas). Absolute µs are inflated by a co-running job on a
shared machine, the interleaved A/B ratio is the measurement.

Cross-model context (from profile dumps, indicative): `pow`'s exclusive
share of total program Ir is 7.3% on this GP model, 1.9% on a Kronecker-GP
model, 0.7% on an accelerated-GP model, the GP-kernel class is the
exposure. The fix is unconditional and helps wherever arithmetic squaring
occurs.

## Solution (derivation. The diff is one concrete instantiation)

1. Replace `std::pow(x, 2)` with a widened multiply:

   ```cpp
   const double x_d = x;
   return x_d * x_d;
   ```

2. Widen before multiplying, this is the load-bearing detail. The
   template is enabled for *all* arithmetic `T`, including integral and
   float types, and the previous code promoted through `double` (the
   function returns `double`; `std::pow`'s arithmetic overloads promote to
   `double`). A naive `x * x`:
   - for integral `x` computes an *int* product, which overflows for
     |x| > 46,341 where the promoted path does not;
   - for `float` `x` rounds in float and then promotes, a
     double-rounding drift relative to the correctly rounded double
     square.
   Widening to `double` first reproduces the previous semantics exactly
   (promotion to double, then the rounded double product), minus the libm
   call. The two corner types are exactly what the added bit-identity
   micro-check exercises (below).

3. Sibling sites with the same pattern, included here: the two scalar-var
   `squared_distance` overloads in `stan/math/rev/fun/squared_distance.hpp`
   used `std::pow(a.val() − b.val(), 2)` for the value and recomputed
   `a.val() − b.val()` again inside the adjoint callback. Compute the
   difference once into a `const double`, square it for the value, and
   reuse it in the callback (the adjoint expression `2 * diff` is
   unchanged in form). The matrix/vector overloads already use
   `squaredNorm`/products and are untouched.

A maintainer re-deriving this from scratch needs only steps 1–3. The diff
is exactly that, plus tests.

## Validation

- Value agreement at model level: stock vs patched model `.so` on 100
  deterministic random unconstrained points, logp max rel diff 0.0,
  gradients bit-identical on 100/100 points, zero sign flips. Short sampler
  runs (warmup 50 + samples 50, fixed seed and init) produce md5-identical
  draws natively and under valgrind. (These establish agreement on the
  tested inputs, not a universal bit-identity, see the accuracy section.)
- Independent replication via a build flag: compiling the *stock*
  source with `-fno-math-errno` (which unblocks the compiler's own
  `pow(x,2) → x*x` transform; I verified it transforms exactly this
  pattern and nothing else on my workload) reproduces the win without any
  source change: Ir/gradient −8.5%, per-call wall ×0.86–0.88 on the same
  GP model. This is what the optimizer would do if `errno` semantics
  allowed it.
- Corner-type check of the widened multiply: equals the promoted
  `std::pow(x, 2)` semantics exactly on int64 3e9 (promotion), int −46,341
  (int-overflow corner), float 1.0000001f (double-rounding corner), and a
  double sweep {−3.7e5 … 1e300} including the overflow-to-inf case.
- Repo tests (current develop, Eigen 5.0.1): `square_test` (2/2),
  `squared_distance_test` (7/7), plus the mix counterparts (1/1, 2/2) —
  the mix tests carry the finite-difference gradient references.
- FD spot-check of the patched model (central, h = 1e-5): max rel
  4.9e-8, FD noise level.

## References

- C/C++ math function errno semantics and `-fmath-errno` (default-on in
  gcc/clang), why the optimizer cannot remove the call. My flag
  replication (above) directly demonstrates the transform is the
  compiler's own once unblocked.
- IEEE-754 single-rounding guarantees for `x * x`, the basis of the
  strict-accuracy argument. My glibc 2.44 measurement of `pow(x,2)`'s
  1-ulp deviations (~0.08% of doubles).
- Extended measurement logs (pre-registered experiment ledger, callgrind
  dumps, kernel ulp grids, full run JSONs) are available on request, or at
  the public benchmark repo: https://github.com/sims1253/apin
  (`stan/results/` and `stan/WORKLOG.md`).
