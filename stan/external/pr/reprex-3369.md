# Re: is this a legitimate bug (PR 3369, bernoulli_logit_glm partials sign)

How I found it: I was benchmarking a fused kernel for this lpmf and built
a parity harness that checks value and partials against analytic formulas,
branch by branch. The `(ytheta > cutoff)` branch of `theta_derivative`
mismatched by exactly `2 * exp(-ytheta)` on the affected elements. That
is the signature of a dropped `signs` factor, and the two sibling branches
do apply `signs`.

Why the `expect_ad` case passes: with `y=1, x=[1], alpha=0, theta=25` the
wrong-signed gradient has magnitude `exp(-25)`, about `1.39e-11`. Stock
returns `-1.3888e-11` where the analytic value is `+1.3888e-11`. The gap
is `2.8e-11`. Finite differences cannot resolve the sign of a quantity
that small, and any comparison with an absolute floor for near-zero
gradients will pass it. The per-observation error is bounded by
`2 * exp(-20)` (about `4e-9`, right at the cutoff, decaying from there),
so a single-observation test can never see it cleanly.

The bug is still real, and it scales with the number of saturated
observations. Repro that amplifies it past every tolerance (verified on
develop @ 344d7167 and on the fix branch):

```cpp
#include <stan/math.hpp>
#include <iostream>
int main() {
  using stan::math::var;
  const int N = 100000;                       // saturated observations
  Eigen::VectorXi y(N); y.setConstant(1);     // y = 1
  Eigen::MatrixXd x = Eigen::MatrixXd::Ones(N, 1);
  Eigen::Matrix<var, -1, 1> alpha = Eigen::Matrix<var, -1, 1>::Zero(N);
  Eigen::Matrix<var, -1, 1> beta(1); beta(0) = 25.0;   // theta = 25 > cutoff
  var lp = stan::math::bernoulli_logit_glm_lpmf(y, x, alpha, beta);
  lp.grad();
  std::cout.precision(17);
  std::cout << "beta adjoint = " << beta(0).adj() << "\n";
}
```

Output on stock develop:

```
beta adjoint  = -1.3887943864962839e-06
```

The analytic value is `N * exp(-25) = +1.3887943864964021e-06`, and
finite differences of the double implementation agree with the positive
value. With the one-line fix (`signs * exp_m_ytheta` in the first branch
of `theta_derivative`):

```
beta adjoint  = +1.3887943864962839e-06
```

The log density is identical in both cases; only the gradient changes.
Each `alpha_i` carries only its own observation, so its wrong-signed term
stays at `1.39e-11`, but `beta` aggregates all `N` of them, which is
exactly how the error reaches `~1e-6` on real models with many confident
observations. That is also consistent with what I measured on a
hierarchical 2PL benchmark: parameter gradients carried wrong-signed
contributions up to about `1.4e-6` absolute.

The fix and a test that fails on stock by exactly `2 * exp(-25)` are on
my fork ([sims1253/math#4](https://github.com/sims1253/math/pull/4)),
with the same fix for the non-GLM `bernoulli_logit_lpmf` in
[sims1253/math#3](https://github.com/sims1253/math/pull/3).
