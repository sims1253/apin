For count models written with `target +=` — the form brms generates — terms that depend only on the data are recomputed on every log density call. That is every leapfrog step and every adaptation iteration.

In `binomial_logit_glm_lpmf`, `lgamma` over constant `n` and `N` is about 45% of the function's forward instructions (measured at N = 12,573). `poisson_log_glm_lpmf` and `neg_binomial_2_log_glm_lpmf` show the same pattern at 44% and 22%. Sampling statements already drop these terms; the cost is specific to the explicit form.

The terms are invariant across the run. Two fixes are open:

1. Hoist the constant to transformed data and re-add it as one precomputed term per call. The likelihood runs in its propto form internally; `lp__` still reports the full value to the last ulp. One addition per call replaces a transcendental pass per element per gradient.
2. Keep the current form and only hoist the computation. Bit-identical, smaller win.

The first option needs no policy change and keeps the documented meaning of `target +=`.
