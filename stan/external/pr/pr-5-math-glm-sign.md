# Fix missing signs factor in bernoulli_logit_glm_lpmf theta_derivative above the cutoff

Companion of the one-line `bernoulli_logit_lpmf` partials fix ("Fix
missing signs factor in bernoulli_logit_lpmf partials above the cutoff",
branch `bernoulli-logit-partials-sign`), the GLM implementation builds
its per-instance derivative array with the identical three-branch
structure and the identical defect in the first branch. Happy to fold
both into one PR or keep them separate, whichever review prefers. The
derivations are independent.

## Problem

`bernoulli_logit_glm_lpmf(y, x, alpha, beta)` computes the linear
predictor per instance, `theta = alpha + x * beta`, folds the label in
via `signs = 2y − 1` and `ytheta = signs * theta`, and evaluates

```cpp
exp_m_ytheta = exp(-ytheta);
logp = sum((ytheta > cutoff)
               .select(-exp_m_ytheta,
                       (ytheta < -cutoff).select(ytheta, -log1p(exp_m_ytheta))));
```

The derivative array that feeds the `x`/`alpha`/`beta` adjoints is

```cpp
Matrix<T_partials_return, Dynamic, 1> theta_derivative
    = (ytheta > cutoff)
          .select(-exp_m_ytheta,                                // <-- bug
                  (ytheta < -cutoff)
                      .select(signs * T_partials_return(1.0),
                              signs * exp_m_ytheta / (exp_m_ytheta + 1)));
```

with `cutoff = 20.0`.

### Derivation of the correct partial

For `ytheta > cutoff` the value branch is `−exp(−ytheta)`, so

```
d(value) / d(ytheta) = +exp(−ytheta) = +exp_m_ytheta
```

and by the chain rule through `ytheta = signs · theta` (`signs` is
constant in `alpha`, `beta` and `x`):

```
∂lp/∂theta_i = signs_i · exp_m_ytheta_i          (ytheta_i > cutoff)
```

The code instead returns `−exp_m_ytheta`, the derivative *of the value*
with respect to `ytheta` without the chain-rule factor. That is correct
only when `signs = −1` (`y = 0`). For instances with `y = 1` and `theta_i > 20`, and, symmetrically, `y = 0` with `theta_i < −20`, the derivative that flows into every downstream adjoint has the wrong sign. The propagated adjoints are

```
∂lp/∂beta  = xᵀ · theta_derivative        (matrix path)
∂lp/∂alpha = theta_derivative
∂lp/∂x     = beta · theta_derivativeᵀ
```

so each affected element contributes with a flipped sign to all three.
The other two branches apply `signs` correctly. Only the upper branch
drops it, the same one-branch inconsistency as in
`bernoulli_logit_lpmf`.

### Magnitude, and why it survived

The per-element error is the full `2 · exp(−ytheta)` sign flip, bounded
by `2·e^−20 ≈ 4.1e-9` just above the cutoff and shrinking exponentially.
On the sibling non-GLM site the same shape was measured in an
instrumented hierarchical 2PL IRT model (N = 19,200): max 4.08e-9 per
affected element at `ntheta = 20.011`, max ~1.4e-6 absolute (5e-10
relative) on parameter gradients, invisible to casual tolerances,
which is presumably how it went unnoticed. It was found by a tight
value+partials parity harness whose reference derived the partial
analytically. The mismatch was exactly `2·e^−ytheta` on the affected
elements. Present in develop as of 2026-08-23.

## Solution (one line, re-derivable from the problem statement)

In `theta_derivative`'s upper branch, replace `-exp_m_ytheta` with
`signs * exp_m_ytheta`, matching the two sibling branches (which
already multiply by `signs`, e.g. the in-band branch is
`signs * exp_m_ytheta / (exp_m_ytheta + 1)`):

```cpp
Matrix<T_partials_return, Dynamic, 1> theta_derivative
    = (ytheta > cutoff)
          .select(signs * exp_m_ytheta,
                  (ytheta < -cutoff)
                      .select(signs * T_partials_return(1.0),
                              signs * exp_m_ytheta / (exp_m_ytheta + 1)));
```

No other change: the value expression, the other two derivative
branches, and all surrounding code are untouched. This header is the
shared implementation, the `rev` and `mix` paths instantiate the same
`prim` template (there is no rev/mix override), so one fix covers all
modes.

**Same-pattern site, not fixed here (flagged for maintainers):**
`stan/math/opencl/prim/bernoulli_logit_glm_lpmf.hpp` builds
`theta_derivative_expr` with the same structure and the same first
branch (`select(high_bound_expr, -exp_m_ytheta_expr, …)` without
`signs_expr`), so STAN_OPENCL builds have the analogous wrong-sign
derivative for `y = 1` instances above the cutoff. The same one-line
chain-rule fix applies there. Not included here because it belongs with
an OpenCL test run.

## Validation

- Added regression test (`AgradRev.bernoulli_glm_cutoff_partials_sign`
  in `test/unit/math/rev/prob/bernoulli_logit_glm_lpmf_test.cpp`): a
  1×1 design matrix `x = [1]`, `alpha = 0`, `beta = ±(cutoff + 5) = ±25`,
  for both `y = 1, theta = +25` and `y = 0, theta = −25` (both put
  `ytheta = signs · theta` above the cutoff). It checks the autodiff
  gradients of `beta` and `alpha` against (a) the analytic
  value `signs * exp(−ytheta)` and (b) central finite differences of
  the double implementation with `h = 1e-3`, small enough that both FD
  points stay inside the same branch, large enough that the
  ~1.4e-11-magnitude values subtract cleanly.
- The test fails on the unpatched code (verified by rebuild: for
  `y = 1, theta = 25` the adjoints come back as
  `−1.3887943864964021e-11` where `+1.3887943864964021e-11` is
  expected, off by exactly `2·exp(−25)`) and passes with the fix.
  Full test binary with the fix: 23/23 (the file's existing
  value-parity and broadcast tests are unaffected, the bug is in the
  derivative array only).
- The `mix` distribution test for this function (FD-reference tests
  through the same template) passes with the fix.

## References

- Any logistic-regression reference for
  `d/dθ log σ(±θ) = σ(∓θ) = exp(−|ytheta|)/(1 + exp(−|ytheta|))` and its
  saturated tails: the value branch `−exp(−ytheta)` is the standard
  `log σ(ytheta)` tail. Its derivative is `+exp(−ytheta)`, never
  negative, and the chain rule through `signs` restores the sign of the
  label.
- Sibling PR: "Fix missing signs factor in bernoulli_logit_lpmf
  partials above the cutoff" (`bernoulli-logit-partials-sign`), same
  derivation for the non-GLM site, including the discovery harness and
  the propagated model-level error bounds (also available via the
  public benchmark repo https://github.com/sims1253/apin —
  `stan/results/` and `stan/WORKLOG.md`).
