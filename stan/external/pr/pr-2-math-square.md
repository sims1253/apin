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
cases). The result is a real libm call per evaluation — glibc's `pow` is a
branchy, multi-path, *correctly rounded* implementation (~105 instructions
per call measured in the profile below: 3,473,268 Ir over 33,078 calls) —
whereas `x * x` is one (fused) instruction. There is no constant to fold
here: the exponent is a literal `2`, but the base is runtime data.

This line sits in hot paths: covariance kernels (`gp_exp_quad_cov`
computes `square(squared_distance(x_i, x_j))` per kernel pair; the rev
overload computes distances on `value_of` data and instantiates this
template), normal-type lpdfs, and user models. On the measured GP
regression model, `square()` accounts for **57 `pow` calls per gradient
and 8.9% of gradient instructions** (callgrind): of 33,078 executed `pow`
calls, 32,889 come from `gp_exp_quad_cov` (55 kernel pairs for N=11, plus
`square(sigma)` and `square(l)`).

### Why the change is safe: the correctly-rounded argument

For IEEE-754 double, `x * x` is by definition the correctly rounded
square. glibc's `pow` is correctly rounded (documented since glibc 2.28),
so `pow(x, 2)` returns the same correctly rounded value: **the two are
bit-identical on glibc**. This is not an approximation argument — it is an
identity between two correctly rounded evaluations of the same exact
product. On platforms whose `pow` is not correctly rounded the change can
differ by at most 1 ulp (normal floating-point non-associativity
territory).

## Evidence

GP regression model (`gp_exp_quad_cov`, n = 11 → 55 kernel pairs), matched
binaries, identical inputs, gcc 16.2.1, glibc, Zen 3; medians of 3
interleaved reps; callgrind on a fixed seeded run (warmup 50 / samples 50,
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
across all six stanzas); absolute µs are inflated by a co-running job on a
shared machine — the interleaved A/B ratio is the measurement.

Cross-model context (from profile dumps, indicative): `pow`'s exclusive
share of total program Ir is 7.3% on this GP model, 1.9% on a Kronecker-GP
model, 0.7% on an accelerated-GP model — the GP-kernel class is the
exposure; the fix is unconditional and helps wherever arithmetic squaring
occurs.

## Solution (derivation; the diff is one concrete instantiation)

1. Replace `std::pow(x, 2)` with a widened multiply:

   ```cpp
   const double x_d = x;
   return x_d * x_d;
   ```

2. **Widen before multiplying — this is the load-bearing detail.** The
   template is enabled for *all* arithmetic `T`, including integral and
   float types, and the previous code promoted through `double` (the
   function returns `double`; `std::pow`'s arithmetic overloads promote to
   `double`). A naive `x * x`:
   - for integral `x` computes an *int* product, which overflows for
     |x| > 46,341 where the promoted path does not;
   - for `float` `x` rounds in float and then promotes — a
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

A maintainer re-deriving this from scratch needs only steps 1–3; the diff
is exactly that, plus tests.

## Validation

- **Bit-identity at model level:** stock vs patched model `.so` on 100
  deterministic random unconstrained points — logp max rel diff 0.0,
  gradients bit-identical on 100/100 points, zero sign flips; full sampler
  runs (warmup 50 + samples 50, fixed seed and init) produce
  md5-identical draws natively and under valgrind.
- **Bit-identity micro-check of the corner types:** the widened multiply
  equals `std::pow(x, 2)` exactly on int64 3e9 (promotion), int −46,341
  (int-overflow corner), float 1.0000001f (double-rounding corner), and a
  double sweep {−3.7e5 … 1e300} including the overflow-to-inf case.
- **Repo tests (current develop, Eigen 5.0.1):** `square_test` (2/2),
  `squared_distance_test` (7/7), plus the mix counterparts (1/1, 2/2) —
  the mix tests carry the finite-difference gradient references.
- **FD spot-check** of the patched model (central, h = 1e-5): max rel
  4.9e-8 — FD noise level.

## References

- glibc manual: `pow` is correctly rounded (since 2.28) — the basis of the
  bit-identity argument.
- C/C++ math function errno semantics and `-fmath-errno` (default-on in
  gcc/clang) — why the optimizer cannot remove the call.
- Internal evidence trail: our benchmark repo `results/gp_micro_w33.md`
  (W-33, the measured ceiling incl. the negative cholesky-adjoint
  assessment) and `results/upstream_dryrun_w44.md` (W-44, develop-port
  test runs). Happy to attach.
