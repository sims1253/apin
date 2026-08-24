# Why expect_ad does not catch this (with pointers)

Two separate reasons, both verified against the tree at 344d7167.

## 1. The existing test never enters the buggy branch

The test at
`test/unit/math/mix/prob/bernoulli_logit_glm_lpmf_test.cpp` uses
`Eigen::MatrixXd::Random(2, 2)` for `x` and `VectorXd::Random(2)` for
`alpha`/`beta`. Those draws put every `theta = alpha + x * beta` well
inside |theta| < 20, so the `(ytheta > cutoff)` branch is never executed
at all. The branch has no coverage today.

## 2. A sign flip below ~5e-9 is invisible to the gradient comparison

The case you added (y=1, x=[1], alpha=0, theta=25) does enter the branch.
There the gradient is tiny, and that is where the harness has a blind
spot by construction:

- `test/unit/math/test_ad.hpp`, lines 138-140: `expect_ad` compares the
  reverse-mode gradient against `stan::math::finite_diff_gradient_auto`
  through `expect_near_rel(..., tols.gradient_grad_, ...)`.
- `test/unit/math/ad_tolerances.hpp`, line 48: `gradient_grad_` defaults
  to `relative_tolerance(1e-4)`.
- `test/unit/math/relative_tolerance.hpp`: that constructor sets
  `tol_min = max(tol * tol, 1e-14) = 1e-8`, and the comparison of two
  inexact values uses

  ```
  inexact(x, y) = max(tol * 0.5 * (|x| + |y|), tol_min)
  ```

For beta at this test point: reverse-mode gives `-1.3888e-11` (stock),
finite differences give `+1.3888e-11`. The relative term is
`1e-4 * 1.3888e-11 = 1.4e-15`, so the allowed difference is the floor,
`1e-8`. The actual difference is `2.8e-11`. It passes with a 200%
relative error, because the values sit under the absolute floor.

This is a deliberate tradeoff, not a defect in the helper: finite
differences of near-zero gradients need an absolute floor, since their
relative error explodes. But it defines a blind spot: any gradient whose
magnitude is below about half the floor cannot be sign-checked at all.
The error here is bounded per observation by `2 * exp(-20) = 4.1e-9`, so
single-observation tests can never see it.

## What does catch it

Amplify past the floor by aggregating observations. N = 100000 rows of
(y=1, x=1) with beta = 25: stock returns `beta adjoint = -1.3887943864962839e-06`
where the analytic value is `N * exp(-25) = +1.3887943864964021e-06` and
finite differences agree with the positive value. A `2.8e-6` gap against
a `1e-8` floor fails loudly. Verified on develop @ 344d7167 and on the
fix branch, same lp in both:
https://github.com/sims1253/apin/blob/main/stan/scratch/reprex_3369.cpp
