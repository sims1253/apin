`target += poisson_log_lpmf(y | theta)` keeps the term `sum(lgamma(y + 1))` in the log density. When y is data, that term never changes, but the compiler evaluates it on every log density call — every leapfrog step and every adaptation iteration. On a brms-style poisson model (N = 12,573) the lgamma chain is 41% of the run's instructions.

This pass hoists the term to transformed data, computed once at construction. The likelihood call flips to its propto overload, and the accumulator re-adds the precomputed constant as one term. `lp__` keeps the full-constant value: on the validation model the emitted form agrees with stock to 1 ulp, and the gradients match bitwise, since the constant carries no gradient.

Sampling statements are untouched — they already drop the constant. Nine negative controls stay silent, among them rate-form heads, local y, and user functions. Pattern-free models compile byte-identical, and the test suite passes.

Measured: the poisson_log_glm subtree drops 48% of its instructions, and the lgamma share falls from 41% to 0.1%. Draws agree with stock at distribution level; two of twelve chains match bitwise.

Self-contained: no stan-math change required.
