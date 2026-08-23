# Fix missing signs factor in bernoulli_logit_lpmf partials above the cutoff

## Problem

`bernoulli_logit_lpmf` computes, per observation, with
`signs = 2n − 1` and `ntheta = signs * theta`:

```cpp
exp_m_ntheta = exp(-ntheta);
logp = (ntheta > cutoff)
           .select(-exp_m_ntheta,
                   (ntheta < -cutoff).select(ntheta, -log1p(exp_m_ntheta)));

edge<0>(ops_partials).partials_
    = (ntheta > cutoff)
          .select(
              -exp_m_ntheta,                                   // <-- bug
              (ntheta >= -cutoff)
                  .select(signs * exp_m_ntheta / (exp_m_ntheta + 1),
                          signs));
```

### Derivation of the correct partial

For `ntheta > cutoff` the value branch is `−exp(−ntheta)`, so

```
d(value) / d(ntheta) = +exp(−ntheta) = +exp_m_ntheta
```

and by the chain rule through `ntheta = signs · theta` (signs is constant
in `theta`):

```
∂lp/∂theta = signs · exp_m_ntheta          (ntheta > cutoff)
```

The code instead returns `−exp_m_ntheta`, the derivative *of the value*
without the chain-rule factor. That is correct only when `signs = −1`
(`n = 0`). **For observations with `n = 1` and `theta > 20` (and,
symmetrically, `n = 0` with `theta < −20`) the gradient of every such
element has the wrong sign.** The other two branches apply `signs`
correctly. Only the upper branch drops it.

### Magnitude, and why it survived

The per-element error is the full `2 · exp(−ntheta)` sign flip, bounded by
`2·e^−20 ≈ 4.1e-9` just above the cutoff and shrinking exponentially.
In an instrumented model (hierarchical 2PL IRT, N = 19,200 observations)
the propagated effect at wild random unconstrained points was max
4.08e-9 per affected partial (at ntheta = 20.011) and max
1.4e-6 absolute (5e-10 relative) on parameter gradients, invisible to
casual tolerances, which is presumably how it went unnoticed. It was found
by a tight value+partials parity harness whose reference derived the
partial analytically: the mismatch was exactly `2·e^−ntheta` on the
affected elements. Present in develop as of 2026-08-23.

## Solution (one line, re-derivable from the problem statement)

In the partials' upper branch, replace `-exp_m_ntheta` with
`signs * exp_m_ntheta` (kept wrapped in the same
`promote_scalar<T_partials_return>` style as the sibling branches):

```cpp
edge<0>(ops_partials).partials_
    = (ntheta > cutoff)
          .select(
              promote_scalar<T_partials_return>(signs * exp_m_ntheta),
              (ntheta >= -cutoff)
                  .select(promote_scalar<T_partials_return>(
                              signs * exp_m_ntheta / (exp_m_ntheta + 1)),
                          promote_scalar<T_partials_return>(signs)));
```

No other change: the value expression, the other two partials branches,
and all surrounding code are untouched. This file is the shared
implementation, the rev and mix paths instantiate the same template, so
one fix covers all modes.

Same-pattern site, not fixed here (flagged for maintainers):
`bernoulli_logit_glm_lpmf.hpp` builds its `theta_derivative` with the
identical three-branch structure and the identical first branch
(`-exp_m_ytheta` without `signs`), so GLM instances with `y = 1` and
`ytheta > 20` have the same wrong-sign derivative feeding the
`x`/`alpha`/`beta` adjoints. The same one-line chain-rule fix applies;
happy to include it in this PR or a follow-up, whichever review prefers.

## Validation

- Added regression test (`cutoff_partials_sign` in
  `test/unit/math/prim/prob/bernoulli_logit_test.cpp`): for both
  `n = 1, theta = +25` and `n = 0, theta = −25` (both put `ntheta` above
  the cutoff) it checks the autodiff gradient of
  `bernoulli_logit_lpmf(n, theta)` against (a) the analytic value
  `signs * exp(−ntheta)` and (b) central finite differences of the double
  implementation with h = 1e-3, small enough that both FD points stay
  inside the same branch, large enough that the ~1e-11-magnitude values
  subtract cleanly.
- The test fails on the unpatched code (verified by rebuild: the
  autodiff gradient comes back with the sign flipped, off by
  `2·exp(−ntheta)`) and passes with the fix. Full test binary: 6/6.
- Repo test suite for the file passes with the fix (the existing
  value-space `cutoff` test is unaffected, the bug is in partials only).

## References

- Hoffman & Gelman (2014), or any logistic-regression reference, for
  `d/dθ log σ(±θ) = σ(∓θ) = exp(−|ntheta|)/(1 + exp(−|ntheta|))` and its
  saturated tails, the value branch `−exp(−ntheta)` is the standard
  `log σ(ntheta)` tail. Its derivative is `+exp(−ntheta)`, never negative.
- The discovery harness and per-element error analysis, together with the
  propagated model-level bounds, are available on request or via the
  public benchmark repo (https://github.com/sims1253/apin, `stan/results/`
  and `stan/WORKLOG.md`). Happy to attach.
